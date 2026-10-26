"""Parallel cohort billing report runners."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from typing import Any, TypeVar

import polars as pl

from src.bilun.domain.claims.models import ClaimHeader
from src.bilun.domain.claims.patient_context import (
    build_bill_claim_context,
    build_patient_claim_context,
)
from src.bilun.domain.optimization.copay_exemption_context import (
    bill_copay_exemption_input,
)
from src.bilun.domain.optimization.copay_exemption_types import CopayExemptionInput
from src.bilun.domain.optimization.copay_exemptions import evaluate_copay_exemption

from .cohort_summary import build_cohort_recovery_summary
from .priority import assign_priority_by_percentile
from .types import BillingActionReport, CohortRecoverySummary

logger = logging.getLogger("ilay.sut_billing_optimizer")

T = TypeVar("T")
R = TypeVar("R")

_DEFAULT_COPAY_EXEMPTION = {
    "exempt": False,
    "n_qualifying": 0,
    "qualifying_diagnoses": [],
}


def _compute_patient_billing_report(*args: Any, **kwargs: Any) -> BillingActionReport:
    """Resolve via orchestrator facade so tests can monkeypatch entry points."""
    from .orchestrator import compute_patient_billing_report

    return compute_patient_billing_report(*args, **kwargs)


def map_parallel(
    items: list[T],
    fn: Callable[[T], R],
    *,
    max_workers: int,
) -> list[R]:
    """Run ``fn`` over ``items`` with optional thread parallelism."""
    if not items:
        return []
    worker_count = max(1, min(int(max_workers), len(items)))
    if worker_count == 1:
        return [fn(item) for item in items]
    with ThreadPoolExecutor(max_workers=worker_count) as executor:
        return list(executor.map(fn, items))


def alerts_by_patient_id(cache: dict[str, Any]) -> dict[str, dict[str, Any]]:
    alerts_cache = cache.get("patient_alerts_cache", {})
    return {
        alert["patient_id"]: alert for alert in alerts_cache.get("patients", [])
    }


def patient_ids_from_cache(
    cache: dict[str, Any],
    alerts_by_pid: dict[str, dict[str, Any]],
) -> list[str]:
    sut_by_pid = cache.get("sut_by_pid", {})
    lab_df_pl: pl.DataFrame = cache.get("lab_df_pl", pl.DataFrame())

    patient_id_set = set(sut_by_pid.keys()) if hasattr(sut_by_pid, "keys") else set()
    patient_id_set.update(alerts_by_pid.keys())
    if not lab_df_pl.is_empty() and "patient_id" in lab_df_pl.columns:
        patient_id_set.update(lab_df_pl["patient_id"].unique().to_list())
    return sorted(patient_id_set)


def bill_copay_exemption(
    pid: str,
    claim: ClaimHeader,
    alerts_by_pid: dict[str, dict[str, Any]],
    copay_inputs_by_pid: dict[str, CopayExemptionInput],
) -> dict[str, Any]:
    """The copay exemption of one bill's report: the patient's, with EK-1/A read on the bill's date (#292).

    The patient's copay input (``assemble_sut_context`` builds it) is evaluated again on the bill's
    own date (``bill_copay_exemption_input``), so a bill served before an EK-1/A change reads the
    list in force then. Without an input (a cache built without one) the patient-level result of the
    alerts cache is reused, read on the patient's latest claim.
    """
    patient_input = copay_inputs_by_pid.get(pid)
    if patient_input is None:
        alert = alerts_by_pid.get(pid, {})
        return alert.get("copay_exemption", _DEFAULT_COPAY_EXEMPTION)
    return evaluate_copay_exemption(bill_copay_exemption_input(patient_input, claim))


def compute_all_bill_billing_reports(
    cache: dict[str, Any],
    *,
    max_workers: int = 1,
) -> dict[str, BillingActionReport]:
    """Compute one billing report per (patient, claim) bill.

    Mirrors :func:`compute_all_billing_reports` but scopes each report to a
    single ``claim_id`` via ``build_bill_claim_context``, with the clinical lab
    feed filtered to the claim's episode (``visit_id``). The copay exemption is
    the patient's read on the bill's own date (``bill_copay_exemption``: EK-1/A
    as of the bill, #292); the copay block reads a claim-scoped ground (the
    emergency visit, SUT 1.8.5.(5)) on the bill's own claim only. Keyed by
    ``f"{patient_id}::{claim_id}"`` so it stores in the generic payload-rows
    table. Returns ``{}`` when no claim dataset is present.
    """
    claim_dataset = cache.get("sut_claim_dataset")
    if claim_dataset is None:
        return {}

    alerts_by_pid = alerts_by_patient_id(cache)
    copay_inputs_by_pid = cache.get("copay_inputs_by_pid") or {}
    lab_df_pl: pl.DataFrame = cache.get("lab_df_pl", pl.DataFrame())

    # Each bill's exemption is evaluated here, before the fan-out: the EK-1/A index
    # of its date is built in this thread, not in the workers.
    tasks: list[tuple[str, str, dict[str, Any]]] = [
        (
            pid,
            claim.claim_id,
            bill_copay_exemption(pid, claim, alerts_by_pid, copay_inputs_by_pid),
        )
        for pid, claims in claim_dataset.claims_by_patient.items()
        for claim in claims
    ]
    if not tasks:
        return {}

    def _one(
        task: tuple[str, str, dict[str, Any]],
    ) -> tuple[str, BillingActionReport | None]:
        pid, claim_id, copay_exemption = task
        key = f"{pid}::{claim_id}"
        bill_context = build_bill_claim_context(pid, claim_id, claim_dataset)
        if bill_context is None:
            return key, None
        report = _compute_patient_billing_report(
            pid,
            claim_context=bill_context,
            copay_exemption=copay_exemption,
            lab_df_pl=lab_df_pl,
        )
        return key, report

    results = map_parallel(tasks, _one, max_workers=max_workers)
    reports = {key: report for key, report in results if report is not None}
    assign_priority_by_percentile(list(reports.values()))
    return reports


def compute_all_billing_reports(
    cache: dict[str, Any],
    *,
    max_workers: int = 1,
) -> tuple[dict[str, BillingActionReport], CohortRecoverySummary]:
    """Compute billing reports for all patients using pre-cached pipeline data.

    This is the main entry point called from the analytics cache builder after
    SUT claim context is assembled.

    Args:
        cache: The _pipeline_cache dict containing:
            - sut_by_pid: optional exact SUT claim-total payloads keyed by patient
            - patient_alerts_cache: dict with "patients" list
            - lab_df_pl: Polars DataFrame of lab tests
    Returns:
        Tuple of (billing_reports_by_pid, cohort_summary).
    """
    t0 = time.perf_counter()

    claim_dataset = cache.get("sut_claim_dataset")
    alerts_by_pid = alerts_by_patient_id(cache)
    lab_df_pl: pl.DataFrame = cache.get("lab_df_pl", pl.DataFrame())

    patient_ids = patient_ids_from_cache(cache, alerts_by_pid)
    if not patient_ids:
        logger.warning("No SUT patient inputs in cache — billing reports will be empty")
        return {}, CohortRecoverySummary()

    worker_count = max(1, min(int(max_workers), len(patient_ids)))
    logger.info(
        "Computing billing reports for %d patients (workers=%d)...",
        len(patient_ids),
        worker_count,
    )

    def _build_report(pid: str) -> BillingActionReport:
        alert = alerts_by_pid.get(pid, {})
        copay_exemption = alert.get("copay_exemption", _DEFAULT_COPAY_EXEMPTION)

        claim_context = None
        if claim_dataset is not None:
            claim_context = build_patient_claim_context(pid, claim_dataset)

        return _compute_patient_billing_report(
            pid,
            claim_context=claim_context,
            copay_exemption=copay_exemption,
            lab_df_pl=lab_df_pl,
        )

    report_list = map_parallel(patient_ids, _build_report, max_workers=worker_count)
    reports = dict(zip(patient_ids, report_list, strict=True))

    assign_priority_by_percentile(list(reports.values()))

    summary = build_cohort_recovery_summary(reports, claim_dataset=claim_dataset)

    elapsed = time.perf_counter() - t0
    logger.info(
        "Billing reports computed for %d patients in %.1fs — "
        "total recoverable: %.0f TRY",
        len(reports),
        elapsed,
        summary.grand_total_recoverable,
    )

    return reports, summary
