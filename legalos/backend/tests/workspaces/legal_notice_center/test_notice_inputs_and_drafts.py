"""Hindi quote verification, messy inputs (chat pastes, page photos) and the reply-letter / action-plan switch (fake LLM)."""
import json
from datetime import date

import pytest

from app.shared.exceptions import BadRequestException
from app.workspaces.legal_notice_center.engine import brief, pipeline, prompts, textprep
from app.workspaces.legal_notice_center.engine.schemas import NoticeFacts, NoticeOcr, NoticeReplyDraft
from tests.workspaces.legal_notice_center.sample_notices import CHEQUE_BOUNCE_NOTICE, CIVIL_SUMMONS, HINDI_CHEQUE_NOTICE, WHATSAPP_PASTE

RECEIVED = TODAY = date(2026, 10, 22)
HINDI_DEADLINE = "अतः आपको इस नोटिस की प्राप्ति के १५ दिनों के भीतर रु. 2,40,000/- का भुगतान करने हेतु कहा जाता है"


def _facts(**kw) -> str:
    base = dict(notice_type="cheque_bounce", title="Cheque bounce notice", summary_points=["x"])
    base.update(kw)
    return json.dumps(base, ensure_ascii=False)


def _handler(facts_json: str, reply_text: str = "Sir, [CONFIRM: were goods received?]"):
    calls = []

    def h(call):
        calls.append(call)
        if call.schema is NoticeFacts:
            return facts_json
        if call.schema is NoticeReplyDraft:
            return json.dumps(dict(reply_text=reply_text, points_to_confirm=[], documents_to_gather=["Invoices"]))
        raise AssertionError(call.schema)
    return h, calls


# ------------------------------------------------------------------ Hindi / regional

def test_hindi_quotes_verify_despite_invisible_encoding_differences():
    segs = textprep.notice_segments(HINDI_CHEQUE_NOTICE)
    assert textprep.verify_quote(HINDI_DEADLINE, segs)
    # the model's copy: ASCII digits, a decomposed nukta and a stray zero-width joiner
    variant = HINDI_DEADLINE.replace("१५", "15").replace("प्राप्ति", "प्रा‍प्ति")
    assert textprep.verify_quote(variant, segs)
    assert textprep.verify_quote("सभी दस्तावेज़ हमारे पास सुरक्षित हैं", segs)
    # a plausible but invented Hindi sentence must fail
    assert not textprep.verify_quote("अतः आपको इस नोटिस की प्राप्ति के 7 दिनों के भीतर रु. 5,00,000/- का भुगतान करना होगा", segs)


def test_hindi_notice_end_to_end_english_summary_and_corrected_deadline(fake_llm):
    h, calls = _handler(_facts(
        language="hi", notice_date="2026-10-12", summary_points=["Patel Yarn Traders says your cheque for Rs 2,40,000 bounced."],
        summary_local=["पटेल यार्न ट्रेडर्स का कहना है कि आपका चेक बाउंस हुआ।"], response_days=30,      # the model misread 15 as 30
        deadline_quote=HINDI_DEADLINE, amount_claimed=240000))
    fake_llm(h)
    a = pipeline.analyze_text(HINDI_CHEQUE_NOTICE, RECEIVED, "Kulkarni Textiles Pvt Ltd", TODAY)
    assert a.quotes_verified == {"deadline": True}
    assert a.facts.response_days == 15 and a.facts.response_days_from == "receipt" and a.corrections
    assert a.deadline.due == date(2026, 11, 6) and a.deadline_verified and a.notice_date_verified
    assert a.facts.summary_points[0].startswith("Patel") and a.facts.summary_local
    assert "Hindi" in prompts.FACTS_SYSTEM and len(calls) == 2


# ------------------------------------------------------------------ messy inputs

def test_whatsapp_paste_is_cleaned_and_quotes_verify_against_the_clean_text(fake_llm):
    clean, chat = textprep.clean_notice_text(WHATSAPP_PASTE)
    assert chat and "Ramesh Kulkarni:" not in clean and "Media omitted" not in clean and "*" not in clean
    assert clean.startswith("LEGAL NOTICE")
    h, _ = _handler(_facts(response_days=15, deadline_quote="within 15 days from the receipt of this notice"))
    fake_llm(h)
    a = pipeline.analyze_text(WHATSAPP_PASTE, RECEIVED, "Co", TODAY)
    assert a.input_cleaned and a.text == clean and a.deadline_verified


def test_ordinary_notice_text_is_not_mangled_by_the_chat_cleaner():
    clean, chat = textprep.clean_notice_text(CHEQUE_BOUNCE_NOTICE)
    assert not chat and "Ref: MA/2026/118" in clean and "Date: 12 October 2026" in clean


def test_page_photos_are_read_in_one_ocr_call_in_page_order(fake_llm):
    seen = []

    def h(call):
        seen.append(call)
        assert call.schema is NoticeOcr and len(call.files) == 3 and call.files[0][1] == "image/jpeg"
        return json.dumps({"pages": [{"number": 2, "text": "page two"}, {"number": 1, "text": "page one"}, {"number": 3, "text": "page three"}]})
    fake_llm(h)
    text, ocr = pipeline.read_notice_files([(b"\xff\xd8\xff1", "p1.jpg"), (b"\xff\xd8\xff2", "p2.jpg"), (b"\x89PNG3", "p3.png")])
    assert ocr and text == "page one\n\npage two\n\npage three" and len(seen) == 1


