"""Structured-output schemas for notice analysis (sent to Gemini as the response schema).

The notice types are granular (form / section level) because the reply window, the consequence chain and
whether a reply letter is even the right move all depend on it. The broad values (gst_notice,
income_tax_notice, labour_notice, regulatory_other, other) remain as fallbacks and for cases stored earlier.
"""
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class NoticeType(str, Enum):
    # --- GST
    gst_scrutiny_asmt10 = "gst_scrutiny_asmt10"
    gst_show_cause_drc01 = "gst_show_cause_drc01"
    gst_demand_order_drc07 = "gst_demand_order_drc07"
    gst_registration_cancellation_reg17 = "gst_registration_cancellation_reg17"
    gst_non_filer_gstr3a = "gst_non_filer_gstr3a"
    gst_notice = "gst_notice"                  # any other GST notice
    # --- income tax / TDS
    it_inquiry_142_1 = "it_inquiry_142_1"
    it_scrutiny_143_2 = "it_scrutiny_143_2"
    it_reassessment_148 = "it_reassessment_148"
    it_demand_156 = "it_demand_156"
    it_penalty_271 = "it_penalty_271"
    tds_default = "tds_default"
    income_tax_notice = "income_tax_notice"    # any other income-tax notice
    # --- labour and inspections
    epf_inquiry_7a = "epf_inquiry_7a"
    epf_damages_14b = "epf_damages_14b"
    esi_inquiry_45a = "esi_inquiry_45a"
    labour_inspection = "labour_inspection"    # labour commissioner / Shops & Establishments
    labour_notice = "labour_notice"            # any other PF / ESI / labour notice
    factory_inspection = "factory_inspection"
    pollution_control = "pollution_control"
    fssai_notice = "fssai_notice"
    legal_metrology = "legal_metrology"
    municipal_property_tax = "municipal_property_tax"
    municipal_trade_licence = "municipal_trade_licence"
    # --- banks, lenders, payment recovery
    bank_loan_recall = "bank_loan_recall"
    sarfaesi_13_2 = "sarfaesi_13_2"
    cheque_bounce = "cheque_bounce"            # NI Act s.138 demand
    lok_adalat = "lok_adalat"
    msme_samadhaan = "msme_samadhaan"          # reference before the MSE Facilitation Council
    msme_delayed_payment = "msme_delayed_payment"
    legal_demand = "legal_demand"              # payment demand / recovery from a lawyer or party
    # --- courts, tribunals, police
    arbitration_invocation = "arbitration_invocation"
    court_summons = "court_summons"            # civil court / tribunal summons
    court_summons_criminal = "court_summons_criminal"
    police_summons = "police_summons"
    # --- disputes
    insurance_repudiation = "insurance_repudiation"
    rera_notice = "rera_notice"
    consumer_complaint = "consumer_complaint"
    ip_notice = "ip_notice"                    # trademark / copyright cease-and-desist
    defamation = "defamation"
    tenancy_notice = "tenancy_notice"          # rent / eviction
    employment_dispute = "employment_dispute"  # claim by an employee / ex-employee
    contract_breach = "contract_breach"
    regulatory_other = "regulatory_other"
    other = "other"


class NoticeFacts(BaseModel):
    notice_type: NoticeType
    title: str = Field(description="Short plain-English title, e.g. 'Cheque bounce notice from Mehta & Associates'.")
    language: Optional[str] = Field(default=None, description="Main language of the notice as an ISO code: en, hi, mr, gu, ta, te, kn, bn, pa... 'mixed' if two.")
    form_or_section: Optional[str] = Field(default=None, description="The form or section the notice is issued under, as printed, e.g. 'FORM GST DRC-01', 'Section 143(2)'.")
    issuer_name: Optional[str] = Field(default=None, description="Who sent it (law firm, officer, company).")
    issuer_role: Optional[str] = Field(default=None, description="e.g. 'Advocate for ABC Traders', 'GST Superintendent'.")
    addressed_to: Optional[str] = None
    reference_number: Optional[str] = None
    notice_date: Optional[str] = Field(default=None, description="Date on the notice, ISO YYYY-MM-DD, null if not stated.")
    summary_points: List[str] = Field(description="3-5 plain-English bullets (max 25 words each): who is claiming what, why, and what happens if ignored.")
    summary_local: List[str] = Field(
        default_factory=list, description="Only when the notice is not in English: the same summary bullets in the notice's language. Empty otherwise.")
    allegations: List[str] = Field(
        default_factory=list, description="Each separate allegation, discrepancy or query the notice raises, in the notice's order, one short English line each.")
    demands: List[str] = Field(default_factory=list, description="Each thing the sender demands, one per item.")
    amount_claimed: Optional[float] = Field(default=None, description="Total amount demanded in rupees as a number, null if none.")
    response_days: Optional[int] = Field(default=None, description="Number of days the notice gives to respond/pay, null if not stated.")
    response_days_from: Optional[str] = Field(
        default=None, description="Only when response_days is set: 'receipt' if the days count from receipt/service of the notice, 'notice_date' if they count from the date of the notice. null if unclear.")
    response_period_unit: Optional[str] = Field(
        default=None, description="Only when response_days is set: 'days', 'working_days' or 'months' as the notice words it (response_days then holds that count).")
    response_deadline_date: Optional[str] = Field(default=None, description="An explicit deadline date, ISO YYYY-MM-DD, null if not stated.")
    forthwith: bool = Field(default=False, description="True when the notice demands action 'forthwith' / 'immediately' without a date or period.")
    deadline_quote: Optional[str] = Field(default=None, description="VERBATIM sentence from the notice that states the deadline (max 300 chars).")
    hearing_date: Optional[str] = Field(default=None, description="Date fixed for a hearing or appearance, ISO YYYY-MM-DD, null if none.")
    hearing_quote: Optional[str] = Field(default=None, description="VERBATIM sentence from the notice that fixes the hearing / appearance date.")
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
    reply_text: str = Field(description="Complete formal reply letter (or action plan). Any fact only the company knows must be written as [CONFIRM: what is needed].")
    points_to_confirm: List[str] = Field(default_factory=list, description="Facts the company must verify before sending.")
    documents_to_gather: List[str] = Field(default_factory=list, description="Documents that support the reply (invoices, delivery challans, bank statements...).")


class OcrPage(BaseModel):
    number: int
    text: str


class NoticeOcr(BaseModel):
    pages: List[OcrPage]
