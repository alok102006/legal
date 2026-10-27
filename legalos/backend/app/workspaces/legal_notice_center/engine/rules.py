"""Deterministic notice rules: response deadline, urgency, statutory windows and law notes.

The AI reads the notice; these rules decide the date arithmetic and the urgency, so they are explainable
and testable. Every statutory window and law note carries its source. Legal notes are general information
marked "confirm with a lawyer". A deadline is never invented:

  stated            the notice itself gives a date or a number of days (verified when the quote is found in the text)
  statutory_default the notice states nothing, and a rule below gives a window for this notice type (cited)
  unknown           neither - the UI says so and asks the user to check the notice
"""
from dataclasses import dataclass
from datetime import date, timedelta
from typing import NamedTuple, Optional

from app.workspaces.legal_notice_center.engine.schemas import NoticeFacts, NoticeType

RULES_VERSION = "2026-10-27.2"

TYPE_LABELS = {
    NoticeType.cheque_bounce: "Cheque bounce notice",
    NoticeType.legal_demand: "Payment demand / recovery notice",
    NoticeType.gst_notice: "GST notice",
    NoticeType.income_tax_notice: "Income tax notice",
    NoticeType.labour_notice: "Labour / PF / ESI notice",
    NoticeType.msme_delayed_payment: "MSME delayed-payment notice",
    NoticeType.consumer_complaint: "Consumer complaint",
    NoticeType.ip_notice: "Trademark / IP notice",
    NoticeType.employment_dispute: "Employee claim",
    NoticeType.tenancy_notice: "Rent / eviction notice",
    NoticeType.court_summons: "Court summons",
    NoticeType.defamation: "Defamation notice",
    NoticeType.contract_breach: "Contract breach notice",
    NoticeType.regulatory_other: "Regulatory notice",
    NoticeType.other: "Other notice",
}


# ---------------------------------------------------------------- statutory reply windows

@dataclass(frozen=True)
class StatutoryWindow:
    days: int
    anchor: str          # what the days count from: "receipt"
    citation: str        # the section that gives the window
    note: str            # one line shown to the user


# Used ONLY when the notice itself states no deadline. Add a type here only when the statute fixes the window.
STATUTORY_WINDOWS = {
    NoticeType.cheque_bounce: StatutoryWindow(
        15, "receipt", "Negotiable Instruments Act 1881, s.138(b)-(c)",
        "The drawer has 15 days from receiving the demand notice to pay the cheque amount."),
    NoticeType.consumer_complaint: StatutoryWindow(
        30, "receipt", "Consumer Protection Act 2019, s.38(2)(a)",
        "The written version is due within 30 days of receiving the complaint; the Commission may allow up to 15 more days."),
}

# Windows that exist in law but depend on the notice (so we only mention them, never use them as a deadline).
# GST show-cause notices commonly allow 30 days (CGST Rules r.142, r.99 for scrutiny), income-tax notices fix a date
# (Income-tax Act 1961 s.142(1), s.148A(b): 7 to 30 days as specified in the notice) - the notice states it.


class LegalNote(NamedTuple):
    text: str            # 2-3 lines in plain English: what the law generally says
    ref: str             # section + act cited (the "source")
    if_ignored: str      # what generally happens if the notice is ignored


