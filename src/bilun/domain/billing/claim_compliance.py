from __future__ import annotations

from dataclasses import asdict
from typing import Any

from src.bilun.domain.billing.rule_findings import (
    DIAGNOSIS_RULE_ID,
    ICU_RULE_ID,
    RuleEvaluation,
    RuleEvaluationBatch,
    RuleFinding,
)
from src.bilun.domain.billing.types import ClaimCompliance


_LINE_FIELDS = {
    "procedure": (
        "procedure_line_id",
        "procedure_code",
        "procedure_name",
        "lab_billing_status",
    ),
    "drug": ("drug_claim_line_id", "drug_code", "drug_name"),
    "material": (
        "material_line_id",
        "material_code",
        "material_name",
        "barcode_sut_mismatch",
        "titubb_uts_barcode_documentation_missing",
    ),
    "claim": (),
}


def _matches_finding(violation: dict[str, Any], finding: RuleFinding) -> bool:
    if (
        violation.get("rule_id") != finding.rule_id
        or violation.get("claim_id") != finding.claim_id
    ):
        return False
    if finding.line_id is None:
        return True
    return any(
        violation.get(key) == finding.line_id
        for key in ("procedure_line_id", "drug_claim_line_id", "material_line_id")
    )


def _serialize_finding(
    finding: RuleFinding,
    batch: RuleEvaluationBatch,
) -> dict[str, Any]:
    row = asdict(finding)
    row["status"] = "violation"
    source = next(
        (
            violation
            for violation in batch.legacy_violations
            if _matches_finding(violation, finding)
        ),
        None,
    )
    if source is not None:
        for key in _LINE_FIELDS[finding.line_kind]:
            if key in source:
                row[key] = source[key]
    return row


def _serialize_evaluation(evaluation: RuleEvaluation) -> dict[str, Any]:
    return {
        "patient_id": evaluation.patient_id,
        "claim_id": evaluation.claim_id,
        "rule_id": evaluation.rule_id,
        "status": evaluation.evaluation_status,
        "evaluation_status": evaluation.evaluation_status,
        "required_inputs": list(evaluation.required_inputs),
        "missing_inputs": list(evaluation.missing_inputs),
    }


def project_claim_compliance(
    patient_id: str,
    batch: RuleEvaluationBatch,
) -> ClaimCompliance:
    if any(
        row.patient_id != patient_id
        for row in (*batch.findings, *batch.evaluations)
    ):
        raise ValueError("Claim compliance batch must belong to the report patient")
    return ClaimCompliance(
        findings=[_serialize_finding(row, batch) for row in batch.findings],
        evaluations=[_serialize_evaluation(row) for row in batch.evaluations],
    )
