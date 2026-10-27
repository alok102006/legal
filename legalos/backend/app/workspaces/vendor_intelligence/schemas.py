import uuid
from datetime import date, datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class VendorIn(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    gstin: Optional[str] = Field(default=None, max_length=20)
    pan: Optional[str] = Field(default=None, max_length=12)
    state_code: Optional[str] = Field(default=None, max_length=2)
    udyam_number: Optional[str] = Field(default=None, max_length=40)
    msme_category: Optional[Literal["micro", "small", "medium", "none", "unknown"]] = None
    notes: Optional[str] = Field(default=None, max_length=1000)


class VendorUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=2, max_length=200)
    gstin: Optional[str] = Field(default=None, max_length=20)
    pan: Optional[str] = Field(default=None, max_length=12)
    state_code: Optional[str] = Field(default=None, max_length=2)
    udyam_number: Optional[str] = Field(default=None, max_length=40)
    msme_category: Optional[Literal["micro", "small", "medium", "none", "unknown"]] = None
    notes: Optional[str] = Field(default=None, max_length=1000)


class CheckOut(BaseModel):
    key: str
    label: str
    status: str
    detail: str


class VendorBrief(BaseModel):
    id: uuid.UUID
    name: str
    gstin: Optional[str] = None
    pan: Optional[str] = None
    udyam_number: Optional[str] = None
    state_name: Optional[str] = None
    msme_category: Optional[str] = None
    risk_level: str
    summary: Optional[str] = None
    registry_source: Optional[str] = None
    last_checked_at: Optional[datetime] = None
    created_at: datetime


class LinkedContract(BaseModel):
    id: uuid.UUID
    title: Optional[str] = None
    status: str
    risk_level: Optional[str] = None
    overall_score: Optional[int] = None


class LinkedNotice(BaseModel):
    id: uuid.UUID
    title: Optional[str] = None
    status: str
    urgency: Optional[str] = None
    response_deadline: Optional[date] = None


class HistoryEntry(BaseModel):
    at: datetime
    risk_level: str
    registry_source: Optional[str] = None
    registry_status: Optional[str] = None
    summary: Optional[str] = None


class VendorDetail(VendorBrief):
    kind: str = "gstin"
    pan: Optional[str] = None
    state_code: Optional[str] = None
    udyam_number: Optional[str] = None
    notes: Optional[str] = None
    reasons: List[str] = []
    checks: List[CheckOut] = []
    registry: Optional[Dict[str, Any]] = None
    registry_mode: str = "offline"            # live | sample | offline
    registry_provider: Optional[str] = None
    history: List[HistoryEntry] = []
    contracts: List[LinkedContract] = []
    notices: List[LinkedNotice] = []


class QuickCheckIn(BaseModel):
    name: str = Field(default="", max_length=200)
    gstin: Optional[str] = Field(default=None, max_length=20)
    pan: Optional[str] = Field(default=None, max_length=12)
    state_code: Optional[str] = Field(default=None, max_length=2)


class QuickCheckOut(BaseModel):
    risk_level: str
    summary: str
    checks: List[CheckOut]
    registry: Optional[Dict[str, Any]] = None
    registry_source: Optional[str] = None


class CheckIn(BaseModel):
    """The check desk: one number (GSTIN, PAN or Udyam). Name is optional and only used for the name-vs-registry check."""
    identifier: str = Field(min_length=1, max_length=40)
    name: Optional[str] = Field(default=None, max_length=200)
    state_code: Optional[str] = Field(default=None, max_length=2)


class CheckResult(BaseModel):
    kind: Literal["gstin", "pan", "udyam"]
    identifier: str
    suggested_name: Optional[str] = None      # the registry's legal name, when we got one
    risk_level: str                           # high | medium | low | unverified
    summary: str
    reasons: List[str] = []
    checks: List[CheckOut] = []
    registry: Optional[Dict[str, Any]] = None
    registry_source: Optional[str] = None     # live | sample | unavailable
    registry_mode: str = "offline"            # live | sample | offline
    registry_provider: Optional[str] = None
    state_name: Optional[str] = None
    pan: Optional[str] = None
    holder_type: Optional[str] = None
    saved_vendor: Optional[VendorBrief] = None
    contracts: List[LinkedContract] = []
    notices: List[LinkedNotice] = []
    checked_at: datetime


class SampleOut(BaseModel):
    gstin: str
    name: str
    label: str
