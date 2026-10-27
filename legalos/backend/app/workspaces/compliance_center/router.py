import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import RequestContext, get_ctx, get_organization, require_writer
from app.shared.audit import log_event
from app.shared.db.models import Organization
from app.shared.db.session import get_db_session
from app.workspaces.compliance_center import schemas, service

router = APIRouter()


@router.get("/tasks", response_model=List[schemas.TaskOut])
async def list_tasks(
    state: Optional[str] = Query(None, pattern="^(overdue|due_soon|upcoming|done)$"),
    category: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db_session),
    org: Organization = Depends(get_organization),
):
    return await service.list_tasks(db, org, state, category)


@router.get("/summary", response_model=schemas.SummaryOut)
async def get_summary(db: AsyncSession = Depends(get_db_session), org: Organization = Depends(get_organization)):
    return await service.summary(db, org)


@router.get("/rules", response_model=schemas.RulesOverview)
async def get_rules(org: Organization = Depends(get_organization)):
    """Which rules apply to this company and why, which don't, and what we don't cover yet."""
    return service.rules_overview(org)


@router.get("/profile-facts", response_model=schemas.ProfileFacts)
async def get_profile_facts(org: Organization = Depends(get_organization)):
    """The company facts that drive the calendar, each with the rules it switches on or off."""
    return service.profile_facts(org)


@router.post("/sync", response_model=schemas.SyncOut)
async def sync(
    db: AsyncSession = Depends(get_db_session),
    org: Organization = Depends(get_organization),
    ctx: RequestContext = Depends(require_writer),
):
    """Rebuilds the calendar from the company profile. Never deletes completed or custom tasks."""
    result = await service.sync_calendar(db, org)
    await log_event(db, organization_id=ctx.organization_id, user_id=ctx.user_id, action="compliance.synced",
                    meta={"created": result.created, "removed": result.removed})
    await db.commit()
    return {**result.__dict__, "rules_version": service.sch.rules_version()}


@router.post("/tasks", response_model=schemas.TaskOut, status_code=201)
async def create_task(
    payload: schemas.TaskCreate,
    db: AsyncSession = Depends(get_db_session),
    ctx: RequestContext = Depends(require_writer),
):
    task = await service.create_custom(db, ctx, payload)
    return (await service.tasks_out(db, ctx.organization_id, [task]))[0]


@router.post("/tasks/bulk-complete", response_model=schemas.BulkCompleteOut)
async def bulk_complete(
    payload: schemas.BulkCompleteIn,
    db: AsyncSession = Depends(get_db_session),
    ctx: RequestContext = Depends(require_writer),
):
    return {"completed": await service.bulk_complete(db, ctx, payload.ids, payload.note)}


@router.patch("/tasks/{task_id}", response_model=schemas.TaskOut)
async def update_task(
    task_id: uuid.UUID,
    payload: schemas.TaskUpdate,
    db: AsyncSession = Depends(get_db_session),
    ctx: RequestContext = Depends(require_writer),
):
    task = await service.update_task(db, ctx, task_id, payload.model_dump(exclude_unset=True))
    return (await service.tasks_out(db, ctx.organization_id, [task]))[0]


@router.delete("/tasks/{task_id}")
async def delete_task(
    task_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
    ctx: RequestContext = Depends(require_writer),
):
    await service.delete_task(db, ctx, task_id)
    return {"status": "deleted"}
