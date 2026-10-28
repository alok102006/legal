import json
import re
import uuid

import pytest

from app.core.llm.errors import LLMUnavailable
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


def test_profile_note_is_shown_but_not_part_of_the_citable_text():
    e = ai.Excerpt(marker="C1", doc_id="x", doc_title="Manual", page=None, text="Verbatim body text.", via=["overview"], note="AI summary")
    assert "Document profile (not quotable): AI summary" in ai.render_excerpts([e]) and e.text == "Verbatim body text."


# ------------------------------------------------------------------ chunking: structure

INSURANCE = """POLICY SCHEDULE
Policy Number: 2026/FSP/VAD/0045871

4. SUM INSURED

Section I - Fire
2.1 Building: Rs 3,50,00,000
Total under Section I: Rs 7,50,00,000.

Section II - Burglary
Stock in warehouse: Rs 60,00,000.

5. CLAIMS

5.1 In the event of any loss, the Insured shall give written notice within forty-eight (48) hours of the occurrence.
5.2 In case of burglary, the police must be informed and a copy of the FIR sent to the Insurer.
"""


def test_section_path_follows_the_heading_hierarchy_and_clause_numbers():
    chunks = chunking.chunk_document(_doc([INSURANCE], has_pages=False))
    fire = next(c for c in chunks if "3,50,00,000" in c.text)
    assert fire.section == "4. SUM INSURED > Section I - Fire > 2.1"
    assert "2.1 Building: Rs 3,50,00,000" in fire.text                         # a "number: amount" line is a fact, not a heading
    burglary = next(c for c in chunks if "60,00,000" in c.text)
    assert burglary.section == "4. SUM INSURED > Section II - Burglary"
    claims = next(c for c in chunks if "forty-eight" in c.text)
    assert claims.section == "5. CLAIMS > 5.1–5.2"
    assert "Policy Number: 2026/FSP/VAD/0045871" in chunks[0].text and chunks[0].section == "POLICY SCHEDULE"


def test_hindi_numbered_headings_and_isolated_titles():
    text = "फैक्टरी सुरक्षा नियमावली\n\n3. दुर्घटना की सूचना\n\n3.1 पर्यवेक्षक दुर्घटना रिपोर्ट फॉर्म 24 घंटे के भीतर जमा करेगा।\n3.2 गंभीर दुर्घटना की सूचना 12 घंटे के भीतर दी जाएगी।\n"
    chunks = chunking.chunk_document(_doc([text], has_pages=False))
    c = next(c for c in chunks if "24 घंटे" in c.text)
    assert c.section == "3. दुर्घटना की सूचना > 3.1–3.2" and "12 घंटे" in c.text


def test_a_run_of_short_numbered_lines_is_a_list_not_headings():
    text = "Present:\n1. Mr. N. Patel, Managing Director\n2. Ms. K. Shah, Director\n3. Mr. Y. Desai, Director\n\nThe quorum being present, the meeting began at 11 am."
    chunks = chunking.chunk_document(_doc([text], has_pages=False))
    assert len(chunks) == 1 and chunks[0].section is None and "2. Ms. K. Shah" in chunks[0].text


def test_dates_and_amount_lines_are_not_headings():
    for line in ["12 August 2026", "GSTIN: 24ABCDE1234F1Z5", "2.1 Building: Rs 3,50,00,000", "Rs 5,64,750 paid by NEFT."]:
        assert chunking.heading_of(line) is None, line
    for line in ["1. Working hours", "4.2 Burglary claims", "SECTION-WISE SUM INSURED", "# Leave", "Chapter 3 Leave", "अध्याय 2 छुट्टी"]:
        assert chunking.heading_of(line), line


def test_lists_stay_with_their_lead_in():
    text = "8. EXCLUSIONS\nThe following are excluded from cover:\n(a) war and invasion;\n(b) wear and tear;\n(c) theft without forcible entry.\n"
    chunks = chunking.chunk_document(_doc([text], has_pages=False))
    c = next(c for c in chunks if "(b) wear and tear" in c.text)
    assert c.text.startswith("The following are excluded from cover:") and "(c) theft" in c.text and c.section == "8. EXCLUSIONS"


