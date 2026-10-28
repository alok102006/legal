"""Vendor service: create / re-check / link vendors. Every read and write is scoped to the organisation."""
import asyncio
import dataclasses
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from rapidfuzz import fuzz
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.dependencies import RequestContext
from app.shared.audit import log_event
from app.shared.exceptions import BadRequestException, NotFoundException
from app.shared.india import identifiers as ids
from app.workspaces.contract_intelligence.models import Contract
from app.workspaces.legal_notice_center.models import NoticeCase
from app.workspaces.vendor_intelligence import engine, registry
from app.workspaces.vendor_intelligence.errors import AUTH, QUOTA, UNAVAILABLE
from app.workspaces.vendor_intelligence.models import Vendor

logger = logging.getLogger("legalos.vendors")
NAME_MATCH_THRESHOLD = 85
HISTORY_LIMIT = 20


def _clean(v: Optional[str]) -> Optional[str]:
    v = (v or "").strip()
    return v or None


def _registry_dict(r: engine.RegistryResult) -> dict:
    return {k: v for k, v in dataclasses.asdict(r).items() if v not in (None, "")}


async def _apply_assessment(v: Vendor, force: bool = False) -> engine.RegistryResult:
    """Looks the supplier up (cache first, unless `force`) and stores the verdict on it. Returns the registry result."""
    reg = await registry.lookup(v.gstin, force=force)
    _apply_registry(v, reg)
    return reg


def _apply_registry(v: Vendor, reg: engine.RegistryResult) -> None:
    a = engine.assess(v.name, v.gstin, v.pan, v.state_code, v.udyam_number, v.msme_category, reg)
    now = datetime.now(timezone.utc)
    prior = list((v.registry_data or {}).get("history") or [])
    entry = {"at": now.isoformat(), "risk_level": a.risk_level, "registry_source": reg.source,
             "registry_status": reg.status, "summary": a.summary}
    v.risk_level, v.summary = a.risk_level, a.summary
    v.checks = [dataclasses.asdict(c) for c in a.checks]
    v.registry_source = reg.source
    v.registry_data = {**_registry_dict(reg), "history": (prior + [entry])[-HISTORY_LIMIT:]}
    v.last_checked_at = now
    # fill what the checks derived, never overwriting what the user entered
    v.pan = v.pan or a.derived.get("pan")
    v.state_code = v.state_code or a.derived.get("state_code")
    v.msme_category = v.msme_category or a.derived.get("msme_category")


def _normalise(data: dict) -> dict:
    out = dict(data)
    if "gstin" in out:
        g = _clean(out["gstin"])
        out["gstin"] = ids.normalize(g) if g else None
    if "pan" in out:
        p = _clean(out["pan"])
        out["pan"] = ids.normalize(p) if p else None
    if "udyam_number" in out:
        u = _clean(out["udyam_number"])
        out["udyam_number"] = ids.normalize(u) if u else None
    if "name" in out and out["name"]:
        out["name"] = out["name"].strip()
    if out.get("state_code") and out["state_code"] not in ids.STATE_CODES:
        raise BadRequestException("Unknown state code.")
    return out


def to_brief(v: Vendor) -> dict:
    return {
        "id": v.id, "name": v.name, "gstin": v.gstin, "pan": v.pan, "udyam_number": v.udyam_number,
        "state_name": ids.STATE_CODES.get(v.state_code or ""),
        "msme_category": v.msme_category, "risk_level": v.risk_level, "summary": v.summary,
        "registry_source": v.registry_source, "last_checked_at": v.last_checked_at, "created_at": v.created_at,
    }


def _names_match(names: List[str], candidate: Optional[str]) -> bool:
    c = (candidate or "").lower()
    return bool(c) and any(fuzz.token_set_ratio(n.lower(), c) >= NAME_MATCH_THRESHOLD for n in names if n)


