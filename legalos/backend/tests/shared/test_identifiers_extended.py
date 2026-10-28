from datetime import date

import pytest

from app.shared.india import identifiers as ids


def _gstin(state="27", pan="AABCK1234F", entity="1"):
    first14 = f"{state}{pan}{entity}Z"
    return first14 + ids.gstin_check_char(first14)


# ------------------------------------------------------------------ GSTIN state table

ALL_STATE_CODES = [f"{i:02d}" for i in range(1, 39)] + ["97", "99"]


def test_state_table_covers_every_gst_code():
    for code in ALL_STATE_CODES:
        if code != "25":                       # retired (merged into 26); kept only as a legacy code
            assert code in ids.STATE_CODES, code
    assert ids.STATE_CODES["26"] == "Dadra and Nagar Haveli and Daman and Diu"
    assert ids.STATE_CODES["38"] == "Ladakh" and ids.STATE_CODES["97"] == "Other Territory"
    assert ids.STATE_CODES["99"] == "Centre Jurisdiction" and ids.STATE_CODES["36"] == "Telangana"


@pytest.mark.parametrize("code", [c for c in ALL_STATE_CODES])
def test_a_gstin_for_every_state_code_decodes(code):
    info = ids.decode_gstin(_gstin(state=code))
    assert info.valid, info.error
    assert info.state_name == ids.STATE_CODES[code]


def test_legacy_code_25_is_accepted_with_a_warning():
    info = ids.decode_gstin(_gstin(state="25"))
    assert info.valid and info.warnings and "merged into 26" in info.warnings[0]


@pytest.mark.parametrize("code", ["00", "39", "50", "98"])
def test_unknown_state_codes_are_rejected(code):
    assert not ids.decode_gstin(_gstin(state=code)).valid


def test_gstin_with_impossible_pan_holder_type_is_invalid():
    info = ids.decode_gstin(_gstin(pan="AABXK1234F"))
    assert not info.valid and "holder type" in info.error


# ------------------------------------------------------------------ PAN

@pytest.mark.parametrize("letter,label", [("P", "Individual"), ("C", "Company"), ("H", "Hindu Undivided Family"), ("F", "Firm / LLP"),
                                          ("A", "Association of Persons"), ("B", "Body of Individuals"), ("T", "Trust"),
                                          ("L", "Local Authority"), ("J", "Artificial Juridical Person"), ("G", "Government")])
def test_every_pan_holder_type_is_decoded(letter, label):
    info = ids.decode_pan(f"AAA{letter}K1234F")
    assert info.valid and info.details["holder_type"] == label


def test_invalid_pan_cases():
    assert "4th character" in ids.decode_pan("AAAXK1234F").error
    assert not ids.decode_pan("AAACK12345").valid and not ids.decode_pan("").valid
    assert not ids.validate_pan("ABC")


def test_pan_fifth_letter_vs_name_is_only_a_warning():
    ok = ids.decode_pan("AAACS4321K", name="Shree Steel Traders")
    assert ok.valid and not ok.warnings
    bad = ids.decode_pan("AAACS4321K", name="Zenith Metals Pvt Ltd")
    assert bad.valid and len(bad.warnings) == 1 and "'S'" in bad.warnings[0]
    # prefixes like M/s are skipped, and an individual's surname may be the first or the last word
    assert not ids.decode_pan("AAACS4321K", name="M/s Shree Steel").warnings
    assert not ids.decode_pan("ABCPK1234F", name="Rajesh Kumar").warnings
    assert not ids.decode_pan("ABCPR1234F", name="Rajesh Kumar").warnings
    assert ids.decode_pan("ABCPZ1234F", name="Rajesh Kumar").warnings
    # names we cannot judge (Devanagari) or no name: no warning
    assert not ids.decode_pan("AAACS4321K", name="श्री स्टील").warnings and not ids.decode_pan("AAACS4321K").warnings


def test_tan():
    assert ids.decode_tan("MUMS12345B").valid and not ids.decode_tan("MUMS1234B").valid
    assert ids.decode_tan("MUMS12345B", name="Shree Traders").valid
    assert ids.decode_tan("MUMS12345B", name="Zenith").warnings


# ------------------------------------------------------------------ Udyam

def test_udyam_state_codes():
    ok = ids.decode_udyam("udyam-mh-26-0012345")
    assert ok.valid and ok.details["state_name"] == "Maharashtra" and ok.details["district_code"] == "26"
    assert ids.decode_udyam("UDYAMMH260012345").value == "UDYAM-MH-26-0012345"      # hyphens restored
    assert not ids.decode_udyam("UDYAM-XX-26-0012345").valid                         # not a state
    assert "state code" in ids.decode_udyam("UDYAM-XX-26-0012345").error
    assert not ids.decode_udyam("UDYAM-MH-26-12345").valid
    for code in ("TN", "TS", "UK", "WB", "DL", "KA", "GJ", "LA", "JK", "AN"):
        assert ids.decode_udyam(f"UDYAM-{code}-01-0000001").valid, code
    assert ids.validate_udyam("UDYAM-MH-26-0012345") and not ids.validate_udyam("12345")


