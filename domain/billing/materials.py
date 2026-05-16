"""
src/bilun/domain/billing/materials.py
Algorithm 5: Material reimbursability pre-check with EK-3C-1/3C-2 rules.
"""

from __future__ import annotations

import logging
from typing import Any

import pandas as pd

from ..constants import _GAZETTE_CURATED_DIR
from ..materials import get_all_specialty_materials
from .types import MaterialPreCheck

logger = logging.getLogger("ilay.sut_billing_optimizer")

_CHAPTER_TO_SPECIALTY: dict[str, list[str]] = {
    "I": ["EK-3H", "EK-3I", "EK-3M"],
    "C": ["EK-3O"],
    "M": ["EK-3F-1", "EK-3F-2", "EK-3F-3", "EK-3F-4"],
    "H": ["EK-3G", "EK-3J"],
    "G": ["EK-3E-1", "EK-3E-2"],
    "J": ["EK-3S"],
    "K": ["EK-3R"],
    "N": ["EK-3L", "EK-3K", "EK-3P"],
    "D": ["EK-3O"],
}

_specialty_price_stats: dict[str, dict[str, Any]] | None = None
_ek3c1_preauth: list[dict[str, Any]] | None = None
_ek3c2_miat: list[dict[str, Any]] | None = None


def _get_specialty_price_stats() -> dict[str, dict[str, Any]]:
    """Compute per-specialty price statistics from EK-3 materials."""
    global _specialty_price_stats
    if _specialty_price_stats is not None:
        return _specialty_price_stats

    all_mats = get_all_specialty_materials()
    by_source: dict[str, list[float]] = {}
    for mat in all_mats:
        src = mat.get("source", "")
        price = mat.get("price_try", 0.0)
        if src and price and price > 0:
            by_source.setdefault(src, []).append(price)

    stats: dict[str, dict[str, Any]] = {}
    for src, prices in by_source.items():
        if not prices:
            continue
        sp = sorted(prices)
        n = len(sp)
        stats[src] = {
            "n_materials": n,
            "p10": round(sp[max(0, int(n * 0.10))], 2),
            "p50": round(sp[n // 2], 2),
            "p90": round(sp[min(n - 1, int(n * 0.90))], 2),
            "max": round(sp[-1], 2),
        }

    _specialty_price_stats = stats
    return _specialty_price_stats


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
        df = pd.read_parquet(path)
        items = []
        for _, row in df.iterrows():
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
        df = pd.read_parquet(path)
        items = []
        for _, row in df.iterrows():
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


def _precheck_materials(
    patient_id: str,
    chapters: set[str],
) -> MaterialPreCheck:
    """Algorithm 5: Material reimbursability pre-check based on diagnosis profile.

    Args:
        patient_id: Patient identifier.
        chapters: Set of ICD-10 chapter letters.

    Returns:
        MaterialPreCheck with pre-auth flags, MIAT warnings, and gazette ceilings.
    """
    result = MaterialPreCheck()

    if not chapters:
        return result

    relevant_specialties: set[str] = set()
    for ch in chapters:
        specs = _CHAPTER_TO_SPECIALTY.get(ch.upper(), [])
        relevant_specialties.update(specs)

    if not relevant_specialties:
        return result

    specialty_stats = _get_specialty_price_stats()
    for spec in sorted(relevant_specialties):
        stats = specialty_stats.get(spec)
        if stats:
            result.gazette_ceiling_by_specialty[spec] = stats["p90"]

    ek3c1_items = _get_ek3c1_preauth()
    if ek3c1_items:
        for item in ek3c1_items[:20]:
            result.pre_auth_required.append(
                {
                    "sut_code": item["sut_code"],
                    "material_name": item["material_name"],
                    "price_try": item.get("price_try", 0.0),
                    "note": "Requires medical board (sağlık kurulu) approval before SGK submission",
                }
            )
        result.pre_auth_required = result.pre_auth_required[:5]

    miat_items = _get_ek3c2_miat()
    if miat_items:
        for item in miat_items[:10]:
            result.miat_restricted.append(
                {
                    "sut_code": item["sut_code"],
                    "material_name": item["material_name"],
                    "miat_period": item.get("miat_period", ""),
                    "price_try": item.get("price_try", 0.0),
                    "note": f"Minimum time between uses: {item.get('miat_period', 'N/A')}",
                }
            )
        result.miat_restricted = result.miat_restricted[:5]

    return result