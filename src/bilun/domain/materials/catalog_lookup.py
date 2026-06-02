"""Resolve SUT material codes to catalog names (EK-3C and specialty lists)."""

from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path

import polars as pl

from ..constants import _EK3_SPECIALTY_CATALOGS, _GAZETTE_CURATED_DIR

logger = logging.getLogger("bilun.domain.materials.catalog_lookup")

_CODE_INDEX: dict[str, str] | None = None
_EK3C_CODE_SET: frozenset[str] | None = None
_EK3_ALL_CODE_SET: frozenset[str] | None = None

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
