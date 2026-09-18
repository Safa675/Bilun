"""Contract tests for split SUT loader modules and import seams."""

from __future__ import annotations

import json

import pandas as pd
import pytest

pytestmark = pytest.mark.unit


def test_loaders_facade_exports_split_helpers():
    import src.bilun.domain.loaders as loaders

    assert callable(loaders._load_katsayi_history)
    assert callable(loaders.resolve_current_katsayi)
    assert callable(loaders._load_curated_ek2b_by_asof)
    assert callable(loaders._load_ek1a_exemptions)
    assert callable(loaders.get_cached_ek2a)


def test_katsayi_resolves_from_history_file():
    from src.bilun.domain.catalog import get_katsayi
    from src.bilun.domain.constants import DEFAULT_KATSAYI

    assert get_katsayi() == pytest.approx(DEFAULT_KATSAYI)


def test_katsayi_falls_back_when_history_missing(monkeypatch, tmp_path):
    import src.bilun.domain.loaders.katsayi as katsayi_loader
    from src.bilun.domain.constants import DEFAULT_KATSAYI

    monkeypatch.setattr(
        katsayi_loader, "KATSAYI_HISTORY_PATH", tmp_path / "missing-katsayi.json"
    )
    monkeypatch.setattr(katsayi_loader, "_katsayi_history_cache", None)

    assert katsayi_loader.resolve_current_katsayi() == DEFAULT_KATSAYI


def test_katsayi_prefers_open_ended_coefficient(monkeypatch, tmp_path):
    import src.bilun.domain.loaders.katsayi as katsayi_loader

    path = tmp_path / "katsayi.json"
    path.write_text(
        json.dumps(
            {
                "coefficients": [
                    {
                        "katsayi": 0.5,
                        "effective_from": "2010-01-01",
                        "effective_to": "2019-12-31",
                    },
                    {
                        "katsayi": 0.593,
                        "effective_from": "2020-01-01",
                        "effective_to": None,
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(katsayi_loader, "KATSAYI_HISTORY_PATH", path)
    monkeypatch.setattr(katsayi_loader, "_katsayi_history_cache", None)

    assert katsayi_loader.resolve_current_katsayi() == pytest.approx(0.593)


def test_gazette_curated_loaders_handle_missing_parquet(monkeypatch, tmp_path):
    import src.bilun.domain.loaders.gazette as gazette

    monkeypatch.setattr(gazette, "_ek2b_raw_cache", None)
    monkeypatch.setattr(gazette, "_ek2b_by_asof_cache", {})
    monkeypatch.setattr(gazette, "_ek2c_raw_cache", None)
    monkeypatch.setattr(gazette, "_ek2c_by_asof_cache", {})
    monkeypatch.setattr(
        gazette,
        "EK2B_CURATED_HISTORY_PATH",
        tmp_path / "missing-ek2b-history.parquet",
    )
    monkeypatch.setattr(
        gazette,
        "EK2C_CURATED_HISTORY_PATH",
        tmp_path / "missing-ek2c-history.parquet",
    )

    assert gazette._load_curated_ek2b_by_asof("2026-01-01") == {}

    ek2c = gazette._load_curated_ek2c_by_asof("2026-01-01")
    assert ek2c["packages"] == []
    assert ek2c["by_code"] == {}
    assert ek2c["stats"]["total_packages"] == 0


def test_legacy_loaders_handle_missing_parquet(monkeypatch, tmp_path):
    import src.bilun.domain.loaders.legacy as legacy

    monkeypatch.setattr(legacy, "EK1A_CURATED_PATH", tmp_path / "missing-ek1a.parquet")
    monkeypatch.setattr(legacy, "EK2G_CURATED_PATH", tmp_path / "missing-ek2g.parquet")
    monkeypatch.setattr(legacy, "EK2C1_CURATED_PATH", tmp_path / "missing-ek2c1.parquet")
    monkeypatch.setattr(legacy, "_ek1a_cache", None)
    monkeypatch.setattr(legacy, "_ek2g_cache", None)
    monkeypatch.setattr(legacy, "_ek2c1_cache", None)

    ek1a = legacy._load_ek1a_exemptions()
    assert ek1a.empty
    assert legacy._load_ek2g_no_surcharge() == {}
    assert legacy._load_ek2c1_copay_rates() == {}


def test_legacy_ek1a_loader_normalizes_malign_labels(monkeypatch, tmp_path):
    import src.bilun.domain.loaders.legacy as legacy

    ek1a_path = tmp_path / "ek1a.parquet"
    pd.DataFrame(
        {
            "icd10_start": ["C50"],
            "icd10_end": ["C50"],
            "disease_name_tr": ["Memenin Malıgn Neoplazmı"],
        }
    ).to_parquet(ek1a_path)

    monkeypatch.setattr(legacy, "EK1A_CURATED_PATH", ek1a_path)
    monkeypatch.setattr(legacy, "_ek1a_cache", None)

    ek1a = legacy._load_ek1a_exemptions()

    assert ek1a.loc[0, "disease_name_tr"] == "Memenin Malign Neoplazmı"


def test_public_sut_packages_export_expected_helpers():
    from src.bilun.domain.billing import compute_all_billing_reports
    from src.bilun.domain.optimization import compute_optimization_summary
    from src.bilun.domain.pricing import __all__ as pricing_exports

    assert "get_drg_package_price" not in pricing_exports
    assert "get_drg_package_price_for_date" not in pricing_exports
    assert callable(compute_optimization_summary)
    assert callable(compute_all_billing_reports)
