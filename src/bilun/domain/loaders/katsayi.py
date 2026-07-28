"""SUT katsayi (puan → TL) history loader."""

from __future__ import annotations

import json
import logging
from typing import Any

from ..constants import DEFAULT_KATSAYI, KATSAYI_HISTORY_PATH

logger = logging.getLogger("ilay.sut_catalog")

_katsayi_history_cache: dict[str, Any] | None = None


def _load_katsayi_history() -> dict[str, Any]:
    """Load ``sut_katsayi_history.json`` (cached)."""
    global _katsayi_history_cache
    if _katsayi_history_cache is not None:
        return _katsayi_history_cache

    if not KATSAYI_HISTORY_PATH.exists():
        logger.warning("Katsayi history JSON not found: %s", KATSAYI_HISTORY_PATH)
        _katsayi_history_cache = {}
        return _katsayi_history_cache

    try:
        with open(KATSAYI_HISTORY_PATH, encoding="utf-8") as handle:
            data = json.load(handle)
        _katsayi_history_cache = data if isinstance(data, dict) else {}
        return _katsayi_history_cache
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Failed to load katsayi history JSON: %s", exc)
        _katsayi_history_cache = {}
        return _katsayi_history_cache


def resolve_current_katsayi(history: dict[str, Any] | None = None) -> float:
    """Pick the open-ended (or latest) katsayi from history; fallback DEFAULT_KATSAYI."""
    payload = history if history is not None else _load_katsayi_history()
    coefficients = payload.get("coefficients") or []
    if not isinstance(coefficients, list) or not coefficients:
        return DEFAULT_KATSAYI

    current: dict[str, Any] | None = None
    for entry in coefficients:
        if not isinstance(entry, dict):
            continue
        if entry.get("effective_to") is None and entry.get("katsayi") is not None:
            current = entry
            break
    if current is None:
        for entry in reversed(coefficients):
            if isinstance(entry, dict) and entry.get("katsayi") is not None:
                current = entry
                break
    if current is None:
        return DEFAULT_KATSAYI
    try:
        return float(current["katsayi"])
    except (TypeError, ValueError):
        return DEFAULT_KATSAYI
