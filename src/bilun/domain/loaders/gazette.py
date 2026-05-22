"""
Gazette and curated-parquet loader helpers for SUT pricing.
"""

from __future__ import annotations

import logging
import math
from pathlib import Path
from typing import Any

import pandas as pd

from ..constants import (
    EK2A_PARQUET_PATH,
    EK2B_CURATED_HISTORY_PATH,
    EK2B_PARQUET_PATH,
    EK2C_CURATED_HISTORY_PATH,
    EK3H_PARQUET_PATH,
    EK3I_PARQUET_PATH,
    _OLD_TO_NEW_CODE,
)
from ..utils import _safe_float, _safe_str

logger = logging.getLogger("ilay.sut_catalog")

_parquet_by_code: dict[str, dict[str, Any]] = {}
_parquet_loaded: bool = False

_ek2a_cache: dict[str, Any] | None = None
_ek3h_cache: list[dict[str, Any]] | None = None
_ek3i_cache: list[dict[str, Any]] | None = None


def _load_parquet_ek2b() -> dict[str, dict[str, Any]]:
    """Load the compiled EK-2B parquet file into a code -> entry dict."""
    global _parquet_by_code, _parquet_loaded
    if _parquet_loaded:
        return _parquet_by_code

    if not EK2B_PARQUET_PATH.exists():
        logger.warning("EK-2B parquet not found: %s", EK2B_PARQUET_PATH)
        _parquet_loaded = True
        return _parquet_by_code

    try:
        df = pd.read_parquet(EK2B_PARQUET_PATH)
        by_code: dict[str, dict[str, Any]] = {}
        for _, row in df.iterrows():
            code = str(row.get("ISLEM_KODU", "")).strip()
            if not code:
                continue
            name = str(row.get("ISLEM_ADI", "")).strip() or None
            desc_val = row.get("ACIKLAMA")
            description = str(desc_val).strip() if pd.notna(desc_val) else None
            puan = _safe_float(row.get("ISLEM_PUANI"))
            price = _safe_float(row.get("ISLEM_BEDELI_TL"))
            if name and price is not None:
                by_code[code] = {
                    "code": code,
                    "name": name,
                    "description": description,
                    "puan": puan,
                    "price_try": round(price, 2),
                }
        logger.info(
            "Loaded EK-2B parquet: %d procedures (price range %.2f-%.2f TRY)",
            len(by_code),
            min(e["price_try"] for e in by_code.values()) if by_code else 0,
            max(e["price_try"] for e in by_code.values()) if by_code else 0,
        )
        _parquet_by_code = by_code
        _parquet_loaded = True
        return _parquet_by_code
    except Exception as e:
        logger.warning("Failed to load EK-2B parquet: %s", e)
        _parquet_by_code = {}
        _parquet_loaded = True
        return _parquet_by_code


def _load_curated_ek2b_by_asof(asof_date: str) -> dict[str, dict[str, Any]]:
    """Load EK-2B entries from curated history table filtered as-of date."""
    if not EK2B_CURATED_HISTORY_PATH.exists():
        return {}

    df = pd.read_parquet(EK2B_CURATED_HISTORY_PATH)
    if df.empty:
        return {}

    df = df.copy()
    df["effective_date_parsed"] = pd.to_datetime(df["effective_date"], errors="coerce")
    cutoff = pd.to_datetime(asof_date)
    df = df[df["effective_date_parsed"].notna()]
    eligible = df[df["effective_date_parsed"] <= cutoff]
    if eligible.empty:
        eligible = df.sort_values(["code", "effective_date_parsed"]).drop_duplicates(
            subset=["code"], keep="first"
        )
    else:
        eligible = eligible.sort_values(
            ["code", "effective_date_parsed"]
        ).drop_duplicates(subset=["code"], keep="last")

    by_code: dict[str, dict[str, Any]] = {}
    for _, row in eligible.iterrows():
        code = str(row.get("code", "")).strip()
        if not code:
            continue
        entry = {
            "code": code,
            "name": _safe_str(row.get("name")),
            "description": _safe_str(row.get("description")),
            "puan": _safe_float(row.get("puan")),
            "price_try": _safe_float(row.get("price_try")),
            "effective_date": _safe_str(row.get("effective_date")),
        }
        if entry["name"] and entry["price_try"] is not None:
            entry["price_try"] = round(float(entry["price_try"]), 2)
            by_code[code] = entry

    for old_code, new_code in _OLD_TO_NEW_CODE.items():
        if new_code in by_code and old_code not in by_code:
            by_code[old_code] = by_code[new_code]

    return by_code


