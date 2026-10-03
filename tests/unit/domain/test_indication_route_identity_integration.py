"""Unknown indication facts must not manufacture a selected clinical route."""
from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from src.bilun.api.routes.validation import router
from src.bilun.shared.models import ClaimValidationRequest
from src.bilun.domain.claims.adapter import build_context_from_material_dict
from src.bilun.domain.prose_rules.drug_indication import evaluate_drug_indication_line_detailed


@pytest.mark.parametrize("report_present", [False, True])
@pytest.mark.parametrize("service_date", [None, "2026-01-02", "2026-10-02"])
def test_unknown_hbv_scope_preserves_ambiguous_route_through_http(report_present, service_date):
    raw = {
        "claim_id": "SYNTHETIC-INDICATION-AMBIGUITY",
        "materials": [{"name": "BARACLUDE 0.5 MG (ENTEKAVIR)"}],
        "drug_context": {
            "primary_icd10": "B18.1", "service_date": service_date,
            "board_report_present": report_present, "report_duration_months": None,
        },
    }
    request = ClaimValidationRequest.model_validate(raw)
    for mode in ("python", "json"):
        context = build_context_from_material_dict(request.model_dump(mode=mode))
        result = evaluate_drug_indication_line_detailed(
            drug_line=context.drug_lines[0], claim=context.claims[0], diagnoses=[]
        )
        assert result["selected_rule_id"] is None
        assert result["violation"]["rule_id"] is None
        assert result["violation"]["selected_rule_id"] is None
        assert result["violation"]["violation_kind"] == "ambiguous_route"
        assert result["violation"]["severity"] == "review"
        observation = next(
            item for item in result["clinical_restrictions"]
            if item["constraint_set"] == "other_indication_source_constraints"
        )
        assert observation["criterion_status"] in {"unknown", "not_evaluated"}
        assert observation["checks"] == []
        assert observation["clinical_eligibility_complete"] is False
    app = FastAPI()
    app.include_router(router, prefix="/api")
    with TestClient(app) as client:
        response = client.post(
            "/api/validate-claim", json=raw,
            headers={"X-Bilun-Validation-Contract": "2"},
        )
    assert response.status_code == 200
    public = response.json()
    advisory = next(item for item in public["advisories"] if item["rule"] == "drug_indication")
    assert advisory.get("selected_rule_id") is None
    assert advisory["disposition"] == "review_only"
    observation = next(
        item for item in advisory["clinical_restrictions"]
        if item["constraint_set"] == "other_indication_source_constraints"
    )
    assert observation["criterion_status"] in {"unknown", "not_evaluated"}
    assert observation["checks"] == []
    assert observation["clinical_eligibility_complete"] is False
    assert public["is_valid"] is None and public["violations"] == []
    assert not any(key in advisory for key in ("payable_try", "risk_amount", "savings_try"))
