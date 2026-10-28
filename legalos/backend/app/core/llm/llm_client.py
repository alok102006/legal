"""Single entrypoint for every LLM call.

- `generate` / `generate_async`: plain text or JSON-mode (legacy API, unchanged signature).
- `generate_text` / `generate_text_async`: plain text with options (temperature, token cap, timeout).
- `generate_structured` / `generate_structured_async`: schema-validated results, one automatic
  repair attempt, optional on-disk cache, optional PDF/image parts, per-call timeout, output cap sized to the schema.
- `llm_health`: real status of the configured provider (used by /health and the UI).
- `quota_status`: which key/model pairs are out of daily quota (re-exported from the Gemini provider).

Failures raise typed errors from `app.core.llm.errors`; callers must handle them explicitly
(mark the job failed / retryable) and never substitute a "safe" default result.

Repair path (never loops): a locally-fixable answer (code fences, trailing commas, raw newlines in strings) is
fixed without a model call; otherwise exactly ONE repair call is made, with a larger output cap in case the first
answer was cut off. If that is still invalid the call raises `LLMInvalidOutput` carrying the start of the raw text.
"""
import asyncio
import hashlib
import json
import logging
import re
import time
from typing import Any, Optional, Sequence, Type, TypeVar

from pydantic import BaseModel, ValidationError

from app.config import settings
from app.core.llm import cache as llm_cache
from app.core.llm import limiter
from app.core.llm.errors import LLMBadRequest, LLMInvalidOutput
from app.core.llm.providers.fake_provider import generate_fake
from app.core.llm.providers.gemini_provider import (  # noqa: F401  (quota_status is part of this module's API)
    USAGE,
    check_gemini,
    generate_gemini,
    generate_gemini_structured,
    models_check,
    quota_status,
)
from app.core.llm.providers.local_provider import generate_local

logger = logging.getLogger("legalos.llm")

T = TypeVar("T", bound=BaseModel)

RAW_LOG_CHARS = 1000          # how much of a bad model answer goes into the log / the exception
MAX_OUTPUT_TOKENS_CEILING = 65536


# ------------------------------------------------------------------ plain text API

def generate(prompt: str, system: str = "", json_mode: bool = False, workspace: str = "") -> str:
    provider = settings.llm_provider.lower().strip()
    logger.info("LLM call workspace=%r provider=%s json_mode=%s", workspace, provider, json_mode)
    start = time.time()
    try:
        if provider == "gemini":
            response = generate_gemini(prompt, system=system, json_mode=json_mode)
        elif provider == "local":
            response = generate_local(prompt, system=system, json_mode=json_mode)
        elif provider == "fake":
            response = generate_fake(prompt, system=system, json_mode=json_mode)
        else:
            raise ValueError(f"Unsupported LLM_PROVIDER: {provider}")
        logger.info("LLM call ok provider=%s elapsed=%.2fs", provider, time.time() - start)
        return response
    except Exception as e:
        logger.error("LLM call failed provider=%s elapsed=%.2fs error=%s", provider, time.time() - start, str(e)[:300])
        raise


async def generate_async(prompt: str, system: str = "", json_mode: bool = False, workspace: str = "") -> str:
    """Runs the blocking call in a worker thread so the event loop is never blocked."""
    return await asyncio.to_thread(generate, prompt=prompt, system=system, json_mode=json_mode, workspace=workspace)


def generate_text(
    prompt: str,
    system: str = "",
    workspace: str = "",
    temperature: float = 0.2,
    max_output_tokens: Optional[int] = None,
    timeout: Optional[float] = None,
) -> str:
    """Free-form text answer. `timeout` bounds one HTTP request (seconds); the total deadline still applies."""
    provider = settings.llm_provider.lower().strip()
    logger.info("LLM text call workspace=%r provider=%s", workspace, provider)
    if provider == "gemini":
        return generate_gemini(prompt, system=system, temperature=temperature,
                               max_output_tokens=max_output_tokens, timeout=timeout)
    if provider == "fake":
        return generate_fake(prompt, system=system, temperature=temperature,
                             max_output_tokens=max_output_tokens, timeout=timeout)
    if provider == "local":
        return generate_local(prompt, system=system, json_mode=False)
    raise ValueError(f"Unsupported LLM_PROVIDER: {provider}")


async def generate_text_async(*args, **kwargs) -> str:
    return await asyncio.to_thread(generate_text, *args, **kwargs)


