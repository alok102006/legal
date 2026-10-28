import json
import os
import time
from datetime import date

import pytest

from app.config import settings
from app.shared.india import identifiers as ids
from app.workspaces.vendor_intelligence import engine, registry, registry_cache
from app.workspaces.vendor_intelligence.errors import UNAVAILABLE, RegistryError


def gstin(state="27", pan="AAFFS4321K"):
    first14 = f"{state}{pan}1Z"
    return first14 + ids.gstin_check_char(first14)


@pytest.fixture
def live(monkeypatch):
    """A fake paid registry: counts calls, answers from `answers` (a RegistryResult or an exception)."""
    state = {"calls": 0, "answer": None}
    monkeypatch.setattr(registry, "active_provider", lambda: "sandbox")

    async def fake_live(provider, g):
        state["calls"] += 1
        if isinstance(state["answer"], Exception):
            raise state["answer"]
        return engine.RegistryResult(source="live", provider=provider, legal_name="Shree Steel Traders", status="Active",
                                     registration_date="2019-06-12", filing_status=state["answer"] or "Regular")

    monkeypatch.setattr(registry, "_live", fake_live)
    return state


# ------------------------------------------------------------------ 24 h cache

async def test_second_lookup_is_served_from_the_cache_without_a_paid_call(live):
    g = gstin()
    first = await registry.lookup(g)
    second = await registry.lookup(g)
    assert live["calls"] == 1
    assert first.source == "live" and not first.cached and first.fetched_at
    assert second.source == "live" and second.cached and second.fetched_at == first.fetched_at
    assert second.legal_name == "Shree Steel Traders" and second.filing_status == "Regular"


async def test_force_bypasses_the_cache(live):
    g = gstin()
    await registry.lookup(g)
    await registry.lookup(g, force=True)
    assert live["calls"] == 2


async def test_entries_expire_after_the_ttl(live, monkeypatch):
    g = gstin()
    await registry.lookup(g)
    path = registry_cache._path(g)
    row = json.load(open(path))
    row["at"] = time.time() - (settings.registry_cache_ttl_hours * 3600 + 60)
    json.dump(row, open(path, "w"))
    await registry.lookup(g)
    assert live["calls"] == 2


async def test_errors_are_never_cached(live):
    live["answer"] = RegistryError(UNAVAILABLE)
    g = gstin()
    assert (await registry.lookup(g)).error_kind == UNAVAILABLE
    assert (await registry.lookup(g)).error_kind == UNAVAILABLE
    assert live["calls"] == 2 and not os.path.exists(registry_cache._path(g))


async def test_not_found_is_cached_but_only_briefly(live):
    live["answer"] = RegistryError("not_found")
    g = gstin()
    r1, r2 = await registry.lookup(g), await registry.lookup(g)
    assert r1.error_kind == r2.error_kind == "not_found" and r2.cached and live["calls"] == 1
    path = registry_cache._path(g)
    row = json.load(open(path))
    row["at"] = time.time() - registry_cache.NOT_FOUND_TTL_SECONDS - 5
    json.dump(row, open(path, "w"))
    await registry.lookup(g)
    assert live["calls"] == 2


async def test_cache_is_per_gstin_and_survives_a_new_process(live):
    a, b = gstin(), gstin(pan="AAACK9876M")
    await registry.lookup(a)
    await registry.lookup(b)
    assert live["calls"] == 2
    registry_cache.COUNTERS.update(hits=0, misses=0)         # "restart": only the files remain
    await registry.lookup(a)
    assert live["calls"] == 2 and registry_cache.COUNTERS["hits"] == 1


def test_needs_live_call_reflects_the_cache(live):
    g = gstin()
    assert registry.needs_live_call(g) and not registry.needs_live_call(None) and not registry.needs_live_call("junk")
    registry_cache.put(g, registry_cache.FOUND, {"legal_name": "X", "status": "Active", "provider": "sandbox"})
    assert not registry.needs_live_call(g)


async def test_sample_records_are_free_and_not_cached(monkeypatch):
    sample = registry.sample_gstins()[0]["gstin"]
    r = await registry.lookup(sample)
    assert r.source == "sample" and not os.path.exists(registry_cache._path(sample))


