"""Tests for legacy estimators visit-price enrichment (exact tier row only)."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit


def _reset_runtime_state() -> None:
    from src.bilun.domain.runtime_state import get_sut_runtime_state

    state = get_sut_runtime_state()
    state.enrichment_done = False
    state.sut_visit_prices.clear()
    state.sut_lab_prices.clear()
    state.sut_lab_prices_lower.clear()


def test_enrich_visit_prices_requires_tier_and_specialty(monkeypatch) -> None:
    from src.bilun.domain import estimators

    _reset_runtime_state()
    estimators.SUT_VISIT_PRICES["outpatient"] = (85.73, 85.73)

    lookup = monkeypatch.setattr(
        estimators,
        "lookup_ek2a_visit_price_try",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("lookup should not run without tier + specialty")
        ),
    )
    _ = lookup

    assert estimators.enrich_visit_prices_from_claim_header(specialty_code="1000") is False
    assert estimators.SUT_VISIT_PRICES["outpatient"] == (85.73, 85.73)


def test_enrich_visit_prices_rejects_specialty_mean_fallback(monkeypatch) -> None:
    from src.bilun.domain import estimators

    _reset_runtime_state()
    estimators.SUT_VISIT_PRICES["outpatient"] = (85.73, 85.73)

    monkeypatch.setattr(
        estimators,
        "lookup_ek2a_visit_price_try",
        lambda *_args, **_kwargs: (120.0, "ek2a_specialty_mean"),
    )

    assert (
        estimators.enrich_visit_prices_from_claim_header(
            specialty_code="1000",
            facility_tier="3",
        )
        is False
    )
    assert estimators.SUT_VISIT_PRICES["outpatient"] == (85.73, 85.73)


def test_enrich_visit_prices_applies_exact_tier_row(monkeypatch) -> None:
    from src.bilun.domain import estimators

    _reset_runtime_state()
    estimators.SUT_VISIT_PRICES["outpatient"] = (85.73, 85.73)

    monkeypatch.setattr(
        estimators,
        "lookup_ek2a_visit_price_try",
        lambda *_args, **_kwargs: (142.5, "ek2a_tier_row"),
    )

    assert (
        estimators.enrich_visit_prices_from_claim_header(
            specialty_code="1000",
            facility_tier="3",
            provider_type="EAH",
        )
        is True
    )
    assert estimators.SUT_VISIT_PRICES["outpatient"] == (142.5, 142.5)
    assert estimators.SUT_VISIT_PRICES["emergency"] == (142.5, 142.5)
