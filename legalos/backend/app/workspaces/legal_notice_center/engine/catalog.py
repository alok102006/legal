"""What each kind of notice means in Indian law: the reference table behind every notice case.

One entry per NoticeType. Everything here is general decision support with its source (act + section):
  window      the reply / payment / appeal period ONLY where a statute itself fixes it. Otherwise None, and the
              deadline must come from the notice ("stated") or stays unknown. Never a "usual practice" number.
  if_ignored  the legal consequence chain, step by step.
  handler     who should prepare the response: owner | ca | lawyer | lawyer_required.
  response    'letter' (a written reply is the right move) or 'action_plan' (appearance, portal filing, payment
              or appeal is what the law expects; a letter would be the wrong instrument).
  verified    False where a point is still being checked (recently renumbered law, state-specific rules); the
              UI shows "being verified" and verify_note says what is open.
"""
from dataclasses import dataclass
from typing import Optional, Tuple

from app.workspaces.legal_notice_center.engine.schemas import NoticeType as T

CATALOG_VERSION = "2026-10-28.1"


@dataclass(frozen=True)
class StatutoryWindow:
    count: int
    unit: str            # days | working_days | months
    anchor: str          # receipt | notice_date - what the period counts from
    citation: str        # act + section that fixes it
    note: str            # one plain line shown to the user
    purpose: str = "reply"   # reply | pay | appeal | appoint | file | written_statement


@dataclass(frozen=True)
class NoticeRule:
    label: str
    family: str
    classify: str        # one line telling the model when to choose this type
    meaning: str
    if_ignored: str
    ref: str
    documents: Tuple[str, ...]
    handler: str
    response: str
    channel: str         # how the response is actually made
    window: Optional[StatutoryWindow] = None
    without_prejudice: bool = False
    urgency_floor: str = "low"
    verified: bool = True
    verify_note: str = ""


HANDLER_LABELS = {
    "owner": "You can handle this yourself; keep a lawyer informed if the amount is large.",
    "ca": "Your CA / tax or compliance consultant should prepare and file the response.",
    "lawyer": "Have a lawyer review the response before it goes out.",
    "lawyer_required": "Do not handle this without a lawyer: an appearance before a court, police or tribunal is involved.",
}

_IT_NOTE = ("The Income-tax Act 2025 applies from 1 April 2026 with renumbered sections; proceedings for earlier years keep the "
            "1961 Act sections cited here. Rely on the section printed on the notice.")
_LABOUR_NOTE = ("The four Labour Codes replace these Acts (brought into force in November 2025, with transition for pending matters); "
                "the section numbers in the new Codes are being verified. Rely on the section printed on the notice.")
_STATE_NOTE = "This depends on your state's municipal law; the periods and penalties differ by state and are being verified."

_GST_DOCS = ("GSTR-1 and GSTR-3B returns for the period", "GSTR-2A / 2B statements", "Purchase and sales registers",
             "Tax invoices and e-way bills", "Payment challans (DRC-03 / cash ledger)")

