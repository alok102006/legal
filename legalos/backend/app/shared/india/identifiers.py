"""Offline validators/decoders for Indian business identifiers.

These need no API and no network: they catch typos and fake numbers instantly and extract
useful facts (state, PAN, holder type). A passing checksum or format does NOT prove the registration
exists or is active - that needs a live registry lookup. Every function is pure.

Covered: GSTIN (with checksum), PAN, TAN, Udyam, CIN, LLPIN, IFSC, IEC, FSSAI licence, ESIC and PF numbers.
`identify` guesses which one a pasted string is; `decode(kind, value)` runs the matching decoder.
"""
import re
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Dict, List, Optional, Tuple

GSTIN_RE = re.compile(r"^(\d{2})([A-Z]{5}\d{4}[A-Z])([1-9A-Z])Z([0-9A-Z])$")
PAN_RE = re.compile(r"^[A-Z]{5}\d{4}[A-Z]$")
TAN_RE = re.compile(r"^[A-Z]{4}\d{5}[A-Z]$")
UDYAM_RE = re.compile(r"^UDYAM-([A-Z]{2})-(\d{2})-(\d{7})$")
UDYAM_LOOSE_RE = re.compile(r"^UDYAM-?([A-Z]{2})-?(\d{2})-?(\d{7})$")
CIN_RE = re.compile(r"^([LU])(\d{5})([A-Z]{2})(\d{4})([A-Z]{3})(\d{6})$")
LLPIN_RE = re.compile(r"^[A-Z]{3}-\d{4}$")
IFSC_RE = re.compile(r"^([A-Z]{4})0([A-Z0-9]{6})$")
IEC_RE = re.compile(r"^[A-Z0-9]{10}$")
FSSAI_RE = re.compile(r"^\d{14}$")
ESIC_RE = re.compile(r"^\d{17}$")
PF_RE = re.compile(r"^([A-Z]{2})([A-Z]{3})(\d{7})(\d{3})?$")

_CODEPOINT = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"

# GST state / UT codes. 26 is the merged Dadra & Nagar Haveli and Daman & Diu (since 2020); 25 was Daman & Diu before
# that and still appears on older GSTINs, so it is accepted with a warning. 28 is Andhra Pradesh before the 2014 split.
STATE_CODES = {
    "01": "Jammu and Kashmir", "02": "Himachal Pradesh", "03": "Punjab", "04": "Chandigarh",
    "05": "Uttarakhand", "06": "Haryana", "07": "Delhi", "08": "Rajasthan", "09": "Uttar Pradesh",
    "10": "Bihar", "11": "Sikkim", "12": "Arunachal Pradesh", "13": "Nagaland", "14": "Manipur",
    "15": "Mizoram", "16": "Tripura", "17": "Meghalaya", "18": "Assam", "19": "West Bengal",
    "20": "Jharkhand", "21": "Odisha", "22": "Chhattisgarh", "23": "Madhya Pradesh", "24": "Gujarat",
    "25": "Daman and Diu (old code, now 26)",
    "26": "Dadra and Nagar Haveli and Daman and Diu", "27": "Maharashtra", "28": "Andhra Pradesh (before division)",
    "29": "Karnataka", "30": "Goa", "31": "Lakshadweep", "32": "Kerala", "33": "Tamil Nadu",
    "34": "Puducherry", "35": "Andaman and Nicobar Islands", "36": "Telangana", "37": "Andhra Pradesh",
    "38": "Ladakh", "97": "Other Territory", "99": "Centre Jurisdiction",
}

# 4th character of a PAN identifies the holder type
PAN_HOLDER_TYPES = {
    "P": "Individual", "C": "Company", "H": "Hindu Undivided Family", "F": "Firm / LLP",
    "A": "Association of Persons", "B": "Body of Individuals", "T": "Trust",
    "L": "Local Authority", "J": "Artificial Juridical Person", "G": "Government",
}

# Maps PAN holder type to our onboarding entity types (a hint only; LLP vs partnership both use "F")
PAN_TO_ENTITY_HINT = {
    "P": "sole_proprietorship", "C": "private_limited", "F": "partnership", "T": "trust_society",
    "H": "other", "A": "other", "B": "other", "L": "other", "J": "other", "G": "other",
}

