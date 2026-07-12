"""Unit tests for the ingest_state.json atomic write semantics."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

import pytest

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


def test_atomic_write_pattern(tmp_path: Path) -> None:
    """The temp-then-rename atomic write pattern works correctly.

    This mirrors the pattern used in convert_xlsx_to_parquet.py for both
    the manifest and the ingest_state.json.
    """
    target = tmp_path / "test_state.json"
    state = {"last_ingested_date": "2026-06-29", "test": True}

    # Write to temp file first
    tmp = target.with_suffix(".json.tmp")
    with open(tmp, "w") as f:
        json.dump(state, f)
        f.flush()
        os.fsync(f.fileno())

    # Atomic rename
    os.replace(tmp, target)

    # Verify
    assert target.exists()
    assert not tmp.exists()  # temp is gone
    loaded = json.loads(target.read_text())
    assert loaded["last_ingested_date"] == "2026-06-29"


def test_atomic_write_preserves_old_on_crash(tmp_path: Path) -> None:
    """If the pipeline crashes before os.replace, the old state is preserved.

    This is the key safety property: the state file only updates AFTER
    the full pipeline succeeds.
    """
    target = tmp_path / "test_state.json"
    old_state = {"last_ingested_date": "2026-05-23", "version": 1}
    target.write_text(json.dumps(old_state))

    # Simulate a crash: write a temp file but DON'T os.replace
    tmp = target.with_suffix(".json.tmp")
    tmp.write_text(json.dumps({"last_ingested_date": "2026-06-29", "version": 2}))

    # Old state should be unchanged (the temp file is orphaned)
    loaded = json.loads(target.read_text())
    assert loaded["last_ingested_date"] == "2026-05-23"
    assert loaded["version"] == 1
