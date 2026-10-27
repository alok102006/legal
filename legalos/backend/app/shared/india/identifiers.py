"""Offline validators/decoders for Indian business identifiers.

These need no API and no network: they catch typos and fake numbers instantly and extract
useful facts (state, PAN, holder type). A passing checksum does NOT prove the registration
exists or is active - that needs a live registry lookup.
"""
import re
from dataclasses import dataclass
from typing import Optional

GSTIN_RE = re.compile(r"^(\d{2})([A-Z]{5}\d{4}[A-Z])([1-9A-Z])Z([0-9A-Z])$")
PAN_RE = re.compile(r"^[A-Z]{5}\d{4}[A-Z]$")
UDYAM_RE = re.compile(r"^UDYAM-([A-Z]{2})-(\d{2})-(\d{7})$")
CIN_RE = re.compile(r"^([LU])(\d{5})([A-Z]{2})(\d{4})([A-Z]{3})(\d{6})$")
LLPIN_RE = re.compile(r"^[A-Z]{3}-\d{4}$")

_CODEPOINT = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"

STATE_CODES = {
    "01": "Jammu and Kashmir", "02": "Himachal Pradesh", "03": "Punjab", "04": "Chandigarh",
    "05": "Uttarakhand", "06": "Haryana", "07": "Delhi", "08": "Rajasthan", "09": "Uttar Pradesh",
    "10": "Bihar", "11": "Sikkim", "12": "Arunachal Pradesh", "13": "Nagaland", "14": "Manipur",
    "15": "Mizoram", "16": "Tripura", "17": "Meghalaya", "18": "Assam", "19": "West Bengal",
    "20": "Jharkhand", "21": "Odisha", "22": "Chhattisgarh", "23": "Madhya Pradesh", "24": "Gujarat",
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


def gstin_check_char(first14: str) -> str:
    total = 0
    for i, ch in enumerate(first14):
        val = _CODEPOINT.index(ch)
        factor = 1 if i % 2 == 0 else 2
        prod = val * factor
        total += prod // 36 + prod % 36
    return _CODEPOINT[(36 - (total % 36)) % 36]


def normalize(value: Optional[str]) -> str:
    return re.sub(r"\s+", "", (value or "")).upper()


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
    if gstin_check_char(g[:14]) != g[14]:
        return GstinInfo(False, g, "The check digit does not match - there is probably a typo in this GSTIN.")
    holder = pan[3]
    return GstinInfo(
        valid=True, gstin=g, state_code=state_code, state_name=STATE_CODES[state_code], pan=pan,
        holder_type=PAN_HOLDER_TYPES.get(holder), entity_hint=PAN_TO_ENTITY_HINT.get(holder),
        registration_number=entity_no,
    )


def validate_pan(value: Optional[str]) -> bool:
    return bool(PAN_RE.match(normalize(value))) and normalize(value)[3] in PAN_HOLDER_TYPES


def validate_udyam(value: Optional[str]) -> bool:
    return bool(UDYAM_RE.match(normalize(value)))


def validate_cin(value: Optional[str]) -> bool:
    return bool(CIN_RE.match(normalize(value)))


def validate_llpin(value: Optional[str]) -> bool:
    return bool(LLPIN_RE.match(normalize(value)))
