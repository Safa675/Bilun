"""Explicit pediatric initiation paths, signed source measurements and boundaries."""
from __future__ import annotations

from dataclasses import asdict, replace
from datetime import date, datetime
import hashlib
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from src.bilun.domain.claims.adapter import build_context_from_material_dict
from src.bilun.domain.claims.growth_hormone import PEDIATRIC_GH_INITIATION_FIELDS, PEDIATRIC_GH_SDS_FIELDS
from src.bilun.domain.claims.parsing.row_parsers import parse_drug_line
from src.bilun.domain.prose_rules.drug_indication import evaluate_drug_indication_line_detailed, list_drug_indication_rules
from src.bilun.shared.models import MaterialItem
from tests.unit.domain.prose_rules.test_growth_hormone_continuation import line, _claim

pytestmark = pytest.mark.unit
ROOT = Path(__file__).resolve().parents[4]
BASE = dict(gh_patient_group="pediatric", gh_treatment_phase="initiation", gh_initiation_pathway="standard",
            gh_pubertal_status="prepubertal", gh_reported_growth_age_band="4_1_prepubertal",
            gh_chronological_age_years=8.2, bone_age_years=6.2, annual_growth_velocity_cm=4.99)


def evaluate(*, reverse=False, **kwargs):
    rules = list_drug_indication_rules()
    return evaluate_drug_indication_line_detailed(drug_line=replace(line(), **{**BASE, **kwargs}),
        claim=_claim(primary_icd10="E23.0"), diagnoses=[], rules=list(reversed(rules)) if reverse else rules)


def failed(result, criterion):
    hit = result["violation"]
    return hit is not None and criterion in hit.get("growth_hormone_failed_criteria", [])


@pytest.mark.parametrize("reverse", [False, True])
def test_known_source_path_selects_before_report_details(reverse):
    result = evaluate(reverse=reverse)
    assert result["selected_rule_id"] == "4.2.6.pediatric_somatropin_initiation_board"
    assert result["missing_inputs"] == ["gh_initiation_clinical_assessment"]
    assert result["violation"]["severity"] == "review"


@pytest.mark.parametrize("path", [None, "", "other", False, 0])
def test_no_path_is_inferred_from_diagnosis_or_numeric_measurements(path):
    result = evaluate(gh_initiation_pathway=path, annual_growth_velocity_cm=100)
    assert result["evaluation_status"] == "missing_inputs"
    assert result["missing_inputs"] == ["gh_initiation_pathway"]


@pytest.mark.parametrize("band,age,threshold", [("0_2_years", 1.5, 10), ("2_1_4_years", 3, 7), ("4_1_prepubertal", 8.2, 5)])
@pytest.mark.parametrize("delta,violates", [(-0.01, False), (0, True), (0.01, True)])
def test_strict_source_growth_band_boundaries(band, age, threshold, delta, violates):
    result = evaluate(gh_reported_growth_age_band=band, gh_chronological_age_years=age,
                      annual_growth_velocity_cm=threshold + delta)
    assert failed(result, "annual_growth_velocity_cm") is violates


def test_missing_band_never_comes_from_recorded_numeric_age():
    result = evaluate(gh_reported_growth_age_band=None, gh_chronological_age_years=2.05)
    assert "gh_reported_growth_age_band" in result["missing_inputs"]
    assert result["violation"]["severity"] == "review"


@pytest.mark.parametrize("age,bone,violates", [(8.2, 6.2, False), (8.2, 6.2001, True), (8.2, 6.1999, False),
                                              (4, 2, False), (4, 2.01, True), (3.99, None, False)])
def test_bone_age_delay_decimal_equality_and_under4_exception(age, bone, violates):
    result = evaluate(gh_chronological_age_years=age, bone_age_years=bone,
                      gh_reported_growth_age_band="2_1_4_years" if age <= 4 else "4_1_prepubertal")
    assert failed(result, "bone_age_years") is violates
    if age < 4:
        assert "bone_age_years" not in result["required_inputs"]
        assert "bone_age_years" not in result["missing_inputs"]


