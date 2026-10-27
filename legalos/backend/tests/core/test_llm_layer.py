import json
from types import SimpleNamespace

import pytest
from pydantic import BaseModel

from app.config import settings
from app.core.llm import cache, llm_client
from app.core.llm.errors import (
    LLMAuthError, LLMBadRequest, LLMInvalidOutput, LLMQuotaError, LLMUnavailable,
)
from app.core.llm.providers import gemini_provider


class ApiError(Exception):
    def __init__(self, code, message="boom"):
        super().__init__(message)
        self.code = code


class Answer(BaseModel):
    value: int
    label: str


def _fake_client(script):
    """script: list of items; Exception instances are raised, anything else is returned as resp.text."""
    calls = {"models": [], "n": 0}

    def generate_content(model, contents, config):
        calls["models"].append(model)
        item = script[min(calls["n"], len(script) - 1)]
        calls["n"] += 1
        if isinstance(item, Exception):
            raise item
        return SimpleNamespace(text=item, usage_metadata=None)

    client = SimpleNamespace(models=SimpleNamespace(generate_content=generate_content))
    return client, calls


@pytest.fixture
def gemini(monkeypatch):
    settings.llm_provider = "gemini"
    settings.gemini_model = "m1"
    settings.gemini_fallback_models = "m2"
    settings.llm_max_retries = 2
    monkeypatch.setattr(gemini_provider.time, "sleep", lambda s: None)
    gemini_provider._exhausted.clear()          # daily-quota memory must not leak between tests

    def install(script, keys=1):
        client, calls = _fake_client(script)
        monkeypatch.setattr(gemini_provider, "get_gemini_client", lambda force_new=False: client)
        monkeypatch.setattr(gemini_provider, "_client_for", lambda key_index: client)
        monkeypatch.setattr(gemini_provider, "_key_count", lambda: keys)
        return calls

    yield install
    gemini_provider._exhausted.clear()


# ---------------------------------------------------------------- classification

@pytest.mark.parametrize("code,msg,expected", [
    (401, "API key not valid", LLMAuthError),
    (403, "PERMISSION_DENIED", LLMAuthError),
    (429, "RESOURCE_EXHAUSTED retry in 12s", LLMQuotaError),
    (503, "overloaded", LLMUnavailable),
    (400, "bad schema", LLMBadRequest),
    (None, "Connection reset by peer", LLMUnavailable),
])
def test_classify_error(code, msg, expected):
    e = ApiError(code, msg)
    if code is None:
        del e.code
    assert isinstance(gemini_provider.classify_error(e), expected)


def test_retry_hint_parsed():
    err = gemini_provider.classify_error(ApiError(429, "Please retry in 12.5s."))
    assert err.retry_after == 12.5


# ---------------------------------------------------------------- retry / fallback

def test_transient_error_is_retried(gemini):
    calls = gemini([ApiError(503), "hello"])
    assert llm_client.generate("hi") == "hello"
    assert calls["models"] == ["m1", "m1"]


def test_auth_error_is_not_retried_and_is_typed(gemini):
    calls = gemini([ApiError(401, "API key not valid")])
    with pytest.raises(LLMAuthError):
        llm_client.generate("hi")
    assert calls["n"] == 1


def test_daily_quota_falls_back_to_next_model(gemini):
    calls = gemini([ApiError(429, "RESOURCE_EXHAUSTED: GenerateRequestsPerDay quota"), "from-fallback"])
    assert llm_client.generate("hi") == "from-fallback"
    assert calls["models"] == ["m1", "m2"]


def test_quota_exhausted_everywhere_raises_quota_error(gemini):
    gemini([ApiError(429, "RESOURCE_EXHAUSTED PerDay")])
    with pytest.raises(LLMQuotaError):
        llm_client.generate("hi")


