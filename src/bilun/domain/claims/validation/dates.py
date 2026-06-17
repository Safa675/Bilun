"""Claim date-range validation helpers."""

from __future__ import annotations

from datetime import date
from typing import Iterable, Mapping

from src.bilun.domain.claims.models import (
    ClaimDiagnosis,
    ClaimHeader,
    DrugClaimLine,
    MaterialClaimLine,
    ProcedureClaimLine,
)


def date_within_claim(
    line_id: str,
    claim_id: str,
    line_date: date,
    claims: Mapping[str, ClaimHeader],
    errors: list[str],
) -> None:
    claim = claims.get(claim_id)
    if claim is None:
        return
    if not claim.claim_start_date <= line_date <= claim.claim_end_date:
        errors.append(
            f"{line_id} date {line_date.isoformat()} is outside claim "
            f"{claim_id} range {claim.claim_start_date.isoformat()}..{claim.claim_end_date.isoformat()}"
        )


def validate_diagnosis_dates(
    claims: Mapping[str, ClaimHeader],
    diagnoses: Iterable[ClaimDiagnosis],
    errors: list[str],
) -> None:
    for diagnosis in diagnoses:
        date_within_claim(
            diagnosis.diagnosis_id,
            diagnosis.claim_id,
            diagnosis.diagnosis_date,
            claims,
            errors,
        )


def validate_line_dates(
    claims: Mapping[str, ClaimHeader],
    procedures: Iterable[ProcedureClaimLine],
    materials: Iterable[MaterialClaimLine],
    drugs: Iterable[DrugClaimLine],
    errors: list[str],
) -> None:
    for line in procedures:
        date_within_claim(
            line.procedure_line_id, line.claim_id, line.procedure_date, claims, errors
        )
    for line in materials:
        date_within_claim(
            line.material_line_id, line.claim_id, line.material_date, claims, errors
        )
    for line in drugs:
        date_within_claim(
            line.drug_claim_line_id, line.claim_id, line.drug_claim_date, claims, errors
        )
