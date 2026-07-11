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
    EK2C_CURATED_HISTORY_PATH,
    EK2C_DENTAL_CURATED_HISTORY_PATH,
    EK3H_PARQUET_PATH,
    EK3I_PARQUET_PATH,
    _EK2C_DENTAL_XLS_FALLBACK,
    _OLD_TO_NEW_CODE,
)
from ..utils import _safe_float, _safe_str

logger = logging.getLogger("ilay.sut_catalog")

_ek2a_cache: dict[str, Any] | None = None
_ek3h_cache: list[dict[str, Any]] | None = None
_ek3i_cache: list[dict[str, Any]] | None = None

# The curated history parquets never change within a process. Read each once,
# keep the parsed+filtered-by-date result in a per-asof_date cache so the 80+
# distinct procedure dates in a cohort don't re-read + re-filter the same 62k
# rows every call. Profiled: iterrows over ek2b was 0.887s/call × 87 dates.
_ek2b_raw_cache: pd.DataFrame | None = None
_ek2b_by_asof_cache: dict[str, dict[str, dict[str, Any]]] = {}
_ek2c_raw_cache: pd.DataFrame | None = None
_ek2c_by_asof_cache: dict[str, dict[str, Any]] = {}
# EK-2Ç dental procedures. Temporal filtering mirrors EK-2B (effective_date).
_ek2c_dental_raw_cache: pd.DataFrame | None = None
_ek2c_dental_by_asof_cache: dict[str, dict[str, dict[str, Any]]] = {}


def _load_curated_ek2b_by_asof(asof_date: str) -> dict[str, dict[str, Any]]:
    """Load EK-2B entries from curated history table filtered as-of date."""
    cached = _ek2b_by_asof_cache.get(asof_date)
    if cached is not None:
        return cached
    if not EK2B_CURATED_HISTORY_PATH.exists():
        return {}

    global _ek2b_raw_cache
    if _ek2b_raw_cache is None:
        _ek2b_raw_cache = pd.read_parquet(EK2B_CURATED_HISTORY_PATH)
    df = _ek2b_raw_cache
    if df.empty:
        return {}

    # Parse effective_date once on first load and stash on the cached frame so
    # every date-variant reuses the parsed column instead of re-parsing.
    if "effective_date_parsed" not in df.columns:
        df = df.copy()
        df["effective_date_parsed"] = pd.to_datetime(df["effective_date"], errors="coerce")
        _ek2b_raw_cache = df

    cutoff = pd.to_datetime(asof_date)
    parsed = df[df["effective_date_parsed"].notna()]
    eligible = parsed[parsed["effective_date_parsed"] <= cutoff]
    if eligible.empty:
        eligible = parsed.sort_values(["code", "effective_date_parsed"]).drop_duplicates(
            subset=["code"], keep="first"
        )
    else:
        eligible = eligible.sort_values(
            ["code", "effective_date_parsed"]
        ).drop_duplicates(subset=["code"], keep="last")

    # Vectorized dict construction (to_dict) — ~6.5× faster than iterrows for
    # 62k rows, and avoids per-row Series allocation.
    records = eligible.to_dict(orient="records")
    by_code: dict[str, dict[str, Any]] = {}
    for row in records:
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

    _ek2b_by_asof_cache[asof_date] = by_code
    return by_code


def _load_curated_ek2c_by_asof(asof_date: str) -> dict[str, Any]:
    """Load EK-2C packages from curated history table filtered as-of date."""
    cached = _ek2c_by_asof_cache.get(asof_date)
    if cached is not None:
        return cached
    if not EK2C_CURATED_HISTORY_PATH.exists():
        return {
            "packages": [],
            "by_code": {},
            "group_stats": {},
            "stats": {"total_packages": 0},
        }

    global _ek2c_raw_cache
    if _ek2c_raw_cache is None:
        _ek2c_raw_cache = pd.read_parquet(EK2C_CURATED_HISTORY_PATH)
    df = _ek2c_raw_cache
    if df.empty:
        return {
            "packages": [],
            "by_code": {},
            "group_stats": {},
            "stats": {"total_packages": 0},
        }

    if "effective_date_parsed" not in df.columns:
        df = df.copy()
        df["effective_date_parsed"] = pd.to_datetime(df["effective_date"], errors="coerce")
        _ek2c_raw_cache = df

    cutoff = pd.to_datetime(asof_date)
    parsed = df[df["effective_date_parsed"].notna()]
    eligible = parsed[parsed["effective_date_parsed"] <= cutoff]
    if eligible.empty:
        eligible = parsed.sort_values(
            ["package_code", "effective_date_parsed"]
        ).drop_duplicates(subset=["package_code"], keep="first")
    else:
        eligible = eligible.sort_values(
            ["package_code", "effective_date_parsed"]
        ).drop_duplicates(subset=["package_code"], keep="last")

    records = eligible.to_dict(orient="records")
    packages: list[dict[str, Any]] = []
    by_code: dict[str, dict[str, Any]] = {}
    for row in records:
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

    result = {
        "packages": packages,
        "by_code": by_code,
        "group_stats": group_stats,
        "stats": stats,
    }
    _ek2c_by_asof_cache[asof_date] = result
    return result


