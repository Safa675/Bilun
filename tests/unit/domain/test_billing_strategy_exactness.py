"""Focused tests for Phase 4 billing strategy exactness gating."""

from __future__ import annotations

from types import SimpleNamespace

import polars as pl
import pytest

pytestmark = pytest.mark.unit


def test_billing_strategy_is_unavailable_without_exact_claim_inputs():
    from src.bilun.domain.billing.strategy import _recommend_billing_strategy

    result = _recommend_billing_strategy(
        "P1",
        {"I"},
    )

    assert result.recommendations == []
    assert result.exactness_status == "missing_exact_inputs"
    assert result.unavailable_reason is not None
    assert result.required_inputs_missing == [
        "itemized_billed_procedure_lines",
        "episode_package_eligibility_context",
        "admission_dates",
    ]
    assert result.total_savings == 0.0


def test_copay_is_unavailable_without_exact_claim_inputs():
    from src.bilun.domain.billing.copay import _optimize_copay

    result = _optimize_copay(
        "P1",
        {
            "exempt": True,
            "qualifying_diagnoses": [{"disease": "Diabetes", "range": "E10-E14"}],
        },
    )

    assert result.is_exempt is True
    assert result.exemption_disease == "Diabetes"
    assert result.total_copay_savings_try == 0.0
    assert result.exactness_status == "missing_exact_inputs"
    assert result.required_inputs_missing == [
        "billed_procedure_codes",
        "procedure_claim_dates",
        "dispensed_drug_claim_lines",
        "billed_drug_amounts",
    ]


def test_billing_report_totals_exclude_gated_strategy(monkeypatch):
    import src.bilun.domain.billing.orchestrator as billing_mod

    monkeypatch.setattr(
        billing_mod,
        "_optimize_lab_billing",
        lambda *_args, **_kwargs: SimpleNamespace(
            total_savings=12.5,
            flagged_tests=[],
            exactness_status="exact",
            required_inputs_missing=[],
        ),
    )
    monkeypatch.setattr(
        billing_mod,
        "_optimize_drug_costs",
        lambda *_args, **_kwargs: SimpleNamespace(
            total_savings=7.5,
            drug_recommendations=[],
            exactness_status="exact",
            required_inputs_missing=[],
        ),
    )
    monkeypatch.setattr(
        billing_mod,
        "_optimize_copay",
        lambda *_args, **_kwargs: SimpleNamespace(
            total_copay_savings_try=5.0,
            is_exempt=False,
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
            unavailable_reason="Needs exact claim lines.",
            required_inputs_missing=["itemized_billed_procedure_lines"],
            total_savings=0.0,
        ),
    )
    monkeypatch.setattr(
        billing_mod,
        "_precheck_materials",
        lambda *_args, **_kwargs: SimpleNamespace(
            pre_auth_required=[],
            miat_restricted=[],
            exactness_status="exact",
            required_inputs_missing=[],
        ),
    )

    report = billing_mod.compute_patient_billing_report(
        "P1",
        chapters={"I"},
    )

    assert report.billing_strategy.exactness_status == "missing_exact_inputs"
    assert report.exactness_status == "partial_exact"
    assert report.required_inputs_missing == ["itemized_billed_procedure_lines"]
    assert report.total_recoverable_try == 25.0
    assert report.action_count == 0
