"""Tiny on-disk cache for deterministic LLM calls.

Keyed by model + prompts + schema + prompt version + input-file hashes, so re-running an
analysis on the same document with the same prompt version costs zero Gemini calls.
Only successful, validated answers are cached.
"""
import hashlib
import json
import logging
import os
import time
from typing import Optional

from app.config import settings

logger = logging.getLogger("legalos.llm.cache")


def make_key(**parts) -> str:
    blob = json.dumps(parts, sort_keys=True, default=str, ensure_ascii=False)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _path(key: str) -> str:
    return os.path.join(settings.llm_cache_dir, key[:2], f"{key}.json")


def get(key: str) -> Optional[str]:
    if not settings.llm_cache_enabled:
        return None
    try:
        with open(_path(key), "r", encoding="utf-8") as f:
            return json.load(f)["text"]
    except FileNotFoundError:
        return None
    except Exception as e:  # corrupt cache entry must never break a request
        logger.warning("LLM cache read failed: %s", e)
        return None


def put(key: str, text: str, model: str = "") -> None:
    if not settings.llm_cache_enabled:
        return
    try:
        p = _path(key)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        tmp = p + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({"text": text, "model": model, "ts": time.time()}, f)
        os.replace(tmp, p)
    except Exception as e:
        logger.warning("LLM cache write failed: %s", e)
