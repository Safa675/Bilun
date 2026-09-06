"""
src/bilun/domain/pricing/temporal.py
Temporal historical pricing helpers for EK-2B and EK-2C catalogs.

Runtime lookups use the canonical as-of catalog path (``load_sut_catalog``).
The history helpers at the bottom of the module read curated parquet history
directly for audit and exploration.
"""

from __future__ import annotations

import logging
from datetime import date, datetime
from pathlib import Path
from typing import Literal

import polars as pl

from ..catalog import _normalize_asof_date, load_sut_catalog

logger = logging.getLogger("ilay.sut_pricing.temporal")

# Cache for loaded dataframes
_ek2b_history: pl.DataFrame | None = None
_ek2c_history: pl.DataFrame | None = None


def _load_ek2b_history() -> pl.DataFrame:
    """Load EK-2B catalog history with caching."""
    global _ek2b_history
    if _ek2b_history is not None:
        return _ek2b_history

    ek2b_path = Path("data/gazette/curated/ek2b_catalog_history.parquet")
    if not ek2b_path.exists():
        ek2b_path = Path(__file__).resolve().parents[4] / ek2b_path

    if not ek2b_path.exists():
        raise FileNotFoundError(f"EK-2B history not found at {ek2b_path}")

    _ek2b_history = pl.read_parquet(str(ek2b_path))
    logger.info(f"Loaded EK-2B history: {len(_ek2b_history)} rows")
    return _ek2b_history


def _load_ek2c_history() -> pl.DataFrame:
    """Load EK-2C catalog history with caching."""
    global _ek2c_history
    if _ek2c_history is not None:
        return _ek2c_history

    ek2c_path = Path("data/gazette/curated/ek2c_catalog_history.parquet")
    if not ek2c_path.exists():
        ek2c_path = Path(__file__).resolve().parents[4] / ek2c_path

    if not ek2c_path.exists():
        raise FileNotFoundError(f"EK-2C history not found at {ek2c_path}")

    _ek2c_history = pl.read_parquet(str(ek2c_path))
    logger.info(f"Loaded EK-2C history: {len(_ek2c_history)} rows")
    return _ek2c_history


def _parse_date(d: date | datetime | str) -> date:
    """Normalize date input to date object."""
    if isinstance(d, str):
        return datetime.strptime(d, "%Y-%m-%d").date()
    if isinstance(d, datetime):
        return d.date()
    return d


def _normalize_required_asof_date(procedure_date: date | datetime | str) -> str:
    """Normalize a required pricing date; missing dates are not allowed."""
    if procedure_date is None:
        raise ValueError("procedure_date is required for temporal pricing")
    return _normalize_asof_date(procedure_date)


def _is_effective_on_or_before(entry: dict[str, object], asof_date: str) -> bool:
    effective_date = str(entry.get("effective_date") or "").strip()
    return bool(effective_date) and effective_date <= asof_date


def _normalize_procedure_code(code: str) -> str:
    return code.strip().replace(".", "").replace(" ", "").replace("-", "")


def get_ek2b_price_for_date(
    code: str,
    procedure_date: date | datetime | str,
    price_type: Literal["price_try", "puan"] = "price_try",
) -> float | None:
    """
    Get the EK-2B price (or puan) for a specific procedure code on a specific date.

    This looks up the historical price that was effective on the given date,
    not the latest price.

    Args:
        code: EK-2B procedure code (e.g., "99000", "99201")
        procedure_date: Date when the procedure was performed
        price_type: Which price field to return ("price_try" or "puan")

    Returns:
        The historical price/puan, or None if not found

    Example:
        >>> get_ek2b_price_for_date("99000", "2023-06-15")
        150.50
    """
    asof_date = _normalize_required_asof_date(procedure_date)
    catalog = load_sut_catalog(visit_date=asof_date)
    by_code = catalog.get("ek2b", {}).get("by_code", {})

    normalized = _normalize_procedure_code(code)
    entry = by_code.get(normalized)
    if entry is None and normalized and normalized[0] in ("P", "p"):
        entry = by_code.get(normalized[1:])

    if entry is None or not _is_effective_on_or_before(entry, asof_date):
        return None

    value = entry.get(price_type)
    return float(value) if value is not None else None


def get_ek2c_price_for_date(
    package_code: str,
    procedure_date: date | datetime | str,
) -> float | None:
    """
    Get the EK-2C package price for a specific package on a specific date.

    This looks up the historical price that was effective on the given date,
    not the latest price.

    Args:
        package_code: EK-2C package code (e.g., "A1", "B2", "C1")
        procedure_date: Date when the procedure was performed

    Returns:
        The historical package price in TRY, or None if not found

    Example:
        >>> get_ek2c_price_for_date("A1", "2023-06-15")
        850000.0
    """
    asof_date = _normalize_required_asof_date(procedure_date)
    catalog = load_sut_catalog(visit_date=asof_date)
    by_code = catalog.get("ek2c", {}).get("by_code", {})

    normalized = _normalize_procedure_code(package_code)
    entry = by_code.get(normalized)
    if entry is None and normalized and normalized[0] not in ("P", "p"):
        # EK-2/C catalogs store package codes with a "P" prefix (e.g. P609270);
        # accept bare codes (e.g. 609270) by retrying with the prefix — mirrors
        # the P-fallback in get_ek2b_price_for_date.
        entry = by_code.get(f"P{normalized}")

    if entry is None or not _is_effective_on_or_before(entry, asof_date):
        return None

    price = entry.get("price_try")
    return float(price) if price is not None else None


def get_price_history(
    code: str,
    catalog: Literal["ek2b", "ek2c"] = "ek2b",
) -> pl.DataFrame:
    """
    Get the complete price history for a specific code.

    Args:
        code: Procedure code (EK-2B) or package code (EK-2C)
        catalog: Which catalog to query ("ek2b" or "ek2c")

    Returns:
        DataFrame with price history sorted by effective_date
    """
    if catalog == "ek2b":
        df = _load_ek2b_history()
        result = df.filter(pl.col("code") == code).sort("effective_date")
    else:
        df = _load_ek2c_history()
        result = df.filter(pl.col("package_code") == code).sort("effective_date")

    return result
