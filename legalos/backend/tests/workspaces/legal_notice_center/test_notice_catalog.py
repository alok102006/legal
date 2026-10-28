"""The notice reference table: complete, sourced, and conservative about statutory windows."""
from app.workspaces.legal_notice_center.engine import prompts, rules
from app.workspaces.legal_notice_center.engine.catalog import CATALOG, HANDLER_LABELS
from app.workspaces.legal_notice_center.engine.schemas import NoticeType

# A reply window is only used where a statute fixes it. Adding one here must be a deliberate, cited decision.
EXPECTED_WINDOWS = {
    "gst_scrutiny_asmt10": (30, "days", "receipt", "r.99(2)"),
    "gst_demand_order_drc07": (3, "months", "receipt", "s.107(1)"),
    "gst_registration_cancellation_reg17": (7, "working_days", "receipt", "r.22(2)"),
    "gst_non_filer_gstr3a": (15, "days", "receipt", "r.68"),
    "it_demand_156": (30, "days", "receipt", "s.220(1)"),
    "sarfaesi_13_2": (60, "days", "notice_date", "s.13(2)"),
    "cheque_bounce": (15, "days", "receipt", "s.138"),
    "arbitration_invocation": (30, "days", "receipt", "s.11(4)"),
    "court_summons": (30, "days", "receipt", "Order VIII r.1"),
    "consumer_complaint": (30, "days", "receipt", "s.38(2)(a)"),
}

REQUIRED_TYPES = {
    "gst_scrutiny_asmt10", "gst_show_cause_drc01", "gst_demand_order_drc07", "gst_registration_cancellation_reg17", "gst_non_filer_gstr3a",
    "it_inquiry_142_1", "it_scrutiny_143_2", "it_reassessment_148", "it_demand_156", "it_penalty_271", "tds_default",
    "epf_inquiry_7a", "epf_damages_14b", "esi_inquiry_45a", "labour_inspection", "factory_inspection", "pollution_control", "fssai_notice",
    "legal_metrology", "municipal_property_tax", "municipal_trade_licence", "bank_loan_recall", "sarfaesi_13_2", "cheque_bounce",
    "lok_adalat", "msme_samadhaan", "arbitration_invocation", "court_summons", "court_summons_criminal", "police_summons",
    "insurance_repudiation", "rera_notice", "consumer_complaint", "ip_notice", "defamation", "tenancy_notice", "employment_dispute",
    "contract_breach", "legal_demand", "other",
    # kept for cases stored before the granular taxonomy
    "gst_notice", "income_tax_notice", "labour_notice", "regulatory_other", "msme_delayed_payment",
}


def test_every_type_has_a_complete_sourced_entry():
    assert REQUIRED_TYPES <= {t.value for t in NoticeType}
    assert set(CATALOG) == set(NoticeType)
    for t, r in CATALOG.items():
        assert r.label and r.meaning and r.if_ignored and r.ref and r.channel and r.documents, t
        assert r.handler in HANDLER_LABELS and r.response in ("letter", "action_plan"), t
        assert r.urgency_floor in ("low", "medium", "high", "critical"), t
        assert r.verified or r.verify_note, f"{t}: unverified entries must say what is being verified"


def test_statutory_windows_are_exactly_the_cited_ones():
    got = {t.value: (w.count, w.unit, w.anchor) for t, w in rules.STATUTORY_WINDOWS.items()}
    assert got == {k: v[:3] for k, v in EXPECTED_WINDOWS.items()}
    for t, w in rules.STATUTORY_WINDOWS.items():
        assert EXPECTED_WINDOWS[t.value][3] in w.citation and w.note


def test_types_where_a_letter_is_the_wrong_move_get_an_action_plan():
    plan = {t.value for t, r in CATALOG.items() if r.response == "action_plan"}
    assert {"court_summons", "court_summons_criminal", "police_summons", "it_scrutiny_143_2", "it_inquiry_142_1",
            "gst_demand_order_drc07", "lok_adalat"} <= plan
    assert not {"cheque_bounce", "gst_show_cause_drc01", "legal_demand", "ip_notice"} & plan


def test_appearance_matters_require_a_lawyer():
    for t in ("court_summons", "court_summons_criminal", "police_summons", "arbitration_invocation"):
        assert CATALOG[NoticeType(t)].handler == "lawyer_required"


def test_the_prompt_lists_every_type_from_the_table():
    for t in NoticeType:
        assert f"  {t.value} = " in prompts.FACTS_SYSTEM


def test_type_info_is_ui_ready_and_tolerates_unknown_stored_types():
    info = rules.type_info("gst_registration_cancellation_reg17")
    assert info["statutory_window"]["unit"] == "working_days" and info["handler_label"] and info["response"] == "letter"
    assert rules.type_info("police_summons")["verified"] is False
    assert rules.type_info("some_old_type") is None and rules.deadline_rule("some_old_type", "statutory_default") is None
