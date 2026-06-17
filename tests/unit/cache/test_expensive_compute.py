"""Unit tests for expensive analytics cache compute."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from src.bilun.cache.expensive_compute import (
    ExpensiveComputeContext,
    compute_patient_expensive_sections,
    should_skip_drg_backfill,
)
from src.bilun.domain.claims.loader import load_sut_claim_dataset

pytestmark = pytest.mark.unit


def test_should_not_skip_drg_backfill_for_exact_claim_line_payload() -> None:
    assert not should_skip_drg_backfill(
        {
            "source": "claim_lines",
            "exactness_status": "exact",
        }
    )


def test_should_skip_drg_backfill_for_missing_exact_inputs() -> None:
    assert should_skip_drg_backfill(
        {
            "source": "claim_lines",
            "exactness_status": "missing_exact_inputs",
        }
    )


def test_should_not_skip_legacy_heuristic_sut_estimate() -> None:
    assert not should_skip_drg_backfill({"total_try": 100.0})


def test_expensive_compute_context_from_backfill_context() -> None:
    dataset = load_sut_claim_dataset()
    ctx = ExpensiveComputeContext.from_backfill_context({"sut_claim_dataset": dataset})

    assert ctx.sut_claim_dataset is dataset


def test_compute_patient_expensive_sections_returns_drg_summary() -> None:
    dataset = load_sut_claim_dataset()
    ctx = ExpensiveComputeContext(sut_claim_dataset=dataset)

    payload, completed = compute_patient_expensive_sections(
        patient_id="SENTETIK-HASTA-0001",
        sut_estimate={"legacy": True},
        ctx=ctx,
        timeout_ms=5000,
    )

    assert completed is True
    assert payload.drg_summary is not None
    assert payload.drg_summary["pricing_status"] in {
        "exact",
        "partial_exact",
        "missing_exact_inputs",
        "unknown_date",
    }
    assert payload.consistency_warnings == ()


def test_compute_patient_expensive_sections_with_claim_dataset_only() -> None:
    dataset = load_sut_claim_dataset()
    ctx = ExpensiveComputeContext(sut_claim_dataset=dataset)

    payload, completed = compute_patient_expensive_sections(
        patient_id="SENTETIK-HASTA-0001",
        sut_estimate=None,
        ctx=ctx,
        timeout_ms=5000,
    )

    assert completed is True
    assert payload.drg_summary is not None


def test_compute_patient_expensive_sections_respects_timeout_budget() -> None:
    dataset = load_sut_claim_dataset()
    ctx = ExpensiveComputeContext(sut_claim_dataset=dataset)

    with patch(
        "src.bilun.cache.expensive_compute.time.perf_counter",
        side_effect=[0.0, 0.0, 10.0],
    ):
        payload, completed = compute_patient_expensive_sections(
            patient_id="SENTETIK-HASTA-0001",
            sut_estimate={"legacy": True},
            ctx=ctx,
            timeout_ms=1,
        )

    assert completed is False
