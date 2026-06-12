"""
src/bilun/domain/billing/lab.py
Algorithm 1: Lab billing optimizer with hemogram bundling and §2.2.2.B session factors.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from ..constants import HEMOGRAM_TESTS, BILUN_TO_SUT_CODE
from ..estimators import SUT_LAB_DEFAULT, _ensure_enrichment
from ..catalog import get_all_lab_prices, get_lab_price, lookup_procedure_code
from .types import LabOptimization

logger = logging.getLogger("ilay.sut_billing_optimizer")

_gazette_lab_prices_by_asof: dict[str, dict[str, float]] = {}


@dataclass
class _EncounterLabBucket:
    hemogram_subtests: int = 0
    entries: list[tuple[str, str, float]] = field(default_factory=list)
    service_date: Any | None = None


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


def _apply_session_fractions_to_encounter(
    billable: list[tuple[str, str, float]],
    *,
    flagged: list[dict[str, Any]],
) -> tuple[float, float]:
    """Return (normative_total, session_fraction_savings) for one encounter's billable lines."""
    from src.bilun.domain.prose_rules.session_pricing import compute_session_point_factors

    naive_total = sum(price for _, _, price in billable)
    if len(billable) < 2:
        return naive_total, 0.0

    codes = [code for _, code, _ in billable]
    session = compute_session_point_factors(
        codes,
        same_incision=True,
        cross_specialty=False,
    )
    if session.rule_id == "single_procedure" or not session.factors:
        return naive_total, 0.0

    adjusted_total = 0.0
    session_savings = 0.0
    primary_code = ""
    for (test_name, sut_code, price), factor in zip(
        billable, session.factors, strict=True
    ):
        line_amount = round(price * factor.point_factor, 2)
        adjusted_total += line_amount
        if factor.is_primary:
            primary_code = sut_code
        elif factor.point_factor < 1.0:
            line_savings = round(price * (1.0 - factor.point_factor), 2)
            if line_savings > 0:
                session_savings += line_savings
                flagged.append(
                    {
                        "test_name": test_name,
                        "sut_code": sut_code,
                        "gazette_price": round(price, 2),
                        "flag_type": "session_fraction_overbilling",
                        "savings_try": line_savings,
                        "expected_point_factor": factor.point_factor,
                        "primary_sut_code": primary_code,
                        "rule_id": session.rule_id,
                        "sut_section": session.sut_section,
                        "detail": (
                            f"Secondary lab billed at full list price; SUT §{session.sut_section} "
                            f"requires {factor.point_factor:.0%} point factor in same session "
                            f"(primary: {primary_code})."
                        ),
                    }
                )

    return round(adjusted_total, 2), round(session_savings, 2)


def _optimize_lab_billing(
    patient_id: str,
    patient_lab_tests: list[str],
    patient_lab_dates: list[str | None] | None = None,
    patient_lab_visit_ids: list[str | None] | None = None,
) -> LabOptimization:
    """Algorithm 1: Normative lab billing with hemogram bundling and session fractions.

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

    encounters: dict[str, _EncounterLabBucket] = {}
    encounter_asof: dict[str, Any | None] = {}
    orphan_normative = 0.0
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
                orphan_normative += _resolve_lab_test_price(
                    "Hemoglobin", visit_date=service_date
                )[0]
            else:
                orphan_normative += _resolve_lab_test_price(tn, visit_date=service_date)[0]
            continue

        bucket = encounters.setdefault(encounter_key, _EncounterLabBucket())
        if bucket.service_date is None and service_date is not None:
            bucket.service_date = service_date
            encounter_asof[encounter_key] = service_date

        if tn in hemogram_set:
            bucket.hemogram_subtests += 1
            continue

        price, sut_code, display_name = _resolve_lab_test_price(tn, visit_date=service_date)
        if sut_code:
            bucket.entries.append((display_name, sut_code, price))

    normative_total = orphan_normative
    session_fraction_savings = 0.0

    for enc_key, bucket in encounters.items():
        billable: list[tuple[str, str, float]] = []
        if bucket.hemogram_subtests > 0:
            hem_price = _hemogram_price_for_encounter(enc_key, encounter_asof)
            billable.append(("Hemogram (CBC)", hemogram_sut_code, hem_price))
        billable.extend(bucket.entries)

        enc_normative, enc_session_savings = _apply_session_fractions_to_encounter(
            billable,
            flagged=flagged,
        )
        normative_total += enc_normative
        session_fraction_savings += enc_session_savings

    total_hemogram_subtests = sum(b.hemogram_subtests for b in encounters.values())
    n_hemogram_encounters = sum(1 for b in encounters.values() if b.hemogram_subtests > 0)
    if total_hemogram_subtests > 0:
        excess = total_hemogram_subtests - n_hemogram_encounters
        if excess > 0:
            weighted_price = 0.0
            if n_hemogram_encounters > 0:
                for enc_key, bucket in encounters.items():
                    if bucket.hemogram_subtests > 0:
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

    result.normative_cost_try = round(normative_total, 2)
    result.session_fraction_savings = round(session_fraction_savings, 2)
    result.flagged_tests = flagged
    return result
