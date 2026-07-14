"""Foreign-key and parent claim consistency checks."""

from __future__ import annotations

from collections.abc import Iterable, Mapping

from src.bilun.domain.claims.models import (
    ClaimDiagnosis,
    ClaimHeader,
    DrugClaimLine,
    MaterialClaimLine,
    MedulaRejectionEvent,
    PerformedProcedureLine,
    ProcedureClaimLine,
)
from src.bilun.domain.claims.validation.dates import date_within_claim


def validate_child_claim_link(
    child_id: str,
    claim_id: str,
    patient_id: str,
    episode_id: str | None,
    claims: Mapping[str, ClaimHeader],
    errors: list[str],
) -> ClaimHeader | None:
    claim = claims.get(claim_id)
    if claim is None:
        errors.append(f"{child_id} references unknown claim_id: {claim_id}")
        return None
    if patient_id != claim.patient_id:
        errors.append(f"{child_id} patient_id does not match claim {claim_id}")
    if episode_id is not None and episode_id != claim.episode_id:
        errors.append(f"{child_id} episode_id does not match claim {claim_id}")
    return claim


def validate_claim_links(
    claims: Mapping[str, ClaimHeader],
    diagnoses: Iterable[ClaimDiagnosis],
    procedures: Iterable[ProcedureClaimLine],
    materials: Iterable[MaterialClaimLine],
    drugs: Iterable[DrugClaimLine],
    errors: list[str],
) -> None:
    procedure_by_id = {line.procedure_line_id: line for line in procedures}
    for diagnosis in diagnoses:
        validate_child_claim_link(
            diagnosis.diagnosis_id,
            diagnosis.claim_id,
            diagnosis.patient_id,
            diagnosis.episode_id,
            claims,
            errors,
        )
    for line in list(procedures) + list(drugs):
        line_id = getattr(line, "procedure_line_id", getattr(line, "drug_claim_line_id", ""))
        validate_child_claim_link(
            line_id,
            line.claim_id,
            line.patient_id,
            line.episode_id,
            claims,
            errors,
        )
    for line in materials:
        if (
            validate_child_claim_link(
                line.material_line_id,
                line.claim_id,
                line.patient_id,
                None,
                claims,
                errors,
            )
            is None
        ):
            continue
        procedure = procedure_by_id.get(line.procedure_line_id)
        if procedure is None:
            errors.append(
                f"{line.material_line_id} references unknown procedure_line_id: "
                f"{line.procedure_line_id}"
            )
        elif procedure.claim_id != line.claim_id or procedure.patient_id != line.patient_id:
            errors.append(f"{line.material_line_id} procedure link crosses claim or patient")


def validate_performed_links(
    claims: Mapping[str, ClaimHeader],
    performed_lines: Iterable[PerformedProcedureLine],
    errors: list[str],
) -> None:
    for line in performed_lines:
        if (
            validate_child_claim_link(
                line.performed_line_id,
                line.claim_id,
                line.patient_id,
                line.episode_id,
                claims,
                errors,
            )
            is None
        ):
            continue
        date_within_claim(
            line.performed_line_id,
            line.claim_id,
            line.service_date,
            claims,
            errors,
        )


def validate_medula_rejection_links(
    claims: Mapping[str, ClaimHeader],
    events: Iterable[MedulaRejectionEvent],
    errors: list[str],
) -> None:
    for event in events:
        if (
            validate_child_claim_link(
                event.rejection_event_id,
                event.claim_id,
                event.patient_id,
                event.episode_id,
                claims,
                errors,
            )
            is None
        ):
            continue
        if event.rejection_timestamp is not None:
            date_within_claim(
                event.rejection_event_id,
                event.claim_id,
                event.rejection_timestamp,
                claims,
                errors,
            )
