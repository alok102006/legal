"""India-specific rule engine for contracts.

Deterministic checks, each with its legal basis. Two kinds:
- presence rules: fire only when the triggering clause is LOCATED in the text; the finding carries that sentence
  verbatim (with segment and page), so it is verified by construction;
- absence rules (no cap, no dispute clause, no stamp duty, no GST clause): fire only when the extracted facts say
  so AND a text search confirms the absence, and only when the whole contract was reviewed.

Legal references are marked `status="to_verify"`; the UI shows them as "Legal note - verify before relying".
Bump RULES_VERSION whenever a rule or note changes.
"""
import re
from dataclasses import dataclass, field
from functools import cached_property
from typing import Callable, Dict, List, Optional

from app.shared.india.identifiers import STATE_CODES
from app.workspaces.contract_intelligence.engine import evidence as ev
from app.workspaces.contract_intelligence.engine.contract_types import TypeProfile, profile
from app.workspaces.contract_intelligence.engine.schemas import (
    ContractFacts, ContractType, DisputeMechanism, FindingCategory, Severity,
)
from app.workspaces.contract_intelligence.engine.segmenter import Segment

RULES_VERSION = "2026-10-29.1"

_BUYER_WORDS = ("buyer", "purchaser", "customer", "recipient", "principal", "client", "ordering", "procuring",
                "owner", "hirer", "depositor", "shipper", "consignor", "advertiser", "subscriber")
_SELLER_WORDS = ("supplier", "seller", "vendor", "contractor", "service provider", "consultant", "manufacturer",
                 "job worker", "transporter", "carrier", "agency", "merchant")
# Parties that receive money, deposits or security: rules that protect a payer do not apply to them.
_CREDITOR_WORDS = ("landlord", "lessor", "licensor", "lender", "financier", "bank", "creditor", "franchisor", "nbfc")
_FOREIGN = re.compile(
    r"\b(singapore|england|english law|london|new york|delaware|wilmington|california|dubai|uae|united arab emirates|"
    r"hong kong|united states|usa|u\.s\.a\.?|germany|netherlands|mauritius|switzerland|geneva|paris|france|japan|"
    r"tokyo|china|australia|canada|siac|lcia|icc|hkiac|american arbitration)\b", re.I)


@dataclass
class OrgProfile:
    entity_type: Optional[str] = None
    msme_category: Optional[str] = None   # micro | small | medium | none | unknown
    state_code: Optional[str] = None      # GST state code, e.g. "27"
    gstin: Optional[str] = None


@dataclass
class RuleFinding:
    rule_id: str
    category: FindingCategory
    severity: Severity
    title: str
    why_it_matters: str
    recommendation: str
    legal_note: str                       # legal basis in words
    legal_ref: str                        # statute / case reference
    condition_note: Optional[str] = None  # when it applies, if conditional
    keywords: List[str] = field(default_factory=list)  # fallback anchor when there is no quote (absence rules)
    quote: Optional[str] = None           # verbatim sentence that triggered the rule (presence rules)
    segment_id: Optional[str] = None
    page: Optional[int] = None
    status: str = "to_verify"

    def cite(self, e: Optional[ev.Evidence]) -> "RuleFinding":
        if e is not None:
            self.quote, self.segment_id, self.page = e.quote, e.segment.id, e.segment.page_start
        return self


@dataclass
class RuleContext:
    facts: ContractFacts
    org: Optional[OrgProfile]
    segments: List[Segment]
    complete: bool = True                 # the whole contract was reviewed (absence rules allowed)

    @property
    def profile(self) -> TypeProfile:
        return profile(self.facts.contract_type)

    @property
    def client_role(self) -> str:
        return next((p.role.lower() for p in self.facts.parties if p.is_our_client), "")

    @property
    def client_known(self) -> bool:
        return any(p.is_our_client for p in self.facts.parties)

    @property
    def client_is_buyer(self) -> bool:
        r = self.client_role
        return any(w in r for w in _BUYER_WORDS) and not any(w in r for w in _SELLER_WORDS)

    @property
    def client_is_seller(self) -> bool:
        return any(w in self.client_role for w in _SELLER_WORDS)

    @property
    def client_is_creditor(self) -> bool:
        return any(w in self.client_role for w in _CREDITOR_WORDS)

    @property
    def client_is_employer(self) -> bool:
        return self.facts.contract_type == ContractType.employment and any(
            w in self.client_role for w in ("employer", "company"))

    @cached_property
    def full_text(self) -> str:
        return "\n".join(s.text for s in self.segments)

    @cached_property
    def client_aliases(self) -> List[str]:
        out = [a for p in self.facts.parties if p.is_our_client for a in ev.aliases(p.name, p.role, self.full_text)]
        if self.client_is_employer:
            out += ["company", "employer"]          # offer letters call the employer "the Company"
        return out

    @cached_property
    def other_aliases(self) -> List[str]:
        out = [a for p in self.facts.parties if not p.is_our_client for a in ev.aliases(p.name, p.role, self.full_text)]
        if self.client_is_employer:
            out += ["you", "your", "employee"]       # offer letters address the employee directly
        return [a for a in out if a not in self.client_aliases]

    def actor(self, e: ev.Evidence, verb: Optional[re.Pattern] = None) -> Optional[str]:
        """'client' / 'other' / 'both' / None: the party named just before the operative verb of the sentence
        (the first `verb` match at or after the trigger, else the trigger itself) - i.e. who it binds or empowers."""
        pos = e.start
        if verb is not None:
            m = verb.search(e.sentence, e.start) or verb.search(e.sentence)
            pos = m.start() if m else pos
        return ev.last_party_before(e.sentence, pos, self.client_aliases, self.other_aliases)

    def binds_client(self, e: ev.Evidence, verb: Optional[re.Pattern] = None) -> bool:
        """The obligation in this sentence falls on our client (or on both sides, or we cannot tell)."""
        return self.actor(e, verb) != "other"

    def empowers_other(self, e: ev.Evidence, verb: Optional[re.Pattern] = None) -> bool:
        """The right in this sentence belongs to the counterparty (or we cannot tell who holds it)."""
        return self.actor(e, verb) != "client"


Rule = Callable[[RuleContext], Optional[RuleFinding]]


def _rx(pattern: str) -> re.Pattern:
    return re.compile(pattern, re.I)


# Operative verbs used to find who a sentence binds ("X shall pay", "X may revise").
_PAY_VERB = _rx(r"\b(?:shall|will|must|agrees? to|is liable to|be liable to)\s+(?:also\s+|remain\s+liable\s+to\s+|forthwith\s+)?(?:pay|forfeit|be liable|reimburse|remain liable)")
_POWER_VERB = _rx(r"\b(?:may|can|shall be (?:entitled|free) to|is (?:entitled|free) to|reserves?|at (?:its|his|their) (?:sole |absolute )?discretion)\b")


