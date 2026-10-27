from datetime import date

import pytest

from app.workspaces.compliance_center import service

TODAY = date(2026, 10, 22)


@pytest.fixture(autouse=True)
def frozen_today(monkeypatch):
    monkeypatch.setattr(service, "today_ist", lambda: TODAY)


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


async def _new_org(api, email="owner@acme.in"):
    r = await api.post("/api/v1/auth/register", json={
        "email": email, "password": "s3cretpass", "full_name": "Asha Patel", "company_name": "Acme Traders"})
    return _auth(r.json()["token"])


async def test_demo_org_gets_calendar_with_states(api):
    tasks = (await api.get("/api/v1/compliance/tasks")).json()
    assert len(tasks) > 20
    gstr3b = [t for t in tasks if t["rule_id"] == "gst-gstr3b-monthly"]
    assert gstr3b and all(t["source_ref"] and t["penalty_desc"] for t in gstr3b)
    states = {t["state"] for t in tasks}
    assert states <= {"overdue", "due_soon", "upcoming", "done"}
    # 20 Oct 2026 was 2 days ago: GSTR-3B for Sep is overdue, not silently dropped
    sep = next(t for t in gstr3b if t["period_label"] == "Sep 2026")
    assert sep["state"] == "overdue" and sep["days_left"] == -2
    # the due date list is sorted soonest first
    dates = [t["due_date"] for t in tasks]
    assert dates == sorted(dates)


async def test_summary_counts(api):
    s = (await api.get("/api/v1/compliance/summary")).json()
    assert s["needs_profile"] is False
    assert s["overdue"] >= 1
    assert s["next_deadlines"] and s["next_deadlines"][0]["days_left"] >= 0
    assert s["rules_version"]


async def test_complete_and_reopen(api):
    tasks = (await api.get("/api/v1/compliance/tasks")).json()
    t = next(t for t in tasks if t["state"] == "overdue")
    r = await api.patch(f"/api/v1/compliance/tasks/{t['id']}", json={"status": "completed", "note": "Filed on 21 Oct, ARN 123"})
    assert r.status_code == 200 and r.json()["state"] == "done" and r.json()["completion_note"].startswith("Filed")
    again = await api.patch(f"/api/v1/compliance/tasks/{t['id']}", json={"status": "pending"})
    assert again.json()["state"] == "overdue" and again.json()["completed_at"] is None


async def test_sync_is_idempotent(api):
    first = (await api.get("/api/v1/compliance/tasks")).json()
    r = (await api.post("/api/v1/compliance/sync")).json()
    assert r["created"] == 0 and r["removed"] == 0
    assert len((await api.get("/api/v1/compliance/tasks")).json()) == len(first)


async def test_profile_change_removes_pending_but_keeps_completed_and_custom(api):
    h = await _new_org(api)
    await api.patch("/api/v1/org", headers=h, json={
        "entity_type": "private_limited", "state_code": "27", "turnover_band": "5-20cr",
        "gst_filing_frequency": "monthly", "registrations": {"gst": True}})
    tasks = (await api.get("/api/v1/compliance/tasks", headers=h)).json()
    gst = [t for t in tasks if t["rule_id"] == "gst-gstr1-monthly"]
    assert gst
    done = await api.patch(f"/api/v1/compliance/tasks/{gst[0]['id']}", headers=h, json={"status": "completed"})
    assert done.status_code == 200
    custom = await api.post("/api/v1/compliance/tasks", headers=h, json={
        "title": "Renew FSSAI licence", "category": "license", "due_date": "2026-12-01"})
    assert custom.status_code == 201 and custom.json()["is_custom"] is True

    # GST registration dropped -> pending GST tasks go away; completed + custom stay
    await api.patch("/api/v1/org", headers=h, json={"registrations": {"gst": False}})
    after = (await api.get("/api/v1/compliance/tasks", headers=h)).json()
    gst_after = [t for t in after if (t["rule_id"] or "").startswith("gst-")]
    assert [t["id"] for t in gst_after] == [gst[0]["id"]] and gst_after[0]["state"] == "done"
    assert any(t["title"] == "Renew FSSAI licence" for t in after)


