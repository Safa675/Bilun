"""Billing integration with exact claim lines."""

from __future__ import annotations

import pytest

from src.bilun.domain.billing.orchestrator import compute_patient_billing_report
from src.bilun.domain.claims import build_patient_claim_context, load_sut_claim_dataset

pytestmark = pytest.mark.unit


def test_billing_report_uses_exact_drug_and_copay_from_claim_context() -> None:
    dataset = load_sut_claim_dataset()
    patient_id = "SENTETIK-HASTA-0001"
    ctx = build_patient_claim_context(patient_id, dataset)
    assert ctx is not None

    report = compute_patient_billing_report(
        patient_id,
        claim_context=ctx,
        copay_exemption={
            "exempt": True,
            "qualifying_diagnoses": [{"disease": "Hypertension", "range": "I10-I15"}],
        },
        chapters={"I"},
    )

    assert report.drug.exactness_status == "exact"
    assert report.copay.exactness_status == "exact"
    assert report.billing_strategy.exactness_status == "exact"
    assert report.drug.generic_substitution_savings >= 0.0


def test_exempt_patient_drug_and_rx_copay_not_double_counted_in_total() -> None:
    dataset = load_sut_claim_dataset()
    patient_id = "SENTETIK-HASTA-0001"
    ctx = build_patient_claim_context(patient_id, dataset)
    assert ctx is not None

    report = compute_patient_billing_report(
        patient_id,
        claim_context=ctx,
        copay_exemption={
            "exempt": True,
            "qualifying_diagnoses": [{"disease": "Hypertension", "range": "I10-I15"}],
        },
        chapters={"I"},
    )

    rx = report.copay.rx_copay_savings_try
    visit = report.copay.total_copay_savings_try
    drug = report.drug.generic_substitution_savings

    if rx > 0:
        assert drug == 0.0

    expected_floor = visit + rx + report.lab.total_savings
    if report.billing_strategy.exactness_status == "exact":
        expected_floor += report.billing_strategy.total_savings

    assert report.total_recoverable_try == round(expected_floor, 2)
    assert report.copay.total_copay_savings_try == report.copay.visit_copay_savings_try


def test_billing_strategy_without_claim_context_stays_unavailable() -> None:
    from src.bilun.domain.billing.strategy import _recommend_billing_strategy

    result = _recommend_billing_strategy("P1", set("I"))
    assert result.exactness_status == "missing_exact_inputs"
    assert len(result.recommendations) == 1
    assert result.recommendations[0]["recommendation"] == "review_package_eligibility"
