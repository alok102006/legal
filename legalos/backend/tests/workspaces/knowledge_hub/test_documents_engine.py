import uuid

from app.core.rag.parsing import Page, ParsedDocument
from app.workspaces.contract_intelligence.engine import verify
from app.workspaces.knowledge_hub.engine import ai, chunking, retrieval


def _doc(pages, has_pages=True):
    return ParsedDocument(pages=[Page(i + 1, t) for i, t in enumerate(pages)], kind="pdf" if has_pages else "text", has_pages=has_pages)


HANDBOOK = """EMPLOYEE HANDBOOK

1. Working hours
The standard working week is 48 hours across six days. Overtime is paid at twice the normal rate.

2. Notice period
Managers must give 60 days written notice before resigning. All other staff must give 30 days notice.

3. Leave
Employees are entitled to 24 days of paid leave per calendar year. Unused leave up to 12 days may be carried forward.

Grade | Basic | HRA
A | 50000 | 20000
B | 40000 | 16000
C | 30000 | 12000
"""


def test_sections_are_detected_and_attached_to_chunks():
    chunks = chunking.chunk_document(_doc([HANDBOOK]))
    by_text = {c.text[:20]: c for c in chunks}
    leave = next(c for c in chunks if "carried forward" in c.text)
    assert leave.section and leave.section.startswith("3. Leave")
    assert leave.embed_text.startswith("3. Leave")              # section prepended for embedding only
    assert "3. Leave" not in leave.text                         # stored text stays verbatim
    notice = next(c for c in chunks if "60 days" in c.text)
    assert notice.section.startswith("2. Notice")


def test_tables_are_kept_as_rows_with_header():
    chunks = chunking.chunk_document(_doc([HANDBOOK]))
    table = [c for c in chunks if c.kind == "table"]
    assert table and table[0].text.startswith("Grade | Basic | HRA") and "C | 30000" in table[0].text


def test_chunks_never_cross_pages():
    p1 = "\n\n".join(f"Paragraph {i}. " + "word " * 60 for i in range(6))
    chunks = chunking.chunk_document(_doc([p1, "Page two says the probation period is six months."]))
    assert all(c.page in (1, 2) for c in chunks) and chunks[-1].page == 2 and len(chunks) >= 3


def test_hindi_text_is_chunked_and_verifiable():
    hindi = "नोटिस अवधि\n\nप्रबंधकों को त्यागपत्र देने से पहले 60 दिनों का लिखित नोटिस देना होगा। अन्य कर्मचारियों को 30 दिनों का नोटिस देना होगा।"
    chunks = chunking.chunk_document(_doc([hindi], has_pages=False))
    assert chunks
    segs = ai.chunk_segments(chunks)
    m = verify.find_quote("प्रबंधकों को त्यागपत्र देने से पहले 60 दिनों का लिखित नोटिस देना होगा", segs)
    assert m.verified and m.exact


def test_short_quotes_must_match_exactly_and_trivial_ones_fail():
    segs = ai.chunk_segments(chunking.chunk_document(_doc([HANDBOOK])))
    assert not verify.find_quote("the supplier", segs).verified                        # too short to mean anything
    assert verify.find_quote("Managers must give 60 days written notice before resigning", segs).verified
    near = verify.find_quote("Managers must give sixty days notice before", segs)
    assert not near.verified                                                           # < 60 chars: exact only
    long_noisy = verify.find_quote("Employees are entitled to 24 days of paid leave per calendar year. Unused leave up to 12 days may be carried  forwards", segs)
    assert long_noisy.verified and not long_noisy.exact                               # long: fuzzy allowed


def test_rrf_rewards_agreement_between_retrievers():
    a, b, c, d = (uuid.uuid4() for _ in range(4))
    hits = retrieval.rrf({"keyword0": [a, b, c], "vector0": [b, d, a]})
    ranked = [h.chunk_id for h in hits]
    assert ranked[0] in (a, b) and ranked.index(d) > ranked.index(b)


def test_render_excerpts_includes_section_and_neighbours():
    e = ai.Excerpt(marker="C1", doc_id="x", doc_title="Handbook", page=3, text="Body", via=["keyword"], section="Leave", before="prev text", after="next text")
    out = ai.render_excerpts([e])
    assert "[[C1 | Handbook | Leave | p.3]]" in out and "prev text" in out and "next text" in out
