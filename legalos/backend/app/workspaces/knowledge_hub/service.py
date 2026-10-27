"""Documents service: ingest -> structure-aware index -> AI review -> collections -> conversations with cited answers.

Grounding contract: every answer sentence carries a [Cn] marker; every citation's quote is verified against
the stored chunk text (Unicode-aware). Confidence is computed from verification + reranker agreement.
"""
import asyncio
import json
import logging
import os
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import AsyncIterator, Dict, List, Optional, Tuple

from sqlalchemy import and_, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.embeddings.embedder import EMBED_MODEL, run_model
from app.core.rag import document_parser
from app.core.rag.parsing import Page, ParsedDocument
from app.dependencies import RequestContext
from app.shared.audit import log_event
from app.shared.db.models import Document
from app.shared.db.session import async_session_maker
from app.shared.exceptions import BadRequestException, NotFoundException
from app.shared.storage import file_storage
from app.workspaces.compliance_center.models import ComplianceTask
from app.workspaces.contract_intelligence.engine import pipeline as contract_pipeline
from app.workspaces.contract_intelligence.engine import verify
from app.workspaces.contract_intelligence.engine.segmenter import Segment
from app.workspaces.contract_intelligence.service import classify_failure
from app.workspaces.knowledge_hub.engine import ai, chunking, retrieval
from app.workspaces.knowledge_hub.models import ChatTurn, Conversation, DocChunk, KnowledgeDocument

logger = logging.getLogger("legalos.documents")

MAX_FILE_SIZE = 15 * 1024 * 1024
ALLOWED = {"pdf", "docx", "txt", "md", "csv", "xlsx"}
DEFAULT_COLLECTION = "General"
HISTORY_TURNS = 6
_IST = timezone(timedelta(hours=5, minutes=30))


def today_ist() -> date:
    return datetime.now(_IST).date()


def validate_upload(filename: str, data: bytes) -> str:
    if not data:
        raise BadRequestException("The file is empty.")
    if len(data) > MAX_FILE_SIZE:
        raise BadRequestException("File is too large. The maximum is 15 MB.")
    ext = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""
    if ext not in ALLOWED:
        raise BadRequestException(f"'.{ext}' files are not supported. Use PDF, Word, Excel, CSV or text files.")
    if ext == "pdf" and not data.startswith(b"%PDF"):
        raise BadRequestException("This file is named .pdf but is not a valid PDF.")
    if ext in ("docx", "xlsx") and not data.startswith(b"PK"):
        raise BadRequestException(f"This file is named .{ext} but is not a valid {'Word' if ext == 'docx' else 'Excel'} file.")
    return ext


# ------------------------------------------------------------------ presentation

def to_list_item(d: KnowledgeDocument) -> dict:
    return {
        "id": d.id, "title": d.title, "filename": d.filename, "category": d.category or DEFAULT_COLLECTION, "doc_type": d.doc_type,
        "language": d.language,
        "file_type": d.file_type, "page_count": d.page_count, "status": d.status, "stage": d.stage, "review_state": d.review_state,
        "expiry_date": d.expiry_date, "expiry_label": d.expiry_label, "concern_count": len(d.concerns or []),
        "error_kind": d.error_kind, "error_message": d.error_message, "created_at": d.created_at,
    }


def to_detail(d: KnowledgeDocument) -> dict:
    out = to_list_item(d)
    out.update(
        summary_points=d.summary_points or [], key_facts=d.key_facts or [], concerns=d.concerns or [], missing_items=d.missing_items or [],
        suggested_questions=d.suggested_questions or [], review_error=d.review_error, chunk_count=d.chunk_count,
        in_calendar=d.expiry_task_id is not None, ocr_used=d.ocr_used,
        chunks=[{"chunk_index": c.chunk_index, "page": c.page, "section": c.section, "text": c.text} for c in d.chunks[:400]],
    )
    return out


# ------------------------------------------------------------------ create

