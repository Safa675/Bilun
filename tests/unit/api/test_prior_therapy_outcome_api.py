"""Source-backed prior outcomes survive HTTP and cached billing projections.

The two pinned production rows are evaluated with matching diagnosis, biomarker,
report and prescriber inputs. The corpus loader is restricted to the real source
row. An existing unrelated cache hashes drug tuples containing dicts and raises
before drug evaluation, so its actual builder body runs without memoization in
this fixture. HTTP parsing, the claim adapter, evaluator, canonical findings and
public serialization run normally. Isolating a row avoids choosing among the
full corpus's other clinical routes or certifying clinical eligibility.
"""

from copy import deepcopy
import json

import duckdb
from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from src.bilun.api.public_responses import project_public_response
from src.bilun.api.routes import validation
from src.bilun.api.schemas import DrugIndicationReviewResponse
from src.bilun.domain.billing import engine, gap_closing_evaluations
from src.bilun.domain.billing.drug_indication_findings import (
    evaluate_drug_indication_findings,
    normalize_drug_indication_payload,
)
from src.bilun.domain.claims.adapter import build_context_from_material_dict
from src.bilun.domain.prose_rules import drug_indication as prose, gap_closing, payment_method
from src.bilun.shared.models import ClaimValidationRequest


pytestmark = pytest.mark.unit

_SOURCE_RULES = (
    "4.2.14.C.tier_c_b.C005024.dasatinib",
    "4.2.14.C.tier_c_b.C005043.bosutinib",
)
_MONEY_FIELDS = {
    "amount_try", "payable_try", "savings_try", "recoverable_uplift_try",
    "compliance_savings_try", "risk_amount", "risk_amount_try", "audit_exposure_try",
}


@pytest.fixture(scope="session", autouse=True)
def _reconcile_drug_manifests_at_session_start():
    # This read-only regression owns no corpus/manifests. The normal global
    # fixture reconciles them with write=True, unrelated to outcome checks.
    yield


@pytest.fixture(params=_SOURCE_RULES)
def source_rules(request):
    production = next(
        row for row in prose.list_drug_indication_rules() if row["rule_id"] == request.param
    )
    production = deepcopy(production)
    assert production["requires_prior_therapy"] == {
        "drug_or_class": "imatinib", "outcome": "resistant_or_intolerant",
    }
    assert production["gate_b_sources"]
    return [production]


def _request(rules, prior):
    return {
        "claim_id": "PRIOR-OUTCOME-API",
        "materials": [{
            "name": rules[0]["drug_names"][0], "prior_therapies": prior,
            "biomarkers": [{"marker": "BCR_ABL", "status": "positive"}],
        }],
        "drug_context": {
            "primary_icd10": "C92.1", "prescriber_specialty": "tıbbi onkoloji",
            "board_report_present": True, "service_date": "2026-10-02",
        },
    }


def _assert_unpriced_public(value):
    if isinstance(value, dict):
        assert not (_MONEY_FIELDS & value.keys())
        for nested in value.values():
            _assert_unpriced_public(nested)
    elif isinstance(value, list):
        for nested in value:
            _assert_unpriced_public(nested)


@pytest.fixture
def endpoint(monkeypatch, source_rules):
    observed = []
    real_evaluate = engine.evaluate_drug_indication_findings

    def capture(*args, **kwargs):
        batch = real_evaluate(*args, **kwargs)
        observed.append(batch)
        return batch

    monkeypatch.setattr(prose, "list_drug_indication_rules", lambda: source_rules)
    monkeypatch.setattr(engine, "evaluate_drug_indication_findings", capture)
    # Existing broad-rule cache keys cannot hash prior_therapies/biomarker dicts.
    # Exercise the original builder, rather than a stubbed result, at both aliases.
    builder = gap_closing._build_gap_closing_context.__wrapped__
    monkeypatch.setattr(gap_closing_evaluations, "_build_gap_closing_context", builder)
    monkeypatch.setattr(payment_method, "_gap_closing_build_context", builder)
    app = FastAPI()
    app.include_router(validation.router, prefix="/api")
    with TestClient(app) as client:
        yield client, observed