def _in_text(c: RuleContext, days: float, near: re.Pattern) -> Optional[ev.Evidence]:
    """Sentence that states a period of `days` (or the same period in months) next to `near` words."""
    for num in ev.days_pattern(days):
        found = ev.find_first(c.segments, near, also=num)
        if found:
            return found
    return None


# ------------------------------------------------------------------ payment

_PAYMENT = _rx(r"\b(pay\w*|invoice\w*|bill\w*|credit period)\b|भुगतान")


def r_msme_payment_buyer(c: RuleContext) -> Optional[RuleFinding]:
    f = c.facts
    if not c.profile.msme_supply or not c.client_is_buyer or f.payment_days is None or f.payment_days <= 45:
        return None
    e = _in_text(c, f.payment_days, _PAYMENT)
    if not e:
        return None
    return RuleFinding(
        rule_id="IN-MSME-45-BUYER", category=FindingCategory.payment_terms,
        severity=Severity.high if f.payment_days > 90 else Severity.medium,
        title=f"Payment period of {f.payment_days} days exceeds the 45-day MSME limit",
        why_it_matters=(
            "If your supplier is a registered micro or small enterprise, the law caps the credit period at 45 days "
            "(15 days if there is no written agreement) and delayed payment carries compound interest. "
            "Amounts left unpaid beyond the limit can also lose their tax deduction until paid."),
        recommendation="Check the supplier's Udyam registration. If they are MSME-registered, set payment to 45 days or less, or budget for statutory interest.",
        legal_note="Payment to micro and small enterprise suppliers must be made within the statutory period, with interest on delay; unpaid sums beyond it are deductible only when actually paid.",
        legal_ref="MSMED Act 2006 ss.15-16; Income-tax Act 1961 s.43B(h)",
        condition_note="Applies only if the supplier is a registered micro or small enterprise.",
        keywords=["payment", "days", "invoice"],
    ).cite(e)


def r_msme_seller_rights(c: RuleContext) -> Optional[RuleFinding]:
    f, org = c.facts, c.org
    if not org or (org.msme_category or "").lower() not in ("micro", "small"):
        return None
    if not c.profile.msme_supply and f.contract_type != ContractType.purchase_order:
        return None
    if not c.client_is_seller or f.payment_days is None or f.payment_days <= 45:
        return None
    e = _in_text(c, f.payment_days, _PAYMENT)
    if not e:
        return None
    return RuleFinding(
        rule_id="IN-MSME-45-SELLER", category=FindingCategory.payment_terms, severity=Severity.medium,
        title=f"You can ask for payment within 45 days (contract says {f.payment_days})",
        why_it_matters="As a registered micro/small enterprise, you are entitled to payment within 45 days of acceptance, with interest if the buyer is late. A longer contractual period does not override this.",
        recommendation="Ask the buyer to reduce the payment period to 45 days or less, and mention your Udyam registration on invoices.",
        legal_note="Statutory payment period and interest for dues owed to micro and small enterprises.",
        legal_ref="MSMED Act 2006 ss.15-16",
        keywords=["payment", "days", "invoice"],
    ).cite(e)


_INTEREST = _rx(r"\binterest\b|ब्याज")
_COMPOUND = _rx(r"compound\w*|चक्रवृद्धि")


def r_high_interest(c: RuleContext) -> Optional[RuleFinding]:
    """Default/penal interest well above commercial norms. Loans: above 24% p.a.; other deals: above 18% p.a."""
    if c.client_is_creditor or (c.client_is_seller and not c.profile.lending):
        return None
    limit = 24.0 if c.profile.lending else 18.0
    worst = None
    for e in ev.find_all(c.segments, _INTEREST):
        rates = ev.annual_rates(e.sentence)
        if not rates or not c.binds_client(e, _PAY_VERB):
            continue
        rate = max(r for r, _ in rates)
        compounding = bool(_COMPOUND.search(e.sentence))
        if rate > limit or (rate >= limit and compounding):
            if worst is None or rate > worst[0]:
                worst = (rate, compounding, e)
    if not worst:
        return None
    rate, compounding, e = worst
    high = rate > limit + 6 or (compounding and rate > limit)
    return RuleFinding(
        rule_id="IN-INTEREST-HIGH", category=FindingCategory.payment_terms,
        severity=Severity.high if high else Severity.medium,
        title=f"Interest of {rate:g}% a year" + (", compounded" if compounding else "") + " on late payment",
        why_it_matters=f"Any delay quickly becomes expensive: {rate:g}% a year is well above normal commercial rates"
                       + (" and compounding makes it grow faster." if compounding else "."),
        recommendation=f"Ask for simple interest at or below {12 if not c.profile.lending else 18}% a year, charged only on the overdue amount and only after a grace period.",
        legal_note=("Courts treat a stipulated default rate as a penalty and award only reasonable compensation up to it; "
                    "for lenders, RBI's fair-practice rules require penal charges to be reasonable and not compounded."
                    if c.profile.lending else
                    "A contractual default rate is enforceable only as reasonable compensation; courts can reduce an "
                    "excessive or compounded rate. For dues to MSEs, the statutory rate is three times the RBI bank rate."),
        legal_ref=("Indian Contract Act 1872 s.74; RBI circular on Penal Charges in Loan Accounts (18 Aug 2023)"
                   if c.profile.lending else "Indian Contract Act 1872 s.74; Interest Act 1978; MSMED Act 2006 s.16"),
        keywords=["interest", "per annum", "delay"],
    ).cite(e)


_PRICE_CHANGE = _rx(
    r"\b(may|can|shall be (?:entitled|free) to|is (?:entitled|free) to|reserves? (?:the|its) right to|at (?:its|his|their) (?:sole |absolute )?discretion)\b"
    r"[^.;]{0,60}?\b(revise|change|increase|modify|vary|alter|amend|escalate|update)\w*\b[^.;]{0,50}?"
    r"\b(prices?|price list|rates?|fees?|charges|tariffs?|commissions?|margins?|discounts?|rent|terms|policies|this agreement)\b"
    r"|\b(prices?|price list|rates?|fees?|charges|tariffs?)\b[^.;]{0,60}\bwhich\b[^.;]{0,30}\b(?:may|can)\s+(?:revise|change|increase|modify|vary|alter)"
    r"|\b(prices?|price list|rates?|fees?|charges|tariffs?)\b[^.;]{0,40}\bas (?:revised|amended|changed) (?:by [a-z ]+ )?from time to time")
_MUTUAL_CHANGE = _rx(r"mutual\w*|both parties|agreed in writing|signed by both|with the (?:prior )?(?:written )?consent of the")


