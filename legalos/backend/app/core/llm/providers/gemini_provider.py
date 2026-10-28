"""Gemini provider.

Responsibilities: build requests (text, JSON, schema-constrained, with PDF/image parts),
classify failures into typed errors, retry with backoff, honour the server's `retryDelay` to the second,
fall back to other keys and models when a daily quota is exhausted (and remember that across restarts),
bound every call by a per-request timeout and a total deadline, and throttle per key for free-tier limits.

Written to tolerate older/newer `google-genai` versions: optional config fields are only
sent if the installed SDK supports them.
"""
import hashlib
import json
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
# Persisted to `<llm_cache_dir>/quota_state.json` so a restart (uvicorn --reload!) does not forget it and burn
# calls rediscovering that a key is used up.
_exhausted: dict[tuple[int, str], float] = {}
_exhausted_lock = threading.Lock()
_loaded_from: Optional[str] = None
_DAY = 24 * 3600
_MAX_RATE_WAITS = 6          # per-minute 429s we will wait out per key/model before moving on
_MAX_HINT_WAIT = 120.0       # never sleep longer than this on a server hint


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


def _key_id(key_index: int) -> str:
    """Stable, non-secret id of a key (hash prefix), so persisted state survives a re-ordering of the keys."""
    keys = settings.gemini_keys
    if key_index < len(keys):
        return hashlib.sha256(keys[key_index].encode()).hexdigest()[:10]
    return f"idx{key_index}"


def _state_path() -> str:
    return os.path.join(settings.llm_cache_dir, "quota_state.json")


def _load_state() -> None:
    """Merges the persisted quota memory once per state file (re-read when the cache dir changes, e.g. in tests)."""
    global _loaded_from
    path = _state_path()
    if _loaded_from == path:
        return
    with _exhausted_lock:
        _loaded_from = path
        try:
            with open(path, "r", encoding="utf-8") as f:
                rows = json.load(f).get("exhausted", [])
        except FileNotFoundError:
            return
        except Exception as e:
            logger.warning("could not read quota state %s: %s", path, e)
            return
        by_id = {_key_id(i): i for i in range(_key_count())}
        now = time.time()
        for row in rows:
            idx = by_id.get(row.get("key"))
            if idx is not None and row.get("until", 0) > now and row.get("model"):
                _exhausted.setdefault((idx, row["model"]), float(row["until"]))
        if _exhausted:
            logger.info("restored daily-quota memory for %d key/model pair(s)", len(_exhausted))


def _save_state() -> None:
    """Caller holds `_exhausted_lock`."""
    now = time.time()
    rows = [{"key": _key_id(k), "model": m, "until": t} for (k, m), t in _exhausted.items() if t > now]
    path = _state_path()
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({"version": 1, "exhausted": rows}, f)
        os.replace(tmp, path)
    except Exception as e:
        logger.warning("could not persist quota state: %s", e)


def _is_exhausted(key_index: int, model: str) -> bool:
    _load_state()
    until = _exhausted.get((key_index, model))
    return until is not None and until > time.time()


