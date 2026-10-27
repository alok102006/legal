"""Compliance calendar engine: rules (YAML data) + organisation profile -> dated obligations.

Pure functions, no database. The service layer stores/updates the resulting occurrences.
"""
import calendar as _cal
from dataclasses import dataclass, field
from datetime import date, timedelta
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import yaml

RULES_PATH = Path(__file__).with_name("rules_in.yaml")

TURNOVER_ORDER = ["lt20l", "20l-1.5cr", "1.5-5cr", "5-20cr", "20-50cr", "gt50cr"]

# GST QRMP: GSTR-3B is due on the 22nd for these states, the 24th elsewhere (state codes)
GST_X_STATES = {"22", "23", "24", "25", "26", "27", "28", "29", "30", "31", "32", "33", "34", "35", "36", "37"}


@dataclass
class OrgFacts:
    entity_type: Optional[str] = None
    registrations: Dict[str, bool] = field(default_factory=dict)
    gst_filing_frequency: Optional[str] = None
    turnover_band: Optional[str] = None
    employee_band: Optional[str] = None
    state_code: Optional[str] = None


@dataclass
class Occurrence:
    rule_id: str
    period_key: str
    period_label: str
    due_date: date
    title: str
    category: str
    authority: str
    form: str
    description: str
    penalty: str
    source: str
    needs_confirmation: bool
    confirm_note: Optional[str]
    verify: bool


@dataclass
class RuleDecision:
    rule: Dict[str, Any]
    applies: bool
    reason: str          # human sentence: why it applies / does not apply


# ----------------------------------------------------------------- loading

