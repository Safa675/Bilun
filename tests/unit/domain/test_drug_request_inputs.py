"""Supported drug inputs preserve unknown and explicit negative facts at the API boundary."""
from datetime import date
import json

import pytest

from src.bilun.shared.models import ClaimValidationRequest
from src.bilun.domain.claim_validation_v2 import _drug_missing_inputs
from src.bilun.domain.claims.adapter import build_context_from_material_dict
from src.bilun.domain.validation_contract import ValidationAdvisory
from src.bilun.domain.constants import _GAZETTE_DIR

pytestmark = pytest.mark.unit


def test_supported_drug_facts_survive_request_and_adapter(monkeypatch):
    monkeypatch.setattr(
        "src.bilun.domain.claims.adapter._enrich_material_regulatory_flags", lambda rows: rows
    )
    request = ClaimValidationRequest.model_validate({
        "claim_id": "INPUTS",
        "drug_context": {"primary_icd10": "", "board_report_present": False,
                         "report_duration_months": 0, "service_date": "2026-06-30"},
        "materials": [{"name": "trastuzumab", "annual_application_count": 0,
                       "is_loading_phase": False,
                       "biomarkers": [{"marker": "HER2", "status": "negative"}],
                       "prior_therapies": [{"drug_or_class": "imatinib", "outcome": "resistant"}]}],
    })
    assert request.drug_context.service_date == date(2026, 6, 30)
    context = build_context_from_material_dict(request.model_dump())
    assert len(context.drug_lines) == 1  # Missing diagnosis must not silently disable checks.
    line = context.drug_lines[0]
    assert line.annual_application_count == 0
    assert line.is_loading_phase is False
    assert line.drug_specialty_board_report_present is False
    assert line.drug_report_duration_months == 0
    assert line.biomarkers == ({"marker": "HER2", "status": "negative"},)
    assert line.prior_therapies == ({"drug_or_class": "imatinib", "outcome": "resistant"},)


def test_unknown_drug_facts_remain_unknown(monkeypatch):
    monkeypatch.setattr(
        "src.bilun.domain.claims.adapter._enrich_material_regulatory_flags", lambda rows: rows
    )
    request = ClaimValidationRequest.model_validate({
        "drug_context": {"primary_icd10": ""}, "materials": [{"name": "drug"}],
    })
    context = build_context_from_material_dict(request.model_dump())
    line = context.drug_lines[0]
    assert line.is_loading_phase is None
    assert line.annual_application_count is None
    assert line.drug_specialty_board_report_present is None
    assert line.drug_report_duration_months is None
    assert line.biomarkers is None
    assert line.prior_therapies is None
    assert request.drug_context.service_date is None


def test_missing_drug_inputs_are_bounded_and_publicly_serializable():
    missing = _drug_missing_inputs({"missing_inputs": [
        "primary_icd10", "biomarkers.HER2", "prior_therapies.drug_or_class",
        "annual_application_count", "primary_icd10", "secret_field", 3,
    ]})
    assert missing == ["annual_application_count", "biomarkers.HER2", "primary_icd10",
                       "prior_therapies.drug_or_class"]
    advisory = ValidationAdvisory(
        evidence_id="request:1", rule="drug_indication", material_name="drug",
        message="Historical rule observation requires source and input review.",
        disposition="review_only", source_status="historical_match_unverified",
        missing_inputs=missing,
    )
    assert advisory.model_dump()["missing_inputs"] == missing


def test_incomplete_prior_history_does_not_become_negative_when_transporting_rows(monkeypatch):
    from src.bilun.domain.prose_rules._drug_indication.constraints import (
        _evaluate_prior_therapy_constraints,
    )

    monkeypatch.setattr(
        "src.bilun.domain.claims.adapter._enrich_material_regulatory_flags", lambda rows: rows
    )
    request = ClaimValidationRequest.model_validate({
        "drug_context": {"primary_icd10": "C34.9"},
        "materials": [{"name": "synthetic drug", "prior_therapies": [
            {"drug_or_class": "unrelated therapy", "outcome": "resistant"},
            {"drug_or_class": "", "outcome": ""},
        ]}],
    })
    context = build_context_from_material_dict(request.model_dump())
    result = _evaluate_prior_therapy_constraints(
        rule={"requires_prior_therapy": {"drug_or_class": "imatinib", "outcome": "resistant"}},
        drug_line=context.drug_lines[0], claim=context.claims[0], icd_codes=["C34.9"],
    )
    assert result["violation_kind"] == "needs_prior_therapy_verification"
    assert result["missing_inputs"] == ["prior_therapies.drug_or_class"]


def test_every_authored_temporal_prerequisite_survives_bounded_projection():
    catalog = json.loads((_GAZETTE_DIR / "temporal/drug_amendments_2026_10.json").read_text())
    required = {"historical_rule_version", "effective_rule_version"}
    for rule in [*catalog["rules"], *catalog["quarantined_rules"]]:
        required.update(rule.get("unimplemented_clinical_inputs", []))
    result = _drug_missing_inputs({"missing_inputs": [*required, "unrecognized_patient_note"]})
    assert result == sorted(required)
