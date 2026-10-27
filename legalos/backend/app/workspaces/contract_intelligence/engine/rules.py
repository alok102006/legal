"""India-specific rule engine for contracts.

Deterministic checks over the *extracted facts* (never over free LLM judgement), each with its
legal basis. All legal references are marked `status="to_verify"` until a lawyer/CA has
confirmed them; the UI shows them as "Legal note - verify before relying".

Bump RULES_VERSION whenever a rule or note changes.
"""
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

from app.workspaces.contract_intelligence.engine.schemas import (
    ContractFacts, ContractType, DisputeMechanism, FindingCategory, Severity,
)
from app.workspaces.contract_intelligence.engine.segmenter import Segment

RULES_VERSION = "2026-10-27.1"

_BUYER_WORDS = ("buyer", "purchaser", "customer", "recipient", "principal", "client", "ordering", "procuring")
_SELLER_WORDS = ("supplier", "seller", "vendor", "contractor", "service provider", "consultant", "manufacturer")
_FOREIGN_LAW_WORDS = (
    "singapore", "england", "english law", "new york", "delaware", "california", "dubai", "uae",
    "united arab", "hong kong", "london", "united states", "usa", "germany", "netherlands",
)


@dataclass
class OrgProfile:
    entity_type: Optional[str] = None
    msme_category: Optional[str] = None   # micro | small | medium | none | unknown
    state_code: Optional[str] = None
    gstin: Optional[str] = None


@dataclass
class RuleFinding:
    rule_id: str
    category: FindingCategory
    severity: Severity
    title: str
    why_it_matters: str
    recommendation: str
    basis: str                      # legal basis in words
    source_ref: str                 # statute reference
    condition_note: Optional[str] = None   # when it applies, if conditional
    keywords: List[str] = field(default_factory=list)  # to anchor to a segment
    status: str = "to_verify"


@dataclass
class RuleContext:
    facts: ContractFacts
    org: Optional[OrgProfile]
    segments: List[Segment]

    @property
    def client_role(self) -> str:
        for p in self.facts.parties:
            if p.is_our_client:
                return p.role.lower()
        return ""

    @property
    def client_is_buyer(self) -> bool:
        r = self.client_role
        return any(w in r for w in _BUYER_WORDS) and not any(w in r for w in _SELLER_WORDS)

    @property
    def client_is_seller(self) -> bool:
        return any(w in self.client_role for w in _SELLER_WORDS)


Rule = Callable[[RuleContext], Optional[RuleFinding]]


def r_msme_payment_buyer(c: RuleContext) -> Optional[RuleFinding]:
    f = c.facts
    if f.contract_type not in (ContractType.supply, ContractType.service) or not c.client_is_buyer:
        return None
    if f.payment_days is None or f.payment_days <= 45:
        return None
    return RuleFinding(
        rule_id="IN-MSME-45-BUYER",
        category=FindingCategory.payment_terms,
        severity=Severity.high if f.payment_days > 90 else Severity.medium,
        title=f"Payment period of {f.payment_days} days exceeds the 45-day MSME limit",
        why_it_matters=(
            "If your supplier is a registered micro or small enterprise, the law caps the credit period at 45 days "
            "(15 days if there is no written agreement) and delayed payment carries compound interest. "
            "Amounts left unpaid beyond the limit can also lose their tax deduction until paid."
        ),
        recommendation="Check the supplier's Udyam registration. If they are MSME-registered, set payment to 45 days or less, or budget for statutory interest.",
        basis="Payment to micro and small enterprise suppliers must be made within the statutory period, with interest on delay; unpaid sums beyond it are deductible only when actually paid.",
        source_ref="MSMED Act 2006 ss.15-16; Income-tax Act 1961 s.43B(h)",
        condition_note="Applies only if the supplier is a registered micro or small enterprise.",
        keywords=["payment", "days", "invoice"],
    )


def r_msme_seller_rights(c: RuleContext) -> Optional[RuleFinding]:
    f, org = c.facts, c.org
    if not org or (org.msme_category or "").lower() not in ("micro", "small"):
        return None
    if f.contract_type not in (ContractType.supply, ContractType.service) or not c.client_is_seller:
        return None
    if f.payment_days is None or f.payment_days <= 45:
        return None
    return RuleFinding(
        rule_id="IN-MSME-45-SELLER",
        category=FindingCategory.payment_terms,
        severity=Severity.medium,
        title=f"You can ask for payment within 45 days (contract says {f.payment_days})",
        why_it_matters="As a registered micro/small enterprise, you are entitled to payment within 45 days of acceptance, with interest if the buyer is late. A longer contractual period does not override this.",
        recommendation="Ask the buyer to reduce the payment period to 45 days or less, and mention your Udyam registration on invoices.",
        basis="Statutory payment period and interest for dues owed to micro and small enterprises.",
        source_ref="MSMED Act 2006 ss.15-16",
        keywords=["payment", "days", "invoice"],
    )


