import uuid
from typing import List
from pydantic import BaseModel
from fastapi import APIRouter, Depends, UploadFile, File, BackgroundTasks, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db_session, get_current_user
from app.shared.auth.auth_service import UserStub
from app.shared.exceptions import BadRequestException
from app.workspaces.legal_notice_center import service, schemas

router = APIRouter()

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB limit
ALLOWED_EXTENSIONS = {"pdf", "docx", "txt", "md"}


class PasteTextRequest(BaseModel):
    title: str
    text: str


@router.post("/analyze/file", response_model=schemas.NoticeSummarySchema)
async def analyze_notice_file(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db_session),
    current_user: UserStub = Depends(get_current_user)
):
    """
    Upload notice file (PDF, DOCX, TXT, MD) and schedule background analysis.
    """
    file_bytes = await file.read()
    if len(file_bytes) > MAX_FILE_SIZE:
        raise BadRequestException(f"File size exceeds maximum allowed 10MB.")
        
    filename = file.filename or "notice.txt"
    if "." not in filename:
        raise BadRequestException("Missing file extension. Supported: PDF, DOCX, TXT.")
        
    ext = filename.lower().split(".")[-1]
    if ext not in ALLOWED_EXTENSIONS:
        raise BadRequestException(f"Unsupported file format '{ext}'.")
        
    # 1. Create document stub and notice in DB
    notice = await service.create_and_start_analysis(
        session=db,
        file_bytes=file_bytes,
        filename=filename,
        user_id=current_user.id
    )
    # Commit to get ID
    await db.commit()
    
    # 2. Trigger background analysis task
    background_tasks.add_task(
        service.run_async_notice_analysis,
        notice_id=notice.id,
        file_bytes=file_bytes,
        filename=filename,
        document_id=notice.document_id
    )
    
    return {
        "id": notice.id,
        "document_id": notice.document_id,
        "notice_type": notice.notice_type,
        "urgency": notice.urgency,
        "created_at": notice.created_at,
        "original_filename": filename
    }


@router.post("/analyze/text", response_model=schemas.NoticeSummarySchema)
async def analyze_notice_text(
    background_tasks: BackgroundTasks,
    payload: PasteTextRequest,
    db: AsyncSession = Depends(get_db_session),
    current_user: UserStub = Depends(get_current_user)
):
    """
    Accepts pasted notice text, wraps it as virtual txt file, and schedules analysis.
    """
    if not payload.text.strip():
        raise BadRequestException("Notice text content cannot be empty.")
        
    filename = f"{payload.title.strip().replace(' ', '_') or 'pasted_notice'}.txt"
    file_bytes = payload.text.strip().encode("utf-8")
    
    # 1. Create document stub and notice in DB
    notice = await service.create_and_start_analysis(
        session=db,
        file_bytes=file_bytes,
        filename=filename,
        user_id=current_user.id
    )
    await db.commit()
    
    # 2. Trigger background analysis task
    background_tasks.add_task(
        service.run_async_notice_analysis,
        notice_id=notice.id,
        file_bytes=file_bytes,
        filename=filename,
        document_id=notice.document_id
    )
    
    return {
        "id": notice.id,
        "document_id": notice.document_id,
        "notice_type": notice.notice_type,
        "urgency": notice.urgency,
        "created_at": notice.created_at,
        "original_filename": filename
    }


@router.get("/", response_model=List[schemas.NoticeSummarySchema])
async def list_notices(
    db: AsyncSession = Depends(get_db_session),
    current_user: UserStub = Depends(get_current_user)
):
    """Retrieves notice summaries history."""
    return await service.list_notices(db)


@router.get("/{id}", response_model=schemas.NoticeDetailSchema)
async def get_notice(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
    current_user: UserStub = Depends(get_current_user)
):
    """Retrieves full notice profile with generated replies."""
    notice = await service.get_notice_details(db, id)
    if not notice:
        raise HTTPException(status_code=404, detail="Legal notice not found.")
    return notice


@router.post("/{id}/regenerate", response_model=schemas.DraftReplySchema)
async def regenerate_reply(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
    current_user: UserStub = Depends(get_current_user)
):
    """Triggers RAG retrieval and regenerates response letter for a notice."""
    draft = await service.regenerate_reply(db, id)
    await db.commit()
    return draft


@router.delete("/{id}", status_code=204)
async def delete_notice(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
    current_user: UserStub = Depends(get_current_user)
):
    """Deletes a legal notice, its draft replies, document file, and Qdrant vectors."""
    await service.delete_notice_and_document(db, id)
    await db.commit()
    return None