async def test_system_tasks_cannot_be_deleted_or_edited_but_custom_can(api):
    tasks = (await api.get("/api/v1/compliance/tasks")).json()
    sys_task = tasks[0]
    assert (await api.delete(f"/api/v1/compliance/tasks/{sys_task['id']}")).status_code == 400
    assert (await api.patch(f"/api/v1/compliance/tasks/{sys_task['id']}", json={"due_date": "2030-01-01"})).status_code == 400

    c = (await api.post("/api/v1/compliance/tasks", json={"title": "Board meeting", "due_date": "2026-11-05"})).json()
    edited = await api.patch(f"/api/v1/compliance/tasks/{c['id']}", json={"due_date": "2026-11-06"})
    assert edited.status_code == 200 and edited.json()["due_date"] == "2026-11-06"
    assert (await api.delete(f"/api/v1/compliance/tasks/{c['id']}")).status_code == 200


async def test_tenancy_isolation(api):
    mine = (await api.get("/api/v1/compliance/tasks")).json()
    other = await _new_org(api, "intruder@other.in")
    assert (await api.get("/api/v1/compliance/tasks", headers=other)).json() == []
    assert (await api.patch(f"/api/v1/compliance/tasks/{mine[0]['id']}", headers=other, json={"status": "completed"})).status_code == 404
    assert (await api.get("/api/v1/compliance/summary", headers=other)).json()["needs_profile"] is True


async def test_new_org_gets_calendar_when_profile_completed(api):
    h = await _new_org(api)
    assert (await api.get("/api/v1/compliance/tasks", headers=h)).json() == []
    await api.patch("/api/v1/org", headers=h, json={"entity_type": "llp", "state_code": "07", "turnover_band": "lt20l"})
    tasks = (await api.get("/api/v1/compliance/tasks", headers=h)).json()
    ids = {t["rule_id"] for t in tasks}
    assert "llp-form8" in ids and "companies-aoc4" not in ids
    # corrected LLP Form 11 date (30 May, not 30 July) falls before the window, so Form 8 is the LLP filing shown
    f8 = next(t for t in tasks if t["rule_id"] == "llp-form8")
    assert f8["due_date"] == "2026-10-30"


async def test_bulk_complete_catch_up_is_org_scoped(api):
    tasks = (await api.get("/api/v1/compliance/tasks")).json()
    overdue_ids = [t["id"] for t in tasks if t["state"] == "overdue"]
    assert len(overdue_ids) >= 3
    other = await _new_org(api, "other@x.in")
    # another organisation cannot complete our tasks
    assert (await api.post("/api/v1/compliance/tasks/bulk-complete", headers=other, json={"ids": overdue_ids})).json() == {"completed": 0}
    r = await api.post("/api/v1/compliance/tasks/bulk-complete", json={"ids": overdue_ids, "note": "Filed before joining"})
    assert r.json() == {"completed": len(overdue_ids)}
    after = (await api.get("/api/v1/compliance/summary")).json()
    assert after["overdue"] == 0
    # idempotent
    assert (await api.post("/api/v1/compliance/tasks/bulk-complete", json={"ids": overdue_ids})).json() == {"completed": 0}


async def test_concurrent_first_visits_do_not_collide(api):
    """The home page asks for /summary and /tasks at the same moment on a brand-new calendar."""
    import asyncio

    from sqlalchemy import delete

    from app.workspaces.compliance_center.models import ComplianceTask
    from app.shared.db.session import async_session_maker

    h = await _new_org(api, "race@acme.in")
    await api.patch("/api/v1/org", headers=h, json={"entity_type": "private_limited", "state_code": "27", "turnover_band": "5-20cr",
                                                    "gst_filing_frequency": "monthly", "registrations": {"gst": True}})
    async with async_session_maker() as s:                       # simulate "first visit, no calendar yet"
        await s.execute(delete(ComplianceTask))
        await s.commit()

    responses = await asyncio.gather(*[
        api.get(p, headers=h) for p in ("/api/v1/compliance/summary", "/api/v1/compliance/tasks",
                                        "/api/v1/compliance/summary", "/api/v1/compliance/tasks")])
    assert [r.status_code for r in responses] == [200, 200, 200, 200]
    tasks = (await api.get("/api/v1/compliance/tasks", headers=h)).json()
    keys = [(t["rule_id"], t["period_label"]) for t in tasks]
    assert len(keys) == len(set(keys)) and len(keys) > 10          # built exactly once


async def test_rules_overview_explains_everything(api):
    r = (await api.get("/api/v1/compliance/rules")).json()
    assert r["applicable"] and r["not_covered"]
    assert all(x["reason"] for x in r["applicable"] + r["not_applicable"])
    assert any(x["id"] == "gst-gstr1-quarterly" for x in r["not_applicable"])      # demo org files monthly
