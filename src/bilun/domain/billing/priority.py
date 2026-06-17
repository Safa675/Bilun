"""Priority tiering for billing action reports."""

from __future__ import annotations

from .types import BillingActionReport


def assign_priority_by_percentile(reports: list[BillingActionReport]) -> None:
    """Tier reports high/medium/low by sgk_uplift percentile (in place)."""
    recoverables = sorted(r.sgk_uplift_try for r in reports if r.sgk_uplift_try > 0)
    if not recoverables:
        return
    n = len(recoverables)
    p75 = recoverables[min(n - 1, int(n * 0.75))]
    p50 = recoverables[min(n - 1, int(n * 0.50))]
    for report in reports:
        opportunity = report.sgk_uplift_try
        if opportunity >= p75:
            report.priority = "high"
        elif opportunity >= p50:
            report.priority = "medium"
        else:
            report.priority = "low"
