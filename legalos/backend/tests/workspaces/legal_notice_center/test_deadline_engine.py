"""Table-driven tests for the deadline engine: Indian date formats, the earliest-of rule, missing and past dates."""
from datetime import date

import pytest

from app.workspaces.legal_notice_center.engine import dates, rules
from app.workspaces.legal_notice_center.engine.schemas import NoticeFacts, NoticeType

RECEIVED = date(2026, 10, 22)


def facts(**kw) -> NoticeFacts:
    base = dict(notice_type=NoticeType.legal_demand, title="T", summary_points=["x"])
    base.update(kw)
    return NoticeFacts(**base)


# ------------------------------------------------------------------ reading dates written the Indian way

@pytest.mark.parametrize("text, ref, expected", [
    ("pay on or before 12.10.2026", None, [date(2026, 10, 12)]),
    ("dated 12-10-26", None, [date(2026, 10, 12)]),
    ("dated 12/10/2026", None, [date(2026, 10, 12)]),                     # day first, never 10 December
    ("by the 12th October, 2026", None, [date(2026, 10, 12)]),
    ("by 12th day of October 2026", None, [date(2026, 10, 12)]),
    ("by October 5, 2026", None, [date(2026, 10, 5)]),
    ("by 30 October", date(2026, 10, 12), [date(2026, 10, 30)]),        # year from the notice date
    ("by 5 January", date(2026, 12, 20), [date(2027, 1, 5)]),           # ... rolling into next year
    ("by 30 October", None, []),                                        # no year and no reference: not guessed
    ("30 अक्टूबर 2026 तक भुगतान करें", None, [date(2026, 10, 30)]),
    ("दिनांक १२/१०/२०२६", None, [date(2026, 10, 12)]),                  # Devanagari digits
    ("15 फ़रवरी 2027", None, [date(2027, 2, 15)]),                       # nukta spelling
    ("૩૦ ઓક્ટોબર ૨૦૨૬ સુધી", None, [date(2026, 10, 30)]),                 # Gujarati
    ("३० ऑक्टोबर २०२६ पर्यंत", None, [date(2026, 10, 30)]),              # Marathi
    ("Rs. 2,40,000 under Section 16(2)(aa)", None, []),                 # amounts and sections are not dates
    ("31/31/2026", None, []),
])
def test_find_dates(text, ref, expected):
    assert dates.find_dates(text, ref) == expected


@pytest.mark.parametrize("text, period, anchor", [
    ("within 15 days from the receipt of this notice", (15, "days"), "receipt"),
    ("within fifteen (15) days of the date of this notice", (15, "days"), "notice_date"),
    ("within seven days", (7, "days"), None),
    ("within 7 working days from the date of service of this notice", (7, "working_days"), "receipt"),
    ("within 3 months from the date of communication", (3, "months"), None),
    ("pay Rs. 2,40,000 within 15 days", (15, "days"), None),           # the amount is not the period
    ("इस नोटिस की प्राप्ति के 15 दिनों के भीतर", (15, "days"), "receipt"),
    ("सात दिन के अंदर जवाब दें", (7, "days"), None),
    ("નોટિસ મળ્યાના ૧૫ દિવસમાં", (15, "days"), "receipt"),
    ("नोटिस दिनांक 12.10.2026 को जारी", None, None),                    # "दिनांक" (date) is not "दिन" (day)
    ("vacate by 30 November 2026, being the expiry of fifteen days", (15, "days"), None),   # "2026" is not 202 days
    ("compensation under Section 25F within one month", (1, "months"), None),   # "25F" is a section, not 25 months
    ("within thirty (30) days of the issue of this notice", (30, "days"), "notice_date"),
])
def test_find_period_and_anchor(text, period, anchor):
    p = dates.find_period(text)
    assert ((p.count, p.unit) if p else None) == period
    assert dates.period_anchor(text) == anchor


# ------------------------------------------------------------------ the earliest-of rule

@pytest.mark.parametrize("case, kw, due, source, anchor", [
    ("stated period from receipt", dict(response_days=7, response_days_from="receipt"), date(2026, 10, 29), "stated", "receipt"),
    ("stated date", dict(response_deadline_date="2026-10-30"), date(2026, 10, 30), "stated", "explicit"),
    ("period from the notice date", dict(response_days=15, response_days_from="notice_date", notice_date="2026-10-12"),
     date(2026, 10, 27), "stated", "notice_date"),
    ("unclear anchor: the earlier notice date", dict(response_days=15, notice_date="2026-10-12"), date(2026, 10, 27), "stated", "notice_date"),
    ("cheque: notice allows 30 days, the statute 15",
     dict(notice_type=NoticeType.cheque_bounce, response_days=30, response_days_from="receipt"), date(2026, 11, 6), "statutory_default", "receipt"),
    ("consumer: hearing before the 30-day window",
     dict(notice_type=NoticeType.consumer_complaint, hearing_date="2026-11-02"), date(2026, 11, 2), "stated", "hearing"),
    ("civil summons: written statement before a far hearing",
     dict(notice_type=NoticeType.court_summons, hearing_date="2027-01-15"), date(2026, 11, 21), "statutory_default", "receipt"),
    ("SARFAESI: 60 days from the notice date",
     dict(notice_type=NoticeType.sarfaesi_13_2, notice_date="2026-10-01"), date(2026, 11, 30), "statutory_default", "notice_date"),
    ("REG-17: 7 working days, Sundays skipped",
     dict(notice_type=NoticeType.gst_registration_cancellation_reg17), date(2026, 10, 30), "statutory_default", "receipt"),
    ("DRC-07: appeal within 3 months", dict(notice_type=NoticeType.gst_demand_order_drc07), date(2027, 1, 22), "statutory_default", "receipt"),
    ("months stated by the notice", dict(response_days=2, response_period_unit="months", response_days_from="receipt"),
     date(2026, 12, 22), "stated", "receipt"),
])
def test_deadline_table(case, kw, due, source, anchor):
    d = rules.compute_deadline(facts(**kw), RECEIVED)
    assert (d.due, d.source, d.anchor) == (due, source, anchor), case
    assert d.note


