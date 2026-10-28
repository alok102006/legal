"""Documents service: ingest -> structure-aware index -> AI review -> collections -> conversations with cited answers.

Grounding contract: every answer sentence carries a [Cn] marker; every citation's quote is verified against
the stored chunk text (Unicode-aware). Confidence is computed from verification + reranker agreement.
"""
import asyncio
import json
import logging
import os
import re
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import AsyncIterator, Dict, List, Optional, Sequence, Tuple

from sqlalchemy import and_, delete, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.embeddings.embedder import EMBED_MODEL, run_model
from app.core.rag import parsing
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
IMAGE_TYPES = contract_pipeline.IMAGE_TYPES                       # png / jpg / jpeg / webp, read with AI OCR
ALLOWED = {"pdf", "docx", "txt", "md", "csv", "xlsx", *IMAGE_TYPES}
DEFAULT_COLLECTION = "General"
HISTORY_TURNS = 6
OVERVIEW_DIRECT_CHUNKS = 6          # above this, an overview of one document goes through a digest of all of it
INDEX_VERSION = f"{EMBED_MODEL}|{chunking.CHUNKER_VERSION}"      # stored in docs.embed_model once vectors are in
PENDING_VECTORS = f"pending|{chunking.CHUNKER_VERSION}"           # chunks stored, vectors still to be written
_IST = timezone(timedelta(hours=5, minutes=30))
_OLE_MAGIC = b"\xd0\xcf\x11\xe0"
_IMAGE_MAGIC = {"png": (b"\x89PNG",), "jpg": (b"\xff\xd8",), "jpeg": (b"\xff\xd8",), "webp": (b"RIFF",)}


def today_ist() -> date:
    return datetime.now(_IST).date()


def validate_upload(filename: str, data: bytes) -> str:
    if not data:
        raise BadRequestException("The file is empty.")
    if len(data) > MAX_FILE_SIZE:
        raise BadRequestException("File is too large. The maximum is 15 MB.")
    ext = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""
    if ext in ("doc", "xls"):
        raise BadRequestException(f"Old .{ext} files are not supported. Open it and save it as .{ext}x, then upload again.")
    if ext not in ALLOWED:
        raise BadRequestException(f"'.{ext}' files are not supported. Use PDF, Word, Excel, CSV, text or image (PNG/JPG) files.")
    if ext == "pdf" and not data.startswith(b"%PDF"):
        raise BadRequestException("This file is named .pdf but is not a valid PDF.")
    if ext in ("docx", "xlsx") and data.startswith(_OLE_MAGIC):
        raise BadRequestException(f"This {'Word' if ext == 'docx' else 'Excel'} file is password-protected. Remove the password and upload it again.")
    if ext in ("docx", "xlsx") and not data.startswith(b"PK"):
        raise BadRequestException(f"This file is named .{ext} but is not a valid {'Word' if ext == 'docx' else 'Excel'} file.")
    if ext in ("txt", "md", "csv") and b"\x00" in data[:4096] and not data.startswith((b"\xff\xfe", b"\xfe\xff")):
        raise BadRequestException("This does not look like a text file.")
    if ext in _IMAGE_MAGIC and not data.startswith(_IMAGE_MAGIC[ext]):
        raise BadRequestException(f"This file is named .{ext} but is not a valid image.")
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


def pdf_subset(data: bytes, numbers: Sequence[int]) -> bytes:
    """A new PDF holding only the given 1-based pages. pypdfium2 ships with pdfplumber, so this needs no extra
    dependency."""
    import io

    import pypdfium2 as pdfium

    src, out = pdfium.PdfDocument(data), pdfium.PdfDocument.new()
    try:
        out.import_pages(src, pages=[n - 1 for n in numbers])
        buf = io.BytesIO()
        out.save(buf)
        return buf.getvalue()
    finally:
        out.close()
        src.close()


def _ocr_pdf(data: bytes, on_stage) -> ParsedDocument:
    """The shared contract OCR path (batched page-wise Gemini OCR). It returns (document, calls) in newer
    versions of the contracts engine and the bare document in older ones; only the document is needed here."""
    out = contract_pipeline.ocr_pdf(data, on_stage)
    return out[0] if isinstance(out, tuple) else out