def r_unilateral_price(c: RuleContext) -> Optional[RuleFinding]:
    for e in ev.find_all(c.segments, _PRICE_CHANGE, unless=_MUTUAL_CHANGE):
        if not c.empowers_other(e, _POWER_VERB):
            continue
        terms = bool(re.search(r"\b(terms|policies|this agreement)\b", e.quote, re.I)) and not re.search(
            r"\b(price|rate|fee|charge|tariff|rent|commission|margin)", e.quote, re.I)
        what = "the terms" if terms else "prices"
        return RuleFinding(
            rule_id="IN-PRICE-UNILATERAL", category=FindingCategory.unilateral_change, severity=Severity.high,
            title=f"Other side can change {what} on its own",
            why_it_matters=f"They can change {what} without your agreement, so the deal you signed is not the deal you may end up paying for.",
            recommendation="Ask for changes only by written agreement, or at least a cap (e.g. linked to WPI/CPI), 30-60 days' notice and a right to exit without penalty if you do not accept.",
            legal_note="A contract is varied only by consent; a clause that lets one side vary price or terms is enforced as written, but changes beyond what it allows, or applied arbitrarily, can be challenged.",
            legal_ref="Indian Contract Act 1872 ss.10, 29, 62",
            keywords=["revise", "price", "change"],
        ).cite(e)
    return None


# ------------------------------------------------------------------ termination, lock-in, notice

_TERMINATE = _rx(r"terminat\w*|समाप्त")


def r_termination_imbalance(c: RuleContext) -> Optional[RuleFinding]:
    f = c.facts
    if f.termination_notice_days_client is not None or f.termination_notice_days_other is None:
        return None
    e = _in_text(c, f.termination_notice_days_other, _TERMINATE)
    if not e:
        return None
    return RuleFinding(
        rule_id="IN-TERM-ONESIDED", category=FindingCategory.termination, severity=Severity.high,
        title="Only the other side can terminate for convenience",
        why_it_matters="They can walk away on notice, but you have no matching right, so you may be stuck in a deal that no longer works.",
        recommendation="Ask for a mutual right to terminate for convenience with the same notice period.",
        legal_note="Termination rights exist only as written in the contract; a one-sided right is generally enforced as agreed.",
        legal_ref="Indian Contract Act 1872 s.39",
        keywords=["terminat", "notice"],
    ).cite(e)


def r_notice_asymmetry(c: RuleContext) -> Optional[RuleFinding]:
    f = c.facts
    mine, theirs = f.termination_notice_days_client, f.termination_notice_days_other
    if mine is None or theirs is None or theirs <= 0 or mine <= 2 * theirs:
        return None
    e = _in_text(c, mine, _rx(r"notice|नोटिस|सूचना"))
    if not e:
        return None
    return RuleFinding(
        rule_id="IN-NOTICE-ASYM", category=FindingCategory.termination,
        severity=Severity.high if mine >= 4 * theirs else Severity.medium,
        title=f"You must give {mine} days' notice, they give only {theirs}",
        why_it_matters="Exiting costs you far more time than it costs them, so they can leave quickly while you stay bound.",
        recommendation="Ask for the same notice period for both sides.",
        legal_note="Notice periods are enforced as agreed; an unequal period is not unlawful but is a negotiable imbalance.",
        legal_ref="Indian Contract Act 1872 s.39",
        keywords=["notice", "terminat"],
    ).cite(e)


_LOCK_IN = _rx(r"lock[\s-]?in|minimum (?:term|period|tenure)|लॉक[\s-]?इन|न्यूनतम अवधि")
_LOCK_EXIT = _rx(r"(?:may|can|entitled to)\s+(?:terminate|exit|surrender)[^.;]{0,80}(?:during|within|before the (?:end|expiry) of)\s+the\s+lock")


def r_long_lock_in(c: RuleContext) -> Optional[RuleFinding]:
    if c.client_is_employer or c.client_is_creditor:     # an employee bond / tenant lock-in protects the client
        return None
    for e in ev.find_all(c.segments, _LOCK_IN):
        months = max(ev.durations_in_months(e.sentence), default=None)
        if months is None and c.facts.lock_in_months:
            months = float(c.facts.lock_in_months)
        if months is None or months <= 24 or not c.binds_client(e):
            continue
        if ev.find_first(c.segments, _LOCK_EXIT):
            return None
        return RuleFinding(
            rule_id="IN-LOCKIN-24M", category=FindingCategory.lock_in_exclusivity, severity=Severity.high,
            title=f"Locked in for {months:g} months with no way out",
            why_it_matters="You cannot exit during the lock-in even if your business changes, and leaving early usually means paying for the whole remaining period.",
            recommendation="Ask to cut the lock-in to 12 months or less, or for an exit right with a fixed, small compensation (e.g. 1-3 months' fee).",
            legal_note="A lock-in is enforceable as agreed; the sum claimed for leaving early is treated as damages and courts award only reasonable compensation up to the stated amount.",
            legal_ref="Indian Contract Act 1872 ss.73-74",
            keywords=["lock-in", "lock in", "minimum period"],
        ).cite(e)
    return None


_RENEW = _rx(r"renew\w*|नवीनीकरण")
_AUTO = _rx(r"automatic\w*|deemed|stand renewed|unless|shall renew|auto[\s-]?renew|स्वतः")


def r_auto_renewal(c: RuleContext) -> Optional[RuleFinding]:
    f = c.facts
    if f.auto_renewal is not True:
        return None
    e = ev.find_first(c.segments, _RENEW, also=_AUTO)
    if not e:
        return None
    long_notice = f.renewal_notice_days is None or f.renewal_notice_days >= 60
    return RuleFinding(
        rule_id="IN-AUTORENEW", category=FindingCategory.auto_renewal,
        severity=Severity.medium if long_notice else Severity.low,
        title="Renews automatically" + (f" unless you give {f.renewal_notice_days} days' notice" if f.renewal_notice_days else ""),
        why_it_matters="If you miss the notice window you are locked in for another full term.",
        recommendation="Add a calendar reminder for the notice date, and try to shorten the notice period to 30 days or less.",
        legal_note="Renewal and lock-in operate as written; courts generally enforce agreed terms.",
        legal_ref="Indian Contract Act 1872 s.10",
        keywords=["renew", "auto", "term"],
    ).cite(e)


# ------------------------------------------------------------------ money held or taken as security

_DEPOSIT = _rx(r"deposit|जमा|अग्रिम राशि")
_REFUND = _rx(r"refund\w*|return\w*|repa(?:y|id)\w*|वापस")
_NO_INTEREST = _rx(r"interest[\s-]?free|without (?:any )?interest|free of interest|no interest|बिना ब्याज")
_REFUND_PERIOD = ev.duration_after("within|after|beyond|of|in")
_LATE_REFUND_INTEREST = _rx(r"(?:delay|fail\w*)[^.;]{0,80}refund[^.;]{0,80}interest|interest[^.;]{0,60}(?:delay\w*|late)[^.;]{0,40}refund")


