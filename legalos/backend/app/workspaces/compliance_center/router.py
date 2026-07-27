import uuid
from typing import List
from fastapi import APIRouter, Depends, UploadFile, File, BackgroundTasks, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db_session, get_current_user
from app.shared.auth.auth_service import UserStub
from app.shared.exceptions import BadRequestException, NotFoundException
from app.workspaces.compliance_center import service, schemas

router = APIRouter()

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB limit
ALLOWED_EXTENSIONS = {"pdf", "docx", "txt", "md"}


@router.get("/tasks", response_model=List[schemas.ComplianceTaskResponse])
async def get_tasks(
    db: AsyncSession = Depends(get_db_session),
    current_user: UserStub = Depends(get_current_user)
):
    """
    Retrieves all compliance tasks for the current user.
    """
    return await service.list_compliance_tasks(db, current_user.id)


@router.post("/tasks", response_model=schemas.ComplianceTaskResponse)
async def create_task(
    payload: schemas.ComplianceTaskCreate,
    db: AsyncSession = Depends(get_db_session),
    current_user: UserStub = Depends(get_current_user)
):
    """
    Creates a new custom compliance task.
    """
    task = await service.create_compliance_task(db, payload, current_user.id)
    await db.commit()
    return task


@router.put("/tasks/{task_id}", response_model=schemas.ComplianceTaskResponse)
async def update_task(
    task_id: uuid.UUID,
    payload: schemas.ComplianceTaskUpdate,
    db: AsyncSession = Depends(get_db_session),
    current_user: UserStub = Depends(get_current_user)
):
    """
    Updates details of an existing compliance task (e.g. status).
    """
    task = await service.update_compliance_task(db, task_id, payload.model_dump(exclude_unset=True))
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    await db.commit()
    return task


@router.delete("/tasks/{task_id}")
async def delete_task(
    task_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
    current_user: UserStub = Depends(get_current_user)
):
    """
    Deletes a compliance task.
    """
    success = await service.delete_compliance_task(db, task_id)
    if not success:
        raise HTTPException(status_code=404, detail="Task not found")
    await db.commit()
    return {"status": "success", "message": "Task deleted successfully"}


@router.post("/init", response_model=List[schemas.ComplianceTaskResponse])
async def init_statutory_tasks(
    payload: schemas.BusinessTypeInit,
    db: AsyncSession = Depends(get_db_session),
    current_user: UserStub = Depends(get_current_user)
):
    """
    Generates standard statutory compliance checklist tasks for the current user
    based on the business entity type.
    """
    tasks = await service.initialize_statutory_tasks(db, payload.business_type, current_user.id)
    await db.commit()
    return tasks


@router.post("/upload", response_model=schemas.ComplianceDocumentAnalysisResponse)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db_session),
    current_user: UserStub = Depends(get_current_user)
):
    """
    Uploads a compliance document (e.g., GST registration, FSSAI certificate, tax notice)
    and runs asynchronous background analysis.
    """
    file_bytes = await file.read()
    if len(file_bytes) > MAX_FILE_SIZE:
        raise BadRequestException("File size exceeds the 10MB maximum limit.")
        
    filename = file.filename or "compliance_document.txt"
    if "." not in filename:
        raise BadRequestException("Missing file extension. Supported formats: PDF, DOCX, TXT, MD.")
        
    ext = filename.lower().split(".")[-1]
    if ext not in ALLOWED_EXTENSIONS:
        raise BadRequestException(f"Unsupported file format '{ext}'.")
        
    # 1. Create document stub and analysis record in DB
    analysis = await service.upload_and_start_analysis(
        session=db,
        file_bytes=file_bytes,
        filename=filename,
        user_id=current_user.id
    )
    
    # 2. Trigger async analysis background task
    background_tasks.add_task(
        service.run_async_compliance_analysis,
        analysis_id=analysis.id,
        file_bytes=file_bytes,
        filename=filename,
        document_id=analysis.document_id,
        user_id=current_user.id
    )
    
    return analysis


@router.get("/analyses", response_model=List[schemas.ComplianceDocumentAnalysisResponse])
async def list_analyses(
    db: AsyncSession = Depends(get_db_session),
    current_user: UserStub = Depends(get_current_user)
):
    """
    Retrieves all compliance document analyses history.
    """
    return await service.list_document_analyses(db)


@router.get("/analyses/{id}", response_model=schemas.ComplianceDocumentAnalysisResponse)
async def get_analysis(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
    current_user: UserStub = Depends(get_current_user)
):
    """
    Retrieves details of a single compliance document analysis report.
    """
    analysis = await service.get_document_analysis(db, id)
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis report not found.")
    return analysis


@router.post("/init-by-gstin", response_model=schemas.ComplianceInitResponse)
async def init_by_gstin(
    payload: schemas.GSTINInit,
    db: AsyncSession = Depends(get_db_session),
    current_user: UserStub = Depends(get_current_user)
):
    """
    Retrieves company constitution from the GSTIN registry and automatically
    populates the compliance task list based on that business type.
    """
    try:
        result = await service.initialize_statutory_tasks_by_gstin(db, payload.gstin, current_user.id)
        await db.commit()
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