def _ocr_pages(data: bytes, parsed: ParsedDocument, numbers: List[int], on_stage) -> ParsedDocument:
    """OCR only the listed pages of a PDF (a typed policy with a scanned signature page or annexure) and put the
    text back in place. Uses the shared contract OCR path on a PDF cut down to those pages."""
    ocr = _ocr_pdf(pdf_subset(data, numbers), on_stage)
    by_number = {numbers[p.number - 1]: p.text for p in ocr.pages if 0 < p.number <= len(numbers)}
    pages = [Page(p.number, by_number.get(p.number, p.text)) for p in parsed.pages]
    return ParsedDocument(pages=pages, kind="pdf", has_pages=True,
                          warnings=parsed.warnings + [f"Pages {', '.join(map(str, sorted(by_number)))} were scanned and read with AI OCR; please double-check key figures."])


def load_document(data: bytes, filename: str, on_stage) -> Tuple[ParsedDocument, bool]:
    """Bytes -> (ParsedDocument, ocr_used) for any supported file. Images and scanned PDFs go through the shared
    Gemini OCR path (whole document when it is all scanned, otherwise only the image-only pages). Raises
    DocumentParseError / BadRequestException with a message the user can act on."""
    on_stage("parsing")
    ext = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""
    if ext in IMAGE_TYPES:
        on_stage("ocr")
        return contract_pipeline.ocr_image(data, IMAGE_TYPES[ext]), True
    parsed = parsing.parse_company_document(data, filename)
    ocr_used = False
    if parsed.kind == "pdf" and parsed.is_scanned:
        parsed, ocr_used = _ocr_pdf(data, on_stage), True
    elif parsed.kind == "pdf" and parsed.image_pages:
        try:
            parsed, ocr_used = _ocr_pages(data, parsed, parsed.image_pages, on_stage), True
        except BadRequestException as e:              # nothing legible on those pages: keep the typed text
            logger.info("partial OCR found no text: %s", e.detail)
    if not parsed.text.strip():
        raise parsing.DocumentParseError("empty", "No readable text was found in this document.")
    return parsed, ocr_used


def _chunks_from_rows(rows: Sequence[DocChunk]) -> List[chunking.Chunk]:
    return [chunking.Chunk(r.chunk_index, r.page, r.text, r.section, r.kind,
                           chunking.table_reading(r.text) if r.kind == "table" else None) for r in rows]


def _parsed_from_chunks(chunks: Sequence[chunking.Chunk], has_pages: bool) -> ParsedDocument:
    """Rebuilds page text from stored chunks (headings re-inserted) so an OCR'd document can be reviewed again
    without paying for OCR twice."""
    pages: Dict[int, List[str]] = {}
    last_section: Optional[str] = None
    for c in chunks:
        lines = pages.setdefault(c.page or 1, [])
        if c.section and c.section != last_section:
            lines.append(c.section.split(" > ")[-1])
            last_section = c.section
        lines.append(c.text)
    return ParsedDocument(pages=[Page(n, "\n\n".join(t)) for n, t in sorted(pages.items())], kind="text", has_pages=has_pages)


_running: set = set()


async def run_ingest(doc_pk: uuid.UUID) -> None:
    """Background job: parse -> chunk -> store (keyword-searchable) -> vectors -> AI review. Idempotent and
    resumable: a second run for the same document while one is going is ignored; stored chunks of the current
    chunker version are reused (no re-parse, no second OCR bill); vectors are written only if missing; the review
    runs only if it is not done. When Qdrant is down the document is still `ready` and keyword-searchable; its
    vectors are written by the next run (recover_at_startup picks it up)."""
    if doc_pk in _running:
        return
    _running.add(doc_pk)
    try:
        await _ingest(doc_pk)
    finally:
        _running.discard(doc_pk)


