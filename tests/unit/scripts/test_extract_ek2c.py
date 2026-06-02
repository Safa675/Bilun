"""Unit tests for EK-2C catalog extraction (has_star column)."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

pytestmark = pytest.mark.unit

PROJECT_ROOT = Path(__file__).resolve().parents[3]
EK2C_RAW = (
    PROJECT_ROOT
    / "data/gazette/raw/annex=EK-2C/effective_date=2026-01-31"
    / "EK-2C_TANIYA_DAYALI_ISLEM_PUAN_LISTESI_Yur._31.01.2026__EK-2C.parquet"
)


class TestExtractEk2c:
    def test_extracts_has_star_from_2026_raw(self) -> None:
        from scripts.sut.catalogs.price_history import extract_ek2c

        if not EK2C_RAW.exists():
            pytest.skip(f"Raw EK-2C parquet missing: {EK2C_RAW}")

        raw = pd.read_parquet(EK2C_RAW)
        out = extract_ek2c(raw)

        assert "has_star" in out.columns
        assert out["has_star"].dtype == bool
        assert out["has_star"].sum() > 0
        assert out.loc[out["package_code"] == "P550970", "has_star"].iloc[0] == True

    def test_turkish_header_row_is_detected(self) -> None:
        from scripts.sut.catalogs.price_history import extract_ek2c

        if not EK2C_RAW.exists():
            pytest.skip(f"Raw EK-2C parquet missing: {EK2C_RAW}")

        raw = pd.read_parquet(EK2C_RAW)
        out = extract_ek2c(raw)
        assert len(out) > 1000


class TestCatalogMembershipStar:
    def test_procedure_has_star_lookup(self) -> None:
        from src.bilun.domain.prose_rules import catalog_membership

        catalog_membership.get_ek2c_codes_as_of.cache_clear()
        catalog_membership._ek2c_frame_asof.cache_clear()
        catalog_membership._ek2c_entry_map_asof.cache_clear()

        entry = catalog_membership.get_ek2c_entry("P550970")
        if entry is None:
            pytest.skip("P550970 not in curated EK-2C catalog")

        assert entry["has_star"] is True
        assert catalog_membership.procedure_has_star("550970") is True

    def test_payment_method_table_includes_override_rule(self) -> None:
        from src.bilun.domain.prose_rules.payment_method import load_decision_table

        table = load_decision_table()
        override = next(
            (rule for rule in table["rules"] if rule["rule_id"] == "2.2.2.(2).override"),
            None,
        )
        assert override is not None
        assert override["condition"]["procedure_has_star"] is False
        assert override["action"]["payment_method"] == "overridable"
