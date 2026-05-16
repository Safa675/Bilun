"""
src/bilun/domain/materials/cardiac.py
EK-3H and EK-3I cardiac materials.
"""

from __future__ import annotations

import logging
from typing import Any

from ..loaders import get_cached_ek3h, get_cached_ek3i

logger = logging.getLogger("ilay.sut_catalog")


def get_ek3_cardiology_materials() -> list[dict[str, Any]]:
    """Get EK-3H cardiology material pricing (cached, from curated parquet)."""
    return get_cached_ek3h()


def get_ek3_cv_surgery_materials() -> list[dict[str, Any]]:
    """Get EK-3I cardiovascular surgery material pricing (cached, from curated parquet)."""
    return get_cached_ek3i()


def get_cardiac_material_price_range() -> tuple[float, float]:
    """Get min/max material prices for cardiac patients (EK-3H + EK-3I).

    Returns (min_price, max_price) for typical cardiac materials.
    Uses stents and valve prostheses as representative range.
    """
    all_materials = get_ek3_cardiology_materials() + get_ek3_cv_surgery_materials()
    if not all_materials:
        return (500.0, 8000.0)

    prices = [m["price_try"] for m in all_materials if m.get("price_try", 0) > 0]
    if not prices:
        return (500.0, 8000.0)

    sorted_prices = sorted(prices)
    n = len(sorted_prices)
    p10 = sorted_prices[max(0, int(n * 0.10))]
    p90 = sorted_prices[min(n - 1, int(n * 0.90))]
    return (round(p10, 2), round(p90, 2))