def test_table_pieces_repeat_the_header_and_embed_header_value_readings():
    rows = ["SKU | Description | Price (Rs)"] + [f"SIP-FAS-{i:03d} | Item {i} | {100 + i}" for i in range(1, 15)]
    chunks = chunking.chunk_document(_doc(["PRICE TABLE\n\n" + "\n".join(rows)], has_pages=False))
    tables = [c for c in chunks if c.kind == "table"]
    assert len(tables) >= 3 and all(c.text.startswith("SKU | Description | Price (Rs)") for c in tables)
    t = next(c for c in tables if "SIP-FAS-007" in c.text)
    assert "SKU: SIP-FAS-007; Description: Item 7; Price (Rs): 107" in t.embed_text and t.section == "PRICE TABLE"
    assert "SKU: SIP-FAS-007" not in t.text                                     # stored text stays verbatim


def test_table_reading_of_a_stored_chunk_matches_the_fresh_one():
    text = "Rates for FY 2026-27:\nSKU | Price\nA-1 | 10\nA-2 | 20"
    fresh = [c for c in chunking.chunk_document(_doc([text], has_pages=False)) if c.kind == "table"][0]
    assert chunking.table_reading(fresh.text) == fresh.embed == "Rates for FY 2026-27:\nSKU: A-1; Price: 10\nSKU: A-2; Price: 20"


def test_spreadsheet_rows_are_not_given_a_fake_header():
    rows = ["SKU: A-1 | Price: 10", "SKU: A-2 | Price: 20", "SKU: A-3 | Price: 30"]
    pieces = chunking.table_pieces(rows)
    assert pieces == [("\n".join(rows), None)]


def test_long_paragraphs_are_cut_at_sentence_ends_never_inside_amounts():
    sentence = "The premium of Rs. 5,64,750 is payable by No. 3 cheque within 15 days of the invoice dated 1.4.2026 at the head office. "
    text = sentence * 30
    pieces = chunking.split_text(text.strip())
    assert len(pieces) > 1 and all(p.endswith("head office.") for p in pieces[:-1])
    assert all(p.startswith("The premium of Rs. 5,64,750") for p in pieces)


def test_unbreakable_text_is_cut_between_words_not_inside_numbers():
    text = " ".join(f"amount Rs 1,{i:02d},000" for i in range(400))
    for p in chunking.split_text(text):
        assert re.fullmatch(r"(amount Rs 1,\d{2,3},000 ?)+", p), p[:80]


def test_repeated_page_headers_and_footers_are_removed_and_duplicates_dropped():
    topics = ["leave", "salary", "overtime", "grievances"]
    pages = [f"ACME TEXTILES PVT LTD - CONFIDENTIAL\nThis page explains the rules on {t} for all staff.\nPage {i} of 4" for i, t in enumerate(topics, 1)]
    pages.append(pages[0].replace("Page 1", "Page 5"))                          # a duplicated page
    chunks = chunking.chunk_document(_doc(pages))
    assert not any("CONFIDENTIAL" in c.text or re.search(r"Page \d of 4", c.text) for c in chunks)
    assert len([c for c in chunks if "rules on leave" in c.text]) == 1 and len(chunks) == 4


def test_overlap_carries_the_last_sentence_into_the_next_chunk():
    paras = [f"Rule {i}. Staff in grade {i} get {i} extra days of leave every year. This applies from April." for i in range(1, 30)]
    chunks = chunking.chunk_document(_doc(["\n".join(paras)], has_pages=False))
    assert len(chunks) >= 2 and chunks[1].text.startswith("This applies from April.")


# ------------------------------------------------------------------ retrieval: query analysis

