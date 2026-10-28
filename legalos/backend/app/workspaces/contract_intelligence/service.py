"""Contract Intelligence service: upload -> background analysis -> findings, retry, chat, delete.

Failures are never converted into "safe" results: a contract that cannot be analysed is marked
`failed` with a user-presentable reason and can be retried.
"""
import asyncio
import logging
import os
import re
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import List, Optional, Tuple

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.llm import llm_client
from app.core.llm.errors import LLMAuthError, LLMBadRequest, LLMError, LLMInvalidOutput, LLMQuotaError, LLMUnavailable
from app.dependencies import RequestContext
from app.shared.audit import log_event
from app.shared.db.models import Document, Organization
from app.shared.db.session import async_session_maker
from app.shared.exceptions import BadRequestException, NotFoundException
from app.shared.storage import file_storage
from app.workspaces.contract_intelligence import repository
from app.workspaces.contract_intelligence.engine import inputs, pipeline, prompts, rules, verify
from app.workspaces.contract_intelligence.engine.contract_types import profile
from app.workspaces.contract_intelligence.engine.schemas import ChatAnswer
from app.workspaces.contract_intelligence.engine.segmenter import Segment as EngineSegment
from app.workspaces.contract_intelligence.engine.segmenter import render_for_llm
from app.workspaces.contract_intelligence.models import ChatMessage, Contract, Finding, Segment

logger = logging.getLogger("legalos.contracts")

MAX_FILE_SIZE = 10 * 1024 * 1024
MAX_COMBINED_SIZE = 25 * 1024 * 1024          # PDF assembled from several photos
CHAT_TOP_FINDINGS = 8
ALLOWED_EXTENSIONS = {"pdf", "docx", "txt", "md", "png", "jpg", "jpeg", "webp"}
_IMAGE_MAGIC = {"png": (b"\x89PNG",), "jpg": (b"\xff\xd8\xff",), "jpeg": (b"\xff\xd8\xff",), "webp": (b"RIFF",)}


# ------------------------------------------------------------------ helpers

def validate_upload(filename: str, data: bytes) -> str:
    if not data:
        raise BadRequestException("The file is empty.")
    if len(data) > MAX_FILE_SIZE:
        raise BadRequestException(f"File is too large ({len(data) // (1024 * 1024)} MB). The maximum is 10 MB.")
    if "." not in filename:
        raise BadRequestException("The file has no extension. Please upload a PDF, Word, text or image file.")
    ext = filename.lower().rsplit(".", 1)[-1]
    if ext not in ALLOWED_EXTENSIONS:
        raise BadRequestException(f"'.{ext}' files are not supported. Please upload a PDF, Word, text or image file.")
    if ext == "pdf" and not data.startswith(b"%PDF"):
        raise BadRequestException("This file is named .pdf but is not a valid PDF.")
    if ext == "docx" and not data.startswith(b"PK"):
        raise BadRequestException("This file is named .docx but is not a valid Word document.")
    if ext in ("txt", "md") and b"\x00" in data[:4096]:
        raise BadRequestException("This does not look like a text file.")
    return ext


def classify_failure(exc: BaseException) -> Tuple[str, str]:
    """-> (error_kind, user-presentable message)"""
    if isinstance(exc, LLMAuthError):
        return "auth", exc.user_message
    if isinstance(exc, LLMQuotaError):
        return "quota", exc.user_message
    if isinstance(exc, LLMInvalidOutput):
        return "invalid_output", exc.user_message
    if isinstance(exc, LLMBadRequest):
        return "bad_input", exc.user_message
    if isinstance(exc, LLMUnavailable):
        return "unavailable", exc.user_message
    if isinstance(exc, LLMError):
        return "unavailable", exc.user_message
    if isinstance(exc, BadRequestException):
        return "bad_input", str(exc.detail)
    if isinstance(exc, FileNotFoundError):
        return "bad_input", "The original file could not be found. Please upload the contract again."
    return "internal", "Something went wrong while analysing this contract. Please retry; if it keeps failing, contact support."


def _title_from_filename(filename: str) -> str:
    return os.path.splitext(os.path.basename(filename))[0].replace("_", " ").strip() or "Contract"


def _to_engine_segments(rows: List[Segment]) -> List[EngineSegment]:
    return [EngineSegment(id=r.seg_id, number=r.number, heading=r.heading, text=r.text,
                          page_start=r.page_start, page_end=r.page_end) for r in rows]


# ------------------------------------------------------------------ upload / list / detail

