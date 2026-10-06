"""Standalone API contracts keep MDS candidate inspection private and gated."""
from dataclasses import fields
from datetime import date, datetime
import json

from pydantic import ValidationError
import pytest

from src.bilun.api import mds_clinical_draft as api
from src.bilun.domain.claims.mds_evidence import MdsEvidence
from src.bilun.domain.prose_rules._drug_indication import clinical_mds as clinical
from src.bilun.domain.validation_contract import ValidationClinicalRestriction


DAY = date(2026, 10, 2)
RULE = "4.2.9.mds_esa_hematology_report"
pytestmark = pytest.mark.unit


def request(**changes):
    return {
        "drug_name": "epoetin alfa",
        "selected_rule_id": RULE,
        "drug_claim_date": DAY.isoformat(),
        "observed_icd10_codes": ["D46.1"],
        "mds_evidence": {
            "applies_on": DAY.isoformat(),
            "assessment_date": DAY.isoformat(),
            "indication": "mds_anemia",
            "substance": "epoetin_alfa",
            "phase": "initiation",
            "hb_value": 10.0,
            "hb_unit": "g/dL",
            "hb_date": DAY.isoformat(),
            "blast_value": 4.0,
            "blast_unit": "%",
            "blast_date": DAY.isoformat(),
            "serum_epo_value": 400.0,
            "serum_epo_unit": "mu/ml",
            "serum_epo_date": DAY.isoformat(),
            "weekly_dose_value": 900.0,
            "weekly_dose_unit": "IU/kg/week",
            "specialist_report_present": True,
            "report_author_specialty": "hematology",
            "report_date": DAY.isoformat(),
            "prescribed_by_specialist": True,
            "prescribed_by_specialty": "hematology",
            "prescription_based_on_same_hematology_report": True,
            "usage_dose_documented_in_report": True,
            "usage_duration_documented_in_report": True,
            "lab_results_dates_documented_in_prescription_or_report": True,
            "hemogram_date": DAY.isoformat(),
            "hemogram_result_documented_in_prescription": True,
            "hemogram_date_documented_in_prescription": True,
            "prescribed_supply_months": 1,
        },
        **changes,
    }


def assert_draft(response, kind):
    assert isinstance(response, api.MdsClinicalDraftResponse)
    assert response.review_status == "review_required"
    assert response.is_draft is True
    assert response.clinical_eligibility_complete is False
    assert response.integration_status == "registered_gated_draft"
    assert response.inspection_kind == kind
    if response.restriction is not None:
        assert isinstance(response.restriction, ValidationClinicalRestriction)
        assert response.restriction.clinical_eligibility_complete is False
        assert response.restriction.verification_status == "ai_generated_pending_review"


@pytest.mark.parametrize("transport", ["mapping", "typed", "json"])
def test_default_helper_returns_only_gated_runtime_review(transport):
    raw = request()
    value = raw if transport == "mapping" else (
        api.MdsClinicalDraftRequest.model_validate(raw) if transport == "typed"
        else api.MdsClinicalDraftRequest.model_validate_json(json.dumps(raw))
    )
    response = api.evaluate_mds_draft_request(value)
    assert_draft(response, "gated_runtime")
    restriction = response.restriction
    assert restriction.constraint_set == "mds_epoetin"
    assert restriction.criterion_status == "not_evaluated"
    assert restriction.checks == []
    assert {"verified_source_for_service_date", "mds_clinical_interpretation_release"} <= set(
        restriction.missing_inputs
    )
    assert restriction.source_authority.family_id == "mds_epoetin"
    assert restriction.source_authority.status == "review_required"


def test_local_candidate_helper_remains_draft_even_when_necessary_checks_clear():
    response = api.inspect_mds_candidate_request(request())
    assert_draft(response, "local_candidate")
    assert response.restriction.criterion_status == "criterion_clear"
    assert response.restriction.checks
    assert all(check.status == "pass" for check in response.restriction.checks)
    assert api.evaluate_mds_draft_request(request()).restriction.criterion_status == "not_evaluated"


@pytest.mark.parametrize("transport", ["mapping", "typed", "json"])
@pytest.mark.parametrize("relation,status,parsed", [
    (True, "criterion_clear", True), (False, "restriction_not_met", False),
    (None, "unknown", None), (1, "unknown", None), ("true", "unknown", None),
])
def test_same_report_relationship_survives_existing_api_transport_without_inference(transport, relation, status, parsed):
    field = "prescription_based_on_same_hematology_report"
    raw = request()
    raw["mds_evidence"][field] = relation
    typed = api.MdsClinicalDraftRequest.model_validate(raw)
    assert getattr(typed.mds_evidence, field) is parsed
    value = raw if transport == "mapping" else (
        typed if transport == "typed" else api.MdsClinicalDraftRequest.model_validate_json(json.dumps(raw))
    )
    response = api.inspect_mds_candidate_request(value)
    assert_draft(response, "local_candidate")
    restriction = response.restriction
    assert restriction.criterion_status == status
    assert restriction.missing_inputs == (["mds_evidence." + field] if parsed is None else [])
    assert any(check.field == "mds_evidence." + field for check in restriction.checks)
    runtime = api.evaluate_mds_draft_request(value)
    assert_draft(runtime, "gated_runtime")
    assert runtime.restriction.criterion_status == "not_evaluated"
    assert runtime.restriction.checks == []


