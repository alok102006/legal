"""Small in-process job runner for slow work (AI analyses) that must not block a request.

Why: contracts, notices and documents each analyse in a background task today. They all need the same things:
bounded concurrency (the free Gemini tier cannot take a burst), one retry when the AI is briefly busy, and a way
to show progress. This module gives them one shared implementation. Nothing here knows about any workspace.

Usage (adopting workspaces call these; none do yet):

    from app.shared import jobs

    async def analyse(job: jobs.Job) -> None:
        ...                                    # the work; raise on failure; may call job.note("reading pages")

    async def on_status(job: jobs.Job) -> None:     # sync or async; called on every status change
        await save_status(job.key, job.status, job.error_kind)

    job = jobs.submit(analyse, name="contract.analyse", key=f"contract:{contract_id}", on_status=on_status)
    await job.wait()                            # optional; tests and "analyse now" endpoints use it

API
- `submit(fn, *, name, key=None, on_status=None, retries=1) -> Job`: queues `fn(job)` (a coroutine function).
  When `key` is given and a job with that key is still queued/running, that job is returned instead of a duplicate.
- `Job.status`: queued | running | retrying | succeeded | failed.  Also `attempts`, `error`, `error_kind`,
  `retry_in` (seconds until the retry, while status == "retrying"), `result` (what `fn` returned) and `await job.wait()`.
- Retry policy: a failure with `LLMUnavailable` or a per-minute `LLMQuotaError` is retried up to `retries` times
  (default once) after the server's `retry_after` hint (default 20 s, at most `max_retry_wait` = 90 s). A daily-quota
  error, a hint longer than `max_retry_wait`, or any other exception fails the job at once: waiting would not help.
- `error_kind` is one of: quota, unavailable, auth, bad_input, invalid_output, internal (same words the
  workspaces already store).
- Concurrency: `JOBS_MAX_CONCURRENCY` workers (default 2) per event loop. `stats()` reports queue depth for /health.
- Lifecycle: `start()` (called from the app's lifespan; also lazy on first `submit`) and `await shutdown()`.
  Jobs are in memory only: after a restart a workspace must re-queue its unfinished rows (as it already does at startup).
"""
import asyncio
import inspect
import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Optional

from app.config import settings
from app.core.llm.errors import (
    LLMAuthError,
    LLMBadRequest,
    LLMError,
    LLMInvalidOutput,
    LLMQuotaError,
    LLMUnavailable,
)

logger = logging.getLogger("legalos.jobs")

QUEUED, RUNNING, RETRYING, SUCCEEDED, FAILED = "queued", "running", "retrying", "succeeded", "failed"
_ACTIVE = (QUEUED, RUNNING, RETRYING)
DEFAULT_RETRY_WAIT = 20.0
MAX_RETRY_WAIT = 90.0
RETRY_MARGIN = 0.5            # added to the server's hint so we do not retry a hair too early
_KEEP_FINISHED = 200            # finished jobs remembered for stats / lookups


def error_kind(exc: BaseException) -> str:
    """Same vocabulary the workspaces store on their rows."""
    if isinstance(exc, LLMAuthError):
        return "auth"
    if isinstance(exc, LLMQuotaError):
        return "quota"
    if isinstance(exc, LLMInvalidOutput):
        return "invalid_output"
    if isinstance(exc, LLMBadRequest):
        return "bad_input"
    if isinstance(exc, LLMError):
        return "unavailable"
    return "internal"


def _retry_wait(exc: BaseException, max_wait: float) -> Optional[float]:
    """Seconds to wait before retrying `exc`, or None when a retry is pointless."""
    if isinstance(exc, LLMQuotaError):
        if exc.daily:
            return None
    elif not isinstance(exc, LLMUnavailable):
        return None
    wait = (exc.retry_after or DEFAULT_RETRY_WAIT) + RETRY_MARGIN
    return wait if wait <= max_wait else None


StatusCallback = Callable[["Job"], Any]


@dataclass
class Job:
    id: str
    name: str
    fn: Callable[["Job"], Awaitable[Any]]
    key: Optional[str] = None
    retries: int = 1
    on_status: Optional[StatusCallback] = None
    status: str = QUEUED
    attempts: int = 0
    error: Optional[str] = None
    error_kind: Optional[str] = None
    retry_in: Optional[float] = None
    note_text: Optional[str] = None
    result: Any = None
    submitted_at: float = field(default_factory=time.time)
    finished_at: Optional[float] = None
    _done: asyncio.Event = field(default_factory=asyncio.Event, repr=False)

    @property
    def finished(self) -> bool:
        return self.status not in _ACTIVE

    async def wait(self, timeout: Optional[float] = None) -> "Job":
        await asyncio.wait_for(self._done.wait(), timeout)
        return self

    async def note(self, text: str) -> None:
        """Progress text for the UI ("reading pages", "checking clauses"); reported through `on_status`."""
        self.note_text = text
        await _notify(self)


async def _notify(job: Job) -> None:
    """Status callbacks must never break the runner: their failures are logged and ignored."""
    if job.on_status is None:
        return
    try:
        out = job.on_status(job)
        if inspect.isawaitable(out):
            await out
    except Exception:
        logger.exception("status callback failed for job %s (%s)", job.id, job.name)


