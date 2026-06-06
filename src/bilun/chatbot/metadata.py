"""SUT build and gazette metadata for BILUN chatbot."""

from __future__ import annotations

from typing import Any

CHAT_CONTEXT_SCHEMA_VERSION = "2026-05-23"


def get_chat_model_context(active_build_id: str | None = None) -> dict[str, Any]:
    """Return live SUT metadata for BILUN (no IHP ML artifact references)."""
    return {
        "product": "BILUN",
        "build_id": active_build_id,
        "gazette_version": None,
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
