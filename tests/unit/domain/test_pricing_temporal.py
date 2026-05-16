"""Focused unit tests for canonical temporal SUT pricing helpers."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def _reset_drg_caches():
    import src.bilun.domain.pricing.drg as drg

    drg._ek2c_group_medians = None
    drg._ek2c_chapter_medians = None
    drg._ek2c_exact_medians_by_asof.clear()
    yield
    drg._ek2c_group_medians = None
    drg._ek2c_chapter_medians = None
    drg._ek2c_exact_medians_by_asof.clear()


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


def test_get_drg_package_price_for_date_uses_true_keyword_filtered_median(monkeypatch):
    import src.bilun.domain.pricing.drg as drg

    fake_catalog = {
        "ek2c": {
            "packages": [
                {
                    "package_code": "PKG-1",
                    "group": "A3",
                    "name": "Koroner bypass paketi",
                    "price_try": 100.0,
                    "effective_date": "2023-03-24",
                },
                {
                    "package_code": "PKG-2",
                    "group": "A3",
                    "name": "Kalp kapak paketi",
                    "price_try": 300.0,
                    "effective_date": "2023-03-24",
                },
                {
                    "package_code": "PKG-3",
                    "group": "A3",
                    "name": "Genel cerrahi paketi",
                    "price_try": 900.0,
                    "effective_date": "2023-03-24",
                },
            ]
        }
    }

    monkeypatch.setattr(drg, "load_sut_catalog", lambda visit_date=None: fake_catalog)

    assert drg.get_drg_package_price_for_date("I", "2023-06-15", "I10") == 200.0


def test_get_drg_package_price_for_date_falls_back_to_dated_group_median(monkeypatch):
    import src.bilun.domain.pricing.drg as drg

    fake_catalog = {
        "ek2c": {
            "packages": [
                {
                    "package_code": "PKG-1",
                    "group": "C",
                    "name": "Genel dahiliye paketi",
                    "price_try": 10.0,
                    "effective_date": "2023-03-24",
                },
                {
                    "package_code": "PKG-2",
                    "group": "C",
                    "name": "Genel servis paketi",
                    "price_try": 30.0,
                    "effective_date": "2023-03-24",
                },
            ]
        }
    }

    monkeypatch.setattr(drg, "load_sut_catalog", lambda visit_date=None: fake_catalog)

    assert drg.get_drg_package_price_for_date("E", "2023-06-15") == 20.0


def test_get_drg_package_price_for_date_does_not_fall_forward_from_prehistory(monkeypatch):
    import src.bilun.domain.pricing.drg as drg

    fake_catalog = {
        "ek2c": {
            "packages": [
                {
                    "package_code": "PKG-1",
                    "group": "A3",
                    "name": "Koroner bypass paketi",
                    "price_try": 100.0,
                    "effective_date": "2024-01-01",
                }
            ]
        }
    }

    monkeypatch.setattr(drg, "load_sut_catalog", lambda visit_date=None: fake_catalog)

    assert drg.get_drg_package_price_for_date("I", "2023-06-15", "I10") is None


def test_temporal_drg_price_wrapper_delegates_to_canonical_helper(monkeypatch):
    import src.bilun.domain.pricing.temporal as temporal

    captured: dict[str, object] = {}

    def fake_get_drg_package_price_for_date(**kwargs):
        captured.update(kwargs)
        return 321.0

    monkeypatch.setattr(
        temporal,
        "_get_drg_package_price_for_date",
        fake_get_drg_package_price_for_date,
    )

    assert temporal.get_drg_package_price_for_date("I", "2023-06-15", "I10") == 321.0
    assert captured == {
        "icd10_chapter": "I",
        "procedure_date": "2023-06-15",
        "icd10_code": "I10",
    }
