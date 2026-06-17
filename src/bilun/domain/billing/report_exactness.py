"""Exactness rollup for billing reports and cohort summaries."""

from __future__ import annotations

from typing import Any

from .block_registry import BILLING_BLOCK_SPECS, BillingBlockSpec
from .types import (
    BILLING_REPORT_PARTIAL_REASON,
    COHORT_RECOVERY_PARTIAL_REASON,
    EXACTNESS_STATUS_EXACT,
    EXACTNESS_STATUS_MISSING_INPUTS,
    EXACTNESS_STATUS_NOT_APPLICABLE,
    EXACTNESS_STATUS_PARTIAL,
    BillingActionReport,
    CohortRecoverySummary,
)


def block_exactness_status(block: Any) -> str:
    status = str(
        getattr(block, "exactness_status", EXACTNESS_STATUS_MISSING_INPUTS) or ""
    ).strip()
    return status or EXACTNESS_STATUS_MISSING_INPUTS


def iter_report_blocks(report: BillingActionReport) -> list[Any]:
    return [getattr(report, spec.attr) for spec in BILLING_BLOCK_SPECS]


def collect_required_inputs(blocks: list[Any]) -> list[str]:
    ordered: list[str] = []
    for block in blocks:
        for name in getattr(block, "required_inputs_missing", []) or []:
            if name not in ordered:
                ordered.append(name)
    return ordered


def _mark_block_missing_inputs(block: Any, spec: BillingBlockSpec) -> None:
    block.exactness_status = EXACTNESS_STATUS_MISSING_INPUTS
    block.unavailable_reason = spec.unavailable_reason
    block.required_inputs_missing = list(spec.required_inputs)


def set_missing_inputs_report(report: BillingActionReport) -> None:
    """Mark every billing block as missing exact inputs when claim context is absent.

    No heuristic ₺ amounts are produced. The report shape is preserved so the
    frontend can still render empty sections.
    """
    for spec in BILLING_BLOCK_SPECS:
        _mark_block_missing_inputs(getattr(report, spec.attr), spec)


def finalize_report_exactness(report: BillingActionReport) -> None:
    blocks = iter_report_blocks(report)
    non_exact_blocks = [
        block
        for block in blocks
        if block_exactness_status(block)
        not in (EXACTNESS_STATUS_EXACT, EXACTNESS_STATUS_NOT_APPLICABLE)
    ]
    if not non_exact_blocks:
        report.exactness_status = EXACTNESS_STATUS_EXACT
        report.unavailable_reason = None
        report.required_inputs_missing = []
        return

    if all(
        block_exactness_status(block) == EXACTNESS_STATUS_MISSING_INPUTS
        for block in non_exact_blocks
    ):
        report.exactness_status = EXACTNESS_STATUS_MISSING_INPUTS
        report.unavailable_reason = getattr(
            non_exact_blocks[0], "unavailable_reason", None
        )
        report.required_inputs_missing = collect_required_inputs(non_exact_blocks)
        return

    report.exactness_status = EXACTNESS_STATUS_PARTIAL
    report.unavailable_reason = BILLING_REPORT_PARTIAL_REASON
    report.required_inputs_missing = collect_required_inputs(non_exact_blocks)
    if not report.required_inputs_missing:
        report.required_inputs_missing = [
            f"{getattr(block, '__class__', type(block)).__name__}.required_inputs_missing"
            for block in non_exact_blocks
        ]


def finalize_summary_exactness(
    summary: CohortRecoverySummary,
    reports: dict[str, BillingActionReport],
) -> None:
    non_exact_reports = [
        report
        for report in reports.values()
        if block_exactness_status(report) != EXACTNESS_STATUS_EXACT
    ]
    if not non_exact_reports:
        summary.exactness_status = EXACTNESS_STATUS_EXACT
        summary.unavailable_reason = None
        summary.required_inputs_missing = []
        return

    if all(
        block_exactness_status(report) == EXACTNESS_STATUS_MISSING_INPUTS
        for report in non_exact_reports
    ):
        summary.exactness_status = EXACTNESS_STATUS_MISSING_INPUTS
        summary.unavailable_reason = getattr(
            non_exact_reports[0], "unavailable_reason", None
        )
        summary.required_inputs_missing = collect_required_inputs(non_exact_reports)
        return

    summary.exactness_status = EXACTNESS_STATUS_PARTIAL
    summary.unavailable_reason = COHORT_RECOVERY_PARTIAL_REASON
    summary.required_inputs_missing = collect_required_inputs(non_exact_reports)
    if not summary.required_inputs_missing:
        summary.required_inputs_missing = ["cohort_billing_report.required_inputs_missing"]
