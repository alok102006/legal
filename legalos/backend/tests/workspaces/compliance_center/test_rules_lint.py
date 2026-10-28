"""`rules_lint`: the rules file is checked like code, and every statutory date is pinned against the law."""
import copy
from datetime import date

import pytest

from app.workspaces.compliance_center.engine import lint
from app.workspaces.compliance_center.engine import schedule as sch
from app.workspaces.compliance_center.engine.schedule import OrgFacts

WINDOW = (date(2026, 4, 1), date(2027, 6, 30))


def _dates(org, rule_id, window=WINDOW):
    return {o.period_key: o.due_date for o in sch.build_calendar(org, *window) if o.rule_id == rule_id}


def pvt(**kw):
    base = dict(entity_type="private_limited", registrations={"gst": True, "tds": True, "pf": True, "esi": True},
                gst_filing_frequency="monthly", turnover_band="5-20cr", state_code="27")
    base.update(kw)
    return OrgFacts(**base)


# ------------------------------------------------------------------ the lint itself

def test_rules_file_passes_the_lint():
    assert lint.lint_rules() == []


def test_every_rule_has_source_penalty_and_a_valid_schedule():
    for r in sch.load_rules()["rules"]:
        assert r["source"].strip() and len(r["penalty"]) >= lint.MIN_PENALTY_CHARS, r["id"]
        assert lint._check_schedule(r["id"], r["schedule"]) == [], r["id"]


def _data():
    return copy.deepcopy(sch.load_rules())


def _rule(data, rid):
    return next(r for r in data["rules"] if r["id"] == rid)


def test_lint_catches_missing_source_and_short_penalty():
    d = _data()
    _rule(d, "tds-payment")["source"] = ""
    _rule(d, "pf-monthly")["penalty"] = "Fine."
    problems = lint.lint_rules(d)
    assert any("tds-payment: missing source" in p for p in problems)
    assert any("pf-monthly: penalty text is too short" in p for p in problems)


def test_lint_catches_invalid_schedules():
    d = _data()
    _rule(d, "companies-dpt3")["schedule"] = {"kind": "fixed_list", "dates": [{"month": 2, "day": 30, "year_offset": 1}]}
    _rule(d, "pf-monthly")["schedule"] = {"kind": "monthly", "day": 40, "months_after": 1}
    _rule(d, "esi-monthly")["schedule"] = {"kind": "yearly"}
    _rule(d, "dpdp-readiness")["schedule"] = {"kind": "once", "date": "13/05/2027"}
    _rule(d, "tds-return")["schedule"]["dates"][1]["label"] = "q1"            # duplicate label would collide stored tasks
    problems = " | ".join(lint.lint_rules(d))
    assert "does not exist in month 2" in problems
    assert "pf-monthly: monthly schedule needs a day" in problems
    assert "esi-monthly: unknown schedule kind" in problems
    assert "dpdp-readiness: 'once' needs an ISO date" in problems
    assert "tds-return: fixed_list labels must be unique" in problems


def test_lint_catches_rules_that_collide():
    d = _data()
    dup = copy.deepcopy(_rule(d, "pf-monthly"))
    dup["id"], dup["title"] = "pf-monthly-copy", "PF again"
    d["rules"].append(dup)
    assert any("same form and the same conditions" in p for p in lint.lint_rules(d))

    d = _data()
    d["rules"].append(copy.deepcopy(_rule(d, "pf-monthly")))
    assert any("duplicate id" in p for p in lint.lint_rules(d))


def test_lint_catches_two_rules_for_one_form_applying_to_the_same_business():
    d = _data()
    broader = copy.deepcopy(_rule(d, "gst-gstr3b-monthly"))
    broader["id"], broader["title"] = "gst-gstr3b-any", "GSTR-3B for everyone"
    broader["when"] = {"registration": "gst"}                                 # overlaps with the quarterly rule
    d["rules"].append(broader)
    assert any("all apply to" in p for p in lint.lint_rules(d))


def test_lint_requires_a_confirm_note_when_a_rule_is_unverified():
    d = _data()
    r = _rule(d, "tds-payment")
    r["verify"] = True
    r.pop("confirm_note", None)
    assert any("tds-payment: marked verify" in p for p in lint.lint_rules(d))


def test_lint_catches_bad_conditions_and_late_fees():
    d = _data()
    _rule(d, "tds-payment")["when"] = {"registration": "tds", "moon_phase": "full"}
    _rule(d, "tds-return")["late_fee"] = {"cap": 100}
    problems = " | ".join(lint.lint_rules(d))
    assert "unknown conditions" in problems and "late_fee needs per_day or flat" in problems


# ------------------------------------------------------------------ statutory dates, pinned

def test_gst_dates():
    assert _dates(pvt(), "gst-gstr1-monthly")["2026-09"] == date(2026, 10, 11)
    assert _dates(pvt(), "gst-gstr3b-monthly")["2026-09"] == date(2026, 10, 20)
    q = pvt(gst_filing_frequency="quarterly")
    assert _dates(q, "gst-gstr1-quarterly")["FY2026-q2"] == date(2026, 10, 13)
    assert _dates(q, "gst-gstr3b-quarterly")["FY2026-q2"] == date(2026, 10, 22)                    # Maharashtra: 22nd
    assert _dates(pvt(gst_filing_frequency="quarterly", state_code="09"), "gst-gstr3b-quarterly")["FY2026-q2"] == date(2026, 10, 24)
    assert _dates(q, "gst-pmt06")["2026-10"] == date(2026, 11, 25)
    comp = OrgFacts(entity_type="partnership", registrations={"gst": True, "gst_composition": True}, turnover_band="1.5-5cr")
    assert _dates(comp, "gst-cmp08")["FY2026-q2"] == date(2026, 10, 18)
    assert _dates(comp, "gst-gstr4")["FY2025-annual"] == date(2026, 4, 30)
    assert _dates(pvt(), "gst-gstr9")["FY2025-annual"] == date(2026, 12, 31)
    assert _dates(pvt(), "gst-gstr9c")["FY2025-annual"] == date(2026, 12, 31)