async def combine_photos(uploads: List[Tuple[str, bytes]]) -> Tuple[str, bytes]:
    """Several photos of one contract (in upload order) -> one image-only PDF that goes through page-wise OCR."""
    for name, data in uploads:
        if validate_upload(name, data) not in pipeline.IMAGE_TYPES:
            raise BadRequestException("To upload several files at once, every file must be a photo (JPG, PNG or WebP) "
                                      "of one contract's pages, in order. Upload PDFs and Word files one at a time.")
    pdf = await asyncio.to_thread(inputs.photos_to_pdf, [d for _, d in uploads])
    if len(pdf) > MAX_COMBINED_SIZE:
        raise BadRequestException("These photos are too large together. Please upload fewer pages or a PDF scan.")
    stem = os.path.splitext(os.path.basename(uploads[0][0]))[0] or "contract"
    return f"{stem} ({len(uploads)} pages).pdf", pdf


async def create_upload(
    session: AsyncSession, ctx: RequestContext, file_bytes: bytes, filename: str, client_party: Optional[str],
) -> Contract:
    validate_upload(filename, file_bytes)
    path = await file_storage.save_file(filename, file_bytes, ctx.organization_id)
    try:
        doc = await repository.create_document(session, ctx.organization_id, filename, path, ctx.user_id)
        contract = await repository.create_contract(
            session, ctx.organization_id, doc.id, _title_from_filename(filename),
            client_party.strip() if client_party and client_party.strip() else None)
        await log_event(session, organization_id=ctx.organization_id, user_id=ctx.user_id,
                        action="contract.uploaded", entity_type="contract", entity_id=contract.id,
                        meta={"filename": filename, "bytes": len(file_bytes)})
        await session.commit()
    except Exception:
        await file_storage.delete_file(path)
        raise
    return contract


async def list_contracts(session: AsyncSession, ctx: RequestContext) -> List[dict]:
    return await repository.list_contracts(session, ctx.organization_id)


async def get_detail(session: AsyncSession, ctx: RequestContext, contract_id: uuid.UUID) -> dict:
    c = await repository.get_contract(session, ctx.organization_id, contract_id, full=True)
    if not c:
        raise NotFoundException("Contract not found.")
    counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}
    for f in c.findings:
        if f.counts_toward_score and f.status != "dismissed":
            counts[f.severity] += 1
    return {
        "id": c.id, "title": c.title, "counterparty_name": c.counterparty_name, "contract_type": c.contract_type,
        "contract_type_label": profile(c.contract_type).label if c.contract_type else None,
        "status": c.status, "stage": c.stage, "risk_level": c.risk_level, "overall_score": c.overall_score,
        "finding_counts": counts, "error_kind": c.error_kind, "error_message": c.error_message,
        "filename": c.document.original_filename if c.document else None,
        "created_at": c.created_at, "analyzed_at": c.analyzed_at,
        "summary_points": c.summary_points or [], "facts": c.facts, "score_breakdown": c.score_breakdown,
        "warnings": c.warnings or [], "page_count": c.page_count,
        "has_pages": bool(c.page_count), "ocr_used": c.ocr_used,
        "prompt_version": c.prompt_version, "rules_version": c.rules_version,
        "findings": c.findings, "segments": c.segments,
    }


# ------------------------------------------------------------------ background analysis

async def _set_stage(contract_id: uuid.UUID, stage: str) -> None:
    async with async_session_maker() as s:
        await s.execute(update(Contract).where(Contract.id == contract_id).values(stage=stage))
        await s.commit()