def r_deposit_refund(c: RuleContext) -> Optional[RuleFinding]:
    """Deposit refunded late (> 60 days after exit) or, for a big interest-free deposit, with no interest if late."""
    if c.client_is_creditor:
        return None
    slow, free = None, None
    for e in ev.find_all(c.segments, _DEPOSIT):
        if _REFUND.search(e.sentence):
            days = max(ev.durations_in_days(e.sentence, _REFUND_PERIOD), default=None)
            if days is not None and days > 60 and slow is None:
                slow = (days, e)
        if _NO_INTEREST.search(e.sentence) and free is None:
            free = e
    if slow is None and c.facts.deposit_refund_days and c.facts.deposit_refund_days > 60:
        found = _in_text(c, c.facts.deposit_refund_days, _DEPOSIT)
        slow = (float(c.facts.deposit_refund_days), found) if found else None
    no_late_interest = not ev.mentions(c.segments, _LATE_REFUND_INTEREST)
    if slow:
        days, e = slow
        return RuleFinding(
            rule_id="IN-DEPOSIT-REFUND", category=FindingCategory.payment_terms,
            severity=Severity.high if days >= 120 and no_late_interest else Severity.medium,
            title=f"Deposit refunded only {days:g} days after you leave",
            why_it_matters="Your money stays blocked for months after exit" + (", with no interest for the delay." if no_late_interest else "."),
            recommendation="Ask for refund on the day you hand back possession (or within 30 days at most), with 12-18% interest for any delay and the right to stay until it is refunded.",
            legal_note="No statute fixes a refund period for commercial deposits, so the contract governs; a refund withheld beyond it is recoverable as a debt with interest at the court's discretion. Some states' tenancy laws (Model Tenancy Act 2021) require refund at handover.",
            legal_ref="Indian Contract Act 1872 s.73; Interest Act 1978 s.3; Model Tenancy Act 2021 s.11 (where adopted)",
            keywords=["deposit", "refund"],
        ).cite(e)
    if free and no_late_interest and c.facts.contract_type in (ContractType.lease, ContractType.distribution, ContractType.dealership,
                                                                  ContractType.franchise, ContractType.equipment_hire, ContractType.warehousing):
        return RuleFinding(
            rule_id="IN-DEPOSIT-REFUND", category=FindingCategory.payment_terms, severity=Severity.low,
            title="Interest-free deposit with no interest if refunded late",
            why_it_matters="The other side holds your money for free and has no cost if it refunds late.",
            recommendation="Ask for interest on any refund delayed beyond 30 days, or a smaller deposit.",
            legal_note="Interest-free deposits are lawful and common; without a late-refund interest clause, interest for delay depends on the court's discretion.",
            legal_ref="Interest Act 1978 s.3",
            keywords=["deposit", "interest"],
        ).cite(free)
    return None


_ESCALATION = _rx(r"escalat\w*|increase\w*|enhance\w*|revis\w*|hike\w*|बढ़|वृद्धि")
_FEE_WORDS = _rx(r"\b(rent|licen[cs]e fee|fees?|compensation|charges|hire|subscription|price)\b|किराया|शुल्क")
_EVERY = _rx(rf"every\s+{ev.NUM}\s*\)?\s*(?:\(\s*\w+\s*\)\s*)?(months?|years?)|(annual\w*|per annum|each year|every year|yearly|year[\s-]on[\s-]year|on each renewal|प्रति वर्ष|वार्षिक)")


def r_escalation(c: RuleContext) -> Optional[RuleFinding]:
    if not c.profile.recurring_fee or c.client_is_creditor:
        return None
    for e in ev.find_all(c.segments, _ESCALATION, also=_FEE_WORDS):
        pcts = ev.percents(e.sentence)
        every = _EVERY.search(e.sentence)
        if not pcts or not every:
            continue
        years = 1.0                                        # "annually" / "each year" / "on each renewal"
        if every.group(1):
            n = ev.to_number(every.group(1)) or 12
            years = n / 12 if every.group(2).lower().startswith("month") else n
        per_year = round(max(pcts) / years, 1)
        if per_year <= 10:
            continue
        what = "Rent goes" if c.facts.contract_type == ContractType.lease else "Fees go"
        return RuleFinding(
            rule_id="IN-ESCALATION-10", category=FindingCategory.payment_terms,
            severity=Severity.high if per_year >= 15 else Severity.medium,
            title=f"{what} up {per_year:g}% a year",
            why_it_matters=f"At {per_year:g}% a year the cost roughly doubles in {max(1, round(72 / per_year))} years; the market norm is about 5% a year (or 15% every 3 years).",
            recommendation="Ask for 5% a year (or 15% every three years), simple not compounded, and no increase during any lock-in.",
            legal_note="Escalation is a commercial term enforced as agreed; there is no statutory cap for commercial premises or services.",
            legal_ref="Indian Contract Act 1872 s.10",
            condition_note="Calculated from the percentage and interval stated in the clause; check against the schedule of payments.",
            keywords=["escalat", "increase", "rent"],
        ).cite(e)
    if c.facts.escalation_percent_per_year and c.facts.escalation_percent_per_year > 10:
        e = ev.find_first(c.segments, _ESCALATION, also=_rx(r"%|per\s*cent|प्रतिशत"))
        if e:
            pct = c.facts.escalation_percent_per_year
            return RuleFinding(
                rule_id="IN-ESCALATION-10", category=FindingCategory.payment_terms,
                severity=Severity.high if pct >= 15 else Severity.medium,
                title=f"Fees go up about {pct:g}% a year",
                why_it_matters="Year-on-year increases above 10% make the deal much costlier over its life.",
                recommendation="Ask for 5% a year (or 15% every three years), simple not compounded.",
                legal_note="Escalation is a commercial term enforced as agreed.", legal_ref="Indian Contract Act 1872 s.10",
                keywords=["escalat", "increase"],
            ).cite(e)
    return None


_GUARANTEE = _rx(
    r"personal(?:ly)?\s+guarant\w*|guarant\w*[^.;]{0,100}\b(directors?|promoters?|partners?|proprietors?|spouses?)\b"
    r"|\b(directors?|promoters?|partners?|proprietors?)\b[^.;]{0,100}\bguarant\w*|व्यक्तिगत गारंटी")


