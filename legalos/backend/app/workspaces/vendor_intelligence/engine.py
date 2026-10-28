"""Vendor assessment: deterministic checks with reasons (no invented data, no black-box score).

Offline checks need no API: GSTIN structure + checksum, PAN structure, name-vs-PAN-holder consistency,
state consistency, Udyam format. A registry lookup (live API, or clearly labelled sample records in demo mode)
adds status/registration-age/filing checks. Verdict: cancelled/suspended or invalid number -> high ("Do not pay");
name/entity mismatch, not filing, registry has no record -> medium ("Check before paying"); all good and live
active -> low ("Safe to proceed"); offline only -> unverified ("Looks valid, not verified live"). A vendor that was NOT looked up in a registry is never called "low risk":
the best it can be is "unverified".
"""
import dataclasses
import re
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Dict, List, Optional

from rapidfuzz import fuzz

from app.shared.india import identifiers as ids

PASS, WARN, FAIL, UNKNOWN = "pass", "warn", "fail", "unknown"


@dataclass
class Check:
    key: str
    label: str
    status: str            # pass | warn | fail | unknown
    detail: str


@dataclass
class RegistryResult:
    source: str            # live | sample | unavailable
    message: str = ""
    legal_name: Optional[str] = None
    trade_name: Optional[str] = None
    status: Optional[str] = None            # Active | Cancelled | Suspended | Inactive
    registration_date: Optional[str] = None  # ISO
    constitution: Optional[str] = None
    state: Optional[str] = None
    note: Optional[str] = None               # e.g. filing behaviour (sample records)
    msme_category: Optional[str] = None
    provider: Optional[str] = None           # sandbox | generic (live) | sample
    error_kind: Optional[str] = None         # not_connected | no_gstin | invalid_gstin | auth | quota | unavailable | not_found
    filing_status: Optional[str] = None      # as reported by the provider, when it gives one
    taxpayer_type: Optional[str] = None      # Regular | Composition ...
    cancellation_date: Optional[str] = None  # ISO
    fetched_at: Optional[str] = None         # when the registry was actually asked (ISO); older than "now" for cached results
    cached: bool = False                     # True when served from the 24 h lookup cache (no paid call was made)


@dataclass
class Assessment:
    checks: List[Check]
    risk_level: str                      # high | medium | low | unverified
    summary: str
    derived: Dict[str, Any] = field(default_factory=dict)
    reasons: List[str] = field(default_factory=list)


_COMPANY = re.compile(r"\b(pvt\.?|private)\s*(ltd\.?|limited)\b|\blimited\b|\bltd\.?\b", re.I)
_BAD_FILING = re.compile(r"not\s*fil|non[-\s]?fil|default|late|irregular|pending|delay|overdue", re.I)
_GOOD_FILING = re.compile(r"regular|up[-\s]?to[-\s]?date|compliant|filed|timely", re.I)
_LLP = re.compile(r"\bllp\b|\blimited liability partnership\b", re.I)


def _expected_holder(name: str) -> Optional[str]:
    """PAN 4th letter implied by the legal form written in the name, when it is unambiguous."""
    if _LLP.search(name):
        return "F"
    if _COMPANY.search(name):
        return "C"
    return None


def _age_years(iso: Optional[str], today: date) -> Optional[float]:
    if not iso:
        return None
    try:
        return (today - date.fromisoformat(iso)).days / 365.25
    except ValueError:
        return None