# ------------------------------------------------------------------ filing status surfaces in the verdict

async def test_filing_status_from_the_provider_is_checked(live):
    g = gstin()
    live["answer"] = "Not Filed (3 months)"
    reg = await registry.lookup(g)
    a = engine.assess("Shree Steel Traders", g, registry=reg, today=date(2026, 10, 28))
    assert {c.key: c.status for c in a.checks}["filing"] == "warn" and a.risk_level == "medium"
    assert reg.filing_status == "Not Filed (3 months)"

    live["answer"] = "Regular"
    reg2 = await registry.lookup(g, force=True)
    a2 = engine.assess("Shree Steel Traders", g, registry=reg2, today=date(2026, 10, 28))
    assert {c.key: c.status for c in a2.checks}["filing"] == "pass" and a2.risk_level == "low"


# ------------------------------------------------------------------ PAN 5th letter vs name (warning only)

def test_company_name_that_does_not_match_the_pan_initial_warns():
    g = gstin(pan="AAACS4321K")
    a = engine.assess("Zenith Metals Private Limited", g)
    c = {x.key: x for x in a.checks}["pan_name"]
    assert c.status == "warn" and a.risk_level == "medium"
    ok = engine.assess("Shree Steel Private Limited", g)
    assert "pan_name" not in {x.key for x in ok.checks}


def test_individual_pans_are_not_name_checked():
    # sole proprietors trade under names unrelated to their own
    g = gstin(pan="AABPK1234F")
    assert "pan_name" not in {x.key for x in engine.assess("Zenith Traders", g).checks}


def test_registry_legal_name_can_satisfy_the_pan_check():
    g = gstin(pan="AAACS4321K")
    reg = engine.RegistryResult(source="live", legal_name="Shree Steel Traders", status="Active", registration_date="2015-01-01")
    a = engine.assess("Zenith Brand", g, registry=reg)
    assert "pan_name" not in {x.key for x in a.checks}


# ------------------------------------------------------------------ other identifiers

def test_valid_cin_is_unverified_with_decoded_facts():
    a = engine.assess_identifier("cin", "U74999KA2020PTC123456")
    assert a.risk_level == "unverified" and "Karnataka" in a.checks[0].detail and "MCA" in a.summary
    assert a.derived["state_name"] == "Karnataka"


def test_invalid_numbers_are_high_risk_with_the_reason():
    for kind, value in [("cin", "U74999KA2099PTC123456"), ("ifsc", "SBIN1001234"), ("tan", "MUMS1234B"), ("fssai", "123")]:
        a = engine.assess_identifier(kind, value)
        assert a.risk_level == "high" and a.checks[0].status == "fail", kind


def test_warnings_make_other_identifiers_medium():
    a = engine.assess_identifier("cin", "L74999KA2020PTC123456")
    assert a.risk_level == "medium" and any(c.key == "format_note" for c in a.checks)


def test_ifsc_names_the_bank():
    assert "HDFC Bank" in engine.assess_identifier("ifsc", "HDFC0000001").checks[0].detail


# ------------------------------------------------------------------ the rules are explained

def test_every_check_key_the_engine_can_emit_is_explained():
    documented = {c["key"] for c in engine.RISK_RULES["checks"]}
    g = gstin(pan="AAACS4321K")
    cancelled = engine.RegistryResult(source="live", legal_name="Other Ltd", status="Cancelled", registration_date="2026-06-01",
                                      filing_status="Not filed", note="n")
    produced = set()
    for a in (
        engine.assess("Zenith Metals Pvt Ltd", g, "AAACS4321K", "07", "UDYAM-MH-26-0012345", registry=cancelled, today=date(2026, 10, 28)),
        engine.assess("Zenith Metals LLP", g, "AAACS4321L", "07", "bad", registry=engine.RegistryResult(source="unavailable", error_kind="not_found")),
        engine.assess("X", None), engine.assess("X", None, pan="AABCK1234F"),
        engine.assess_identifier("cin", "L74999KA2020PTC123456"), engine.assess_identifier("cin", "x"),
    ):
        produced |= {c.key for c in a.checks}
    assert produced <= documented, produced - documented
    assert {l["level"] for l in engine.RISK_RULES["levels"]} == {"high", "medium", "low", "unverified"}
