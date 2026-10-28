import json
from datetime import date

import pytest

from app.core.llm.errors import LLMUnavailable
from app.workspaces.legal_notice_center import service
from app.workspaces.legal_notice_center.engine.schemas import NoticeFacts, NoticeOcr, NoticeReplyDraft
from tests.workspaces.legal_notice_center.sample_notices import CHEQUE_BOUNCE_NOTICE

TODAY = date(2026, 10, 22)


@pytest.fixture(autouse=True)
def frozen(monkeypatch):
    monkeypatch.setattr(service, "IST_TODAY", lambda: TODAY)


def handler(call):
    if call.schema is NoticeFacts:
        return json.dumps(dict(
            notice_type="cheque_bounce", title="Cheque bounce notice from Mehta & Associates", issuer_name="Mehta & Associates",
            reference_number="MA/2026/118", notice_date="2026-10-12", summary_points=["Cheque for Rs 2,40,000 bounced; pay in 15 days."],
            demands=["Pay Rs 2,40,000"], amount_claimed=240000, response_days=15,
            deadline_quote="within 15 days from the receipt of this notice", statutes_cited=["Section 138 NI Act"],
            consequences_stated="Criminal proceedings", if_ignored="A criminal complaint can be filed against you.",
            demand_quote="you are hereby called upon to pay the said sum of Rs. 2,40,000/- within 15 days from the receipt of this notice",
            amount_quote="a quote that is not in the notice at all, so it must be reported as unverified",
            what_to_do_now=["Find the invoices dated 2 and 9 September", "Show the notice to your advocate"]))
    if call.schema is NoticeReplyDraft:
        extra = " (firmer tone)" if "firmer" in call.prompt else ""
        return json.dumps(dict(reply_text=f"Sir, we acknowledge your notice{extra}. [CONFIRM: were goods received?]",
                               points_to_confirm=["Goods received?"], documents_to_gather=["Invoices"]))
    raise AssertionError(call.schema)


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


async def _paste(api, headers=None, received="2026-10-22"):
    r = await api.post("/api/v1/notices/text", json={"text": CHEQUE_BOUNCE_NOTICE, "received_date": received}, headers=headers or {})
    assert r.status_code == 202, r.text
    return r.json()["id"]


async def test_paste_analyse_and_read_back(api, fake_llm):
    fake_llm(handler)
    cid = await _paste(api)
    d = (await api.get(f"/api/v1/notices/{cid}")).json()
    assert d["status"] == "analyzed" and d["notice_type"] == "cheque_bounce" and d["type_label"] == "Cheque bounce notice"
    assert d["urgency"] == "critical" and d["response_deadline"] == "2026-11-06" and d["days_left"] == 15
    assert d["deadline_verified"] is True and d["deadline_source"] == "stated"
    assert d["legal_ref"].startswith("Negotiable Instruments Act")
    assert len(d["drafts"]) == 1 and d["drafts"][0]["placeholders"] == ["[CONFIRM: were goods received?]"]
    assert d["review_status"] == "draft" and d["in_calendar"] is True
    assert d["actions"] == ["Find the invoices dated 2 and 9 September", "Show the notice to your advocate"] and d["actions_done"] == []
    assert d["if_ignored"].startswith("A criminal") and d["legal_if_ignored"] and d["received_confirmed"] is True
    kq = {q["kind"]: q["verified"] for q in d["key_quotes"]}
    assert kq == {"deadline": True, "amount": False, "demand": True}


async def test_action_checklist_state_is_saved_and_received_date_flag(api, fake_llm):
    fake_llm(handler)
    cid = await _paste(api)
    assert (await api.patch(f"/api/v1/notices/{cid}", json={"actions_done": [1, 1, 7]})).json()["actions_done"] == [1]
    # no received date given -> the deadline is counted from today but flagged as unconfirmed until the user says
    r = await api.post("/api/v1/notices/text", json={"text": CHEQUE_BOUNCE_NOTICE})
    d = (await api.get(f"/api/v1/notices/{r.json()['id']}")).json()
    assert d["needs_received_date"] is True and d["received_confirmed"] is False
    d2 = (await api.patch(f"/api/v1/notices/{d['id']}", json={"received_date": "2026-10-22"})).json()
    assert d2["needs_received_date"] is False and d2["received_confirmed"] is True


async def test_deadline_is_added_to_the_compliance_calendar_and_follows_changes(api, fake_llm):
    fake_llm(handler)
    cid = await _paste(api)
    tasks = (await api.get("/api/v1/compliance/tasks")).json()
    t = next(t for t in tasks if t["title"].startswith("Reply to notice"))
    assert t["due_date"] == "2026-11-06" and t["is_custom"] is True

    # received later -> deadline and calendar move together
    r = await api.patch(f"/api/v1/notices/{cid}", json={"received_date": "2026-10-25"})
    assert r.json()["response_deadline"] == "2026-11-09"
    t2 = next(t for t in (await api.get("/api/v1/compliance/tasks")).json() if t["title"].startswith("Reply to notice"))
    assert t2["due_date"] == "2026-11-09"

    # closing the case completes the reminder; deleting removes it
    await api.patch(f"/api/v1/notices/{cid}", json={"status": "closed"})
    t3 = next(t for t in (await api.get("/api/v1/compliance/tasks")).json() if t["title"].startswith("Reply to notice"))
    assert t3["state"] == "done"
    assert (await api.delete(f"/api/v1/notices/{cid}")).status_code == 200
    assert not [t for t in (await api.get("/api/v1/compliance/tasks")).json() if t["title"].startswith("Reply to notice")]