async def linked_contracts(session: AsyncSession, org_id: uuid.UUID, vendor_name) -> List[dict]:
    """Contracts whose counterparty matches any of the given name(s)."""
    names = [vendor_name] if isinstance(vendor_name, str) else [n for n in vendor_name if n]
    if not names:
        return []
    rows = (await session.execute(select(Contract).where(Contract.organization_id == org_id))).scalars().all()
    return [{"id": c.id, "title": c.title, "status": c.status, "risk_level": c.risk_level, "overall_score": c.overall_score}
            for c in rows if _names_match(names, c.counterparty_name)]


async def linked_notices(session: AsyncSession, org_id: uuid.UUID, names: List[str], identifier: Optional[str]) -> List[dict]:
    """Notices issued by this supplier (name match on issuer) or whose text quotes its GSTIN/PAN."""
    names = [n for n in names if n]
    stmt = select(NoticeCase).where(NoticeCase.organization_id == org_id).order_by(NoticeCase.created_at.desc()).limit(300)
    out = []
    for n in (await session.execute(stmt)).scalars().all():
        quoted = bool(identifier and len(identifier) >= 10 and n.raw_text and identifier in n.raw_text.upper().replace(" ", ""))
        if quoted or _names_match(names, n.issuer_name):
            out.append({"id": n.id, "title": n.title or n.issuer_name, "status": n.status, "urgency": n.urgency,
                        "response_deadline": n.response_deadline})
    return out


def _kind_of(v: Vendor) -> str:
    return "gstin" if v.gstin else "pan" if v.pan else "udyam" if v.udyam_number else "gstin"


def _vendor_names(v: Vendor) -> List[str]:
    reg = v.registry_data or {}
    return [v.name, reg.get("legal_name"), reg.get("trade_name")]


async def to_detail(session: AsyncSession, v: Vendor) -> dict:
    d = to_brief(v)
    stored = dict(v.registry_data or {})
    history = list(reversed(stored.pop("history", []) or []))
    mode, provider = registry.registry_mode(registry.result_from_dict(stored, v.registry_source))
    names = _vendor_names(v)
    d.update(kind=_kind_of(v), pan=v.pan, state_code=v.state_code, udyam_number=v.udyam_number, notes=v.notes,
             reasons=engine.reasons_for(v.checks or [], v.risk_level), checks=v.checks or [], registry=stored,
             registry_mode=mode, registry_provider=provider, history=history,
             contracts=await linked_contracts(session, v.organization_id, names),
             notices=await linked_notices(session, v.organization_id, names, v.gstin or v.pan))
    return d


async def get_vendor(session: AsyncSession, ctx: RequestContext, vendor_id: uuid.UUID) -> Vendor:
    v = await session.get(Vendor, vendor_id)
    if not v or v.organization_id != ctx.organization_id:
        raise NotFoundException("Vendor not found.")
    return v


async def list_vendors(session: AsyncSession, ctx: RequestContext) -> List[Vendor]:
    stmt = select(Vendor).where(Vendor.organization_id == ctx.organization_id).order_by(Vendor.created_at.desc())
    return list((await session.execute(stmt)).scalars().all())


async def create_vendor(session: AsyncSession, ctx: RequestContext, data: dict) -> Vendor:
    data = _normalise(data)
    v = Vendor(organization_id=ctx.organization_id, created_by=ctx.user_id, **data)
    await _apply_assessment(v)
    session.add(v)
    try:
        await session.flush()
    except IntegrityError:
        await session.rollback()
        raise BadRequestException("A vendor with this GSTIN is already in your list.")
    await log_event(session, organization_id=ctx.organization_id, user_id=ctx.user_id, action="vendor.checked",
                    entity_type="vendor", entity_id=v.id, meta={"risk": v.risk_level, "source": v.registry_source})
    await session.commit()
    await session.refresh(v)
    return v


async def update_vendor(session: AsyncSession, ctx: RequestContext, vendor_id: uuid.UUID, data: dict) -> Vendor:
    v = await get_vendor(session, ctx, vendor_id)
    for k, val in _normalise(data).items():
        setattr(v, k, val)
    await _apply_assessment(v)
    try:
        await session.flush()
    except IntegrityError:
        await session.rollback()
        raise BadRequestException("Another vendor with this GSTIN is already in your list.")
    await log_event(session, organization_id=ctx.organization_id, user_id=ctx.user_id, action="vendor.updated",
                    entity_type="vendor", entity_id=v.id, meta={"risk": v.risk_level})
    await session.commit()
    await session.refresh(v)
    return v


