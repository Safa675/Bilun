"""Occupational illness / work accident copay exemptions."""

from __future__ import annotations

from typing import Any

_OCCUPATIONAL_VISIT_TYPES = frozenset(
    {"is_kazasi", "meslek_hastaligi", "work_accident", "occupational_disease"}
)
_OCCUPATIONAL_CONTEXTS = frozenset(
    {"is_kazasi", "meslek_hastaligi", "work_accident", "occupational_disease"}
)


def _normalize(value: str) -> str:
    return str(value or "").strip().lower().replace(" ", "_")


def evaluate_occupational_exemption(
    claim_visit_types: tuple[str, ...],
    occupational_contexts: tuple[str, ...],
) -> dict[str, Any] | None:
    """Return exemption source when visit or claim context is occupational."""
    visit_norm = {_normalize(v) for v in claim_visit_types if v}
    context_norm = {_normalize(v) for v in occupational_contexts if v}

    matched_visit = visit_norm & _OCCUPATIONAL_VISIT_TYPES
    matched_context = context_norm & _OCCUPATIONAL_CONTEXTS

    if matched_visit:
        key = sorted(matched_visit)[0]
        return {
            "category": "is_kazasi_meslek",
            "rule_source": "SUT §1.8.5(1) work accident / occupational disease",
            "counts_toward_exempt": True,
            "evidence": {"visit_type": key},
        }
    if matched_context:
        key = sorted(matched_context)[0]
        return {
            "category": "is_kazasi_meslek",
            "rule_source": "SUT §1.8.5(1) work accident / occupational disease",
            "counts_toward_exempt": True,
            "evidence": {"occupational_context": key},
        }
    return None
