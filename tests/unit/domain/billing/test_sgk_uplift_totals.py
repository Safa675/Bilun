"""SGK uplift vs compliance KPI split (Phase 0)."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from src.bilun.domain.billing.orchestrator import (
    _finalize_report_totals,
    _sum_sgk_uplift_try,
)
from src.bilun.domain.billing.types import (
    BillingActionReport,
    BillingStrategyRecommendation,
    LabOptimization,
    SessionPricingUplift,
)

pytestmark = pytest.mark.unit


def test_lab_savings_are_compliance_not_sgk_uplift() -> None:
    report = BillingActionReport(
        patient_id="P1",
        lab=LabOptimization(
            hemogram_bundling_savings=42.0,
            session_fraction_savings=8.0,
            exactness_status="exact",
        ),
        billing_strategy=BillingStrategyRecommendation(exactness_status="exact"),
        session_uplift=SessionPricingUplift(exactness_status="exact"),
    )
    _finalize_report_totals(report)
    assert report.compliance_adjustment_try == 50.0
    assert report.sgk_uplift_try == 0.0
    assert report.total_recoverable_try == 0.0


def test_session_uplift_included_in_sgk_headline() -> None:
    report = BillingActionReport(
        patient_id="P1",
        lab=LabOptimization(exactness_status="exact"),
        session_uplift=SessionPricingUplift(
            opportunities=[
                {
                    "recoverable_uplift_try": 150.0,
                    "included_in_sgk_total": True,
                }
            ],
            exactness_status="exact",
        ),
        billing_strategy=BillingStrategyRecommendation(
            recommendations=[
                {
                    "claim_id": "C1",
                    "recommendation": "itemized",
                    "recommendation_kind": "optional_override",
                    "savings_try": 200.0,
                }
            ],
            exactness_status="exact",
        ),
    )
    _finalize_report_totals(report)
    assert report.sgk_uplift_try == 350.0
    assert report.total_recoverable_try == 350.0
    assert _sum_sgk_uplift_try(report) == 350.0


def test_grand_total_excludes_lab_in_orchestrator_summary(monkeypatch) -> None:
    import src.bilun.domain.billing.orchestrator as billing_mod

    def _report(pid: str, lab_savings: float) -> SimpleNamespace:
        inner = BillingActionReport(
            patient_id=pid,
            lab=LabOptimization(
                hemogram_bundling_savings=lab_savings,
                exactness_status="exact",
            ),
            billing_strategy=BillingStrategyRecommendation(exactness_status="exact"),
            session_uplift=SessionPricingUplift(exactness_status="exact"),
        )
        _finalize_report_totals(inner)
        inner.action_count = 0
        inner.priority = "low"
        inner.exactness_status = "exact"
        inner.required_inputs_missing = []
        return inner

    cache = {
        "sut_by_pid": {"P1": {}, "P2": {}},
        "patient_alerts_cache": {
            "patients": [
                {"patient_id": "P1", "icd10_chapters": [], "copay_exemption": {}},
                {"patient_id": "P2", "icd10_chapters": [], "copay_exemption": {}},
            ]
        },
        "lab_df_pl": __import__("polars").DataFrame(),
    }

    reports = {
        "P1": _report("P1", 10.0),
        "P2": _report("P2", 20.0),
    }

    monkeypatch.setattr(
        billing_mod,
        "compute_patient_billing_report",
        lambda pid, **kwargs: reports[pid],
    )

    _, summary = billing_mod.compute_all_billing_reports(cache)

    assert summary.total_compliance_adjustment == 30.0
    assert summary.total_lab_savings == 30.0
    assert summary.grand_total_recoverable == 0.0
    assert summary.total_sgk_uplift == 0.0
    assert summary.savings_by_category["compliance"] == 30.0
    assert summary.savings_by_category["sgk_uplift"] == 0.0
