"""Unavailable evaluation for El Kitabı Table 15 #22.

The Health Ministry handbook's outpatient-errors table compares an exam's
date with the patient's acceptance date. The ingested claim model has an
inpatient admission date and a claim service range, but no outpatient
acceptance date. Neither available date establishes the handbook predicate.

Source: Health Ministry, Faturalandırma Usul ve Esasları El Kitabı (2022),
printed p. 48, Table 15 #22:
https://dosyamerkez.saglik.gov.tr/Eklenti/44522/0/faturalandirma-usul-ve-esaslari-el-kitabi-06122022pdf.pdf
"""

from __future__ import annotations

from src.bilun.domain.billing.rule_findings import RuleEvaluation, RuleEvaluationBatch
from src.bilun.domain.claims.patient_context import PatientClaimContext


EXAM_ACCEPTANCE_DATE_RULE_ID = "tablo15_22_exam_admission_date_mismatch"
_REQUIRED_INPUTS = ["claim_headers", "procedure_lines", "patient_acceptance_date"]
_UNAVAILABLE_REASON = "patient_acceptance_date_not_ingested"


def evaluate_exam_acceptance_date_unavailable(
    patient_id: str,
    ctx: PatientClaimContext | None,
) -> RuleEvaluationBatch:
    """Record the missing outpatient acceptance date without inferring a pass."""
    if ctx is not None and (
        ctx.patient_id != patient_id
        or any(claim.patient_id != patient_id for claim in ctx.claims)
    ):
        raise ValueError("Exam-date context must belong to the report patient")

    if ctx is None or not ctx.claims:
        missing = ["claim_context"] if ctx is None else ["claim_headers"]
        return RuleEvaluationBatch(
            evaluations=(
                RuleEvaluation(
                    patient_id=patient_id,
                    claim_id=None,
                    rule_id=EXAM_ACCEPTANCE_DATE_RULE_ID,
                    evaluation_status="missing_inputs",
                    required_inputs=list(_REQUIRED_INPUTS),
                    missing_inputs=missing,
                ),
            ),
        )

    return RuleEvaluationBatch(
        evaluations=tuple(
            RuleEvaluation(
                patient_id=patient_id,
                claim_id=claim.claim_id,
                rule_id=EXAM_ACCEPTANCE_DATE_RULE_ID,
                evaluation_status="unavailable",
                required_inputs=list(_REQUIRED_INPUTS),
                missing_inputs=["patient_acceptance_date"],
                reason=_UNAVAILABLE_REASON,
            )
            for claim in sorted(ctx.claims, key=lambda row: row.claim_id)
        ),
    )
