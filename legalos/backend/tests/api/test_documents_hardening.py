"""Documents workspace: any-file ingest, exact-token search, routing, overviews, robustness (fake LLM only)."""
import asyncio
import io
import json
import re
import uuid
from datetime import date

import pytest
from sqlalchemy import select

from app.shared.db.session import async_session_maker
from app.workspaces.knowledge_hub import service
from app.workspaces.knowledge_hub.engine import retrieval
from app.workspaces.knowledge_hub.engine.ai import DocAnswer, DocDigest, DocumentReview, QueryPlan
from app.workspaces.knowledge_hub.models import DocChunk, KnowledgeDocument
from tests.api.test_documents_api import LICENCE, _conv, _upload, handler


@pytest.fixture(autouse=True)
def frozen(monkeypatch):
    monkeypatch.setattr(service, "today_ist", lambda: date(2026, 10, 27))


def _review_json(title="Document", language="English", doc_type="Other"):
    return json.dumps(dict(doc_type=doc_type, title=title, language=language, summary_points=[f"About {title}."]))


async def _doc_row(did) -> KnowledgeDocument:
    async with async_session_maker() as s:
        return await s.get(KnowledgeDocument, uuid.UUID(str(did)))


def _marker_for(excerpts: str, text: str) -> str:
    """The [[Cn | ...]] marker of the excerpt containing `text` (what a real model would cite)."""
    blocks = re.findall(r"\[\[(C\d+) \|[^\n]*\]\]\n(.*?)(?=\n\n\[\[C|\Z)", excerpts, re.S)
    return next(m for m, body in blocks if text in body)


def _xlsx(rows) -> bytes:
    import openpyxl

    wb = openpyxl.Workbook()
    for r in rows:
        wb.active.append(r)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


# ------------------------------------------------------------------ files and exact tokens

async def test_spreadsheet_rows_are_indexed_and_found_by_exact_code(api, fake_llm):
    fake_llm(lambda call: _review_json("Dealer price list", doc_type="Price list"))
    data = _xlsx([["SKU", "Description", "Price (Rs)"]] + [[f"SIP-FAS-{i:03d}", f"Hex nut M{i}", 300 + i] for i in range(1, 30)])
    r = await api.post("/api/v1/knowledge/documents/upload", files={"file": ("prices.xlsx", data)}, data={"category": "Finance"})
    d = (await api.get(f"/api/v1/knowledge/documents/{r.json()['id']}")).json()
    assert d["status"] == "ready" and d["file_type"] == "XLSX"
    assert any("SKU: SIP-FAS-017 | Description: Hex nut M17 | Price (Rs): 317" in c["text"] for c in d["chunks"])
    hits = (await api.get("/api/v1/knowledge/search", params={"q": "price of SIP-FAS-017"})).json()
    assert "SIP-FAS-017" in hits[0]["snippet"] and "exact" in hits[0]["via"]


def _png() -> bytes:
    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (60, 40), "white").save(buf, format="PNG")
    return buf.getvalue()


async def test_photo_of_a_certificate_is_read_with_ocr(api, fake_llm):
    def h(call):
        if call.schema.__name__ == "_OcrResult":
            assert call.files and call.files[0][1] == "image/png"
            return json.dumps({"pages": [{"number": 1, "text": "TRADE LICENCE\nLicence No. SMC/TL/2026/4471\nValid until 31 March 2027."}]})
        return _review_json("Trade licence", doc_type="Licence or certificate")
    fake_llm(h)
    r = await api.post("/api/v1/knowledge/documents/upload", files={"file": ("licence.png", _png())}, data={"category": "Licences"})
    assert r.status_code == 202
    d = (await api.get(f"/api/v1/knowledge/documents/{r.json()['id']}")).json()
    assert d["status"] == "ready" and d["ocr_used"] is True
    assert any("SMC/TL/2026/4471" in c["text"] for c in d["chunks"])


