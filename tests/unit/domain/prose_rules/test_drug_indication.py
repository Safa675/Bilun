"""Unit tests for §4.2 drug indication prose matcher (Tier 3b)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from src.bilun.domain.billing.claim_drug_indication import validate_drug_indication_from_claims
from src.bilun.domain.claims.models import ClaimDiagnosis, ClaimHeader, DrugClaimLine
from src.bilun.domain.claims.patient_context import PatientClaimContext
from src.bilun.domain.prose_rules.drug_indication import (
    check_drug_indication_for_context,
    drug_indication_coverage_scope,
    evaluate_drug_indication_line,
    list_drug_indication_rules,
    load_drug_indication_rules,
)


def _claim(*, primary_icd10: str = "C34.9") -> ClaimHeader:
    return ClaimHeader(
        claim_id="C1",
        patient_id="P1",
        episode_id="E1",
        claim_type="yatis",
        facility_tier="2",
        provider_type="kamu",
        department="onkoloji",
        admission_date=date(2026, 1, 1),
        discharge_date=date(2026, 1, 5),
        claim_start_date=date(2026, 1, 1),
        claim_end_date=date(2026, 1, 5),
        primary_icd10=primary_icd10,
        package_candidate=False,
        expected_total_billed_try=Decimal("0"),
        expected_total_payable_try=Decimal("0"),
        expected_denial_reason="",
        scenario_tag="test",
    )


def _drug_line(
    *,
    drug_name: str = "AVASTIN 400 MG (BEVACIZUMAB)",
    report_present: bool | None = None,
) -> DrugClaimLine:
    return DrugClaimLine(
        drug_claim_line_id="D1",
        prescription_id="RX1",
        claim_id="C1",
        patient_id="P1",
        episode_id="E1",
        drug_claim_date=date(2026, 1, 2),
        drug_name=drug_name,
        drug_code="",
        barkod="",
        equivalence_group="",
        quantity=1,
        unit_price_try=Decimal("10000"),
        billed_amount_try=Decimal("10000"),
        expected_payable_try=Decimal("7200"),
        discount_tier_expected=Decimal("0.28"),
        denial_reason_expected="",
        rule_trace_expected="",
        drug_specialty_board_report_present=report_present,
    )


def test_load_drug_indication_rules_pilot_corpus() -> None:
    payload = load_drug_indication_rules()
    rules = list_drug_indication_rules()
    assert payload["rule_set_id"] == "drug_indication_prose"
    assert "4.2.14.C" in payload["sut_anchors"]
    assert len(rules) == 18


def test_drug_indication_coverage_scope_partial() -> None:
    scope = drug_indication_coverage_scope()
    assert scope["prose_engine_status"] == "partial"
    assert scope["pilot_rule_count"] == 18


def test_bevacizumab_missing_board_report_is_error() -> None:
    claim = _claim()
    hit = evaluate_drug_indication_line(
        drug_line=_drug_line(report_present=False),
        claim=claim,
        diagnoses=(),
    )
    assert hit is not None
    assert hit["violation_kind"] == "missing_board_report"
    assert hit["severity"] == "error"
    assert hit["rule_id"] == "4.2.14.C.(1).bevacizumab_oncology_board"


def test_bevacizumab_with_board_report_passes() -> None:
    hit = evaluate_drug_indication_line(
        drug_line=_drug_line(report_present=True),
        claim=_claim(),
        diagnoses=(),
    )
    assert hit is None


def test_bevacizumab_indication_mismatch_for_non_cancer_icd() -> None:
    hit = evaluate_drug_indication_line(
        drug_line=_drug_line(report_present=True),
        claim=_claim(primary_icd10="J45.9"),
        diagnoses=(),
    )
    assert hit is not None
    assert hit["violation_kind"] == "indication_mismatch"


def test_unknown_report_flag_is_review() -> None:
    hit = evaluate_drug_indication_line(
        drug_line=_drug_line(report_present=None),
        claim=_claim(),
        diagnoses=(),
    )
    assert hit is not None
    assert hit["violation_kind"] == "needs_report_verification"
    assert hit["severity"] == "review"


def test_claim_wiring_returns_exact_violations() -> None:
    ctx = PatientClaimContext(
        patient_id="P1",
        claims=(_claim(),),
        procedure_lines=(),
        material_lines=(),
        drug_lines=(_drug_line(report_present=False),),
        diagnoses=(
            ClaimDiagnosis(
                diagnosis_id="DG1",
                claim_id="C1",
                patient_id="P1",
                episode_id="E1",
                icd10_code="C34.9",
                is_primary=True,
                diagnosis_role="birincil",
                diagnosis_date=date(2026, 1, 1),
                exemption_eligible=False,
            ),
        ),
    )
    violations = check_drug_indication_for_context(ctx)
    assert len(violations) == 1

    review = validate_drug_indication_from_claims(ctx)
    assert review.exactness_status == "exact"
    assert review.violation_count == 1
    assert review.error_count == 1
