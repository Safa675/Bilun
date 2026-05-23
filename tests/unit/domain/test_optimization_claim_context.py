"""Exact claim-line wiring for SUT surcharge and copay-rate optimization."""

from __future__ import annotations

import pytest

from src.bilun.domain.claims import load_sut_claim_dataset
from src.bilun.domain.optimization.claim_context import (
    build_copay_rate_claim_context,
    build_surcharge_claim_context,
)
from src.bilun.domain.optimization.copay_rates import analyze_copay_rate_exposure
from src.bilun.domain.optimization.runtime_claim_context import ClaimContextManager
from src.bilun.domain.optimization.surcharge import analyze_surcharge_exposure

pytestmark = pytest.mark.unit


def test_surcharge_exposure_uses_exact_claim_context() -> None:
    dataset = load_sut_claim_dataset()
    patient_id = "SENTETIK-HASTA-0003"
    procedure_lines = dataset.procedure_lines_by_patient[patient_id]
    context = build_surcharge_claim_context(patient_id, procedure_lines)

    with ClaimContextManager(surcharge=context):
        result = analyze_surcharge_exposure(set())

    assert result["exactness_status"] == "exact"
    assert result["n_applicable_procedures"] >= 1
    assert result["n_total_ek2g"] >= 1
    assert result["exposure_rate"] >= 0.0


def test_copay_rate_exposure_uses_exact_claim_context() -> None:
    dataset = load_sut_claim_dataset()
    patient_id = "SENTETIK-HASTA-0001"
    procedure_lines = dataset.procedure_lines_by_patient[patient_id]
    context = build_copay_rate_claim_context(patient_id, procedure_lines)

    with ClaimContextManager(copay_rate=context):
        result = analyze_copay_rate_exposure(set())

    assert result["exactness_status"] == "exact"
    assert result["n_applicable_procedures"] >= 1
    assert result["n_total_ek2c1"] >= 1
    assert result["mean_rate"] >= 0.0


def test_surcharge_exposure_without_context_is_unavailable() -> None:
    result = analyze_surcharge_exposure(set())
    assert result["exactness_status"] == "missing_exact_inputs"
