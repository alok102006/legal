"""Structured-output schemas for the contract engine (also the API vocabulary).

Keep these flat and explicit: they are sent to Gemini as the response schema.
"""
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class ContractType(str, Enum):
    supply = "supply"                # goods purchase / supply
    service = "service"              # services / consulting / AMC
    distribution = "distribution"    # dealer / distributor / agency / reseller
    franchise = "franchise"          # franchise / licensing of a brand or business format
    partnership = "partnership"      # partnership deed / joint venture / shareholders' arrangement
    lease = "lease"                  # rent / leave-and-licence
    employment = "employment"        # offer letter / employment / consultancy-individual
    nda = "nda"
    loan_guarantee = "loan_guarantee"
    software_license = "software_license"
    other = "other"


class FindingCategory(str, Enum):
    liability_indemnity = "liability_indemnity"
    termination = "termination"
    lock_in_exclusivity = "lock_in_exclusivity"
    non_compete = "non_compete"
    penalty_damages = "penalty_damages"
    payment_terms = "payment_terms"
    auto_renewal = "auto_renewal"
    unilateral_change = "unilateral_change"
    ip_ownership = "ip_ownership"
    confidentiality = "confidentiality"
    dispute_resolution = "dispute_resolution"
    force_majeure = "force_majeure"
    assignment_subcontract = "assignment_subcontract"
    data_protection = "data_protection"
    stamp_execution = "stamp_execution"
    other = "other"


class Severity(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class DisputeMechanism(str, Enum):
    courts = "courts"
    arbitration = "arbitration"
    both = "both"
    none = "none"


# ------------------------------------------------------------------ pass 1: facts

class Party(BaseModel):
    name: str = Field(description="Legal name of the party exactly as written in the contract.")
    role: str = Field(description="Role in this contract, e.g. Buyer, Supplier, Landlord, Tenant, Employer, Disclosing Party.")
    is_our_client: bool = Field(default=False, description="True only for the party the analysis is being done for.")


class ContractFacts(BaseModel):
    title: str = Field(description="Title of the agreement as written, or a short descriptive title.")
    contract_type: ContractType
    contract_type_detail: Optional[str] = Field(
        default=None,
        description="Optional 2-6 word plain description of this specific contract, e.g. 'Shop lease in Surat' or 'Yarn supply agreement'. Null if the type says it all.",
    )
    summary_points: List[str] = Field(
        description="4-6 plain-English bullets (max 25 words each) a non-lawyer business owner can read in 30 seconds: what this deal is, who owes what, for how long, and the single biggest watch-out."
    )
    parties: List[Party]
    effective_date: Optional[str] = Field(default=None, description="ISO date YYYY-MM-DD, null if not stated.")
    end_date: Optional[str] = Field(default=None, description="ISO date YYYY-MM-DD if stated or directly computable, else null.")
    term_description: Optional[str] = Field(default=None, description="Term in words, e.g. '3 years from the Effective Date'.")
    auto_renewal: Optional[bool] = Field(default=None, description="True if the contract renews automatically, False if it clearly does not, null if not stated.")
    renewal_notice_days: Optional[int] = Field(default=None, description="Days of notice needed to stop renewal, if any.")
    contract_value_amount: Optional[float] = Field(default=None, description="Total or annual value as a number in the stated currency, null if not stated.")
    contract_value_currency: Optional[str] = Field(default=None, description="ISO currency code, e.g. INR.")
    contract_value_basis: Optional[str] = Field(default=None, description="What the value covers, e.g. 'total', 'per year', 'per month rent'.")
    payment_days: Optional[int] = Field(default=None, description="Number of days after invoice/delivery by which payment must be made. Null if not stated.")
    payment_terms_text: Optional[str] = Field(default=None, description="Short description of payment schedule/terms.")
    late_payment_interest: Optional[str] = Field(default=None, description="Interest/penalty on late payment as written, if any.")
    governing_law: Optional[str] = Field(default=None, description="e.g. 'Laws of India'.")
    jurisdiction: Optional[str] = Field(default=None, description="Courts/venue named, e.g. 'Courts at Pune'.")
    dispute_mechanism: Optional[DisputeMechanism] = None
    arbitration_seat: Optional[str] = None
    termination_terms: Optional[str] = Field(default=None, description="One or two short sentences on how and when the contract can be ended, by whom, and any lock-in; null if not stated.")
    termination_notice_days_client: Optional[int] = Field(default=None, description="Days of notice our client must give to terminate for convenience; null if no such right.")
    termination_notice_days_other: Optional[int] = Field(default=None, description="Days of notice the counterparty must give to terminate for convenience; null if no such right.")
    liability_cap_present: Optional[bool] = Field(default=None, description="True if liability is capped at a stated amount/formula; False if uncapped or no cap clause.")
    liability_cap_text: Optional[str] = None
    stamp_duty_mentioned: Optional[bool] = Field(default=None, description="True if the document refers to stamp paper / stamp duty / registration.")
    key_dates: List[str] = Field(default_factory=list, description="Other important dates/deadlines, each as 'YYYY-MM-DD: what happens'.")


# ------------------------------------------------------------------ pass 2: findings

class RawFinding(BaseModel):
    segment_id: Optional[str] = Field(default=None, description="The id (e.g. S7) of the segment containing the quote.")
    category: FindingCategory
    severity: Severity
    title: str = Field(description="Plain-English headline, max 12 words, e.g. 'Unlimited liability for any loss'.")
    why_it_matters: str = Field(description="1-2 sentences on the concrete consequence for our client, in plain English.")
    quote: str = Field(description="VERBATIM text copied from the contract (max 300 characters). Never paraphrase.")
    recommendation: str = Field(description="What our client should ask for or do, in one or two sentences.")
    suggested_wording: Optional[str] = Field(default=None, description="Ready-to-send replacement clause text, if a rewrite is appropriate.")


class MissingProtection(BaseModel):
    category: FindingCategory
    title: str = Field(description="What protection is absent, e.g. 'No cap on liability'.")
    why_it_matters: str
    suggested_wording: Optional[str] = None


class RiskAnalysis(BaseModel):
    findings: List[RawFinding]
    missing_protections: List[MissingProtection] = Field(default_factory=list)


# ------------------------------------------------------------------ chat

class ChatCitation(BaseModel):
    quote: str = Field(description="Verbatim text from the contract that supports the answer (max 300 chars).")
    segment_id: Optional[str] = None


class ChatAnswer(BaseModel):
    answer: str = Field(description="Plain-English answer based ONLY on the contract text.")
    found_in_contract: bool = Field(description="False if the contract does not address the question.")
    citations: List[ChatCitation] = Field(default_factory=list)
