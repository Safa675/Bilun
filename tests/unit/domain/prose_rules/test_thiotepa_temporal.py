"""Verified thiotepa relocation must not keep an erroneous carmustine rule alive."""
from dataclasses import replace
from datetime import date

import pytest

from src.bilun.domain.prose_rules.drug_indication import (
    evaluate_drug_indication_line_detailed, list_drug_indication_rules,
)
from tests.unit.domain.prose_rules.test_drug_indication import _claim, _drug_line

WRONG = "4.2.61.onco.carmustine_offlabel_bmt_conditioning_coverage"
C71 = "4.2.14.C.carmustine_brain_tumor_board"


def evaluate(name, day, code="C83.9", report=True, rules=None):
    line = replace(_drug_line(drug_name=name, report_present=report,
                              report_duration_months=6, prescriber_specialty="erişkin hematoloji"),
                   drug_claim_date=date.fromisoformat(day) if day else None)
    return evaluate_drug_indication_line_detailed(drug_line=line, claim=_claim(primary_icd10=code),
                                                 diagnoses=[], rules=rules)


@pytest.mark.parametrize("name", ["thiotepa", "tiyotepa", "tiotepa"])
@pytest.mark.parametrize("day", ["2026-09-05", "2026-09-06", "2026-10-10"])
def test_successor_partial_review_for_every_alias_after_boundary(name, day):
    result = evaluate(name, day)
    assert result["selected_rule_id"] == "sut.temporal.thiotepa.2026-09-05"
    assert result["temporal_evidence"]["publication_date"] == "2026-08-29"
    assert result["temporal_evidence"]["valid_from"] == "2026-09-05"
    assert result["evaluation_status"] == "missing_inputs"
    assert "transplant_preparation_indication" in result["missing_inputs"]
    assert result["violation"]["severity"] == "review"
    assert result["temporal_evidence"]["clinical_eligibility_complete"] is False


@pytest.mark.parametrize("name", ["thiotepa", "tiyotepa", "tiotepa"])
def test_historical_aliases_do_not_inherit_generic_tiotepa_clearance(name):
    result = evaluate(name, "2026-09-04")
    assert result["selected_rule_id"] is None
    assert result["temporal_evidence"]["status"] == "historical_source_unverified"
    assert result["violation"]["severity"] == "review"


@pytest.mark.parametrize("name", ["thiotepa", "tiyotepa", "tiotepa"])
def test_missing_date_requires_review_for_all_aliases(name):
    result = evaluate(name, None)
    assert result["selected_rule_id"] is None
    assert "drug_claim_date" in result["missing_inputs"]
    assert result["violation"]["severity"] == "review"


@pytest.mark.parametrize("day", ["2026-09-04", "2026-09-05", "2026-09-06", None])
@pytest.mark.parametrize("name", ["karmustin", "carmustine"])
@pytest.mark.parametrize("code", ["C81.9", "C82.9", "C83.9", "C84.9", "C85.9"])
def test_mistargeted_lymphoma_rule_never_becomes_carmustine_payment_or_mismatch(day, name, code):
    result = evaluate(name, day, code)
    assert result["selected_rule_id"] is None
    assert result["temporal_evidence"]["status"] == "source_target_mismatch"
    assert result["temporal_evidence"]["excluded_rule_ids"] == [WRONG]
    assert result["temporal_evidence"]["repeal_effective_date"] == "2026-09-05"
    assert result["violation"]["severity"] == "review"
    assert result["violation"]["violation_kind"] != "indication_mismatch"
    assert result["eligible_route_rule_ids"] == []


@pytest.mark.parametrize("day", ["2026-09-04", "2026-09-05", "2026-09-06", None])
@pytest.mark.parametrize("report", [True, False])
@pytest.mark.parametrize("name", ["karmustin", "carmustine"])
def test_unrelated_legitimate_c71_route_is_identical_without_wrong_rule(day, report, name):
    rules = list_drug_indication_rules()
    expected = evaluate(name, day, "C71.9", report,
                        [r for r in rules if r["rule_id"] != WRONG and not r.get("temporal_source_only")])
    actual = evaluate(name, day, "C71.9", report)
    assert actual == expected
    assert actual["selected_rule_id"] == C71


def test_exact_id_correction_does_not_remove_other_rule_on_same_section():
    rules = list_drug_indication_rules()
    other = {"rule_id": "synthetic.legitimate", "sut_section": "4.2.61", "drug_names": ["karmustin"],
             "icd10_codes": ["C83"], "report_required": False}
    result = evaluate("karmustin", "2026-09-05", rules=[*rules, other])
    assert result["selected_rule_id"] == "synthetic.legitimate"
    assert result["violation"] is None