def test_exact_tokens_find_codes_amounts_dates_and_clause_numbers():
    toks = {t.label: t for t in retrieval.exact_tokens("rate of SIP-FAS-003 and GSTR-3B, who signs above ₹2,40,000 on 12/08/2026 per clause 4.2 for a/c 50200012345678?")}
    assert {"SIP-FAS-003", "GSTR-3B", "2,40,000", "12/08/2026", "4.2", "50200012345678"} <= set(toks)
    assert "240,000" in toks["2,40,000"].variants and "240000" in toks["2,40,000"].variants
    assert "12 August 2026" in toks["12/08/2026"].variants and "2026-08-12" in toks["12/08/2026"].variants
    assert toks["4.2"].clause == "4.2"
    assert retrieval.exact_tokens("how many days of leave do managers get?") == []


def test_amount_variants_cover_indian_and_international_grouping():
    assert set(retrieval._amount_variants("240000")) >= {"2,40,000", "240,000"}
    assert "3,50,00,000" in retrieval._amount_variants("35000000")


def test_query_words_drop_stop_words_in_every_script():
    assert retrieval.query_words("कितने दिन का बीमारी अवकाश मिलता है?") == ["दिन", "बीमारी", "अवकाश", "मिलता"]
    assert retrieval.query_words("What is the -rate for yarn?") == ["rate", "yarn"]


def test_glossary_adds_hindi_words_only_for_latin_questions():
    assert "सप्ताह" in retrieval.glossary_expansion("maternity leave kitne hafte ka hai")
    assert retrieval.glossary_expansion("मातृत्व अवकाश कितने सप्ताह") is None
    assert retrieval.glossary_expansion("SIP-FAS-003 price") is None


def test_route_weights_only_prefer_when_one_document_stands_out():
    a, b, c = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    assert retrieval.route_weights({a: 0.50, b: 0.52, c: 0.51}) == {a: 0.0, b: 0.0, c: 0.0}
    w = retrieval.route_weights({a: 0.70, b: 0.40, c: 0.30})
    assert w[a] == 1.0 and w[c] == 0.0 and 0 < w[b] < 1


def test_diversify_caps_per_document_but_not_when_one_document_has_everything():
    d1, d2 = uuid.uuid4(), uuid.uuid4()
    hits = [retrieval.Hit(uuid.uuid4(), 10 - i) for i in range(6)]
    one_doc = {h.chunk_id: d1 for h in hits}
    assert len(retrieval.diversify(hits, one_doc, top_k=5)) == 5
    mixed = {h.chunk_id: (d1 if i < 5 else d2) for i, h in enumerate(hits)}
    picked = retrieval.diversify(hits, mixed, top_k=4)
    assert hits[5] in picked and sum(1 for h in picked if mixed[h.chunk_id] == d1) == retrieval.PER_DOC


def test_diversify_keeps_the_best_passage_of_every_sub_question():
    hits = [retrieval.Hit(uuid.uuid4(), 10 - i) for i in range(10)]
    doc = {h.chunk_id: uuid.uuid4() for h in hits}
    picked = retrieval.diversify(hits, doc, top_k=3, must=[hits[9].chunk_id])
    assert hits[9] in picked and len(picked) == 3


# ------------------------------------------------------------------ language, planning, digests

@pytest.mark.parametrize("text,guess,expected", [
    ("सभी कर्मचारियों को प्रति वर्ष 24 दिन का सवेतन अवकाश मिलेगा। बीमारी अवकाश 7 दिन का होगा।", "English", "Hindi"),
    ("सर्व कर्मचाऱ्यांना दरवर्षी 24 दिवसांची पगारी रजा मिळेल. आजारी रजा 7 दिवसांची असेल.", "Marathi", "Marathi"),
    ("All employees get 24 days of paid leave every year and sick leave of seven days.", "Hindi", "English"),
    ("Sabhi employees ko saal mein 24 din ki chutti milegi aur sick leave 7 din ki hai, agar doctor ka certificate ho toh.", None, "Hinglish"),
    ("બધા કર્મચારીઓને દર વર્ષે 24 દિવસની પગારવાળી રજા મળશે.", None, "Gujarati"),
    ("Leave policy. All employees get 24 days of paid leave. सभी कर्मचारियों को प्रति वर्ष 24 दिन का सवेतन अवकाश मिलेगा।", None, "English and Hindi"),
])
def test_language_detection_is_script_based(text, guess, expected):
    assert ai.detect_language(text, guess) == expected


