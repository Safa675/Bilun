"""Feature 5 gating: DRG unbundling is unavailable without exact claim lines."""

from __future__ import annotations

from typing import Any

from .exactness import unavailable_patient_drg_unbundling


def detect_drg_unbundling(
    patient_icd10_chapters: set[str],
) -> dict[str, Any]:
    """Gate DRG unbundling until exact itemized claim inputs exist."""
    _ = patient_icd10_chapters
    return unavailable_patient_drg_unbundling()
