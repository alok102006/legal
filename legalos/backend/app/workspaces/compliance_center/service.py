"""Compliance calendar service.

System tasks are generated from the rules engine and identified by (organisation, rule, period), so
syncing is idempotent: it never duplicates, never touches completed work, and never deletes tasks
the user created themselves.
"""
import logging
import uuid
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Dict, List, Optional

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import RequestContext
from app.shared.audit import log_event
from app.shared.db.models import Organization
from app.shared.exceptions import BadRequestException, NotFoundException
from app.workspaces.compliance_center.engine import schedule as sch
from app.workspaces.compliance_center.models import ComplianceTask

logger = logging.getLogger("legalos.compliance")

IST = timezone(timedelta(hours=5, minutes=30))
LOOKBACK_DAYS = 45      # recently-missed deadlines stay visible as overdue
HORIZON_DAYS = 400
DUE_SOON_DAYS = 7


def today_ist() -> date:
    return datetime.now(IST).date()


def org_facts(org: Organization) -> sch.OrgFacts:
    return sch.OrgFacts(
        entity_type=org.entity_type, registrations=dict(org.registrations or {}),
        gst_filing_frequency=org.gst_filing_frequency, turnover_band=org.turnover_band,
        employee_band=org.employee_band, state_code=org.state_code,
    )


def profile_ready(org: Organization) -> bool:
    return bool(org.entity_type and org.state_code)


def state_of(task: ComplianceTask, today: date) -> tuple[str, Optional[int]]:
    days = (task.due_date - today).days if task.due_date else None
    if task.status == "completed":
        return "done", days
    if days is None:
        return "upcoming", None
    if days < 0:
        return "overdue", days
    return ("due_soon" if days <= DUE_SOON_DAYS else "upcoming"), days


def to_out(task: ComplianceTask, today: date, origin: Optional[dict] = None) -> dict:
    state, days = state_of(task, today)
    rule = sch.rule_by_id(task.rule_id) if not task.is_custom else None
    estimate = sch.penalty_estimate(rule, task.due_date, today) if state == "overdue" else None
    portal = sch.portal_for(task.authority) if rule else None
    return {
        "file_where": portal["name"] if portal else None, "file_url": portal["url"] if portal else None,
        "verified": not bool(rule and rule.get("verify")), "penalty_estimate": estimate, "origin": origin,
        "id": task.id, "title": task.title, "category": task.category, "due_date": task.due_date,
        "status": task.status, "state": state, "days_left": days, "description": task.description,
        "penalty_desc": task.penalty_desc, "rule_id": task.rule_id, "period_label": task.period_label,
        "form_name": task.form_name, "authority": task.authority, "source_ref": task.source_ref,
        "needs_confirmation": task.needs_confirmation, "confirm_note": task.confirm_note,
        "is_custom": task.is_custom, "completed_at": task.completed_at, "completion_note": task.completion_note,
    }


async def origins_for(session: AsyncSession, org_id: uuid.UUID, tasks: List[ComplianceTask]) -> Dict[uuid.UUID, dict]:
    """Reminders pushed by other workspaces -> where they came from (derived on the fly, no schema change):
    contracts mark theirs with rule_id 'contract-end:<id>' / 'contract-notice:<id>'; notices and documents
    keep the task id on their own row. Never fails the calendar if another workspace's table is unavailable."""
    out: Dict[uuid.UUID, dict] = {}
    pushed = [t for t in tasks if t.is_custom]
    if not pushed:
        return out
    try:
        async with session.begin_nested():
            from app.workspaces.contract_intelligence.models import Contract
            from app.workspaces.knowledge_hub.models import KnowledgeDocument
            from app.workspaces.legal_notice_center.models import NoticeCase

            by_contract: Dict[uuid.UUID, List[uuid.UUID]] = {}
            for t in pushed:
                kind, _, ident = (t.rule_id or "").partition(":")
                if kind in ("contract-end", "contract-notice") and ident:
                    try:
                        by_contract.setdefault(uuid.UUID(ident), []).append(t.id)
                    except ValueError:
                        pass
            if by_contract:
                rows = (await session.execute(
                    select(Contract.id, Contract.title, Contract.counterparty_name)
                    .where(Contract.organization_id == org_id, Contract.id.in_(list(by_contract))))).all()
                for cid, title, cp in rows:
                    for tid in by_contract[cid]:
                        out[tid] = {"kind": "contract", "label": f"Contract: {title or cp or 'untitled'}", "href": f"/contracts/{cid}"}

            ids = [t.id for t in pushed if t.id not in out]
            if ids:
                rows = (await session.execute(
                    select(NoticeCase.id, NoticeCase.title, NoticeCase.source_name, NoticeCase.compliance_task_id)
                    .where(NoticeCase.organization_id == org_id, NoticeCase.compliance_task_id.in_(ids)))).all()
                for nid, title, src, tid in rows:
                    out[tid] = {"kind": "notice", "label": f"Notice: {title or src or 'untitled'}", "href": f"/notices/{nid}"}
                rows = (await session.execute(
                    select(KnowledgeDocument.id, KnowledgeDocument.title, KnowledgeDocument.expiry_task_id)
                    .where(KnowledgeDocument.organization_id == org_id, KnowledgeDocument.expiry_task_id.in_(ids)))).all()
                for did, title, tid in rows:
                    out[tid] = {"kind": "document", "label": f"Document: {title}", "href": f"/documents/{did}"}
    except Exception:  # noqa: BLE001 - origin links are a nicety; the calendar must still load
        logger.warning("could not resolve reminder origins", exc_info=True)
    return out


