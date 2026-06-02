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


_GREEN_ZONE_EXAM_CODE = "520021"


def _normalize_procedure_code(value: str) -> str:
    return str(value or "").strip()


def evaluate_visit_type_exemptions(
    claim_visit_types: tuple[str, ...],
    claim_procedure_codes: tuple[str, ...] = (),
) -> list[dict[str, Any]]:
    """Return exemption sources for emergency or preventive visit types."""
    sources: list[dict[str, Any]] = []
    normalized = {_normalize_visit_type(v) for v in claim_visit_types if v}
    if not normalized:
        return sources

    procedure_codes = {
        _normalize_procedure_code(code) for code in claim_procedure_codes if code
    }

    only_green_zone_exam = bool(procedure_codes) and procedure_codes <= {
        _GREEN_ZONE_EXAM_CODE
    }
    if normalized & _EMERGENCY_TYPES and not only_green_zone_exam:
        matched = sorted(normalized & _EMERGENCY_TYPES)[0]
        sources.append(
            {
                "category": "acil_servis",
                "rule_source": "SUT §1.8.5(5) emergency visit copay waiver (520021 excluded)",
                "counts_toward_exempt": True,
                "evidence": {
                    "visit_type": matched,
                    "procedure_codes": sorted(procedure_codes),
                },
            }
        )

    if normalized & _PREVENTIVE_TYPES:
        matched = sorted(normalized & _PREVENTIVE_TYPES)[0]
        sources.append(
            {
                "category": "koruyucu_saglik",
                "rule_source": "SUT §1.8.5(6) preventive health copay waiver",
                "counts_toward_exempt": True,
                "evidence": {"visit_type": matched},
            }
        )

    return sources
