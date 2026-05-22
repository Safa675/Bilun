"""Feature 2 gating: surcharge compliance now requires exact claim inputs."""

from __future__ import annotations

from typing import Any

from .exactness import build_exact_surcharge_exposure, unavailable_surcharge_exposure
from .runtime_claim_context import get_surcharge_context


def analyze_surcharge_exposure(patient_icd10_chapters: set[str]) -> dict[str, Any]:
    """Analyze surcharge compliance from exact claim lines when available."""

    _ = patient_icd10_chapters
    context = get_surcharge_context()
    if context is not None:
        return build_exact_surcharge_exposure(context)
    return unavailable_surcharge_exposure()
