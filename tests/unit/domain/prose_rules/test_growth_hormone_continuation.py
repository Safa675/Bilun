"""Source-pinned, explicitly entered Turner continuation facts and boundaries."""
from __future__ import annotations

from dataclasses import asdict, replace
from datetime import date, datetime
import hashlib
import json
from pathlib import Path

import pytest
from pydantic import ValidationError
import yaml

from src.bilun.domain.claims.adapter import build_context_from_material_dict
from src.bilun.domain.claims.growth_hormone import GROWTH_HORMONE_FIELDS
from src.bilun.domain.claims.parsing.row_parsers import parse_drug_line
from src.bilun.domain.prose_rules.drug_indication import (
    evaluate_drug_indication_line_detailed,
    list_drug_indication_rules,
)
from src.bilun.domain.prose_rules._drug_indication.routing import _semantic_route_signature
from src.bilun.shared.models import MaterialItem
from tests.unit.domain.prose_rules.test_drug_indication_4206 import _claim, _drug_line

pytestmark = pytest.mark.unit
ROOT = Path(__file__).resolve().parents[4]
RULE_ID = "4.2.6.turner_somatropin_pediatric_board"
VALID = dict(gh_treatment_phase="continuation", epiphyses_closed=False,
             annual_growth_velocity_cm=4.01, height_cm=154.99, bone_age_years=13.99)


def line(**overrides):
    return replace(_drug_line(drug_name="GENOTROPIN (SOMATROPIN)", report_present=True,
                             report_duration_months=12, prescriber_specialty="çocuk endokrinoloji"),
                   **{**VALID, **overrides})


def evaluate(**overrides):
    return evaluate_drug_indication_line_detailed(
        drug_line=line(**overrides), claim=_claim(primary_icd10="Q96.9"), diagnoses=[],
    )


def test_known_negative_stops_pass_only_this_constraint():
    result = evaluate()
    assert result["selected_rule_id"] == RULE_ID
    assert result["violation"] is None
    assert result["evaluation_status"] == "evaluated"


@pytest.mark.parametrize("field,value", [
    ("epiphyses_closed", True),
    ("annual_growth_velocity_cm", 4), ("annual_growth_velocity_cm", 0),
    ("height_cm", 155), ("height_cm", 160),
    ("bone_age_years", 14), ("bone_age_years", 15),
])
def test_any_one_stop_dominates_missing_other_clinical_measurements(field, value):
    fields = dict.fromkeys(GROWTH_HORMONE_FIELDS[1:])
    fields[field] = value
    result = evaluate(**fields)
    hit = result["violation"]
    assert hit["violation_kind"] == "growth_hormone_continuation_stop"
    assert hit["growth_hormone_stop_criteria"] == [field]
    assert hit["severity"] == "error"
    assert hit["missing_inputs"] == []
    assert result["evaluation_status"] == "evaluated"
    assert not any(k in hit for k in ["savings_try", "payable_try", "recoverable_uplift_try"])


def test_all_positive_stops_are_retained():
    hit = evaluate(epiphyses_closed=True, annual_growth_velocity_cm=4,
                   height_cm=155, bone_age_years=14)["violation"]
    assert hit["growth_hormone_stop_criteria"] == list(GROWTH_HORMONE_FIELDS[1:])


@pytest.mark.parametrize("field", GROWTH_HORMONE_FIELDS)
def test_missing_field_is_review_not_pass(field):
    result = evaluate(**{field: None})
    assert result["violation"]["violation_kind"] == "needs_growth_hormone_verification"
    assert result["violation"]["severity"] == "review"
    assert result["missing_inputs"] == [field]
    assert result["evaluation_status"] == "missing_inputs"


@pytest.mark.parametrize("phase", [None, "", "unknown", True, 1])
def test_phase_is_never_inferred_from_q96_or_measurements(phase):
    result = evaluate(gh_treatment_phase=phase, epiphyses_closed=True)
    assert result["evaluation_status"] == "missing_inputs"
    assert result["missing_inputs"] == ["gh_treatment_phase"]


def test_explicit_initiation_bypasses_continuation_constraint():
    result = evaluate(gh_treatment_phase="initiation", epiphyses_closed=True)
    assert result["violation"] is None


@pytest.mark.parametrize("when", [None, "2026-10-02", datetime(2026, 10, 2), date(2024, 5, 16)])
def test_missing_invalid_or_pre_heading_date_cannot_apply_current_stop(when):
    result = evaluate(drug_claim_date=when, epiphyses_closed=True)
    assert result["violation"]["violation_kind"] == "needs_growth_hormone_verification"
    assert result["evaluation_status"] == "missing_inputs"
    assert result["missing_inputs"] == (["historical_sut_version"] if type(when) is date
                                        else ["drug_claim_date"])


