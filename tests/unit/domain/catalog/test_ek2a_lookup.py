"""EK-2A tier-aware visit lookup (L4.3)."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit


def test_lookup_ek2a_visit_price_try_returns_price(monkeypatch) -> None:
    from src.bilun.domain import catalog as cat

    monkeypatch.setattr(
        cat,
        "get_ek2a_visit_prices",
        lambda: {
            "specialties": [
                {
                    "code": "5200",
                    "name": "Dahiliye",
                    "section": "1",
                    "prices_try": {"B": 100.0, "A1": 200.0, "U1": 250.0},
                }
            ]
        },
    )

    price, method = cat.lookup_ek2a_visit_price_try(
        "5200",
        facility_tier="2_basamak_kamu",
    )
    assert price == 100.0
    assert method == "ek2a_tier_row"

    price3, method3 = cat.lookup_ek2a_visit_price_try(
        "5200",
        facility_tier="3_basamak",
        provider_type="egitim_arastirma",
    )
    assert price3 == 250.0
    assert method3 == "ek2a_tier_row"


def test_lookup_ek2a_visit_price_try_unresolved_tier(monkeypatch) -> None:
    from src.bilun.domain import catalog as cat

    monkeypatch.setattr(
        cat,
        "get_ek2a_visit_prices",
        lambda: {
            "specialties": [
                {
                    "code": "5200",
                    "name": "Dahiliye",
                    "section": "1",
                    "prices_try": {"B": 100.0, "A1": 200.0, "U1": 250.0},
                }
            ]
        },
    )

    price, method = cat.lookup_ek2a_visit_price_try("5200", facility_tier="devlet")
    assert price is None
    assert method == "missing_facility_tier"
