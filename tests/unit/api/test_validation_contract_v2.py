"""Old/new validator compatibility retains authentication and honest status."""

import pytest
from copy import deepcopy
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError

from src.bilun.api import SessionGateMiddleware
from src.bilun.api.routes import validation
from src.bilun.api.validation_schemas import ValidateClaimV2Response
from src.bilun.shared.models import ClaimValidationRequest

pytestmark = pytest.mark.unit


@pytest.fixture
def client(monkeypatch):
    # Test the real middleware without app lifespan/cache startup or credentials.
    monkeypatch.setattr("src.bilun.api.is_auth_configured", lambda: True)
    monkeypatch.setattr(
        "src.bilun.api.verify_session_token",
        lambda value: "test" if value == "test-session" else None,
    )
    app = FastAPI()
    app.include_router(validation.router, prefix="/api")
    app.add_middleware(SessionGateMiddleware)
    with TestClient(app) as result:
        yield result


def _login(client):
    from src.bilun.api.auth import COOKIE_NAME

    client.cookies.set(COOKIE_NAME, "test-session")


@pytest.mark.parametrize("path", ["/api/validate-claim", "/api/validate-claim/legacy"])
def test_both_contracts_require_authentication(client, path):
    response = client.post(
        path, json={"materials": []}, headers={"X-Bilun-Validation-Contract": "2"}
    )
    assert response.status_code == 401


@pytest.mark.parametrize("version", [None, "1", "3"])
def test_authenticated_old_frontend_gets_actionable_upgrade_instead_of_new_semantics(
    client, version
):
    _login(client)
    headers = {"X-Bilun-Validation-Contract": version} if version else {}
    response = client.post("/api/validate-claim", json={"materials": []}, headers=headers)
    assert response.status_code == 409
    body = response.json()
    assert body["code"] == "validation_contract_upgrade_required"
    assert "yenileyin" in body["detail"]
    assert "Reload" in body["detail"]
    assert body["legacy_endpoint"] == "/api/validate-claim/legacy"


def test_explicit_legacy_endpoint_retains_old_empty_claim_result(client):
    _login(client)
    response = client.post(
        "/api/validate-claim/legacy", json={"claim_id": "EMPTY", "materials": []}
    )
    assert response.status_code == 200
    body = response.json()
    assert "contract_version" not in body
    assert body["claim_id"] == "EMPTY"
    assert body["is_valid"] is True
    assert body["violations"] == []
    assert body["total_savings_try"] == 0
    assert body["total_risk_try"] == 0