def seconds_until_daily_reset(now: Optional[float] = None) -> float:
    """Free-tier daily quotas reset at midnight Pacific time. Google's `retryDelay` on a daily-quota 429 is only
    the short per-minute window, so it must not be used as the "come back" time."""
    now = time.time() if now is None else now
    try:
        from datetime import datetime, timedelta
        from zoneinfo import ZoneInfo

        pacific = datetime.fromtimestamp(now, ZoneInfo("America/Los_Angeles"))
        midnight = (pacific + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        return max(60.0, (midnight - pacific).total_seconds())
    except Exception:                                   # no tz database: assume standard time (UTC-8), the safe side
        return max(60.0, _DAY - ((now - 8 * 3600) % _DAY))


def _mark_exhausted(key_index: int, model: str, retry_after: Optional[float] = None) -> None:
    """Skip this key/model until the daily reset (or for `retry_after` seconds when a caller knows better)."""
    _load_state()
    wait = seconds_until_daily_reset() if retry_after is None else retry_after
    with _exhausted_lock:
        _exhausted[(key_index, model)] = time.time() + wait
        _save_state()
    logger.warning("daily quota used up: key #%d model=%s; skipping it for %.0f min", key_index + 1, model, wait / 60)


def quota_status() -> dict:
    """For /health/llm: which key/model pairs are out of daily quota and when they come back."""
    _load_state()
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


def model_output_cap(model: str) -> int:
    """Largest `max_output_tokens` the model accepts; asking for more is a 400. Gemini 1.x / 2.0 stop at 8192."""
    return 8192 if model.startswith(("gemini-1", "gemini-2.0")) else 65536


def _build_config(
    system: str,
    json_mode: bool,
    schema: Optional[Type[BaseModel]],
    temperature: float,
    thinking_budget: Optional[int],
    max_output_tokens: Optional[int],
    model: str = "gemini-2.5-flash",
    timeout: Optional[float] = None,
) -> types.GenerateContentConfig:
    fields = types.GenerateContentConfig.model_fields
    kw: dict = {"temperature": temperature}
    if system:
        kw["system_instruction"] = system
    kw["response_mime_type"] = "application/json" if (json_mode or schema is not None) else "text/plain"
    if schema is not None:
        kw["response_schema"] = schema
    if max_output_tokens and "max_output_tokens" in fields:
        kw["max_output_tokens"] = min(max_output_tokens, model_output_cap(model))
    if thinking_budget is not None and "thinking_config" in fields:
        tf = types.ThinkingConfig.model_fields
        if _is_gen2(model):
            if "thinking_budget" in tf:
                kw["thinking_config"] = types.ThinkingConfig(thinking_budget=thinking_budget)
        elif "thinking_level" in tf:
            # Gemini 3+ cannot switch thinking off and rejects a budget; "low" is the cheapest it offers
            kw["thinking_config"] = types.ThinkingConfig(thinking_level="low" if thinking_budget <= 1024 else "high")
    if "http_options" in fields:
        kw["http_options"] = types.HttpOptions(timeout=int((timeout or settings.llm_timeout_seconds) * 1000))
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


def _wait_for(err: LLMError, transient_attempt: int, rate_wait: int) -> float:
    """Seconds to sleep before retrying `err`. A server hint (`retryDelay`) is honoured to the second plus a
    small margin; without a hint, rate limits wait for a fraction of the 60 s window and other errors back off."""
    hinted = getattr(err, "retry_after", None)
    if hinted:
        return min(hinted + 0.5, _MAX_HINT_WAIT)
    if isinstance(err, LLMQuotaError):
        return min(5.0 * (2 ** (rate_wait - 1)), 60.0)
    return min((2 ** (transient_attempt - 1)) * 2 + random.uniform(0, 1), 30.0)


def _generate_one_model(model: str, contents, config, key_index: int = 0, deadline: Optional[float] = None) -> str:
    """One model on one key, with retries. Per-minute rate limits (429 with a retry hint) are waited out without
    using up the transient-error retries; the gate of this key is paused so queued calls wait as well."""
    max_retries = max(0, settings.llm_max_retries)
    transient = rate_waits = 0
    while True:
        started = time.time()
        try:
            client = _client_for(key_index)
            with get_gate(key_index).slot():
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
                _mark_exhausted(key_index, model)
            rate_limited = isinstance(err, LLMQuotaError) and not daily_quota
            if rate_limited:
                rate_waits += 1
                exhausted_budget = rate_waits > _MAX_RATE_WAITS
            else:
                transient += 1
                exhausted_budget = transient > max_retries
            give_up = not err.retryable or daily_quota or exhausted_budget
            wait = 0.0 if give_up else _wait_for(err, transient, rate_waits)
            out_of_time = not give_up and deadline is not None and time.monotonic() + wait > deadline
            if give_up or out_of_time:
                logger.error("gemini failed model=%s key=#%d kind=%s%s: %s", model, key_index + 1, type(err).__name__,
                             " (out of time)" if out_of_time else "", str(e)[:300])
                raise err from e
            logger.warning("gemini %s on %s key #%d; retrying in %.1fs", type(err).__name__, model, key_index + 1, wait)
            if rate_limited:
                get_gate(key_index).limiter.penalise(wait)      # everyone queued on this key pauses too
            elif isinstance(err, LLMUnavailable):
                reset_client()  # drop possibly-stale connections
            time.sleep(wait)


def _generate(
    prompt: str,
    system: str = "",
    json_mode: bool = False,
    schema: Optional[Type[BaseModel]] = None,
    files: Optional[Sequence[tuple[bytes, str]]] = None,
    temperature: float = 0.2,
    thinking_budget: Optional[int] = None,
    max_output_tokens: Optional[int] = None,
    timeout: Optional[float] = None,
) -> str:
    contents = prompt
    if files:
        contents = [types.Part.from_bytes(data=data, mime_type=mime) for data, mime in files] + [prompt]
    total = max(float(settings.llm_total_timeout_seconds), 2 * (timeout or 0))
    deadline = time.monotonic() + total
    # Order: every key on the primary model first (same quality), then the fallback models.
    last: Optional[LLMError] = None
    skipped = 0
    for i, model in enumerate(_model_chain()):
        config = _build_config(system, json_mode, schema, temperature, thinking_budget, max_output_tokens, model, timeout)
        for key_index in range(_key_count()):
            if _is_exhausted(key_index, model):
                skipped += 1
                continue
            if time.monotonic() >= deadline:
                raise last or LLMUnavailable(f"The AI call did not finish within {total:.0f} s.")
            try:
                return _generate_one_model(model, contents, config, key_index, deadline)
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
        err = LLMQuotaError(f"All {skipped} key/model combinations are out of daily quota.",
                            user_message="The AI service's daily free quota is used up on every configured key and model. It resets within 24 hours.")
        err.daily = True
        raise err
    raise last


# --------------------------------------------------------------------------- public API

def generate_gemini(prompt: str, system: str = "", json_mode: bool = False,
                    temperature: float = 0.2, max_output_tokens: Optional[int] = None,
                    timeout: Optional[float] = None) -> str:
    """Plain text / JSON-mode generation (legacy signature kept for existing callers)."""
    return _generate(prompt=prompt, system=system, json_mode=json_mode, temperature=temperature,
                     max_output_tokens=max_output_tokens, timeout=timeout)


def generate_gemini_structured(
    prompt: str,
    system: str,
    schema: Type[BaseModel],
    files: Optional[Sequence[tuple[bytes, str]]] = None,
    temperature: float = 0.1,
    thinking_budget: Optional[int] = None,
    max_output_tokens: Optional[int] = None,
    timeout: Optional[float] = None,
) -> str:
    """Schema-constrained JSON generation. Returns raw JSON text (caller validates)."""
    return _generate(
        prompt=prompt, system=system, json_mode=True, schema=schema, files=files,
        temperature=temperature, thinking_budget=thinking_budget, max_output_tokens=max_output_tokens,
        timeout=timeout,
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


# --------------------------------------------------------------------------- startup sanity check

_models_check: Optional[dict] = None


def models_check() -> Optional[dict]:
    """The result of the last `check_models`, or None when it has not run."""
    return _models_check


def check_models() -> dict:
    """Lists the models this key can use (a metadata call: it spends no generation quota) and compares them with
    GEMINI_MODEL and the fallbacks. A typo or a retired model otherwise only shows up as a failed analysis."""
    global _models_check
    chain = _model_chain()
    try:
        available: dict[str, Optional[list]] = {}
        for m in _client_for(0).models.list():
            available[str(getattr(m, "name", "")).removeprefix("models/")] = getattr(m, "supported_actions", None)
    except Exception as e:
        err = classify_error(e)
        _models_check = {"checked": False, "kind": type(err).__name__, "message": err.user_message}
        logger.warning("could not list Gemini models (%s); skipping the model sanity check", type(err).__name__)
        return _models_check
    missing = [m for m in chain if m not in available]
    unsupported = [m for m in chain if m in available and available[m] and "generateContent" not in available[m]]
    _models_check = {
        "checked": True, "configured": chain, "missing": missing, "unsupported": unsupported,
        "primary_ok": bool(chain) and chain[0] not in missing and chain[0] not in unsupported,
        "suggestions": sorted(n for n in available if n.startswith("gemini-") and "flash" in n)[:8] if missing else [],
    }
    if missing:
        logger.error("GEMINI_MODEL / fallbacks not available for this key: %s. Models with 'flash': %s",
                     ", ".join(missing), ", ".join(_models_check["suggestions"]) or "none")
    if unsupported:
        logger.error("models that do not support generateContent: %s", ", ".join(unsupported))
    return _models_check