async def _ingest(doc_pk: uuid.UUID) -> None:
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
        stored = list((await session.execute(select(DocChunk).where(DocChunk.doc_id == doc_pk).order_by(DocChunk.chunk_index))).scalars())
        current = (kd.embed_model or "").endswith("|" + chunking.CHUNKER_VERSION)
        reuse = bool(stored) and (current or kd.ocr_used)
        reparsed = not reuse
        try:
            if reuse:
                chunks = _chunks_from_rows(stored)
                rows = stored
                parsed = None
            else:
                core_doc = await session.get(Document, kd.document_id)
                if core_doc is None:
                    raise FileNotFoundError(kd.document_id)
                with open(core_doc.storage_path, "rb") as fh:
                    data = fh.read()
                parsed, ocr_used = await asyncio.to_thread(load_document, data, core_doc.original_filename, on_stage)
                chunks = chunking.chunk_document(parsed)
                if not chunks:
                    raise parsing.DocumentParseError("empty", "No readable text was found in this document.")
                await asyncio.to_thread(retrieval.delete_vectors, doc_pk)
                await session.execute(delete(DocChunk).where(DocChunk.doc_id == doc_pk))
                rows = [DocChunk(id=uuid.uuid4(), doc_id=doc_pk, organization_id=org_id, chunk_index=c.index, page=c.page,
                                 text=c.text, section=c.section, kind=c.kind) for c in chunks]
                session.add_all(rows)
                kd.chunk_count, kd.page_count = len(rows), (len(parsed.pages) if parsed.has_pages else None)
                kd.ocr_used, kd.embed_model = ocr_used, PENDING_VECTORS
                kd.review_state, kd.review_error = "pending", None
            kd.status, kd.stage, kd.error_kind, kd.error_message = "ready", "indexing", None, None
            await session.commit()                                   # from here on the document is keyword-searchable
        except Exception as exc:
            await session.rollback()
            kind, message = classify_failure(exc)
            if isinstance(exc, FileNotFoundError):
                message = "The original file could not be found. Please upload the document again."
            (logger.exception if kind == "internal" else logger.warning)("document ingest failed doc=%s kind=%s", doc_pk, kind)
            await _set(doc_pk, status="failed", stage=None, error_kind=kind, error_message=message)
            return

        if kd.embed_model != INDEX_VERSION:
            try:
                await run_model(retrieval.index_vectors, org_id, doc_pk, [r.id for r in rows],
                                [c.embed_text for c in chunks], collection)
                await _set(doc_pk, embed_model=INDEX_VERSION)
            except Exception as e:                                   # Qdrant down: keyword search still works
                logger.warning("vector indexing deferred for doc=%s: %s", doc_pk, e)
                await _set(doc_pk, embed_model=PENDING_VECTORS)
        needs_review = reparsed or kd.review_state != "done"
        title = kd.title

    if not needs_review:
        await _set(doc_pk, stage="done")
        return
    await _set(doc_pk, stage="reviewing")
    if parsed is None:
        parsed = await _reparse_for_review(doc_pk, chunks)
    await _review(doc_pk, org_id, parsed, chunks, title)


async def _reparse_for_review(doc_pk: uuid.UUID, chunks: List[chunking.Chunk]) -> ParsedDocument:
    """The text to review when chunks were reused: the original file for typed documents (cheap, exact), the
    stored chunks for OCR'd ones (no second OCR)."""
    async with async_session_maker() as s:
        kd = await s.get(KnowledgeDocument, doc_pk)
        core = await s.get(Document, kd.document_id) if kd and kd.document_id else None
    if kd and not kd.ocr_used and core and os.path.exists(core.storage_path):
        try:
            with open(core.storage_path, "rb") as fh:
                return await asyncio.to_thread(parsing.parse_company_document, fh.read(), core.original_filename)
        except Exception as e:
            logger.info("re-parse for review failed, using stored chunks: %s", e)
    return _parsed_from_chunks(chunks, has_pages=bool(kd and kd.page_count))


