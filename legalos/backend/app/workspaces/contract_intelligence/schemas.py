import uuid
from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, field_validator


class FindingOut(BaseModel):
    id: uuid.UUID
    source: str                      # ai | rule | missing
    category: str
    severity: str
    title: str
    why_it_matters: str
    recommendation: Optional[str] = None
    suggested_wording: Optional[str] = None
    quote: Optional[str] = None
    segment_id: Optional[str] = None
    page: Optional[int] = None
    verified: bool = False
    counts_toward_score: bool = False
    rule_id: Optional[str] = None
    legal_note: Optional[str] = None
    legal_ref: Optional[str] = None
    condition_note: Optional[str] = None
    status: str = "open"

    model_config = {"from_attributes": True}


class SegmentOut(BaseModel):
    seg_id: str
    number: Optional[str] = None
    heading: str
    text: str
    page_start: Optional[int] = None
    page_end: Optional[int] = None

    model_config = {"from_attributes": True}


class FindingCounts(BaseModel):
    critical: int = 0
    high: int = 0
    medium: int = 0
    low: int = 0


class ContractListItem(BaseModel):
    id: uuid.UUID
    title: Optional[str] = None
    counterparty_name: Optional[str] = None
    contract_type: Optional[str] = None
    status: str                       # queued | processing | analyzed | failed
    stage: Optional[str] = None
    risk_level: Optional[str] = None
    overall_score: Optional[int] = None
    finding_counts: FindingCounts = FindingCounts()
    error_kind: Optional[str] = None
    error_message: Optional[str] = None
    filename: Optional[str] = None
    created_at: datetime
    analyzed_at: Optional[datetime] = None


class ContractDetail(ContractListItem):
    contract_type_label: Optional[str] = None     # e.g. "Dealership agreement"; covers types the UI has no label for
    summary_points: List[str] = []
    facts: Optional[Dict[str, Any]] = None
    score_breakdown: Optional[Dict[str, Any]] = None
    warnings: List[str] = []
    page_count: Optional[int] = None
    has_pages: bool = False
    ocr_used: bool = False
    prompt_version: Optional[str] = None
    rules_version: Optional[str] = None
    findings: List[FindingOut] = []
    segments: List[SegmentOut] = []


class ChatIn(BaseModel):
    question: str = Field(min_length=3, max_length=1000)


class CitationOut(BaseModel):
    quote: str
    segment_id: Optional[str] = None
    page: Optional[int] = None
    verified: bool = False
    finding: Optional[str] = None        # title of the review finding this quote backs (negotiation answers)
    legal_ref: Optional[str] = None


class ChatMessageOut(BaseModel):
    id: uuid.UUID
    role: str
    content: str
    citations: List[CitationOut] = Field(default_factory=list)
    found_in_contract: Optional[bool] = None
    created_at: datetime

    model_config = {"from_attributes": True}

    @field_validator("citations", mode="before")
    @classmethod
    def _none_to_empty(cls, v):
        return v or []


class FindingStatusIn(BaseModel):
    status: Literal["open", "resolved", "dismissed"]