async def test_typed_pdf_with_a_scanned_page_ocrs_only_that_page(api, fake_llm):
    from PIL import Image
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfgen import canvas

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    for k, line in enumerate(["LEAVE POLICY", "Casual leave is twelve days in a calendar year for every employee.",
                              "Sick leave is seven days a year; a doctor's certificate is needed after three days.",
                              "Annexure A, the signed board approval, follows on the next page."]):
        c.drawString(40, 800 - 16 * k, line)
    c.showPage()
    c.drawImage(ImageReader(Image.new("RGB", (300, 400), "white")), 0, 0, width=595, height=842)
    c.showPage()
    c.save()
    ocr_pages = []

    def h(call):
        if call.schema.__name__ == "_OcrResult":
            import pypdfium2
            ocr_pages.append(len(pypdfium2.PdfDocument(call.files[0][0])))
            return json.dumps({"pages": [{"number": 1, "text": "ANNEXURE A\nApproved by the Board of Directors on 12 August 2026."}]})
        return _review_json("Leave policy", doc_type="HR policy")
    fake_llm(h)
    r = await api.post("/api/v1/knowledge/documents/upload", files={"file": ("leave.pdf", buf.getvalue())}, data={"category": "HR"})
    d = (await api.get(f"/api/v1/knowledge/documents/{r.json()['id']}")).json()
    assert ocr_pages == [1] and d["ocr_used"] is True and d["page_count"] == 2      # only the scanned page went to OCR
    assert any(c["page"] == 2 and "12 August 2026" in c["text"] for c in d["chunks"])
    assert any(c["page"] == 1 and "Casual leave is twelve days" in c["text"] for c in d["chunks"])


async def test_hindi_document_language_comes_from_the_text(api, fake_llm):
    fake_llm(lambda call: _review_json("Leave policy", language="English"))
    hindi = "छुट्टी नीति\n\n1. सवेतन अवकाश\nसभी कर्मचारियों को प्रति कैलेंडर वर्ष 24 दिन का सवेतन अवकाश मिलेगा।\n\n2. बीमारी अवकाश\nप्रति वर्ष 7 दिन का बीमारी अवकाश मिलेगा।"
    did = await _upload(api, hindi, "chutti.txt")
    assert (await api.get(f"/api/v1/knowledge/documents/{did}")).json()["language"] == "Hindi"


@pytest.mark.parametrize("name,data,msg", [
    ("old.doc", b"\xd0\xcf\x11\xe0" + b"\x00" * 64, "save it as .docx"),
    ("locked.xlsx", b"\xd0\xcf\x11\xe0" + b"\x00" * 64, "password-protected"),
    ("fake.png", b"GIF89a....", "not a valid image"),
])
async def test_unusable_files_are_rejected_with_a_clear_message(api, name, data, msg):
    r = await api.post("/api/v1/knowledge/documents/upload", files={"file": (name, data)})
    assert r.status_code == 400 and msg in r.json()["detail"]


async def test_unreadable_file_fails_with_a_typed_reason(api, fake_llm):
    import zipfile

    fake_llm(handler)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:                  # looks like a workbook from outside, but is not one
        z.writestr("[Content_Types].xml", "<Types/>")
        z.writestr("xl/workbook.xml", "not xml at all")
    r = await api.post("/api/v1/knowledge/documents/upload", files={"file": ("broken.xlsx", buf.getvalue())})
    d = (await api.get(f"/api/v1/knowledge/documents/{r.json()['id']}")).json()
    assert d["status"] == "failed" and d["error_kind"] == "bad_input" and "could not be opened" in d["error_message"]


# ------------------------------------------------------------------ answering

async def test_what_documents_do_i_have_is_answered_without_ai(api, fake_llm):
    state = fake_llm(handler)
    await _upload(api)
    await _upload(api, LICENCE, "fire.txt", category="Licences")
    cid = await _conv(api)
    before = len(state.calls)
    r = (await api.post(f"/api/v1/knowledge/conversations/{cid}/ask", json={"question": "What documents do I have?"})).json()
    assert len(state.calls) == before                                       # no planner, no answer call
    assert "You have 2 documents" in r["content"] and "Employee Handbook" in r["content"] and "Fire Safety Certificate" in r["content"]
    assert "valid until 31 Dec 2026" in r["content"]
    r2 = (await api.post(f"/api/v1/knowledge/conversations/{cid}/ask", json={"question": "mere paas kaun se documents hain?"})).json()
    assert "You have 2 documents" in r2["content"] and len(state.calls) == before