async def create_upload(session: AsyncSession, ctx: RequestContext, data: bytes, filename: str, category: Optional[str], title: Optional[str]) -> KnowledgeDocument:
    ext = validate_upload(filename, data)
    path = await file_storage.save_file(filename, data, ctx.organization_id)
    try:
        doc = Document(workspace="knowledge_hub", original_filename=filename, storage_path=path, uploaded_by=ctx.user_id, organization_id=ctx.organization_id)
        session.add(doc)
        await session.flush()
        kd = KnowledgeDocument(
            organization_id=ctx.organization_id, document_id=doc.id, created_by=ctx.user_id, filename=filename, file_type=ext.upper(),
            title=(title or "").strip() or os.path.splitext(os.path.basename(filename))[0].replace("_", " ").strip() or "Document",
            category=(category or "").strip() or DEFAULT_COLLECTION, status="processing", stage="queued")
        session.add(kd)
        await session.flush()
        await log_event(session, organization_id=ctx.organization_id, user_id=ctx.user_id, action="document.uploaded",
                        entity_type="document", entity_id=kd.id, meta={"filename": filename})
        await session.commit()
    except Exception:
        await file_storage.delete_file(path)
        raise
    return kd


# ------------------------------------------------------------------ ingest

async def _set(doc_pk: uuid.UUID, **values) -> None:
    async with async_session_maker() as s:
        await s.execute(update(KnowledgeDocument).where(KnowledgeDocument.id == doc_pk).values(**values))
        await s.commit()


def _load(data: bytes, filename: str, on_stage) -> Tuple[ParsedDocument, bool]:
    ext = filename.lower().rsplit(".", 1)[-1]
    if ext in ("csv", "xlsx"):
        text = document_parser.parse_document(data, filename)
        if len(text.strip()) < 20:
            raise BadRequestException("The spreadsheet has no readable content.")
        return ParsedDocument(pages=[Page(1, text)], kind="text", has_pages=False), False
    return contract_pipeline.prepare_document(data, filename, on_stage)


