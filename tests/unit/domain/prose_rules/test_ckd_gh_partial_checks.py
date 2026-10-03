"""No inferred persistence/disease: CKD GH dose and initiation source checks."""
from __future__ import annotations

from dataclasses import asdict, replace
from datetime import date
import hashlib
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from src.bilun.domain.claims.adapter import build_context_from_material_dict
from src.bilun.domain.claims.growth_hormone import CKD_GH_BOOLEAN_FIELDS, CKD_GH_NUMERIC_FIELDS
from src.bilun.domain.claims.parsing.row_parsers import parse_drug_line
from src.bilun.domain.prose_rules.drug_indication import evaluate_drug_indication_line_detailed, list_drug_indication_rules
from src.bilun.shared.models import MaterialItem
from tests.unit.domain.prose_rules.test_growth_hormone_continuation import line, _claim

pytestmark = pytest.mark.unit
ROOT = Path(__file__).resolve().parents[4]
BASE = {**dict.fromkeys(CKD_GH_BOOLEAN_FIELDS, False), "ckd_growth_disorder_confirmed": True,
        "gh_patient_group": "pediatric", "gh_treatment_phase": "initiation",
        "drug_report_duration_months": 6, "ckd_parathyroid_hormone_pg_ml": 499.9,
        "gh_daily_dose_mg_per_kg": 0.045, "epiphyses_closed": False}
FLAGS = (*CKD_GH_BOOLEAN_FIELDS[2:], "epiphyses_closed")


def evaluate(*, reverse=False, icd="N18.5", **overrides):
    rules = list_drug_indication_rules()
    return evaluate_drug_indication_line_detailed(
        drug_line=replace(line(), **{**BASE, **overrides}), claim=_claim(primary_icd10=icd), diagnoses=[],
        rules=list(reversed(rules)) if reverse else rules)


@pytest.mark.parametrize("reverse", [False, True])
@pytest.mark.parametrize("phase", ["initiation", "continuation"])
def test_negative_partial_checks_never_claim_complete_eligibility(reverse, phase):
    result = evaluate(reverse=reverse, gh_treatment_phase=phase)
    assert result["violation"]["severity"] == "review"
    assert result["evaluation_status"] == "missing_inputs"
    assert result["missing_inputs"] == [f"ckd_growth_{phase}_clinical_assessment"]


@pytest.mark.parametrize("field", FLAGS)
def test_known_initiation_exclusion_dominates_unknown_other_clinical_facts(field):
    values = {**dict.fromkeys(CKD_GH_BOOLEAN_FIELDS[1:]), "epiphyses_closed": None,
              "ckd_parathyroid_hormone_pg_ml": None, "gh_daily_dose_mg_per_kg": None}
    values[field] = True
    result = evaluate(**values)
    assert result["violation"]["violation_kind"] == "growth_hormone_initiation_exclusion"
    assert result["violation"]["growth_hormone_exclusion_criteria"] == [field]
    assert result["evaluation_status"] == "evaluated"
    assert result["missing_inputs"] == []


@pytest.mark.parametrize("pth,violation", [(499.99, False), (500, True), (500.01, True)])
def test_pth_initiation_boundary_is_independent_of_persistence(pth, violation):
    hit = evaluate(ckd_parathyroid_hormone_pg_ml=pth,
                   ckd_persistent_severe_secondary_hyperparathyroidism=None)["violation"]
    assert (hit["violation_kind"] == "growth_hormone_initiation_exclusion") is violation
    if violation:
        assert hit["growth_hormone_exclusion_criteria"] == ["ckd_parathyroid_hormone_pg_ml"]
        assert "persistan" not in hit["message_tr"]


def test_persistent_condition_requires_explicit_flag_plus_numeric_threshold():
    hit = evaluate(ckd_parathyroid_hormone_pg_ml=500,
                   ckd_persistent_severe_secondary_hyperparathyroidism=True)["violation"]
    assert hit["growth_hormone_exclusion_criteria"] == ["ckd_parathyroid_hormone_pg_ml",
        "ckd_persistent_severe_secondary_hyperparathyroidism"]
    result = evaluate(ckd_parathyroid_hormone_pg_ml=None,
                      ckd_persistent_severe_secondary_hyperparathyroidism=True)
    assert result["violation"]["severity"] == "review"
    assert "ckd_parathyroid_hormone_pg_ml" in result["missing_inputs"]


def test_contradictory_persistent_condition_and_low_pth_needs_reconciliation():
    result = evaluate(ckd_persistent_severe_secondary_hyperparathyroidism=True)
    assert result["violation"]["severity"] == "review"
    assert "ckd_parathyroid_status_reconciliation" in result["missing_inputs"]


@pytest.mark.parametrize("phase", ["initiation", "continuation"])
@pytest.mark.parametrize("dose,outside", [(0, True), (0.044999, True), (0.045, False),
                                         (0.0475, False), (0.05, False), (0.050001, True)])
def test_dose_range_is_inclusive_and_weight_normalized(phase, dose, outside):
    result = evaluate(gh_treatment_phase=phase, gh_daily_dose_mg_per_kg=dose)
    assert (result["violation"]["violation_kind"] == "growth_hormone_dose_out_of_range") is outside
    assert result["violation"]["severity"] == ("error" if outside else "review")
    assert not any(k in result["violation"] for k in ["savings_try", "payable_try", "recoverable_uplift_try"])


