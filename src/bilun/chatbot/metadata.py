"""SUT build and gazette metadata for BILUN chatbot."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

CHAT_CONTEXT_SCHEMA_VERSION = "2026-05-23"

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_MANIFEST_PATH = _PROJECT_ROOT / "data" / "gazette" / "version_manifest.parquet"


def _read_active_gazette_version() -> str | None:
    """Return the latest effective_date from the gazette manifest, or None.

    The manifest is the source of truth for which SUT tebliği is active.
    Read defensively so a missing/corrupt manifest never breaks the chatbot.
    """
    try:
        df = pd.read_parquet(_MANIFEST_PATH)
        latest = df["effective_date"].max()
        if pd.isna(latest):
            return None
        return str(latest)
    except (FileNotFoundError, OSError, KeyError, ValueError):
        return None


def get_chat_model_context(active_build_id: str | None = None) -> dict[str, Any]:
    """Return live SUT metadata for BILUN (no IHP ML artifact references)."""
    return {
        "product": "BILUN",
        "build_id": active_build_id,
        "gazette_version": _read_active_gazette_version(),
        "claim_dataset": "synthetic_demo",
        "rule_engines": {
            "active": ["copay_exemptions", "temporal_price_validation"],
            "gated": [
                "surcharge_eligibility",
                "copay_rate_eligibility",
                "drg_unbundling",
            ],
        },
        "billing_algorithms": ["lab", "copay", "strategy", "materials"],
    }


def get_missing_context_blocks(
    active_tab: str,
    db_context: dict[str, Any] | None = None,
    model_context: dict[str, Any] | None = None,
    patient_id: str | None = None,
) -> list[str]:
    """Return optional context blocks that are unavailable for the given workspace tab."""
    db_context = db_context or {}
    tab = (active_tab or "").lower()
    missing: list[str] = []

    if "analytics" in tab or "optimizer" in tab:
        if not any(
            db_context.get(key)
            for key in ("optimization_summary", "recovery_summary")
        ):
            missing.append("optimization_summary")

    if "patient" in tab or "billing" in tab:
        if patient_id and not db_context.get("patient_outcome"):
            missing.append("patient_outcome")

    return missing