def assess(
    name: str,
    gstin: Optional[str],
    pan: Optional[str] = None,
    state_code: Optional[str] = None,
    udyam_number: Optional[str] = None,
    msme_category: Optional[str] = None,
    registry: Optional[RegistryResult] = None,
    today: Optional[date] = None,
) -> Assessment:
    today = today or date.today()
    checks: List[Check] = []
    derived: Dict[str, Any] = {}
    info = None

    # ---------------------------------------------------------------- GSTIN
    if not (gstin or "").strip():
        if (pan or "").strip() or (udyam_number or "").strip():
            checks.append(Check("gstin", "GSTIN", UNKNOWN,
                                "No GSTIN given, so GST registration was not checked. Ask for the GSTIN to confirm it."))
        else:
            checks.append(Check("gstin", "GSTIN", WARN,
                                "No GSTIN given. You generally cannot claim input tax credit on purchases from an unregistered supplier."))
    else:
        info = ids.decode_gstin(gstin)
        if not info.valid:
            checks.append(Check("gstin", "GSTIN format and check digit", FAIL, info.error or "Invalid GSTIN."))
        else:
            checks.append(Check("gstin", "GSTIN format and check digit", PASS,
                                f"Structure and check digit are valid ({info.state_name}, PAN {info.pan})."))
            derived.update(pan=info.pan, state_code=info.state_code, state_name=info.state_name, holder_type=info.holder_type)

    # ---------------------------------------------------------------- PAN
    holder_letter: Optional[str] = info.pan[3] if (info and info.valid) else None
    if pan and pan.strip():
        if not ids.validate_pan(pan):
            checks.append(Check("pan", "PAN", FAIL, "The PAN you entered is not valid. " + (ids.decode_pan(pan).error or "")))
        elif info and info.valid and ids.normalize(pan) != info.pan:
            checks.append(Check("pan", "PAN matches GSTIN", FAIL,
                                f"The PAN you entered ({ids.normalize(pan)}) is different from the PAN inside the GSTIN ({info.pan})."))
        else:
            p = ids.normalize(pan)
            holder = ids.PAN_HOLDER_TYPES.get(p[3])
            checks.append(Check("pan", "PAN", PASS, f"PAN format is valid ({holder})" + (" and matches the GSTIN." if info and info.valid else ".")))
            derived.setdefault("pan", p)
            derived.setdefault("holder_type", holder)
            holder_letter = holder_letter or p[3]

    # ---------------------------------------------------------------- legal form vs PAN holder type
    entity_name = name.strip() or ((registry.legal_name or "").strip() if registry and registry.source != "unavailable" else "")
    if holder_letter and entity_name:
        expected = _expected_holder(entity_name)
        holder_txt = ids.PAN_HOLDER_TYPES.get(holder_letter, holder_letter)
        if expected and expected != holder_letter:
            checks.append(Check("entity", "Business type matches the name", WARN,
                                f"The name '{entity_name}' says a {'company' if expected == 'C' else 'firm/LLP'}, but the PAN is registered to a "
                                f"{holder_txt}. A genuine registration normally matches, so confirm who you are paying."))
        elif expected:
            checks.append(Check("entity", "Business type matches the name", PASS, f"The name and the PAN holder type ({holder_txt}) agree."))
        else:
            checks.append(Check("entity", "Business type", PASS, f"Registered as: {holder_txt}."))
    elif holder_letter:
        checks.append(Check("entity", "Business type", PASS, f"The PAN says this is a {ids.PAN_HOLDER_TYPES.get(holder_letter, holder_letter)}."))

    # ---------------------------------------------------------------- state
    if info and info.valid and state_code:
        if state_code != info.state_code:
            checks.append(Check("state", "State", WARN,
                                f"You said the vendor is in {ids.STATE_CODES.get(state_code, state_code)}, but the GSTIN is registered in {info.state_name}. "
                                "This affects whether CGST+SGST or IGST applies."))
        else:
            checks.append(Check("state", "State", PASS, f"GSTIN state matches ({info.state_name})."))

    # ---------------------------------------------------------------- Udyam / MSME
    if udyam_number and udyam_number.strip():
        if ids.validate_udyam(udyam_number):
            checks.append(Check("udyam", "Udyam (MSME) number", PASS, "Format is valid. It has not been confirmed on the Udyam portal, so do not rely on the MSME category yet."))
        else:
            checks.append(Check("udyam", "Udyam (MSME) number", WARN, "This does not look like a valid Udyam number (expected UDYAM-XX-00-0000000)."))

    # ---------------------------------------------------------------- registry
    if registry is None or registry.source == "unavailable":
        kind = registry.error_kind if registry else "not_connected"
        msg = registry.message if registry and registry.message else "Not checked: the live GST registry is not connected."
        if kind == "not_found":
            checks.append(Check("registry", "GST registry record", WARN,
                                "The GST registry has no record of this GSTIN. The number is well-formed but may not exist - confirm with the supplier before paying."))
        else:
            tail = (" Offline checks above only prove the number is well-formed, not that it is active."
                    if kind in ("not_connected", "no_gstin", "invalid_gstin", None) else " Offline checks above are still valid; try the registry check again.")
            checks.append(Check("registry", "GST registry status", UNKNOWN, msg + tail))
    else:
        tag = "Sample record (demo data)" if registry.source == "sample" else "Live GST registry"
        st = (registry.status or "").strip().lower()
        if st == "active":
            checks.append(Check("registry", f"Registration status - {tag}", PASS, "Registration is active."))
        elif st in ("cancelled", "suspended", "inactive"):
            extra = f" (cancelled on {registry.cancellation_date})" if registry.cancellation_date else ""
            checks.append(Check("registry", f"Registration status - {tag}", FAIL,
                                f"Registration is {st}{extra}. Input tax credit on purchases from this supplier can be denied, and the business may have shut down."))
        else:
            checks.append(Check("registry", f"Registration status - {tag}", UNKNOWN, f"Status returned: {registry.status or 'unknown'}."))
        if registry.legal_name and name.strip():
            score = fuzz.token_set_ratio(name.lower(), registry.legal_name.lower())
            trade = fuzz.token_set_ratio(name.lower(), registry.trade_name.lower()) if registry.trade_name else 0
            if max(score, trade) >= 70:
                checks.append(Check("name", "Name matches the registry", PASS, f"Registered as '{registry.legal_name}'."))
            else:
                checks.append(Check("name", "Name matches the registry", WARN,
                                    f"You entered '{name.strip()}' but the registry shows '{registry.legal_name}'. Confirm you are paying the right entity."))
        age = _age_years(registry.registration_date, today)
        if age is not None and age < 1:
            checks.append(Check("age", "Registration age", WARN, f"Registered only {age:.1f} years ago. New registrations carry more risk; consider advance-payment limits."))
        elif age is not None:
            checks.append(Check("age", "Registration age", PASS, f"Registered for about {age:.0f} years."))
        inactive = st in ("cancelled", "suspended", "inactive")
        if registry.filing_status and not inactive:
            fs = registry.filing_status
            if _BAD_FILING.search(fs):
                checks.append(Check("filing", "Return filing", WARN, f"The registry reports the filing status as '{fs}'. Unfiled returns put your input tax credit at risk."))
            elif _GOOD_FILING.search(fs):
                checks.append(Check("filing", "Return filing", PASS, f"The registry reports the filing status as '{fs}'."))
            else:
                checks.append(Check("filing", "Return filing", UNKNOWN, f"Filing status reported: '{fs}'."))
        if registry.note and not inactive:     # already covered by the status check when inactive
            checks.append(Check("behaviour", "Compliance behaviour", WARN, registry.note))
        derived["registry_status"] = registry.status
        if registry.msme_category and not msme_category:
            derived["msme_category"] = registry.msme_category

    # ---------------------------------------------------------------- PAN 5th letter vs the name (warning only)
    pan_value = derived.get("pan")
    if pan_value and holder_letter and holder_letter != "P":      # sole proprietors trade under names unrelated to their own
        names = [n for n in (name, registry.legal_name if registry else None, registry.trade_name if registry else None) if n and n.strip()]
        warnings = [ids.pan_name_warning(pan_value, n) for n in names]
        if names and all(warnings):
            checks.append(Check("pan_name", "PAN matches the name", WARN, warnings[0] or ""))

    # ---------------------------------------------------------------- overall
    fails = [c for c in checks if c.status == FAIL]
    warns = [c for c in checks if c.status == WARN]
    registry_ok = any(c.key == "registry" and c.status == PASS for c in checks)
    if fails:
        risk, summary = "high", f"Do not pay yet. {fails[0].detail}"
    elif warns:
        risk, summary = "medium", f"Proceed with care. {warns[0].detail}"
    elif registry_ok:
        risk, summary = "low", "No problems found in the checks we could run."
    else:
        risk, summary = "unverified", "Nothing looks wrong, but the registration has not been confirmed with the GST registry."
    reasons = reasons_for([dataclasses.asdict(c) for c in checks], risk)
    return Assessment(checks=checks, risk_level=risk, summary=summary, derived=derived, reasons=reasons)


