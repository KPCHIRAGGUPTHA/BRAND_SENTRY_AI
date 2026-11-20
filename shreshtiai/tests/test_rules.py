from datetime import date

from shreshti.rules.gstin import checksum_char, validate_gstin
from shreshti.rules.late_fee import compute_late_fee
from shreshti.rules.tax_type import COMPLIANT, NEEDS_REVIEW, NON_COMPLIANT, check_tax_type

# Publicly documented sample GSTINs used in GST tutorials.
VALID_MH = "27AAPFU0939F1ZV"
VALID_KA = "29AAGCB7383J1Z4"


# ---------- GSTIN ----------
def test_valid_gstins_pass():
    for g in (VALID_MH, VALID_KA):
        r = validate_gstin(g)
        assert r.valid, r.errors
    assert validate_gstin(VALID_KA).state == "Karnataka"


def test_lowercase_and_spaces_are_normalised():
    assert validate_gstin(f"  {VALID_KA.lower()} ").valid


def test_checksum_mismatch_is_caught():
    bad = VALID_KA[:14] + ("5" if VALID_KA[14] != "5" else "6")
    r = validate_gstin(bad)
    assert not r.valid
    assert "Checksum" in r.errors[0]
    assert checksum_char(VALID_KA[:14]) == VALID_KA[14]


def test_wrong_length_and_format():
    assert "15 characters" in validate_gstin("29AAGCB7383J1Z").errors[0]
    assert "format" in validate_gstin("29AAGCB7383J1X4").errors[0]


def test_unknown_state_code():
    first14 = "28AAGCB7383J1Z"  # 28 (old Andhra Pradesh) is not in the active list
    r = validate_gstin(first14 + checksum_char(first14))
    assert not r.valid and "state code" in r.errors[0]


# ---------- Tax type ----------
def test_intra_state_igst_is_wrong():
    f = check_tax_type("29", "29", cgst=0, sgst=0, igst=180)
    assert f.verdict == NON_COMPLIANT and f.expected == "CGST + SGST"


def test_inter_state_split_is_wrong():
    f = check_tax_type("29", "33", cgst=90, sgst=90, igst=0)
    assert f.verdict == NON_COMPLIANT and f.expected == "IGST"


def test_correct_cases_pass():
    assert check_tax_type("29", "29", 90, 90, 0).verdict == COMPLIANT
    assert check_tax_type("29", "33", 0, 0, 180).verdict == COMPLIANT


def test_unequal_halves_and_special_cases():
    assert check_tax_type("29", "29", 100, 80, 0).verdict == NON_COMPLIANT
    assert check_tax_type("29", "33", 0, 0, 180, special_case=True).verdict == NEEDS_REVIEW


# ---------- Late fee ----------
def test_late_fee_small_business():
    r = compute_late_fee(date(2026, 10, 20), date(2026, 10, 30), aato=80_00_000)
    assert r.days_late == 10 and r.late_fee == 500 and not r.cap_applied


def test_late_fee_cap_and_nil_return():
    r = compute_late_fee(date(2026, 1, 20), date(2026, 6, 20), aato=1 * 10_000_000)
    assert r.late_fee == 2000 and r.cap_applied
    nil = compute_late_fee(date(2026, 1, 20), date(2026, 6, 20), aato=0, nil_return=True)
    assert nil.late_fee == 500


def test_interest_and_on_time():
    r = compute_late_fee(date(2026, 10, 20), date(2026, 11, 19), aato=50_00_000, tax_paid_late=30_000)
    assert r.days_late == 30 and r.interest == round(30_000 * 0.18 * 30 / 365, 2)
    assert compute_late_fee(date(2026, 10, 20), date(2026, 10, 19), aato=50_00_000).total == 0