def test_daily_quota_rotates_to_the_next_key_before_changing_model(gemini):
    calls = gemini([ApiError(429, "RESOURCE_EXHAUSTED GenerateRequestsPerDayPerProjectPerModel retryDelay: 3600s"), "from-key-2"], keys=2)
    assert llm_client.generate("hi") == "from-key-2"
    assert calls["models"] == ["m1", "m1"]                      # same model, second key
    # the used-up key/model pair is remembered: the next call goes straight to key 2
    calls2 = gemini(["again"], keys=2)
    assert llm_client.generate("hello") == "again" and calls2["models"] == ["m1"]
    q = gemini_provider.quota_status()
    assert q["keys"] == 2 and q["exhausted"] == [{"key": 1, "model": "m1", "resets_in_minutes": 59}]


def test_fallback_model_rejecting_the_request_shape_moves_on(gemini):
    calls = gemini([ApiError(429, "RESOURCE_EXHAUSTED PerDay"), ApiError(400, "thinking_budget is not supported"), "from-m3"])
    settings.gemini_fallback_models = "m2,m3"
    assert llm_client.generate("hi") == "from-m3"
    assert calls["models"] == ["m1", "m2", "m3"]


# ---------------------------------------------------------------- structured output

def test_structured_happy_path(fake_llm):
    fake_llm(lambda c: json.dumps({"value": 3, "label": "ok"}))
    out = llm_client.generate_structured("p", Answer, system="s")
    assert out == Answer(value=3, label="ok")


def test_structured_strips_code_fences(fake_llm):
    fake_llm(lambda c: '```json\n{"value": 1, "label": "x"}\n```')
    assert llm_client.generate_structured("p", Answer).value == 1


def test_structured_repairs_once(fake_llm):
    answers = iter(['{"value": "not-an-int"}', '{"value": 2, "label": "fixed"}'])
    state = fake_llm(lambda c: next(answers))
    out = llm_client.generate_structured("p", Answer)
    assert out.label == "fixed"
    assert len(state.calls) == 2
    assert "not valid for the required schema" in state.calls[1].prompt


def test_structured_raises_after_failed_repair(fake_llm):
    fake_llm(lambda c: "garbage")
    with pytest.raises(LLMInvalidOutput):
        llm_client.generate_structured("p", Answer)


def test_provider_error_propagates_not_swallowed(fake_llm):
    def boom(call):
        raise LLMUnavailable("down")
    fake_llm(boom)
    with pytest.raises(LLMUnavailable):
        llm_client.generate_structured("p", Answer)


def test_structured_cache_avoids_second_call(monkeypatch):
    settings.llm_provider = "gemini"
    settings.llm_cache_enabled = True
    calls = {"n": 0}

    def fake_structured(prompt, system, schema, **kw):
        calls["n"] += 1
        return '{"value": 9, "label": "cached"}'

    monkeypatch.setattr(llm_client, "generate_gemini_structured", fake_structured)
    a = llm_client.generate_structured("same prompt", Answer, system="s", prompt_version="v1")
    b = llm_client.generate_structured("same prompt", Answer, system="s", prompt_version="v1")
    c = llm_client.generate_structured("same prompt", Answer, system="s", prompt_version="v2")
    assert a == b and calls["n"] == 2  # v1 cached once, v2 is a new key


def test_cache_roundtrip(tmp_path):
    settings.llm_cache_enabled = True
    k = cache.make_key(a=1, b="x")
    assert cache.get(k) is None
    cache.put(k, "payload", "m")
    assert cache.get(k) == "payload"


def test_health_reports_invalid_key(monkeypatch):
    settings.llm_provider = "gemini"

    def raise_auth(force_new=False):
        raise LLMAuthError("no key")

    monkeypatch.setattr(gemini_provider, "get_gemini_client", raise_auth)
    gemini_provider._health_cache.update(at=0.0, value=None)
    status = llm_client.llm_health(force=True)
    assert status["ok"] is False and status["kind"] == "LLMAuthError"
