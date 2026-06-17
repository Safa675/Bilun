"""TRY headline totals for billing action reports."""

from __future__ import annotations

from typing import TYPE_CHECKING

from src.bilun.domain.billing.claim_audit_exposure import compute_audit_exposure_from_claims

from .block_registry import BILLING_BLOCK_SPECS
from .report_exactness import block_exactness_status
from .types import EXACTNESS_STATUS_EXACT, BillingActionReport

if TYPE_CHECKING:
    from src.bilun.domain.claims.patient_context import PatientClaimContext


def sum_compliance_adjustment_try(report: BillingActionReport) -> float:
    """Over-billing corrections (e.g. lab hemogram bundling) — not SGK uplift."""
    if block_exactness_status(report.lab) != EXACTNESS_STATUS_EXACT:
        return 0.0
    return round(report.lab.total_savings, 2)


def _sum_exact_block_field(
    report: BillingActionReport,
    attr: str,
    field: str,
) -> float:
    block = getattr(report, attr)
    if block_exactness_status(block) != EXACTNESS_STATUS_EXACT:
        return 0.0
    return float(getattr(block, field))


def sum_sgk_uplift_try(report: BillingActionReport) -> float:
    """Legitimate Kurum ödemesi uplift; excludes compliance lab savings."""
    total = sum(
        _sum_exact_block_field(report, spec.attr, spec.uplift_field)
        for spec in BILLING_BLOCK_SPECS
        if spec.uplift_field
    )
    return round(total, 2)


def _apply_report_scalar(
    report: BillingActionReport,
    *,
    attr: str,
    report_scalar: str,
    block_scalar: str,
    default: float | int,
) -> None:
    block = getattr(report, attr)
    if block_exactness_status(block) == EXACTNESS_STATUS_EXACT:
        value = getattr(block, block_scalar)
        if isinstance(default, int):
            setattr(report, report_scalar, int(value))
        else:
            setattr(report, report_scalar, value)
    else:
        setattr(report, report_scalar, default)


def finalize_report_totals(
    report: BillingActionReport,
    *,
    claim_context: PatientClaimContext | None = None,
) -> None:
    report.compliance_adjustment_try = sum_compliance_adjustment_try(report)
    report.sgk_uplift_try = sum_sgk_uplift_try(report)
    report.total_recoverable_try = report.sgk_uplift_try
    if claim_context is not None and claim_context.procedure_lines:
        report.audit_exposure_try = compute_audit_exposure_from_claims(claim_context)
    else:
        report.audit_exposure_try = 0.0

    for spec in BILLING_BLOCK_SPECS:
        if spec.report_scalar and spec.block_scalar:
            _apply_report_scalar(
                report,
                attr=spec.attr,
                report_scalar=spec.report_scalar,
                block_scalar=spec.block_scalar,
                default=spec.scalar_default,
            )
