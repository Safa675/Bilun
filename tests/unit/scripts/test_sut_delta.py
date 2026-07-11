"""Unit tests for the SUT catalog delta computation."""

from __future__ import annotations

from pathlib import Path

import polars as pl
import pytest

from scripts.sut.sut_delta import compute_catalog_delta, format_summary

pytestmark = pytest.mark.unit


def _build_test_history(tmp_path: Path) -> Path:
    """Build a small curated history parquet with 3 versions for testing.

    Schema mirrors the real ek2b_catalog_history.parquet structure.
    """
    df = pl.DataFrame(
        {
            "code": [
                "100010", "100010", "100010",  # unchanged across versions
                "100020", "100020", "100020",  # price changes
                "100030", "100030", None,       # removed in v3
                None, "100040", "100040",       # new in v2
                None, None, "100050",           # new in v3
            ],
            "puan": [
                100.0, 100.0, 100.0,  # unchanged
                200.0, 250.0, 250.0,  # price change v1→v2
                300.0, 300.0, None,   # removed
                None, 400.0, 400.0,   # new in v2
                None, None, 500.0,    # new in v3
            ],
            "price_try": [
                59.3, 59.3, 59.3,
                118.6, 148.25, 148.25,
                177.9, 177.9, None,
                None, 237.2, 237.2,
                None, None, 296.5,
            ],
            "name": [
                "Test A", "Test A", "Test A",
                "Test B", "Test B", "Test B Renamed",  # name change v2→v3
                "Test C", "Test C", "",
                "", "Test D", "Test D",
                "", "", "Test E",
            ],
            "effective_date": [
                "2025-01-01", "2026-01-01", "2026-06-29",
                "2025-01-01", "2026-01-01", "2026-06-29",
                "2025-01-01", "2026-01-01", "",
                "", "2026-01-01", "2026-06-29",
                "", "", "2026-06-29",
            ],
            "valid_from": [
                "2025-01-01", "2026-01-01", "2026-06-29",
                "2025-01-01", "2026-01-01", "2026-06-29",
                "2025-01-01", "2026-01-01", None,
                None, "2026-01-01", "2026-06-29",
                None, None, "2026-06-29",
            ],
            "valid_to": [
                "2025-12-31", "2026-06-28", None,
                "2025-12-31", "2026-06-28", None,
                "2025-12-31", "2026-06-28", None,
                None, "2026-06-28", None,
                None, None, None,
            ],
        }
    )
    # Filter out None code rows (they're just padding for alignment)
    df = df.filter(pl.col("code").is_not_null())

    parquet_path = tmp_path / "test_catalog_history.parquet"
    df.write_parquet(parquet_path)
    return parquet_path


def test_delta_detects_new_codes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Codes present in new but not old are detected."""
    parquet_path = _build_test_history(tmp_path)
    monkeypatch.setattr(
        "scripts.sut.sut_delta.CURATED_DIR", tmp_path
    )

    delta = compute_catalog_delta(
        "test", "code", ["puan", "price_try", "name"],
        "2026-01-01", "2026-06-29",
    )

    assert "100040" not in delta["new_codes"]  # existed in old slice
    assert "100050" in delta["new_codes"]       # new in v3


def test_delta_detects_removed_codes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Codes present in old but not new are detected."""
    parquet_path = _build_test_history(tmp_path)
    monkeypatch.setattr("scripts.sut.sut_delta.CURATED_DIR", tmp_path)

    delta = compute_catalog_delta(
        "test", "code", ["puan", "price_try", "name"],
        "2026-01-01", "2026-06-29",
    )

    assert "100030" in delta["removed_codes"]


def test_delta_detects_price_changes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Price changes for common codes are detected."""
    parquet_path = _build_test_history(tmp_path)
    monkeypatch.setattr("scripts.sut.sut_delta.CURATED_DIR", tmp_path)

    delta = compute_catalog_delta(
        "test", "code", ["puan", "price_try", "name"],
        "2025-01-01", "2026-06-29",
    )

    price_codes = [pc["code"] for pc in delta["price_changes"]]
    # 100020 had puan 200 → 250
    assert "100020" in price_codes


def test_delta_detects_name_changes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Name changes for common codes are detected separately from price."""
    parquet_path = _build_test_history(tmp_path)
    monkeypatch.setattr("scripts.sut.sut_delta.CURATED_DIR", tmp_path)

    delta = compute_catalog_delta(
        "test", "code", ["puan", "price_try", "name"],
        "2026-01-01", "2026-06-29",
    )

    name_codes = [nc["code"] for nc in delta["name_changes"]]
    # 100020 had "Test B" → "Test B Renamed"
    assert "100020" in name_codes


def test_delta_no_changes_same_date(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """When old_date == new_date, no changes are detected."""
    parquet_path = _build_test_history(tmp_path)
    monkeypatch.setattr("scripts.sut.sut_delta.CURATED_DIR", tmp_path)

    delta = compute_catalog_delta(
        "test", "code", ["puan", "price_try", "name"],
        "2026-06-29", "2026-06-29",
    )

    assert len(delta["new_codes"]) == 0
    assert len(delta["removed_codes"]) == 0
    assert len(delta["price_changes"]) == 0
    assert len(delta["name_changes"]) == 0


def test_delta_missing_parquet(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Missing parquet returns error dict, not crash."""
    monkeypatch.setattr("scripts.sut.sut_delta.CURATED_DIR", tmp_path)
    delta = compute_catalog_delta(
        "nonexistent", "code", ["puan"], "2026-01-01", "2026-06-29"
    )
    assert "error" in delta


def test_format_summary_handles_errors() -> None:
    """format_summary gracefully handles error entries."""
    deltas = [
        {"annex": "test", "error": "parquet not found"},
        {
            "annex": "ek2b",
            "old_count": 100,
            "new_count": 105,
            "new_codes": ["X1", "X2"],
            "removed_codes": [],
            "common_codes": 100,
            "price_changes": [{"code": "A1", "field": "puan", "old": "100", "new": "200"}],
            "name_changes": [],
        },
    ]
    summary = format_summary(deltas)
    assert "⚠️" in summary
    assert "EK2B" in summary  # format_summary uppercases annex names
    assert "+5" in summary  # +5 codes
