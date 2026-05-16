"""SUT label normalization helpers."""

from __future__ import annotations

from typing import Any

_DISPLAY_TEXT_REPLACEMENTS: tuple[tuple[str, str], ...] = (
    ("Malıgn", "Malign"),
)


def normalize_sut_display_text(text: str | None) -> str:
    """Normalize curated SUT labels for display without changing valid Turkish text."""
    normalized = str(text or "")
    for source, target in _DISPLAY_TEXT_REPLACEMENTS:
        normalized = normalized.replace(source, target)
    return normalized


def normalize_qualifying_diagnoses(
    diagnoses: list[dict[str, Any]] | None,
) -> list[dict[str, Any]]:
    """Normalize cached EK-1A diagnosis labels in patient-alert payloads."""
    normalized_rows: list[dict[str, Any]] = []
    for diagnosis in diagnoses or []:
        if not isinstance(diagnosis, dict):
            continue
        normalized = dict(diagnosis)
        normalized["disease"] = normalize_sut_display_text(
            normalized.get("disease") if isinstance(normalized.get("disease"), str) else None
        )
        normalized_rows.append(normalized)
    return normalized_rows