@pytest.mark.parametrize("day", ["2026-10-04", "2026-10-09", "2026-10-10", None])
@pytest.mark.parametrize("name", ["karmustin", "carmustine", "BICNU (CARMUSTINE)"])
def test_removed_executable_rule_keeps_scoped_source_review_at_public_boundary(day, name):
    from src.bilun.api.public_responses import project_public_response
    from src.bilun.api.schemas import DrugTemporalEvidenceResponse

    rules = list_drug_indication_rules()
    assert not any(row["rule_id"] == WRONG for row in rules)
    correction = next(row for row in rules if row.get("temporal_source_correction"))
    assert correction["icd10_codes"] == ["C81", "C82", "C83", "C84", "C85"]
    result = evaluate(name, day, "C83.3", rules=rules)
    assert result["selected_rule_id"] is None
    assert result["eligible_route_rule_ids"] == []
    assert result["matched_icd10_codes"] == []
    assert result["violation"]["severity"] == "review"
    assert result["violation"]["violation_kind"] == "needs_temporal_clinical_verification"
    evidence = result["temporal_evidence"]
    assert evidence["status"] == "source_target_mismatch"
    assert evidence["clinical_eligibility_complete"] is False
    assert "supported_checks" not in evidence
    assert DrugTemporalEvidenceResponse.model_validate(evidence).excluded_rule_ids == [WRONG]
    public = project_public_response({"drug_indication": {"violations": [result["violation"]]}},
                                     "get_billing_report")
    shown = public["drug_indication"]["violations"][0]["temporal_evidence"]
    assert shown["status"] == "source_target_mismatch"
    assert shown["excluded_rule_ids"] == [WRONG]
    assert shown["clinical_eligibility_complete"] is False


@pytest.mark.parametrize("name,code", [
    ("unrelated_medicine", "C83.3"), ("carmustinemab", "C83.3"),
    ("karmustinol", "C83.3"), ("carmustine", "A00.9"),
    ("karmustin", "C80.9"), ("karmustin", "C86.9"),
])
def test_removed_rule_correction_preserves_unrelated_medicine_and_diagnosis(name, code):
    rules = list_drug_indication_rules()
    expected = evaluate(name, "2026-10-04", code,
                        rules=[row for row in rules if not row.get("temporal_source_correction")])
    actual = evaluate(name, "2026-10-04", code, rules=rules)
    assert actual == expected
    assert actual.get("temporal_evidence", {}).get("status") != "source_target_mismatch"


def test_explicit_rules_without_correction_remain_self_contained():
    route = {"rule_id": WRONG, "sut_section": "4.2.61", "drug_names": ["karmustin"],
             "icd10_codes": ["C83"], "report_required": False}
    result = evaluate("karmustin", "2026-10-04", "C83.3", rules=[route])
    assert result["selected_rule_id"] == WRONG
    assert result["violation"] is None
    assert "temporal_evidence" not in result


@pytest.mark.parametrize("months,status", [(None, "unknown"), (0, "fail"), (5, "fail"), (6, "pass"), (7, "fail")])
def test_six_month_report_is_exact_and_still_not_clinical_clearance(months, status):
    line = replace(_drug_line(drug_name="thiotepa", report_present=True,
                              report_duration_months=months, prescriber_specialty="erişkin hematoloji"),
                   drug_claim_date=date(2026, 9, 5))
    result = evaluate_drug_indication_line_detailed(drug_line=line, claim=_claim(), diagnoses=[])
    check = next(row for row in result["temporal_evidence"]["supported_checks"] if row["field"] == "drug_report_duration_months")
    assert check["status"] == status
    assert result["violation"]["severity"] == "review"
    assert result["evaluation_status"] == "missing_inputs"


def test_corrected_source_identity_survives_public_projection():
    from src.bilun.api.public_responses import project_public_response
    from src.bilun.api.schemas import DrugTemporalEvidenceResponse
    result = evaluate("karmustin", "2026-09-05")
    evidence = result["temporal_evidence"]
    model = DrugTemporalEvidenceResponse.model_validate(evidence)
    assert model.excluded_rule_ids == [WRONG]
    assert model.repeal_effective_date == date(2026, 9, 5)
    public = project_public_response({"drug_indication": {"violations": [result["violation"]]}}, "get_billing_report")
    shown = public["drug_indication"]["violations"][0]["temporal_evidence"]
    assert shown["excluded_rule_ids"] == [WRONG]
    assert shown["repeal_effective_date"] == "2026-09-05"
