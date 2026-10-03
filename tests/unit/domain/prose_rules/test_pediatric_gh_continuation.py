"""Pediatric source discrimination, current stop criteria, and repealed limits."""
from __future__ import annotations

from dataclasses import replace
from datetime import date
import hashlib
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from src.bilun.domain.claims.growth_hormone import parse_growth_hormone_inputs
from src.bilun.domain.prose_rules.drug_indication import (
    evaluate_drug_indication_line_detailed, list_drug_indication_rules,
)
from src.bilun.shared.models import MaterialItem
from tests.unit.domain.prose_rules.test_growth_hormone_continuation import line, _claim

pytestmark = pytest.mark.unit
ROOT = Path(__file__).resolve().parents[4]
PEDS = {"4.2.6.pediatric_gh_monitoring_board", "4.2.6.pediatric_gh_renewal_board"}


def evaluate(*, reverse=False, **overrides):
    rules = list_drug_indication_rules()
    drug = replace(line(), **{"gh_patient_group": "pediatric", "gh_height_reference_sex": "female",
                             "height_cm": 156.99, **overrides})
    return evaluate_drug_indication_line_detailed(
        drug_line=drug, claim=_claim(primary_icd10="E23.0"), diagnoses=[],
        rules=list(reversed(rules)) if reverse else rules,
    )


@pytest.mark.parametrize("reverse", [False, True])
@pytest.mark.parametrize("drug", ["SOMATROPIN", "NGENLA (SOMATROGON)"])
def test_explicit_pediatric_continuation_routes_are_order_independent(reverse, drug):
    result = evaluate(reverse=reverse, drug_name=drug)
    assert result["selected_rule_id"] in PEDS
    assert result["violation"] is None


@pytest.mark.parametrize("field,value", [("epiphyses_closed", True), ("annual_growth_velocity_cm", 4),
                                        ("height_cm", 157)])
def test_pediatric_any_stop_dominates_unrelated_missing_facts(field, value):
    values = dict(epiphyses_closed=None, annual_growth_velocity_cm=None, height_cm=None,
                  gh_height_reference_sex="female")
    values[field] = value
    hit = evaluate(**values)["violation"]
    assert hit["violation_kind"] == "growth_hormone_continuation_stop"
    assert hit["growth_hormone_stop_criteria"] == [field]
    assert hit["severity"] == "error"
    assert hit["evaluation_status"] == "evaluated"
    assert hit["missing_inputs"] == []


@pytest.mark.parametrize("sex,height,stop", [("female", 156.99, False), ("female", 157, True),
                                           ("female", 157.01, True), ("male", 167.99, False),
                                           ("male", 168, True), ("male", 168.01, True)])
def test_exact_sex_specific_height_boundaries(sex, height, stop):
    result = evaluate(gh_height_reference_sex=sex, height_cm=height)
    assert bool(result["violation"]) is stop
    if stop:
        assert result["violation"]["growth_hormone_stop_criteria"] == ["height_cm"]


@pytest.mark.parametrize("bone_age", [None, 14, 16, 20])
def test_repealed_pediatric_bone_age_stop_never_applies(bone_age):
    assert evaluate(bone_age_years=bone_age)["violation"] is None


@pytest.mark.parametrize("field", ["epiphyses_closed", "annual_growth_velocity_cm", "height_cm",
                                   "gh_height_reference_sex"])
def test_unknown_applicable_measurement_stays_review(field):
    result = evaluate(**{field: None})
    assert result["evaluation_status"] == "missing_inputs"
    assert result["missing_inputs"] == [field]
    assert result["violation"]["severity"] == "review"


@pytest.mark.parametrize("specialty", ["çocuk endokrinoloji", "endokrinoloji", "iç hastalıkları"])
def test_specialist_and_e23_cannot_infer_pediatric_group(specialty):
    result = evaluate(gh_patient_group=None, prescriber_specialty=specialty)
    assert result["applicability_status"] == "ambiguous_route"
    assert result["selected_rule_id"] is None
    assert result["missing_inputs"] == ["gh_patient_group"]


def test_missing_phase_cannot_choose_pediatric_initiation_or_continuation():
    result = evaluate(gh_treatment_phase=None)
    assert result["applicability_status"] == "ambiguous_route"
    assert result["missing_inputs"] == ["gh_treatment_phase"]


