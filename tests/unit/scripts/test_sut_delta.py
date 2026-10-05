"""Unit tests for the SUT catalog delta computation."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import polars as pl
import pytest

from scripts.sut import sut_delta
from scripts.sut.sut_delta import (
    compute_all_deltas,
    compute_snapshot_delta,
    compute_temporal_delta,
    format_summary,
)

pytestmark = pytest.mark.unit


# ── Temporal delta tests ────────────────────────────────────────────────────


def _build_test_history(tmp_path: Path) -> Path:
    """Build a small curated history parquet with 3 versions for testing."""
    df = pl.DataFrame(
        {
            "code": [
                "100010", "100010", "100010",
                "100020", "100020", "100020",
                "100030", "100030", None,
                None, "100040", "100040",
                None, None, "100050",
            ],
            "puan": [
                100.0, 100.0, 100.0,
                200.0, 250.0, 250.0,
                300.0, 300.0, None,
                None, 400.0, 400.0,
                None, None, 500.0,
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
                "Test B", "Test B", "Test B Renamed",
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
    df = df.filter(pl.col("code").is_not_null())
    parquet_path = tmp_path / "test_catalog_history.parquet"
    df.write_parquet(parquet_path)
    return parquet_path


_TEMPORAL_SPEC = {
    "annex": "test",
    "file": "test_catalog_history.parquet",
    "key": "code",
    "value_cols": ["puan", "price_try", "name"],
}


def test_temporal_delta_detects_new_codes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Codes present in new but not old are detected."""
    _build_test_history(tmp_path)
    monkeypatch.setattr("scripts.sut.sut_delta.CURATED_DIR", tmp_path)
    delta = compute_temporal_delta(_TEMPORAL_SPEC, "2026-01-01", "2026-06-29")
    assert "100040" not in delta["new_codes"]  # existed in old slice
    assert "100050" in delta["new_codes"]       # new in v3


def test_temporal_delta_detects_removed_codes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _build_test_history(tmp_path)
    monkeypatch.setattr("scripts.sut.sut_delta.CURATED_DIR", tmp_path)
    delta = compute_temporal_delta(_TEMPORAL_SPEC, "2026-01-01", "2026-06-29")
    assert "100030" in delta["removed_codes"]


def test_temporal_delta_detects_price_changes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _build_test_history(tmp_path)
    monkeypatch.setattr("scripts.sut.sut_delta.CURATED_DIR", tmp_path)
    delta = compute_temporal_delta(_TEMPORAL_SPEC, "2025-01-01", "2026-06-29")
    price_codes = [pc["code"] for pc in delta["price_changes"]]
    assert "100020" in price_codes


def test_temporal_delta_detects_name_changes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _build_test_history(tmp_path)
    monkeypatch.setattr("scripts.sut.sut_delta.CURATED_DIR", tmp_path)
    delta = compute_temporal_delta(_TEMPORAL_SPEC, "2026-01-01", "2026-06-29")
    name_codes = [nc["code"] for nc in delta["name_changes"]]
    assert "100020" in name_codes


