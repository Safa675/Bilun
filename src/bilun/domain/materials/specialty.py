"""
src/bilun/domain/materials/specialty.py
All EK-3 specialty materials (EK-3A through EK-3T).
"""

from __future__ import annotations

import logging
from typing import Any

from ..constants import _EK3_SPECIALTY_CATALOGS, _GAZETTE_CURATED_DIR
from ..loaders import _load_ek3_materials_parquet
from .cardiac import get_ek3_cardiology_materials, get_ek3_cv_surgery_materials

logger = logging.getLogger("ilay.sut_catalog")

_all_specialty_cache: list[dict[str, Any]] | None = None


def get_all_specialty_materials() -> list[dict[str, Any]]:
    """Load ALL curated EK-3 specialty material catalogs (cached).

    Combines EK-3H, EK-3I with all newly curated specialty catalogs.

    Returns:
        List of material dicts with keys: sut_code, material_name, description,
        price_try, category, source.
    """
    global _all_specialty_cache
    if _all_specialty_cache is not None:
        return _all_specialty_cache

    all_materials = list(get_ek3_cardiology_materials())
    all_materials.extend(get_ek3_cv_surgery_materials())

    for annex_label, (filename, desc) in _EK3_SPECIALTY_CATALOGS.items():
        path = _GAZETTE_CURATED_DIR / filename
        materials = _load_ek3_materials_parquet(path, annex_label)
        if materials:
            all_materials.extend(materials)

    logger.info(
        "All specialty materials loaded: %d items across %d+ annexes",
        len(all_materials),
        2 + len(_EK3_SPECIALTY_CATALOGS),
    )
    _all_specialty_cache = all_materials
    return _all_specialty_cache