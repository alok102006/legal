import json

import pytest

from app.core.llm.errors import LLMUnavailable
from app.core.rag.parsing import Page, ParsedDocument, parse_text_bytes
from app.workspaces.contract_intelligence.engine import pipeline, rules, scoring, verify
from app.workspaces.contract_intelligence.engine.schemas import (
    ContractFacts, ContractType, FindingCategory, RiskAnalysis, Severity,
)
from app.workspaces.contract_intelligence.engine.segmenter import render_for_llm, segment_contract

from tests.workspaces.contract_intelligence.sample_contracts import BALANCED_AGREEMENT, SUPPLY_AGREEMENT


def _doc(text: str) -> ParsedDocument:
    return parse_text_bytes(text.encode("utf-8"))


# ------------------------------------------------------------------ segmenter

def test_segmenter_finds_numbered_clauses():
    segs = segment_contract(_doc(SUPPLY_AGREEMENT))
    headings = [s.heading.lower() for s in segs]
    assert any("scope of supply" in h for h in headings)
    assert any("term and termination" in h for h in headings)
    assert any("liability" in h for h in headings)
    assert len(segs) >= 7
    # sub-clauses stay with their parent clause
    payment = next(s for s in segs if "payment" in s.heading.lower())
    assert "60 days" in payment.text and "24% per annum" in payment.text


def test_segmenter_tracks_pages_for_pdfs():
    doc = ParsedDocument(
        pages=[Page(1, "1. PAYMENT\nPay within 30 days."), Page(2, "2. TERMINATION\nEither party may terminate.")],
        kind="pdf", has_pages=True,
    )
    segs = segment_contract(doc)
    by_head = {s.heading: s for s in segs}
    assert by_head["PAYMENT"].page_start == 1
    assert by_head["TERMINATION"].page_start == 2


def test_render_for_llm_has_citable_markers():
    out = render_for_llm(segment_contract(_doc(SUPPLY_AGREEMENT)))
    assert "[[S1" in out and "[[S2" in out


def test_segmenter_fallback_for_unstructured_text():
    text = "\n".join(f"This is plain sentence number {i} of a very long unstructured agreement text." for i in range(60))
    segs = segment_contract(_doc(text))
    assert len(segs) >= 2


# ------------------------------------------------------------------ verify

def test_quote_verification_exact_fuzzy_and_fabricated():
    segs = segment_contract(_doc(SUPPLY_AGREEMENT))
    exact = verify.find_quote("The Buyer shall pay each invoice within 60 days of receipt of the invoice.", segs)
    assert exact.verified and exact.score == 100.0

    noisy = verify.find_quote("The Buyer shall pay each invoice  within 60 days of receipt of the\ninvoice", segs)
    assert noisy.verified

    near = verify.find_quote("Buyer shall pay every invoice within sixty (60) days from receipt of invoice", segs)
    assert near.verified is False or near.score >= verify.FUZZY_THRESHOLD

    fake = verify.find_quote("The Supplier shall provide a 5 year warranty on all goods supplied hereunder.", segs)
    assert not fake.verified


def test_quote_hint_prefers_given_segment():
    segs = segment_contract(_doc(SUPPLY_AGREEMENT))
    m = verify.find_quote("any amendment must be in writing and signed by both parties", segs, hint_segment_id="S99")
    assert m.verified and m.segment_id != "S99"


# ------------------------------------------------------------------ rules

def _facts(**kw) -> ContractFacts:
    base = dict(
        title="T", contract_type=ContractType.supply, summary_points=["x"],
        parties=[{"name": "Kumar Auto", "role": "Buyer", "is_our_client": True}, {"name": "Shree Steel", "role": "Supplier"}],
    )
    base.update(kw)
    return ContractFacts(**base)


def _ids(facts, org=None):
    return {r.rule_id for r in rules.run_rules(facts, org, [])}


def test_msme_rule_fires_for_buyer_over_45_days():
    assert "IN-MSME-45-BUYER" in _ids(_facts(payment_days=60))
    assert "IN-MSME-45-BUYER" not in _ids(_facts(payment_days=30))
    assert "IN-MSME-45-BUYER" not in _ids(_facts(payment_days=None))


def test_msme_rule_not_for_non_supply_contracts():
    assert "IN-MSME-45-BUYER" not in _ids(_facts(payment_days=90, contract_type=ContractType.lease))


def test_msme_seller_rule_uses_org_profile():
    facts = _facts(
        payment_days=90,
        parties=[{"name": "Small Co", "role": "Supplier", "is_our_client": True}, {"name": "Big Co", "role": "Buyer"}],
    )
    assert "IN-MSME-45-SELLER" in _ids(facts, rules.OrgProfile(msme_category="small"))
    assert "IN-MSME-45-SELLER" not in _ids(facts, rules.OrgProfile(msme_category="none"))
    assert "IN-MSME-45-SELLER" not in _ids(facts, None)


def test_structural_rules():
    ids = _ids(_facts(
        liability_cap_present=False, auto_renewal=True, renewal_notice_days=90,
        governing_law="Laws of Singapore", termination_notice_days_other=15, stamp_duty_mentioned=False,
    ))
    assert {"IN-LIAB-NOCAP", "IN-AUTORENEW", "IN-FOREIGN-LAW", "IN-TERM-ONESIDED", "IN-STAMP"} <= ids


