"""
src/bilun/domain/billing/lab.py
Algorithm 1: Lab billing optimizer with hemogram bundling + duplicate detection.
"""

from __future__ import annotations

import logging
from typing import Any

from ..constants import HEMOGRAM_TESTS, BILUN_TO_SUT_CODE
from ..estimators import SUT_LAB_DEFAULT, _ensure_enrichment
from ..catalog import get_all_lab_prices, get_lab_price, lookup_procedure_code
from .types import LabOptimization

logger = logging.getLogger("ilay.sut_billing_optimizer")

_gazette_lab_prices_by_asof: dict[str, dict[str, float]] = {}


def _service_date_for_index(
    index: int,
    *,
    patient_lab_dates: list[str | None] | None,
) -> Any | None:
    if patient_lab_dates and index < len(patient_lab_dates):
        return patient_lab_dates[index]
    return None


def _asof_key(visit_date: Any | None) -> str:
    if visit_date is None:
        return "__default__"
    return str(visit_date).strip() or "__default__"


def _get_gazette_lab_prices(visit_date: Any | None = None) -> dict[str, float]:
    """Get exact gazette lab prices for a service/as-of date (L4.1 temporal catalog)."""
    key = _asof_key(visit_date)
    if key in _gazette_lab_prices_by_asof:
        return _gazette_lab_prices_by_asof[key]

    _ensure_enrichment()

    prices: dict[str, float] = {}
    try:
        direct_prices = get_all_lab_prices(visit_date=visit_date)
        if direct_prices:
            prices.update(direct_prices)
    except Exception as exc:
        logger.debug("Direct gazette lab prices load failed: %s", exc)

    if not prices:
        for name in BILUN_TO_SUT_CODE:
            unit = get_lab_price(name, visit_date=visit_date)
            if unit is not None:
                prices[name] = unit

    _gazette_lab_prices_by_asof[key] = prices
    return prices


def _resolve_lab_test_price(
    test_name: str,
    *,
    visit_date: Any | None = None,
) -> tuple[float, str, str]:
    """Resolve gazette price and SUT code for a lab test name or L-code."""

    gazette = _get_gazette_lab_prices(visit_date)
    tn = str(test_name).strip()
    if not tn:
        return SUT_LAB_DEFAULT[0], "", ""

    upper = tn.upper()
    if upper.startswith("L") and len(upper) >= 4:
        lookup = lookup_procedure_code(upper, visit_date=visit_date)
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
) -> str | None:
    """Resolve encounter bucket: visit_id preferred, else date. None if neither is known."""

    if patient_lab_visit_ids and index < len(patient_lab_visit_ids):
        visit_id = patient_lab_visit_ids[index]
        if visit_id:
            return f"visit:{str(visit_id).strip()}"

    if patient_lab_dates and index < len(patient_lab_dates) and patient_lab_dates[index]:
        return f"date:{str(patient_lab_dates[index]).strip()}"

    return None


def _hemogram_price_for_encounter(
    encounter_key: str,
    encounter_asof: dict[str, Any | None],
) -> float:
    asof = encounter_asof.get(encounter_key)
    gazette = _get_gazette_lab_prices(asof)
    return gazette.get("Hemoglobin", SUT_LAB_DEFAULT[0])


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
        patient_lab_dates: Optional parallel list of test dates (service date for EK-2B as-of).
        patient_lab_visit_ids: Optional parallel list of visit IDs (preferred encounter key).

    Returns:
        LabOptimization with exact gazette-priced normative cost and savings.
    """
    _ = patient_id
    result = LabOptimization()

    if not patient_lab_tests:
        return result

    hemogram_set = HEMOGRAM_TESTS
    hemogram_sut_code = BILUN_TO_SUT_CODE.get("Hemoglobin", "L107020")

    hemogram_by_encounter: dict[str, int] = {}
    encounter_asof: dict[str, Any | None] = {}
    test_counts_by_encounter: dict[tuple[str, str], int] = {}
    normative_total = 0.0
    flagged: list[dict[str, Any]] = []

    for i, test_name in enumerate(patient_lab_tests):
        tn = str(test_name).strip() if test_name else ""
        if not tn:
            continue

        service_date = _service_date_for_index(i, patient_lab_dates=patient_lab_dates)
        encounter_key = _encounter_key(
            i,
            patient_lab_visit_ids=patient_lab_visit_ids,
            patient_lab_dates=patient_lab_dates,
        )
        if encounter_key is None:
            if tn in hemogram_set:
                normative_total += _resolve_lab_test_price(
                    "Hemoglobin", visit_date=service_date
                )[0]
            else:
                normative_total += _resolve_lab_test_price(tn, visit_date=service_date)[0]
            continue

        if encounter_key not in encounter_asof and service_date is not None:
            encounter_asof[encounter_key] = service_date

        if tn in hemogram_set:
            hemogram_by_encounter[encounter_key] = (
                hemogram_by_encounter.get(encounter_key, 0) + 1
            )
            continue

        count_key = (encounter_key, tn)
        test_counts_by_encounter[count_key] = test_counts_by_encounter.get(count_key, 0) + 1

        price, sut_code, display_name = _resolve_lab_test_price(
            tn, visit_date=service_date
        )

        normative_total += price
        _ = display_name, sut_code

    total_hemogram_subtests = sum(hemogram_by_encounter.values())
    n_hemogram_encounters = len(hemogram_by_encounter)
    if total_hemogram_subtests > 0:
        for enc_key in hemogram_by_encounter:
            normative_total += _hemogram_price_for_encounter(enc_key, encounter_asof)

        excess = total_hemogram_subtests - n_hemogram_encounters
        if excess > 0:
            weighted_price = 0.0
            if n_hemogram_encounters > 0:
                for enc_key in hemogram_by_encounter:
                    weighted_price += _hemogram_price_for_encounter(
                        enc_key, encounter_asof
                    )
                weighted_price /= n_hemogram_encounters
            else:
                weighted_price = SUT_LAB_DEFAULT[0]

            bundling_savings = excess * weighted_price
            result.hemogram_bundling_savings = round(bundling_savings, 2)
            flagged.append(
                {
                    "test_name": "Hemogram (CBC) Bundle",
                    "sut_code": hemogram_sut_code,
                    "gazette_price": round(weighted_price, 2),
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
        if count <= 1:
            continue
        asof = encounter_asof.get(encounter_key)
        price, sut_code, display_name = _resolve_lab_test_price(tn, visit_date=asof)
        encounter_label = encounter_key.removeprefix("visit:").removeprefix("date:")
        flagged.append(
            {
                "test_name": display_name or tn,
                "sut_code": sut_code,
                "gazette_price": round(price, 2),
                "flag_type": "clinical_review_duplicate",
                "savings_try": None,
                "review_kind": "clinical_utilization",
                "detail": (
                    f"Test ordered {count}x in encounter {encounter_label} "
                    f"— clinical review: verify repeat necessity "
                    f"(not a recoverable billing adjustment; MEDULA does not reject duplicate SUT codes)"
                ),
            }
        )

    result.duplicate_test_savings = 0.0
    result.normative_cost_try = round(normative_total, 2)
    result.flagged_tests = flagged
    return result
