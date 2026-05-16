"""
src/bilun/domain/materials/exclusions.py
EK-3B-1 bundled consumables and EK-3B-2 non-reimbursable materials.
"""

from __future__ import annotations

import logging
from typing import Any

import pandas as pd

from ..constants import EK3B1_BUNDLED_PATH, EK3B2_NON_REIMBURSABLE_PATH
from ..utils import _safe_str, turkish_lower

logger = logging.getLogger("ilay.sut_catalog")

_EK3B2_CACHE: list[dict[str, Any]] | None = None
_EK3B1_CACHE: list[dict[str, Any]] | None = None


def get_non_reimbursable_materials() -> list[dict[str, Any]]:
    """Get the list of non-reimbursable materials from EK-3B-2.

    Returns:
        List of dicts with keys: sira_no, material_name.
    """
    global _EK3B2_CACHE
    if _EK3B2_CACHE is not None:
        return _EK3B2_CACHE

    if not EK3B2_NON_REIMBURSABLE_PATH.exists():
        logger.warning(
            "EK-3B-2 non-reimbursable catalog not found: %s",
            EK3B2_NON_REIMBURSABLE_PATH,
        )
        _EK3B2_CACHE = []
        return _EK3B2_CACHE

    try:
        df = pd.read_parquet(EK3B2_NON_REIMBURSABLE_PATH)
        records: list[dict[str, Any]] = []
        for _, row in df.iterrows():
            records.append(
                {
                    "sira_no": row.get("sira_no"),
                    "material_name": _safe_str(row.get("material_name")),
                }
            )
        logger.info("EK-3B-2 non-reimbursable materials loaded: %d items", len(records))
        _EK3B2_CACHE = records
        return _EK3B2_CACHE
    except Exception as e:
        logger.warning("Failed to load EK-3B-2 non-reimbursable materials: %s", e)
        _EK3B2_CACHE = []
        return _EK3B2_CACHE


def get_bundled_consumables() -> list[dict[str, Any]]:
    """Get the list of consumables bundled into procedure prices from EK-3B-1.

    Returns:
        List of dicts with keys: sira_no, item_name, description.
    """
    global _EK3B1_CACHE
    if _EK3B1_CACHE is not None:
        return _EK3B1_CACHE

    if not EK3B1_BUNDLED_PATH.exists():
        logger.warning("EK-3B-1 bundled consumables not found: %s", EK3B1_BUNDLED_PATH)
        _EK3B1_CACHE = []
        return _EK3B1_CACHE

    try:
        df = pd.read_parquet(EK3B1_BUNDLED_PATH)
        records: list[dict[str, Any]] = []
        for _, row in df.iterrows():
            records.append(
                {
                    "sira_no": row.get("sira_no"),
                    "item_name": _safe_str(row.get("item_name")),
                    "description": _safe_str(row.get("description")),
                }
            )
        logger.info("EK-3B-1 bundled consumables loaded: %d items", len(records))
        _EK3B1_CACHE = records
        return _EK3B1_CACHE
    except Exception as e:
        logger.warning("Failed to load EK-3B-1 bundled consumables: %s", e)
        _EK3B1_CACHE = []
        return _EK3B1_CACHE


def is_material_reimbursable(material_name: str) -> bool:
    """Check whether a material name appears in EK-3B-2 non-reimbursable list.

    Args:
        material_name: Material name to check.

    Returns:
        True if the material IS reimbursable, False if non-reimbursable.
    """
    exclusions = get_non_reimbursable_materials()
    if not exclusions:
        return True

    needle = turkish_lower(material_name.strip())
    for entry in exclusions:
        mat_name = turkish_lower((entry.get("material_name") or "").strip())
        if not mat_name:
            continue
        if needle in mat_name or mat_name in needle:
            return False
    return True


def is_consumable_bundled(item_name: str) -> bool:
    """Check whether a consumable is bundled into procedure prices (EK-3B-1).

    Args:
        item_name: Consumable name to check.

    Returns:
        True if the consumable IS bundled, False if can be billed separately.
    """
    bundled = get_bundled_consumables()
    if not bundled:
        return False

    needle = turkish_lower(item_name.strip())
    for entry in bundled:
        entry_name = turkish_lower((entry.get("item_name") or "").strip())
        if not entry_name:
            continue
        if needle in entry_name or entry_name in needle:
            return True
    return False