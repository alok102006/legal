"""Legal Notice Center service.

Upload/paste a notice -> AI extraction -> deterministic deadline + urgency -> reply draft for lawyer review.
The response deadline is mirrored into the compliance calendar so it cannot be missed.
"""
import asyncio
import logging
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import List, Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.dependencies import RequestContext
from app.shared.audit import log_event
from app.shared.db.models import Document, Organization
from app.shared.db.session import async_session_maker
from app.shared.exceptions import BadRequestException, NotFoundException
from app.shared.storage import file_storage
from app.workspaces.compliance_center.models import ComplianceTask
from app.workspaces.contract_intelligence.service import classify_failure, validate_upload
from app.workspaces.legal_notice_center.engine import pipeline, prompts, rules
from app.workspaces.legal_notice_center.engine.schemas import NoticeFacts
from app.workspaces.legal_notice_center.models import NoticeCase, ReplyDraft

logger = logging.getLogger("legalos.notices")
_IST = timezone(timedelta(hours=5, minutes=30))


def IST_TODAY() -> date:
    return datetime.now(_IST).date()


# ------------------------------------------------------------------ presentation helpers

def _days_left(case: NoticeCase, today: date) -> Optional[int]:
    return (case.response_deadline - today).days if case.response_deadline else None


def to_list_item(c: NoticeCase, today: Optional[date] = None) -> dict:
    today = today or IST_TODAY()
    return {
        "id": c.id, "title": c.title or c.source_name or "Notice", "notice_type": c.notice_type,
        "type_label": rules.TYPE_LABELS.get(rules.NoticeType(c.notice_type)) if c.notice_type else None,
        "urgency": c.urgency, "status": c.status, "stage": c.stage, "issuer_name": c.issuer_name,
        "amount_claimed": float(c.amount_claimed) if c.amount_claimed is not None else None,
        "response_deadline": c.response_deadline, "days_left": _days_left(c, today), "review_status": c.review_status,
        "error_kind": c.error_kind, "error_message": c.error_message, "source_name": c.source_name, "created_at": c.created_at,
    }


def _meta(c: NoticeCase) -> dict:
    return (c.facts or {}).get("meta") or {}


def to_detail(c: NoticeCase, today: Optional[date] = None) -> dict:
    d = to_list_item(c, today)
    facts, meta = c.facts or {}, _meta(c)
    note = rules.legal_note(rules.NoticeType(c.notice_type)) if c.notice_type else None
    quotes_ok = meta.get("quotes_verified") or {}
    key_quotes = [{"kind": kind, "text": text, "verified": bool(quotes_ok.get(kind))}
                  for kind, text in (("deadline", c.deadline_quote), ("amount", facts.get("amount_quote")), ("demand", facts.get("demand_quote")))
                  if text and text.strip()]
    actions = [a for a in (facts.get("what_to_do_now") or []) if isinstance(a, str) and a.strip()]
    d.update(
        reference_number=c.reference_number, notice_date=c.notice_date, received_date=c.received_date, response_days=c.response_days,
        deadline_source=c.deadline_source, deadline_note=c.deadline_note, deadline_quote=c.deadline_quote,
        deadline_verified=c.deadline_verified, deadline_rule=rules.deadline_rule(c.notice_type, c.deadline_source),
        received_confirmed=bool(meta.get("received_confirmed", True)),
        needs_received_date=(not meta.get("received_confirmed", True)) and meta.get("anchor") == "receipt",
        issuer_role=facts.get("issuer_role"), addressed_to=facts.get("addressed_to"),
        summary_points=c.summary_points or [], demands=c.demands or [],
        statutes=c.statutes or [], consequences=c.consequences, legal_note=c.legal_note, legal_ref=c.legal_ref,
        legal_if_ignored=note.if_ignored if note else None, if_ignored=facts.get("if_ignored"),
        actions=actions, actions_done=[i for i in (meta.get("actions_done") or []) if isinstance(i, int) and 0 <= i < len(actions)],
        key_quotes=key_quotes,
        ocr_used=c.ocr_used, in_calendar=c.compliance_task_id is not None, raw_text=c.raw_text,
        drafts=[{**{k: getattr(x, k) for k in ("id", "version", "reply_text", "author", "instructions", "created_at")},
                 "placeholders": x.placeholders or [], "points_to_confirm": x.points_to_confirm or [],
                 "documents_to_gather": x.documents_to_gather or []} for x in sorted(c.drafts, key=lambda x: -x.version)],
    )
    return d


# ------------------------------------------------------------------ calendar link

