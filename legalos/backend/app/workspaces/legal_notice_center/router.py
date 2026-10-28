import uuid
from datetime import date
from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import RequestContext, get_ctx, require_writer
from app.shared.db.session import get_db_session
from app.workspaces.legal_notice_center import schemas, service

router = APIRouter()


def _item(case):
    return service.to_list_item(case)


@router.get("", response_model=List[schemas.CaseListItem])
async def list_notices(db: AsyncSession = Depends(get_db_session), ctx: RequestContext = Depends(get_ctx)):
    return await service.list_cases(db, ctx)


@router.post("/upload", response_model=schemas.CaseListItem, status_code=202)
async def upload_notice(
    background_tasks: BackgroundTasks,
    file: Optional[UploadFile] = File(None),
    files: List[UploadFile] = File([], description="Several page photos of one notice, in page order."),
    received_date: Optional[date] = Form(None),
    db: AsyncSession = Depends(get_db_session),
    ctx: RequestContext = Depends(require_writer),
):
    uploads = ([file] if file else []) + list(files)
    payload = [(await u.read(), u.filename or "notice.txt") for u in uploads]
    case = await service.create_from_files(db, ctx, payload, received_date)
    background_tasks.add_task(service.run_analysis, case.id)
    return _item(case)


@router.post("/text", response_model=schemas.CaseListItem, status_code=202)
async def paste_notice(
    body: schemas.TextIn,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db_session),
    ctx: RequestContext = Depends(require_writer),
):
    case = await service.create_from_text(db, ctx, body.text, body.title, body.received_date)
    background_tasks.add_task(service.run_analysis, case.id)
    return _item(case)


@router.get("/{case_id}", response_model=schemas.CaseDetail)
async def get_notice(case_id: uuid.UUID, db: AsyncSession = Depends(get_db_session), ctx: RequestContext = Depends(get_ctx)):
    return await service.get_detail(db, ctx, case_id)


@router.post("/{case_id}/retry", response_model=schemas.CaseListItem, status_code=202)
async def retry_notice(case_id: uuid.UUID, background_tasks: BackgroundTasks, db: AsyncSession = Depends(get_db_session),
                       ctx: RequestContext = Depends(require_writer)):
    case = await service.prepare_retry(db, ctx, case_id)
    background_tasks.add_task(service.run_analysis, case.id)
    return _item(case)


@router.patch("/{case_id}", response_model=schemas.CaseDetail)
async def update_notice(case_id: uuid.UUID, body: schemas.CaseUpdate, db: AsyncSession = Depends(get_db_session),
                        ctx: RequestContext = Depends(require_writer)):
    return service.to_detail(await service.update_case(db, ctx, case_id, body.model_dump(exclude_unset=True)))


@router.post("/{case_id}/draft", response_model=schemas.CaseDetail)
async def regenerate_draft(case_id: uuid.UUID, body: schemas.RegenerateIn, db: AsyncSession = Depends(get_db_session),
                           ctx: RequestContext = Depends(require_writer)):
    return service.to_detail(await service.regenerate_draft(db, ctx, case_id, body.instructions))


@router.put("/{case_id}/draft", response_model=schemas.CaseDetail)
async def save_draft(case_id: uuid.UUID, body: schemas.SaveDraftIn, db: AsyncSession = Depends(get_db_session),
                     ctx: RequestContext = Depends(require_writer)):
    return service.to_detail(await service.save_user_draft(db, ctx, case_id, body.reply_text))


@router.delete("/{case_id}")
async def delete_notice(case_id: uuid.UUID, db: AsyncSession = Depends(get_db_session), ctx: RequestContext = Depends(require_writer)):
    await service.delete_case(db, ctx, case_id)
    return {"status": "deleted"}
