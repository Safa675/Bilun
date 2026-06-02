"""Build copay exemption inputs from claim datasets and patient metadata."""

from __future__ import annotations

from typing import Any

from src.bilun.domain.claims.models import ClaimHeader, PatientCopayProfile
from src.bilun.domain.optimization.copay_exemption_types import CopayExemptionInput


def build_copay_exemption_input(
    *,
    diagnoses: list[str],
    patient_profile: PatientCopayProfile | None = None,
    patient_claims: tuple[ClaimHeader, ...] = (),
    claim_procedure_codes: tuple[str, ...] = (),
    age_at_latest_claim: float | None = None,
    has_chronic_health_report: bool | None = None,
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
        claim_procedure_codes=tuple(claim_procedure_codes),
        occupational_contexts=tuple(occupational),
        age_at_latest_claim=resolved_age,
        has_chronic_health_report=has_chronic_health_report,
    )


def build_copay_inputs_by_patient(
    patient_ids: list[str],
    diagnoses_by_pid: dict[str, list[str]],
    *,
    claims_by_patient: dict[str, tuple[ClaimHeader, ...]] | None = None,
    copay_profiles_by_patient: dict[str, PatientCopayProfile] | None = None,
    procedure_lines_by_patient: dict[str, tuple[Any, ...]] | None = None,
    age_by_patient: dict[str, float] | None = None,
    health_report_by_patient: dict[str, bool] | None = None,
) -> dict[str, CopayExemptionInput]:
    claims_by_patient = claims_by_patient or {}
    copay_profiles_by_patient = copay_profiles_by_patient or {}
    procedure_lines_by_patient = procedure_lines_by_patient or {}
    age_by_patient = age_by_patient or {}
    health_report_by_patient = health_report_by_patient or {}

    inputs: dict[str, CopayExemptionInput] = {}
    for patient_id in patient_ids:
        procedure_codes: list[str] = []
        for line in procedure_lines_by_patient.get(patient_id, ()):
            code = str(getattr(line, "procedure_code", "") or "").strip()
            if code:
                procedure_codes.append(code)

        inputs[patient_id] = build_copay_exemption_input(
            diagnoses=diagnoses_by_pid.get(patient_id, []),
            patient_profile=copay_profiles_by_patient.get(patient_id),
            patient_claims=claims_by_patient.get(patient_id, ()),
            claim_procedure_codes=tuple(procedure_codes),
            age_at_latest_claim=age_by_patient.get(patient_id),
            has_chronic_health_report=health_report_by_patient.get(patient_id),
        )
    return inputs