def r_personal_guarantee(c: RuleContext) -> Optional[RuleFinding]:
    if c.client_is_creditor:
        return None
    e = ev.find_first(c.segments, _GUARANTEE, unless=_rx(r"\bno personal guarantee|without (?:any )?personal guarantee"))
    if not e:
        return None
    return RuleFinding(
        rule_id="IN-PERSONAL-GUARANTEE", category=FindingCategory.liability_indemnity, severity=Severity.critical,
        title="Director / owner must give a personal guarantee",
        why_it_matters="If the business cannot pay, the guarantor's personal savings, house and other assets can be pursued, and the guarantor can face personal insolvency proceedings.",
        recommendation="Avoid it, or cap it at a fixed amount and period, make it non-continuing, and require release on repayment or exit.",
        legal_note="A surety's liability is co-extensive with the borrower's unless the guarantee limits it, and the creditor may proceed against the guarantor without first suing the borrower. Personal guarantors to companies can be taken through insolvency under the IBC.",
        legal_ref="Indian Contract Act 1872 ss.126-128; IBC 2016 Part III; Lalit Kumar Jain v Union of India (2021)",
        keywords=["guarantee", "director"],
    ).cite(e)


_CHEQUE = _rx(
    r"blank\s+cheques?|undated\s+cheques?|un-dated\s+cheques?|security\s+cheques?|cheques?[^.;]{0,200}\b(?:left\s+)?blank\b"
    r"|cheques?[^.;]{0,100}\b(?:as|by way of|towards|for)\s+(?:collateral\s+)?security|post[\s-]?dated\s+cheques?[^.;]{0,100}security"
    r"|खाली चेक|सुरक्षा चेक")


def r_security_cheques(c: RuleContext) -> Optional[RuleFinding]:
    if c.client_is_creditor or c.client_is_seller:
        return None
    e = ev.find_first(c.segments, _CHEQUE)
    if not e:
        return None
    blank = bool(re.search(r"blank|undated|un-dated|खाली", e.sentence, re.I))
    return RuleFinding(
        rule_id="IN-SECURITY-CHEQUE", category=FindingCategory.liability_indemnity,
        severity=Severity.high if blank else Severity.medium,
        title="Blank or undated cheques given as security" if blank else "Cheques given as security",
        why_it_matters="The other side can fill in an amount and date and present the cheque; if it bounces you face a criminal complaint for cheque dishonour, even if the amount is disputed.",
        recommendation="Avoid blank cheques. If security cheques are unavoidable, fix the amount and date, list them by number, and require their return on repayment or exit.",
        legal_note="A signed blank cheque authorises the holder to complete it; a security cheque presented when a debt is due can attract cheque-bounce prosecution.",
        legal_ref="Negotiable Instruments Act 1881 ss.20, 138; Sripati Singh v State of Jharkhand (2021)",
        keywords=["cheque"],
    ).cite(e)


_MANDATE = _rx(r"\b(ecs|nach|e-?mandate|auto[\s-]?debit|standing instructions?|electronic clearing|debit mandate|direct debit|si mandate)\b|ऑटो[\s-]?डेबिट")
_MANDATE_CAP = _rx(r"maximum|not exceed|up to|upto|capped|limit(?:ed)? to|ceiling|अधिकतम")
_ANY_DUES = _rx(r"any (?:amounts?|sums?|dues|charges|monies)|all (?:amounts?|sums?|dues|monies|charges)|outstanding|charges|penal|as (?:may be )?determined by|it considers due")


def r_auto_debit(c: RuleContext) -> Optional[RuleFinding]:
    if c.client_is_creditor or c.client_is_seller:
        return None
    for e in ev.find_all(c.segments, _MANDATE, unless=_MANDATE_CAP):
        has_fixed_amount = bool(re.search(r"(?:rs\.?|inr|₹)\s*[\d,]+", e.sentence, re.I))
        if has_fixed_amount and not _ANY_DUES.search(e.sentence):
            continue                      # a mandate for a stated EMI is normal
        return RuleFinding(
            rule_id="IN-AUTODEBIT-NOCAP", category=FindingCategory.payment_terms, severity=Severity.medium,
            title="Auto-debit mandate with no maximum amount",
            why_it_matters="The other side can pull money from your bank account for whatever it says is due, including disputed charges, and you find out after it is gone.",
            recommendation="Limit the mandate to the fixed instalment amount with a stated maximum and end date, and require prior notice of every debit.",
            legal_note="RBI's e-mandate framework requires a pre-debit notification and lets you set a maximum amount and cancel the mandate; NACH mandates carry a maximum amount.",
            legal_ref="RBI e-mandate framework for recurring transactions (2019, as amended); NPCI NACH procedural guidelines",
            keywords=["mandate", "debit", "nach", "ecs"],
        ).cite(e)
    return None


_ORIGINALS = _rx(r"\boriginals?\b[^.;]{0,80}\b(certificates?|documents?|title deeds?|degree|mark\s?sheets?|testimonials|registration certificate|rc book|passport)|मूल\s+(?:प्रमाण|दस्तावेज)")


def r_original_documents(c: RuleContext) -> Optional[RuleFinding]:
    e = ev.find_first(c.segments, _ORIGINALS, also=_rx(r"retain\w*|custody|keep|hold|lodge\w*|deposit\w*|जमा"))
    if not e:
        return None
    if c.facts.contract_type == ContractType.employment:
        return RuleFinding(
            rule_id="IN-ORIGINAL-DOCS", category=FindingCategory.other, severity=Severity.medium,
            title="Employer keeps the employee's original certificates",
            why_it_matters="Holding an employee's original certificates to stop them leaving is treated by courts as coercive; you can be ordered to return them, and it invites labour complaints.",
            recommendation="Verify originals and return them the same day; keep self-attested copies only.",
            legal_note="Courts have ordered employers to return withheld original certificates; retention cannot lawfully enforce a bond or notice period, and post-employment restraints are void.",
            legal_ref="Indian Contract Act 1872 ss.23, 27 (High Court rulings on withheld certificates)",
            keywords=["original", "certificate"],
        ).cite(e)
    if c.client_is_creditor:              # whoever holds them, the documents at stake are the client's
        return None
    lending = c.profile.lending
    return RuleFinding(
        rule_id="IN-ORIGINAL-DOCS", category=FindingCategory.other, severity=Severity.low if lending else Severity.medium,
        title="Your original documents are kept by the other side",
        why_it_matters="Without a fixed return date you may struggle to get title deeds or certificates back after you pay or exit, which blocks sale or fresh borrowing.",
        recommendation="List the documents in a schedule and require their return within 30 days of repayment or termination, with compensation for delay.",
        legal_note=("Lenders must release original property documents within 30 days of full repayment and pay Rs 5,000 per day of delay."
                    if lending else "Documents handed over are held in trust and must be returned when the purpose ends."),
        legal_ref=("RBI circular on release of movable/immovable property documents (13 Sep 2023)"
                   if lending else "Indian Contract Act 1872 ss.148, 160 (bailment)"),
        keywords=["original", "documents"],
    ).cite(e)


# ------------------------------------------------------------------ restraints, penalties, assignment

_NON_COMPETE = _rx(
    r"non[\s-]?compet\w*|shall not[^.;]{0,200}?\b(compet\w*|engage\w*|carry on|be (?:employed|engaged|concerned|interested|associated)|"
    r"associated with|join\w*|deal in|distribute|market|work for|provide services to)\b|प्रतिस्पर्धा")
