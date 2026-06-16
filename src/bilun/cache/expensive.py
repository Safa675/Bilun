"""
Pipeline: canonical cache read and expensive per-patient computation.

Surviving public functions:
    _compute_patient_expensive_sections — pure per-patient DRG + gap compute,
        invoked from the analytics-cache builder backfill.
"""

from __future__ import annotations

from collections.abc import Mapping
import json
import logging
import time
from typing import Any

import polars as pl

from src.bilun.domain.analytics import compute_drg_summary

logger = logging.getLogger(__name__)

_MISSING_DRG_PRICING_METADATA_REASON = (
    "DRG pricing exactness metadata was not provided by the SUT payload."
)


def _required_inputs_from(source: Any) -> list[str]:
    return list(getattr(source, "required_inputs_missing", []) or [])


def _ordered_required_inputs(*sources: Any) -> list[str]:
    ordered: list[str] = []
    for source in sources:
        for item in _required_inputs_from(source):
            if item not in ordered:
                ordered.append(item)
    return ordered


def _pricing_status_or_unavailable(source: Any) -> tuple[str, str | None, list[str]]:
    raw_status = getattr(source, "pricing_status", None)
    status = str(raw_status).strip() if raw_status is not None else ""
    if status:
        return (
            status,
            getattr(source, "unavailable_reason", None),
            _required_inputs_from(source),
        )
    return (
        "missing_exact_inputs",
        _MISSING_DRG_PRICING_METADATA_REASON,
        ["pricing_status"],
    )


def _normalize_cached_pricing_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    normalized = dict(payload)
    raw_status = normalized.get("pricing_status")
    status = str(raw_status).strip() if raw_status is not None else ""
    if status:
        return normalized
    normalized["pricing_status"] = "missing_exact_inputs"
    normalized["unavailable_reason"] = (
        normalized.get("unavailable_reason") or _MISSING_DRG_PRICING_METADATA_REASON
    )
    normalized["required_inputs_missing"] = list(
        normalized.get("required_inputs_missing") or ["pricing_status"]
    )
    return normalized


def normalize_cached_drg_summary_payload(drg_summary: Any) -> Any:
    """Backfill explicit unavailable pricing metadata for stale cache rows."""

    if not isinstance(drg_summary, Mapping):
        return drg_summary
    normalized = _normalize_cached_pricing_payload(drg_summary)
    episodes = normalized.get("episodes")
    if isinstance(episodes, list):
        normalized["episodes"] = [
            _normalize_cached_pricing_payload(episode)
            if isinstance(episode, Mapping)
            else episode
            for episode in episodes
        ]
    return normalized


def _resolve_drg_inputs(
    *,
    patient_id: str,
    ctx: dict[str, Any],
) -> pl.DataFrame:
    ana_by_pid = ctx.get("ana_by_pid")
    if ana_by_pid is not None and hasattr(ana_by_pid, "get"):
        patient_frame = ana_by_pid.get(patient_id)
        if isinstance(patient_frame, pl.DataFrame):
            return patient_frame

    ana_df_full = ctx.get("ana_df")
    if ana_df_full is None:
        return pl.DataFrame()

    if isinstance(ana_df_full, pl.DataFrame):
        id_col = "patient_id" if "patient_id" in ana_df_full.columns else "HASTA_ID" if "HASTA_ID" in ana_df_full.columns else None
        if id_col:
            return ana_df_full.filter(pl.col(id_col) == patient_id)
        return ana_df_full.head(0)

    return pl.DataFrame()


def _compute_patient_expensive_sections(
    *,
    patient_id: str,
    sut_estimate,
    ctx: dict,
    timeout_ms: int,
) -> tuple[dict[str, Any], bool]:
    """Compute expensive outcome sections with a hard time budget.

    Returns (payload, completed_within_budget).
    """
    t0 = time.perf_counter()

    def _timed_out() -> bool:
        return (time.perf_counter() - t0) * 1000.0 > timeout_ms

    payload: dict[str, Any] = {
        "drg_summary": None,
        "consistency_warnings": [],
    }

    if sut_estimate is None:
        return payload, True

    try:
        if not _timed_out():
            ana_df_input = _resolve_drg_inputs(
                patient_id=patient_id,
                ctx=ctx,
            )
            drg = compute_drg_summary(
                patient_id,
                ana_df_input,
                sut_estimate,
                claim_dataset=ctx.get("sut_claim_dataset"),
            )
            drg_status, drg_unavailable_reason, drg_required_inputs = (
                _pricing_status_or_unavailable(drg)
            )
            episode_payloads: list[dict[str, Any]] = []
            for ep in drg.episodes[:10]:
                ep_status, ep_unavailable_reason, ep_required_inputs = (
                    _pricing_status_or_unavailable(ep)
                )
                episode_payloads.append(
                    {
                        "episode_id": ep.episode_id,
                        "claim_id": getattr(ep, "claim_id", ep.episode_id),
                        "primary_icd10": ep.primary_icd10,
                        "primary_icd10_chapter": ep.primary_icd10_chapter,
                        "description": ep.description,
                        "los_days": ep.los_days,
                        "lab_cost": ep.lab_cost,
                        "visit_cost": ep.visit_cost,
                        "rx_cost": ep.rx_cost,
                        "procedure_cost": ep.procedure_cost,
                        "total_cost": ep.total_cost,
                        "drg_package_price": ep.drg_package_price,
                        "package_code": getattr(ep, "package_code", None),
                        "ek2c_group": ep.ek2c_group,
                        "admission_date": ep.admission_date,
                        "discharge_date": ep.discharge_date,
                        "pricing_status": ep_status,
                        "pricing_date": getattr(ep, "pricing_date", ep.admission_date),
                        "unavailable_reason": ep_unavailable_reason,
                        "required_inputs_missing": ep_required_inputs,
                    }
                )
            if drg_status != "exact" and not drg_required_inputs:
                drg_required_inputs = _ordered_required_inputs(*drg.episodes[:10])
            payload["drg_summary"] = {
                "n_episodes": drg.n_episodes,
                "total_drg_cost": drg.total_drg_cost,
                "mean_episode_cost": drg.mean_episode_cost,
                "most_expensive_drg": drg.most_expensive_drg,
                "dominant_icd10_chapter": drg.dominant_icd10_chapter,
                "total_drg_package_price": drg.total_drg_package_price,
                "fully_priced": getattr(drg, "fully_priced", True),
                "priced_episode_count": getattr(drg, "priced_episode_count", drg.n_episodes),
                "unknown_date_episode_count": getattr(drg, "unknown_date_episode_count", 0),
                "pricing_status": drg_status,
                "unavailable_reason": drg_unavailable_reason,
                "required_inputs_missing": drg_required_inputs,
                "episodes": episode_payloads,
            }
    except Exception as exc:
        logger.warning("DRG computation failed for %s: %s", patient_id, exc)

    complete = not _timed_out()
    return payload, complete
