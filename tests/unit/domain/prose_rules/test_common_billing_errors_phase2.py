"""Unit tests for the Phase 2 Tablo 15 common billing error detectors.

Error #9 retains its legacy callable but cannot emit without a period-closure
date; the other detectors cover positive and negative cases.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from src.bilun.domain.claims.models import (
    ClaimHeader,
    DrugClaimLine,
    MaterialClaimLine,
    ProcedureClaimLine,
)
from src.bilun.domain.prose_rules.common_billing_errors import (
    detect_admission_billing_window,
    detect_donor_prep_as_exam,
    detect_drug_quantity_error,
    detect_green_area_bundled_extras,
    detect_inpatient_on_outpatient,
    detect_material_identity_errors,
    detect_material_preauth_missing,
    detect_material_type_missing,
    detect_normal_poliklinik_wrong_method,
    detect_unreported_lab_result,
    detect_vakabasi_wrong_method,
)

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Construction helpers (mirror the pattern in test_common_billing_errors.py).
# ---------------------------------------------------------------------------


def _make_claim_header(
    *,
    claim_id: str = "C1",
    patient_id: str = "P1",
    episode_id: str = "E1",
    claim_type: str = "yatis",
    admission: date | None = date(2026, 7, 10),
    discharge: date | None = date(2026, 7, 13),
    claim_end: date | None = None,
    primary_icd10: str = "K35.8",
    department: str = "genel",
    occupational_context: str = "none",
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
        claim_end_date=claim_end or discharge or date.today(),
        primary_icd10=primary_icd10,
        package_candidate=False,
        expected_total_billed_try=Decimal("1000"),
        expected_total_payable_try=Decimal("900"),
        expected_denial_reason="",
        scenario_tag="test",
        occupational_context=occupational_context,
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
    is_package_included: bool = False,
    lab_billing_status: str = "",
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
        is_package_included=is_package_included,
        package_code="",
        surcharge_applicable=False,
        copay_rate_applicable=False,
        denial_reason_expected="",
        rule_trace_expected="",
        procedure_specialty_code=procedure_specialty_code,
        lab_billing_status=lab_billing_status,
    )


def _make_drug_line(
    *,
    drug_claim_line_id: str = "D1",
    claim_id: str = "C1",
    barkod: str = "8690000000001",
    drug_name: str = "Parasetamol",
    drug_code: str = "PARA1",
    quantity: int = 1,
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
        quantity=quantity,
        unit_price_try=Decimal("100"),
        billed_amount_try=Decimal("100"),
        expected_payable_try=Decimal("72"),
        discount_tier_expected=Decimal("0.28"),
        denial_reason_expected="",
        rule_trace_expected="",
    )


def _make_material_line(
    *,
    material_line_id: str = "ML1",
    claim_id: str = "C1",
    material_code: str = "500000",
    material_name: str = "test material",
    material_type: str = "consumable",
    requires_pre_auth: bool = False,
    barcode_sut_mismatch: bool = False,
    titubb_uts_barcode_documentation_missing: bool = False,
) -> MaterialClaimLine:
    return MaterialClaimLine(
        material_line_id=material_line_id,
        claim_id=claim_id,
        procedure_line_id="",
        patient_id="P1",
        material_date=date(2026, 7, 10),
        material_code=material_code,
        material_name=material_name,
        material_type=material_type,
        specialty_category="general",
        quantity=1,
        unit_price_try=Decimal("500"),
        billed_amount_try=Decimal("500"),
        expected_payable_try=Decimal("500"),
        is_bundled=False,
        requires_pre_auth=requires_pre_auth,
        denial_reason_expected="",
        rule_trace_expected="",
        barcode_sut_mismatch=barcode_sut_mismatch,
        titubb_uts_barcode_documentation_missing=titubb_uts_barcode_documentation_missing,
    )


# ===========================================================================
# Error #3 — detect_vakabasi_wrong_method
# ===========================================================================


def test_vakabasi_wrong_method_positive() -> None:
    """Outpatient exam billed as package → violation."""
    claim = _make_claim_header(
        claim_id="C1",
        claim_type="poliklinik",
        admission=None,
        discharge=None,
    )
    line = _make_proc_line(
        procedure_line_id="PL1",
        claim_id="C1",
        procedure_category="muayene",
        is_package_included=True,  # vakabaşı on an outpatient exam
    )

    violations = detect_vakabasi_wrong_method([claim], [line])

    assert len(violations) == 1
    v = violations[0]
    assert v["claim_id"] == "C1"
    assert v["rule_id"] == "tablo15_3_vakabasi_wrong_method"
    assert v["procedure_line_id"] == "PL1"
    assert v["severity"] == "error"
    assert v["is_package_included"] is True


def test_vakabasi_wrong_method_negative() -> None:
    """Outpatient exam billed itemized (not package) → no violation."""
    claim = _make_claim_header(
        claim_id="C1",
        claim_type="poliklinik",
        admission=None,
        discharge=None,
    )
    line = _make_proc_line(
        procedure_line_id="PL1",
        claim_id="C1",
        procedure_category="muayene",
        is_package_included=False,  # correct per-visit billing
    )

    violations = detect_vakabasi_wrong_method([claim], [line])

    assert violations == []


# ===========================================================================
# Error #4 — detect_normal_poliklinik_wrong_method
# ===========================================================================


def test_normal_poliklinik_wrong_method_positive() -> None:
    """Inpatient package-category line billed itemized → violation."""
    claim = _make_claim_header(
        claim_id="C1",
        claim_type="yatis",
        admission=date(2026, 7, 10),
        discharge=date(2026, 7, 13),
    )
    line = _make_proc_line(
        procedure_line_id="PL1",
        claim_id="C1",
        procedure_category="paket",
        is_package_included=False,  # inpatient package billed itemized — wrong
    )

    violations = detect_normal_poliklinik_wrong_method([claim], [line])

    assert len(violations) == 1
    v = violations[0]
    assert v["claim_id"] == "C1"
    assert v["rule_id"] == "tablo15_4_normal_poliklinik_wrong_method"
    assert v["procedure_line_id"] == "PL1"
    assert v["severity"] == "error"


def test_normal_poliklinik_wrong_method_negative() -> None:
    """Inpatient package line correctly marked package-included → no violation."""
    claim = _make_claim_header(
        claim_id="C1",
        claim_type="yatis",
        admission=date(2026, 7, 10),
        discharge=date(2026, 7, 13),
    )
    line = _make_proc_line(
        procedure_line_id="PL1",
        claim_id="C1",
        procedure_category="paket",
        is_package_included=True,  # correct package billing
    )

    violations = detect_normal_poliklinik_wrong_method([claim], [line])

    assert violations == []


# ===========================================================================
# Error #5 — detect_material_identity_errors
# ===========================================================================


def test_material_identity_errors_positive() -> None:
    """Material line with barcode/SUT mismatch → violation."""
    claim = _make_claim_header(claim_id="C1")
    line = _make_material_line(
        material_line_id="ML1",
        claim_id="C1",
        barcode_sut_mismatch=True,
    )

    violations = detect_material_identity_errors([claim], (line,))

    assert len(violations) == 1
    v = violations[0]
    assert v["claim_id"] == "C1"
    assert v["rule_id"] == "tablo15_5_material_identity_error"
    assert v["severity"] == "error"
    assert v["barcode_sut_mismatch"] is True


def test_material_identity_errors_negative() -> None:
    """Material line with no identity flags → no violation."""
    claim = _make_claim_header(claim_id="C1")
    line = _make_material_line(
        material_line_id="ML1",
        claim_id="C1",
        barcode_sut_mismatch=False,
        titubb_uts_barcode_documentation_missing=False,
    )

    violations = detect_material_identity_errors([claim], (line,))

    assert violations == []


# ===========================================================================
# Error #7 — detect_green_area_bundled_extras
# ===========================================================================


def test_green_area_bundled_extras_positive() -> None:
    """Green-area exam (520021) + another procedure on same claim → violation on the extra."""
    claim = _make_claim_header(claim_id="C1")
    green = _make_proc_line(
        procedure_line_id="PL1",
        claim_id="C1",
        procedure_code="520021",
        procedure_category="muayene",
    )
    extra = _make_proc_line(
        procedure_line_id="PL2",
        claim_id="C1",
        procedure_code="401010",
        procedure_category="muayene",
    )

    violations = detect_green_area_bundled_extras([claim], [green, extra])

    assert len(violations) == 1
    v = violations[0]
    assert v["claim_id"] == "C1"
    assert v["rule_id"] == "tablo15_7_green_area_bundled_extra"
    assert v["procedure_line_id"] == "PL2"
    assert v["procedure_code"] == "401010"
    assert v["green_area_exam_code"] == "520021"


def test_green_area_bundled_extras_same_rule_and_claim_keep_distinct_line_ids() -> None:
    """Two identical extra codes must not collapse to one claim/code identity."""
    claim = _make_claim_header(claim_id="C1")
    green = _make_proc_line(procedure_line_id="PL1", procedure_code="520021")
    extras = [
        _make_proc_line(procedure_line_id=line_id, procedure_code="401010")
        for line_id in ("PL2", "PL3")
    ]

    violations = detect_green_area_bundled_extras([claim], [green, *extras])

    assert [
        (v["rule_id"], v["claim_id"], v["procedure_code"], v["procedure_line_id"])
        for v in violations
    ] == [
        ("tablo15_7_green_area_bundled_extra", "C1", "401010", "PL2"),
        ("tablo15_7_green_area_bundled_extra", "C1", "401010", "PL3"),
    ]


def test_green_area_bundled_extras_negative() -> None:
    """Green-area exam alone (no extras) → no violation."""
    claim = _make_claim_header(claim_id="C1")
    green = _make_proc_line(
        procedure_line_id="PL1",
        claim_id="C1",
        procedure_code="520021",
        procedure_category="muayene",
    )

    violations = detect_green_area_bundled_extras([claim], [green])

    assert violations == []


# ===========================================================================
# Error #9 — detect_admission_billing_window
# ===========================================================================


def test_admission_billing_window_long_stay_is_not_late_submission() -> None:
    """A 70-day stay says nothing about when its invoice period was closed."""
    claim = _make_claim_header(
        claim_id="C1",
        claim_type="yatis",
        admission=date(2026, 5, 1),
        discharge=date(2026, 7, 10),
        claim_end=date(2026, 7, 10),
    )

    violations = detect_admission_billing_window([claim])

    assert violations == []


def test_admission_billing_window_short_stay_cannot_prove_timely_billing() -> None:
    """A short stay also lacks the period-closure evidence needed to decide."""
    claim = _make_claim_header(
        claim_id="C1",
        claim_type="yatis",
        admission=date(2026, 6, 20),
        discharge=date(2026, 7, 10),
        claim_end=date(2026, 7, 10),
    )

    violations = detect_admission_billing_window([claim])

    assert violations == []


def test_admission_billing_window_outpatient_is_not_admission_based() -> None:
    """The Ministry handbook's Table 15 row is not an inpatient stay cap."""
    claim = _make_claim_header(
        claim_type="poliklinik",
        admission=date(2026, 7, 10),
        discharge=date(2026, 7, 10),
        claim_end=date(2026, 7, 10),
    )

    assert detect_admission_billing_window([claim], claim_ids_with_procs={"C1"}) == []


