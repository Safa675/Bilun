"""Shared Gate B primitives and unified artifact writer dispatch."""

from __future__ import annotations

import json
import unicodedata
from pathlib import Path
from typing import Any, Callable

import polars as pl


def normalize_tr(text: str) -> str:
    folded = unicodedata.normalize("NFKD", str(text).casefold())
    return "".join(ch for ch in folded if not unicodedata.combining(ch))


def encoded_clause_ids_from_rules(rules: list[dict[str, Any]]) -> set[str]:
    encoded: set[str] = set()
    for rule in rules:
        for clause_id in rule.get("gate_b_sources") or []:
            encoded.add(str(clause_id))
    return encoded


def load_rules_for_sections(rules_path: Path, prefixes: tuple[str, ...]) -> list[dict[str, Any]]:
    payload = json.loads(rules_path.read_text(encoding="utf-8"))
    rules = payload.get("rules") or []
    if not prefixes:
        return list(rules)
    return [
        rule
        for rule in rules
        if any(str(rule.get("sut_section") or "").startswith(prefix) for prefix in prefixes)
    ]


def gate_b_summary_by_columns(enriched: pl.DataFrame, columns: tuple[str, ...]) -> dict[str, int]:
    if enriched.is_empty():
        return {"total": 0}
    summary: dict[str, int] = {"total": enriched.height}
    for col in columns:
        if col not in enriched.columns:
            continue
        for key, count in enriched.group_by(col).len().iter_rows():
            summary[f"{col}:{key}"] = int(count)
    return summary


def write_gate_b_outputs(
    frame: pl.DataFrame,
    manifest: dict[str, Any],
    *,
    corpus_csv: Path,
    manifest_path: Path,
) -> tuple[pl.DataFrame, dict[str, Any]]:
    corpus_csv.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    frame.write_csv(corpus_csv)
    from scripts.sut.prose.manifest_reconcile import write_reconciled_manifest

    write_reconciled_manifest(manifest_path, manifest)
    return frame, manifest


def write_standard_gate_b_artifacts(
    *,
    clauses_path: Path,
    corpus_csv: Path,
    manifest_path: Path,
    effective_date: str,
    rules: list[dict[str, Any]],
    export_candidates: Callable[..., pl.DataFrame],
    build_manifest: Callable[..., dict[str, Any]],
    encoded_clause_ids: frozenset[str] | None = None,
) -> tuple[pl.DataFrame, dict[str, Any]]:
    """Standard drug-indication Gate B path: export → manifest → CSV + JSON."""
    manifest = build_manifest(
        export_candidates(clauses_path),
        rules,
        effective_date=effective_date,
    )
    encoded = encoded_clause_ids or frozenset(manifest.get("gate_b_sources_encoded") or [])
    frame = export_candidates(clauses_path, encoded_clause_ids=encoded)
    return write_gate_b_outputs(frame, manifest, corpus_csv=corpus_csv, manifest_path=manifest_path)


def write_gate_b_from_rules_path(
    *,
    clauses_path: Path,
    rules_path: Path,
    corpus_csv: Path,
    manifest_path: Path,
    effective_date: str,
    section_prefixes: tuple[str, ...],
    export_candidates: Callable[..., pl.DataFrame],
    build_manifest: Callable[..., dict[str, Any]],
) -> tuple[pl.DataFrame, dict[str, Any]]:
    rules = load_rules_for_sections(rules_path, section_prefixes)
    return write_standard_gate_b_artifacts(
        clauses_path=clauses_path,
        corpus_csv=corpus_csv,
        manifest_path=manifest_path,
        effective_date=effective_date,
        rules=rules,
        export_candidates=export_candidates,
        build_manifest=build_manifest,
    )
