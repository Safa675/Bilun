"""Occupational illness / work accident copay exemptions."""

from __future__ import annotations

from typing import Any

from src.bilun.domain.turkish_fold import TurkishFold, fold_turkish

_OCCUPATIONAL_VISIT_TYPES = frozenset(
    {"is_kazasi", "meslek_hastaligi", "work_accident", "occupational_disease"}
)
_OCCUPATIONAL_CONTEXTS = frozenset(
    {"is_kazasi", "meslek_hastaligi", "work_accident", "occupational_disease"}
)


def evaluate_occupational_exemption(
    claim_visit_types: tuple[str, ...],
    occupational_contexts: tuple[str, ...],
) -> dict[str, Any] | None:
    """Return exemption source when visit or claim context is occupational."""
    visit_norm = {
        fold_turkish(v, TurkishFold.LOWER, strip=True).replace(" ", "_")
        for v in claim_visit_types
        if v
    }
    context_norm = {
        fold_turkish(v, TurkishFold.LOWER, strip=True).replace(" ", "_")
        for v in occupational_contexts
        if v
    }

    matched_visit = visit_norm & _OCCUPATIONAL_VISIT_TYPES
    matched_context = context_norm & _OCCUPATIONAL_CONTEXTS

    if matched_visit:
        key = sorted(matched_visit)[0]
        return {
            "category": "is_kazasi_meslek",
            "rule_source": "SUT §1.8.5(1) work accident / occupational disease",
            "counts_toward_exempt": True,
            "waives_sections": ("1.8.1", "1.8.2", "1.8.3"),
            "evidence": {"visit_type": key},
        }
    if matched_context:
        key = sorted(matched_context)[0]
        return {
            "category": "is_kazasi_meslek",
            "rule_source": "SUT §1.8.5(1) work accident / occupational disease",
            "counts_toward_exempt": True,
            "waives_sections": ("1.8.1", "1.8.2", "1.8.3"),
            "evidence": {"occupational_context": key},
        }
    return None
