"""Tiny on-disk cache for deterministic LLM calls.

Keyed by model + prompts + schema + prompt version + input-file hashes, so re-running an
analysis on the same document with the same prompt version costs zero Gemini calls.
Only successful, validated answers are cached.

The cache is bounded: when it grows past `llm_cache_max_mb` or `llm_cache_max_entries`, the least recently
used entries (oldest file modification time; a hit "touches" its file) are deleted until it is back under 90% of
both limits. `cache_stats()` reports size and hit rate for /health.
"""
import hashlib
import json
import logging
import os
import re
import threading
import time
from typing import Optional

from app.config import settings

logger = logging.getLogger("legalos.llm.cache")

_lock = threading.Lock()
_COUNTERS = {"hits": 0, "misses": 0, "puts": 0, "evictions": 0}
# Approximate occupancy, recomputed by a directory scan on first use and whenever the directory changes.
_usage: dict = {"dir": None, "entries": 0, "bytes": 0}


def make_key(**parts) -> str:
    blob = json.dumps(parts, sort_keys=True, default=str, ensure_ascii=False)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


_ENTRY_NAME = re.compile(r"^[0-9a-f]{64}\.json$")      # cache entries only: quota_state.json lives in the same folder


def _path(key: str) -> str:
    return os.path.join(settings.llm_cache_dir, key[:2], f"{key}.json")


def _scan() -> list[tuple[float, int, str]]:
    """(mtime, size, path) of every cache entry."""
    found: list[tuple[float, int, str]] = []
    root = settings.llm_cache_dir
    if not os.path.isdir(root):
        return found
    for folder, _dirs, files in os.walk(root):
        for name in files:
            if not _ENTRY_NAME.match(name):
                continue
            path = os.path.join(folder, name)
            try:
                st = os.stat(path)
            except OSError:
                continue
            found.append((st.st_mtime, st.st_size, path))
    return found


def _sync_usage() -> None:
    """Caller holds `_lock`. Rebuilds the occupancy numbers when we have not looked at this directory yet."""
    if _usage["dir"] != settings.llm_cache_dir:
        entries = _scan()
        _usage.update(dir=settings.llm_cache_dir, entries=len(entries), bytes=sum(e[1] for e in entries))


def _limits() -> tuple[int, int]:
    return max(1, settings.llm_cache_max_mb) * 1024 * 1024, max(1, settings.llm_cache_max_entries)


def _evict_if_needed() -> None:
    """Caller holds `_lock`. Deletes least-recently-used entries when a limit is exceeded."""
    max_bytes, max_entries = _limits()
    if _usage["bytes"] <= max_bytes and _usage["entries"] <= max_entries:
        return
    entries = sorted(_scan())                                   # oldest first
    total, count = sum(e[1] for e in entries), len(entries)
    target_bytes, target_entries = int(max_bytes * 0.9), int(max_entries * 0.9)
    for _mtime, size, path in entries:
        if total <= target_bytes and count <= target_entries:
            break
        try:
            os.remove(path)
        except OSError:
            continue
        total -= size
        count -= 1
        _COUNTERS["evictions"] += 1
    _usage.update(entries=count, bytes=total)
    logger.info("LLM cache trimmed to %d entries / %.1f MB", count, total / 1048576)


def get(key: str) -> Optional[str]:
    if not settings.llm_cache_enabled:
        return None
    path = _path(key)
    try:
        with open(path, "r", encoding="utf-8") as f:
            text = json.load(f)["text"]
    except FileNotFoundError:
        _COUNTERS["misses"] += 1
        return None
    except Exception as e:  # corrupt cache entry must never break a request
        logger.warning("LLM cache read failed: %s", e)
        _COUNTERS["misses"] += 1
        return None
    _COUNTERS["hits"] += 1
    try:
        os.utime(path)                                          # mark as recently used (LRU)
    except OSError:
        pass
    return text


def put(key: str, text: str, model: str = "") -> None:
    if not settings.llm_cache_enabled:
        return
    try:
        p = _path(key)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        tmp = p + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({"text": text, "model": model, "ts": time.time()}, f)
        with _lock:
            _sync_usage()
            replaced = os.path.getsize(p) if os.path.exists(p) else None
            os.replace(tmp, p)
            _COUNTERS["puts"] += 1
            _usage["bytes"] += os.path.getsize(p) - (replaced or 0)
            _usage["entries"] += 0 if replaced is not None else 1
            _evict_if_needed()
    except Exception as e:
        logger.warning("LLM cache write failed: %s", e)


def cache_stats() -> dict:
    """Occupancy and hit rate, for /health/llm. Scans the directory, so it is cheap only because the cache is bounded."""
    entries = _scan()
    max_bytes, max_entries = _limits()
    lookups = _COUNTERS["hits"] + _COUNTERS["misses"]
    return {
        "enabled": settings.llm_cache_enabled,
        "entries": len(entries),
        "size_mb": round(sum(e[1] for e in entries) / 1048576, 2),
        "max_entries": max_entries,
        "max_mb": max_bytes // 1048576,
        "hits": _COUNTERS["hits"],
        "misses": _COUNTERS["misses"],
        "hit_rate": round(_COUNTERS["hits"] / lookups, 3) if lookups else None,
        "puts": _COUNTERS["puts"],
        "evictions": _COUNTERS["evictions"],
    }