@pytest.mark.parametrize("assessed", [True, False, None])
def test_puberty_requires_explicit_specialist_assessment_instead_of_numeric_velocity(assessed):
    result = evaluate(gh_pubertal_status="pubertal", gh_reported_growth_age_band="pubertal",
                      gh_pubertal_growth_assessment_completed=assessed, annual_growth_velocity_cm=100,
                      bone_age_years=100, gh_chronological_age_years=None)
    assert failed(result, "gh_pubertal_growth_assessment_completed") is (assessed is False)
    assert "annual_growth_velocity_cm" not in result["required_inputs"]
    assert "bone_age_years" not in result["required_inputs"]
    if assessed is None:
        assert "gh_pubertal_growth_assessment_completed" in result["missing_inputs"]


def test_puberty_epiphy_closure_is_source_failure():
    assert failed(evaluate(gh_pubertal_status="pubertal", gh_reported_growth_age_band="pubertal",
                           gh_pubertal_growth_assessment_completed=True, epiphyses_closed=True), "epiphyses_closed")


@pytest.mark.parametrize("band,stage", [("pubertal", "prepubertal"), ("0_2_years", "pubertal")])
def test_conflicting_source_stage_is_review_before_measurement_conclusions(band, stage):
    result = evaluate(gh_reported_growth_age_band=band, gh_pubertal_status=stage,
                      annual_growth_velocity_cm=100, epiphyses_closed=True)
    assert result["missing_inputs"] == ["gh_growth_stage_reconciliation"]


@pytest.mark.parametrize("path", ["organic_or_surgical", "neurosecretory_bioinactive"])
def test_source_exception_paths_never_inherit_standard_clinical_or_report_requirements(path):
    result = evaluate(gh_initiation_pathway=path, annual_growth_velocity_cm=100, bone_age_years=100,
                      drug_specialty_board_report_present=False)
    assert result["missing_inputs"] == ["gh_initiation_clinical_assessment"]
    assert result["violation"]["severity"] == "review"
    assert "annual_growth_velocity_cm" not in result["required_inputs"]


def sga1(**kw):
    return evaluate(**{**dict.fromkeys(["gh_pubertal_status", "gh_reported_growth_age_band", "bone_age_years"]),
        "gh_initiation_pathway": "sga_case_1", "gh_birth_weight_for_gestational_age_sds": -2.01,
        "gh_chronological_age_years": 4, "gh_last_year_growth_velocity_sds": -0.01, **kw})


@pytest.mark.parametrize("weight,length,violates,missing", [(-2.01, None, False, False), (None, -2.01, False, False),
    (-2, -2, True, False), (-1.99, -1.99, True, False), (-2, None, False, True), (None, None, False, True)])
def test_sga_birth_weight_or_length_strict_threshold(weight, length, violates, missing):
    result = sga1(gh_birth_weight_for_gestational_age_sds=weight, gh_birth_length_for_gestational_age_sds=length)
    assert failed(result, "gh_birth_size_sds") is violates
    assert any(f.endswith("gestational_age_sds") for f in result["missing_inputs"]) is missing


@pytest.mark.parametrize("age,velocity,criterion", [(3.99, -0.01, "gh_chronological_age_years"),
    (4, 0, "gh_last_year_growth_velocity_sds"), (4.01, 0.01, "gh_last_year_growth_velocity_sds")])
def test_sga_case1_age_and_catchup_boundaries(age, velocity, criterion):
    assert failed(sga1(gh_chronological_age_years=age, gh_last_year_growth_velocity_sds=velocity), criterion)


def test_sga1_success_is_partial_and_does_not_request_standard_conditions():
    result = sga1(annual_growth_velocity_cm=100, epiphyses_closed=True)
    assert result["missing_inputs"] == ["gh_initiation_clinical_assessment"]
    assert "epiphyses_closed" not in result["required_inputs"]
    assert "gh_pubertal_status" not in result["required_inputs"]


def sga2(**kw):
    return evaluate(**{"gh_initiation_pathway": "sga_case_2", "gh_sga_birth_status_confirmed": True,
                       "gh_current_height_sds": -2.51, "gh_parent_adjusted_height_sds": -1.01, **kw})


