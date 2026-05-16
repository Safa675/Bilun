from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.api.schemas.patients import PatientOutcomeResponse
from src.bilun.api.schemas import (
    BillingReportResponse,
    SUTDataSourceMetadata,
    SutCachePayloadResponse,
    SutPatientOutcomeResponse,
)

pytestmark = pytest.mark.unit

SYNTHETIC_DATA_SOURCE = {
    "mode": "synthetic_demo",
    "label": "Synthetic SUT demo claim data",
    "claim_source": "data/synthetic/sut/claims",
    "clinical_source": "data/synthetic/sut/clean",
    "is_synthetic": True,
    "notice": "Demo data only. Rule calculations are exact for these synthetic claim lines.",
}


def test_sut_patient_outcome_schema_requires_drg_pricing_status() -> None:
    payload = {
        "patient_id": "P1",
        "drg_summary": {"total_drg_cost": 123.4},
        "expensive_analytics": {"state": "ready", "included": True},
    }

    with pytest.raises(ValidationError):
        SutPatientOutcomeResponse.model_validate(payload)


def test_sut_data_source_schema_preserves_synthetic_demo_metadata() -> None:
    parsed = SUTDataSourceMetadata.model_validate(SYNTHETIC_DATA_SOURCE)

    assert parsed.mode == "synthetic_demo"
    assert parsed.is_synthetic is True
    assert parsed.claim_source == "data/synthetic/sut/claims"


def test_sut_cache_schema_defaults_missing_provenance_to_unavailable_not_real() -> None:
    parsed = SutCachePayloadResponse.model_validate({"total": 1})

    assert parsed.data_source.mode == "unavailable"
    assert parsed.data_source.is_synthetic is None
    assert parsed.data_source.required_inputs_missing == ["data_source"]


def test_patient_outcome_schema_requires_drg_pricing_status() -> None:
    payload = {
        "drg_summary": {"total_drg_cost": 123.4},
        "expensive_analytics": {"state": "ready", "included": True},
    }

    with pytest.raises(ValidationError):
        PatientOutcomeResponse.model_validate(payload)


def test_sut_patient_outcome_schema_preserves_explicit_exact_drg_status() -> None:
    payload = {
        "patient_id": "P1",
        "drg_summary": {
            "total_drg_cost": 123.4,
            "pricing_status": "exact",
        },
        "expensive_analytics": {"state": "ready", "included": True},
    }

    parsed = SutPatientOutcomeResponse.model_validate(payload)

    assert parsed.drg_summary is not None
    assert parsed.drg_summary.pricing_status == "exact"
    assert parsed.drg_summary.required_inputs_missing == []
    assert parsed.expensive_analytics.state == "ready"


def test_sut_patient_outcome_schema_preserves_unavailable_drg_status() -> None:
    payload = {
        "patient_id": "P1",
        "drg_summary": {
            "total_drg_cost": 0.0,
            "pricing_status": "unknown_date",
            "unavailable_reason": "Missing admission date.",
            "required_inputs_missing": ["admission_date"],
            "episodes": [
                {
                    "episode_id": 1,
                    "pricing_status": "unknown_date",
                    "unavailable_reason": "Missing admission date.",
                    "required_inputs_missing": ["admission_date"],
                }
            ],
        },
    }

    parsed = SutPatientOutcomeResponse.model_validate(payload)

    assert parsed.drg_summary is not None
    assert parsed.drg_summary.pricing_status == "unknown_date"
    assert parsed.drg_summary.required_inputs_missing == ["admission_date"]
    assert parsed.drg_summary.episodes[0].pricing_status == "unknown_date"


def test_sut_patient_outcome_schema_rejects_unavailable_drg_without_inputs() -> None:
    payload = {
        "patient_id": "P1",
        "drg_summary": {
            "total_drg_cost": 0.0,
            "pricing_status": "unknown_date",
            "episodes": [
                {
                    "episode_id": 1,
                    "pricing_status": "unknown_date",
                    "required_inputs_missing": ["admission_date"],
                }
            ],
        },
    }

    with pytest.raises(ValidationError):
        SutPatientOutcomeResponse.model_validate(payload)


def test_billing_report_schema_missing_exactness_defaults_to_unavailable() -> None:
    payload = {
        "patient_id": "P1",
        "billing_strategy": {"recommendations": []},
        "total_recoverable_try": 12.5,
    }

    parsed = BillingReportResponse.model_validate(payload)

    assert parsed.exactness_status == "missing_exact_inputs"
    assert parsed.unavailable_reason == "Exactness metadata was not provided by the SUT payload."
    assert parsed.required_inputs_missing == ["exactness_status"]
    assert parsed.billing_strategy.exactness_status == "missing_exact_inputs"
    assert parsed.billing_strategy.required_inputs_missing == ["exactness_status"]


def test_billing_report_schema_preserves_explicit_exact_status() -> None:
    payload = {
        "patient_id": "P1",
        "billing_strategy": {
            "recommendations": [],
            "exactness_status": "exact",
        },
        "total_recoverable_try": 12.5,
        "exactness_status": "exact",
    }

    parsed = BillingReportResponse.model_validate(payload)

    assert parsed.exactness_status == "exact"
    assert parsed.unavailable_reason is None
    assert parsed.required_inputs_missing == []
    assert parsed.billing_strategy.exactness_status == "exact"
    assert parsed.billing_strategy.required_inputs_missing == []


def test_billing_report_schema_rejects_explicit_unavailable_without_inputs() -> None:
    payload = {
        "patient_id": "P1",
        "billing_strategy": {
            "recommendations": [],
            "exactness_status": "missing_exact_inputs",
        },
        "total_recoverable_try": 12.5,
        "exactness_status": "partial_exact",
        "required_inputs_missing": ["itemized_billed_procedure_lines"],
    }

    with pytest.raises(ValidationError):
        BillingReportResponse.model_validate(payload)
