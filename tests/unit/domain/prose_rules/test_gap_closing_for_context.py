"""W1.3 tests — gap_closing _for_context wrappers."""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal
from typing import Any

import pytest

from src.bilun.domain.claims.models import (
    ClaimHeader,
    ClaimDiagnosis,
    DrugClaimLine,
    MaterialClaimLine,
    ProcedureClaimLine,
)
from src.bilun.domain.claims.patient_context import PatientClaimContext
from src.bilun.domain.prose_rules.gap_closing import (
    _build_gap_closing_context,
    check_gap_closing_misc_for_context,
    check_gap_closing_treatment_for_context,
)

pytestmark = pytest.mark.unit


def _make_header(
    *,
    claim_type: str = "ayakta",
    facility_tier: str = "ozel",
    provider_type: str = "sozlesmeli",
    department: str = "genel",
    package_candidate: bool | None = None,
) -> ClaimHeader:
    from datetime import date
    return ClaimHeader(
        claim_id="C1",
        patient_id="P1",
        episode_id="E1",
        claim_type=claim_type,
        facility_tier=facility_tier,
        provider_type=provider_type,
        department=department,
        admission_date=None,
        discharge_date=None,
        claim_start_date=date.today(),
        claim_end_date=date.today(),
        primary_icd10="Z00.0",
        package_candidate=package_candidate,
        expected_total_billed_try=Decimal("100"),
        expected_total_payable_try=Decimal("90"),
        expected_denial_reason="",
        scenario_tag="test",
    )


def _make_ctx(
    *,
    header: ClaimHeader | None = None,
    procedure_lines: tuple[ProcedureClaimLine, ...] = (),
    material_lines: tuple[MaterialClaimLine, ...] = (),
    drug_lines: tuple[DrugClaimLine, ...] = (),
) -> PatientClaimContext:
    h = header or _make_header()
    return PatientClaimContext(
        patient_id="P1",
        claims=(h,),
        procedure_lines=procedure_lines,
        material_lines=material_lines,
        drug_lines=drug_lines,
        diagnoses=(),
    )


def _make_procedure(
    *,
    code: str = "520030",
    category: str = "genel",
) -> ProcedureClaimLine:
    from datetime import date
    return ProcedureClaimLine(
        procedure_line_id="PL1",
        claim_id="C1",
        patient_id="P1",
        episode_id="E1",
        procedure_date=date.today(),
        procedure_code=code,
        procedure_name="Test procedure",
        procedure_category=category,
        quantity=1,
        unit_price_try=Decimal("100"),
        billed_amount_try=Decimal("100"),
        expected_payable_try=Decimal("90"),
        is_package_included=False,
        package_code="",
        surcharge_applicable=False,
        copay_rate_applicable=False,
        denial_reason_expected="",
        rule_trace_expected="",
    )


def test_build_context_maps_header_fields() -> None:
    """_build_gap_closing_context surfaces facility_tier, provider_type, claim_type."""
    ctx = _make_ctx(header=_make_header(facility_tier="devlet", provider_type="sozlesmeli", claim_type="ayakta"))
    context = _build_gap_closing_context(ctx)
    assert context["facility_tier"] == "devlet"
    assert context["provider_type"] == "sozlesmeli"
    assert context["care_setting"] == "outpatient"


def test_build_context_derives_emergency_from_department() -> None:
    """is_emergency derived from 'acil' in department."""
    ctx = _make_ctx(header=_make_header(department="acil servis"))
    context = _build_gap_closing_context(ctx)
    assert context["is_emergency"] is True


def test_build_context_surfaces_procedure_fields() -> None:
    """procedure_category, procedure_code_any surfaced from procedure lines."""
    ctx = _make_ctx(procedure_lines=(_make_procedure(code="520030", category="kardiyoloji"),))
    context = _build_gap_closing_context(ctx)
    assert context["procedure_category"] == "kardiyoloji"
    assert "520030" in (context["procedure_code_any"] or [])


def test_gap_closing_misc_runs_without_crash() -> None:
    """check_gap_closing_misc_for_context returns a list (may be empty for this claim)."""
    ctx = _make_ctx()
    result = check_gap_closing_misc_for_context(ctx)
    assert isinstance(result, list)


def test_gap_closing_treatment_runs_without_crash() -> None:
    """check_gap_closing_treatment_for_context returns a list."""
    ctx = _make_ctx()
    result = check_gap_closing_treatment_for_context(ctx)
    assert isinstance(result, list)


def test_gap_closing_empty_context_returns_empty() -> None:
    """No claims → empty context → no violations."""
    from src.bilun.domain.claims.patient_context import PatientClaimContext
    ctx = PatientClaimContext(
        patient_id="P1",
        claims=(),
        procedure_lines=(),
        material_lines=(),
        drug_lines=(),
        diagnoses=(),
    )
    assert check_gap_closing_misc_for_context(ctx) == []
    assert check_gap_closing_treatment_for_context(ctx) == []