_AFTER_END = _rx(
    r"\b(after|following|post|subsequent to|from the date of)\b[^.;]{0,60}\b(terminat\w*|expir\w*|cessation|leaving|resignation|"
    r"end|exit|separation|relieving)\b|\bthereafter\b|after (?:the )?(?:term|employment)|के बाद")


def r_post_term_non_compete(c: RuleContext) -> Optional[RuleFinding]:
    e = ev.find_first(c.segments, _NON_COMPETE, also=_AFTER_END)
    if not e:
        return None
    note = ("Agreements in restraint of trade are void to that extent, so a non-compete that continues after the contract or "
            "employment ends is generally unenforceable; restrictions during the term are usually valid.")
    ref = "Indian Contract Act 1872 s.27; Percept D'Mark v Zaheer Khan (2006)"
    if c.client_is_employer or (c.client_known and c.actor(e) == "other"):
        return RuleFinding(
            rule_id="IN-NONCOMPETE-POST", category=FindingCategory.non_compete, severity=Severity.low,
            title="Your post-exit non-compete is unlikely to be enforceable",
            why_it_matters="You may be relying on a restriction a court will not enforce; protect yourself with confidentiality and non-solicit terms instead.",
            recommendation="Keep the restriction to the term of the contract and rely on confidentiality, IP and non-solicitation clauses after exit.",
            legal_note=note, legal_ref=ref, keywords=["compet", "after"],
        ).cite(e)
    partnership = c.facts.contract_type in (ContractType.partnership, ContractType.shareholder_agreement)
    return RuleFinding(
        rule_id="IN-NONCOMPETE-POST", category=FindingCategory.non_compete,
        severity=Severity.medium if partnership else Severity.high,
        title="Non-compete continues after the contract ends",
        why_it_matters="It tries to stop you doing similar business after the relationship ends, and can be used to threaten you with litigation even if it is weak in law.",
        recommendation="Limit the restriction to the term of the contract; after exit accept only confidentiality and non-solicitation of their customers or staff.",
        legal_note=note, legal_ref=ref,
        condition_note=("Partners and sellers of goodwill can agree reasonable post-exit restraints (Partnership Act ss.11, 36, 54; "
                        "Contract Act s.27 exception)." if partnership else None),
        keywords=["compet", "after"],
    ).cite(e)


_PENALTY = _rx(r"\bpenalt(?:y|ies)\b|liquidated damages|pre[\s-]?estimate|agreed compensation|forfeit\w*|जुर्माना|दंड|हर्जाना")
_LARGE_SUM = _rx(r"\btimes\b|entire|whole|unexpired|annual\s+(?:ctc|salary|fee)|\bctc\b|irrespective of (?:whether|any) loss|without proof")


def r_penalty_clause(c: RuleContext) -> Optional[RuleFinding]:
    best = None
    for e in ev.find_all(c.segments, _PENALTY):
        if re.search(r"\binterest\b", e.sentence, re.I) and not re.search(r"liquidated|penalty|forfeit", e.sentence, re.I):
            continue                      # default interest is the interest rule's job
        if not c.binds_client(e, _PAY_VERB):
            continue
        big = bool(_LARGE_SUM.search(e.sentence)) or any(p >= 10 for p in ev.percents(e.sentence))
        if best is None or (big and not best[0]):
            best = (big, e)
    if not best:
        return None
    big, e = best
    return RuleFinding(
        rule_id="IN-PENALTY-S74", category=FindingCategory.penalty_damages, severity=Severity.high if big else Severity.medium,
        title="Heavy fixed penalty / liquidated damages" if big else "Fixed penalty or liquidated damages",
        why_it_matters="You agree in advance to pay a fixed sum on breach, often far more than any real loss, and it will be used as leverage in any dispute.",
        recommendation="Cap liquidated damages (e.g. 0.5% per week, maximum 5-10% of the value), make them the sole remedy, and remove 'irrespective of loss' language.",
        legal_note="Whether called a penalty or liquidated damages, a court awards only reasonable compensation not exceeding the stated sum, and the claimant must generally show some loss unless it is impossible to prove.",
        legal_ref="Indian Contract Act 1872 s.74; Kailash Nath Associates v DDA (2015)",
        keywords=["penalty", "liquidated", "damages"],
    ).cite(e)


_ASSIGN = _rx(
    r"\b(may|can|shall be (?:entitled|free) to|is (?:entitled|free) to)\b[^.;]{0,30}?\b(assign|novate|transfer|securiti[sz]e)\w*\b"
    r"[^.;]{0,160}?\b(without|no need (?:for|of)|not require)\b[^.;]{0,40}?\b(consent|approval|notice|reference)\b"
    r"|\bfree to assign\b")


def r_assignment(c: RuleContext) -> Optional[RuleFinding]:
    for e in ev.find_all(c.segments, _ASSIGN):
        if not c.empowers_other(e, _POWER_VERB):
            continue
        return RuleFinding(
            rule_id="IN-ASSIGN-NOCONSENT", category=FindingCategory.assignment_subcontract, severity=Severity.medium,
            title="Other side can transfer the contract without your consent",
            why_it_matters="You could end up dealing with a stranger (a buyer, a collection agency or a competitor) with the same rights against you.",
            recommendation="Require your prior written consent, or at least notice, and limit transfers to group companies or a buyer of the whole business; keep your rights against the original party.",
            legal_note="Rights (benefits) can generally be assigned, but obligations cannot be transferred without the other party's consent; a clause allowing free transfer of the whole contract is enforced as written.",
            legal_ref="Indian Contract Act 1872 ss.37, 40-41, 62; Khardah Co v Raymond & Co (1962)",
            keywords=["assign", "transfer"],
        ).cite(e)
    return None


# ------------------------------------------------------------------ disputes

_DISPUTE = _rx(r"arbitrat\w*|jurisdiction|courts?\s+(?:at|of|in)\b|\bseat\b|\bvenue\b|मध्यस्थ|न्यायालय|क्षेत्राधिकार")
_GOVERNING = _rx(r"govern\w*|jurisdiction|courts?\s+(?:at|of|in)\b|न्यायालय|क्षेत्राधिकार")
_SEAT = _rx(r"\bseat\b|\bvenue\b|place of arbitration|arbitrat\w*|स्थान")


