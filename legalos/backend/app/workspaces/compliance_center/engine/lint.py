"""Consistency checks for `rules_in.yaml`, run by the test suite (and usable from a shell: `python -m ...engine.lint`).

A wrong deadline silently misleads every customer, so the rules file is linted like code. `lint_rules` returns a list of
human-readable problems (empty = clean):

- every rule has an id, title, category, authority, form, a `source` (act + section) and a real `penalty` text;
- the schedule is valid for its kind (days exist in their month, overrides name real months, dates parse ...);
- `late_fee` is structured sensibly, and a rule marked `needs_confirmation` / `verify` says what to confirm;
- no two rules collide: no duplicate ids or titles, no two rules with the same form and conditions, and no organisation
  profile for which two rules for the same form apply at once;
- every rule really fires: a profile built from its own `when` is selected and gets at least one due date.
"""
import calendar
import itertools
import json
from datetime import date
from typing import Any, Dict, List, Optional

from app.workspaces.compliance_center.engine import schedule as sch

CATEGORIES = {"tax", "labor", "corporate", "other"}
KNOWN_WHEN = {"always", "registration", "not_registration", "state_in", "entity_in", "entity_not_in", "gst_frequency",
              "turnover_min_band", "turnover_max_band"}
SCHEDULE_KINDS = {"monthly", "quarterly", "fixed_list", "once"}
MIN_PENALTY_CHARS = 20

ENTITY_TYPES = ["sole_proprietorship", "partnership", "llp", "private_limited", "public_limited", "opc", "trust_society", "other"]
REGISTRATION_SETS = [{}, {"gst": True}, {"gst": True, "gst_composition": True}, {"tds": True, "pf": True, "esi": True, "pt": True},
                     {"gst": True, "tds": True, "pf": True, "esi": True, "pt": True}]


def _is_int(v: Any, low: int, high: int) -> bool:
    return isinstance(v, int) and not isinstance(v, bool) and low <= v <= high


def _check_schedule(rid: str, sched: Dict[str, Any]) -> List[str]:
    problems: List[str] = []
    kind = sched.get("kind")
    if kind not in SCHEDULE_KINDS:
        return [f"{rid}: unknown schedule kind '{kind}'"]
    if kind in ("monthly", "quarterly"):
        if "months_after" in sched and not _is_int(sched["months_after"], 0, 12):
            problems.append(f"{rid}: months_after must be 0-12")
        grouped = sched.get("day_by_state_group")
        if kind == "quarterly" and grouped:
            if set(grouped) != {"x", "y"} or not all(_is_int(d, 1, 31) for d in grouped.values()):
                problems.append(f"{rid}: day_by_state_group needs integer days 1-31 for x and y")
        elif not _is_int(sched.get("day"), 1, 31):
            problems.append(f"{rid}: {kind} schedule needs a day between 1 and 31")
    if kind == "monthly":
        if not all(_is_int(m, 1, 12) for m in sched.get("skip_period_months", [])):
            problems.append(f"{rid}: skip_period_months must be months 1-12")
        for month, spec in (sched.get("overrides") or {}).items():
            if not _is_int(int(month), 1, 12) or not set(spec) <= {"day", "months_after"}:
                problems.append(f"{rid}: bad override for month {month}")
            elif "day" in spec and not _is_int(spec["day"], 1, 31):
                problems.append(f"{rid}: override day for month {month} must be 1-31")
    if kind == "fixed_list":
        dates = sched.get("dates") or []
        if not dates:
            problems.append(f"{rid}: fixed_list has no dates")
        labels = [d.get("label", "annual") for d in dates]
        if len(labels) != len(set(labels)):
            problems.append(f"{rid}: fixed_list labels must be unique (they key the stored tasks)")
        for d in dates:
            if not _is_int(d.get("month"), 1, 12) or not _is_int(d.get("day"), 1, 31):
                problems.append(f"{rid}: bad date {d}")
            elif d["day"] > calendar.monthrange(2024, d["month"])[1]:
                problems.append(f"{rid}: day {d['day']} does not exist in month {d['month']}")
            if not _is_int(d.get("year_offset", 0), 0, 2):
                problems.append(f"{rid}: year_offset must be 0-2")
    if kind == "once":
        try:
            date.fromisoformat(str(sched.get("date")))
        except ValueError:
            problems.append(f"{rid}: 'once' needs an ISO date (YYYY-MM-DD)")
    return problems


