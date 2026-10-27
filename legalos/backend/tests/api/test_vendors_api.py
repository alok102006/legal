from app.shared.india import identifiers as ids
from app.workspaces.vendor_intelligence import registry


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