async def test_ai_outage_marks_failed_with_retry_and_no_canned_reply(api, fake_llm):
    def down(call):
        raise LLMUnavailable("503")
    fake_llm(down)
    cid = await _paste(api)
    d = (await api.get(f"/api/v1/notices/{cid}")).json()
    assert d["status"] == "failed" and d["error_kind"] == "unavailable"
    assert d["drafts"] == [] and d["urgency"] is None            # no fake "medium urgency", no canned reply
    fake_llm(handler)
    assert (await api.post(f"/api/v1/notices/{cid}/retry")).status_code == 202
    assert (await api.get(f"/api/v1/notices/{cid}")).json()["status"] == "analyzed"


async def test_regenerate_and_edit_create_versions_and_reset_review(api, fake_llm):
    fake_llm(handler)
    cid = await _paste(api)
    await api.patch(f"/api/v1/notices/{cid}", json={"review_status": "lawyer_approved"})
    d = (await api.post(f"/api/v1/notices/{cid}/draft", json={"instructions": "make it firmer"})).json()
    assert [x["version"] for x in d["drafts"]] == [2, 1] and "firmer tone" in d["drafts"][0]["reply_text"]
    assert d["review_status"] == "draft"                         # new text must be reviewed again
    d2 = (await api.put(f"/api/v1/notices/{cid}/draft", json={"reply_text": "My own edited reply with [CONFIRM: date of delivery]"})).json()
    assert d2["drafts"][0]["author"] == "user" and d2["drafts"][0]["placeholders"] == ["[CONFIRM: date of delivery]"]
    assert (await api.patch(f"/api/v1/notices/{cid}", json={"review_status": "ready_for_lawyer"})).json()["review_status"] == "ready_for_lawyer"


async def test_file_upload_and_validation(api, fake_llm):
    fake_llm(handler)
    ok = await api.post("/api/v1/notices/upload", files={"file": ("notice.txt", CHEQUE_BOUNCE_NOTICE.encode())}, data={"received_date": "2026-10-22"})
    assert ok.status_code == 202
    assert (await api.get(f"/api/v1/notices/{ok.json()['id']}")).json()["status"] == "analyzed"
    assert (await api.post("/api/v1/notices/upload", files={"file": ("x.exe", b"MZ")})).status_code == 400
    assert (await api.post("/api/v1/notices/text", json={"text": "too short"})).status_code == 422


async def test_tenancy_and_list_order(api, fake_llm):
    fake_llm(handler)
    cid = await _paste(api)
    r = await api.post("/api/v1/auth/register", json={"email": "o@x.in", "password": "s3cretpass", "full_name": "O X", "company_name": "O Co"})
    other = _auth(r.json()["token"])
    assert (await api.get("/api/v1/notices", headers=other)).json() == []
    for call in (api.get(f"/api/v1/notices/{cid}", headers=other), api.delete(f"/api/v1/notices/{cid}", headers=other),
                 api.post(f"/api/v1/notices/{cid}/draft", json={}, headers=other)):
        assert (await call).status_code == 404
    lst = (await api.get("/api/v1/notices")).json()
    assert lst[0]["id"] == cid and lst[0]["urgency"] == "critical"


# ------------------------------------------------------------------ production-grade behaviour

SARFAESI_NOTICE = """STATE BANK OF INDIA, STRESSED ASSETS RECOVERY BRANCH, SURAT
DEMAND NOTICE UNDER SECTION 13(2) OF THE SECURITISATION AND RECONSTRUCTION OF FINANCIAL ASSETS AND ENFORCEMENT OF SECURITY INTEREST ACT, 2002
To: Kulkarni Textiles Pvt Ltd (Borrower)
Your loan account has been classified as a non-performing asset. You are hereby called upon to discharge in full your liabilities of Rs. 48,50,000/- within 60 days from the date of this notice, failing which the bank shall exercise its rights under Section 13(4).
Authorised Officer
"""


def _facts_handler(facts: dict, reply="Sir, [CONFIRM: was the loan repaid in part?]"):
    def h(call):
        if call.schema is NoticeFacts:
            return json.dumps({"title": "Notice", "summary_points": ["x"], **facts}, ensure_ascii=False)
        if call.schema is NoticeReplyDraft:
            return json.dumps(dict(reply_text=reply, points_to_confirm=[], documents_to_gather=[]))
        if call.schema is NoticeOcr:
            return json.dumps({"pages": [{"number": 1, "text": CHEQUE_BOUNCE_NOTICE[:400]}, {"number": 2, "text": CHEQUE_BOUNCE_NOTICE[400:]}]})
        raise AssertionError(call.schema)
    return h


