"""Drug form JSON preserves supplied facts at the public validation boundary."""

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from src.bilun.api.routes import validation
from src.bilun.domain import claim_validation_v2
from src.bilun.shared.models import ClaimValidationRequest

pytestmark = pytest.mark.unit


def test_form_json_preserves_unknown_empty_and_negative_inputs(monkeypatch):
    empty_result = validation.validate_claim_endpoint(ClaimValidationRequest(), "2")
    captured = {}

    def capture(legacy, *, supplied_claim):
        captured.update(legacy=legacy, supplied=supplied_claim)
        return empty_result

    monkeypatch.setattr(validation, "validate_claim_v2", capture)
    app = FastAPI()
    app.include_router(validation.router, prefix="/api")
    request = {
        "claim_id": "FORM",
        "drug_context": {
            "primary_icd10": "", "prescriber_specialty": "",
            "board_report_present": False, "report_duration_months": 0,
            "service_date": "2026-06-30",
        },
        "materials": [{
            "name": "synthetic drug", "annual_application_count": 0,
            "is_loading_phase": False,
            "biomarkers": [{"marker": "HER2", "status": "negative"}],
            "prior_therapies": [{"drug_or_class": "", "outcome": ""}],
        }, {"name": "untouched", "biomarkers": None, "prior_therapies": None},
            {"name": "cleared", "biomarkers": [], "prior_therapies": []}],
    }
    with TestClient(app) as client:
        response = client.post("/api/validate-claim", json=request,
                               headers={"X-Bilun-Validation-Contract": "2"})
    assert response.status_code == 200
    for payload in captured.values():
        context = payload["drug_context"]
        assert context["primary_icd10"] == ""
        assert context["board_report_present"] is False
        assert context["report_duration_months"] == 0
        assert context["service_date"] == "2026-06-30"
        first, untouched, cleared = payload["materials"]
        assert first["annual_application_count"] == 0
        assert first["is_loading_phase"] is False
        assert first["biomarkers"] == [{"marker": "HER2", "status": "negative"}]
        assert first["prior_therapies"] == [{"drug_or_class": "", "outcome": ""}]
        assert untouched["biomarkers"] is None
        assert untouched["prior_therapies"] is None
        assert cleared["biomarkers"] == []
        assert cleared["prior_therapies"] == []


def test_typed_api_exposes_missing_drug_inputs_without_certifying_observations(monkeypatch):
    monkeypatch.setattr(claim_validation_v2, "analyze_claim", lambda *args, **kwargs: [{
        "rule": "drug_indication", "severity": "review", "material_name": "Drug",
        "message": "Source observation", "violation_kind": "needs_biomarker_verification",
        "missing_inputs": ["biomarkers.HER2", "annual_application_count", "route_discriminator"],
        "savings_try": 0, "risk_amount": 0,
    }])
    result = validation.validate_claim_endpoint(ClaimValidationRequest.model_validate({
        "materials": [{"name": "Drug"}], "drug_context": {"primary_icd10": ""},
    }), "2")
    advisory = next(row for row in result["advisories"] if row["rule"] == "drug_indication")
    assert advisory["missing_inputs"] == [
        "annual_application_count", "biomarkers.HER2", "route_discriminator",
    ]
    assert advisory["disposition"] == "review_only"
    assert advisory["source_status"] == "historical_match_unverified"
    assert result["is_valid"] is None
    assert result["violations"] == []
    assert "legacy_result" not in result
    assert "risk_amount" not in advisory
    assert "savings_try" not in advisory