def test_initiation_exclusions_are_not_copied_into_continuation():
    result = evaluate(gh_treatment_phase="continuation", ckd_first_post_transplant_year=True,
                      ckd_active_cancer=True, ckd_parathyroid_hormone_pg_ml=800)
    assert result["violation"]["severity"] == "review"
    assert result["missing_inputs"] == ["ckd_growth_continuation_clinical_assessment"]


@pytest.mark.parametrize("field", [*CKD_GH_BOOLEAN_FIELDS[1:], *CKD_GH_NUMERIC_FIELDS, "epiphyses_closed"])
def test_missing_clinical_inputs_stay_missing(field):
    result = evaluate(**{field: None})
    assert result["violation"]["severity"] == "review"
    assert field in result["missing_inputs"]


@pytest.mark.parametrize("icd", ["N18.5", "N19", "N25", "Z99.2"])
def test_renal_or_dialysis_codes_cannot_confirm_growth_indication(icd):
    result = evaluate(icd=icd, ckd_growth_disorder_confirmed=None,
                      epiphyses_closed=True, drug_specialty_board_report_present=False)
    assert result["violation"]["severity"] == "review"
    assert "ckd_growth_disorder_confirmed" in result["missing_inputs"]


@pytest.mark.parametrize("field,value", [("gh_patient_group", None), ("gh_patient_group", "adult"),
                                        ("gh_treatment_phase", None), ("ckd_growth_disorder_confirmed", False)])
def test_known_scope_before_report_or_clinical_exclusion(field, value):
    result = evaluate(**{field: value}, epiphyses_closed=True,
                      drug_specialty_board_report_present=False)
    assert result["violation"]["severity"] == "review"
    assert field in result["missing_inputs"]


@pytest.mark.parametrize("when", [None, date(2024, 5, 16)])
def test_date_authority_precedes_current_report_or_clinical_failure(when):
    result = evaluate(drug_claim_date=when, epiphyses_closed=True, drug_specialty_board_report_present=False)
    assert result["violation"]["severity"] == "review"
    assert result["missing_inputs"] == (["drug_claim_date"] if when is None else ["historical_sut_version"])


def test_current_heading_first_day_enforces_known_exclusion():
    assert evaluate(drug_claim_date=date(2024, 5, 17), epiphyses_closed=True)["violation"]["severity"] == "error"


@pytest.mark.parametrize("drug", ["SOMATROGON", "büyüme hormonu", "buyume hormonu", "MECASERMIN"])
def test_other_or_unidentified_growth_drug_does_not_get_ckd_protocol(drug):
    result = evaluate(drug_name=drug, epiphyses_closed=True, gh_daily_dose_mg_per_kg=1)
    assert (result["violation"] or {}).get("violation_kind") not in {
        "growth_hormone_initiation_exclusion", "growth_hormone_dose_out_of_range"}


@pytest.mark.parametrize("field,value", [("ckd_parathyroid_hormone_pg_ml", "500"),
    ("ckd_parathyroid_hormone_pg_ml", float("nan")), ("gh_daily_dose_mg_per_kg", float("inf")),
    ("gh_daily_dose_mg_per_kg", -1), ("ckd_first_post_transplant_year", "false"),
    ("ckd_persistent_severe_secondary_hyperparathyroidism", 1)])
def test_invalid_fields_do_not_coerce_to_claims(field, value):
    with pytest.raises(ValidationError):
        MaterialItem(name="somatropin", **{field: value})
    result = evaluate(**{field: value})
    assert result["violation"]["severity"] == "review"
    assert field in result["missing_inputs"]


def test_explicit_values_and_unknowns_survive_ingestion():
    keys = (*CKD_GH_BOOLEAN_FIELDS, *CKD_GH_NUMERIC_FIELDS)
    values = {key: BASE[key] for key in keys}
    item = MaterialItem(name="somatropin", **values)
    context = build_context_from_material_dict({"claim_id": "CKD", "materials": [item.model_dump()],
        "drug_context": {"primary_icd10": "N18.5"}})
    assert {key: getattr(context.drug_lines[0], key) for key in keys} == values
    errors = []
    parsed = parse_drug_line(asdict(replace(line(), **values)), errors)
    assert errors == []
    assert {key: getattr(parsed, key) for key in keys} == values
    assert all(MaterialItem(name="somatropin").model_dump()[key] is None for key in keys)


def test_original_source_hashes_and_heading_scope():
    evidence = json.loads((ROOT / "data/gazette/source_evidence/ckd_somatropin_partial_checks.json").read_text())
    assert evidence["verified_current_heading_from"] == "2024-05-17"
    assert evidence["dose_mg_per_kg_per_day_inclusive"] == [0.045, 0.05]
    for version in evidence["sources"]:
        for row in version["paragraphs"]:
            assert hashlib.sha256(row["text"].encode()).hexdigest() == row["text_sha256"]
        heading = version["paragraphs"][2]
        assert "somatropin" in heading["text"]
        assert all(not r["struck"] for r in heading["runs"] if r["text"].strip())
        assert "17/05/2024" in version["paragraphs"][0]["text"]
    assert [r["text"] for r in evidence["sources"][0]["paragraphs"]] == \
           [r["text"] for r in evidence["sources"][1]["paragraphs"]]