# ===========================================================================
# Error #10 — detect_unreported_lab_result
# ===========================================================================


def test_unreported_lab_result_positive() -> None:
    """Lab line with pending lab_billing_status → violation."""
    claim = _make_claim_header(claim_id="C1")
    line = _make_proc_line(
        procedure_line_id="PL1",
        claim_id="C1",
        procedure_code="901050",
        procedure_category="laboratuvar",
        lab_billing_status="pending",
    )

    violations = detect_unreported_lab_result([claim], [line])

    assert len(violations) == 1
    v = violations[0]
    assert v["claim_id"] == "C1"
    assert v["rule_id"] == "tablo15_10_unreported_lab_result"
    assert v["severity"] == "warning"
    assert v["lab_billing_status"] == "pending"


def test_unreported_lab_result_negative() -> None:
    """Lab line with a populated (reported) status → no violation."""
    claim = _make_claim_header(claim_id="C1")
    line = _make_proc_line(
        procedure_line_id="PL1",
        claim_id="C1",
        procedure_code="901050",
        procedure_category="laboratuvar",
        lab_billing_status="reported",
    )

    violations = detect_unreported_lab_result([claim], [line])

    assert violations == []


# ===========================================================================
# Error #11 — detect_drug_quantity_error
# ===========================================================================


