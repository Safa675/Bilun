from __future__ import annotations

from collections import defaultdict
from datetime import date
from typing import Any
from urllib.parse import quote

from src.bilun.domain.billing.types import ClaimCompliance
from src.bilun.domain.claims.models import ClaimHeader, ProcedureClaimLine
from src.bilun.domain.claims.patient_context import PatientClaimContext
from src.bilun.domain.prose_rules.common_billing_errors import detect_missing_diagnosis
from src.bilun.domain.prose_rules.icu_bundled_leakage import detect_icu_bundled_leakage

ICU_RULE_ID = "icu_bundled_leakage_510090"
DIAGNOSIS_RULE_ID = "tablo15_8_missing_diagnosis"
_RECOGNIZED_CLAIM_TYPES = frozenset(
    {"yatis", "yatarak", "inpatient", "poliklinik", "ayakta", "outpatient", "gunubirlik"}
)
_MONEY_FIELDS = (
    "amount_try",
    "billed_try",
    "payable_try",
    "savings_try",
    "recoverable_uplift_try",
    "compliance_savings_try",
    "risk_amount_try",
    "audit_exposure_try",
)


def _evaluation(
    patient_id: str, claim_id: str | None, rule_id: str, missing: list[str]
) -> dict[str, Any]:
    return {
        "patient_id": patient_id,
        "claim_id": claim_id,
        "rule_id": rule_id,
        "status": "missing_inputs" if missing else "evaluated",
        "missing_inputs": missing,
    }


def project_claim_compliance(
    patient_id: str, ctx: PatientClaimContext | None
) -> ClaimCompliance:
    result = ClaimCompliance()
    if ctx is None:
        result.evaluations = [
            _evaluation(patient_id, None, rule_id, ["claim_context"])
            for rule_id in (ICU_RULE_ID, DIAGNOSIS_RULE_ID)
        ]
        return result
    if ctx.patient_id != patient_id or any(
        row.patient_id != patient_id
        for rows in (
            ctx.claims, ctx.procedure_lines, ctx.material_lines, ctx.drug_lines,
            ctx.diagnoses, ctx.performed_procedure_lines, ctx.medula_rejection_events,
        )
        for row in rows
    ):
        raise ValueError("Claim compliance context must belong to the report patient")
    if not ctx.claims:
        result.evaluations = [
            _evaluation(patient_id, None, rule_id, ["claim_headers"])
            for rule_id in (ICU_RULE_ID, DIAGNOSIS_RULE_ID)
        ]
        return result

    procedures: dict[str, list[ProcedureClaimLine]] = defaultdict(list)
    claim_ids = {claim.claim_id for claim in ctx.claims}
    for line in ctx.procedure_lines:
        if line.claim_id not in claim_ids:
            raise ValueError("Claim compliance procedure must belong to a context claim")
        procedures[line.claim_id].append(line)

    icu_claims: list[ClaimHeader] = []
    diagnosis_claims: list[ClaimHeader] = []
    for claim in sorted(ctx.claims, key=lambda row: row.claim_id):
        lines = procedures[claim.claim_id]
        missing = []
        if claim.claim_type.strip().casefold() not in _RECOGNIZED_CLAIM_TYPES:
            missing.append("claim_type")
        if not lines:
            missing.append("procedure_lines")
        if any(not line.procedure_code.strip() for line in lines):
            missing.append("procedure_code")
        if any(
            not isinstance(line.procedure_date, date) or line.procedure_date == date.min
            for line in lines
        ):
            missing.append("procedure_date")
        result.evaluations.append(_evaluation(patient_id, claim.claim_id, ICU_RULE_ID, missing))
        if not missing:
            icu_claims.append(claim)

        missing = [] if claim.primary_icd10_available else ["primary_icd10"]
        result.evaluations.append(
            _evaluation(patient_id, claim.claim_id, DIAGNOSIS_RULE_ID, missing)
        )
        if not missing:
            diagnosis_claims.append(claim)

    violations = detect_icu_bundled_leakage(
        icu_claims,
        [line for claim in icu_claims for line in procedures[claim.claim_id]],
    )
    violations.extend(detect_missing_diagnosis(diagnosis_claims))
    findings: dict[str, dict[str, Any]] = {}
    for violation in violations:
        rule_id = violation["rule_id"]
        claim_id = violation["claim_id"]
        line_id = violation.get("procedure_line_id")
        action_id = "claim_compliance:" + ":".join(
            quote(value, safe="") for value in (rule_id, patient_id, claim_id, line_id or "")
        )
        finding = {
            "action_id": action_id,
            "patient_id": patient_id,
            "claim_id": claim_id,
            "rule_id": rule_id,
            "kind": rule_id,
            "status": "violation",
            "finding_type": "compliance",
            "detail": violation["detail"],
            "sut_section_id": violation["sut_section_id"],
            **dict.fromkeys(_MONEY_FIELDS),
        }
        for key in ("procedure_line_id", "procedure_code", "procedure_name"):
            if key in violation:
                finding[key] = violation[key]
        findings.setdefault(action_id, finding)
    result.findings = [findings[key] for key in sorted(findings)]
    return result
