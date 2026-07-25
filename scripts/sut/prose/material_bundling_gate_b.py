"""Compatibility facade — §3.1–3.2 material Gate B now uses gate_b_generic (Track F)."""

from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path
from typing import Any

import polars as pl

from scripts.sut.prose.gate_b_generic import export_candidates, gate_b_summary
from scripts.sut.prose.gate_b_sections import SECTION_MATERIAL_31_32

_PROJECT_ROOT = Path(__file__).resolve().parents[3]

# Kept for triage/export scripts that still import these helpers from the facade.
_EK3B1_TEXT_PATTERNS = (
    r"ek-3\s*b-1",
    r"ek-3/b\s*listes",
    r"ek-3b\s*listes",
    r"sarf\s+malzemeleri\s*listes",
    r"paket\s+sarf",
    r"tüketim\s+malzemeleri\s*listes",
)
_EK3B2_TEXT_PATTERNS = (
    r"ek-3\s*b-2",
    r"kurumca\s+karşılanmaz\s+malzemeler\s*listes",
    r"ödenmeyecek\s+malzemeler\s*listes",
    r"hariç\s+malzemeler\s*listes",
)


def _normalize_tr(text: str) -> str:
    """NFKD fold used by material triage/export scripts (kept on facade)."""
    folded = unicodedata.normalize("NFKD", str(text).casefold())
    return "".join(ch for ch in folded if not unicodedata.combining(ch))


def _matches_any_pattern(text: str, patterns: tuple[str, ...]) -> bool:
    normalized = _normalize_tr(text)
    return any(re.search(pat, normalized) for pat in patterns)


def _annex_refs_list(raw: Any) -> list[str]:
    """Parse annex_refs cell (list / JSON string) for triage CSV exporters."""
    if raw is None:
        return []
    if isinstance(raw, list):
        return [str(item) for item in raw]
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, list):
                return [str(item) for item in parsed]
        except json.JSONDecodeError:
            return []
    return []


def _duplicate_of(*, excerpt: str, annex_refs: list[str]) -> str:
    """Heuristic annex-duplicate label used by R5 gap triage CSV."""
    annex_upper = " ".join(annex_refs).upper()
    ek3b1_annex = any(
        token in annex_upper for token in ("EK-3B-1", "EK-3/B", "EK-3B", "EK-3B1")
    )
    ek3b2_annex = "EK-3B-2" in annex_upper or "EK-3B2" in annex_upper
    ek3b1_text = _matches_any_pattern(excerpt, _EK3B1_TEXT_PATTERNS)
    ek3b2_text = _matches_any_pattern(excerpt, _EK3B2_TEXT_PATTERNS)
    if (ek3b1_annex or ek3b1_text) and (ek3b2_annex or ek3b2_text):
        return "ek3b1_and_ek3b2"
    if ek3b1_annex or ek3b1_text:
        return "ek3b1"
    if ek3b2_annex or ek3b2_text:
        return "ek3b2"
    return "none"


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
    "_annex_refs_list",
    "_duplicate_of",
]
