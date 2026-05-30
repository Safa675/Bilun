"""Visit-type copay exemptions (emergency, preventive)."""

from __future__ import annotations

from typing import Any

_EMERGENCY_TYPES = frozenset(
    {"acil", "acil_servis", "emergency", "emergency_department"}
)
_PREVENTIVE_TYPES = frozenset(
    {"koruyucu", "koruyucu_saglik", "preventive", "preventive_health"}
)


def _normalize_visit_type(value: str) -> str:
    return str(value or "").strip().lower().replace(" ", "_")


def evaluate_visit_type_exemptions(
    claim_visit_types: tuple[str, ...],
) -> list[dict[str, Any]]:
    """Return exemption sources for emergency or preventive visit types."""
    sources: list[dict[str, Any]] = []
    normalized = {_normalize_visit_type(v) for v in claim_visit_types if v}
    if not normalized:
        return sources

    if normalized & _EMERGENCY_TYPES:
        matched = sorted(normalized & _EMERGENCY_TYPES)[0]
        sources.append(
            {
                "category": "acil_servis",
                "rule_source": "SUT emergency visit copay waiver (visit type)",
                "evidence": {"visit_type": matched},
            }
        )

    if normalized & _PREVENTIVE_TYPES:
        matched = sorted(normalized & _PREVENTIVE_TYPES)[0]
        sources.append(
            {
                "category": "koruyucu_saglik",
                "rule_source": "SUT preventive health copay waiver (visit type)",
                "evidence": {"visit_type": matched},
            }
        )

    return sources
