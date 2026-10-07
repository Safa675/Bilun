"""Snapshot date guards and byte-preserving curated catalog reruns."""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import pandas as pd
import pytest

from scripts.sut import _common as common
from scripts.sut import build_curated_catalogs as builder

pytestmark = pytest.mark.unit

AS_OF = dt.date(2026, 10, 5)
PACKAGE_SUFFIX = "Değişiklik Tebliği İşlenmiş Güncel 2013 SUT"


def _raw(
    root: Path,
    effective_date: str = "unknown",
    *,
    name: str = "current.parquet",
    package_date: str | None = None,
    frame: pd.DataFrame | None = None,
) -> Path:
    path = root / "raw" / "annex=EK-TEST" / f"effective_date={effective_date}" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    data = frame.copy() if frame is not None else pd.DataFrame({"code": ["001"], "value": [1]})
    if package_date is not None:
        package = f"{package_date}-{PACKAGE_SUFFIX}"
        data["__source_file"] = f"raw data/{package}/EK-TEST.xlsx"
    data.to_parquet(path, index=False)
    return path


def _extract(raw: pd.DataFrame) -> pd.DataFrame:
    return raw[["code", "value"]].copy()


def _run_builder(
    monkeypatch: pytest.MonkeyPatch, root: Path, *, source: str = "raw_latest"
) -> int:
    spec = {
        "annex": "EK-TEST",
        "output": "test.parquet",
        "source": source,
        "extractor": _extract,
        "label": "Test catalog",
        "history_key": "code",
    }
    monkeypatch.setattr(builder, "CATALOG_SPECS", [spec])
    monkeypatch.setattr(
        "sys.argv",
        ["build_curated_catalogs", "--parquet-root", str(root), "--overwrite", "--as-of", AS_OF.isoformat()],
    )
    return builder.main()


def test_effective_date_boundary_and_later_future_are_not_selected(tmp_path: Path) -> None:
    previous = _raw(tmp_path, "2026-10-04")
    boundary = _raw(tmp_path, "2026-10-05")
    _raw(tmp_path, "2026-10-06")
    assert common._find_raw_parquet(tmp_path, "EK-TEST", as_of=AS_OF) == boundary
    assert common._find_raw_parquet(tmp_path, "EK-TEST", as_of=AS_OF - dt.timedelta(days=1)) == previous


@pytest.mark.parametrize("effective_date", ["unknown", "2026-10-01"])
def test_future_source_package_is_excluded_even_if_partition_is_not_future(
    tmp_path: Path, effective_date: str
) -> None:
    _raw(tmp_path, effective_date, package_date="2026.10.06")
    assert common._find_raw_parquet(tmp_path, "EK-TEST", as_of=AS_OF) is None
    assert common._read_raw(tmp_path, "EK-TEST", as_of=AS_OF) is None


def test_unknown_partition_source_package_boundary_is_inclusive(tmp_path: Path) -> None:
    path = _raw(tmp_path, package_date="2026.10.05")
    assert common._find_raw_parquet(tmp_path, "EK-TEST", as_of=AS_OF) == path


def test_any_future_source_in_a_candidate_prevents_activation(tmp_path: Path) -> None:
    path = _raw(tmp_path, package_date="2026.10.04")
    data = pd.read_parquet(path)
    future = data.copy()
    future["__source_file"] = f"raw data/2026.10.06-{PACKAGE_SUFFIX}/EK-TEST.xlsx"
    pd.concat([data, future]).to_parquet(path, index=False)
    assert common._find_raw_parquet(tmp_path, "EK-TEST", as_of=AS_OF) is None


