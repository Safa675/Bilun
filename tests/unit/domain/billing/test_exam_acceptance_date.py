"""Table 15 #22 cannot decide without the outpatient acceptance date."""

from __future__ import annotations

from dataclasses import replace
from datetime import date
from decimal import Decimal

import pytest

from src.bilun.domain.billing.claim_compliance import project_claim_compliance
from src.bilun.domain.billing.exam_acceptance_date import (
    EXAM_ACCEPTANCE_DATE_RULE_ID,
    evaluate_exam_acceptance_date_unavailable,
)
from src.bilun.domain.claims.models import ClaimHeader
from src.bilun.domain.claims.patient_context import PatientClaimContext

pytestmark = pytest.mark.unit


def _claim(claim_id: str) -> ClaimHeader:
    return ClaimHeader(
        claim_id=claim_id,
        patient_id="P1",
        episode_id=f"E-{claim_id}",
        claim_type="poliklinik",
        facility_tier="devlet",
        provider_type="sozlesmeli",
        department="genel",
        admission_date=None,
        discharge_date=None,
        claim_start_date=date(2026, 7, 10),
        claim_end_date=date(2026, 7, 13),
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


def test_service_range_and_hospital_admission_do_not_replace_acceptance_date() -> None:
    outpatient = _claim("C2")
    inpatient = replace(
        _claim("C1"),
        claim_type="yatis",
        admission_date=date(2026, 7, 10),
        discharge_date=date(2026, 7, 13),
    )

    batch = evaluate_exam_acceptance_date_unavailable(
        "P1", _context(outpatient, inpatient)
    )
    projected = project_claim_compliance("P1", batch)

    assert batch.findings == ()
    assert batch.legacy_violations == ()
    assert [row["claim_id"] for row in projected.evaluations] == ["C1", "C2"]
    for row in projected.evaluations:
        assert row["rule_id"] == EXAM_ACCEPTANCE_DATE_RULE_ID
        assert row["status"] == "unavailable"
        assert row["line_kind"] == "claim"
        assert row["missing_inputs"] == ["patient_acceptance_date"]
        assert row["reason"] == "patient_acceptance_date_not_ingested"


def test_missing_claim_context_is_patient_level_missing_inputs() -> None:
    batch = evaluate_exam_acceptance_date_unavailable("P1", None)

    assert batch.findings == ()
    assert len(batch.evaluations) == 1
    assert batch.evaluations[0].claim_id is None
    assert batch.evaluations[0].evaluation_status == "missing_inputs"
    assert batch.evaluations[0].missing_inputs == ["claim_context"]


def test_foreign_claim_is_rejected() -> None:
    with pytest.raises(ValueError, match="belong to the report patient"):
        evaluate_exam_acceptance_date_unavailable(
            "P1", _context(replace(_claim("C1"), patient_id="P2"))
        )
