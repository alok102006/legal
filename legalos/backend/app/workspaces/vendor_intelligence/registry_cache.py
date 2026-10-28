"""24-hour cache of live GST registry lookups, one small JSON file per GSTIN.

Why: every live lookup spends money (a wallet or a quota). Re-checking a supplier, re-opening the check desk or
"re-check all suppliers" must not pay twice for the same answer. Registry data is public, so one cache is shared by
all organisations. Files survive restarts (the dev server reloads on every edit). Only real answers are cached:
a successful record for `registry_cache_ttl_hours`, and "no such GSTIN" for one hour (a new registration should
not look missing for a day). Errors (auth, quota, timeouts) are never cached.
"""
import json
import logging
import os
import re
import time
from typing import Any, Dict, Optional, Tuple

from app.config import settings

logger = logging.getLogger("legalos.vendors")

NOT_FOUND_TTL_SECONDS = 3600
FOUND, MISSING = "found", "not_found"
_SAFE = re.compile(r"^[0-9A-Z]{15}$")

COUNTERS = {"hits": 0, "misses": 0, "writes": 0}


def _path(gstin: str) -> Optional[str]:
    return os.path.join(settings.registry_cache_dir, f"{gstin}.json") if _SAFE.match(gstin) else None


def get(gstin: str) -> Optional[Tuple[str, Dict[str, Any], float]]:
    """(kind, stored result dict, fetched_at epoch) when a fresh entry exists, else None."""
    path = _path(gstin)
    if path is None:
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            row = json.load(f)
    except FileNotFoundError:
        COUNTERS["misses"] += 1
        return None
    except Exception as e:                                  # a corrupt file must never break a lookup
        logger.warning("registry cache read failed for %s: %s", gstin[:4] + "...", e)
        COUNTERS["misses"] += 1
        return None
    ttl = NOT_FOUND_TTL_SECONDS if row.get("kind") == MISSING else max(1, settings.registry_cache_ttl_hours) * 3600
    if time.time() - float(row.get("at", 0)) > ttl:
        COUNTERS["misses"] += 1
        return None
    COUNTERS["hits"] += 1
    return row["kind"], row.get("result") or {}, float(row["at"])


def put(gstin: str, kind: str, result: Dict[str, Any]) -> None:
    path = _path(gstin)
    if path is None:
        return
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({"kind": kind, "at": time.time(), "result": result}, f)
        os.replace(tmp, path)
        COUNTERS["writes"] += 1
    except Exception as e:
        logger.warning("registry cache write failed: %s", e)


def has_fresh(gstin: str) -> bool:
    """Is a fresh answer stored? (Does not count as a hit or a miss.)"""
    saved = dict(COUNTERS)
    try:
        return get(gstin) is not None
    finally:
        COUNTERS.update(saved)


def clear(gstin: str) -> None:
    path = _path(gstin)
    if path and os.path.exists(path):
        os.remove(path)
