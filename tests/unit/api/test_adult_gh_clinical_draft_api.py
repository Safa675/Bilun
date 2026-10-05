"""Local adult GH inspection contract preserves unknown facts and closed gates."""
from __future__ import annotations

from dataclasses import replace
from datetime import date, datetime, timedelta
import json

import pytest
from pydantic import ValidationError

from src.bilun.api import app
from src.bilun.api import adult_gh_clinical_draft as draft
from src.bilun.api.adult_gh_clinical_draft import (
    AdultGhClinicalDraftRequest,
    AdultGhClinicalDraftResponse,
    review_adult_gh_clinical_draft,
)
from src.bilun.domain.claims.adult_gh import (
    AdultGhEvidence,
    AdultGhStimulationTest,
    parse_adult_gh_evidence,
)


SELECTED_RULE = "4.2.6.adult_somatropin_board_report"
SERVICE = date(2026, 10, 5)
PENDING = [
    "adult_gh_source_date_admission",
    "adult_gh_independent_clinical_interpretation",
]


def payload() -> dict:
    return {
        "drug_name": "somatropin",
        "selected_rule_id": SELECTED_RULE,
        "drug_claim_date": SERVICE.isoformat(),
        "gh_patient_group": "adult",
        "epiphyses_closed": True,
        "gh_treatment_phase": "initiation",
        "adult_gh_evidence": {
            "applies_on": SERVICE.isoformat(),
            "assessment_date": "2026-10-04",
            "diagnosis_pathway": "adult_hypothalamic_pituitary",
            "adult_hypothalamic_pituitary_gh_deficiency_suspected": True,
            "stimulation_tests": [
                {
                    "test_id": "ITT-1",
                    "performed_on": "2026-10-02",
                    "kind": "itt",
                    "inadequate_response_documented": True,
                    "peak_gh_mcg_l": 2.9,
                    "peak_gh_documented_in_report": True,
                },
                {
                    "test_id": "OTHER-2",
                    "performed_on": "2026-10-03",
                    "kind": "other",
                    "inadequate_response_documented": True,
                    # Other-test numerical peaks cannot inherit ITT's threshold.
                    "peak_gh_mcg_l": 4.0,
                },
            ],
        },
    }


def review(raw: dict) -> dict:
    request = AdultGhClinicalDraftRequest.model_validate(raw)
    return review_adult_gh_clinical_draft(request).model_dump(mode="json")


@pytest.mark.parametrize("encoding", ["mapping", "evidence_json", "request_json", "typed"])
def test_mapping_json_and_typed_evidence_share_the_same_dated_contract(encoding):
    raw = payload()
    expected = AdultGhClinicalDraftRequest.model_validate(raw)
    if encoding == "evidence_json":
        raw["adult_gh_evidence"] = json.dumps(raw["adult_gh_evidence"])
    elif encoding == "typed":
        raw["drug_claim_date"] = SERVICE
        raw["adult_gh_evidence"] = parse_adult_gh_evidence(raw["adult_gh_evidence"])
    actual = (
        AdultGhClinicalDraftRequest.model_validate_json(json.dumps(raw))
        if encoding == "request_json"
        else AdultGhClinicalDraftRequest.model_validate(raw)
    )
    assert actual == expected
    assert isinstance(actual.adult_gh_evidence, AdultGhEvidence)
    assert isinstance(actual.adult_gh_evidence.stimulation_tests[0], AdultGhStimulationTest)
    assert actual.adult_gh_evidence.applies_on == SERVICE
    assert actual.adult_gh_evidence.stimulation_tests[0].performed_on == date(2026, 10, 2)


def test_candidate_clear_cannot_open_runtime_or_complete_payment_eligibility():
    response = review(payload())
    assert response["schema_version"] == "adult_gh_clinical_draft.v1"
    assert response["selected_rule_id"] == SELECTED_RULE
    assert response["drug_claim_date"] == "2026-10-05"
    assert response["runtime_enabled"] is False
    assert response["clinical_eligibility_complete"] is False
    assert response["pending_requirements"] == PENDING
    assert response["candidate_result"]["criterion_status"] == "criterion_clear"
    assert response["candidate_result"]["clinical_eligibility_complete"] is False
    assert response["runtime_result"]["criterion_status"] == "not_evaluated"
    assert response["runtime_result"]["checks"] == []
    assert {
        "verified_source_for_service_date", "adult_gh_clinical_interpretation_release",
    } <= set(response["runtime_result"]["missing_inputs"])
    assert response["runtime_result"]["clinical_eligibility_complete"] is False