def test_v2_empty_inputs_are_incomplete_without_exposing_historical_results(client):
    _login(client)
    response = client.post(
        "/api/validate-claim",
        json={"claim_id": "EMPTY", "materials": []},
        headers={"X-Bilun-Validation-Contract": "2"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["contract_version"] == 2
    assert body["validation_status"] == "partially_evaluated"
    assert body["is_valid"] is None
    assert body["violations"] == []
    assert "legacy_result" not in body
    assert not any("amount" in key or "savings" in key or "risk" in key for key in body)


def test_default_api_never_publishes_raw_legacy_money_or_denial_payload(client):
    _login(client)
    response = client.post(
        "/api/validate-claim",
        json={"materials": [{"name": "Cerrahi steril eldiven", "billed_amount": 987654.32}]},
        headers={"X-Bilun-Validation-Contract": "2"},
    )
    assert response.status_code == 200
    assert response.json()["violations"] == []
    assert "legacy_result" not in response.text
    assert "987654.32" not in response.text
    assert "risk_amount" not in response.text
    assert "savings_try" not in response.text
    assert "Should not be billed" not in response.text


@pytest.mark.parametrize("name,family,reason", [
    ("Bistüri ucu", "bundling", "ek3b1_exception_setting_and_exact_line_proof_required"),
    ("İnflow kateter", "exclusion", "ek3b2_exception_applicability_and_exact_line_proof_required"),
])
def test_v2_api_carries_unresolved_annex_proof_as_typed_review(client, name, family, reason):
    _login(client)
    response = client.post(
        "/api/validate-claim",
        json={"claim_id": "C1", "materials": [{"name": name, "billed_amount": 100}]},
        headers={"X-Bilun-Validation-Contract": "2"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["validation_status"] == "review_required"
    assert body["is_valid"] is None
    assert body["violations"] == []
    review = next(row for row in body["advisories"] if row["rule"] == family)
    assert review["disposition"] == "review_only"
    assert review["source_status"] == "historical_match_unverified"
    assert review["reason"] == reason
    assert "legacy_result" not in body
    assert not any(key in review for key in ("savings_try", "risk_amount", "amount_try"))


@pytest.mark.parametrize("name,annex,expected,reason", [
    ("Cerrahi steril eldiven", "ek3b1", False, "surgical_sterile_glove_exception"),
    ("Nonsteril eldiven", "ek3b1", True, None),
    ("Viskosüplemantasyon ürünleri", "ek3b2", None, "sut_annex_exception_applicability_required"),
    ("İnflow kateter", "ek3b2", True, None),
])
def test_v2_api_exposes_corrected_material_applicability_without_payment_claim(
    client, name, annex, expected, reason
):
    _login(client)
    response = client.post(
        "/api/validate-claim",
        json={"claim_id": "C1", "materials": [{"name": name, "billed_amount": 100}]},
        headers={"X-Bilun-Validation-Contract": "2"},
    )
    assert response.status_code == 200
    body = response.json()
    assert len(body["material_applicability"]) == 1
    material = body["material_applicability"][0]
    assert material["material_id"] == f'{body["request_id"]}:material:0'
    assert material["material_index"] == 0
    assert material["material_name"] == name
    assert material[annex] == {"matched": expected, "source_reason": reason}
    assert "is_reimbursable" not in material
    assert "savings_try" not in material


@pytest.fixture
def typed_payload():
    return validation.validate_claim_endpoint(
        ClaimValidationRequest.model_validate({"materials": [{"name": "Bistüri ucu"}]}),
        "2",
    )


@pytest.mark.parametrize("field", ["savings_try", "risk_amount", "amount_try"])
@pytest.mark.parametrize("surface", ["violations", "advisories"])
def test_typed_evidence_schema_rejects_monetary_leaks(typed_payload, field, surface):
    payload = deepcopy(typed_payload)
    evidence = {
        "evidence_id": "E1", "rule": "source-proven", "material_name": "Material",
        "message": "Evidence", field: 100,
        "disposition": "unpriced_compliance" if surface == "violations" else "review_only",
        "source_status": "primary_meaning_and_date_verified" if surface == "violations"
        else "historical_match_unverified",
    }
    payload[surface] = [evidence]
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        ValidateClaimV2Response.model_validate(payload)


@pytest.mark.parametrize("change", [
    {"disposition": "unpriced_compliance"},
    {"source_status": "made_up_proof"},
    {"disposition": "error"},
])
def test_advisory_cannot_claim_confirmed_disposition_or_fabricated_source(typed_payload, change):
    payload = deepcopy(typed_payload)
    payload["advisories"][0].update(change)
    with pytest.raises(ValidationError):
        ValidateClaimV2Response.model_validate(payload)


def test_historical_money_is_allowed_only_at_explicit_legacy_endpoint(typed_payload):
    historical = validation.validate_claim_legacy_endpoint(
        ClaimValidationRequest.model_validate({"materials": []})
    )
    assert historical["total_savings_try"] == 0
    payload = deepcopy(typed_payload)
    payload["legacy_result"] = historical
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        ValidateClaimV2Response.model_validate(payload)


def test_coverage_cannot_understate_unresolved_evaluations(typed_payload):
    payload = deepcopy(typed_payload)
    payload["coverage"]["unresolved_count"] += 1
    with pytest.raises(ValidationError, match="Unresolved count"):
        ValidateClaimV2Response.model_validate(payload)


def test_incomplete_scope_cannot_be_labeled_valid(typed_payload):
    payload = deepcopy(typed_payload)
    payload["is_valid"] = True
    with pytest.raises(ValidationError, match="Validation status"):
        ValidateClaimV2Response.model_validate(payload)


def test_provenance_rejects_adapter_defaults_as_verified_facts(typed_payload):
    payload = deepcopy(typed_payload)
    payload["provenance"]["adapter_defaults_are_evidence"] = True
    with pytest.raises(ValidationError):
        ValidateClaimV2Response.model_validate(payload)


def test_api_shared_projection_rejects_injected_nested_money(monkeypatch, typed_payload):
    payload = deepcopy(typed_payload)
    payload["advisories"][0]["risk_amount"] = 999
    monkeypatch.setattr(validation, "validate_claim_v2", lambda *_, **__: payload)
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        validation.validate_claim_endpoint(ClaimValidationRequest(materials=[]), "2")
