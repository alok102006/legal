"""What an Indian SME actually signs: one profile per contract type.

Each profile says who the SME usually is in that deal (so the review is done from the right side when the
organisation's name does not appear in the contract), the checklist the reviewer must walk topic by topic, and
which deterministic rules make sense for it. Keeping this in one table means a new type is one entry, and the
prompts, the rules and the UI label can never disagree about what a type is.
"""
from dataclasses import dataclass
from typing import Dict, List, Tuple

from app.workspaces.contract_intelligence.engine.schemas import ContractType as T


@dataclass(frozen=True)
class TypeProfile:
    label: str
    client_default: str                       # who the SME usually is, in words the model understands
    client_roles: Tuple[str, ...]             # role words that identify that party in the "parties" list
    checklist: Tuple[str, ...]                # topics the reviewer walks one by one
    liability_cap_expected: bool = False      # a liability cap is a normal protection in this deal
    stamp: str = ""                           # "" = do not check; "low"/"medium" = severity if stamp duty unmentioned
    msme_supply: bool = False                 # goods/services bought from a supplier (MSMED 45-day rule)
    taxable_supply: bool = False              # GST normally applies to the consideration
    recurring_fee: bool = False               # rent/fee that may escalate year on year
    lending: bool = False                     # loan/credit/guarantee: interest thresholds differ


_COMMON_TAIL = (
    "liability cap and indemnity", "termination rights of each side and notice", "dispute resolution, seat and courts",
    "assignment without consent", "stamp duty and execution",
)

