"""Production hardening of the LLM layer: timeouts, output sizing, repair path, quota memory, rate limits, cache bounds."""
import json
import logging
import os
import time
from types import SimpleNamespace
from typing import List

import pytest
from pydantic import BaseModel

from app.config import settings
from app.core.llm import cache, limiter, llm_client
from app.core.llm.errors import LLMInvalidOutput, LLMQuotaError, LLMUnavailable
from app.core.llm.providers import fake_provider, gemini_provider


class Small(BaseModel):
    value: int


class Item(BaseModel):
    title: str
    quote: str
    risk: str
    page: int


class Big(BaseModel):
    summary: str
    items: List[Item]


class ApiError(Exception):
    def __init__(self, code, message="boom"):
        super().__init__(message)
        self.code = code


# ------------------------------------------------------------------ output sizing and options

def test_max_output_tokens_is_sized_to_the_schema():
    small = llm_client.default_max_output_tokens(Small)
    big = llm_client.default_max_output_tokens(Big)
    assert 1024 <= small < big <= llm_client.MAX_OUTPUT_TOKENS_CEILING
    # thinking headroom: a model that must think needs more room than one told not to
    assert llm_client.default_max_output_tokens(Big, thinking_budget=0) < llm_client.default_max_output_tokens(Big, thinking_budget=8000)


def test_default_cap_and_timeout_reach_the_provider(fake_llm):
    state = fake_llm(lambda c: '{"value": 1}')
    llm_client.generate_structured("p", Small, timeout=45)
    call = state.last
    assert call.max_output_tokens == llm_client.default_max_output_tokens(Small)
    assert call.timeout == 45


def test_explicit_cap_is_respected(fake_llm):
    state = fake_llm(lambda c: '{"value": 1}')
    llm_client.generate_structured("p", Small, max_output_tokens=777)
    assert state.last.max_output_tokens == 777


def test_gemini_caps_are_clamped_per_model():
    assert gemini_provider.model_output_cap("gemini-2.0-flash") == 8192
    assert gemini_provider.model_output_cap("gemini-2.5-flash") == 65536


def test_generate_text_with_options(fake_llm):
    state = fake_llm(lambda c: "plain answer")
    assert llm_client.generate_text("hi", system="s", temperature=0.5, max_output_tokens=300, timeout=9) == "plain answer"
    assert (state.last.temperature, state.last.max_output_tokens, state.last.timeout) == (0.5, 300, 9)


def test_public_api_is_still_there():
    for name in ("generate_structured", "generate_structured_async", "generate_text", "llm_health", "quota_status", "generate"):
        assert callable(getattr(llm_client, name))


# ------------------------------------------------------------------ repair path

def test_trailing_comma_and_raw_newline_are_fixed_without_a_second_call(fake_llm):
    state = fake_llm(lambda c: '```json\n{"value": 4, "label": "line1\nline2",}\n```')

    class WithLabel(BaseModel):
        value: int
        label: str

    out = llm_client.generate_structured("p", WithLabel)
    assert out.value == 4 and out.label == "line1\nline2"
    assert len(state.calls) == 1


def test_repair_makes_exactly_one_extra_call_with_a_bigger_cap_then_gives_up(fake_llm, caplog):
    state = fake_llm(lambda c: '{"value": "x" ' + "y" * 5000)          # always broken (and long)
    with caplog.at_level(logging.WARNING, logger="legalos.llm"):
        with pytest.raises(LLMInvalidOutput) as exc:
            llm_client.generate_structured("p", Small)
    assert len(state.calls) == 2                                        # never loops
    assert state.calls[1].max_output_tokens > state.calls[0].max_output_tokens
    # the raw text is logged and attached, truncated
    assert len(exc.value.raw_excerpt) < 1100 and exc.value.raw_excerpt.startswith('{"value": "x"')
    assert any("raw=" in r.getMessage() for r in caplog.records)


def test_truncated_json_is_not_patched_up_locally(fake_llm):
    answers = iter(['{"value": 1, "label": "cut off', '{"value": 2}'])
    state = fake_llm(lambda c: next(answers))
    assert llm_client.generate_structured("p", Small).value == 2
    assert len(state.calls) == 2


def test_schema_error_becomes_invalid_output_not_validation_error(fake_llm):
    fake_llm(lambda c: '{"wrong": true}')
    with pytest.raises(LLMInvalidOutput):
        llm_client.generate_structured("p", Small)


# ------------------------------------------------------------------ fake provider is feature complete

def test_fake_script_route_and_exceptions(fake_llm):
    fake_provider.script(LLMUnavailable("down"), {"value": 3}, Small(value=4))
    with pytest.raises(LLMUnavailable):
        llm_client.generate_structured("p", Small)
    assert llm_client.generate_structured("p", Small).value == 3
    assert llm_client.generate_structured("p", Small).value == 4
    assert llm_client.generate_structured("p", Small).value == 4        # last item repeats

    fake_provider.set_handler(None)
    fake_provider.route({Small: {"value": 9}, "needle": "text answer"})
    assert llm_client.generate_structured("p", Small).value == 9
    assert llm_client.generate_text("find the needle here") == "text answer"
    assert fake_provider.STATE.latency == 0.0


