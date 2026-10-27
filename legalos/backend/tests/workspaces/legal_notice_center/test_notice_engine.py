import json
from datetime import date

import pytest

from app.core.llm.errors import LLMUnavailable
from app.shared.exceptions import BadRequestException
from app.workspaces.legal_notice_center.engine import pipeline, rules
from app.workspaces.legal_notice_center.engine.schemas import NoticeFacts, NoticeReplyDraft, NoticeType
from tests.workspaces.legal_notice_center.sample_notices import CHEQUE_BOUNCE_NOTICE, GST_NOTICE_NO_DEADLINE

RECEIVED = date(2026, 10, 22)
TODAY = date(2026, 10, 22)


def facts(**kw):
    base = dict(notice_type=NoticeType.legal_demand, title="T", summary_points=["x"])
    base.update(kw)
    return NoticeFacts(**base)


# ------------------------------------------------------------------ deadline rules

def test_stated_days_count_from_receipt():
    d = rules.compute_deadline(facts(response_days=30), RECEIVED)
    assert d.due == date(2026, 11, 21) and d.source == "stated" and d.days == 30


def test_explicit_date_wins_over_days():
    d = rules.compute_deadline(facts(response_days=30, response_deadline_date="2026-11-05"), RECEIVED)
    assert d.due == date(2026, 11, 5) and d.source == "stated"


def test_cheque_bounce_falls_back_to_the_statutory_15_days():
    d = rules.compute_deadline(facts(notice_type=NoticeType.cheque_bounce), RECEIVED)
    assert d.due == date(2026, 11, 6) and d.source == "statutory_default" and "Confirm with a lawyer" in d.note


def test_days_can_count_from_the_notice_date_instead_of_receipt():
    d = rules.compute_deadline(facts(response_days=15, response_days_from="notice_date", notice_date="2026-10-12"), RECEIVED)
    assert d.due == date(2026, 10, 27) and d.source == "stated" and d.anchor == "notice_date"


def test_statutory_windows_carry_their_source():
    d = rules.compute_deadline(facts(notice_type=NoticeType.consumer_complaint), RECEIVED)
    assert d.due == date(2026, 11, 21) and d.source == "statutory_default" and "s.38(2)(a)" in d.note
    assert rules.deadline_rule("consumer_complaint", "statutory_default").startswith("Consumer Protection Act")
    assert rules.deadline_rule("cheque_bounce", "stated") is None


def test_unknown_deadline_is_not_invented():
    d = rules.compute_deadline(facts(notice_type=NoticeType.gst_notice), RECEIVED)
    assert d.due is None and d.source == "unknown"


def test_bad_dates_are_ignored_not_crashed_on():
    assert rules.parse_iso("not a date") is None and rules.parse_iso(None) is None
    assert rules.compute_deadline(facts(response_deadline_date="31/31/2026"), RECEIVED).due is None


# ------------------------------------------------------------------ urgency

@pytest.mark.parametrize("type_, days, amount, expected", [
    (NoticeType.cheque_bounce, 15, 240000, "critical"),          # criminal exposure, whatever the date
    (NoticeType.court_summons, 40, None, "critical"),
    (NoticeType.gst_notice, 30, None, "low"),
    (NoticeType.gst_notice, 14, None, "medium"),
    (NoticeType.gst_notice, 5, None, "high"),
    (NoticeType.gst_notice, 2, None, "critical"),
    (NoticeType.legal_demand, 30, 800000, "high"),               # large sum
    (NoticeType.legal_demand, None, None, "medium"),             # unknown deadline needs attention
])
def test_urgency(type_, days, amount, expected):
    f = facts(notice_type=type_, response_days=days, amount_claimed=amount)
    dl = rules.compute_deadline(f, RECEIVED)
    assert rules.urgency_for(f, dl, TODAY) == expected


def test_overdue_is_critical():
    f = facts(response_days=10)
    dl = rules.compute_deadline(f, date(2026, 10, 1))             # due 11 Oct, today 22 Oct
    assert rules.urgency_for(f, dl, TODAY) == "critical"


