import json
from datetime import date

import pytest

from app.core.llm.errors import LLMUnavailable
from app.workspaces.knowledge_hub import service
from app.workspaces.knowledge_hub.engine.ai import DocAnswer, DocumentReview, QueryPlan

HR_POLICY = """EMPLOYEE HANDBOOK - KULKARNI TEXTILES PVT LTD

1. Working hours
The standard working week is 48 hours across six days. Overtime is paid at twice the normal rate.

2. Notice period
Managers must give 60 days written notice before resigning. All other staff must give 30 days notice.
During probation of six months, either side may end employment with 7 days notice.

3. Leave
Employees are entitled to 24 days of paid leave per calendar year. Unused leave up to 12 days may be carried forward.

4. Confidentiality
Employees must not disclose pricing, customer lists or dyeing formulas during or after employment.
"""

LICENCE = """FIRE SAFETY CERTIFICATE
Issued to Kulkarni Textiles Pvt Ltd, Plot 14, Sachin GIDC, Surat.
This certificate is valid until 31 December 2026 and must be renewed before that date.
The premises were inspected and found to comply with the Gujarat Fire Prevention and Life Safety Measures Act."""


@pytest.fixture(autouse=True)
def frozen(monkeypatch):
    monkeypatch.setattr(service, "today_ist", lambda: date(2026, 10, 27))


def handler(call):
    if call.schema is DocumentReview:
        if "FIRE SAFETY" in call.prompt:
            return json.dumps(dict(doc_type="Licence or certificate", title="Fire Safety Certificate", language="English",
                                   summary_points=["Fire safety approval for the Sachin GIDC plant."], key_facts=[{"label": "Valid until", "value": "31 December 2026"}],
                                   expiry_date="2026-12-31", expiry_label="Fire safety certificate valid until",
                                   expiry_quote="valid until 31 December 2026 and must be renewed before that date", concerns=[], missing_items=[],
                                   suggested_questions=["When does the fire certificate expire?"]))
        return json.dumps(dict(doc_type="HR policy", title="Employee Handbook", language="English", summary_points=["Rules on hours, notice, leave and confidentiality."],
                               key_facts=[{"label": "Manager notice period", "value": "60 days"}],
                               concerns=[{"title": "Confidentiality has no end date", "why_it_matters": "Staff are bound forever, which may not be enforceable.",
                                          "quote": "must not disclose pricing, customer lists or dyeing formulas during or after employment"}],
                               missing_items=["Grievance procedure"], suggested_questions=["What is the notice period for managers?", "How much paid leave do employees get?"]))
    if call.schema is QueryPlan:
        q = call.prompt.split("Latest question:")[-1].strip()
        if "spaceship" in q:
            return json.dumps(dict(standalone_question=q, search_queries=["spaceship parking policy"], answerable_from_documents=True))
        if q.lower().startswith("and for"):
            return json.dumps(dict(standalone_question="What is the notice period for other staff?", search_queries=["notice period staff", "resignation notice days"], answerable_from_documents=True))
        return json.dumps(dict(standalone_question=q, search_queries=[q, "notice period resignation"], answerable_from_documents=True))
    if call.schema is DocAnswer:
        asked = call.prompt.split("Question:")[-1].split("=== EXCERPTS")[0]
        if "notice" not in call.prompt.split("=== EXCERPTS")[-1].lower():   # like the real model: no answer when the excerpts don't cover it
            return json.dumps(dict(answer="Your documents don't cover this.", found_in_documents=False, citations=[]))
        if "other staff" in asked:
            return json.dumps(dict(answer="Other staff must give 30 days notice. [C1]", found_in_documents=True,
                                   citations=[{"quote": "All other staff must give 30 days notice.", "excerpt": "C1"}]))
        return json.dumps(dict(answer="Managers must give 60 days' notice. [C1]", found_in_documents=True,
                               citations=[{"quote": "Managers must give 60 days written notice before resigning", "excerpt": "C1"}]))
    raise AssertionError(call.schema)


