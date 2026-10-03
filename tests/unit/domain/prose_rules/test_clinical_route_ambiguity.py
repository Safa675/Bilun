"""Necessary clinical observations cannot establish a missing indication route."""

from dataclasses import replace
from datetime import date

import pytest

from src.bilun.domain.prose_rules.drug_indication import (
    _evaluate_drug_indication_line_with_rules,
    evaluate_drug_indication_line_detailed,
    list_drug_indication_rules,
)
from tests.unit.domain.prose_rules.test_clinical_remaining_indications import noninvasive
from tests.unit.domain.prose_rules.test_drug_indication_4213_4216 import _claim, _drug_line


def _evaluate(line, *, reverse=False):
    rules = list_drug_indication_rules()
    if reverse:
        rules = list(reversed(rules))
    args = {"drug_line": line, "claim": _claim(primary_icd10="B18.1"),
            "diagnoses": [], "rules": rules}
    base = _evaluate_drug_indication_line_with_rules(**args)
    assert base["violation"]["violation_kind"] == "ambiguous_route"
    return base, evaluate_drug_indication_line_detailed(**args)


def _assert_preserved(base, actual):
    before, after = base["violation"], actual["violation"]
    assert actual["selected_rule_id"] is None
    for key in ("violation_kind", "rule_id", "selected_rule_id", "message_tr",
                "eligible_route_rule_ids", "applicability_status"):
        assert after[key] == before[key]
    assert after["severity"] == "review"
    assert after["clinical_restrictions"] == actual["clinical_restrictions"]
    assert after["clinical_eligibility_complete"] is False
    assert set(before["missing_inputs"]) <= set(after["missing_inputs"])
    assert "remaining_sut_clinical_criteria" in after["missing_inputs"]


@pytest.mark.parametrize("report", [None, False, True])
@pytest.mark.parametrize("day", [None, date(2026, 1, 2), date(2026, 10, 2)])
@pytest.mark.parametrize("reverse", [False, True])
def test_missing_indication_evidence_preserves_ambiguous_route(report, day, reverse):
    line = replace(_drug_line(drug_name="BARACLUDE 0.5 MG (ENTEKAVIR)",
                              report_present=report), drug_claim_date=day)
    base, actual = _evaluate(line, reverse=reverse)
    _assert_preserved(base, actual)
    assert actual["clinical_restrictions"][0]["criterion_status"] in {
        "unknown", "not_evaluated"
    }


@pytest.mark.parametrize("reverse", [False, True])
def test_clear_necessary_hbv_checks_preserve_ambiguous_route(reverse):
    line = replace(noninvasive(), drug_name="entekavir", drug_report_duration_months=None,
                   prescriber_specialty=None)
    base, actual = _evaluate(line, reverse=reverse)
    _assert_preserved(base, actual)
    assert actual["clinical_restrictions"][0]["criterion_status"] == "criterion_clear"


@pytest.mark.parametrize("reverse", [False, True])
def test_concrete_failed_clinical_check_retains_priority(reverse):
    line = replace(noninvasive(hbv_dna_iu_ml=1999), drug_name="entekavir",
                   drug_report_duration_months=None, prescriber_specialty=None)
    _, actual = _evaluate(line, reverse=reverse)
    assert actual["violation"]["violation_kind"] == "clinical_restriction_not_met"
    assert actual["violation"]["severity"] == "error"
    assert actual["selected_rule_id"] == "other_indication_source_constraints"
    assert actual["clinical_restrictions"][0]["criterion_status"] == "restriction_not_met"
    assert actual["clinical_eligibility_complete"] is False
