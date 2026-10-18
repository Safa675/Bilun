"""Focused tests for billing strategy exactness gating (claim-line only)."""

from __future__ import annotations

import pytest

from src.bilun.domain.billing.orchestrator import compute_patient_billing_report
from tests.fixtures import synthetic_cohort as cohort

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

    # S1 bills a mandated package itemised: the SUT strategy has to say "package" for its claim.
    role = cohort.role("showcase_S1")
    dataset = load_sut_claim_dataset()
    ctx = build_patient_claim_context(role.patient_id, dataset)
    assert ctx is not None

    report = compute_patient_billing_report(
        role.patient_id,
        claim_context=ctx,
    )

    assert report.billing_strategy.exactness_status == "exact"
    claim_recs = [
        rec
        for rec in report.billing_strategy.recommendations
        if rec.get("claim_id") == role.claim_id and "recommendation_kind" in rec
    ]
    assert claim_recs
    assert claim_recs[0]["recommendation"] == "package"
    assert claim_recs[0]["recommendation_kind"] == "mandatory_compliance"
    assert claim_recs[0]["payment_method_kind"] == "DRG_MANDATORY"
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
