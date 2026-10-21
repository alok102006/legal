import uuid
from typing import List, Optional, Dict, Any
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.workspaces.knowledge_hub.models import RegisteredCompany, CompanyDocument


async def get_company_by_gstin(
    session: AsyncSession,
    gstin: str
) -> Optional[RegisteredCompany]:
    """Retrieve company by GSTIN with documents preloaded."""
    stmt = (
        select(RegisteredCompany)
        .options(selectinload(RegisteredCompany.documents))
        .where(RegisteredCompany.gstin == gstin.upper().strip())
    )
    res = await session.execute(stmt)
    return res.scalar_one_or_none()


async def get_company_by_id(
    session: AsyncSession,
    company_id: uuid.UUID
) -> Optional[RegisteredCompany]:
    """Retrieve company by UUID with documents preloaded."""
    stmt = (
        select(RegisteredCompany)
        .options(selectinload(RegisteredCompany.documents))
        .where(RegisteredCompany.id == company_id)
    )
    res = await session.execute(stmt)
    return res.scalar_one_or_none()


async def list_companies(
    session: AsyncSession
) -> List[RegisteredCompany]:
    """List all registered companies ordered by creation date."""
    stmt = (
        select(RegisteredCompany)
        .options(selectinload(RegisteredCompany.documents))
        .order_by(RegisteredCompany.created_at.desc())
    )
    res = await session.execute(stmt)
    return list(res.scalars().all())


async def upsert_company(
    session: AsyncSession,
    profile: Dict[str, Any],
    user_id: Optional[uuid.UUID] = None
) -> RegisteredCompany:
    """Create or update registered company from parsed Sandbox profile."""
    gstin = profile["gstin"].upper().strip()
    existing = await get_company_by_gstin(session, gstin)

    if existing:
        existing.legal_name = profile["legal_name"]
        existing.trade_name = profile.get("trade_name")
        existing.entity_type = profile.get("entity_type")
        existing.registration_date = profile.get("registration_date")
        existing.taxpayer_type = profile.get("taxpayer_type")
        existing.status = profile.get("status", "Active")
        existing.state_jurisdiction = profile.get("state_jurisdiction")
        existing.center_jurisdiction = profile.get("center_jurisdiction")
        existing.principal_address = profile.get("principal_address")
        existing.nature_of_business = profile.get("nature_of_business")
        existing.raw_profile_response = profile.get("raw_response")
        company = existing
    else:
        company = RegisteredCompany(
            gstin=gstin,
            legal_name=profile["legal_name"],
            trade_name=profile.get("trade_name"),
            entity_type=profile.get("entity_type"),
            registration_date=profile.get("registration_date"),
            taxpayer_type=profile.get("taxpayer_type"),
            status=profile.get("status", "Active"),
            state_jurisdiction=profile.get("state_jurisdiction"),
            center_jurisdiction=profile.get("center_jurisdiction"),
            principal_address=profile.get("principal_address"),
            nature_of_business=profile.get("nature_of_business"),
            raw_profile_response=profile.get("raw_response"),
            registered_by=user_id
        )
        session.add(company)

    await session.commit()
    return await get_company_by_id(session, company.id)


async def delete_company(
    session: AsyncSession,
    company_id: uuid.UUID
) -> bool:
    """Delete a registered company by UUID."""
    company = await get_company_by_id(session, company_id)
    if not company:
        return False

    await session.delete(company)
    await session.commit()
    return True


async def get_company_document(
    session: AsyncSession,
    document_id: uuid.UUID
) -> Optional[CompanyDocument]:
    """Retrieve specific company document by ID."""
    stmt = select(CompanyDocument).where(CompanyDocument.id == document_id)
    res = await session.execute(stmt)
    return res.scalar_one_or_none()


async def create_company_document(
    session: AsyncSession,
    company_id: uuid.UUID,
    title: str,
    document_category: str = "Policy",
    summary: Optional[str] = None,
    file_name: Optional[str] = None,
    file_type: Optional[str] = None,
    file_path: Optional[str] = None,
    extracted_text: Optional[str] = None,
    document_id: Optional[uuid.UUID] = None
) -> CompanyDocument:
    """Add a corporate knowledge document to a company."""
    doc = CompanyDocument(
        company_id=company_id,
        document_id=document_id,
        title=title,
        document_category=document_category,
        summary=summary,
        file_name=file_name,
        file_type=file_type,
        file_path=file_path,
        extracted_text=extracted_text
    )
    session.add(doc)
    await session.commit()
    await session.refresh(doc)
    return doc


async def delete_company_document(
    session: AsyncSession,
    document_id: uuid.UUID
) -> bool:
    """Delete a company document from PostgreSQL."""
    doc = await get_company_document(session, document_id)
    if not doc:
        return False

    await session.delete(doc)
    await session.commit()
    return True


async def update_document_risk_analysis(
    session: AsyncSession,
    document_id: uuid.UUID,
    risk_data: dict
) -> None:
    """Persist AI risk analysis JSON to the company document record."""
    doc = await get_company_document(session, document_id)
    if doc:
        doc.risk_analysis = risk_data
        await session.commit()