# ------------------------------------------------------------------ output sizing

_STRING_TOKENS, _SCALAR_TOKENS, _OBJECT_OVERHEAD = 60, 10, 6
_ASSUMED_ITEMS = 8             # a list in the schema is assumed to hold this many items
_MAX_SCHEMA_DEPTH = 6


def _slots(node: Any, defs: dict, depth: int = 0) -> int:
    """Rough number of output tokens a JSON-schema node can produce (field names + values)."""
    if depth > _MAX_SCHEMA_DEPTH or not isinstance(node, dict):
        return _SCALAR_TOKENS
    if "$ref" in node:
        return _slots(defs.get(node["$ref"].rsplit("/", 1)[-1], {}), defs, depth + 1)
    for union in ("anyOf", "oneOf", "allOf"):
        if union in node:
            return max(_slots(n, defs, depth + 1) for n in node[union]) if node[union] else _SCALAR_TOKENS
    kind = node.get("type")
    if kind == "object" or "properties" in node:
        props = node.get("properties") or {}
        return _OBJECT_OVERHEAD + sum(_SCALAR_TOKENS // 2 + _slots(v, defs, depth + 1) for v in props.values())
    if kind == "array":
        return _ASSUMED_ITEMS * _slots(node.get("items", {}), defs, depth + 1)
    if kind == "string" and "enum" not in node:
        return _STRING_TOKENS
    return _SCALAR_TOKENS


def default_max_output_tokens(schema: Type[BaseModel], thinking_budget: Optional[int] = None) -> int:
    """Output cap sized to what the schema can produce, so a verbose list cannot be cut mid-JSON and a tiny
    schema does not get a huge cap. Gemini counts thinking tokens against the cap, so headroom for them is added."""
    raw = schema.model_json_schema()
    needed = _slots(raw, raw.get("$defs", {}))
    thinking = 4096 if thinking_budget is None or thinking_budget < 0 else max(thinking_budget, 1024)
    return int(min(MAX_OUTPUT_TOKENS_CEILING, max(1024, needed) + thinking))


# ------------------------------------------------------------------ structured API

_FENCE = re.compile(r"^```[a-zA-Z]*\s*|\s*```$")
_TRAILING_COMMA = re.compile(r",(\s*[}\]])")


def extract_json_text(raw: str) -> str:
    """Strips code fences / chatter around a JSON payload."""
    text = _FENCE.sub("", raw.strip()).strip()
    if text[:1] in "{[":
        return text
    starts = [i for i in (text.find("{"), text.find("[")) if i != -1]
    if not starts:
        return text
    start = min(starts)
    end = max(text.rfind("}"), text.rfind("]"))
    return text[start:end + 1] if end > start else text


def repair_json_text(raw: str) -> Optional[str]:
    """Deterministic fixes for the usual almost-JSON a model emits: trailing commas and raw control characters
    inside strings. Returns None when nothing could be fixed. Truncated output is deliberately NOT patched up (that
    would silently invent the missing tail); it goes to the model repair call instead."""
    text = extract_json_text(raw)
    candidate = _TRAILING_COMMA.sub(r"\1", text)
    try:
        return json.dumps(json.loads(candidate, strict=False), ensure_ascii=False)
    except ValueError:
        return None


def _validate(raw: str, schema: Type[T]) -> T:
    try:
        return schema.model_validate_json(extract_json_text(raw))
    except (ValidationError, ValueError):
        fixed = repair_json_text(raw)
        if fixed is None:
            raise
        return schema.model_validate_json(fixed)


def _excerpt(raw: str) -> str:
    return raw[:RAW_LOG_CHARS] + (f"...[+{len(raw) - RAW_LOG_CHARS} chars]" if len(raw) > RAW_LOG_CHARS else "")


def _call_structured(
    prompt: str,
    system: str,
    schema: Type[BaseModel],
    files: Optional[Sequence[tuple[bytes, str]]],
    temperature: float,
    thinking_budget: Optional[int],
    max_output_tokens: Optional[int],
    timeout: Optional[float],
) -> str:
    provider = settings.llm_provider.lower().strip()
    if provider == "gemini":
        return generate_gemini_structured(
            prompt, system, schema, files=files, temperature=temperature,
            thinking_budget=thinking_budget, max_output_tokens=max_output_tokens, timeout=timeout,
        )
    if provider == "fake":
        return generate_fake(prompt, system=system, json_mode=True, schema=schema, files=files,
                             temperature=temperature, max_output_tokens=max_output_tokens,
                             thinking_budget=thinking_budget, timeout=timeout)
    if provider == "local":
        if files:
            raise LLMBadRequest("The local provider does not support file inputs.")
        return generate_local(prompt, system=system, json_mode=True)
    raise ValueError(f"Unsupported LLM_PROVIDER: {provider}")


def generate_structured(
    prompt: str,
    schema: Type[T],
    system: str = "",
    workspace: str = "",
    files: Optional[Sequence[tuple[bytes, str]]] = None,
    temperature: float = 0.1,
    thinking_budget: Optional[int] = None,
    max_output_tokens: Optional[int] = None,
    use_cache: bool = True,
    prompt_version: str = "v1",
    timeout: Optional[float] = None,
) -> T:
    """
    Returns a validated `schema` instance or raises an LLMError.

    `max_output_tokens` defaults to a size derived from the schema (see `default_max_output_tokens`).
    `timeout` is the per-request limit in seconds (default: LLM_TIMEOUT_SECONDS); the whole call, retries
    and fallbacks included, is bounded by LLM_TOTAL_TIMEOUT_SECONDS.
    At most one model repair call is made if the answer does not validate (after free local fixes).
    """
    provider = settings.llm_provider.lower().strip()
    caching = use_cache and provider != "fake"
    key = None
    if caching:
        key = llm_cache.make_key(
            provider=provider, model=settings.gemini_model, system=system, prompt=prompt,
            schema=schema.model_json_schema(), temperature=temperature, version=prompt_version,
            files=[hashlib.sha256(d).hexdigest() + m for d, m in (files or [])],
        )
        hit = llm_cache.get(key)
        if hit:
            try:
                logger.info("LLM cache hit workspace=%r schema=%s", workspace, schema.__name__)
                return _validate(hit, schema)
            except (ValidationError, ValueError):
                pass  # stale/incompatible entry: fall through and regenerate

    cap = max_output_tokens or default_max_output_tokens(schema, thinking_budget)
    logger.info("LLM structured call workspace=%r schema=%s provider=%s max_out=%d", workspace, schema.__name__, provider, cap)
    raw = _call_structured(prompt, system, schema, files, temperature, thinking_budget, cap, timeout)
    try:
        result = _validate(raw, schema)
    except (ValidationError, ValueError) as first_err:
        logger.warning("LLM output failed validation (%s); one repair attempt. raw=%r", str(first_err)[:200], _excerpt(raw))
        repair_prompt = (
            f"{prompt}\n\n---\nYour previous answer was not valid for the required schema.\n"
            f"Validation error: {str(first_err)[:600]}\n"
            f"Previous answer (truncated):\n{raw[:3000]}\n\n"
            f"Return ONLY a corrected, COMPLETE JSON object that satisfies the schema."
        )
        bigger = min(cap * 2, MAX_OUTPUT_TOKENS_CEILING)       # the first answer may simply have been cut off
        raw = _call_structured(repair_prompt, system, schema, files, 0.0, thinking_budget, bigger, timeout)
        try:
            result = _validate(raw, schema)
        except (ValidationError, ValueError) as second_err:
            logger.error("LLM output invalid after repair schema=%s workspace=%r error=%s raw=%r",
                         schema.__name__, workspace, str(second_err)[:300], _excerpt(raw))
            err = LLMInvalidOutput(f"Output invalid after repair: {str(second_err)[:300]}")
            err.raw_excerpt = _excerpt(raw)
            raise err from second_err

    if key:
        llm_cache.put(key, raw, settings.gemini_model)
    return result


async def generate_structured_async(*args, **kwargs):
    return await asyncio.to_thread(generate_structured, *args, **kwargs)


# ------------------------------------------------------------------ health

def llm_health(force: bool = False) -> dict:
    """Provider status plus the operational numbers /health/llm shows: usage, cache, per-key queue, model check."""
    provider = settings.llm_provider.lower().strip()
    extras = {"usage": dict(USAGE), "cache": llm_cache.cache_stats(), "queue": limiter.gate_stats()}
    if provider == "gemini":
        status = check_gemini(force=force)
        return {"provider": "gemini", **status, **extras, "quota": quota_status(), "models": models_check()}
    return {"provider": provider, "ok": provider == "fake", **extras}