def test_several_files_must_all_be_photos():
    with pytest.raises(BadRequestException):
        pipeline.read_notice_files([(b"%PDF", "a.pdf"), (b"\xff\xd8\xff", "b.jpg")])


# ------------------------------------------------------------------ reply letter vs action plan

def test_a_court_summons_gets_an_action_plan_not_a_letter(fake_llm):
    h, calls = _handler(_facts(notice_type="court_summons", hearing_date="2027-01-15",
                               hearing_quote="you are hereby summoned to appear in this Court in person or by a pleader duly instructed on 15.01.2027 at 11:00 AM to answer the claim"),
                        reply_text="WHAT THIS NOTICE REQUIRES\nAppear on 15 Jan 2027.\nSTEPS\n1. Engage an advocate.")
    fake_llm(h)
    a = pipeline.analyze_text(CIVIL_SUMMONS, RECEIVED, {"legal_name": "Kulkarni Textiles Pvt Ltd", "gstin": "24ABCDE1234F1Z5"}, TODAY)
    assert a.draft_kind == "action_plan" and a.reply.reply_text.startswith("ACTION PLAN - not a reply letter")
    draft_call = calls[-1]
    assert draft_call.system == prompts.PLAN_SYSTEM and "Write an ACTION PLAN" in draft_call.prompt
    assert "GSTIN: 24ABCDE1234F1Z5" in draft_call.prompt
    # written statement (30 days from service) comes before the far hearing
    assert a.deadline.due == date(2026, 11, 21) and a.urgency == "critical"
    assert [c.basis for c in a.deadline.candidates] == ["hearing", "statutory"]


@pytest.mark.parametrize("notice_type, wp", [("cheque_bounce", True), ("gst_show_cause_drc01", False)])
def test_letters_follow_the_per_type_structure(fake_llm, notice_type, wp):
    h, calls = _handler(_facts(notice_type=notice_type, reference_number="MA/2026/118", notice_date="2026-10-12",
                               allegations=["Cheque no. 004512 was dishonoured", "Rs 2,40,000 is due"]))
    fake_llm(h)
    a = pipeline.analyze_text(CHEQUE_BOUNCE_NOTICE, RECEIVED, "Kulkarni Textiles Pvt Ltd", TODAY)
    p = calls[-1].prompt
    assert a.draft_kind == "letter" and calls[-1].system == prompts.REPLY_SYSTEM
    assert "1. Cheque no. 004512 was dishonoured\n  2. Rs 2,40,000 is due" in p and "Ref. MA/2026/118 dated 12 Oct 2026" in p
    assert ("Include 'WITHOUT PREJUDICE'" in p) is wp and ("Do NOT mark it without prejudice" in p) is (not wp)


def test_figures_not_in_the_notice_are_flagged_for_checking(fake_llm):
    h, _ = _handler(_facts(), reply_text="Sir, our client paid Rs. 1,75,000 against invoice 004512. [CONFIRM: Rs 9,99,999 paid?]")
    fake_llm(h)
    a = pipeline.analyze_text(CHEQUE_BOUNCE_NOTICE, RECEIVED, "Co", TODAY)
    flagged = [p for p in a.reply.points_to_confirm if p.startswith("Check this figure")]
    assert flagged == ["Check this figure: the draft mentions 175000, which is not in the notice."]


# ------------------------------------------------------------------ lawyer brief (deterministic)

def test_lawyer_brief_is_built_from_stored_fields_only():
    d = {
        "title": "Cheque bounce notice", "type_label": "Cheque bounce notice", "issuer_name": "Mehta & Associates",
        "reference_number": "MA/2026/118", "notice_date": date(2026, 10, 12), "received_date": date(2026, 10, 22),
        "received_confirmed": False, "amount_claimed": 240000.0, "statutes": ["Section 138 NI Act"],
        "response_deadline": date(2026, 11, 6), "deadline_verified": True, "deadline_note": "The notice gives 15 days.",
        "deadline_basis": [{"due": "2026-11-06", "explanation": "15 days from receipt", "verified": True}],
        "allegations": ["Cheque dishonoured"], "demands": ["Pay Rs 2,40,000"],
        "key_quotes": [{"kind": "amount", "text": "Rs. 2,40,000", "verified": False}],
        "type_info": {"ref": "NI Act s.138", "if_ignored": "Criminal complaint", "channel": "Reply through a lawyer", "verified": True, "documents": ["Bank memo"]},
        "draft_kind": "letter", "review_status": "ready_for_lawyer", "needs_received_date": True,
        "drafts": [{"version": 2, "author": "user", "placeholders": ["[CONFIRM: goods received?]"], "points_to_confirm": ["Goods received?"],
                    "documents_to_gather": ["Invoices"]}],
    }
    text = brief.build_lawyer_brief(d)
    for part in ("Rs 2,40,000", "22 Oct 2026 (assumed - client to confirm)", "6 Nov 2026 (verified against the notice)",
                 "[amount, UNVERIFIED]", "Reply letter, version 2 (edited by the client); review status: ready for lawyer",
                 "- Date the notice was actually received", "- [CONFIRM: goods received?]", "- Bank memo"):
        assert part in text, part
    assert brief.build_lawyer_brief(d) == text