async def _sync_calendar_task(session: AsyncSession, case: NoticeCase, ctx_user: Optional[uuid.UUID]) -> None:
    task = await session.get(ComplianceTask, case.compliance_task_id) if case.compliance_task_id else None
    if case.status == "closed":
        if task and task.status != "completed":
            task.status, task.completed_at, task.completion_note = "completed", datetime.now(timezone.utc), "Notice case closed"
        return
    if not case.response_deadline:
        if task:
            await session.delete(task)
            case.compliance_task_id = None
        return
    title = f"Reply to notice: {case.title or case.source_name or 'notice'}"[:190]
    desc = f"{rules.TYPE_LABELS.get(rules.NoticeType(case.notice_type), 'Notice') if case.notice_type else 'Notice'}"
    if case.issuer_name:
        desc += f" from {case.issuer_name}"
    desc += ". Open it in Notices to see the summary and the draft reply."
    if task is None:
        task = ComplianceTask(organization_id=case.organization_id, user_id=ctx_user, title=title, category="other",
                              due_date=case.response_deadline, description=desc, is_custom=True, status="pending",
                              penalty_desc=(case.consequences or None))
        session.add(task)
        await session.flush()
        case.compliance_task_id = task.id
    else:
        task.title, task.due_date, task.description = title, case.response_deadline, desc


# ------------------------------------------------------------------ create

async def create_from_text(session: AsyncSession, ctx: RequestContext, text: str, title: Optional[str], received: Optional[date]) -> NoticeCase:
    case = NoticeCase(organization_id=ctx.organization_id, created_by=ctx.user_id, raw_text=text.strip(), title=(title or "").strip() or None,
                      source_name="Pasted text", status="processing", stage="queued", received_date=received or IST_TODAY(),
                      facts={"meta": {"received_confirmed": received is not None}})
    session.add(case)
    await session.flush()
    await log_event(session, organization_id=ctx.organization_id, user_id=ctx.user_id, action="notice.created",
                    entity_type="notice", entity_id=case.id, meta={"source": "text"})
    await session.commit()
    return case


async def create_from_file(session: AsyncSession, ctx: RequestContext, data: bytes, filename: str, received: Optional[date]) -> NoticeCase:
    validate_upload(filename, data)
    path = await file_storage.save_file(filename, data, ctx.organization_id)
    try:
        doc = Document(workspace="legal_notice_center", original_filename=filename, storage_path=path,
                       uploaded_by=ctx.user_id, organization_id=ctx.organization_id)
        session.add(doc)
        await session.flush()
        case = NoticeCase(organization_id=ctx.organization_id, created_by=ctx.user_id, document_id=doc.id, source_name=filename,
                          status="processing", stage="queued", received_date=received or IST_TODAY(),
                          facts={"meta": {"received_confirmed": received is not None}})
        session.add(case)
        await session.flush()
        await log_event(session, organization_id=ctx.organization_id, user_id=ctx.user_id, action="notice.created",
                        entity_type="notice", entity_id=case.id, meta={"source": "file", "filename": filename})
        await session.commit()
    except Exception:
        await file_storage.delete_file(path)
        raise
    return case


# ------------------------------------------------------------------ analysis

async def _set_stage(case_id: uuid.UUID, stage: str) -> None:
    async with async_session_maker() as s:
        await s.execute(update(NoticeCase).where(NoticeCase.id == case_id).values(stage=stage))
        await s.commit()