LEGAL_NOTES = {
    NoticeType.cheque_bounce: LegalNote(
        "A cheque that bounces for insufficient funds is a criminal offence if the drawer does not pay within 15 days of receiving the sender's "
        "demand notice. The sender must have issued the notice within 30 days of the bank's return memo. After the 15 days, they have one month to file a complaint.",
        "Negotiable Instruments Act 1881, ss.138 and 142",
        "The sender can file a criminal complaint. The penalty can be up to 2 years in jail, a fine up to twice the cheque amount, or both."),
    NoticeType.legal_demand: LegalNote(
        "A demand notice is not a court order. It is the step before a recovery suit, and the reply you send is read by the court later. Reply in writing "
        "within the time it states, and do not admit what you do not accept.",
        "Indian Contract Act 1872; Code of Civil Procedure 1908; Limitation Act 1963",
        "The sender can file a civil recovery suit for the amount with interest and costs."),
    NoticeType.gst_notice: LegalNote(
        "A show-cause notice asks you to explain a tax demand or mismatch with documents. Replying on the GST portal within the stated time lets the officer "
        "consider your side. Paying the tax and interest within 30 days of a show-cause notice can reduce or remove the penalty. "
        "For FY 2024-25 onward the same scheme sits in s.74A.",
        "CGST Act 2017, ss.73, 74 (s.74A from FY 2024-25)",
        "The officer can pass an order confirming the demand with interest and penalty, without hearing you. You would then have to appeal, and recovery can start."),
    NoticeType.income_tax_notice: LegalNote(
        "Reply on the income-tax e-filing portal by the date in the notice, with supporting documents. The section named in the notice tells you whether this is an "
        "inquiry (s.142(1)), a scrutiny (s.143(2)) or a reassessment (s.148 / 148A).",
        "Income-tax Act 1961, ss.142(1), 143(2), 148, 148A, 144",
        "The officer can assess your income on their own estimate (best-judgment assessment) and levy a penalty for not complying with the notice."),
    NoticeType.labour_notice: LegalNote(
        "PF and ESI authorities can inquire into unpaid or late contributions and call you to a hearing. Bring proof of contributions paid (challans, returns). "
        "Late payment carries interest and damages.",
        "EPF Act 1952, ss.7A, 7Q, 14B; ESI Act 1948, s.45A",
        "The authority can decide the dues without your records, add interest and damages, and recover them from your bank account."),
    NoticeType.msme_delayed_payment: LegalNote(
        "A buyer must pay a registered micro or small supplier by the agreed date, and in any case within 45 days of acceptance of the goods. "
        "Beyond that, compound interest at three times the RBI bank rate runs, and the supplier can approach the MSE Facilitation Council.",
        "MSMED Act 2006, ss.15, 16, 18, 19",
        "Interest keeps adding up, and the Council can pass an award. To challenge an award you must first deposit 75% of it."),
    NoticeType.consumer_complaint: LegalNote(
        "If a consumer complaint is filed against you, you must file your written version within 30 days of receiving it. The Commission can allow up to 15 more days, "
        "and no more.",
        "Consumer Protection Act 2019, s.38",
        "The Commission can decide the case on the complainant's version alone, which can mean a refund, compensation and costs."),
    NoticeType.ip_notice: LegalNote(
        "A cease-and-desist letter claims you are using a mark, name or content that belongs to the sender. The law has no fixed reply time, but a court can grant "
        "a quick injunction, so a prompt written reply matters.",
        "Trade Marks Act 1999, ss.29, 134, 135; Copyright Act 1957, ss.51, 55",
        "The sender can sue for an injunction (stopping your use), damages and an account of profits, sometimes with an interim order before you are heard."),
    NoticeType.employment_dispute: LegalNote(
        "An employee's claim (wages, dues, gratuity, termination) is usually decided by a labour authority or court. Keep the appointment letter, attendance, "
        "salary records and the termination papers ready.",
        "Industrial Disputes Act 1947 / Industrial Relations Code 2020; Payment of Gratuity Act 1972; Payment of Wages Act 1936 / Code on Wages 2019",
        "The employee can raise a dispute before the labour authority or file a claim, and the dues can grow with interest."),
    NoticeType.tenancy_notice: LegalNote(
        "A landlord can end a monthly tenancy with a 15-day notice, but a tenant cannot be thrown out without a court order. Rent-control laws of your state may "
        "give extra protection. Keep rent receipts and the rent agreement ready.",
        "Transfer of Property Act 1882, ss.106, 111; the state Rent Control Act",
        "The landlord can file an eviction suit and claim arrears of rent with interest."),
    NoticeType.court_summons: LegalNote(
        "A summons orders you to appear (yourself or through a lawyer) on the date it states. Engage a lawyer straight away: in a civil suit your written statement "
        "is generally due within 30 days of service, and a missed date can end in a one-sided order.",
        "Code of Civil Procedure 1908, Order V and Order VIII rule 1",
        "The court can proceed without you and pass an ex-parte order or decree."),
    NoticeType.defamation: LegalNote(
        "A defamation notice says something you said or published harmed the sender's reputation, and usually demands a take-down and an apology. "
        "Do not repeat the statement and do not delete evidence before a lawyer has seen it.",
        "Bharatiya Nyaya Sanhita 2023, s.356 (earlier IPC ss.499-500); civil law of defamation",
        "The sender can file a civil suit for damages and an injunction, and a criminal complaint."),
    NoticeType.contract_breach: LegalNote(
        "A breach notice says you did not do what a contract required and asks you to fix it or pay compensation. Check the contract's notice, cure and "
        "arbitration clauses before replying.",
        "Indian Contract Act 1872, ss.73, 74; Specific Relief Act 1963; Arbitration and Conciliation Act 1996",
        "The sender can end the contract, claim damages or the agreed penalty, and start arbitration or a suit."),
}


