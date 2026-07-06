"""Feature 2 gating: surcharge compliance now requires exact claim inputs.

CODE-ONLY BY DESIGN — surcharge exposure is computed via
``exactness.build_exact_surcharge_exposure`` + EK-2G list membership. The ~21
unencoded §1.9 clauses are surcharge-eligibility text the code resolves;
encoding as prose would duplicate the EK-2G catalog lookup. See
plans/refactor/rule-encoding-gap-closure-roadmap.md.
"""

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
