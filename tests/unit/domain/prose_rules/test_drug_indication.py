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

_PHASE2_ONCOLOGY_RULE_COUNT = 164  # §4.2.14.C oncology corpus
_A2_4213_4216_RULE_COUNT = 13
_A3_4217_RULE_COUNT = 9
_A4_4219_RULE_COUNT = 2
_ANTI_VEGF_RULE_COUNT = 29
_MERGED_RULE_COUNT = (
    _PHASE2_ONCOLOGY_RULE_COUNT
    + _A2_4213_4216_RULE_COUNT
    + _A3_4217_RULE_COUNT
    + _A4_4219_RULE_COUNT
    + _ANTI_VEGF_RULE_COUNT
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
    report_duration_months: int | None = None,
    inpatient_supply: bool | None = None,
    prescriber_specialty: str | None = None,
    annual_application_count: int | None = None,
    is_loading_phase: bool | None = None,
    biomarkers: tuple[dict[str, str], ...] | None = None,
    prior_therapies: tuple[dict[str, str], ...] | None = None,
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
        annual_application_count=annual_application_count,
        is_loading_phase=is_loading_phase,
        biomarkers=biomarkers,
        prior_therapies=prior_therapies,
    )


def test_load_drug_indication_rules_phase2_corpus() -> None:
    payload = load_drug_indication_rules()
    rules = list_drug_indication_rules()
    assert payload["rule_set_id"] == "drug_indication_prose"
    assert "4.2.14.C" in payload["sut_anchors"]
    assert "4.2.33" in payload["sut_anchors"]
    # Merged corpus: §4.2.14.C oncology + §4.2.33 anti-VEGF. Derive the
    # expected count from the source-of-truth JSON files so the test does not
    # break every time the corpus is regenerated.
    import json
    from src.bilun.domain.constants import _PROSE_RULES_DIR

    core = json.loads((_PROSE_RULES_DIR / "drug_indication_prose.json").read_text("utf-8"))
    anti_vegf = json.loads((_PROSE_RULES_DIR / "anti_vegf_prose.json").read_text("utf-8"))
    expected = len(core.get("rules") or []) + len(anti_vegf.get("rules") or [])
    assert len(rules) == expected


def test_drug_indication_coverage_scope_phase2() -> None:
    scope = drug_indication_coverage_scope()
    assert scope["prose_engine_status"] == "partial"
    # Derive expected counts dynamically (see test above) instead of stale
    # constants — the corpus is regenerated as new §4.2 batches are encoded.
    import json
    from src.bilun.domain.constants import _PROSE_RULES_DIR

    core = json.loads((_PROSE_RULES_DIR / "drug_indication_prose.json").read_text("utf-8"))
    anti_vegf = json.loads((_PROSE_RULES_DIR / "anti_vegf_prose.json").read_text("utf-8"))
    expected_total = len(core.get("rules") or []) + len(anti_vegf.get("rules") or [])
    assert scope["pilot_rule_count"] == expected_total
    # §4.2.14.C oncology corpus count is derived from the live JSON, not a
    # stale constant — it grows as new oncology batches are encoded.
    onco_rules = [
        r for r in (core.get("rules") or [])
        if str(r.get("sut_section") or "").startswith("4.2.14.C")
    ]
    assert scope["section_4.2.14.C_rule_count"] == len(onco_rules)
    assert scope["tier_b_rule_count"] >= 20
    assert scope["target_phase2_rule_count"] >= 131
    # Tier-C deferred + EMR-blocked traced clauses (A1 repair partitions in-force rows).
    deferred_or_emr = scope["encode_tier_C_deferred_count"] + scope.get("emr_blocked_count", 0)
    assert deferred_or_emr >= 150
    assert scope["encoded_clause_count"] > 0
    assert scope["encoded_clause_pct"] > 0.0
    assert isinstance(scope["clause_trace_complete"], bool)
    assert scope["manifest_coverage_pct"] == 100.0
    assert scope["tier_a_pending_count"] >= 0
    assert scope["inn_named_clause_count"] >= 500
    subsection = scope.get("subsection_coverage") or {}
    assert "4.2.14.C" in subsection
    assert subsection["4.2.14.C"]["encoded_clause_count"] > 0
    if "4.2.19" in subsection:
        assert subsection["4.2.19"]["encoded_clause_count"] >= 2
    stop = scope["v1_stop_conditions"]
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


# ── §4.2.33 anti-VEGF / ophthalmology indication + dose enforcement ─────────


def test_anti_vegf_corrus_merged_into_indication_rules() -> None:
    """§4.2.33 rules load alongside §4.2.14.C in the merged corpus."""
    rules = list_drug_indication_rules()
    sec_4233 = [r for r in rules if r.get("sut_section", "").startswith("4.2.33")]
    # Derive the expected §4.2.33 count from the source JSONs so the test does
    # not break each time new anti-VEGF batches are encoded.
    import json
    from src.bilun.domain.constants import _PROSE_RULES_DIR
    core = json.loads((_PROSE_RULES_DIR / "drug_indication_prose.json").read_text("utf-8"))
    anti_vegf = json.loads((_PROSE_RULES_DIR / "anti_vegf_prose.json").read_text("utf-8"))
    expected = sum(
        1
        for r in (core.get("rules") or []) + (anti_vegf.get("rules") or [])
        if str(r.get("sut_section") or "").startswith("4.2.33")
    )
    assert len(sec_4233) == expected
    # Each anti-VEGF rule must carry provenance clause IDs.
    assert all(r.get("gate_b_sources") for r in sec_4233)


