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
            checks.append(Check("pan", "PAN", FAIL, "The PAN you entered is not a valid PAN format (AAAAA9999A)."))
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
