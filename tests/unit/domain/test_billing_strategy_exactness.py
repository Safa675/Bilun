"""Focused tests for billing strategy exactness gating (claim-line only)."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from src.bilun.domain.billing.orchestrator import compute_patient_billing_report

pytestmark = pytest.mark.unit


def test_billing_strategy_is_unavailable_without_exact_claim_inputs() -> None:
    report = compute_patient_billing_report("P1")

    assert report.billing_strategy.recommendations == []
    assert report.billing_strategy.exactness_status == "missing_exact_inputs"
    assert report.exactness_status == "missing_exact_inputs"


def test_billing_strategy_with_chapters_only_stays_unavailable() -> None:
    report = compute_patient_billing_report("P1")

    assert report.billing_strategy.recommendations == []
    assert report.billing_strategy.exactness_status == "missing_exact_inputs"
    assert report.total_recoverable_try is None


def test_billing_report_with_claim_context_uses_sut_strategy() -> None:
    from src.bilun.domain.claims import build_patient_claim_context, load_sut_claim_dataset

    dataset = load_sut_claim_dataset()
    ctx = build_patient_claim_context("SENTETIK-HASTA-0003", dataset)
    assert ctx is not None

    report = compute_patient_billing_report(
        "SENTETIK-HASTA-0003",
        claim_context=ctx,
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


def test_billing_report_without_claim_context_excludes_heuristic_totals() -> None:
    report = compute_patient_billing_report("P1")

    assert report.billing_strategy.exactness_status == "missing_exact_inputs"
    assert report.exactness_status == "missing_exact_inputs"
    assert "itemized_billed_procedure_lines" in report.required_inputs_missing
    assert report.sgk_uplift_try is None
    assert report.total_recoverable_try is None
    assert report.compliance_adjustment_try is None
    assert report.action_count == 0
