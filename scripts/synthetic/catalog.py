"""Gazette catalogue loading functions for the SUT synthetic data generator v2."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from constants import CURATED_DIR

_GAZETTE_CACHE: dict[str, pd.DataFrame] = {}


def _gazette(name: str, path: Path) -> pd.DataFrame:
    if name in _GAZETTE_CACHE:
        return _GAZETTE_CACHE[name]
    if not path.exists():
        df = pd.DataFrame()
    else:
        df = pd.read_parquet(path)
    _GAZETTE_CACHE[name] = df
    return df


def _ek2b() -> pd.DataFrame:
    """Load the latest EK-2B catalog snapshot from curated history.

    Returns a DataFrame with one row per procedure code using the most recent
    effective_date, with columns: code, name, puan, description, price_try.
    """
    df = _gazette("ek2b", CURATED_DIR / "ek2b_catalog_history.parquet")
    if df.empty:
        return df
    work = df.copy()
    work["effective_date_dt"] = pd.to_datetime(work["effective_date"], errors="coerce")
    work = work.sort_values("effective_date_dt").drop_duplicates(
        subset=["code"], keep="last"
    )
    return work


def _ek2c_latest() -> pd.DataFrame:
    df = _gazette("ek2c", CURATED_DIR / "ek2c_catalog_history.parquet")
    if df.empty:
        return df
    work = df.copy()
    work["effective_date_dt"] = pd.to_datetime(work["effective_date"], errors="coerce")
    return work.sort_values("effective_date_dt").drop_duplicates(
        subset=["package_code"], keep="last"
    )


def _ek2c1() -> pd.DataFrame:
    return _gazette("ek2c1", CURATED_DIR / "ek2c1_copay_rates.parquet")


def _ek2g() -> pd.DataFrame:
    return _gazette("ek2g", CURATED_DIR / "ek2g_no_surcharge.parquet")


def _ek4a() -> pd.DataFrame:
    return _gazette("ek4a", CURATED_DIR / "ek4a_drugs.parquet")


def _ek3_material(catalog_filename: str) -> pd.DataFrame:
    key = f"ek3_{catalog_filename}"
    return _gazette(key, CURATED_DIR / catalog_filename)


def _ek1a() -> pd.DataFrame:
    return _gazette("ek1a", CURATED_DIR / "ek1a_chronic_exemptions.parquet")


def _money(value: float) -> float:
    return round(float(value), 2)


def _drug_unit_price(drug_row: pd.Series, rng: np.random.Generator) -> float:
    tier_raw = drug_row.get("discount_tier_1")
    try:
        tier = float(tier_raw) if tier_raw is not None else 0.28
    except (ValueError, TypeError):
        tier = 0.28
    status = str(drug_row.get("discount_status", ""))
    base = rng.uniform(20.0, 500.0)
    if "KAN" in status.upper():
        base = rng.uniform(300.0, 3000.0)
    elif tier >= 0.4:
        base = rng.uniform(15.0, 150.0)
    elif tier >= 0.28:
        base = rng.uniform(25.0, 350.0)
    return _money(base)
