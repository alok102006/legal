import uuid
from datetime import date, datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, Field


class DraftOut(BaseModel):
    id: uuid.UUID
    version: int
    reply_text: str
    placeholders: List[str] = []
    points_to_confirm: List[str] = []
    documents_to_gather: List[str] = []
    author: str
    instructions: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class CaseListItem(BaseModel):
    id: uuid.UUID
    title: Optional[str] = None
    notice_type: Optional[str] = None
    type_label: Optional[str] = None
    urgency: Optional[str] = None
    status: str
    stage: Optional[str] = None
    issuer_name: Optional[str] = None
    amount_claimed: Optional[float] = None
    response_deadline: Optional[date] = None
    days_left: Optional[int] = None
    review_status: str = "draft"
    error_kind: Optional[str] = None
    error_message: Optional[str] = None
    source_name: Optional[str] = None
    created_at: datetime


class KeyQuote(BaseModel):
    kind: Literal["deadline", "amount", "demand"]
    text: str
    verified: bool = False


class CaseDetail(CaseListItem):
    reference_number: Optional[str] = None
    notice_date: Optional[date] = None
    received_date: Optional[date] = None
    response_days: Optional[int] = None
    deadline_source: Optional[str] = None
    deadline_note: Optional[str] = None
    deadline_quote: Optional[str] = None
    deadline_verified: bool = False
    deadline_rule: Optional[str] = None            # citation, when the date comes from a statutory window
    received_confirmed: bool = True
    needs_received_date: bool = False              # the deadline counts from receipt and the user has not said when it arrived
    issuer_role: Optional[str] = None
    addressed_to: Optional[str] = None
    summary_points: List[str] = []
    demands: List[str] = []
    statutes: List[str] = []
    consequences: Optional[str] = None
    legal_note: Optional[str] = None
    legal_ref: Optional[str] = None
    legal_if_ignored: Optional[str] = None
    if_ignored: Optional[str] = None
    actions: List[str] = []
    actions_done: List[int] = []
    key_quotes: List[KeyQuote] = []
    ocr_used: bool = False
    in_calendar: bool = False
    raw_text: Optional[str] = None
    drafts: List[DraftOut] = []


class TextIn(BaseModel):
    text: str = Field(min_length=40, max_length=120_000)
    title: Optional[str] = Field(default=None, max_length=200)
    received_date: Optional[date] = None


class CaseUpdate(BaseModel):
    received_date: Optional[date] = None
    review_status: Optional[Literal["draft", "ready_for_lawyer", "lawyer_approved"]] = None
    status: Optional[Literal["analyzed", "closed"]] = None
    actions_done: Optional[List[int]] = None


class RegenerateIn(BaseModel):
    instructions: Optional[str] = Field(default=None, max_length=300)


class SaveDraftIn(BaseModel):
    reply_text: str = Field(min_length=20, max_length=20_000)
