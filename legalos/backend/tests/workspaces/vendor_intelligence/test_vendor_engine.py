import pytest

from app.shared.india import identifiers as ids
from app.workspaces.vendor_intelligence import engine, registry


def gstin(state="27", pan="AAFFS4321K"):
    first14 = f"{state}{pan}1Z"
    return first14 + ids.gstin_check_char(first14)


def statuses(a):
    return {c.key: c.status for c in a.checks}


def test_valid_gstin_without_registry_is_unverified_never_low():
    a = engine.assess("Shree Steel Traders", gstin())
    assert a.risk_level == "unverified"
    assert statuses(a)["registry"] == "unknown" and statuses(a)["gstin"] == "pass"
    assert "not" in a.summary.lower() or "confirmed" in a.summary.lower()


def test_typo_in_gstin_is_high_risk_instantly():
    g = gstin()
    typo = g[:-1] + ("A" if g[-1] != "A" else "B")
    a = engine.assess("Shree Steel Traders", typo)
    assert a.risk_level == "high" and statuses(a)["gstin"] == "fail"
    assert a.summary.startswith("Do not pay yet")


def test_company_name_but_firm_pan_is_flagged():
    # PAN 4th letter F (firm) but the name claims to be a Private Limited company
    a = engine.assess("Shree Steel Industries Pvt Ltd", gstin(pan="AAFFS4321K"))
    assert statuses(a)["entity"] == "warn" and a.risk_level == "medium"      # "Check before paying", not "Do not pay"
    # consistent: company name with a company PAN
    ok = engine.assess("Apex Shell Logistics Pvt Ltd", gstin(pan="AAACA1111A"))
    assert statuses(ok)["entity"] == "pass"


def test_pan_and_state_consistency():
    g = gstin(state="27", pan="AAFFS4321K")
    assert statuses(engine.assess("X Traders", g, pan="AAFFS9999K"))["pan"] == "fail"
    assert statuses(engine.assess("X Traders", g, pan="AAFFS4321K"))["pan"] == "pass"
    a = engine.assess("X Traders", g, state_code="24")
    assert statuses(a)["state"] == "warn" and a.risk_level == "medium"


def test_no_gstin_is_a_warning_about_input_tax_credit():
    a = engine.assess("Local Supplier", None)
    assert statuses(a)["gstin"] == "warn" and a.risk_level == "medium"
    assert "input tax credit" in a.summary.lower()


def test_udyam_format():
    g = gstin()
    assert statuses(engine.assess("X Traders", g, udyam_number="UDYAM-MH-26-0012345"))["udyam"] == "pass"
    assert statuses(engine.assess("X Traders", g, udyam_number="12345"))["udyam"] == "warn"


@pytest.mark.asyncio
async def test_sample_registry_records_are_labelled_and_deterministic():
    samples = {s["name"]: s["gstin"] for s in registry.sample_gstins()}
    active = await registry.lookup(samples["Shree Steel Traders"])
    assert active.source == "sample" and active.status == "Active" and active.msme_category == "small"
    a = engine.assess("Shree Steel Traders", samples["Shree Steel Traders"], registry=active)
    assert a.risk_level == "low" and "Sample record" in [c.label for c in a.checks if c.key == "registry"][0]

    cancelled = await registry.lookup(samples["Apex Shell Logistics Pvt Ltd"])
    b = engine.assess("Apex Shell Logistics Pvt Ltd", samples["Apex Shell Logistics Pvt Ltd"], registry=cancelled)
    assert b.risk_level == "high" and statuses(b)["registry"] == "fail"

    notfiling = await registry.lookup(samples["Karnavati Steel Trading Pvt Ltd"])
    c = engine.assess("Karnavati Steel Trading Pvt Ltd", samples["Karnavati Steel Trading Pvt Ltd"], registry=notfiling)
    assert c.risk_level == "medium" and statuses(c)["behaviour"] == "warn"


@pytest.mark.asyncio
async def test_unknown_but_valid_gstin_is_never_invented():
    r = await registry.lookup(gstin(pan="AABCX1234Q"))
    assert r.source == "unavailable" and r.legal_name is None


@pytest.mark.asyncio
async def test_registry_name_mismatch_warns():
    g = [s["gstin"] for s in registry.sample_gstins() if s["name"] == "Shree Steel Traders"][0]
    reg = await registry.lookup(g)
    a = engine.assess("Completely Different Name Ltd", g, registry=reg)
    assert statuses(a)["name"] == "warn"