def test_drug_quantity_error_positive() -> None:
    """Drug line with quantity 0 → violation."""
    claim = _make_claim_header(claim_id="C1")
    line = _make_drug_line(drug_claim_line_id="D1", claim_id="C1", quantity=0)

    violations = detect_drug_quantity_error([claim], (line,))

    assert len(violations) == 1
    v = violations[0]
    assert v["claim_id"] == "C1"
    assert v["rule_id"] == "tablo15_11_drug_quantity_error"
    assert v["severity"] == "error"
    assert v["quantity"] == 0


def test_drug_quantity_error_negative() -> None:
    """Drug line with quantity within bounds → no violation."""
    claim = _make_claim_header(claim_id="C1")
    line = _make_drug_line(drug_claim_line_id="D1", claim_id="C1", quantity=10)

    violations = detect_drug_quantity_error([claim], (line,))

    assert violations == []


# ===========================================================================
# Error #15 — detect_material_preauth_missing
# ===========================================================================


def test_material_preauth_missing_positive() -> None:
    """Material requiring pre-auth with no approval → violation."""
    claim = _make_claim_header(claim_id="C1")
    line = _make_material_line(
        material_line_id="ML1",
        claim_id="C1",
        requires_pre_auth=True,
    )

    violations = detect_material_preauth_missing([claim], (line,))

    assert len(violations) == 1
    v = violations[0]
    assert v["claim_id"] == "C1"
    assert v["rule_id"] == "tablo15_15_material_preauth_missing"
    assert v["severity"] == "warning"
    assert v["requires_pre_auth"] is True