@pytest.mark.parametrize("service", [
    date(2024, 5, 16), date(2025, 9, 15), date(2026, 10, 6),
])
def test_complete_candidate_cannot_admit_historical_gaps_or_future_dates(service):
    raw = payload()
    raw["drug_claim_date"] = service.isoformat()
    raw["adult_gh_evidence"]["applies_on"] = service.isoformat()
    raw["adult_gh_evidence"]["assessment_date"] = (service - timedelta(days=1)).isoformat()
    for offset, test in enumerate(raw["adult_gh_evidence"]["stimulation_tests"]):
        test["performed_on"] = (service - timedelta(days=3 - offset)).isoformat()
    response = review(raw)
    assert response["candidate_result"]["criterion_status"] == "criterion_clear"
    assert response["runtime_result"]["criterion_status"] == "not_evaluated"
    assert response["runtime_result"]["checks"] == []
    assert "verified_source_for_service_date" in response["runtime_result"]["missing_inputs"]
    assert response["pending_requirements"] == PENDING
    assert response["runtime_enabled"] is False
    assert response["clinical_eligibility_complete"] is False


def test_childhood_retest_path_and_exact_itt_rule_identity_are_preserved():
    raw = payload()
    raw["selected_rule_id"] = "4.2.6.A2.insulin_tolerance_test_peak_gh_report"
    evidence = raw["adult_gh_evidence"]
    evidence["diagnosis_pathway"] = "childhood_onset_retest"
    evidence["childhood_gh_deficiency_diagnosed"] = True
    evidence["childhood_gh_treatment_received"] = True
    evidence["gh_stopped_due_to_epiphyseal_closure"] = True
    for test in evidence["stimulation_tests"]:
        test["retest_after_epiphyseal_closure_stop"] = True
    response = review(raw)
    assert response["selected_rule_id"] == "4.2.6.A2.insulin_tolerance_test_peak_gh_report"
    assert response["candidate_result"]["criterion_status"] == "criterion_clear"
    assert response["runtime_result"]["criterion_status"] == "not_evaluated"


@pytest.mark.parametrize("value", ["true", "false", 1, 0, [], {}, "", None])
def test_invalid_epiphyseal_fact_stays_unknown_without_boolean_coercion(value):
    raw = payload()
    raw["epiphyses_closed"] = value
    request = AdultGhClinicalDraftRequest.model_validate(raw)
    assert request.epiphyses_closed is None
    result = review_adult_gh_clinical_draft(request).candidate_result
    assert result["criterion_status"] == "unknown"
    assert "epiphyses_closed" in result["missing_inputs"]


@pytest.mark.parametrize(("field", "value"), [
    ("gh_patient_group", "Adult"), ("gh_patient_group", 18),
    ("gh_patient_group", True), ("gh_treatment_phase", "start"),
    ("gh_treatment_phase", 1), ("gh_treatment_phase", {}),
])
def test_invalid_scope_enum_stays_unknown(field, value):
    raw = payload()
    raw[field] = value
    response = review(raw)
    assert response[field] is None
    assert response["candidate_result"]["criterion_status"] == "unknown"
    assert field in response["candidate_result"]["missing_inputs"]


@pytest.mark.parametrize("value", [
    "2026-10-05T00:00:00", "2026-02-30", "20261005", 1791158400,
    datetime(2026, 10, 5), True, None,
])
def test_invalid_service_date_is_not_coerced_to_an_actual_service_date(value):
    raw = payload()
    raw["drug_claim_date"] = value
    response = review(raw)
    assert response["drug_claim_date"] is None
    assert response["candidate_result"]["criterion_status"] == "not_evaluated"
    assert response["candidate_result"]["checks"] == []
    assert "drug_claim_date" in response["candidate_result"]["missing_inputs"]