def _check_rule(rule: Dict[str, Any]) -> List[str]:
    rid = rule.get("id", "<no id>")
    problems: List[str] = []
    for key in ("id", "title", "category", "authority", "form", "when", "schedule", "penalty", "source", "description"):
        if not rule.get(key):
            problems.append(f"{rid}: missing {key}")
    if rule.get("category") not in CATEGORIES:
        problems.append(f"{rid}: category must be one of {sorted(CATEGORIES)}")
    if len(str(rule.get("penalty", ""))) < MIN_PENALTY_CHARS:
        problems.append(f"{rid}: penalty text is too short to be useful")
    if not any(ch.isdigit() for ch in str(rule.get("source", ""))) and "notification" not in str(rule.get("source", "")).lower():
        problems.append(f"{rid}: source should cite an act and section (or a notification)")
    unknown = set(rule.get("when", {})) - KNOWN_WHEN
    if unknown:
        problems.append(f"{rid}: unknown conditions {sorted(unknown)}")
    for band in (rule.get("when", {}).get("turnover_min_band"), rule.get("when", {}).get("turnover_max_band")):
        if band is not None and band not in sch.TURNOVER_ORDER:
            problems.append(f"{rid}: unknown turnover band '{band}'")
    if rule.get("schedule"):
        problems += _check_schedule(rid, rule["schedule"])
    fee = rule.get("late_fee")
    if fee:
        if not ({"per_day", "flat"} & set(fee)):
            problems.append(f"{rid}: late_fee needs per_day or flat")
        for k in ("per_day", "cap", "flat"):
            if k in fee and not (isinstance(fee[k], (int, float)) and fee[k] > 0):
                problems.append(f"{rid}: late_fee.{k} must be a positive number")
    if (rule.get("verify") or rule.get("needs_confirmation")) and not rule.get("confirm_note"):
        problems.append(f"{rid}: marked verify / needs_confirmation but has no confirm_note")
    return problems


def _profile_for(rule: Dict[str, Any]) -> sch.OrgFacts:
    """An organisation that satisfies the rule's own conditions."""
    when = rule.get("when", {})
    regs = {when["registration"]: True} if "registration" in when else {}
    entity = (when.get("entity_in") or [None])[0]
    if "entity_not_in" in when:
        entity = next(e for e in ENTITY_TYPES if e not in when["entity_not_in"])
    band: Optional[str] = when.get("turnover_min_band") or when.get("turnover_max_band")
    return sch.OrgFacts(entity_type=entity, registrations=regs, gst_filing_frequency=when.get("gst_frequency"),
                        turnover_band=band, state_code=(when.get("state_in") or ["27"])[0])


def _collisions(rules: List[Dict[str, Any]]) -> List[str]:
    problems: List[str] = []
    ids = [r.get("id") for r in rules]
    titles = [r.get("title") for r in rules]
    for label, values in (("id", ids), ("title", titles)):
        for v in {x for x in values if values.count(x) > 1}:
            problems.append(f"duplicate {label}: {v}")
    seen: Dict[tuple, str] = {}
    for r in rules:
        key = (r.get("form"), json.dumps(r.get("when"), sort_keys=True))
        if key in seen:
            problems.append(f"{r['id']} and {seen[key]} have the same form and the same conditions")
        seen[key] = r["id"]
    # Profile grid: no organisation may get two rules for the same form at once.
    forms = {r["id"]: r.get("form") for r in rules}
    for entity, regs, freq, band in itertools.product(ENTITY_TYPES + [None], REGISTRATION_SETS, ["monthly", "quarterly", None],
                                                      sch.TURNOVER_ORDER + [None]):
        org = sch.OrgFacts(entity_type=entity, registrations=dict(regs), gst_filing_frequency=freq, turnover_band=band, state_code="29")
        by_form: Dict[str, List[str]] = {}
        for r in rules:
            if sch.decide(r, org).applies:
                by_form.setdefault(forms[r["id"]], []).append(r["id"])
        for form, rule_ids in by_form.items():
            if len(rule_ids) > 1:
                problems.append(f"rules {rule_ids} (form {form}) all apply to entity={entity} regs={sorted(regs)} freq={freq} band={band}")
                return problems          # one example is enough; the grid would repeat it thousands of times
    return problems


def _every_rule_fires(rules: List[Dict[str, Any]]) -> List[str]:
    problems: List[str] = []
    start, end = date(2026, 1, 1), date(2029, 12, 31)
    for r in rules:
        if not r.get("schedule") or _check_schedule(r.get("id", "?"), r["schedule"]):
            continue                                # already reported as a schedule problem; it cannot be expanded
        org = _profile_for(r)
        if not sch.decide(r, org).applies:
            problems.append(f"{r['id']}: a profile built from its own conditions does not select it")
        elif not sch.occurrences_for_rule(r, org, start, end):
            problems.append(f"{r['id']}: produces no due date between {start} and {end}")
    return problems


def lint_rules(data: Optional[Dict[str, Any]] = None) -> List[str]:
    data = data if data is not None else sch.load_rules()
    rules = data.get("rules", [])
    problems: List[str] = []
    if not data.get("version"):
        problems.append("rules file has no version")
    for rule in rules:
        problems += _check_rule(rule)
    problems += _collisions(rules)
    problems += _every_rule_fires(rules)
    for rule in rules:
        authority = rule.get("authority")
        if authority in (data.get("portals") or {}) and not data["portals"][authority].get("url"):
            problems.append(f"portal for {authority} has no url")
    return problems


if __name__ == "__main__":  # pragma: no cover
    found = lint_rules()
    print("\n".join(found) if found else "rules_in.yaml: clean")
    raise SystemExit(1 if found else 0)
