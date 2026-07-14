"""Direct tests for report_exactness rollup.

Audit finding #16: finalize_report_exactness and finalize_summary_exactness
had ZERO direct tests. These cover the 3-branch rollup (exact / partial /
missing_inputs) and the class-name fallback branch.
"""

from __future__ import annotations

import pytest

from src.bilun.domain.billing.report_exactness import (
    block_exactness_status,
    finalize_report_exactness,
)
from src.bilun.domain.billing.types import (
    BillingActionReport,
    EXACTNESS_STATUS_EXACT,
    EXACTNESS_STATUS_MISSING_INPUTS,
    EXACTNESS_STATUS_NOT_APPLICABLE,
    EXACTNESS_STATUS_PARTIAL,
)
from src.bilun.domain.billing.block_registry import BILLING_BLOCK_SPECS


pytestmark = pytest.mark.unit


def _set_all_blocks(report: BillingActionReport, status: str) -> None:
    """Set every billing block to the given exactness status."""
    for spec in BILLING_BLOCK_SPECS:
        block = getattr(report, spec.attr)
        block.exactness_status = status


def test_all_blocks_exact_yields_exact() -> None:
    """When every block is EXACT, the report should be EXACT."""
    report = BillingActionReport()
    _set_all_blocks(report, EXACTNESS_STATUS_EXACT)
    finalize_report_exactness(report)
    assert report.exactness_status == EXACTNESS_STATUS_EXACT


def test_all_blocks_missing_inputs_yields_missing_inputs() -> None:
    """When every block is MISSING_INPUTS, the report should be MISSING_INPUTS."""
    report = BillingActionReport()
    _set_all_blocks(report, EXACTNESS_STATUS_MISSING_INPUTS)
    for spec in BILLING_BLOCK_SPECS:
        block = getattr(report, spec.attr)
        block.required_inputs_missing = ["test_input"]
    finalize_report_exactness(report)
    assert report.exactness_status == EXACTNESS_STATUS_MISSING_INPUTS
    assert len(report.required_inputs_missing) > 0


def test_mixed_exact_and_partial_yields_partial() -> None:
    """When some blocks are EXACT and some PARTIAL, the report should be PARTIAL."""
    report = BillingActionReport()
    _set_all_blocks(report, EXACTNESS_STATUS_EXACT)
    report.copay.exactness_status = EXACTNESS_STATUS_PARTIAL
    report.copay.required_inputs_missing = ["copay_rate"]
    finalize_report_exactness(report)
    assert report.exactness_status == EXACTNESS_STATUS_PARTIAL


def test_not_applicable_blocks_do_not_downgrade() -> None:
    """NOT_APPLICABLE blocks should not downgrade the report."""
    report = BillingActionReport()
    _set_all_blocks(report, EXACTNESS_STATUS_EXACT)
    report.copay.exactness_status = EXACTNESS_STATUS_NOT_APPLICABLE
    finalize_report_exactness(report)
    assert report.exactness_status == EXACTNESS_STATUS_EXACT


def test_block_exactness_status_reflects_block_field() -> None:
    """block_exactness_status reads the block's exactness_status field."""
    report = BillingActionReport()
    report.lab.exactness_status = EXACTNESS_STATUS_PARTIAL
    assert block_exactness_status(report.lab) == EXACTNESS_STATUS_PARTIAL
