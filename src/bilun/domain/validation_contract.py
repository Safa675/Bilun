"""Strict unpriced validator contract shared by API and chatbot serialization."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .sut.runtime_coverage_schema import RuntimeCoverageResponse
from .sut.source_authority_schema import ClinicalSourceAuthorityEvidence


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


class ValidationClinicalCheck(_StrictContract):
    field: str = Field(min_length=1, max_length=240)
    status: Literal['pass', 'fail', 'unknown']


class ValidationClinicalRestriction(_StrictContract):
    source_authority: ClinicalSourceAuthorityEvidence | None = None
    runtime_coverage: RuntimeCoverageResponse | None = None
    constraint_set: str = Field(min_length=1, max_length=240)
    criterion_status: Literal['not_evaluated', 'unknown', 'criterion_clear', 'restriction_not_met']
    missing_inputs: list[str] = Field(default_factory=list, max_length=64)
    checks: list[ValidationClinicalCheck] = Field(default_factory=list, max_length=64)
    source_refs: list[str] = Field(default_factory=list, max_length=32)
    clinical_eligibility_complete: Literal[False] = False
    verification_status: Literal['ai_generated_pending_review'] = 'ai_generated_pending_review'
    checks_truncated: bool = False
    source_refs_truncated: bool = False


class ValidationAdvisory(_ValidationEvidence):
    source_authority: ClinicalSourceAuthorityEvidence | None = None
    missing_inputs: list[str] = Field(default_factory=list)
    disposition: Literal[
        "unavailable", "review_only", "information_only", "permission_or_instruction",
    ]
    source_status: Literal["authored_locator_unverified", "historical_match_unverified"]
    clinical_restrictions: list[ValidationClinicalRestriction] = Field(default_factory=list, max_length=8)
    clinical_eligibility_complete: Literal[False] | None = None
    selected_rule_id: str | None = None


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


class ValidationDrugRuntimeCoverage(_StrictContract):
    """Measured metadata for one actual request drug line, never a finding."""

    claim_id: str = Field(max_length=512)
    drug_claim_line_id: str = Field(min_length=1, max_length=512)
    selected_rule_id: str | None = Field(default=None, max_length=512)
    runtime_coverage: RuntimeCoverageResponse

    @model_validator(mode="after")
    def verify_identity(self):
        if self.claim_id != self.claim_id.strip() or self.drug_claim_line_id != self.drug_claim_line_id.strip():
            raise ValueError("Runtime line identities must be normalized")
        if self.selected_rule_id is not None and (not self.selected_rule_id or self.selected_rule_id != self.selected_rule_id.strip()):
            raise ValueError("Selected rule identity must be normalized")
        return self


class ValidateClaimV2Response(_StrictContract):
    drug_runtime_coverage: list[ValidationDrugRuntimeCoverage] | None = None
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
        contexts = [(row.claim_id, row.drug_claim_line_id) for row in self.drug_runtime_coverage or []]
        # The adapter emits a drug line only for a named material at this exact
        # submitted position. Bound export length to actual request scope rather
        # than an unrelated cap that would reject previously accepted requests.
        named_drug_line_ids = {
            f"DRUG-{self.claim_id}-{row.material_index + 1:03d}"
            for row in self.material_applicability if row.material_name.strip()
        }
        if (any(claim != self.claim_id or line not in named_drug_line_ids for claim, line in contexts)
                or len(contexts) != len(set(contexts))):
            raise ValueError("Runtime summaries must belong uniquely to actual request drug lines")
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
