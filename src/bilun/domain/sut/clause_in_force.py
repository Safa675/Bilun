"""Helpers for yürürlükteki (in-force) SUT clause text — filter-at-read layer."""

from __future__ import annotations

from typing import Any

import polars as pl


def clause_display_text(row: dict[str, Any] | Any) -> str:
    """Return regulatory text for product surfaces (API, chatbot, Gate B)."""
    if isinstance(row, dict):
        if row.get("is_in_force") and row.get("in_force_text"):
            return str(row["in_force_text"])
        if row.get("in_force_text"):
            return str(row["in_force_text"])
        return str(row.get("text_tr") or "")
    if getattr(row, "is_in_force", False) and getattr(row, "in_force_text", None):
        return str(row.in_force_text)
    in_force = getattr(row, "in_force_text", None)
    if in_force:
        return str(in_force)
    return str(getattr(row, "text_tr", None) or "")


def in_force_polars_filter(frame: pl.DataFrame) -> pl.DataFrame:
    """Keep only in-force rows when the column exists; otherwise pass through."""
    if "is_in_force" not in frame.columns:
        return frame
    return frame.filter(pl.col("is_in_force"))


def regulatory_text_column(frame: pl.DataFrame) -> str:
    """Name of the column to use for regulatory text matching."""
    if "in_force_text" in frame.columns:
        return "in_force_text"
    return "text_tr"
