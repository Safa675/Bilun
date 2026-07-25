"""Compatibility facade — §2.2 payment Gate B now uses gate_b_generic (Track F)."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

import polars as pl

from scripts.sut.prose.gate_b_generic import export_candidates, write_artifacts
from scripts.sut.prose.gate_b_sections import SECTION_PAYMENT_22

_PROJECT_ROOT = Path(__file__).resolve().parents[3]


def load_candidate_clauses(clauses_path: Path) -> pl.DataFrame:
    return export_candidates(clauses_path, SECTION_PAYMENT_22)


def enrich_gate_b_dataframe(frame: pl.DataFrame) -> pl.DataFrame:
    """Legacy name — export_candidates already enriches."""
    return frame


def run_gate_b_pipeline(
    *,
    clauses_path: Path,
    prose_json_path: Path,
    corpus_csv_path: Path,
    manifest_path: Path,
    write_prose_json: bool = False,
) -> dict[str, Any]:
    _ = write_prose_json  # JSON remapping retired — cites authored in YAML
    frame, manifest = write_artifacts(
        clauses_path=clauses_path,
        section=SECTION_PAYMENT_22,
        effective_date=date.today().isoformat(),
        rules_path=prose_json_path,
        manifest_path=manifest_path,
        corpus_csv=corpus_csv_path,
        write_corpus=False,
    )
    return {"frame": frame, "manifest": manifest, "rows": frame.height}
