"""Focused unit tests for canonical temporal SUT pricing helpers."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit


def test_get_ek2b_price_for_date_uses_canonical_catalog(monkeypatch):
    import src.bilun.domain.pricing.temporal as temporal

    fake_catalog = {
        "ek2b": {
            "by_code": {
                "551320": {
                    "code": "551320",
                    "price_try": 122.15,
                    "puan": 45.0,
                    "effective_date": "2023-03-24",
                }
            }
        }
    }

    monkeypatch.setattr(temporal, "load_sut_catalog", lambda visit_date=None: fake_catalog)

    assert temporal.get_ek2b_price_for_date("551.320", "2023-06-15") == 122.15
    assert temporal.get_ek2b_price_for_date("551320", "2023-01-01") is None
    assert temporal.get_ek2b_price_for_date("551320", "2023-06-15", "puan") == 45.0


def test_get_ek2c_price_for_date_uses_canonical_catalog(monkeypatch):
    import src.bilun.domain.pricing.temporal as temporal

    fake_catalog = {
        "ek2c": {
            "by_code": {
                "P613380": {
                    "package_code": "P613380",
                    "price_try": 5274.86,
                    "effective_date": "2023-03-24",
                }
            }
        }
    }

    monkeypatch.setattr(temporal, "load_sut_catalog", lambda visit_date=None: fake_catalog)

    assert temporal.get_ek2c_price_for_date("P613380", "2023-06-15") == 5274.86
    assert temporal.get_ek2c_price_for_date("P613380", "2023-01-01") is None
