"""Compatibility facade — §1.8 copay Gate B now uses gate_b_generic (Track F)."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

import polars as pl

from scripts.sut.prose.clause_identity import (
    AmbiguousClauseCiteError,
    NonEncodeEligibleCiteError,
    UnknownClauseCiteError,
    resolve_gate_b_sources_to_clause_ids,
)
from scripts.sut.prose.copay_compositor_traces import COMPOSITOR_CLAUSE_TRACES
from scripts.sut.prose.gate_b_generic import export_candidates, write_artifacts
from scripts.sut.prose.gate_b_sections import SECTION_COPAY_18

_PROJECT_ROOT = Path(__file__).resolve().parents[3]

# Re-export for older imports
_COMPOSITOR_CLAUSE_TRACES = COMPOSITOR_CLAUSE_TRACES


def export_copay_exemption_candidates(
    clauses_path: Path,
    *,
    encoded_clause_ids: frozenset[str] | None = None,
) -> pl.DataFrame:
    frame = export_candidates(
        clauses_path,
        SECTION_COPAY_18,
        encoded_clause_ids=encoded_clause_ids,
    )
    if frame.is_empty():
        return frame
    # Preserve legacy category_hint column used by unit tests.
    return frame.with_columns(
        pl.when(pl.col("section_id").str.starts_with("1.8.2"))
        .then(pl.lit("rate"))
        .when(pl.col("section_id").str.starts_with("1.8.3"))
        .then(pl.lit("rate"))
        .when(pl.col("section_id").str.starts_with("1.8.4"))
        .then(pl.lit("rate"))
        .otherwise(pl.lit("exemption"))
        .alias("category_hint")
    )


def map_json_rules_to_clause_ids(
    rules_path: Path,
    clauses_path: Path,
) -> dict[str, list[str]]:
    payload = json.loads(rules_path.read_text(encoding="utf-8"))
    clauses = pl.read_parquet(clauses_path)
    mapping: dict[str, list[str]] = {}
    for rule in payload.get("rules") or []:
        rid = str(rule.get("rule_id") or "")
        if not rid:
            continue
        refs = rule.get("gate_b_sources") or []
        try:
            ids = sorted(
                resolve_gate_b_sources_to_clause_ids(
                    refs,
                    clauses,
                    in_force_only=True,
                    encode_eligible_only=False,
                    allow_ambiguous=True,
                )
            )
        except (
            AmbiguousClauseCiteError,
            NonEncodeEligibleCiteError,
            UnknownClauseCiteError,
        ):
            ids = [str(r) for r in refs if str(r).startswith(("C", "F"))]
        mapping[rid] = ids
    return mapping


def build_encoded_manifest(rules_path: Path, clauses_path: Path) -> dict[str, Any]:
    _, manifest = write_artifacts(
        clauses_path=clauses_path,
        section=SECTION_COPAY_18,
        effective_date=date.today().isoformat(),
        rules_path=rules_path,
        write_corpus=False,
    )
    return manifest


def write_gate_b_artifacts(
    *,
    clauses_path: Path,
    rules_path: Path,
    corpus_csv: Path,
    manifest_path: Path,
    write_corpus: bool = False,
) -> tuple[pl.DataFrame, dict[str, Any]]:
    return write_artifacts(
        clauses_path=clauses_path,
        section=SECTION_COPAY_18,
        effective_date=date.today().isoformat(),
        rules_path=rules_path,
        manifest_path=manifest_path,
        corpus_csv=corpus_csv,
        write_corpus=write_corpus,
    )
