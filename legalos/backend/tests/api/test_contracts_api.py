import json

from app.core.llm.errors import LLMAuthError, LLMUnavailable
from app.workspaces.contract_intelligence.engine.schemas import ChatAnswer, ChecklistSweep, ContractFacts, RiskAnalysis
from tests.workspaces.contract_intelligence.sample_contracts import SUPPLY_AGREEMENT

QUOTE = ("The Buyer shall indemnify the Supplier against all losses, claims and expenses of whatever nature "
         "arising out of this Agreement, without limit.")


def _handler(call):
    if call.schema is ContractFacts:
        return json.dumps(dict(
            title="Supply Agreement", contract_type="supply", summary_points=["Steel supply deal."],
            parties=[{"name": "Kumar Auto Components Private Limited", "role": "Buyer"},
                     {"name": "Shree Steel Traders", "role": "Supplier"}],
            payment_days=60, auto_renewal=True, renewal_notice_days=90, liability_cap_present=False, end_date="2031-03-31",
            governing_law="Laws of Singapore", termination_notice_days_other=15, stamp_duty_mentioned=False))
    if call.schema is RiskAnalysis:
        return json.dumps({"findings": [{
            "segment_id": "S6", "category": "liability_indemnity", "severity": "critical",
            "title": "Unlimited indemnity", "why_it_matters": "You pay for any loss.",
            "quote": QUOTE, "recommendation": "Cap it.", "suggested_wording": "Liability capped at fees paid."}],
            "missing_protections": []})
    if call.schema is ChatAnswer:
        return json.dumps({"answer": "Payment is due within 60 days of invoice receipt.", "found_in_contract": True,
                           "citations": [{"quote": "The Buyer shall pay each invoice within 60 days of receipt of the invoice.",
                                          "segment_id": "S3"}]})
    if call.schema is ChecklistSweep:
        return json.dumps({"items": []})
    raise AssertionError(call.schema)


def _upload(api, content=SUPPLY_AGREEMENT.encode(), name="supply.txt", headers=None, party=None):
    data = {"client_party": party} if party else None
    return api.post("/api/v1/contracts/upload", files={"file": (name, content)}, data=data, headers=headers or {})


async def _new_org_headers(api, email):
    r = await api.post("/api/v1/auth/register", json={
        "email": email, "password": "s3cretpass", "full_name": "Other Person", "company_name": "Other Co"})
    return {"Authorization": f"Bearer {r.json()['token']}"}


async def test_upload_analyse_and_read_back(api, fake_llm):
    fake_llm(_handler)
    up = await _upload(api, party="Kumar Auto Components Private Limited")
    assert up.status_code == 202
    cid = up.json()["id"]

    d = (await api.get(f"/api/v1/contracts/{cid}")).json()
    assert d["status"] == "analyzed" and d["stage"] == "done"
    assert d["contract_type"] == "supply" and d["counterparty_name"] == "Shree Steel Traders"
    assert d["risk_level"] == "high" and d["overall_score"] >= 55
    assert d["summary_points"] == ["Steel supply deal."]
    assert len(d["segments"]) >= 7

    titles = {f["title"]: f for f in d["findings"]}
    assert titles["Unlimited indemnity"]["verified"] is True
    assert any(f["rule_id"] == "IN-MSME-45-BUYER" for f in d["findings"])
    assert d["findings"][0]["severity"] == "critical"          # most severe first

    lst = (await api.get("/api/v1/contracts")).json()
    assert lst[0]["finding_counts"]["critical"] == 1 and lst[0]["filename"] == "supply.txt"


async def test_contract_dates_become_calendar_reminders_without_duplicates(api, fake_llm):
    fake_llm(_handler)
    cid = (await _upload(api)).json()["id"]

    def reminders(tasks):
        return {t["title"].split(":")[0]: t for t in tasks if t["title"].startswith(("Contract ends", "Last day to stop"))}

    r = reminders((await api.get("/api/v1/compliance/tasks")).json())
    assert set(r) == {"Contract ends", "Last day to stop auto-renewal"}
    assert r["Contract ends"]["due_date"] == "2031-03-31"
    assert r["Last day to stop auto-renewal"]["due_date"] == "2030-12-31"       # 31 Mar 2031 minus 90 days

    await api.post(f"/api/v1/contracts/{cid}/retry")                              # re-analysis must not duplicate
    assert len(reminders((await api.get("/api/v1/compliance/tasks")).json())) == 2

    await api.delete(f"/api/v1/contracts/{cid}")
    assert reminders((await api.get("/api/v1/compliance/tasks")).json()) == {}