@pytest.mark.parametrize("value", ["false", 0, {}, None])
def test_invalid_documented_test_response_stays_unknown(value):
    raw = payload()
    raw["adult_gh_evidence"]["stimulation_tests"][0]["inadequate_response_documented"] = value
    request = AdultGhClinicalDraftRequest.model_validate(raw)
    assert request.adult_gh_evidence.stimulation_tests[0].inadequate_response_documented is None
    result = review_adult_gh_clinical_draft(request).candidate_result
    assert result["criterion_status"] == "unknown"
    assert "adult_gh_evidence.stimulation_tests[0].inadequate_response_documented" in result["missing_inputs"]


def test_typed_dataclass_facts_are_revalidated_instead_of_trusted():
    raw = payload()
    evidence = parse_adult_gh_evidence(raw["adult_gh_evidence"])
    invalid_test = replace(
        evidence.stimulation_tests[0],
        inadequate_response_documented="true",
        peak_gh_mcg_l=True,
        peak_gh_documented_in_report=1,
    )
    raw["adult_gh_evidence"] = replace(
        evidence,
        adult_hypothalamic_pituitary_gh_deficiency_suspected="true",
        stimulation_tests=(invalid_test, evidence.stimulation_tests[1]),
    )
    request = AdultGhClinicalDraftRequest.model_validate(raw)
    parsed = request.adult_gh_evidence
    assert parsed.adult_hypothalamic_pituitary_gh_deficiency_suspected is None
    assert parsed.stimulation_tests[0].inadequate_response_documented is None
    assert parsed.stimulation_tests[0].peak_gh_mcg_l is None
    assert parsed.stimulation_tests[0].peak_gh_documented_in_report is None
    assert review_adult_gh_clinical_draft(request).candidate_result["criterion_status"] == "unknown"


def test_existing_pydantic_request_is_revalidated_by_the_helper():
    raw = payload()
    raw["adult_gh_evidence"] = parse_adult_gh_evidence(raw["adult_gh_evidence"])
    raw["epiphyses_closed"] = "true"
    raw["drug_claim_date"] = SERVICE
    unsafe_typed = AdultGhClinicalDraftRequest.model_construct(**raw)
    response = review_adult_gh_clinical_draft(unsafe_typed)
    assert response.epiphyses_closed is None
    assert response.candidate_result["criterion_status"] == "unknown"


@pytest.mark.parametrize("value", ["{", "[]", [], 1, False, None])
def test_malformed_evidence_never_becomes_a_complete_record(value):
    raw = payload()
    raw["adult_gh_evidence"] = value
    request = AdultGhClinicalDraftRequest.model_validate(raw)
    assert request.adult_gh_evidence is None
    response = review_adult_gh_clinical_draft(request)
    assert response.candidate_result["criterion_status"] == "not_evaluated"
    assert response.clinical_eligibility_complete is False


def test_complete_candidate_failure_is_only_a_draft_restriction():
    raw = payload()
    raw["adult_gh_evidence"]["additional_anterior_pituitary_deficiency_confirmed"] = False
    raw["adult_gh_evidence"]["stimulation_tests"][0]["peak_gh_mcg_l"] = 3
    response = review(raw)
    assert response["candidate_result"]["criterion_status"] == "restriction_not_met"
    assert response["runtime_result"]["criterion_status"] == "not_evaluated"
    assert response["runtime_enabled"] is False
    assert response["clinical_eligibility_complete"] is False


