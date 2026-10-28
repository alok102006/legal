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
    kind: Literal["deadline", "hearing", "amount", "demand"]
    text: str
    verified: bool = False


class DeadlineBasis(BaseModel):
    """One date the deadline engine considered; the earliest one is the deadline."""
    due: date
    basis: Literal["stated_date", "stated_period", "hearing", "statutory"]
    anchor: str
    verified: bool
    explanation: str
    citation: Optional[str] = None


class StatutoryWindowOut(BaseModel):
    count: int
    unit: str
    anchor: str
    citation: str
    note: str
    purpose: str


class TypeInfo(BaseModel):
    """Reference-table facts about this kind of notice (no AI): meaning, consequence chain, documents, who replies."""
    label: str
    family: str
    meaning: str
    if_ignored: str
    ref: str
    documents: List[str] = []
    handler: Literal["owner", "ca", "lawyer", "lawyer_required"]
    handler_label: str
    response: Literal["letter", "action_plan"]
    channel: str
    verified: bool = True                         # False -> the UI shows "being verified"
    verify_note: Optional[str] = None
    statutory_window: Optional[StatutoryWindowOut] = None


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
    deadline_basis: List[DeadlineBasis] = []       # every date considered (stated / period / hearing / statutory)
    overdue: bool = False
    forthwith: bool = False                        # the notice demands action "forthwith" without a date
    hearing_date: Optional[date] = None
    needs_notice_date: bool = False                # a period counts from the notice date, which could not be read
    notice_date_verified: bool = True
    date_corrections: List[str] = []               # where the notice's own words overrode the AI's reading of a date
    received_confirmed: bool = True
    needs_received_date: bool = False              # the deadline counts from receipt and the user has not said when it arrived
    issuer_role: Optional[str] = None
    addressed_to: Optional[str] = None
    form_or_section: Optional[str] = None
    language: Optional[str] = None
    summary_local: List[str] = []                  # the summary in the notice's own language (non-English notices)
    allegations: List[str] = []
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
    type_info: Optional[TypeInfo] = None
    draft_kind: Literal["letter", "action_plan"] = "letter"
    lawyer_required: bool = False
    lawyer_brief: Optional[str] = None             # one-page handoff built from stored fields (no AI call)
    input_cleaned: bool = False                    # chat-export noise was removed from pasted text
    pages: int = 1
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
    notice_date: Optional[date] = None
    review_status: Optional[Literal["draft", "ready_for_lawyer", "lawyer_approved"]] = None
    status: Optional[Literal["analyzed", "closed"]] = None
    actions_done: Optional[List[int]] = None


class RegenerateIn(BaseModel):
    instructions: Optional[str] = Field(default=None, max_length=300)


class SaveDraftIn(BaseModel):
    reply_text: str = Field(min_length=20, max_length=20_000)