def test_digest_passages_reach_the_end_of_a_long_document():
    chunks = [(i, f"Section {i // 5}", "x" * 1000) for i in range(300)]
    picked = ai.digest_passages(chunks, budget=40_000)
    assert sum(len(t) for _, _, t in picked) <= 40_000
    assert picked[-1][0] >= 290 and len({s for _, s, _ in picked}) == 40            # every section is represented
    assert ai.digest_passages(chunks[:5], budget=40_000) == chunks[:5]


def test_plan_keeps_the_users_own_hindi_words_and_sub_questions(fake_llm):
    def handler(call):
        return json.dumps(dict(standalone_question="How many days of sick leave?", sub_questions=["How many days of sick leave?", "When is a doctor's certificate needed?"],
                               search_queries=["sick leave days"], answerable_from_documents=True))
    fake_llm(handler)
    plan = ai.plan_query("बीमारी अवकाश कितने दिन का है और डॉक्टर का प्रमाणपत्र कब चाहिए?", "")
    assert "बीमारी अवकाश कितने दिन का है और डॉक्टर का प्रमाणपत्र कब चाहिए?" in plan.search_queries
    assert "When is a doctor's certificate needed?" in plan.search_queries and len(plan.sub_questions) == 2


def test_planner_failure_falls_back_to_the_raw_question(fake_llm):
    def down(call):
        raise LLMUnavailable("503")
    fake_llm(down)
    plan = ai.plan_query("leave carried forward?", "")
    assert plan.search_queries == ["leave carried forward?"] and plan.intent == "lookup"


def test_long_documents_are_reviewed_by_section_notes_then_merged(fake_llm, monkeypatch):
    monkeypatch.setattr(ai, "MAX_REVIEW_CHARS", 2000)
    sections = [f"{i}. SECTION {i}\n{i}.1 " + f"Clause text for section {i} sets a limit of {i * 10} days for the request. " * 6 for i in range(1, 9)]
    sections.append("9. RENEWAL\n9.1 This licence is valid until 31 March 2027 and must be renewed before that date.")
    parsed = _doc(["\n\n".join(sections)], has_pages=False)
    chunks = chunking.chunk_document(parsed)
    seen = []

    def handler(call):
        seen.append(call.schema.__name__)
        if call.schema is ai.SectionNotes:
            return json.dumps({"sections": [
                {"section": "9. RENEWAL", "summary": "Renewal date.", "facts": [
                    {"fact": "Valid until 31 March 2027", "quote": "This licence is valid until 31 March 2027 and must be renewed before that date"},
                    {"fact": "Invented fact", "quote": "the licensee shall pay a penalty of Rs 9,99,999 every single day"}]}]})
        assert "Valid until 31 March 2027" in call.prompt and "Invented fact" not in call.prompt     # unverified notes never reach the review
        return json.dumps(dict(doc_type="Licence or certificate", title="Trade licence", language="English", summary_points=["A licence."],
                               expiry_date="2027-03-31", expiry_label="Licence valid until",
                               expiry_quote="This licence is valid until 31 March 2027 and must be renewed before that date"))
    fake_llm(handler)
    result = ai.review_document(parsed, chunks, "scan_001")
    assert seen == ["SectionNotes", "DocumentReview"] and result.sectioned and not result.truncated
    assert result.expiry_verified and str(result.expiry) == "2027-03-31" and result.language == "English"


def test_short_documents_are_reviewed_in_one_call(fake_llm):
    seen = []

    def handler(call):
        seen.append(call.schema.__name__)
        return json.dumps(dict(doc_type="HR policy", title="Handbook", language="Hindi", summary_points=["x"]))
    fake_llm(handler)
    result = ai.review_document(_doc([HANDBOOK]), chunking.chunk_document(_doc([HANDBOOK])), "handbook")
    assert seen == ["DocumentReview"] and not result.sectioned and result.language == "English"   # script wins over the guess
