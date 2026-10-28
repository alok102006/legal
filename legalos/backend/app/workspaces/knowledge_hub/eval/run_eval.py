"""Retrieval evaluation for the Documents workspace.

Indexes the synthetic documents in dataset.json into a throw-away organisation (with the doc type and summary an
ingest review would have produced, so document routing is exercised), runs every question through the real retrieval
stack (exact-token + keyword + vector + RRF + document routing + reranker) and reports hit@1 / hit@k: whether a passage
containing the expected answer text is the top result / among the passages handed to the model.

Question options in dataset.json:
- `history` + `standalone`: a follow-up. Without the LLM the given standalone rewrite is searched (that is what the
  planner produces); with --with-llm the planner rewrites it from the history.
- `sub` + `expect_all`: a multi-part question. Every part must be found; hit@1 means the first part ranks first.

No AI quota is used unless --with-llm is passed, which also runs the query planner and the answer model and reports
the verified-citation rate.

    docker compose exec -T backend python -m app.workspaces.knowledge_hub.eval.run_eval [--with-llm]
"""
import argparse
import asyncio
import inspect
import json
import sys
import time
import uuid
from pathlib import Path
from typing import List, Optional

from app.core.rag.parsing import parse_text_bytes
from app.shared.db.models import Organization
from app.shared.db.session import async_session_maker
from app.workspaces.knowledge_hub.engine import ai, retrieval
from app.workspaces.knowledge_hub.engine.chunking import chunk_document
from app.workspaces.knowledge_hub.models import DocChunk, KnowledgeDocument

DATASET = Path(__file__).with_name("dataset.json")


def _norm(s: str) -> str:
    return " ".join(s.split()).lower()


def _rank(texts: list, doc_id: uuid.UUID, expect: str) -> Optional[int]:
    want = _norm(expect)
    ranks = [i for i, (did, t) in enumerate(texts) if did == doc_id and want in _norm(t)]
    return ranks[0] + 1 if ranks else None


def _queries(item: dict, with_llm: bool) -> tuple[List[str], str, List[str]]:
    """-> (search queries, rerank question, sub-questions) for one dataset item."""
    if with_llm:
        plan = ai.plan_query(item["q"], item.get("history", ""))
        return plan.search_queries or [item["q"]], plan.standalone_question, plan.sub_questions
    question = item.get("standalone", item["q"])
    subs = item.get("sub", [])
    return list(dict.fromkeys([question, *subs])), question, subs


async def main(with_llm: bool) -> int:
    data = json.loads(DATASET.read_text(encoding="utf-8"))
    org = uuid.uuid4()
    doc_ids: dict[str, uuid.UUID] = {}
    results = []
    accepts_subs = "sub_questions" in inspect.signature(retrieval.hybrid_search).parameters
    async with async_session_maker() as s:
        s.add(Organization(id=org, legal_name="documents-eval"))
        await s.flush()
        try:
            for d in data["documents"]:
                doc_id = uuid.uuid4()
                s.add(KnowledgeDocument(id=doc_id, organization_id=org, title=d["title"], category=d["collection"], status="ready",
                                        doc_type=d.get("doc_type"), summary_points=d.get("summary")))
                await s.flush()
                chunks = chunk_document(parse_text_bytes(d["text"].encode()))
                rows = [DocChunk(id=uuid.uuid4(), doc_id=doc_id, organization_id=org, chunk_index=c.index, page=c.page,
                                 text=c.text, section=c.section, kind=c.kind) for c in chunks]
                s.add_all(rows)
                await s.flush()
                await asyncio.to_thread(retrieval.index_vectors, org, doc_id, [r.id for r in rows], [c.embed_text for c in chunks], d["collection"])
                doc_ids[d["key"]] = doc_id
            await s.commit()

            scope = retrieval.Scope(org)
            for item in data["questions"]:
                t0 = time.time()
                queries, question, subs = _queries(item, with_llm)
                extra = {"sub_questions": subs} if accepts_subs else {}
                hits = await retrieval.hybrid_search(s, scope, queries, top_k=retrieval.TOP_K, rerank_query=question, **extra)
                texts = []
                for h in hits:
                    c = await s.get(DocChunk, h.chunk_id)
                    texts.append((c.doc_id, (c.section or "") + " " + c.text))
                parts = item.get("expect_all") or [{"doc": item["doc"], "expect": item["expect"]}]
                ranks = [_rank(texts, doc_ids[p["doc"]], p["expect"]) for p in parts]
                rank = None if None in ranks else (ranks[0] if len(ranks) == 1 else max(1, max(ranks) - len(ranks) + 1))
                row = {"q": item["q"], "rank": rank, "ms": int((time.time() - t0) * 1000), "tags": item.get("tags", [])}
                if with_llm and hits:
                    items = [ai.Excerpt(marker=f"C{i + 1}", doc_id=str(did), doc_title="", page=None, section=None, text=t, via=h.via, rerank=h.score)
                             for i, ((did, t), h) in enumerate(zip(texts, hits))]
                    ans = ai.answer_question(question, items, item.get("history", ""))
                    row["found"] = ans.found_in_documents
                    row["verified"] = sum(1 for c in ans.citations if _norm(c.quote) in _norm(" ".join(t for _, t in texts)))
                    row["citations"] = len(ans.citations)
                results.append(row)
        finally:
            await s.delete(await s.get(Organization, org))      # cascades documents and chunks
            await s.commit()
            for d in doc_ids.values():
                retrieval.delete_vectors(d)

    n = len(results)
    hit1 = sum(1 for r in results if r["rank"] == 1)
    hitk = sum(1 for r in results if r["rank"] is not None)
    print(f"\nDocuments retrieval eval — {n} questions over {len(doc_ids)} documents (planner {'on' if with_llm else 'off'}, k={retrieval.TOP_K})")
    for r in results:
        mark = "OK " if r["rank"] == 1 else ("ok " if r["rank"] else "MISS")
        extra = f"  found={r['found']} verified={r['verified']}/{r['citations']}" if "found" in r else ""
        tags = f" [{','.join(r['tags'])}]" if r["tags"] else ""
        print(f"  {mark} rank={r['rank'] or '-'} {r['ms']:4d}ms  {r['q']}{tags}{extra}")
    print(f"\n  hit@1 = {hit1}/{n} ({100 * hit1 // n}%)   hit@{retrieval.TOP_K} = {hitk}/{n} ({100 * hitk // n}%)")
    if with_llm:
        cited = sum(r.get("citations", 0) for r in results)
        ver = sum(r.get("verified", 0) for r in results)
        print(f"  verified citations = {ver}/{cited}   answered = {sum(1 for r in results if r.get('found'))}/{n}")
    return 0 if hitk == n else 1


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--with-llm", action="store_true", help="also run the query planner and answer model (uses AI quota)")
    sys.exit(asyncio.run(main(ap.parse_args().with_llm)))
