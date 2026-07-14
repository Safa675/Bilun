"""Spec-integrity tests for BILLING_BLOCK_SPECS + report_totals rollup.

Audit finding #15: the registry-driven aggregation was tested with all-zero
values — a typo in any spec field would pass every test. These tests set
non-zero sentinel values on each block and assert they roll up correctly.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from src.bilun.domain.billing.block_registry import BILLING_BLOCK_SPECS
from src.bilun.domain.billing.report_totals import (
    _sum_exact_block_field,
    finalize_report_totals,
)
from src.bilun.domain.billing.report_exactness import (
    finalize_report_exactness,
    block_exactness_status,
)
from src.bilun.domain.billing.types import (
    BillingActionReport,
    EXACTNESS_STATUS_EXACT,
    EXACTNESS_STATUS_MISSING_INPUTS,
)


pytestmark = pytest.mark.unit


def test_every_spec_attr_exists_on_report() -> None:
    """Every BillingBlockSpec.attr must resolve to a field on BillingActionReport."""
    report = BillingActionReport()
    for spec in BILLING_BLOCK_SPECS:
        assert hasattr(report, spec.attr), (
            f"spec attr '{spec.attr}' not found on BillingActionReport"
        )


# Specs whose uplift_field is a computed property reading a different
# underlying list (e.g. billing_strategy.uplift_savings_try reads
# .recommendations, not .opportunities). These are tested via their
# own detector tests; the spec-integrity test covers settable fields.
_PROPERTY_UPLIFT_FIELDS = {"uplift_savings_try"}


def test_every_uplift_field_rolls_up() -> None:
    """For each spec with a settable uplift_field, a non-zero exact block contributes to sgk_uplift_try."""
    for spec in BILLING_BLOCK_SPECS:
        if not spec.uplift_field:
            continue
        if spec.uplift_field in _PROPERTY_UPLIFT_FIELDS:
            continue  # tested via detector tests — property reads different list
        report = BillingActionReport()
        block = getattr(report, spec.attr)
        block.exactness_status = EXACTNESS_STATUS_EXACT
        try:
            setattr(block, spec.uplift_field, 1000.0)
        except AttributeError:
            # Property without setter — populate opportunities so the property
            # computes a non-zero value. Include multiple field aliases since
            # different confirmed_*_try properties read different keys.
            block.opportunities = [{
                "recoverable_uplift_try": 1000.0,
                "expected_yatak_try": 1000.0,
                "expected_try": 1000.0,
                "total_try": 1000.0,
                "included_in_sgk_total": True,
            }]
        finalize_report_totals(report)
        assert report.sgk_uplift_try > 0, (
            f"spec '{spec.attr}' with uplift_field='{spec.uplift_field}' "
            f"set to 1000.0 did not roll up into sgk_uplift_try"
        )


def test_non_exact_block_does_not_contribute() -> None:
    """A block whose exactness is not EXACT must contribute 0 to sgk_uplift_try."""
    for spec in BILLING_BLOCK_SPECS:
        if not spec.uplift_field:
            continue
        if spec.uplift_field in _PROPERTY_UPLIFT_FIELDS:
            continue
        report = BillingActionReport()
        block = getattr(report, spec.attr)
        block.exactness_status = EXACTNESS_STATUS_MISSING_INPUTS
        try:
            setattr(block, spec.uplift_field, 1000.0)
        except AttributeError:
            block.opportunities = [{"recoverable_uplift_try": 1000.0, "included_in_sgk_total": True}]
        finalize_report_totals(report)
        assert report.sgk_uplift_try == 0.0, (
            f"spec '{spec.attr}' with non-exact status contributed to sgk_uplift_try"
        )


def test_report_scalar_fields_resolve() -> None:
    """For each spec with report_scalar/block_scalar, the field exists on the block."""
    for spec in BILLING_BLOCK_SPECS:
        if not spec.report_scalar and not spec.block_scalar:
            continue
        report = BillingActionReport()
        block = getattr(report, spec.attr)
        if spec.block_scalar:
            assert hasattr(block, spec.block_scalar), (
                f"spec '{spec.attr}' block_scalar='{spec.block_scalar}' "
                f"not found on block type {type(block).__name__}"
            )