async def tasks_out(session: AsyncSession, org_id: uuid.UUID, tasks: List[ComplianceTask], today: Optional[date] = None) -> List[dict]:
    today = today or today_ist()
    origins = await origins_for(session, org_id, tasks)
    return [to_out(t, today, origins.get(t.id)) for t in tasks]



# ------------------------------------------------------------------ sync

@dataclass
class SyncResult:
    created: int = 0
    updated: int = 0
    removed: int = 0
    kept: int = 0


async def sync_calendar(session: AsyncSession, org: Organization, today: Optional[date] = None) -> SyncResult:
    today = today or today_ist()
    result = SyncResult()
    if not profile_ready(org):
        return result

    # Serialise concurrent syncs for the same organisation (e.g. two page requests arriving together):
    # the second waits for the first to commit, then sees its rows and creates nothing new.
    await session.execute(text("SELECT pg_advisory_xact_lock(hashtext(:k))"), {"k": f"compliance-sync:{org.id}"})

    facts = org_facts(org)
    decisions = sch.applicable_rules(facts)
    applicable_ids = {d.rule["id"] for d in decisions if d.applies}
    desired = sch.build_calendar(facts, today - timedelta(days=LOOKBACK_DAYS), today + timedelta(days=HORIZON_DAYS))
    version = sch.rules_version()

    rows = (await session.execute(
        select(ComplianceTask).where(ComplianceTask.organization_id == org.id, ComplianceTask.rule_id.is_not(None),
                                     ComplianceTask.is_custom.is_(False))        # reminders created by other workspaces are never touched
    )).scalars().all()
    existing: Dict[tuple, ComplianceTask] = {(r.rule_id, r.period_key): r for r in rows}

    for occ in desired:
        key = (occ.rule_id, occ.period_key)
        task = existing.get(key)
        fields = dict(
            title=occ.title, category=occ.category, due_date=occ.due_date, description=occ.description,
            penalty_desc=occ.penalty, period_label=occ.period_label, form_name=occ.form, authority=occ.authority,
            source_ref=occ.source, needs_confirmation=occ.needs_confirmation, confirm_note=occ.confirm_note,
            rules_version=version,
        )
        if task is None:
            session.add(ComplianceTask(organization_id=org.id, rule_id=occ.rule_id, period_key=occ.period_key,
                                       status="pending", is_custom=False, **fields))
            result.created += 1
        elif task.status == "completed":
            result.kept += 1
        else:
            changed = any(getattr(task, k) != v for k, v in fields.items() if k != "rules_version")
            for k, v in fields.items():
                setattr(task, k, v)
            result.updated += 1 if changed else 0
            result.kept += 0 if changed else 1

    # Remove untouched system tasks whose rule no longer applies (profile changed). Completed work stays.
    stale = [t for t in rows if t.status == "pending" and t.rule_id not in applicable_ids]
    for t in stale:
        await session.delete(t)
    result.removed = len(stale)
    await session.flush()
    return result


async def ensure_synced(session: AsyncSession, org: Organization) -> None:
    """First visit after onboarding: build the calendar if there is none yet."""
    if not profile_ready(org):
        return
    n = (await session.execute(
        select(func.count()).select_from(ComplianceTask)
        .where(ComplianceTask.organization_id == org.id, ComplianceTask.rule_id.is_not(None))
    )).scalar_one()
    if n == 0:
        await sync_calendar(session, org)
        await session.commit()


# ------------------------------------------------------------------ queries