def test_the_note_explains_the_choice_and_lists_the_other_dates():
    d = rules.compute_deadline(facts(notice_type=NoticeType.cheque_bounce, response_days=30, response_days_from="receipt"), RECEIVED)
    assert "Negotiable Instruments Act" in d.note and "also considered: 21 Nov 2026 (period in the notice)" in d.note
    assert [c.basis for c in d.candidates] == ["stated_period", "statutory"]


def test_a_period_from_an_unreadable_notice_date_asks_instead_of_guessing():
    d = rules.compute_deadline(facts(response_days=15, response_days_from="notice_date"), RECEIVED)
    assert d.due is None and d.source == "unknown" and d.needs == ["notice_date"] and "enter the notice date" in d.note
    d2 = rules.compute_deadline(facts(notice_type=NoticeType.sarfaesi_13_2), RECEIVED)
    assert d2.due is None and d2.needs == ["notice_date"]


def test_forthwith_is_not_turned_into_a_date_but_raises_urgency():
    f = facts(forthwith=True)
    d = rules.compute_deadline(f, RECEIVED)
    assert d.due is None and d.forthwith and "forthwith" in d.note
    assert rules.urgency_for(f, d, RECEIVED) == "high"


def test_a_notice_received_late_is_overdue_and_critical():
    f = facts(response_deadline_date="2026-09-30")
    d = rules.compute_deadline(f, date(2026, 10, 25))
    assert d.due == date(2026, 9, 30) and rules.urgency_for(f, d, date(2026, 10, 28)) == "critical"


def test_unverified_stated_dates_are_flagged_and_statutory_ones_are_not():
    d = rules.compute_deadline(facts(response_days=10, response_days_from="receipt"), RECEIVED, deadline_verified=False)
    assert d.verified is False and rules.UNVERIFIED_NOTE in d.note
    s = rules.compute_deadline(facts(notice_type=NoticeType.consumer_complaint), RECEIVED, deadline_verified=False)
    assert s.verified is True and rules.UNVERIFIED_NOTE not in s.note


# ------------------------------------------------------------------ the notice's words override the AI's dates

NOTICE = "LEGAL NOTICE dated 12.10.2026. You are called upon to pay within 7 days from the receipt of this notice."


@pytest.mark.parametrize("kw, quote_ok, expect", [
    # model said 15 days; the verified quote says 7 days from receipt
    (dict(response_days=15, deadline_quote="pay within 7 days from the receipt of this notice"), True,
     dict(response_days=7, response_days_from="receipt")),
    # quote not verified: nothing is overridden
    (dict(response_days=15, deadline_quote="pay within 7 days from the receipt of this notice"), False, dict(response_days=15)),
    # day/month swap on 12.10.2026 is corrected from the text
    (dict(notice_date="2026-12-10"), True, dict(notice_date="2026-10-12")),
    # "by 30 October" without a year: the year comes from the notice date
    (dict(notice_date="2026-10-12", response_deadline_date="2027-10-30", deadline_quote="reply by 30 October positively"), True,
     dict(response_deadline_date="2026-10-30")),
    # forthwith with no date or period
    (dict(deadline_quote="You are directed to pay the amount forthwith."), True, dict(forthwith=True)),
    # period plus "that is, on or before": both are kept, the earliest-of rule decides
    (dict(deadline_quote="within 15 days of the receipt of this notice, that is, on or before 31 October 2026"), True,
     dict(response_days=15, response_deadline_date="2026-10-31")),
    # a date in the quote that is the notice's own date is not a deadline
    (dict(notice_date="2026-10-12", deadline_quote="By this notice dated 12.10.2026 you are to pay within 15 days"), True,
     dict(response_days=15, response_deadline_date=None)),
    # an AI date that appears nowhere in the notice is dropped
    (dict(response_deadline_date="2026-11-11", deadline_quote="pay within 7 days from the receipt of this notice"), True,
     dict(response_days=7, response_deadline_date=None)),
    # Hindi quote: the period and anchor are read from Devanagari
    (dict(response_days=30, deadline_quote="इस नोटिस की प्राप्ति के १५ दिनों के भीतर भुगतान करें"), True,
     dict(response_days=15, response_days_from="receipt")),
])
def test_reconcile_with_the_quote(kw, quote_ok, expect):
    f, notes, _ = rules.reconcile_facts(facts(**kw), NOTICE, RECEIVED, quote_ok, False)
    for k, v in expect.items():
        assert getattr(f, k) == v, (k, notes)


def test_notice_date_found_in_the_text_is_marked_verified():
    _, _, ok = rules.reconcile_facts(facts(notice_date="2026-10-12"), NOTICE, RECEIVED, False, False)
    _, _, missing = rules.reconcile_facts(facts(notice_date="2026-10-01"), NOTICE, RECEIVED, False, False)
    assert ok is True and missing is False


def test_hearing_date_is_read_from_the_hearing_quote():
    f, _, _ = rules.reconcile_facts(
        facts(notice_date="2026-10-12", hearing_date="2026-05-11", hearing_quote="appear before the undersigned on 05.11.2026 at 11 AM"),
        NOTICE, RECEIVED, False, True)
    assert f.hearing_date == "2026-11-05"