async def run_ingest(doc_pk: uuid.UUID) -> None:
    loop = asyncio.get_running_loop()

    def on_stage(stage: str) -> None:
        try:
            asyncio.run_coroutine_threadsafe(_set(doc_pk, stage=stage), loop).result(timeout=10)
        except Exception as e:
            logger.debug("stage update failed: %s", e)

    async with async_session_maker() as session:
        kd = await session.get(KnowledgeDocument, doc_pk)
        if kd is None:
            return
        org_id, collection = kd.organization_id, kd.category
        try:
            core_doc = await session.get(Document, kd.document_id)
            with open(core_doc.storage_path, "rb") as fh:
                data = fh.read()
            parsed, ocr_used = await asyncio.to_thread(_load, data, core_doc.original_filename, on_stage)
            chunks = chunking.chunk_document(parsed)
            if not chunks:
                raise BadRequestException("No readable text was found in this document.")
            await asyncio.to_thread(retrieval.delete_vectors, doc_pk)
            for old in list((await session.execute(select(DocChunk).where(DocChunk.doc_id == doc_pk))).scalars()):
                await session.delete(old)
            await session.flush()
            rows = [DocChunk(id=uuid.uuid4(), doc_id=doc_pk, organization_id=org_id, chunk_index=c.index, page=c.page,
                             text=c.text, section=c.section, kind=c.kind) for c in chunks]
            session.add_all(rows)
            await session.flush()
            on_stage("indexing")
            await run_model(retrieval.index_vectors, org_id, doc_pk, [r.id for r in rows], [c.embed_text for c in chunks], collection)
            kd.chunk_count, kd.page_count = len(rows), (len(parsed.pages) if parsed.has_pages else None)
            kd.ocr_used, kd.status, kd.stage, kd.embed_model = ocr_used, "ready", "reviewing", EMBED_MODEL
            kd.error_kind = kd.error_message = None
            kd.review_state, kd.review_error = "pending", None
            await session.commit()
        except Exception as exc:
            await session.rollback()
            kind, message = classify_failure(exc)
            (logger.exception if kind == "internal" else logger.warning)("document ingest failed doc=%s kind=%s", doc_pk, kind)
            await _set(doc_pk, status="failed", stage=None, error_kind=kind, error_message=message)
            return

        # ---- AI review: independent of indexing (a failure here leaves the document searchable)
        try:
            result = await asyncio.to_thread(ai.review_document, parsed, chunks, kd.title)
            async with async_session_maker() as s2:
                d = await s2.get(KnowledgeDocument, doc_pk)
                r = result.review
                d.doc_type, d.summary_points, d.language = r.doc_type, r.summary_points, r.language
                d.key_facts = [f.model_dump() for f in r.key_facts[:8]]
                d.concerns, d.missing_items = result.concerns, r.missing_items[:5]
                d.suggested_questions = r.suggested_questions[:4]
                d.expiry_date = result.expiry if result.expiry_verified else None
                d.expiry_label = r.expiry_label if result.expiry_verified else None
                if r.title and (d.title == os.path.splitext(os.path.basename(d.filename or ""))[0].replace("_", " ").strip()):
                    d.title = r.title[:200]
                d.review_state, d.review_error, d.stage, d.prompt_version = "done", None, "done", ai.PROMPT_VERSION
                if result.truncated:
                    d.review_error = "This document is very long; the summary covers the first part only. Search and questions cover all of it."
                await _sync_expiry_task(s2, d)
                await log_event(s2, organization_id=org_id, user_id=None, action="document.reviewed", entity_type="document", entity_id=doc_pk,
                                meta={"concerns": len(result.concerns)})
                await s2.commit()
        except Exception as exc:
            kind, message = classify_failure(exc)
            logger.warning("document review failed doc=%s kind=%s", doc_pk, kind)
            await _set(doc_pk, review_state="failed", review_error=message, stage="done")


async def _sync_expiry_task(session: AsyncSession, d: KnowledgeDocument) -> None:
    task = await session.get(ComplianceTask, d.expiry_task_id) if d.expiry_task_id else None
    if not d.expiry_date or d.expiry_date < today_ist():
        if task:
            await session.delete(task)
            d.expiry_task_id = None
        return
    title = f"{d.expiry_label or 'Document expires'}: {d.title}"[:190]
    desc = f"From your document \"{d.title}\". Check whether it needs renewing before this date."
    if task is None:
        task = ComplianceTask(organization_id=d.organization_id, user_id=d.created_by, title=title, category="license",
                              due_date=d.expiry_date, description=desc, is_custom=True, status="pending")
        session.add(task)
        await session.flush()
        d.expiry_task_id = task.id
    else:
        task.title, task.due_date, task.description = title, d.expiry_date, desc


_background: set = set()


async def recover_at_startup() -> int:
    """Resumes document work a restart cut short, instead of leaving it for the user to retry:
    - documents still marked processing (ingest was interrupted),
    - documents whose AI review never finished (review_state pending),
    - documents indexed with a previous embedding model.
    They are re-run one at a time in the background (the model pool is small); the review prompt is cached,
    so re-running a document that was already reviewed does not spend AI quota."""
    async with async_session_maker() as s:
        ids = list((await s.execute(select(KnowledgeDocument.id).where(or_(
            KnowledgeDocument.status == "processing",
            and_(KnowledgeDocument.status == "failed", KnowledgeDocument.error_kind == "interrupted"),
            and_(KnowledgeDocument.status == "ready", KnowledgeDocument.review_state == "pending"),
            and_(KnowledgeDocument.status == "ready", (KnowledgeDocument.embed_model.is_(None)) | (KnowledgeDocument.embed_model != EMBED_MODEL)),
        )).order_by(KnowledgeDocument.created_at))).scalars())
    if not ids:
        return 0
    for pk in ids:
        await _set(pk, status="processing", stage="queued", error_kind=None, error_message=None)

    async def _run_all():
        for pk in ids:
            try:
                await run_ingest(pk)
            except Exception as e:                      # one bad document must not stop the rest
                logger.warning("recovery failed for %s: %s", pk, e)

    task = asyncio.create_task(_run_all())
    _background.add(task)
    task.add_done_callback(_background.discard)
    return len(ids)


