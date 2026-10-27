"""Gemini provider.

Responsibilities: build requests (text, JSON, schema-constrained, with PDF/image parts),
classify failures into typed errors, retry with backoff, honour server retry hints,
fall back to cheaper models when quota is exhausted, and throttle for free-tier limits.

Written to tolerate older/newer `google-genai` versions: optional config fields are only
sent if the installed SDK supports them.
"""
import logging
import os
import random
import re
import threading
import time
from typing import Optional, Sequence, Type

from google import genai
from google.genai import types
from pydantic import BaseModel

from app.config import settings
from app.core.llm.errors import (
    LLMAuthError,
    LLMBadRequest,
    LLMError,
    LLMQuotaError,
    LLMUnavailable,
)
from app.core.llm.limiter import get_gate

logger = logging.getLogger("legalos.llm.gemini")

_client: Optional[genai.Client] = None
_clients: dict[int, genai.Client] = {}          # extra keys, by index into settings.gemini_keys
_client_lock = threading.Lock()

# Simple in-process usage counters (exposed via /health/llm).
USAGE = {"calls": 0, "errors": 0, "prompt_tokens": 0, "output_tokens": 0}
_usage_lock = threading.Lock()

# (key index, model) -> epoch seconds when its daily free-tier quota resets. Skipped until then.
_exhausted: dict[tuple[int, str], float] = {}
_DAY = 24 * 3600


def get_gemini_client(force_new: bool = False) -> genai.Client:
    global _client
    with _client_lock:
        if _client is None or force_new:
            api_key = settings.gemini_api_key or os.environ.get("GEMINI_API_KEY")
            if not api_key:
                raise LLMAuthError("GEMINI_API_KEY is not set.")
            _client = genai.Client(api_key=api_key)
        return _client


def _client_for(key_index: int) -> genai.Client:
    if key_index == 0:
        return get_gemini_client()
    with _client_lock:
        c = _clients.get(key_index)
        if c is None:
            c = _clients[key_index] = genai.Client(api_key=settings.gemini_keys[key_index])
        return c


def _key_count() -> int:
    return max(1, len(settings.gemini_keys))


def reset_client() -> None:
    global _client
    with _client_lock:
        _client = None
        _clients.clear()


def _is_exhausted(key_index: int, model: str) -> bool:
    until = _exhausted.get((key_index, model))
    return until is not None and until > time.time()


def _mark_exhausted(key_index: int, model: str, retry_after: Optional[float]) -> None:
    _exhausted[(key_index, model)] = time.time() + (retry_after if retry_after else _DAY)
    logger.warning("daily quota used up: key #%d model=%s; skipping it for %.0f min", key_index + 1, model,
                   (retry_after or _DAY) / 60)


def quota_status() -> dict:
    """For /health/llm: which key/model pairs are out of daily quota and when they come back."""
    now = time.time()
    out = [{"key": k + 1, "model": m, "resets_in_minutes": int((t - now) / 60)} for (k, m), t in _exhausted.items() if t > now]
    return {"keys": _key_count(), "models": _model_chain(), "exhausted": out}


# --------------------------------------------------------------------------- errors

_TRANSIENT_HINTS = (
    "wsarecv", "connection was forcibly closed", "connection reset", "timed out", "timeout",
    "remote host", "connection aborted", "broken pipe", "econnreset", "stream reading error",
    "server disconnected", "temporarily unavailable", "overloaded",
)


def _retry_after_seconds(text: str) -> Optional[float]:
    m = re.search(r"retry in\s*([0-9]+(?:\.[0-9]+)?)\s*s", text, re.I)
    if not m:
        m = re.search(r"retryDelay['\"]?\s*[:=]\s*['\"]?([0-9]+(?:\.[0-9]+)?)\s*s", text, re.I)
    return float(m.group(1)) if m else None


