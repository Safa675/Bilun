"""Unit tests for the ingest_state.json atomic write semantics."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest
import yaml

from scripts.sut import convert_xlsx_to_parquet as converter

pytestmark = pytest.mark.unit


def test_ingest_state_file_exists() -> None:
    """The seeded ingest_state.json exists and is valid JSON."""
    repo_root = Path(__file__).resolve().parents[3]
    state_path = repo_root / "data" / "gazette" / "ingest_state.json"
    assert state_path.exists(), f"ingest_state.json not found at {state_path}"
    state = json.loads(state_path.read_text())
    assert "last_ingested_date" in state
    assert "pipeline_version" in state
    assert state["pipeline_version"] == 2


def test_ingest_state_has_valid_date() -> None:
    """The last_ingested_date is a valid ISO date string."""
    repo_root = Path(__file__).resolve().parents[3]
    state = json.loads((repo_root / "data" / "gazette" / "ingest_state.json").read_text())
    date_str = state["last_ingested_date"]
    parts = date_str.split("-")
    assert len(parts) == 3
    assert all(p.isdigit() for p in parts)


@pytest.fixture
def conversion(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path, SimpleNamespace]:
    source = tmp_path / "2026.10.02-custom"
    source.mkdir()
    output = tmp_path / "gazette"
    output.mkdir()
    (output / "ingest_state.json").write_text(json.dumps({
        "last_ingested_date": "2026-08-29", "pipeline_version": 2, "last_ingested_at": "old"}))
    args = SimpleNamespace(input_dir=str(source), output_dir=str(output), limit=None,
        include_mulga=False, overwrite_manifest=False, defer_state=False)
    monkeypatch.setattr(converter, "parse_args", lambda: args)
    monkeypatch.setattr(converter, "find_latest_consolidated_sut_dir", lambda _: pytest.fail("Custom input must not consult global latest"))
    return source, output, args


def workbook(path: Path, *, empty: bool = False) -> None:
    pd.DataFrame({"barcode": [] if empty else ["00123", "00001"],
        "name": [] if empty else ["A", "B"]}).to_excel(path, index=False)


@pytest.mark.parametrize("mode", ["empty", "limit-zero", "empty-sheet", "failure"])
def test_incomplete_conversion_preserves_state_and_manifest(conversion, mode: str) -> None:
    source, output, args = conversion
    if mode != "empty":
        path = source / "EK-4A.xlsx"
        workbook(path, empty=mode == "empty-sheet")
        if mode == "failure":
            path.write_bytes(b"not an Excel workbook")
    if mode == "limit-zero":
        args.limit = 0
    state = (output / "ingest_state.json").read_bytes()
    assert converter.main() == 1
    assert (output / "ingest_state.json").read_bytes() == state
    assert not (output / "version_manifest.parquet").exists()


def test_custom_input_and_limited_run_never_advance_complete_date(conversion) -> None:
    source, output, args = conversion
    workbook(source / "EK-4A.xlsx")
    workbook(source / "EK-4B.xlsx")
    args.limit = 1
    assert converter.main() == 0
    state = json.loads((output / "ingest_state.json").read_text())
    assert state["last_ingested_date"] == "2026-08-29"
    assert state["last_ingested_at"] == "old"
    assert state["manifest_row_count"] == 1
    manifest = pd.read_parquet(output / "version_manifest.parquet")
    assert manifest.iloc[0]["source_file"] == str(source / "EK-4A.xlsx")


def test_deferred_state_and_semantic_rerun_preserve_bytes(conversion) -> None:
    source, output, args = conversion
    workbook(source / "EK-4A.xlsx")
    args.defer_state = True
    before = (output / "ingest_state.json").read_bytes()
    assert converter.main() == 0
    raw = next((output / "raw").rglob("*.parquet"))
    frame = pd.read_parquet(raw)
    assert frame["barcode"].tolist() == ["00123", "00001"]
    frame["__ingested_at"] = "old timestamp retained"
    frame.to_parquet(raw, index=False)
    raw_bytes = raw.read_bytes()
    manifest_bytes = (output / "version_manifest.parquet").read_bytes()
    assert converter.main() == 0
    assert raw.read_bytes() == raw_bytes
    assert (output / "version_manifest.parquet").read_bytes() == manifest_bytes
    assert (output / "ingest_state.json").read_bytes() == before


def test_failure_after_one_workbook_preserves_committed_manifest(conversion) -> None:
    source, output, args = conversion
    workbook(source / "EK-4A.xlsx")
    assert converter.main() == 0
    before = {p: p.read_bytes() for p in [output / "version_manifest.parquet", output / "ingest_state.json"]}
    (source / "EK-4B.xlsx").write_bytes(b"broken")
    assert converter.main() == 1
    assert all(p.read_bytes() == content for p, content in before.items())


def test_manifest_atomic_failure_preserves_old_state(conversion, monkeypatch: pytest.MonkeyPatch) -> None:
    source, output, args = conversion
    workbook(source / "EK-4A.xlsx")
    assert converter.main() == 0
    before = (output / "ingest_state.json").read_bytes()
    workbook(source / "EK-4B.xlsx")
    replace = converter.os.replace
    def fail_manifest(src, dst):
        if Path(dst).name == "version_manifest.parquet":
            raise OSError("manifest commit failed")
        replace(src, dst)
    monkeypatch.setattr(converter.os, "replace", fail_manifest)
    with pytest.raises(OSError, match="manifest commit failed"):
        converter.main()
    assert (output / "ingest_state.json").read_bytes() == before


def test_raw_equality_preserves_schema_values_and_source_identity() -> None:
    raw = pd.DataFrame({"barcode": ["00123"], "__source_file": ["raw data/a/EK-4A.xlsx"], "__ingested_at": ["old"]})
    new = raw.assign(__source_file="/home/runner/work/Bilun/Bilun/raw data/a/EK-4A.xlsx", __ingested_at="new")
    assert converter.frames_equal(raw, new, raw=True)
    assert not converter.frames_equal(raw, new.assign(barcode="123"), raw=True)
    assert not converter.frames_equal(raw, new.assign(barcode=123), raw=True)
    assert not converter.frames_equal(raw, new.assign(__source_file="raw data/b/EK-4A.xlsx"), raw=True)


def test_workflow_pins_input_and_completes_only_after_reports() -> None:
    path = Path(__file__).resolve().parents[3] / ".github/workflows/sut-monitor.yml"
    steps = yaml.safe_load(path.read_text())["jobs"]["monitor"]["steps"]
    named = {step.get("name"): step for step in steps}
    assert named["Fetch new SUT package"]["id"] == "fetch"
    ingest = named["Run ingest pipeline"]["run"]
    assert '--input-dir "${{ steps.fetch.outputs.input_dir }}" --defer-state' in ingest
    assert '--inventory "${{ steps.fetch.outputs.inventory_path }}" --prepare-corpus' in ingest
    positions = {step.get("name"): index for index, step in enumerate(steps)}
    completion = positions["Complete verified package ingestion"]
    assert completion > positions["Run ingest pipeline"]
    assert completion > positions["Compute clause_key diff (Track E)"]
    assert completion > positions["Compute delta"]
    assert completion < positions["Create PR"]
    for step in ("Compute clause_key diff (Track E)", "Compute delta"):
        assert "--legacy-input-fingerprints" in named[step]["run"]
        assert 'if [ -f "$receipt" ]' in named[step]["run"]
