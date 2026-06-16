"""Tests for billing bugfixes: copay/drug dedupe and orchestrator totals."""

from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace

import pytest

pytestmark = pytest.mark.unit


def test_copay_total_excludes_rx_component() -> None:
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
        drug_lines=[
            SimpleNamespace(
                billed_amount_try=Decimal("50"),
                expected_payable_try=Decimal("40"),
            )
        ],
    )

    result = optimize_copay_from_claims(
        ctx,
        {"exempt": True, "qualifying_diagnoses": [{"disease": "Diabetes", "range": "E10-E14"}]},
    )

    assert result.visit_copay_savings_try == 20.0
    assert result.rx_copay_savings_try == 10.0
    assert result.total_copay_savings_try == 20.0
    assert result.patient_copay_waived_total_try == 30.0
    assert result.savings_beneficiary == "patient_and_sgk"
    assert result.gap_kind == "exemption_correction"


def test_orchestrator_without_claim_context_returns_missing_inputs() -> None:
    import src.bilun.domain.billing.orchestrator as billing_mod

    report = billing_mod.compute_patient_billing_report("P1", chapters={"I"})

    assert report.exactness_status == "missing_exact_inputs"
    assert report.total_recoverable_try == 0.0
    assert report.copay.exactness_status == "missing_exact_inputs"
    assert report.billing_strategy.exactness_status == "missing_exact_inputs"
    assert report.materials.exactness_status == "missing_exact_inputs"
    assert report.lab.exactness_status == "missing_exact_inputs"
