"""Tests for per-patient recovery summary helpers."""

from __future__ import annotations

import pytest

from src.bilun.domain.billing.orchestrator import (
    patient_recovery_summary_entry,
    patient_recovery_summary_from_payload,
)
from src.bilun.domain.billing.types import BillingActionReport, CopayOptimization, LabOptimization


def test_patient_recovery_summary_from_payload_maps_nested_savings() -> None:
    payload = {
        "patient_id": "P1",
        "total_recoverable_try": 42.5,
        "sgk_uplift_try": 42.5,
        "compliance_adjustment_try": 0.0,
        "priority": "high",
        "action_count": 3,
        "lab": {"total_savings": 1.0},
        "drug": {"total_savings": 0.0},
        "copay": {"total_copay_savings_try": 0.0, "exactness_status": "exact", "is_exempt": False},
        "billing_strategy": {"uplift_savings_try": 41.5},
    }

    summary = patient_recovery_summary_from_payload(payload)

    assert summary == {
        "patient_id": "P1",
        "total_recoverable_try": 42.5,
        "sgk_uplift_try": 42.5,
        "compliance_adjustment_try": 0.0,
        "exemption_gap_try": 0.0,
        "total_opportunity_try": 42.5,
        "priority": "high",
        "action_count": 3,
        "top_action_type": "strategy",
    }


def test_patient_recovery_summary_entry_uses_report_fields() -> None:
    report = BillingActionReport(
        patient_id="P2",
        total_recoverable_try=0.0,
        copay=CopayOptimization(exactness_status="exact", required_inputs_missing=[]),
        action_count=0,
        priority="low",
    )

    summary = patient_recovery_summary_entry(report)

    assert summary["patient_id"] == "P2"
    assert summary["total_recoverable_try"] == 0.0
    assert summary["exemption_gap_try"] == 0.0
    assert summary["total_opportunity_try"] == 0.0
    assert summary["priority"] == "low"
    assert summary["action_count"] == 0
    assert summary["top_action_type"] == "none"


@pytest.mark.parametrize("amount", [None, 0.0, 12.5])
def test_live_and_cached_summaries_preserve_missing_and_zero(amount: float | None) -> None:
    report = BillingActionReport(
        patient_id="SYNTHETIC-MONEY",
        total_recoverable_try=amount,
        sgk_uplift_try=amount,
        compliance_adjustment_try=amount,
        copay=CopayOptimization(exactness_status="exact", required_inputs_missing=[]),
    )
    cached = patient_recovery_summary_from_payload(
        {
            "patient_id": report.patient_id,
            "total_recoverable_try": amount,
            "sgk_uplift_try": amount,
            "compliance_adjustment_try": amount,
            "copay": {"is_exempt": False, "exactness_status": "exact"},
        }
    )
    live = patient_recovery_summary_entry(report)
    for field in (
        "total_recoverable_try",
        "sgk_uplift_try",
        "compliance_adjustment_try",
        "total_opportunity_try",
    ):
        assert live[field] == amount
        assert cached[field] == amount


def test_missing_payload_does_not_create_zero_amounts() -> None:
    summary = patient_recovery_summary_from_payload({"patient_id": "SYNTHETIC-MISSING"})
    for field in (
        "total_recoverable_try",
        "sgk_uplift_try",
        "compliance_adjustment_try",
        "exemption_gap_try",
        "total_opportunity_try",
    ):
        assert summary[field] is None


def test_explicit_zero_uplift_does_not_fall_back_to_positive_hospital_total() -> None:
    summary = patient_recovery_summary_from_payload(
        {
            "total_recoverable_try": 100.0,
            "sgk_uplift_try": 0.0,
            "copay": {"is_exempt": False, "exactness_status": "exact"},
        }
    )
    assert summary["sgk_uplift_try"] == 0.0


def test_empty_copay_context_leaves_all_money_uncomputed() -> None:
    from src.bilun.domain.billing.claim_copay import optimize_copay_from_claims
    from src.bilun.domain.claims.patient_context import PatientClaimContext

    context = PatientClaimContext("SYNTHETIC-EMPTY", (), (), (), (), ())
    copay = optimize_copay_from_claims(context, {"exempt": True})
    assert copay.exactness_status == "missing_exact_inputs"
    for field in (
        "visit_copay_savings_try",
        "rx_copay_savings_try",
        "total_copay_savings_try",
        "patient_copay_waived_total_try",
        "patient_copay_try",
        "ilave_ucret_total_try",
    ):
        assert getattr(copay, field) is None


