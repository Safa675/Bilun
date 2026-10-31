"""
src/bilun/domain/optimization/temporal.py
Feature 4: Temporal price validation (EK-2B/2C History).
"""

from __future__ import annotations

import logging
from typing import Any

import pandas as pd

from ..constants import EK2B_CURATED_HISTORY_PATH, EK2C_CURATED_HISTORY_PATH

logger = logging.getLogger("bilun.domain.optimization")

_temporal_audit_cache: dict[str, Any] | None = None


def _compute_annex_temporal_stats(df: pd.DataFrame, code_col: str) -> dict[str, Any]:
    """Compute temporal price change statistics for an annex history DataFrame."""
    if df.empty:
        return {
            "n_codes": 0,
            "n_effective_dates": 0,
            "date_range": [],
            "effective_dates": [],
            "n_codes_with_changes": 0,
            "price_change_rate": 0.0,
            "mean_price_delta_pct": 0.0,
            "top_increases": [],
            "top_decreases": [],
        }

    work = df.drop_duplicates(subset=[code_col, "effective_date"], keep="last").copy()
    work = work.sort_values([code_col, "effective_date"]).reset_index(drop=True)

    dates = sorted(work["effective_date"].unique().tolist())
    n_codes = work[code_col].nunique()

    # `rows` is sorted by code and date: a code's rows are adjacent, its first and last are its old and new price.
    rows = work[work[code_col].notna()]
    codes = rows[code_col].to_numpy()
    prices = rows["price_try"].to_numpy()
    names = rows["name"].to_numpy() if "name" in rows.columns else None
    effective = rows["effective_date"].to_numpy()
    codes_with_changes = 0
    all_deltas: list[dict[str, Any]] = []

    first = 0
    for last, code in enumerate(codes):
        if last + 1 < len(codes) and codes[last + 1] == code:
            continue
        oldest, first = first, last + 1
        if oldest == last:
            continue
        old_price = prices[oldest]
        new_price = prices[last]
        if pd.isna(old_price) or pd.isna(new_price) or old_price == 0:
            continue
        delta_pct = round(((new_price - old_price) / old_price) * 100, 2)
        if abs(delta_pct) > 0.01:
            codes_with_changes += 1
        name = names[last] if names is not None else str(code)
        if pd.isna(name):
            name = str(code)
        all_deltas.append(
            {
                "code": str(code),
                "name": str(name),
                "old_price": round(float(old_price), 2),
                "new_price": round(float(new_price), 2),
                "delta_pct": delta_pct,
                "old_date": str(effective[oldest]),
                "new_date": str(effective[last]),
            }
        )

    all_deltas.sort(key=lambda x: x["delta_pct"], reverse=True)
    top_increases = all_deltas[:10]
    top_decreases = sorted(all_deltas, key=lambda x: x["delta_pct"])[:10]

    mean_delta = (
        round(sum(d["delta_pct"] for d in all_deltas) / len(all_deltas), 2)
        if all_deltas
        else 0.0
    )

    return {
        "n_codes": n_codes,
        "n_effective_dates": len(dates),
        "date_range": [dates[0], dates[-1]] if dates else [],
        "effective_dates": dates,
        "n_codes_with_changes": codes_with_changes,
        "price_change_rate": round(codes_with_changes / n_codes, 4) if n_codes else 0.0,
        "mean_price_delta_pct": mean_delta,
        "top_increases": top_increases,
        "top_decreases": top_decreases,
    }


def audit_temporal_prices() -> dict[str, Any]:
    """System-level audit of price changes across gazette amendment dates.

    Returns:
        {
            "ek2b": { ... temporal stats ... },
            "ek2c": { ... temporal stats ... },
            "methodology": str,
        }
    """
    global _temporal_audit_cache
    if _temporal_audit_cache is not None:
        return _temporal_audit_cache

    ek2b_stats: dict[str, Any] = {
        "n_codes": 0,
        "n_effective_dates": 0,
        "date_range": [],
        "effective_dates": [],
        "n_codes_with_changes": 0,
        "price_change_rate": 0.0,
        "mean_price_delta_pct": 0.0,
        "top_increases": [],
        "top_decreases": [],
    }
    ek2c_stats: dict[str, Any] = dict(ek2b_stats)

    try:
        if EK2B_CURATED_HISTORY_PATH.exists():
            ek2b_df = pd.read_parquet(EK2B_CURATED_HISTORY_PATH)
            ek2b_stats = _compute_annex_temporal_stats(ek2b_df, "code")
    except Exception as exc:
        logger.warning("Failed to load EK-2B history: %s", exc)

    try:
        if EK2C_CURATED_HISTORY_PATH.exists():
            ek2c_df = pd.read_parquet(EK2C_CURATED_HISTORY_PATH)
            ek2c_stats = _compute_annex_temporal_stats(ek2c_df, "package_code")
    except Exception as exc:
        logger.warning("Failed to load EK-2C history: %s", exc)

    result = {
        "ek2b": ek2b_stats,
        "ek2c": ek2c_stats,
        "methodology": (
            "Loads the full temporal history of EK-2B (fee-for-service procedure "
            "points) and EK-2C (diagnosis-based package points) across all ingested "
            "gazette amendment dates. Compares the earliest and latest price for "
            "each code to detect changes. "
            "100% real gazette data from official SUT amendments."
        ),
    }
    _temporal_audit_cache = result
    return result