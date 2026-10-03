"""Source review stays explicit through the HTTP contract after later-family merges."""

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from src.bilun.api.routes.validation import router


@pytest.fixture
def validation_client():
    app = FastAPI()
    app.include_router(router, prefix="/api")
    with TestClient(app) as client:
        yield client


def _source_guard_row(client, raw):
    response = client.post(
        "/api/validate-claim", json=raw, headers={"X-Bilun-Validation-Contract": "2"}
    )
    assert response.status_code == 200
    public = response.json()
    row = next(item for item in public["advisories"] if item["rule"] == "drug_indication")
    guard = next(
        item for item in row["clinical_restrictions"]
        if item["constraint_set"] == "source_context_clinical_review"
    )
    assert guard["criterion_status"] == "unknown" and guard["checks"] == []
    assert guard["clinical_eligibility_complete"] is False and guard["source_refs"]
    assert row["clinical_eligibility_complete"] is False and row["disposition"] == "review_only"
    assert public["is_valid"] is None and not public["violations"]
    assert "remaining_sut_clinical_criteria" in row["missing_inputs"]
    assert not any(
        key in row for key in ("payable_try", "risk_amount", "savings_try", "recoverable_uplift_try")
    )
    return row


@pytest.mark.parametrize("board_report", [None, False, True])
@pytest.mark.parametrize(
    "service_date,reason",
    [
        (None, "drug_claim_date"),
        ("2024-05-16", "verified_source_for_service_date"),
        ("2026-10-02", None),
        ("2026-10-03", "verified_source_for_service_date"),
    ],
)
def test_mds_source_quarantine_does_not_infer_report_or_temporal_authority(
    validation_client, board_report, service_date, reason
):
    row = _source_guard_row(validation_client, {
        "materials": [{"name": "darbepoetin", "quantity": 1}],
        "drug_context": {
            "service_date": service_date, "primary_icd10": "D46.1",
            "board_report_present": board_report, "report_duration_months": 1,
            "prescriber_specialty": "hematoloji",
        },
    })
    assert row["selected_rule_id"] == "4.2.9.A-2.darbepoetin_mds_source_review"
    if reason is not None:
        assert reason in row["missing_inputs"]


@pytest.mark.parametrize("pediatric", [None, False, True])
def test_adult_source_guard_survives_composed_enteral_evidence(validation_client, pediatric):
    row = _source_guard_row(validation_client, {
        "materials": [{
            "name": "enteral beslenme ürünü", "quantity": 1,
            "enteral_evidence": {"pediatric": pediatric},
        }],
        "drug_context": {
            "service_date": "2026-10-02", "primary_icd10": "E43",
            "board_report_present": True, "report_duration_months": 3,
        },
    })
    assert row["selected_rule_id"] == "4.2.8.A.adult_malnutrition_1200kcal_3mo_report"
    kinds = {item["constraint_set"] for item in row["clinical_restrictions"]}
    if pediatric is not False:
        assert "enteral_pediatric_reports_2026" in kinds
