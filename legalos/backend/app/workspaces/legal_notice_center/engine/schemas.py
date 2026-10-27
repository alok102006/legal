"""Structured-output schemas for notice analysis (sent to Gemini as the response schema)."""
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class NoticeType(str, Enum):
    cheque_bounce = "cheque_bounce"            # NI Act s.138 demand
    legal_demand = "legal_demand"              # payment demand / recovery from a lawyer or party
    gst_notice = "gst_notice"                  # GST show-cause / demand / scrutiny
    income_tax_notice = "income_tax_notice"
    labour_notice = "labour_notice"            # PF / ESI / labour department
    msme_delayed_payment = "msme_delayed_payment"
    consumer_complaint = "consumer_complaint"
    ip_notice = "ip_notice"                    # trademark / copyright cease-and-desist
    employment_dispute = "employment_dispute"  # claim by an employee / ex-employee
    tenancy_notice = "tenancy_notice"          # rent / eviction
    court_summons = "court_summons"
    defamation = "defamation"
    contract_breach = "contract_breach"
    regulatory_other = "regulatory_other"
    other = "other"


class NoticeFacts(BaseModel):
    notice_type: NoticeType
    title: str = Field(description="Short plain-English title, e.g. 'Cheque bounce notice from Mehta & Associates'.")
    issuer_name: Optional[str] = Field(default=None, description="Who sent it (law firm, officer, company).")
    issuer_role: Optional[str] = Field(default=None, description="e.g. 'Advocate for ABC Traders', 'GST Superintendent'.")
    addressed_to: Optional[str] = None
    reference_number: Optional[str] = None
    notice_date: Optional[str] = Field(default=None, description="Date on the notice, ISO YYYY-MM-DD, null if not stated.")
    summary_points: List[str] = Field(description="3-5 plain-English bullets (max 25 words each): who is claiming what, why, and what happens if ignored.")
    demands: List[str] = Field(default_factory=list, description="Each thing the sender demands, one per item.")
    amount_claimed: Optional[float] = Field(default=None, description="Total amount demanded in rupees as a number, null if none.")
    response_days: Optional[int] = Field(default=None, description="Number of days the notice gives to respond/pay, null if not stated.")
    response_days_from: Optional[str] = Field(
        default=None, description="Only when response_days is set: 'receipt' if the days count from receipt/service of the notice, 'notice_date' if they count from the date of the notice. null if unclear.")
    response_deadline_date: Optional[str] = Field(default=None, description="An explicit deadline date, ISO YYYY-MM-DD, null if not stated.")
    deadline_quote: Optional[str] = Field(default=None, description="VERBATIM sentence from the notice that states the deadline (max 300 chars).")
    amount_quote: Optional[str] = Field(default=None, description="VERBATIM sentence from the notice that states the amount claimed (max 300 chars), null if no amount.")
    demand_quote: Optional[str] = Field(default=None, description="VERBATIM sentence from the notice that states what the sender demands (max 300 chars).")
    statutes_cited: List[str] = Field(default_factory=list, description="Laws or sections the notice cites, e.g. 'Section 138 Negotiable Instruments Act'.")
    consequences_stated: Optional[str] = Field(default=None, description="What the sender says will happen if there is no response.")
    if_ignored: Optional[str] = Field(
        default=None, description="1-2 plain-English sentences: what realistically happens if the reader does nothing, based only on the notice's own warning and the law it cites. null if neither says.")
    what_to_do_now: List[str] = Field(
        default_factory=list, description="3-5 concrete next actions for the reader, in order, each starting with a verb and under 22 words, specific to THIS notice. No invented facts.")
    key_dates: List[str] = Field(default_factory=list, description="Other important dates, each as 'YYYY-MM-DD: what'.")


class NoticeReplyDraft(BaseModel):
    reply_text: str = Field(description="Complete formal reply letter. Any fact only the company knows must be written as [CONFIRM: what is needed].")
    points_to_confirm: List[str] = Field(default_factory=list, description="Facts the company must verify before sending.")
    documents_to_gather: List[str] = Field(default_factory=list, description="Documents that support the reply (invoices, delivery challans, bank statements...).")