def test_every_main_type_has_a_label_and_most_have_notes():
    assert all(t in rules.TYPE_LABELS for t in NoticeType)
    assert rules.legal_note(NoticeType.cheque_bounce)[1].startswith("Negotiable Instruments Act")
    # every type with a note says what happens if ignored; every type the brief names is covered
    assert all(n.if_ignored and n.ref for n in rules.LEGAL_NOTES.values())
    assert {"gst_notice", "income_tax_notice", "msme_delayed_payment", "tenancy_notice", "defamation", "contract_breach", "ip_notice"} <= {t.value for t in NoticeType}


# ------------------------------------------------------------------ pipeline (fake LLM)

def _handler(quote_override=None):
    def h(call):
        if call.schema is NoticeFacts:
            return json.dumps(dict(
                notice_type="cheque_bounce", title="Cheque bounce notice from Mehta & Associates", issuer_name="Mehta & Associates",
                issuer_role="Advocate for M/s Patel Yarn Traders", reference_number="MA/2026/118", notice_date="2026-10-12",
                summary_points=["Patel Yarn Traders says your cheque for Rs 2,40,000 bounced and wants payment in 15 days."],
                demands=["Pay Rs 2,40,000 within 15 days of receipt"], amount_claimed=240000, response_days=15,
                deadline_quote=quote_override or "within 15 days from the receipt of this notice",
                statutes_cited=["Section 138 Negotiable Instruments Act 1881"], consequences_stated="Criminal proceedings under Section 138"))
        if call.schema is NoticeReplyDraft:
            return json.dumps(dict(
                reply_text="Ref: MA/2026/118\n\nSir,\nWe acknowledge your notice dated 12 October 2026. Cheque no. 004512 was issued against "
                           "[CONFIRM: were the goods received in full and on time?]. Our records show [CONFIRM: payments made so far].\n\nYours faithfully",
                points_to_confirm=["Were the goods received in full?"], documents_to_gather=["Invoices", "Bank statement"]))
        raise AssertionError(call.schema)
    return h


def test_pipeline_extracts_verifies_and_drafts_with_placeholders(fake_llm):
    fake_llm(_handler())
    a = pipeline.analyze_text(CHEQUE_BOUNCE_NOTICE, RECEIVED, "Kulkarni Textiles Pvt Ltd", TODAY)
    assert a.facts.notice_type == NoticeType.cheque_bounce
    assert a.deadline.due == date(2026, 11, 6) and a.deadline_verified is True
    assert a.urgency == "critical"
    assert len(a.placeholders) == 2 and all(p.startswith("[CONFIRM") for p in a.placeholders)
    assert a.reply.documents_to_gather == ["Invoices", "Bank statement"]


def test_a_deadline_quote_that_is_not_in_the_notice_is_flagged(fake_llm):
    fake_llm(_handler(quote_override="within 7 working days from the date of this notice"))
    a = pipeline.analyze_text(CHEQUE_BOUNCE_NOTICE, RECEIVED, "Kulkarni Textiles Pvt Ltd", TODAY)
    assert a.deadline_verified is False
    assert "could not match" in a.deadline.note


def test_llm_failure_is_not_turned_into_a_canned_result(fake_llm):
    def down(call):
        raise LLMUnavailable("503")
    fake_llm(down)
    with pytest.raises(LLMUnavailable):
        pipeline.analyze_text(CHEQUE_BOUNCE_NOTICE, RECEIVED, "Co", TODAY)


def test_tiny_notice_is_rejected():
    with pytest.raises(BadRequestException):
        pipeline.analyze_text("hello", RECEIVED, "Co", TODAY)


def test_placeholder_extraction_dedupes():
    t = "A [CONFIRM: x] and again [CONFIRM: x] and [FILL: y] but not [other]"
    assert pipeline.placeholders_in(t) == ["[CONFIRM: x]", "[FILL: y]"]