# Commercial deals where a liability cap is a normal, expected protection. Not for leases, loans,
# employment letters or NDAs, where "no cap" is the norm and flagging it would be noise.
_LIABILITY_CAP_TYPES = (
    ContractType.supply, ContractType.service, ContractType.distribution, ContractType.franchise,
    ContractType.software_license, ContractType.partnership, ContractType.other,
)


def r_uncapped_liability(c: RuleContext) -> Optional[RuleFinding]:
    if c.facts.liability_cap_present is not False or c.facts.contract_type not in _LIABILITY_CAP_TYPES:
        return None
    return RuleFinding(
        rule_id="IN-LIAB-NOCAP",
        category=FindingCategory.liability_indemnity,
        severity=Severity.high,
        title="No cap on liability",
        why_it_matters="The contract does not limit how much you could owe if something goes wrong, so a single dispute could exceed the value of the deal.",
        recommendation="Ask for a cap, commonly the fees paid or payable in the previous 12 months, with carve-outs only for fraud and wilful misconduct.",
        basis="Indian law lets a party recover proven loss caused by breach; without a contractual cap the exposure is not limited by the deal value.",
        source_ref="Indian Contract Act 1872 s.73",
        keywords=["liab", "indemn", "damages"],
    )


def r_foreign_law(c: RuleContext) -> Optional[RuleFinding]:
    text = f"{c.facts.governing_law or ''} {c.facts.jurisdiction or ''} {c.facts.arbitration_seat or ''}".lower()
    if not text.strip() or not any(w in text for w in _FOREIGN_LAW_WORDS):
        return None
    return RuleFinding(
        rule_id="IN-FOREIGN-LAW",
        category=FindingCategory.dispute_resolution,
        severity=Severity.medium,
        title="Foreign governing law or venue",
        why_it_matters="Disputes would be decided under foreign law and/or in a foreign venue, which is slower and far costlier for an Indian SME to fight.",
        recommendation="Ask for Indian law and an Indian seat, or institutional arbitration in a neutral, low-cost seat.",
        basis="Foreign-seated arbitration and foreign courts follow different procedures; enforcing awards/decrees across borders adds cost and time.",
        source_ref="Arbitration and Conciliation Act 1996 (Part I / Part II)",
        keywords=["governing law", "jurisdiction", "arbitration"],
    )


def r_no_dispute_clause(c: RuleContext) -> Optional[RuleFinding]:
    f = c.facts
    if f.governing_law or f.jurisdiction or (f.dispute_mechanism not in (None, DisputeMechanism.none)):
        return None
    return RuleFinding(
        rule_id="IN-NO-DISPUTE",
        category=FindingCategory.dispute_resolution,
        severity=Severity.medium,
        title="No governing law or dispute-resolution clause found",
        why_it_matters="Without an agreed law, venue or process, a dispute starts with an argument about where and how to fight it.",
        recommendation="Add: governing law (Laws of India), exclusive jurisdiction of courts at your city, or arbitration with a named seat and a mutually appointed arbitrator.",
        basis="Parties may choose forum and process; silence leaves it to default territorial jurisdiction rules.",
        source_ref="Arbitration and Conciliation Act 1996; Code of Civil Procedure 1908 ss.16-20",
        keywords=["dispute", "law", "court"],
    )


def r_auto_renewal(c: RuleContext) -> Optional[RuleFinding]:
    f = c.facts
    if f.auto_renewal is not True:
        return None
    long_notice = f.renewal_notice_days is None or f.renewal_notice_days >= 60
    return RuleFinding(
        rule_id="IN-AUTORENEW",
        category=FindingCategory.auto_renewal,
        severity=Severity.medium if long_notice else Severity.low,
        title="Renews automatically" + (f" unless you give {f.renewal_notice_days} days' notice" if f.renewal_notice_days else ""),
        why_it_matters="If you miss the notice window you are locked in for another full term.",
        recommendation="Add a calendar reminder for the notice date, and try to shorten the notice period to 30 days or less.",
        basis="Renewal and lock-in operate as written; courts generally enforce agreed terms.",
        source_ref="Indian Contract Act 1872 s.10",
        keywords=["renew", "auto", "term"],
    )


