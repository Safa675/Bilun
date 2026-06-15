"""Tests for the claim-line based lab optimizer.

Session-fraction / seans kesir oranı rules are intentionally NOT applied to lab
tests because SUT §2.2.2.A(5) / §2.2.2.B refer to surgical/medical procedures
with "kesi" (incision), not laboratory "tetkikler".
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

import pytest

pytestmark = pytest.mark.unit


@dataclass(frozen=True)
class _MockProcedureClaimLine:
    procedure_line_id: str
    claim_id: str
    patient_id: str
    episode_id: str
    procedure_date: str
    procedure_code: str
    procedure_name: str
    procedure_category: str
    quantity: int
    unit_price_try: Decimal
    billed_amount_try: Decimal
    expected_payable_try: Decimal
    is_package_included: bool = False
    package_code: str = ""
    surcharge_applicable: bool = False
    copay_rate_applicable: bool = False
    denial_reason_expected: str = ""
    rule_trace_expected: str = ""
    lab_result_id: str = ""
    lab_billing_status: str = ""
    procedure_specialty_code: str = ""


@dataclass(frozen=True)
class _MockClaimHeader:
    claim_id: str
    patient_id: str
    episode_id: str
    claim_start_date: str = ""
    admission_date: str | None = None


@dataclass(frozen=True)
class _MockPatientClaimContext:
    patient_id: str
    claims: tuple[Any, ...]
    procedure_lines: tuple[Any, ...]
    material_lines: tuple[Any, ...] = ()
    drug_lines: tuple[Any, ...] = ()
    diagnoses: tuple[Any, ...] = ()
    performed_procedure_lines: tuple[Any, ...] = ()
    medula_rejection_events: tuple[Any, ...] = ()


def _lab_line(
    *,
    code: str,
    name: str,
    billed: str,
    episode: str = "V1",
    claim: str = "C1",
) -> _MockProcedureClaimLine:
    return _MockProcedureClaimLine(
        procedure_line_id=f"L-{code}",
        claim_id=claim,
        patient_id="P1",
        episode_id=episode,
        procedure_date="2024-01-01",
        procedure_code=code,
        procedure_name=name,
        procedure_category="laboratuvar",
        quantity=1,
        unit_price_try=Decimal(billed),
        billed_amount_try=Decimal(billed),
        expected_payable_try=Decimal("0"),
    )


def test_one_billed_lab_per_visit_no_flag() -> None:
    from src.bilun.domain.billing.claim_lab import _optimize_lab_billing_from_claims

    ctx = _MockPatientClaimContext(
        patient_id="P1",
        claims=(_MockClaimHeader("C1", "P1", "V1"),),
        procedure_lines=(_lab_line(code="L112180", name="Kortizol", billed="12.84"),),
    )
    result = _optimize_lab_billing_from_claims(ctx)
    assert result.hemogram_bundling_savings == 0.0
    assert result.session_fraction_savings == 0.0
    assert not result.flagged_tests


def test_multiple_distinct_labs_same_visit_no_session_fraction_flag() -> None:
    """Session-fraction rules do not apply to lab tests."""
    from src.bilun.domain.billing.claim_lab import _optimize_lab_billing_from_claims

    ctx = _MockPatientClaimContext(
        patient_id="P1",
        claims=(_MockClaimHeader("C1", "P1", "V1"),),
        procedure_lines=(
            _lab_line(code="L112180", name="Kortizol", billed="12.84"),
            _lab_line(code="L120000", name="İdrar", billed="7.89"),
            _lab_line(code="L103430", name="HLA", billed="888.97"),
        ),
    )
    result = _optimize_lab_billing_from_claims(ctx)
    assert result.session_fraction_savings == 0.0
    assert not any(
        f["flag_type"] == "session_fraction_overbilling" for f in result.flagged_tests
    )


def test_hemogram_bundling_on_claim_lines() -> None:
    from src.bilun.domain.billing.claim_lab import _optimize_lab_billing_from_claims

    ctx = _MockPatientClaimContext(
        patient_id="P1",
        claims=(_MockClaimHeader("C1", "P1", "V1"),),
        procedure_lines=(
            _lab_line(code="L101010", name="Hemoglobin", billed="10.00"),
            _lab_line(code="L101020", name="Hematokrit", billed="10.00"),
        ),
    )
    result = _optimize_lab_billing_from_claims(ctx)
    assert result.hemogram_bundling_savings > 0.0
    assert any(f["flag_type"] == "hemogram_unbundling" for f in result.flagged_tests)


def test_no_hemogram_bundling_for_single_cbc_line() -> None:
    from src.bilun.domain.billing.claim_lab import _optimize_lab_billing_from_claims

    ctx = _MockPatientClaimContext(
        patient_id="P1",
        claims=(_MockClaimHeader("C1", "P1", "V1"),),
        procedure_lines=(_lab_line(code="L107020", name="Tam Kan Sayımı (Hemogram)", billed="19.73"),),
    )
    result = _optimize_lab_billing_from_claims(ctx)
    assert result.hemogram_bundling_savings == 0.0
    assert not result.flagged_tests