def test_explicit_initiation_does_not_apply_continuation_stop():
    result = evaluate(gh_treatment_phase="initiation", epiphyses_closed=True)
    assert result["selected_rule_id"] is None
    assert result["missing_inputs"] == ["gh_initiation_pathway"]
    assert result["violation"]["severity"] == "review"


def test_adult_closed_epiphyses_do_not_receive_pediatric_stop():
    result = evaluate(gh_patient_group="adult", epiphyses_closed=True,
                      prescriber_specialty="endokrinoloji", height_cm=180)
    assert result["selected_rule_id"] == "4.2.6.adult_somatropin_board_report"
    assert result["violation"] is None


@pytest.mark.parametrize("when", [None, date(2024, 5, 16)])
def test_prior_or_unknown_service_date_never_gets_current_pediatric_stop(when):
    result = evaluate(drug_claim_date=when, epiphyses_closed=True)
    assert result["violation"]["violation_kind"] == "needs_growth_hormone_verification"
    assert result["evaluation_status"] == "missing_inputs"


def test_first_day_current_heading_enforces_current_not_superseded_height():
    assert evaluate(drug_claim_date=date(2024, 5, 17), height_cm=155)["violation"] is None
    assert evaluate(drug_claim_date=date(2024, 5, 17), height_cm=157)["violation"]["violation_kind"] == \
        "growth_hormone_continuation_stop"


@pytest.mark.parametrize("field,value", [("gh_patient_group", "child"), ("gh_patient_group", True),
                                        ("gh_height_reference_sex", "unknown"),
                                        ("gh_height_reference_sex", 0)])
def test_categories_are_explicit_typed_choices_without_inference(field, value):
    with pytest.raises(ValidationError):
        MaterialItem(name="somatropin", **{field: value})
    assert parse_growth_hormone_inputs({field: value})[field] is None
    assert evaluate(**{field: value})["evaluation_status"] == "missing_inputs"


def test_source_hashes_repeal_and_generated_manifest_are_pinned():
    evidence = json.loads((ROOT / "data/gazette/source_evidence/pediatric_gh_continuation.json").read_text())
    assert evidence["verified_current_heading_from"] == "2024-05-17"
    for version in evidence["sources"]:
        for p in version["paragraphs"]:
            assert hashlib.sha256(p["text"].encode()).hexdigest() == p["text_sha256"]
        assert version["paragraphs"][1]["has_struck_runs"] is True
        assert version["paragraphs"][2]["has_struck_runs"] is False
        assert "Mülga" in version["paragraphs"][-2]["text"]
        assert version["paragraphs"][-1]["has_struck_runs"] is True
    assert [p["text"] for p in evidence["sources"][0]["paragraphs"]] == \
           [p["text"] for p in evidence["sources"][1]["paragraphs"]]
    manifest = json.loads((ROOT / "data/gazette/prose_manifests/L4.2_drug_indication_4206_manifest.json").read_text())
    encoded = set(manifest["encoded_clause_ids"])
    # Three pediatric stops + their OR introduction, four Turner stops + theirs.
    assert {"C004037", "C004038", "C004039", "C004040", "C004058", "C004059",
            "C004060", "C004061", "C004062"} <= encoded


def test_recorded_categories_survive_public_model_adapter_and_parquet_parser():
    from dataclasses import asdict
    from src.bilun.domain.claims.adapter import build_context_from_material_dict
    from src.bilun.domain.claims.parsing.row_parsers import parse_drug_line

    values = {"gh_patient_group": "pediatric", "gh_height_reference_sex": "male"}
    item = MaterialItem(name="somatropin", **values)
    context = build_context_from_material_dict({"claim_id": "P", "materials": [item.model_dump()],
        "drug_context": {"primary_icd10": "E23.0"}})
    assert {k: getattr(context.drug_lines[0], k) for k in values} == values
    errors = []
    parsed = parse_drug_line(asdict(replace(line(), **values)), errors)
    assert errors == []
    assert {k: getattr(parsed, k) for k in values} == values


@pytest.mark.parametrize("drug", ["büyüme hormonu", "buyume hormonu", "MECASERMIN"])
def test_generic_or_other_growth_drug_never_uses_pediatric_stop(drug):
    result = evaluate(drug_name=drug, epiphyses_closed=True)
    assert result["selected_rule_id"] not in PEDS
    assert (result["violation"] or {}).get("violation_kind") != "growth_hormone_continuation_stop"