def classify_error(e: BaseException) -> LLMError:
    """Maps any SDK / network exception to a typed LLMError."""
    if isinstance(e, LLMError):
        return e
    code = getattr(e, "code", None)
    if code is None:
        code = getattr(e, "status_code", None)
    text = str(e)
    low = text.lower()

    if code in (401, 403) or "api key not valid" in low or "unauthenticated" in low or "permission_denied" in low:
        return LLMAuthError(text)
    if code == 429 or "resource_exhausted" in low:
        err = LLMQuotaError(text)
        err.retry_after = _retry_after_seconds(text)  # type: ignore[attr-defined]
        err.daily = "perday" in low.replace(" ", "").replace("_", "")  # type: ignore[attr-defined]
        return err
    if code == 404 or ("model" in low and "not found" in low):
        err = LLMBadRequest(text, user_message="The configured AI model is not available for this key.")
        err.model_missing = True  # type: ignore[attr-defined]
        return err
    if code in (500, 502, 503, 504) or isinstance(e, (TimeoutError, ConnectionError)) or any(h in low for h in _TRANSIENT_HINTS):
        return LLMUnavailable(text)
    if code == 400:
        return LLMBadRequest(text)
    return LLMUnavailable(text)


# --------------------------------------------------------------------------- requests

def _model_chain() -> list[str]:
    chain: list[str] = []
    for m in [settings.gemini_model, *settings.fallback_models]:
        if m and m not in chain:
            chain.append(m)
    return chain


def _is_gen2(model: str) -> bool:
    return model.startswith("gemini-2") or model.startswith("gemini-1")


def _build_config(
    system: str,
    json_mode: bool,
    schema: Optional[Type[BaseModel]],
    temperature: float,
    thinking_budget: Optional[int],
    max_output_tokens: Optional[int],
    model: str = "gemini-2.5-flash",
) -> types.GenerateContentConfig:
    fields = types.GenerateContentConfig.model_fields
    kw: dict = {"temperature": temperature}
    if system:
        kw["system_instruction"] = system
    kw["response_mime_type"] = "application/json" if (json_mode or schema is not None) else "text/plain"
    if schema is not None:
        kw["response_schema"] = schema
    if max_output_tokens and "max_output_tokens" in fields:
        kw["max_output_tokens"] = max_output_tokens
    if thinking_budget is not None and "thinking_config" in fields:
        tf = types.ThinkingConfig.model_fields
        if _is_gen2(model):
            if "thinking_budget" in tf:
                kw["thinking_config"] = types.ThinkingConfig(thinking_budget=thinking_budget)
        elif "thinking_level" in tf:
            # Gemini 3+ cannot switch thinking off and rejects a budget; "low" is the cheapest it offers
            kw["thinking_config"] = types.ThinkingConfig(thinking_level="low" if thinking_budget <= 1024 else "high")
    if "http_options" in fields:
        kw["http_options"] = types.HttpOptions(timeout=settings.llm_timeout_seconds * 1000)
    return types.GenerateContentConfig(**kw)


def _record_usage(resp, model: str, elapsed: float) -> None:
    um = getattr(resp, "usage_metadata", None)
    p = getattr(um, "prompt_token_count", 0) or 0
    o = getattr(um, "candidates_token_count", 0) or 0
    with _usage_lock:
        USAGE["calls"] += 1
        USAGE["prompt_tokens"] += p
        USAGE["output_tokens"] += o
    logger.info("gemini ok model=%s elapsed=%.2fs prompt_tokens=%s output_tokens=%s", model, elapsed, p, o)


def _extract_text(resp) -> str:
    text = None
    try:
        text = resp.text
    except Exception:
        text = None
    if text:
        return text
    fb = getattr(resp, "prompt_feedback", None)
    block = getattr(fb, "block_reason", None) if fb else None
    if block:
        raise LLMBadRequest(f"Request blocked by safety filter: {block}",
                            user_message="The AI declined to process this content.")
    raise LLMUnavailable("Gemini returned an empty response.")


