from app.shared.india import identifiers as ids


def _gstin(state="27", pan="AABCK1234F"):
    first14 = f"{state}{pan}1Z"
    return first14 + ids.gstin_check_char(first14)


async def _register(api, email="owner@acme.in", company="Acme Traders", password="s3cretpass"):
    r = await api.post("/api/v1/auth/register", json={
        "email": email, "password": password, "full_name": "Asha Patel", "company_name": company})
    return r


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


async def test_register_login_me_roundtrip(api):
    r = await _register(api)
    assert r.status_code == 201
    token = r.json()["token"]
    assert r.json()["organization"]["onboarding_completed"] is False

    me = await api.get("/api/v1/auth/me", headers=_auth(token))
    assert me.status_code == 200 and me.json()["user"]["email"] == "owner@acme.in"
    assert me.json()["user"]["role"] == "owner" and me.json()["user"]["is_demo"] is False

    login = await api.post("/api/v1/auth/login", json={"email": "OWNER@acme.in", "password": "s3cretpass"})
    assert login.status_code == 200 and login.json()["token"]


async def test_wrong_password_and_unknown_email_look_identical(api):
    await _register(api)
    bad_pw = await api.post("/api/v1/auth/login", json={"email": "owner@acme.in", "password": "nope-nope"})
    unknown = await api.post("/api/v1/auth/login", json={"email": "ghost@acme.in", "password": "nope-nope"})
    assert bad_pw.status_code == unknown.status_code == 401
    assert bad_pw.json()["detail"] == unknown.json()["detail"]


async def test_register_validation(api):
    assert (await _register(api, password="short")).status_code == 400
    assert (await _register(api)).status_code == 201
    assert (await _register(api)).status_code == 400            # duplicate email
    r = await api.post("/api/v1/auth/register", json={
        "email": "not-an-email", "password": "longenough1", "full_name": "A B", "company_name": "Co"})
    assert r.status_code == 422


async def test_invalid_token_is_rejected(api):
    r = await api.get("/api/v1/auth/me", headers=_auth("garbage"))
    assert r.status_code == 401


async def test_demo_persona_works_without_token(api):
    r = await api.get("/api/v1/auth/me", headers={"X-User-Role": "ca"})
    assert r.status_code == 200 and r.json()["user"]["is_demo"] is True
    assert r.json()["user"]["full_name"] == "Anjali Sharma"


async def test_onboarding_with_gstin_fills_profile(api):
    token = (await _register(api)).json()["token"]
    h = _auth(token)

    bad = await api.patch("/api/v1/org", json={"gstin": "27AABCK1234F1ZX"}, headers=h)
    assert bad.status_code == 400 and "GSTIN" in bad.json()["detail"]

    ok = await api.patch("/api/v1/org", json={"gstin": _gstin(), "msme_category": "small"}, headers=h)
    assert ok.status_code == 200
    body = ok.json()
    assert body["state_code"] == "27" and body["state_name"] == "Maharashtra"
    assert body["pan"] == "AABCK1234F" and body["entity_type"] == "private_limited"
    assert body["onboarding_completed"] is True and body["missing_fields"] == []


async def test_gstin_cannot_be_claimed_by_two_organisations(api):
    t1 = (await _register(api, email="a@x.in", company="A Co")).json()["token"]
    t2 = (await _register(api, email="b@x.in", company="B Co")).json()["token"]
    g = _gstin()
    assert (await api.patch("/api/v1/org", json={"gstin": g}, headers=_auth(t1))).status_code == 200
    dup = await api.patch("/api/v1/org", json={"gstin": g}, headers=_auth(t2))
    assert dup.status_code == 400 and "already registered" in dup.json()["detail"]


async def test_gstin_check_endpoint_is_offline_and_honest(api):
    token = (await _register(api)).json()["token"]
    r = await api.post("/api/v1/org/gstin-check", json={"gstin": _gstin()}, headers=_auth(token))
    assert r.json()["valid"] is True and r.json()["registry_checked"] is False


async def test_audit_log_records_actions(api):
    from sqlalchemy import select

    from app.shared.db.models import AuditEvent
    from app.shared.db.session import async_session_maker

    token = (await _register(api)).json()["token"]
    await api.patch("/api/v1/org", json={"industry": "Textiles"}, headers=_auth(token))
    async with async_session_maker() as s:
        actions = [a for (a,) in (await s.execute(select(AuditEvent.action))).all()]
    assert "account.registered" in actions and "org.updated" in actions