def test_balanced_facts_trigger_nothing_serious():
    ids = _ids(_facts(
        contract_type=ContractType.service, payment_days=30, liability_cap_present=True, auto_renewal=False,
        governing_law="Laws of India", dispute_mechanism="arbitration",
        termination_notice_days_client=30, termination_notice_days_other=30, stamp_duty_mentioned=True,
    ))
    assert ids == set()


# ------------------------------------------------------------------ scoring

def test_score_counts_only_evidence_backed_items_and_caps_categories():
    items = [
        scoring.ScoreInput("liability_indemnity", Severity.critical, True),
        scoring.ScoreInput("liability_indemnity", Severity.critical, True),   # capped at 40 for the category
        scoring.ScoreInput("payment_terms", Severity.high, False),            # unverified: ignored
        scoring.ScoreInput("termination", Severity.low, True),
    ]
    res = scoring.compute_score(items)
    assert res.by_category == {"liability_indemnity": 40, "termination": 3}
    assert res.score == 43 and res.level == "medium"


def test_score_levels():
    assert scoring.level_for(10) == "low" and scoring.level_for(30) == "medium" and scoring.level_for(80) == "high"


# ------------------------------------------------------------------ pipeline (fake LLM)

def _facts_json(**over):
    d = dict(
        title="Supply Agreement", contract_type="supply",
        summary_points=["Buyer purchases steel sheets from the Supplier."],
        parties=[{"name": "Kumar Auto Components Private Limited", "role": "Buyer", "is_our_client": False},
                 {"name": "Shree Steel Traders", "role": "Supplier", "is_our_client": False}],
        effective_date="2026-04-01", payment_days=60, auto_renewal=True, renewal_notice_days=90,
        liability_cap_present=False, governing_law="Laws of Singapore", jurisdiction="Courts of Singapore",
        termination_notice_days_client=None, termination_notice_days_other=15, stamp_duty_mentioned=False,
    )
    d.update(over)
    return json.dumps(d)


REAL_QUOTE = "The Buyer shall indemnify the Supplier against all losses, claims and expenses of whatever nature arising out of this Agreement, without limit."


def _handler(call):
    if call.schema is ContractFacts:
        return _facts_json()
    if call.schema is RiskAnalysis:
        return json.dumps({
            "findings": [
                {"segment_id": "S6", "category": "liability_indemnity", "severity": "critical",
                 "title": "Unlimited indemnity in the Supplier's favour",
                 "why_it_matters": "You pay for any loss of any size.", "quote": REAL_QUOTE,
                 "recommendation": "Cap it.", "suggested_wording": "Liability is capped at fees paid in 12 months."},
                {"segment_id": "S3", "category": "penalty_damages", "severity": "high",
                 "title": "Hallucinated penalty", "why_it_matters": "n/a",
                 "quote": "The Supplier shall pay a penalty of ten percent for every week of delay beyond the scheduled date.",
                 "recommendation": "n/a"},
            ],
            "missing_protections": [
                {"category": "force_majeure", "title": "No force majeure clause", "why_it_matters": "No relief for events beyond control."}
            ],
        })
    raise AssertionError("unexpected schema")


def test_pipeline_end_to_end_with_fake_llm(fake_llm):
    fake_llm(_handler)
    res = pipeline.analyze_parsed(
        _doc(SUPPLY_AGREEMENT), org=rules.OrgProfile(entity_type="private_limited"),
        org_name="Kumar Auto Components Pvt Ltd",
    )
    # client was identified from the organisation name
    assert [p.role for p in res.facts.parties if p.is_our_client] == ["Buyer"]

    by_title = {f.title: f for f in res.findings}
    real = by_title["Unlimited indemnity in the Supplier's favour"]
    assert real.verified and real.counts_toward_score and real.page is None  # txt has no pages
    fake = by_title["Hallucinated penalty"]
    assert not fake.verified and not fake.counts_toward_score

    rule_ids = {f.rule_id for f in res.findings if f.rule_id}
    assert {"IN-MSME-45-BUYER", "IN-FOREIGN-LAW", "IN-TERM-ONESIDED", "IN-AUTORENEW", "IN-STAMP"} <= rule_ids
    assert any(f.source == "missing" and f.category == "force_majeure" for f in res.findings)

    assert res.score.level == "high"
    assert "Hallucinated penalty" not in res.score.top_drivers
    assert any("could not be matched" in w for w in res.warnings)
    # most severe first
    assert res.findings[0].severity == "critical"


def test_rule_and_ai_finding_about_the_same_issue_are_merged_not_double_counted(fake_llm):
    fake_llm(_handler)
    res = pipeline.analyze_parsed(_doc(SUPPLY_AGREEMENT), org_name="Kumar Auto Components Pvt Ltd")
    liability = [f for f in res.findings if f.category == "liability_indemnity"]
    assert len(liability) == 1                               # AI "unlimited indemnity" + rule "no cap" -> one finding
    f = liability[0]
    assert f.source == "ai" and f.rule_id == "IN-LIAB-NOCAP" and f.legal_ref and f.severity == "critical"
    assert res.score.by_category["liability_indemnity"] == 30    # counted once


def test_pipeline_propagates_llm_failure(fake_llm):
    def boom(call):
        raise LLMUnavailable("down")
    fake_llm(boom)
    with pytest.raises(LLMUnavailable):
        pipeline.analyze_parsed(_doc(SUPPLY_AGREEMENT))


def test_pipeline_rejects_tiny_documents():
    from app.shared.exceptions import BadRequestException
    with pytest.raises(BadRequestException):
        pipeline.prepare_document(b"too short", "x.txt")