def _generate_one_model(model: str, contents, config, key_index: int = 0) -> str:
    max_retries = max(0, settings.llm_max_retries)
    for attempt in range(max_retries + 1):
        started = time.time()
        try:
            client = _client_for(key_index)
            with get_gate().slot():
                resp = client.models.generate_content(model=model, contents=contents, config=config)
            text = _extract_text(resp)
            _record_usage(resp, model, time.time() - started)
            return text
        except Exception as e:
            err = classify_error(e)
            with _usage_lock:
                USAGE["errors"] += 1
            daily_quota = isinstance(err, LLMQuotaError) and getattr(err, "daily", False)
            if daily_quota:
                _mark_exhausted(key_index, model, getattr(err, "retry_after", None))
            if not err.retryable or daily_quota or attempt >= max_retries:
                logger.error("gemini failed model=%s key=#%d attempt=%d kind=%s: %s",
                             model, key_index + 1, attempt + 1, type(err).__name__, str(e)[:300])
                raise err from e
            hinted = getattr(err, "retry_after", None)
            wait = min(hinted + 1, 65) if hinted else min((2 ** attempt) * 2 + random.uniform(0, 1), 30)
            logger.warning("gemini transient %s on %s (attempt %d/%d); retrying in %.1fs",
                           type(err).__name__, model, attempt + 1, max_retries + 1, wait)
            if isinstance(err, LLMUnavailable):
                reset_client()  # drop possibly-stale connections
            time.sleep(wait)
    raise LLMUnavailable("retry loop exited unexpectedly")  # pragma: no cover


def _generate(
    prompt: str,
    system: str = "",
    json_mode: bool = False,
    schema: Optional[Type[BaseModel]] = None,
    files: Optional[Sequence[tuple[bytes, str]]] = None,
    temperature: float = 0.2,
    thinking_budget: Optional[int] = None,
    max_output_tokens: Optional[int] = None,
) -> str:
    contents = prompt
    if files:
        contents = [types.Part.from_bytes(data=data, mime_type=mime) for data, mime in files] + [prompt]
    # Order: every key on the primary model first (same quality), then the fallback models.
    last: Optional[LLMError] = None
    skipped = 0
    for i, model in enumerate(_model_chain()):
        config = _build_config(system, json_mode, schema, temperature, thinking_budget, max_output_tokens, model)
        for key_index in range(_key_count()):
            if _is_exhausted(key_index, model):
                skipped += 1
                continue
            try:
                return _generate_one_model(model, contents, config, key_index)
            except (LLMQuotaError, LLMUnavailable) as e:
                last = e
                logger.warning("model %s key #%d exhausted/unavailable (%s); trying the next key or model",
                               model, key_index + 1, type(e).__name__)
            except LLMBadRequest as e:
                if getattr(e, "model_missing", False):
                    last = e
                    logger.warning("model %s not available for this key; trying next fallback if any", model)
                    break                                   # a missing model is missing for every key
                if i > 0 and "blocked" not in str(e).lower():
                    last = e                                # a fallback model rejecting our request shape: try the next
                    logger.warning("fallback model %s rejected the request: %s", model, str(e)[:200])
                    break
                raise
    if last is None:
        raise LLMQuotaError(f"All {skipped} key/model combinations are out of daily quota.",
                            user_message="The AI service's daily free quota is used up on every configured key and model. It resets within 24 hours.")
    raise last


# --------------------------------------------------------------------------- public API

def generate_gemini(prompt: str, system: str = "", json_mode: bool = False) -> str:
    """Plain text / JSON-mode generation (legacy signature kept for existing callers)."""
    return _generate(prompt=prompt, system=system, json_mode=json_mode)


def generate_gemini_structured(
    prompt: str,
    system: str,
    schema: Type[BaseModel],
    files: Optional[Sequence[tuple[bytes, str]]] = None,
    temperature: float = 0.1,
    thinking_budget: Optional[int] = None,
    max_output_tokens: Optional[int] = None,
) -> str:
    """Schema-constrained JSON generation. Returns raw JSON text (caller validates)."""
    return _generate(
        prompt=prompt, system=system, json_mode=True, schema=schema, files=files,
        temperature=temperature, thinking_budget=thinking_budget, max_output_tokens=max_output_tokens,
    )


_health_cache: dict = {"at": 0.0, "value": None}


def check_gemini(force: bool = False) -> dict:
    """Cheap key/model validity check (no generation quota used). Cached for 60 s."""
    now = time.time()
    if not force and _health_cache["value"] is not None and now - _health_cache["at"] < 60:
        return _health_cache["value"]
    result: dict
    try:
        client = get_gemini_client(force_new=True)
        client.models.get(model=settings.gemini_model)
        result = {"ok": True, "model": settings.gemini_model}
    except Exception as e:
        err = classify_error(e)
        result = {"ok": False, "model": settings.gemini_model,
                  "kind": type(err).__name__, "message": err.user_message}
    _health_cache.update(at=now, value=result)
    return result
