"""Deterministic notice rules: the response deadline, urgency, and views of the notice catalog.

The AI reads the notice; these rules do the date arithmetic and decide urgency, so both are explainable and testable.
A deadline is never invented. Every candidate date carries its basis:

  stated date      the notice names a date ("by 30 October 2026")              -> verified by the deadline quote
  stated period    the notice gives a period ("within 7 days of receipt")      -> verified by the deadline quote
  hearing          the notice fixes a hearing / appearance date                -> verified by the hearing quote
  statutory        a statute fixes the window for this notice type (catalog)   -> act + section

The EARLIEST candidate is the deadline (a wrong later date costs more than a wrong earlier one), and the note says
why and lists the others. Missing inputs are asked for, not guessed: a period counted from the notice date with no
readable notice date yields no candidate and asks for the date.

  source: stated | statutory_default | unknown   (kept for stored cases and the UI)
"""
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import List, NamedTuple, Optional, Tuple

from dateutil.relativedelta import relativedelta

from app.workspaces.legal_notice_center.engine import dates
from app.workspaces.legal_notice_center.engine.catalog import CATALOG, HANDLER_LABELS, NoticeRule, StatutoryWindow, rule_for
from app.workspaces.legal_notice_center.engine.schemas import NoticeFacts, NoticeType

RULES_VERSION = "2026-10-28.1"

TYPE_LABELS = {t: r.label for t, r in CATALOG.items()}
STATUTORY_WINDOWS = {t: r.window for t, r in CATALOG.items() if r.window}


class LegalNote(NamedTuple):
    text: str            # 2-3 lines in plain English: what the law generally says
    ref: str             # section + act cited (the "source")
    if_ignored: str      # the consequence chain if the notice is ignored


LEGAL_NOTES = {t: LegalNote(r.meaning, r.ref, r.if_ignored) for t, r in CATALOG.items()}

UNVERIFIED_NOTE = "The AI read this deadline from the notice but we could not match the wording. Please check the notice itself."
_RANK = {"low": 0, "medium": 1, "high": 2, "critical": 3}
_BASIS_ORDER = {"stated_date": 0, "stated_period": 1, "hearing": 2, "statutory": 3}


def legal_note(notice_type: NoticeType) -> Optional[LegalNote]:
    return LEGAL_NOTES.get(notice_type)


def safe_type(value: Optional[str]) -> Optional[NoticeType]:
    """Stored type string -> enum; None for values from an older taxonomy instead of crashing a read."""
    try:
        return NoticeType(value) if value else None
    except ValueError:
        return None


def parse_iso(value: Optional[str]) -> Optional[date]:
    if not value:
        return None
    try:
        return date.fromisoformat(value.strip()[:10])
    except ValueError:
        return None


def fmt(d: date) -> str:
    return d.strftime("%d %b %Y").lstrip("0")


# ---------------------------------------------------------------- date arithmetic

def add_period(start: date, count: int, unit: str) -> date:
    """Last day of a period counted from `start` (the start day itself excluded, General Clauses Act s.9).

    Working days skip Sundays only: public holidays and second Saturdays can only make the real date later, so the
    date we show is never later than the true one."""
    if unit == "months":
        return start + relativedelta(months=count)
    if unit == "working_days":
        d, left = start, count
        while left:
            d += timedelta(days=1)
            if d.weekday() != 6:
                left -= 1
        return d
    return start + timedelta(days=count)


def _period_words(count: int, unit: str) -> str:
    return {"working_days": f"{count} working days", "months": f"{count} month" + ("s" if count != 1 else "")}.get(unit, f"{count} days")


# ---------------------------------------------------------------- reconciling the AI's dates with the notice's words

def reconcile_facts(facts: NoticeFacts, notice_text: str, received: date,
                    deadline_quote_ok: bool, hearing_quote_ok: bool) -> Tuple[NoticeFacts, List[str], bool]:
    """Re-read the verified quotes deterministically and correct the AI's dates where the notice's own words differ.

    Returns (facts, corrections shown to the user, notice_date_found_in_text)."""
    upd: dict = {}
    notes: List[str] = []
    text_dates = set(dates.find_dates(notice_text))

    nd = parse_iso(facts.notice_date)
    nd_found = nd is not None and nd in text_dates
    if nd and not nd_found and _swap(nd) in text_dates:
        upd["notice_date"], nd_found = _swap(nd).isoformat(), True
        notes.append(f"Notice date read from the notice as {fmt(_swap(nd))} (day first).")
        nd = _swap(nd)
    ref = nd or received

    if deadline_quote_ok and facts.deadline_quote:
        q = facts.deadline_quote
        period, anchor = dates.find_period(q), dates.period_anchor(q)
        if period:
            if facts.response_days != period.count or (facts.response_period_unit or "days") != period.unit:
                notes.append(f"Period taken from the notice's words: {_period_words(period.count, period.unit)}.")
            upd.update(response_days=period.count, response_period_unit=period.unit)
            if anchor and facts.response_days_from != anchor:
                upd["response_days_from"] = anchor
        quoted = dates.find_dates(q, ref)
        model_dt = parse_iso(facts.response_deadline_date)
        fixed, why = _quoted_deadline_date(model_dt, quoted, set(dates.find_dates(notice_text, ref)), nd)
        if fixed != model_dt:
            upd["response_deadline_date"] = fixed.isoformat() if fixed else None
            notes.append(why)
        if not period and not quoted and dates.says_forthwith(q):
            upd["forthwith"] = True

    if hearing_quote_ok and facts.hearing_quote:
        quoted = dates.find_dates(facts.hearing_quote, ref)
        model_dt = parse_iso(facts.hearing_date)
        if quoted and model_dt not in quoted:
            later = [d for d in quoted if d >= ref] or quoted
            upd["hearing_date"] = later[-1].isoformat()
            notes.append(f"Hearing date read from the notice's words as {fmt(later[-1])}.")
    return (facts.model_copy(update=upd) if upd else facts), notes, nd_found


