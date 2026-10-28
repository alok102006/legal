import uuid
from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, Request, UploadFile
from fastapi.responses import FileResponse
from starlette.datastructures import UploadFile as StarletteUpload
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import RequestContext, get_ctx, require_writer
from app.shared.db.session import get_db_session
from app.shared.exceptions import BadRequestException
from app.workspaces.contract_intelligence import schemas, service

router = APIRouter()


@router.post("/upload", response_model=schemas.ContractListItem, status_code=202)
async def upload_contract(
    request: Request,
    background_tasks: BackgroundTasks,
    file: Optional[UploadFile] = File(None),
    client_party: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db_session),
    ctx: RequestContext = Depends(require_writer),
):
    """Validates and stores the file, then analyses it in the background (poll GET /{id}).

    Send one document as `file`, or several photos of one contract's pages as repeated `files` parts (in page
    order); the photos are combined into one PDF and read page by page. (`files` is read from the form directly:
    FastAPI 0.110 rejects an optional list of uploads.)"""
    extra = [u for u in (await request.form()).getlist("files") if isinstance(u, StarletteUpload)]
    uploads = [(u.filename or "contract.txt", await u.read()) for u in ([file] if file else []) + extra]
    if not uploads:
        raise BadRequestException("Please choose a file to upload.")
    name, data = uploads[0] if len(uploads) == 1 else await service.combine_photos(uploads)
    contract = await service.create_upload(db, ctx, data, name, client_party)
    background_tasks.add_task(service.run_analysis, contract.id)
    return {
        "id": contract.id, "title": contract.title, "status": contract.status, "stage": contract.stage,
        "filename": name, "created_at": contract.created_at, "finding_counts": {},
    }


@router.get("", response_model=List[schemas.ContractListItem])
async def list_contracts(db: AsyncSession = Depends(get_db_session), ctx: RequestContext = Depends(get_ctx)):
    return await service.list_contracts(db, ctx)


@router.get("/{contract_id}", response_model=schemas.ContractDetail)
async def get_contract(contract_id: uuid.UUID, db: AsyncSession = Depends(get_db_session),
                       ctx: RequestContext = Depends(get_ctx)):
    return await service.get_detail(db, ctx, contract_id)


@router.post("/{contract_id}/retry", response_model=schemas.ContractListItem, status_code=202)
async def retry_analysis(contract_id: uuid.UUID, background_tasks: BackgroundTasks,
                         db: AsyncSession = Depends(get_db_session), ctx: RequestContext = Depends(require_writer)):
    c = await service.prepare_retry(db, ctx, contract_id)
    background_tasks.add_task(service.run_analysis, c.id)
    return {"id": c.id, "title": c.title, "status": c.status, "stage": c.stage,
            "created_at": c.created_at, "finding_counts": {}}


@router.get("/{contract_id}/messages", response_model=List[schemas.ChatMessageOut])
async def list_messages(contract_id: uuid.UUID, db: AsyncSession = Depends(get_db_session),
                        ctx: RequestContext = Depends(get_ctx)):
    return await service.list_messages(db, ctx, contract_id)


@router.post("/{contract_id}/chat", response_model=schemas.ChatMessageOut)
async def chat(contract_id: uuid.UUID, body: schemas.ChatIn, db: AsyncSession = Depends(get_db_session),
               ctx: RequestContext = Depends(require_writer)):
    """Ask a question about this contract; answers are limited to the contract text and cited."""
    return await service.ask(db, ctx, contract_id, body.question)


@router.patch("/{contract_id}/findings/{finding_id}", response_model=schemas.FindingOut)
async def update_finding(contract_id: uuid.UUID, finding_id: uuid.UUID, body: schemas.FindingStatusIn,
                         db: AsyncSession = Depends(get_db_session), ctx: RequestContext = Depends(require_writer)):
    return await service.set_finding_status(db, ctx, contract_id, finding_id, body.status)


@router.get("/{contract_id}/file")
async def download_file(contract_id: uuid.UUID, db: AsyncSession = Depends(get_db_session),
                        ctx: RequestContext = Depends(get_ctx)):
    path, name = await service.get_file_path(db, ctx, contract_id)
    return FileResponse(path, filename=name)


@router.delete("/{contract_id}")
async def delete_contract(contract_id: uuid.UUID, db: AsyncSession = Depends(get_db_session),
                          ctx: RequestContext = Depends(require_writer)):
    await service.delete_contract(db, ctx, contract_id)
    return {"status": "deleted"}
