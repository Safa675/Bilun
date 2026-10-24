from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any, Literal
from urllib.parse import quote

from src.bilun.domain.claims.claim_type import care_setting_gap
from src.bilun.domain.claims.patient_context import PatientClaimContext
from src.bilun.domain.prose_rules.common_billing_errors import (
    detect_material_identity_errors,
    detect_missing_diagnosis,
    detect_missing_drug_barcode,
    detect_unreported_lab_result,
)
from src.bilun.domain.prose_rules.icu_bundled_leakage import (
    detect_icu_bundled_leakage,
)


LineKind = Literal["procedure", "drug", "material", "claim"]
EvaluationStatus = Literal["evaluated", "missing_inputs", "unavailable"]

ICU_RULE_ID = "icu_bundled_leakage_510090"
DIAGNOSIS_RULE_ID = "tablo15_8_missing_diagnosis"
LAB_RULE_ID = "tablo15_10_unreported_lab_result"
DRUG_BARCODE_RULE_ID = "tablo15_20_missing_drug_barcode"
MATERIAL_IDENTITY_RULE_ID = "tablo15_5_material_identity_error"

_RULE_ORDER = (
    ICU_RULE_ID,
    DIAGNOSIS_RULE_ID,
    LAB_RULE_ID,
    DRUG_BARCODE_RULE_ID,
    MATERIAL_IDENTITY_RULE_ID,
)
_REQUIRED_INPUTS = {
    ICU_RULE_ID: [
        "claim_headers",
        "claim_type",
        "procedure_lines",
        "procedure_code",
        "procedure_date",
    ],
    DIAGNOSIS_RULE_ID: ["claim_headers", "primary_icd10"],
    LAB_RULE_ID: ["claim_headers", "procedure_lines", "lab_billing_status"],
    DRUG_BARCODE_RULE_ID: ["claim_headers", "drug_lines", "barkod"],
    MATERIAL_IDENTITY_RULE_ID: ["claim_headers", "material_lines", "material_identity"],
}
_LINE_MAPPING: dict[str, tuple[LineKind, str | None]] = {
    ICU_RULE_ID: ("procedure", "procedure_line_id"),
    DIAGNOSIS_RULE_ID: ("claim", None),
    LAB_RULE_ID: ("procedure", "procedure_line_id"),
    DRUG_BARCODE_RULE_ID: ("drug", "drug_claim_line_id"),
    MATERIAL_IDENTITY_RULE_ID: ("material", "material_line_id"),
}
_SOURCE_ENGINE = {
    ICU_RULE_ID: "detect_icu_bundled_leakage",
    DIAGNOSIS_RULE_ID: "detect_missing_diagnosis",
    LAB_RULE_ID: "detect_unreported_lab_result",
    DRUG_BARCODE_RULE_ID: "detect_missing_drug_barcode",
    MATERIAL_IDENTITY_RULE_ID: "detect_material_identity_errors",
}


def build_finding_id(
    *,
    rule_id: str,
    patient_id: str,
    claim_id: str,
    line_kind: LineKind,
    line_id: str | None,
) -> str:
    return "claim_compliance:" + ":".join(
        quote(value, safe="")
        for value in (rule_id, patient_id, claim_id, line_kind, line_id or "")
    )


def build_evaluation_id(
    *,
    rule_id: str,
    patient_id: str,
    claim_id: str | None,
    line_kind: LineKind,
    line_id: str | None,
) -> str:
    """Identify one rule evaluation at its actual claim or source-line scope."""
    return "claim_evaluation:" + ":".join(
        quote(value, safe="")
        for value in (rule_id, patient_id, claim_id or "", line_kind, line_id or "")
    )


@dataclass(frozen=True)
class RuleFinding:
    finding_id: str
    patient_id: str
    claim_id: str
    line_kind: LineKind
    line_id: str | None
    rule_id: str
    kind: str
    severity: str
    detail: str
    sut_section_id: str | None
    regulatory_source: object | None
    source_engine: str
    evaluation_status: EvaluationStatus
    required_inputs: list[str]
    missing_inputs: list[str]
    finding_type: Literal["compliance"] = "compliance"
    surface: Literal["claim_compliance"] = "claim_compliance"
    money_semantics: Literal["unpriced_compliance"] = "unpriced_compliance"
    amount_try: None = None
    billed_try: None = None
    payable_try: None = None
    savings_try: None = None
    recoverable_uplift_try: None = None
    compliance_savings_try: None = None
    risk_amount_try: None = None
    audit_exposure_try: None = None
    action_id: str = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "action_id", self.finding_id)