async def _review(doc_pk: uuid.UUID, org_id: uuid.UUID, parsed: ParsedDocument, chunks: List[chunking.Chunk], title: str) -> None:
    """AI review: independent of indexing (a failure here leaves the document searchable)."""
    try:
        result = await asyncio.to_thread(ai.review_document, parsed, chunks, title)
        async with async_session_maker() as s2:
            d = await s2.get(KnowledgeDocument, doc_pk)
            r = result.review
            d.doc_type, d.summary_points, d.language = r.doc_type, r.summary_points, result.language or r.language
            d.key_facts = [f.model_dump() for f in r.key_facts[:8]]
            d.concerns, d.missing_items = result.concerns, r.missing_items[:5]
            d.suggested_questions = r.suggested_questions[:4]
            d.expiry_date = result.expiry if result.expiry_verified else None
            d.expiry_label = r.expiry_label if result.expiry_verified else None
            if r.title and (d.title == os.path.splitext(os.path.basename(d.filename or ""))[0].replace("_", " ").strip()):
                d.title = r.title[:200]
            d.review_state, d.review_error, d.stage, d.prompt_version = "done", None, "done", ai.PROMPT_VERSION
            if result.truncated:
                d.review_error = (f"This document is very long; the summary covers the first {ai.MAX_MAP_CHARS // 1000}k characters. "
                                  "Search and questions cover all of it.")
            await _sync_expiry_task(s2, d)
            await log_event(s2, organization_id=org_id, user_id=None, action="document.reviewed", entity_type="document", entity_id=doc_pk,
                            meta={"concerns": len(result.concerns), "sectioned": result.sectioned})
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
    - documents whose vectors are missing (Qdrant was down) or were built by an older embedding model / chunker.
    They are re-run one at a time in the background (the model pool is small). run_ingest only redoes the
    missing steps: a ready document keeps its status and chunks while its vectors or review are completed, and an
    already-reviewed document is not reviewed again (no AI quota spent)."""
    async with async_session_maker() as s:
        rows = (await s.execute(select(KnowledgeDocument.id, KnowledgeDocument.status).where(or_(
            KnowledgeDocument.status == "processing",
            and_(KnowledgeDocument.status == "failed", KnowledgeDocument.error_kind == "interrupted"),
            and_(KnowledgeDocument.status == "ready", KnowledgeDocument.review_state == "pending"),
            and_(KnowledgeDocument.status == "ready", (KnowledgeDocument.embed_model.is_(None)) | (KnowledgeDocument.embed_model != INDEX_VERSION)),
        )).order_by(KnowledgeDocument.created_at))).all()
    if not rows:
        return 0
    ids = [r.id for r in rows]
    for r in rows:
        if r.status == "ready":
            await _set(r.id, stage="queued")
        else:
            await _set(r.id, status="processing", stage="queued", error_kind=None, error_message=None)

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
    if d.status == "ready":                 # a ready document stays searchable while its review / vectors are redone
        d.stage = "queued"
    else:
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
                           via=h.via, section=c.section, rerank=h.rerank)
            if with_neighbours:
                e.before, e.after = await retrieval.neighbours(session, c.id)
            items.append(e)
    return items


def _snippet(text: str, query: str, width: int = 320) -> str:
    flat = " ".join(text.split())
    low = flat.lower()
    words = [w.lower() for w in retrieval.query_words(query) if len(w) > 2]
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
    """Recent turns for the planner. Assistant turns name the documents they cited, so a follow-up ("and for
    managers?") can be resolved to the same document."""
    lines = []
    for t in turns[-HISTORY_TURNS:]:
        titles = list(dict.fromkeys(c.get("document_title") for c in (t.citations or []) if isinstance(c, dict) and c.get("document_title")))
        source = f" [from: {'; '.join(titles[:3])}]" if titles else ""
        lines.append(f"{t.role.upper()}{source}: {t.content[:600]}")
    return "\n".join(lines)


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


def _closest_documents(doc_scores: Dict[uuid.UUID, float], docs: Sequence[KnowledgeDocument], limit: int = 3) -> Optional[str]:
    """'The closest documents by subject are A, B and C' from the routing scores (None with fewer than 2 docs)."""
    if len(doc_scores) < 2:
        return None
    title = {d.id: d.title for d in docs}
    best = [title[d] for d, _ in sorted(doc_scores.items(), key=lambda kv: -kv[1]) if d in title][:limit]
    if not best:
        return None
    names = [f"“{t}”" for t in best]
    listed = names[0] if len(names) == 1 else ", ".join(names[:-1]) + " and " + names[-1]
    return f"The documents closest to this subject are {listed}; if the answer should be there, it may be worded differently, otherwise add the document that covers it."


def _not_found(suggestion: Optional[str] = None) -> dict:
    text = "I couldn't find anything in your documents about this. Try different words, or add the document that would have the answer."
    if suggestion:
        text += f"\n\n**Not in your documents:** {suggestion}"
    return {"content": text, "found_in_documents": False, "citations": [], "sources": [], "confidence": 0}


_LIST_DOCS = re.compile(
    r"\b(what|which|list|show)\b[^?]{0,40}\b(documents?|files?|docs)\b[^?]{0,30}\b(have|uploaded|added|there|available|stored)\b"
    r"|^\s*(list|show)( me)?( all)?( my| the| our)? (documents|files|docs)\b"
    r"|\b(kaun|kon)\s*(se|si|sa)\s*(documents?|files?|docs)\b"
    r"|कौन\s*(से|सी)\s*(दस्तावेज़|दस्तावेज|फ़ाइल|फाइल)|(सभी|सारे)\s*(दस्तावेज़|दस्तावेज)", re.I)


def is_document_list_request(question: str) -> bool:
    """'What documents do I have?' / 'list my files' / 'kaun se documents hain' - answered from the database."""
    return bool(_LIST_DOCS.search(question))


def _documents_reply(docs: List[KnowledgeDocument], collection: Optional[str]) -> dict:
    """One line per document: title, type, size, expiry and the first summary point. No AI call."""
    where = f"the {collection} collection" if collection else "your documents"
    if not docs:
        return {"content": f"There are no ready documents in {where} yet. Add one to get started.", "found_in_documents": False,
                "citations": [], "sources": [], "confidence": 0}
    lines = []
    for d in docs[:50]:
        meta = [m for m in (d.doc_type, f"{d.page_count} pages" if d.page_count else None, d.language,
                            f"valid until {d.expiry_date.strftime('%d %b %Y')}" if d.expiry_date else None) if m]
        about = (d.summary_points or [None])[0]
        lines.append(f"- **{d.title}**" + (f" ({', '.join(meta)})" if meta else "") + (f": {about}" if about else ""))
    more = f"\n\n…and {len(docs) - 50} more." if len(docs) > 50 else ""
    plural = "s" if len(docs) != 1 else ""
    return {"content": f"You have {len(docs)} document{plural} in {where}:\n\n" + "\n".join(lines) + more,
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


GENERIC_WORDS = {"document", "documents", "file", "files", "doc", "docs", "pdf", "copy", "summary", "summarise", "summarize",
                 "about", "main", "points", "\u0926\u0938\u094d\u0924\u093e\u0935\u0947\u091c\u093c", "\u0926\u0938\u094d\u0924\u093e\u0935\u0947\u091c", "\u092b\u093e\u0907\u0932"}


def match_target(docs: Sequence[KnowledgeDocument], target: Optional[str]) -> List[uuid.UUID]:
    """Documents whose title / type / file name share the most words with how the user named one ('the safety
    manual'). Empty when no word matches, so the caller can fall back to routing by meaning."""
    if not target:
        return []
    words = [w.lower() for w in retrieval.query_words(target) if len(w) > 2 and w.lower() not in GENERIC_WORDS]
    if not words:
        return []
    scored = []
    for d in docs:
        hay = f"{d.title} {d.doc_type or ''} {d.filename or ''}".lower()
        scored.append((sum(1 for w in words if w in hay), d.id))
    best = max((s for s, _ in scored), default=0)
    return [d for s, d in scored if s == best] if best else []


async def _rank_documents(session: AsyncSession, scope: retrieval.Scope, text: str) -> Dict[uuid.UUID, float]:
    """Document routing scores; routing only steers the search, so a failure means 'no preference', not an error."""
    try:
        return await retrieval.rank_documents(session, scope, text)
    except Exception as e:
        logger.warning("document routing unavailable: %s", e)
        return {}


async def _resolve_target(session: AsyncSession, scope: retrieval.Scope, docs: List[KnowledgeDocument], target: Optional[str]) -> List[uuid.UUID]:
    """Lexical match first; otherwise the document whose profile is clearly closest in meaning (a Hindi-titled
    safety manual for 'the safety manual')."""
    ids = match_target(docs, target)
    if ids or not target or len(docs) < 2:
        return ids
    scores = sorted((await _rank_documents(session, scope, target)).items(), key=lambda kv: -kv[1])
    if len(scores) >= 2 and scores[0][1] - scores[1][1] >= 0.08:
        return [scores[0][0]]
    return []


def _profile(d: KnowledgeDocument) -> str:
    parts = [f"{d.title}" + (f" ({d.doc_type})" if d.doc_type else "") + (f", language {d.language}" if d.language else "")]
    if d.summary_points:
        parts.append("Summary: " + " ".join(f"\u2022 {pt}" for pt in d.summary_points))
    if d.key_facts:
        parts.append("Key facts: " + "; ".join(f"{f.get('label')}: {f.get('value')}" for f in d.key_facts if isinstance(f, dict)))
    return " | ".join(parts)


async def _opening_items(session: AsyncSession, docs: Sequence[KnowledgeDocument]) -> List[ai.Excerpt]:
    """One excerpt per document: verbatim opening text, with the AI profile as a non-citable note."""
    items: List[ai.Excerpt] = []
    for d in docs[:6]:
        opening = list((await session.execute(select(DocChunk).where(DocChunk.doc_id == d.id).order_by(DocChunk.chunk_index).limit(3))).scalars())
        if not opening:
            continue
        items.append(ai.Excerpt(marker=f"C{len(items) + 1}", doc_id=str(d.id), doc_title=d.title, page=opening[0].page,
                                text="\n\n".join(c.text for c in opening)[:2500], via=["overview"], section=opening[0].section,
                                note=_profile(d)))
    return items


async def _digest_items(session: AsyncSession, d: KnowledgeDocument) -> List[ai.Excerpt]:
    """Overview of ONE long document (map step): one AI call reads the whole chunk set and names its main points
    with quotes; each verified quote brings its passage, in document order, into the answer call (reduce step)."""
    rows = list((await session.execute(select(DocChunk).where(DocChunk.doc_id == d.id).order_by(DocChunk.chunk_index))).scalars())
    passages = ai.digest_passages([(r.chunk_index, r.section, r.text) for r in rows])
    digest = await asyncio.to_thread(ai.digest_document, d.title, passages)
    by_index = {r.chunk_index: r for r in rows}
    notes: Dict[int, List[str]] = {}
    for p in digest.points:
        idx = int(re.sub(r"\D", "", p.excerpt) or -1)
        row = by_index.get(idx)
        seg = [Segment(id=str(idx), number=None, heading="", text=row.text, page_start=row.page, page_end=row.page)] if row else []
        if row and verify.find_quote(p.quote, seg).verified:
            notes.setdefault(idx, []).append(p.point)
    if not notes:                                     # nothing verifiable: fall back to the opening pages
        return await _opening_items(session, [d])
    items = []
    for idx in sorted(notes)[:10]:
        r = by_index[idx]
        note = ("; ".join(notes[idx]) if items else f"{_profile(d)} | Main point here: {'; '.join(notes[idx])}")
        items.append(ai.Excerpt(marker=f"C{len(items) + 1}", doc_id=str(d.id), doc_title=d.title, page=r.page, text=r.text,
                                via=["overview"], section=r.section, note=note))
    return items


async def _overview(session: AsyncSession, scope: retrieval.Scope, docs: List[KnowledgeDocument], target_ids: List[uuid.UUID]) -> List[ai.Excerpt]:
    chosen = [d for d in docs if d.id in target_ids] if target_ids else docs
    if len(chosen) == 1 and (chosen[0].chunk_count or 0) > OVERVIEW_DIRECT_CHUNKS:
        return await _digest_items(session, chosen[0])
    return await _opening_items(session, chosen)


def _rerank_query(question: str, plan: ai.QueryPlan) -> str:
    """Rerank against the user's own words when they wrote in an Indic script: a model rewrite of Devanagari can come
    back garbled through JSON escaping, and the original is already a complete question."""
    import re
    return question.strip() if re.search(r"[ऀ-෿]", question) else plan.standalone_question


async def _answer_core(session: AsyncSession, ctx: RequestContext, conv: Conversation, question: str) -> dict:
    docs = await _ready_docs(session, ctx, conv.collection)
    if is_document_list_request(question):
        return _documents_reply(docs, conv.collection)
    history = _history_text(conv.messages)
    plan = await asyncio.to_thread(ai.plan_query, question, history)
    if plan.intent == "conversation" or not plan.answerable_from_documents:
        return _conversation_reply(docs, conv.collection)
    if plan.intent == "documents":
        return _documents_reply(docs, conv.collection)
    scope = await _scope(session, ctx, conv.collection)
    target_ids = await _resolve_target(session, scope, docs, plan.target_document)
    doc_scores: Dict[uuid.UUID, float] = {}
    if plan.intent == "overview":
        items = await _overview(session, scope, docs, target_ids)
        if not items:
            return _conversation_reply([], conv.collection)
        ans = await asyncio.to_thread(ai.answer_question, plan.standalone_question, items, history, True)
    else:
        if target_ids:
            # "in the safety manual, ..." -> search only that document
            scope = retrieval.Scope(ctx.organization_id, target_ids)
        else:
            doc_scores = await _rank_documents(session, scope, plan.standalone_question)
        hits = await retrieval.hybrid_search(session, scope, plan.search_queries, top_k=retrieval.TOP_K, rerank_query=_rerank_query(question, plan),
                                             sub_questions=plan.sub_questions, doc_scores=doc_scores)
        items = await _load_hits(session, ctx, hits, with_neighbours=True)
        if not items:
            return _not_found(_closest_documents(doc_scores, docs))
        ans = await asyncio.to_thread(ai.answer_question, plan.standalone_question, items, history)
        if not ans.found_in_documents:
            hint = _closest_documents(doc_scores, docs)
            if hint:
                ans.not_covered = f"{ans.not_covered.strip()} {hint}" if ans.not_covered else hint
    citations, confidence = _build_citations(ans, items)
    text = ans.render()
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
