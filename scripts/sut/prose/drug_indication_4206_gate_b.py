"""§4.2.6 growth hormone Gate B — thin shim delegating to gate_b_generic."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import polars as pl

from scripts.sut.prose.gate_b_shim import shim_export_candidates, shim_build_manifest, shim_write_artifacts

_SECTION = "4206"


def _all_4206_batch_rules() -> list[dict[str, Any]]:
    from scripts.sut.rule_sources import load_legacy_drug_batch

    return [
        *load_legacy_drug_batch("drug_indication_4206_batch_rules.py:BATCH_A6_RULES"),
        *load_legacy_drug_batch("drug_indication_4206_a2_batch_rules.py:BATCH_A2_RULES"),
    ]


def export_4206_candidates(clauses_path: Path, *, encoded_clause_ids: frozenset[str] | None = None) -> pl.DataFrame:
    return shim_export_candidates(_SECTION, clauses_path, encoded_clause_ids=encoded_clause_ids)


def build_4206_manifest(gate_b_frame: pl.DataFrame, rules: list[dict[str, Any]], *, effective_date: str) -> dict[str, Any]:
    return shim_build_manifest(_SECTION, gate_b_frame, rules, effective_date=effective_date)


def write_gate_b_artifacts(
    *,
    clauses_path: Path,
    rules: list[dict[str, Any]],
    corpus_csv: Path,
    manifest_path: Path,
    effective_date: str,
) -> tuple[pl.DataFrame, dict[str, Any]]:
    return shim_write_artifacts(
        _SECTION,
        clauses_path=clauses_path,
        rules=rules,
        corpus_csv=corpus_csv,
        manifest_path=manifest_path,
        effective_date=effective_date,
    )
