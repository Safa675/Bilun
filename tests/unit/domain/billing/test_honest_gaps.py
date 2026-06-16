"""Tests for billing honest-gap integrity (no fabricated TRY in heuristics)."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit


def test_orchestrator_total_includes_only_exact_blocks() -> None:
    import src.bilun.domain.billing.orchestrator as billing_mod

    report = billing_mod.compute_patient_billing_report("P1", chapters={"I"})

    # Without claim lines every block is missing inputs, so no money is counted.
    assert report.compliance_adjustment_try == 0.0
    assert report.sgk_uplift_try == 0.0
    assert report.total_recoverable_try == 0.0
    assert report.exactness_status == "missing_exact_inputs"


def test_orchestrator_claim_context_required_constant_defaults_true() -> None:
    from src.bilun.domain.constants import SUT_REQUIRE_CLAIM_LINES

    assert SUT_REQUIRE_CLAIM_LINES is True


def test_exempt_copay_from_claims_reports_waived_amounts_not_heuristic_savings() -> None:
    from decimal import Decimal
    from types import SimpleNamespace

    from src.bilun.domain.billing.claim_copay import optimize_copay_from_claims

    ctx = SimpleNamespace(
        procedure_lines=[
            SimpleNamespace(
                copay_rate_applicable=True,
                procedure_code="P001",
                procedure_name="Visit proc",
                billed_amount_try=Decimal("100"),
                expected_payable_try=Decimal("80"),
            )
        ],
        drug_lines=[],
    )

    result = optimize_copay_from_claims(
        ctx,
        {
            "exempt": True,
            "qualifying_diagnoses": [{"disease": "Diabetes", "range": "E10-E14"}],
        },
    )

    assert result.exactness_status == "exact"
    assert result.visit_copay_savings_try == 20.0
    assert "EK-1A exemption may apply" not in str(result.rate_corrections)
