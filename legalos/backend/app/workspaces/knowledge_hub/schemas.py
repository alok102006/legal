import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class CompanyRegisterRequest(BaseModel):
    gstin: str = Field(..., description="15-character GSTIN identifier", min_length=15, max_length=15)


class CompanyDocumentResponse(BaseModel):
    id: uuid.UUID
    company_id: uuid.UUID
    document_id: Optional[uuid.UUID] = None
    title: str
    document_category: str
    summary: Optional[str] = None
    file_name: Optional[str] = None
    file_type: Optional[str] = None
    file_path: Optional[str] = None
    extracted_text: Optional[str] = None
    risk_analysis: Optional[Dict[str, Any]] = None  # AI Risk Radar output
    created_at: datetime

    class Config:
        from_attributes = True


class RegisteredCompanyResponse(BaseModel):
    id: uuid.UUID
    gstin: str
    legal_name: str
    trade_name: Optional[str] = None
    entity_type: Optional[str] = None
    registration_date: Optional[str] = None
    taxpayer_type: Optional[str] = None
    status: str
    state_jurisdiction: Optional[str] = None
    center_jurisdiction: Optional[str] = None
    principal_address: Optional[Dict[str, Any]] = None
    nature_of_business: Optional[List[str]] = None
    registered_by: Optional[uuid.UUID] = None
    created_at: datetime
    updated_at: datetime
    documents: List[CompanyDocumentResponse] = []

    class Config:
        from_attributes = True


class CompanyProfilePreview(BaseModel):
    gstin: str
    legal_name: str
    trade_name: Optional[str] = None
    entity_type: Optional[str] = None
    registration_date: Optional[str] = None
    taxpayer_type: Optional[str] = None
    status: str
    state_jurisdiction: Optional[str] = None
    center_jurisdiction: Optional[str] = None
    principal_address: Optional[Dict[str, Any]] = None
    nature_of_business: Optional[List[str]] = None
    raw_response: Optional[Dict[str, Any]] = None


class DocumentUploadRequest(BaseModel):
    company_id: uuid.UUID
    title: str
    document_category: str = "Policy"
    summary: Optional[str] = None


class GroundTruthExcerpt(BaseModel):
    document_title: str
    file_name: Optional[str] = None
    excerpt: str


class KnowledgeAskRequest(BaseModel):
    question: str = Field(..., min_length=2)
    company_id: Optional[uuid.UUID] = None
    document_id: Optional[uuid.UUID] = None


class KnowledgeAskResponse(BaseModel):
    answer: str
    company_context: Optional[str] = None
    sources: List[str] = []
    ground_truth_excerpts: List[GroundTruthExcerpt] = []