def test_temporal_delta_no_changes_same_date(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _build_test_history(tmp_path)
    monkeypatch.setattr("scripts.sut.sut_delta.CURATED_DIR", tmp_path)
    delta = compute_temporal_delta(_TEMPORAL_SPEC, "2026-06-29", "2026-06-29")
    assert len(delta["new_codes"]) == 0
    assert len(delta["removed_codes"]) == 0
    assert len(delta["price_changes"]) == 0
    assert len(delta["name_changes"]) == 0


def test_temporal_delta_missing_parquet(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("scripts.sut.sut_delta.CURATED_DIR", tmp_path)
    delta = compute_temporal_delta(
        {"annex": "nonexistent", "file": "nope.parquet", "key": "code", "value_cols": ["puan"]},
        "2026-01-01", "2026-06-29",
    )
    assert "error" in delta


# ── Snapshot delta tests ────────────────────────────────────────────────────


def test_snapshot_delta_reports_row_count_and_hash(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Snapshot delta returns row_count and content_hash for non-temporal parquets."""
    monkeypatch.setattr("scripts.sut.sut_delta.CURATED_DIR", tmp_path)

    df = pl.DataFrame({"sut_code": ["A1", "A2", "A3"], "price": [100, 200, 300]})
    df.write_parquet(tmp_path / "test_snapshot.parquet")

    delta = compute_snapshot_delta("test_snap", "test_snapshot.parquet", "2026-01-01", "2026-06-29")
    assert delta["type"] == "snapshot"
    assert delta["row_count"] == 3
    assert "content_hash" in delta
    assert len(delta["content_hash"]) > 0


def test_snapshot_delta_missing_parquet(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("scripts.sut.sut_delta.CURATED_DIR", tmp_path)
    delta = compute_snapshot_delta("missing", "nonexistent.parquet", "2026-01-01", "2026-06-29")
    assert "error" in delta


def test_snapshot_delta_different_content_different_hash(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Two parquets with same row count but different content produce different hashes."""
    monkeypatch.setattr("scripts.sut.sut_delta.CURATED_DIR", tmp_path)

    pl.DataFrame({"sut_code": ["A1", "A2"], "price": [100, 200]}).write_parquet(
        tmp_path / "snap_a.parquet"
    )
    pl.DataFrame({"sut_code": ["A1", "A2"], "price": [100, 999]}).write_parquet(
        tmp_path / "snap_b.parquet"
    )

    delta_a = compute_snapshot_delta("a", "snap_a.parquet", "2026-01-01", "2026-06-29")
    delta_b = compute_snapshot_delta("b", "snap_b.parquet", "2026-01-01", "2026-06-29")
    assert delta_a["content_hash"] != delta_b["content_hash"]


# ── Compute-all-deltas integration test ─────────────────────────────────────


def test_compute_all_deltas_returns_both_types(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """compute_all_deltas returns both temporal and snapshot deltas."""
    # Build a temporal parquet
    _build_test_history(tmp_path)

    # Build a snapshot parquet
    pl.DataFrame({"code": ["X1", "X2"], "name": ["A", "B"]}).write_parquet(
        tmp_path / "ek3a_materials.parquet"
    )

    monkeypatch.setattr("scripts.sut.sut_delta.CURATED_DIR", tmp_path)
    monkeypatch.setattr(
        "scripts.sut.sut_delta._TEMPORAL_SPECS",
        [{"annex": "test", "file": "test_catalog_history.parquet", "key": "code", "value_cols": ["puan"]}],
    )

    deltas = compute_all_deltas("2026-01-01", "2026-06-29")
    types = [d["type"] for d in deltas]
    assert "temporal" in types
    assert "snapshot" in types


# ── Format summary tests ────────────────────────────────────────────────────


def test_format_summary_handles_errors() -> None:
    """format_summary gracefully handles error entries."""
    deltas = [
        {"annex": "test", "error": "parquet not found", "type": "temporal"},
        {
            "annex": "ek2b",
            "type": "temporal",
            "old_count": 100,
            "new_count": 105,
            "new_codes": ["X1", "X2"],
            "removed_codes": [],
            "common_codes": 100,
            "price_changes": [{"code": "A1", "field": "puan", "old": "100", "new": "200"}],
            "name_changes": [],
        },
        {
            "annex": "ek3a materials",
            "type": "snapshot",
            "row_count": 401,
            "col_count": 6,
            "content_hash": "abc123",
            "note": "snapshot",
        },
    ]
    summary = format_summary(deltas)
    assert "⚠️" in summary
    assert "EK2B" in summary  # format_summary uppercases temporal annex names
    assert "+5" in summary
    assert "ek3a materials" in summary
    assert "abc123" in summary


@pytest.fixture
def delta_report_inputs(tmp_path, monkeypatch):
    history_path = _build_test_history(tmp_path)
    snapshot_path = tmp_path / "snapshot.parquet"
    pl.DataFrame({"code": ["X1", "X2"], "price": [100, 200]}).write_parquet(snapshot_path)
    monkeypatch.setattr(sut_delta, "CURATED_DIR", tmp_path)
    monkeypatch.setattr(sut_delta, "DELTA_DIR", tmp_path / "reports")
    monkeypatch.setattr(sut_delta, "_TEMPORAL_SPECS", [_TEMPORAL_SPEC])
    monkeypatch.delenv("GITHUB_OUTPUT", raising=False)
    return history_path, snapshot_path, tmp_path / "reports" / "2026-06-29_delta.json"


def _run_delta_report(monkeypatch, *, old_date="2026-01-01", legacy_proof=None):
    argv = ["sut_delta", old_date, "2026-06-29"]
    if legacy_proof is not None:
        argv.extend(["--legacy-input-fingerprints", str(legacy_proof)])
    monkeypatch.setattr("sys.argv", argv)
    return sut_delta.main()


def test_new_delta_report_records_typed_input_fingerprints(delta_report_inputs, monkeypatch):
    _, _, report = delta_report_inputs
    assert _run_delta_report(monkeypatch) == 0
    payload = json.loads(report.read_text())
    fingerprints = payload["input_fingerprints"]
    assert fingerprints["algorithm"] == "sha256-typed-catalog-inputs-v1"
    assert set(fingerprints["catalogs"]) == {"snapshot.parquet", "test_catalog_history.parquet"}
    assert all(len(value) == 64 for value in fingerprints["catalogs"].values())


def test_delta_rerun_preserves_bytes_across_row_order_and_encoding(delta_report_inputs, monkeypatch):
    history, snapshot, report = delta_report_inputs
    _run_delta_report(monkeypatch)
    original = report.read_bytes()
    for path in (history, snapshot):
        pl.read_parquet(path).reverse().write_parquet(path, compression="uncompressed")
    assert _run_delta_report(monkeypatch) == 0
    assert report.read_bytes() == original


def test_delta_different_catalog_content_cannot_overwrite_history(delta_report_inputs, monkeypatch):
    _, snapshot, report = delta_report_inputs
    _run_delta_report(monkeypatch)
    original = report.read_bytes()
    pl.DataFrame({"code": ["X1", "X2"], "price": [100, 999]}).write_parquet(snapshot)
    with pytest.raises(ValueError, match="Refusing to overwrite historical delta report"):
        _run_delta_report(monkeypatch)
    assert report.read_bytes() == original


def test_delta_fingerprint_detects_dtype_change_hidden_by_legacy_csv_hash(delta_report_inputs, monkeypatch):
    _, snapshot, report = delta_report_inputs
    _run_delta_report(monkeypatch)
    original = report.read_bytes()
    before = compute_snapshot_delta("snapshot", snapshot.name, "2026-01-01", "2026-06-29")
    pl.read_parquet(snapshot).with_columns(pl.col("price").cast(pl.String)).write_parquet(snapshot)
    after = compute_snapshot_delta("snapshot", snapshot.name, "2026-01-01", "2026-06-29")
    assert before == after  # The old string-cast hash alone cannot distinguish these inputs.
    with pytest.raises(ValueError, match="source transition differs"):
        _run_delta_report(monkeypatch)
    assert report.read_bytes() == original


def test_delta_self_comparison_cannot_erase_historical_transition(delta_report_inputs, monkeypatch):
    _, _, report = delta_report_inputs
    _run_delta_report(monkeypatch)
    original = report.read_bytes()
    with pytest.raises(ValueError, match="Refusing to overwrite historical delta report"):
        _run_delta_report(monkeypatch, old_date="2026-06-29")
    assert report.read_bytes() == original


def test_legacy_delta_same_comparison_is_byte_preserving(delta_report_inputs, monkeypatch, capsys):
    _, _, report = delta_report_inputs
    _run_delta_report(monkeypatch)
    payload = json.loads(report.read_text())
    fingerprints = payload.pop("input_fingerprints")
    report.write_text(json.dumps(payload))
    proof = report.with_name("delta-input-fingerprints.json")
    proof.write_text(json.dumps({
        "report_sha256": hashlib.sha256(report.read_bytes()).hexdigest(),
        "input_fingerprints": fingerprints,
    }))
    original = report.read_bytes()
    capsys.readouterr()
    assert _run_delta_report(monkeypatch, legacy_proof=proof) == 0
    assert report.read_bytes() == original
    assert "using verified typed input fingerprints" in capsys.readouterr().out


def test_legacy_delta_conflict_preserves_existing_bytes(delta_report_inputs, monkeypatch):
    _, snapshot, report = delta_report_inputs
    _run_delta_report(monkeypatch)
    payload = json.loads(report.read_text())
    payload.pop("input_fingerprints")
    report.write_text(json.dumps(payload))
    original = report.read_bytes()
    pl.DataFrame({"code": ["X1", "X2"], "price": [100, 999]}).write_parquet(snapshot)
    with pytest.raises(ValueError, match="cannot be verified"):
        _run_delta_report(monkeypatch)
    assert report.read_bytes() == original


def test_legacy_delta_without_proof_cannot_claim_an_exact_rerun(delta_report_inputs, monkeypatch):
    _, _, report = delta_report_inputs
    _run_delta_report(monkeypatch)
    payload = json.loads(report.read_text())
    payload.pop("input_fingerprints")
    report.write_text(json.dumps(payload))
    original = report.read_bytes()
    with pytest.raises(ValueError, match="cannot be verified"):
        _run_delta_report(monkeypatch)
    assert report.read_bytes() == original


@pytest.mark.parametrize("first,second", [
    (None, float("nan")), (None, float("inf")),
    (None, -float("inf")), (float("nan"), float("inf")),
])
def test_delta_fingerprint_distinguishes_null_and_nonfinite_prices(
    delta_report_inputs, monkeypatch, first, second,
):
    _, snapshot, report = delta_report_inputs
    pl.DataFrame({
        "code": ["X1", "X2"], "price": pl.Series([first, 100.0], dtype=pl.Float64),
    }).write_parquet(snapshot)
    _run_delta_report(monkeypatch)
    original = report.read_bytes()
    pl.DataFrame({
        "code": ["X1", "X2"], "price": pl.Series([second, 100.0], dtype=pl.Float64),
    }).write_parquet(snapshot)
    with pytest.raises(ValueError, match="source transition differs"):
        _run_delta_report(monkeypatch)
    assert report.read_bytes() == original