async def run_analysis(case_id: uuid.UUID) -> None:
    loop = asyncio.get_running_loop()

    def on_stage(stage: str) -> None:
        try:
            asyncio.run_coroutine_threadsafe(_set_stage(case_id, stage), loop).result(timeout=10)
        except Exception as e:
            logger.debug("stage update failed: %s", e)

    async with async_session_maker() as session:
        case = await session.get(NoticeCase, case_id)
        if case is None:
            return
        try:
            org = await session.get(Organization, case.organization_id)
            ocr_used = False
            text = case.raw_text
            if not text:
                doc = await session.get(Document, case.document_id)
                with open(doc.storage_path, "rb") as fh:
                    data = fh.read()
                text, ocr_used = await asyncio.to_thread(pipeline.read_notice_file, data, doc.original_filename, on_stage)
            received = case.received_date or IST_TODAY()
            old_meta = _meta(case)
            result = await asyncio.to_thread(pipeline.analyze_text, text, received, org.legal_name if org else "", IST_TODAY(), on_stage, ocr_used)

            f, dl = result.facts, result.deadline
            note = rules.legal_note(f.notice_type)
            case.raw_text = text
            case.title = case.title or f.title
            case.notice_type, case.urgency, case.issuer_name = f.notice_type.value, result.urgency, f.issuer_name
            case.reference_number, case.notice_date = f.reference_number, rules.parse_iso(f.notice_date)
            case.amount_claimed, case.response_days = f.amount_claimed, dl.days if dl.source == "stated" else f.response_days
            case.response_deadline, case.deadline_source, case.deadline_note = dl.due, dl.source, dl.note
            case.deadline_quote, case.deadline_verified = f.deadline_quote, result.deadline_verified
            case.summary_points, case.demands, case.statutes = f.summary_points, f.demands, f.statutes_cited
            case.consequences = f.consequences_stated
            case.legal_note, case.legal_ref = (note.text, note.ref) if note else (None, None)
            case.facts = {**f.model_dump(mode="json"), "meta": {
                "received_confirmed": bool(old_meta.get("received_confirmed", False)), "anchor": dl.anchor,
                "quotes_verified": result.quotes_verified, "actions_done": []}}
            case.ocr_used, case.prompt_version = result.ocr_used, prompts.PROMPT_VERSION
            case.status, case.stage, case.error_kind, case.error_message = "analyzed", "done", None, None
            case.analyzed_at = datetime.now(timezone.utc)

            for old in list((await session.execute(select(ReplyDraft).where(ReplyDraft.case_id == case_id))).scalars()):
                await session.delete(old)
            await session.flush()
            session.add(ReplyDraft(case_id=case_id, version=1, reply_text=result.reply.reply_text, placeholders=result.placeholders,
                                   points_to_confirm=result.reply.points_to_confirm, documents_to_gather=result.reply.documents_to_gather, author="ai"))
            await _sync_calendar_task(session, case, case.created_by)
            await log_event(session, organization_id=case.organization_id, user_id=None, action="notice.analyzed",
                            entity_type="notice", entity_id=case_id, meta={"type": case.notice_type, "urgency": case.urgency})
            await session.commit()
        except Exception as exc:
            await session.rollback()
            kind, message = classify_failure(exc)
            (logger.exception if kind == "internal" else logger.warning)("notice analysis failed case=%s kind=%s", case_id, kind)
            async with async_session_maker() as s2:
                await s2.execute(update(NoticeCase).where(NoticeCase.id == case_id).values(
                    status="failed", stage=None, error_kind=kind, error_message=message))
                await s2.commit()


async def mark_interrupted() -> int:
    async with async_session_maker() as s:
        res = await s.execute(update(NoticeCase).where(NoticeCase.status == "processing").values(
            status="failed", stage=None, error_kind="interrupted",
            error_message="The analysis was interrupted by a server restart. Click Try again to run it again."))
        await s.commit()
        return res.rowcount or 0


# ------------------------------------------------------------------ queries / mutations

async def _get(session: AsyncSession, ctx: RequestContext, case_id: uuid.UUID, drafts: bool = False) -> NoticeCase:
    stmt = select(NoticeCase).where(NoticeCase.id == case_id, NoticeCase.organization_id == ctx.organization_id)
    # populate_existing: the identity map may hold a stale copy (e.g. before a new draft was added)
    stmt = stmt.options(selectinload(NoticeCase.drafts)).execution_options(populate_existing=True)
    case = (await session.execute(stmt)).scalar_one_or_none()
    if not case:
        raise NotFoundException("Notice not found.")
    return case


async def list_cases(session: AsyncSession, ctx: RequestContext) -> List[dict]:
    rows = (await session.execute(select(NoticeCase).where(NoticeCase.organization_id == ctx.organization_id)
                                  .order_by(NoticeCase.created_at.desc()))).scalars().all()
    today = IST_TODAY()
    items = [to_list_item(c, today) for c in rows]
    rank = {"critical": 0, "high": 1, "medium": 2, "low": 3, None: 4}
    # open cases first, most urgent first
    return sorted(items, key=lambda i: (i["status"] == "closed", rank.get(i["urgency"], 4), i["response_deadline"] or date.max))


async def get_detail(session: AsyncSession, ctx: RequestContext, case_id: uuid.UUID) -> dict:
    return to_detail(await _get(session, ctx, case_id))


async def prepare_retry(session: AsyncSession, ctx: RequestContext, case_id: uuid.UUID) -> NoticeCase:
    case = await _get(session, ctx, case_id)
    if case.status == "processing":
        raise BadRequestException("This notice is already being analysed.")
    case.status, case.stage, case.error_kind, case.error_message = "processing", "queued", None, None
    await session.commit()
    return case