async def recheck(session: AsyncSession, ctx: RequestContext, vendor_id: uuid.UUID, refresh: bool = False) -> Vendor:
    """Re-runs the checks. A registry answer fetched in the last 24 h is reused; `refresh=True` asks (and pays) again."""
    v = await get_vendor(session, ctx, vendor_id)
    await _apply_assessment(v, force=refresh)
    await log_event(session, organization_id=ctx.organization_id, user_id=ctx.user_id, action="vendor.rechecked",
                    entity_type="vendor", entity_id=v.id, meta={"risk": v.risk_level, "refresh": refresh})
    await session.commit()
    await session.refresh(v)
    return v


RECHECK_CONCURRENCY = 4


async def recheck_all(session: AsyncSession, ctx: RequestContext) -> Dict[str, Any]:
    """Re-checks every saved supplier of the organisation. Cached registry answers are free; at most
    `registry_recheck_max_live` paid lookups are made per call and the rest are reported as deferred (they keep their
    previous verdict untouched). Lookups run a few at a time; nothing is saved until all have answered."""
    vendors = await list_vendors(session, ctx)
    budget = max(0, settings.registry_recheck_max_live)
    plan: List[Vendor] = []
    deferred: List[Vendor] = []
    for v in vendors:
        if registry.needs_live_call(v.gstin):
            if budget <= 0:
                deferred.append(v)
                continue
            budget -= 1
        plan.append(v)

    gate = asyncio.Semaphore(RECHECK_CONCURRENCY)

    async def look(v: Vendor) -> engine.RegistryResult:
        async with gate:
            return await registry.lookup(v.gstin)

    results = await asyncio.gather(*(look(v) for v in plan))
    changed, live, from_cache, failed = [], 0, 0, 0
    provider = registry.active_provider()
    for v, reg in zip(plan, results):
        before = v.risk_level
        if reg.source == "unavailable" and provider and reg.error_kind in (AUTH, QUOTA, UNAVAILABLE):
            failed += 1                       # keep the earlier verdict: a failed lookup must not overwrite a good one
            continue
        _apply_registry(v, reg)
        if reg.cached:
            from_cache += 1
        elif reg.source == "live":
            live += 1
        if v.risk_level != before:
            changed.append({"id": v.id, "name": v.name, "previous": before, "current": v.risk_level})
    await log_event(session, organization_id=ctx.organization_id, user_id=ctx.user_id, action="vendor.rechecked_all",
                    entity_type="vendor", meta={"total": len(vendors), "live": live, "cached": from_cache,
                                                "failed": failed, "deferred": len(deferred), "changed": len(changed)})
    await session.commit()
    return {"total": len(vendors), "rechecked": len(plan) - failed, "live_lookups": live, "from_cache": from_cache,
            "failed": failed, "deferred": len(deferred), "deferred_names": [v.name for v in deferred][:20],
            "changed": changed, "registry_mode": registry.registry_mode()[0],
            "max_live_per_run": settings.registry_recheck_max_live}


async def delete_vendor(session: AsyncSession, ctx: RequestContext, vendor_id: uuid.UUID) -> None:
    v = await get_vendor(session, ctx, vendor_id)
    await log_event(session, organization_id=ctx.organization_id, user_id=ctx.user_id, action="vendor.deleted",
                    entity_type="vendor", entity_id=v.id)
    await session.delete(v)
    await session.commit()


async def quick_check(data: dict) -> dict:
    """Instant check without saving (kept for older callers)."""
    d = _normalise({k: v for k, v in data.items() if v is not None})
    reg = await registry.lookup(d.get("gstin"))
    a = engine.assess(d.get("name", ""), d.get("gstin"), d.get("pan"), d.get("state_code"), None, None, reg)
    return {"risk_level": a.risk_level, "summary": a.summary, "checks": [dataclasses.asdict(c) for c in a.checks],
            "registry": _registry_dict(reg), "registry_source": reg.source}


