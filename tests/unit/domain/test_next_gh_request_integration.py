"""Source-bound GH facts survive the actual HTTP boundary without payment clearance."""
from copy import deepcopy
import json
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from src.bilun.api.routes.validation import router
from src.bilun.shared.models import ClaimValidationRequest
from src.bilun.domain.claims.adapter import build_context_from_material_dict
from src.bilun.domain.prose_rules.drug_indication import evaluate_drug_indication_line_detailed

MATRIX = json.loads((Path(__file__).resolve().parents[2] / "fixtures/gh_http_request_boundaries.json").read_text())


@pytest.mark.parametrize("case", MATRIX["cases"], ids=lambda case: case["name"])
def test_actual_http_retains_source_boundaries_and_explicit_facts(case):
    raw = deepcopy(MATRIX["common_request"])
    facts = {**MATRIX["bases"][case["base"]], **case["material_patch"]}
    raw["materials"][0].update(facts)
    raw["materials"][0]["name"] = case["medicine"]
    raw["drug_context"].update(case["drug_context_patch"])
    req = ClaimValidationRequest.model_validate(raw)
    expected = case["expected_internal"]
    for mode in ("python", "json"):
        context = build_context_from_material_dict(req.model_dump(mode=mode))
        line = context.drug_lines[0]
        for field, value in facts.items():
            assert getattr(line, field) == value, field
        actual = evaluate_drug_indication_line_detailed(drug_line=line, claim=context.claims[0], diagnoses=[])
        hit = actual["violation"]
        if "missing_inputs" in expected:
            assert actual["missing_inputs"] == expected["missing_inputs"]
        if "missing_contains" in expected:
            assert expected["missing_contains"] in actual["missing_inputs"]
        if "failed_contains" in expected:
            assert expected["failed_contains"] in hit["growth_hormone_failed_criteria"]
        if "severity" in expected:
            assert hit["severity"] == expected["severity"]
    app = FastAPI()
    app.include_router(router, prefix="/api")
    with TestClient(app) as client:
        response = client.post("/api/validate-claim", json=raw, headers={"X-Bilun-Validation-Contract": "2"})
    assert response.status_code == 200
    public = response.json()
    row = next(item for item in public["advisories"] if item["rule"] == "drug_indication")
    assert set(expected.get("missing_inputs", [])) <= set(row["missing_inputs"])
    if "missing_contains" in expected:
        assert expected["missing_contains"] in row["missing_inputs"]
    assert row["disposition"] == "review_only" and public["is_valid"] is None
    assert not public["violations"]
    assert not any(key in row for key in ("payable_try", "risk_amount", "savings_try", "recoverable_uplift_try"))
