"""Focused tests for Phase 4 billing strategy exactness gating."""

from __future__ import annotations

from types import SimpleNamespace

import polars as pl
import pytest

pytestmark = pytest.mark.unit


def test_billing_strategy_is_unavailable_without_exact_claim_inputs():
    from src.bilun.domain.billing.strategy import _recommend_billing_strategy

    result = _recommend_billing_strategy("P1", None)

    assert result.recommendations == []
    assert result.exactness_status == "missing_exact_inputs"


def test_billing_strategy_with_chapters_adds_review_flags() -> None:
    from src.bilun.domain.billing.strategy import _recommend_billing_strategy

    result = _recommend_billing_strategy(
        "P1",
        {"I"},
    )

    assert len(result.recommendations) == 1
    assert result.recommendations[0]["chapter"] == "I"
    assert result.recommendations[0]["savings_try"] is None
    assert result.exactness_status == "missing_exact_inputs"


def test_billing_report_with_claim_context_uses_sut_strategy() -> None:
    from src.bilun.domain.billing.orchestrator import compute_patient_billing_report
    from src.bilun.domain.claims import build_patient_claim_context, load_sut_claim_dataset

    dataset = load_sut_claim_dataset()
    ctx = build_patient_claim_context("SENTETIK-HASTA-0003", dataset)
    assert ctx is not None

    report = compute_patient_billing_report(
        "SENTETIK-HASTA-0003",
        claim_context=ctx,
        chapters={"I"},
    )

    assert report.billing_strategy.exactness_status == "exact"
    claim_recs = [
        rec
        for rec in report.billing_strategy.recommendations
        if rec.get("claim_id") == "F-SENTETIK-HASTA-0003-011"
        and "recommendation_kind" in rec
    ]
    assert claim_recs
    assert claim_recs[0]["recommendation"] == "package"
    assert claim_recs[0]["recommendation_kind"] == "optional_override"
    assert "lower than" not in claim_recs[0]["detail"]

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
    assert len(result.rate_corrections) == 1
    assert "EK-1A exemption may apply" in result.rate_corrections[0]["detail"]
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
    assert "itemized_billed_procedure_lines" in report.required_inputs_missing
    # Gated strategy contributes no SGK uplift; lab savings are compliance-only.
    assert report.sgk_uplift_try == 0.0
    assert report.total_recoverable_try == 0.0
    assert report.compliance_adjustment_try == 12.5
    assert report.action_count == 0
