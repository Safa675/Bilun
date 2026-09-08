"""
src/bilun/domain/billing/orchestrator.py
Thin facade — re-exports billing entry points and test-compat aliases.
"""

from __future__ import annotations

from .cohort_runner import compute_all_bill_billing_reports, compute_all_billing_reports
from .patient_report import compute_patient_billing_report
from .procedure_dedup import dedupe_addon_against_capture
from .recovery_summary import (
    _get_top_action_type,
    patient_recovery_summary_entry,
    patient_recovery_summary_from_payload,
)
from .report_totals import finalize_report_totals, sum_sgk_uplift_try

# Backward-compatible private aliases for tests and monkeypatch targets.
_finalize_report_totals = finalize_report_totals
_sum_sgk_uplift_try = sum_sgk_uplift_try
_dedupe_addon_against_capture = dedupe_addon_against_capture

__all__ = [
    "compute_patient_billing_report",
    "compute_all_billing_reports",
    "compute_all_bill_billing_reports",
    "_get_top_action_type",
    "patient_recovery_summary_entry",
    "patient_recovery_summary_from_payload",
    "_finalize_report_totals",
    "_sum_sgk_uplift_try",
    "_dedupe_addon_against_capture",
]