def test_fake_fails_loudly_without_a_handler():
    from app.core.llm.errors import LLMAuthError
    settings.llm_provider = "fake"
    fake_provider.set_handler(None)
    with pytest.raises(LLMAuthError):
        llm_client.generate_structured("p", Small)


# ------------------------------------------------------------------ daily quota memory

def test_daily_quota_memory_survives_a_restart(monkeypatch):
    monkeypatch.setattr(gemini_provider, "_key_count", lambda: 2)
    gemini_provider._exhausted.clear()
    gemini_provider._mark_exhausted(1, "m1")
    assert os.path.exists(gemini_provider._state_path())
    # simulate a new process: memory empty, nothing loaded yet
    gemini_provider._exhausted.clear()
    gemini_provider._loaded_from = None
    assert gemini_provider._is_exhausted(1, "m1")
    assert not gemini_provider._is_exhausted(0, "m1")
    assert gemini_provider.quota_status()["exhausted"][0]["key"] == 2
    gemini_provider._exhausted.clear()


def test_expired_quota_entries_are_not_restored(monkeypatch):
    monkeypatch.setattr(gemini_provider, "_key_count", lambda: 1)
    os.makedirs(settings.llm_cache_dir, exist_ok=True)
    with open(gemini_provider._state_path(), "w") as f:
        json.dump({"version": 1, "exhausted": [{"key": "idx0", "model": "m1", "until": time.time() - 5}]}, f)
    gemini_provider._exhausted.clear()
    gemini_provider._loaded_from = None
    assert not gemini_provider._is_exhausted(0, "m1")


def test_daily_reset_is_at_pacific_midnight():
    secs = gemini_provider.seconds_until_daily_reset()
    assert 60 <= secs <= 24 * 3600 + 60


# ------------------------------------------------------------------ rate limits queue instead of failing

@pytest.fixture
def gemini(monkeypatch):
    settings.llm_provider = "gemini"
    settings.gemini_model, settings.gemini_fallback_models, settings.llm_max_retries = "m1", "", 1
    gemini_provider._exhausted.clear()
    sleeps: list = []
    # only the provider's own waits are recorded and skipped; the limiter keeps real (short) sleeps
    monkeypatch.setattr(gemini_provider, "time", SimpleNamespace(
        sleep=lambda s: sleeps.append(s), time=time.time, monotonic=time.monotonic))

    def install(script):
        calls = {"n": 0}

        def generate_content(model, contents, config):
            item = script[min(calls["n"], len(script) - 1)]
            calls["n"] += 1
            if isinstance(item, Exception):
                raise item
            return SimpleNamespace(text=item, usage_metadata=None)

        client = SimpleNamespace(models=SimpleNamespace(generate_content=generate_content))
        monkeypatch.setattr(gemini_provider, "_client_for", lambda i: client)
        monkeypatch.setattr(gemini_provider, "_key_count", lambda: 1)
        return calls, sleeps

    yield install
    gemini_provider._exhausted.clear()


def test_per_minute_429_waits_the_exact_retry_delay_and_does_not_use_up_retries(gemini):
    limit = ApiError(429, "RESOURCE_EXHAUSTED: GenerateRequestsPerMinutePerProjectPerModel. Please retry in 0.2s.")
    calls, sleeps = gemini([limit, limit, limit, "finally"])           # 3 rate limits, max_retries is only 1
    assert llm_client.generate("hi") == "finally"
    assert calls["n"] == 4
    assert sleeps == [pytest.approx(0.7)] * 3                           # hint + 0.5 s margin, not exponential backoff


def test_rate_limit_pauses_the_whole_key_gate(gemini):
    calls, _ = gemini([ApiError(429, "RESOURCE_EXHAUSTED PerMinute retry in 0.2s"), "ok"])
    llm_client.generate("hi")
    assert limiter.get_gate(0).limiter._blocked_until > 0


def test_transient_errors_still_use_the_retry_budget(gemini):
    calls, _ = gemini([ApiError(503), ApiError(503), "never reached"])
    with pytest.raises(LLMUnavailable):
        llm_client.generate("hi")
    assert calls["n"] == 2                                             # 1 try + max_retries(1)


def test_a_hint_beyond_the_total_deadline_fails_fast(gemini):
    settings.llm_total_timeout_seconds = 5
    calls, sleeps = gemini([ApiError(429, "RESOURCE_EXHAUSTED PerMinute retry in 60s"), "late"])
    with pytest.raises(LLMQuotaError):
        llm_client.generate("hi")
    assert calls["n"] == 1 and not sleeps


def test_gate_is_per_key_and_reports_queue_depth():
    assert limiter.get_gate(0) is not limiter.get_gate(1)
    assert limiter.get_gate(0) is limiter.get_gate(0)
    stats = limiter.gate_stats()
    assert {"waiting", "in_flight", "keys"} <= set(stats) and set(stats["keys"]) == {"key1", "key2"}


