from datetime import date

import pytest

from app.workspaces.compliance_center.engine import schedule as sch
from app.workspaces.compliance_center.engine.schedule import OrgFacts

WINDOW = (date(2026, 4, 1), date(2027, 5, 31))


def _by_rule(occs, rule_id):
    return {o.period_key: o.due_date for o in occs if o.rule_id == rule_id}


def pvt_ltd(**kw):
    base = dict(entity_type="private_limited", registrations={"gst": True, "tds": True}, gst_filing_frequency="monthly",
                turnover_band="5-20cr", employee_band="50-199", state_code="27")
    base.update(kw)
    return OrgFacts(**base)


# ------------------------------------------------------------------ rules file integrity

def test_rules_file_is_well_formed():
    data = sch.load_rules()
    known_when = {"always", "registration", "not_registration", "state_in", "entity_in", "entity_not_in", "gst_frequency", "turnover_min_band", "turnover_max_band"}
    for r in data["rules"]:
        for k in ("id", "title", "category", "authority", "when", "schedule", "penalty", "source"):
            assert k in r, f"{r.get('id')} missing {k}"
        assert set(r["when"]) <= known_when, f"{r['id']} has unknown condition"
        assert r["schedule"]["kind"] in ("monthly", "quarterly", "fixed_list", "once")
        for band in (r["when"].get("turnover_min_band"), r["when"].get("turnover_max_band")):
            assert band is None or band in sch.TURNOVER_ORDER
    assert sch.rules_version()


# ------------------------------------------------------------------ recurrence

def test_monthly_gstr3b_dates():
    occs = sch.build_calendar(pvt_ltd(), date(2026, 10, 22), date(2027, 3, 31))
    d = _by_rule(occs, "gst-gstr3b-monthly")
    assert d == {
        "2026-10": date(2026, 11, 20), "2026-11": date(2026, 12, 20), "2026-12": date(2027, 1, 20),
        "2027-01": date(2027, 2, 20), "2027-02": date(2027, 3, 20),
    }
    assert "2026-09" not in d       # due 20 Oct 2026, before the window


def test_tds_payment_march_exception():
    d = _by_rule(sch.build_calendar(pvt_ltd(), *WINDOW), "tds-payment")
    assert d["2027-02"] == date(2027, 3, 7)
    assert d["2027-03"] == date(2027, 4, 30)       # tax deducted in March is due 30 April, not 7 April
    assert d["2026-04"] == date(2026, 5, 7)


def test_tds_returns_quarterly_dates():
    d = _by_rule(sch.build_calendar(pvt_ltd(), *WINDOW), "tds-return")
    assert d["FY2026-q1"] == date(2026, 7, 31)
    assert d["FY2026-q2"] == date(2026, 10, 31)
    assert d["FY2026-q3"] == date(2027, 1, 31)
    assert d["FY2025-q4"] == date(2026, 5, 31)


def test_qrmp_gstr3b_depends_on_state_group():
    mh = _by_rule(sch.build_calendar(pvt_ltd(gst_filing_frequency="quarterly", state_code="27"), *WINDOW), "gst-gstr3b-quarterly")
    dl = _by_rule(sch.build_calendar(pvt_ltd(gst_filing_frequency="quarterly", state_code="07"), *WINDOW), "gst-gstr3b-quarterly")
    assert mh["FY2026-q2"] == date(2026, 10, 22)
    assert dl["FY2026-q2"] == date(2026, 10, 24)


def test_qrmp_monthly_payment_skips_quarter_end_months():
    d = _by_rule(sch.build_calendar(pvt_ltd(gst_filing_frequency="quarterly"), *WINDOW), "gst-pmt06")
    assert "2026-10" in d and "2026-11" in d            # months 1 and 2 of Oct-Dec quarter
    assert "2026-09" not in d and "2026-12" not in d    # quarter-end months have no PMT-06
    assert d["2026-10"] == date(2026, 11, 25)


def test_monthly_filer_has_no_qrmp_rules():
    ids = {o.rule_id for o in sch.build_calendar(pvt_ltd(), *WINDOW)}
    assert "gst-gstr3b-monthly" in ids and "gst-gstr3b-quarterly" not in ids and "gst-pmt06" not in ids


def test_advance_tax_installments():
    d = _by_rule(sch.build_calendar(pvt_ltd(), *WINDOW), "advance-tax")
    assert d == {"FY2026-i1": date(2026, 6, 15), "FY2026-i2": date(2026, 9, 15),
                 "FY2026-i3": date(2026, 12, 15), "FY2026-i4": date(2027, 3, 15)}


