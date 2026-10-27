"""Process-wide throttling for LLM calls (free-tier friendly).

`generate*` functions run in worker threads, so plain threading primitives are used.
"""
import threading
import time
from collections import deque
from contextlib import contextmanager


class RateLimiter:
    """Sliding-window limiter: at most `rpm` calls start within any 60 s window."""

    def __init__(self, rpm: int, window: float = 60.0):
        self.rpm = max(1, rpm)
        self.window = window
        self._stamps: deque[float] = deque()
        self._lock = threading.Lock()

    def acquire(self) -> float:
        """Blocks until a slot is free. Returns seconds waited."""
        waited = 0.0
        while True:
            with self._lock:
                now = time.monotonic()
                while self._stamps and now - self._stamps[0] >= self.window:
                    self._stamps.popleft()
                if len(self._stamps) < self.rpm:
                    self._stamps.append(now)
                    return waited
                sleep_for = self.window - (now - self._stamps[0]) + 0.05
            time.sleep(sleep_for)
            waited += sleep_for


class LLMGate:
    """Combines a concurrency cap and the rate limiter. Reconfigurable at runtime (tests)."""

    def __init__(self, max_concurrency: int, rpm: int):
        self._sem = threading.BoundedSemaphore(max(1, max_concurrency))
        self.limiter = RateLimiter(rpm)

    @contextmanager
    def slot(self):
        self._sem.acquire()
        try:
            self.limiter.acquire()
            yield
        finally:
            self._sem.release()


_gate: LLMGate | None = None
_gate_lock = threading.Lock()


def get_gate() -> LLMGate:
    global _gate
    if _gate is None:
        with _gate_lock:
            if _gate is None:
                from app.config import settings

                _gate = LLMGate(settings.llm_max_concurrency, settings.llm_requests_per_minute)
    return _gate


def reset_gate() -> None:
    """For tests."""
    global _gate
    _gate = None
