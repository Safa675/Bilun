"""Explicit PWS scope, phase-specific reports and partial stopping evidence."""
from __future__ import annotations

from dataclasses import asdict, replace
from datetime import date
import hashlib
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from src.bilun.domain.claims.adapter import build_context_from_material_dict
from src.bilun.domain.claims.growth_hormone import PWS_FIELDS
from src.bilun.domain.claims.parsing.row_parsers import parse_drug_line
from src.bilun.domain.prose_rules.drug_indication import (
    evaluate_drug_indication_line_detailed, list_drug_indication_rules,
)
from src.bilun.shared.models import MaterialItem
from tests.unit.domain.prose_rules.test_growth_hormone_continuation import line, _claim

pytestmark = pytest.mark.unit
ROOT = Path(__file__).resolve().parents[4]
STOP_FIELDS = (*PWS_FIELDS[1:], "epiphyses_closed")
BASE = {"gh_patient_group": "pediatric", "pws_genetic_diagnosis_confirmed": True,
        "drug_report_duration_months": 6, **dict.fromkeys(STOP_FIELDS, False)}


def evaluate(*, reverse=False, **overrides):
    rules = list_drug_indication_rules()
    return evaluate_drug_indication_line_detailed(
        drug_line=replace(line(), **{**BASE, **overrides}),
        claim=_claim(primary_icd10="Q87.1"), diagnoses=[],
        rules=list(reversed(rules)) if reverse else rules,
    )


@pytest.mark.parametrize("reverse", [False, True])
def test_negative_stop_screen_is_partial_review_not_full_eligibility(reverse):
    result = evaluate(reverse=reverse)
    assert result["selected_rule_id"] in {
        "4.2.6.A4.prader_willi_gh_no_stimulation_test", "4.2.6.pws_somatropin_tertiary_board"}
    assert result["violation"]["severity"] == "review"
    assert result["evaluation_status"] == "missing_inputs"
    assert result["missing_inputs"] == ["pws_remaining_clinical_criteria"]


@pytest.mark.parametrize("field", STOP_FIELDS)
def test_any_known_stop_dominates_other_unknown_clinical_flags(field):
    values = dict.fromkeys(STOP_FIELDS)
    values[field] = True
    result = evaluate(**values)
    hit = result["violation"]
    assert hit["violation_kind"] == "growth_hormone_continuation_stop"
    assert hit["growth_hormone_stop_criteria"] == [field]
    assert hit["severity"] == "error"
    assert result["evaluation_status"] == "evaluated"
    assert result["missing_inputs"] == []
    assert not any(k in hit for k in ["savings_try", "payable_try", "recoverable_uplift_try"])


@pytest.mark.parametrize("field", STOP_FIELDS)
def test_unknown_negative_screen_requires_each_unknown_flag(field):
    result = evaluate(**{field: None})
    assert result["violation"]["severity"] == "review"
    assert set(result["missing_inputs"]) == {field, "pws_remaining_clinical_criteria"}


@pytest.mark.parametrize("phase,duration,expected", [
    ("initiation", 3, "needs_growth_hormone_verification"),
    ("initiation", 6, "report_duration_mismatch"),
    ("continuation", 3, "report_duration_mismatch"),
    ("continuation", 6, "needs_growth_hormone_verification"),
    ("continuation", None, "needs_report_verification"),
])
def test_exact_phase_specific_reports(phase, duration, expected):
    result = evaluate(gh_treatment_phase=phase, drug_report_duration_months=duration)
    assert result["violation"]["violation_kind"] == expected
    if expected == "report_duration_mismatch":
        assert result["violation"]["expected_report_duration_months"] == (3 if phase == "initiation" else 6)
        assert "4.2.6.A-4" in result["violation"]["message_tr"]
    elif duration is not None:
        assert result["missing_inputs"] == (["pws_initiation_clinical_assessment"] if phase == "initiation"
                                            else ["pws_remaining_clinical_criteria"])