def _load_curated_ek2c_by_asof(asof_date: str) -> dict[str, Any]:
    """Load EK-2C packages from curated history table filtered as-of date."""
    if not EK2C_CURATED_HISTORY_PATH.exists():
        return {
            "packages": [],
            "by_code": {},
            "group_stats": {},
            "stats": {"total_packages": 0},
        }

    df = pd.read_parquet(EK2C_CURATED_HISTORY_PATH)
    if df.empty:
        return {
            "packages": [],
            "by_code": {},
            "group_stats": {},
            "stats": {"total_packages": 0},
        }

    df = df.copy()
    df["effective_date_parsed"] = pd.to_datetime(df["effective_date"], errors="coerce")
    cutoff = pd.to_datetime(asof_date)
    df = df[df["effective_date_parsed"].notna()]
    eligible = df[df["effective_date_parsed"] <= cutoff]
    if eligible.empty:
        eligible = df.sort_values(
            ["package_code", "effective_date_parsed"]
        ).drop_duplicates(subset=["package_code"], keep="first")
    else:
        eligible = eligible.sort_values(
            ["package_code", "effective_date_parsed"]
        ).drop_duplicates(subset=["package_code"], keep="last")

    packages: list[dict[str, Any]] = []
    by_code: dict[str, dict[str, Any]] = {}
    for _, row in eligible.iterrows():
        code = str(row.get("package_code", "")).strip()
        name = _safe_str(row.get("name"))
        price = _safe_float(row.get("price_try"))
        if not code or not name or price is None:
            continue
        entry = {
            "package_code": code,
            "name": name,
            "description": _safe_str(row.get("description")),
            "group": _safe_str(row.get("group")),
            "puan": _safe_float(row.get("puan")),
            "price_try": round(float(price), 2),
            "effective_date": _safe_str(row.get("effective_date")),
        }
        packages.append(entry)
        by_code[code] = entry

    group_stats: dict[str, dict[str, Any]] = {}
    for pkg in packages:
        grp = pkg["group"] or "unknown"
        group_stats.setdefault(grp, {"count": 0, "prices": []})
        group_stats[grp]["count"] += 1
        group_stats[grp]["prices"].append(pkg["price_try"])

    for grp, gs in group_stats.items():
        prices = gs.pop("prices")
        gs["price_min"] = round(min(prices), 2)
        gs["price_max"] = round(max(prices), 2)
        gs["price_mean"] = round(sum(prices) / len(prices), 2)

    all_prices = [p["price_try"] for p in packages]
    stats = {
        "total_packages": len(packages),
        "unique_groups": sorted(group_stats.keys()),
        "price_min": round(min(all_prices), 2) if all_prices else 0,
        "price_max": round(max(all_prices), 2) if all_prices else 0,
        "price_mean": round(sum(all_prices) / len(all_prices), 2) if all_prices else 0,
    }

    return {
        "packages": packages,
        "by_code": by_code,
        "group_stats": group_stats,
        "stats": stats,
    }


def _load_ek2a() -> dict[str, Any]:
    """Load EK-2A outpatient visit pricing by specialty from curated parquet."""
    if not EK2A_PARQUET_PATH.exists():
        logger.warning("EK-2A curated parquet not found: %s", EK2A_PARQUET_PATH)
        return {}
    try:
        df = pd.read_parquet(EK2A_PARQUET_PATH)
        specialties: list[dict[str, Any]] = []

        for _, row in df.iterrows():
            code = str(row.get("specialty_code", "")).strip()
            name = str(row.get("specialty_name", "")).strip()
            if not code or not name:
                continue
            prices_try: dict[str, float] = {}
            for col in [
                "OH3",
                "U1",
                "U2",
                "A1",
                "A1_DAL",
                "A2",
                "A2_DAL",
                "B",
                "C",
                "OH2",
                "D",
                "E",
                "KTM",
                "KDM",
                "OTM",
                "ODM",
            ]:
                val = row.get(col)
                if val is not None and not (isinstance(val, float) and math.isnan(val)):
                    try:
                        prices_try[col] = float(val)
                    except (ValueError, TypeError):
                        pass
            specialties.append(
                {
                    "code": code,
                    "name": name,
                    "section": str(row.get("section", "")).strip(),
                    "prices_try": prices_try,
                }
            )
        logger.info("EK-2A loaded from parquet: %d specialties", len(specialties))
        return {"specialties": specialties}
    except Exception as e:
        logger.warning("Could not load EK-2A parquet: %s", e)
        return {}


