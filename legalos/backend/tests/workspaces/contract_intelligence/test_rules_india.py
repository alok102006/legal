"""Every India rule: fires on the clause it is about (with that clause quoted verbatim), stays quiet otherwise."""
from typing import Dict, Optional

from app.core.rag.parsing import parse_text_bytes
from app.workspaces.contract_intelligence.engine import rules, verify
from app.workspaces.contract_intelligence.engine.schemas import ContractFacts
from app.workspaces.contract_intelligence.engine.segmenter import segment_contract

ROLES = {
    "supply": ("Buyer", "Supplier"), "distribution": ("Distributor", "Company"), "lease": ("Licensee", "Licensor"),
    "loan_guarantee": ("Borrower", "Lender"), "software_license": ("Customer", "Vendor"), "service": ("Client", "Consultant"),
    "employment": ("Employer", "Employee"), "partnership": ("Partner", "Partner B"),
}


def run(text: str, ctype: str = "supply", org: Optional[rules.OrgProfile] = None, client_role: Optional[str] = None,
        complete: bool = True, **facts) -> Dict[str, rules.RuleFinding]:
    mine, theirs = ROLES[ctype]
    mine = client_role or mine
    f = ContractFacts(title="T", contract_type=ctype, summary_points=[], parties=[
        {"name": f"Alpha {mine} Pvt Ltd", "role": mine, "is_our_client": True},
        {"name": f"Beta {theirs} Ltd", "role": theirs}], **facts)
    segs = segment_contract(parse_text_bytes(text.encode("utf-8")))
    found = {r.rule_id: r for r in rules.run_rules(f, org, segs, complete=complete)}
    for r in found.values():                      # presence rules always quote real text
        if r.quote:
            assert verify.find_quote(r.quote, segs).verified or len(r.quote) < 25, r.quote
            assert r.segment_id and r.legal_ref
    return found


def clause(body: str) -> str:
    return f"AGREEMENT\n\n1. GENERAL\nThis agreement is made at Ahmedabad between the parties named above.\n\n2. TERMS\n{body}\n"


# ------------------------------------------------------------------ restraint, penalty, interest

def test_post_term_non_compete_binds_client():
    r = run(clause("The Distributor shall not, during the Term and for two (2) years thereafter, deal in any competing product."),
            "distribution")["IN-NONCOMPETE-POST"]
    assert r.severity.value == "high" and "s.27" in r.legal_ref and "thereafter" in r.quote


def test_non_compete_only_during_term_is_fine():
    assert "IN-NONCOMPETE-POST" not in run(clause("The Distributor shall not deal in any competing product during the Term."), "distribution")


def test_non_compete_in_employers_offer_letter_is_flagged_as_unenforceable_protection():
    r = run(clause("You shall not join any competing business for a period of one year after leaving the Company."),
            "employment")["IN-NONCOMPETE-POST"]
    assert r.severity.value == "low" and "unlikely to be enforceable" in r.title


def test_heavy_liquidated_damages_paid_by_client():
    r = run(clause("If purchases fall short, the Distributor shall pay to the Company thirty per cent (30%) of the shortfall as liquidated damages."),
            "distribution")["IN-PENALTY-S74"]
    assert r.severity.value == "high" and "s.74" in r.legal_ref


def test_damages_payable_to_client_are_not_flagged():
    assert "IN-PENALTY-S74" not in run(clause(
        "If delivery is late, the Supplier shall pay to the Buyer liquidated damages of 0.5% per week of delay."))


def test_interest_above_threshold_and_compounded():
    r = run(clause("Any delay in payment shall carry interest at 24% per annum, compounded monthly."))["IN-INTEREST-HIGH"]
    assert r.severity.value == "high" and "24%" in r.title
    assert "IN-INTEREST-HIGH" not in run(clause("Any delay in payment shall carry simple interest at 12% per annum."))


def test_monthly_interest_is_annualised():
    r = run(clause("Overdue sums shall carry interest at two per cent (2%) per month until paid."))["IN-INTEREST-HIGH"]
    assert "24%" in r.title


def test_loan_interest_uses_a_higher_threshold():
    assert "IN-INTEREST-HIGH" not in run(clause("The loan shall carry interest at 20% per annum."), "loan_guarantee")
    r = run(clause("If any EMI is not paid, the Borrower shall pay penal interest at thirty-six per cent (36%) per annum, compounded monthly."),
            "loan_guarantee")["IN-INTEREST-HIGH"]
    assert r.severity.value == "high" and "RBI" in r.legal_ref


