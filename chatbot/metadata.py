"""Artifact-driven metadata helpers for BILUN chatbot.

Stripped of IHP-specific EBM artifact lookups.
"""

from __future__ import annotations

import hashlib
import json
import logging
from typing import Any

logger = logging.getLogger("bilun.chatbot")

CHAT_CONTEXT_SCHEMA_VERSION = "2026-04-13"


def get_chat_model_context(active_build_id: str | None = None) -> dict[str, Any]:
    """Return live chat metadata for BILUN (no IHP EBM artifacts)."""
    return {
        "build_id": active_build_id,
        "engine": None,
        "target": None,
        "created_at": None,
        "training_auc": None,
        "training_pr_auc": None,
        "training_brier": None,
        "n_features": None,
        "n_samples": None,
        "n_folds": None,
        "n_subscores": 0,
        "subscores": [],
    }


def has_active_model(model_context: dict[str, Any] | None) -> bool:
    return bool((model_context or {}).get("engine"))


def has_performance_metrics(model_context: dict[str, Any] | None) -> bool:
    model_context = model_context or {}
    return all(
        model_context.get(key) is not None
        for key in ("training_auc", "training_pr_auc", "training_brier")
    )


def get_missing_context_blocks(
    active_tab: str,
    db_context: dict[str, Any] | None = None,
    model_context: dict[str, Any] | None = None,
    patient_id: str | None = None,
) -> list[str]:
    """Return optional context blocks that are unavailable for the given tab."""
    db_context = db_context or {}
    model_context = model_context or get_chat_model_context()
    tab = (active_tab or "").lower()
    missing: list[str] = []

    if not has_active_model(model_context):
        missing.append("active_model")

    if "performance" in tab or "validation" in tab:
        if not has_performance_metrics(model_context):
            missing.append("performance_metrics")

    if "causal" in tab and not db_context.get("causal_drivers"):
        missing.append("causal_drivers")

    if "optimizer" in tab:
        if not any(
            db_context.get(key)
            for key in (
                "optimization_summary",
                "recovery_summary",
                "patient_alerts_summary",
            )
        ):
            missing.append("optimizer_summary")

    return missing


def build_smart_notes_cache_fingerprint(
    build_id: str | None,
    model_context: dict[str, Any] | None = None,
) -> str:
    """Fingerprint smart-notes context so stale payloads are never reused."""
    model_context = model_context or get_chat_model_context(build_id)
    payload = {
        "schema_version": CHAT_CONTEXT_SCHEMA_VERSION,
        "build_id": build_id,
        "engine": model_context.get("engine"),
        "target": model_context.get("target"),
        "created_at": model_context.get("created_at"),
        "n_features": model_context.get("n_features"),
        "subscore_names": [
            item.get("name")
            for item in model_context.get("subscores", [])
            if item.get("name")
        ],
    }
    encoded = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()