# Two-letter state codes inside a Udyam number (UDYAM-MH-26-0012345). Aliases seen in the wild are accepted.
UDYAM_STATE_CODES = {
    "AN": "Andaman and Nicobar Islands", "AP": "Andhra Pradesh", "AR": "Arunachal Pradesh", "AS": "Assam",
    "BR": "Bihar", "CH": "Chandigarh", "CG": "Chhattisgarh", "DD": "Daman and Diu", "DL": "Delhi",
    "DN": "Dadra and Nagar Haveli", "GA": "Goa", "GJ": "Gujarat", "HP": "Himachal Pradesh", "HR": "Haryana",
    "JH": "Jharkhand", "JK": "Jammu and Kashmir", "KA": "Karnataka", "KL": "Kerala", "LA": "Ladakh",
    "LD": "Lakshadweep", "MH": "Maharashtra", "ML": "Meghalaya", "MN": "Manipur", "MP": "Madhya Pradesh",
    "MZ": "Mizoram", "NL": "Nagaland", "OD": "Odisha", "OR": "Odisha", "PB": "Punjab", "PY": "Puducherry",
    "RJ": "Rajasthan", "SK": "Sikkim", "TN": "Tamil Nadu", "TR": "Tripura", "TS": "Telangana", "TG": "Telangana",
    "UK": "Uttarakhand", "UP": "Uttar Pradesh", "WB": "West Bengal",
}

# Registrar-of-Companies state codes in a CIN (differ from Udyam's for a few states: CT, OR, UR, TG).
CIN_STATE_CODES = {**UDYAM_STATE_CODES, "CT": "Chhattisgarh", "UR": "Uttarakhand", "UT": "Uttarakhand"}

# Class of company, the last three letters before the serial number of a CIN. Only the ones we are sure about.
CIN_COMPANY_TYPES = {
    "PTC": "Private company (limited by shares)", "PLC": "Public company (limited by shares)",
    "OPC": "One Person Company", "GOI": "Government of India company", "SGC": "State Government company",
    "NPL": "Section 8 (not-for-profit) company", "ULT": "Unlimited company (private)",
    "ULL": "Unlimited company (public)", "GAP": "Company limited by guarantee (public)",
    "GAT": "Company limited by guarantee (private)",
}
_KNOWN_OTHER_CIN_TYPES = {"FTC", "FLC"}           # real classes; described only as "foreign-linked company"

# Bank code (first four letters of an IFSC) -> bank, for the big names. Unknown codes are fine, just unnamed.
IFSC_BANKS = {
    "SBIN": "State Bank of India", "HDFC": "HDFC Bank", "ICIC": "ICICI Bank", "UTIB": "Axis Bank",
    "PUNB": "Punjab National Bank", "BARB": "Bank of Baroda", "CNRB": "Canara Bank", "UBIN": "Union Bank of India",
    "BKID": "Bank of India", "IDIB": "Indian Bank", "KKBK": "Kotak Mahindra Bank", "YESB": "Yes Bank",
    "IDFB": "IDFC FIRST Bank", "INDB": "IndusInd Bank", "FDRL": "Federal Bank", "MAHB": "Bank of Maharashtra",
    "IOBA": "Indian Overseas Bank", "CBIN": "Central Bank of India", "UCBA": "UCO Bank", "SIBL": "South Indian Bank",
    "KARB": "Karnataka Bank", "RATN": "RBL Bank", "SCBL": "Standard Chartered Bank", "HSBC": "HSBC",
    "CITI": "Citibank", "BDBL": "Bandhan Bank", "AUBL": "AU Small Finance Bank", "PSIB": "Punjab & Sind Bank",
}

_NAME_NOISE = {"M/S", "MS", "MESSRS", "THE", "SHRI", "SMT", "MR", "MRS", "DR"}


# ------------------------------------------------------------------ shared result type

@dataclass
class IdInfo:
    """Result of decoding one identifier. `valid` is about format (and checksum where one exists), nothing more."""
    kind: str
    valid: bool
    value: str
    error: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)


def normalize(value: Optional[str]) -> str:
    return re.sub(r"\s+", "", (value or "")).upper()


def _bad(kind: str, value: str, error: str) -> IdInfo:
    return IdInfo(kind, False, value, error)


def _initial(name: Optional[str], *, any_word: bool = False) -> Optional[str]:
    """First Latin letter of a name (skipping M/s, Shri ...); None when the name is not in Latin letters."""
    words = [w for w in re.split(r"[\s.,]+", (name or "").strip()) if w and w.upper() not in _NAME_NOISE]
    if not words or not re.match(r"[A-Za-z]", words[0]):
        return None
    return words[-1][0].upper() if any_word else words[0][0].upper()


# ------------------------------------------------------------------ GSTIN

@dataclass
class GstinInfo:
    valid: bool
    gstin: str
    error: Optional[str] = None
    state_code: Optional[str] = None
    state_name: Optional[str] = None
    pan: Optional[str] = None
    holder_type: Optional[str] = None
    entity_hint: Optional[str] = None
    registration_number: Optional[str] = None  # n-th registration of the PAN in the state
    warnings: List[str] = field(default_factory=list)