CATALOG: dict[T, NoticeRule] = {
    # ------------------------------------------------------------------ GST
    T.gst_scrutiny_asmt10: NoticeRule(
        "GST scrutiny notice (ASMT-10)", "gst",
        "Form GST ASMT-10: discrepancies found on scrutiny of returns under CGST s.61",
        "The GST officer found discrepancies while scrutinising your returns (s.61) and asks you to explain them, or to accept them "
        "and pay the tax with interest. You reply in Form GST ASMT-11.",
        "If you do not explain in time, the officer can start an audit (s.65), a special audit (s.66) or an inspection (s.67), or issue a "
        "show-cause notice demanding the tax with interest and penalty (s.73 / s.74 / s.74A).",
        "CGST Act 2017, s.61; CGST Rules 2017, r.99", _GST_DOCS + ("Reconciliation of the figures the notice questions",),
        "ca", "letter", "Reply in Form GST ASMT-11 on the GST portal with the supporting documents",
        StatutoryWindow(30, "days", "receipt", "CGST Rules 2017, r.99(2)",
                        "The reply in ASMT-11 is due within 30 days of being informed, unless the officer allows more time.")),
    T.gst_show_cause_drc01: NoticeRule(
        "GST show-cause notice (DRC-01)", "gst",
        "Form GST DRC-01 / show-cause notice proposing tax, interest and penalty under CGST s.73, s.74 or s.74A",
        "The officer proposes a tax demand with interest and penalty (s.73 where no fraud is alleged, s.74 for fraud or suppression, "
        "s.74A for FY 2024-25 onward) and asks you to show cause. Reply in Form GST DRC-06 within the time the notice gives and ask "
        "for a personal hearing. Paying the tax and interest early (within 30 days of the notice under s.73 / s.74) removes or "
        "reduces the penalty.",
        "The officer confirms the demand without your side in an order (summary in DRC-07) with interest (s.50) and penalty -> "
        "the amount becomes recoverable -> recovery from your bank account, your debtors or your property (s.79) -> an appeal is "
        "possible only with a 10% pre-deposit of the disputed tax (s.107).",
        "CGST Act 2017, ss.73, 74, 74A, 75(4); CGST Rules 2017, r.142", _GST_DOCS + ("Supplier-wise ITC reconciliation", "Proof of payment to suppliers"),
        "ca", "letter", "Reply in Form GST DRC-06 on the GST portal and ask for a personal hearing (s.75(4))",
        urgency_floor="medium"),
    T.gst_demand_order_drc07: NoticeRule(
        "GST demand order (DRC-07)", "gst",
        "Form GST DRC-07: summary of an ORDER confirming a GST demand (not a show-cause)",
        "This is not a notice but the summary of an order confirming a tax demand. The amount is payable. You can appeal to the "
        "Appellate Authority in Form GST APL-01 within 3 months of the order being communicated (one more month if the delay is "
        "explained), after depositing 10% of the disputed tax; obvious errors can be rectified (s.161).",
        "The demand becomes final -> the officer recovers it from your bank account, from people who owe you money, or by attaching "
        "and selling property (s.79) -> interest keeps running until it is paid (s.50).",
        "CGST Act 2017, ss.79, 107, 161", ("The order and the show-cause notice it follows", "Your DRC-06 reply and hearing record") + _GST_DOCS,
        "lawyer", "action_plan", "Pay, apply for rectification, or appeal in Form GST APL-01 with the 10% pre-deposit (s.107(6))",
        StatutoryWindow(3, "months", "receipt", "CGST Act 2017, s.107(1)",
                        "An appeal must be filed within 3 months of the order being communicated (s.107(4) allows one more month for sufficient cause).",
                        "appeal"),
        urgency_floor="high"),
    T.gst_registration_cancellation_reg17: NoticeRule(
        "GST registration cancellation notice (REG-17)", "gst",
        "Form GST REG-17: show-cause why GST registration should not be cancelled",
        "The officer proposes to cancel your GST registration (s.29(2)), for example for not filing returns or not working from the "
        "declared place of business. Reply in Form GST REG-18. The registration may already be suspended (r.21A).",
        "Registration is cancelled (REG-19) -> you cannot issue tax invoices or collect GST, buyers lose input tax credit on your "
        "invoices -> tax dues remain payable -> you must apply for revocation (s.30) within its time limit.",
        "CGST Act 2017, ss.29, 30; CGST Rules 2017, rr.21A, 22", ("Pending returns (file them first)", "Proof of the place of business: rent agreement, electricity bill, photographs"),
        "ca", "letter", "Reply in Form GST REG-18 on the GST portal",
        StatutoryWindow(7, "working_days", "receipt", "CGST Rules 2017, r.22(2)",
                        "The reply in REG-18 is due within 7 working days of service of the notice."),
        urgency_floor="high"),
    T.gst_non_filer_gstr3a: NoticeRule(
        "GST return non-filing notice (GSTR-3A)", "gst",
        "Form GSTR-3A: notice to a return defaulter under CGST s.46",
        "You have not filed one or more GST returns (s.46). File the pending return(s) with late fee and interest within 15 days.",
        "The officer assesses your tax to the best of judgment (s.62, order in ASMT-13) with interest and penalty -> continued "
        "non-filing can lead to cancellation of registration (s.29(2)). Filing the valid return within the time s.62(2) allows "
        "withdraws the best-judgment order.",
        "CGST Act 2017, ss.46, 62; CGST Rules 2017, r.68", ("Sales and purchase data for the pending periods", "Cash / credit ledger balance"),
        "ca", "action_plan", "File the pending return(s) on the GST portal",
        StatutoryWindow(15, "days", "receipt", "CGST Rules 2017, r.68", "The pending return must be filed within 15 days of the notice.", "file")),
    T.gst_notice: NoticeRule(
        "GST notice", "gst", "any other GST notice, summons, audit or inspection (CGST Act)",
        "A GST officer asks you to explain, produce records or attend. Reply on the GST portal or as the notice directs, within the time it states.",
        "The officer can decide the matter on the information they have, with tax, interest and penalty, and start recovery.",
        "CGST Act 2017 (the section printed on the notice)", _GST_DOCS, "ca", "letter", "Reply as the notice directs, usually on the GST portal"),

    # ------------------------------------------------------------------ income tax / TDS
    T.it_inquiry_142_1: NoticeRule(
        "Income-tax inquiry notice (s.142(1))", "income_tax",
        "Income-tax notice under s.142(1): file a return or produce accounts / documents / information",
        "The Assessing Officer asks you to file a return or produce accounts, documents or information by the date in the notice. "
        "Respond on the e-filing portal (e-Proceedings) with what is asked; you can request an adjournment there.",
        "Best-judgment assessment on the information the department has (s.144) -> tax demand with interest -> penalty of Rs 10,000 "
        "for each failure (s.272A(1)(d)); wilful failure can be prosecuted (s.276D).",
        "Income-tax Act 1961, ss.142(1), 144, 272A(1)(d), 276D",
        ("Return and computation of income", "Books of account and bank statements", "Documents the notice lists"),
        "ca", "action_plan", "Upload the response on the income-tax e-filing portal (e-Proceedings)", verify_note=_IT_NOTE),
    T.it_scrutiny_143_2: NoticeRule(
        "Income-tax scrutiny notice (s.143(2))", "income_tax",
        "Income-tax notice under s.143(2): return selected for (limited / complete) scrutiny",
        "Your return was selected for scrutiny (limited or complete). Under faceless assessment you respond on the e-filing portal; "
        "the specific questions usually follow in s.142(1) notices.",
        "Best-judgment assessment (s.144) -> demand with interest -> penalty for non-compliance (s.272A(1)(d)) and for under-reporting "
        "income, 50% to 200% of the tax (s.270A).",
        "Income-tax Act 1961, ss.143(2), 144, 270A, 272A",
        ("Return of income and computation", "Audited accounts / books", "Bank statements for the year", "Evidence for the issues listed"),
        "ca", "action_plan", "Upload the response on the income-tax e-filing portal (e-Proceedings)", verify_note=_IT_NOTE),
    T.it_reassessment_148: NoticeRule(
        "Income-tax reassessment notice (s.148 / 148A)", "income_tax",
        "Income-tax notice under s.148 or s.148A: income escaping assessment / reopening",
        "The department believes income escaped assessment. A s.148A show-cause notice lets you object before a s.148 notice is issued; "
        "a s.148 notice requires a return for that year within the period it states. Reopening time limits depend on the year and amount (s.149).",
        "The officer decides under s.148A without your objections and issues a s.148 notice -> reassessment on best judgment (s.144) -> "
        "demand, interest and penalty.",
        "Income-tax Act 1961, ss.147, 148, 148A, 149",
        ("Return and assessment record for that year", "Documents on the transaction the notice names", "Bank statements"),
        "ca", "action_plan", "Respond on the e-filing portal; consider whether the reopening is within time",
        urgency_floor="high", verified=False, verify_note="Post-2024 reassessment procedure details are being verified. " + _IT_NOTE),
    T.it_demand_156: NoticeRule(
        "Income-tax demand notice (s.156)", "income_tax",
        "Income-tax notice of demand under s.156 (tax / interest / penalty payable)",
        "Tax is payable under an assessment, intimation or order. Check the demand on the portal first (it may be a processing error "
        "you can rectify under s.154). Pay within 30 days, or appeal to the CIT(Appeals) within 30 days and ask for a stay.",
        "You become an 'assessee in default' (s.220(4)) -> interest at 1% a month (s.220(2)) -> penalty (s.221) -> refunds are adjusted "
        "and the Tax Recovery Officer can attach bank accounts and property (ss.222, 226).",
        "Income-tax Act 1961, ss.156, 220, 221, 226, 246A, 249",
        ("The assessment order / intimation behind the demand", "Challans of tax already paid", "Form 26AS / AIS"),
        "ca", "action_plan", "Respond on the e-filing portal ('Response to outstanding demand'), pay, or appeal in Form 35",
        StatutoryWindow(30, "days", "receipt", "Income-tax Act 1961, s.220(1)",
                        "The demand is payable within 30 days of service; an appeal to CIT(Appeals) is also due within 30 days (s.249(2)).", "pay"),
        urgency_floor="medium", verify_note=_IT_NOTE),
    T.it_penalty_271: NoticeRule(
        "Income-tax penalty show-cause (s.274 with s.270A / 271)", "income_tax",
        "Income-tax penalty show-cause notice under s.274 read with s.270A, s.271 or similar",
        "The officer proposes a penalty (for under-reporting or misreporting income under s.270A, or another default under s.271 and "
        "following) and gives you a hearing under s.274. Immunity from the s.270A penalty may be available under s.270AA if you accept "
        "the assessment and do not appeal.",
        "The penalty is levied without your explanation -> it becomes a demand under s.156 -> recovery as for any tax demand.",
        "Income-tax Act 1961, ss.270A, 270AA, 271, 274",
        ("Assessment order", "Explanation and evidence for each addition"), "ca", "letter",
        "File the written submission on the e-filing portal (e-Proceedings)", verify_note=_IT_NOTE),
    T.tds_default: NoticeRule(
        "TDS default notice", "income_tax",
        "TDS / TCS default intimation or notice (TRACES, s.200A, s.201 'assessee in default')",
        "The TDS officer or TRACES shows a short deduction, late deduction, late payment or late filing of TDS, or proposes to treat you "
        "as an 'assessee in default' (s.201). Many defaults are fixed by filing a correction statement.",
        "Interest (s.201(1A)) and late-filing fee (s.234E) keep adding -> demand -> penalty (ss.271C, 271H) -> recovery from the bank "
        "account; failure to pay TDS already deducted can be prosecuted (s.276B).",
        "Income-tax Act 1961, ss.200A, 201, 234E, 271C, 271H, 276B",
        ("TDS returns (24Q / 26Q) for the quarter", "TDS challans", "Justification report from TRACES"),
        "ca", "action_plan", "Download the justification report on TRACES; file a correction statement or pay", verify_note=_IT_NOTE),
    T.income_tax_notice: NoticeRule(
        "Income-tax notice", "income_tax", "any other income-tax notice",
        "The income-tax department asks for information, a return or an explanation. Respond on the e-filing portal by the date in the notice.",
        "Best-judgment assessment (s.144) and penalty for non-compliance.",
        "Income-tax Act 1961 (the section printed on the notice)", ("Return of income", "Books and bank statements"),
        "ca", "action_plan", "Respond on the income-tax e-filing portal", verify_note=_IT_NOTE),

    # ------------------------------------------------------------------ labour, inspections, regulators
    T.epf_inquiry_7a: NoticeRule(
        "PF dues inquiry (s.7A EPF Act)", "labour",
        "EPFO summons / notice for an inquiry under s.7A EPF Act (determination of PF dues)",
        "The PF authority is inquiring into the PF dues of your establishment (coverage, wages on which PF was paid, employees left out) "
        "and summons you to appear with records on the date fixed. It has the powers of a civil court.",
        "The dues are decided without your records -> demand with interest (s.7Q) and damages (s.14B) -> recovery by attaching bank "
        "accounts and property (ss.8B-8G) -> an appeal to the Tribunal needs a 75% deposit (s.7O), which can be reduced.",
        "EPF & MP Act 1952, ss.7A, 7O, 7Q, 8B-8G, 14B",
        ("Wage registers and salary sheets", "PF ECR challans and returns", "Attendance records", "List of contract workers"),
        "ca", "action_plan", "Appear (yourself or an authorised representative) on the hearing date with the records",
        urgency_floor="medium", verified=False, verify_note=_LABOUR_NOTE),
    T.epf_damages_14b: NoticeRule(
        "PF damages notice (s.14B)", "labour",
        "EPFO show-cause for damages for late PF remittance under s.14B (often with interest under s.7Q)",
        "PF was paid late and the authority proposes damages for the delay (rising with the length of delay, up to 100% of the arrears) "
        "plus interest at 12% a year (s.7Q). Explain the reasons for the delay in writing and at the hearing.",
        "Damages are levied without your explanation -> recovery from your bank account (s.8B onward); an appeal lies to the Tribunal (s.7I).",
        "EPF & MP Act 1952, ss.7I, 7Q, 8B, 14B; EPF Scheme para 32A",
        ("PF challans with payment dates", "Bank statements for the period", "Proof of the reasons for delay"),
        "ca", "letter", "Written reply and appearance on the hearing date", verified=False, verify_note=_LABOUR_NOTE),
    T.esi_inquiry_45a: NoticeRule(
        "ESI contribution determination (s.45A)", "labour",
        "ESIC notice proposing to determine contributions under s.45A ESI Act, or claiming damages under s.85B",
        "ESIC proposes to fix your contributions on its own estimate because records were not produced or contributions were not paid, "
        "and gives you a hearing.",
        "Contributions are fixed without your records -> interest and damages (s.85B) -> recovery as arrears of land revenue (s.45B), "
        "including bank attachment.",
        "ESI Act 1948, ss.45A, 45B, 85B", ("Wage registers", "ESI challans and returns", "Employee list with wages"),
        "ca", "letter", "Written reply and appearance on the hearing date", verified=False, verify_note=_LABOUR_NOTE),
    T.labour_inspection: NoticeRule(
        "Labour Commissioner / Shops & Establishments notice", "labour",
        "notice from the Labour Commissioner, labour inspector or Shops & Establishments inspector (registration, wages, registers, "
        "working hours) or a conciliation notice on an employee's dispute",
        "A labour inspector or the Labour Commissioner alleges violations (registration, wages, overtime, leave, registers, opening hours) "
        "under the state Shops and Establishments Act or a labour law, or calls you to conciliation of an employee's dispute.",
        "Prosecution before a magistrate with fines (higher for continuing offences); a failed conciliation is referred to the labour "
        "court, which can proceed without you.",
        "State Shops and Establishments Act; Industrial Disputes Act 1947 / Industrial Relations Code 2020",
        ("Shops & Establishments registration", "Attendance and wage registers", "Leave records", "Appointment letters"),
        "ca", "letter", "Written reply to the inspector and attendance on the date fixed", verified=False,
        verify_note=_LABOUR_NOTE + " " + _STATE_NOTE),
    T.labour_notice: NoticeRule(
        "Labour / PF / ESI notice", "labour", "any other PF, ESI or labour-department notice",
        "A labour authority inquires into dues or compliance and may call you to a hearing. Bring proof of contributions and registers.",
        "The authority can decide the dues without your records, add interest and damages, and recover them from your bank account.",
        "EPF Act 1952; ESI Act 1948; Code on Social Security 2020", ("PF / ESI challans and returns", "Wage registers"),
        "ca", "letter", "Written reply and appearance on the date fixed", verified=False, verify_note=_LABOUR_NOTE),
    T.factory_inspection: NoticeRule(
        "Factory inspector notice", "regulator",
        "notice or order from the Inspector / Director of Factories (licence, safety, health, welfare)",
        "The Inspector of Factories found contraventions (licence, safety, health, welfare, registers) and asks you to comply or explain. "
        "It can also be an order prohibiting use of a machine or area that is dangerous.",
        "Prosecution of the occupier and the manager (imprisonment and fines, higher for continuing contraventions) -> for imminent "
        "danger, a prohibitory order stopping work.",
        "Factories Act 1948, ss.9, 40(2), 92 / Occupational Safety, Health and Working Conditions Code 2020",
        ("Factory licence and approved plans", "Safety certificates (boiler, lift, pressure vessels)", "Registers and accident records"),
        "lawyer", "letter", "Comply, then send a written compliance report to the Inspector", verified=False, verify_note=_LABOUR_NOTE),
    T.pollution_control: NoticeRule(
        "Pollution Control Board notice", "regulator",
        "State Pollution Control Board show-cause / direction (consent to establish / operate, discharge or emission limits)",
        "The Pollution Control Board alleges you are operating without valid consent (CTE / CTO) or breaching discharge or emission "
        "limits, and proposes directions that can include closure or cutting electricity and water.",
        "Closure direction and disconnection of power and water (Water Act s.33A, Air Act s.31A) -> environmental compensation -> penalties or prosecution.",
        "Water Act 1974, ss.25, 33A; Air Act 1981, ss.21, 31A; Environment (Protection) Act 1986, s.5",
        ("Consent to establish / operate", "Effluent / emission test reports", "Hazardous-waste records"),
        "lawyer", "letter", "Written reply to the Board and personal hearing", urgency_floor="medium", verified=False,
        verify_note="Penalty provisions were amended in 2023-24 (Jan Vishwas Act, Water Amendment Act 2024) and are being verified."),
    T.fssai_notice: NoticeRule(
        "FSSAI / food safety notice", "regulator",
        "Food Safety officer notice: improvement notice (s.32 FSS Act), sample failure, licence suspension",
        "A Designated Officer found you are not following food-safety rules and issued an improvement notice (s.32) stating what to fix "
        "and by when (at least 14 days), or the notice relates to a food sample that failed.",
        "Licence suspended if the improvement notice is not complied with, then cancelled after a show-cause (s.32(3)) -> failed samples "
        "lead to adjudication penalties (ss.50-57) or prosecution (ss.58-65).",
        "Food Safety and Standards Act 2006, ss.32, 46, 50-65", ("FSSAI licence / registration", "Lab reports", "Supplier invoices for the batch"),
        "lawyer", "letter", "Comply within the period and report compliance in writing to the Designated Officer"),
    T.legal_metrology: NoticeRule(
        "Legal Metrology notice", "regulator",
        "Legal Metrology (weights and measures) notice: packaged-commodity declarations, unverified weighing instruments",
        "The Legal Metrology department alleges a violation such as unverified weighing instruments or packages without the required "
        "declarations (MRP, net quantity, manufacturer, customer care). Many offences can be compounded by paying a fee (s.48).",
        "Prosecution and fines (ss.25-47), seizure of goods or instruments (s.15); repeat offences carry higher penalties.",
        "Legal Metrology Act 2009, ss.15, 18, 36, 48; Legal Metrology (Packaged Commodities) Rules 2011",
        ("Verification certificates of weighing instruments", "Package labels", "Registration as packer / importer"),
        "lawyer", "letter", "Written reply, or apply for compounding (s.48)"),
    T.municipal_property_tax: NoticeRule(
        "Municipal property-tax notice", "municipal",
        "municipal corporation / council notice on property tax (demand, revised assessment, arrears)",
        "The municipal body demands property tax, revises the assessment or claims arrears. Objections and appeals against an assessment "
        "have short time limits under your state's municipal law.",
        "Interest and penalty on arrears -> warrant of distress: attachment and sale of movable property or sealing of the premises -> "
        "recovery as arrears of land revenue.",
        "State municipal corporation / municipalities Act", ("Property-tax bills and receipts", "Sale deed / lease", "Assessment order"),
        "owner", "letter", "Written objection to the assessing officer within the time stated", verified=False, verify_note=_STATE_NOTE),
    T.municipal_trade_licence: NoticeRule(
        "Trade licence notice", "municipal",
        "municipal trade / health / shop licence notice (trading without licence, breach of licence conditions)",
        "The municipal body says you trade without a valid licence or have breached its conditions, and may propose sealing or a fine.",
        "Fines and prosecution under the state municipal law -> sealing of the shop or premises.",
        "State municipal corporation / municipalities Act", ("Trade licence and renewal receipts", "Fire NOC where required"),
        "owner", "letter", "Apply / renew the licence and reply in writing", verified=False, verify_note=_STATE_NOTE),

    # ------------------------------------------------------------------ banks, lenders, payment recovery
    T.bank_loan_recall: NoticeRule(
        "Bank / NBFC loan recall notice", "bank",
        "bank or NBFC notice recalling a loan / demanding the full outstanding (not yet a SARFAESI s.13(2) notice)",
        "The lender says your loan is in default and recalls the full outstanding. It is usually the step before the account is "
        "classified NPA and recovery under SARFAESI, the Debts Recovery Tribunal or the Insolvency Code.",
        "Account classified NPA -> SARFAESI s.13(2) demand and then possession and sale of the security -> application before the DRT "
        "(debts of Rs 20 lakh or more) -> insolvency petition (IBC s.7) for defaults of Rs 1 crore or more; guarantors are pursued too.",
        "SARFAESI Act 2002; Recovery of Debts and Bankruptcy Act 1993; Insolvency and Bankruptcy Code 2016, ss.4, 7",
        ("Sanction letter and loan agreement", "Loan account statement", "Repayment proof", "Security documents"),
        "lawyer", "letter", "Written representation to the lender (dispute the figures or propose restructuring)", urgency_floor="medium"),
    T.sarfaesi_13_2: NoticeRule(
        "SARFAESI demand notice (s.13(2))", "bank",
        "secured lender's demand notice under s.13(2) SARFAESI Act (60 days to pay, else enforcement of security)",
        "A secured lender demands the full outstanding within 60 days of the notice, failing which it can take over the secured assets "
        "(property, machinery, receivables). You can send a representation or objection (s.13(3A)); the lender must reply with "
        "reasons within 15 days.",
        "Possession notice and takeover of the secured asset (s.13(4)) -> auction sale -> any shortfall recovered through the DRT; a "
        "s.13(4) measure can be challenged before the DRT within 45 days (s.17).",
        "SARFAESI Act 2002, ss.13(2), 13(3A), 13(4), 17",
        ("Loan agreement and security documents", "Loan account statement", "Valuation of the secured assets"),
        "lawyer", "letter", "Representation / objection to the authorised officer under s.13(3A)",
        StatutoryWindow(60, "days", "notice_date", "SARFAESI Act 2002, s.13(2)",
                        "The borrower has 60 days from the date of the notice to pay the amount demanded.", "pay"),
        urgency_floor="high"),
    T.cheque_bounce: NoticeRule(
        "Cheque bounce notice", "bank",
        "demand after a dishonoured cheque (s.138 Negotiable Instruments Act)",
        "A cheque that bounces for insufficient funds is a criminal offence if the drawer does not pay within 15 days of receiving the "
        "sender's demand notice. The sender must have issued the notice within 30 days of the bank's return memo. After the 15 days, "
        "they have one month to file a complaint.",
        "After the 15 days the sender can file a criminal complaint within one month (s.142) -> the magistrate summons you as accused -> "
        "conviction can mean up to 2 years' jail, a fine up to twice the cheque amount, or both; the court can order interim "
        "compensation of up to 20% of the cheque amount (s.143A).",
        "Negotiable Instruments Act 1881, ss.138, 142, 143A",
        ("The cheque details and bank return memo", "Invoices and delivery records of the underlying deal", "Ledger of the sender's account", "Proof of any payments made"),
        "lawyer", "letter", "Reply through a lawyer (and pay within 15 days if the amount is owed)",
        StatutoryWindow(15, "days", "receipt", "Negotiable Instruments Act 1881, s.138(b)-(c)",
                        "The drawer has 15 days from receiving the demand notice to pay the cheque amount.", "pay"),
        without_prejudice=True, urgency_floor="critical"),
    T.lok_adalat: NoticeRule(
        "Lok Adalat notice", "bank",
        "notice to attend a Lok Adalat (often pre-litigation, sent by a bank or a legal services authority)",
        "A lender or party has referred the dispute to a Lok Adalat for settlement on the date fixed. Attending is voluntary but useful: "
        "nothing is decided without your consent, and a settlement recorded there is final and cannot be appealed (s.21).",
        "No award is passed against you, but the matter goes back and the lender usually proceeds with a recovery suit, a DRT "
        "application or SARFAESI action.",
        "Legal Services Authorities Act 1987, ss.19-22", ("Loan account statement", "Repayment proof", "A settlement proposal you can afford"),
        "owner", "action_plan", "Attend the Lok Adalat on the date fixed"),
    T.msme_samadhaan: NoticeRule(
        "MSME Facilitation Council reference (Samadhaan)", "bank",
        "notice from the Micro and Small Enterprises Facilitation Council (MSEFC) / MSME Samadhaan on a supplier's delayed-payment reference",
        "A micro or small supplier has filed a delayed-payment reference against you before the MSE Facilitation Council (s.18). The "
        "Council first tries conciliation, then arbitrates, and should decide within 90 days. Interest is compounded monthly at three "
        "times the RBI bank rate (s.16). Check whether the supplier was registered (Udyam) before your order.",
        "The Council can pass an award without you for the principal and compound interest -> to challenge it in court you must first "
        "deposit 75% of the award (s.19) -> the award is enforced like a court decree.",
        "MSMED Act 2006, ss.15-19", ("Purchase orders and invoices", "Payment records and ledger", "Supplier's Udyam certificate (check its date)", "Quality / rejection correspondence"),
        "lawyer", "letter", "File a written reply before the Council (MSME Samadhaan portal) and attend the conciliation", urgency_floor="high"),
    T.msme_delayed_payment: NoticeRule(
        "MSME delayed-payment notice", "bank",
        "a micro / small supplier's own demand letter claiming delayed payment and interest (MSMED Act s.15-16), not yet before the Council",
        "A buyer must pay a registered micro or small supplier by the agreed date, and in any case within 45 days of acceptance of the "
        "goods. Beyond that, compound interest at three times the RBI bank rate runs, and the supplier can approach the MSE "
        "Facilitation Council.",
        "Interest keeps adding up -> reference to the Facilitation Council (s.18) -> award -> to challenge it you must first deposit 75% (s.19).",
        "MSMED Act 2006, ss.15, 16, 18, 19", ("Purchase orders and invoices", "Goods receipt / acceptance records", "Payment records", "Supplier's Udyam certificate"),
        "lawyer", "letter", "Written reply", without_prejudice=True),
    T.legal_demand: NoticeRule(
        "Payment demand / recovery notice", "dispute",
        "a lawyer's or a party's demand for payment / recovery not covered by a more specific type",
        "A demand notice is not a court order. It is the step before a recovery suit, and the reply is read by the court later. "
        "Reply in writing within the time it states, and do not admit what you do not accept.",
        "Civil recovery suit for the amount with interest and costs (commercial disputes need pre-institution mediation first) -> decree -> attachment.",
        "Indian Contract Act 1872; Code of Civil Procedure 1908; Commercial Courts Act 2015, s.12A; Limitation Act 1963",
        ("Contract / purchase order", "Invoices and delivery records", "Ledger and payment proof", "Correspondence"),
        "lawyer", "letter", "Written reply by registered post / email", without_prejudice=True),

    # ------------------------------------------------------------------ courts, tribunals, police
    T.arbitration_invocation: NoticeRule(
        "Arbitration invocation notice (s.21)", "court",
        "notice invoking arbitration under s.21 Arbitration and Conciliation Act / proposing an arbitrator",
        "The other party has started arbitration under the contract's arbitration clause; proceedings legally begin when you receive this "
        "request (s.21). If it asks you to appoint or agree on an arbitrator and you do not within 30 days, the other side can ask the "
        "court or the designated institution to appoint one (s.11).",
        "The arbitrator is appointed without your choice -> the arbitration proceeds and an award can be passed without you (s.25) -> "
        "the award is enforced like a court decree (s.36).",
        "Arbitration and Conciliation Act 1996, ss.11, 21, 25, 36",
        ("The contract and its arbitration clause", "All correspondence on the dispute", "Invoices / performance records"),
        "lawyer_required", "letter", "Reply through a lawyer: nominate an arbitrator or object to the proposal",
        StatutoryWindow(30, "days", "receipt", "Arbitration and Conciliation Act 1996, s.11(4)-(5)",
                        "You have 30 days from receipt to appoint your arbitrator or agree on one; after that the other side can apply for an appointment.",
                        "appoint"),
        urgency_floor="high"),
    T.court_summons: NoticeRule(
        "Court summons (civil)", "court",
        "summons or notice from a civil court, commercial court or tribunal in a suit or case filed against the reader",
        "A civil court has issued summons in a suit filed against you. Appear (through a lawyer) on the date fixed and file your written "
        "statement within 30 days of service; the court can extend this up to 90 days, but in commercial suits 120 days is the absolute limit.",
        "The suit is heard without you (Order IX r.6) -> a decree is passed against you -> the decree is executed by attaching bank "
        "accounts or property (Order XXI).",
        "Code of Civil Procedure 1908, Order V, Order VIII r.1, Order IX r.6",
        ("The plaint and documents served with the summons", "Your records of the transaction", "Correspondence with the plaintiff"),
        "lawyer_required", "action_plan", "Engage an advocate; appear on the date fixed and file the written statement",
        StatutoryWindow(30, "days", "receipt", "Code of Civil Procedure 1908, Order VIII r.1",
                        "The written statement is due within 30 days of service of the summons.", "written_statement"),
        urgency_floor="critical"),
    T.court_summons_criminal: NoticeRule(
        "Court summons (criminal)", "court",
        "summons from a magistrate / criminal court to appear as an accused (e.g. a cheque-bounce complaint)",
        "A magistrate has taken cognisance of a criminal complaint (for example a cheque-bounce complaint under s.138 NI Act) and "
        "summons you as accused to appear on the date fixed. You can usually appear through counsel and seek bail or exemption.",
        "The court can issue a bailable and then a non-bailable warrant for your arrest, and in serious cases declare you a proclaimed "
        "person and attach your property.",
        "Bharatiya Nagarik Suraksha Sanhita 2023 (earlier CrPC 1973): summons and warrants; the offence section printed on the summons",
        ("The complaint copy served with the summons", "Records of the underlying transaction"),
        "lawyer_required", "action_plan", "Engage a criminal-law advocate and appear on the date fixed",
        urgency_floor="critical", verified=False, verify_note="BNSS section references are being verified; rely on the section printed on the summons."),
    T.police_summons: NoticeRule(
        "Police notice / summons", "court",
        "police notice to appear or to produce documents (BNSS s.35(3) / s.179 / s.94, earlier CrPC s.41A / s.160 / s.91)",
        "The police require you to appear for questioning (as a witness, or as a person against whom a complaint is made) or to produce "
        "documents. Check the section on the notice: under the BNSS 2023 a notice of appearance in place of arrest is s.35(3) (earlier "
        "CrPC s.41A) and a witness notice is s.179 (earlier CrPC s.160).",
        "Not complying with a notice of appearance can lead to arrest; ignoring a witness or document notice can lead to further "
        "coercive steps under the applicable procedure law.",
        "Summons under the applicable procedure law: Bharatiya Nagarik Suraksha Sanhita 2023 (earlier CrPC 1973)",
        ("The notice and any FIR / complaint number on it", "Documents the notice asks for"),
        "lawyer_required", "action_plan", "Speak to a criminal-law advocate before appearing; comply on the date fixed",
        urgency_floor="critical", verified=False, verify_note="BNSS section references are being verified; rely on the section printed on the notice."),

    # ------------------------------------------------------------------ disputes
    T.insurance_repudiation: NoticeRule(
        "Insurance claim rejection", "dispute",
        "insurer's letter rejecting (repudiating) or short-settling a claim",
        "The insurer has rejected your claim or settled it for less. Ask the insurer's grievance cell for a review in writing; if it is not "
        "resolved you can complain to the Insurance Ombudsman (claims up to Rs 50 lakh) or file a consumer complaint (within 2 years, CPA 2019 s.69).",
        "Nothing happens against you, but the claim can become time-barred: the policy may set a time limit to sue, and the Ombudsman "
        "and consumer-commission periods run from the rejection.",
        "Insurance Ombudsman Rules 2017; Consumer Protection Act 2019, s.69; IRDAI policyholder-protection regulations",
        ("Policy document and schedule", "Claim form and surveyor report", "Rejection letter", "Bills and proof of loss"),
        "owner", "letter", "Written grievance to the insurer, then the Ombudsman or consumer commission", verified=False,
        verify_note="Ombudsman time limits and monetary limits are being verified."),
    T.rera_notice: NoticeRule(
        "RERA notice", "dispute",
        "notice from a Real Estate Regulatory Authority or its adjudicating officer (complaint under RERA s.31)",
        "The Real Estate Regulatory Authority (or its adjudicating officer) has registered a complaint or started proceedings (s.31) and asks "
        "for your reply by the date or hearing fixed. It applies whether you are a promoter, an agent or an allottee.",
        "The Authority decides on the complainant's version: refund with interest, compensation and penalties -> failing to comply with an "
        "order can cost up to 5% of the project cost (s.63) -> orders are recovered as arrears of land revenue (s.40).",
        "Real Estate (Regulation and Development) Act 2016, ss.31, 35-40, 63, 71",
        ("Agreement for sale / allotment letter", "Payment receipts", "Project registration and approvals", "Possession correspondence"),
        "lawyer", "letter", "Written reply before the Authority and appearance on the hearing date"),
    T.consumer_complaint: NoticeRule(
        "Consumer complaint", "dispute",
        "notice of a complaint already filed before a District / State / National Consumer Commission",
        "A consumer complaint has been filed against you. You must file your written version within 30 days of receiving it; the "
        "Commission can allow up to 15 more days, and no more.",
        "The Commission decides on the complainant's version alone -> refund, compensation and costs -> non-compliance with its order "
        "is punishable (s.72).",
        "Consumer Protection Act 2019, ss.38, 72", ("Invoice and warranty", "Service / delivery records", "Correspondence with the customer"),
        "lawyer", "action_plan", "File the written version before the Commission (through an advocate or yourself)",
        StatutoryWindow(30, "days", "receipt", "Consumer Protection Act 2019, s.38(2)(a)",
                        "The written version is due within 30 days of receiving the complaint; the Commission may allow up to 15 more days.",
                        "written_statement"),
        urgency_floor="medium"),
    T.ip_notice: NoticeRule(
        "Trademark / IP notice", "dispute",
        "trademark / copyright / design cease-and-desist or infringement claim",
        "A cease-and-desist letter claims you use a mark, name or content that belongs to the sender. The law sets no reply time, but a "
        "court can grant a quick injunction, so a prompt written reply matters.",
        "Suit for an injunction (stopping your use), damages and an account of profits, sometimes with an interim order before you are heard.",
        "Trade Marks Act 1999, ss.29, 134, 135; Copyright Act 1957, ss.51, 55",
        ("Your trademark application / registration", "Proof of first use (invoices, ads, website archives)", "Design / content creation records"),
        "lawyer", "letter", "Reply through a lawyer", without_prejudice=True),
    T.defamation: NoticeRule(
        "Defamation notice", "dispute",
        "demand to take down statements and apologise for harming reputation",
        "The sender says something you said or published harmed their reputation, and usually demands a take-down and an apology. "
        "Do not repeat the statement and do not delete evidence before a lawyer has seen it.",
        "Civil suit for damages and an injunction, and a criminal complaint (BNS s.356).",
        "Bharatiya Nyaya Sanhita 2023, s.356 (earlier IPC ss.499-500); civil law of defamation",
        ("The statement / post as published, with date", "Proof that it is true or fair comment"),
        "lawyer", "letter", "Reply through a lawyer", without_prejudice=True),
    T.tenancy_notice: NoticeRule(
        "Rent / eviction notice", "dispute",
        "rent arrears, termination of tenancy or eviction notice by a landlord (or by a tenant)",
        "A landlord can end a monthly tenancy with a 15-day notice, but a tenant cannot be removed without a court order. Your state's "
        "rent-control law may give extra protection. Keep rent receipts and the rent agreement ready.",
        "Eviction suit and a claim for arrears of rent with interest and mesne profits -> decree -> eviction through the court.",
        "Transfer of Property Act 1882, ss.106, 111; the state Rent Control Act",
        ("Rent / leave-and-licence agreement", "Rent receipts and bank transfers", "Correspondence with the landlord"),
        "lawyer", "letter", "Written reply", without_prejudice=True),
    T.employment_dispute: NoticeRule(
        "Employee claim", "dispute",
        "claim by an employee or ex-employee (wages, dues, gratuity, wrongful termination), from them or their lawyer",
        "An employee's claim (wages, dues, gratuity, termination) is usually decided by a labour authority or court. Keep the "
        "appointment letter, attendance, salary records and the termination papers ready.",
        "Dispute before the labour authority or a claim petition -> order for dues with interest, reinstatement or compensation.",
        "Industrial Relations Code 2020 / Industrial Disputes Act 1947; Payment of Gratuity Act 1972; Code on Wages 2019",
        ("Appointment letter", "Attendance and salary records", "Full-and-final settlement", "Termination / resignation papers"),
        "lawyer", "letter", "Written reply", without_prejudice=True, verified=False, verify_note=_LABOUR_NOTE),
    T.contract_breach: NoticeRule(
        "Contract breach notice", "dispute",
        "allegation that a contract was breached (pure non-payment cases are legal_demand)",
        "A breach notice says you did not do what a contract required and asks you to fix it or pay compensation. Check the contract's "
        "notice, cure and arbitration clauses before replying.",
        "Termination of the contract -> claim for damages or the agreed penalty -> arbitration or a suit.",
        "Indian Contract Act 1872, ss.73, 74; Specific Relief Act 1963; Arbitration and Conciliation Act 1996",
        ("The contract", "Performance / delivery records", "Correspondence on the alleged breach"),
        "lawyer", "letter", "Written reply", without_prejudice=True),
    T.regulatory_other: NoticeRule(
        "Regulatory notice", "regulator", "any other government or regulator notice",
        "A government department or regulator asks you to explain, comply or attend. Reply as the notice directs, within the time it states.",
        "The authority can decide without your side, impose a penalty or take action under the law it cites.",
        "The Act and section printed on the notice", ("Licences and registrations the notice relates to", "Records the notice asks for"),
        "owner", "letter", "Reply as the notice directs"),
    T.other: NoticeRule(
        "Other notice", "other", "anything else",
        "A notice that does not fit a standard category. Read what it asks for and by when, and keep proof of any reply.",
        "Depends on the notice; check its own warning.", "As cited in the notice", ("The notice and related correspondence",),
        "owner", "letter", "Written reply"),
}


def rule_for(notice_type: T) -> NoticeRule:
    return CATALOG[notice_type]


def type_guide() -> str:
    """The classification list for the extraction prompt, generated so the prompt and the table never drift."""
    return "\n".join(f"  {t.value} = {r.classify};" for t, r in CATALOG.items())
