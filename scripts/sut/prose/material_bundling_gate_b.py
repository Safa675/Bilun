"""Compatibility facade — §3.1–3.2 material Gate B now uses gate_b_generic (Track F)."""

from __future__ import annotations

import unicodedata
from pathlib import Path

import polars as pl

from scripts.sut.prose.gate_b_generic import export_candidates, gate_b_summary
from scripts.sut.prose.gate_b_sections import SECTION_MATERIAL_31_32

_PROJECT_ROOT = Path(__file__).resolve().parents[3]


def _normalize_tr(text: str) -> str:
    """NFKD fold used by material triage/export scripts (kept on facade)."""
    folded = unicodedata.normalize("NFKD", str(text).casefold())
    return "".join(ch for ch in folded if not unicodedata.combining(ch))


def load_candidate_clauses(clauses_path: Path) -> pl.DataFrame:
    return export_candidates(clauses_path, SECTION_MATERIAL_31_32)


def enrich_gate_b_dataframe(
    frame: pl.DataFrame,
    *,
    prose_json_path: Path | None = None,
) -> pl.DataFrame:
    """Legacy enrich — generic export already tags encode_priority.

    Adds stub columns expected by older unit tests / review CSV.
    """
    _ = prose_json_path
    if frame.is_empty():
        return frame
    extras = [
        pl.lit(None, dtype=pl.Utf8).alias("duplicate_of"),
        pl.lit("generic_export").alias("selection_reason"),
        pl.lit(None, dtype=pl.Utf8).alias("suggested_condition_type"),
    ]
    missing = [expr for expr in extras if expr.meta.output_name() not in frame.columns]
    return frame.with_columns(missing) if missing else frame


def build_review_sample(
    frame: pl.DataFrame,
    *,
    fraction: float = 0.25,
    min_rows: int = 12,
    n: int | None = None,
) -> pl.DataFrame:
    if frame.is_empty():
        return frame
    if n is None:
        n = max(min_rows, int(frame.height * fraction))
    return frame.head(min(n, frame.height))


__all__ = [
    "load_candidate_clauses",
    "enrich_gate_b_dataframe",
    "build_review_sample",
    "gate_b_summary",
    "_normalize_tr",
]
