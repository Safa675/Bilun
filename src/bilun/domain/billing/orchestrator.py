"""
src/bilun/domain/billing/orchestrator.py
Main orchestrators: compute_patient_billing_report, compute_all_billing_reports.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import logging
import time
from typing import TYPE_CHECKING, Any

import polars as pl

from .types import (
    BILLING_REPORT_PARTIAL_REASON,
    COHORT_RECOVERY_PARTIAL_REASON,
    EXACTNESS_STATUS_EXACT,
    EXACTNESS_STATUS_MISSING_INPUTS,
    EXACTNESS_STATUS_PARTIAL,
    BillingActionReport,
    CohortRecoverySummary,
)
from src.bilun.domain.claims.patient_context import build_patient_claim_context
from src.bilun.domain.billing.claim_copay import optimize_copay_from_claims
from src.bilun.domain.billing.claim_materials import precheck_materials_from_claims
from src.bilun.domain.billing.claim_strategy import recommend_billing_strategy_from_claims
from src.bilun.domain.billing.drug_claims import optimize_drug_from_claims
from .lab import _optimize_lab_billing
from .drug import _optimize_drug_costs
from .copay import _optimize_copay
from .strategy import _recommend_billing_strategy
from .materials import _precheck_materials

if TYPE_CHECKING:
    from src.bilun.domain.claims.loader import SUTClaimDataset
    from src.bilun.domain.claims.patient_context import PatientClaimContext

logger = logging.getLogger("ilay.sut_billing_optimizer")


def _block_exactness_status(block: Any) -> str:
    status = str(
        getattr(block, "exactness_status", EXACTNESS_STATUS_MISSING_INPUTS) or ""
    ).strip()
    return status or EXACTNESS_STATUS_MISSING_INPUTS


def _sum_exact_recoverable_try(report: BillingActionReport) -> float:
    """Sum savings only from billing blocks marked exact."""
    total = 0.0
    if _block_exactness_status(report.lab) == EXACTNESS_STATUS_EXACT:
        total += report.lab.total_savings
    if _block_exactness_status(report.drug) == EXACTNESS_STATUS_EXACT:
        total += report.drug.total_savings
    if _block_exactness_status(report.copay) == EXACTNESS_STATUS_EXACT:
        total += report.copay.total_copay_savings_try
        total += float(getattr(report.copay, "rx_copay_savings_try", 0.0) or 0.0)
    if _block_exactness_status(report.billing_strategy) == EXACTNESS_STATUS_EXACT:
        total += report.billing_strategy.total_savings
    return round(total, 2)


def _collect_required_inputs(blocks: list[Any]) -> list[str]:
    ordered: list[str] = []
    for block in blocks:
        for name in getattr(block, "required_inputs_missing", []) or []:
            if name not in ordered:
                ordered.append(name)
    return ordered


def _finalize_report_exactness(report: BillingActionReport) -> None:
    blocks = [
        report.lab,
        report.drug,
        report.copay,
        report.billing_strategy,
        report.materials,
    ]
    non_exact_blocks = [
        block for block in blocks if _block_exactness_status(block) != EXACTNESS_STATUS_EXACT
    ]
    if not non_exact_blocks:
        report.exactness_status = EXACTNESS_STATUS_EXACT
        report.unavailable_reason = None
        report.required_inputs_missing = []
        return

    report.exactness_status = EXACTNESS_STATUS_PARTIAL
    report.unavailable_reason = BILLING_REPORT_PARTIAL_REASON
    report.required_inputs_missing = _collect_required_inputs(non_exact_blocks)
    if not report.required_inputs_missing:
        report.required_inputs_missing = [
            f"{getattr(block, '__class__', type(block)).__name__}.required_inputs_missing"
            for block in non_exact_blocks
        ]


def _finalize_summary_exactness(
    summary: CohortRecoverySummary,
    reports: dict[str, BillingActionReport],
) -> None:
    non_exact_reports = [
        report
        for report in reports.values()
        if _block_exactness_status(report) != EXACTNESS_STATUS_EXACT
    ]
    if not non_exact_reports:
        summary.exactness_status = EXACTNESS_STATUS_EXACT
        summary.unavailable_reason = None
        summary.required_inputs_missing = []
        return

    summary.exactness_status = EXACTNESS_STATUS_PARTIAL
    summary.unavailable_reason = COHORT_RECOVERY_PARTIAL_REASON
    summary.required_inputs_missing = _collect_required_inputs(non_exact_reports)
    if not summary.required_inputs_missing:
        summary.required_inputs_missing = ["cohort_billing_report.required_inputs_missing"]


def compute_patient_billing_report(
    pid: str,
    *,
    claim_context: PatientClaimContext | None = None,
    patient_lab_tests: list[str] | None = None,
    patient_lab_dates: list[str | None] | None = None,
    patient_lab_visit_ids: list[str | None] | None = None,
    patient_drug_names: list[str] | None = None,
    copay_exemption: dict[str, Any] | None = None,
    chapters: set[str] | None = None,
) -> BillingActionReport:
    """Compute a full billing action report for a single patient.

    Calls all 5 algorithms and assembles the combined report.

    Args:
        pid: Patient identifier.
        patient_lab_tests: List of lab test names.
        patient_drug_names: List of drug names.
        copay_exemption: Pre-computed copay exemption result.
        chapters: Pre-computed ICD-10 chapter set.

    Returns:
        BillingActionReport with all algorithm results.
    """
    report = BillingActionReport(patient_id=pid)

    report.lab = _optimize_lab_billing(
        pid,
        patient_lab_tests or [],
        patient_lab_dates,
        patient_lab_visit_ids,
    )

    exemption = copay_exemption or {
        "exempt": False,
        "n_qualifying": 0,
        "qualifying_diagnoses": [],
    }

    if claim_context is not None and claim_context.drug_lines:
        report.drug = optimize_drug_from_claims(claim_context, is_exempt=bool(exemption.get("exempt")))
    else:
        report.drug = _optimize_drug_costs(pid, patient_drug_names or [])

    if claim_context is not None and (
        claim_context.procedure_lines or claim_context.drug_lines
    ):
        report.copay = optimize_copay_from_claims(claim_context, exemption)
    else:
        report.copay = _optimize_copay(pid, exemption)

    if claim_context is not None and claim_context.claims:
        report.billing_strategy = recommend_billing_strategy_from_claims(claim_context)
    else:
        report.billing_strategy = _recommend_billing_strategy(pid, chapters or set())

    if claim_context is not None:
        report.materials = precheck_materials_from_claims(claim_context)
    else:
        report.materials = _precheck_materials(pid, chapters or set())

    report.total_recoverable_try = _sum_exact_recoverable_try(report)

    actions = (
        len(report.lab.flagged_tests)
        + len(report.drug.drug_recommendations)
        + (1 if report.copay.is_exempt else 0)
        + len(report.billing_strategy.recommendations)
        + len(report.materials.pre_auth_required)
        + len(report.materials.miat_restricted)
        + len(report.materials.bundled_separate_billing)
        + len(report.materials.miat_interval_violations)
    )
    report.action_count = actions

    _finalize_report_exactness(report)

    return report


def compute_all_billing_reports(
    cache: dict[str, Any],
    *,
    max_workers: int = 1,
) -> tuple[dict[str, BillingActionReport], CohortRecoverySummary]:
    """Compute billing reports for all patients using pre-cached pipeline data.

    This is the main entry point called from pipeline.py after all SUT
    data is pre-computed.

    Args:
        cache: The _pipeline_cache dict containing:
            - sut_by_pid: optional exact SUT claim-total payloads keyed by patient
            - patient_alerts_cache: dict with "patients" list
            - lab_df_pl: Polars DataFrame of lab tests
            - rec_df_pl: Polars DataFrame of prescriptions

    Returns:
        Tuple of (billing_reports_by_pid, cohort_summary).
    """
    t0 = time.perf_counter()

    sut_by_pid = cache.get("sut_by_pid", {})
    claim_dataset: SUTClaimDataset | None = cache.get("sut_claim_dataset")
    alerts_cache = cache.get("patient_alerts_cache", {})
    lab_df_pl: pl.DataFrame = cache.get("lab_df_pl", pl.DataFrame())
    rec_df_pl: pl.DataFrame = cache.get("rec_df_pl", pl.DataFrame())

    alerts_by_pid: dict[str, dict[str, Any]] = {}
    for alert in alerts_cache.get("patients", []):
        alerts_by_pid[alert["patient_id"]] = alert

    lab_tests_by_pid: dict[str, list[str]] = {}
    lab_dates_by_pid: dict[str, list[str | None]] = {}
    lab_visit_ids_by_pid: dict[str, list[str | None]] = {}
    if not lab_df_pl.is_empty() and "patient_id" in lab_df_pl.columns:
        if "test_name" in lab_df_pl.columns:
            date_col = next(
                (c for c in ("date", "test_date", "tarih") if c in lab_df_pl.columns),
                None,
            )
            visit_col = "visit_id" if "visit_id" in lab_df_pl.columns else None
            agg_exprs = [pl.col("test_name").cast(pl.Utf8).fill_null("").alias("tests")]
            if date_col:
                agg_exprs.append(
                    pl.col(date_col).cast(pl.Utf8).fill_null("").alias("dates")
                )
            if visit_col:
                agg_exprs.append(
                    pl.col(visit_col).cast(pl.Utf8).fill_null("").alias("visit_ids")
                )
            lab_agg = lab_df_pl.group_by("patient_id").agg(agg_exprs)
            for row in lab_agg.iter_rows(named=True):
                lab_tests_by_pid[row["patient_id"]] = row["tests"]
                if date_col and "dates" in row:
                    lab_dates_by_pid[row["patient_id"]] = row["dates"]
                if visit_col and "visit_ids" in row:
                    lab_visit_ids_by_pid[row["patient_id"]] = row["visit_ids"]

    drug_names_by_pid: dict[str, list[str]] = {}
    if not rec_df_pl.is_empty() and "patient_id" in rec_df_pl.columns:
        if "drug_name" in rec_df_pl.columns:
            rx_agg = rec_df_pl.group_by("patient_id").agg(
                pl.col("drug_name").cast(pl.Utf8).fill_null("").alias("drugs")
            )
            for row in rx_agg.iter_rows(named=True):
                drug_names_by_pid[row["patient_id"]] = row["drugs"]

    reports: dict[str, BillingActionReport] = {}
    patient_id_set = set(sut_by_pid.keys()) if hasattr(sut_by_pid, "keys") else set()
    patient_id_set.update(alerts_by_pid.keys())
    patient_id_set.update(lab_tests_by_pid.keys())
    patient_id_set.update(drug_names_by_pid.keys())
    patient_ids = sorted(patient_id_set)
    if not patient_ids:
        logger.warning("No SUT patient inputs in cache — billing reports will be empty")
        return {}, CohortRecoverySummary()

    worker_count = max(1, min(int(max_workers), max(1, len(patient_ids))))

    logger.info(
        "Computing billing reports for %d patients (workers=%d)...",
        len(patient_ids),
        worker_count,
    )

    def _build_report(pid: str) -> BillingActionReport:
        alert = alerts_by_pid.get(pid, {})
        copay_exemption = alert.get(
            "copay_exemption",
            {"exempt": False, "n_qualifying": 0, "qualifying_diagnoses": []},
        )
        chapters_list = alert.get("icd10_chapters", [])
        chapters = set(chapters_list)

        claim_context = None
        if claim_dataset is not None:
            claim_context = build_patient_claim_context(pid, claim_dataset)

        report = compute_patient_billing_report(
            pid,
            claim_context=claim_context,
            patient_lab_tests=lab_tests_by_pid.get(pid, []),
            patient_lab_dates=lab_dates_by_pid.get(pid),
            patient_lab_visit_ids=lab_visit_ids_by_pid.get(pid),
            patient_drug_names=drug_names_by_pid.get(pid, []),
            copay_exemption=copay_exemption,
            chapters=chapters,
        )
        return report

    if worker_count == 1:
        report_list = [_build_report(pid) for pid in patient_ids]
    else:
        with ThreadPoolExecutor(max_workers=worker_count) as executor:
            report_list = list(executor.map(_build_report, patient_ids))

    for pid, report in zip(patient_ids, report_list, strict=True):
        reports[pid] = report

    recoverables = sorted(
        [
            r.total_recoverable_try
            for r in reports.values()
            if r.total_recoverable_try > 0
        ]
    )
    if recoverables:
        n = len(recoverables)
        p75 = recoverables[min(n - 1, int(n * 0.75))]
        p50 = recoverables[min(n - 1, int(n * 0.50))]
        for report in reports.values():
            if report.total_recoverable_try >= p75:
                report.priority = "high"
            elif report.total_recoverable_try >= p50:
                report.priority = "medium"
            else:
                report.priority = "low"

    summary = CohortRecoverySummary()
    summary.n_patients = len(reports)

    priority_dist: dict[str, int] = {"high": 0, "medium": 0, "low": 0}

    for report in reports.values():
        if _block_exactness_status(report.lab) == EXACTNESS_STATUS_EXACT:
            summary.total_lab_savings += report.lab.total_savings
        if _block_exactness_status(report.drug) == EXACTNESS_STATUS_EXACT:
            summary.total_drug_savings += report.drug.total_savings
        if _block_exactness_status(report.copay) == EXACTNESS_STATUS_EXACT:
            summary.total_copay_savings += (
                report.copay.total_copay_savings_try
                + report.copay.rx_copay_savings_try
            )
        if _block_exactness_status(report.billing_strategy) == EXACTNESS_STATUS_EXACT:
            summary.total_strategy_savings += report.billing_strategy.total_savings
        summary.total_material_flags += len(report.materials.pre_auth_required) + len(
            report.materials.miat_restricted
        ) + len(report.materials.bundled_separate_billing) + len(
            report.materials.miat_interval_violations
        )
        priority_dist[report.priority] = priority_dist.get(report.priority, 0) + 1

    summary.total_lab_savings = round(summary.total_lab_savings, 2)
    summary.total_drug_savings = round(summary.total_drug_savings, 2)
    summary.total_copay_savings = round(summary.total_copay_savings, 2)
    summary.total_strategy_savings = round(summary.total_strategy_savings, 2)
    summary.grand_total_recoverable = round(
        sum(r.total_recoverable_try for r in reports.values()),
        2,
    )
    summary.priority_distribution = priority_dist

    sorted_reports = sorted(
        reports.values(), key=lambda r: r.total_recoverable_try, reverse=True
    )
    summary.patient_summaries = [
        patient_recovery_summary_entry(r) for r in sorted_reports
    ]
    summary.top_patients = summary.patient_summaries[:10]

    summary.savings_by_category = {
        "lab": summary.total_lab_savings,
        "drug": summary.total_drug_savings,
        "copay": summary.total_copay_savings,
        "strategy": summary.total_strategy_savings,
    }
    _finalize_summary_exactness(summary, reports)

    elapsed = time.perf_counter() - t0
    logger.info(
        "Billing reports computed for %d patients in %.1fs — "
        "total recoverable: %.0f TRY",
        len(reports),
        elapsed,
        summary.grand_total_recoverable,
    )

    return reports, summary


def _top_action_type_from_savings(savings: dict[str, float]) -> str:
    if not any(v > 0 for v in savings.values()):
        return "none"
    return max(savings, key=lambda k: savings[k])


def _get_top_action_type(report: BillingActionReport) -> str:
    """Determine the primary action type for a patient report."""
    return _top_action_type_from_savings(
        {
            "lab": report.lab.total_savings,
            "drug": report.drug.total_savings,
            "copay": report.copay.total_copay_savings_try,
            "strategy": report.billing_strategy.total_savings,
        }
    )


def patient_recovery_summary_entry(report: BillingActionReport) -> dict[str, Any]:
    """Compact per-patient recovery row for cohort tables."""
    return {
        "patient_id": report.patient_id,
        "total_recoverable_try": report.total_recoverable_try,
        "priority": report.priority,
        "action_count": report.action_count,
        "top_action_type": _get_top_action_type(report),
    }


def patient_recovery_summary_from_payload(report: dict[str, Any]) -> dict[str, Any]:
    """Build a recovery summary dict from cached billing report JSON."""
    savings = {
        "lab": float((report.get("lab") or {}).get("total_savings") or 0),
        "drug": float((report.get("drug") or {}).get("total_savings") or 0),
        "copay": float((report.get("copay") or {}).get("total_copay_savings_try") or 0),
        "strategy": float((report.get("billing_strategy") or {}).get("total_savings") or 0),
    }
    return {
        "patient_id": str(report.get("patient_id") or ""),
        "total_recoverable_try": float(report.get("total_recoverable_try") or 0),
        "priority": str(report.get("priority") or "low"),
        "action_count": int(report.get("action_count") or 0),
        "top_action_type": _top_action_type_from_savings(savings),
    }
