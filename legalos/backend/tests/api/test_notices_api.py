import json
from datetime import date

import pytest

from app.core.llm.errors import LLMUnavailable
from app.workspaces.legal_notice_center import service
from app.workspaces.legal_notice_center.engine.schemas import NoticeFacts, NoticeReplyDraft
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