def r_foreign_law(c: RuleContext) -> Optional[RuleFinding]:
    m = _FOREIGN.search(f"{c.facts.governing_law or ''} | {c.facts.jurisdiction or ''}")
    if not m:
        return None
    e = ev.find_first(c.segments, re.compile(re.escape(m.group(0)), re.I), also=_GOVERNING)
    if not e:
        return None
    return RuleFinding(
        rule_id="IN-FOREIGN-LAW", category=FindingCategory.dispute_resolution, severity=Severity.medium,
        title="Foreign governing law or courts",
        why_it_matters="Disputes would be decided under foreign law and/or in foreign courts, which is slower and far costlier for an Indian SME to fight.",
        recommendation="Ask for Indian law and Indian courts (or arbitration seated in India).",
        legal_note="Foreign courts follow their own law and procedure; a foreign decree is enforceable in India only if it is from a reciprocating territory, otherwise a fresh suit is needed.",
        legal_ref="Code of Civil Procedure 1908 ss.13, 44A",
        keywords=["governing law", "jurisdiction"],
    ).cite(e)


def r_arbitration_seat_abroad(c: RuleContext) -> Optional[RuleFinding]:
    seat = c.facts.arbitration_seat or ""
    e = None
    if _FOREIGN.search(seat):
        e = ev.find_first(c.segments, _FOREIGN, also=_SEAT)
    if e is None:
        e = ev.find_first(c.segments, _rx(r"\b(?:seat|venue|place) (?:and venue )?of (?:the )?arbitration\b|\barbitration\b[^.;]{0,80}\b(?:seated|held) (?:in|at)\b"),
                          also=_FOREIGN)
        if e is None:
            return None
    return RuleFinding(
        rule_id="IN-ARB-SEAT-ABROAD", category=FindingCategory.dispute_resolution, severity=Severity.high,
        title="Arbitration would take place abroad",
        why_it_matters="Foreign institutional arbitration typically costs tens of lakhs in fees, travel and foreign counsel, which can make even a valid claim not worth pursuing.",
        recommendation="Ask for arbitration seated in your city in India (e.g. under MCIA/ICA/DIAC rules) with a sole arbitrator.",
        legal_note="With a foreign seat, Indian courts cannot set aside the award; it is enforced in India as a foreign award under Part II. Two Indian parties may validly choose a foreign seat.",
        legal_ref="Arbitration and Conciliation Act 1996 Part II (ss.44-48); BALCO v Kaiser (2012); PASL Wind v GE Power (2021)",
        keywords=["arbitration", "seat"],
    ).cite(e)


def r_no_dispute_clause(c: RuleContext) -> Optional[RuleFinding]:
    f = c.facts
    if not c.complete or f.governing_law or f.jurisdiction or f.dispute_mechanism not in (None, DisputeMechanism.none):
        return None
    if ev.mentions(c.segments, _rx(r"arbitrat\w*|jurisdiction|governed by|governing law|courts? (?:at|of|in)|मध्यस्थ|न्यायालय|क्षेत्राधिकार")):
        return None
    return RuleFinding(
        rule_id="IN-NO-DISPUTE", category=FindingCategory.dispute_resolution, severity=Severity.medium,
        title="No governing law or dispute-resolution clause found",
        why_it_matters="Without an agreed law, venue or process, a dispute starts with an argument about where and how to fight it.",
        recommendation="Add: governing law (Laws of India), exclusive jurisdiction of courts at your city, or arbitration with a named seat and a mutually appointed arbitrator.",
        legal_note="Parties may choose forum and process; silence leaves it to default territorial jurisdiction rules.",
        legal_ref="Arbitration and Conciliation Act 1996; Code of Civil Procedure 1908 ss.16-20",
        keywords=["dispute", "law", "court"],
    )


# Cities that commonly appear in jurisdiction clauses -> GST state code.
_CITY_STATE = {
    "mumbai": "27", "pune": "27", "nagpur": "27", "thane": "27", "nashik": "27", "aurangabad": "27",
    "delhi": "07", "new delhi": "07", "gurugram": "06", "gurgaon": "06", "faridabad": "06", "noida": "09",
    "ghaziabad": "09", "lucknow": "09", "kanpur": "09", "agra": "09", "varanasi": "09",
    "bengaluru": "29", "bangalore": "29", "mysuru": "29", "mysore": "29", "mangaluru": "29",
    "chennai": "33", "coimbatore": "33", "madurai": "33", "tiruppur": "33", "hyderabad": "36", "secunderabad": "36",
    "kolkata": "19", "howrah": "19", "ahmedabad": "24", "surat": "24", "vadodara": "24", "rajkot": "24",
    "gandhinagar": "24", "jaipur": "08", "jodhpur": "08", "udaipur": "08", "indore": "23", "bhopal": "23",
    "chandigarh": "04", "ludhiana": "03", "amritsar": "03", "jalandhar": "03", "kochi": "32", "ernakulam": "32",
    "thiruvananthapuram": "32", "patna": "10", "bhubaneswar": "21", "cuttack": "21", "guwahati": "18",
    "visakhapatnam": "37", "vijayawada": "37", "panaji": "30", "goa": "30", "raipur": "22", "ranchi": "20",
    "jamshedpur": "20", "dehradun": "05", "shimla": "02", "jammu": "01", "srinagar": "01",
}


def _state_of(place: str) -> Optional[str]:
    low = place.lower()
    for code, name in STATE_CODES.items():
        if re.search(rf"\b{re.escape(name.lower())}\b", low):
            return code
    for city, code in sorted(_CITY_STATE.items(), key=lambda kv: -len(kv[0])):
        if re.search(rf"\b{re.escape(city)}\b", low):
            return code
    return None


def r_jurisdiction_out_of_state(c: RuleContext) -> Optional[RuleFinding]:
    """Courts/seat in another state, when the SME is the weaker side (it would have to travel to fight)."""
    home = (c.org.state_code if c.org else None) or ""
    if home not in STATE_CODES or not c.client_known or c.client_is_creditor or c.client_is_employer:
        return None
    place = " ".join(x for x in (c.facts.jurisdiction, c.facts.arbitration_seat) if x)
    code = _state_of(place) if place and not _FOREIGN.search(place) else None
    if code is None or code == home:
        return None
    city = next((k for k in sorted(_CITY_STATE, key=len, reverse=True) if re.search(rf"\b{k}\b", place.lower())), None)
    word = city or STATE_CODES[code].lower()
    e = ev.find_first(c.segments, re.compile(rf"\b{re.escape(word)}\b", re.I), also=_DISPUTE)
    if not e:
        return None
    return RuleFinding(
        rule_id="IN-JURIS-OUT-OF-STATE", category=FindingCategory.dispute_resolution, severity=Severity.medium,
        title=f"Disputes must be fought in {STATE_CODES[code]}, not {STATE_CODES[home]}",
        why_it_matters="Every hearing means travel and an out-of-state lawyer, which raises the cost of enforcing your rights and makes settling on their terms more likely.",
        recommendation=f"Ask for courts (or an arbitration seat) in your own city in {STATE_CODES[home]}, or at least a neutral online/hybrid arbitration.",
        legal_note="Parties may confine disputes to one of the courts that has jurisdiction, and such exclusive-jurisdiction clauses are generally enforced.",
        legal_ref="Code of Civil Procedure 1908 s.20; Swastik Gases v Indian Oil (2013)",
        condition_note="Based on your organisation's registered state in Settings.",
        keywords=["jurisdiction", "court"],
    ).cite(e)