@pytest.mark.parametrize("additional", [None, "false", 0, {}])
@pytest.mark.parametrize("transport", ["mapping", "request_json"])
def test_one_supportive_test_with_one_false_test_and_unknown_exception_stays_unknown(
    additional, transport,
):
    raw = payload()
    evidence = raw["adult_gh_evidence"]
    if additional is not None:
        evidence["additional_anterior_pituitary_deficiency_confirmed"] = additional
    # The ITT record is fully documented but its peak fails; the other test is
    # supportive. An unknown exception cannot determine whether one is enough.
    evidence["stimulation_tests"][0]["peak_gh_mcg_l"] = 3
    request = (
        AdultGhClinicalDraftRequest.model_validate_json(json.dumps(raw))
        if transport == "request_json"
        else AdultGhClinicalDraftRequest.model_validate(raw)
    )
    assert request.adult_gh_evidence.additional_anterior_pituitary_deficiency_confirmed is None
    response = review_adult_gh_clinical_draft(request).model_dump(mode="json")
    candidate = response["candidate_result"]
    assert candidate["criterion_status"] == "unknown"
    assert "adult_gh_evidence.additional_anterior_pituitary_deficiency_confirmed" in candidate["missing_inputs"]
    assert {
        "field": "adult_gh_evidence.stimulation_tests[0].peak_gh_mcg_l", "status": "fail",
    } in candidate["checks"]
    assert {
        "field": "adult_gh_evidence.stimulation_tests[1].inadequate_response_documented",
        "status": "pass",
    } in candidate["checks"]
    assert candidate["clinical_eligibility_complete"] is False
    assert response["runtime_result"]["criterion_status"] == "not_evaluated"
    assert response["runtime_result"]["clinical_eligibility_complete"] is False
    assert response["runtime_result"]["checks"] == []
    assert response["runtime_enabled"] is False
    assert response["clinical_eligibility_complete"] is False
    assert response["pending_requirements"] == PENDING


@pytest.mark.parametrize("drug_name", ["somatrogon", "risdiplam", "growth hormone"])
def test_unrelated_drug_and_somatrogon_have_no_draft_scope(drug_name):
    raw = payload()
    raw["drug_name"] = drug_name
    response = review(raw)
    assert response["drug_name"] == drug_name
    assert response["selected_rule_id"] == SELECTED_RULE
    assert response["candidate_result"] is None
    assert response["runtime_result"] is None
    assert response["clinical_eligibility_complete"] is False


@pytest.mark.parametrize(("field", "value"), [
    ("epiphyses_closed", False), ("gh_patient_group", "pediatric"),
    ("gh_treatment_phase", "continuation"), ("selected_rule_id", "unrelated_rule"),
])
def test_explicit_out_of_scope_context_is_preserved_and_not_evaluated(field, value):
    raw = payload()
    raw[field] = value
    response = review(raw)
    assert response[field] == value
    assert response["candidate_result"] is None
    assert response["runtime_result"] is None


@pytest.mark.parametrize("field", [
    "runtime_enabled", "clinical_eligibility_complete", "adult_gh_source_date_admission",
    "adult_gh_independent_clinical_interpretation", "adult_gh_clinical_interpretation_release",
])
def test_request_cannot_supply_release_or_completion_gates(field):
    raw = payload()
    raw[field] = True
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        AdultGhClinicalDraftRequest.model_validate(raw)


@pytest.mark.parametrize("field", ["drug_name", "selected_rule_id"])
def test_routing_identity_is_a_strict_string(field):
    raw = payload()
    raw[field] = 1
    with pytest.raises(ValidationError, match="Input should be a valid string"):
        AdultGhClinicalDraftRequest.model_validate(raw)


def test_native_schema_and_json_serialization_keep_typed_evidence_dates():
    request = AdultGhClinicalDraftRequest.model_validate(payload())
    serialized = json.loads(request.model_dump_json())
    assert serialized["adult_gh_evidence"]["applies_on"] == "2026-10-05"
    assert serialized["adult_gh_evidence"]["stimulation_tests"][0]["performed_on"] == "2026-10-02"
    assert serialized["adult_gh_evidence"]["stimulation_tests"][0]["peak_gh_mcg_l"] == 2.9
    assert AdultGhClinicalDraftRequest.model_validate(serialized) == request
    schema = AdultGhClinicalDraftRequest.model_json_schema()
    assert "AdultGhEvidence" in schema["$defs"]
    assert "AdultGhStimulationTest" in schema["$defs"]
    date_schema = schema["$defs"]["AdultGhStimulationTest"]["properties"]["performed_on"]
    assert {"format": "date", "type": "string"} in date_schema["anyOf"]
    response = review_adult_gh_clinical_draft(request)
    assert AdultGhClinicalDraftResponse.model_validate_json(response.model_dump_json()) == response


def test_local_candidate_helper_has_no_dedicated_endpoint():
    assert not hasattr(draft, "router")
    assert all(
        getattr(getattr(route, "endpoint", None), "__module__", None) != draft.__name__
        for route in app.routes
    )
    assert all("adult-gh" not in getattr(route, "path", "") for route in app.routes)