@pytest.mark.parametrize("prior,kind,severity,criterion", [
    ([{"drug_or_class": "imatinib"}], "needs_prior_therapy_verification", "review", "unknown"),
    ([{"drug_or_class": "imatinib", "outcome": ""}], "needs_prior_therapy_verification", "review", "unknown"),
    ([{"drug_or_class": "imatinib", "outcome": "unknown"}], "needs_prior_therapy_verification", "review", "unknown"),
    ([{"drug_or_class": "imatinib", "outcome": "completed"}], "needs_prior_therapy_verification", "review", "unknown"),
    ([{"drug_or_class": "imatinib", "outcome": "failed"}], "needs_prior_therapy_verification", "review", "unknown"),
    ([{"drug_or_class": "imatinib", "outcome": "responsive"}], "prior_therapy_mismatch", "error", "restriction_not_met"),
    ([{"drug_or_class": "nilotinib", "outcome": "resistant"}], "prior_therapy_mismatch", "error", "restriction_not_met"),
    ([{"drug_or_class": "imat", "outcome": "resistant"}], "prior_therapy_mismatch", "error", "restriction_not_met"),
    ([{"drug_or_class": "nonimatinib", "outcome": "resistant"}], "prior_therapy_mismatch", "error", "restriction_not_met"),
    ([{"drug_or_class": "nilotinib", "outcome": "resistant"},
      {"drug_or_class": "imatinib", "outcome": "responsive"}], "prior_therapy_mismatch", "error", "restriction_not_met"),
])
def test_http_prior_outcome_retains_review_and_no_payment_conclusion(
    endpoint, source_rules, prior, kind, severity, criterion,
):
    client, observed = endpoint
    response = client.post(
        "/api/validate-claim", json=_request(source_rules, prior),
        headers={"X-Bilun-Validation-Contract": "2"},
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert len(observed) == 1
    finding, = observed[0].findings
    assert observed[0].evaluations[0].selected_rule_id == source_rules[0]["rule_id"]
    assert finding.finding_kind == kind and finding.severity == severity
    advisory, = [row for row in payload["advisories"] if row["rule"] == "drug_indication"]
    assert advisory["disposition"] == "review_only"
    assert advisory["source_status"] == "historical_match_unverified"
    assert advisory["clinical_eligibility_complete"] is False
    restriction, = advisory["clinical_restrictions"]
    assert restriction["criterion_status"] == criterion
    assert restriction["source_refs"] == source_rules[0]["gate_b_sources"]
    assert restriction["clinical_eligibility_complete"] is False
    assert advisory["missing_inputs"] == (["prior_therapies"] if severity == "review" else [])
    assert payload["is_valid"] is None and payload["violations"] == []
    _assert_unpriced_public(payload)


@pytest.mark.parametrize("outcome", ["resistant", "intolerant", "resistant_or_intolerant"])
def test_http_source_alternatives_clear_only_the_prior_requirement(endpoint, source_rules, outcome):
    client, observed = endpoint
    prior = [{"drug_or_class": "imatinib", "outcome": outcome}]
    response = client.post(
        "/api/validate-claim", json=_request(source_rules, prior),
        headers={"X-Bilun-Validation-Contract": "2"},
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert len(observed) == 1 and observed[0].findings == ()
    assert observed[0].evaluations[0].selected_rule_id == source_rules[0]["rule_id"]
    assert not [row for row in payload["advisories"] if row["rule"] == "drug_indication"]
    assert all(row["clinical_eligibility_complete"] is not True for row in payload["advisories"])
    assert payload["violations"] == []
    _assert_unpriced_public(payload)


@pytest.mark.parametrize("outcome,kind,criterion", [
    ("unknown", "needs_prior_therapy_verification", "unknown"),
    ("responsive", "prior_therapy_mismatch", "restriction_not_met"),
])
def test_public_billing_cache_preserves_outcome_status_without_raw_data(source_rules, outcome, kind, criterion):
    raw = _request(source_rules, [{"drug_or_class": "imatinib", "outcome": outcome}])
    normalized = ClaimValidationRequest.model_validate(raw).model_dump(mode="json")
    context = build_context_from_material_dict(normalized)
    batch = evaluate_drug_indication_findings(context.patient_id, context, rules=source_rules)
    finding, = batch.findings
    assert batch.evaluations[0].selected_rule_id == source_rules[0]["rule_id"]
    assert finding.finding_kind == kind
    payload = {
        "evaluations": [row.to_dict() for row in batch.evaluations],
        "findings": [row.to_dict() for row in batch.findings],
        "violations": list(batch.legacy_violations),
    }
    DrugIndicationReviewResponse.model_validate(payload)
    for rows in payload.values():
        for row in rows:
            row["raw_evidence"] = {"prior_therapies": raw["materials"][0]["prior_therapies"],
                                   "private_note": "DO_NOT_PUBLISH"}
    public = project_public_response({"drug_indication": payload}, "get_billing_report")
    serialized = json.dumps(public)
    assert "DO_NOT_PUBLISH" not in serialized and "raw_evidence" not in serialized
    for rows in public["drug_indication"].values():
        for row in rows:
            assert row["clinical_eligibility_complete"] is False
            restriction, = row["clinical_restrictions"]
            assert restriction["criterion_status"] == criterion
            assert restriction["source_refs"] == source_rules[0]["gate_b_sources"]
            assert restriction["clinical_eligibility_complete"] is False
            assert row.get("savings_try", 0) == 0 and row.get("risk_amount", 0) == 0
    with duckdb.connect(":memory:") as connection:
        connection.execute("CREATE TABLE reports(payload JSON)")
        connection.execute("INSERT INTO reports VALUES (?)", [serialized])
        cached = json.loads(connection.execute("SELECT payload FROM reports").fetchone()[0])
    assert cached == public
    assert normalize_drug_indication_payload(cached["drug_indication"]) == normalize_drug_indication_payload(public["drug_indication"])