async def test_missing_notice_date_is_asked_for_then_drives_the_deadline(api, fake_llm):
    fake_llm(_facts_handler(dict(notice_type="sarfaesi_13_2", amount_claimed=4850000, response_days=60, response_days_from="notice_date",
                                 deadline_quote="You are hereby called upon to discharge in full your liabilities of Rs. 48,50,000/- within 60 days from the date of this notice, failing which the bank shall exercise its rights under Section 13(4).")))
    r = await api.post("/api/v1/notices/text", json={"text": SARFAESI_NOTICE, "received_date": "2026-10-22"})
    d = (await api.get(f"/api/v1/notices/{r.json()['id']}")).json()
    assert d["needs_notice_date"] is True and d["response_deadline"] is None and d["deadline_source"] == "unknown"
    assert d["type_info"]["statutory_window"]["citation"] == "SARFAESI Act 2002, s.13(2)" and d["urgency"] == "high"
    d2 = (await api.patch(f"/api/v1/notices/{d['id']}", json={"notice_date": "2026-10-05"})).json()
    assert d2["needs_notice_date"] is False and d2["response_deadline"] == "2026-12-04" and d2["in_calendar"] is True
    assert d2["deadline_verified"] is True and {b["basis"] for b in d2["deadline_basis"]} == {"stated_period", "statutory"}
    assert "Rs 48,50,000" in d2["lawyer_brief"] and "4. LAW" in d2["lawyer_brief"]


async def test_court_summons_gets_an_action_plan_and_a_lawyer_gate(api, fake_llm):
    fake_llm(_facts_handler(dict(notice_type="court_summons", hearing_date="2026-11-30"), reply="STEPS\n1. Engage an advocate."))
    r = await api.post("/api/v1/notices/text", json={"text": CHEQUE_BOUNCE_NOTICE, "received_date": "2026-10-22"})
    d = (await api.get(f"/api/v1/notices/{r.json()['id']}")).json()
    assert d["draft_kind"] == "action_plan" and d["lawyer_required"] is True
    assert d["drafts"][0]["reply_text"].startswith("ACTION PLAN") and d["type_info"]["handler"] == "lawyer_required"
    # hearing date unverified (no quote) but earlier than the 30-day written statement window
    assert d["response_deadline"] == "2026-11-21" and d["deadline_source"] == "statutory_default"


async def test_page_photos_upload_as_one_notice(api, fake_llm):
    fake_llm(_facts_handler(dict(notice_type="cheque_bounce", response_days=15,
                                 deadline_quote="within 15 days from the receipt of this notice")))
    files = [("files", ("page1.jpg", b"\xff\xd8\xff" + b"1" * 50, "image/jpeg")), ("files", ("page2.jpg", b"\xff\xd8\xff" + b"2" * 50, "image/jpeg"))]
    r = await api.post("/api/v1/notices/upload", files=files, data={"received_date": "2026-10-22"})
    assert r.status_code == 202, r.text
    d = (await api.get(f"/api/v1/notices/{r.json()['id']}")).json()
    assert d["status"] == "analyzed" and d["pages"] == 2 and d["ocr_used"] is True and d["deadline_verified"] is True
    assert d["source_name"] == "page1.jpg (+1 pages)"
    mixed = [("files", ("a.pdf", b"%PDF-1.4", "application/pdf")), ("files", ("b.jpg", b"\xff\xd8\xff", "image/jpeg"))]
    assert (await api.post("/api/v1/notices/upload", files=mixed)).status_code == 400
    assert (await api.delete(f"/api/v1/notices/{d['id']}")).status_code == 200


async def test_hindi_notice_detail(api, fake_llm):
    from tests.workspaces.legal_notice_center.sample_notices import HINDI_CHEQUE_NOTICE
    quote = "अतः आपको इस नोटिस की प्राप्ति के १५ दिनों के भीतर रु. 2,40,000/- का भुगतान करने हेतु कहा जाता है"
    fake_llm(_facts_handler(dict(notice_type="cheque_bounce", language="hi", notice_date="2026-10-12", response_days=15,
                                 deadline_quote=quote, summary_local=["आपका चेक बाउंस हुआ।"])))
    r = await api.post("/api/v1/notices/text", json={"text": HINDI_CHEQUE_NOTICE, "received_date": "2026-10-22"})
    d = (await api.get(f"/api/v1/notices/{r.json()['id']}")).json()
    assert d["language"] == "hi" and d["summary_local"] == ["आपका चेक बाउंस हुआ।"]
    assert d["key_quotes"] == [{"kind": "deadline", "text": quote, "verified": True}]
    assert d["response_deadline"] == "2026-11-06" and d["notice_date_verified"] is True