async def test_ai_outage_marks_failed_not_safe_and_retry_recovers(api, fake_llm):
    def down(call):
        raise LLMUnavailable("503")
    fake_llm(down)
    cid = (await _upload(api)).json()["id"]
    d = (await api.get(f"/api/v1/contracts/{cid}")).json()
    assert d["status"] == "failed" and d["error_kind"] == "unavailable"
    assert d["overall_score"] is None and d["findings"] == []     # NOT "risk 0"

    fake_llm(_handler)
    assert (await api.post(f"/api/v1/contracts/{cid}/retry")).status_code == 202
    d2 = (await api.get(f"/api/v1/contracts/{cid}")).json()
    assert d2["status"] == "analyzed" and d2["error_message"] is None and d2["findings"]


async def test_invalid_api_key_is_reported_as_auth_problem(api, fake_llm):
    def bad_key(call):
        raise LLMAuthError("401")
    fake_llm(bad_key)
    cid = (await _upload(api)).json()["id"]
    d = (await api.get(f"/api/v1/contracts/{cid}")).json()
    assert d["status"] == "failed" and d["error_kind"] == "auth"
    assert "not configured" in d["error_message"]


async def test_upload_validation(api):
    assert (await _upload(api, b"MZ\x90\x00", "virus.exe")).status_code == 400
    assert (await _upload(api, b"not really a pdf", "fake.pdf")).status_code == 400
    assert (await _upload(api, b"", "empty.txt")).status_code == 400
    assert (await _upload(api, b"x" * (10 * 1024 * 1024 + 1), "big.txt")).status_code == 400


async def test_tenancy_isolation(api, fake_llm):
    fake_llm(_handler)
    cid = (await _upload(api)).json()["id"]                       # demo org
    other = await _new_org_headers(api, "intruder@other.in")

    assert (await api.get("/api/v1/contracts", headers=other)).json() == []
    assert (await api.get(f"/api/v1/contracts/{cid}", headers=other)).status_code == 404
    assert (await api.delete(f"/api/v1/contracts/{cid}", headers=other)).status_code == 404
    assert (await api.post(f"/api/v1/contracts/{cid}/chat", json={"question": "What is the term?"}, headers=other)).status_code == 404
    assert (await api.get(f"/api/v1/contracts/{cid}/file", headers=other)).status_code == 404
    # the owner still sees it
    assert (await api.get(f"/api/v1/contracts/{cid}")).status_code == 200


async def test_chat_is_cited_and_persisted(api, fake_llm):
    fake_llm(_handler)
    cid = (await _upload(api)).json()["id"]
    r = await api.post(f"/api/v1/contracts/{cid}/chat", json={"question": "When must I pay invoices?"})
    assert r.status_code == 200
    body = r.json()
    assert body["found_in_contract"] is True and body["citations"][0]["verified"] is True
    assert "could not match" not in body["content"]
    msgs = (await api.get(f"/api/v1/contracts/{cid}/messages")).json()
    assert [m["role"] for m in msgs] == ["user", "assistant"]


async def test_chat_negotiation_cites_top_findings_in_order(api, fake_llm):
    fake_llm(_handler)
    cid = (await _upload(api, party="Kumar Auto Components Private Limited")).json()["id"]
    detail = (await api.get(f"/api/v1/contracts/{cid}")).json()
    top = next(f for f in detail["findings"] if f["counts_toward_score"] and f["quote"])
    r = (await api.post(f"/api/v1/contracts/{cid}/chat", json={"question": "What should I negotiate first?"})).json()
    added = [c for c in r["citations"] if c.get("finding")]
    assert added and added[0]["finding"] == top["title"] and added[0]["verified"] is True


