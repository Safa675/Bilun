"""
src/bilun/domain/pricing/drg.py
Legacy DRG package pricing using EK-2C median prices with ICD-10 keyword filtering.

.. deprecated::
    These median helpers are non-product. Patient DRG analytics and billing
    strategy now use exact billed package lines and the dated EK-2C catalog
    entry for the billed code. Keep this module only for historical tests or
    future grouper research; do not call it from product code paths.
"""

from __future__ import annotations

from typing import Any
import logging
from statistics import median

from ..catalog import _normalize_asof_date, load_sut_catalog
from ..constants import _ICD10_CHAPTER_TO_EK2C_GROUP
from .keywords import _ICD10_CHAPTER_KEYWORDS

logger = logging.getLogger("ilay.sut_pricing")

_ek2c_group_medians: dict[str, float] | None = None
_ek2c_chapter_medians: dict[str, float] | None = None
_ek2c_exact_medians_by_asof: dict[str, tuple[dict[str, float], dict[str, float]]] = {}

_DRG_PRICE_CAP_FACTOR: float = 3.0
_FALLBACK_GROUP_MEDIANS = {
    "A1": 908_561.20,
    "A2": 141_501.16,
    "A3": 47_151.84,
    "B": 16_432.13,
    "C": 7_593.09,
    "D": 4_544.92,
    "E": 1_638.93,
}


def _is_effective_on_or_before(entry: dict[str, Any], asof_date: str) -> bool:
    """Return whether a dated catalog entry is effective for the requested date."""
    effective_date = str(entry.get("effective_date") or "").strip()
    return bool(effective_date) and effective_date <= asof_date


def _build_ek2c_median_prices(
    visit_date: Any | None = None,
) -> tuple[dict[str, float], dict[str, float]]:
    """Build exact per-date DRG medians from the canonical as-of EK-2C catalog.

    Returns (group_medians, chapter_medians).

    Strategy:
    1. Load the canonical as-of EK-2C catalog.
    2. Compute group-level medians (fallback for any chapter).
    3. For each ICD-10 chapter that has keyword mappings, filter the
       packages in its EK-2C group by Turkish clinical keywords and
       take the true median of the matched subset. If no matches, fall back
       to the group median.
    """
    asof_date = _normalize_asof_date(visit_date)
    cached = _ek2c_exact_medians_by_asof.get(asof_date)
    if cached is not None:
        return cached

    group_medians: dict[str, float] = {}
    chapter_medians: dict[str, float] = {}
    catalog = load_sut_catalog(visit_date=asof_date)
    packages = catalog.get("ek2c", {}).get("packages", [])

    group_prices: dict[str, list[float]] = {}
    group_packages: dict[str, list[dict[str, Any]]] = {}
    for package in packages:
        if not _is_effective_on_or_before(package, asof_date):
            continue
        group = str(package.get("group") or "").strip()
        price = package.get("price_try")
        if not group or price is None:
            continue
        price_value = float(price)
        group_prices.setdefault(group, []).append(price_value)
        group_packages.setdefault(group, []).append(package)

    for group, prices in group_prices.items():
        group_medians[group] = float(median(prices))

    for chapter, keywords in _ICD10_CHAPTER_KEYWORDS.items():
        group = _ICD10_CHAPTER_TO_EK2C_GROUP.get(chapter, "C")
        packages_in_group = group_packages.get(group, [])
        if not packages_in_group:
            continue

        matched_prices = [
            float(package["price_try"])
            for package in packages_in_group
            if any(kw in str(package.get("name") or "").lower() for kw in keywords)
        ]
        if matched_prices:
            chapter_medians[chapter] = float(median(matched_prices))
        elif group in group_medians:
            chapter_medians[chapter] = group_medians[group]

    _ek2c_exact_medians_by_asof[asof_date] = (group_medians, chapter_medians)
    return group_medians, chapter_medians


def _get_ek2c_group_median_prices(visit_date: Any | None = None) -> dict[str, float]:
    """Return per-group median EK-2C prices (cached)."""
    global _ek2c_group_medians, _ek2c_chapter_medians
    if visit_date is not None:
        group_medians, _ = _build_ek2c_median_prices(visit_date=visit_date)
        return group_medians

    if _ek2c_group_medians is not None:
        return _ek2c_group_medians

    group_medians, chapter_medians = _build_ek2c_median_prices()
    _ek2c_group_medians = dict(group_medians)
    _ek2c_chapter_medians = dict(chapter_medians)
    for k, v in _FALLBACK_GROUP_MEDIANS.items():
        _ek2c_group_medians.setdefault(k, v)

    return _ek2c_group_medians


def _get_ek2c_chapter_median_prices(
    visit_date: Any | None = None,
) -> dict[str, float]:
    """Return per-ICD10-chapter keyword-filtered median EK-2C prices (cached)."""
    global _ek2c_chapter_medians
    if visit_date is not None:
        _, chapter_medians = _build_ek2c_median_prices(visit_date=visit_date)
        return chapter_medians

    if _ek2c_chapter_medians is None:
        _get_ek2c_group_median_prices()
    assert _ek2c_chapter_medians is not None
    return _ek2c_chapter_medians


def get_drg_package_price(
    icd10_chapter: str,
    icd10_code: str | None = None,
) -> float:
    """Estimate the EK-2C DRG package price for an ICD-10 chapter/code.

    .. deprecated::
        Non-product median heuristic. Use exact billed package lines or
        ``get_ek2c_price_for_date`` for the billed package code instead.

    Pricing strategy (most specific → least specific):
      1. Chapter-level keyword-filtered median (matches EK-2C package names
          relevant to the ICD-10 chapter via Turkish clinical keywords).
      2. Group-level median (all packages in the EK-2C group).
      3. Hardcoded fallback for the group (stale but safe).

    Args:
        icd10_chapter: Single uppercase letter (e.g. "I", "C", "J").
        icd10_code: Optional full ICD-10 code (e.g. "I10", "I25.0").
            Reserved for future sub-chapter specificity; currently used
            for logging only.

    Returns:
        Estimated median DRG package price in TRY.
    """
    ch = icd10_chapter.upper()

    chapter_medians = _get_ek2c_chapter_median_prices()
    if ch in chapter_medians:
        return chapter_medians[ch]

    group = _ICD10_CHAPTER_TO_EK2C_GROUP.get(ch, "C")
    group_medians = _get_ek2c_group_median_prices()
    return group_medians.get(group, group_medians.get("C", 7_593.09))


def get_drg_package_price_for_date(
    icd10_chapter: str,
    procedure_date: Any,
    icd10_code: str | None = None,
) -> float | None:
    """Return a dated DRG chapter price using the canonical as-of catalog.

    .. deprecated::
        Non-product median heuristic. Use exact billed package lines or
        ``get_ek2c_price_for_date`` for the billed package code instead.

    Unlike the legacy current-price helper, this function does not fall back to
    future/latest prices or hardcoded group medians when the requested date has
    no eligible EK-2C packages.
    """
    _ = icd10_code  # Reserved for later sub-chapter specificity.
    ch = icd10_chapter.upper()

    chapter_medians = _get_ek2c_chapter_median_prices(visit_date=procedure_date)
    if ch in chapter_medians:
        return chapter_medians[ch]

    group = _ICD10_CHAPTER_TO_EK2C_GROUP.get(ch, "C")
    group_medians = _get_ek2c_group_median_prices(visit_date=procedure_date)
    return group_medians.get(group)
