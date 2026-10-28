import asyncio

import pytest

from app.core.llm.errors import LLMAuthError, LLMInvalidOutput, LLMQuotaError, LLMUnavailable
from app.shared import jobs


@pytest.fixture(autouse=True)
def _fast_retries(monkeypatch):
    monkeypatch.setattr(jobs, "RETRY_MARGIN", 0.0)
    monkeypatch.setattr(jobs, "DEFAULT_RETRY_WAIT", 0.01)


def _unavailable(hint=0.01):
    e = LLMUnavailable("busy")
    e.retry_after = hint
    return e


async def test_job_runs_and_reports_every_status_change():
    runner = jobs.JobRunner(concurrency=1)
    seen = []

    async def work(job):
        await job.note("reading")
        return 42

    job = runner.submit(work, name="t", on_status=lambda j: seen.append((j.status, j.note_text)))
    await job.wait(timeout=2)
    assert job.status == jobs.SUCCEEDED and job.result == 42 and job.attempts == 1
    assert [s for s, _ in seen] == ["running", "running", "succeeded"]
    assert ("running", "reading") in seen
    await runner.shutdown()


async def test_async_callbacks_work_and_callback_errors_never_break_the_job():
    runner = jobs.JobRunner(concurrency=1)
    calls = []

    async def on_status(job):
        calls.append(job.status)
        raise RuntimeError("callback bug")

    async def work(job):
        return "ok"

    job = runner.submit(work, name="t", on_status=on_status)
    await job.wait(timeout=2)
    assert job.status == jobs.SUCCEEDED and calls == ["running", "succeeded"]
    await runner.shutdown()


async def test_concurrency_is_bounded():
    runner = jobs.JobRunner(concurrency=2)
    active = peak = 0

    async def work(job):
        nonlocal active, peak
        active += 1
        peak = max(peak, active)
        await asyncio.sleep(0.03)
        active -= 1

    submitted = [runner.submit(work, name=f"j{i}") for i in range(6)]
    assert runner.stats()["queued"] + runner.stats()["running"] >= 1
    await asyncio.gather(*(j.wait(timeout=3) for j in submitted))
    assert peak == 2
    assert runner.stats()["succeeded_recent"] == 6 and runner.stats()["depth"] == 0
    await runner.shutdown()


async def test_retries_once_on_unavailable_with_the_hint_then_succeeds():
    runner = jobs.JobRunner(concurrency=1)
    attempts = []
    seen = []

    async def work(job):
        attempts.append(1)
        if len(attempts) == 1:
            raise _unavailable(0.02)
        return "second time lucky"

    job = runner.submit(work, name="t", on_status=lambda j: seen.append((j.status, j.retry_in)))
    await job.wait(timeout=2)
    assert job.status == jobs.SUCCEEDED and job.attempts == 2 and job.error is None
    assert ("retrying", 0.02) in seen
    await runner.shutdown()


async def test_per_minute_quota_is_retried_but_daily_quota_is_not():
    runner = jobs.JobRunner(concurrency=1)
    n = {"minute": 0, "daily": 0}

    async def per_minute(job):
        n["minute"] += 1
        if n["minute"] == 1:
            e = LLMQuotaError("rpm")
            e.retry_after = 0.01
            raise e

    async def daily(job):
        n["daily"] += 1
        e = LLMQuotaError("daily")
        e.daily = True
        raise e

    a, b = runner.submit(per_minute, name="a"), runner.submit(daily, name="b")
    await asyncio.gather(a.wait(timeout=2), b.wait(timeout=2))
    assert a.status == jobs.SUCCEEDED and a.attempts == 2
    assert b.status == jobs.FAILED and n["daily"] == 1 and b.error_kind == "quota"
    await runner.shutdown()


async def test_only_one_retry_then_failure_with_a_kind():
    runner = jobs.JobRunner(concurrency=1)

    async def work(job):
        raise _unavailable()

    job = runner.submit(work, name="t")
    await job.wait(timeout=2)
    assert job.status == jobs.FAILED and job.attempts == 2 and job.error_kind == "unavailable"
    await runner.shutdown()


async def test_a_hint_longer_than_the_wait_limit_fails_immediately():
    runner = jobs.JobRunner(concurrency=1, max_retry_wait=1.0)

    async def work(job):
        raise _unavailable(300)

    job = runner.submit(work, name="t")
    await job.wait(timeout=2)
    assert job.status == jobs.FAILED and job.attempts == 1
    await runner.shutdown()


@pytest.mark.parametrize("exc,kind", [(LLMAuthError("k"), "auth"), (LLMInvalidOutput("x"), "invalid_output"),
                                      (ValueError("bug"), "internal")])
async def test_other_errors_are_not_retried_and_are_classified(exc, kind):
    runner = jobs.JobRunner(concurrency=1)

    async def work(job):
        raise exc

    job = runner.submit(work, name="t")
    await job.wait(timeout=2)
    assert job.status == jobs.FAILED and job.attempts == 1 and job.error_kind == kind
    await runner.shutdown()


async def test_same_key_is_not_queued_twice_while_active():
    runner = jobs.JobRunner(concurrency=1)
    gate = asyncio.Event()

    async def work(job):
        await gate.wait()

    first = runner.submit(work, name="t", key="contract:1")
    again = runner.submit(work, name="t", key="contract:1")
    assert first is again
    gate.set()
    await first.wait(timeout=2)
    third = runner.submit(work, name="t", key="contract:1")      # finished, so a new job is allowed
    assert third is not first
    await third.wait(timeout=2)
    await runner.shutdown()


async def test_module_level_api_and_stats():
    await jobs.shutdown()
    assert jobs.stats()["depth"] == 0

    async def work(job):
        return 1

    job = jobs.submit(work, name="t")
    await job.wait(timeout=2)
    assert job.status == jobs.SUCCEEDED and jobs.stats()["succeeded_recent"] == 1
    await jobs.shutdown()
