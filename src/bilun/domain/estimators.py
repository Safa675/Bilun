"""
Legacy SUT price lookup seam.

This module intentionally no longer exposes patient cost estimators. It remains
only to preserve exact lab/visit price lookup helpers used by rule-based SUT
billing code while callers migrate to more specific modules.
"""

from __future__ import annotations

import logging

from .catalog import lookup_ek2a_visit_price_try
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


def enrich_visit_prices_from_claim_header(
    *,
    specialty_code: str | None,
    facility_tier: str | None = None,
    provider_type: str | None = None,
) -> bool:
    """Update outpatient/emergency visit prices from EK-2A when tier + specialty are known.

    Returns True when an exact EK-2A tier row was applied; False when inputs are
    incomplete or no tier-specific price exists (gazette fallbacks remain).
    """
    code = str(specialty_code or "").strip()
    if not code or not (facility_tier or provider_type):
        return False

    try:
        price, method = lookup_ek2a_visit_price_try(
            code,
            facility_tier=facility_tier,
            provider_type=provider_type,
        )
    except Exception as exc:
        logger.debug("EK-2A visit enrichment skipped: %s", exc)
        return False

    if price is None or method != "ek2a_tier_row":
        return False

    SUT_VISIT_PRICES["outpatient"] = (price, price)
    SUT_VISIT_PRICES["emergency"] = (price, price)
    logger.info(
        "Visit prices enriched from EK-2A %s: %.2f TRY (%s)",
        code,
        price,
        method,
    )
    return True