async def test_unanswered_question_suggests_the_closest_documents(api, fake_llm):
    def h(call):
        if call.schema is DocAnswer:
            return json.dumps(dict(answer="Your documents don't cover the fire NOC fee.", found_in_documents=False, citations=[]))
        if call.schema is QueryPlan:
            return json.dumps(dict(standalone_question="What fee is paid to renew the fire safety certificate?",
                                   search_queries=["fire certificate renewal fee"], answerable_from_documents=True))
        return handler(call)
    fake_llm(h)
    await _upload(api)
    await _upload(api, LICENCE, "fire.txt", category="Licences")
    cid = await _conv(api)
    r = (await api.post(f"/api/v1/knowledge/conversations/{cid}/ask", json={"question": "fire NOC renewal fee kitni hai?"})).json()
    assert r["found_in_documents"] is False and "closest to this subject" in r["content"]
    assert r["content"].index("Fire Safety Certificate") < r["content"].index("Employee Handbook")   # best match first


LONG_SOP = "\n\n".join(
    f"{i}. STEP {i} OF THE PURCHASE PROCEDURE\n{i}.1 " + (f"For step {i} the purchase team records the vendor details, checks the quotation and files form PUR-F-{i:02d} within {i + 2} working days. " * 5)
    for i in range(1, 13)) + "\n\n13. RECORDS\n13.1 All purchase records are kept for eight years in the ERP system and in the record room."


async def test_overview_of_a_long_document_digests_all_of_it_in_one_extra_call(api, fake_llm):
    seen = []

    def h(call):
        seen.append(call.schema.__name__)
        if call.schema is DocumentReview:
            return _review_json("Purchase SOP", doc_type="SOP")
        if call.schema is QueryPlan:
            return json.dumps(dict(intent="overview", standalone_question="Summarise the purchase SOP", search_queries=["purchase SOP"], answerable_from_documents=True))
        if call.schema is DocDigest:
            passages = re.findall(r"\[S(\d+)\][^\n]*\n([^\n]+)", call.prompt)
            assert any("eight years" in t for _, t in passages)                  # the end of the document is read
            pts = [{"point": f"Point {i}", "excerpt": f"S{i}", "quote": t[:80]} for i, t in passages[::3]]
            pts.append({"point": "Records kept 8 years", "excerpt": f"S{passages[-1][0]}", "quote": "All purchase records are kept for eight years in the ERP system"})
            pts.append({"point": "Invented point", "excerpt": "S0", "quote": "the vendor must pay a deposit of ten crore rupees before any order"})
            return json.dumps({"points": pts})
        assert call.schema is DocAnswer
        excerpts = call.prompt.split("=== EXCERPTS ===")[1]
        assert "eight years" in excerpts and "Document profile (not quotable)" in excerpts and "Invented point" not in excerpts
        marker = _marker_for(excerpts, "eight years")
        return json.dumps(dict(answer=f"The SOP sets out 12 purchase steps and keeps records for eight years. [{marker}]", found_in_documents=True,
                               citations=[{"quote": "All purchase records are kept for eight years in the ERP system", "excerpt": marker}]))
    fake_llm(h)
    did = await _upload(api, LONG_SOP, "sop.txt")
    assert (await api.get(f"/api/v1/knowledge/documents/{did}")).json()["chunk_count"] > service.OVERVIEW_DIRECT_CHUNKS
    seen.clear()
    cid = await _conv(api)
    r = (await api.post(f"/api/v1/knowledge/conversations/{cid}/ask", json={"question": "Summarise the purchase SOP"})).json()
    assert seen == ["QueryPlan", "DocDigest", "DocAnswer"]
    assert r["found_in_documents"] and r["citations"][0]["verified"] is True


async def test_multi_part_question_brings_a_passage_for_every_part(api, fake_llm):
    def h(call):
        if call.schema is QueryPlan:
            return json.dumps(dict(standalone_question="What notice must managers give and when does the fire certificate expire?",
                                   sub_questions=["What notice period must managers give?", "When does the fire certificate expire?"],
                                   search_queries=["manager notice period", "fire certificate valid until"], answerable_from_documents=True))
        if call.schema is DocAnswer:
            excerpts = call.prompt.split("=== EXCERPTS ===")[1]
            assert "60 days" in excerpts and "31 December 2026" in excerpts
            m = _marker_for(excerpts, "60 days")
            return json.dumps(dict(answer=f"Managers give 60 days notice [{m}]; the certificate is valid until 31 December 2026.", found_in_documents=True,
                                   citations=[{"quote": "Managers must give 60 days written notice before resigning", "excerpt": m}]))
        return handler(call)
    fake_llm(h)
    await _upload(api)
    await _upload(api, LICENCE, "fire.txt", category="Licences")
    cid = await _conv(api)
    r = (await api.post(f"/api/v1/knowledge/conversations/{cid}/ask", json={"question": "manager notice and fire certificate expiry?"})).json()
    assert r["found_in_documents"] is True and r["citations"][0]["verified"]


