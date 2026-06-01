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


def _encounter_key(
    index: int,
    *,
    patient_lab_visit_ids: list[str | None] | None,
    patient_lab_dates: list[str | None] | None,
) -> str:
    """Resolve encounter bucket: visit_id preferred, date fallback, else unknown."""

    if patient_lab_visit_ids and index < len(patient_lab_visit_ids):
        visit_id = patient_lab_visit_ids[index]
        if visit_id:
            return f"visit:{str(visit_id).strip()}"

    if patient_lab_dates and index < len(patient_lab_dates) and patient_lab_dates[index]:
        return f"date:{str(patient_lab_dates[index]).strip()}"

    return "unknown"


def _optimize_lab_billing(
    patient_id: str,
    patient_lab_tests: list[str],
    patient_lab_dates: list[str | None] | None = None,
    patient_lab_visit_ids: list[str | None] | None = None,
) -> LabOptimization:
    """Algorithm 1: Normative lab billing with hemogram bundling + duplicate detection.

    Args:
        patient_id: Patient identifier.
        patient_lab_tests: List of test names for this patient.
        patient_lab_dates: Optional parallel list of test dates (fallback encounter key).
        patient_lab_visit_ids: Optional parallel list of visit IDs (preferred encounter key).

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

    hemogram_by_encounter: dict[str, int] = {}
    test_counts_by_encounter: dict[tuple[str, str], int] = {}
    normative_total = 0.0
    flagged: list[dict[str, Any]] = []

    for i, test_name in enumerate(patient_lab_tests):
        tn = str(test_name).strip() if test_name else ""
        if not tn:
            continue

        encounter_key = _encounter_key(
            i,
            patient_lab_visit_ids=patient_lab_visit_ids,
            patient_lab_dates=patient_lab_dates,
        )

        if tn in hemogram_set:
            hemogram_by_encounter[encounter_key] = (
                hemogram_by_encounter.get(encounter_key, 0) + 1
            )
            continue

        count_key = (encounter_key, tn)
        test_counts_by_encounter[count_key] = test_counts_by_encounter.get(count_key, 0) + 1

        price, sut_code, display_name = _resolve_lab_test_price(tn, gazette)

        normative_total += price
        _ = display_name, sut_code

    total_hemogram_subtests = sum(hemogram_by_encounter.values())
    n_hemogram_encounters = len(hemogram_by_encounter)
    if total_hemogram_subtests > 0:
        normative_total += hemogram_price * n_hemogram_encounters

        excess = total_hemogram_subtests - n_hemogram_encounters
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
                        f"{total_hemogram_subtests} CBC subtests across "
                        f"{n_hemogram_encounters} encounter(s) "
                        f"should be billed as {n_hemogram_encounters} hemogram(s) (L107020)"
                    ),
                }
            )

    for (encounter_key, tn), count in test_counts_by_encounter.items():
        if count > 1:
            price, sut_code, display_name = _resolve_lab_test_price(tn, gazette)
            dup_savings = price * (count - 1)
            result.duplicate_test_savings += dup_savings
            encounter_label = encounter_key.removeprefix("visit:").removeprefix("date:")
            flagged.append(
                {
                    "test_name": display_name or tn,
                    "sut_code": sut_code,
                    "gazette_price": round(price, 2),
                    "flag_type": "duplicate_test",
                    "savings_try": round(dup_savings, 2),
                    "detail": (
                        f"Test ordered {count}x in encounter {encounter_label} "
                        f"— only 1 reimbursable per encounter"
                    ),
                }
            )

    result.duplicate_test_savings = round(result.duplicate_test_savings, 2)
    result.normative_cost_try = round(normative_total, 2)
    result.flagged_tests = flagged
    return result