@pytest.mark.parametrize("field,value", [("pws_genetic_diagnosis_confirmed", None),
                                        ("pws_genetic_diagnosis_confirmed", False),
                                        ("gh_patient_group", None), ("gh_patient_group", "adult"),
                                        ("gh_treatment_phase", None)])
def test_q87_specialty_or_other_stop_cannot_supply_missing_scope(field, value):
    result = evaluate(**{field: value}, epiphyses_closed=True,
                      drug_specialty_board_report_present=False)
    assert result["evaluation_status"] == "missing_inputs"
    assert result["violation"]["severity"] == "review"
    assert field in result["missing_inputs"]


@pytest.mark.parametrize("when", [None, date(2024, 5, 16)])
def test_unknown_and_historical_date_precede_current_report_or_clinical_conclusions(when):
    result = evaluate(drug_claim_date=when, epiphyses_closed=True,
                      drug_specialty_board_report_present=False)
    assert result["violation"]["violation_kind"] == "needs_growth_hormone_verification"
    assert result["missing_inputs"] == (["drug_claim_date"] if when is None else ["historical_sut_version"])


def test_first_verified_heading_day_applies_stop():
    assert evaluate(drug_claim_date=date(2024, 5, 17), epiphyses_closed=True)["violation"]["violation_kind"] == \
        "growth_hormone_continuation_stop"


@pytest.mark.parametrize("drug", ["SOMATROGON", "büyüme hormonu", "buyume hormonu", "MECASERMIN"])
def test_non_somatropin_or_unknown_identity_never_gets_pws_stop(drug):
    result = evaluate(drug_name=drug, epiphyses_closed=True)
    assert (result["violation"] or {}).get("violation_kind") != "growth_hormone_continuation_stop"


@pytest.mark.parametrize("field", PWS_FIELDS)
def test_clinical_flags_are_strict_and_cannot_coerce_false_strings(field):
    with pytest.raises(ValidationError):
        MaterialItem(name="somatropin", **{field: "false"})
    result = evaluate(**{field: "false"})
    assert result["evaluation_status"] == "missing_inputs"
    assert field in result["missing_inputs"]


def test_all_flags_preserve_explicit_false_true_and_unknown_at_ingestion():
    values = dict.fromkeys(PWS_FIELDS, False)
    values["pws_genetic_diagnosis_confirmed"] = True
    item = MaterialItem(name="somatropin", **values)
    context = build_context_from_material_dict({"claim_id": "PWS", "materials": [item.model_dump()],
        "drug_context": {"primary_icd10": "Q87.1"}})
    assert {k: getattr(context.drug_lines[0], k) for k in values} == values
    errors = []
    parsed = parse_drug_line(asdict(replace(line(), **values)), errors)
    assert errors == []
    assert {k: getattr(parsed, k) for k in values} == values
    assert all(MaterialItem(name="somatropin").model_dump()[k] is None for k in PWS_FIELDS)


def test_pinned_source_heading_whitespace_strike_and_clinical_wording():
    evidence = json.loads((ROOT / "data/gazette/source_evidence/pws_somatropin_continuation.json").read_text())
    assert evidence["verified_current_heading_from"] == "2024-05-17"
    for version in evidence["sources"]:
        rows = version["paragraphs"]
        for row in rows:
            assert hashlib.sha256(row["text"].encode()).hexdigest() == row["text_sha256"]
        assert "17/05/2024" in rows[0]["text"]
        # Any strike in the current heading is whitespace, not removed scope.
        assert all(not r["struck"] for r in rows[2]["runs"] if r["text"].strip())
        assert "tedavi edilemeyen" in rows[-2]["text"]
        assert "Epifiz" in rows[-1]["text"]
    assert [r["text"] for r in evidence["sources"][0]["paragraphs"]] == \
           [r["text"] for r in evidence["sources"][1]["paragraphs"]]