# ------------------------------------------------------------------ absence: cap, stamp, GST

_LIABILITY = _rx(r"indemnif\w*|liabilit\w*|liable|क्षतिपूर्ति|दायित्व")
_CAP = _rx(r"(?:aggregate|total|maximum|cumulative|entire)\s+liability|liabilit\w*[^.;]{0,100}\b(?:shall not exceed|not exceed|limited to|capped|cap of|restricted to|in no event exceed)|दायित्व[^।]{0,80}सीमित")


def r_uncapped_liability(c: RuleContext) -> Optional[RuleFinding]:
    if not c.complete or c.facts.liability_cap_present is not False or not c.profile.liability_cap_expected:
        return None
    if ev.mentions(c.segments, _CAP):
        return None
    return RuleFinding(
        rule_id="IN-LIAB-NOCAP", category=FindingCategory.liability_indemnity, severity=Severity.high,
        title="No cap on liability",
        why_it_matters="The contract does not limit how much you could owe if something goes wrong, so a single dispute could exceed the value of the deal.",
        recommendation="Ask for a cap, commonly the fees paid or payable in the previous 12 months, with carve-outs only for fraud and wilful misconduct.",
        legal_note="Indian law lets a party recover proven loss caused by breach; without a contractual cap the exposure is not limited by the deal value.",
        legal_ref="Indian Contract Act 1872 s.73",
        keywords=["liab", "indemn", "damages"],
    ).cite(ev.find_first(c.segments, _LIABILITY))


def r_stamp_duty(c: RuleContext) -> Optional[RuleFinding]:
    f = c.facts
    sev = c.profile.stamp
    if not c.complete or not sev or f.stamp_duty_mentioned is True:
        return None
    if f.stamp_duty_mentioned is None and not c.segments:
        return None
    if ev.mentions(c.segments, _rx(r"stamp|e-stamp|sub-registrar|registration act|स्टाम्प|स्टांप|मुद्रांक")):
        return None
    return RuleFinding(
        rule_id="IN-STAMP", category=FindingCategory.stamp_execution, severity=Severity(sev),
        title="No reference to stamp duty",
        why_it_matters="An insufficiently stamped agreement can be refused as evidence in court until duty and a penalty are paid. Leases beyond 11 months generally also need registration.",
        recommendation="Execute on the correct stamp paper for your state (or e-stamp) before signing; confirm whether registration is required.",
        legal_note="Instruments not duly stamped are inadmissible in evidence until duty and penalty are paid; stamp duty rates are state-specific.",
        legal_ref="Indian Stamp Act 1899 s.35 and state stamp laws; Registration Act 1908 s.17",
        condition_note="Duty and registration rules differ by state - confirm locally.",
        keywords=["stamp", "execut", "witness"],
    )


_GST = _rx(r"\b(gst|goods and services tax|igst|cgst|sgst|utgst)\b|inclusive of (?:all )?(?:applicable )?taxes|exclusive of (?:all )?(?:applicable )?taxes|plus (?:applicable )?taxes|taxes (?:as )?applicable|जीएसटी|माल और सेवा कर")
_PRICE = _rx(r"\b(price|rate|fees?|consideration|rent|charges|amount payable|invoice)\b|मूल्य|किराया|शुल्क")


def r_no_gst_clause(c: RuleContext) -> Optional[RuleFinding]:
    if not c.complete or not c.profile.taxable_supply or not c.segments or ev.mentions(c.segments, _GST):
        return None
    anchor = ev.find_first(c.segments, _PRICE)
    if anchor is None:
        return None
    return RuleFinding(
        rule_id="IN-NO-GST", category=FindingCategory.payment_terms, severity=Severity.medium,
        title="Price is silent on GST",
        why_it_matters="It is unclear whether the price includes GST. The supplier may add 18% on top, or (if you are the supplier) you may have to pay the tax out of your price.",
        recommendation="State whether amounts are exclusive of GST (charged extra on a valid tax invoice) and require the supplier to file returns so input tax credit is available.",
        legal_note="GST is payable on the transaction value; input tax credit is available to the recipient only on a valid tax invoice and if the supplier has filed and paid the tax.",
        legal_ref="CGST Act 2017 ss.15, 16, 31",
        condition_note="Residential leases and some exempt supplies carry no GST.",
        keywords=["price", "payment"],
    ).cite(anchor)


RULES: List[Rule] = [
    r_msme_payment_buyer, r_msme_seller_rights, r_high_interest, r_unilateral_price, r_termination_imbalance,
    r_notice_asymmetry, r_long_lock_in, r_auto_renewal, r_deposit_refund, r_escalation, r_personal_guarantee,
    r_security_cheques, r_auto_debit, r_original_documents, r_post_term_non_compete, r_penalty_clause, r_assignment,
    r_foreign_law, r_arbitration_seat_abroad, r_no_dispute_clause, r_jurisdiction_out_of_state, r_uncapped_liability,
    r_stamp_duty, r_no_gst_clause,
]
ABSENCE_RULES = {"IN-LIAB-NOCAP", "IN-NO-DISPUTE", "IN-STAMP", "IN-NO-GST"}


def run_rules(facts: ContractFacts, org: Optional[OrgProfile], segments: List[Segment],
              complete: bool = True) -> List[RuleFinding]:
    ctx = RuleContext(facts=facts, org=org, segments=segments, complete=complete)
    return [res for rule in RULES if (res := rule(ctx))]


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
        "ref": "Arbitration and Conciliation Act 1996 ss.11-12; Perkins Eastman v HSCC (2019)",
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
    FindingCategory.unilateral_change: {
        "note": "A contract is varied only by consent; a unilateral-variation clause is enforced as written but cannot be used arbitrarily.",
        "ref": "Indian Contract Act 1872 ss.10, 62",
    },
    FindingCategory.assignment_subcontract: {
        "note": "Benefits under a contract can generally be assigned; obligations cannot be transferred without the other party's consent.",
        "ref": "Indian Contract Act 1872 ss.37, 40-41",
    },
    FindingCategory.lock_in_exclusivity: {
        "note": "Lock-ins and exclusivity during the term are generally enforceable; compensation for early exit is limited to reasonable compensation up to the stated sum.",
        "ref": "Indian Contract Act 1872 ss.27, 74",
    },
    FindingCategory.termination: {
        "note": "Termination rights exist only as written; a contract terminable at will can usually be ended on its notice period without damages beyond it.",
        "ref": "Indian Contract Act 1872 s.39; Specific Relief Act 1963 s.14",
    },
}
