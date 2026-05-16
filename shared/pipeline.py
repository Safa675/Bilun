"""BILUN pipeline helpers — DRG payload normalization.

Extracted from ILAY's src/api/pipeline.py for standalone BILUN use.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

_MISSING_DRG_PRICING_METADATA_REASON = (
    "DRG pricing exactness metadata was not provided by the BILUN payload."
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
