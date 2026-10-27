"""Local embedding + reranking models (loaded once per process, cached on disk).

Embedder: paraphrase-multilingual-MiniLM-L12-v2 (384 dims) so Hindi/Gujarati/Marathi/Hinglish text is
searchable alongside English. Reranker: a cross-encoder that re-scores (query, passage) pairs; far more
precise than vector similarity, cheap enough on CPU for a few dozen passages.
"""
import logging
import os
import threading
import time

from app.config import settings

logger = logging.getLogger("legalos.embeddings")

EMBED_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
RERANK_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"
EMBED_DIM = 384

_embedder = None
_reranker = None
_lock = threading.RLock()

# Model inference runs on its own small pool so it can never starve (or be starved by) the default
# executor that asyncio.to_thread uses for LLM calls, file reads and health checks.
from concurrent.futures import ThreadPoolExecutor  # noqa: E402

MODEL_POOL = ThreadPoolExecutor(max_workers=2, thread_name_prefix="models")


class Embedder:
    def __init__(self):
        os.environ["HF_HOME"] = settings.hf_home
        os.environ["SENTENCE_TRANSFORMERS_HOME"] = settings.sentence_transformers_home
        from sentence_transformers import SentenceTransformer
        t = time.time()
        self.model = SentenceTransformer(EMBED_MODEL, cache_folder=settings.hf_home)
        logger.info("loaded %s in %.1fs", EMBED_MODEL, time.time() - t)

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        return self.model.encode(texts, convert_to_numpy=True, normalize_embeddings=True, batch_size=32).tolist()


class Reranker:
    def __init__(self):
        from sentence_transformers import CrossEncoder
        t = time.time()
        self.model = CrossEncoder(RERANK_MODEL, max_length=512)
        logger.info("loaded %s in %.1fs", RERANK_MODEL, time.time() - t)

    def score(self, query: str, passages: list[str]) -> list[float]:
        if not passages:
            return []
        return [float(x) for x in self.model.predict([(query, p) for p in passages], batch_size=16)]


def get_embedder() -> Embedder:
    global _embedder
    if _embedder is None:
        with _lock:
            if _embedder is None:
                _embedder = Embedder()
    return _embedder


def get_reranker() -> Reranker:
    global _reranker
    if _reranker is None:
        with _lock:
            if _reranker is None:
                _reranker = Reranker()
    return _reranker


def warm_up() -> None:
    """Load both models once, before any request thread needs them."""
    get_embedder()
    get_reranker()


async def run_model(fn, *args):
    """Run a model call on the dedicated model pool (not the default asyncio executor)."""
    import asyncio
    return await asyncio.get_running_loop().run_in_executor(MODEL_POOL, fn, *args)