@pytest.mark.parametrize("state,day", [("27", 22), ("29", 22), ("24", 22), ("33", 22), ("36", 22), ("26", 22), ("38", 24),
                                       ("07", 24), ("09", 24), ("19", 24), ("20", 24), ("21", 24), ("03", 24)])
def test_qrmp_state_groups(state, day):
    org = pvt(gst_filing_frequency="quarterly", state_code=state)
    assert _dates(org, "gst-gstr3b-quarterly")["FY2026-q2"].day == day


def test_tds_and_income_tax_dates():
    org = pvt()
    pay = _dates(org, "tds-payment")
    assert pay["2026-09"] == date(2026, 10, 7) and pay["2027-03"] == date(2027, 4, 30)
    ret = _dates(org, "tds-return")
    assert ret == {"FY2025-q4": date(2026, 5, 31), "FY2026-q1": date(2026, 7, 31), "FY2026-q2": date(2026, 10, 31),
                   "FY2026-q3": date(2027, 1, 31), "FY2026-q4": date(2027, 5, 31)}
    assert _dates(org, "tds-form16")["FY2025-annual"] == date(2026, 6, 15)
    adv = {k: v for k, v in _dates(org, "advance-tax").items() if k.startswith("FY2026")}
    assert [adv[k] for k in sorted(adv)] == [date(2026, 6, 15), date(2026, 9, 15), date(2026, 12, 15), date(2027, 3, 15)]
    assert _dates(org, "tax-audit-report")["FY2025-annual"] == date(2026, 9, 30)
    assert _dates(org, "itr-audit-cases")["FY2025-annual"] == date(2026, 10, 31)
    firm = OrgFacts(entity_type="partnership", registrations={}, turnover_band="20l-1.5cr")
    assert _dates(firm, "itr-firm-nonaudit")["FY2025-annual"] == date(2026, 7, 31)
    firm_audit = OrgFacts(entity_type="partnership", registrations={}, turnover_band="5-20cr")
    assert _dates(firm_audit, "itr-firm-audit")["FY2025-annual"] == date(2026, 10, 31)


def test_pf_esi_dates():
    org = pvt()
    assert _dates(org, "pf-monthly")["2026-09"] == date(2026, 10, 15)
    assert _dates(org, "esi-monthly")["2026-09"] == date(2026, 10, 15)


def test_companies_act_dates_follow_the_agm():
    org = pvt()
    agm = _dates(org, "companies-agm")["FY2025-annual"]
    assert agm == date(2026, 9, 30)
    assert _dates(org, "companies-aoc4")["FY2025-annual"] == date(2026, 10, 30) == date.fromordinal(agm.toordinal() + 30)
    assert _dates(org, "companies-mgt7")["FY2025-annual"] == date(2026, 11, 29) == date.fromordinal(agm.toordinal() + 60)
    assert _dates(org, "companies-adt1")["FY2025-annual"] == date(2026, 10, 15) == date.fromordinal(agm.toordinal() + 15)
    assert _dates(org, "companies-dir3kyc")["FY2026-annual"] == date(2026, 9, 30)
    assert _dates(org, "companies-dpt3")["FY2025-annual"] == date(2026, 6, 30)
    msme = _dates(org, "companies-msme1")
    assert msme["FY2025-h2"] == date(2026, 4, 30) and msme["FY2026-h1"] == date(2026, 10, 31)


def test_llp_dates():
    llp = OrgFacts(entity_type="llp", registrations={}, turnover_band="20l-1.5cr")
    assert _dates(llp, "llp-form11")["FY2025-annual"] == date(2026, 5, 30)
    assert _dates(llp, "llp-form8")["FY2025-annual"] == date(2026, 10, 30)
    assert _dates(llp, "companies-dir3kyc")["FY2026-annual"] == date(2026, 9, 30)


def test_uncertain_rules_stay_flagged_for_confirmation():
    flagged = {r["id"]: r for r in sch.load_rules()["rules"] if r.get("verify") or r.get("needs_confirmation")}
    for must in ("pt-karnataka", "companies-dir3kyc", "dpdp-readiness", "gst-gstr4", "companies-adt1", "tds-form16",
                 "companies-aoc4", "companies-mgt7"):
        assert must in flagged and flagged[must]["confirm_note"], must
    assert flagged["pt-karnataka"].get("verify") and flagged["companies-dir3kyc"].get("verify")


def test_professional_tax_and_shops_act_are_not_guessed():
    not_covered = " ".join(f"{n['title']} {n['reason']}" for n in sch.not_covered())
    for state in ("Maharashtra", "West Bengal", "Gujarat", "Tamil Nadu", "Telangana"):
        assert state in not_covered
    assert "Shops and Establishment" in not_covered
    assert not [r["id"] for r in sch.load_rules()["rules"] if r["id"].startswith("pt-") and r["id"] != "pt-karnataka"]
    assert "ADT-1" not in not_covered                                         # now a real rule