def test_existing_api_does_not_infer_relationship_from_complete_report_and_prescriber_facts():
    raw = request()
    raw["mds_evidence"].pop("prescription_based_on_same_hematology_report")
    response = api.inspect_mds_candidate_request(raw)
    assert_draft(response, "local_candidate")
    assert response.restriction.criterion_status == "unknown"
    assert response.restriction.missing_inputs == ["mds_evidence.prescription_based_on_same_hematology_report"]


@pytest.mark.parametrize("key", [
    "private_note", "candidate", "inspection_kind", "interpretation_released",
    "source_admitted", "clinical_eligibility_complete",
])
def test_request_cannot_enable_candidate_or_release_with_top_level_fields(key):
    with pytest.raises(ValidationError):
        api.evaluate_mds_draft_request(request(**{key: True}))


@pytest.mark.parametrize("field,bad", [
    ("hb_value", "10"), ("hb_value", True), ("hb_value", float("nan")),
    ("blast_value", "4"), ("blast_value", False),
    ("serum_epo_value", "400"), ("weekly_dose_value", "900"),
    ("weekly_dose_value", float("inf")), ("prescribed_supply_months", True),
    ("specialist_report_present", "true"), ("prescribed_by_specialist", 1),
    ("hb_unit", "g/L"), ("blast_unit", "fraction"),
    ("serum_epo_unit", "IU/L"), ("weekly_dose_unit", "IU/week"),
    ("phase", "renewal"), ("applies_on", "2026-10-2"),
    ("assessment_date", "2026-02-30"), ("hb_date", "2026-10-02T00:00:00Z"),
])
def test_invalid_optional_clinical_facts_stay_unknown_without_coercion(field, bad):
    raw = request()
    raw["mds_evidence"][field] = bad
    typed = api.MdsClinicalDraftRequest.model_validate(raw)
    assert isinstance(typed.mds_evidence, MdsEvidence)
    assert getattr(typed.mds_evidence, field) is None
    response = api.inspect_mds_candidate_request(typed)
    assert_draft(response, "local_candidate")
    assert response.restriction.criterion_status in {"unknown", "not_evaluated"}
    assert response.restriction.missing_inputs
    assert api.evaluate_mds_draft_request(typed).restriction.checks == []


@pytest.mark.parametrize("bad", [None, [], True, 4, "not JSON", "[]", "null"])
def test_absent_or_non_object_evidence_never_invents_facts(bad):
    typed = api.MdsClinicalDraftRequest.model_validate(request(mds_evidence=bad))
    assert typed.mds_evidence is None
    response = api.evaluate_mds_draft_request(typed)
    assert_draft(response, "gated_runtime")
    assert response.restriction.criterion_status == "not_evaluated"
    assert response.restriction.checks == []


@pytest.mark.parametrize("bad", [None, True, 123, "2026-02-30", "2026-10-02T00:00:00Z", datetime(2026, 10, 2)])
def test_service_date_is_exact_optional_fact_and_never_defaults_to_today(bad):
    typed = api.MdsClinicalDraftRequest.model_validate(request(drug_claim_date=bad))
    assert typed.drug_claim_date is None
    response = api.evaluate_mds_draft_request(typed)
    assert response.restriction.criterion_status == "not_evaluated"
    assert "drug_claim_date" in response.restriction.missing_inputs
    assert response.restriction.checks == []


@pytest.mark.parametrize("bad", ["D46.1", ("D46.1",), [True], ["D46.1", 123]])
def test_observed_codes_are_not_coerced_or_derived_from_invalid_context(bad):
    typed = api.MdsClinicalDraftRequest.model_validate(request(observed_icd10_codes=bad))
    assert typed.observed_icd10_codes is None


def test_constructed_typed_request_is_revalidated_before_evaluation(monkeypatch):
    raw = request(drug_claim_date="2026-10-02T00:00:00Z")
    raw["mds_evidence"]["hb_value"] = True
    constructed = api.MdsClinicalDraftRequest.model_construct(**raw)
    captured = []

    def observe(line, selected, *, codes):
        captured.append((line, selected, codes))
        return None

    monkeypatch.setattr(api, "evaluate_mds_clinical_draft", observe)
    response = api.evaluate_mds_draft_request(constructed)
    assert_draft(response, "gated_runtime")
    assert captured[0][0].drug_claim_date is None
    assert isinstance(captured[0][0].mds_evidence, MdsEvidence)
    assert captured[0][0].mds_evidence.hb_value is None


