from app.shared.india import identifiers as ids


def _make_gstin(state="27", pan="AABCK1234F", entity="1"):
    first14 = f"{state}{pan}{entity}Z"
    return first14 + ids.gstin_check_char(first14)


def test_generated_gstin_is_valid_and_decoded():
    info = ids.decode_gstin(_make_gstin())
    assert info.valid
    assert info.state_name == "Maharashtra"
    assert info.pan == "AABCK1234F"
    assert info.holder_type == "Company" and info.entity_hint == "private_limited"


def test_known_public_gstin_checksum():
    # Widely published sample GSTIN (format example in GST documentation)
    info = ids.decode_gstin("27AAPFU0939F1ZV")
    assert info.valid, info.error


def test_typo_is_caught_by_checksum():
    good = _make_gstin()
    bad = good[:-1] + ("A" if good[-1] != "A" else "B")
    info = ids.decode_gstin(bad)
    assert not info.valid and "check digit" in info.error


def test_bad_shapes():
    assert not ids.decode_gstin("").valid
    assert not ids.decode_gstin("27AABCK1234F1Z").valid          # too short
    assert not ids.decode_gstin("27AABCK1234F1X5").valid         # no Z
    assert not ids.decode_gstin(_make_gstin(state="50")).valid   # unknown state


def test_whitespace_and_case_are_normalised():
    g = _make_gstin()
    assert ids.decode_gstin(f" {g[:2]} {g[2:].lower()} ").valid


def test_pan_udyam_cin():
    assert ids.validate_pan("AABCK1234F") and not ids.validate_pan("AABXK1234F") and not ids.validate_pan("123")
    assert ids.validate_udyam("udyam-mh-26-0012345") and not ids.validate_udyam("UDYAM-MH-26-12345")
    assert ids.validate_cin("U74999MH2020PTC123456") and not ids.validate_cin("X74999MH2020PTC123456")
    assert ids.validate_llpin("AAB-1234")
