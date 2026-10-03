"""Necessary mecasermin stops on verified source dates, not invented law dates."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, replace
from datetime import date
import hashlib
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from src.bilun.domain.claims.adapter import build_context_from_material_dict
from src.bilun.domain.claims.parsing.row_parsers import parse_drug_line
from src.bilun.domain.prose_rules.drug_indication import evaluate_drug_indication_line_detailed, list_drug_indication_rules
from src.bilun.shared.models import MaterialItem
from tests.unit.domain.prose_rules.test_growth_hormone_continuation import line, _claim

pytestmark = pytest.mark.unit
ROOT = Path(__file__).resolve().parents[4]
RULE_ID = "4.2.6.laron_mecasermin_continuation_board"
FIELDS = ("epiphyses_closed", "annual_growth_velocity_cm", "pretreatment_annual_growth_velocity_cm",
          "height_cm", "gh_height_reference_sex", "height_percentile")
BASE = {"drug_name": "INCRELEX (MECASERMIN)", "drug_claim_date": date(2026, 10, 2),
        "mecasermin_laron_syndrome_confirmed": True, "gh_treatment_phase": "continuation",
        "epiphyses_closed": False, "annual_growth_velocity_cm": 5.2,
        "pretreatment_annual_growth_velocity_cm": 3.2, "height_cm": 154.99,
        "gh_height_reference_sex": "female", "height_percentile": 24.99, "mecasermin_daily_dose_mcg_per_kg": 120}


def evaluate(*, reverse=False, rules=None, **overrides):
    chosen = list_drug_indication_rules() if rules is None else rules
    return evaluate_drug_indication_line_detailed(
        drug_line=replace(line(), **{**BASE, **overrides}), claim=_claim(primary_icd10="E34.31"),
        diagnoses=[], rules=list(reversed(chosen)) if reverse else chosen)


@pytest.mark.parametrize("when", [date(2026, 8, 29), date(2026, 10, 2)])
@pytest.mark.parametrize("reverse", [False, True])
def test_negative_screen_on_supported_source_dates_is_still_partial_review(when, reverse):
    result = evaluate(drug_claim_date=when, reverse=reverse)
    assert result["selected_rule_id"] == RULE_ID
    assert result["violation"]["severity"] == "review"
    assert result["missing_inputs"] == ["mecasermin_remaining_clinical_criteria"]


@pytest.mark.parametrize("when", [date(2013, 3, 24), date(2017, 9, 23), date(2026, 8, 28),
                                  date(2026, 8, 30), date(2026, 9, 15), date(2026, 10, 1),
                                  date(2026, 10, 4), date(2027, 1, 1)])
def test_every_unverified_service_date_is_review_including_between_snapshots(when):
    result = evaluate(drug_claim_date=when, epiphyses_closed=True,
                      drug_specialty_board_report_present=False)
    assert result["violation"]["severity"] == "review"
    assert result["missing_inputs"] == ["mecasermin_source_version"]


def test_no_service_date_is_not_replaced_by_today():
    result = evaluate(drug_claim_date=None, epiphyses_closed=True)
    assert result["missing_inputs"] == ["drug_claim_date"]


@pytest.mark.parametrize("overrides,criterion", [
    ({"epiphyses_closed": True}, "epiphyses_closed"),
    ({"annual_growth_velocity_cm": 5.19, "pretreatment_annual_growth_velocity_cm": 3.2},
     "growth_velocity_gain_under_2_cm_per_year"),
    ({"height_cm": 155, "gh_height_reference_sex": "female"}, "height_cm"),
    ({"height_percentile": 25}, "height_percentile"),
])
def test_each_known_stop_dominates_other_missing_measurements(overrides, criterion):
    result = evaluate(**{**dict.fromkeys(FIELDS), **overrides})
    hit = result["violation"]
    assert hit["violation_kind"] == "growth_hormone_continuation_stop"
    assert hit["growth_hormone_stop_criteria"] == [criterion]
    assert result["evaluation_status"] == "evaluated"
    assert result["missing_inputs"] == []
    assert "2026-10-02" in hit["message_tr"]
    assert not any(k in hit for k in ["savings_try", "payable_try", "recoverable_uplift_try"])


@pytest.mark.parametrize("baseline,current,stop", [(0, 1.9999, True), (0, 2, False),
    (3.2, 5.19999, True), (3.2, 5.2, False), (3.2, 5.20001, False), (7, 6, True)])
def test_growth_gain_strict_two_cm_boundary_uses_decimal_values(baseline, current, stop):
    hit = evaluate(annual_growth_velocity_cm=current, pretreatment_annual_growth_velocity_cm=baseline)["violation"]
    assert (hit["severity"] == "error") is stop


@pytest.mark.parametrize("sex,height,stop", [("female", 154.99, False), ("female", 155, True),
    ("male", 164.99, False), ("male", 165, True), ("male", 166, True)])
def test_height_thresholds_are_sex_reference_specific(sex, height, stop):
    hit = evaluate(gh_height_reference_sex=sex, height_cm=height)["violation"]
    assert (hit["severity"] == "error") is stop


@pytest.mark.parametrize("percentile,stop", [(0, False), (24.9999, False), (25, True), (25.001, True), (100, True)])
def test_height_percentile_boundary(percentile, stop):
    assert (evaluate(height_percentile=percentile)["violation"]["severity"] == "error") is stop


@pytest.mark.parametrize("field", FIELDS)
def test_missing_measurements_remain_unknown(field):
    result = evaluate(**{field: None})
    assert result["violation"]["severity"] == "review"
    assert set(result["missing_inputs"]) == {field, "mecasermin_remaining_clinical_criteria"}


@pytest.mark.parametrize("field,value", [("mecasermin_laron_syndrome_confirmed", None),
    ("mecasermin_laron_syndrome_confirmed", False), ("gh_treatment_phase", None)])
def test_diagnosis_or_measurements_do_not_supply_scope_or_phase(field, value):
    result = evaluate(**{field: value}, epiphyses_closed=True, drug_specialty_board_report_present=False)
    assert result["violation"]["severity"] == "review"
    assert field in result["missing_inputs"]


def test_initial_phase_does_not_apply_continuation_stop():
    result = evaluate(gh_treatment_phase="initiation", epiphyses_closed=True, mecasermin_daily_dose_mcg_per_kg=120)
    assert result["selected_rule_id"] == "4.2.6.laron_mecasermin_initiation_board"
    assert result["violation"]["severity"] == "review"
    assert result["missing_inputs"] == ["mecasermin_remaining_clinical_criteria"]


@pytest.mark.parametrize("name", ["SOMATROPIN", "SOMATROGON", "IGF1", "IGF-1", "rhigf", "büyüme hormonu"])
def test_unidentified_or_other_drug_never_gets_mecasermin_stop(name):
    result = evaluate(drug_name=name, epiphyses_closed=True)
    assert result["selected_rule_id"] != RULE_ID


def test_source_points_cannot_be_relabeled_as_legal_start():
    rules = deepcopy(list_drug_indication_rules())
    for rule in rules:
        if rule.get("mecasermin_source_scope"):
            rule["mecasermin_source_authority"]["legal_valid_from"] = "2013-03-24"
    result = evaluate(rules=rules, epiphyses_closed=True)
    assert result["violation"]["severity"] == "review"
    assert result["missing_inputs"] == ["mecasermin_source_version"]


@pytest.mark.parametrize("field,value", [("mecasermin_laron_syndrome_confirmed", "true"),
    ("pretreatment_annual_growth_velocity_cm", -1), ("pretreatment_annual_growth_velocity_cm", "3.2"),
    ("pretreatment_annual_growth_velocity_cm", float("nan")), ("height_percentile", -0.01),
    ("height_percentile", 100.01), ("height_percentile", float("inf")), ("height_percentile", True)])
def test_invalid_input_is_not_coerced_into_a_clinical_fact(field, value):
    with pytest.raises(ValidationError):
        MaterialItem(name="mecasermin", **{field: value})
    result = evaluate(**{field: value})
    assert result["violation"]["severity"] == "review"
    assert field in result["missing_inputs"]


def test_new_inputs_survive_api_model_adapter_and_parser_without_defaults():
    keys = ("mecasermin_laron_syndrome_confirmed", "pretreatment_annual_growth_velocity_cm", "height_percentile", "mecasermin_daily_dose_mcg_per_kg")
    values = {key: BASE[key] for key in keys}
    item = MaterialItem(name="mecasermin", **values)
    context = build_context_from_material_dict({"claim_id": "M", "materials": [item.model_dump()],
        "drug_context": {"primary_icd10": "E34.31"}})
    assert {key: getattr(context.drug_lines[0], key) for key in keys} == values
    errors = []
    parsed = parse_drug_line(asdict(replace(line(), **values)), errors)
    assert errors == []
    assert {key: getattr(parsed, key) for key in keys} == values
    assert all(MaterialItem(name="mecasermin").model_dump()[key] is None for key in keys)


def test_original_sources_include_numbered_bullets_and_explicit_history_limit():
    evidence = json.loads((ROOT / "data/gazette/source_evidence/mecasermin_known_as_of_continuation.json").read_text())
    assert evidence["legal_valid_from"] is None
    assert evidence["known_as_of_dates"] == ["2026-08-29", "2026-10-02"]
    assert evidence["coverage_kind"] == "verified_snapshot_dates_only"
    assert "Every date other" in evidence["unserved_service_dates"]
    assert "49,709,128" in evidence["historical_source_research"]["result"]
    for version in evidence["sources"]:
        for row in version["paragraphs"]:
            assert hashlib.sha256(row["text"].encode()).hexdigest() == row["text_sha256"]
        numbered = [row for row in version["paragraphs"] if row.get("word_numbering")]
        assert len(numbered) == 3
        assert all(row["word_numbering"]["format"] == "lowerLetter" for row in numbered)
        assert all(row["word_numbering"]["level_text"] == "%3)" for row in numbered)
        assert all(not run["struck"] for row in version["paragraphs"] for run in row["runs"] if run["text"].strip())
    assert [row["text"] for row in evidence["sources"][0]["paragraphs"]] == \
           [row["text"] for row in evidence["sources"][1]["paragraphs"]]


@pytest.mark.parametrize("authority", [None, [], {}, {"known_as_of_dates": "2026-10-02"},
    {"legal_valid_from": None, "known_as_of_dates": ["2026-10-02"], "coverage_kind": "legal_interval"}])
def test_malformed_source_authority_stays_review(authority):
    rules = deepcopy(list_drug_indication_rules())
    for rule in rules:
        if rule.get("mecasermin_source_scope"):
            rule["mecasermin_source_authority"] = authority
    result = evaluate(rules=rules, epiphyses_closed=True)
    assert result["violation"]["severity"] == "review"
    assert result["missing_inputs"] == ["mecasermin_source_version"]


@pytest.mark.parametrize("dose,exceeded", [(0, False), (119.999, False), (120, False), (120.001, True), (121, True)])
def test_initiation_dose_ceiling_is_120_micrograms_per_kg_per_day(dose, exceeded):
    result = evaluate(gh_treatment_phase="initiation", mecasermin_daily_dose_mcg_per_kg=dose)
    assert (result["violation"]["violation_kind"] == "mecasermin_initial_dose_exceeded") is exceeded
    assert result["violation"]["severity"] == ("error" if exceeded else "review")


def test_initial_dose_limit_not_applied_to_continuation():
    assert evaluate(mecasermin_daily_dose_mcg_per_kg=121)["violation"]["severity"] == "review"


def test_no_initial_dose_inferred_from_ckd_milligram_input_or_dispensed_quantity():
    result = evaluate(gh_treatment_phase="initiation", mecasermin_daily_dose_mcg_per_kg=None,
                      gh_daily_dose_mg_per_kg=0.12, quantity=120)
    assert "mecasermin_daily_dose_mcg_per_kg" in result["missing_inputs"]
    assert result["violation"]["severity"] == "review"


@pytest.mark.parametrize("value", ["120", -1, float("inf"), True])
def test_invalid_initial_dose_never_coerces(value):
    with pytest.raises(ValidationError):
        MaterialItem(name="mecasermin", mecasermin_daily_dose_mcg_per_kg=value)
    result = evaluate(gh_treatment_phase="initiation", mecasermin_daily_dose_mcg_per_kg=value)
    assert result["violation"]["severity"] == "review"
    assert "mecasermin_daily_dose_mcg_per_kg" in result["missing_inputs"]


def test_initiation_review_honestly_mentions_its_partial_dose_check():
    message = evaluate(gh_treatment_phase="initiation")["violation"]["message_tr"]
    assert "doz üst sınırı kontrolü" in message
    assert "yalnız devam" not in message