async def list_tasks(
    session: AsyncSession, org: Organization, state: Optional[str] = None, category: Optional[str] = None,
    today: Optional[date] = None,
) -> List[dict]:
    today = today or today_ist()
    await ensure_synced(session, org)
    stmt = select(ComplianceTask).where(ComplianceTask.organization_id == org.id)
    if category:
        stmt = stmt.where(ComplianceTask.category == category)
    stmt = stmt.order_by(ComplianceTask.due_date.asc().nullslast(), ComplianceTask.title)
    tasks = (await session.execute(stmt)).scalars().all()
    out = await tasks_out(session, org.id, list(tasks), today)
    if state:
        out = [t for t in out if t["state"] == state]
    # hide completed items that are far in the past so the list stays focused
    cutoff = today - timedelta(days=LOOKBACK_DAYS)
    return [t for t in out if not (t["state"] == "done" and t["due_date"] and t["due_date"] < cutoff)]


async def summary(session: AsyncSession, org: Organization, today: Optional[date] = None) -> dict:
    today = today or today_ist()
    version = sch.rules_version()
    if not profile_ready(org):
        return {"needs_profile": True, "rules_version": version, "today": today, "next_deadlines": [], **_rule_counts(None)}
    await ensure_synced(session, org)
    tasks = (await session.execute(select(ComplianceTask).where(ComplianceTask.organization_id == org.id))).scalars().all()
    pending = [t for t in tasks if t.status == "pending" and t.due_date]
    overdue = [t for t in pending if t.due_date < today]
    upcoming = sorted([t for t in pending if t.due_date >= today], key=lambda t: t.due_date)
    month_ago = datetime.now(timezone.utc) - timedelta(days=30)
    system = [t for t in tasks if not t.is_custom and t.rule_id]
    last_synced = max((max(t.updated_at, t.created_at) for t in system), default=None)
    return {
        "needs_profile": False,
        "overdue": len(overdue),
        "due_in_7_days": sum(1 for t in upcoming if (t.due_date - today).days <= 7),
        "due_in_30_days": sum(1 for t in upcoming if (t.due_date - today).days <= 30),
        "completed_last_30_days": sum(1 for t in tasks if t.status == "completed" and t.completed_at and t.completed_at >= month_ago),
        "needs_confirmation": sum(1 for t in upcoming[:30] if t.needs_confirmation),
        "next_deadlines": [
            {"id": t.id, "title": t.title, "period_label": t.period_label, "due_date": t.due_date,
             "days_left": (t.due_date - today).days, "needs_confirmation": t.needs_confirmation}
            for t in upcoming[:5]
        ],
        "rules_version": version, "today": today, "last_synced": last_synced, **_rule_counts(org),
    }


def _rule_counts(org: Optional[Organization]) -> dict:
    rules = sch.load_rules()["rules"]
    out = {"rules_total": len(rules), "sources_total": len({r.get("source", "") for r in rules if r.get("source")}),
           "rules_applicable": 0}
    if org is not None:
        out["rules_applicable"] = sum(1 for d in sch.applicable_rules(org_facts(org)) if d.applies)
    return out


_FACTS = [
    ("entity_type", "Type of business", "field"), ("state_code", "State", "field"),
    ("gst", "GST registration", "registration"), ("gst_composition", "GST composition scheme", "registration"),
    ("gst_filing_frequency", "How you file GST", "field"), ("turnover_band", "Yearly turnover", "field"),
    ("tds", "TDS (tax deducted at source)", "registration"), ("pf", "Provident Fund (EPF)", "registration"),
    ("esi", "ESI", "registration"), ("pt", "Professional Tax", "registration"),
    ("employee_band", "Employees", "field"), ("always", "Applies to every business", "always"),
]


def profile_facts(org: Organization) -> dict:
    """Profile facts -> the rules each one switches on or off. Computed on the fly from the rules file."""
    decisions = sch.applicable_rules(org_facts(org))
    regs = org.registrations or {}
    facts = []
    for key, label, kind in _FACTS:
        rules = []
        for d in decisions:
            r = d.rule
            keys = ["always"] if r.get("when", {}).get("always") else sch.fact_keys(r)
            if key in keys:
                rules.append({"id": r["id"], "title": r["title"], "form": r.get("form", ""), "applies": d.applies,
                              "reason": d.reason, "verified": not bool(r.get("verify"))})
        rules.sort(key=lambda x: (not x["applies"], x["title"]))
        if kind == "registration":
            value = "yes" if regs.get(key) else "no"
        elif kind == "field":
            value = getattr(org, key, None)
        else:
            value = None
        hint = None
        if key == "employee_band" and org.employee_band:
            hint = ("With 20 or more employees, PF registration is usually required. Switch on Provident Fund if you have one."
                    if org.employee_band in ("20-49", "50-199", "200+") and not regs.get("pf")
                    else "No filing depends on this directly. PF and ESI follow the registrations you have switched on.")
        if not rules and key != "employee_band":
            continue
        facts.append({"key": key, "label": label, "kind": kind, "value": value, "hint": hint, "rules": rules})
    return {"facts": facts, "rules_applicable": sum(1 for d in decisions if d.applies), "rules_total": len(decisions)}