async def _upload(api, text=HR_POLICY, name="handbook.txt", headers=None, category="HR"):
    r = await api.post("/api/v1/knowledge/documents/upload", files={"file": (name, text.encode())}, data={"category": category}, headers=headers or {})
    assert r.status_code == 202, r.text
    return r.json()["id"]


async def _conv(api, collection=None, headers=None):
    r = await api.post("/api/v1/knowledge/conversations", json={"collection": collection}, headers=headers or {})
    assert r.status_code == 201
    return r.json()["id"]


async def test_upload_index_review_and_collections(api, fake_llm):
    fake_llm(handler)
    did = await _upload(api)
    d = (await api.get(f"/api/v1/knowledge/documents/{did}")).json()
    assert d["status"] == "ready" and d["review_state"] == "done" and d["doc_type"] == "HR policy" and d["language"] == "English"
    assert d["chunk_count"] >= 2 and any(c["section"] for c in d["chunks"])
    assert d["concerns"][0]["verified"] is True and d["suggested_questions"]
    assert d["title"] == "Employee Handbook" and d["category"] == "HR"
    cols = (await api.get("/api/v1/knowledge/collections")).json()
    assert cols == [{"name": "HR", "count": 1, "ready": 1}]
    assert (await api.get("/api/v1/knowledge/documents", params={"collection": "Finance"})).json() == []


async def test_conversation_answers_with_verified_citations_and_follow_up(api, fake_llm):
    fake_llm(handler)
    await _upload(api)
    cid = await _conv(api)
    r = (await api.post(f"/api/v1/knowledge/conversations/{cid}/ask", json={"question": "What notice period do managers have?"})).json()
    assert r["found_in_documents"] is True and "60 days" in r["content"]
    assert r["citations"][0]["verified"] is True and r["citations"][0]["document_title"] == "Employee Handbook"
    assert r["citations"][0]["section"].startswith("2.") and r["confidence"] >= 70
    assert r["sources"] and r["sources"][0]["marker"] == "C1"
    # follow-up uses the conversation
    r2 = (await api.post(f"/api/v1/knowledge/conversations/{cid}/ask", json={"question": "and for other staff?"})).json()
    assert "30 days" in r2["content"] and r2["citations"][0]["verified"]
    conv = (await api.get(f"/api/v1/knowledge/conversations/{cid}")).json()
    assert [t["role"] for t in conv["turns"]] == ["user", "assistant", "user", "assistant"]
    assert conv["title"].startswith("What notice period")                     # auto-titled from the first question
    assert (await api.get("/api/v1/knowledge/conversations")).json()[0]["id"] == cid


async def test_streaming_endpoint_emits_stage_delta_done(api, fake_llm):
    fake_llm(handler)
    await _upload(api)
    cid = await _conv(api)
    async with api.stream("POST", f"/api/v1/knowledge/conversations/{cid}/ask/stream", json={"question": "What notice period do managers have?"}) as resp:
        assert resp.status_code == 200
        body = (await resp.aread()).decode()
    assert "event: stage" in body and "event: delta" in body and "event: done" in body
    done = json.loads([l for l in body.split("\n") if l.startswith("data:")][-1][5:])
    assert done["citations"][0]["verified"] is True


async def test_nothing_relevant_does_not_call_the_answer_model(api, fake_llm):
    state = fake_llm(handler)
    await _upload(api)
    cid = await _conv(api)
    r = (await api.post(f"/api/v1/knowledge/conversations/{cid}/ask", json={"question": "What is our policy on spaceship parking?"})).json()
    assert r["found_in_documents"] is False and r["citations"] == [] and r["confidence"] == 0
    assert not any(c.schema is DocAnswer for c in state.calls)


async def test_collection_scoping(api, fake_llm):
    fake_llm(handler)
    await _upload(api)                                             # HR
    await _upload(api, LICENCE, "fire.txt", category="Licences")
    cid = await _conv(api, collection="Licences")
    r = (await api.post(f"/api/v1/knowledge/conversations/{cid}/ask", json={"question": "What notice period do managers have?"})).json()
    assert r["found_in_documents"] is False                        # the handbook is outside this collection
    hits = (await api.get("/api/v1/knowledge/search", params={"q": "notice period", "collection": "HR"})).json()
    assert hits and all(h["document_title"] == "Employee Handbook" for h in hits)