def test_cohort_can_rank_mixed_missing_positive_and_zero_reports() -> None:
    from src.bilun.domain.billing.cohort_summary import build_cohort_recovery_summary
    from src.bilun.domain.billing.priority import assign_priority_by_percentile

    reports = {
        "missing": BillingActionReport(
            patient_id="missing", lab=LabOptimization(exactness_status="missing_exact_inputs")
        ),
        "positive": BillingActionReport(
            patient_id="positive",
            total_recoverable_try=20.0,
            sgk_uplift_try=20.0,
            copay=CopayOptimization(exactness_status="exact", required_inputs_missing=[]),
        ),
        "zero": BillingActionReport(
            patient_id="zero",
            total_recoverable_try=0.0,
            sgk_uplift_try=0.0,
            copay=CopayOptimization(exactness_status="exact", required_inputs_missing=[]),
        ),
    }
    assign_priority_by_percentile(list(reports.values()))
    summary = build_cohort_recovery_summary(reports, claim_dataset=None)
    assert [row["patient_id"] for row in summary.patient_summaries] == [
        "positive",
        "zero",
        "missing",
    ]
    assert [row["total_opportunity_try"] for row in summary.patient_summaries] == [20.0, 0.0, None]
    assert summary.grand_total_recoverable == 20.0


@pytest.mark.parametrize("missing", [None, 0.0])
def test_copay_partial_sum_is_unknown_but_computed_zero_is_known(missing: float | None) -> None:
    payload = {
        "patient_id": "SYNTHETIC-COPAY",
        "total_recoverable_try": 100.0,
        "copay": {
            "is_exempt": True,
            "exactness_status": "exact",
            "total_copay_savings_try": 20.0,
            "rx_copay_savings_try": missing,
        },
    }
    summary = patient_recovery_summary_from_payload(payload)
    assert summary["exemption_gap_try"] == (None if missing is None else 20.0)
    assert summary["total_opportunity_try"] == (None if missing is None else 120.0)
    payload["copay"]["patient_copay_waived_total_try"] = 0.0
    assert patient_recovery_summary_from_payload(payload)["exemption_gap_try"] == 0.0


def test_n_patients_with_actions_counts_only_positive_recoverable() -> None:
    """n_patients_with_actions counts patients with recoverable > 0 while n_patients stays loaded count (#234)."""
    from dataclasses import asdict

    from src.bilun.api.public_responses import project_public_response
    from src.bilun.domain.billing.cohort_summary import build_cohort_recovery_summary

    three_reports = {
        "P1": BillingActionReport(
            patient_id="P1", total_recoverable_try=150.0, sgk_uplift_try=150.0, action_count=2
        ),
        "P2": BillingActionReport(
            patient_id="P2", total_recoverable_try=75.0, sgk_uplift_try=75.0, action_count=1
        ),
        "P3": BillingActionReport(
            patient_id="P3", total_recoverable_try=0.0, sgk_uplift_try=0.0, action_count=3
        ),
    }
    summary = build_cohort_recovery_summary(three_reports, claim_dataset=None)
    assert summary.n_patients == 3
    assert summary.n_patients_with_actions == 2
    projected = project_public_response(asdict(summary), "get_revenue_recovery")
    assert projected["n_patients"] == 3
    assert projected["n_patients_with_actions"] == 2

    zero_reports = {
        "P1": BillingActionReport(
            patient_id="P1", total_recoverable_try=0.0, sgk_uplift_try=0.0, action_count=1
        ),
        "P2": BillingActionReport(
            patient_id="P2", total_recoverable_try=0.0, sgk_uplift_try=0.0, action_count=0
        ),
    }
    zero_summary = build_cohort_recovery_summary(zero_reports, claim_dataset=None)
    assert zero_summary.n_patients == 2
    assert zero_summary.n_patients_with_actions == 0