def gstin_check_char(first14: str) -> str:
    total = 0
    for i, ch in enumerate(first14):
        val = _CODEPOINT.index(ch)
        factor = 1 if i % 2 == 0 else 2
        prod = val * factor
        total += prod // 36 + prod % 36
    return _CODEPOINT[(36 - (total % 36)) % 36]


def decode_gstin(value: Optional[str]) -> GstinInfo:
    g = normalize(value)
    if len(g) != 15:
        return GstinInfo(False, g, "A GSTIN has exactly 15 characters.")
    m = GSTIN_RE.match(g)
    if not m:
        return GstinInfo(False, g, "This does not match the GSTIN format (2-digit state, PAN, entity number, Z, check digit).")
    state_code, pan, entity_no, _check = m.groups()
    if state_code not in STATE_CODES:
        return GstinInfo(False, g, f"Unknown state code '{state_code}'.")
    if pan[3] not in PAN_HOLDER_TYPES:
        return GstinInfo(False, g, f"The PAN inside this GSTIN has an impossible holder type '{pan[3]}'.")
    if gstin_check_char(g[:14]) != g[14]:
        return GstinInfo(False, g, "The check digit does not match - there is probably a typo in this GSTIN.")
    holder = pan[3]
    warnings = ["State code 25 (Daman and Diu) was merged into 26 in 2020; confirm this registration on the GST portal."] \
        if state_code == "25" else []
    return GstinInfo(
        valid=True, gstin=g, state_code=state_code, state_name=STATE_CODES[state_code], pan=pan,
        holder_type=PAN_HOLDER_TYPES.get(holder), entity_hint=PAN_TO_ENTITY_HINT.get(holder),
        registration_number=entity_no, warnings=warnings,
    )


# ------------------------------------------------------------------ PAN / TAN

def decode_pan(value: Optional[str], name: Optional[str] = None) -> IdInfo:
    """PAN: 5 letters, 4 digits, 1 letter. 4th letter = holder type. 5th letter = first letter of the holder's
    surname (individuals) or name (everyone else); a mismatch with `name` is only a WARNING because names change
    and trade names differ from registered ones."""
    p = normalize(value)
    if not PAN_RE.match(p):
        return _bad("pan", p, "A PAN is 5 letters, 4 digits and 1 letter (AAAAA9999A).")
    if p[3] not in PAN_HOLDER_TYPES:
        return _bad("pan", p, f"The 4th character '{p[3]}' is not a valid PAN holder type "
                              f"({', '.join(sorted(PAN_HOLDER_TYPES))}).")
    info = IdInfo("pan", True, p, details={
        "holder_code": p[3], "holder_type": PAN_HOLDER_TYPES[p[3]], "entity_hint": PAN_TO_ENTITY_HINT[p[3]],
        "name_initial": p[4],
    })
    warning = pan_name_warning(p, name)
    if warning:
        info.warnings.append(warning)
    return info


def pan_name_warning(pan: str, name: Optional[str]) -> Optional[str]:
    """Why the PAN's 5th character does not fit `name`, or None when it fits / cannot be judged.
    Individuals: the letter should start the surname, which in India is the last or the first word of the name."""
    if not PAN_RE.match(pan) or not name:
        return None
    if pan[3] == "P":
        initials = {_initial(name), _initial(name, any_word=True)}
    else:
        initials = {_initial(name)}
    initials.discard(None)
    if not initials or pan[4] in initials:
        return None
    what = "surname" if pan[3] == "P" else "name"
    return (f"The 5th character of the PAN is '{pan[4]}', which is normally the first letter of the holder's {what}, "
            f"but '{name.strip()}' does not start with it. This happens after a rename or when a trade name is used, "
            f"so treat it as a reason to double-check, not as an error.")


def decode_tan(value: Optional[str], name: Optional[str] = None) -> IdInfo:
    """TAN (tax deduction account number): 4 letters, 5 digits, 1 letter. The 4th letter is the first letter of the
    deductor's name (a mismatch is only a warning)."""
    t = normalize(value)
    if not TAN_RE.match(t):
        return _bad("tan", t, "A TAN is 4 letters, 5 digits and 1 letter (AAAA99999A).")
    info = IdInfo("tan", True, t, details={"name_initial": t[3]})
    initial = _initial(name)
    if initial and initial != t[3]:
        info.warnings.append(f"The 4th character of the TAN is '{t[3]}' (the deductor's first initial) but the name starts "
                             f"with '{initial}'. Check it is the right deductor.")
    return info