# ------------------------------------------------------------------ documents

async def _get(session: AsyncSession, ctx: RequestContext, doc_id: uuid.UUID) -> KnowledgeDocument:
    stmt = (select(KnowledgeDocument).where(KnowledgeDocument.id == doc_id, KnowledgeDocument.organization_id == ctx.organization_id)
            .options(selectinload(KnowledgeDocument.chunks)).execution_options(populate_existing=True))
    d = (await session.execute(stmt)).scalar_one_or_none()
    if not d:
        raise NotFoundException("Document not found.")
    return d


async def list_documents(session: AsyncSession, ctx: RequestContext, collection: Optional[str] = None) -> List[dict]:
    stmt = select(KnowledgeDocument).where(KnowledgeDocument.organization_id == ctx.organization_id)
    if collection:
        stmt = stmt.where(func.coalesce(KnowledgeDocument.category, DEFAULT_COLLECTION) == collection)
    rows = (await session.execute(stmt.order_by(KnowledgeDocument.created_at.desc()))).scalars().all()
    return [to_list_item(d) for d in rows]


async def list_collections(session: AsyncSession, ctx: RequestContext) -> List[dict]:
    col = func.coalesce(KnowledgeDocument.category, DEFAULT_COLLECTION)
    rows = (await session.execute(
        select(col, func.count(), func.count().filter(KnowledgeDocument.status == "ready"))
        .where(KnowledgeDocument.organization_id == ctx.organization_id).group_by(col).order_by(col))).all()
    return [{"name": n, "count": c, "ready": r} for n, c, r in rows]


async def get_detail(session: AsyncSession, ctx: RequestContext, doc_id: uuid.UUID) -> dict:
    return to_detail(await _get(session, ctx, doc_id))


async def update_document(session: AsyncSession, ctx: RequestContext, doc_id: uuid.UUID, title: Optional[str], category: Optional[str]) -> KnowledgeDocument:
    d = await _get(session, ctx, doc_id)
    if title and title.strip():
        d.title = title.strip()[:200]
    if category is not None:
        d.category = category.strip() or DEFAULT_COLLECTION
    await session.commit()
    return d


async def prepare_retry(session: AsyncSession, ctx: RequestContext, doc_id: uuid.UUID) -> KnowledgeDocument:
    d = await _get(session, ctx, doc_id)
    if d.status == "processing":
        raise BadRequestException("This document is already being processed.")
    d.status, d.stage, d.error_kind, d.error_message = "processing", "queued", None, None
    await session.commit()
    return d


async def get_file(session: AsyncSession, ctx: RequestContext, doc_id: uuid.UUID) -> Tuple[str, str]:
    d = await _get(session, ctx, doc_id)
    core = await session.get(Document, d.document_id) if d.document_id else None
    if not core or not os.path.exists(core.storage_path):
        raise NotFoundException("The original file is no longer available.")
    return core.storage_path, core.original_filename


async def delete_document(session: AsyncSession, ctx: RequestContext, doc_id: uuid.UUID) -> None:
    d = await _get(session, ctx, doc_id)
    if d.expiry_task_id:
        t = await session.get(ComplianceTask, d.expiry_task_id)
        if t:
            await session.delete(t)
    core = await session.get(Document, d.document_id) if d.document_id else None
    path = core.storage_path if core else None
    await asyncio.to_thread(retrieval.delete_vectors, doc_id)
    await log_event(session, organization_id=ctx.organization_id, user_id=ctx.user_id, action="document.deleted", entity_type="document", entity_id=doc_id)
    await session.delete(d)
    if core:
        await session.delete(core)
    await session.commit()
    if path:
        await file_storage.delete_file(path)


