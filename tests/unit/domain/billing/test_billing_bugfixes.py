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


def test_orchestrator_recoverable_total_counts_rx_once_with_visit_copay(monkeypatch) -> None:
    import src.bilun.domain.billing.orchestrator as billing_mod

    monkeypatch.setattr(
        billing_mod,
        "_optimize_copay",
        lambda *_args, **_kwargs: SimpleNamespace(
            total_copay_savings_try=20.0,
            rx_copay_savings_try=10.0,
            patient_copay_waived_total_try=30.0,
            is_exempt=True,
            exactness_status="exact",
            required_inputs_missing=[],
        ),
    )
    monkeypatch.setattr(
        billing_mod,
        "_recommend_billing_strategy",
        lambda *_args, **_kwargs: SimpleNamespace(
            recommendations=[],
            exactness_status="missing_exact_inputs",
            total_savings=0.0,
            required_inputs_missing=["itemized_billed_procedure_lines"],
        ),
    )
    monkeypatch.setattr(
        billing_mod,
        "_precheck_materials",
        lambda *_args, **_kwargs: SimpleNamespace(
            pre_auth_required=[],
            miat_restricted=[],
            miat_interval_violations=[],
            bundled_separate_billing=[],
            exactness_status="partial_exact",
            required_inputs_missing=["billed_material_codes"],
        ),
    )

    report = billing_mod.compute_patient_billing_report("P1", chapters={"I"})

    assert report.total_recoverable_try == 0.0
    assert report.copay.patient_copay_waived_total_try == 30.0
