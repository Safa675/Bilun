"""PWS initiation exclusions use recorded source criteria, never inferred obesity."""
from __future__ import annotations

from dataclasses import asdict, replace
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from src.bilun.domain.claims.growth_hormone import PWS_INITIATION_EXCLUSION_FIELDS
from src.bilun.domain.claims.parsing.row_parsers import parse_drug_line
from src.bilun.shared.models import MaterialItem
from tests.unit.domain.prose_rules.test_growth_hormone_continuation import line
from tests.unit.domain.prose_rules.test_pws_gh_continuation import evaluate

pytestmark = pytest.mark.unit
ROOT = Path(__file__).resolve().parents[4]
FIELDS = (*PWS_INITIATION_EXCLUSION_FIELDS, "epiphyses_closed")


def initiation(**overrides):
    return evaluate(**{"gh_treatment_phase": "initiation", "drug_report_duration_months": 3,
                       **dict.fromkeys(FIELDS, False), **overrides})


@pytest.mark.parametrize("field", FIELDS)
def test_any_source_initiation_exclusion_is_decisive(field):
    result = initiation(**{**dict.fromkeys(FIELDS), field: True})
    assert result["violation"]["violation_kind"] == "growth_hormone_initiation_exclusion"
    assert result["violation"]["growth_hormone_exclusion_criteria"] == [field]
    assert result["evaluation_status"] == "evaluated"
    assert result["missing_inputs"] == []


def test_explicit_negative_exclusions_still_need_other_initiation_assessment():
    result = initiation()
    assert result["violation"]["severity"] == "review"
    assert result["missing_inputs"] == ["pws_initiation_clinical_assessment"]
    assert "pws_progressive_scoliosis" not in result["required_inputs"]


@pytest.mark.parametrize("field", FIELDS)
def test_unknown_exclusion_is_never_defaulted_absent(field):
    result = initiation(**{field: None})
    assert set(result["missing_inputs"]) == {field, "pws_initiation_clinical_assessment"}
    assert result["violation"]["severity"] == "review"


def test_scoliosis_is_not_an_initiation_exclusion():
    assert initiation(pws_progressive_scoliosis=True)["violation"]["severity"] == "review"


def test_obesity_source_criterion_is_not_a_continuation_stop():
    result = evaluate(pws_severe_obesity_source_criterion_present=True)
    assert result["violation"]["severity"] == "review"
    assert result["missing_inputs"] == ["pws_remaining_clinical_criteria"]
    assert "pws_severe_obesity_source_criterion_present" not in result["required_inputs"]


@pytest.mark.parametrize("value", ["false", 0, 1, {}, []])
def test_source_assessment_is_strict_boolean(value):
    with pytest.raises(ValidationError):
        MaterialItem(name="somatropin", pws_severe_obesity_source_criterion_present=value)
    result = initiation(pws_severe_obesity_source_criterion_present=value)
    assert "pws_severe_obesity_source_criterion_present" in result["missing_inputs"]


def test_scope_precedes_known_exclusion():
    result = initiation(pws_genetic_diagnosis_confirmed=None,
                        pws_severe_obesity_source_criterion_present=True)
    assert result["violation"]["severity"] == "review"
    assert result["missing_inputs"] == ["pws_genetic_diagnosis_confirmed"]


def test_no_obesity_inference_from_unrelated_numeric_data():
    item = MaterialItem(name="somatropin", body_weight_kg=100, ideal_weight_kg=30, bmi=35)
    assert item.pws_severe_obesity_source_criterion_present is None
    row = asdict(line())
    row.update(body_weight_kg=100, ideal_weight_kg=30, bmi=35)
    errors = []
    assert parse_drug_line(row, errors).pws_severe_obesity_source_criterion_present is None
    assert errors == []


@pytest.mark.parametrize("value", [None, False, True])
def test_explicit_assessment_survives_parquet_input(value):
    errors = []
    parsed = parse_drug_line(asdict(replace(line(), pws_severe_obesity_source_criterion_present=value)), errors)
    assert errors == []
    assert parsed.pws_severe_obesity_source_criterion_present is value


def test_source_wording_and_phase_sets_remain_distinct():
    source = json.loads((ROOT / "data/gazette/source_evidence/pws_somatropin_continuation.json").read_text())
    assert "%225" in source["field_semantics"]["pws_severe_obesity_source_criterion_present"]
    assert "pws_severe_obesity_source_criterion_present" in source["initiation_exclusion_if_any_true"]
    assert "pws_severe_obesity_source_criterion_present" not in source["continuation_stop_if_any_true"]
    assert "pws_progressive_scoliosis" not in source["initiation_exclusion_if_any_true"]
