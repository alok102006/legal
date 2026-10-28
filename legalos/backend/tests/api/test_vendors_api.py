import pytest

from app.config import settings
from app.shared.india import identifiers as ids
from app.workspaces.vendor_intelligence import engine, registry, registry_cache
from app.workspaces.vendor_intelligence.errors import UNAVAILABLE, RegistryError


def _sample(name):
    return next(s["gstin"] for s in registry.sample_gstins() if s["name"] == name)


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


async def _new_org(api, email="v@x.in"):
    r = await api.post("/api/v1/auth/register", json={"email": email, "password": "s3cretpass", "full_name": "V X", "company_name": "V Co"})
    return _auth(r.json()["token"])


async def test_create_check_and_read_back(api):
    g = _sample("Shree Steel Traders")
    r = await api.post("/api/v1/vendors", json={"name": "Shree Steel Traders", "gstin": g})
    assert r.status_code == 201
    v = r.json()
    assert v["risk_level"] == "low" and v["registry_source"] == "sample" and v["msme_category"] == "small"
    assert v["state_name"] == "Maharashtra" and v["pan"] == "AAFFS4321K"
    assert {c["key"] for c in v["checks"]} >= {"gstin", "entity", "registry"}
    got = (await api.get(f"/api/v1/vendors/{v['id']}")).json()
    assert got["id"] == v["id"]
    assert len((await api.get("/api/v1/vendors")).json()) == 1


async def test_fake_and_cancelled_vendors_are_flagged_before_payment(api):
    bad = ids.gstin_check_char("27AAFFS4321K1Z")
    typo = "27AAFFS4321K1Z" + ("A" if bad != "A" else "B")
    r = (await api.post("/api/v1/vendors", json={"name": "Quick Supplies", "gstin": typo})).json()
    assert r["risk_level"] == "high" and r["checks"][0]["status"] == "fail"
    c = (await api.post("/api/v1/vendors", json={"name": "Apex Shell Logistics Pvt Ltd", "gstin": _sample("Apex Shell Logistics Pvt Ltd")})).json()
    assert c["risk_level"] == "high" and c["summary"].startswith("Do not pay yet")


async def test_duplicate_gstin_rejected(api):
    g = _sample("Shree Steel Traders")
    assert (await api.post("/api/v1/vendors", json={"name": "Shree Steel Traders", "gstin": g})).status_code == 201
    dup = await api.post("/api/v1/vendors", json={"name": "Shree Steel Traders 2", "gstin": g})
    assert dup.status_code == 400 and "already" in dup.json()["detail"]


async def test_quick_check_does_not_save(api):
    r = await api.post("/api/v1/vendors/quick-check", json={"name": "Shree Steel Traders", "gstin": _sample("Shree Steel Traders")})
    assert r.status_code == 200 and r.json()["risk_level"] == "low"
    assert (await api.get("/api/v1/vendors")).json() == []


async def test_samples_endpoint_in_demo_mode(api):
    s = (await api.get("/api/v1/vendors/samples")).json()
    assert len(s) == 4 and all(x["label"] for x in s)


async def test_tenancy_isolation(api):
    v = (await api.post("/api/v1/vendors", json={"name": "Shree Steel Traders", "gstin": _sample("Shree Steel Traders")})).json()
    other = await _new_org(api)
    assert (await api.get("/api/v1/vendors", headers=other)).json() == []
    assert (await api.get(f"/api/v1/vendors/{v['id']}", headers=other)).status_code == 404
    assert (await api.delete(f"/api/v1/vendors/{v['id']}", headers=other)).status_code == 404
    assert (await api.post(f"/api/v1/vendors/{v['id']}/recheck", headers=other)).status_code == 404


async def test_update_recheck_and_delete(api):
    v = (await api.post("/api/v1/vendors", json={"name": "Shree Steel Traders"})).json()
    assert v["risk_level"] == "medium"                                  # no GSTIN
    up = (await api.patch(f"/api/v1/vendors/{v['id']}", json={"gstin": _sample("Shree Steel Traders")})).json()
    assert up["risk_level"] == "low" and up["gstin"]
    assert (await api.post(f"/api/v1/vendors/{v['id']}/recheck")).status_code == 200
    assert (await api.delete(f"/api/v1/vendors/{v['id']}")).status_code == 200
    assert (await api.get(f"/api/v1/vendors/{v['id']}")).status_code == 404