def test_default_snapshot_date_uses_utc_today(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class FixedDatetime(dt.datetime):
        @classmethod
        def now(cls, tz: dt.tzinfo | None = None) -> dt.datetime:
            assert tz is dt.UTC
            return cls(2026, 10, 5, 0, 0, tzinfo=dt.UTC)

    monkeypatch.setattr(common.dt, "datetime", FixedDatetime)
    current = _raw(tmp_path, "2026-10-05")
    _raw(tmp_path, "2026-10-06")
    assert common._find_raw_parquet(tmp_path, "EK-TEST") == current


def test_current_unknown_source_is_preferred_to_repealed_dated_source(tmp_path: Path) -> None:
    current = _raw(tmp_path, package_date="2026.10.02")
    _raw(tmp_path, "2026-10-04", name="MULGA_old.parquet", package_date="2026.10.02")
    assert common._find_raw_parquet(tmp_path, "EK-TEST", as_of=AS_OF) == current


def test_future_current_candidate_cannot_shadow_existing_current_source(tmp_path: Path) -> None:
    current = _raw(tmp_path, "2026-10-01", package_date="2026.10.02")
    _raw(tmp_path, package_date="2026.10.06")
    assert common._find_raw_parquet(tmp_path, "EK-TEST", as_of=AS_OF) == current


def test_same_decoded_artifact_preserves_bytes_and_mtime(tmp_path: Path) -> None:
    frame = pd.DataFrame({"code": ["001", "001", "002"], "value": [1, 2, 3]})
    path = tmp_path / "catalog.parquet"
    frame.to_parquet(path, index=False, compression=None)
    before = path.read_bytes(), path.stat().st_mtime_ns
    assert builder._write_curated_if_changed(path, frame.copy()) is False
    assert (path.read_bytes(), path.stat().st_mtime_ns) == before
    pd.testing.assert_frame_equal(pd.read_parquet(path), frame)


def test_pandas_string_storage_variation_does_not_change_decoded_semantics(tmp_path: Path) -> None:
    path = tmp_path / "catalog.parquet"
    original = pd.DataFrame({"code": pd.Series(["001", None], dtype=object)})
    original.to_parquet(path, index=False, compression=None)
    before = path.read_bytes(), path.stat().st_mtime_ns
    for dtype in ["str", "string"]:
        assert builder._write_curated_if_changed(path, original.astype({"code": dtype})) is False
        assert (path.read_bytes(), path.stat().st_mtime_ns) == before


@pytest.mark.parametrize("change", ["value", "dtype", "columns", "order", "duplicate", "provenance"])
def test_actual_schema_dtype_value_order_or_provenance_changes_write(
    tmp_path: Path, change: str
) -> None:
    original = pd.DataFrame({"code": ["001", "002"], "value": [1, 2], "source_parquet": ["old", "old"]})
    candidate = original.copy()
    if change == "value":
        candidate.loc[0, "value"] = 9
    elif change == "dtype":
        candidate["value"] = candidate["value"].astype("float64")
    elif change == "columns":
        candidate = candidate[["value", "code", "source_parquet"]]
    elif change == "order":
        candidate = candidate.iloc[::-1].reset_index(drop=True)
    elif change == "duplicate":
        candidate = pd.concat([candidate, candidate.iloc[:1]], ignore_index=True)
    else:
        candidate.loc[0, "source_parquet"] = "new"
    path = tmp_path / "catalog.parquet"
    original.to_parquet(path, index=False)
    before = path.read_bytes()
    assert builder._write_curated_if_changed(path, candidate) is True
    assert path.read_bytes() != before
    pd.testing.assert_frame_equal(pd.read_parquet(path), candidate)


def test_complete_builder_rerun_is_byte_preserving(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _raw(tmp_path, "2026-10-05")
    _raw(tmp_path, "2026-10-06", frame=pd.DataFrame({"code": ["999"], "value": [99]}))
    assert _run_builder(monkeypatch, tmp_path) == 0
    output = tmp_path / "curated" / "test.parquet"
    before = output.read_bytes(), output.stat().st_mtime_ns
    assert _run_builder(monkeypatch, tmp_path) == 0
    assert (output.read_bytes(), output.stat().st_mtime_ns) == before
    assert pd.read_parquet(output)["code"].tolist() == ["001"]


@pytest.mark.parametrize("all_future", [False, True])
def test_missing_or_all_future_raw_returns_failure_without_overwriting_existing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, all_future: bool
) -> None:
    if all_future:
        _raw(tmp_path, "2026-10-06")
    output = tmp_path / "curated" / "test.parquet"
    output.parent.mkdir()
    pd.DataFrame({"code": ["old"], "value": [8]}).to_parquet(output, index=False)
    before = output.read_bytes()
    assert _run_builder(monkeypatch, tmp_path) == 1
    assert output.read_bytes() == before


def _manifest(root: Path, dates: list[str]) -> pd.DataFrame:
    rows = []
    for effective_date in dates:
        rows.append({
            "annex_code": "EK-TEST",
            "effective_date": effective_date,
            "parquet_path": f"data/gazette/raw/annex=EK-TEST/effective_date={effective_date}/current.parquet",
        })
    frame = pd.DataFrame(rows)
    frame.to_parquet(root / "version_manifest.parquet", index=False)
    return builder._load_manifest(root)


def test_history_keeps_future_validity_and_relative_source_identity_across_reruns(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _raw(tmp_path, "2026-10-01")
    _raw(tmp_path, "2026-10-06", package_date="2026.10.06", frame=pd.DataFrame({"code": ["001"], "value": [2]}))
    _manifest(tmp_path, ["2026-10-01", "2026-10-06"])
    assert _run_builder(monkeypatch, tmp_path, source="raw_all_versions") == 0
    output = tmp_path / "curated" / "test.parquet"
    result = pd.read_parquet(output)
    assert result["valid_from"].tolist() == ["2026-10-01", "2026-10-06"]
    assert result.loc[0, "valid_to"] == "2026-10-05"
    assert pd.isna(result.loc[1, "valid_to"])
    assert result["source_parquet"].tolist() == [
        f"data/gazette/raw/annex=EK-TEST/effective_date={effective_date}/current.parquet"
        for effective_date in ["2026-10-01", "2026-10-06"]
    ]
    before = output.read_bytes(), output.stat().st_mtime_ns
    assert _run_builder(monkeypatch, tmp_path, source="raw_all_versions") == 0
    assert (output.read_bytes(), output.stat().st_mtime_ns) == before


def test_missing_history_input_cannot_publish_partial_history(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _raw(tmp_path, "2026-10-01")
    _manifest(tmp_path, ["2026-10-01", "2026-10-06"])
    assert _run_builder(monkeypatch, tmp_path, source="raw_all_versions") == 1
    assert not (tmp_path / "curated" / "test.parquet").exists()


def test_relocated_history_uses_requested_root_and_canonical_source_path(tmp_path: Path) -> None:
    requested_root = tmp_path / "requested"
    other_root = tmp_path / "other"
    local = _raw(requested_root, "2026-10-01")
    stale = _raw(other_root, "2026-10-01", frame=pd.DataFrame({"code": ["wrong"], "value": [99]}))
    row = pd.Series({"annex_code": "EK-TEST", "effective_date": "2026-10-01", "parquet_path": str(stale)})
    assert builder._relocate_parquet(requested_root, row) == local
    assert builder._source_parquet_identity(requested_root, local) == "data/gazette/raw/annex=EK-TEST/effective_date=2026-10-01/current.parquet"
