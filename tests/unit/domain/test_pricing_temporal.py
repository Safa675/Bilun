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


def test_expired_code_804460_respects_valid_to_in_temporal_and_membership():
    import src.bilun.domain.pricing.temporal as temporal
    from src.bilun.domain.prose_rules.catalog_membership import get_ek2b_codes_as_of

    assert temporal.get_ek2b_price_for_date("804460", "2020-06-01") == pytest.approx(67.92, abs=0.01)
    assert temporal.get_ek2b_price_for_date("804460", "2024-08-01") is None
    assert "804460" in get_ek2b_codes_as_of("2020-06-01")
    assert "804460" not in get_ek2b_codes_as_of("2024-08-01")


def test_curated_history_parquets_have_no_inverted_validity_or_duplicate_valid_from():
    import polars as pl
    from src.bilun.domain.constants import (
        EK2B_CURATED_HISTORY_PATH,
        EK2C_CURATED_HISTORY_PATH,
        EK2C_DENTAL_CURATED_HISTORY_PATH,
    )

    for path, key_col in (
        (EK2B_CURATED_HISTORY_PATH, "code"),
        (EK2C_CURATED_HISTORY_PATH, "package_code"),
        (EK2C_DENTAL_CURATED_HISTORY_PATH, "code"),
    ):
        df = pl.read_parquet(path)
        inverted = df.filter(
            pl.col("valid_to").is_not_null() & (pl.col("valid_to") < pl.col("valid_from"))
        )
        assert len(inverted) == 0, f"{path.name} has rows with valid_to < valid_from"
        dups = df.group_by([key_col, "valid_from"]).len().filter(pl.col("len") > 1)
        assert len(dups) == 0, f"{path.name} has duplicate ({key_col}, valid_from) rows"