async def test_vendor_is_linked_to_its_contracts_by_counterparty_name(api):
    from app.shared.auth.auth_service import DEMO_ORG_ID
    from app.shared.db.models import Document
    from app.shared.db.session import async_session_maker
    from app.workspaces.contract_intelligence.models import Contract

    async with async_session_maker() as s:
        doc = Document(workspace="contract_intelligence", original_filename="a.txt", storage_path="x", organization_id=DEMO_ORG_ID)
        s.add(doc)
        await s.flush()
        s.add(Contract(document_id=doc.id, organization_id=DEMO_ORG_ID, title="Supply Agreement", counterparty_name="Shree Steel Traders",
                       status="analyzed", risk_level="high", overall_score=71))
        await s.commit()
    v = (await api.post("/api/v1/vendors", json={"name": "Shree Steel Traders", "gstin": _sample("Shree Steel Traders")})).json()
    assert [c["title"] for c in v["contracts"]] == ["Supply Agreement"]
    m = (await api.get("/api/v1/vendors/match", params={"name": "Shree Steel Traders Pvt"})).json()
    assert m and m["id"] == v["id"]
    assert (await api.get("/api/v1/vendors/match", params={"name": "Unrelated Co"})).json() is None


# ------------------------------------------------------------------ check desk: more number types

async def test_check_desk_accepts_cin_tan_ifsc_and_others(api):
    async def check(identifier, **extra):
        r = await api.post("/api/v1/vendors/check", json={"identifier": identifier, **extra})
        assert r.status_code == 200, r.text
        return r.json()

    cin = await check("U74999KA2020PTC123456")
    assert cin["kind"] == "cin" and cin["risk_level"] == "unverified" and cin["details"]["state_name"] == "Karnataka"
    assert cin["registry_mode"] == "offline" and "MCA" in cin["summary"]

    assert (await check("MUMS12345B"))["kind"] == "tan"
    ifsc = await check("HDFC0000001")
    assert ifsc["kind"] == "ifsc" and "HDFC Bank" in ifsc["checks"][0]["detail"]
    assert (await check("11520011000123"))["kind"] == "fssai"
    assert (await check("DL/CPM/0012345/000"))["kind"] == "pf"

    bad = await check("U74999KA2099PTC123456")
    assert bad["kind"] == "cin" and bad["risk_level"] == "high" and "year" in bad["summary"]

    # an alphanumeric IEC cannot be guessed (it looks like a PAN), so the caller says what it is
    iec = await check("0305008111", kind="iec")
    assert iec["kind"] == "iec" and iec["risk_level"] == "unverified"
    assert (await api.post("/api/v1/vendors/check", json={"identifier": "x", "kind": "passport"})).status_code == 422


async def test_check_desk_still_handles_gstin_pan_udyam(api):
    g = _sample("Shree Steel Traders")
    assert (await api.post("/api/v1/vendors/check", json={"identifier": g})).json()["kind"] == "gstin"
    assert (await api.post("/api/v1/vendors/check", json={"identifier": "AAFFS4321K"})).json()["kind"] == "pan"
    u = (await api.post("/api/v1/vendors/check", json={"identifier": "UDYAM-XX-26-0012345"})).json()
    assert u["kind"] == "udyam" and u["risk_level"] != "low" and any(c["status"] == "warn" for c in u["checks"])


async def test_risk_rules_are_explained(api):
    r = (await api.get("/api/v1/vendors/risk-rules")).json()
    assert {l["level"] for l in r["levels"]} == {"high", "medium", "low", "unverified"}
    assert any(c["key"] == "registry" for c in r["checks"]) and r["notes"]


# ------------------------------------------------------------------ live registry: cache and "re-check all"

@pytest.fixture
def live_registry(monkeypatch):
    state = {"calls": 0, "fail": False}
    monkeypatch.setattr(registry, "active_provider", lambda: "sandbox")

    async def fake_live(provider, g):
        state["calls"] += 1
        if state["fail"]:
            raise RegistryError(UNAVAILABLE)
        return engine.RegistryResult(source="live", provider=provider, legal_name="Live Supplier", status="Active",
                                     registration_date="2015-04-01", filing_status="Regular")

    monkeypatch.setattr(registry, "_live", fake_live)
    return state


def _g(pan):
    first14 = f"27{pan}1Z"
    return first14 + ids.gstin_check_char(first14)


async def _add(api, name, pan):
    r = await api.post("/api/v1/vendors", json={"name": name, "gstin": _g(pan)})
    assert r.status_code == 201, r.text
    return r.json()


