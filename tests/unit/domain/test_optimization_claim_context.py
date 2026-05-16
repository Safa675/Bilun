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
    patient_id = "SENTETIK-HASTA-003"
    context = build_surcharge_claim_context(
        patient_id,
        dataset.procedure_lines_by_patient[patient_id],
    )

    with ClaimContextManager(surcharge=context):
        result = analyze_surcharge_exposure(set())

    assert result["exactness_status"] == "exact"
    assert result["n_applicable_procedures"] == 3
    assert result["n_total_ek2g"] == 3
    assert result["exposure_rate"] == 1.0
    assert [rule["code"] for rule in result["applicable_rules"]] == [
        "510010",
        "550010",
        "P614980",
    ]


def test_copay_rate_exposure_uses_exact_claim_context() -> None:
    dataset = load_sut_claim_dataset()
    patient_id = "SENTETIK-HASTA-001"
    context = build_copay_rate_claim_context(
        patient_id,
        dataset.procedure_lines_by_patient[patient_id],
    )

    with ClaimContextManager(copay_rate=context):
        result = analyze_copay_rate_exposure(set())

    assert result["exactness_status"] == "exact"
    assert result["n_applicable_procedures"] == 3
    assert result["n_total_ek2c1"] == 3
    assert result["mean_rate"] == 100.0
    assert [procedure["code"] for procedure in result["procedures_with_rates"]] == [
        "520030",
        "L107010",
        "L107020",
    ]


def test_claim_context_absence_preserves_unavailable_fallbacks() -> None:
    surcharge = analyze_surcharge_exposure({"C"})
    copay_rate = analyze_copay_rate_exposure({"C"})

    assert surcharge["exactness_status"] == "missing_exact_inputs"
    assert surcharge["n_applicable_procedures"] is None
    assert copay_rate["exactness_status"] == "missing_exact_inputs"
    assert copay_rate["n_applicable_procedures"] is None