async def test_expiry_date_becomes_a_calendar_reminder(api, fake_llm):
    fake_llm(handler)
    did = await _upload(api, LICENCE, "fire.txt", category="Licences")
    d = (await api.get(f"/api/v1/knowledge/documents/{did}")).json()
    assert d["expiry_date"] == "2026-12-31" and d["in_calendar"] is True
    tasks = (await api.get("/api/v1/compliance/tasks")).json()
    assert next(t for t in tasks if t["title"].startswith("Fire safety certificate valid until"))["due_date"] == "2026-12-31"
    assert (await api.delete(f"/api/v1/knowledge/documents/{did}")).status_code == 200
    assert not [t for t in (await api.get("/api/v1/compliance/tasks")).json() if t["title"].startswith("Fire safety")]


async def test_ai_outage_keeps_document_searchable_and_chat_fails_honestly(api, fake_llm):
    def down(call):
        raise LLMUnavailable("503")
    fake_llm(down)
    did = await _upload(api)
    d = (await api.get(f"/api/v1/knowledge/documents/{did}")).json()
    assert d["status"] == "ready" and d["review_state"] == "failed"
    assert (await api.get("/api/v1/knowledge/search", params={"q": "leave carried forward"})).json()
    cid = await _conv(api)
    assert (await api.post(f"/api/v1/knowledge/conversations/{cid}/ask", json={"question": "How many days of leave?"})).status_code == 503


async def test_suggestions_come_from_documents(api, fake_llm):
    fake_llm(handler)
    assert (await api.get("/api/v1/knowledge/suggestions")).json() == {"questions": []}
    await _upload(api)
    qs = (await api.get("/api/v1/knowledge/suggestions")).json()["questions"]
    assert "What is the notice period for managers?" in qs


async def test_tenancy_isolation_for_documents_and_conversations(api, fake_llm):
    fake_llm(handler)
    did = await _upload(api)
    cid = await _conv(api)
    r = await api.post("/api/v1/auth/register", json={"email": "o@x.in", "password": "s3cretpass", "full_name": "O X", "company_name": "O Co"})
    other = {"Authorization": f"Bearer {r.json()['token']}"}
    assert (await api.get("/api/v1/knowledge/documents", headers=other)).json() == []
    assert (await api.get(f"/api/v1/knowledge/documents/{did}", headers=other)).status_code == 404
    assert (await api.get(f"/api/v1/knowledge/conversations/{cid}", headers=other)).status_code == 404
    assert (await api.post(f"/api/v1/knowledge/conversations/{cid}/ask", json={"question": "notice period?"}, headers=other)).status_code == 404
    assert (await api.get("/api/v1/knowledge/search", params={"q": "dyeing formulas"}, headers=other)).json() == []
    other_conv = await _conv(api, headers=other)
    r2 = (await api.post(f"/api/v1/knowledge/conversations/{other_conv}/ask", json={"question": "What notice period do managers have?"}, headers=other)).json()
    assert r2["found_in_documents"] is False


async def test_rename_and_move_document_between_collections(api, fake_llm):
    fake_llm(handler)
    did = await _upload(api)
    r = (await api.patch(f"/api/v1/knowledge/documents/{did}", json={"category": "Policies", "title": "Staff handbook"})).json()
    assert r["category"] == "Policies" and r["title"] == "Staff handbook"
    assert [c["name"] for c in (await api.get("/api/v1/knowledge/collections")).json()] == ["Policies"]


async def test_retry_reindexes_without_duplicating(api, fake_llm):
    fake_llm(handler)
    did = await _upload(api)
    n1 = (await api.get(f"/api/v1/knowledge/documents/{did}")).json()["chunk_count"]
    assert (await api.post(f"/api/v1/knowledge/documents/{did}/retry")).status_code == 202
    d = (await api.get(f"/api/v1/knowledge/documents/{did}")).json()
    assert d["chunk_count"] == n1
    hits = (await api.get("/api/v1/knowledge/search", params={"q": "dyeing formulas"})).json()
    assert len(hits) == len({(h["document_id"], h["snippet"]) for h in hits})