async def test_check_desk_and_vendor_creation_share_one_paid_lookup(api, live_registry):
    g = _g("AAACL1234A")
    first = (await api.post("/api/v1/vendors/check", json={"identifier": g})).json()
    assert first["registry"]["filing_status"] == "Regular" and first["registry"]["cached"] is False
    again = (await api.post("/api/v1/vendors/check", json={"identifier": g})).json()
    assert again["registry"]["cached"] is True and again["registry"]["fetched_at"] == first["registry"]["fetched_at"]
    v = await _add(api, "Live Supplier", "AAACL1234A")
    assert live_registry["calls"] == 1 and v["registry"]["filing_status"] == "Regular"


async def test_recheck_all_respects_the_cache(api, live_registry):
    for i, pan in enumerate(["AAACL1111A", "AAACL2222B", "AAACL3333C"]):
        await _add(api, f"Live Supplier {i}", pan)
    assert live_registry["calls"] == 3
    r = (await api.post("/api/v1/vendors/recheck-all")).json()
    assert live_registry["calls"] == 3                                   # nothing paid again
    assert r["total"] == 3 and r["from_cache"] == 3 and r["live_lookups"] == 0 and r["failed"] == 0 and r["deferred"] == 0
    assert r["registry_mode"] == "live"


async def test_recheck_all_caps_paid_lookups_and_keeps_failed_verdicts(api, live_registry, monkeypatch):
    vendors = [await _add(api, f"Live Supplier {i}", pan) for i, pan in enumerate(["AAACL1111A", "AAACL2222B", "AAACL3333C"])]
    for v in vendors:                                                    # a day later: every answer is stale
        registry_cache.clear(v["gstin"])
    monkeypatch.setattr(settings, "registry_recheck_max_live", 2)
    r = (await api.post("/api/v1/vendors/recheck-all")).json()
    assert r["live_lookups"] == 2 and r["deferred"] == 1 and len(r["deferred_names"]) == 1 and r["max_live_per_run"] == 2

    for v in vendors:
        registry_cache.clear(v["gstin"])
    live_registry["fail"] = True
    monkeypatch.setattr(settings, "registry_recheck_max_live", 10)
    r = (await api.post("/api/v1/vendors/recheck-all")).json()
    assert r["failed"] == 3 and r["live_lookups"] == 0
    kept = (await api.get(f"/api/v1/vendors/{vendors[0]['id']}")).json()
    assert kept["risk_level"] == "low" and kept["registry_source"] == "live"     # a failed lookup never overwrites a good verdict


async def test_single_recheck_uses_the_cache_unless_refresh_is_asked(api, live_registry):
    v = await _add(api, "Live Supplier", "AAACL1111A")
    await api.post(f"/api/v1/vendors/{v['id']}/recheck")
    assert live_registry["calls"] == 1
    await api.post(f"/api/v1/vendors/{v['id']}/recheck", params={"refresh": "true"})
    assert live_registry["calls"] == 2


async def test_recheck_all_reports_changed_verdicts(api, live_registry, monkeypatch):
    v = await _add(api, "Live Supplier", "AAACL1111A")
    assert v["risk_level"] == "low"
    registry_cache.clear(v["gstin"])

    async def now_cancelled(provider, g):
        return engine.RegistryResult(source="live", provider=provider, legal_name="Live Supplier", status="Cancelled",
                                     registration_date="2015-04-01", cancellation_date="2026-09-30")

    monkeypatch.setattr(registry, "_live", now_cancelled)
    r = (await api.post("/api/v1/vendors/recheck-all")).json()
    assert r["live_lookups"] == 1 and [(c["name"], c["previous"], c["current"]) for c in r["changed"]] == [("Live Supplier", "low", "high")]
    assert (await api.get(f"/api/v1/vendors/{v['id']}")).json()["risk_level"] == "high"


async def test_recheck_all_is_writer_only(api):
    from app.shared.auth.auth_service import DEMO_ORG_ID
    from app.shared.auth.security import create_access_token
    from app.shared.db.models import Membership, User
    from app.shared.db.session import async_session_maker

    async with async_session_maker() as s:
        user = User(full_name="Auditor Asha", email="auditor@demo.in", role="business_owner")
        s.add(user)
        await s.flush()
        s.add(Membership(user_id=user.id, organization_id=DEMO_ORG_ID, role="viewer"))
        await s.commit()
        viewer = {"Authorization": f"Bearer {create_access_token(user.id, DEMO_ORG_ID)}"}
    assert (await api.post("/api/v1/vendors/recheck-all", headers=viewer)).status_code == 403
    assert (await api.get("/api/v1/vendors/risk-rules", headers=viewer)).status_code == 200
