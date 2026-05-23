"""
src/bilun/domain/billing/lab.py
Algorithm 1: Lab billing optimizer with hemogram bundling + duplicate detection.
"""

from __future__ import annotations

import logging
from typing import Any

from ..constants import HEMOGRAM_TESTS, BILUN_TO_SUT_CODE
from ..estimators import SUT_LAB_PRICES, SUT_LAB_DEFAULT, _ensure_enrichment
from ..catalog import get_all_lab_prices, lookup_procedure_code
from .types import LabOptimization

logger = logging.getLogger("ilay.sut_billing_optimizer")

_gazette_lab_prices: dict[str, float] | None = None


def _get_gazette_lab_prices() -> dict[str, float]:
    """Get exact gazette lab prices (single value, not min/max range)."""
    global _gazette_lab_prices
    if _gazette_lab_prices is not None:
        return _gazette_lab_prices

    _ensure_enrichment()

    _gazette_lab_prices = {}
    for name, (price_min, price_max) in SUT_LAB_PRICES.items():
        _gazette_lab_prices[name] = price_min

    try:
        direct_prices = get_all_lab_prices()
        if direct_prices:
            for name, price in direct_prices.items():
                _gazette_lab_prices[name] = price
    except Exception as exc:
        logger.debug("Direct gazette lab prices load failed: %s", exc)

    return _gazette_lab_prices


logger = logging.getLogger("ilay.sut_billing_optimizer")


def _resolve_lab_test_price(test_name: str, gazette: dict[str, float]) -> tuple[float, str, str]:
    """Resolve gazette price and SUT code for a lab test name or L-code."""

    tn = str(test_name).strip()
    if not tn:
        return SUT_LAB_DEFAULT[0], "", ""

    upper = tn.upper()
    if upper.startswith("L") and len(upper) >= 4:
        lookup = lookup_procedure_code(upper)
        entry = lookup.get("entry") if lookup else None
        if entry is not None:
            price = float(entry.get("price_try") or SUT_LAB_DEFAULT[0])
            code = str(entry.get("code") or upper)
            name = str(entry.get("name") or upper)
            return price, code, name

    price = gazette.get(tn)
    if price is None:
        price = gazette.get(tn.lower(), SUT_LAB_DEFAULT[0])
    sut_code = BILUN_TO_SUT_CODE.get(tn, "")
    return price, sut_code, tn


def _optimize_lab_billing(
    patient_id: str,
    patient_lab_tests: list[str],
    patient_lab_dates: list[str | None] | None = None,
) -> LabOptimization:
    """Algorithm 1: Normative lab billing with hemogram bundling + duplicate detection.

    Args:
        patient_id: Patient identifier.
        patient_lab_tests: List of test names for this patient.
        patient_lab_dates: Optional parallel list of test dates (for duplicate detection).

    Returns:
        LabOptimization with exact gazette-priced normative cost and savings.
    """
    gazette = _get_gazette_lab_prices()
    result = LabOptimization()

    if not patient_lab_tests:
        return result

    hemogram_set = HEMOGRAM_TESTS
    hemogram_price = gazette.get(
        "Hemoglobin", SUT_LAB_PRICES.get("Hemoglobin", SUT_LAB_DEFAULT)[0]
    )
    hemogram_sut_code = BILUN_TO_SUT_CODE.get("Hemoglobin", "L107020")

    hemogram_by_date: dict[str, int] = {}
    test_counts: dict[str, int] = {}
    normative_total = 0.0
    flagged: list[dict[str, Any]] = []

    for i, test_name in enumerate(patient_lab_tests):
        tn = str(test_name).strip() if test_name else ""
        if not tn:
            continue

        if tn in hemogram_set:
            date_key = "unknown"
            if patient_lab_dates and i < len(patient_lab_dates) and patient_lab_dates[i]:
                date_key = str(patient_lab_dates[i]).strip()
            hemogram_by_date[date_key] = hemogram_by_date.get(date_key, 0) + 1
            continue

        test_counts[tn] = test_counts.get(tn, 0) + 1

        price, sut_code, display_name = _resolve_lab_test_price(tn, gazette)

        normative_total += price
        _ = display_name

    total_hemogram_subtests = sum(hemogram_by_date.values())
    n_hemogram_dates = len(hemogram_by_date)
    if total_hemogram_subtests > 0:
        normative_total += hemogram_price * n_hemogram_dates

        excess = total_hemogram_subtests - n_hemogram_dates
        if excess > 0:
            bundling_savings = excess * hemogram_price
            result.hemogram_bundling_savings = round(bundling_savings, 2)
            flagged.append(
                {
                    "test_name": "Hemogram (CBC) Bundle",
                    "sut_code": hemogram_sut_code,
                    "gazette_price": round(hemogram_price, 2),
                    "flag_type": "hemogram_unbundling",
                    "savings_try": round(bundling_savings, 2),
                    "detail": (
                        f"{total_hemogram_subtests} CBC subtests across {n_hemogram_dates} date(s) "
                        f"should be billed as {n_hemogram_dates} hemogram(s) (L107020)"
                    ),
                }
            )

    for tn, count in test_counts.items():
        if count > 1:
            price, sut_code, display_name = _resolve_lab_test_price(tn, gazette)
            dup_savings = price * (count - 1)
            result.duplicate_test_savings += dup_savings
            flagged.append(
                {
                    "test_name": display_name or tn,
                    "sut_code": sut_code,
                    "gazette_price": round(price, 2),
                    "flag_type": "duplicate_test",
                    "savings_try": round(dup_savings, 2),
                    "detail": f"Test ordered {count}x — only 1 reimbursable per encounter",
                }
            )

    result.duplicate_test_savings = round(result.duplicate_test_savings, 2)
    result.normative_cost_try = round(normative_total, 2)
    result.flagged_tests = flagged
    return result