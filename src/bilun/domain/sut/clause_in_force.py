"""Helpers for yürürlükteki (in-force) SUT clause text — filter-at-read layer."""

from __future__ import annotations

from typing import Any


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
