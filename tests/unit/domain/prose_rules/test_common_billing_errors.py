"""Unit tests for the top-5 Tablo 15 common billing error detectors.

One positive (error detected) and one negative (no error) test per detector:
- ``detect_duplicate_exam_10day``            (Tablo 15 #2)
- ``detect_missing_diagnosis``               (Tablo 15 #8)
- ``detect_duplicate_tests``                 (Tablo 15 #12)
- ``detect_exam_admission_date_mismatch``    (Tablo 15 #22)
- ``detect_missing_drug_barcode``            (Tablo 15 #20)
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from src.bilun.domain.claims.models import (
    ClaimHeader,
    DrugClaimLine,
    ProcedureClaimLine,
)
from src.bilun.domain.prose_rules.common_billing_errors import (
    detect_duplicate_exam_10day,
    detect_duplicate_tests,
    detect_exam_admission_date_mismatch,
    detect_missing_diagnosis,
    detect_missing_drug_barcode,
)

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Construction helpers (mirror the pattern in test_anestezi_puani.py).
# ---------------------------------------------------------------------------


def _make_claim_header(
    *,
    claim_id: str = "C1",
    patient_id: str = "P1",
    episode_id: str = "E1",
    claim_type: str = "yatis",
    admission: date | None = date(2026, 7, 10),
    discharge: date | None = date(2026, 7, 13),
    primary_icd10: str = "K35.8",
    department: str = "genel",
) -> ClaimHeader:
    return ClaimHeader(
        claim_id=claim_id,
        patient_id=patient_id,
        episode_id=episode_id,
        claim_type=claim_type,
        facility_tier="devlet",
        provider_type="sozlesmeli",
        department=department,
        admission_date=admission,
        discharge_date=discharge,
        claim_start_date=admission or date.today(),
        claim_end_date=discharge or date.today(),
        primary_icd10=primary_icd10,
        package_candidate=False,
        expected_total_billed_try=Decimal("1000"),
        expected_total_payable_try=Decimal("900"),
        expected_denial_reason="",
        scenario_tag="test",
    )


def _make_proc_line(
    *,
    procedure_line_id: str = "PL1",
    claim_id: str = "C1",
    procedure_code: str = "401010",
    procedure_category: str = "muayene",
    procedure_date: date = date(2026, 7, 10),
    procedure_specialty_code: str = "1000",
    quantity: int = 1,
) -> ProcedureClaimLine:
    return ProcedureClaimLine(
        procedure_line_id=procedure_line_id,
        claim_id=claim_id,
        patient_id="P1",
        episode_id="E1",
        procedure_date=procedure_date,
        procedure_code=procedure_code,
        procedure_name="test procedure",
        procedure_category=procedure_category,
        quantity=quantity,
        unit_price_try=Decimal("1000"),
        billed_amount_try=Decimal("1000"),
        expected_payable_try=Decimal("1000"),
        is_package_included=False,
        package_code="",
        surcharge_applicable=False,
        copay_rate_applicable=False,
        denial_reason_expected="",
        rule_trace_expected="",
        procedure_specialty_code=procedure_specialty_code,
    )


def _make_drug_line(
    *,
    drug_claim_line_id: str = "D1",
    claim_id: str = "C1",
    barkod: str = "8690000000001",
    drug_name: str = "Parasetamol",
    drug_code: str = "PARA1",
) -> DrugClaimLine:
    return DrugClaimLine(
        drug_claim_line_id=drug_claim_line_id,
        prescription_id="RX1",
        claim_id=claim_id,
        patient_id="P1",
        episode_id="E1",
        drug_claim_date=date(2026, 7, 10),
        drug_name=drug_name,
        drug_code=drug_code,
        barkod=barkod,
        equivalence_group="",
        quantity=1,
        unit_price_try=Decimal("100"),
        billed_amount_try=Decimal("100"),
        expected_payable_try=Decimal("72"),
        discount_tier_expected=Decimal("0.28"),
        denial_reason_expected="",
        rule_trace_expected="",
    )


# ===========================================================================
# Error #2 — detect_duplicate_exam_10day
# ===========================================================================


def test_duplicate_exam_10day_positive() -> None:
    """Two same-specialty outpatient exams 5 days apart → violation on 2nd."""
    c1 = _make_claim_header(
        claim_id="C1",
        claim_type="poliklinik",
        admission=None,
        discharge=None,
    )
    c2 = _make_claim_header(
        claim_id="C2",
        claim_type="poliklinik",
        admission=None,
        discharge=None,
    )
    l1 = _make_proc_line(
        procedure_line_id="PL1",
        claim_id="C1",
        procedure_specialty_code="1000",
        procedure_date=date(2026, 7, 1),
    )
    l2 = _make_proc_line(
        procedure_line_id="PL2",
        claim_id="C2",
        procedure_specialty_code="1000",
        procedure_date=date(2026, 7, 6),  # 5 days later, same specialty
    )

    violations = detect_duplicate_exam_10day([c1, c2], [l1, l2])

    assert len(violations) == 1
    v = violations[0]
    assert v["claim_id"] == "C2"
    assert v["rule_id"] == "tablo15_2_duplicate_exam_10day"
    assert v["severity"] == "error"
    assert v["procedure_specialty_code"] == "1000"
    assert v["gap_days"] == 5
    assert v["prior_claim_id"] == "C1"


def test_duplicate_exam_10day_negative() -> None:
    """Two exams >10 days apart → no violation."""
    c1 = _make_claim_header(
        claim_id="C1",
        claim_type="poliklinik",
        admission=None,
        discharge=None,
    )
    c2 = _make_claim_header(
        claim_id="C2",
        claim_type="poliklinik",
        admission=None,
        discharge=None,
    )
    l1 = _make_proc_line(
        procedure_line_id="PL1",
        claim_id="C1",
        procedure_specialty_code="1000",
        procedure_date=date(2026, 7, 1),
    )
    l2 = _make_proc_line(
        procedure_line_id="PL2",
        claim_id="C2",
        procedure_specialty_code="1000",
        procedure_date=date(2026, 7, 20),  # 19 days later — outside window
    )

    violations = detect_duplicate_exam_10day([c1, c2], [l1, l2])

    assert violations == []


# ===========================================================================
# Error #8 — detect_missing_diagnosis
# ===========================================================================


def test_missing_diagnosis_positive() -> None:
    """Claim with empty primary_icd10 → violation."""
    claim = _make_claim_header(claim_id="C1", primary_icd10="")

    violations = detect_missing_diagnosis([claim])

    assert len(violations) == 1
    v = violations[0]
    assert v["claim_id"] == "C1"
    assert v["rule_id"] == "tablo15_8_missing_diagnosis"
    assert v["severity"] == "error"


def test_missing_diagnosis_negative() -> None:
    """Claim with a populated primary_icd10 → no violation."""
    claim = _make_claim_header(claim_id="C1", primary_icd10="J03.90")

    violations = detect_missing_diagnosis([claim])

    assert violations == []


# ===========================================================================
# Error #12 — detect_duplicate_tests
# ===========================================================================


def test_duplicate_tests_positive() -> None:
    """Same lab code on two claims within 7 days → violation on the later."""
    c1 = _make_claim_header(claim_id="C1")
    c2 = _make_claim_header(claim_id="C2")
    l1 = _make_proc_line(
        procedure_line_id="PL1",
        claim_id="C1",
        procedure_code="901050",
        procedure_category="laboratuvar",
        procedure_date=date(2026, 7, 1),
    )
    l2 = _make_proc_line(
        procedure_line_id="PL2",
        claim_id="C2",
        procedure_code="901050",  # same code, different claim
        procedure_category="laboratuvar",
        procedure_date=date(2026, 7, 4),  # 3 days later — within window
    )

    violations = detect_duplicate_tests([c1, c2], [l1, l2])

    assert len(violations) == 1
    v = violations[0]
    assert v["claim_id"] == "C2"
    assert v["rule_id"] == "tablo15_12_duplicate_test"
    assert v["severity"] == "warning"
    assert v["procedure_code"] == "901050"
    assert v["prior_claim_id"] == "C1"
    assert v["gap_days"] == 3


def test_duplicate_tests_negative() -> None:
    """Same code on two claims but >7 days apart → no violation."""
    c1 = _make_claim_header(claim_id="C1")
    c2 = _make_claim_header(claim_id="C2")
    l1 = _make_proc_line(
        procedure_line_id="PL1",
        claim_id="C1",
        procedure_code="901050",
        procedure_category="laboratuvar",
        procedure_date=date(2026, 7, 1),
    )
    l2 = _make_proc_line(
        procedure_line_id="PL2",
        claim_id="C2",
        procedure_code="901050",
        procedure_category="laboratuvar",
        procedure_date=date(2026, 7, 20),  # 19 days later — outside window
    )

    violations = detect_duplicate_tests([c1, c2], [l1, l2])

    assert violations == []


# ===========================================================================
# Error #22 — detect_exam_admission_date_mismatch
# ===========================================================================


def test_exam_admission_date_mismatch_positive() -> None:
    """Inpatient claim whose first procedure date != admission date."""
    claim = _make_claim_header(
        claim_id="C1",
        claim_type="yatis",
        admission=date(2026, 7, 10),
        discharge=date(2026, 7, 13),
    )
    # Earliest procedure on 2026-07-12, admission on 2026-07-10 → mismatch.
    line = _make_proc_line(
        procedure_line_id="PL1",
        claim_id="C1",
        procedure_date=date(2026, 7, 12),
    )

    violations = detect_exam_admission_date_mismatch([claim], [line])

    assert len(violations) == 1
    v = violations[0]
    assert v["claim_id"] == "C1"
    assert v["rule_id"] == "tablo15_22_exam_admission_date_mismatch"
    assert v["severity"] == "error"
    assert v["first_procedure_date"] == date(2026, 7, 12)
    assert v["admission_date"] == date(2026, 7, 10)


def test_exam_admission_date_mismatch_negative() -> None:
    """Inpatient claim whose earliest procedure date == admission date."""
    claim = _make_claim_header(
        claim_id="C1",
        claim_type="yatis",
        admission=date(2026, 7, 10),
        discharge=date(2026, 7, 13),
    )
    line = _make_proc_line(
        procedure_line_id="PL1",
        claim_id="C1",
        procedure_date=date(2026, 7, 10),  # matches admission
    )

    violations = detect_exam_admission_date_mismatch([claim], [line])

    assert violations == []


# ===========================================================================
# Error #20 — detect_missing_drug_barcode
# ===========================================================================


def test_missing_drug_barcode_positive() -> None:
    """Drug line with empty barkod → violation."""
    claim = _make_claim_header(claim_id="C1")
    line = _make_drug_line(drug_claim_line_id="D1", claim_id="C1", barkod="")

    violations = detect_missing_drug_barcode([claim], (line,))

    assert len(violations) == 1
    v = violations[0]
    assert v["claim_id"] == "C1"
    assert v["rule_id"] == "tablo15_20_missing_drug_barcode"
    assert v["severity"] == "error"
    assert v["drug_claim_line_id"] == "D1"


def test_missing_drug_barcode_negative() -> None:
    """Drug line with a populated barkod → no violation."""
    claim = _make_claim_header(claim_id="C1")
    line = _make_drug_line(
        drug_claim_line_id="D1", claim_id="C1", barkod="8690000000001"
    )

    violations = detect_missing_drug_barcode([claim], (line,))

    assert violations == []
