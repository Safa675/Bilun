"""Exact per-claim and per-patient total aggregation."""

from __future__ import annotations

from decimal import Decimal
from collections.abc import Iterable, Mapping

from src.bilun.domain.claims.indexing import index_sequence
from src.bilun.domain.claims.models import (
    ClaimHeader,
    ClaimTotals,
    DrugClaimLine,
    MaterialClaimLine,
    PatientSUTClaimTotals,
    ProcedureClaimLine,
)


def build_claim_totals(
    claims: Mapping[str, ClaimHeader],
    procedures: Iterable[ProcedureClaimLine],
    materials: Iterable[MaterialClaimLine],
    drugs: Iterable[DrugClaimLine],
) -> dict[str, ClaimTotals]:
    procedure_by_claim = index_sequence(procedures, "claim_id")
    material_by_claim = index_sequence(materials, "claim_id")
    drug_by_claim = index_sequence(drugs, "claim_id")
    totals: dict[str, ClaimTotals] = {}
    for claim_id, claim in claims.items():
        procedure_lines = procedure_by_claim.get(claim_id, ())
        material_lines = material_by_claim.get(claim_id, ())
        drug_lines = drug_by_claim.get(claim_id, ())
        all_lines = (*procedure_lines, *material_lines, *drug_lines)
        totals[claim_id] = ClaimTotals(
            claim_id=claim_id,
            patient_id=claim.patient_id,
            total_billed_try=sum((line.billed_amount_try for line in all_lines), Decimal("0.00")),
            total_expected_payable_try=sum(
                (line.expected_payable_try for line in all_lines), Decimal("0.00")
            ),
            procedure_line_count=len(procedure_lines),
            material_line_count=len(material_lines),
            drug_line_count=len(drug_lines),
            lab_billed_line_count=sum(
                1 for line in procedure_lines if line.procedure_category.casefold() == "laboratuvar"
            ),
        )
    return totals


def validate_claim_total_reconciliation(
    claims: Mapping[str, ClaimHeader],
    claim_totals: Mapping[str, ClaimTotals],
    errors: list[str],
) -> None:
    for claim_id, claim in claims.items():
        totals = claim_totals[claim_id]
        if totals.total_billed_try != claim.expected_total_billed_try:
            errors.append(f"{claim_id} billed total does not reconcile")
        if totals.total_expected_payable_try != claim.expected_total_payable_try:
            errors.append(f"{claim_id} payable total does not reconcile")


def build_patient_totals(
    claims: Iterable[ClaimHeader],
    claim_totals: Mapping[str, ClaimTotals],
) -> dict[str, PatientSUTClaimTotals]:
    claims_by_patient = index_sequence(claims, "patient_id")
    patient_totals: dict[str, PatientSUTClaimTotals] = {}
    for patient_id, patient_claims in claims_by_patient.items():
        totals = [claim_totals[claim.claim_id] for claim in patient_claims]
        patient_totals[patient_id] = PatientSUTClaimTotals(
            patient_id=patient_id,
            total_billed_try=sum((total.total_billed_try for total in totals), Decimal("0.00")),
            total_expected_payable_try=sum(
                (total.total_expected_payable_try for total in totals), Decimal("0.00")
            ),
            claim_count=len(patient_claims),
            procedure_line_count=sum(total.procedure_line_count for total in totals),
            material_line_count=sum(total.material_line_count for total in totals),
            drug_line_count=sum(total.drug_line_count for total in totals),
            lab_billed_line_count=sum(total.lab_billed_line_count for total in totals),
        )
    return patient_totals
