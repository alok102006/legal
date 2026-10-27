"""Org-scoped data access for contracts. Every read/write takes the organisation id."""
import uuid
from typing import Dict, List, Optional

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.shared.db.models import Document
from app.workspaces.contract_intelligence.models import ChatMessage, Contract, Finding, Segment


async def get_contract(session: AsyncSession, org_id: uuid.UUID, contract_id: uuid.UUID, *, full: bool = False) -> Optional[Contract]:
    stmt = select(Contract).where(Contract.id == contract_id, Contract.organization_id == org_id)
    if full:
        stmt = stmt.options(selectinload(Contract.findings), selectinload(Contract.segments), selectinload(Contract.document))
    else:
        stmt = stmt.options(selectinload(Contract.document))
    return (await session.execute(stmt)).scalar_one_or_none()


async def list_contracts(session: AsyncSession, org_id: uuid.UUID) -> List[dict]:
    """Contracts of the organisation with per-severity finding counts (only evidence-backed findings)."""
    counts_stmt = (
        select(Finding.contract_id, Finding.severity, func.count(Finding.id))
        .join(Contract, Contract.id == Finding.contract_id)
        .where(Contract.organization_id == org_id, Finding.counts_toward_score.is_(True), Finding.status != "dismissed")
        .group_by(Finding.contract_id, Finding.severity)
    )
    counts: Dict[uuid.UUID, Dict[str, int]] = {}
    for cid, sev, n in (await session.execute(counts_stmt)).all():
        counts.setdefault(cid, {})[sev] = n

    stmt = (
        select(Contract, Document.original_filename)
        .join(Document, Document.id == Contract.document_id)
        .where(Contract.organization_id == org_id)
        .order_by(Contract.created_at.desc())
    )
    rows = []
    for c, filename in (await session.execute(stmt)).all():
        rows.append({
            "id": c.id, "title": c.title, "counterparty_name": c.counterparty_name,
            "contract_type": c.contract_type, "status": c.status, "stage": c.stage,
            "risk_level": c.risk_level, "overall_score": c.overall_score,
            "finding_counts": counts.get(c.id, {}), "error_kind": c.error_kind,
            "error_message": c.error_message, "filename": filename,
            "created_at": c.created_at, "analyzed_at": c.analyzed_at,
        })
    return rows


async def create_document(
    session: AsyncSession, org_id: uuid.UUID, original_filename: str, storage_path: str,
    uploaded_by: Optional[uuid.UUID],
) -> Document:
    doc = Document(workspace="contract_intelligence", original_filename=original_filename,
                   storage_path=storage_path, uploaded_by=uploaded_by, organization_id=org_id)
    session.add(doc)
    await session.flush()
    return doc


async def create_contract(
    session: AsyncSession, org_id: uuid.UUID, document_id: uuid.UUID, title: str, client_party: Optional[str],
) -> Contract:
    contract = Contract(document_id=document_id, organization_id=org_id, title=title,
                        counterparty_name=None, status="processing", stage="queued", client_party=client_party)
    session.add(contract)
    await session.flush()
    return contract


async def clear_analysis(session: AsyncSession, contract_id: uuid.UUID) -> None:
    """Removes previous engine output (used for retry / re-analysis)."""
    await session.execute(delete(Finding).where(Finding.contract_id == contract_id))
    await session.execute(delete(Segment).where(Segment.contract_id == contract_id))
    await session.flush()


async def recent_messages(session: AsyncSession, contract_id: uuid.UUID, limit: int = 6) -> List[ChatMessage]:
    stmt = (select(ChatMessage).where(ChatMessage.contract_id == contract_id)
            .order_by(ChatMessage.created_at.desc()).limit(limit))
    rows = list((await session.execute(stmt)).scalars().all())
    rows.reverse()
    return rows


async def all_messages(session: AsyncSession, contract_id: uuid.UUID) -> List[ChatMessage]:
    stmt = select(ChatMessage).where(ChatMessage.contract_id == contract_id).order_by(ChatMessage.created_at)
    return list((await session.execute(stmt)).scalars().all())
