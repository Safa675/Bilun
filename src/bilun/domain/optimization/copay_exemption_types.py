"""Types for composable SUT copay exemption evaluation."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
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
    # The date the EK-1/A list is read on (#292): the latest evaluated claim's date
    # (admission, else start), one bill's own date; None = no claim, read on today.
    service_date: date | None = None


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
