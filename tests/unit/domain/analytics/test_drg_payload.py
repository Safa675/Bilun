"""Unit tests for cached DRG payload normalization."""

from __future__ import annotations

import pytest

from src.bilun.domain.analytics.drg_payload import (
    MISSING_DRG_PRICING_METADATA_REASON,
    normalize_cached_drg_summary_payload,
    normalize_cached_pricing_payload,
    pricing_status_from,
    serialize_drg_summary,
)

pytestmark = pytest.mark.unit


def test_normalize_cached_pricing_payload_backfills_missing_status() -> None:
    normalized = normalize_cached_pricing_payload({"total_drg_cost": 123.4})

    assert normalized["pricing_status"] == "missing_exact_inputs"
    assert normalized["unavailable_reason"] == MISSING_DRG_PRICING_METADATA_REASON
    assert normalized["required_inputs_missing"] == ["pricing_status"]
    assert normalized["total_drg_cost"] == 123.4


def test_normalize_cached_drg_summary_payload_normalizes_nested_episodes() -> None:
    normalized = normalize_cached_drg_summary_payload(
        {
            "total_drg_cost": 50.0,
            "episodes": [
                {"episode_id": "E1", "total_cost": 50.0},
                "not-a-mapping",
            ],
        }
    )

    assert normalized["pricing_status"] == "missing_exact_inputs"
    assert normalized["episodes"][0]["pricing_status"] == "missing_exact_inputs"
    assert normalized["episodes"][0]["required_inputs_missing"] == ["pricing_status"]
    assert normalized["episodes"][1] == "not-a-mapping"


def test_normalize_cached_drg_summary_payload_preserves_explicit_exact_status() -> None:
    payload = {
        "total_drg_cost": 123.4,
        "pricing_status": "exact",
        "required_inputs_missing": [],
        "episodes": [
            {
                "episode_id": "E1",
                "pricing_status": "exact",
                "required_inputs_missing": [],
            }
        ],
    }

    normalized = normalize_cached_drg_summary_payload(payload)

    assert normalized == payload


def test_normalize_cached_drg_summary_payload_passthrough_non_mapping() -> None:
    assert normalize_cached_drg_summary_payload(None) is None
    assert normalize_cached_drg_summary_payload("raw") == "raw"


def test_pricing_status_from_dataclass_like_object() -> None:
    class _Episode:
        pricing_status = "unknown_date"
        unavailable_reason = "Missing admission date."
        required_inputs_missing = ["admission_date"]

    status, reason, missing = pricing_status_from(_Episode())

    assert status == "unknown_date"
    assert reason == "Missing admission date."
    assert missing == ["admission_date"]


def test_pricing_status_from_missing_metadata() -> None:
    status, reason, missing = pricing_status_from(object())

    assert status == "missing_exact_inputs"
    assert reason == MISSING_DRG_PRICING_METADATA_REASON
    assert missing == ["pricing_status"]


def test_serialize_drg_summary_matches_api_schema() -> None:
    from src.bilun.api.schemas import DRGSummaryResponse
    from src.bilun.domain.analytics.drg import DRGEpisode, DRGSummary

    summary = DRGSummary(
        patient_id="P1",
        n_episodes=1,
        episodes=[
            DRGEpisode(
                episode_id="E1",
                claim_id="C1",
                primary_icd10="J18.9",
                primary_icd10_chapter="X",
                description="Pneumonia",
                los_days=3.0,
                lab_cost=10.0,
                visit_cost=0.0,
                rx_cost=0.0,
                procedure_cost=100.0,
                total_cost=110.0,
                drg_package_price=500.0,
                package_code="PK1",
                ek2c_group="G1",
                admission_date="2024-01-01",
                discharge_date="2024-01-04",
                pricing_status="exact",
                pricing_date="2024-01-01",
            )
        ],
        total_drg_cost=110.0,
        mean_episode_cost=110.0,
        most_expensive_drg="Pneumonia",
        dominant_icd10_chapter="X",
        total_drg_package_price=500.0,
        fully_priced=True,
        priced_episode_count=1,
        unknown_date_episode_count=0,
        pricing_status="exact",
    )

    parsed = DRGSummaryResponse.model_validate(serialize_drg_summary(summary))

    assert parsed.pricing_status == "exact"
    assert parsed.n_episodes == 1
    assert parsed.episodes[0].claim_id == "C1"


def test_serialize_drg_summary_round_trip_from_claim_dataset() -> None:
    from src.bilun.api.schemas import DRGSummaryResponse
    from src.bilun.domain.analytics import compute_drg_summary, serialize_drg_summary
    from src.bilun.domain.claims.loader import load_sut_claim_dataset

    dataset = load_sut_claim_dataset()
    drg = compute_drg_summary(
        "SENTETIK-HASTA-0001",
        None,
        claim_dataset=dataset,
    )

    parsed = DRGSummaryResponse.model_validate(serialize_drg_summary(drg))

    assert parsed.pricing_status in {"exact", "partial_exact", "missing_exact_inputs", "unknown_date"}
    assert parsed.n_episodes == drg.n_episodes