@pytest.mark.parametrize("field,boundary", [("gh_current_height_sds", -2.5), ("gh_parent_adjusted_height_sds", -1)])
@pytest.mark.parametrize("delta,violates", [(-0.01, False), (0, True), (0.01, True)])
def test_sga_case2_both_strict_conditions(field, boundary, delta, violates):
    result = sga2(**{field: boundary + delta})
    assert failed(result, field) is violates


@pytest.mark.parametrize("confirmed", [False, None])
def test_sga_case2_scope_precedes_known_measurement_failure(confirmed):
    assert sga2(gh_sga_birth_status_confirmed=confirmed, gh_current_height_sds=0)["missing_inputs"] == ["gh_sga_birth_status_confirmed"]


def test_sga2_never_inherits_case1_age_or_catchup_conditions():
    result = sga2(gh_chronological_age_years=1, gh_last_year_growth_velocity_sds=100,
                  gh_birth_weight_for_gestational_age_sds=0, gh_birth_length_for_gestational_age_sds=0)
    assert result["missing_inputs"] == ["gh_initiation_clinical_assessment"]
    assert "gh_chronological_age_years" not in result["required_inputs"]


@pytest.mark.parametrize("drug,path", [("somatrogon", "sga_case_1"), ("somatrogon", "neurosecretory_bioinactive"),
    ("büyüme hormonu", "standard"), ("mecasermin", "standard")])
def test_exact_medicine_identity_cannot_receive_unrelated_pediatric_initiation_threshold(drug, path):
    result = evaluate(drug_name=drug, gh_initiation_pathway=path, annual_growth_velocity_cm=100)
    assert not failed(result, "annual_growth_velocity_cm")


@pytest.mark.parametrize("when", [None, "2026-10-02", datetime(2026, 10, 2), date(2024, 5, 16)])
def test_unknown_or_historical_source_precedes_new_conclusion(when):
    result = evaluate(drug_claim_date=when, annual_growth_velocity_cm=100)
    assert result["missing_inputs"] == (["historical_sut_version"] if type(when) is date else ["drug_claim_date"])


def test_current_heading_first_day_inclusive():
    assert failed(evaluate(drug_claim_date=date(2024, 5, 17), annual_growth_velocity_cm=100), "annual_growth_velocity_cm")


@pytest.mark.parametrize("field", PEDIATRIC_GH_SDS_FIELDS)
@pytest.mark.parametrize("v", [-2.5, 0, 2.5])
def test_signed_sds_are_explicit_finite_values(field, v):
    assert getattr(MaterialItem(name="somatropin", **{field: v}), field) == v


@pytest.mark.parametrize("field,v", [("gh_chronological_age_years", -1), ("gh_pubertal_status", "male"),
    ("gh_reported_growth_age_band", 4), ("gh_pubertal_growth_assessment_completed", 1),
    ("gh_sga_birth_status_confirmed", "false"), ("gh_current_height_sds", "-3"),
    ("gh_current_height_sds", True), ("gh_current_height_sds", float("nan")), ("gh_current_height_sds", float("inf"))])
def test_invalid_inputs_rejected_by_api_and_unknown_at_direct_boundary(field, v):
    with pytest.raises(ValidationError):
        MaterialItem(name="somatropin", **{field: v})
    row = {**asdict(line()), field: v}
    errors = []
    assert getattr(parse_drug_line(row, errors), field) is None
    assert errors


def test_new_inputs_survive_both_request_and_flat_ingest():
    facts = dict(gh_initiation_pathway="sga_case_1", gh_reported_growth_age_band="2_1_4_years",
                 gh_chronological_age_years=4, gh_pubertal_status="prepubertal",
                 gh_pubertal_growth_assessment_completed=False, gh_sga_birth_status_confirmed=False,
                 **dict.fromkeys(PEDIATRIC_GH_SDS_FIELDS, -2.7))
    assert set(facts) == set(PEDIATRIC_GH_INITIATION_FIELDS)
    item = MaterialItem(name="somatropin", **facts)
    context = build_context_from_material_dict({"claim_id": "gh-init", "materials": [item.model_dump()],
        "drug_context": {"primary_icd10": "E23.0"}})
    parsed = parse_drug_line({**asdict(line()), **facts}, [])
    # All fields have shared parser wiring; source assumptions cannot replace them.
    for field, value in facts.items():
        assert getattr(parsed, field) == value
        assert getattr(context.drug_lines[0], field) == value