def r_termination_imbalance(c: RuleContext) -> Optional[RuleFinding]:
    f = c.facts
    if f.termination_notice_days_client is None and f.termination_notice_days_other is not None:
        return RuleFinding(
            rule_id="IN-TERM-ONESIDED",
            category=FindingCategory.termination,
            severity=Severity.high,
            title="Only the other side can terminate for convenience",
            why_it_matters="They can walk away on notice, but you have no matching right, so you may be stuck in a deal that no longer works.",
            recommendation="Ask for a mutual right to terminate for convenience with the same notice period.",
            basis="Termination rights exist only as written in the contract.",
            source_ref="Indian Contract Act 1872 s.39",
            keywords=["terminat", "notice"],
        )
    return None


def r_stamp_duty(c: RuleContext) -> Optional[RuleFinding]:
    f = c.facts
    if f.stamp_duty_mentioned is not False:
        return None
    if f.contract_type not in (
        ContractType.lease, ContractType.loan_guarantee, ContractType.distribution, ContractType.franchise,
        ContractType.partnership, ContractType.service, ContractType.supply,
    ):
        return None
    is_lease = f.contract_type == ContractType.lease
    return RuleFinding(
        rule_id="IN-STAMP",
        category=FindingCategory.stamp_execution,
        severity=Severity.medium if is_lease else Severity.low,
        title="No reference to stamp duty",
        why_it_matters="An insufficiently stamped agreement can be refused as evidence in court until duty and a penalty are paid. Leases beyond 11 months generally also need registration.",
        recommendation="Execute on the correct stamp paper for your state (or e-stamp) before signing; confirm whether registration is required.",
        basis="Instruments not duly stamped are inadmissible in evidence until duty and penalty are paid; stamp duty rates are state-specific.",
        source_ref="Indian Stamp Act 1899 s.35 and state stamp laws; Registration Act 1908 s.17",
        condition_note="Duty and registration rules differ by state - confirm locally.",
        keywords=["stamp", "execut", "witness"],
    )


RULES: List[Rule] = [
    r_msme_payment_buyer, r_msme_seller_rights, r_uncapped_liability, r_foreign_law,
    r_no_dispute_clause, r_auto_renewal, r_termination_imbalance, r_stamp_duty,
]


def run_rules(facts: ContractFacts, org: Optional[OrgProfile], segments: List[Segment]) -> List[RuleFinding]:
    ctx = RuleContext(facts=facts, org=org, segments=segments)
    out: List[RuleFinding] = []
    for rule in RULES:
        res = rule(ctx)
        if res:
            out.append(res)
    return out


# Legal notes attached to AI findings of a given category (always "verify before relying").
LEGAL_NOTES: Dict[FindingCategory, Dict[str, str]] = {
    FindingCategory.non_compete: {
        "note": "Agreements in restraint of trade are void, so non-compete restrictions that apply after the contract or employment ends are generally hard to enforce; restrictions during the term are usually valid. Courts decide case by case.",
        "ref": "Indian Contract Act 1872 s.27",
    },
    FindingCategory.penalty_damages: {
        "note": "Where a contract names a penalty or liquidated sum, courts typically award reasonable compensation not exceeding the amount named. A very high fixed penalty may not be enforced in full.",
        "ref": "Indian Contract Act 1872 s.74",
    },
    FindingCategory.dispute_resolution: {
        "note": "A clause letting one party alone appoint the sole arbitrator can be challenged under the Arbitration Act as interpreted by the Supreme Court. Prefer a mutually agreed or institution-appointed arbitrator.",
        "ref": "Arbitration and Conciliation Act 1996 ss.11-12",
    },
    FindingCategory.payment_terms: {
        "note": "Payments to micro and small enterprise suppliers are subject to a statutory time limit and interest on delay; check the supplier's Udyam status.",
        "ref": "MSMED Act 2006 ss.15-16",
    },
    FindingCategory.data_protection: {
        "note": "The Digital Personal Data Protection Act 2023 and its 2025 Rules phase in obligations on consent, notice, security and breach reporting for personal data; full compliance is expected around May 2027.",
        "ref": "DPDP Act 2023; DPDP Rules 2025",
    },
    FindingCategory.stamp_execution: {
        "note": "Stamp duty and registration requirements are state-specific; insufficiently stamped instruments are inadmissible in evidence until duty and penalty are paid.",
        "ref": "Indian Stamp Act 1899 s.35",
    },
    FindingCategory.liability_indemnity: {
        "note": "Indemnities are enforceable as written; absent a cap, recovery is limited only by the loss proved.",
        "ref": "Indian Contract Act 1872 ss.124-125, s.73",
    },
}