async def update_case(session: AsyncSession, ctx: RequestContext, case_id: uuid.UUID, data: dict) -> NoticeCase:
    case = await _get(session, ctx, case_id)
    if "review_status" in data and data["review_status"]:
        if data["review_status"] == "lawyer_approved" and case.status != "analyzed" and case.status != "closed":
            raise BadRequestException("The notice must be analysed first.")
        case.review_status = data["review_status"]
    analysed = bool(case.facts) and "notice_type" in case.facts
    if data.get("received_date") and analysed and data["received_date"] != case.received_date:
        case.received_date = data["received_date"]
        facts = NoticeFacts.model_validate(case.facts)
        dl = rules.compute_deadline(facts, case.received_date)
        if not case.deadline_verified:
            dl = rules.flag_unverified(dl)
        case.response_deadline, case.deadline_source, case.deadline_note = dl.due, dl.source, dl.note
        case.urgency = rules.urgency_for(facts, dl, IST_TODAY())
        case.facts = {**case.facts, "meta": {**_meta(case), "received_confirmed": True, "anchor": dl.anchor}}
    elif data.get("received_date") and not analysed:
        case.received_date = data["received_date"]
    if data.get("received_date") and analysed:
        case.facts = {**case.facts, "meta": {**_meta(case), "received_confirmed": True}}
    if data.get("actions_done") is not None and analysed:
        n = len(case.facts.get("what_to_do_now") or [])
        done = sorted({i for i in data["actions_done"] if 0 <= i < n})
        case.facts = {**case.facts, "meta": {**_meta(case), "actions_done": done}}
    if data.get("status"):
        case.status = data["status"]
    await _sync_calendar_task(session, case, ctx.user_id)
    await log_event(session, organization_id=ctx.organization_id, user_id=ctx.user_id, action="notice.updated",
                    entity_type="notice", entity_id=case.id, meta={k: str(v) for k, v in data.items() if k != "actions_done"})
    await session.commit()
    return await _get(session, ctx, case_id)


async def _next_version(session: AsyncSession, case_id: uuid.UUID) -> int:
    rows = (await session.execute(select(ReplyDraft.version).where(ReplyDraft.case_id == case_id))).scalars().all()
    return (max(rows) if rows else 0) + 1


async def regenerate_draft(session: AsyncSession, ctx: RequestContext, case_id: uuid.UUID, instructions: Optional[str]) -> NoticeCase:
    case = await _get(session, ctx, case_id)
    if case.status not in ("analyzed", "closed") or not case.facts or not case.raw_text:
        raise BadRequestException("The notice has not been analysed yet.")
    org = await session.get(Organization, ctx.organization_id)
    facts = NoticeFacts.model_validate(case.facts)
    draft = await asyncio.to_thread(pipeline.draft_reply, case.raw_text, facts, org.legal_name if org else "", instructions)
    session.add(ReplyDraft(case_id=case_id, version=await _next_version(session, case_id), reply_text=draft.reply_text,
                           placeholders=pipeline.placeholders_in(draft.reply_text), points_to_confirm=draft.points_to_confirm,
                           documents_to_gather=draft.documents_to_gather, author="ai", instructions=(instructions or None)))
    case.review_status = "draft"
    await log_event(session, organization_id=ctx.organization_id, user_id=ctx.user_id, action="notice.draft_regenerated",
                    entity_type="notice", entity_id=case_id)
    await session.commit()
    return await _get(session, ctx, case_id)


async def save_user_draft(session: AsyncSession, ctx: RequestContext, case_id: uuid.UUID, text: str) -> NoticeCase:
    case = await _get(session, ctx, case_id)
    latest = max(case.drafts, key=lambda d: d.version) if case.drafts else None
    session.add(ReplyDraft(case_id=case_id, version=await _next_version(session, case_id), reply_text=text,
                           placeholders=pipeline.placeholders_in(text),
                           points_to_confirm=latest.points_to_confirm if latest else [],
                           documents_to_gather=latest.documents_to_gather if latest else [], author="user"))
    case.review_status = "draft"        # any edit needs a fresh review
    await log_event(session, organization_id=ctx.organization_id, user_id=ctx.user_id, action="notice.draft_edited",
                    entity_type="notice", entity_id=case_id)
    await session.commit()
    return await _get(session, ctx, case_id)


async def delete_case(session: AsyncSession, ctx: RequestContext, case_id: uuid.UUID) -> None:
    case = await _get(session, ctx, case_id)
    if case.compliance_task_id:
        t = await session.get(ComplianceTask, case.compliance_task_id)
        if t:
            await session.delete(t)
    path = None
    if case.document_id:
        doc = await session.get(Document, case.document_id)
        if doc:
            path = doc.storage_path
            await session.delete(doc)
    await log_event(session, organization_id=ctx.organization_id, user_id=ctx.user_id, action="notice.deleted",
                    entity_type="notice", entity_id=case_id)
    await session.delete(case)
    await session.commit()
    if path:
        await file_storage.delete_file(path)