def _read_ek2c_dental_frame() -> pd.DataFrame | None:
    """Read the EK-2Ç dental catalog, preferring the curated parquet.

    Falls back to the raw ``.xls`` workbook when the curated parquet has not
    been built yet (keeps ``lookup_procedure_code`` working on a fresh
    checkout that has the raw data but hasn't run the full ETL). The fallback
    path returns a single-version snapshot stamped with the workbook's
    effective date (parsed from the filename) or today's date.
    """
    if EK2C_DENTAL_CURATED_HISTORY_PATH.exists():
        return pd.read_parquet(EK2C_DENTAL_CURATED_HISTORY_PATH)

    if not _EK2C_DENTAL_XLS_FALLBACK.exists():
        return None

    try:
        import re as _re

        import pandas as _pd

        raw = _pd.read_excel(_EK2C_DENTAL_XLS_FALLBACK, engine="xlrd")
        # Header row is the first row (İŞLEM KODU / İŞLEM ADI / ...).
        header = raw.iloc[0].fillna("").astype(str).str.strip().tolist()
        # Build position map for the known columns.
        pos: dict[str, int] = {}
        for i, label in enumerate(header):
            key = label.upper()
            pos.setdefault(key, i)
        code_col = pos.get("İŞLEM KODU".upper()) or pos.get("ISLEM KODU")
        # The .xls header is in Turkish casing; fall back to positional columns
        # (the dental sheet is a fixed 4-column layout: code/name/notes/puan).
        if code_col is None:
            code_col, name_col, puan_col = 0, 1, 3
        else:
            name_col = pos.get("İŞLEM ADI".upper()) or pos.get("ISLEM ADI") or 1
            puan_col = pos.get("İŞLEM PUANI".upper()) or pos.get("ISLEM PUANI") or 3

        body = raw.iloc[1:].reset_index(drop=True)
        out = _pd.DataFrame()
        out["code"] = body.iloc[:, code_col].apply(
            lambda x: _re.sub(r"\s*\(.*$", "", str(x)).strip() if _pd.notna(x) else ""
        )
        out["name"] = body.iloc[:, name_col].apply(
            lambda x: str(x).strip() if _pd.notna(x) else ""
        )
        out["puan"] = _pd.to_numeric(body.iloc[:, puan_col], errors="coerce")
        out = out.dropna(subset=["puan"])
        out = out[out["code"].str.match(r"^P?40\d{4}$", na=False)]
        # SUT puan→TRY coefficient (kept in sync with price_history.py).
        out["price_try"] = (out["puan"] * 0.593).round(2)
        out["effective_date"] = "2026-01-01"  # filename: Yür.01.01.2026
        return out.reset_index(drop=True)[
            ["code", "name", "puan", "price_try", "effective_date"]
        ]
    except Exception as exc:  # pragma: no cover - defensive fallback
        logger.warning("EK-2Ç .xls fallback parse failed: %s", exc)
        return None


def _load_curated_ek2c_dental_by_asof(asof_date: str) -> dict[str, dict[str, Any]]:
    """Load EK-2Ç dental entries from curated history (or .xls fallback), as-of date."""
    cached = _ek2c_dental_by_asof_cache.get(asof_date)
    if cached is not None:
        return cached

    global _ek2c_dental_raw_cache
    if _ek2c_dental_raw_cache is None:
        _ek2c_dental_raw_cache = _read_ek2c_dental_frame()
    df = _ek2c_dental_raw_cache
    if df is None or df.empty:
        return {}

    work = df
    if "effective_date" in work.columns:
        if "effective_date_parsed" not in work.columns:
            work = work.copy()
            work["effective_date_parsed"] = pd.to_datetime(
                work["effective_date"], errors="coerce"
            )
            _ek2c_dental_raw_cache = work
        cutoff = pd.to_datetime(asof_date)
        parsed = work[work["effective_date_parsed"].notna()]
        eligible = parsed[parsed["effective_date_parsed"] <= cutoff]
        if eligible.empty:
            eligible = parsed.sort_values(
                ["code", "effective_date_parsed"]
            ).drop_duplicates(subset=["code"], keep="first")
        else:
            eligible = eligible.sort_values(
                ["code", "effective_date_parsed"]
            ).drop_duplicates(subset=["code"], keep="last")
    else:
        eligible = work.drop_duplicates(subset=["code"], keep="last")

    records = eligible.to_dict(orient="records")
    by_code: dict[str, dict[str, Any]] = {}
    for row in records:
        code = str(row.get("code", "")).strip()
        if not code:
            continue
        puan = _safe_float(row.get("puan"))
        price = _safe_float(row.get("price_try"))
        if price is None and puan is not None:
            price = round(float(puan) * 0.593, 2)
        name = _safe_str(row.get("name"))
        if not name or price is None:
            continue
        by_code[code] = {
            "code": code,
            "name": name,
            "description": _safe_str(row.get("description")),
            "puan": puan,
            "price_try": round(float(price), 2),
            "effective_date": _safe_str(row.get("effective_date")),
            "annex": "EK-2Ç",
        }

    _ek2c_dental_by_asof_cache[asof_date] = by_code
    return by_code


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