def reasons_for(checks: List[Dict[str, Any]], risk: str) -> List[str]:
    """The plain-English reasons that drove the verdict, derived from the stored checks (works for saved suppliers too)."""
    def by(status: str) -> List[str]:
        return [c["detail"] for c in checks if c.get("status") == status]

    if risk == "high":
        return by(FAIL) + by(WARN)
    if risk == "medium":
        return by(WARN)
    if risk == "low":
        good = [c["detail"] for c in checks if c.get("status") == PASS and c.get("key") in ("registry", "name", "age", "filing", "entity")]
        return good[:4] or by(PASS)[:3]
    return by(PASS)[:2] + by(UNKNOWN)[:1]


# ----------------------------------------------------------------------------- other identifiers (check desk only)

_NO_REGISTRY = {
    "tan": "A TAN proves the business is registered to deduct tax; confirm it on the Income Tax e-filing portal.",
    "cin": "Confirm the company is active and its name on the MCA portal (company master data).",
    "llpin": "Confirm the LLP is active on the MCA portal (LLP master data).",
    "ifsc": "Confirm the branch details on the RBI / bank website before sending money.",
    "iec": "Confirm the IEC on the DGFT portal.",
    "fssai": "Confirm the licence and its expiry on the FSSAI FoSCoS portal.",
    "esic": "Confirm the code on the ESIC employer portal.",
    "pf": "Confirm the establishment on the EPFO employer portal.",
}
_LABELS = {"tan": "TAN", "cin": "CIN", "llpin": "LLPIN", "ifsc": "IFSC", "iec": "IEC", "fssai": "FSSAI licence number",
           "esic": "ESIC employer code", "pf": "PF establishment code"}