async def run_analysis(contract_id: uuid.UUID) -> None:
    """Background worker. Reads the stored file, runs the engine in a worker thread, persists results."""
    loop = asyncio.get_running_loop()

    def on_stage(stage: str) -> None:
        # called from the worker thread; wait so stage order is preserved
        try:
            asyncio.run_coroutine_threadsafe(_set_stage(contract_id, stage), loop).result(timeout=10)
        except Exception as e:  # progress is cosmetic; never fail the analysis for it
            logger.debug("stage update failed: %s", e)

    async with async_session_maker() as session:
        contract = await session.get(Contract, contract_id)
        if contract is None:
            return
        org_id = contract.organization_id   # captured: attributes expire after a rollback
        try:
            doc = await session.get(Document, contract.document_id)
            org = await session.get(Organization, contract.organization_id) if contract.organization_id else None
            with open(doc.storage_path, "rb") as fh:
                file_bytes = fh.read()
            org_profile = rules.OrgProfile(
                entity_type=org.entity_type, msme_category=org.msme_category,
                state_code=org.state_code, gstin=org.gstin) if org else None

            logger.info("analysis started contract=%s", contract_id)
            result = await asyncio.to_thread(
                pipeline.analyze_file, file_bytes, doc.original_filename, org_profile,
                org.legal_name if org else None, contract.client_party, on_stage)

            await repository.clear_analysis(session, contract_id)
            facts = result.facts
            client = next((p for p in facts.parties if p.is_our_client), None)
            other = next((p for p in facts.parties if not p.is_our_client), None)
            contract.title = (facts.title or contract.title or "").strip() or contract.title
            contract.counterparty_name = other.name if other else None
            contract.client_party = contract.client_party or (client.name if client else None)
            contract.contract_type = facts.contract_type.value
            contract.summary_points = facts.summary_points
            contract.facts = facts.model_dump(mode="json", exclude={"summary_points"})
            contract.overall_score = result.score.score
            contract.risk_level = result.score.level
            cov = result.coverage
            contract.score_breakdown = {
                **result.score.breakdown(),
                "coverage": {
                    "truncated": bool(cov and cov.truncated), "reviewed_segments": cov.reviewed_segments if cov else None,
                    "total_segments": cov.total_segments if cov else None, "reviewed_pages": cov.reviewed_pages if cov else None,
                    "total_pages": cov.total_pages if cov else None, "parts": cov.parts if cov else None,
                },
                "review": result.review,
            }
            contract.warnings = result.warnings
            contract.page_count = result.page_count or None
            contract.ocr_used = result.ocr_used
            contract.prompt_version = result.prompt_version
            contract.rules_version = result.rules_version
            contract.analyzed_at = datetime.now(timezone.utc)
            contract.status, contract.stage = "analyzed", "done"
            contract.error_kind = contract.error_message = None

            for i, s in enumerate(result.segments):
                session.add(Segment(contract_id=contract_id, seg_index=i, seg_id=s.id, number=s.number,
                                    heading=s.heading, text=s.text, page_start=s.page_start, page_end=s.page_end))
            for i, f in enumerate(result.findings):
                session.add(Finding(
                    contract_id=contract_id, sort_order=i, source=f.source, category=f.category, severity=f.severity,
                    title=f.title, why_it_matters=f.why_it_matters, recommendation=f.recommendation,
                    suggested_wording=f.suggested_wording, quote=f.quote, segment_id=f.segment_id, page=f.page,
                    verified=f.verified, counts_toward_score=f.counts_toward_score, rule_id=f.rule_id,
                    legal_note=f.legal_note, legal_ref=f.legal_ref, condition_note=f.condition_note))
            await sync_contract_reminders(session, contract, facts)
            await log_event(session, organization_id=contract.organization_id, user_id=None,
                            action="contract.analyzed", entity_type="contract", entity_id=contract_id,
                            meta={"score": result.score.score, "findings": len(result.findings)})
            await session.commit()
            logger.info("analysis finished contract=%s score=%s", contract_id, result.score.score)
        except Exception as exc:
            await session.rollback()
            kind, message = classify_failure(exc)
            if kind == "internal":
                logger.exception("analysis crashed contract=%s", contract_id)
            else:
                logger.warning("analysis failed contract=%s kind=%s: %s", contract_id, kind, str(exc)[:200])
            async with async_session_maker() as s2:
                await s2.execute(update(Contract).where(Contract.id == contract_id).values(
                    status="failed", stage=None, error_kind=kind, error_message=message))
                await log_event(s2, organization_id=org_id, user_id=None,
                                action="contract.analysis_failed", entity_type="contract", entity_id=contract_id,
                                meta={"kind": kind})
                await s2.commit()


def _iso(value) -> Optional[date]:
    try:
        return date.fromisoformat(str(value)[:10]) if value else None
    except ValueError:
        return None


