"""Regressions for the source-explicit imatinib outcome requirement."""

from typing import Any

import pytest

from src.bilun.domain.prose_rules.drug_indication import (
    _evaluate_prior_therapy_constraints,
    evaluate_drug_indication_line_detailed,
    list_drug_indication_rules,
)
from tests.unit.domain.prose_rules.test_drug_indication import _claim, _drug_line


_RULE_IDS = (
    "4.2.14.C.tier_c_b.C005024.dasatinib",
    "4.2.14.C.tier_c_b.C005043.bosutinib",
)
_LEGACY_RULES = [
    rule for rule in list_drug_indication_rules()
    if rule.get("requires_prior_therapy") and rule["rule_id"] not in _RULE_IDS
]


@pytest.fixture(params=_RULE_IDS)
def rule(request: pytest.FixtureRequest) -> dict[str, Any]:
    return next(row for row in list_drug_indication_rules() if row["rule_id"] == request.param)


def _evaluate(rule: dict[str, Any], prior: tuple[dict[str, str], ...] | None):
    return _evaluate_prior_therapy_constraints(
        rule=rule,
        drug_line=_drug_line(prior_therapies=prior),
        claim=_claim(primary_icd10="C92.1"),
        icd_codes=["C92.1"],
    )


@pytest.mark.parametrize("outcome", ["resistant", "intolerant", "resistant_or_intolerant"])
def test_source_supported_alternatives_pass_the_prior_therapy_check(rule, outcome):
    assert _evaluate(rule, ({"drug_or_class": "imatinib", "outcome": outcome},)) is None


def test_identity_and_outcome_accept_outer_whitespace_and_case(rule):
    assert _evaluate(rule, ({"drug_or_class": "  IMATINIB  ", "outcome": " InToLeRaNt "},)) is None


@pytest.mark.parametrize("outcome", [None, "", " ", "unknown", "unrecognized", "failed", "completed"])
def test_missing_or_unresolved_matching_outcome_requires_review(rule, outcome):
    prior = {"drug_or_class": "imatinib"}
    if outcome is not None:
        prior["outcome"] = outcome
    hit = _evaluate(rule, (prior,))
    assert hit["violation_kind"] == "needs_prior_therapy_verification"
    assert hit["severity"] == "review"
    # The public missing-input vocabulary supports the whole history field.
    assert hit["missing_inputs"] == ["prior_therapies"]
    assert hit["required_prior_therapy"] == "imatinib"
    assert hit["required_outcome"] == "resistant_or_intolerant"
    assert hit["clinical_eligibility_complete"] is False


def test_known_response_does_not_satisfy_resistance_or_intolerance(rule):
    hit = _evaluate(rule, ({"drug_or_class": "imatinib", "outcome": "responsive"},))
    assert hit["violation_kind"] == "prior_therapy_mismatch"
    assert hit["severity"] == "error"
    evidence = hit["clinical_restrictions"][0]
    assert evidence["criterion_status"] == "restriction_not_met"
    assert evidence["checks"] == [
        {"field": "prior_therapies.drug_or_class", "status": "pass"},
        {"field": "prior_therapies.outcome", "status": "fail"},
    ]
    assert evidence["source_refs"] == rule["gate_b_sources"]
    assert evidence["clinical_eligibility_complete"] is False


@pytest.mark.parametrize("drug", ["imat", "nonimatinib", "imatinib_other", "nilotinib"])
def test_partial_or_unrelated_identity_cannot_supply_the_required_outcome(rule, drug):
    hit = _evaluate(rule, ({"drug_or_class": drug, "outcome": "resistant"},))
    assert hit["violation_kind"] == "prior_therapy_mismatch"
    assert hit["severity"] == "error"
    assert hit["clinical_restrictions"][0]["checks"] == [
        {"field": "prior_therapies.drug_or_class", "status": "fail"},
        {"field": "prior_therapies.outcome", "status": "unknown"},
    ]


@pytest.mark.parametrize("prior,missing", [
    (None, ["prior_therapies"]),
    ((), ["prior_therapies"]),
    (({"outcome": "resistant"},), ["prior_therapies.drug_or_class"]),
    (({"drug_or_class": " ", "outcome": "intolerant"},), ["prior_therapies.drug_or_class"]),
])
def test_absent_history_or_identity_remains_unknown(rule, prior, missing):
    hit = _evaluate(rule, prior)
    assert hit["violation_kind"] == "needs_prior_therapy_verification"
    assert hit["severity"] == "review"
    assert hit["missing_inputs"] == missing


