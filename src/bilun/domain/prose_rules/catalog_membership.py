"""EK-2B / EK-2C procedure membership lookups for prose rule evaluation."""

from __future__ import annotations

import logging
from datetime import date, datetime
from functools import lru_cache
from pathlib import Path

import pandas as pd

from ..constants import EK2B_CURATED_HISTORY_PATH, EK2C_CURATED_HISTORY_PATH
from .ek2c_prose_drg_locked import load_prose_drg_locked_code_set

logger = logging.getLogger("bilun.domain.prose_rules.catalog_membership")


def normalize_procedure_code(raw: str) -> str:
    code = str(raw or "").strip().replace(".", "").replace(" ", "").replace("-", "")
    if code.startswith(("P", "p")):
        code = code[1:]
    return code


def _coerce_asof_key(as_of_date: date | str | None) -> str:
    if as_of_date is None:
        return date.today().isoformat()
    if isinstance(as_of_date, date):
        return as_of_date.isoformat()
    text = str(as_of_date).strip()
    if not text:
        return date.today().isoformat()
    try:
        return datetime.strptime(text[:10], "%Y-%m-%d").date().isoformat()
    except ValueError:
        return date.today().isoformat()


def _eligible_history_rows(
    history_path: Path,
    code_column: str,
    asof_key: str,
) -> pd.DataFrame:
    if not history_path.exists():
        logger.warning("Catalog history not found: %s", history_path)
        return pd.DataFrame()

    df = pd.read_parquet(history_path)
    if df.empty or code_column not in df.columns:
        return pd.DataFrame()

    work = df.copy()
    if "effective_date" not in work.columns:
        return work.drop_duplicates(subset=[code_column], keep="last")

    work["effective_date_parsed"] = pd.to_datetime(work["effective_date"], errors="coerce")
    cutoff = pd.to_datetime(asof_key)
    work = work[work["effective_date_parsed"].notna()]
    eligible = work[work["effective_date_parsed"] <= cutoff]
    if eligible.empty:
        # B-H2: no amendment is effective on or before the cutoff (e.g. a
        # claim dated before the earliest curated gazette, or a date.min
        # sentinel). Returning the OLDEST amendment as a fallback silently
        # served a price that was never effective on the service date and is
        # inconsistent with pricing/temporal.py (_is_effective_on_or_before
        # returns None there). Return empty so callers (get_ek2b_codes_as_of
        # -> empty frozenset, get_ek2c_entry -> None) correctly signal "no
        # price as of this date".
        return eligible.reset_index(drop=True)
    eligible = eligible.sort_values(
        [code_column, "effective_date_parsed"]
    ).drop_duplicates(subset=[code_column], keep="last")
    return eligible.reset_index(drop=True)


@lru_cache(maxsize=64)
def get_ek2b_codes_as_of(asof_key: str) -> frozenset[str]:
    eligible = _eligible_history_rows(EK2B_CURATED_HISTORY_PATH, "code", asof_key)
    if eligible.empty:
        return frozenset()
    codes = {
        normalize_procedure_code(str(value))
        for value in eligible["code"].dropna()
        if str(value).strip()
    }
    codes.discard("")
    return frozenset(codes)


@lru_cache(maxsize=64)
def _ek2c_frame_asof(asof_key: str) -> pd.DataFrame:
    return _eligible_history_rows(EK2C_CURATED_HISTORY_PATH, "package_code", asof_key)


@lru_cache(maxsize=64)
def get_ek2c_codes_as_of(asof_key: str) -> frozenset[str]:
    work = _ek2c_frame_asof(asof_key)
    if work.empty:
        return frozenset()
    codes = {
        normalize_procedure_code(str(value))
        for value in work["package_code"].dropna()
        if str(value).strip()
    }
    codes.discard("")
    return frozenset(codes)


@lru_cache(maxsize=64)
def _ek2c_entry_map_asof(asof_key: str) -> dict[str, dict[str, object]]:
    work = _ek2c_frame_asof(asof_key)
    if work.empty:
        return {}

    entries: dict[str, dict[str, object]] = {}
    locked_seed = load_prose_drg_locked_code_set()
    for row in work.itertuples(index=False):
        normalized = normalize_procedure_code(str(getattr(row, "package_code", "")))
        if not normalized:
            continue
        parquet_locked = bool(getattr(row, "prose_drg_locked", False))
        entries[normalized] = {
            "package_code": str(getattr(row, "package_code", "")),
            "name": str(getattr(row, "name", "")),
            "group": str(getattr(row, "group", "")),
            "has_star": bool(getattr(row, "has_star", False)),
            "prose_drg_locked": parquet_locked or normalized in locked_seed,
            "puan": getattr(row, "puan", None),
            "price_try": getattr(row, "price_try", None),
            "effective_date": str(getattr(row, "effective_date", "")),
        }
    return entries


def get_ek2b_codes() -> frozenset[str]:
    """Latest EK-2B membership (as of today)."""
    return get_ek2b_codes_as_of(_coerce_asof_key(None))


def get_ek2c_codes() -> frozenset[str]:
    """Latest EK-2C membership (as of today)."""
    return get_ek2c_codes_as_of(_coerce_asof_key(None))


def get_ek2c_entry(
    procedure_code: str,
    *,
    as_of_date: date | str | None = None,
) -> dict[str, object] | None:
    """Return EK-2C metadata for a procedure code as of the given date."""
    normalized = normalize_procedure_code(procedure_code)
    if not normalized:
        return None
    asof_key = _coerce_asof_key(as_of_date)
    return _ek2c_entry_map_asof(asof_key).get(normalized)


def procedure_has_star(
    procedure_code: str,
    *,
    as_of_date: date | str | None = None,
) -> bool:
    entry = get_ek2c_entry(procedure_code, as_of_date=as_of_date)
    return bool(entry and entry.get("has_star"))


def procedure_prose_drg_locked(
    procedure_code: str,
    *,
    as_of_date: date | str | None = None,
) -> bool:
    """True when SUT prose requires EK-2/C package billing (§2.2.2 proviso list)."""
    entry = get_ek2c_entry(procedure_code, as_of_date=as_of_date)
    if entry and entry.get("prose_drg_locked"):
        return True
    normalized = normalize_procedure_code(procedure_code)
    return bool(normalized) and normalized in load_prose_drg_locked_code_set()


def procedure_annex_membership(
    procedure_code: str,
    *,
    as_of_date: date | str | None = None,
) -> tuple[bool, bool]:
    """Return (in_ek2b, in_ek2c) for a normalized procedure code as of date."""
    normalized = normalize_procedure_code(procedure_code)
    if not normalized:
        return False, False
    asof_key = _coerce_asof_key(as_of_date)
    ek2b = get_ek2b_codes_as_of(asof_key)
    ek2c = get_ek2c_codes_as_of(asof_key)
    return normalized in ek2b, normalized in ek2c
