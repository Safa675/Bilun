"""R5 Epic B Phase B0 — material bundling gap triage export."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import polars as pl
import pytest

pytestmark = pytest.mark.unit

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "data/gazette/prose_corpus/L1.4_material_bundling_r5_gap_triage.csv"


@pytest.fixture(scope="module")
def triage_frame() -> pl.DataFrame:
    if not OUT.is_file():
        subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts/sut/export_material_bundling_r5_gap_triage.py"),
            ],
            cwd=str(ROOT),
            check=True,
        )
    return pl.read_csv(OUT)


def test_gap_triage_csv_exists(triage_frame: pl.DataFrame) -> None:
    assert OUT.is_file()
    assert triage_frame.height >= 0


def test_gap_triage_row_count_bounded(triage_frame: pl.DataFrame) -> None:
    assert triage_frame.height <= 50


def test_gap_triage_clause_ids_start_with_c(triage_frame: pl.DataFrame) -> None:
    if triage_frame.height == 0:
        pytest.skip("no motor-bound gaps remain")
    assert triage_frame["clause_id"].str.starts_with("C").all()


def test_gap_triage_required_columns(triage_frame: pl.DataFrame) -> None:
    assert set(triage_frame.columns) >= {
        "clause_id",
        "section_id",
        "deontic_modality",
        "theme",
        "triage_action",
    }
    allowed = {"encode_now", "manifest_header_only", "duplicate_ek3b"}
    if triage_frame.height:
        assert set(triage_frame["triage_action"].unique().to_list()) <= allowed
