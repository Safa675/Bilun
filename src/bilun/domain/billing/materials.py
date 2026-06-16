"""
EK-3C catalog loaders shared by claim-line material precheck.
"""

from __future__ import annotations

import logging
from typing import Any

import polars as pl

from ..constants import _GAZETTE_CURATED_DIR

logger = logging.getLogger("ilay.sut_billing_optimizer")

_ek3c1_preauth: list[dict[str, Any]] | None = None
_ek3c2_miat: list[dict[str, Any]] | None = None


def _get_ek3c1_preauth() -> list[dict[str, Any]]:
    """Load EK-3C-1 materials requiring medical board pre-authorization."""
    global _ek3c1_preauth
    if _ek3c1_preauth is not None:
        return _ek3c1_preauth

    path = _GAZETTE_CURATED_DIR / "ek3c1_materials.parquet"
    if not path.exists():
        logger.debug("EK-3C-1 parquet not found: %s", path)
        _ek3c1_preauth = []
        return _ek3c1_preauth

    try:
        df = pl.read_parquet(path)
        items = []
        for row in df.iter_rows(named=True):
            items.append(
                {
                    "sut_code": str(row.get("sut_code", "")).strip(),
                    "material_name": str(row.get("material_name", "")).strip(),
                    "price_try": float(row.get("price_try", 0.0))
                    if row.get("price_try")
                    else 0.0,
                }
            )
        _ek3c1_preauth = items
        logger.info("EK-3C-1 pre-auth items loaded: %d", len(items))
    except Exception as e:
        logger.warning("Failed to load EK-3C-1: %s", e)
        _ek3c1_preauth = []

    return _ek3c1_preauth


def _get_ek3c2_miat() -> list[dict[str, Any]]:
    """Load EK-3C-2 materials with MIAT period restrictions."""
    global _ek3c2_miat
    if _ek3c2_miat is not None:
        return _ek3c2_miat

    path = _GAZETTE_CURATED_DIR / "ek3c2_materials.parquet"
    if not path.exists():
        logger.debug("EK-3C-2 parquet not found: %s", path)
        _ek3c2_miat = []
        return _ek3c2_miat

    try:
        df = pl.read_parquet(path)
        items = []
        for row in df.iter_rows(named=True):
            miat = row.get("miat_period") or row.get("miat") or ""
            if miat and str(miat) not in ("", "nan", "None"):
                items.append(
                    {
                        "sut_code": str(row.get("sut_code", "")).strip(),
                        "material_name": str(row.get("material_name", "")).strip(),
                        "miat_period": str(miat).strip(),
                        "price_try": float(row.get("price_try", 0.0))
                        if row.get("price_try")
                        else 0.0,
                    }
                )
        _ek3c2_miat = items
        logger.info("EK-3C-2 MIAT-restricted items loaded: %d", len(items))
    except Exception as e:
        logger.warning("Failed to load EK-3C-2 MIAT items: %s", e)
        _ek3c2_miat = []

    return _ek3c2_miat
