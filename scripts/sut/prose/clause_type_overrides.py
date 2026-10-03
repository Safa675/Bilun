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
    if "clause_type" not in frame.columns:
        return frame
    specs = overrides if overrides is not None else load_clause_type_overrides()
    if not specs:
        return frame

    out = frame
    for clause_id, spec in specs.items():
        new_type = spec.get("clause_type")
        if not new_type:
            continue
        number = spec.get("clause_number")
        if number is not None and (type(number) is not int or number < 1):
            raise ValueError("Authored clause_number override must be a positive integer")
        if "#" in clause_id:
            # Full source coordinate + content hash remains stable when C IDs
            # shift. Never fall back to an opaque ID for a missing source key.
            if "clause_key" in out.columns:
                mask = pl.col("clause_key").cast(pl.Utf8) == clause_id
            elif {"clause_coordinate", "content_hash"} <= set(out.columns):
                mask = pl.concat_str([pl.col("clause_coordinate"), pl.lit("#"),
                                      pl.col("content_hash")]) == clause_id
            else:
                continue
        elif "clause_id" in out.columns:
            mask = pl.col("clause_id").cast(pl.Utf8) == clause_id
        else:
            continue
        out = out.with_columns(
            pl.when(mask)
            .then(pl.lit(str(new_type)))
            .otherwise(pl.col("clause_type"))
            .alias("clause_type")
        )
        if spec.get("clause_number") is not None:
            previous_number = pl.col("clause_number") if "clause_number" in out.columns else pl.lit(None)
            out = out.with_columns(
                pl.when(mask).then(pl.lit(number)).otherwise(previous_number).alias("clause_number")
            )
        if spec.get("clause_letter") is not None:
            previous_letter = pl.col("clause_letter") if "clause_letter" in out.columns else pl.lit(None)
            out = out.with_columns(
                pl.when(mask).then(pl.lit(str(spec["clause_letter"])))
                .otherwise(previous_letter).alias("clause_letter")
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
    if not specs or "clause_type" not in frame.columns:
        return frame
    out = frame.copy()
    for clause_id, spec in specs.items():
        new_type = spec.get("clause_type")
        if not new_type:
            continue
        number = spec.get("clause_number")
        if number is not None and (type(number) is not int or number < 1):
            raise ValueError("Authored clause_number override must be a positive integer")
        if "#" in clause_id:
            if "clause_key" in out.columns:
                mask = out["clause_key"].astype(str) == clause_id
            elif {"clause_coordinate", "content_hash"} <= set(out.columns):
                mask = (out["clause_coordinate"].astype(str) + "#" +
                        out["content_hash"].astype(str)) == clause_id
            else:
                continue
        elif "clause_id" in out.columns:
            mask = out["clause_id"].astype(str) == clause_id
        else:
            continue
        if not mask.any():
            continue
        out.loc[mask, "clause_type"] = str(new_type)
        if spec.get("clause_number") is not None:
            if "clause_number" not in out.columns:
                out["clause_number"] = None
            out.loc[mask, "clause_number"] = number
        if spec.get("clause_letter") is not None:
            if "clause_letter" not in out.columns:
                out["clause_letter"] = None
            out.loc[mask, "clause_letter"] = str(spec["clause_letter"])
        if "is_heading" in out.columns:
            out.loc[mask, "is_heading"] = False
    return out
