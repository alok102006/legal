"""Retrieval: keyword (Postgres FTS, english + simple configs) + vector (Qdrant) fused by reciprocal rank,
then re-scored by a cross-encoder, then expanded with the neighbouring chunks for context.

Why each stage:
- keyword search is exact for names, section numbers, amounts ("clause 7", "Rs 5 lakh") and works for any script
  via the `simple` config; vectors find the same idea in different words; RRF merges both without tuning.
- the reranker reads (question, passage) together and is far more precise than either retriever.
- neighbours give the model the sentence before/after the match (a "12 days" chunk needs its "Leave" context).
"""
import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence

from qdrant_client.http import models as qm
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.embeddings.embedder import get_embedder, get_reranker, run_model
from app.core.vectorstore.qdrant_client import get_qdrant_client
from app.workspaces.knowledge_hub.models import DocChunk

logger = logging.getLogger("legalos.documents.retrieval")
RRF_K = 60
EMBED_BATCH = 48
POOL = 30            # candidates before reranking
TOP_K = 6            # passages handed to the model


@dataclass
class Hit:
    chunk_id: uuid.UUID
    score: float
    via: List[str] = field(default_factory=list)   # keyword | vector | rerank


# ----------------------------------------------------------------- indexing

def index_vectors(org_id: uuid.UUID, doc_id: uuid.UUID, chunk_ids: Sequence[uuid.UUID], texts: Sequence[str], collection: Optional[str] = None) -> None:
    embedder, client = get_embedder(), get_qdrant_client()
    for i in range(0, len(texts), EMBED_BATCH):
        vecs = embedder.embed(list(texts[i:i + EMBED_BATCH]))
        client.upsert(
            collection_name=settings.documents_collection, wait=True,
            points=[qm.PointStruct(id=str(chunk_ids[i + j]), vector=v,
                                   payload={"org_id": str(org_id), "doc_id": str(doc_id), "collection": collection or ""})
                    for j, v in enumerate(vecs)],
        )


def delete_vectors(doc_id: uuid.UUID) -> None:
    try:
        get_qdrant_client().delete(
            collection_name=settings.documents_collection,
            points_selector=qm.Filter(must=[qm.FieldCondition(key="doc_id", match=qm.MatchValue(value=str(doc_id)))]))
    except Exception as e:
        logger.warning("vector cleanup failed for %s: %s", doc_id, e)


# ----------------------------------------------------------------- searching

@dataclass
class Scope:
    org_id: uuid.UUID
    doc_ids: Optional[List[uuid.UUID]] = None       # restrict to these documents (a collection), None = all


def vector_search(scope: Scope, query: str, k: int) -> List[uuid.UUID]:
    must = [qm.FieldCondition(key="org_id", match=qm.MatchValue(value=str(scope.org_id)))]
    if scope.doc_ids is not None:
        must.append(qm.FieldCondition(key="doc_id", match=qm.MatchAny(any=[str(d) for d in scope.doc_ids])))
    vec = get_embedder().embed([query])[0]
    res = get_qdrant_client().query_points(collection_name=settings.documents_collection, query=vec,
                                           query_filter=qm.Filter(must=must), limit=k, score_threshold=0.15)
    return [uuid.UUID(str(p.id)) for p in res.points]


async def keyword_search(session: AsyncSession, scope: Scope, query: str, k: int) -> List[uuid.UUID]:
    tsq_en = func.websearch_to_tsquery("english", query)
    tsq_simple = func.websearch_to_tsquery("simple", query)
    rank = func.greatest(func.ts_rank_cd(DocChunk.tsv, tsq_en), func.ts_rank_cd(DocChunk.tsv_simple, tsq_simple))
    stmt = (select(DocChunk.id).where(DocChunk.organization_id == scope.org_id)
            .where(or_(DocChunk.tsv.op("@@")(tsq_en), DocChunk.tsv_simple.op("@@")(tsq_simple)))
            .order_by(rank.desc()).limit(k))
    if scope.doc_ids is not None:
        stmt = stmt.where(DocChunk.doc_id.in_(scope.doc_ids))
    return list((await session.execute(stmt)).scalars().all())


def rrf(rank_lists: Dict[str, List[uuid.UUID]], k: int = RRF_K) -> List[Hit]:
    scores: Dict[uuid.UUID, float] = {}
    via: Dict[uuid.UUID, List[str]] = {}
    for name, ids in rank_lists.items():
        for rank, cid in enumerate(ids, start=1):
            scores[cid] = scores.get(cid, 0.0) + 1.0 / (k + rank)
            via.setdefault(cid, []).append(name)
    return [Hit(cid, s, via[cid]) for cid, s in sorted(scores.items(), key=lambda x: -x[1])]


async def hybrid_search(session: AsyncSession, scope: Scope, queries: Sequence[str], top_k: int = TOP_K,
                        rerank_query: Optional[str] = None) -> List[Hit]:
    """Runs every query variant through both retrievers, fuses, reranks against the original question."""
    lists: Dict[str, List[uuid.UUID]] = {}
    for i, q in enumerate(queries):
        lists[f"keyword{i}"] = await keyword_search(session, scope, q, POOL)
        try:
            lists[f"vector{i}"] = await run_model(vector_search, scope, q, POOL)
        except Exception as e:
            logger.warning("vector search unavailable, keyword only: %s", e)
    fused = rrf(lists)[:POOL]
    for h in fused:
        h.via = sorted({v.rstrip("0123456789") for v in h.via})
    if not fused:
        return []

    rows = (await session.execute(select(DocChunk.id, DocChunk.text, DocChunk.section)
                                  .where(DocChunk.id.in_([h.chunk_id for h in fused])))).all()
    text_by_id = {r.id: (f"{r.section}\n{r.text}" if r.section else r.text) for r in rows}
    try:
        scores = await run_model(get_reranker().score, rerank_query or queries[0], [text_by_id.get(h.chunk_id, "") for h in fused])
        for h, s in zip(fused, scores):
            h.score = s
            h.via.append("rerank")
        fused.sort(key=lambda h: -h.score)
    except Exception as e:                           # reranker missing: fused order is still sensible
        logger.warning("reranker unavailable: %s", e)
    return fused[:top_k]


async def neighbours(session: AsyncSession, chunk_id: uuid.UUID) -> tuple[Optional[str], Optional[str]]:
    """Text of the chunk before and after (same document), for context."""
    c = await session.get(DocChunk, chunk_id)
    if not c:
        return None, None
    rows = (await session.execute(select(DocChunk.chunk_index, DocChunk.text).where(
        DocChunk.doc_id == c.doc_id, DocChunk.chunk_index.in_([c.chunk_index - 1, c.chunk_index + 1])))).all()
    by = {r.chunk_index: r.text for r in rows}
    return by.get(c.chunk_index - 1), by.get(c.chunk_index + 1)
