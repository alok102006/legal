"""Single entrypoint for every LLM call.

- `generate` / `generate_async`: plain text or JSON-mode (legacy API, unchanged signature).
- `generate_structured` / `generate_structured_async`: schema-validated results, one automatic
  repair attempt, optional on-disk cache, optional PDF/image parts.
- `llm_health`: real status of the configured provider (used by /health and the UI).

Failures raise typed errors from `app.core.llm.errors`; callers must handle them explicitly
(mark the job failed / retryable) and never substitute a "safe" default result.
"""
import asyncio
import hashlib
import json
import logging
import re
import time
from typing import Optional, Sequence, Type, TypeVar

from pydantic import BaseModel, ValidationError

from app.config import settings
from app.core.llm import cache as llm_cache
from app.core.llm.errors import LLMBadRequest, LLMError, LLMInvalidOutput
from app.core.llm.providers.fake_provider import generate_fake
from app.core.llm.providers.gemini_provider import (
    USAGE,
    quota_status,
    check_gemini,
    generate_gemini,
    generate_gemini_structured,
)
from app.core.llm.providers.local_provider import generate_local

logger = logging.getLogger("legalos.llm")

T = TypeVar("T", bound=BaseModel)


# ------------------------------------------------------------------ legacy text API

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


# ------------------------------------------------------------------ structured API

_FENCE = re.compile(r"^```[a-zA-Z]*\s*|\s*```$")


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


def _validate(raw: str, schema: Type[T]) -> T:
    return schema.model_validate_json(extract_json_text(raw))


def _call_structured(
    prompt: str,
    system: str,
    schema: Type[BaseModel],
    files: Optional[Sequence[tuple[bytes, str]]],
    temperature: float,
    thinking_budget: Optional[int],
    max_output_tokens: Optional[int],
) -> str:
    provider = settings.llm_provider.lower().strip()
    if provider == "gemini":
        return generate_gemini_structured(
            prompt, system, schema, files=files, temperature=temperature,
            thinking_budget=thinking_budget, max_output_tokens=max_output_tokens,
        )
    if provider == "fake":
        return generate_fake(prompt, system=system, json_mode=True, schema=schema, files=files)
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
) -> T:
    """
    Returns a validated `schema` instance or raises an LLMError.
    One repair attempt is made if the first answer does not validate.
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

    logger.info("LLM structured call workspace=%r schema=%s provider=%s", workspace, schema.__name__, provider)
    raw = _call_structured(prompt, system, schema, files, temperature, thinking_budget, max_output_tokens)
    try:
        result = _validate(raw, schema)
    except (ValidationError, ValueError) as first_err:
        logger.warning("LLM output failed validation (%s); attempting repair", str(first_err)[:200])
        repair_prompt = (
            f"{prompt}\n\n---\nYour previous answer was not valid for the required schema.\n"
            f"Validation error: {str(first_err)[:600]}\n"
            f"Previous answer (truncated):\n{raw[:3000]}\n\n"
            f"Return ONLY a corrected JSON object that satisfies the schema."
        )
        raw = _call_structured(repair_prompt, system, schema, files, 0.0, thinking_budget, max_output_tokens)
        try:
            result = _validate(raw, schema)
        except (ValidationError, ValueError) as second_err:
            raise LLMInvalidOutput(f"Output invalid after repair: {str(second_err)[:300]}") from second_err

    if key:
        llm_cache.put(key, raw, settings.gemini_model)
    return result


async def generate_structured_async(*args, **kwargs):
    return await asyncio.to_thread(generate_structured, *args, **kwargs)


# ------------------------------------------------------------------ health

def llm_health(force: bool = False) -> dict:
    provider = settings.llm_provider.lower().strip()
    if provider == "gemini":
        status = check_gemini(force=force)
        return {"provider": "gemini", **status, "usage": dict(USAGE), "quota": quota_status()}
    return {"provider": provider, "ok": provider == "fake", "usage": dict(USAGE)}