async def sync_contract_reminders(session: AsyncSession, contract: Contract, facts) -> None:
    """Contract dates become calendar reminders (idempotent): the end date, and the last day to stop auto-renewal.
    Identified by rule_id 'contract-end:<id>' / 'contract-notice:<id>' so re-analysis updates instead of duplicating."""
    from sqlalchemy import delete as sa_delete

    from app.workspaces.compliance_center.models import ComplianceTask

    today = datetime.now(timezone.utc).date()
    end = _iso(getattr(facts, "end_date", None))
    wanted = {}
    title = contract.title or "contract"
    if end and end >= today:
        wanted["contract-end"] = (end, f"Contract ends: {title}"[:190],
                                  "End date read by the AI from your contract. Confirm it in the contract, and decide whether to renew or renegotiate.")
        notice_days = getattr(facts, "renewal_notice_days", None)
        if getattr(facts, "auto_renewal", None) and notice_days:
            last_day = end - timedelta(days=int(notice_days))
            if last_day >= today:
                wanted["contract-notice"] = (last_day, f"Last day to stop auto-renewal: {title}"[:190],
                                             f"The contract renews automatically unless you give {notice_days} days' notice before {end.strftime('%d %b %Y')}. "
                                             "Dates are read by the AI; confirm them in the contract.")
    await session.execute(sa_delete(ComplianceTask).where(
        ComplianceTask.organization_id == contract.organization_id, ComplianceTask.is_custom.is_(True),
        ComplianceTask.rule_id.in_([f"contract-end:{contract.id}", f"contract-notice:{contract.id}"]),
        ComplianceTask.status == "pending"))
    for kind, (due, task_title, desc) in wanted.items():
        session.add(ComplianceTask(organization_id=contract.organization_id, user_id=None, title=task_title, category="corporate", due_date=due,
                                   description=desc, is_custom=True, status="pending", rule_id=f"{kind}:{contract.id}", period_key="once"))


async def mark_interrupted_jobs() -> int:
    """On startup: analyses that were running when the server stopped can never finish."""
    async with async_session_maker() as s:
        res = await s.execute(
            update(Contract).where(Contract.status.in_(["processing", "queued"]))
            .values(status="failed", stage=None, error_kind="interrupted",
                    error_message="The analysis was interrupted by a server restart. Click Retry to run it again."))
        await s.commit()
        return res.rowcount or 0


async def flag_legacy_contracts() -> int:
    """Contracts analysed by the v1 engine have no evidence-backed results; offer re-analysis
    instead of presenting them as reviewed."""
    async with async_session_maker() as s:
        res = await s.execute(
            update(Contract).where(Contract.status == "analyzed", Contract.prompt_version.is_(None))
            .values(status="failed", stage=None, error_kind="legacy",
                    error_message="This contract was reviewed with an earlier version of LegalOS. Click Try again to review it with the new engine."))
        await s.commit()
        return res.rowcount or 0


async def prepare_retry(session: AsyncSession, ctx: RequestContext, contract_id: uuid.UUID) -> Contract:
    c = await repository.get_contract(session, ctx.organization_id, contract_id)
    if not c:
        raise NotFoundException("Contract not found.")
    if c.status in ("processing", "queued"):
        raise BadRequestException("This contract is already being analysed.")
    c.status, c.stage, c.error_kind, c.error_message = "processing", "queued", None, None
    await log_event(session, organization_id=ctx.organization_id, user_id=ctx.user_id,
                    action="contract.reanalysis_requested", entity_type="contract", entity_id=c.id)
    await session.commit()
    return c


# ------------------------------------------------------------------ chat

_DEVANAGARI = re.compile(r"[ऀ-ॿ]")
_ENFORCE = re.compile(r"enforc|\bvalid|\blegal|binding|court|\bvoid|allowed|lawful|stand up|वैध|कानून|लागू|मान्य|अदालत|न्यायालय", re.I)
_NEGOTIATE = re.compile(r"negotiat|push back|ask for|priorit|\bfirst\b|biggest|worst|main risk|top risk|most important|"
                        r"बातचीत|सबसे|पहले|मुख्य जोखिम", re.I)
_CATEGORY_WORDS = {
    "non_compete": r"compet|restrain|प्रतिस्पर्धा", "penalty_damages": r"penalt|liquidated|damages|जुर्माना|हर्जाना",
    "payment_terms": r"interest|payment|deposit|escalat|rent|ब्याज|भुगतान|जमा", "termination": r"terminat|notice|exit|समाप्त",
    "dispute_resolution": r"arbitrat|court|jurisdiction|dispute|मध्यस्थ|अदालत|विवाद",
    "lock_in_exclusivity": r"lock|exclusiv", "liability_indemnity": r"guarant|indemn|liab|cheque|गारंटी|चेक",
    "assignment_subcontract": r"assign|transfer", "unilateral_change": r"price|change|revise|amend",
    "stamp_execution": r"stamp|regist|स्टाम्प", "other": r"certificate|original|document",
}
_SEV = {"critical": 0, "high": 1, "medium": 2, "low": 3}
_STOP = {"the", "and", "for", "what", "this", "that", "with", "can", "does", "are", "contract", "agreement", "how", "who"}