class JobRunner:
    """Bounded-concurrency queue living on one event loop."""

    def __init__(self, concurrency: int, max_retry_wait: float = MAX_RETRY_WAIT):
        self.concurrency = max(1, concurrency)
        self.max_retry_wait = max_retry_wait
        self._queue: asyncio.Queue[Job] = asyncio.Queue()
        self._workers: list[asyncio.Task] = []
        self._jobs: dict[str, Job] = {}
        self._by_key: dict[str, Job] = {}
        self._finished: list[Job] = []

    # -- lifecycle
    def start(self) -> None:
        if not self._workers:
            self._workers = [asyncio.create_task(self._worker(i)) for i in range(self.concurrency)]

    async def shutdown(self) -> None:
        for w in self._workers:
            w.cancel()
        await asyncio.gather(*self._workers, return_exceptions=True)
        self._workers = []

    # -- submitting
    def submit(self, fn: Callable[[Job], Awaitable[Any]], *, name: str, key: Optional[str] = None,
               on_status: Optional[StatusCallback] = None, retries: int = 1) -> Job:
        if key and key in self._by_key and not self._by_key[key].finished:
            return self._by_key[key]
        self.start()
        job = Job(id=uuid.uuid4().hex[:12], name=name, fn=fn, key=key, retries=max(0, retries), on_status=on_status)
        self._jobs[job.id] = job
        if key:
            self._by_key[key] = job
        self._queue.put_nowait(job)
        return job

    def get(self, job_id: str) -> Optional[Job]:
        return self._jobs.get(job_id)

    def stats(self) -> dict:
        jobs = list(self._jobs.values())
        return {
            "queued": sum(j.status == QUEUED for j in jobs),
            "running": sum(j.status == RUNNING for j in jobs),
            "retrying": sum(j.status == RETRYING for j in jobs),
            "depth": self._queue.qsize(),
            "workers": self.concurrency,
            "failed_recent": sum(j.status == FAILED for j in self._finished),
            "succeeded_recent": sum(j.status == SUCCEEDED for j in self._finished),
        }

    # -- running
    async def _worker(self, index: int) -> None:
        while True:
            job = await self._queue.get()
            try:
                await self._run(job)
            except asyncio.CancelledError:
                raise
            except Exception:                       # _run handles job errors; this is a runner bug, never die
                logger.exception("job runner crashed on %s", job.id)
            finally:
                self._queue.task_done()

    async def _set(self, job: Job, status: str) -> None:
        job.status = status
        await _notify(job)

    async def _run(self, job: Job) -> None:
        while True:
            job.attempts += 1
            job.retry_in = None
            await self._set(job, RUNNING)
            try:
                job.result = await job.fn(job)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                wait = _retry_wait(exc, self.max_retry_wait) if job.attempts <= job.retries else None
                if wait is not None:
                    logger.warning("job %s (%s) hit %s; retrying in %.1fs", job.id, job.name, type(exc).__name__, wait)
                    job.error, job.error_kind, job.retry_in = str(exc)[:300], error_kind(exc), wait
                    await self._set(job, RETRYING)
                    await asyncio.sleep(wait)
                    continue
                job.error = getattr(exc, "user_message", None) or str(exc)[:300]
                job.error_kind = error_kind(exc)
                logger.error("job %s (%s) failed after %d attempt(s): %s: %s", job.id, job.name, job.attempts,
                             type(exc).__name__, str(exc)[:300])
                await self._finish(job, FAILED)
                return
            job.error = job.error_kind = None
            await self._finish(job, SUCCEEDED)
            return

    async def _finish(self, job: Job, status: str) -> None:
        job.finished_at = time.time()
        await self._set(job, status)
        job._done.set()
        self._finished.append(job)
        if len(self._finished) > _KEEP_FINISHED:
            old = self._finished.pop(0)
            self._jobs.pop(old.id, None)
            if old.key and self._by_key.get(old.key) is old:
                del self._by_key[old.key]


# ------------------------------------------------------------------ module-level runner (one per event loop)

_runner: Optional[JobRunner] = None
_runner_loop: Optional[asyncio.AbstractEventLoop] = None


def get_runner() -> JobRunner:
    """The runner of the running event loop (a new one if the loop changed, as it does between tests)."""
    global _runner, _runner_loop
    loop = asyncio.get_running_loop()
    if _runner is None or _runner_loop is not loop:
        _runner, _runner_loop = JobRunner(settings.jobs_max_concurrency), loop
    return _runner


def submit(fn: Callable[[Job], Awaitable[Any]], *, name: str, key: Optional[str] = None,
           on_status: Optional[StatusCallback] = None, retries: int = 1) -> Job:
    return get_runner().submit(fn, name=name, key=key, on_status=on_status, retries=retries)


def start() -> None:
    get_runner().start()


async def shutdown() -> None:
    global _runner, _runner_loop
    if _runner is not None:
        await _runner.shutdown()
    _runner, _runner_loop = None, None


def stats() -> dict:
    """Queue numbers for /health (zeros before the first job)."""
    if _runner is None:
        return {"queued": 0, "running": 0, "retrying": 0, "depth": 0, "workers": settings.jobs_max_concurrency,
                "failed_recent": 0, "succeeded_recent": 0}
    return _runner.stats()