def _describe(info: "ids.IdInfo") -> str:
    d = info.details
    if info.kind == "cin":
        bits = [d.get("listing_status"), d.get("company_type"), f"registered in {d['state_name']}" if d.get("state_name") else None,
                f"incorporated {d['incorporation_year']}"]
        return "Format is valid: " + ", ".join(b for b in bits if b) + "."
    if info.kind == "ifsc":
        bank = d.get("bank_name") or f"bank code {d['bank_code']}"
        return f"Format is valid: {bank}, branch code {d['branch_code']}."
    if info.kind == "iec" and d.get("pan_based"):
        return "Format is valid (PAN-based IEC)."
    if info.kind == "pf":
        return f"Format is valid (region {d['region_code']}, office {d['office_code']}, establishment {d['establishment_number']})."
    return "Format is valid."


def assess_identifier(kind: str, value: str, name: Optional[str] = None, today: Optional[date] = None) -> Assessment:
    """Offline check of a CIN, TAN, LLPIN, IFSC, IEC, FSSAI, ESIC or PF number. These have no registry we can query, so
    the best outcome is "unverified": the number is well-formed and the summary says where to confirm it."""
    info = ids.decode(kind, value, name=name, today=today)
    label = _LABELS.get(kind, kind.upper())
    if not info.valid:
        checks = [Check("format", f"{label} format", FAIL, info.error or f"Invalid {label}.")]
        return Assessment(checks=checks, risk_level="high", summary=f"Do not pay yet. {checks[0].detail}",
                          reasons=[checks[0].detail])
    checks = [Check("format", f"{label} format", PASS, _describe(info))]
    checks += [Check("format_note", f"{label} detail", WARN, w) for w in info.warnings]
    derived = {k: v for k, v in info.details.items() if v is not None}
    if info.warnings:
        return Assessment(checks=checks, risk_level="medium", summary=f"Proceed with care. {info.warnings[0]}",
                          derived=derived, reasons=list(info.warnings))
    return Assessment(checks=checks, risk_level="unverified",
                      summary=f"The {label} is well-formed, but it has not been confirmed with the issuing authority. {_NO_REGISTRY.get(kind, '')}".strip(),
                      derived=derived, reasons=[checks[0].detail])


