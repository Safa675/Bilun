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


def test_billing_strategy_without_claim_context_stays_unavailable() -> None:
    from src.bilun.domain.billing.strategy import _recommend_billing_strategy

    result = _recommend_billing_strategy("P1", {"I"})
    assert result.exactness_status == "missing_exact_inputs"