def test_material_preauth_missing_negative() -> None:
    """Material not requiring pre-auth → no violation."""
    claim = _make_claim_header(claim_id="C1")
    line = _make_material_line(
        material_line_id="ML1",
        claim_id="C1",
        requires_pre_auth=False,
    )

    violations = detect_material_preauth_missing([claim], (line,))

    assert violations == []


# ===========================================================================
# Error #16 — detect_material_type_missing
# ===========================================================================


def test_material_type_missing_positive() -> None:
    """Material line with empty material_type → violation."""
    claim = _make_claim_header(claim_id="C1")
    line = _make_material_line(
        material_line_id="ML1",
        claim_id="C1",
        material_type="",
    )

    violations = detect_material_type_missing([claim], (line,))

    assert len(violations) == 1
    v = violations[0]
    assert v["claim_id"] == "C1"
    assert v["rule_id"] == "tablo15_16_material_type_missing"
    assert v["severity"] == "error"


def test_material_type_missing_negative() -> None:
    """Material line with a populated material_type → no violation."""
    claim = _make_claim_header(claim_id="C1")
    line = _make_material_line(
        material_line_id="ML1",
        claim_id="C1",
        material_type="implant",
    )

    violations = detect_material_type_missing([claim], (line,))

    assert violations == []


# ===========================================================================
# Error #21 — detect_inpatient_on_outpatient
# ===========================================================================


