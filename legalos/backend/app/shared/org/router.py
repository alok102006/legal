"""Organisation profile + onboarding endpoints (/api/v1/org)."""
import uuid
from typing import Dict, List, Literal, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import RequestContext, get_ctx, require_writer
from app.shared.audit import log_event
from app.shared.db.models import Organization
from app.shared.db.session import get_db_session
from app.shared.exceptions import BadRequestException
from app.shared.india import identifiers as ids

router = APIRouter()

EntityType = Literal["private_limited", "public_limited", "llp", "partnership", "sole_proprietorship",
                     "opc", "trust_society", "other"]
MsmeCategory = Literal["micro", "small", "medium", "none", "unknown"]

# Fields we need before the compliance calendar and contract rules can be accurate.
REQUIRED_FOR_ONBOARDING = ("legal_name", "entity_type", "state_code")


class OrgOut(BaseModel):
    id: uuid.UUID
    legal_name: str
    trade_name: Optional[str] = None
    entity_type: Optional[str] = None
    gstin: Optional[str] = None
    pan: Optional[str] = None
    cin_or_llpin: Optional[str] = None
    udyam_number: Optional[str] = None
    msme_category: Optional[str] = None
    industry: Optional[str] = None
    state_code: Optional[str] = None
    state_name: Optional[str] = None
    employee_band: Optional[str] = None
    turnover_band: Optional[str] = None
    gst_filing_frequency: Optional[str] = None
    registrations: Dict[str, bool] = {}
    onboarding_completed: bool = False
    missing_fields: List[str] = []

    model_config = {"from_attributes": True}


class OrgUpdate(BaseModel):
    legal_name: Optional[str] = Field(default=None, min_length=2, max_length=200)
    trade_name: Optional[str] = None
    entity_type: Optional[EntityType] = None
    gstin: Optional[str] = None
    pan: Optional[str] = None
    cin_or_llpin: Optional[str] = None
    udyam_number: Optional[str] = None
    msme_category: Optional[MsmeCategory] = None
    industry: Optional[str] = None
    state_code: Optional[str] = None
    employee_band: Optional[Literal["1-9", "10-19", "20-49", "50-199", "200+"]] = None
    turnover_band: Optional[Literal["lt20l", "20l-1.5cr", "1.5-5cr", "5-20cr", "20-50cr", "gt50cr"]] = None
    gst_filing_frequency: Optional[Literal["monthly", "quarterly", "none"]] = None
    registrations: Optional[Dict[str, bool]] = None


class GstinCheckIn(BaseModel):
    gstin: str


def _to_out(org: Organization) -> OrgOut:
    out = OrgOut.model_validate(org)
    out.missing_fields = [f for f in REQUIRED_FOR_ONBOARDING if not getattr(org, f)]
    return out


@router.get("", response_model=OrgOut)
async def get_org(ctx: RequestContext = Depends(get_ctx), db: AsyncSession = Depends(get_db_session)):
    org = await db.get(Organization, ctx.organization_id)
    return _to_out(org)


@router.post("/gstin-check")
async def gstin_check(body: GstinCheckIn, ctx: RequestContext = Depends(get_ctx)):
    """Offline GSTIN validation (format, checksum, state, PAN, holder type). No network call."""
    info = ids.decode_gstin(body.gstin)
    return {
        "valid": info.valid, "gstin": info.gstin, "error": info.error, "state_code": info.state_code,
        "state_name": info.state_name, "pan": info.pan, "holder_type": info.holder_type,
        "entity_hint": info.entity_hint,
        "registry_checked": False,
        "note": "Checksum and structure verified. This does not confirm the registration is active.",
    }


@router.patch("", response_model=OrgOut)
async def update_org(
    body: OrgUpdate,
    ctx: RequestContext = Depends(require_writer),
    db: AsyncSession = Depends(get_db_session),
):
    org = await db.get(Organization, ctx.organization_id)
    data = body.model_dump(exclude_unset=True)

    if "gstin" in data and data["gstin"]:
        info = ids.decode_gstin(data["gstin"])
        if not info.valid:
            raise BadRequestException(f"GSTIN: {info.error}")
        taken = await db.execute(select(Organization.id).where(Organization.gstin == info.gstin, Organization.id != org.id))
        if taken.first():
            raise BadRequestException("This GSTIN is already registered to another organisation on LegalOS.")
        data["gstin"] = info.gstin
        # Fill (never overwrite) details implied by the GSTIN
        data.setdefault("pan", info.pan)
        data.setdefault("state_code", info.state_code)
        if not org.entity_type and "entity_type" not in data and info.entity_hint:
            data["entity_type"] = info.entity_hint
    elif "gstin" in data:
        data["gstin"] = None

    if data.get("pan"):
        if not ids.validate_pan(data["pan"]):
            raise BadRequestException("PAN looks invalid (expected format AAAAA9999A).")
        data["pan"] = ids.normalize(data["pan"])
    if data.get("udyam_number"):
        if not ids.validate_udyam(data["udyam_number"]):
            raise BadRequestException("Udyam number looks invalid (expected format UDYAM-MH-26-0012345).")
        data["udyam_number"] = ids.normalize(data["udyam_number"])
    if data.get("state_code"):
        if data["state_code"] not in ids.STATE_CODES:
            raise BadRequestException("Unknown state code.")
        data["state_name"] = ids.STATE_CODES[data["state_code"]]

    for k, v in data.items():
        setattr(org, k, v)
    org.onboarding_completed = all(getattr(org, f) for f in REQUIRED_FOR_ONBOARDING)
    if org.onboarding_completed:
        # the compliance calendar depends on the profile: keep it in step (idempotent, never touches completed/custom tasks)
        from app.workspaces.compliance_center import service as compliance_service
        await compliance_service.sync_calendar(db, org)
    await log_event(db, organization_id=org.id, user_id=ctx.user_id, action="org.updated",
                    entity_type="organization", entity_id=org.id, meta={"fields": sorted(data.keys())})
    await db.commit()
    await db.refresh(org)
    return _to_out(org)


@router.get("/activity")
async def recent_activity(limit: int = 20, ctx: RequestContext = Depends(get_ctx), db: AsyncSession = Depends(get_db_session)):
    """Recent events in this organisation, phrased for the owner (from the audit log)."""
    from app.shared.db.models import AuditEvent
    from app.shared.org.activity import describe

    rows = (await db.execute(
        select(AuditEvent).where(AuditEvent.organization_id == ctx.organization_id)
        .order_by(AuditEvent.created_at.desc()).limit(max(1, min(limit, 50)) * 2)
    )).scalars().all()
    items = [d for d in (describe(r) for r in rows) if d]
    return items[:max(1, min(limit, 50))]


@router.get("/states")
async def list_states():
    return [{"code": c, "name": n} for c, n in sorted(ids.STATE_CODES.items(), key=lambda x: x[1])]
