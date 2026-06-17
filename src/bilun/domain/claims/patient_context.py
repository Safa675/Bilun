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
        MedulaRejectionEvent,
        PerformedProcedureLine,
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
    performed_procedure_lines: tuple[PerformedProcedureLine, ...] = ()
    medula_rejection_events: tuple[MedulaRejectionEvent, ...] = ()
    medula_rejection_ingest_available: bool = False

    def slice_for_claim(self, claim_id: str) -> PatientClaimContext | None:
        """Scope this bundle to a single bill (``claim_id``).

        Returns ``None`` when the claim is not present in this context.
        """
        claims = tuple(c for c in self.claims if c.claim_id == claim_id)
        if not claims:
            return None

        return PatientClaimContext(
            patient_id=self.patient_id,
            claims=claims,
            procedure_lines=tuple(
                p for p in self.procedure_lines if p.claim_id == claim_id
            ),
            material_lines=tuple(
                m for m in self.material_lines if m.claim_id == claim_id
            ),
            drug_lines=tuple(d for d in self.drug_lines if d.claim_id == claim_id),
            diagnoses=tuple(dg for dg in self.diagnoses if dg.claim_id == claim_id),
            performed_procedure_lines=tuple(
                p for p in self.performed_procedure_lines if p.claim_id == claim_id
            ),
            medula_rejection_events=tuple(
                e for e in self.medula_rejection_events if e.claim_id == claim_id
            ),
            medula_rejection_ingest_available=self.medula_rejection_ingest_available,
        )


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
    performed = tuple(
        dataset.performed_procedure_lines_by_patient.get(patient_id, ())
    )
    medula_events = tuple(
        dataset.medula_rejection_events_by_patient.get(patient_id, ())
    )

    if not any((claims, procedures, materials, drugs, diagnoses, performed, medula_events)):
        return None

    return PatientClaimContext(
        patient_id=patient_id,
        claims=claims,
        procedure_lines=procedures,
        material_lines=materials,
        drug_lines=drugs,
        diagnoses=diagnoses,
        performed_procedure_lines=performed,
        medula_rejection_events=medula_events,
        medula_rejection_ingest_available=dataset.medula_rejection_ingest_available,
    )


def build_bill_claim_context(
    patient_id: str,
    claim_id: str,
    dataset: SUTClaimDataset,
) -> PatientClaimContext | None:
    """Scope a patient's claim context down to a single bill (``claim_id``).

    Every line-item model carries ``claim_id`` (see ``claims/models.py``), so
    the patient bundle filters cleanly to one bill. Returns ``None`` when the
    claim does not belong to the patient. The resulting context still has
    ``patient_id`` set so downstream algorithms behave identically to a
    single-claim patient. Callers that also scope the clinical lab feed should
    use ``bill.claims[0].episode_id`` (lab rows carry ``visit_id == episode_id``).
    """

    base = build_patient_claim_context(patient_id, dataset)
    if base is None:
        return None

    return base.slice_for_claim(claim_id)


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