def _quoted_deadline_date(model_dt: Optional[date], quoted: List[date], text_dates: set,
                          notice_dt: Optional[date]) -> Tuple[Optional[date], str]:
    """The deadline date the verified quote supports. A date in the quote that is not after the notice date is
    the notice's own date ("notice dated 12.10.2026, pay within 15 days"), never a deadline."""
    if model_dt is not None and (model_dt in quoted or model_dt in text_dates):
        return model_dt, ""
    future = [d for d in quoted if notice_dt is None or d > notice_dt]
    if future:
        best = max(future)
        return best, f"Deadline date read from the notice's words as {fmt(best)}" + (f" (the AI had {fmt(model_dt)})." if model_dt else ".")
    if model_dt is not None:
        return None, f"The AI's deadline date {fmt(model_dt)} does not appear in the notice, so it is not used."
    return None, ""


def _swap(d: date) -> Optional[date]:
    try:
        return date(d.year, d.day, d.month) if d.day <= 12 else None
    except ValueError:
        return None


# ---------------------------------------------------------------- deadline

@dataclass(frozen=True)
class Candidate:
    due: date
    basis: str            # stated_date | stated_period | hearing | statutory
    anchor: str           # explicit | receipt | notice_date | hearing
    verified: bool
    explanation: str
    citation: Optional[str] = None

    def as_dict(self) -> dict:
        return {"due": self.due.isoformat(), "basis": self.basis, "anchor": self.anchor, "verified": self.verified,
                "explanation": self.explanation, "citation": self.citation}


@dataclass
class Deadline:
    due: Optional[date]
    source: str                    # stated | statutory_default | unknown
    days: Optional[int]
    note: str
    anchor: Optional[str] = None   # explicit | receipt | notice_date | hearing | None
    verified: bool = False         # the chosen date is backed by a matched quote or a statute
    candidates: List[Candidate] = field(default_factory=list)
    needs: List[str] = field(default_factory=list)     # inputs to ask the user for: "notice_date"
    forthwith: bool = False


def _period_candidate(facts: NoticeFacts, received: date, notice_dt: Optional[date], verified: bool,
                      needs: List[str]) -> Optional[Candidate]:
    n, unit = facts.response_days, facts.response_period_unit or "days"
    words = _period_words(n, unit)
    if facts.response_days_from == "notice_date":
        if not notice_dt:
            needs.append("notice_date")
            return None
        return Candidate(add_period(notice_dt, n, unit), "stated_period", "notice_date", verified,
                         f"The notice gives {words} from its own date ({fmt(notice_dt)}).")
    if facts.response_days_from is None and notice_dt and notice_dt < received:
        return Candidate(add_period(notice_dt, n, unit), "stated_period", "notice_date", verified,
                         f"The notice gives {words} without saying from when; counted from the date of the notice "
                         f"({fmt(notice_dt)}), the earlier and safer reading.")
    return Candidate(add_period(received, n, unit), "stated_period", "receipt", verified,
                     f"The notice gives {words}. Counted from the day you received it ({fmt(received)}).")


def _statutory_candidate(w: StatutoryWindow, received: date, notice_dt: Optional[date], needs: List[str]) -> Optional[Candidate]:
    start = received if w.anchor == "receipt" else notice_dt
    if start is None:
        needs.append("notice_date")
        return None
    when = f"the day you received it ({fmt(received)})" if w.anchor == "receipt" else f"the date of the notice ({fmt(start)})"
    return Candidate(add_period(start, w.count, w.unit), "statutory", w.anchor, True,
                     f"{w.note} Counted from {when} ({w.citation}).", w.citation)


