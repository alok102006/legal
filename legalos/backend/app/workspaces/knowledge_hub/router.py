import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, status, HTTPException, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db_session, get_current_user
from app.shared.auth.auth_service import UserStub
from app.workspaces.knowledge_hub import service
from app.workspaces.knowledge_hub.schemas import (
    CompanyRegisterRequest,
    RegisteredCompanyResponse,
    CompanyProfilePreview,
    CompanyDocumentResponse,
    DocumentUploadRequest,
    KnowledgeAskRequest,
    KnowledgeAskResponse,
    GroundTruthExcerpt
)

router = APIRouter()


@router.post("/companies/preview", response_model=CompanyProfilePreview)
async def preview_company(
    req: CompanyRegisterRequest
):
    """
    Previews live taxpayer profiling metadata from Sandbox API without storing in database.
    """
    profile = await service.preview_company_profile(req.gstin)
    return CompanyProfilePreview(
        gstin=profile["gstin"],
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
        raw_response=profile.get("raw_response")
    )


@router.post("/companies", response_model=RegisteredCompanyResponse, status_code=status.HTTP_201_CREATED)
async def register_company(
    req: CompanyRegisterRequest,
    session: AsyncSession = Depends(get_db_session),
    current_user: UserStub = Depends(get_current_user)
):
    """
    Registers a company using 15-character GSTIN, profiles via Sandbox API, and persists in PostgreSQL.
    """
    company = await service.register_company_by_gstin(session, req.gstin, user_id=current_user.id)
    return company


@router.get("/companies", response_model=List[RegisteredCompanyResponse])
async def list_companies(
    session: AsyncSession = Depends(get_db_session)
):
    """
    Lists all companies registered in Knowledge Hub.
    """
    return await service.list_registered_companies(session)


@router.get("/companies/{company_id}", response_model=RegisteredCompanyResponse)
async def get_company(
    company_id: uuid.UUID,
    session: AsyncSession = Depends(get_db_session)
):
    """
    Gets detailed corporate profile for a registered company.
    """
    return await service.get_registered_company(session, company_id)


@router.delete("/companies/{company_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_company(
    company_id: uuid.UUID,
    session: AsyncSession = Depends(get_db_session)
):
    """
    Unregisters / deletes a company from Knowledge Hub.
    """
    await service.delete_registered_company(session, company_id)
    return None


@router.post("/documents/upload", response_model=CompanyDocumentResponse, status_code=status.HTTP_201_CREATED)
async def upload_company_document_file(
    company_id: uuid.UUID = Form(...),
    title: Optional[str] = Form(None),
    document_category: str = Form("Policy"),
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_db_session)
):
    """
    Uploads a document file (.pdf, .docx, .csv, .xlsx, .txt, .md), parses text content,
    indexes into Qdrant vector database for RAG Ground Truth, and saves to PostgreSQL.
    """
    file_bytes = await file.read()
    filename = file.filename or "uploaded_doc.pdf"
    
    doc = await service.upload_and_process_company_document(
        session=session,
        company_id=company_id,
        filename=filename,
        file_bytes=file_bytes,
        title=title,
        document_category=document_category
    )
    return doc


@router.delete("/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: uuid.UUID,
    session: AsyncSession = Depends(get_db_session)
):
    """
    Deletes a company document completely from PostgreSQL, disk storage, and Qdrant.
    """
    await service.delete_company_document_by_id(session, document_id)
    return None



@router.post("/ask", response_model=KnowledgeAskResponse)
async def ask_knowledge(
    req: KnowledgeAskRequest,
    session: AsyncSession = Depends(get_db_session)
):
    """
    AI Assistant Q&A using uploaded PDF, Word, CSV, Excel files as STRICT GROUND TRUTH.
    """
    res = await service.ask_company_knowledge(
        session=session,
        question=req.question,
        company_id=req.company_id,
        document_id=req.document_id
    )
    return KnowledgeAskResponse(
        answer=res["answer"],
        company_context=res.get("company_context"),
        sources=res.get("sources", []),
        ground_truth_excerpts=[
            GroundTruthExcerpt(**item) for item in res.get("ground_truth_excerpts", [])
        ]
    )
