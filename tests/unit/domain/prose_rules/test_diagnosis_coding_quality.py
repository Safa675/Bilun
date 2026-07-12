"""Unit tests for the ICD-10 diagnosis-coding quality detectors.

One or more positive (error detected) and negative (no error) test per
detector, plus coverage of the ``claim_ids_with_procs`` gate and the
``_for_context`` wrappers:

- ``detect_never_principal_diagnosis``          (A1)
- ``detect_diagnosis_procedure_mismatch``       (A2)
- ``detect_unnecessary_additional_diagnosis``   (A3)
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest

from src.bilun.domain.claims.models import (
    ClaimDiagnosis,
    ClaimHeader,
    ProcedureClaimLine,
)
from src.bilun.domain.prose_rules.diagnosis_coding_quality import (
    detect_diagnosis_procedure_mismatch,
    detect_diagnosis_procedure_mismatch_for_context,
    detect_never_principal_diagnosis,
    detect_never_principal_diagnosis_for_context,
    detect_unnecessary_additional_diagnosis,
    detect_unnecessary_additional_diagnosis_for_context,
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
    claim_type: str = "poliklinik",
    admission: date | None = None,
    discharge: date | None = None,
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
        claim_start_date=admission or date(2026, 1, 1),
        claim_end_date=discharge or date(2026, 1, 1),
        primary_icd10=primary_icd10,
        package_candidate=False,
        expected_total_billed_try=Decimal("100"),
        expected_total_payable_try=Decimal("90"),
        expected_denial_reason="",
        scenario_tag="test",
    )


def _make_proc_line(
    *,
    procedure_line_id: str = "PL1",
    claim_id: str = "C1",
    procedure_code: str = "401010",
    procedure_category: str = "muayene",
    procedure_date: date = date(2026, 1, 1),
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
        quantity=1,
        unit_price_try=Decimal("100"),
        billed_amount_try=Decimal("100"),
        expected_payable_try=Decimal("100"),
        is_package_included=False,
        package_code="",
        surcharge_applicable=False,
        copay_rate_applicable=False,
        denial_reason_expected="",
        rule_trace_expected="",
    )


def _make_diagnosis(
    *,
    diagnosis_id: str = "DX1",
    claim_id: str = "C1",
    icd10_code: str = "K35.8",
    is_primary: bool = False,
    diagnosis_role: str = "ek",
) -> ClaimDiagnosis:
    return ClaimDiagnosis(
        diagnosis_id=diagnosis_id,
        claim_id=claim_id,
        patient_id="P1",
        episode_id="E1",
        icd10_code=icd10_code,
        is_primary=is_primary,
        diagnosis_role=diagnosis_role,
        diagnosis_date=date(2026, 1, 1),
        exemption_eligible=False,
    )


# ===========================================================================
# A1 — detect_never_principal_diagnosis
# ===========================================================================


def test_never_principal_r_code_positive() -> None:
    """R69 (unknown causes of morbidity) as principal → violation."""
    claim = _make_claim_header(claim_id="C1", primary_icd10="R69")

    violations = detect_never_principal_diagnosis([claim])

    assert len(violations) == 1
    v = violations[0]
    assert v["claim_id"] == "C1"
    assert v["rule_id"] == "never_principal_diagnosis_blocklist"
    assert v["type"] == "diagnosis_quality"
    assert v["severity"] == "error"
    assert v["primary_icd10"] == "R69"
    assert v["savings_category"] == "sgk_uplift"
    assert v["savings_basis"] == "sourced"


def test_never_principal_z_history_positive() -> None:
    """Z85 (personal history of malignant neoplasm) as principal → violation."""
    claim = _make_claim_header(claim_id="C2", primary_icd10="Z85.3")

    violations = detect_never_principal_diagnosis([claim])

    assert len(violations) == 1
    assert violations[0]["claim_id"] == "C2"
    assert violations[0]["primary_icd10"] == "Z85.3"
    assert "kişisel hastalık öyküsü" in violations[0]["reason"]


def test_never_principal_external_cause_positive() -> None:
    """W19 (fall on same level) external-cause code as principal → violation."""
    claim = _make_claim_header(claim_id="C3", primary_icd10="W19")

    violations = detect_never_principal_diagnosis([claim])

    assert len(violations) == 1
    assert violations[0]["primary_icd10"] == "W19"


def test_never_principal_definitive_code_negative() -> None:
    """K358 / K35.8 (appendicitis) as principal → no violation."""
    claim = _make_claim_header(claim_id="C4", primary_icd10="K358")

    violations = detect_never_principal_diagnosis([claim])

    assert violations == []


def test_never_principal_empty_skipped() -> None:
    """Empty primary_icd10 is skipped (owned by detect_missing_diagnosis)."""
    claim = _make_claim_header(claim_id="C5", primary_icd10="")

    violations = detect_never_principal_diagnosis([claim])

    assert violations == []


def test_never_principal_claim_ids_gate() -> None:
    """claim_ids_with_procs filters out claims not carrying procedures."""
    flagged = _make_claim_header(claim_id="C1", primary_icd10="R69")
    gated = _make_claim_header(claim_id="C2", primary_icd10="R10")

    violations = detect_never_principal_diagnosis(
        [flagged, gated], claim_ids_with_procs={"C1"}
    )

    assert {v["claim_id"] for v in violations} == {"C1"}


# ===========================================================================
# A2 — detect_diagnosis_procedure_mismatch
# ===========================================================================


def test_dx_procedure_mismatch_f_orthopedic_positive() -> None:
    """F-code (mental health) principal + orthopedic surgery (60xxxx) → warning."""
    claim = _make_claim_header(claim_id="C1", primary_icd10="F32.9")
    line = _make_proc_line(
        procedure_line_id="PL1",
        claim_id="C1",
        procedure_code="601020",  # orthopedic surgery family
        procedure_category="ortopedi",
    )

    violations = detect_diagnosis_procedure_mismatch([claim], [line])

    assert len(violations) == 1
    v = violations[0]
    assert v["claim_id"] == "C1"
    assert v["rule_id"] == "dx_procedure_mismatch"
    assert v["severity"] == "warning"
    assert v["procedure_code"] == "601020"
    assert v["primary_icd10"] == "F32.9"


def test_dx_procedure_mismatch_consistent_negative() -> None:
    """F-code principal + a mental-health-consistent procedure → no violation."""
    claim = _make_claim_header(claim_id="C1", primary_icd10="F32.9")
    line = _make_proc_line(
        procedure_line_id="PL1",
        claim_id="C1",
        procedure_code="901050",  # lab code, not ortho/cardiac/screening
        procedure_category="laboratuvar",
    )

    violations = detect_diagnosis_procedure_mismatch([claim], [line])

    assert violations == []


def test_dx_procedure_mismatch_no_procedure_negative() -> None:
    """A claim with no procedure lines is never flagged."""
    claim = _make_claim_header(claim_id="C1", primary_icd10="F32.9")

    violations = detect_diagnosis_procedure_mismatch([claim], [])

    assert violations == []


# ===========================================================================
# A3 — detect_unnecessary_additional_diagnosis
# ===========================================================================


def test_unnecessary_additional_same_chapter_positive() -> None:
    """K35.8 (definitive) + R10.4 (digestive symptom) same chapter → warning."""
    claim = _make_claim_header(claim_id="C1", primary_icd10="K35.8")
    definitive = _make_diagnosis(
        diagnosis_id="DX1", claim_id="C1", icd10_code="K35.8", is_primary=True
    )
    symptom = _make_diagnosis(
        diagnosis_id="DX2", claim_id="C1", icd10_code="R10.4", diagnosis_role="ek"
    )

    violations = detect_unnecessary_additional_diagnosis(
        [claim], [definitive, symptom]
    )

    assert len(violations) == 1
    v = violations[0]
    assert v["claim_id"] == "C1"
    assert v["rule_id"] == "unnecessary_additional_diagnosis"
    assert v["severity"] == "warning"
    assert v["redundant_icd10"] == "R10.4"
    assert "K35.8" in v["paired_definitive_icd10"]


def test_unnecessary_additional_different_chapter_negative() -> None:
    """J20 (bronchitis) + R10.4 (abdominal pain) different chapters → no flag."""
    claim = _make_claim_header(claim_id="C1", primary_icd10="J20.9")
    definitive = _make_diagnosis(
        diagnosis_id="DX1", claim_id="C1", icd10_code="J20.9", is_primary=True
    )
    symptom = _make_diagnosis(
        diagnosis_id="DX2", claim_id="C1", icd10_code="R10.4", diagnosis_role="ek"
    )

    violations = detect_unnecessary_additional_diagnosis(
        [claim], [definitive, symptom]
    )

    assert violations == []


def test_unnecessary_additional_general_r_code_negative() -> None:
    """General R-symptom (R50 fever) maps to no chapter → never flagged."""
    claim = _make_claim_header(claim_id="C1", primary_icd10="K35.8")
    definitive = _make_diagnosis(
        diagnosis_id="DX1", claim_id="C1", icd10_code="K35.8", is_primary=True
    )
    general_fever = _make_diagnosis(
        diagnosis_id="DX2", claim_id="C1", icd10_code="R50.9", diagnosis_role="ek"
    )

    violations = detect_unnecessary_additional_diagnosis(
        [claim], [definitive, general_fever]
    )

    assert violations == []


# ===========================================================================
# _for_context wrappers
# ===========================================================================


def test_for_context_wrappers_delegate() -> None:
    """The three _for_context wrappers delegate to their detector functions."""
    claim = _make_claim_header(claim_id="C1", primary_icd10="R69")
    proc = _make_proc_line(
        procedure_line_id="PL1", claim_id="C1", procedure_code="601020"
    )
    definitive = _make_diagnosis(
        diagnosis_id="DX1", claim_id="C1", icd10_code="K35.8", is_primary=True
    )
    symptom = _make_diagnosis(
        diagnosis_id="DX2", claim_id="C1", icd10_code="R10.4"
    )
    ctx = SimpleNamespace(
        claims=(claim,),
        procedure_lines=(proc,),
        diagnoses=(definitive, symptom),
    )

    never_principal = detect_never_principal_diagnosis_for_context(ctx)
    mismatch = detect_diagnosis_procedure_mismatch_for_context(ctx)
    unnecessary = detect_unnecessary_additional_diagnosis_for_context(ctx)

    assert len(never_principal) == 1
    assert never_principal[0]["rule_id"] == "never_principal_diagnosis_blocklist"
    # R69 is not F/O/S/T, so no mismatch on this claim.
    assert mismatch == []
    assert len(unnecessary) == 1
    assert unnecessary[0]["rule_id"] == "unnecessary_additional_diagnosis"
