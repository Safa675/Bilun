"""Unit tests for §4.2 drug indication prose matcher (Tier 3b + Phase 2)."""

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

_PHASE2_RULE_COUNT = 131


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
    report_duration_months: int | None = None,
    inpatient_supply: bool | None = None,
    prescriber_specialty: str | None = None,
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
        drug_report_duration_months=report_duration_months,
        drug_inpatient_supply=inpatient_supply,
        prescriber_specialty=prescriber_specialty,
    )


def test_load_drug_indication_rules_phase2_corpus() -> None:
    payload = load_drug_indication_rules()
    rules = list_drug_indication_rules()
    assert payload["rule_set_id"] == "drug_indication_prose"
    assert "4.2.14.C" in payload["sut_anchors"]
    assert len(rules) == _PHASE2_RULE_COUNT


def test_drug_indication_coverage_scope_phase2() -> None:
    scope = drug_indication_coverage_scope()
    assert scope["prose_engine_status"] == "partial"
    assert scope["pilot_rule_count"] == _PHASE2_RULE_COUNT
    assert scope["section_4.2.14.C_rule_count"] == _PHASE2_RULE_COUNT
    assert scope["tier_b_rule_count"] >= 20
    assert scope["target_phase2_rule_count"] >= 131
    assert scope["encode_tier_C_deferred_count"] >= 500
    assert scope["encoded_clause_count"] > 0
    assert scope["encoded_clause_pct"] > 0.0
    assert scope["clause_trace_complete"] is True
    assert scope["manifest_coverage_pct"] == 100.0
    assert scope["tier_a_pending_count"] >= 0
    assert scope["inn_named_clause_count"] >= 500
    stop = scope["v1_stop_conditions"]
    assert stop["v1_manifest_complete"] is True
    assert stop["v1_corpus_complete"] is True
    assert stop["v1_synthetic_complete"] is True
    assert stop["v1_inn_coverage_stretch_goal"] is False


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


def test_daratumumab_with_matching_icd_and_report_passes() -> None:
    hit = evaluate_drug_indication_line(
        drug_line=_drug_line(
            drug_name="DARZALEX 400 MG (DARATUMUMAB)",
            report_present=True,
        ),
        claim=_claim(primary_icd10="C90.0"),
        diagnoses=(),
    )
    assert hit is None


def test_atezolizumab_indication_mismatch_for_asthma() -> None:
    hit = evaluate_drug_indication_line(
        drug_line=_drug_line(
            drug_name="TECENTRIQ (ATEZOLIZUMAB)",
            report_present=True,
        ),
        claim=_claim(primary_icd10="J45.9"),
        diagnoses=(),
    )
    assert hit is not None
    assert hit["violation_kind"] == "indication_mismatch"
    assert hit["rule_id"] == "4.2.14.C.(15).atezolizumab_nsclc_board"


def test_tier_b_report_duration_match_passes() -> None:
    hit = evaluate_drug_indication_line(
        drug_line=_drug_line(
            drug_name="HERCEPTIN 440 MG (TRASTUZUMAB)",
            report_present=True,
            report_duration_months=3,
            prescriber_specialty="Tıbbi Onkoloji",
        ),
        claim=_claim(primary_icd10="C50.9"),
        diagnoses=(),
    )
    assert hit is None


def test_tier_b_report_duration_mismatch_is_error() -> None:
    hit = evaluate_drug_indication_line(
        drug_line=_drug_line(
            drug_name="HERCEPTIN 440 MG (TRASTUZUMAB)",
            report_present=True,
            report_duration_months=12,
        ),
        claim=_claim(primary_icd10="C50.9"),
        diagnoses=(),
    )
    assert hit is not None
    assert hit["violation_kind"] == "report_duration_mismatch"
    assert hit["rule_id"] == "4.2.14.C.trastuzumab_3mo_ecg_board"


def test_tier_b_inpatient_supply_required() -> None:
    hit = evaluate_drug_indication_line(
        drug_line=_drug_line(
            drug_name="KEYTRUDA 100 MG (PEMBROLIZUMAB)",
            report_present=True,
            inpatient_supply=False,
        ),
        claim=_claim(primary_icd10="C34.9"),
        diagnoses=(),
    )
    assert hit is not None
    assert hit["violation_kind"] == "inpatient_supply_required"


def test_tier_b_prescriber_specialty_mismatch() -> None:
    hit = evaluate_drug_indication_line(
        drug_line=_drug_line(
            drug_name="HERCEPTIN 440 MG (TRASTUZUMAB)",
            report_present=True,
            prescriber_specialty="Dahiliye",
        ),
        claim=_claim(primary_icd10="C50.9"),
        diagnoses=(),
    )
    assert hit is not None
    assert hit["violation_kind"] == "prescriber_specialty_mismatch"


def _run_golden_samples(path_suffix: str) -> None:
    from pathlib import Path
    import json

    golden_path = (
        Path(__file__).resolve().parents[4]
        / f"data/gazette/prose_rules/golden/drug_indication_4.2.14.C_{path_suffix}.json"
    )
    samples = json.loads(golden_path.read_text(encoding="utf-8"))["samples"]
    rules = list_drug_indication_rules()
    for sample in samples:
        hit = evaluate_drug_indication_line(
            drug_line=_drug_line(
                drug_name=sample["drug_name"],
                report_present=sample["report_present"],
                report_duration_months=sample.get("drug_report_duration_months"),
                inpatient_supply=sample.get("drug_inpatient_supply"),
                prescriber_specialty=sample.get("prescriber_specialty"),
            ),
            claim=_claim(primary_icd10=sample["primary_icd10"]),
            diagnoses=(),
            rules=rules,
        )
        expected = sample["expect_violation"]
        if expected is None:
            assert hit is None, sample
        else:
            assert hit is not None, sample
            assert hit["violation_kind"] == expected, sample


def test_golden_phase1_samples() -> None:
    _run_golden_samples("batch_a")


def test_golden_phase2_tier_b_samples() -> None:
    _run_golden_samples("batch_b")


def test_golden_sprint1_samples() -> None:
    _run_golden_samples("sprint1")


def test_trabectedin_missing_board_report() -> None:
    hit = evaluate_drug_indication_line(
        drug_line=_drug_line(
            drug_name="YONDELIS 1 MG (TRABECTEDIN)",
            report_present=False,
        ),
        claim=_claim(primary_icd10="C49.9"),
        diagnoses=(),
    )
    assert hit is not None
    assert hit["violation_kind"] == "missing_board_report"
    assert hit["rule_id"] == "4.2.14.C.trabectedin_sarcoma_board"


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
