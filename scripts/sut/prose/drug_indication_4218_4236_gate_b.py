"""§4.2.18 obesity / §4.2.36 Parkinson Gate B — thin shim delegating to gate_b_generic.

Was ~360 lines; now delegates to the generic engine via gate_b_sections.py.
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

_SECTION = "4218_4236"


def _with_defer_themes(frame: pl.DataFrame) -> pl.DataFrame:
    """Back-compat: legacy export emitted a ``defer_themes`` csv column."""
    if frame.is_empty() or "defer_themes" in frame.columns:
        return frame
    from scripts.sut.prose.drug_indication_gate_b import infer_defer_themes

    rows = []
    for r in frame.iter_rows(named=True):
        themes = infer_defer_themes(str(r.get("text_tr") or "")) if r.get("encode_tier") == "C" else []
        rows.append(",".join(themes) if themes else "")
    return frame.with_columns(pl.Series("defer_themes", rows))


def export_4218_4236_candidates(
    clauses_path: Path, *, encoded_clause_ids: frozenset[str] | None = None
) -> pl.DataFrame:
    frame = shim_export_candidates(_SECTION, clauses_path, encoded_clause_ids=encoded_clause_ids)
    return _with_defer_themes(frame)


def build_4218_4236_manifest(
    gate_b_frame: pl.DataFrame, rules: list[dict[str, Any]], *, effective_date: str
) -> dict[str, Any]:
    return shim_build_manifest(_SECTION, gate_b_frame, rules, effective_date=effective_date)


def write_gate_b_artifacts(
    *,
    clauses_path: Path,
    rules_path: Path,
    corpus_csv: Path,
    manifest_path: Path,
    effective_date: str,
    batch_rules: list[dict[str, Any]] | None = None,
) -> tuple[pl.DataFrame, dict[str, Any]]:
    frame, manifest = shim_write_artifacts(
        _SECTION,
        clauses_path=clauses_path,
        rules_path=rules_path,
        corpus_csv=corpus_csv,
        manifest_path=manifest_path,
        effective_date=effective_date,
        batch_rules=batch_rules,
    )
    # Legacy export carried a defer_themes column; re-add it to the written corpus.
    frame = _with_defer_themes(frame)
    frame.write_csv(corpus_csv)
    return frame, manifest
