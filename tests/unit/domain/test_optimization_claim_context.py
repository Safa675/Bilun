"""Exact claim-line wiring for SUT surcharge and copay-rate optimization."""

from __future__ import annotations

from decimal import Decimal

import pytest

from src.bilun.domain.claims import load_sut_claim_dataset
from src.bilun.domain.optimization.claim_context import (
    build_copay_rate_claim_context,
    build_surcharge_claim_context,
)
from src.bilun.domain.optimization.copay_rates import analyze_copay_rate_exposure
from src.bilun.domain.optimization.runtime_claim_context import ClaimContextManager
from src.bilun.domain.optimization.surcharge import analyze_surcharge_exposure
from tests.fixtures.synthetic_cohort import patient_ids
from tests.fixtures.t2_catalog_lines import (
    ek2c1_only_code,
    ek2g_only_code,
    procedure_line,
    unlisted_code,
)

pytestmark = pytest.mark.unit


def test_surcharge_exposure_uses_exact_claim_context() -> None:
    """A line on the EK-2G list is applicable, any other line only counts towards the total.

    The showcase cohort has no line on the EK-2G list, so the lines are built here.
    """
    listed = procedure_line(ek2g_only_code(), line_id="L1", day=15)
    other = procedure_line(unlisted_code(), line_id="L2", day=16, surcharge_flag=True)
    context = build_surcharge_claim_context("P-T2", [listed, other])
    assert context is not None

    with ClaimContextManager(surcharge=context):
        result = analyze_surcharge_exposure(set())

    assert result["exactness_status"] == "exact"
    assert result["n_applicable_procedures"] == 1
    assert result["n_total_ek2g"] == 2
    assert result["exposure_rate"] == 0.5
    assert result["n_flag_catalog_mismatches"] == 0
    assert [rule["code"] for rule in result["applicable_rules"]] == [listed.procedure_code]


def test_copay_rate_exposure_uses_exact_claim_context() -> None:
    """Lines on the EK-2C-1 list are applicable, and only a rate off the mandated one is a violation.

    The showcase cohort has no line on the EK-2C-1 list, so the lines are built here.
    """
    code, mandated = ek2c1_only_code()
    compliant = procedure_line(
        code, line_id="L1", day=15, payable=str(Decimal("100.00") - mandated)
    )
    violating = procedure_line(code, line_id="L2", day=16, payable="100.00")  # implied copay 0%
    other = procedure_line(unlisted_code(), line_id="L3", day=17)
    context = build_copay_rate_claim_context("P-T2", [compliant, violating, other])
    assert context is not None

    with ClaimContextManager(copay_rate=context):
        result = analyze_copay_rate_exposure(set())

    assert result["exactness_status"] == "exact"
    assert result["n_applicable_procedures"] == 2
    assert result["n_total_ek2c1"] == 3
    assert result["n_flag_catalog_mismatches"] == 0
    assert result["n_rate_catalog_mismatches"] == 1
    assert result["n_violations"] == 1
    assert result["mean_rate"] == float(mandated / 2)  # (mandated rate + 0%) / 2 lines
    assert [row["code"] for row in result["rate_catalog_mismatches"]] == [code]


def test_cohort_claim_lines_feed_exact_contexts() -> None:
    """The loaded lines of every cohort patient become exact contexts that cover all of them."""
    dataset = load_sut_claim_dataset()

    for patient_id in patient_ids():
        lines = dataset.procedure_lines_by_patient[patient_id]
        surcharge_context = build_surcharge_claim_context(patient_id, lines)
        copay_rate_context = build_copay_rate_claim_context(patient_id, lines)
        assert surcharge_context is not None and copay_rate_context is not None

        with ClaimContextManager(surcharge=surcharge_context, copay_rate=copay_rate_context):
            surcharge = analyze_surcharge_exposure(set())
            copay_rate = analyze_copay_rate_exposure(set())

        assert surcharge["exactness_status"] == "exact", patient_id
        assert copay_rate["exactness_status"] == "exact", patient_id
        assert surcharge["n_total_ek2g"] == len(lines), patient_id
        assert copay_rate["n_total_ek2c1"] == len(lines), patient_id


def test_surcharge_exposure_without_context_is_unavailable() -> None:
    result = analyze_surcharge_exposure(set())
    assert result["exactness_status"] == "missing_exact_inputs"
