"""Types for composable SUT copay exemption evaluation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from src.bilun.domain.claims.models import PatientCopayProfile


@dataclass
class CopayExemptionInput:
    """Inputs for a single patient exemption evaluation."""

    diagnoses: list[str] = field(default_factory=list)
    patient_profile: PatientCopayProfile | None = None
    claim_visit_types: tuple[str, ...] = ()
    claim_procedure_codes: tuple[str, ...] = ()
    occupational_contexts: tuple[str, ...] = ()
    age_at_latest_claim: float | None = None
    has_chronic_health_report: bool | None = None


def empty_copay_exemption_result() -> dict[str, Any]:
    return {
        "exempt": False,
        "n_qualifying": 0,
        "qualifying_diagnoses": [],
        "exemption_sources": [],
        "categories_not_evaluated": [],
        "primary_exemption_category": None,
        "partial_exempt": False,
    }