# ----------------------------------------------------------------------------- the rules, in plain English

RISK_RULES: Dict[str, Any] = {
    "levels": [
        {"level": "high", "label": "Do not pay yet",
         "when": ["Any check FAILS: a number has a typo (checksum), a PAN does not match the one inside the GSTIN, or the "
                  "registry says the registration is cancelled, suspended or inactive."]},
        {"level": "medium", "label": "Proceed with care",
         "when": ["No check fails, but at least one WARNS: no GSTIN given, name or business type differs from the "
                  "registry or the PAN, state differs, registered less than a year ago, returns reported as not filed, "
                  "or the registry has no record of the number."]},
        {"level": "low", "label": "Safe to proceed",
         "when": ["Nothing failed or warned AND the live GST registry confirmed an active registration. "
                  "Sample (demo) records can show this too, and are labelled as samples."]},
        {"level": "unverified", "label": "Looks valid, not verified live",
         "when": ["Nothing failed or warned, but no registry confirmed the registration (not connected, lookup failed, or "
                  "the number type has no registry). A supplier that was never looked up is never called low risk."]},
    ],
    "checks": [
        {"key": "gstin", "label": "GSTIN format and check digit", "fails_when": "wrong length/format, unknown state code, impossible PAN holder type or the check digit does not match", "warns_when": "no GSTIN given"},
        {"key": "pan", "label": "PAN", "fails_when": "invalid PAN format, or it differs from the PAN inside the GSTIN", "warns_when": ""},
        {"key": "entity", "label": "Business type matches the name", "fails_when": "", "warns_when": "the name says Pvt Ltd / LLP but the PAN holder type is something else"},
        {"key": "state", "label": "State", "fails_when": "", "warns_when": "the state you gave differs from the GSTIN state (affects CGST+SGST vs IGST)"},
        {"key": "udyam", "label": "Udyam (MSME) number", "fails_when": "", "warns_when": "not a valid UDYAM-XX-00-0000000 number or an unknown state code"},
        {"key": "registry", "label": "GST registry status", "fails_when": "registration is cancelled, suspended or inactive", "warns_when": "the registry has no record of the GSTIN"},
        {"key": "name", "label": "Name matches the registry", "fails_when": "", "warns_when": "the name you gave is not similar (token match below 70%) to the registered legal or trade name"},
        {"key": "age", "label": "Registration age", "fails_when": "", "warns_when": "registered less than a year ago"},
        {"key": "filing", "label": "Return filing", "fails_when": "", "warns_when": "the registry reports non-filing, late or irregular filing"},
        {"key": "behaviour", "label": "Compliance behaviour", "fails_when": "", "warns_when": "the registry record carries a compliance note (demo samples only)"},
        {"key": "pan_name", "label": "PAN matches the name", "fails_when": "", "warns_when": "for non-individual PANs, the 5th letter is not the first letter of the name (warning only: renames and trade names are common)"},
        {"key": "format", "label": "Number format (CIN, TAN, LLPIN, IFSC, IEC, FSSAI, ESIC, PF)", "fails_when": "wrong length or pattern, impossible year or checks specific to that number", "warns_when": ""},
        {"key": "format_note", "label": "Number detail", "fails_when": "", "warns_when": "an unrecognised state code or company class, or a listed company with a private-company class"},
    ],
    "notes": [
        "These are deterministic rules, not a score: every verdict lists the checks behind it.",
        "A passing format or checksum only shows the number is well-formed; only a live registry shows it is active.",
        "Live registry results are kept for 24 hours per GSTIN to avoid repeated paid lookups; the check time is shown.",
    ],
}
