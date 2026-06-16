"""Billing integration with exact claim lines."""

from __future__ import annotations

import pytest

from src.bilun.domain.billing.orchestrator import compute_patient_billing_report
from src.bilun.domain.claims import build_patient_claim_context, load_sut_claim_dataset

pytestmark = pytest.mark.unit


def test_billing_report_uses_exact_copay_from_claim_context() -> None:
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

    assert report.copay.exactness_status == "exact"
    assert report.billing_strategy.exactness_status == "exact"


def test_exempt_patient_rx_copay_in_total() -> None:
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

    assert report.total_recoverable_try == report.sgk_uplift_try
    assert report.sgk_uplift_try == round(
        report.billing_strategy.uplift_savings_try
        + report.session_uplift.confirmed_uplift_try
        + report.drg_uplift.confirmed_uplift_try
        + report.blood_uplift.confirmed_uplift_try
        + report.material_uplift.confirmed_uplift_try
        + report.procedure_addon_uplift.confirmed_uplift_try,
        2,
    )
    assert report.copay.patient_copay_waived_total_try == round(visit + rx, 2)
    assert report.copay.total_copay_savings_try == report.copay.visit_copay_savings_try


def test_billing_strategy_without_claim_context_stays_unavailable() -> None:
    report = compute_patient_billing_report("P1", chapters={"I"})

    assert report.billing_strategy.exactness_status == "missing_exact_inputs"
    assert report.billing_strategy.recommendations == []
    assert report.total_recoverable_try == 0.0
