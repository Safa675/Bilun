"""Cohort grand_total_recoverable uses per-patient exact totals (L3.6)."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

pytestmark = pytest.mark.unit


def test_grand_total_sums_patient_recoverable_not_heuristic_blocks(monkeypatch) -> None:
    import src.bilun.domain.billing.orchestrator as billing_mod

    def _report(pid: str, lab_savings: float) -> SimpleNamespace:
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
                uplift_savings_try=0.0,
                optional_override_uplift_try=0.0,
            ),
            session_uplift=SimpleNamespace(
                opportunities=[],
                exactness_status="exact",
                required_inputs_missing=[],
                total_uplift_try=0.0,
                confirmed_uplift_try=0.0,
            ),
            drg_uplift=SimpleNamespace(
                opportunities=[],
                exactness_status="exact",
                required_inputs_missing=[],
                total_uplift_try=0.0,
                confirmed_uplift_try=0.0,
            ),
            blood_uplift=SimpleNamespace(
                opportunities=[],
                exactness_status="exact",
                required_inputs_missing=[],
                confirmed_uplift_try=0.0,
                total_uplift_try=0.0,
            ),
            yatak_puani=SimpleNamespace(
                opportunities=[],
                exactness_status="exact",
                required_inputs_missing=[],
                confirmed_yatak_try=0.0,
            ),
            icu_puani=SimpleNamespace(
                opportunities=[],
                exactness_status="exact",
                required_inputs_missing=[],
                confirmed_icu_try=0.0,
            ),
            yenidogan_yatak=SimpleNamespace(
                opportunities=[],
                exactness_status="exact",
                required_inputs_missing=[],
                confirmed_yenidogan_yatak_try=0.0,
            ),
            refakatci=SimpleNamespace(
                opportunities=[],
                exactness_status="exact",
                required_inputs_missing=[],
                confirmed_refakat_try=0.0,
            ),
            anestezi_puani=SimpleNamespace(
                opportunities=[],
                exactness_status="exact",
                required_inputs_missing=[],
                confirmed_anestezi_try=0.0,
            ),
            material_uplift=SimpleNamespace(
                opportunities=[],
                exactness_status="exact",
                required_inputs_missing=[],
                total_uplift_try=0.0,
                confirmed_uplift_try=0.0,
            ),
            care_setting_review=SimpleNamespace(
                opportunities=[],
                exactness_status="exact",
                required_inputs_missing=[],
                total_uplift_try=0.0,
                confirmed_uplift_try=0.0,
            ),
            procedure_addon_uplift=SimpleNamespace(
                opportunities=[],
                exactness_status="exact",
                required_inputs_missing=[],
                total_uplift_try=0.0,
                confirmed_uplift_try=0.0,
            ),
            procedure_capture_gap=SimpleNamespace(
                opportunities=[],
                exactness_status="exact",
                required_inputs_missing=[],
                total_gap_try=0.0,
                confirmed_gap_try=0.0,
            ),
            capture_gap_try=0.0,
            drg_package_adequacy=SimpleNamespace(
                opportunities=[],
                exactness_status="exact",
                required_inputs_missing=[],
                total_uplift_try=0.0,
                confirmed_uplift_try=0.0,
                review_uplift_try=0.0,
            ),
            package_adequacy_review_try=0.0,
            medula_rejection_playbook=SimpleNamespace(
                entries=[],
                exactness_status="exact",
                required_inputs_missing=[],
                entry_count=0,
                rebill_permitted_count=0,
            ),
            medula_playbook_entry_count=0,
            sgk_uplift_try=0.0,
            audit_exposure_try=0.0,
            compliance_adjustment_try=lab_savings,
            materials=SimpleNamespace(
                pre_auth_required=[],
                miat_restricted=[],
                bundled_separate_billing=[],
                miat_interval_violations=[],
                exactness_status="exact",
                required_inputs_missing=[],
            ),
            total_recoverable_try=0.0,
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
    assert summary.total_compliance_adjustment == 30.0
    assert summary.grand_total_recoverable == 0.0
    assert summary.total_sgk_uplift == 0.0
