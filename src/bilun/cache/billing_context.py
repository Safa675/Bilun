"""Billing assembly helpers for analytics cache context."""

from __future__ import annotations

from typing import Any

import polars as pl


def _build_billing_cache(
    *,
    sut_by_pid: dict[str, Any],
    patient_alerts_cache: dict[str, Any],
    lab_df: pl.DataFrame,
    rec_df: pl.DataFrame,
    sut_claim_dataset: Any | None = None,
) -> dict[str, Any]:
    return {
        "sut_by_pid": sut_by_pid,
        "patient_alerts_cache": patient_alerts_cache,
        "lab_df_pl": lab_df,
        "rec_df_pl": rec_df,
        "sut_claim_dataset": sut_claim_dataset,
    }


def assemble_billing_context(
    *,
    sut_by_pid: dict[str, Any],
    patient_alerts_cache: dict[str, Any],
    lab_df: pl.DataFrame,
    rec_df: pl.DataFrame,
    billing_workers: int | None,
    compute_all_billing_reports_fn,
    sut_claim_dataset: Any | None = None,
) -> dict[str, Any]:
    billing_cache = _build_billing_cache(
        sut_by_pid=sut_by_pid,
        patient_alerts_cache=patient_alerts_cache,
        lab_df=lab_df,
        rec_df=rec_df,
        sut_claim_dataset=sut_claim_dataset,
    )
    if billing_workers is None:
        billing_reports, revenue_recovery = compute_all_billing_reports_fn(billing_cache)
    else:
        billing_reports, revenue_recovery = compute_all_billing_reports_fn(
            billing_cache,
            max_workers=billing_workers,
        )
    return {
        "billing_reports": billing_reports,
        "revenue_recovery": revenue_recovery,
    }