# ------------------------------------------------------------------ retrieval helpers

async def _scope(session: AsyncSession, ctx: RequestContext, collection: Optional[str]) -> retrieval.Scope:
    if not collection:
        return retrieval.Scope(ctx.organization_id)
    ids = list((await session.execute(select(KnowledgeDocument.id).where(
        KnowledgeDocument.organization_id == ctx.organization_id,
        func.coalesce(KnowledgeDocument.category, DEFAULT_COLLECTION) == collection))).scalars())
    return retrieval.Scope(ctx.organization_id, ids)


async def _load_hits(session: AsyncSession, ctx: RequestContext, hits, with_neighbours: bool = False) -> List[ai.Excerpt]:
    ids = [h.chunk_id for h in hits]
    rows = (await session.execute(
        select(DocChunk, KnowledgeDocument.title).join(KnowledgeDocument, KnowledgeDocument.id == DocChunk.doc_id)
        .where(DocChunk.id.in_(ids), DocChunk.organization_id == ctx.organization_id))).all()
    by_id = {c.id: (c, t) for c, t in rows}
    items: List[ai.Excerpt] = []
    for h in hits:
        if h.chunk_id in by_id:
            c, title = by_id[h.chunk_id]
            e = ai.Excerpt(marker=f"C{len(items) + 1}", doc_id=str(c.doc_id), doc_title=title, page=c.page, text=c.text,
                           via=h.via, section=c.section, rerank=h.score if "rerank" in h.via else None)
            if with_neighbours:
                e.before, e.after = await retrieval.neighbours(session, c.id)
            items.append(e)
    return items


