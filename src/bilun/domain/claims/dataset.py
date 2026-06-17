"""In-memory claim table bundles and validated datasets."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from src.bilun.domain.claims.models import (
    ClaimDiagnosis,
    ClaimHeader,
    ClaimTotals,
    DrugClaimLine,
    ExpectedRuleOutput,
    MaterialClaimLine,
    MedulaRejectionEvent,
    PatientCopayProfile,
    PatientSUTClaimTotals,
    PerformedProcedureLine,
    ProcedureClaimLine,
)
from src.bilun.domain.claims.types import RowDict


@dataclass(frozen=True)
class ClaimTables:
    headers: tuple[RowDict, ...]
    diagnoses: tuple[RowDict, ...]
    procedures: tuple[RowDict, ...]
    materials: tuple[RowDict, ...]
    drugs: tuple[RowDict, ...]
    expected_outputs: tuple[RowDict, ...]
    copay_profiles: tuple[RowDict, ...] = ()
    performed_procedures: tuple[RowDict, ...] = ()
    medula_rejections: tuple[RowDict, ...] = ()
    medula_rejection_ingest_available: bool = False


@dataclass(frozen=True)
class SUTClaimDataset:
    """Validated exact claim rows with per-claim and per-patient indexes."""

    claims: dict[str, ClaimHeader]
    diagnoses: dict[str, ClaimDiagnosis]
    procedure_lines: dict[str, ProcedureClaimLine]
    material_lines: dict[str, MaterialClaimLine]
    drug_lines: dict[str, DrugClaimLine]
    performed_procedure_lines: dict[str, PerformedProcedureLine]
    medula_rejection_events: dict[str, MedulaRejectionEvent]
    medula_rejection_ingest_available: bool
    expected_outputs: dict[str, ExpectedRuleOutput]
    claims_by_patient: dict[str, tuple[ClaimHeader, ...]]
    diagnoses_by_patient: dict[str, tuple[ClaimDiagnosis, ...]]
    diagnoses_by_claim: dict[str, tuple[ClaimDiagnosis, ...]]
    diagnoses_by_episode: dict[str, tuple[ClaimDiagnosis, ...]]
    procedure_lines_by_claim: dict[str, tuple[ProcedureClaimLine, ...]]
    material_lines_by_claim: dict[str, tuple[MaterialClaimLine, ...]]
    drug_lines_by_claim: dict[str, tuple[DrugClaimLine, ...]]
    procedure_lines_by_patient: dict[str, tuple[ProcedureClaimLine, ...]]
    material_lines_by_patient: dict[str, tuple[MaterialClaimLine, ...]]
    drug_lines_by_patient: dict[str, tuple[DrugClaimLine, ...]]
    performed_procedure_lines_by_claim: dict[str, tuple[PerformedProcedureLine, ...]]
    performed_procedure_lines_by_patient: dict[str, tuple[PerformedProcedureLine, ...]]
    medula_rejection_events_by_claim: dict[str, tuple[MedulaRejectionEvent, ...]]
    medula_rejection_events_by_patient: dict[str, tuple[MedulaRejectionEvent, ...]]
    expected_outputs_by_claim: dict[str, tuple[ExpectedRuleOutput, ...]]
    expected_outputs_by_line: dict[str, tuple[ExpectedRuleOutput, ...]]
    claim_totals: dict[str, ClaimTotals]
    patient_totals: dict[str, PatientSUTClaimTotals]
    copay_profiles_by_patient: dict[str, PatientCopayProfile]

    def claim_lines(
        self, claim_id: str
    ) -> tuple[tuple[ProcedureClaimLine, ...], tuple[MaterialClaimLine, ...], tuple[DrugClaimLine, ...]]:
        """Return procedure, material, and drug lines for a claim."""

        return (
            self.procedure_lines_by_claim.get(claim_id, ()),
            self.material_lines_by_claim.get(claim_id, ()),
            self.drug_lines_by_claim.get(claim_id, ()),
        )

    @classmethod
    def from_rows(
        cls,
        *,
        claim_headers: Sequence[RowDict],
        diagnoses: Sequence[RowDict],
        procedure_lines: Sequence[RowDict],
        material_lines: Sequence[RowDict],
        drug_lines: Sequence[RowDict],
        expected_outputs: Sequence[RowDict],
        copay_profiles: Sequence[RowDict] = (),
        performed_procedure_lines: Sequence[RowDict] = (),
        medula_rejection_events: Sequence[RowDict] = (),
        medula_rejection_ingest_available: bool = False,
    ) -> SUTClaimDataset:
        """Build a validated dataset from raw row dictionaries."""

        from src.bilun.domain.claims.dataset_builder import build_sut_claim_dataset_from_rows

        return build_sut_claim_dataset_from_rows(
            claim_headers=claim_headers,
            diagnoses=diagnoses,
            procedure_lines=procedure_lines,
            material_lines=material_lines,
            drug_lines=drug_lines,
            expected_outputs=expected_outputs,
            copay_profiles=copay_profiles,
            performed_procedure_lines=performed_procedure_lines,
            medula_rejection_events=medula_rejection_events,
            medula_rejection_ingest_available=medula_rejection_ingest_available,
        )
