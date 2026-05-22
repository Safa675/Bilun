"""
Check-up JSON loader helpers for SUT pricing.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from ..constants import CHECKUP_JSON_PATH

logger = logging.getLogger("ilay.sut_catalog")

_checkup_cache: dict[str, Any] | None = None


def _load_checkup_json() -> dict[str, Any]:
    """Load the check-up-specific SUT pricing JSON (37 lab + 22 procedures)."""
    global _checkup_cache
    if _checkup_cache is not None:
        return _checkup_cache

    if not CHECKUP_JSON_PATH.exists():
        logger.warning("Check-up pricing JSON not found: %s", CHECKUP_JSON_PATH)
        _checkup_cache = {}
        return _checkup_cache

    try:
        with open(CHECKUP_JSON_PATH, encoding="utf-8") as f:
            data = json.load(f)
        logger.info(
            "Loaded check-up pricing JSON: %d lab tests, %d procedures, katsayi=%.3f",
            len(data.get("lab_testleri", {})),
            len(data.get("islemler", {})),
            data.get("meta", {}).get("katsayi", 0),
        )
        _checkup_cache = data
        return _checkup_cache
    except (json.JSONDecodeError, OSError) as e:
        logger.warning("Failed to load check-up pricing JSON: %s", e)
        _checkup_cache = {}
        return _checkup_cache


def _build_checkup_lab_index() -> dict[str, dict[str, Any]]:
    """Build SUT code -> lab test entry index from the check-up JSON."""
    data = _load_checkup_json()
    lab_tests = data.get("lab_testleri", {})
    index: dict[str, dict[str, Any]] = {}
    for _key, entry in lab_tests.items():
        code = entry.get("sut_kodu", "")
        if code:
            index[code] = entry
    return index


def _build_checkup_procedure_index() -> dict[str, dict[str, Any]]:
    """Build SUT code -> procedure entry index from the check-up JSON."""
    data = _load_checkup_json()
    procedures = data.get("islemler", {})
    index: dict[str, dict[str, Any]] = {}
    for _key, entry in procedures.items():
        code = entry.get("sut_kodu", "")
        if code:
            index[code] = entry
    return index
