"""Honest evaluation status for the legacy Tablo 15 #9 timing candidate.

The Health Ministry's 2022 handbook lists acceptances that can no longer be
billed after a period (Table 15 #9). Current SGK SUT 5.2.1 governs the timing
of billing-period closure after the service month. Claim headers contain a
service range but no MEDULA period-closure date, so this candidate cannot be
decided from the ingested data.

Sources:
https://dosyamerkez.saglik.gov.tr/Eklenti/44522/0/faturalandirma-usul-ve-esaslari-el-kitabi-06122022pdf.pdf
https://sgk.gov.tr/duyuru/detay/29082026-SUT-Degisiklik-Tebligi-Islenmis-Guncel-2013-SUT-2026-08-31-03-06-04
"""

from __future__ import annotations

from src.bilun.domain.billing.rule_findings import RuleEvaluation, RuleEvaluationBatch
from src.bilun.domain.claims.patient_context import PatientClaimContext


ADMISSION_BILLING_WINDOW_RULE_ID = "tablo15_9_admission_billing_window"
_REQUIRED_INPUTS = ["claim_headers", "billing_period_closure_date"]
_UNAVAILABLE_REASON = "billing_period_closure_date_not_ingested"


def evaluate_admission_billing_window_unavailable(
    patient_id: str,
    ctx: PatientClaimContext | None,
) -> RuleEvaluationBatch:
    """Record that Tablo 15 #9 cannot be judged from claim service dates."""
    if ctx is not None and (
        ctx.patient_id != patient_id
        or any(claim.patient_id != patient_id for claim in ctx.claims)
    ):
        raise ValueError("Billing-window context must belong to the report patient")

    if ctx is None or not ctx.claims:
        missing = ["claim_context"] if ctx is None else ["claim_headers"]
        return RuleEvaluationBatch(
            evaluations=(
                RuleEvaluation(
                    patient_id=patient_id,
                    claim_id=None,
                    rule_id=ADMISSION_BILLING_WINDOW_RULE_ID,
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
                rule_id=ADMISSION_BILLING_WINDOW_RULE_ID,
                evaluation_status="unavailable",
                required_inputs=list(_REQUIRED_INPUTS),
                missing_inputs=["billing_period_closure_date"],
                reason=_UNAVAILABLE_REASON,
            )
            for claim in sorted(ctx.claims, key=lambda row: row.claim_id)
        ),
    )
