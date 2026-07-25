"""Apply authored ``clause_type`` overrides to a clauses frame (Track A3)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import polars as pl

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_OVERRIDES_PATH = _PROJECT_ROOT / "data" / "gazette" / "clause_type_overrides.yaml"


def load_clause_type_overrides(
    path: Path | None = None,
) -> dict[str, dict[str, Any]]:
    overrides_path = path or DEFAULT_OVERRIDES_PATH
    if not overrides_path.is_file():
        return {}
    import yaml

    payload = yaml.safe_load(overrides_path.read_text(encoding="utf-8")) or {}
    raw = payload.get("overrides") or {}
    out: dict[str, dict[str, Any]] = {}
    for clause_id, spec in raw.items():
        cid = str(clause_id).strip()
        if not cid or not isinstance(spec, dict):
            continue
        out[cid] = dict(spec)
    return out


def apply_clause_type_overrides(
    frame: pl.DataFrame,
    overrides: dict[str, dict[str, Any]] | None = None,
) -> pl.DataFrame:
    """Return a copy of ``frame`` with authored clause_type overrides applied."""
    if "clause_id" not in frame.columns or "clause_type" not in frame.columns:
        return frame
    specs = overrides if overrides is not None else load_clause_type_overrides()
    if not specs:
        return frame

    out = frame
    for clause_id, spec in specs.items():
        new_type = spec.get("clause_type")
        if not new_type:
            continue
        mask = pl.col("clause_id").cast(pl.Utf8) == clause_id
        out = out.with_columns(
            pl.when(mask)
            .then(pl.lit(str(new_type)))
            .otherwise(pl.col("clause_type"))
            .alias("clause_type")
        )
        if "is_heading" in out.columns:
            out = out.with_columns(
                pl.when(mask)
                .then(pl.lit(False))
                .otherwise(pl.col("is_heading"))
                .alias("is_heading")
            )
    return out


def apply_clause_type_overrides_pandas(frame):  # type: ignore[no-untyped-def]
    """Pandas variant for the extractor write path."""
    import pandas as pd

    if not isinstance(frame, pd.DataFrame):
        raise TypeError("expected pandas DataFrame")
    specs = load_clause_type_overrides()
    if not specs or "clause_id" not in frame.columns:
        return frame
    out = frame.copy()
    for clause_id, spec in specs.items():
        new_type = spec.get("clause_type")
        if not new_type:
            continue
        mask = out["clause_id"].astype(str) == clause_id
        if not mask.any():
            continue
        out.loc[mask, "clause_type"] = str(new_type)
        if "is_heading" in out.columns:
            out.loc[mask, "is_heading"] = False
    return out
