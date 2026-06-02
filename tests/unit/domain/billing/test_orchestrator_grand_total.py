"""Cohort grand_total_recoverable uses per-patient exact totals (L3.6)."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

pytestmark = pytest.mark.unit


def test_grand_total_sums_patient_recoverable_not_heuristic_blocks(monkeypatch) -> None:
    import src.bilun.domain.billing.orchestrator as billing_mod

    def _report(pid: str, lab_savings: float, drug_exact: bool) -> SimpleNamespace:
        drug_status = "exact" if drug_exact else "missing_exact_inputs"
        drug_savings = 100.0 if drug_exact else 999.0
        recoverable = lab_savings + (drug_savings if drug_exact else 0.0)
        return SimpleNamespace(
            patient_id=pid,
            lab=SimpleNamespace(
                total_savings=lab_savings,
                flagged_tests=[],
                exactness_status="exact",
                required_inputs_missing=[],
            ),
            drug=SimpleNamespace(
                total_savings=drug_savings,
                drug_recommendations=[],
                exactness_status=drug_status,
                required_inputs_missing=[] if drug_exact else ["drug_lines"],
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
        "P1": _report("P1", 10.0, drug_exact=True),
        "P2": _report("P2", 20.0, drug_exact=False),
    }

    monkeypatch.setattr(
        billing_mod,
        "compute_patient_billing_report",
        lambda pid, **kwargs: reports[pid],
    )

    _, summary = billing_mod.compute_all_billing_reports(cache)

    assert summary.total_lab_savings == 30.0
    assert summary.total_drug_savings == 100.0
    assert summary.grand_total_recoverable == 130.0
