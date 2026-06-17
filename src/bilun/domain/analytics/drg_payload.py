"""Serialize and normalize cached DRG analytics payloads for API and cache reads."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from src.bilun.domain.analytics.drg import DRGEpisode, DRGSummary

MISSING_DRG_PRICING_METADATA_REASON = (
    "DRG pricing exactness metadata was not provided by the analytics payload."
)


def required_inputs_from(source: Any) -> list[str]:
    return list(getattr(source, "required_inputs_missing", []) or [])


def ordered_required_inputs(*sources: Any) -> list[str]:
    ordered: list[str] = []
    for source in sources:
        for item in required_inputs_from(source):
            if item not in ordered:
                ordered.append(item)
    return ordered


def pricing_status_from(source: Any) -> tuple[str, str | None, list[str]]:
    """Return pricing status metadata from a DRG dataclass or cached JSON dict."""

    raw_status = getattr(source, "pricing_status", None)
    if raw_status is None and isinstance(source, Mapping):
        raw_status = source.get("pricing_status")
    status = str(raw_status).strip() if raw_status is not None else ""
    if status:
        unavailable_reason = getattr(source, "unavailable_reason", None)
        if unavailable_reason is None and isinstance(source, Mapping):
            unavailable_reason = source.get("unavailable_reason")
        return status, unavailable_reason, required_inputs_from(source)
    return (
        "missing_exact_inputs",
        MISSING_DRG_PRICING_METADATA_REASON,
        ["pricing_status"],
    )


def normalize_cached_pricing_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Backfill explicit unavailable pricing metadata for one summary or episode row."""

    normalized = dict(payload)
    raw_status = normalized.get("pricing_status")
    status = str(raw_status).strip() if raw_status is not None else ""
    if status:
        return normalized
    normalized["pricing_status"] = "missing_exact_inputs"
    normalized["unavailable_reason"] = (
        normalized.get("unavailable_reason") or MISSING_DRG_PRICING_METADATA_REASON
    )
    normalized["required_inputs_missing"] = list(
        normalized.get("required_inputs_missing") or ["pricing_status"]
    )
    return normalized


def serialize_drg_episode(episode: DRGEpisode) -> dict[str, Any]:
    """Serialize one episode for cache/API payloads (see ``DRGEpisodeResponse``)."""

    pricing_status, unavailable_reason, required_inputs_missing = pricing_status_from(episode)
    return {
        "episode_id": episode.episode_id,
        "claim_id": episode.claim_id,
        "primary_icd10": episode.primary_icd10,
        "primary_icd10_chapter": episode.primary_icd10_chapter,
        "description": episode.description,
        "los_days": episode.los_days,
        "lab_cost": episode.lab_cost,
        "visit_cost": episode.visit_cost,
        "rx_cost": episode.rx_cost,
        "procedure_cost": episode.procedure_cost,
        "total_cost": episode.total_cost,
        "drg_package_price": episode.drg_package_price,
        "package_code": episode.package_code,
        "ek2c_group": episode.ek2c_group,
        "admission_date": episode.admission_date,
        "discharge_date": episode.discharge_date,
        "pricing_status": pricing_status,
        "pricing_date": episode.pricing_date or episode.admission_date,
        "unavailable_reason": unavailable_reason,
        "required_inputs_missing": required_inputs_missing,
    }


def serialize_drg_summary(summary: DRGSummary, *, max_episodes: int = 10) -> dict[str, Any]:
    """Serialize a DRG summary for cache/API payloads (see ``DRGSummaryResponse``)."""

    episodes = summary.episodes[:max_episodes]
    pricing_status, unavailable_reason, required_inputs_missing = pricing_status_from(summary)
    if pricing_status != "exact" and not required_inputs_missing:
        required_inputs_missing = ordered_required_inputs(*episodes)
    return {
        "n_episodes": summary.n_episodes,
        "total_drg_cost": summary.total_drg_cost,
        "mean_episode_cost": summary.mean_episode_cost,
        "most_expensive_drg": summary.most_expensive_drg,
        "dominant_icd10_chapter": summary.dominant_icd10_chapter,
        "total_drg_package_price": summary.total_drg_package_price,
        "fully_priced": summary.fully_priced,
        "priced_episode_count": summary.priced_episode_count,
        "unknown_date_episode_count": summary.unknown_date_episode_count,
        "pricing_status": pricing_status,
        "unavailable_reason": unavailable_reason,
        "required_inputs_missing": required_inputs_missing,
        "episodes": [serialize_drg_episode(episode) for episode in episodes],
    }


def normalize_cached_drg_summary_payload(drg_summary: Any) -> Any:
    """Backfill explicit unavailable pricing metadata for stale cache rows."""

    if not isinstance(drg_summary, Mapping):
        return drg_summary
    normalized = normalize_cached_pricing_payload(drg_summary)
    episodes = normalized.get("episodes")
    if isinstance(episodes, list):
        normalized["episodes"] = [
            normalize_cached_pricing_payload(episode)
            if isinstance(episode, Mapping)
            else episode
            for episode in episodes
        ]
    return normalized
