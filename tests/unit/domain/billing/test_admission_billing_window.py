"""Billing-period timing must stay unavailable without MEDULA closure data."""

from __future__ import annotations

from dataclasses import replace
from datetime import date
from decimal import Decimal

import pytest

from src.bilun.domain.billing.admission_billing_window import (
    ADMISSION_BILLING_WINDOW_RULE_ID,
    evaluate_admission_billing_window_unavailable,
)
from src.bilun.domain.billing.claim_compliance import project_claim_compliance
from src.bilun.domain.billing.engine import analyze_claim
from src.bilun.domain.claims.models import ClaimHeader
from src.bilun.domain.claims.patient_context import PatientClaimContext

pytestmark = pytest.mark.unit


def _claim(
    claim_id: str = "C1",
    patient_id: str = "P1",
    admission: date = date(2026, 7, 9),
    claim_end: date = date(2026, 7, 10),
) -> ClaimHeader:
    return ClaimHeader(
        claim_id=claim_id,
        patient_id=patient_id,
        episode_id="E1",
        claim_type="yatis",
        facility_tier="devlet",
        provider_type="sozlesmeli",
        department="genel",
        admission_date=admission,
        discharge_date=claim_end,
        claim_start_date=admission,
        claim_end_date=claim_end,
        primary_icd10="K35.8",
        expected_total_billed_try=Decimal("1000"),
        expected_total_payable_try=Decimal("900"),
        expected_denial_reason="",
        scenario_tag="test",
    )


def _context(*claims: ClaimHeader) -> PatientClaimContext:
    return PatientClaimContext(
        patient_id="P1",
        claims=claims,
        procedure_lines=(),
        material_lines=(),
        drug_lines=(),
        diagnoses=(),
    )


def test_long_and_short_stays_are_both_unavailable_without_period_closure() -> None:
    long_stay = _claim(
        claim_id="C2",
        admission=date(2026, 5, 1),
        claim_end=date(2026, 7, 10),
    )
    short_stay = _claim(
        claim_id="C1",
        admission=date(2026, 7, 9),
        claim_end=date(2026, 7, 10),
    )

    batch = evaluate_admission_billing_window_unavailable(
        "P1", _context(long_stay, short_stay)
    )
    projected = project_claim_compliance("P1", batch)

    assert batch.findings == ()
    assert batch.legacy_violations == ()
    assert [row["claim_id"] for row in projected.evaluations] == ["C1", "C2"]
    for row in projected.evaluations:
        assert row["rule_id"] == ADMISSION_BILLING_WINDOW_RULE_ID
        assert row["status"] == "unavailable"
        assert row["line_kind"] == "claim"
        assert row["missing_inputs"] == ["billing_period_closure_date"]
        assert row["reason"] == "billing_period_closure_date_not_ingested"


def test_missing_claim_context_has_honest_patient_level_status() -> None:
    batch = evaluate_admission_billing_window_unavailable("P1", None)

    assert batch.findings == ()
    assert len(batch.evaluations) == 1
    assert batch.evaluations[0].claim_id is None
    assert batch.evaluations[0].evaluation_status == "missing_inputs"
    assert batch.evaluations[0].missing_inputs == ["claim_context"]


def test_claims_from_other_patient_are_rejected() -> None:
    wrong_patient = _claim(patient_id="P2")

    with pytest.raises(ValueError, match="belong to the report patient"):
        evaluate_admission_billing_window_unavailable("P1", _context(wrong_patient))


def test_legacy_engine_keeps_real_rules_without_false_late_billing() -> None:
    long_stay = replace(
        _claim(admission=date(2026, 5, 1), claim_end=date(2026, 7, 10)),
        primary_icd10="",
    )

    violations = analyze_claim(_context(long_stay))

    assert any(row.get("rule_id") == "tablo15_8_missing_diagnosis" for row in violations)
    assert all(
        row.get("rule_id") != ADMISSION_BILLING_WINDOW_RULE_ID for row in violations
    )