def rank_findings(rows: List[Finding]) -> List[Finding]:
    """Evidence-backed, open findings, most important first - the order to negotiate in."""
    live = [f for f in rows if f.counts_toward_score and f.status != "dismissed" and f.source != "missing"]
    return sorted(live, key=lambda f: (_SEV.get(f.severity, 9), f.sort_order))[:CHAT_TOP_FINDINGS]


def findings_block(ranked: List[Finding]) -> str:
    if not ranked:
        return "(no evidence-backed findings)"
    lines = []
    for i, f in enumerate(ranked, 1):
        where = ", ".join(x for x in (f.segment_id, f"p.{f.page}" if f.page else None) if x)
        quote = f' - quote: "{f.quote[:160]}"' if f.quote else ""
        legal = f" - legal note: {f.legal_note} ({f.legal_ref})" if f.legal_ref else ""
        lines.append(f"{i}. [{f.severity.upper()}] {f.title} ({where or 'whole contract'}){quote}{legal}")
    return "\n".join(lines)


def select_for_question(segs: List[EngineSegment], question: str, priority: set, budget: int) -> Tuple[List[EngineSegment], bool]:
    """Whole contract when it fits; otherwise the sections most relevant to the question (word overlap, plus the
    clauses behind the top findings), in document order - one call, nothing silently cut from the middle."""
    cost = [len(s.text) + len(s.heading) + 40 for s in segs]
    if sum(cost) <= budget:
        return segs, False
    words = {w for w in re.findall(r"\w{3,}", question.lower()) if w not in _STOP}
    score = [sum(w in s.text.lower() for w in words) + (2 if s.id in priority else 0) for s in segs]
    keep, used = set(), 0
    for i in sorted(range(len(segs)), key=lambda i: -score[i]):
        if used + cost[i] <= budget:
            keep.add(i)
            used += cost[i]
    return [s for i, s in enumerate(segs) if i in keep], True


def with_top_findings(citations: List[dict], ranked: List[Finding], top: int = 3) -> List[dict]:
    """'What should I negotiate first?' must cite the top findings in order, whatever the model chose to quote."""
    cited = {c["segment_id"] for c in citations}
    for f in ranked[:top]:
        if f.quote and f.verified and f.segment_id not in cited:
            citations.append({"quote": f.quote, "segment_id": f.segment_id, "page": f.page, "verified": True,
                              "finding": f.title, "legal_ref": f.legal_ref})
            cited.add(f.segment_id)
    return citations[:6]


def relevant_notes(ranked: List[Finding], citations: List[dict], question: str) -> List[Finding]:
    """Findings whose legal note answers an enforceability question: cited clause or matching topic."""
    cited = {c["segment_id"] for c in citations if c.get("segment_id")}
    out, refs = [], set()
    for f in ranked:
        topical = re.search(_CATEGORY_WORDS.get(f.category, r"$^"), question, re.I)
        if f.legal_ref and f.legal_ref not in refs and (f.segment_id in cited or topical):
            out.append(f)
            refs.add(f.legal_ref)
    return out[:2]


def legal_notes_text(notes: List[Finding], hindi: bool) -> str:
    head = ("कानूनी नोट (सामान्य जानकारी; भरोसा करने से पहले वकील से पुष्टि करें)" if hindi
            else "Legal note (general information; verify with a lawyer before relying)")
    return "".join(f"\n\n{head}: {f.legal_note} ({f.legal_ref})" for f in notes)


async def list_messages(session: AsyncSession, ctx: RequestContext, contract_id: uuid.UUID) -> List[ChatMessage]:
    c = await repository.get_contract(session, ctx.organization_id, contract_id)
    if not c:
        raise NotFoundException("Contract not found.")
    return await repository.all_messages(session, contract_id)


