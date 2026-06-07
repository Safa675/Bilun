"""Unit tests for session under-billing uplift detection."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from src.bilun.domain.claims.models import ClaimHeader, ProcedureClaimLine
from src.bilun.domain.prose_rules.session_uplift import (
    detect_session_underbilling_opportunities,
    needs_clinical_review,
)

pytestmark = pytest.mark.unit


def _claim(**overrides) -> ClaimHeader:
    base = dict(
        claim_id="CLM1",
        patient_id="P1",
        episode_id="E1",
        claim_type="yatarak",
        facility_tier="3",
        provider_type="hospital",
        department="cardiology",
        admission_date=date(2026, 1, 10),
        discharge_date=date(2026, 1, 12),
        claim_start_date=date(2026, 1, 10),
        claim_end_date=date(2026, 1, 12),
        primary_icd10="I21.9",
        package_candidate=True,
        expected_total_billed_try=Decimal("5000"),
        expected_total_payable_try=Decimal("4000"),
        expected_denial_reason="",
        scenario_tag="test",
    )
    base.update(overrides)
    return ClaimHeader(**base)


def _proc(**overrides) -> ProcedureClaimLine:
    base = dict(
        procedure_line_id="PL1",
        claim_id="CLM1",
        patient_id="P1",
        episode_id="E1",
        procedure_date=date(2026, 1, 10),
        procedure_code="610070",
        procedure_name="Test procedure",
        procedure_category="islem",
        quantity=1,
        unit_price_try=Decimal("1000"),
        billed_amount_try=Decimal("1000"),
        expected_payable_try=Decimal("800"),
        is_package_included=False,
        package_code="",
        surcharge_applicable=False,
        copay_rate_applicable=True,
        denial_reason_expected="",
        rule_trace_expected="",
    )
    base.update(overrides)
    return ProcedureClaimLine(**base)


class TestClinicalReviewHeuristic:
    def test_flags_tiny_secondary_on_high_primary(self) -> None:
        assert needs_clinical_review(
            primary_billed_try=10_124.92,
            actual_billed_try=52.48,
            recoverable_uplift_try=2_985.0,
        )

    def test_passes_balanced_secondaries(self) -> None:
        assert not needs_clinical_review(
            primary_billed_try=1_000.0,
            actual_billed_try=100.0,
            recoverable_uplift_try=150.0,
        )


class TestSessionUnderbilling:
    def test_detects_secondary_under_billing(self) -> None:
        claim = _claim()
        session_day = date(2026, 1, 10)
        lines = [
            _proc(
                procedure_line_id="PL1",
                procedure_code="610070",
                procedure_date=session_day,
                billed_amount_try=Decimal("100"),
                procedure_specialty_code="cerrahi",
            ),
            _proc(
                procedure_line_id="PL2",
                procedure_code="609270",
                procedure_date=session_day,
                billed_amount_try=Decimal("1000"),
                procedure_specialty_code="cerrahi",
            ),
        ]
        hits = detect_session_underbilling_opportunities(
            lines,
            claim_id="CLM1",
            same_incision=True,
            claim=claim,
        )
        assert len(hits) == 1
        assert hits[0]["procedure_code"] == "610070"
        assert hits[0]["recoverable_uplift_try"] == pytest.approx(150.0, rel=0.01)
        assert hits[0]["savings_category"] == "sgk_uplift"
        assert hits[0]["included_in_sgk_total"] is True
        assert hits[0].get("review_kind") is None

    def test_no_opportunity_when_secondary_at_allowed_rate(self) -> None:
        claim = _claim()
        session_day = date(2026, 1, 10)
        lines = [
            _proc(
                procedure_line_id="PL1",
                procedure_code="610070",
                procedure_date=session_day,
                billed_amount_try=Decimal("250"),
                procedure_specialty_code="cerrahi",
            ),
            _proc(
                procedure_line_id="PL2",
                procedure_code="609270",
                procedure_date=session_day,
                billed_amount_try=Decimal("1000"),
                procedure_specialty_code="cerrahi",
            ),
        ]
        hits = detect_session_underbilling_opportunities(
            lines,
            same_incision=True,
            claim=claim,
        )
        assert hits == []

    def test_skipped_when_same_incision_unknown(self) -> None:
        lines = [
            _proc(
                procedure_line_id="PL1",
                procedure_code="610070",
                billed_amount_try=Decimal("1000"),
            ),
            _proc(
                procedure_line_id="PL2",
                procedure_code="609270",
                billed_amount_try=Decimal("100"),
            ),
        ]
        hits = detect_session_underbilling_opportunities(lines, same_incision=True)
        assert hits == []