def classify_identifier(raw: str, kind: Optional[str] = None) -> Tuple[str, str]:
    """Any supported number -> (kind, canonical value). `kind` forces the reading (needed for an alphanumeric IEC,
    which looks like a PAN). Unrecognised input is treated as a (malformed) GSTIN so the offline check can say exactly
    what is wrong with it."""
    if kind:
        return kind, {"udyam": ids.normalize_udyam, "pf": ids.normalize_pf}.get(kind, ids.normalize)(raw)
    return ids.identify(raw)


_SAVED_COLUMN = {"gstin": Vendor.gstin, "pan": Vendor.pan, "udyam": Vendor.udyam_number}


async def check_identifier(session: AsyncSession, ctx: RequestContext, raw: str, name: Optional[str] = None,
                           state_code: Optional[str] = None, kind: Optional[str] = None) -> Dict[str, Any]:
    """The check desk: verify one number (no saving). Offline checks always run; the live registry is asked for GSTINs
    (and answers come from the 24 h cache when possible). CIN, TAN, LLPIN, IFSC, IEC, FSSAI, ESIC and PF numbers get
    format checks only: no public registry can be asked for them, and the answer says where to confirm."""
    if not ids.normalize(raw):
        raise BadRequestException("Enter a GSTIN, PAN, Udyam, CIN, TAN, IFSC or other business number.")
    if state_code and state_code not in ids.STATE_CODES:
        raise BadRequestException("Unknown state code.")
    if kind and kind not in ids.KINDS:
        raise BadRequestException(f"Unknown number type '{kind}'.")
    kind, ident = classify_identifier(raw, kind)
    if kind in _SAVED_COLUMN:
        reg = await registry.lookup(ident if kind == "gstin" else None)
        a = engine.assess((name or "").strip(), ident if kind == "gstin" else None, ident if kind == "pan" else None, state_code,
                          ident if kind == "udyam" else None, None, reg)
        mode, provider = registry.registry_mode(reg)
        col = _SAVED_COLUMN[kind]
        saved = (await session.execute(select(Vendor).where(Vendor.organization_id == ctx.organization_id, col == ident).limit(1))).scalars().first()
    else:
        reg = engine.RegistryResult(source="unavailable", error_kind="not_connected",
                                    message="No public registry can be queried for this type of number.")
        a = engine.assess_identifier(kind, ident, (name or "").strip() or None)
        mode, provider, saved = "offline", None, None
    names = [name or "", reg.legal_name or "", reg.trade_name or ""] + (_vendor_names(saved) if saved else [])
    return {
        "kind": kind, "identifier": ident, "suggested_name": reg.legal_name if reg.source != "unavailable" else None,
        "risk_level": a.risk_level, "summary": a.summary, "reasons": a.reasons,
        "checks": [dataclasses.asdict(c) for c in a.checks],
        "registry": _registry_dict(reg), "registry_source": reg.source, "registry_mode": mode, "registry_provider": provider,
        "state_name": a.derived.get("state_name"), "pan": a.derived.get("pan"), "holder_type": a.derived.get("holder_type"),
        "details": {k: v for k, v in a.derived.items() if kind not in _SAVED_COLUMN},
        "saved_vendor": to_brief(saved) if saved else None,
        "contracts": await linked_contracts(session, ctx.organization_id, names),
        "notices": await linked_notices(session, ctx.organization_id, names, ident if kind != "udyam" else None),
        "checked_at": datetime.now(timezone.utc),
    }


async def match_by_name(session: AsyncSession, org_id: uuid.UUID, name: Optional[str]) -> Optional[Vendor]:
    if not name:
        return None
    rows = (await session.execute(select(Vendor).where(Vendor.organization_id == org_id))).scalars().all()
    best, best_score = None, 0
    for v in rows:
        s = fuzz.token_set_ratio(name.lower(), v.name.lower())
        if s > best_score:
            best, best_score = v, s
    return best if best_score >= NAME_MATCH_THRESHOLD else None