@pytest.mark.parametrize("reverse", [False, True])
def test_a_supported_matching_entry_passes_regardless_of_other_entries(rule, reverse):
    prior = (
        {"drug_or_class": "imatinib"},
        {"drug_or_class": "imatinib", "outcome": "responsive"},
        {"drug_or_class": "nilotinib", "outcome": "resistant"},
        {"outcome": "intolerant"},
        {"drug_or_class": "imatinib", "outcome": "intolerant"},
    )
    assert _evaluate(rule, tuple(reversed(prior)) if reverse else prior) is None


@pytest.mark.parametrize("matching_outcome", [None, "responsive"])
@pytest.mark.parametrize("reverse", [False, True])
def test_outcomes_are_not_borrowed_from_an_unrelated_drug(rule, matching_outcome, reverse):
    matching = {"drug_or_class": "imatinib"}
    if matching_outcome is not None:
        matching["outcome"] = matching_outcome
    prior = (matching, {"drug_or_class": "nilotinib", "outcome": "resistant"})
    hit = _evaluate(rule, tuple(reversed(prior)) if reverse else prior)
    assert hit["violation_kind"] == (
        "needs_prior_therapy_verification" if matching_outcome is None else "prior_therapy_mismatch"
    )


@pytest.mark.parametrize("reverse", [False, True])
def test_an_unresolved_matching_entry_preserves_review_with_a_known_mismatch(rule, reverse):
    prior = (
        {"drug_or_class": "imatinib", "outcome": "responsive"},
        {"drug_or_class": "imatinib", "outcome": "unknown"},
    )
    hit = _evaluate(rule, tuple(reversed(prior)) if reverse else prior)
    assert hit["violation_kind"] == "needs_prior_therapy_verification"
    assert hit["severity"] == "review"


@pytest.mark.parametrize("prior,kind", [
    (({"drug_or_class": "imatinib"},), "needs_prior_therapy_verification"),
    (({"drug_or_class": "imatinib", "outcome": "responsive"},), "prior_therapy_mismatch"),
])
def test_public_result_preserves_source_identity_and_incomplete_eligibility(rule, prior, kind):
    drug = rule["drug_names"][0]
    result = evaluate_drug_indication_line_detailed(
        drug_line=_drug_line(
            drug_name=drug, report_present=True,
            prescriber_specialty="tıbbi onkoloji", prior_therapies=prior,
            biomarkers=({"marker": "BCR_ABL", "status": "positive"},),
        ),
        claim=_claim(primary_icd10="C92.1"), diagnoses=(), rules=[rule],
    )
    hit = result["violation"]
    assert hit["violation_kind"] == kind
    assert hit["selected_rule_id"] == hit["rule_id"] == rule["rule_id"]
    assert result["selected_rule_id"] == rule["rule_id"]
    assert result["clinical_restrictions"][0]["source_refs"] == rule["gate_b_sources"]
    assert result["clinical_eligibility_complete"] is False


@pytest.mark.parametrize("legacy", _LEGACY_RULES, ids=lambda row: row["rule_id"])
def test_unaudited_legacy_requirements_keep_missing_history_review(legacy):
    hit = _evaluate(legacy, None)
    assert hit["violation_kind"] == "needs_prior_therapy_verification"
    assert hit["severity"] == "review"
    assert hit["missing_inputs"] == ["prior_therapies"]
    assert "clinical_restrictions" not in hit


@pytest.mark.parametrize("legacy", _LEGACY_RULES, ids=lambda row: row["rule_id"])
@pytest.mark.parametrize("outcome", [None, "responsive"])
def test_unaudited_legacy_outcomes_are_not_given_new_clinical_semantics(legacy, outcome):
    prior = {"drug_or_class": legacy["requires_prior_therapy"]["drug_or_class"]}
    if outcome is not None:
        prior["outcome"] = outcome
    assert _evaluate(legacy, (prior,)) is None


def test_existing_source_scope_guard_still_precedes_prior_therapy_checks(rule):
    guarded = {**rule, "source_clinical_scope_incomplete": True}
    result = evaluate_drug_indication_line_detailed(
        drug_line=_drug_line(
            drug_name=rule["drug_names"][0], report_present=True,
            prescriber_specialty="tıbbi onkoloji",
            prior_therapies=({"drug_or_class": "imatinib", "outcome": "responsive"},),
        ),
        claim=_claim(primary_icd10="C92.1"), diagnoses=(), rules=[guarded],
    )
    assert result["violation"]["violation_kind"] == "needs_clinical_verification"
    assert result["missing_inputs"] == ["remaining_sut_clinical_criteria"]
    assert result["clinical_eligibility_complete"] is False
