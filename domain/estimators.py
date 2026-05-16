"""
Legacy SUT price lookup seam.

This module intentionally no longer exposes patient cost estimators. It remains
only to preserve exact lab/visit price lookup helpers used by rule-based SUT
billing code while callers migrate to more specific modules.
"""

from __future__ import annotations

import logging

from .catalog import get_ek2a_visit_prices
from .constants import _FALLBACK_LAB_PRICES, _FALLBACK_VISIT_PRICES
from .loaders import _load_gazette_lab_prices, _load_gazette_visit_prices
from .runtime_state import get_sut_runtime_state

logger = logging.getLogger("ilay.sut_pricing")

_RUNTIME_STATE = get_sut_runtime_state()

# Legacy import seam consumed by exact lab billing code.
SUT_LAB_PRICES: dict[str, tuple[float, float]] = _RUNTIME_STATE.sut_lab_prices
_SUT_LAB_PRICES_LOWER: dict[str, tuple[float, float]] = _RUNTIME_STATE.sut_lab_prices_lower
SUT_LAB_DEFAULT: tuple[float, float] = _RUNTIME_STATE.sut_lab_default
SUT_VISIT_PRICES: dict[str, tuple[float, float]] = _RUNTIME_STATE.sut_visit_prices


def _ensure_enrichment() -> None:
    """Populate gazette price dictionaries on first use."""
    state = _RUNTIME_STATE
    if state.enrichment_done:
        return

    state.enrichment_done = True

    lab_prices = _load_gazette_lab_prices(_FALLBACK_LAB_PRICES)
    state.sut_lab_prices.clear()
    state.sut_lab_prices.update(lab_prices)

    state.sut_lab_prices_lower.clear()
    state.sut_lab_prices_lower.update({k.lower(): v for k, v in state.sut_lab_prices.items()})

    visit_prices = _load_gazette_visit_prices(_FALLBACK_VISIT_PRICES)
    state.sut_visit_prices.clear()
    state.sut_visit_prices.update(visit_prices)

    _enrich_visit_prices_from_ek2a()
    logger.info("Gazette price lookup enrichment completed")


def get_sut_lab_prices() -> dict[str, tuple[float, float]]:
    """Return enriched SUT lab prices from runtime state."""
    _ensure_enrichment()
    return _RUNTIME_STATE.sut_lab_prices


def get_sut_visit_prices() -> dict[str, tuple[float, float]]:
    """Return enriched SUT visit prices from runtime state."""
    _ensure_enrichment()
    return _RUNTIME_STATE.sut_visit_prices


def get_sut_lab_default() -> tuple[float, float]:
    """Return the default lab price tuple used for unknown lab tests."""
    return _RUNTIME_STATE.sut_lab_default


def _enrich_visit_prices_from_ek2a() -> None:
    """Update visit prices with exact EK-2A outpatient pricing when available."""
    try:
        ek2a_data = get_ek2a_visit_prices()
        specialties = ek2a_data.get("specialties", [])
        if not specialties:
            return

        all_prices = []
        for specialty in specialties:
            all_prices.extend(specialty.get("prices_try", {}).values())

        if all_prices:
            outpatient_price = round(sum(all_prices) / len(all_prices), 2)
            SUT_VISIT_PRICES["outpatient"] = (outpatient_price, outpatient_price)
            SUT_VISIT_PRICES["emergency"] = (outpatient_price, outpatient_price)
            logger.info("Visit prices enriched from EK-2A: %.2f TRY", outpatient_price)
    except Exception as exc:
        logger.debug("EK-2A enrichment skipped: %s", exc)
