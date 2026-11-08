"""El Kitabı Tablo 15 — 24 Most Common Billing Errors, top 5 detectors.

This integration test drives the supported detectors implemented for "El Kitabı
Tablo 15 — En Sık Yapılan 24 Faturalandırma Hatası" through the unified
``analyze_claim(ctx)`` engine (the same entry point the billing orchestrator
and ``validate_claim`` adapter consume), rather than calling each detector
in isolation. The goal is to confirm that each scenario, built from typed
claim models, surfaces its expected violation through the full motor
pipeline. It also checks that the unavailable #22 candidate emits no false
legacy violation.

**Scenarios (Tablo 15):**
- #2  Same-specialty exam within 10 days  → ``tablo15_2_duplicate_exam_10day``
- #8  Missing diagnosis on takip          → ``tablo15_8_missing_diagnosis``
- #12 Duplicate tests within 7 days       → ``tablo15_12_duplicate_test``
- #20 Missing drug barcode                → ``tablo15_20_missing_drug_barcode``
- #22 Outpatient exam/acceptance date     → unavailable without acceptance data

The Tablo 15 detectors are gated on a non-empty ``patient_id`` (see
``engine.analyze_claim``), so every scenario uses ``patient_id="TABLO15-P1"``.
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
from src.bilun.domain.claims.patient_context import PatientClaimContext
from src.bilun.domain.billing.engine import analyze_claim

pytestmark = pytest.mark.unit

_PATIENT_ID = "TABLO15-P1"


# ── Helpers ─────────────────────────────────────────────────────────────────


def _make_outpatient_claim(
    claim_id: str,
    *,
    primary_icd10: str = "J03.9",  # Acute tonsillitis, unspecified
    service_date: date = date(2026, 7, 1),
    claim_type: str = "ayakta",
) -> ClaimHeader:
    """A minimal outpatient ClaimHeader that passes the engine gate."""
    return ClaimHeader(
        claim_id=claim_id,
        patient_id=_PATIENT_ID,
        episode_id=f"{claim_id}-E",
        claim_type=claim_type,
        facility_tier="devlet",
        provider_type="sozlesmeli",
        department="ic",
        admission_date=None,
        discharge_date=None,
        claim_start_date=service_date,
        claim_end_date=service_date,
        primary_icd10=primary_icd10,
        expected_total_billed_try=Decimal("500"),
        expected_total_payable_try=Decimal("500"),
        expected_denial_reason="",
        scenario_tag="elkitabi_tablo15",
    )


def _make_exam_line(
    line_id: str,
    claim_id: str,
    service_date: date,
    *,
    specialty: str = "dahiliye",
) -> ProcedureClaimLine:
    """An outpatient muayene (exam) procedure line."""
    return ProcedureClaimLine(
        procedure_line_id=line_id,
        claim_id=claim_id,
        patient_id=_PATIENT_ID,
        episode_id=f"{claim_id}-E",
        procedure_date=service_date,
        procedure_code="720010",  # Poliklinik muayenesi
        procedure_name="Poliklinik Muayenesi",
        procedure_category="muayene",
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
        procedure_specialty_code=specialty,
    )


def _make_test_line(
    line_id: str,
    claim_id: str,
    service_date: date,
    *,
    code: str = "901320",  # Glikoz (kan şekeri)
) -> ProcedureClaimLine:
    """A lab test procedure line (laboratuvar category)."""
    return ProcedureClaimLine(
        procedure_line_id=line_id,
        claim_id=claim_id,
        patient_id=_PATIENT_ID,
        episode_id=f"{claim_id}-E",
        procedure_date=service_date,
        procedure_code=code,
        procedure_name="Glikoz",
        procedure_category="laboratuvar",
        quantity=1,
        unit_price_try=Decimal("20"),
        billed_amount_try=Decimal("20"),
        expected_payable_try=Decimal("20"),
        is_package_included=False,
        package_code="",
        surcharge_applicable=False,
        copay_rate_applicable=False,
        denial_reason_expected="",
        rule_trace_expected="",
    )


def _rule_ids(violations: list[dict]) -> set[str]:
    return {v.get("rule_id", "") for v in violations}


# ── Test 1 — Missing diagnosis on takip (#8) ────────────────────────────────


def test_tablo15_missing_diagnosis() -> None:
    """#8: A claim with an empty primary_icd10 must be flagged.

    The ``detect_missing_diagnosis`` motor is wired (unconditionally, no
    procedure-line gate) into ``analyze_claim`` whenever ``patient_id`` is
    set, so a header-only context with ``primary_icd10=""`` should produce
    a ``tablo15_8_missing_diagnosis`` violation.
    """
    claim = _make_outpatient_claim("TABLO15-C1", primary_icd10="")
    ctx = PatientClaimContext(
        patient_id=_PATIENT_ID,
        claims=(claim,),
        procedure_lines=(),
        material_lines=(),
        drug_lines=(),
        diagnoses=(),
    )

    violations = analyze_claim(ctx)

    assert "tablo15_8_missing_diagnosis" in _rule_ids(violations), (
        f"expected missing_diagnosis violation, got rule_ids={_rule_ids(violations)}"
    )


# ── Test 2 — Same-specialty exam within 10 days (#2) ────────────────────────


def test_tablo15_duplicate_exam_10day() -> None:
    """#2: Two outpatient exams, same specialty, ≤10 days apart, two bills.

    Build two outpatient claims for the same patient, each with one
    ``muayene`` line in specialty ``dahiliye``, dated 5 days apart. The
    second claim must surface ``tablo15_2_duplicate_exam_10day``.
    """
    claim1 = _make_outpatient_claim("TABLO15-C2A", service_date=date(2026, 7, 1))
    claim2 = _make_outpatient_claim("TABLO15-C2B", service_date=date(2026, 7, 6))

    exam1 = _make_exam_line("TABLO15-EX1", "TABLO15-C2A", date(2026, 7, 1))
    exam2 = _make_exam_line("TABLO15-EX2", "TABLO15-C2B", date(2026, 7, 6))

    ctx = PatientClaimContext(
        patient_id=_PATIENT_ID,
        claims=(claim1, claim2),
        procedure_lines=(exam1, exam2),
        material_lines=(),
        drug_lines=(),
        diagnoses=(),
    )

    violations = analyze_claim(ctx)

    assert "tablo15_2_duplicate_exam_10day" in _rule_ids(violations), (
        f"expected duplicate_exam_10day violation, got rule_ids={_rule_ids(violations)}"
    )


# ── Test 3 — Duplicate tests within 7 days (#12) ────────────────────────────


def test_tablo15_duplicate_tests() -> None:
    """#12: The same lab test on two different claims within 7 days.

    Two outpatient claims for the same patient, each carrying the same
    ``laboratuvar`` procedure code (``901320``), 4 days apart. The later
    line must surface ``tablo15_12_duplicate_test``.
    """
    claim1 = _make_outpatient_claim("TABLO15-C3A", service_date=date(2026, 7, 1))
    claim2 = _make_outpatient_claim("TABLO15-C3B", service_date=date(2026, 7, 5))

    test1 = _make_test_line("TABLO15-T1", "TABLO15-C3A", date(2026, 7, 1))
    test2 = _make_test_line("TABLO15-T2", "TABLO15-C3B", date(2026, 7, 5))

    ctx = PatientClaimContext(
        patient_id=_PATIENT_ID,
        claims=(claim1, claim2),
        procedure_lines=(test1, test2),
        material_lines=(),
        drug_lines=(),
        diagnoses=(),
    )

    violations = analyze_claim(ctx)

    assert "tablo15_12_duplicate_test" in _rule_ids(violations), (
        f"expected duplicate_test violation, got rule_ids={_rule_ids(violations)}"
    )


# ── Test 4 — Missing drug barcode (#20) ─────────────────────────────────────


def _make_drug_line(
    line_id: str,
    claim_id: str,
    service_date: date,
    *,
    barkod: str = "8699786200014",
    drug_code: str = "A10AE01",
    drug_name: str = "İnsülin Glargin",
) -> DrugClaimLine:
    """A minimally-valid DrugClaimLine (all required fields supplied)."""
    return DrugClaimLine(
        drug_claim_line_id=line_id,
        prescription_id=f"{claim_id}-RX",
        claim_id=claim_id,
        patient_id=_PATIENT_ID,
        episode_id=f"{claim_id}-E",
        drug_claim_date=service_date,
        drug_name=drug_name,
        drug_code=drug_code,
        barkod=barkod,
        equivalence_group="",
        quantity=1,
        unit_price_try=Decimal("150"),
        billed_amount_try=Decimal("150"),
        expected_payable_try=Decimal("150"),
        discount_tier_expected=Decimal("0"),
        denial_reason_expected="",
        rule_trace_expected="",
    )


def test_tablo15_missing_drug_barcode() -> None:
    """#20: A drug line whose barkod is empty must be flagged.

    The ``detect_missing_drug_barcode`` motor runs whenever ``ctx.drug_lines``
    is non-empty, so a context with one DrugClaimLine carrying ``barkod=""``
    must surface ``tablo15_20_missing_drug_barcode``.
    """
    claim = _make_outpatient_claim("TABLO15-C4", service_date=date(2026, 7, 1))
    drug = _make_drug_line("TABLO15-D1", "TABLO15-C4", date(2026, 7, 1), barkod="")

    ctx = PatientClaimContext(
        patient_id=_PATIENT_ID,
        claims=(claim,),
        procedure_lines=(),
        material_lines=(),
        drug_lines=(drug,),
        diagnoses=(),
    )

    violations = analyze_claim(ctx)

    assert "tablo15_20_missing_drug_barcode" in _rule_ids(violations), (
        f"expected missing_drug_barcode violation, got rule_ids={_rule_ids(violations)}"
    )


# ── Test 5 — Unsupported exam/acceptance date inference (#22) ──────────────


def test_tablo15_inpatient_surgery_does_not_trigger_outpatient_exam_rule() -> None:
    """#22 must not turn a later inpatient operation into an exam-date error."""
    admission = date(2026, 7, 10)
    discharge = date(2026, 7, 14)
    claim = ClaimHeader(
        claim_id="TABLO15-C5",
        patient_id=_PATIENT_ID,
        episode_id="TABLO15-C5-E",
        claim_type="yatis",
        facility_tier="devlet",
        provider_type="sozlesmeli",
        department="genel_cerrahi",
        admission_date=admission,
        discharge_date=discharge,
        claim_start_date=admission,
        claim_end_date=discharge,
        primary_icd10="",  # keep a separate real missing-diagnosis finding
        expected_total_billed_try=Decimal("5000"),
        expected_total_payable_try=Decimal("5000"),
        expected_denial_reason="",
        scenario_tag="elkitabi_tablo15",
    )
    # Inpatient surgery two days after admission is not a Tablo 15 #22 exam.
    proc = ProcedureClaimLine(
        procedure_line_id="TABLO15-P5",
        claim_id="TABLO15-C5",
        patient_id=_PATIENT_ID,
        episode_id="TABLO15-C5-E",
        procedure_date=date(2026, 7, 12),
        procedure_code="601010",
        procedure_name="Surgical procedure",
        procedure_category="cerrahi",
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

    ctx = PatientClaimContext(
        patient_id=_PATIENT_ID,
        claims=(claim,),
        procedure_lines=(proc,),
        material_lines=(),
        drug_lines=(),
        diagnoses=(),
    )

    violations = analyze_claim(ctx)

    assert "tablo15_8_missing_diagnosis" in _rule_ids(violations)
    assert "tablo15_22_exam_admission_date_mismatch" not in _rule_ids(violations)