PROFILES: Dict[T, TypeProfile] = {
    T.supply: TypeProfile(
        "Supply agreement", "the buyer purchasing the goods", ("buyer", "purchaser", "customer"),
        ("delivery timelines and penalties for delay", "inspection, rejection and replacement", "warranty",
         "price variation and who may change prices", "payment days and late-payment interest (MSMED 45 days)",
         "when title and risk pass", "minimum quantity commitments", "GST on the price", "force majeure", *_COMMON_TAIL),
        liability_cap_expected=True, stamp="low", msme_supply=True, taxable_supply=True),
    T.purchase_order: TypeProfile(
        "Purchase order terms", "the supplier accepting the purchase order (the SME selling to a larger buyer)",
        ("supplier", "vendor", "seller"),
        ("buyer's right to cancel or reschedule the order", "liquidated damages for late delivery",
         "acceptance, rejection and return of goods at supplier's cost", "payment days and MSMED 45-day limit",
         "price firmness and GST", "warranty period and back-to-back obligations", "set-off and deductions from invoices",
         "unlimited indemnity", "governing terms (buyer's standard terms overriding the quotation)", "dispute resolution"),
        liability_cap_expected=True, msme_supply=True, taxable_supply=True),
    T.service: TypeProfile(
        "Service agreement", "the business receiving and paying for the services", ("client", "customer", "company", "recipient"),
        ("scope creep and change requests", "service levels (SLA) and penalties", "acceptance criteria",
         "milestone payments and payment days", "IP ownership of deliverables", "subcontracting", "confidentiality",
         "exit assistance", "GST on fees", *_COMMON_TAIL),
        liability_cap_expected=True, stamp="low", msme_supply=True, taxable_supply=True),
    T.works_construction: TypeProfile(
        "Works / construction contract", "the owner commissioning and paying for the works", ("owner", "employer", "client"),
        ("scope, drawings and variations", "price escalation and extra items", "mobilisation advance and its security",
         "retention money and its release", "liquidated damages for delay and their cap", "defect liability period",
         "measurement and certification of bills", "performance bank guarantee", "insurance and safety (labour laws, BOCW)",
         "GST and works contract tax", *_COMMON_TAIL),
        liability_cap_expected=True, stamp="low", msme_supply=True, taxable_supply=True),
    T.agency_commission: TypeProfile(
        "Agency / commission agreement", "the agent earning commission", ("agent", "commission agent", "sales agent"),
        ("commission rate and when it is earned", "commission on orders after termination", "exclusivity and territory",
         "targets and consequences of missing them", "authority to bind the principal", "expenses and deductions",
         "post-termination non-compete (s.27)", "GST on commission", *_COMMON_TAIL),
        liability_cap_expected=True, stamp="low", taxable_supply=True),
    T.consultancy: TypeProfile(
        "Consultancy / freelancer agreement", "the business engaging the consultant or freelancer", ("client", "company"),
        ("deliverables and acceptance", "fees, milestones and expenses", "IP assignment of work product",
         "confidentiality", "non-solicit and non-compete", "independent contractor status (not an employee)",
         "TDS and GST", "termination and handover", *_COMMON_TAIL),
        liability_cap_expected=True, stamp="low", msme_supply=True, taxable_supply=True),
    T.distribution: TypeProfile(
        "Distribution agreement", "the distributor", ("distributor", "stockist", "reseller"),
        ("exclusivity and territory", "sales targets / minimum purchase and shortfall penalties",
         "price list changes by the company", "credit terms and security deposit", "stock return and buy-back on exit",
         "termination for convenience and compensation", "post-termination non-compete (s.27)", "branding and schemes cost",
         "GST and invoicing", *_COMMON_TAIL),
        liability_cap_expected=True, stamp="low", taxable_supply=True),
    T.dealership: TypeProfile(
        "Dealership agreement", "the dealer", ("dealer", "retailer", "sub-dealer"),
        ("dealer margin and incentive schemes", "targets and penalties", "security deposit and its refund",
         "showroom/infrastructure investment the dealer must make", "unilateral price and policy changes",
         "termination by the company and buy-back of stock/spares", "territory and exclusivity", "warranty claims handling",
         *_COMMON_TAIL),
        liability_cap_expected=True, stamp="low", taxable_supply=True),
    T.franchise: TypeProfile(
        "Franchise agreement", "the franchisee", ("franchisee",),
        ("franchise fee, royalty and hidden charges", "territory and exclusivity", "renewal and transfer rights",
         "mandatory supplies and price control", "training and support promises", "fit-out investment and lock-in",
         "post-termination non-compete (s.27)", "exit costs and stock buy-back", "brand and IP use", *_COMMON_TAIL),
        liability_cap_expected=True, stamp="low", taxable_supply=True),
    T.job_work: TypeProfile(
        "Job-work agreement", "the job worker processing the principal's material", ("job worker", "processor", "contractor"),
        ("ownership and insurance of the principal's material", "wastage/scrap allowance and shortages",
         "quality rejection and who bears it", "job charges and payment days (MSMED)",
         "GST job-work challans and return of goods within time (CGST s.143)", "minimum volume commitments",
         "liability for loss of material", *_COMMON_TAIL),
        liability_cap_expected=True, stamp="low", taxable_supply=True),
    T.logistics: TypeProfile(
        "Logistics / transport contract", "the shipper (consignor) using the transporter", ("shipper", "consignor", "customer", "client"),
        ("liability for loss, damage and delay of goods (Carriage by Road Act)", "limits of carrier liability per kg/consignment",
         "transit insurance", "freight rates, fuel surcharge and revisions", "detention and demurrage charges",
         "lien on goods for unpaid dues", "proof of delivery and claims time limit", "GST (RCM on GTA)", *_COMMON_TAIL),
        liability_cap_expected=True, msme_supply=True, taxable_supply=True),
    T.warehousing: TypeProfile(
        "Warehousing agreement", "the depositor storing goods", ("depositor", "customer", "client"),
        ("storage charges, minimum space commitment and escalation", "liability for loss, theft, fire and pilferage",
         "insurance of stored goods", "warehouse lien on goods for dues", "inventory reconciliation and shrinkage",
         "access and release of goods", "lock-in and exit", "GST", *_COMMON_TAIL),
        liability_cap_expected=True, stamp="low", msme_supply=True, taxable_supply=True, recurring_fee=True),
    T.equipment_hire: TypeProfile(
        "Equipment hire agreement", "the hirer taking the equipment on hire", ("hirer", "lessee", "customer"),
        ("hire charges, minimum hire period and escalation", "breakdown, maintenance and replacement responsibility",
         "damage and loss liability", "insurance", "security deposit and refund", "repossession rights", "GST",
         *_COMMON_TAIL),
        liability_cap_expected=True, stamp="low", msme_supply=True, taxable_supply=True, recurring_fee=True),
    T.lease: TypeProfile(
        "Lease / leave and licence", "the tenant / licensee / lessee", ("tenant", "licensee", "lessee"),
        ("lock-in period and exit penalty", "rent escalation", "security deposit amount, interest and refund timeline",
         "repairs and maintenance (structural vs minor)", "subletting and change of control",
         "termination notice by each side", "eviction, re-entry and overstay charges", "default interest",
         "stamp duty and registration (over 11 months)", "renewal terms", "who pays GST, property tax and society charges"),
        stamp="medium", taxable_supply=True, recurring_fee=True),
    T.employment: TypeProfile(
        "Employment / offer letter", "the employer (the SME issuing the letter)", ("employer", "company"),
        ("notice period and garden leave", "non-compete and non-solicit after exit (s.27)",
         "training bonds and cost recovery", "IP assignment", "probation", "termination for cause",
         "retention of original certificates", "variable pay, bonus and clawback", "statutory benefits (PF, ESI, gratuity)",
         "confidentiality", "dispute resolution"),
        ),
    T.nda: TypeProfile(
        "Non-disclosure agreement", "the receiving party (the SME receiving confidential information)",
        ("recipient", "receiving party"),
        ("definition of confidential information (too broad?)", "duration of the obligation", "one-way vs mutual",
         "exclusions (public domain, already known)", "return/destruction", "permitted disclosures",
         "IP or feedback assignment hidden in the NDA", "non-solicit or non-compete hidden in the NDA",
         "remedies, penalties and indemnity", "jurisdiction and seat")),
    T.loan_guarantee: TypeProfile(
        "Loan / hypothecation agreement", "the borrower", ("borrower", "hirer", "obligor"),
        ("interest rate, reset and penal interest", "processing, prepayment and foreclosure charges",
         "personal/director guarantees", "acceleration and cross-default", "security, hypothecation and cheques",
         "auto-debit mandates", "lender's right to change terms", "repossession without notice",
         "release of original documents after repayment", "lender-appointed arbitrator", "stamp duty"),
        stamp="medium", lending=True),
    T.vehicle_loan: TypeProfile(
        "Vehicle loan", "the borrower", ("borrower", "hirer"),
        ("interest rate (flat vs reducing) and penal interest", "foreclosure charges", "hypothecation on RC and release",
         "repossession process and notice", "insurance tie-ins", "auto-debit (NACH) mandate", "post-dated or blank cheques",
         "guarantor obligations", "lender-appointed arbitrator"),
        stamp="low", lending=True),
    T.credit_facility: TypeProfile(
        "Overdraft / credit facility", "the borrower", ("borrower", "customer"),
        ("sanctioned limit and the bank's right to cancel or reduce it", "interest, renewal and penal charges",
         "drawing power and stock statements", "collateral, personal guarantees and cross-collateral",
         "repayment on demand", "auto-debit and set-off of other accounts", "covenants and events of default",
         "release of documents after closure", "stamp duty"),
        stamp="medium", lending=True),
    T.personal_guarantee: TypeProfile(
        "Personal guarantee", "the guarantor (usually the SME's director, partner or proprietor)", ("guarantor", "surety"),
        ("amount and whether the guarantee is unlimited or continuing", "co-extensive liability and waiver of surety rights",
         "revocation and release", "demand and payment timeline", "personal assets at risk (IBC personal insolvency)",
         "consent to variations without notice", "dispute resolution"),
        stamp="medium", lending=True),
    T.mou_loi: TypeProfile(
        "MoU / letter of intent", "the SME party", (),
        ("which clauses are binding vs non-binding", "exclusivity and no-shop period", "costs and break fee",
         "confidentiality", "timeline to sign the definitive agreement", "termination of the MoU", "dispute resolution")),
    T.shareholder_agreement: TypeProfile(
        "Shareholder / founder agreement", "the founders / promoter shareholders (not the investor)",
        ("founder", "promoter", "promoters"),
        ("vesting and leaver provisions", "drag-along and tag-along", "anti-dilution", "investor veto / reserved matters",
         "board control", "liquidation preference", "exit obligations and buy-back put options on promoters",
         "founder non-compete (s.27)", "transfer restrictions and ROFR", "dispute resolution", "stamp duty"),
        stamp="low"),
    T.partnership: TypeProfile(
        "Partnership deed / joint venture", "the partner signing (the SME owner)", ("partner",),
        ("capital contribution and profit/loss sharing", "authority to bind the firm", "unlimited personal liability",
         "exit, retirement and valuation of a partner's share", "deadlock and dissolution", "non-compete",
         "registration of the firm (Partnership Act s.69)", "dispute resolution"),
        liability_cap_expected=True, stamp="low"),
    T.security_manpower: TypeProfile(
        "Security / manpower contract", "the principal employer receiving the security or manpower services",
        ("client", "principal employer", "company"),
        ("contractor's compliance with wages, PF, ESI and bonus (principal employer liability)",
         "CLRA licence and registers", "replacement and absence deductions", "rates, revisions and minimum wage escalation",
         "liability for theft or loss by deployed staff", "indemnity", "GST", "termination notice"),
        liability_cap_expected=True, stamp="low", msme_supply=True, taxable_supply=True, recurring_fee=True),
    T.amc_maintenance: TypeProfile(
        "AMC / maintenance contract", "the customer receiving maintenance", ("customer", "client"),
        ("scope: what is covered vs chargeable", "response and resolution times", "spare parts pricing",
         "uptime commitments and penalties", "renewal and price escalation", "advance payment and refund on exit",
         "GST", "termination"),
        liability_cap_expected=True, stamp="low", msme_supply=True, taxable_supply=True, recurring_fee=True),
    T.advertising_marketing: TypeProfile(
        "Advertising / marketing agreement", "the advertiser buying the services", ("advertiser", "client", "brand"),
        ("deliverables and performance metrics", "advance payments and refund", "ownership of creatives and data",
         "compliance with advertising codes (ASCI, Consumer Protection Act)", "influencer disclosures",
         "media cost pass-through", "GST", "termination"),
        liability_cap_expected=True, stamp="low", msme_supply=True, taxable_supply=True),
    T.ecommerce_marketplace: TypeProfile(
        "E-commerce marketplace terms", "the seller listing on the marketplace", ("seller", "merchant", "vendor"),
        ("commission, fees and unilateral changes", "payment settlement cycle and holdbacks", "returns and chargebacks",
         "penalties and account suspension", "pricing control and discounts", "liability and indemnity",
         "TCS under GST (s.52) and TDS (s.194-O)", "data use", "termination and delisting", "dispute resolution"),
        liability_cap_expected=True, taxable_supply=True),
    T.software_license: TypeProfile(
        "Software / SaaS agreement", "the customer / subscriber", ("customer", "subscriber", "licensee", "client"),
        ("licence scope and restrictions", "term and auto-renewal", "price increases on renewal",
         "data ownership, security, backups and DPDP obligations", "SLA and uptime credits",
         "suspension rights", "IP indemnity", "termination and data return", "GST", *_COMMON_TAIL),
        liability_cap_expected=True, taxable_supply=True, recurring_fee=True),
    T.other: TypeProfile(
        "Contract", "the smaller business in this deal (the SME)", (),
        ("payment and interest", "term and termination", "liability and indemnity", "IP", "confidentiality",
         "dispute resolution", "assignment"),
        liability_cap_expected=True),
}


def profile(contract_type) -> TypeProfile:
    """Profile for a ContractType or its string value; unknown values fall back to 'other'."""
    try:
        return PROFILES[T(contract_type)]
    except ValueError:
        return PROFILES[T.other]


def checklist_text(contract_type) -> str:
    return "; ".join(profile(contract_type).checklist) + "."


def type_guide() -> str:
    """One line per type, used in the facts prompt so classification and client defaults stay in sync."""
    return "\n".join(f"  {t.value}: {p.label} (client is usually {p.client_default})" for t, p in PROFILES.items())


def all_checklist_topics(contract_type) -> List[str]:
    return list(profile(contract_type).checklist)