async def test_chat_enforceability_gets_the_legal_note(api, fake_llm):
    fake_llm(_handler)
    cid = (await _upload(api, party="Kumar Auto Components Private Limited")).json()["id"]

    def answer(call):
        if call.schema is ChatAnswer:
            assert "REVIEW FINDINGS" in call.prompt and "Unlimited indemnity" in call.prompt
            return json.dumps({"answer": "The Buyer must indemnify the Supplier without limit.", "found_in_contract": True,
                               "citations": [{"quote": QUOTE, "segment_id": "S6"}]})
        return _handler(call)
    fake_llm(answer)
    r = (await api.post(f"/api/v1/contracts/{cid}/chat", json={"question": "Is this indemnity enforceable?"})).json()
    assert "Legal note" in r["content"] and "Indian Contract Act" in r["content"]


async def test_multiple_photos_upload_as_one_contract(api, fake_llm):
    import io

    from PIL import Image

    def jpg():
        buf = io.BytesIO()
        Image.new("RGB", (800, 1100), "white").save(buf, format="JPEG")
        return buf.getvalue()

    pages = SUPPLY_AGREEMENT.split("4. TERM AND TERMINATION")

    def handler(call):
        if call.schema.__name__ == "_OcrResult":
            return json.dumps({"pages": [{"number": 1, "text": pages[0]},
                                         {"number": 2, "text": "4. TERM AND TERMINATION" + pages[1]}]})
        return _handler(call)
    fake_llm(handler)
    r = await api.post("/api/v1/contracts/upload", files=[("files", ("p1.jpg", jpg())), ("files", ("p2.jpg", jpg()))])
    assert r.status_code == 202, r.text
    assert r.json()["filename"] == "p1 (2 pages).pdf"
    d = (await api.get(f"/api/v1/contracts/{r.json()['id']}")).json()
    assert d["status"] == "analyzed" and d["ocr_used"] is True and d["page_count"] == 2
    assert d["contract_type_label"] == "Supply agreement"
    assert d["score_breakdown"]["contributions"] and d["score_breakdown"]["review"]["ocr_calls"] == 1

    mixed = await api.post("/api/v1/contracts/upload", files=[("files", ("p1.jpg", jpg())), ("files", ("x.txt", b"hello"))])
    assert mixed.status_code == 400


async def test_chat_ai_outage_is_503_with_clear_message(api, fake_llm):
    fake_llm(_handler)
    cid = (await _upload(api)).json()["id"]

    def down(call):
        raise LLMUnavailable("503")
    fake_llm(down)
    r = await api.post(f"/api/v1/contracts/{cid}/chat", json={"question": "Anything here?"})
    assert r.status_code == 503 and r.json()["retryable"] is True


async def test_finding_status_and_delete(api, fake_llm):
    fake_llm(_handler)
    cid = (await _upload(api)).json()["id"]
    fid = (await api.get(f"/api/v1/contracts/{cid}")).json()["findings"][0]["id"]
    r = await api.patch(f"/api/v1/contracts/{cid}/findings/{fid}", json={"status": "resolved"})
    assert r.status_code == 200 and r.json()["status"] == "resolved"
    assert (await api.delete(f"/api/v1/contracts/{cid}")).status_code == 200
    assert (await api.get(f"/api/v1/contracts/{cid}")).status_code == 404


async def test_viewer_role_is_read_only(api, fake_llm):
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

    fake_llm(_handler)
    cid = (await _upload(api)).json()["id"]                       # owner uploads
    assert (await _upload(api, headers=viewer)).status_code == 403
    assert (await api.delete(f"/api/v1/contracts/{cid}", headers=viewer)).status_code == 403
    assert (await api.get(f"/api/v1/contracts/{cid}", headers=viewer)).status_code == 200   # can read


async def test_interrupted_jobs_are_recovered_on_startup(api):
    from sqlalchemy import select

    from app.shared.auth.auth_service import DEMO_ORG_ID
    from app.shared.db.models import Document
    from app.shared.db.session import async_session_maker
    from app.workspaces.contract_intelligence import service
    from app.workspaces.contract_intelligence.models import Contract

    async with async_session_maker() as s:
        doc = Document(workspace="contract_intelligence", original_filename="x.txt", storage_path="x", organization_id=DEMO_ORG_ID)
        s.add(doc)
        await s.flush()
        s.add(Contract(document_id=doc.id, organization_id=DEMO_ORG_ID, title="stuck", status="processing", stage="analysing"))
        await s.commit()
    assert await service.mark_interrupted_jobs() == 1
    async with async_session_maker() as s:
        c = (await s.execute(select(Contract))).scalar_one()
    assert c.status == "failed" and c.error_kind == "interrupted"