@dataclass(frozen=True)
class RuleEvaluation:
    patient_id: str
    claim_id: str | None
    rule_id: str
    evaluation_status: EvaluationStatus
    required_inputs: list[str]
    missing_inputs: list[str]
    line_kind: LineKind = "claim"
    line_id: str | None = None
    decision: str | None = None
    reason: str | None = None
    evaluation_id: str = field(init=False)

    def __post_init__(self) -> None:
        if not self.patient_id.strip() or not self.rule_id.strip():
            raise ValueError("Evaluation patient and rule IDs must be nonempty")
        if self.claim_id is not None and not self.claim_id.strip():
            raise ValueError("Evaluation claim ID must be nonempty when present")
        if self.line_kind not in ("claim", "procedure", "drug", "material"):
            raise ValueError(f"Unknown evaluation line kind: {self.line_kind}")
        if self.line_kind != "claim" and self.claim_id is None:
            raise ValueError("Line evaluations require a claim ID")
        if (self.line_kind == "claim") != (self.line_id is None):
            raise ValueError(
                "Line evaluations require a line ID; claim evaluations cannot have one"
            )
        if self.line_id is not None and not self.line_id.strip():
            raise ValueError("Evaluation source line ID must be nonempty")
        object.__setattr__(
            self,
            "evaluation_id",
            build_evaluation_id(
                rule_id=self.rule_id,
                patient_id=self.patient_id,
                claim_id=self.claim_id,
                line_kind=self.line_kind,
                line_id=self.line_id,
            ),
        )


@dataclass(frozen=True)
class RuleEvaluationBatch:
    findings: tuple[RuleFinding, ...] = ()
    evaluations: tuple[RuleEvaluation, ...] = ()
    legacy_violations: tuple[dict[str, Any], ...] = ()


def _evaluation(
    patient_id: str,
    claim_id: str | None,
    rule_id: str,
    missing_inputs: list[str],
) -> RuleEvaluation:
    return RuleEvaluation(
        patient_id=patient_id,
        claim_id=claim_id,
        rule_id=rule_id,
        evaluation_status="missing_inputs" if missing_inputs else "evaluated",
        required_inputs=list(_REQUIRED_INPUTS[rule_id]),
        missing_inputs=missing_inputs,
    )


def _validate_context_ownership(patient_id: str, ctx: PatientClaimContext) -> None:
    if ctx.patient_id != patient_id or any(
        row.patient_id != patient_id
        for rows in (
            ctx.claims,
            ctx.procedure_lines,
            ctx.material_lines,
            ctx.drug_lines,
            ctx.diagnoses,
            ctx.performed_procedure_lines,
            ctx.medula_rejection_events,
        )
        for row in rows
    ):
        raise ValueError("Claim compliance context must belong to the report patient")

    if not ctx.claims:
        return

    claim_ids = {claim.claim_id for claim in ctx.claims}
    for label, rows in (
        ("procedure", ctx.procedure_lines),
        ("material", ctx.material_lines),
        ("drug", ctx.drug_lines),
        ("diagnosis", ctx.diagnoses),
    ):
        if any(row.claim_id not in claim_ids for row in rows):
            raise ValueError(
                f"Claim compliance {label} must belong to a context claim"
            )


def _regulatory_source(violation: dict[str, Any]) -> object | None:
    clause_ref = violation.get("clause_ref")
    if clause_ref is not None:
        return clause_ref
    source_type = violation.get("source_type")
    if source_type is not None:
        return {"source_type": source_type}
    return None


def _normalize_finding(
    patient_id: str,
    violation: dict[str, Any],
) -> RuleFinding:
    rule_id = str(violation["rule_id"])
    line_kind, line_key = _LINE_MAPPING[rule_id]
    line_id = str(violation[line_key]) if line_key and violation.get(line_key) is not None else None
    claim_id = str(violation["claim_id"])
    finding_id = build_finding_id(
        rule_id=rule_id,
        patient_id=patient_id,
        claim_id=claim_id,
        line_kind=line_kind,
        line_id=line_id,
    )
    return RuleFinding(
        finding_id=finding_id,
        patient_id=patient_id,
        claim_id=claim_id,
        line_kind=line_kind,
        line_id=line_id,
        rule_id=rule_id,
        kind=rule_id,
        severity=str(violation.get("severity", "warning")),
        detail=str(violation.get("detail", "")),
        sut_section_id=(
            str(violation["sut_section_id"])
            if violation.get("sut_section_id") is not None
            else None
        ),
        regulatory_source=_regulatory_source(violation),
        source_engine=_SOURCE_ENGINE[rule_id],
        evaluation_status="evaluated",
        required_inputs=list(_REQUIRED_INPUTS[rule_id]),
        missing_inputs=[],
    )