# ------------------------------------------------------------------ CIN

def test_cin_decoded():
    info = ids.decode_cin("L17110MH1973PLC019786", today=date(2026, 10, 28))     # a real listed-company shape
    d = info.details
    assert info.valid and d["listing_status"] == "Listed" and d["industry_code"] == "17110"
    assert d["state_name"] == "Maharashtra" and d["incorporation_year"] == 1973 and d["company_class"] == "PLC"
    assert d["registration_number"] == "019786" and "Public" in d["company_type"] and not info.warnings
    pvt = ids.decode_cin("U74999KA2020PTC123456")
    assert pvt.details["listing_status"] == "Unlisted" and pvt.details["state_name"] == "Karnataka"


@pytest.mark.parametrize("cin,why", [
    ("U74999MH2020PTC12345", "21 characters"),
    ("X74999MH2020PTC123456", "format"),
    ("U74999MH2099PTC123456", "year"),
    ("U74999MH1700PTC123456", "year"),
])
def test_bad_cins(cin, why):
    info = ids.decode_cin(cin, today=date(2026, 10, 28))
    assert not info.valid and why in info.error


def test_cin_warnings_not_errors():
    assert ids.decode_cin("U74999ZZ2020PTC123456").warnings                         # unknown state code
    assert ids.decode_cin("U74999MH2020XYZ123456").warnings                         # unknown class
    listed_private = ids.decode_cin("L74999MH2020PTC123456")
    assert listed_private.valid and "cannot be listed" in listed_private.warnings[0]
    assert ids.validate_cin("U74999MH2020PTC123456") and not ids.validate_cin("nope")


def test_llpin():
    assert ids.validate_llpin("AAB-1234") and not ids.validate_llpin("AAB1234")
    assert ids.decode("llpin", "aab-1234").valid


# ------------------------------------------------------------------ IFSC / IEC / FSSAI / ESIC / PF

def test_ifsc():
    ok = ids.decode_ifsc("sbin0001234")
    assert ok.valid and ok.details["bank_name"] == "State Bank of India" and ok.details["branch_code"] == "001234"
    assert ids.decode_ifsc("ABCD0X12345").valid and ids.decode_ifsc("ABCD0X12345").details["bank_name"] is None
    for bad in ("SBIN1001234", "SBI00001234", "SBIN000123", "SBIN00012345"):
        assert not ids.decode_ifsc(bad).valid, bad


def test_iec():
    assert ids.decode_iec("0305008111").valid                                      # older, all digits
    assert ids.decode_iec("AAACS4321K").details["pan_based"]
    assert not ids.decode_iec("AAAXS4321K").valid                                  # PAN-shaped but impossible holder type
    assert not ids.decode_iec("123").valid


def test_fssai():
    assert ids.decode_fssai("11520011000123").valid
    assert not ids.decode_fssai("1152001100012").valid and not ids.decode_fssai("1152001100012X").valid
    assert not ids.decode_fssai("11111111111111").valid


def test_esic():
    assert ids.decode_esic("31-00-123456-000-0001").valid                          # separators are ignored (17 digits)
    assert ids.decode_esic("12345678901234567").valid
    assert not ids.decode_esic("1234567890123456").valid
    assert not ids.decode_esic("00000000000000000").valid


def test_pf_code():
    full = ids.decode_pf_code("DL/CPM/0012345/000")
    assert full.valid and full.value == "DLCPM0012345000" and full.details["extension"] == "000"
    assert ids.decode_pf_code("MHBAN1234567").valid                                # without extension
    assert not ids.decode_pf_code("DLCPM12345").valid and not ids.decode_pf_code("12CPM0012345000").valid


# ------------------------------------------------------------------ identify / decode

@pytest.mark.parametrize("raw,kind", [
    (_gstin(), "gstin"), ("AABCK1234F", "pan"), ("MUMS12345B", "tan"), ("udyam mh 26 0012345", "udyam"),
    ("U74999MH2020PTC123456", "cin"), ("AAB-1234", "llpin"), ("SBIN0001234", "ifsc"), ("0305008111", "iec"),
    ("11520011000123", "fssai"), ("12345678901234567", "esic"), ("DL/CPM/0012345/000", "pf"), ("garbage", "gstin"),
])
def test_identify(raw, kind):
    assert ids.identify(raw)[0] == kind


def test_identify_canonicalises():
    assert ids.identify(" udyam-mh-26-0012345 ") == ("udyam", "UDYAM-MH-26-0012345")
    assert ids.identify("dl/cpm/0012345/000") == ("pf", "DLCPM0012345000")


def test_decode_dispatch_and_unknown_kind():
    g = ids.decode("gstin", _gstin())
    assert g.valid and g.details["state_name"] == "Maharashtra" and g.details["pan"] == "AABCK1234F"
    assert set(ids.KINDS) == {"gstin", "pan", "tan", "udyam", "cin", "llpin", "ifsc", "iec", "fssai", "esic", "pf"}
    with pytest.raises(ValueError):
        ids.decode("passport", "X")