def validate_pan(value: Optional[str]) -> bool:
    return decode_pan(value).valid


# ------------------------------------------------------------------ Udyam / CIN / LLPIN

def normalize_udyam(value: Optional[str]) -> str:
    """UDYAM-XX-00-0000000 with the hyphens restored when they were left out; anything else is returned upper-cased."""
    v = normalize(value)
    m = UDYAM_LOOSE_RE.match(v)
    return f"UDYAM-{m.group(1)}-{m.group(2)}-{m.group(3)}" if m else v


def decode_udyam(value: Optional[str]) -> IdInfo:
    """Udyam registration number UDYAM-XX-00-0000000: state letters, 2-digit district code, 7-digit serial."""
    u = normalize_udyam(value)
    m = UDYAM_RE.match(u)
    if not m:
        return _bad("udyam", u, "A Udyam number looks like UDYAM-MH-26-0012345 (state letters, 2-digit district, 7-digit number).")
    state, district, serial = m.groups()
    if state not in UDYAM_STATE_CODES:
        return _bad("udyam", u, f"'{state}' is not a state code used in Udyam numbers.")
    return IdInfo("udyam", True, u, details={"state_code": state, "state_name": UDYAM_STATE_CODES[state],
                                              "district_code": district, "serial": serial})


def decode_cin(value: Optional[str], today: Optional[date] = None) -> IdInfo:
    """CIN, 21 characters: listing status (L listed / U unlisted), 5-digit industry code, 2-letter state, 4-digit
    year of incorporation, 3-letter company class, 6-digit registration number."""
    c = normalize(value)
    if len(c) != 21:
        return _bad("cin", c, "A CIN has exactly 21 characters.")
    m = CIN_RE.match(c)
    if not m:
        return _bad("cin", c, "This does not match the CIN format (L/U + 5 digits + state + year + class + 6 digits).")
    listing, industry, state, year_s, klass, number = m.groups()
    year = int(year_s)
    this_year = (today or date.today()).year
    if not 1850 <= year <= this_year:
        return _bad("cin", c, f"The incorporation year {year} is not possible.")
    info = IdInfo("cin", True, c, details={
        "listed": listing == "L", "listing_status": "Listed" if listing == "L" else "Unlisted",
        "industry_code": industry, "state_code": state, "state_name": CIN_STATE_CODES.get(state),
        "incorporation_year": year, "company_class": klass,
        "company_type": CIN_COMPANY_TYPES.get(klass) or ("Foreign-linked company" if klass in _KNOWN_OTHER_CIN_TYPES else None),
        "registration_number": number,
    })
    if state not in CIN_STATE_CODES:
        info.warnings.append(f"State code '{state}' is not one we recognise; check the number on the MCA portal.")
    if klass not in CIN_COMPANY_TYPES and klass not in _KNOWN_OTHER_CIN_TYPES:
        info.warnings.append(f"Company class '{klass}' is not one we recognise; check the number on the MCA portal.")
    if listing == "L" and klass in ("PTC", "OPC", "GAT", "ULT"):
        info.warnings.append("The CIN says listed, but a private company cannot be listed. One of its characters is probably wrong.")
    return info


def validate_cin(value: Optional[str]) -> bool:
    return decode_cin(value).valid


def validate_udyam(value: Optional[str]) -> bool:
    return decode_udyam(value).valid


def validate_llpin(value: Optional[str]) -> bool:
    return bool(LLPIN_RE.match(normalize(value)))


# ------------------------------------------------------------------ banking, trade, food, labour

def decode_ifsc(value: Optional[str]) -> IdInfo:
    """IFSC: 4-letter bank code, a zero, then a 6-character branch code."""
    i = normalize(value)
    m = IFSC_RE.match(i)
    if not m:
        return _bad("ifsc", i, "An IFSC is 11 characters: 4 letters, the digit 0, then 6 letters or digits (SBIN0001234).")
    bank, branch = m.groups()
    return IdInfo("ifsc", True, i, details={"bank_code": bank, "bank_name": IFSC_BANKS.get(bank), "branch_code": branch})


def decode_iec(value: Optional[str]) -> IdInfo:
    """Importer-Exporter Code: 10 characters. Older codes are 10 digits; newer ones are the holder's PAN."""
    i = normalize(value)
    if not IEC_RE.match(i):
        return _bad("iec", i, "An IEC is 10 letters or digits.")
    info = IdInfo("iec", True, i, details={"pan_based": bool(PAN_RE.match(i))})
    if info.details["pan_based"] and i[3] not in PAN_HOLDER_TYPES:
        info.valid, info.error = False, f"This looks PAN-based but its 4th character '{i[3]}' is not a valid PAN holder type."
    return info