@dataclass
class Deadline:
    due: Optional[date]
    source: str                 # stated | statutory_default | unknown
    days: Optional[int]
    note: str
    anchor: Optional[str] = None   # explicit | receipt | notice_date | None - what the date was counted from


def parse_iso(value: Optional[str]) -> Optional[date]:
    if not value:
        return None
    try:
        return date.fromisoformat(value.strip()[:10])
    except ValueError:
        return None


def _fmt(d: date) -> str:
    return d.strftime("%d %b %Y").lstrip("0")


def compute_deadline(facts: NoticeFacts, received: date) -> Deadline:
    stated = parse_iso(facts.response_deadline_date)
    if stated:
        return Deadline(stated, "stated", (stated - received).days, "The notice states this date.", "explicit")
    if facts.response_days:
        n = facts.response_days
        notice_dt = parse_iso(facts.notice_date)
        if facts.response_days_from == "notice_date" and notice_dt:
            return Deadline(notice_dt + timedelta(days=n), "stated", n,
                            f"The notice gives {n} days from its own date ({_fmt(notice_dt)}).", "notice_date")
        return Deadline(received + timedelta(days=n), "stated", n,
                        f"The notice gives {n} days. Counted from the day you received it ({_fmt(received)}).", "receipt")
    window = STATUTORY_WINDOWS.get(facts.notice_type)
    if window:
        return Deadline(received + timedelta(days=window.days), "statutory_default", window.days,
                        f"The notice does not state a period. {window.note} Counted from the day you received it ({_fmt(received)}) "
                        f"({window.citation}). Confirm with a lawyer.", "receipt")
    return Deadline(None, "unknown", None, "The notice does not state a deadline and no standard window applies. Check the notice itself or ask a lawyer.")


def flag_unverified(dl: Deadline) -> Deadline:
    """A deadline the AI says is stated, but whose wording we cannot find in the text, must not read as fact."""
    if dl.source == "stated":
        return Deadline(dl.due, "stated", dl.days,
                        "The AI read this deadline from the notice but we could not match the wording. Please check the notice itself.", dl.anchor)
    return dl


def deadline_rule(notice_type: Optional[str], source: Optional[str]) -> Optional[str]:
    """Citation for a statutory-default deadline (shown as the 'source' of the date)."""
    if source != "statutory_default" or not notice_type:
        return None
    try:
        w = STATUTORY_WINDOWS.get(NoticeType(notice_type))
    except ValueError:
        return None
    return w.citation if w else None


def depends_on_received_date(dl: Deadline) -> bool:
    return dl.anchor == "receipt"


def urgency_for(facts: NoticeFacts, deadline: Deadline, today: date) -> str:
    """critical | high | medium | low - explainable, not an AI opinion."""
    if facts.notice_type in (NoticeType.court_summons, NoticeType.cheque_bounce):
        floor = "critical"
    else:
        floor = "low"
    rank = {"low": 0, "medium": 1, "high": 2, "critical": 3}
    level = floor
    if deadline.due is not None:
        days = (deadline.due - today).days
        by_days = "critical" if days <= 3 else "high" if days <= 7 else "medium" if days <= 21 else "low"
        level = by_days if rank[by_days] > rank[level] else level
    elif floor == "low":
        level = "medium"                                    # unknown deadline: treat as needing attention
    if facts.amount_claimed and facts.amount_claimed >= 500_000 and rank[level] < rank["high"]:
        level = "high"                                      # large sums deserve a lawyer's eye
    return level


def legal_note(notice_type: NoticeType) -> Optional[LegalNote]:
    return LEGAL_NOTES.get(notice_type)