def _snippet(text: str, query: str, width: int = 320) -> str:
    flat = " ".join(text.split())
    low = flat.lower()
    words = [w for w in "".join(ch if ch.isalnum() else " " for ch in query.lower()).split() if len(w) > 2]
    pos = -1
    for w in sorted(words, key=len, reverse=True):
        pos = low.find(w)
        if pos >= 0:
            break
    if pos < 0 or len(flat) <= width:
        return flat[:width] + ("…" if len(flat) > width else "")
    start = max(0, pos - width // 3)
    end = min(len(flat), start + width)
    return ("…" if start > 0 else "") + flat[start:end] + ("…" if end < len(flat) else "")


async def search(session: AsyncSession, ctx: RequestContext, query: str, collection: Optional[str] = None) -> List[dict]:
    scope = await _scope(session, ctx, collection)
    hits = await retrieval.hybrid_search(session, scope, [query], top_k=8)
    items = await _load_hits(session, ctx, hits)
    return [{"document_id": uuid.UUID(e.doc_id), "document_title": e.doc_title, "page": e.page, "section": e.section,
             "snippet": _snippet(e.text, query), "via": e.via} for e in items]


# ------------------------------------------------------------------ conversations

def _conv_out(c: Conversation) -> dict:
    return {"id": c.id, "title": c.title, "collection": c.collection, "created_at": c.created_at, "updated_at": c.updated_at}


def _turn_out(t: ChatTurn) -> dict:
    return {"id": t.id, "role": t.role, "content": t.content, "citations": t.citations or [], "sources": t.sources or [],
            "found_in_documents": t.found_in_documents, "confidence": t.confidence, "created_at": t.created_at}


async def _conv(session: AsyncSession, ctx: RequestContext, conv_id: uuid.UUID, with_turns: bool = False) -> Conversation:
    stmt = select(Conversation).where(Conversation.id == conv_id, Conversation.organization_id == ctx.organization_id)
    if with_turns:
        stmt = stmt.options(selectinload(Conversation.messages)).execution_options(populate_existing=True)
    c = (await session.execute(stmt)).scalar_one_or_none()
    if not c:
        raise NotFoundException("Conversation not found.")
    return c


async def list_conversations(session: AsyncSession, ctx: RequestContext) -> List[dict]:
    rows = (await session.execute(select(Conversation).where(Conversation.organization_id == ctx.organization_id)
                                  .order_by(Conversation.updated_at.desc()).limit(100))).scalars().all()
    return [_conv_out(c) for c in rows]


async def create_conversation(session: AsyncSession, ctx: RequestContext, collection: Optional[str], title: Optional[str]) -> dict:
    c = Conversation(organization_id=ctx.organization_id, created_by=ctx.user_id, collection=collection or None,
                     title=(title or "").strip() or "New chat")
    session.add(c)
    await session.commit()
    await session.refresh(c)
    return _conv_out(c)


async def get_conversation(session: AsyncSession, ctx: RequestContext, conv_id: uuid.UUID) -> dict:
    c = await _conv(session, ctx, conv_id, with_turns=True)
    return {**_conv_out(c), "turns": [_turn_out(t) for t in c.messages]}


async def update_conversation(session: AsyncSession, ctx: RequestContext, conv_id: uuid.UUID, title: Optional[str], collection: Optional[str], set_collection: bool) -> dict:
    c = await _conv(session, ctx, conv_id)
    if title:
        c.title = title.strip()[:120]
    if set_collection:
        c.collection = collection or None
    c.updated_at = datetime.now(timezone.utc)
    await session.commit()
    return _conv_out(c)


async def delete_conversation(session: AsyncSession, ctx: RequestContext, conv_id: uuid.UUID) -> None:
    c = await _conv(session, ctx, conv_id)
    await session.delete(c)
    await session.commit()


async def suggestions(session: AsyncSession, ctx: RequestContext, collection: Optional[str]) -> List[str]:
    """Questions the documents can actually answer (from each document's review), mixed across documents."""
    stmt = select(KnowledgeDocument.suggested_questions).where(KnowledgeDocument.organization_id == ctx.organization_id,
                                                                KnowledgeDocument.suggested_questions.is_not(None))
    if collection:
        stmt = stmt.where(func.coalesce(KnowledgeDocument.category, DEFAULT_COLLECTION) == collection)
    lists = [q for (q,) in (await session.execute(stmt.order_by(KnowledgeDocument.created_at.desc()).limit(8))).all() if q]
    out: List[str] = []
    for i in range(4):
        for qs in lists:
            if i < len(qs) and qs[i] not in out:
                out.append(qs[i])
            if len(out) >= 4:
                return out
    return out


def _history_text(turns: List[ChatTurn]) -> str:
    recent = turns[-HISTORY_TURNS:]
    return "\n".join(f"{t.role.upper()}: {t.content[:600]}" for t in recent)


def _build_citations(ans: ai.DocAnswer, items: List[ai.Excerpt]) -> Tuple[List[dict], int]:
    by_marker = {e.marker: e for e in items}
    all_segs = [Segment(id=x.marker, number=None, heading="", text=x.text, page_start=x.page, page_end=x.page) for x in items]
    citations: List[dict] = []
    verified = 0
    for c in ans.citations[:8]:
        marker = c.excerpt.strip().upper().replace("[", "").replace("]", "")
        e = by_marker.get(marker)
        m = verify.find_quote(c.quote, [s for s in all_segs if s.id == marker] or all_segs)
        if not m.verified and e is None:
            m = verify.find_quote(c.quote, all_segs)
        src = by_marker.get(m.segment_id or "") or e
        verified += 1 if m.verified else 0
        citations.append({"marker": marker, "quote": c.quote, "document_id": src.doc_id if src else None,
                          "document_title": src.doc_title if src else None, "page": m.page if m.verified else (src.page if src else None),
                          "section": src.section if src else None, "verified": m.verified, "exact": m.exact})
    if not citations:
        return [], 0
    share = verified / len(citations)
    top = max((e.rerank for e in items if e.rerank is not None), default=None)
    agreement = 1.0 if top is None else (1.0 if top > 2 else 0.7 if top > 0 else 0.4)
    return citations, int(round(100 * (0.7 * share + 0.3 * agreement)))


def _not_found() -> dict:
    return {"content": "I couldn't find anything in your documents about this. Try different words, or add the document that would have the answer.",
            "found_in_documents": False, "citations": [], "sources": [], "confidence": 0}


async def _ready_docs(session: AsyncSession, ctx: RequestContext, collection: Optional[str]) -> List[KnowledgeDocument]:
    q = select(KnowledgeDocument).where(KnowledgeDocument.organization_id == ctx.organization_id, KnowledgeDocument.status == "ready")
    if collection:
        q = q.where(func.coalesce(KnowledgeDocument.category, DEFAULT_COLLECTION) == collection)
    return list((await session.execute(q.order_by(KnowledgeDocument.created_at.desc()))).scalars())


def _conversation_reply(docs: List[KnowledgeDocument], collection: Optional[str]) -> dict:
    """Greetings, thanks and 'what can you do': answered without AI or search."""
    where = f"the {collection} collection" if collection else "your documents"
    if not docs:
        text = f"I answer questions from {where}, quoting the exact passage each answer comes from. There are no documents here yet, so add one to get started."
    else:
        names = ", ".join(f"\u201c{d.title}\u201d" for d in docs[:5]) + (f" and {len(docs) - 5} more" if len(docs) > 5 else "")
        hint = next((q for d in docs for q in (d.suggested_questions or [])), None)
        plural = "s" if len(docs) != 1 else ""
        text = (f"I answer questions from {where} and quote the exact passage each answer comes from. "
                f"Right now that covers {len(docs)} document{plural}: {names}. "
                "You can ask for a summary of any of them, or a specific fact." + (f" For example: \u201c{hint}\u201d" if hint else ""))
    return {"content": text, "found_in_documents": False, "citations": [], "sources": [], "confidence": 0}


STOP_WORDS = {"the", "document", "file", "this", "that", "doc", "about", "summary", "summarise", "summarize"}


async def _overview_items(session: AsyncSession, ctx: RequestContext, docs: List[KnowledgeDocument], target: Optional[str]) -> List[ai.Excerpt]:
    """One excerpt per document: its AI profile plus the opening text, so a summary can still be cited verbatim."""
    chosen = docs
    if target:
        words = [w for w in "".join(ch if ch.isalnum() else " " for ch in target.lower()).split() if len(w) > 2 and w not in STOP_WORDS]
        matched = [d for d in docs if any(w in f"{d.title} {d.doc_type or ''} {d.filename or ''}".lower() for w in words)]
        chosen = matched or docs
    items: List[ai.Excerpt] = []
    for d in chosen[:6]:
        opening = list((await session.execute(select(DocChunk).where(DocChunk.doc_id == d.id).order_by(DocChunk.chunk_index).limit(3))).scalars())
        profile = [f"Document: {d.title}" + (f" ({d.doc_type})" if d.doc_type else "") + (f", language {d.language}" if d.language else "")]
        if d.summary_points:
            profile.append("Summary: " + " ".join(f"\u2022 {pt}" for pt in d.summary_points))
        if d.key_facts:
            profile.append("Key facts: " + "; ".join(f"{f.get('label')}: {f.get('value')}" for f in d.key_facts if isinstance(f, dict)))
        head = "\n".join(profile)
        body = "\n\n".join(c.text for c in opening)[:2500]
        items.append(ai.Excerpt(marker=f"C{len(items) + 1}", doc_id=str(d.id), doc_title=d.title, page=opening[0].page if opening else None,
                                text=f"{head}\n\nOpening text:\n{body}", via=["overview"], section="Overview"))
    return items


async def _answer_core(session: AsyncSession, ctx: RequestContext, conv: Conversation, question: str) -> dict:
    history = _history_text(conv.messages)
    plan = await asyncio.to_thread(ai.plan_query, question, history)
    if plan.intent == "conversation" or not plan.answerable_from_documents:
        return _conversation_reply(await _ready_docs(session, ctx, conv.collection), conv.collection)
    if plan.intent == "overview":
        items = await _overview_items(session, ctx, await _ready_docs(session, ctx, conv.collection), plan.target_document)
        if not items:
            return _conversation_reply([], conv.collection)
        ans = await asyncio.to_thread(ai.answer_question, plan.standalone_question, items, history, True)
    else:
        scope = await _scope(session, ctx, conv.collection)
        hits = await retrieval.hybrid_search(session, scope, plan.search_queries, top_k=retrieval.TOP_K, rerank_query=plan.standalone_question)
        items = await _load_hits(session, ctx, hits, with_neighbours=True)
        if not items:
            return _not_found()
        ans = await asyncio.to_thread(ai.answer_question, plan.standalone_question, items, history)
    citations, confidence = _build_citations(ans, items)
    text = ans.answer.strip()
    if ans.found_in_documents and citations and not any(c["verified"] for c in citations):
        text += "\n\n(I could not match this to an exact passage, so please check the document itself.)"
    sources = [{"marker": e.marker, "document_id": uuid.UUID(e.doc_id), "document_title": e.doc_title, "page": e.page,
                "section": e.section, "text": e.text, "via": e.via} for e in items]
    return {"content": text, "found_in_documents": ans.found_in_documents, "citations": citations, "sources": sources,
            "confidence": confidence if ans.found_in_documents else 0}


async def ask(session: AsyncSession, ctx: RequestContext, conv_id: uuid.UUID, question: str) -> dict:
    conv = await _conv(session, ctx, conv_id, with_turns=True)
    q = question.strip()
    result = await _answer_core(session, ctx, conv, q)
    session.add(ChatTurn(conversation_id=conv.id, role="user", content=q))
    reply = ChatTurn(conversation_id=conv.id, role="assistant", content=result["content"], citations=result["citations"],
                     sources=[{**s, "document_id": str(s["document_id"])} for s in result["sources"]],
                     found_in_documents=result["found_in_documents"], confidence=result["confidence"])
    session.add(reply)
    if conv.title == "New chat":
        conv.title = (q[:60] + ("…" if len(q) > 60 else ""))
    conv.updated_at = datetime.now(timezone.utc)
    await log_event(session, organization_id=ctx.organization_id, user_id=ctx.user_id, action="document.question_asked",
                    entity_type="conversation", entity_id=conv.id, meta={"found": result["found_in_documents"]})
    await session.commit()
    await session.refresh(reply)
    return _turn_out(reply)


async def ask_stream(ctx: RequestContext, conv_id: uuid.UUID, question: str) -> AsyncIterator[str]:
    """Server-sent events: stage updates while retrieving, then the answer streamed in word groups, then the final turn.
    Owns its database session: a request-scoped session is only released after the whole body is sent, and a
    streamed body can be abandoned by the client, which left connections idle-in-transaction."""
    def ev(kind: str, data) -> str:
        return f"event: {kind}\ndata: {json.dumps(data, default=str, ensure_ascii=False)}\n\n"
    try:
        yield ev("stage", {"stage": "searching"})
        async with async_session_maker() as session:
            turn = await ask(session, ctx, conv_id, question)
        yield ev("stage", {"stage": "writing"})
        words = turn["content"].split(" ")
        step = 6
        for i in range(0, len(words), step):
            yield ev("delta", {"text": " ".join(words[i:i + step]) + (" " if i + step < len(words) else "")})
            await asyncio.sleep(0.02)
        yield ev("done", turn)
    except Exception as exc:
        kind, message = classify_failure(exc)
        logger.warning("ask failed conv=%s kind=%s: %s", conv_id, kind, str(exc)[:200])
        yield ev("error", {"kind": kind, "message": message})