def test_interest_rule_reads_hindi():
    text = "अनुबंध\n\nधारा 1 भुगतान\nविलंबित भुगतान पर 24 प्रतिशत प्रति वर्ष की दर से ब्याज देय होगा और यह क्रेता द्वारा चुकाया जाएगा।"
    assert "IN-INTEREST-HIGH" in run(text)


# ------------------------------------------------------------------ security taken from the client

def test_personal_guarantee_by_director():
    r = run(clause("The Borrower shall procure the personal guarantee of its directors for all sums due."), "loan_guarantee")
    assert r["IN-PERSONAL-GUARANTEE"].severity.value == "critical"
    assert "IN-PERSONAL-GUARANTEE" not in run(clause("The Borrower shall procure the personal guarantee of its directors."),
                                               "loan_guarantee", client_role="Lender")


def test_blank_security_cheques():
    r = run(clause("The Borrower has delivered five cheques signed but with the amount and date left blank as security."), "loan_guarantee")
    assert r["IN-SECURITY-CHEQUE"].severity.value == "high" and "138" in r["IN-SECURITY-CHEQUE"].legal_ref
    assert "IN-SECURITY-CHEQUE" not in run(clause("Payment shall be made by RTGS to the account notified in writing."), "loan_guarantee")


def test_auto_debit_without_cap():
    assert "IN-AUTODEBIT-NOCAP" in run(clause(
        "The Borrower shall register a NACH mandate authorising the Lender to debit any amounts due from its account."), "loan_guarantee")
    assert "IN-AUTODEBIT-NOCAP" not in run(clause(
        "The Borrower shall register a NACH mandate for the monthly EMI of Rs 25,000, with a maximum amount of Rs 25,000."), "loan_guarantee")


def test_original_documents_retained():
    emp = run(clause("The Company shall retain your original educational certificates in its custody during the bond period."), "employment")
    assert emp["IN-ORIGINAL-DOCS"].severity.value == "medium"
    loan = run(clause("The Borrower shall deposit the original title deeds of the factory with the Lender."), "loan_guarantee")
    assert loan["IN-ORIGINAL-DOCS"].severity.value == "low" and "RBI" in loan["IN-ORIGINAL-DOCS"].legal_ref


# ------------------------------------------------------------------ one-sided commercial terms

def test_unilateral_price_change_by_counterparty():
    r = run(clause("The Supplier may revise the prices at any time by giving seven (7) days' written notice."))
    assert r["IN-PRICE-UNILATERAL"].severity.value == "high"
    assert "IN-PRICE-UNILATERAL" not in run(clause("Prices may be revised only by mutual written agreement of both parties."))
    assert "IN-PRICE-UNILATERAL" not in run(clause("The Buyer may revise the prices of future orders by notice."))


def test_price_list_revised_by_company_from_relative_clause():
    r = run(clause("The Products shall be sold at the prices in the Price List, which the Company may revise at any time without notice."),
            "distribution")
    assert "IN-PRICE-UNILATERAL" in r


def test_long_lock_in_without_exit():
    r = run(clause("The Licensee agrees to a lock-in period of thirty-six (36) months during which it cannot terminate."), "lease")
    assert r["IN-LOCKIN-24M"].title.startswith("Locked in for 36 months")
    assert "IN-LOCKIN-24M" not in run(clause("The Licensee agrees to a lock-in period of twelve (12) months."), "lease")
    assert "IN-LOCKIN-24M" not in run(clause(
        "The Licensee agrees to a lock-in period of thirty-six (36) months.\n2.2 The Licensee may terminate this Agreement during the lock-in period on three months' notice."), "lease")


def test_slow_deposit_refund():
    r = run(clause("The Licensor shall refund the security deposit within one hundred and eighty (180) days of handover of possession."), "lease")
    assert "180 days" in r["IN-DEPOSIT-REFUND"].title
    assert "IN-DEPOSIT-REFUND" not in run(clause(
        "The Licensor shall refund the security deposit within 30 days of handover, failing which the delay in refund shall carry interest at 18% per annum."), "lease")


def test_deposit_amount_in_months_is_not_a_refund_period():
    r = run(clause("The Licensee has paid a refundable security deposit equal to six (6) months' rent, which shall be refunded within 15 days of handover."), "lease")
    assert "IN-DEPOSIT-REFUND" not in r


def test_rent_escalation_above_ten_percent_a_year():
    r = run(clause("The rent shall be increased by 15% every twelve (12) months, compounded."), "lease")
    assert r["IN-ESCALATION-10"].severity.value == "high" and "15%" in r["IN-ESCALATION-10"].title
    assert "IN-ESCALATION-10" not in run(clause("The rent shall be increased by 15% every three (3) years."), "lease")