def _load_ek3_materials_parquet(path: Path, label: str) -> list[dict[str, Any]]:
    """Load EK-3H/3I medical material pricing from curated parquet."""
    if not path.exists():
        logger.warning("%s curated parquet not found: %s", label, path)
        return []
    try:
        df = pd.read_parquet(path)
        materials: list[dict[str, Any]] = []
        for _, row in df.iterrows():
            code = str(row.get("sut_code", "")).strip()
            name = str(row.get("material_name", "")).strip()
            price = _safe_float(row.get("price_try"))
            if not name:
                continue
            materials.append(
                {
                    "sut_code": code,
                    "material_name": name,
                    "name": name,
                    "description": str(row.get("description", "")).strip(),
                    "price_try": price if price is not None else 0.0,
                    "category": str(row.get("category", "")).strip(),
                    "source": label,
                }
            )
        logger.info("%s loaded from parquet: %d materials", label, len(materials))
        return materials
    except Exception as e:
        logger.warning("Could not load %s parquet: %s", label, e)
        return []


def get_cached_ek2a() -> dict[str, Any]:
    """Get EK-2A data (cached)."""
    global _ek2a_cache
    if _ek2a_cache is None:
        _ek2a_cache = _load_ek2a()
    return _ek2a_cache


def get_cached_ek3h() -> list[dict[str, Any]]:
    """Get EK-3H cardiology materials (cached)."""
    global _ek3h_cache
    if _ek3h_cache is None:
        _ek3h_cache = _load_ek3_materials_parquet(EK3H_PARQUET_PATH, "EK-3H")
    return _ek3h_cache


def get_cached_ek3i() -> list[dict[str, Any]]:
    """Get EK-3I CV surgery materials (cached)."""
    global _ek3i_cache
    if _ek3i_cache is None:
        _ek3i_cache = _load_ek3_materials_parquet(EK3I_PARQUET_PATH, "EK-3I")
    return _ek3i_cache


def _load_gazette_lab_prices(
    fallback: dict[str, tuple[float, float]],
) -> dict[str, tuple[float, float]]:
    """Load real SUT gazette lab prices. Falls back to representative ranges."""
    try:
        from ..catalog import get_all_lab_prices

        gazette_prices = get_all_lab_prices()
        if gazette_prices:
            result: dict[str, tuple[float, float]] = {}
            for name, price in gazette_prices.items():
                result[name] = (price, price)
            logger.info(
                "Loaded %d real gazette lab prices (e.g. CRP=%.2f TRY)",
                len(result),
                gazette_prices.get("CRP", 0),
            )
            return result
    except Exception as e:
        logger.warning("Failed to load gazette lab prices, using fallback: %s", e)
    return fallback.copy()


def _load_gazette_visit_prices(
    fallback: dict[str, tuple[float, float]],
) -> dict[str, tuple[float, float]]:
    """Load real SUT gazette visit/bed prices. Falls back to representative ranges."""
    try:
        from ..catalog import get_visit_prices

        gazette = get_visit_prices()
        if gazette:
            result: dict[str, tuple[float, float]] = {}
            op = gazette.get("outpatient_visit")
            if op:
                result["outpatient"] = (op, op)
            bed = gazette.get("standard_bed")
            if bed:
                result["inpatient_day"] = (bed, bed)
            icu = gazette.get("icu")
            if icu:
                result["icu_day"] = (icu, icu)
            er = gazette.get("emergency_visit")
            if er:
                result["emergency"] = (er, er)
            fu = gazette.get("primary_care_visit")
            if fu:
                result["follow_up"] = (fu, fu)
            if result:
                logger.info("Loaded %d gazette visit prices", len(result))
                for k, v in fallback.items():
                    if k not in result:
                        result[k] = v
                return result
    except Exception as e:
        logger.warning("Failed to load gazette visit prices, using fallback: %s", e)
    return fallback.copy()