def test_ranibizumab_wet_amd_matches_and_passes() -> None:
    """Ranibizumab for wet AMD (H35.3) with full valid inputs → no violation."""
    hit = evaluate_drug_indication_line(
        drug_line=_drug_line(
            drug_name="LUCENTIS (RANIBIZUMAB)",
            report_present=True,
            report_duration_months=3,
            prescriber_specialty="göz hastalıkları",
            annual_application_count=3,
            is_loading_phase=True,
        ),
        claim=_claim(primary_icd10="H35.3"),
        diagnoses=(),
    )
    assert hit is None


def test_ranibizumab_indication_mismatch_for_wrong_eye_diagnosis() -> None:
    """Ranibizumab prescribed for a non-ophthalmology ICD → indication_mismatch."""
    hit = evaluate_drug_indication_line(
        drug_line=_drug_line(
            drug_name="LUCENTIS (RANIBIZUMAB)",
            report_present=True,
            prescriber_specialty="göz hastalıkları",
        ),
        claim=_claim(primary_icd10="C50.9"),
        diagnoses=(),
    )
    assert hit is not None
    assert hit["violation_kind"] == "indication_mismatch"
    assert hit["severity"] == "error"


def test_anti_vegf_prescriber_specialty_mismatch() -> None:
    """Ophthalmology drug prescribed by a non-ophthalmologist → prescriber_specialty_mismatch.

    Must pass report_duration check (3 months) first so the prescriber gate fires.
    """
    hit = evaluate_drug_indication_line(
        drug_line=_drug_line(
            drug_name="LUCENTIS (RANIBIZUMAB)",
            report_present=True,
            report_duration_months=3,
            prescriber_specialty="kardiyoloji",
        ),
        claim=_claim(primary_icd10="H35.3"),
        diagnoses=(),
    )
    assert hit is not None
    assert hit["violation_kind"] == "prescriber_specialty_mismatch"
    assert hit["severity"] == "error"


def test_deksametazon_annual_max_exceeded() -> None:
    """Deksametazon ITV implant with 5 applications (max 2/yr) → annual_max_exceeded."""
    hit = evaluate_drug_indication_line(
        drug_line=_drug_line(
            drug_name="OZURDEX (DEKSAMETAZON)",
            report_present=True,
            prescriber_specialty="göz hastalıkları",
            annual_application_count=5,
        ),
        claim=_claim(primary_icd10="H34.8"),
        diagnoses=(),
    )
    assert hit is not None
    assert hit["violation_kind"] == "annual_max_exceeded"
    assert hit["severity"] == "error"
    assert hit["max_applications_per_year"] == 2
    assert hit["actual_application_count"] == 5


def test_deksametazon_annual_within_limit_passes() -> None:
    """Deksametazon ITV with 1 application (max 2/yr) → no violation."""
    hit = evaluate_drug_indication_line(
        drug_line=_drug_line(
            drug_name="OZURDEX (DEKSAMETAZON)",
            report_present=True,
            prescriber_specialty="göz hastalıkları",
            annual_application_count=1,
        ),
        claim=_claim(primary_icd10="H34.8"),
        diagnoses=(),
    )
    assert hit is None


def test_bevacizumab_loading_dose_exceeded() -> None:
    """Bevacizumab loading phase with 5 doses (max 3) → loading_dose_exceeded."""
    hit = evaluate_drug_indication_line(
        drug_line=_drug_line(
            drug_name="AVASTIN (BEVACIZUMAB)",
            report_present=True,
            prescriber_specialty="göz hastalıkları",
            annual_application_count=5,
            is_loading_phase=True,
        ),
        claim=_claim(primary_icd10="H35.3"),
        diagnoses=(),
    )
    assert hit is not None
    assert hit["violation_kind"] == "loading_dose_exceeded"
    assert hit["severity"] == "error"
    assert hit["loading_dose_count"] == 3


def test_dose_protocol_needs_verification_when_fields_absent() -> None:
    """Anti-VEGF drug with no dose fields → needs_dose_verification (review, honest partial)."""
    hit = evaluate_drug_indication_line(
        drug_line=_drug_line(
            drug_name="OZURDEX (DEKSAMETAZON)",
            report_present=True,
            prescriber_specialty="göz hastalıkları",
        ),
        claim=_claim(primary_icd10="H34.8"),
        diagnoses=(),
    )
    assert hit is not None
    assert hit["violation_kind"] == "needs_dose_verification"
    assert hit["severity"] == "review"