def evaluate_rule_findings(
    patient_id: str,
    ctx: PatientClaimContext | None,
) -> RuleEvaluationBatch:
    if ctx is None:
        return RuleEvaluationBatch(
            evaluations=tuple(
                _evaluation(patient_id, None, rule_id, ["claim_context"])
                for rule_id in _RULE_ORDER
            )
        )

    _validate_context_ownership(patient_id, ctx)
    if not ctx.claims:
        return RuleEvaluationBatch(
            evaluations=tuple(
                _evaluation(patient_id, None, rule_id, ["claim_headers"])
                for rule_id in _RULE_ORDER
            )
        )

    procedures_by_claim: dict[str, list[Any]] = {}
    for line in ctx.procedure_lines:
        procedures_by_claim.setdefault(line.claim_id, []).append(line)

    normalized_primary_diagnosis: dict[str, str] = {}
    for diagnosis in ctx.diagnoses:
        code = diagnosis.icd10_code.strip()
        if diagnosis.is_primary and code:
            normalized_primary_diagnosis.setdefault(diagnosis.claim_id, code)

    evaluations: list[RuleEvaluation] = []
    evaluation_status: dict[tuple[str, str], EvaluationStatus] = {}
    for claim in sorted(ctx.claims, key=lambda row: row.claim_id):
        lines = procedures_by_claim.get(claim.claim_id, [])
        icu_missing: list[str] = []
        # The care setting comes from the one claim-type vocabulary (#335).
        if care_setting_gap(claim.claim_type) is not None:
            icu_missing.append("claim_type")
        if not lines:
            icu_missing.append("procedure_lines")
        if any(not line.procedure_code.strip() for line in lines):
            icu_missing.append("procedure_code")
        if any(
            not isinstance(line.procedure_date, date) or line.procedure_date == date.min
            for line in lines
        ):
            icu_missing.append("procedure_date")

        header_diagnosis = (claim.primary_icd10 or "").strip()
        normalized_diagnosis = normalized_primary_diagnosis.get(claim.claim_id, "")
        diagnosis_missing = (
            []
            if header_diagnosis or normalized_diagnosis or claim.primary_icd10_available
            else ["primary_icd10"]
        )
        per_rule_missing = {
            ICU_RULE_ID: icu_missing,
            DIAGNOSIS_RULE_ID: diagnosis_missing,
            LAB_RULE_ID: [],
            DRUG_BARCODE_RULE_ID: [],
            MATERIAL_IDENTITY_RULE_ID: [],
        }
        for rule_id in _RULE_ORDER:
            evaluation = _evaluation(
                patient_id,
                claim.claim_id,
                rule_id,
                per_rule_missing[rule_id],
            )
            evaluations.append(evaluation)
            evaluation_status[(claim.claim_id, rule_id)] = evaluation.evaluation_status

    if not ctx.patient_id:
        return RuleEvaluationBatch(evaluations=tuple(evaluations))

    claim_ids_with_procs = {line.claim_id for line in ctx.procedure_lines}
    icu_violations = detect_icu_bundled_leakage(
        list(ctx.claims),
        list(ctx.procedure_lines),
        claim_ids_with_procs=claim_ids_with_procs,
    )
    diagnosis_violations = detect_missing_diagnosis(list(ctx.claims))
    drug_violations = detect_missing_drug_barcode(list(ctx.claims), ctx.drug_lines)
    lab_violations = detect_unreported_lab_result(
        list(ctx.claims),
        list(ctx.procedure_lines),
    )
    material_violations = detect_material_identity_errors(
        list(ctx.claims),
        ctx.material_lines,
    )
    legacy_violations = (
        *icu_violations,
        *diagnosis_violations,
        *drug_violations,
        *lab_violations,
        *material_violations,
    )

    findings: dict[str, RuleFinding] = {}
    for violation in legacy_violations:
        rule_id = str(violation["rule_id"])
        claim_id = str(violation["claim_id"])
        if evaluation_status.get((claim_id, rule_id)) != "evaluated":
            continue
        if (
            rule_id == DIAGNOSIS_RULE_ID
            and normalized_primary_diagnosis.get(claim_id)
        ):
            continue
        finding = _normalize_finding(patient_id, violation)
        findings.setdefault(finding.finding_id, finding)

    return RuleEvaluationBatch(
        findings=tuple(findings[key] for key in sorted(findings)),
        evaluations=tuple(evaluations),
        legacy_violations=tuple(legacy_violations),
    )
