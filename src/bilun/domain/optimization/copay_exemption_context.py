"""Build copay exemption inputs from claim datasets and patient metadata."""

from __future__ import annotations

from typing import Any

from src.bilun.domain.claims.models import ClaimHeader
from src.bilun.domain.optimization.copay_exemption_types import (
    CopayExemptionInput,
    PatientCopayProfile,
)


def build_copay_exemption_input(
    *,
    diagnoses: list[str],
    patient_profile: PatientCopayProfile | None = None,
    patient_claims: tuple[ClaimHeader, ...] = (),
    age_at_latest_claim: float | None = None,
) -> CopayExemptionInput:
    visit_types: list[str] = []
    occupational: list[str] = []
    latest_year: int | None = None

    for claim in patient_claims:
        if claim.claim_type:
            visit_types.append(claim.claim_type)
        ctx = getattr(claim, "occupational_context", None) or "none"
        if ctx and str(ctx).strip().lower() not in ("none", ""):
            occupational.append(str(ctx))
        if claim.claim_end_date is not None:
            year = claim.claim_end_date.year
            if latest_year is None or year > latest_year:
                latest_year = year

    resolved_age = age_at_latest_claim
    if (
        resolved_age is None
        and patient_profile is not None
        and patient_profile.birth_year is not None
        and latest_year is not None
    ):
        resolved_age = float(latest_year - int(patient_profile.birth_year))

    return CopayExemptionInput(
        diagnoses=list(diagnoses),
        patient_profile=patient_profile,
        claim_visit_types=tuple(visit_types),
        occupational_contexts=tuple(occupational),
        age_at_latest_claim=resolved_age,
    )


def build_copay_inputs_by_patient(
    patient_ids: list[str],
    diagnoses_by_pid: dict[str, list[str]],
    *,
    claims_by_patient: dict[str, tuple[ClaimHeader, ...]] | None = None,
    copay_profiles_by_patient: dict[str, PatientCopayProfile] | None = None,
    age_by_patient: dict[str, float] | None = None,
) -> dict[str, CopayExemptionInput]:
    claims_by_patient = claims_by_patient or {}
    copay_profiles_by_patient = copay_profiles_by_patient or {}
    age_by_patient = age_by_patient or {}

    return {
        patient_id: build_copay_exemption_input(
            diagnoses=diagnoses_by_pid.get(patient_id, []),
            patient_profile=copay_profiles_by_patient.get(patient_id),
            patient_claims=claims_by_patient.get(patient_id, ()),
            age_at_latest_claim=age_by_patient.get(patient_id),
        )
        for patient_id in patient_ids
    }
