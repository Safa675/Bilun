"""Cohort grand_total_recoverable uses per-patient exact totals (L3.6)."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

pytestmark = pytest.mark.unit


def test_grand_total_sums_patient_recoverable_not_heuristic_blocks(monkeypatch) -> None:
    import src.bilun.domain.billing.orchestrator as billing_mod

    def _report(pid: str, lab_savings: float) -> SimpleNamespace:
        recoverable = lab_savings
        return SimpleNamespace(
            patient_id=pid,
            lab=SimpleNamespace(
                total_savings=lab_savings,
                flagged_tests=[],
                exactness_status="exact",
                required_inputs_missing=[],
            ),
            copay=SimpleNamespace(
                total_copay_savings_try=0.0,
                rx_copay_savings_try=0.0,
                is_exempt=False,
                exactness_status="exact",
                required_inputs_missing=[],
            ),
            billing_strategy=SimpleNamespace(
                recommendations=[],
                exactness_status="exact",
                required_inputs_missing=[],
                total_savings=0.0,
            ),
            materials=SimpleNamespace(
                pre_auth_required=[],
                miat_restricted=[],
                bundled_separate_billing=[],
                miat_interval_violations=[],
                exactness_status="exact",
                required_inputs_missing=[],
            ),
            total_recoverable_try=recoverable,
            action_count=0,
            priority="low",
        )

    cache = {
        "sut_by_pid": {"P1": {}, "P2": {}},
        "patient_alerts_cache": {
            "patients": [
                {"patient_id": "P1", "icd10_chapters": [], "copay_exemption": {}},
                {"patient_id": "P2", "icd10_chapters": [], "copay_exemption": {}},
            ]
        },
        "lab_df_pl": __import__("polars").DataFrame(),
        "rec_df_pl": __import__("polars").DataFrame(),
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

    assert summary.total_lab_savings == 30.0
    assert summary.grand_total_recoverable == 30.0
