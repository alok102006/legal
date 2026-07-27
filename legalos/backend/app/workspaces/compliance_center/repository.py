import uuid
from typing import List, Optional
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.shared.db.models import Document
from app.workspaces.compliance_center.models import ComplianceTask, ComplianceDocumentAnalysis


async def get_task_by_id(session: AsyncSession, task_id: uuid.UUID) -> Optional[ComplianceTask]:
    """Retrieves a compliance task by ID."""
    return await session.get(ComplianceTask, task_id)


async def list_tasks(
    session: AsyncSession,
    user_id: Optional[uuid.UUID] = None
) -> List[ComplianceTask]:
    """Lists compliance tasks, optionally filtered by user, ordered by due date ascending (closest deadline first)."""
    stmt = select(ComplianceTask)
    if user_id:
        stmt = stmt.where(ComplianceTask.user_id == user_id)
    stmt = stmt.order_by(ComplianceTask.due_date.asc().nullslast(), ComplianceTask.created_at.desc())
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def create_task(
    session: AsyncSession,
    title: str,
    category: str,
    due_date: Optional[any] = None,
    description: Optional[str] = None,
    penalty_desc: Optional[str] = None,
    document_id: Optional[uuid.UUID] = None,
    user_id: Optional[uuid.UUID] = None,
    status: str = "pending"
) -> ComplianceTask:
    """Inserts a new compliance task."""
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    task = ComplianceTask(
        title=title,
        category=category,
        due_date=due_date,
        status=status,
        description=description,
        penalty_desc=penalty_desc,
        document_id=document_id,
        user_id=user_id,
        created_at=now,
        updated_at=now
    )
    session.add(task)
    await session.flush()
    return task


async def update_task(
    session: AsyncSession,
    task_id: uuid.UUID,
    updates: dict
) -> Optional[ComplianceTask]:
    """Updates specific fields of a compliance task."""
    task = await session.get(ComplianceTask, task_id)
    if task:
        for key, val in updates.items():
            if hasattr(task, key) and val is not None:
                setattr(task, key, val)
        await session.flush()
    return task


async def delete_task(session: AsyncSession, task_id: uuid.UUID) -> bool:
    """Deletes a compliance task by ID."""
    task = await session.get(ComplianceTask, task_id)
    if task:
        await session.delete(task)
        await session.flush()
        return True
    return False


async def create_document(
    session: AsyncSession,
    workspace: str,
    original_filename: str,
    storage_path: str,
    uploaded_by: Optional[uuid.UUID] = None
) -> Document:
    """Inserts a core document record for tracking uploads."""
    doc = Document(
        workspace=workspace,
        original_filename=original_filename,
        storage_path=storage_path,
        uploaded_by=uploaded_by
    )
    session.add(doc)
    await session.flush()
    return doc


async def create_document_analysis(
    session: AsyncSession,
    document_id: uuid.UUID,
    authority: str = "Analyzing...",
    document_type: str = "Analyzing...",
    identifier_number: Optional[str] = None,
    issue_date: Optional[any] = None,
    expiry_date: Optional[any] = None,
    status: str = "warning",
    risk_assessment: Optional[str] = None,
    extracted_actions: Optional[list] = None
) -> ComplianceDocumentAnalysis:
    """Creates a new document analysis metadata entry."""
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    analysis = ComplianceDocumentAnalysis(
        document_id=document_id,
        authority=authority,
        document_type=document_type,
        identifier_number=identifier_number,
        issue_date=issue_date,
        expiry_date=expiry_date,
        status=status,
        risk_assessment=risk_assessment,
        extracted_actions=extracted_actions,
        created_at=now,
        updated_at=now
    )
    session.add(analysis)
    await session.flush()
    return analysis


async def list_document_analyses(
    session: AsyncSession
) -> List[ComplianceDocumentAnalysis]:
    """Lists all completed/in-progress compliance document analyses."""
    stmt = select(ComplianceDocumentAnalysis).order_by(ComplianceDocumentAnalysis.created_at.desc())
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_document_analysis_by_id(
    session: AsyncSession,
    analysis_id: uuid.UUID
) -> Optional[ComplianceDocumentAnalysis]:
    """Retrieves document analysis by analysis ID."""
    return await session.get(ComplianceDocumentAnalysis, analysis_id)


async def delete_all_tasks(
    session: AsyncSession,
    user_id: uuid.UUID
) -> None:
    """Removes all compliance tasks for a user (useful for re-initialization)."""
    stmt = delete(ComplianceTask).where(ComplianceTask.user_id == user_id)
    await session.execute(stmt)
    await session.flush()