def test_source_snapshot_and_exact_rule_metadata():
    source = json.loads((ROOT / 'data/gazette/source_evidence/pediatric_gh_initiation.json').read_text())
    assert source['verified_current_heading_from'] == '2024-05-17'
    for doc in source['sources']:
        assert len(doc['paragraphs']) == 20
        for row in doc['paragraphs']:
            assert hashlib.sha256(row['text'].encode()).hexdigest() == row['text_sha256']
            assert ''.join(run['text'] for run in row['runs'] if not run['struck']).strip() == row['active_text']
    rules = [r for r in list_drug_indication_rules() if r.get('pediatric_gh_initiation_protocol')]
    assert len(rules) == 3
    assert all('büyüme hormonu' not in r['drug_names'] for r in rules)


@pytest.mark.parametrize("field", ["annual_growth_velocity_cm", "bone_age_years", "gh_chronological_age_years",
                                   "gh_pubertal_status", "gh_reported_growth_age_band"])
def test_missing_standard_inputs_are_review(field):
    result = evaluate(**{field: None})
    assert result["violation"]["severity"] == "review"
    assert field in result["missing_inputs"]


@pytest.mark.parametrize("field", ["gh_chronological_age_years", "gh_last_year_growth_velocity_sds"])
def test_missing_sga_case1_conjunction_input_is_review(field):
    result = sga1(**{field: None})
    assert result["violation"]["severity"] == "review"
    assert field in result["missing_inputs"]


@pytest.mark.parametrize("field", ["gh_current_height_sds", "gh_parent_adjusted_height_sds"])
def test_missing_sga_case2_measurement_is_review(field):
    result = sga2(**{field: None})
    assert result["violation"]["severity"] == "review"
    assert field in result["missing_inputs"]


def test_missing_standard_stage_prevents_threshold_or_bone_conclusion():
    result = evaluate(gh_pubertal_status=None, annual_growth_velocity_cm=100, bone_age_years=100)
    assert result["violation"]["severity"] == "review"
    assert "gh_pubertal_status" in result["missing_inputs"]


def test_no_sds_age_band_or_puberty_inference_from_other_material_facts():
    item = MaterialItem(name="somatropin", birth_weight_kg=1.2, body_weight_kg=8,
                        height_cm=80, gestational_age_weeks=30, patient_sex="male")
    assert all(getattr(item, field) is None for field in PEDIATRIC_GH_INITIATION_FIELDS)


def test_continuation_ignores_every_new_initiation_field():
    result = evaluate(gh_treatment_phase="continuation", epiphyses_closed=False,
                      gh_height_reference_sex="female", height_cm=150, annual_growth_velocity_cm=5,
                      gh_initiation_pathway="sga_case_1", gh_birth_weight_for_gestational_age_sds=0,
                      gh_last_year_growth_velocity_sds=100, gh_chronological_age_years=0)
    assert result["violation"] is None


@pytest.mark.parametrize("band,age,growth", [("2_1_4_years", 1.5, 8), ("4_1_prepubertal", 1.5, 100),
                                     ("4_1_prepubertal", 3.5, 100), ("0_2_years", 3, 100), ("2_1_4_years", 8, 100)])
def test_clear_age_band_contradictions_are_review_before_any_threshold(band, age, growth):
    result = evaluate(gh_reported_growth_age_band=band, gh_chronological_age_years=age,
                      annual_growth_velocity_cm=growth, bone_age_years=100)
    assert result["missing_inputs"] == ["gh_growth_stage_reconciliation"]
    assert result["violation"]["severity"] == "review"


@pytest.mark.parametrize("band,age", [("0_2_years", 2.05), ("2_1_4_years", 2.05),
                                     ("2_1_4_years", 4.05), ("4_1_prepubertal", 4.05)])
def test_ambiguous_printed_transition_regions_are_not_reclassified(band, age):
    result = evaluate(gh_reported_growth_age_band=band, gh_chronological_age_years=age,
                      annual_growth_velocity_cm=0, bone_age_years=0)
    assert result["missing_inputs"] == ["gh_initiation_clinical_assessment"]
    assert result["violation"]["severity"] == "review"
