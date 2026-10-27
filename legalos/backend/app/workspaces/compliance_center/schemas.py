import uuid
from datetime import date, datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, Field


class PenaltyEstimate(BaseModel):
    """Deterministic late-fee estimate from the rule's structured fee (no AI). Late fee only, not interest."""
    amount: int
    days_late: int
    per_day: Optional[int] = None
    cap: Optional[int] = None
    capped: bool = False
    flat: bool = False
    note: Optional[str] = None


class Origin(BaseModel):
    """Where a pushed reminder came from, so the calendar can link back to it."""
    kind: Literal["contract", "notice", "document"]
    label: str                                    # e.g. "Contract: Acme supply agreement"
    href: str                                     # e.g. /contracts/<id>


class TaskOut(BaseModel):
    id: uuid.UUID
    title: str
    category: str
    due_date: Optional[date] = None
    status: str                                   # pending | completed
    state: str                                    # overdue | due_soon | upcoming | done
    days_left: Optional[int] = None               # negative when overdue
    description: Optional[str] = None
    penalty_desc: Optional[str] = None
    rule_id: Optional[str] = None
    period_label: Optional[str] = None
    form_name: Optional[str] = None
    authority: Optional[str] = None
    source_ref: Optional[str] = None
    needs_confirmation: bool = False
    confirm_note: Optional[str] = None
    is_custom: bool = False
    completed_at: Optional[datetime] = None
    completion_note: Optional[str] = None
    verified: bool = True                         # False = the rule's date is still being verified
    penalty_estimate: Optional[PenaltyEstimate] = None
    origin: Optional[Origin] = None
    file_where: Optional[str] = None              # e.g. "GST portal"
    file_url: Optional[str] = None


class TaskCreate(BaseModel):
    title: str = Field(min_length=2, max_length=200)
    category: Literal["tax", "corporate", "labor", "license", "other"] = "other"
    due_date: date
    description: Optional[str] = Field(default=None, max_length=1000)


class TaskUpdate(BaseModel):
    status: Optional[Literal["pending", "completed"]] = None
    note: Optional[str] = Field(default=None, max_length=1000)
    # only editable on custom tasks
    title: Optional[str] = Field(default=None, min_length=2, max_length=200)
    due_date: Optional[date] = None
    description: Optional[str] = Field(default=None, max_length=1000)
    category: Optional[Literal["tax", "corporate", "labor", "license", "other"]] = None


class BulkCompleteIn(BaseModel):
    ids: List[uuid.UUID] = Field(min_length=1, max_length=300)
    note: Optional[str] = Field(default=None, max_length=500)


class BulkCompleteOut(BaseModel):
    completed: int


class NextDeadline(BaseModel):
    id: uuid.UUID
    title: str
    period_label: Optional[str] = None
    due_date: date
    days_left: int
    needs_confirmation: bool = False


class SummaryOut(BaseModel):
    needs_profile: bool = False
    overdue: int = 0
    due_in_7_days: int = 0
    due_in_30_days: int = 0
    completed_last_30_days: int = 0
    needs_confirmation: int = 0
    next_deadlines: List[NextDeadline] = []
    rules_version: str
    today: date
    rules_total: int = 0
    rules_applicable: int = 0
    sources_total: int = 0
    last_synced: Optional[datetime] = None


class RuleOut(BaseModel):
    id: str
    title: str
    category: str
    authority: str
    form: str
    description: str
    penalty: str
    source: str
    reason: str
    needs_confirmation: bool = False
    confirm_note: Optional[str] = None
    verify: bool = False
    verified: bool = True


class SkippedRuleOut(BaseModel):
    id: str
    title: str
    reason: str


class NotCoveredOut(BaseModel):
    title: str
    reason: str


class RulesOverview(BaseModel):
    rules_version: str
    applicable: List[RuleOut]
    not_applicable: List[SkippedRuleOut]
    not_covered: List[NotCoveredOut]


class FactRule(BaseModel):
    id: str
    title: str
    form: str = ""
    applies: bool
    reason: str
    verified: bool = True


class ProfileFact(BaseModel):
    key: str                                      # entity_type | state_code | gst | tds | ... | always
    label: str
    kind: Literal["field", "registration", "always"]
    value: Optional[str] = None                   # raw profile value (None = not set); registrations are "yes" / "no"
    hint: Optional[str] = None
    rules: List[FactRule]


class ProfileFacts(BaseModel):
    facts: List[ProfileFact]
    rules_applicable: int
    rules_total: int


class SyncOut(BaseModel):
    created: int
    updated: int
    removed: int
    kept: int
    rules_version: str