def test_raw_private_input_extras_and_release_flags_never_reach_output():
    raw = request()
    raw["mds_evidence"].update({
        "private_note": "NEVER_PUBLISH_MDS_NOTE", "risk_amount": 987654.32,
        "interpretation_released": True, "source_admitted": True,
    })
    for helper in (api.evaluate_mds_draft_request, api.inspect_mds_candidate_request):
        response = helper(raw)
        encoded = response.model_dump_json()
        assert all(value not in encoded for value in (
            "NEVER_PUBLISH_MDS_NOTE", "private_note", "987654.32", "risk_amount",
            "raw_evidence", '"hb_value":', '"serum_epo_value":', "interpretation_released",
            "source_admitted", "payable", "savings", "receipts",
        ))
        assert set(response.model_dump()) == {
            "review_status", "is_draft", "clinical_eligibility_complete",
            "integration_status", "inspection_kind", "restriction",
        }


def test_bounded_existing_contract_preserves_every_declared_missing_input(monkeypatch):
    missing = [
        *("mds_evidence." + field.name for field in fields(MdsEvidence)),
        "verified_source_for_service_date", "mds_clinical_interpretation_release",
        "mds_evidence.substance_context_reconciliation",
        "mds_evidence.indication_context_reconciliation",
        "mds_evidence.phase_context_reconciliation", "mds_evidence.phase_interpretation",
    ]

    def outcome(*args, **kwargs):
        return {
            "constraint_set": "mds_epoetin", "criterion_status": "unknown",
            "missing_inputs": missing, "checks": [], "source_refs": [],
            "clinical_eligibility_complete": True,
            "raw_evidence": request()["mds_evidence"], "risk_amount": 987654.32,
        }

    monkeypatch.setattr(api, "evaluate_mds_clinical_draft", outcome)
    response = api.evaluate_mds_draft_request(request())
    assert response.restriction.missing_inputs == missing
    assert response.restriction.clinical_eligibility_complete is False
    assert "raw_evidence" not in response.model_dump_json()
    assert "987654.32" not in response.model_dump_json()


def test_runtime_source_gate_prevents_predicate_attempts(monkeypatch):
    def comparison_forbidden(*args, **kwargs):
        pytest.fail("A gated runtime draft attempted a clinical comparison")

    monkeypatch.setattr(clinical.Reader, "test", comparison_forbidden)
    response = api.evaluate_mds_draft_request(request())
    assert response.restriction.criterion_status == "not_evaluated"
    assert response.restriction.checks == []


@pytest.mark.parametrize("drug", [
    "darbepoetin", "ARANESP", "epoetin", "eritropoietin", "EPREX", "MIRCERA",
])
def test_generic_aliases_and_darbepoetin_cannot_select_alfa_beta_candidate(drug):
    for helper in (api.evaluate_mds_draft_request, api.inspect_mds_candidate_request):
        response = helper(request(drug_name=drug))
        assert_draft(response, "gated_runtime" if helper is api.evaluate_mds_draft_request else "local_candidate")
        assert response.restriction is None


def test_pure_ckd_scope_is_untouched_and_mixed_context_requires_review():
    raw = request(observed_icd10_codes=["N18.5"])
    raw["mds_evidence"]["indication"] = "ckd_anemia"
    assert api.evaluate_mds_draft_request(raw).restriction is None
    assert api.inspect_mds_candidate_request(raw).restriction is None
    mixed = request(observed_icd10_codes=["D46.1", "N18.5"])
    mixed["mds_evidence"]["specialist_report_present"] = False
    response = api.inspect_mds_candidate_request(mixed)
    assert response.restriction.criterion_status == "unknown"
    assert "mds_evidence.indication_context_reconciliation" in response.restriction.missing_inputs


def test_missing_selected_rule_never_selects_by_name_or_evidence():
    for helper in (api.evaluate_mds_draft_request, api.inspect_mds_candidate_request):
        assert helper(request(selected_rule_id=None)).restriction is None


def test_local_candidate_helper_has_no_dedicated_endpoint():
    from src.bilun.api import app

    assert not hasattr(api, "router")
    assert not any("mds" in route.path.casefold() for route in app.routes if hasattr(route, "path"))


@pytest.mark.parametrize("field,value", [
    ("review_status", "clear"), ("is_draft", False),
    ("clinical_eligibility_complete", True), ("integration_status", "registered"),
])
def test_output_contract_cannot_claim_release_or_complete_eligibility(field, value):
    with pytest.raises(ValidationError):
        api.MdsClinicalDraftResponse.model_validate({"inspection_kind": "gated_runtime", field: value})
