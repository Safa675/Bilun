"""Real HTTP validation with mutable clinical facts and the production cache path."""

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from src.bilun.api.routes import validation
from src.bilun.domain.billing import engine
from src.bilun.domain.prose_rules import drug_indication as prose, gap_closing
from tests.unit.api.test_prior_therapy_outcome_api import (
    _assert_unpriced_public,
    _request,
    source_rules as source_rules,
)


pytestmark = pytest.mark.unit


def _client():
    app = FastAPI()
    app.include_router(validation.router, prefix="/api")
    return TestClient(app)


def _observe_evaluations(monkeypatch):
    observed = []
    evaluate = engine.evaluate_drug_indication_findings

    def capture(*args, **kwargs):
        batch = evaluate(*args, **kwargs)
        observed.append(batch)
        return batch

    monkeypatch.setattr(engine, "evaluate_drug_indication_findings", capture)
    return observed


@pytest.fixture
def real_endpoint(monkeypatch, source_rules):
    # Isolate source semantics while every context-builder alias retains the
    # production wrapper; neither cache keys nor builder results are patched.
    monkeypatch.setattr(prose, "list_drug_indication_rules", lambda: source_rules)
    observed = _observe_evaluations(monkeypatch)
    gap_closing._build_gap_closing_context.cache_clear()
    with _client() as client:
        yield client, observed
    gap_closing._build_gap_closing_context.cache_clear()


@pytest.mark.parametrize("prior,kind", [
    ([{"drug_or_class": "imatinib"}], "needs_prior_therapy_verification"),
    ([{"drug_or_class": "imatinib", "outcome": "unknown"}], "needs_prior_therapy_verification"),
    ([{"drug_or_class": "imatinib", "outcome": "responsive"}], "prior_therapy_mismatch"),
    ([{"drug_or_class": "nilotinib", "outcome": "resistant"}], "prior_therapy_mismatch"),
    ([{"drug_or_class": "imatinib", "outcome": "resistant"}], None),
    ([{"drug_or_class": "imatinib", "outcome": "intolerant"}], None),
])
def test_http_uses_production_cache_path_for_nested_clinical_dicts(real_endpoint, source_rules, prior, kind):
    client, observed = real_endpoint
    response = client.post(
        "/api/validate-claim", json=_request(source_rules, prior),
        headers={"X-Bilun-Validation-Contract": "2"},
    )
    assert response.status_code == 200, response.text
    batch, = observed
    assert batch.evaluations[0].selected_rule_id == source_rules[0]["rule_id"]
    assert [row.finding_kind for row in batch.findings] == ([kind] if kind else [])
    payload = response.json()
    advisories = [row for row in payload["advisories"] if row["rule"] == "drug_indication"]
    if kind:
        advisory, = advisories
        assert advisory["disposition"] == "review_only"
        assert advisory["clinical_eligibility_complete"] is False
        assert advisory["clinical_restrictions"][0]["source_refs"] == source_rules[0]["gate_b_sources"]
    else:
        assert advisories == []
    assert payload["violations"] == []
    assert all(row.get("clinical_eligibility_complete") is not True for row in payload["advisories"])
    _assert_unpriced_public(payload)


def test_http_repeated_different_outcomes_cannot_reuse_stale_context(real_endpoint, source_rules):
    client, observed = real_endpoint
    for index, (outcome, kind) in enumerate((
        ("unknown", "needs_prior_therapy_verification"),
        ("resistant", None),
        ("responsive", "prior_therapy_mismatch"),
        ("intolerant", None),
    )):
        response = client.post(
            "/api/validate-claim",
            json=_request(source_rules, [{"drug_or_class": "imatinib", "outcome": outcome}]),
            headers={"X-Bilun-Validation-Contract": "2"},
        )
        assert response.status_code == 200, response.text
        assert len(observed) == index + 1
        assert observed[-1].evaluations[0].selected_rule_id == source_rules[0]["rule_id"]
        assert [row.finding_kind for row in observed[-1].findings] == ([kind] if kind else [])
        advisories = [row for row in response.json()["advisories"] if row["rule"] == "drug_indication"]
        assert len(advisories) == (1 if kind else 0)
        _assert_unpriced_public(response.json())


def test_http_full_corpus_reaches_existing_route_without_cache_bypass(monkeypatch, source_rules):
    # No loader patch here: preserve full-corpus route arbitration and its honest
    # limits instead of asserting that a broad imatinib condition must win.
    observed = _observe_evaluations(monkeypatch)
    with _client() as client:
        response = client.post(
            "/api/validate-claim", json=_request(source_rules, [{"drug_or_class": "imatinib"}]),
            headers={"X-Bilun-Validation-Contract": "2"},
        )
    assert response.status_code == 200, response.text
    batch, = observed
    evaluation, = batch.evaluations
    assert evaluation.drug_claim_line_id
    assert evaluation.to_dict()["evaluation_status"]
    payload = response.json()
    assert all(row.get("clinical_eligibility_complete") is not True for row in payload["advisories"])
    _assert_unpriced_public(payload)