def test_rate_limiter_queues_a_burst_instead_of_failing():
    rl = limiter.RateLimiter(rpm=2, window=0.3)
    started = time.monotonic()
    waits = [rl.acquire() for _ in range(3)]
    assert waits[0] == waits[1] == 0 and waits[2] > 0.15               # third call waited for the window, did not fail
    assert time.monotonic() - started >= 0.25


def test_penalise_blocks_everyone_for_the_hinted_time():
    rl = limiter.RateLimiter(rpm=100, window=60)
    rl.penalise(0.25)
    started = time.monotonic()
    rl.acquire()
    assert time.monotonic() - started >= 0.2


def test_concurrency_cap_is_per_gate_and_counts_waiters():
    gate = limiter.LLMGate(max_concurrency=1, rpm=1000)
    with gate.slot():
        assert gate.stats()["in_flight"] == 1
    assert gate.stats() == {"waiting": 0, "in_flight": 0, "max_concurrency": 1, "rpm": 1000}


# ------------------------------------------------------------------ cache: bounded, LRU, stats

def _put(i):
    key = cache.make_key(i=i)
    cache.put(key, "x" * 100, "m")
    return key


def test_cache_evicts_least_recently_used_when_over_the_entry_cap():
    settings.llm_cache_enabled = True
    settings.llm_cache_max_entries = 5
    keys = []
    for i in range(5):
        keys.append(_put(i))
        os.utime(cache._path(keys[-1]), (1000 + i, 1000 + i))          # distinct ages: key 0 oldest
    assert cache.get(keys[0]) == "x" * 100                              # a hit refreshes key 0 ...
    _put(99)                                                            # ... then overflow
    stats = cache.cache_stats()
    assert stats["entries"] <= 5 and stats["evictions"] >= 1
    assert cache.get(keys[0]) is not None                               # the recently used one survived
    assert cache.get(keys[1]) is None                                   # the least recently used one went


def test_cache_evicts_by_size():
    settings.llm_cache_enabled = True
    settings.llm_cache_max_entries = 10_000
    settings.llm_cache_max_mb = 1
    big = "y" * 400_000
    for i in range(5):
        cache.put(cache.make_key(big=i), big, "m")
    stats = cache.cache_stats()
    assert stats["size_mb"] <= 1.0 and stats["evictions"] >= 1


def test_eviction_never_touches_the_quota_state_file(monkeypatch):
    settings.llm_cache_enabled = True
    settings.llm_cache_max_entries = 2
    monkeypatch.setattr(gemini_provider, "_key_count", lambda: 1)
    gemini_provider._exhausted.clear()
    gemini_provider._mark_exhausted(0, "m1")
    for i in range(6):
        _put(i)
    assert os.path.exists(gemini_provider._state_path())
    assert cache.cache_stats()["entries"] <= 2
    gemini_provider._exhausted.clear()


def test_cache_stats_shape_and_hit_rate():
    settings.llm_cache_enabled = True
    before = cache.cache_stats()
    k = _put(123)
    cache.get(k)
    cache.get(cache.make_key(missing=1))
    after = cache.cache_stats()
    assert after["hits"] == before["hits"] + 1 and after["misses"] == before["misses"] + 1
    assert {"entries", "size_mb", "max_entries", "max_mb", "hit_rate", "puts", "evictions"} <= set(after)


def test_health_includes_cache_queue_and_model_check_fields(fake_llm):
    h = llm_client.llm_health()
    assert h["ok"] and "entries" in h["cache"] and "waiting" in h["queue"]


# ------------------------------------------------------------------ model sanity check at startup

def test_model_check_flags_a_typo_and_suggests_models(monkeypatch):
    settings.gemini_model, settings.gemini_fallback_models = "gemini-2.5-flsh", "gemini-3.5-flash"
    models = [SimpleNamespace(name="models/gemini-3.5-flash", supported_actions=["generateContent"]),
              SimpleNamespace(name="models/gemini-2.5-flash", supported_actions=["generateContent"]),
              SimpleNamespace(name="models/embedding-001", supported_actions=["embedContent"])]
    client = SimpleNamespace(models=SimpleNamespace(list=lambda: iter(models)))
    monkeypatch.setattr(gemini_provider, "_client_for", lambda i: client)
    result = gemini_provider.check_models()
    assert result["checked"] and result["missing"] == ["gemini-2.5-flsh"] and not result["primary_ok"]
    assert "gemini-2.5-flash" in result["suggestions"]
    assert gemini_provider.models_check() is result


def test_model_check_is_harmless_when_listing_fails(monkeypatch):
    def boom():
        raise ApiError(503, "unavailable")

    client = SimpleNamespace(models=SimpleNamespace(list=boom))
    monkeypatch.setattr(gemini_provider, "_client_for", lambda i: client)
    result = gemini_provider.check_models()
    assert result["checked"] is False and result["kind"] == "LLMUnavailable"
