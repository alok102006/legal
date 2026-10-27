from tests.api.test_contracts_api import _handler as contract_handler
from tests.api.test_documents_api import handler as doc_handler
from tests.api.test_notices_api import handler as notice_handler


def _combined(call):
    for h in (contract_handler, notice_handler, doc_handler):
        try:
            return h(call)
        except AssertionError:
            continue
    raise AssertionError(call.schema)


async def test_samples_load_into_own_org_and_activity_describes_them(api, fake_llm):
    fake_llm(_combined)
    for kind, prefix in (("contract", "/contracts/"), ("notice", "/notices/"), ("document", "/documents/")):
        r = await api.post(f"/api/v1/samples/{kind}")
        assert r.status_code == 202 and r.json()["path"].startswith(prefix)
    assert (await api.get("/api/v1/contracts")).json()[0]["status"] == "analyzed"
    assert (await api.get("/api/v1/notices")).json()[0]["status"] == "analyzed"
    assert (await api.get("/api/v1/knowledge/documents")).json()[0]["status"] == "ready"

    feed = (await api.get("/api/v1/org/activity")).json()
    texts = " | ".join(x["text"] for x in feed)
    assert "Finished reviewing a contract" in texts and "Read a notice" in texts and "Reviewed a document" in texts
    assert all(x["created_at"] for x in feed) and any(x["link"] for x in feed)

    # another organisation sees none of it
    r = await api.post("/api/v1/auth/register", json={"email": "o@x.in", "password": "s3cretpass", "full_name": "O X", "company_name": "O Co"})
    other = {"Authorization": f"Bearer {r.json()['token']}"}
    assert [x for x in (await api.get("/api/v1/org/activity", headers=other)).json() if x["action"] != "account.registered"] == []
    assert (await api.post("/api/v1/samples/bogus")).status_code == 422
