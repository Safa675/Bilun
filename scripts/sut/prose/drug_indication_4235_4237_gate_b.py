"""§4.2.35 neuropathic pain / §4.2.37 acromegaly Gate B — thin shim delegating to gate_b_generic.

Was ~390 lines; now delegates to the generic engine via gate_b_sections.py.
This bespoke module (force-C sections, superseded ids, force-include lists) is
fully captured by the SECTION_4235_4237 config in gate_b_sections.py.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import polars as pl

from scripts.sut.prose.gate_b_shim import (
    shim_build_manifest,
    shim_export_candidates,
    shim_write_artifacts,
)

_SECTION = "4235_4237"


def export_4235_4237_candidates(
    clauses_path: Path, *, encoded_clause_ids: frozenset[str] | None = None
) -> pl.DataFrame:
    return shim_export_candidates(_SECTION, clauses_path, encoded_clause_ids=encoded_clause_ids)


def build_4235_4237_manifest(
    gate_b_frame: pl.DataFrame, rules: list[dict[str, Any]], *, effective_date: str
) -> dict[str, Any]:
    return shim_build_manifest(_SECTION, gate_b_frame, rules, effective_date=effective_date)


def write_gate_b_artifacts(
    *,
    clauses_path: Path,
    corpus_csv: Path,
    manifest_path: Path,
    effective_date: str,
    batch_rules: list[dict[str, Any]] | None = None,
) -> tuple[pl.DataFrame, dict[str, Any]]:
    return shim_write_artifacts(
        _SECTION,
        clauses_path=clauses_path,
        corpus_csv=corpus_csv,
        manifest_path=manifest_path,
        effective_date=effective_date,
        batch_rules=batch_rules,
    )