async def ask(session: AsyncSession, ctx: RequestContext, contract_id: uuid.UUID, question: str) -> ChatMessage:
    c = await repository.get_contract(session, ctx.organization_id, contract_id, full=True)
    if not c:
        raise NotFoundException("Contract not found.")
    if c.status != "analyzed":
        raise BadRequestException("This contract has not been analysed yet.")

    question = question.strip()
    ranked = rank_findings(c.findings)
    all_segs = _to_engine_segments(c.segments)
    segs, selected = select_for_question(all_segs, question, {f.segment_id for f in ranked}, pipeline.MAX_DOC_CHARS)
    history_rows = await repository.recent_messages(session, contract_id, 6)
    history = "\n".join(f"{m.role.upper()}: {m.content}" for m in history_rows) or "(none)"

    answer = await llm_client.generate_structured_async(
        prompts.CHAT_USER.format(
            history=history, question=question, document=render_for_llm(segs), findings=findings_block(ranked),
            coverage_note=(f"NOTE: this contract is long; you are shown the {len(segs)} of {len(all_segs)} sections most "
                           "relevant to the question. If the answer is not in them, say you could not find it.\n")
            if selected else ""),
        ChatAnswer, system=prompts.CHAT_SYSTEM, workspace="contract_chat", temperature=0.1,
        prompt_version=prompts.PROMPT_VERSION,
    )

    citations, verified_any = [], False
    for cit in answer.citations[:5]:
        m = verify.find_quote(cit.quote, all_segs, cit.segment_id)
        verified_any = verified_any or m.verified
        citations.append({"quote": cit.quote, "segment_id": m.segment_id or cit.segment_id,
                          "page": m.page, "verified": m.verified})
    hindi = bool(_DEVANAGARI.search(question))
    text = answer.answer.strip()
    if _NEGOTIATE.search(question):
        citations = with_top_findings(citations, ranked)
        verified_any = verified_any or any(ci["verified"] for ci in citations)
    if _ENFORCE.search(question):
        text += legal_notes_text(relevant_notes(ranked, citations, question), hindi)
    if answer.found_in_contract and not verified_any:
        text += ("\n\n(नोट: यह उत्तर अनुबंध के किसी सटीक अंश से मेल नहीं खा सका, कृपया अनुबंध स्वयं देखें।)" if hindi else
                 "\n\n(Note: I could not match this answer to an exact passage, so please check the contract itself.)")

    session.add(ChatMessage(contract_id=contract_id, role="user", content=question))
    reply = ChatMessage(contract_id=contract_id, role="assistant", content=text,
                        citations=citations, found_in_contract=answer.found_in_contract)
    session.add(reply)
    await log_event(session, organization_id=ctx.organization_id, user_id=ctx.user_id,
                    action="contract.question_asked", entity_type="contract", entity_id=contract_id)
    await session.commit()
    await session.refresh(reply)
    return reply


# ------------------------------------------------------------------ findings / delete

async def set_finding_status(session: AsyncSession, ctx: RequestContext, contract_id: uuid.UUID,
                             finding_id: uuid.UUID, status: str) -> Finding:
    c = await repository.get_contract(session, ctx.organization_id, contract_id)
    f = await session.get(Finding, finding_id)
    if not c or not f or f.contract_id != c.id:
        raise NotFoundException("Finding not found.")
    f.status = status
    await log_event(session, organization_id=ctx.organization_id, user_id=ctx.user_id,
                    action="finding.status_changed", entity_type="finding", entity_id=finding_id,
                    meta={"status": status})
    await session.commit()
    return f


async def delete_contract(session: AsyncSession, ctx: RequestContext, contract_id: uuid.UUID) -> None:
    c = await repository.get_contract(session, ctx.organization_id, contract_id)
    if not c:
        raise NotFoundException("Contract not found.")
    doc = await session.get(Document, c.document_id)
    path = doc.storage_path if doc else None
    from sqlalchemy import delete as sa_delete

    from app.workspaces.compliance_center.models import ComplianceTask
    await session.execute(sa_delete(ComplianceTask).where(
        ComplianceTask.organization_id == ctx.organization_id,
        ComplianceTask.rule_id.in_([f"contract-end:{contract_id}", f"contract-notice:{contract_id}"])))
    try:  # legacy v1 contracts indexed clause vectors in Qdrant
        from app.core.vectorstore import retrieval_service
        retrieval_service.delete_by_document("contract_clauses", str(c.document_id))
    except Exception as e:
        logger.debug("qdrant cleanup skipped: %s", e)
    await log_event(session, organization_id=ctx.organization_id, user_id=ctx.user_id,
                    action="contract.deleted", entity_type="contract", entity_id=contract_id)
    await session.delete(doc if doc else c)
    await session.commit()
    if path:
        await file_storage.delete_file(path)


async def get_file_path(session: AsyncSession, ctx: RequestContext, contract_id: uuid.UUID) -> Tuple[str, str]:
    c = await repository.get_contract(session, ctx.organization_id, contract_id)
    if not c or not c.document or not os.path.exists(c.document.storage_path):
        raise NotFoundException("The original file is no longer available.")
    return c.document.storage_path, c.document.original_filename