def test_notice_period_asymmetry():
    text = clause("The Distributor may terminate on ninety (90) days' notice and the Company may terminate on thirty (30) days' notice.")
    assert "IN-NOTICE-ASYM" in run(text, "distribution", termination_notice_days_client=90, termination_notice_days_other=30)
    assert "IN-NOTICE-ASYM" not in run(text, "distribution", termination_notice_days_client=30, termination_notice_days_other=30)


def test_one_sided_termination_needs_the_clause():
    text = clause("The Company may terminate this Agreement at any time on thirty (30) days' written notice.")
    assert "IN-TERM-ONESIDED" in run(text, "distribution", termination_notice_days_other=30)
    assert "IN-TERM-ONESIDED" not in run(clause("Prices are in the schedule."), "distribution", termination_notice_days_other=30)


def test_assignment_without_consent():
    r = run(clause("The Vendor may assign this Agreement without the consent of the Customer."), "software_license")
    assert "Khardah" in r["IN-ASSIGN-NOCONSENT"].legal_ref
    assert "IN-ASSIGN-NOCONSENT" not in run(clause("The Customer may assign this Agreement without consent to its affiliates."),
                                             "software_license")


def test_auto_renewal_needs_the_clause():
    text = clause("This Agreement shall renew automatically for further one-year terms unless either party gives 90 days' notice.")
    assert "IN-AUTORENEW" in run(text, auto_renewal=True, renewal_notice_days=90)
    assert "IN-AUTORENEW" not in run(clause("Prices are in the schedule annexed hereto."), auto_renewal=True)


# ------------------------------------------------------------------ disputes

def test_jurisdiction_in_another_state():
    text = clause("The courts at Mumbai shall have exclusive jurisdiction over all disputes.")
    r = run(text, "distribution", org=rules.OrgProfile(state_code="24"), jurisdiction="Courts at Mumbai")
    assert "Maharashtra" in r["IN-JURIS-OUT-OF-STATE"].title
    assert "IN-JURIS-OUT-OF-STATE" not in run(text, "distribution", org=rules.OrgProfile(state_code="27"), jurisdiction="Courts at Mumbai")
    assert "IN-JURIS-OUT-OF-STATE" not in run(text, "distribution", org=None, jurisdiction="Courts at Mumbai")


def test_arbitration_seated_abroad():
    text = clause("Disputes shall be resolved by arbitration under the SIAC Rules. The seat of arbitration shall be Singapore.")
    r = run(text, arbitration_seat="Singapore")
    assert r["IN-ARB-SEAT-ABROAD"].severity.value == "high" and "BALCO" in r["IN-ARB-SEAT-ABROAD"].legal_ref
    assert "IN-ARB-SEAT-ABROAD" not in run(clause("Disputes shall be resolved by arbitration. The seat of arbitration shall be Pune."),
                                            arbitration_seat="Pune")


def test_foreign_law_needs_a_governing_law_clause_not_the_preamble():
    text = "AGREEMENT\n\n1. PARTIES\nBeta Supplier Ltd, a company incorporated under the laws of Singapore, and the Buyer.\n\n2. PRICE\nPrices are in Schedule A."
    assert "IN-FOREIGN-LAW" not in run(text, governing_law="Laws of Singapore")


def test_no_dispute_clause_only_when_whole_contract_read():
    text = clause("The Supplier shall deliver goods within 30 days of each order.")
    assert "IN-NO-DISPUTE" in run(text)
    assert "IN-NO-DISPUTE" not in run(text, complete=False)


# ------------------------------------------------------------------ absence rules confirmed by text

def test_no_gst_clause_on_taxable_supply():
    assert "IN-NO-GST" in run(clause("The Client shall pay a fee of Rs 50,000 per month within 30 days of invoice."), "service")
    assert "IN-NO-GST" not in run(clause("The Client shall pay a fee of Rs 50,000 per month plus GST within 30 days of invoice."), "service")
    assert "IN-NO-GST" not in run(clause("The Client shall pay a fee of Rs 50,000 per month."), "service", complete=False)


def test_no_cap_rule_double_checks_the_text():
    capped = clause("The Supplier's total liability under this Agreement shall not exceed the fees paid in the previous 12 months.")
    assert "IN-LIAB-NOCAP" not in run(capped, liability_cap_present=False)
    assert "IN-LIAB-NOCAP" in run(clause("The Buyer shall indemnify the Supplier against all losses."), liability_cap_present=False)


def test_stamp_rule_double_checks_the_text():
    assert "IN-STAMP" not in run(clause("This Agreement is executed on stamp paper of appropriate value."), stamp_duty_mentioned=False)
    assert "IN-STAMP" in run(clause("Prices are in Schedule A."), stamp_duty_mentioned=False)
