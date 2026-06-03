"""Resolve SUT material codes to catalog names (EK-3C and specialty lists)."""

from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path

import polars as pl

from ..constants import (
    _EK3_SPECIALTY_CATALOGS,
    _GAZETTE_CURATED_DIR,
    EK3H_PARQUET_PATH,
    EK3I_PARQUET_PATH,
)
from ..utils import turkish_lower

logger = logging.getLogger("bilun.domain.materials.catalog_lookup")

_CODE_INDEX: dict[str, str] | None = None
_EK3C_CODE_SET: frozenset[str] | None = None
_EK3_ALL_CODE_SET: frozenset[str] | None = None
_EK3_PRICE_INDEX: dict[str, float] | None = None

_SEPARATE_BILLING_ALLOW_MARKERS = (
    "ayrica faturalandirilabilir",
    "birlikte faturalandirilabilir",
    "adet faturalandirilabilir",
    "ilave olarak faturalandir",
    "islem bedeline ilave olarak faturalandir",
)


def _fold_tr(text: str) -> str:
    return turkish_lower(str(text)).replace("ı", "i")


def _text_indicates_separate_billing_allowed(*parts: object) -> bool:
    combined = _fold_tr(" ".join(str(part or "") for part in parts))
    return any(_fold_tr(marker) in combined for marker in _SEPARATE_BILLING_ALLOW_MARKERS)
_EK3C_PARQUET_NAMES = (
    "ek3c1_materials.parquet",
    "ek3c2_materials.parquet",
    "ek3c3_materials.parquet",
    "ek3c4_materials.parquet",
    "ek3c5_materials.parquet",
)


def _read_sut_codes_from_parquet(path: Path) -> set[str]:
    try:
        df = pl.read_parquet(path)
    except Exception as exc:
        logger.warning("Failed to read material catalog %s: %s", path, exc)
        return set()
    if "sut_code" not in df.columns:
        return set()
    return {
        str(code).strip().upper()
        for code in df["sut_code"].to_list()
        if code and str(code).strip()
    }


def _read_material_rows_from_parquet(path: Path) -> list[dict[str, object]]:
    try:
        df = pl.read_parquet(path)
    except Exception as exc:
        logger.warning("Failed to read material catalog %s: %s", path, exc)
        return []
    if "sut_code" not in df.columns:
        return []
    return [dict(row) for row in df.iter_rows(named=True)]


@lru_cache(maxsize=1)
def _all_ek3_catalog_paths() -> tuple[Path, ...]:
    paths: list[Path] = []
    for extra in (EK3H_PARQUET_PATH, EK3I_PARQUET_PATH):
        if extra.exists():
            paths.append(extra)
    for name in _EK3C_PARQUET_NAMES:
        path = _GAZETTE_CURATED_DIR / name
        if path.exists():
            paths.append(path)
    for filename, _desc in _EK3_SPECIALTY_CATALOGS.values():
        path = _GAZETTE_CURATED_DIR / filename
        if path.exists():
            paths.append(path)
    return tuple(paths)


@lru_cache(maxsize=1)
def _build_ek3_price_index() -> dict[str, float]:
    index: dict[str, float] = {}
    for path in _all_ek3_catalog_paths():
        for row in _read_material_rows_from_parquet(path):
            code = str(row.get("sut_code") or "").strip().upper()
            price = row.get("price_try")
            if not code or price is None:
                continue
            try:
                value = float(price)
            except (TypeError, ValueError):
                continue
            if value > 0:
                index[code] = value
    return index


@lru_cache(maxsize=1)
def ek3_separate_billing_allowed_codes() -> frozenset[str]:
    """EK-3 rows explicitly marked as separately billable (§3.1.4 / C001823)."""
    allowed: set[str] = set()
    for path in _all_ek3_catalog_paths():
        for row in _read_material_rows_from_parquet(path):
            code = str(row.get("sut_code") or "").strip().upper()
            if not code:
                continue
            if _text_indicates_separate_billing_allowed(
                row.get("description"),
                row.get("material_name"),
                row.get("name"),
            ):
                allowed.add(code)
    return frozenset(allowed)


def lookup_ek3_list_price_try(material_code: str) -> float | None:
    code = str(material_code or "").strip().upper()
    if not code:
        return None
    return _build_ek3_price_index().get(code)


def is_separate_billing_allowed(material_code: str) -> bool:
    code = str(material_code or "").strip().upper()
    if not code:
        return False
    return code in ek3_separate_billing_allowed_codes()


@lru_cache(maxsize=1)
def ek3c_material_code_set() -> frozenset[str]:
    """SUT EK-3/C list material codes (ek3c1–ek3c5 parquets)."""
    global _EK3C_CODE_SET
    if _EK3C_CODE_SET is not None:
        return _EK3C_CODE_SET
    codes: set[str] = set()
    for name in _EK3C_PARQUET_NAMES:
        path = _GAZETTE_CURATED_DIR / name
        if path.exists():
            codes |= _read_sut_codes_from_parquet(path)
    _EK3C_CODE_SET = frozenset(codes)
    return _EK3C_CODE_SET


@lru_cache(maxsize=1)
def ek3_all_material_code_set() -> frozenset[str]:
    """Union of EK-3/C + specialty annex material codes (EK-3A–T parquets)."""
    global _EK3_ALL_CODE_SET
    if _EK3_ALL_CODE_SET is not None:
        return _EK3_ALL_CODE_SET
    codes = set(ek3c_material_code_set())
    for extra in (EK3H_PARQUET_PATH, EK3I_PARQUET_PATH):
        if extra.exists():
            codes |= _read_sut_codes_from_parquet(extra)
    for filename, _desc in _EK3_SPECIALTY_CATALOGS.values():
        path = _GAZETTE_CURATED_DIR / filename
        if path.exists():
            codes |= _read_sut_codes_from_parquet(path)
    _EK3_ALL_CODE_SET = frozenset(codes)
    return _EK3_ALL_CODE_SET


def is_material_in_ek3c_catalog(material_code: str) -> bool:
    code = str(material_code or "").strip().upper()
    if not code:
        return False
    return code in ek3c_material_code_set()


def is_material_in_ek3_catalog(material_code: str) -> bool:
    code = str(material_code or "").strip().upper()
    if not code:
        return False
    return code in ek3_all_material_code_set()


def _material_parquet_paths() -> list[Path]:
    curated = _GAZETTE_CURATED_DIR
    names = [
        "ek3c1_materials.parquet",
        "ek3c2_materials.parquet",
        "ek3h_cardiology_materials.parquet",
        "ek3i_orthopedics_materials.parquet",
    ]
    return [curated / name for name in names if (curated / name).exists()]


@lru_cache(maxsize=1)
def _build_material_code_index() -> dict[str, str]:
    index: dict[str, str] = {}
    for path in _material_parquet_paths():
        try:
            df = pl.read_parquet(path)
        except Exception as exc:
            logger.warning("Failed to read material catalog %s: %s", path, exc)
            continue
        if "sut_code" not in df.columns:
            continue
        name_col = "material_name" if "material_name" in df.columns else "name"
        for row in df.iter_rows(named=True):
            code = str(row.get("sut_code") or "").strip().upper()
            name = str(row.get(name_col) or "").strip()
            if code and name and code not in index:
                index[code] = name
    return index


def resolve_material_name_by_code(material_code: str) -> str | None:
    """Return canonical material name for a SUT material code, if known."""
    code = str(material_code or "").strip().upper()
    if not code:
        return None
    return _build_material_code_index().get(code)
