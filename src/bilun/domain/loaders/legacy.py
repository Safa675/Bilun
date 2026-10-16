"""
Fallback/legacy annex loaders used by optimization features.
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Any

import pandas as pd

from ..constants import EK1A_CURATED_PATH, EK2C1_CURATED_PATH, EK2G_CURATED_PATH
from ..labels import normalize_sut_display_text
from .validity import rows_in_force

logger = logging.getLogger("ilay.sut_catalog")

_ek1a_cache: pd.DataFrame | None = None
_ek2g_cache: dict[str, str] | None = None
_ek2c1_cache: dict[str, dict[str, Any]] | None = None


def _load_ek1a_exemptions(as_of: date | str | None = None) -> pd.DataFrame:
    """EK-1A chronic disease ICD-10 exemption ranges in force on ``as_of`` (default today).

    A range SGK added later carries valid_from (e.g. G11.3 from 2018-02-15); others are
    in force on every date.
    """
    return rows_in_force(_load_ek1a_list(), as_of)


def _load_ek1a_list() -> pd.DataFrame:
    """The whole curated EK-1A list (cached)."""
    global _ek1a_cache
    if _ek1a_cache is not None:
        return _ek1a_cache

    if not EK1A_CURATED_PATH.exists():
        logger.warning("EK-1A curated parquet not found: %s", EK1A_CURATED_PATH)
        _ek1a_cache = pd.DataFrame(
            columns=["icd10_start", "icd10_end", "disease_name_tr"]
        )
        return _ek1a_cache

    try:
        _ek1a_cache = pd.read_parquet(EK1A_CURATED_PATH)
        if "disease_name_tr" in _ek1a_cache.columns:
            _ek1a_cache = _ek1a_cache.copy()
            _ek1a_cache["disease_name_tr"] = _ek1a_cache["disease_name_tr"].map(
                normalize_sut_display_text
            )
        logger.info(
            "Loaded EK-1A: %d chronic disease exemption ranges", len(_ek1a_cache)
        )
    except Exception as e:
        logger.warning("Failed to load EK-1A: %s", e)
        _ek1a_cache = pd.DataFrame(
            columns=["icd10_start", "icd10_end", "disease_name_tr"]
        )
    return _ek1a_cache


def _load_ek2g_no_surcharge() -> dict[str, str]:
    """Load EK-2G procedures where additional fees are prohibited."""
    global _ek2g_cache
    if _ek2g_cache is not None:
        return _ek2g_cache

    if not EK2G_CURATED_PATH.exists():
        logger.warning("EK-2G curated parquet not found: %s", EK2G_CURATED_PATH)
        _ek2g_cache = {}
        return _ek2g_cache

    try:
        df = pd.read_parquet(EK2G_CURATED_PATH)
        _ek2g_cache = dict(zip(df["procedure_code"], df["procedure_name"]))
        logger.info("Loaded EK-2G: %d no-surcharge procedures", len(_ek2g_cache))
    except Exception as e:
        logger.warning("Failed to load EK-2G: %s", e)
        _ek2g_cache = {}
    return _ek2g_cache


def _load_ek2c1_copay_rates() -> dict[str, dict[str, Any]]:
    """Load EK-2C-1 procedures with explicit copayment rate percentages."""
    global _ek2c1_cache
    if _ek2c1_cache is not None:
        return _ek2c1_cache

    if not EK2C1_CURATED_PATH.exists():
        logger.warning("EK-2C-1 curated parquet not found: %s", EK2C1_CURATED_PATH)
        _ek2c1_cache = {}
        return _ek2c1_cache

    try:
        df = pd.read_parquet(EK2C1_CURATED_PATH)
        _ek2c1_cache = {
            row["procedure_code"]: {
                "procedure_name": row["procedure_name"],
                "copay_rate_pct": float(row["copay_rate_pct"]),
            }
            for _, row in df.iterrows()
        }
        logger.info("Loaded EK-2C-1: %d procedures with copay rates", len(_ek2c1_cache))
    except Exception as e:
        logger.warning("Failed to load EK-2C-1: %s", e)
        _ek2c1_cache = {}
    return _ek2c1_cache