def test_company_annual_filings():
    occs = sch.build_calendar(pvt_ltd(), *WINDOW)
    assert _by_rule(occs, "companies-aoc4")["FY2025-annual"] == date(2026, 10, 30)
    assert _by_rule(occs, "companies-mgt7")["FY2025-annual"] == date(2026, 11, 29)
    assert _by_rule(occs, "companies-agm")["FY2025-annual"] == date(2026, 9, 30)
    assert _by_rule(occs, "itr-audit-cases")["FY2025-annual"] == date(2026, 10, 31)
    assert _by_rule(occs, "companies-dpt3")["FY2025-annual"] == date(2026, 6, 30)
    msme = _by_rule(occs, "companies-msme1")
    assert msme["FY2026-h1"] == date(2026, 10, 31) and msme["FY2025-h2"] == date(2026, 4, 30)


def test_llp_dates_corrected():
    llp = OrgFacts(entity_type="llp", registrations={}, turnover_band="20l-1.5cr")
    occs = sch.build_calendar(llp, *WINDOW)
    assert _by_rule(occs, "llp-form11")["FY2025-annual"] == date(2026, 5, 30)     # NOT 30 July
    assert _by_rule(occs, "llp-form8")["FY2025-annual"] == date(2026, 10, 30)
    assert not any(o.rule_id.startswith("companies-aoc") for o in occs)


def test_pf_esi_only_when_registered():
    assert "pf-monthly" not in {o.rule_id for o in sch.build_calendar(pvt_ltd(), *WINDOW)}
    occs = sch.build_calendar(pvt_ltd(registrations={"gst": True, "pf": True, "esi": True}), *WINDOW)
    assert _by_rule(occs, "pf-monthly")["2026-09"] == date(2026, 10, 15)
    assert "esi-monthly" in {o.rule_id for o in occs}


def test_one_time_deadline_only_inside_window():
    assert "dpdp-readiness" in {o.rule_id for o in sch.build_calendar(pvt_ltd(), *WINDOW)}
    assert "dpdp-readiness" not in {o.rule_id for o in sch.build_calendar(pvt_ltd(), date(2026, 4, 1), date(2027, 4, 1))}


# ------------------------------------------------------------------ applicability

def test_proprietor_small_turnover_gets_nonaudit_itr_only():
    org = OrgFacts(entity_type="sole_proprietorship", registrations={"gst": True}, gst_filing_frequency="quarterly",
                   turnover_band="20l-1.5cr", state_code="07")
    ids = {o.rule_id for o in sch.build_calendar(org, *WINDOW)}
    assert "itr-firm-nonaudit" in ids and "itr-firm-audit" not in ids and "itr-audit-cases" not in ids
    assert not any(i.startswith("companies-") for i in ids)
    assert "tax-audit-report" not in ids


def test_larger_firm_gets_audit_rules_flagged_for_confirmation():
    org = OrgFacts(entity_type="partnership", registrations={"gst": True}, gst_filing_frequency="monthly", turnover_band="5-20cr")
    occs = sch.build_calendar(org, *WINDOW)
    ids = {o.rule_id for o in occs}
    assert {"tax-audit-report", "itr-firm-audit", "gst-gstr9", "gst-gstr9c"} <= ids
    assert all(o.needs_confirmation for o in occs if o.rule_id in ("tax-audit-report", "gst-gstr9"))
    assert _by_rule(occs, "tax-audit-report")["FY2025-annual"] == date(2026, 9, 30)


def test_unregistered_business_gets_no_gst_or_tds():
    org = OrgFacts(entity_type="sole_proprietorship", registrations={}, turnover_band="lt20l")
    ids = {o.rule_id for o in sch.build_calendar(org, *WINDOW)}
    assert not any(i.startswith(("gst-", "tds-", "pf-", "esi-")) for i in ids)
    assert "advance-tax" in ids


def test_unknown_turnover_does_not_guess():
    decisions = {d.rule["id"]: d for d in sch.applicable_rules(OrgFacts(entity_type="partnership", registrations={"gst": True}))}
    assert not decisions["tax-audit-report"].applies and "turnover" in decisions["tax-audit-report"].reason.lower()


def test_every_decision_has_a_reason():
    for d in sch.applicable_rules(pvt_ltd()):
        assert d.reason


def test_empty_or_inverted_window():
    assert sch.build_calendar(pvt_ltd(), date(2027, 1, 1), date(2026, 1, 1)) == []


def test_not_covered_list_is_exposed():
    assert any("Professional Tax" in x["title"] for x in sch.not_covered())


def test_month_end_clamping():
    assert sch._safe_date(2027, 2, 31) == date(2027, 2, 28)
