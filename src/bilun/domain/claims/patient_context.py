"""Patient- and cohort-level claim context bundles for billing and optimization."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.bilun.domain.claims.loader import SUTClaimDataset
    from src.bilun.domain.claims.models import (
        ClaimDiagnosis,
        ClaimHeader,
        DrugClaimLine,
        MaterialClaimLine,
        ProcedureClaimLine,
    )


@dataclass(frozen=True)
class PatientClaimContext:
    """Exact claim-line bundle for one patient."""

    patient_id: str
    claims: tuple[ClaimHeader, ...]
    procedure_lines: tuple[ProcedureClaimLine, ...]
    material_lines: tuple[MaterialClaimLine, ...]
    drug_lines: tuple[DrugClaimLine, ...]
    diagnoses: tuple[ClaimDiagnosis, ...]


@dataclass(frozen=True)
class CohortClaimContext:
    """Indexes for cohort-level algorithms."""

    patient_contexts: dict[str, PatientClaimContext]
    all_procedure_lines: tuple[ProcedureClaimLine, ...]
    all_drug_lines: tuple[DrugClaimLine, ...]
    all_material_lines: tuple[MaterialClaimLine, ...]
    n_patients: int


def build_patient_claim_context(
    patient_id: str,
    dataset: SUTClaimDataset,
) -> PatientClaimContext | None:
    """Build exact claim context when the patient has at least one claim line."""

    claims = tuple(dataset.claims_by_patient.get(patient_id, ()))
    procedures = tuple(dataset.procedure_lines_by_patient.get(patient_id, ()))
    materials = tuple(dataset.material_lines_by_patient.get(patient_id, ()))
    drugs = tuple(dataset.drug_lines_by_patient.get(patient_id, ()))
    diagnoses = tuple(dataset.diagnoses_by_patient.get(patient_id, ()))

    if not any((claims, procedures, materials, drugs, diagnoses)):
        return None

    return PatientClaimContext(
        patient_id=patient_id,
        claims=claims,
        procedure_lines=procedures,
        material_lines=materials,
        drug_lines=drugs,
        diagnoses=diagnoses,
    )


def build_cohort_claim_context(dataset: SUTClaimDataset | None) -> CohortClaimContext | None:
    """Build cohort indexes from a loaded claim dataset."""

    if dataset is None:
        return None

    patient_ids = sorted(
        set(dataset.claims_by_patient.keys())
        | set(dataset.procedure_lines_by_patient.keys())
        | set(dataset.drug_lines_by_patient.keys())
    )
    contexts: dict[str, PatientClaimContext] = {}
    for patient_id in patient_ids:
        ctx = build_patient_claim_context(patient_id, dataset)
        if ctx is not None:
            contexts[patient_id] = ctx

    if not contexts:
        return None

    return CohortClaimContext(
        patient_contexts=contexts,
        all_procedure_lines=tuple(dataset.procedure_lines.values()),
        all_drug_lines=tuple(dataset.drug_lines.values()),
        all_material_lines=tuple(dataset.material_lines.values()),
        n_patients=len(contexts),
    )
