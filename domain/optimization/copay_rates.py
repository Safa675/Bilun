"""Feature 3 gating: copay-rate compliance now requires exact claim inputs."""

from __future__ import annotations

from typing import Any

from .exactness import build_exact_copay_rate_exposure, unavailable_copay_rate_exposure
from .runtime_claim_context import get_copay_rate_context


def analyze_copay_rate_exposure(
    patient_icd10_chapters: set[str],
) -> dict[str, Any]:
    """Analyze copay-rate compliance from exact claim lines when available."""

    _ = patient_icd10_chapters
    context = get_copay_rate_context()
    if context is not None:
        return build_exact_copay_rate_exposure(context)
    return unavailable_copay_rate_exposure()