@pytest.mark.parametrize("when", [date(2024, 5, 17), date(2026, 8, 29), date(2026, 10, 2)])
def test_heading_date_boundary_is_inclusive(when):
    assert evaluate(drug_claim_date=when, height_cm=155)["violation"]["violation_kind"] == \
        "growth_hormone_continuation_stop"


@pytest.mark.parametrize("field,value", [
    ("epiphyses_closed", "false"), ("epiphyses_closed", 1),
    ("annual_growth_velocity_cm", True), ("annual_growth_velocity_cm", -1),
    ("annual_growth_velocity_cm", "4"), ("annual_growth_velocity_cm", float("nan")),
    ("height_cm", 0), ("height_cm", float("inf")),
    ("bone_age_years", -1), ("bone_age_years", float("-inf")),
])
def test_invalid_clinical_values_are_unknown_and_api_rejects_them(field, value):
    result = evaluate(**{field: value})
    assert result["evaluation_status"] == "missing_inputs"
    assert result["missing_inputs"] == [field]
    with pytest.raises(ValidationError):
        MaterialItem(name="somatropin", **{field: value})


@pytest.mark.parametrize("drug", ["NGENLA (SOMATROGON)", "büyüme hormonu", "MECASERMIN"])
def test_other_or_unidentified_gh_never_uses_turner_somatropin_gate(drug):
    result = evaluate(drug_name=drug, epiphyses_closed=True)
    assert result["selected_rule_id"] != RULE_ID
    assert (result["violation"] or {}).get("violation_kind") != "growth_hormone_continuation_stop"


@pytest.mark.parametrize("icd", ["E23.0", "Q87.1", "N18.5"])
def test_non_turner_diagnosis_does_not_reuse_turner_thresholds(icd):
    result = evaluate_drug_indication_line_detailed(
        drug_line=line(epiphyses_closed=True), claim=_claim(primary_icd10=icd), diagnoses=[])
    assert result["selected_rule_id"] != RULE_ID
    assert (result["violation"] or {}).get("violation_kind") != "growth_hormone_continuation_stop"


def test_source_and_compiled_rule_and_constraint_semantics_are_pinned():
    source = json.loads((ROOT / "data/gazette/source_evidence/turner_somatropin_continuation.json").read_text())
    assert source["verified_current_heading_from"] == "2024-05-17"
    assert source["verification_status"] == "ai_generated_pending_review"
    for version in source["sources"]:
        assert len(version["docx_sha256"]) == 64
        for paragraph in version["paragraphs"]:
            assert hashlib.sha256(paragraph["text"].encode()).hexdigest() == paragraph["text_sha256"]
        assert version["paragraphs"][2]["has_struck_runs"] is True
        assert all(not p["has_struck_runs"] for p in version["paragraphs"][3:])
    assert [p["text"] for p in source["sources"][0]["paragraphs"]] == \
           [p["text"] for p in source["sources"][1]["paragraphs"]]
    rule = next(r for r in list_drug_indication_rules() if r["rule_id"] == RULE_ID)
    yaml_rule = yaml.safe_load((ROOT / "data/gazette/prose_rule_sources/drug_indication/4.2.6.A-3.yaml").read_text())["rules"][0]
    for key, value in yaml_rule.items():
        assert rule[key] == value
    bare = {k: v for k, v in rule.items() if k != "growth_hormone_continuation_protocol"}
    assert _semantic_route_signature(rule) != _semantic_route_signature(bare)


def test_parser_and_public_adapter_preserve_explicit_false_zero_and_missing():
    values = {**VALID, "annual_growth_velocity_cm": 0}
    item = MaterialItem(name="somatropin", **values)
    assert {k: item.model_dump()[k] for k in values} == values
    context = build_context_from_material_dict({"claim_id": "G", "materials": [item.model_dump()],
        "drug_context": {"primary_icd10": "Q96.9"}})
    assert {k: getattr(context.drug_lines[0], k) for k in values} == values
    errors = []
    parsed = parse_drug_line(asdict(line(**values)), errors)
    assert errors == []
    assert {k: getattr(parsed, k) for k in values} == values
    missing = dict.fromkeys(GROWTH_HORMONE_FIELDS)
    errors = []
    parsed = parse_drug_line(asdict(line(**missing)), errors)
    assert errors == []
    assert all(getattr(parsed, k) is None for k in GROWTH_HORMONE_FIELDS)


def test_parser_reports_invalid_evidence_without_coercing_it():
    errors = []
    parsed = parse_drug_line(asdict(line(epiphyses_closed="false", height_cm="155")), errors)
    assert parsed.epiphyses_closed is None
    assert parsed.height_cm is None
    assert len(errors) == 2
    assert "epiphyses_closed" in errors[0]
    assert "height_cm" in errors[1]