@lru_cache(maxsize=1)
def load_rules() -> Dict[str, Any]:
    with open(RULES_PATH, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    ids = [r["id"] for r in data["rules"]]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate rule ids in rules_in.yaml")
    return data


def rules_version() -> str:
    return str(load_rules()["version"])


# ----------------------------------------------------------------- applicability

def _band_index(band: Optional[str]) -> Optional[int]:
    return TURNOVER_ORDER.index(band) if band in TURNOVER_ORDER else None


def decide(rule: Dict[str, Any], org: OrgFacts) -> RuleDecision:
    when: Dict[str, Any] = rule.get("when", {})
    title = rule["title"]

    if when.get("always"):
        return RuleDecision(rule, True, "Applies to every business.")

    reasons: List[str] = []

    if "registration" in when:
        key = when["registration"]
        if not org.registrations.get(key):
            return RuleDecision(rule, False, f"You haven't said you hold a {key.upper()} registration.")
        reasons.append(f"you hold a {key.upper()} registration")

    if "not_registration" in when:
        key = when["not_registration"]
        if org.registrations.get(key):
            note = "composition scheme taxpayers file CMP-08 and GSTR-4 instead" if key == "gst_composition" else f"you hold {key.upper()}"
            return RuleDecision(rule, False, f"Not for you: {note}.")

    if "state_in" in when:
        if org.state_code not in when["state_in"]:
            return RuleDecision(rule, False, "Applies to businesses in other states.")
        reasons.append("your state")

    if "entity_in" in when:
        if org.entity_type not in when["entity_in"]:
            return RuleDecision(rule, False, "Applies to other types of business.")
        reasons.append("your type of business")

    if "entity_not_in" in when and org.entity_type in when["entity_not_in"]:
        return RuleDecision(rule, False, "Does not apply to your type of business.")

    if "gst_frequency" in when:
        if org.gst_filing_frequency != when["gst_frequency"]:
            return RuleDecision(rule, False, f"You file GST {org.gst_filing_frequency or 'in a different way'}, not {when['gst_frequency']}.")
        reasons.append(f"you file GST {when['gst_frequency']}")

    t_idx = _band_index(org.turnover_band)
    if "turnover_min_band" in when:
        if t_idx is None:
            return RuleDecision(rule, False, "Tell us your turnover to see whether this applies.")
        if t_idx < TURNOVER_ORDER.index(when["turnover_min_band"]):
            return RuleDecision(rule, False, "Your turnover is below the level where this applies.")
        reasons.append("your turnover")
    if "turnover_max_band" in when:
        if t_idx is None:
            return RuleDecision(rule, False, "Tell us your turnover to see whether this applies.")
        if t_idx > TURNOVER_ORDER.index(when["turnover_max_band"]):
            return RuleDecision(rule, False, "Your turnover is above the level where this applies.")
        reasons.append("your turnover")

    return RuleDecision(rule, True, "Applies because of " + " and ".join(reasons) + "." if reasons else f"{title} applies.")


def rule_by_id(rule_id: Optional[str]) -> Optional[Dict[str, Any]]:
    if not rule_id:
        return None
    for r in load_rules()["rules"]:
        if r["id"] == rule_id:
            return r
    return None


def portal_for(authority: Optional[str]) -> Optional[Dict[str, str]]:
    return (load_rules().get("portals") or {}).get(authority or "")


def fact_keys(rule: Dict[str, Any]) -> List[str]:
    """Which profile facts a rule depends on. Registrations are keyed by their name (gst, tds, pf...)."""
    when = rule.get("when", {})
    keys: List[str] = []
    for k in ("registration", "not_registration"):
        if k in when and when[k] not in keys:
            keys.append(when[k])
    if "entity_in" in when or "entity_not_in" in when:
        keys.append("entity_type")
    if "gst_frequency" in when:
        keys.append("gst_filing_frequency")
    if "turnover_min_band" in when or "turnover_max_band" in when:
        keys.append("turnover_band")
    if "state_in" in when or "day_by_state_group" in rule.get("schedule", {}):
        keys.append("state_code")
    return keys


def applicable_rules(org: OrgFacts) -> List[RuleDecision]:
    return [decide(r, org) for r in load_rules()["rules"]]


# ----------------------------------------------------------------- FY helpers

def fy_start_year(d: date) -> int:
    return d.year if d.month >= 4 else d.year - 1


def fy_label(start_year: int) -> str:
    return f"FY {start_year}-{str(start_year + 1)[-2:]}"


def _safe_date(year: int, month: int, day: int) -> date:
    return date(year, month, min(day, _cal.monthrange(year, month)[1]))


def _add_months(year: int, month: int, n: int) -> Tuple[int, int]:
    idx = year * 12 + (month - 1) + n
    return idx // 12, idx % 12 + 1


def _month_label(year: int, month: int) -> str:
    return f"{_cal.month_abbr[month]} {year}"


# ----------------------------------------------------------------- occurrence generation

def _build(rule: Dict[str, Any], key: str, label: str, due: date) -> Occurrence:
    return Occurrence(
        rule_id=rule["id"], period_key=key, period_label=label, due_date=due, title=rule["title"],
        category=rule.get("category", "other"), authority=rule.get("authority", ""), form=rule.get("form", ""),
        description=rule.get("description", ""), penalty=rule.get("penalty", ""), source=rule.get("source", ""),
        needs_confirmation=bool(rule.get("needs_confirmation") or rule.get("verify")),
        confirm_note=rule.get("confirm_note"), verify=bool(rule.get("verify")),
    )


def occurrences_for_rule(rule: Dict[str, Any], org: OrgFacts, start: date, end: date) -> List[Occurrence]:
    sched = rule["schedule"]
    kind = sched["kind"]
    out: List[Occurrence] = []
    first_fy = fy_start_year(start) - 1
    last_fy = fy_start_year(end) + 1

    if kind == "monthly":
        skip = set(sched.get("skip_period_months", []))
        overrides = {str(k): v for k, v in (sched.get("overrides") or {}).items()}
        # period months from (start - 14 months) to end
        y, m = _add_months(start.year, start.month, -14)
        while (y, m) <= (end.year, end.month):
            if m not in skip:
                spec = overrides.get(str(m), {})
                after = spec.get("months_after", sched.get("months_after", 1))
                day = spec.get("day", sched["day"])
                dy, dm = _add_months(y, m, after)
                due = _safe_date(dy, dm, day)
                if start <= due <= end:
                    out.append(_build(rule, f"{y}-{m:02d}", _month_label(y, m), due))
            y, m = _add_months(y, m, 1)

    elif kind == "quarterly":
        group_days = sched.get("day_by_state_group")
        for fy in range(first_fy, last_fy + 1):
            for q, end_month_offset in enumerate((2, 5, 8, 11), start=1):  # quarter end months: Jun, Sep, Dec, Mar
                qy, qm = _add_months(fy, 4, end_month_offset)
                dy, dm = _add_months(qy, qm, sched.get("months_after", 1))
                day = sched.get("day", 20)
                if group_days:
                    day = group_days["x"] if org.state_code in GST_X_STATES else group_days["y"]
                due = _safe_date(dy, dm, day)
                if start <= due <= end:
                    q_label = ["Apr-Jun", "Jul-Sep", "Oct-Dec", "Jan-Mar"][q - 1]
                    out.append(_build(rule, f"FY{fy}-q{q}", f"{q_label} quarter ({fy_label(fy)})", due))

    elif kind == "fixed_list":
        for fy in range(first_fy, last_fy + 1):
            for item in sched["dates"]:
                due = _safe_date(fy + item.get("year_offset", 0), item["month"], item["day"])
                if start <= due <= end:
                    label = item.get("label", "annual")
                    base = fy_label(fy)
                    pretty = {
                        "annual": base, "q1": f"Q1 (Apr-Jun) {base}", "q2": f"Q2 (Jul-Sep) {base}",
                        "q3": f"Q3 (Oct-Dec) {base}", "q4": f"Q4 (Jan-Mar) {base}",
                        "i1": f"1st installment, {base}", "i2": f"2nd installment, {base}",
                        "i3": f"3rd installment, {base}", "i4": f"4th installment, {base}",
                        "h1": f"Apr-Sep {fy}", "h2": f"Oct {fy}-Mar {fy + 1}",
                    }.get(label, f"{label} {base}")
                    if item.get("note") and label.startswith("i"):
                        pretty += f" ({item['note']})"
                    out.append(_build(rule, f"FY{fy}-{label}", pretty, due))

    elif kind == "once":
        due = date.fromisoformat(sched["date"])
        if start <= due <= end:
            out.append(_build(rule, "once", due.strftime("%d %b %Y"), due))
    else:
        raise ValueError(f"Unknown schedule kind '{kind}' in rule {rule['id']}")

    return sorted(out, key=lambda o: o.due_date)


def penalty_estimate(rule: Optional[Dict[str, Any]], due: Optional[date], today: date) -> Optional[Dict[str, Any]]:
    """Deterministic late-fee estimate for a missed deadline, from the rule's structured `late_fee` (no AI).
    Late fee only: interest and other charges are not included. Returns None when the rule declares no
    computable fee or the deadline has not passed."""
    fee = (rule or {}).get("late_fee")
    if not fee or not due or today <= due:
        return None
    days = (today - due).days
    notes: List[str] = []
    capped = False
    if "flat" in fee:
        amount, per_day, cap = int(fee["flat"]), None, None
    else:
        per_day = int(fee["per_day"])
        cap = int(fee["cap"]) if fee.get("cap") is not None else None
        amount = per_day * days
        if cap is not None and amount >= cap:
            amount, capped = cap, True
    for k in ("fee_note", "cap_note"):
        if fee.get(k):
            notes.append(str(fee[k]))
    return {"amount": amount, "days_late": days, "per_day": per_day, "cap": cap, "capped": capped,
            "flat": "flat" in fee, "note": " ".join(notes) or None}


def build_calendar(org: OrgFacts, start: date, end: date) -> List[Occurrence]:
    """All obligations (that apply to this organisation) with a due date in [start, end]."""
    result: List[Occurrence] = []
    for decision in applicable_rules(org):
        if decision.applies:
            result.extend(occurrences_for_rule(decision.rule, org, start, end))
    result.sort(key=lambda o: (o.due_date, o.title))
    return result


def not_covered() -> List[Dict[str, str]]:
    return list(load_rules().get("not_covered", []))