def rules_overview(org: Organization) -> dict:
    decisions = sch.applicable_rules(org_facts(org))
    applicable, skipped = [], []
    for d in decisions:
        r = d.rule
        if d.applies:
            applicable.append({
                "id": r["id"], "title": r["title"], "category": r.get("category", "other"), "authority": r.get("authority", ""),
                "form": r.get("form", ""), "description": r.get("description", ""), "penalty": r.get("penalty", ""),
                "source": r.get("source", ""), "reason": d.reason,
                "needs_confirmation": bool(r.get("needs_confirmation") or r.get("verify")),
                "confirm_note": r.get("confirm_note"), "verify": bool(r.get("verify")),
                "verified": not bool(r.get("verify")),
            })
        else:
            skipped.append({"id": r["id"], "title": r["title"], "reason": d.reason})
    return {"rules_version": sch.rules_version(), "applicable": applicable, "not_applicable": skipped,
            "not_covered": sch.not_covered()}


# ------------------------------------------------------------------ mutations

async def _get(session: AsyncSession, org_id: uuid.UUID, task_id: uuid.UUID) -> ComplianceTask:
    t = await session.get(ComplianceTask, task_id)
    if not t or t.organization_id != org_id:
        raise NotFoundException("Task not found.")
    return t


async def create_custom(session: AsyncSession, ctx: RequestContext, payload) -> ComplianceTask:
    t = ComplianceTask(
        organization_id=ctx.organization_id, user_id=ctx.user_id, title=payload.title.strip(), category=payload.category,
        due_date=payload.due_date, description=payload.description, status="pending", is_custom=True,
    )
    session.add(t)
    await log_event(session, organization_id=ctx.organization_id, user_id=ctx.user_id, action="compliance.task_created",
                    entity_type="compliance_task", entity_id=t.id, meta={"title": t.title})
    await session.commit()
    await session.refresh(t)
    return t


async def update_task(session: AsyncSession, ctx: RequestContext, task_id: uuid.UUID, data: dict) -> ComplianceTask:
    t = await _get(session, ctx.organization_id, task_id)
    editable = {"title", "due_date", "description", "category"}
    if not t.is_custom and editable & set(data):
        raise BadRequestException("Deadlines from the rules engine can't be edited. Add your own reminder instead.")
    for k in editable & set(data):
        if data[k] is not None:
            setattr(t, k, data[k])
    status = data.get("status")
    if status == "completed" and t.status != "completed":
        t.status, t.completed_at = "completed", datetime.now(timezone.utc)
        t.completion_note = data.get("note") or t.completion_note
    elif status == "pending" and t.status != "pending":
        t.status, t.completed_at, t.completion_note = "pending", None, None
    elif "note" in data and data["note"] is not None:
        t.completion_note = data["note"]
    await log_event(session, organization_id=ctx.organization_id, user_id=ctx.user_id, action="compliance.task_updated",
                    entity_type="compliance_task", entity_id=t.id, meta={"fields": sorted(data.keys()), "status": t.status})
    await session.commit()
    await session.refresh(t)
    return t


async def bulk_complete(session: AsyncSession, ctx: RequestContext, ids: List[uuid.UUID], note: Optional[str]) -> int:
    """Catch-up for new accounts: mark several pending tasks as already filed (only this organisation's)."""
    rows = (await session.execute(
        select(ComplianceTask).where(
            ComplianceTask.organization_id == ctx.organization_id, ComplianceTask.id.in_(ids), ComplianceTask.status == "pending")
    )).scalars().all()
    now = datetime.now(timezone.utc)
    for t in rows:
        t.status, t.completed_at = "completed", now
        t.completion_note = note or "Marked as already filed"
    await log_event(session, organization_id=ctx.organization_id, user_id=ctx.user_id, action="compliance.bulk_completed",
                    meta={"count": len(rows)})
    await session.commit()
    return len(rows)


async def delete_task(session: AsyncSession, ctx: RequestContext, task_id: uuid.UUID) -> None:
    t = await _get(session, ctx.organization_id, task_id)
    if not t.is_custom:
        raise BadRequestException(
            "This deadline comes from the rules for your company. Mark it completed, or update your company profile if it doesn't apply.")
    await log_event(session, organization_id=ctx.organization_id, user_id=ctx.user_id, action="compliance.task_deleted",
                    entity_type="compliance_task", entity_id=t.id)
    await session.delete(t)
    await session.commit()
