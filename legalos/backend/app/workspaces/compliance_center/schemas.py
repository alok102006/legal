import uuid
from datetime import date, datetime
from pydantic import BaseModel, Field
from typing import List, Optional, Any


class ComplianceTaskResponse(BaseModel):
    id: uuid.UUID
    title: str
    category: str
    due_date: Optional[date] = None
    status: str
    description: Optional[str] = None
    penalty_desc: Optional[str] = None
    document_id: Optional[uuid.UUID] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ComplianceTaskCreate(BaseModel):
    title: str
    category: str = "other"  # 'tax', 'corporate', 'labor', 'license', 'other'
    due_date: Optional[date] = None
    description: Optional[str] = None
    penalty_desc: Optional[str] = None


class ComplianceTaskUpdate(BaseModel):
    title: Optional[str] = None
    category: Optional[str] = None
    due_date: Optional[date] = None
    status: Optional[str] = None  # 'pending', 'completed', 'overdue'
    description: Optional[str] = None
    penalty_desc: Optional[str] = None


class ComplianceDocumentAnalysisResponse(BaseModel):
    id: uuid.UUID
    document_id: uuid.UUID
    authority: str
    document_type: str
    identifier_number: Optional[str] = None
    issue_date: Optional[date] = None
    expiry_date: Optional[date] = None
    status: str
    risk_assessment: Optional[str] = None
    extracted_actions: Optional[List[Any]] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class BusinessTypeInit(BaseModel):
    business_type: str  # 'private_limited', 'partnership', 'sole_proprietorship', 'llp'


class GSTINInit(BaseModel):
    gstin: str = Field(..., min_length=15, max_length=15, description="15-character GSTIN")


class ComplianceInitResponse(BaseModel):
    company_name: str
    business_type: str
    gstin: str
    constitution: str
    tasks: List[ComplianceTaskResponse]

