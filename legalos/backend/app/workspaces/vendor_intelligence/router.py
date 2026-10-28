import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.dependencies import RequestContext, get_ctx, require_writer
from app.shared.db.session import get_db_session
from app.workspaces.vendor_intelligence import engine, registry, schemas, service

router = APIRouter()


@router.get("", response_model=List[schemas.VendorBrief])
async def list_vendors(db: AsyncSession = Depends(get_db_session), ctx: RequestContext = Depends(get_ctx)):
    return [service.to_brief(v) for v in await service.list_vendors(db, ctx)]


@router.get("/samples", response_model=List[schemas.SampleOut])
async def samples(ctx: RequestContext = Depends(get_ctx)):
    """Demo-only sample suppliers so the registry checks can be shown without paid API access."""
    return registry.sample_gstins() if settings.demo_mode else []


@router.post("/quick-check", response_model=schemas.QuickCheckOut)
async def quick_check(body: schemas.QuickCheckIn, ctx: RequestContext = Depends(get_ctx)):
    return await service.quick_check(body.model_dump())


@router.post("/check", response_model=schemas.CheckResult)
async def check(body: schemas.CheckIn, db: AsyncSession = Depends(get_db_session), ctx: RequestContext = Depends(get_ctx)):
    """The check desk: verify a GSTIN, PAN or Udyam number (offline checks + live registry when connected). Does not save."""
    return await service.check_identifier(db, ctx, body.identifier, body.name, body.state_code, body.kind)


@router.get("/risk-rules", response_model=schemas.RiskRulesOut)
async def risk_rules(ctx: RequestContext = Depends(get_ctx)):
    """Plain-English explanation of every check and of how the verdict (high / medium / low / unverified) is reached."""
    return engine.RISK_RULES


@router.post("/recheck-all", response_model=schemas.RecheckAllOut)
async def recheck_all(db: AsyncSession = Depends(get_db_session), ctx: RequestContext = Depends(require_writer)):
    """Re-check every saved supplier. Registry answers fetched in the last 24 h are reused (no paid call); at most
    REGISTRY_RECHECK_MAX_LIVE paid lookups are made per run."""
    return await service.recheck_all(db, ctx)


@router.get("/match", response_model=Optional[schemas.VendorBrief])
async def match(name: str = Query(..., min_length=2), db: AsyncSession = Depends(get_db_session),
                ctx: RequestContext = Depends(get_ctx)):
    v = await service.match_by_name(db, ctx.organization_id, name)
    return service.to_brief(v) if v else None


@router.post("", response_model=schemas.VendorDetail, status_code=201)
async def create_vendor(body: schemas.VendorIn, db: AsyncSession = Depends(get_db_session),
                        ctx: RequestContext = Depends(require_writer)):
    v = await service.create_vendor(db, ctx, body.model_dump())
    return await service.to_detail(db, v)


@router.get("/{vendor_id}", response_model=schemas.VendorDetail)
async def get_vendor(vendor_id: uuid.UUID, db: AsyncSession = Depends(get_db_session), ctx: RequestContext = Depends(get_ctx)):
    return await service.to_detail(db, await service.get_vendor(db, ctx, vendor_id))


@router.patch("/{vendor_id}", response_model=schemas.VendorDetail)
async def update_vendor(vendor_id: uuid.UUID, body: schemas.VendorUpdate, db: AsyncSession = Depends(get_db_session),
                        ctx: RequestContext = Depends(require_writer)):
    v = await service.update_vendor(db, ctx, vendor_id, body.model_dump(exclude_unset=True))
    return await service.to_detail(db, v)


@router.post("/{vendor_id}/recheck", response_model=schemas.VendorDetail)
async def recheck_vendor(vendor_id: uuid.UUID, refresh: bool = Query(False, description="Ask the live registry again even if a 24 h old answer is stored (costs a lookup)"),
                         db: AsyncSession = Depends(get_db_session), ctx: RequestContext = Depends(require_writer)):
    return await service.to_detail(db, await service.recheck(db, ctx, vendor_id, refresh))


@router.delete("/{vendor_id}")
async def delete_vendor(vendor_id: uuid.UUID, db: AsyncSession = Depends(get_db_session),
                        ctx: RequestContext = Depends(require_writer)):
    await service.delete_vendor(db, ctx, vendor_id)
    return {"status": "deleted"}