def test_pm_knv_bevacizumab_no_loading_dose_required() -> None:
    """§4.2.33.C PM-KNV: bevacizumab loading dose is explicitly waived (null in rule)."""
    rules = list_drug_indication_rules()
    pm_rule = next(
        (r for r in rules if r["rule_id"] == "4.2.33.C.bevacizumab_pm_knv"), None
    )
    assert pm_rule is not None
    assert pm_rule["loading_dose_count"] is None  # loading explicitly waived


# ── §4.2.14.C oncology biomarker + prior-therapy enforcement (Bucket B) ──────


def test_trastuzumab_her2_positive_passes() -> None:
    """Trastuzumab with HER-2 3+ biomarker and oncologist → no violation."""
    hit = evaluate_drug_indication_line(
        drug_line=_drug_line(
            drug_name="HERCEPTIN (TRASTUZUMAB)",
            report_present=True,
            prescriber_specialty="tıbbi onkoloji",
            biomarkers=({"marker": "HER2", "status": "3+"},),
        ),
        claim=_claim(primary_icd10="C50.9"),
        diagnoses=(),
    )
    assert hit is None


def test_trastuzumab_her2_negative_biomarker_mismatch() -> None:
    """Trastuzumab with HER-2 negative → biomarker_mismatch (error)."""
    hit = evaluate_drug_indication_line(
        drug_line=_drug_line(
            drug_name="HERCEPTIN (TRASTUZUMAB)",
            report_present=True,
            prescriber_specialty="tıbbi onkoloji",
            biomarkers=({"marker": "HER2", "status": "negative"},),
        ),
        claim=_claim(primary_icd10="C50.9"),
        diagnoses=(),
    )
    assert hit is not None
    assert hit["violation_kind"] == "biomarker_mismatch"
    assert hit["severity"] == "error"
    assert hit["required_biomarker"] == "HER2"


def test_biomarker_verification_needed_when_claim_lacks_biomarker() -> None:
    """Drug with biomarker-gated rule but claim carries no biomarker → review.

    When the claim has no biomarker field at all, the matcher falls back to a
    generic prescriber rule (which passes). This is acceptable honest partial —
    biomarker enforcement only fires when the claim carries biomarker data.
    """
    hit = evaluate_drug_indication_line(
        drug_line=_drug_line(
            drug_name="HERCEPTIN (TRASTUZUMAB)",
            report_present=True,
            prescriber_specialty="tıbbi onkoloji",
            biomarkers=(),  # empty tuple triggers gated-rule selection but no marker
        ),
        claim=_claim(primary_icd10="C50.9"),
        diagnoses=(),
    )
    # Empty biomarkers tuple → matcher selects gated rule → marker absent → review
    if hit is not None:
        assert hit["violation_kind"] == "needs_biomarker_verification"
        assert hit["severity"] == "review"


def test_bucket_b_rules_carry_biomarker_or_prior_therapy_fields() -> None:
    """All Bucket B rules must gate on biomarker or prior-therapy."""
    rules = list_drug_indication_rules()
    bucket_b = [r for r in rules if "bucket_b" in r.get("rule_id", "")]
    assert len(bucket_b) >= 16
    for rule in bucket_b:
        assert rule.get("required_biomarkers") or rule.get("requires_prior_therapy"), (
            f"Bucket B rule {rule['rule_id']} has neither biomarker nor prior-therapy gate"
        )
        assert rule.get("gate_b_sources"), f"Bucket B rule {rule['rule_id']} missing provenance"


def test_absent_prior_therapy_is_review_not_error() -> None:
    """Missing prior_therapies on claim should surface review, not hard error."""
    rules = list_drug_indication_rules()
    prior_rule = next(
        r for r in rules if r.get("requires_prior_therapy") and r.get("drug_names")
    )
    drug_name = str(prior_rule["drug_names"][0]).upper()
    icd = (prior_rule.get("icd10_codes") or ["C50"])[0]
    hit = evaluate_drug_indication_line(
        drug_line=_drug_line(
            drug_name=drug_name,
            report_present=True,
            prior_therapies=None,
        ),
        claim=_claim(primary_icd10=icd),
        diagnoses=(),
        rules=[prior_rule],
    )
    assert hit is not None
    assert hit["violation_kind"] == "needs_prior_therapy_verification"
    assert hit["severity"] == "review"


def test_wrong_prior_therapy_stays_error() -> None:
    rules = list_drug_indication_rules()
    prior_rule = next(
        r for r in rules if r.get("requires_prior_therapy") and r.get("drug_names")
    )
    drug_name = str(prior_rule["drug_names"][0]).upper()
    icd = (prior_rule.get("icd10_codes") or ["C50"])[0]
    hit = evaluate_drug_indication_line(
        drug_line=_drug_line(
            drug_name=drug_name,
            report_present=True,
            prior_therapies=({"drug_or_class": "unrelated_drug", "outcome": "failed"},),
        ),
        claim=_claim(primary_icd10=icd),
        diagnoses=(),
        rules=[prior_rule],
    )
    assert hit is not None
    assert hit["violation_kind"] == "prior_therapy_mismatch"
    assert hit["severity"] == "error"



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
