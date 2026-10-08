from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.bilun.api.schemas import (
    BILUNDataSourceMetadata,
    BilunCachePayloadResponse,
    BilunPatientOutcomeResponse,
    BillingReportResponse,
)
from src.bilun.api import schemas

pytestmark = pytest.mark.unit

SYNTHETIC_DATA_SOURCE = {
    "mode": "synthetic_demo",
    "label": "Synthetic SUT demo claim data",
    "claim_source": "data/synthetic/sut/claims",
    "clinical_source": "data/synthetic/sut/clean",
    "is_synthetic": True,
    "notice": "Demo data only. Rule calculations are exact for these synthetic claim lines.",
}


def test_bilun_patient_outcome_schema_requires_patient_id() -> None:
    with pytest.raises(ValidationError):
        BilunPatientOutcomeResponse.model_validate({})


def test_bilun_patient_outcome_schema_accepts_minimal_payload() -> None:
    parsed = BilunPatientOutcomeResponse.model_validate({"patient_id": "P1"})

    assert parsed.patient_id == "P1"
    assert parsed.data_source.mode == "unavailable"


def test_sut_data_source_schema_preserves_synthetic_demo_metadata() -> None:
    parsed = BILUNDataSourceMetadata.model_validate(SYNTHETIC_DATA_SOURCE)

    assert parsed.mode == "synthetic_demo"
    assert parsed.is_synthetic is True
    assert parsed.claim_source == "data/synthetic/sut/claims"


def test_sut_cache_schema_defaults_missing_provenance_to_unavailable_not_real() -> None:
    parsed = BilunCachePayloadResponse.model_validate({"total": 1})

    assert parsed.data_source.mode == "unavailable"
    assert parsed.data_source.is_synthetic is None
    assert parsed.data_source.required_inputs_missing == ["data_source"]


def test_billing_report_schema_missing_exactness_defaults_to_unavailable() -> None:
    payload = {
        "patient_id": "P1",
        "billing_strategy": {"recommendations": []},
        "total_recoverable_try": 12.5,
    }

    parsed = BillingReportResponse.model_validate(payload)

    assert parsed.exactness_status == "missing_exact_inputs"
    assert parsed.unavailable_reason == "Exactness metadata was not provided by the bilun payload."
    assert parsed.required_inputs_missing == ["exactness_status"]
    assert parsed.billing_strategy.exactness_status == "missing_exact_inputs"
    assert parsed.billing_strategy.required_inputs_missing == ["exactness_status"]


@pytest.mark.parametrize(
    "model,fields",
    [
        (
            schemas.LabOptimizationResponse,
            ("normative_cost_try", "hemogram_bundling_savings", "session_fraction_savings"),
        ),
        (
            schemas.CopayOptimizationResponse,
            (
                "visit_copay_savings_try",
                "rx_copay_savings_try",
                "total_copay_savings_try",
                "patient_copay_waived_total_try",
                "patient_copay_try",
                "ilave_ucret_total_try",
            ),
        ),
        (schemas.BillingStrategyResponse, ("uplift_savings_try", "optional_override_uplift_try")),
        (
            schemas.SessionPricingUpliftResponse,
            ("total_uplift_try", "confirmed_uplift_try", "review_uplift_try"),
        ),
        (schemas.DrgUpliftRecommendationResponse, ("total_uplift_try", "confirmed_uplift_try")),
        (schemas.BloodComponentUpliftResponse, ("total_uplift_try", "confirmed_uplift_try")),
        (schemas.MaterialUpliftResponse, ("total_uplift_try", "confirmed_uplift_try")),
        (schemas.ProcedureAddonUpliftResponse, ("total_uplift_try", "confirmed_uplift_try")),
        (
            schemas.CareSettingReviewResponse,
            ("total_uplift_try", "confirmed_uplift_try", "review_uplift_try"),
        ),
        (schemas.ProcedureCaptureGapResponse, ("total_gap_try", "confirmed_gap_try")),
        (
            schemas.DrgPackageAdequacyReviewResponse,
            ("total_uplift_try", "confirmed_uplift_try", "review_uplift_try"),
        ),
        (
            schemas.BillingReportResponse,
            (
                "sgk_uplift_try",
                "compliance_adjustment_try",
                "audit_exposure_try",
                "capture_gap_try",
                "package_adequacy_review_try",
                "total_recoverable_try",
            ),
        ),
    ],
)
def test_uncomputed_money_defaults_are_null_and_explicit_zero_survives(model, fields) -> None:
    missing = model.model_validate({}).model_dump(mode="json")
    zero = model.model_validate({field: 0.0 for field in fields}).model_dump(mode="json")
    explicit_null = model.model_validate({field: None for field in fields}).model_dump(mode="json")
    for field in fields:
        assert missing[field] is None
        assert explicit_null[field] is None
        assert zero[field] == 0.0


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


def test_billing_report_schema_populates_missing_inputs_for_partial_exact() -> None:
    payload = {
        "patient_id": "P1",
        "billing_strategy": {
            "recommendations": [],
            "exactness_status": "missing_exact_inputs",
        },
        "total_recoverable_try": 12.5,
        "exactness_status": "partial_exact",
        "required_inputs_missing": [],
    }

    parsed = BillingReportResponse.model_validate(payload)
    assert parsed.exactness_status == "partial_exact"
    assert parsed.required_inputs_missing == ["exactness_status"]
    assert parsed.unavailable_reason == "Exactness metadata was not provided by the bilun payload."
