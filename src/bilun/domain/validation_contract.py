"""Strict unpriced validator contract shared by API and chatbot serialization."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


ValidationDisposition = Literal[
    "not_matched", "missing_inputs", "unavailable", "review_only",
    "information_only", "permission_or_instruction", "unpriced_compliance",
]


class _StrictContract(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class _ValidationEvidence(_StrictContract):
    evidence_id: str = Field(min_length=1)
    rule: str = Field(min_length=1)
    rule_id: str | None = None
    material_name: str
    message: str
    reason: str | None = None


class ValidationFinding(_ValidationEvidence):
    disposition: Literal["unpriced_compliance"]
    source_status: Literal["primary_meaning_and_date_verified"]


class ValidationAdvisory(_ValidationEvidence):
    disposition: Literal[
        "unavailable", "review_only", "information_only", "permission_or_instruction",
    ]
    source_status: Literal["authored_locator_unverified", "historical_match_unverified"]


class ValidationAnnexAssessment(_StrictContract):
    """An annex match, never a reimbursement or payment decision."""

    matched: bool | None
    source_reason: str | None

    @model_validator(mode="after")
    def verify_unknown_reason(self):
        if self.matched is None and not self.source_reason:
            raise ValueError("Unresolved annex applicability requires a source reason")
        return self


class ValidationMaterialApplicability(_StrictContract):
    material_index: int = Field(ge=0)
    material_id: str = Field(min_length=1)
    material_name: str
    material_code: str | None
    ek3b1: ValidationAnnexAssessment
    ek3b2: ValidationAnnexAssessment


class ValidationCoverage(_StrictContract):
    evaluation_count: int = Field(ge=0)
    authored_rule_count: Literal[496]
    unresolved_count: int = Field(ge=0)
    disposition_counts: dict[ValidationDisposition, int]
    scope: Literal["submitted_request_facts_only"]

    @model_validator(mode="after")
    def verify_counts(self):
        counts = self.disposition_counts
        if any(value < 0 for value in counts.values()) or sum(counts.values()) != self.evaluation_count:
            raise ValueError("Disposition counts must reconcile to evaluation scope")
        if self.unresolved_count != counts.get("missing_inputs", 0) + counts.get("unavailable", 0):
            raise ValueError("Unresolved count must reconcile to missing/unavailable scope")
        return self


class ValidationProvenance(_StrictContract):
    identity_kind: Literal["request_scoped_not_verified_patient"]
    supplied_field_count: int = Field(ge=0)
    adapter_defaults_are_evidence: Literal[False]


class ValidateClaimV2Response(_StrictContract):
    contract_version: Literal[2]
    request_id: str
    claim_id: str
    validation_status: Literal[
        "violations_found", "review_required", "partially_evaluated",
        "no_violations_in_evaluated_scope",
    ]
    is_valid: bool | None
    violations: list[ValidationFinding]
    advisories: list[ValidationAdvisory]
    material_applicability: list[ValidationMaterialApplicability]
    coverage: ValidationCoverage
    provenance: ValidationProvenance
    summary: str
    validation_time_ms: float = Field(ge=0, allow_inf_nan=False)

    @model_validator(mode="after")
    def verify_status(self):
        if any(
            row.material_index != index
            or row.material_id != f"{self.request_id}:material:{index}"
            for index, row in enumerate(self.material_applicability)
        ):
            raise ValueError("Material applicability must retain request line identity")
        expected = (
            "violations_found" if self.violations else
            "review_required" if self.advisories else
            "partially_evaluated" if self.coverage.unresolved_count else
            "no_violations_in_evaluated_scope"
        )
        valid = False if self.violations else None if self.advisories or self.coverage.unresolved_count else True
        if self.validation_status != expected or self.is_valid is not valid:
            raise ValueError("Validation status must follow typed findings and unresolved scope")
        return self
