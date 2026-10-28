"""Process-wide throttling for LLM calls (free-tier friendly).

Google rate-limits per API key (per project), so every key gets its own gate: a concurrency cap plus a
sliding-window requests-per-minute limiter. A burst therefore *queues* instead of failing. When the server
answers 429 with a `retryDelay`, `penalise` pauses that key's limiter for exactly that long, so every queued
call waits instead of each one hammering the API and burning its own retries.

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
        self._blocked_until = 0.0
        self._lock = threading.Lock()

    def penalise(self, seconds: float) -> None:
        """The server told us to back off: nobody starts a call for `seconds`."""
        with self._lock:
            self._blocked_until = max(self._blocked_until, time.monotonic() + max(0.0, seconds))

    def acquire(self) -> float:
        """Blocks until a slot is free. Returns seconds waited."""
        waited = 0.0
        while True:
            with self._lock:
                now = time.monotonic()
                while self._stamps and now - self._stamps[0] >= self.window:
                    self._stamps.popleft()
                if now < self._blocked_until:
                    sleep_for = self._blocked_until - now + 0.05
                elif len(self._stamps) < self.rpm:
                    self._stamps.append(now)
                    return waited
                else:
                    sleep_for = self.window - (now - self._stamps[0]) + 0.05
            time.sleep(sleep_for)
            waited += sleep_for


class LLMGate:
    """Combines a concurrency cap and the rate limiter for one API key."""

    def __init__(self, max_concurrency: int, rpm: int):
        self.max_concurrency = max(1, max_concurrency)
        self._sem = threading.BoundedSemaphore(self.max_concurrency)
        self.limiter = RateLimiter(rpm)
        self._lock = threading.Lock()
        self.waiting = 0       # calls queued behind the concurrency cap or the rate window
        self.in_flight = 0

    @contextmanager
    def slot(self):
        with self._lock:
            self.waiting += 1
        entered = False
        self._sem.acquire()
        try:
            self.limiter.acquire()
            with self._lock:
                self.waiting -= 1
                self.in_flight += 1
                entered = True
            yield
        finally:
            with self._lock:
                if entered:
                    self.in_flight -= 1
                else:
                    self.waiting -= 1
            self._sem.release()

    def stats(self) -> dict:
        with self._lock:
            return {"waiting": self.waiting, "in_flight": self.in_flight, "max_concurrency": self.max_concurrency,
                    "rpm": self.limiter.rpm}


_gates: dict[int, LLMGate] = {}
_gate_lock = threading.Lock()


def get_gate(key_index: int = 0) -> LLMGate:
    """The gate of API key number `key_index` (0 = primary key)."""
    gate = _gates.get(key_index)
    if gate is None:
        with _gate_lock:
            gate = _gates.get(key_index)
            if gate is None:
                from app.config import settings

                gate = _gates[key_index] = LLMGate(settings.llm_max_concurrency, settings.llm_requests_per_minute)
    return gate


def gate_stats() -> dict:
    """Queue depth per key, for /health."""
    with _gate_lock:
        gates = dict(_gates)
    per_key = {f"key{idx + 1}": g.stats() for idx, g in sorted(gates.items())}
    return {"waiting": sum(g["waiting"] for g in per_key.values()),
            "in_flight": sum(g["in_flight"] for g in per_key.values()), "keys": per_key}


def reset_gate() -> None:
    """For tests (and after a settings change)."""
    with _gate_lock:
        _gates.clear()
