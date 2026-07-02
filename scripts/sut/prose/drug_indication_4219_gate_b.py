"""§4.2.19 migraine Gate B — thin shim delegating to gate_b_generic.

This file was ~230 lines of duplicate logic; now delegates to the generic engine
via the config table in gate_b_sections.py.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import polars as pl

from scripts.sut.prose.gate_b_shim import shim_export_candidates, shim_build_manifest, shim_write_artifacts

_SECTION = "4219"


def export_4219_candidates(clauses_path: Path, *, encoded_clause_ids: frozenset[str] | None = None) -> pl.DataFrame:
    return shim_export_candidates(_SECTION, clauses_path, encoded_clause_ids=encoded_clause_ids)


def build_4219_manifest(gate_b_frame: pl.DataFrame, rules: list[dict[str, Any]], *, effective_date: str) -> dict[str, Any]:
    return shim_build_manifest(_SECTION, gate_b_frame, rules, effective_date=effective_date)


def write_gate_b_artifacts(*, clauses_path: Path, rules_path: Path, corpus_csv: Path, manifest_path: Path, effective_date: str) -> tuple[pl.DataFrame, dict[str, Any]]:
    return shim_write_artifacts(_SECTION, clauses_path=clauses_path, rules_path=rules_path, corpus_csv=corpus_csv, manifest_path=manifest_path, effective_date=effective_date)
