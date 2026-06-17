"""Cohort-level revenue recovery summary aggregation."""

from __future__ import annotations

from typing import Any

from .block_registry import BILLING_BLOCK_SPECS
from .report_exactness import block_exactness_status, finalize_summary_exactness
from .recovery_summary import patient_recovery_summary_entry, total_opportunity_try
from .types import EXACTNESS_STATUS_EXACT, BillingActionReport, CohortRecoverySummary

_MATERIAL_FLAG_ATTRS = (
    "pre_auth_required",
    "miat_restricted",
    "bundled_separate_billing",
    "miat_interval_violations",
    "prose_bundling_violations",
    "specialty_prose_violations",
)


def _copay_waived_total_try(report: BillingActionReport) -> float:
    waived_total = float(
        getattr(report.copay, "patient_copay_waived_total_try", 0.0) or 0.0
    )
    if waived_total <= 0:
        waived_total = (
            report.copay.total_copay_savings_try + report.copay.rx_copay_savings_try
        )
    return waived_total


def _rollup_lab_and_compliance(
    summary: CohortRecoverySummary,
    report: BillingActionReport,
) -> None:
    if block_exactness_status(report.lab) != EXACTNESS_STATUS_EXACT:
        return
    summary.total_lab_savings += report.lab.total_savings
    summary.total_compliance_adjustment += report.compliance_adjustment_try


def _rollup_billing_strategy(
    summary: CohortRecoverySummary,
    report: BillingActionReport,
) -> None:
    if block_exactness_status(report.billing_strategy) != EXACTNESS_STATUS_EXACT:
        return
    uplift = report.billing_strategy.uplift_savings_try
    summary.total_strategy_savings += uplift
    summary.total_strategy_uplift += uplift
    override_uplift = report.billing_strategy.optional_override_uplift_try
    summary.total_optional_override_uplift += override_uplift
    if override_uplift > 0:
        summary.n_optional_override_patients += 1


def _rollup_copay(summary: CohortRecoverySummary, report: BillingActionReport) -> None:
    if block_exactness_status(report.copay) != EXACTNESS_STATUS_EXACT:
        return
    summary.total_copay_savings += _copay_waived_total_try(report)


def _rollup_registry_block(
    summary: CohortRecoverySummary,
    report: BillingActionReport,
    spec: Any,
) -> None:
    if not spec.cohort_total_field:
        return

    block = getattr(report, spec.attr)
    if block_exactness_status(block) != EXACTNESS_STATUS_EXACT:
        return

    if spec.cohort_value_from_report:
        value = getattr(report, spec.cohort_value_from_report)
    elif spec.uplift_field:
        value = getattr(block, spec.uplift_field)
    else:
        return

    current = getattr(summary, spec.cohort_total_field)
    setattr(summary, spec.cohort_total_field, current + value)

    if spec.cohort_patient_counter_field and float(value) > 0:
        counter = getattr(summary, spec.cohort_patient_counter_field)
        setattr(summary, spec.cohort_patient_counter_field, counter + 1)


def _rollup_material_flags(
    summary: CohortRecoverySummary,
    report: BillingActionReport,
) -> None:
    materials = report.materials
    summary.total_material_flags += sum(
        len(getattr(materials, attr, [])) for attr in _MATERIAL_FLAG_ATTRS
    )


def _finalize_summary_rounding(
    summary: CohortRecoverySummary,
    reports: dict[str, BillingActionReport],
) -> None:
    summary.total_lab_savings = round(summary.total_lab_savings, 2)
    summary.total_copay_savings = round(summary.total_copay_savings, 2)
    summary.total_strategy_savings = round(summary.total_strategy_savings, 2)
    summary.total_session_uplift = round(summary.total_session_uplift, 2)
    summary.total_drg_uplift = round(summary.total_drg_uplift, 2)
    summary.total_blood_uplift = round(summary.total_blood_uplift, 2)
    summary.total_material_uplift = round(summary.total_material_uplift, 2)
    summary.total_procedure_addon_uplift = round(summary.total_procedure_addon_uplift, 2)
    summary.total_optional_override_uplift = round(summary.total_optional_override_uplift, 2)
    summary.total_strategy_uplift = round(summary.total_strategy_uplift, 2)
    summary.total_compliance_adjustment = round(summary.total_compliance_adjustment, 2)
    summary.total_sgk_uplift = round(
        sum(r.sgk_uplift_try for r in reports.values()),
        2,
    )
    summary.total_audit_exposure = round(summary.total_audit_exposure, 2)
    summary.total_capture_gap = round(summary.total_capture_gap, 2)
    summary.total_package_adequacy_review = round(
        summary.total_package_adequacy_review, 2
    )
    summary.grand_total_recoverable = summary.total_sgk_uplift


def _savings_by_category(summary: CohortRecoverySummary) -> dict[str, float]:
    return {
        "sgk_uplift": summary.total_sgk_uplift,
        "session_uplift": summary.total_session_uplift,
        "drg_uplift": summary.total_drg_uplift,
        "blood_uplift": summary.total_blood_uplift,
        "material_uplift": summary.total_material_uplift,
        "procedure_addon_uplift": summary.total_procedure_addon_uplift,
        "optional_override": summary.total_optional_override_uplift,
        "strategy_uplift": summary.total_strategy_uplift,
        "compliance": summary.total_compliance_adjustment,
        "copay_waiver": summary.total_copay_savings,
        "audit_exposure": summary.total_audit_exposure,
        "capture_gap": summary.total_capture_gap,
        "package_adequacy_review": summary.total_package_adequacy_review,
        "gazette_repricing": summary.total_gazette_repricing,
        "lab": summary.total_compliance_adjustment,
        "copay": summary.total_copay_savings,
        "strategy": summary.total_strategy_uplift,
    }


def build_cohort_recovery_summary(
    reports: dict[str, BillingActionReport],
    *,
    claim_dataset: Any | None,
) -> CohortRecoverySummary:
    """Aggregate per-patient billing reports into a cohort summary."""
    summary = CohortRecoverySummary()
    summary.n_patients = len(reports)
    summary.medula_rejection_ingest_available = bool(
        claim_dataset is not None and claim_dataset.medula_rejection_ingest_available
    )

    priority_dist: dict[str, int] = {"high": 0, "medium": 0, "low": 0}

    registry_specs = [
        spec
        for spec in BILLING_BLOCK_SPECS
        if spec.cohort_total_field
        and spec.attr not in ("billing_strategy",)
    ]

    for report in reports.values():
        _rollup_lab_and_compliance(summary, report)
        _rollup_billing_strategy(summary, report)
        for spec in registry_specs:
            _rollup_registry_block(summary, report, spec)
        _rollup_copay(summary, report)
        summary.total_audit_exposure += report.audit_exposure_try
        _rollup_material_flags(summary, report)
        priority_dist[report.priority] = priority_dist.get(report.priority, 0) + 1

    _finalize_summary_rounding(summary, reports)
    summary.priority_distribution = priority_dist

    sorted_reports = sorted(reports.values(), key=total_opportunity_try, reverse=True)
    summary.patient_summaries = [
        patient_recovery_summary_entry(r) for r in sorted_reports
    ]
    summary.top_patients = summary.patient_summaries[:10]
    summary.savings_by_category = _savings_by_category(summary)
    finalize_summary_exactness(summary, reports)

    return summary