def test_inpatient_on_outpatient_positive() -> None:
    """Inpatient-only category line on an outpatient claim → violation."""
    claim = _make_claim_header(
        claim_id="C1",
        claim_type="poliklinik",
        admission=None,
        discharge=None,
    )
    line = _make_proc_line(
        procedure_line_id="PL1",
        claim_id="C1",
        procedure_category="cerrahi",  # inpatient-only category
    )

    violations = detect_inpatient_on_outpatient([claim], [line])

    assert len(violations) == 1
    v = violations[0]
    assert v["claim_id"] == "C1"
    assert v["rule_id"] == "tablo15_21_inpatient_on_outpatient"
    assert v["procedure_line_id"] == "PL1"
    assert v["severity"] == "error"
    assert v["care_setting"] == "outpatient"


def test_inpatient_on_outpatient_negative() -> None:
    """Routine outpatient exam on an outpatient claim → no violation."""
    claim = _make_claim_header(
        claim_id="C1",
        claim_type="poliklinik",
        admission=None,
        discharge=None,
    )
    line = _make_proc_line(
        procedure_line_id="PL1",
        claim_id="C1",
        procedure_category="muayene",
    )

    violations = detect_inpatient_on_outpatient([claim], [line])

    assert violations == []


# ===========================================================================
# Error #24 — detect_donor_prep_as_exam
# ===========================================================================


def test_donor_prep_as_exam_positive() -> None:
    """Donor-prep context exam billed as routine muayene → violation."""
    claim = _make_claim_header(
        claim_id="C1",
        claim_type="poliklinik",
        admission=None,
        discharge=None,
        occupational_context="donor",
    )
    line = _make_proc_line(
        procedure_line_id="PL1",
        claim_id="C1",
        procedure_category="muayene",
    )

    violations = detect_donor_prep_as_exam([claim], [line])

    assert len(violations) == 1
    v = violations[0]
    assert v["claim_id"] == "C1"
    assert v["rule_id"] == "tablo15_24_donor_prep_as_exam"
    assert v["procedure_line_id"] == "PL1"
    assert v["severity"] == "warning"
    assert v["occupational_context"] == "donor"


def test_donor_prep_as_exam_negative() -> None:
    """Routine exam with no donor-prep context → no violation."""
    claim = _make_claim_header(
        claim_id="C1",
        claim_type="poliklinik",
        admission=None,
        discharge=None,
        occupational_context="none",
    )
    line = _make_proc_line(
        procedure_line_id="PL1",
        claim_id="C1",
        procedure_category="muayene",
    )

    violations = detect_donor_prep_as_exam([claim], [line])

    assert violations == []


def test_donor_prep_category_on_same_claim_flags_only_distinct_exam_line() -> None:
    claim = _make_claim_header(
        claim_id="C1",
        claim_type="poliklinik",
        admission=None,
        discharge=None,
        occupational_context="none",
    )
    donor_prep = _make_proc_line(
        procedure_line_id="PL-DONOR",
        claim_id="C1",
        procedure_category="donor_hazirligi",
    )
    exam = _make_proc_line(
        procedure_line_id="PL-EXAM",
        claim_id="C1",
        procedure_category="muayene",
    )

    violations = detect_donor_prep_as_exam([claim], [donor_prep, exam])

    assert len(violations) == 1
    assert violations[0]["procedure_line_id"] == "PL-EXAM"
    assert violations[0]["severity"] == "warning"
    assert violations[0]["occupational_context"] == "none"


def test_donor_prep_category_without_exam_is_not_violation() -> None:
    claim = _make_claim_header(occupational_context="none")
    donor_prep = _make_proc_line(procedure_category="donor_prep")

    assert detect_donor_prep_as_exam([claim], [donor_prep]) == []


def test_donor_prep_category_on_other_claim_does_not_mark_exam() -> None:
    exam_claim = _make_claim_header(claim_id="C1", occupational_context="none")
    donor_claim = _make_claim_header(claim_id="C2", occupational_context="none")
    exam = _make_proc_line(
        procedure_line_id="PL-EXAM",
        claim_id="C1",
        procedure_category="muayene",
    )
    donor_prep = _make_proc_line(
        procedure_line_id="PL-DONOR",
        claim_id="C2",
        procedure_category="donor_hazirligi",
    )

    assert detect_donor_prep_as_exam(
        [exam_claim, donor_claim], [exam, donor_prep]
    ) == []