def candidates_for(facts: NoticeFacts, received: date, deadline_verified: bool = True,
                   hearing_verified: bool = True) -> Tuple[List[Candidate], List[str]]:
    needs: List[str] = []
    out: List[Candidate] = []
    notice_dt = parse_iso(facts.notice_date)
    stated = parse_iso(facts.response_deadline_date)
    if stated:
        out.append(Candidate(stated, "stated_date", "explicit", deadline_verified, f"The notice states {fmt(stated)}."))
    if facts.response_days:
        c = _period_candidate(facts, received, notice_dt, deadline_verified, needs)
        if c:
            out.append(c)
    hearing = parse_iso(facts.hearing_date)
    if hearing:
        out.append(Candidate(hearing, "hearing", "hearing", hearing_verified,
                             f"The notice fixes {fmt(hearing)} for a hearing / appearance; any written reply should be in before it."))
    rule = CATALOG.get(facts.notice_type)
    if rule and rule.window:
        c = _statutory_candidate(rule.window, received, notice_dt, needs)
        if c:
            out.append(c)
    return out, sorted(set(needs))


def compute_deadline(facts: NoticeFacts, received: date, deadline_verified: bool = True,
                     hearing_verified: bool = True) -> Deadline:
    cands, needs = candidates_for(facts, received, deadline_verified, hearing_verified)
    ask = (" The notice gives a period from its own date, but that date could not be read: enter the notice date to include it."
           if "notice_date" in needs else "")
    if not cands:
        if facts.forthwith:
            note = ("The notice demands action 'forthwith' (immediately) and gives no date or period. Treat it as due now: "
                    "respond within days, not weeks.")
        else:
            note = "The notice does not state a deadline and no standard window applies. Check the notice itself or ask a lawyer."
        return Deadline(None, "unknown", None, note + ask, None, False, [], needs, facts.forthwith)

    chosen = min(cands, key=lambda c: (c.due, _BASIS_ORDER[c.basis]))
    base = {"receipt": received, "notice_date": parse_iso(facts.notice_date)}.get(chosen.anchor) or received
    note = chosen.explanation
    if chosen.basis == "statutory":
        note = ("The notice does not state an earlier date. " if not any(c.basis != "statutory" for c in cands) else "") + note
        note += " Confirm with a lawyer."
    elif not chosen.verified:
        note += " " + UNVERIFIED_NOTE
    others = [c for c in cands if c is not chosen]
    if others:
        note += " This is the earliest of the dates that apply; also considered: " + "; ".join(
            f"{fmt(c.due)} ({_BASIS_LABEL[c.basis]})" for c in others) + "."
    return Deadline(chosen.due, "statutory_default" if chosen.basis == "statutory" else "stated", (chosen.due - base).days,
                    note + ask, chosen.anchor, chosen.verified, cands, needs, facts.forthwith)


_BASIS_LABEL = {"stated_date": "date in the notice", "stated_period": "period in the notice",
                "hearing": "hearing date", "statutory": "statutory window"}


def deadline_rule(notice_type: Optional[str], source: Optional[str]) -> Optional[str]:
    """Citation for a statutory-default deadline (shown as the 'source' of the date)."""
    t = safe_type(notice_type)
    if source != "statutory_default" or t is None:
        return None
    w = STATUTORY_WINDOWS.get(t)
    return w.citation if w else None


def urgency_for(facts: NoticeFacts, deadline: Deadline, today: date) -> str:
    """critical | high | medium | low - explainable, not an AI opinion."""
    rule: Optional[NoticeRule] = CATALOG.get(facts.notice_type)
    level = rule.urgency_floor if rule else "low"

    def at_least(lvl: str) -> None:
        nonlocal level
        if _RANK[lvl] > _RANK[level]:
            level = lvl

    if deadline.due is not None:
        days = (deadline.due - today).days
        at_least("critical" if days <= 3 else "high" if days <= 7 else "medium" if days <= 21 else "low")
    else:
        at_least("medium")                                  # unknown deadline: needs attention
    if facts.forthwith:
        at_least("high")
    if facts.amount_claimed and facts.amount_claimed >= 500_000:
        at_least("high")                                    # large sums deserve a lawyer's eye
    return level


def type_info(notice_type: Optional[str]) -> Optional[dict]:
    """Everything the UI shows about the kind of notice, from the catalog (no AI)."""
    t = safe_type(notice_type)
    if t is None:
        return None
    r = rule_for(t)
    w = r.window
    return {
        "label": r.label, "family": r.family, "meaning": r.meaning, "if_ignored": r.if_ignored, "ref": r.ref,
        "documents": list(r.documents), "handler": r.handler, "handler_label": HANDLER_LABELS[r.handler],
        "response": r.response, "channel": r.channel, "verified": r.verified, "verify_note": r.verify_note or None,
        "statutory_window": ({"count": w.count, "unit": w.unit, "anchor": w.anchor, "citation": w.citation, "note": w.note,
                              "purpose": w.purpose} if w else None),
    }