def decode_fssai(value: Optional[str]) -> IdInfo:
    """FSSAI licence / registration number: 14 digits."""
    f = normalize(value)
    if not FSSAI_RE.match(f):
        return _bad("fssai", f, "An FSSAI licence number has exactly 14 digits.")
    if len(set(f)) == 1:
        return _bad("fssai", f, "A number with the same digit repeated cannot be a real licence number.")
    return IdInfo("fssai", True, f)


def decode_esic(value: Optional[str]) -> IdInfo:
    """ESIC employer code: 17 digits."""
    e = re.sub(r"[\s/-]", "", value or "")
    if not ESIC_RE.match(e):
        return _bad("esic", e, "An ESIC employer code has exactly 17 digits.")
    if len(set(e)) == 1:
        return _bad("esic", e, "A number with the same digit repeated cannot be a real ESIC code.")
    return IdInfo("esic", True, e)


def normalize_pf(value: Optional[str]) -> str:
    return re.sub(r"[\s/.\-]", "", (value or "")).upper()


def decode_pf_code(value: Optional[str]) -> IdInfo:
    """EPFO establishment code: 2-letter region, 3-letter office, 7-digit establishment number, optional 3-digit
    extension (DLCPM0012345000). Slashes and dashes are ignored (DL/CPM/0012345/000)."""
    p = normalize_pf(value)
    m = PF_RE.match(p)
    if not m:
        return _bad("pf", p, "A PF establishment code is 2 letters, 3 letters, 7 digits and usually a 3-digit extension "
                             "(DLCPM0012345000).")
    region, office, number, ext = m.groups()
    return IdInfo("pf", True, p, details={"region_code": region, "office_code": office, "establishment_number": number,
                                          "extension": ext})


# ------------------------------------------------------------------ dispatch

KINDS = ("gstin", "pan", "tan", "udyam", "cin", "llpin", "ifsc", "iec", "fssai", "esic", "pf")


def identify(raw: Optional[str]) -> Tuple[str, str]:
    """Guess what a pasted number is -> (kind, canonical value). Ambiguous or unrecognisable input is treated as a
    (malformed) GSTIN so the offline check can say exactly what is wrong with it. A 10-character IEC that is not
    also a PAN is not guessed; the caller passes `kind="iec"` for those."""
    v = normalize(raw)
    if v.startswith("UDYAM"):
        return "udyam", normalize_udyam(v)
    if len(v) == 21 and v[0] in "LU":
        return "cin", v
    if LLPIN_RE.match(v):
        return "llpin", v
    if len(v) == 11 and v[:4].isalpha() and v[4] == "0":
        return "ifsc", v
    if PAN_RE.match(v):
        return "pan", v
    if TAN_RE.match(v):
        return "tan", v
    if len(v) == 10 and v.isdigit():
        return "iec", v
    if FSSAI_RE.match(v):
        return "fssai", v
    if ESIC_RE.match(v):
        return "esic", v
    pf = normalize_pf(raw)
    if len(pf) in (12, 15) and PF_RE.match(pf):
        return "pf", pf
    return "gstin", v


def decode(kind: str, raw: Optional[str], name: Optional[str] = None, today: Optional[date] = None) -> IdInfo:
    """Runs the decoder for `kind` and returns the uniform `IdInfo` (GSTIN included)."""
    if kind == "gstin":
        g = decode_gstin(raw)
        return IdInfo("gstin", g.valid, g.gstin, g.error, {
            "state_code": g.state_code, "state_name": g.state_name, "pan": g.pan, "holder_type": g.holder_type,
            "entity_hint": g.entity_hint, "registration_number": g.registration_number}, list(g.warnings))
    if kind == "pan":
        return decode_pan(raw, name)
    if kind == "tan":
        return decode_tan(raw, name)
    if kind == "udyam":
        return decode_udyam(raw)
    if kind == "cin":
        return decode_cin(raw, today)
    if kind == "llpin":
        v = normalize(raw)
        return IdInfo("llpin", bool(LLPIN_RE.match(v)), v, None if LLPIN_RE.match(v) else "An LLPIN looks like AAB-1234.")
    decoders = {"ifsc": decode_ifsc, "iec": decode_iec, "fssai": decode_fssai, "esic": decode_esic, "pf": decode_pf_code}
    if kind not in decoders:
        raise ValueError(f"Unknown identifier kind '{kind}'.")
    return decoders[kind](raw)