async def test_follow_up_history_names_the_document_that_answered(api, fake_llm):
    prompts = []

    def h(call):
        if call.schema is QueryPlan:
            prompts.append(call.prompt)
        return handler(call)
    fake_llm(h)
    await _upload(api)
    cid = await _conv(api)
    await api.post(f"/api/v1/knowledge/conversations/{cid}/ask", json={"question": "What notice period do managers have?"})
    r = (await api.post(f"/api/v1/knowledge/conversations/{cid}/ask", json={"question": "and for other staff?"})).json()
    assert "ASSISTANT [from: Employee Handbook]:" in prompts[-1] and "30 days" in r["content"]


# ------------------------------------------------------------------ robustness

async def test_vector_store_down_keeps_document_keyword_searchable_and_recovers(api, fake_llm, monkeypatch):
    state = fake_llm(handler)

    def qdrant_down(*a, **k):
        raise ConnectionError("qdrant unreachable")
    monkeypatch.setattr(retrieval, "index_vectors", qdrant_down)
    monkeypatch.setattr(retrieval, "vector_search", qdrant_down)
    did = await _upload(api)
    d = (await api.get(f"/api/v1/knowledge/documents/{did}")).json()
    assert d["status"] == "ready" and d["review_state"] == "done"
    assert (await _doc_row(did)).embed_model == service.PENDING_VECTORS
    hits = (await api.get("/api/v1/knowledge/search", params={"q": "dyeing formulas"})).json()
    assert hits and "vector" not in hits[0]["via"]

    monkeypatch.undo()                                                       # Qdrant is back
    monkeypatch.setattr(service, "today_ist", lambda: date(2026, 10, 27))
    calls = len(state.calls)
    assert await service.recover_at_startup() >= 1
    assert (await _doc_row(did)).status == "ready"                           # never flipped back to processing
    await asyncio.gather(*list(service._background))
    row = await _doc_row(did)
    assert row.embed_model == service.INDEX_VERSION and row.review_state == "done" and row.stage == "done"
    assert len(state.calls) == calls                                         # vectors written, review not repeated


async def test_ingest_is_idempotent_and_reuses_stored_chunks(api, fake_llm, monkeypatch):
    state = fake_llm(handler)
    did = await _upload(api)
    pk = uuid.UUID(did)
    async with async_session_maker() as s:
        ids_before = set((await s.execute(select(DocChunk.id).where(DocChunk.doc_id == pk))).scalars())
    await service._set(pk, review_state="pending")
    parses = []
    real = service.load_document
    monkeypatch.setattr(service, "load_document", lambda *a: parses.append(1) or real(*a))
    state.calls.clear()
    await asyncio.gather(service.run_ingest(pk), service.run_ingest(pk))    # the duplicate run is ignored
    assert [c.schema for c in state.calls] == [DocumentReview] and parses == []
    async with async_session_maker() as s:
        ids_after = set((await s.execute(select(DocChunk.id).where(DocChunk.doc_id == pk))).scalars())
    assert ids_after == ids_before


async def test_documents_chunked_by_an_older_chunker_are_rechunked(api, fake_llm):
    fake_llm(handler)
    did = await _upload(api)
    pk = uuid.UUID(did)
    await service._set(pk, embed_model="sentence-transformers/old-model")
    await service.run_ingest(pk)
    row = await _doc_row(did)
    assert row.embed_model == service.INDEX_VERSION and row.status == "ready" and row.chunk_count >= 2


async def test_retry_of_a_ready_document_keeps_it_searchable(api, fake_llm):
    def down(call):
        from app.core.llm.errors import LLMUnavailable
        raise LLMUnavailable("503")
    fake_llm(down)
    did = await _upload(api)
    assert (await api.get(f"/api/v1/knowledge/documents/{did}")).json()["review_state"] == "failed"
    fake_llm(handler)
    r = await api.post(f"/api/v1/knowledge/documents/{did}/retry")
    assert r.status_code == 202 and r.json()["status"] == "ready"
    d = (await api.get(f"/api/v1/knowledge/documents/{did}")).json()
    assert d["review_state"] == "done" and d["doc_type"] == "HR policy"
