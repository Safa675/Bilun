"""Response schemas for /api/* endpoints.

One file for the whole BILUN domain (7 route submodules, 15 endpoints).
Kept permissive (``extra="allow"``) — many endpoints serve pre-computed
canonical-cache payloads whose shape evolves with the analytics build,
and several pricing endpoints pass through gazette-derived dicts.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from typing import Literal
from typing import Any

from src.bilun.domain.billing.drug_indication_findings import (
    normalize_drug_indication_payload,
)

from pydantic import BaseModel, ConfigDict, Field, model_validator

ExactnessStatus = Literal[
    "exact",
    "unknown_date",
    "missing_exact_inputs",
    "partial_exact",
    "not_applicable",
]
BILUNDataSourceMode = Literal["synthetic_demo", "real_claims", "unavailable"]

_STATUSES_REQUIRING_INPUTS = {
    "unknown_date",
    "missing_exact_inputs",
    "partial_exact",
}
_MISSING_EXACTNESS_METADATA_REASON = (
    "Exactness metadata was not provided by the bilun payload."
)


def _default_missing_exactness_inputs() -> list[str]:
    return ["exactness_status"]


class BILUNDataSourceMetadata(BaseModel):
    """Data-source provenance for BILUN claim and clinical inputs."""

    mode: BILUNDataSourceMode
    label: str
    claim_source: str | None = None
    clinical_source: str | None = None
    is_synthetic: bool | None
    notice: str
    unavailable_reason: str | None = None
    required_inputs_missing: list[str] = Field(default_factory=list)
    error_type: str | None = None

    model_config = ConfigDict(extra="allow")


def default_bilun_data_source_metadata() -> BILUNDataSourceMetadata:
    """Default missing provenance to explicit unavailable, never real."""

    from src.bilun.domain.claims.provenance import unavailable_bilun_data_source_metadata

    return BILUNDataSourceMetadata.model_validate(
        unavailable_bilun_data_source_metadata()
    )


def _ensure_required_inputs_for_status(
    *,
    status: str,
    required_inputs_missing: list[str],
    status_field: str,
) -> None:
    if status in _STATUSES_REQUIRING_INPUTS and not required_inputs_missing:
        raise ValueError(
            f"required_inputs_missing must be non-empty when {status_field} "
            f"is {status!r}"
        )


# ── Generic envelope for cache-derived endpoints ────────────────────────────


class BilunCachePayloadResponse(BaseModel):
    """Generic permissive envelope for endpoints that surface raw
    canonical-cache payloads (optimization-summary, revenue-recovery).
    The cache shape varies per analytics build.
    """

    data_source: BILUNDataSourceMetadata = Field(
        default_factory=default_bilun_data_source_metadata
    )

    model_config = ConfigDict(extra="allow")


# ── validation.py ───────────────────────────────────────────────────────────


class MaterialBundlingCoverageScope(BaseModel):
    prose_rule_id: str
    prose_section_prefixes: list[str]
    prose_engine_status: str
    prose_coverage_tier: str | None = None
    prose_rules_implemented: int | None = None
    prose_effective_date: str | None = None
    implemented_annexes: list[str]
    ek3b1_row_count: int
    ek3b2_row_count: int
    p2_plan_path: str


class ValidateClaimResponse(BaseModel):
    claim_id: str
    coverage_scope: MaterialBundlingCoverageScope | dict[str, Any] | None = None
    specialty_coverage_scope: dict[str, Any] | None = None
    is_valid: bool
    total_claim_amount: float
    total_savings_try: float
    total_risk_try: float
    n_bundling_violations: int
    n_exclusion_violations: int
    validation_time_ms: float | None = None
    summary: Any  # rule_engine returns either a one-liner string or a dict
    violations: list[dict[str, Any]]
    material_lines: list[dict[str, Any]]

    model_config = ConfigDict(extra="allow")


class BundledConsumablesResponse(BaseModel):
    coverage_scope: MaterialBundlingCoverageScope | dict[str, Any] | None = None
    specialty_coverage_scope: dict[str, Any] | None = None
    bundled_consumables: dict[str, Any]
    exclusion_categories: dict[str, Any]

    model_config = ConfigDict(extra="allow")


# ── pricing.py ──────────────────────────────────────────────────────────────


class ProcedureInfoResponse(BaseModel):
    match_type: str
    entry: dict[str, Any] | None = None
    candidates: list[dict[str, Any]]

    model_config = ConfigDict(extra="allow")


class MaterialPricingResponse(BaseModel):
    query: str
    n_matches: int
    materials: list[dict[str, Any]]
    truncated: bool

    model_config = ConfigDict(extra="allow")


class VisitPricingResponse(BaseModel):
    """Pass-through of get_ek2a_visit_prices() output — opaque."""

    model_config = ConfigDict(extra="allow")


class PriceHistoryResponse(BaseModel):
    code: str
    name: str
    history: list[dict[str, Any]]

    model_config = ConfigDict(extra="allow")


class LabPricesResponse(BaseModel):
    tests: list[dict[str, Any]]
    total: int

    model_config = ConfigDict(extra="allow")


# ── alerts.py ───────────────────────────────────────────────────────────────


class PatientAlertsResponse(BaseModel):
    patients: list[dict[str, Any]]
    summary: dict[str, Any]
    pagination: dict[str, Any]
    query: dict[str, Any]
    data_source: BILUNDataSourceMetadata = Field(
        default_factory=default_bilun_data_source_metadata
    )

    model_config = ConfigDict(extra="allow")


class BillingExactnessResponse(BaseModel):
    exactness_status: ExactnessStatus = "missing_exact_inputs"
    unavailable_reason: str | None = None
    required_inputs_missing: list[str] = Field(default_factory=list)

    model_config = ConfigDict(extra="allow")

    @model_validator(mode="after")
    def _validate_exactness_required_inputs(self) -> BillingExactnessResponse:
        if (
            self.exactness_status in _STATUSES_REQUIRING_INPUTS
            and not self.required_inputs_missing
        ):
            if self.exactness_status == "partial_exact" and self.unavailable_reason:
                return self
            self.required_inputs_missing = _default_missing_exactness_inputs()
            self.unavailable_reason = (
                self.unavailable_reason or _MISSING_EXACTNESS_METADATA_REASON
            )
            return self
        _ensure_required_inputs_for_status(
            status=self.exactness_status,
            required_inputs_missing=self.required_inputs_missing,
            status_field="exactness_status",
        )
        return self


class LabOptimizationResponse(BillingExactnessResponse):
    normative_cost_try: float = 0.0
    hemogram_bundling_savings: float = 0.0
    session_fraction_savings: float = 0.0
    flagged_tests: list[dict[str, Any]] = Field(default_factory=list)


class CopayOptimizationResponse(BillingExactnessResponse):
    is_exempt: bool = False
    exemption_disease: str = ""
    exemption_range: str = ""
    exemption_sources: list[dict[str, Any]] = Field(default_factory=list)
    categories_not_evaluated: list[dict[str, Any]] = Field(default_factory=list)
    primary_exemption_category: str | None = None
    copay_primary_outcome: str = "none"
    savings_beneficiary: str = "patient_and_sgk"
    gap_kind: str = "exemption_correction"
    visit_copay_savings_try: float = 0.0
    rx_copay_savings_try: float = 0.0
    total_copay_savings_try: float = 0.0
    patient_copay_waived_total_try: float = 0.0
    patient_copay_try: float = 0.0
    ilave_ucret_total_try: float = 0.0
    line_decomposition_status: str = "missing_inputs"
    rate_corrections: list[dict[str, Any]] = Field(default_factory=list)


class BillingStrategyResponse(BillingExactnessResponse):
    recommendations: list[dict[str, Any]] = Field(default_factory=list)
    uplift_savings_try: float = 0.0
    optional_override_uplift_try: float = 0.0


class SessionPricingUpliftResponse(BillingExactnessResponse):
    opportunities: list[dict[str, Any]] = Field(default_factory=list)
    total_uplift_try: float = 0.0
    confirmed_uplift_try: float = 0.0
    review_uplift_try: float = 0.0
    review_opportunity_count: int = 0


class DrgUpliftRecommendationResponse(BillingExactnessResponse):
    opportunities: list[dict[str, Any]] = Field(default_factory=list)
    total_uplift_try: float = 0.0
    confirmed_uplift_try: float = 0.0


class BloodComponentUpliftResponse(BillingExactnessResponse):
    opportunities: list[dict[str, Any]] = Field(default_factory=list)
    total_uplift_try: float = 0.0
    confirmed_uplift_try: float = 0.0


class MaterialUpliftResponse(BillingExactnessResponse):
    opportunities: list[dict[str, Any]] = Field(default_factory=list)
    total_uplift_try: float = 0.0
    confirmed_uplift_try: float = 0.0


class ProcedureAddonUpliftResponse(BillingExactnessResponse):
    opportunities: list[dict[str, Any]] = Field(default_factory=list)
    total_uplift_try: float = 0.0
    confirmed_uplift_try: float = 0.0


class CareSettingReviewResponse(BillingExactnessResponse):
    opportunities: list[dict[str, Any]] = Field(default_factory=list)
    total_uplift_try: float = 0.0
    confirmed_uplift_try: float = 0.0
    review_uplift_try: float = 0.0
    review_opportunity_count: int = 0


class ProcedureCaptureGapResponse(BillingExactnessResponse):
    opportunities: list[dict[str, Any]] = Field(default_factory=list)
    total_gap_try: float = 0.0
    confirmed_gap_try: float = 0.0


class DrgPackageAdequacyReviewResponse(BillingExactnessResponse):
    opportunities: list[dict[str, Any]] = Field(default_factory=list)
    total_uplift_try: float = 0.0
    confirmed_uplift_try: float = 0.0
    review_uplift_try: float = 0.0
    review_opportunity_count: int = 0


class MedulaRejectionPlaybookResponse(BillingExactnessResponse):
    entries: list[dict[str, Any]] = Field(default_factory=list)
    entry_count: int = 0
    rebill_permitted_count: int = 0


class ClaimSubmissionChecklistResponse(BillingExactnessResponse):
    items: list[dict[str, Any]] = Field(default_factory=list)
    item_count: int = 0
    error_count: int = 0


class MaterialPreCheckResponse(BillingExactnessResponse):
    pre_auth_required: list[dict[str, Any]] = Field(default_factory=list)
    miat_restricted: list[dict[str, Any]] = Field(default_factory=list)
    miat_interval_violations: list[dict[str, Any]] = Field(default_factory=list)
    bundled_separate_billing: list[dict[str, Any]] = Field(default_factory=list)
    prose_bundling_violations: list[dict[str, Any]] = Field(default_factory=list)
    specialty_prose_violations: list[dict[str, Any]] = Field(default_factory=list)
    specialty_coverage_scope: dict[str, Any] | None = None
    kdv_price_reviews: list[dict[str, Any]] = Field(default_factory=list)
    gazette_ceiling_by_specialty: dict[str, float] = Field(default_factory=dict)
    coverage_scope: MaterialBundlingCoverageScope | dict[str, Any] | None = None


class DrugIndicationRouteEvidenceResponse(BaseModel):
    rule_id: str = Field(...)
    sut_section: str | None = None
    icd10_codes: list[str] = Field(...)
    icd10_ranges: list[str] = Field(...)
    regulatory_summary_tr: str = Field(...)
    report_required: bool = Field(...)
    report_duration_months: int | None = Field(...)
    report_specialties: list[str] = Field(...)
    prescriber_specialties: list[str] = Field(...)
    indication_label_tr: str | None = None
    icd10_code_count: int = Field(...)
    icd10_codes_truncated: bool = Field(...)
    icd10_range_count: int = Field(...)
    icd10_ranges_truncated: bool = Field(...)

    model_config = ConfigDict(extra="allow")


class DrugIndicationFindingResponse(BaseModel):
    finding_id: str = Field(...)
    patient_id: str = Field(...)
    claim_id: str = Field(...)
    drug_claim_line_id: str = Field(...)
    drug_name: str = Field(...)
    drug_code: str | None = None
    finding_kind: str = Field(...)
    severity: str = Field(...)
    applicability_status: str = Field(...)
    evaluation_status: str = Field(...)
    observed_icd10_codes: list[str] = Field(...)
    matched_icd10_codes: list[str] = Field(...)
    unmatched_icd10_codes: list[str] = Field(...)
    eligible_routes: list[DrugIndicationRouteEvidenceResponse] = Field(...)
    selected_rule_id: str | None = Field(...)
    explanation_tr: str = Field(...)
    recommended_action_tr: str = Field(...)
    required_inputs: list[str] = Field(...)
    missing_inputs: list[str] = Field(...)
    eligible_route_count: int = 0
    eligible_routes_truncated: bool = False
    observed_icd10_count: int = 0
    observed_icd10_truncated: bool = False

    model_config = ConfigDict(extra="allow")


class DrugIndicationEvaluationResponse(BaseModel):
    patient_id: str = Field(...)
    claim_id: str | None = Field(...)
    drug_claim_line_id: str = Field(...)
    drug_name: str = Field(...)
    drug_code: str | None = None
    applicability_status: str = Field(...)
    evaluation_status: str = Field(...)
    observed_icd10_codes: list[str] = Field(...)
    matched_icd10_codes: list[str] = Field(...)
    unmatched_icd10_codes: list[str] = Field(...)
    eligible_routes: list[DrugIndicationRouteEvidenceResponse] = Field(...)
    selected_rule_id: str | None = None
    finding_id: str | None = None
    finding_kind: str | None = None
    required_inputs: list[str] = Field(...)
    missing_inputs: list[str] = Field(...)
    eligible_route_count: int = 0
    eligible_routes_truncated: bool = False
    observed_icd10_count: int = 0
    observed_icd10_truncated: bool = False

    model_config = ConfigDict(extra="allow")


class DrugIndicationReviewResponse(BillingExactnessResponse):
    violations: list[dict[str, Any]] = Field(default_factory=list)
    findings: list[DrugIndicationFindingResponse] = Field(default_factory=list)
    evaluations: list[DrugIndicationEvaluationResponse] = Field(default_factory=list)
    violation_count: int = 0
    error_count: int = 0
    coverage_scope: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def _normalize_legacy_cache_payload(cls, value: Any) -> Any:
        if isinstance(value, Mapping):
            return normalize_drug_indication_payload(value)
        return value


class BilunPatientOutcomeResponse(BaseModel):
    """BILUN patient outcome payload.

    Kept permissive so the analytics-cache BILUN overlay can evolve without
    coupling this route to IHP outcome fields.
    """

    patient_id: str
    data_source: BILUNDataSourceMetadata = Field(
        default_factory=default_bilun_data_source_metadata
    )

    model_config = ConfigDict(extra="allow")


# ── optimization.py ─────────────────────────────────────────────────────────


class PatientOptimizationResponse(BaseModel):
    patient_id: str
    n_diagnoses: int
    diagnoses: list[Any]
    icd10_chapters: list[str]
    copay_exemptions: dict[str, Any]
    surcharge_exposure: dict[str, Any]
    copay_rate_exposure: dict[str, Any]
    drg_unbundling: dict[str, Any]
    data_source: BILUNDataSourceMetadata = Field(
        default_factory=default_bilun_data_source_metadata
    )

    model_config = ConfigDict(extra="allow")


# ── billing.py ──────────────────────────────────────────────────────────────


class BillingReportResponse(BaseModel):
    """Per-patient billing action report — variable shape per algorithm
    family, stays permissive."""

    patient_id: str | None = None
    lab: LabOptimizationResponse = Field(default_factory=LabOptimizationResponse)
    copay: CopayOptimizationResponse = Field(default_factory=CopayOptimizationResponse)
    billing_strategy: BillingStrategyResponse = Field(
        default_factory=BillingStrategyResponse
    )
    session_uplift: SessionPricingUpliftResponse = Field(
        default_factory=SessionPricingUpliftResponse
    )
    drg_uplift: DrgUpliftRecommendationResponse = Field(
        default_factory=DrgUpliftRecommendationResponse
    )
    blood_uplift: BloodComponentUpliftResponse = Field(
        default_factory=BloodComponentUpliftResponse
    )
    material_uplift: MaterialUpliftResponse = Field(
        default_factory=MaterialUpliftResponse
    )
    care_setting_review: CareSettingReviewResponse = Field(
        default_factory=CareSettingReviewResponse
    )
    procedure_addon_uplift: ProcedureAddonUpliftResponse = Field(
        default_factory=ProcedureAddonUpliftResponse
    )
    procedure_capture_gap: ProcedureCaptureGapResponse = Field(
        default_factory=ProcedureCaptureGapResponse
    )
    drg_package_adequacy: DrgPackageAdequacyReviewResponse = Field(
        default_factory=DrgPackageAdequacyReviewResponse
    )
    medula_rejection_playbook: MedulaRejectionPlaybookResponse = Field(
        default_factory=MedulaRejectionPlaybookResponse
    )
    claim_submission_checklist: ClaimSubmissionChecklistResponse = Field(
        default_factory=ClaimSubmissionChecklistResponse
    )
    materials: MaterialPreCheckResponse = Field(default_factory=MaterialPreCheckResponse)
    drug_indication: DrugIndicationReviewResponse = Field(
        default_factory=DrugIndicationReviewResponse
    )
    medula_rejection_ingest_available: bool = False
    sgk_uplift_try: float = 0.0
    compliance_adjustment_try: float = 0.0
    audit_exposure_try: float = 0.0
    capture_gap_try: float = 0.0
    package_adequacy_review_try: float = 0.0
    medula_playbook_entry_count: int = 0
    claim_submission_checklist_count: int = 0
    drug_indication_violation_count: int = 0
    total_recoverable_try: float = 0.0
    recommended_actions: list[dict[str, Any]] = Field(default_factory=list)
    action_count: int = 0
    priority: str = "low"
    exactness_status: ExactnessStatus = "missing_exact_inputs"
    unavailable_reason: str | None = None
    required_inputs_missing: list[str] = Field(default_factory=list)
    data_source: BILUNDataSourceMetadata = Field(
        default_factory=default_bilun_data_source_metadata
    )

    model_config = ConfigDict(extra="allow")

    @model_validator(mode="after")
    def _validate_exactness_required_inputs(self) -> BillingReportResponse:
        self.drug_indication_violation_count = self.drug_indication.violation_count
        if (
            self.exactness_status in _STATUSES_REQUIRING_INPUTS
            and not self.required_inputs_missing
        ):
            self.required_inputs_missing = _default_missing_exactness_inputs()
            self.unavailable_reason = (
                self.unavailable_reason or _MISSING_EXACTNESS_METADATA_REASON
            )
            return self
        _ensure_required_inputs_for_status(
            status=self.exactness_status,
            required_inputs_missing=self.required_inputs_missing,
            status_field="exactness_status",
        )
        return self


class BILUNPatientsListResponse(BaseModel):
    """BILUN patient listing with cache data-source provenance."""

    patients: list[str]
    total: int
    patient_meta: list[dict[str, Any]]
    cache_mode: str
    data_source: BILUNDataSourceMetadata = Field(
        default_factory=default_bilun_data_source_metadata
    )

    model_config = ConfigDict(extra="allow")


class PatientSearchResponse(BaseModel):
    """Response for GET /api/patients/search — prefix-match results."""

    results: list[dict[str, Any]]
    total_matched: int

    model_config = ConfigDict(extra="allow")


# ── patients.py (claim selector) ────────────────────────────────────────────


class PatientClaimSummary(BaseModel):
    """Lightweight claim header shown in the patient claim selector."""

    claim_id: str
    episode_id: str
    claim_type: str
    admission_date: date | None
    discharge_date: date | None
    claim_start_date: date
    claim_end_date: date
    primary_icd10: str
    expected_total_billed_try: float
    expected_total_payable_try: float
    expected_denial_reason: str = ""
    scenario_tag: str = ""
    recoverable_try: float | None = None
    priority: str | None = None

    model_config = ConfigDict(extra="allow")


class ClaimProcedureLine(BaseModel):
    """One procedure line surfaced inside a claim detail panel."""

    procedure_line_id: str
    procedure_date: date
    procedure_code: str
    procedure_name: str
    procedure_category: str
    quantity: int
    unit_price_try: float
    billed_amount_try: float
    expected_payable_try: float
    is_package_included: bool
    package_code: str = ""
    denial_reason_expected: str = ""
    rule_trace_expected: str = ""

    model_config = ConfigDict(extra="allow")


class ClaimMaterialLine(BaseModel):
    """One material line surfaced inside a claim detail panel."""

    material_line_id: str
    material_date: date
    material_code: str
    material_name: str
    material_type: str
    specialty_category: str
    quantity: int
    unit_price_try: float
    billed_amount_try: float
    expected_payable_try: float
    is_bundled: bool
    requires_pre_auth: bool
    denial_reason_expected: str = ""
    rule_trace_expected: str = ""

    model_config = ConfigDict(extra="allow")


class ClaimDrugLine(BaseModel):
    """One drug line surfaced inside a claim detail panel."""

    drug_claim_line_id: str
    prescription_id: str
    drug_claim_date: date
    drug_name: str
    drug_code: str
    barkod: str
    equivalence_group: str
    quantity: int
    unit_price_try: float
    billed_amount_try: float
    expected_payable_try: float
    discount_tier_expected: float
    denial_reason_expected: str = ""
    rule_trace_expected: str = ""

    model_config = ConfigDict(extra="allow")


class PatientClaimDetailResponse(BaseModel):
    """Full claim snapshot for the patient billing detail panel."""

    claim_id: str
    patient_id: str
    episode_id: str
    claim_type: str
    facility_tier: str
    provider_type: str
    department: str
    admission_date: date | None
    discharge_date: date | None
    claim_start_date: date
    claim_end_date: date
    primary_icd10: str
    package_candidate: bool
    expected_total_billed_try: float
    expected_total_payable_try: float
    expected_denial_reason: str = ""
    scenario_tag: str = ""
    occupational_context: str = "none"
    procedures: list[ClaimProcedureLine]
    materials: list[ClaimMaterialLine]
    drugs: list[ClaimDrugLine]
    data_source: BILUNDataSourceMetadata = Field(
        default_factory=default_bilun_data_source_metadata
    )

    model_config = ConfigDict(extra="allow")


class PatientClaimsListResponse(BaseModel):
    """Response for GET /api/patients/{patient_id}/claims."""

    patient_id: str
    claims: list[PatientClaimSummary]
    total: int
    data_source: BILUNDataSourceMetadata = Field(
        default_factory=default_bilun_data_source_metadata
    )

    model_config = ConfigDict(extra="allow")


class DrugCatalogResponse(BaseModel):
    drugs: list[dict[str, Any]]
    total: int
    page: int
    total_pages: int

    model_config = ConfigDict(extra="allow")


class MaterialsBySpecialtyResponse(BaseModel):
    materials: list[dict[str, Any]]
    total: int
    truncated: bool
    specialties: list[dict[str, Any]]

    model_config = ConfigDict(extra="allow")


# ── rules.py (SUT rule database) ────────────────────────────────────────────

RuleCoverageStatus = Literal[
    "implemented",
    "partial",
    "missing",
    "needs_claim_lines",
    "non_algorithmic",
]

FactCheckVerdict = Literal[
    "COMPLIANT",
    "PARTIAL",
    "HEURISTIC",
    "NEEDS_CLAIM_LINES",
    "WRONG",
    "OUT_OF_SCOPE",
]

MedulaOverlap = Literal[
    "ADDITIVE",
    "PARTIAL_OVERLAP",
    "MEDULA_DUPLICATE",
    "NOT_APPLICABLE",
]


class RuleSources(BaseModel):
    """Regulatory provenance for a rule: SUT sections (§-prefixed) + EK annexes."""

    sut_sections: list[str] = Field(default_factory=list)
    annexes: list[str] = Field(default_factory=list)


class RuleCatalogEntry(BaseModel):
    """One rule in the catalog index."""

    rule_id: str
    rule_category: str
    rule_category_tr: str = ""
    coverage_status: RuleCoverageStatus
    description: str
    description_tr: str = ""
    sources: RuleSources
    keywords: list[str] = Field(default_factory=list)
    domain_modules: list[str] = Field(default_factory=list)
    matched_clause_count: int = 0
    has_clause_mapping: bool = False
    fact_check_verdict: FactCheckVerdict | None = None
    medula_overlap: MedulaOverlap | None = None
    fact_check_units: list[str] = Field(default_factory=list)
    fact_check_note: str | None = None

    model_config = ConfigDict(extra="allow")


class FactCheckVerdictCounts(BaseModel):
    COMPLIANT: int = 0
    PARTIAL: int = 0
    HEURISTIC: int = 0
    NEEDS_CLAIM_LINES: int = 0
    WRONG: int = 0
    OUT_OF_SCOPE: int = 0

    model_config = ConfigDict(extra="allow")


class FactCheckAuditUnitSummary(BaseModel):
    unit_id: str
    title: str
    verdict: FactCheckVerdict
    medula_overlap: MedulaOverlap
    linked_rule_ids: list[str] = Field(default_factory=list)
    note: str | None = None

    model_config = ConfigDict(extra="allow")


class FactCheckRollup(BaseModel):
    """June 2026 algorithm fact-check audit summary (28 units, program closed)."""

    audit_closed: str
    total_units: int
    by_verdict: FactCheckVerdictCounts
    units: list[FactCheckAuditUnitSummary] = Field(default_factory=list)

    model_config = ConfigDict(extra="allow")


class CoverageStatusCount(BaseModel):
    """One coverage status bucket and its count."""

    status: str
    count: int

    model_config = ConfigDict(extra="allow")


class TopGapCategory(BaseModel):
    """One rule category among algorithmic gaps and its frequency."""

    category: str
    count: int

    model_config = ConfigDict(extra="allow")


class ClauseCoverageSummary(BaseModel):
    """Pipeline-health summary for the extracted SUT clause corpus."""

    total_extracted: int = 0
    by_status: list[CoverageStatusCount] = Field(default_factory=list)
    algorithmic_gaps: int = 0
    algorithmic_gap_pct: float = 0.0
    top_gap_categories: list[TopGapCategory] = Field(default_factory=list)

    model_config = ConfigDict(extra="allow")


class ZeroClauseMatch(BaseModel):
    """A rule marked implemented/partial that has no mapped SUT clauses."""

    rule_id: str
    coverage_status: str
    rule_category: str = ""
    rule_category_tr: str = ""
    description_tr: str = ""

    model_config = ConfigDict(extra="allow")


class RegistryCoverageSummary(BaseModel):
    """Pipeline-health summary for the rule registry."""

    total_rules: int = 0
    by_status: list[CoverageStatusCount] = Field(default_factory=list)
    implemented_rules: int = 0
    partial_rules: int = 0
    missing_rules: int = 0
    needs_claim_lines_rules: int = 0
    non_algorithmic_rules: int = 0
    zero_clause_matches: list[ZeroClauseMatch] = Field(default_factory=list)
    rules_without_mapping: list[ZeroClauseMatch] = Field(default_factory=list)

    model_config = ConfigDict(extra="allow")


class CoverageSummaryMeta(BaseModel):
    """Staleness and availability metadata for the coverage summary."""

    generated_at: str | None = None
    artifacts_available: bool = False
    clauses_source_available: bool = False
    unavailable_reason: str | None = None

    model_config = ConfigDict(extra="allow")


class PartialEngineCoverage(BaseModel):
    """Honest partial-engine rollup (registry partial vs manifest-encoded clauses)."""

    rule_id: str
    registry_status: str = "partial"
    prose_engine_status: str = "partial"
    classified_clause_rows: int = 0
    encoded_clause_rows: int = 0
    algorithmic_gap_rows: int = 0
    unencoded_gap_rows: int = 0
    encoded_clause_pct: float = 0.0
    gap_pct_of_classified: float = 0.0
    prose_rules_on_disk: int = 0
    tier_b_rule_count: int = 0
    encode_tier_c_deferred_count: int = 0
    manifest_traced_clause_count: int | None = None
    corpus_export_rows: int | None = None
    kdv_pricing_clauses: int | None = None
    section_4_2_14_C_clause_total: int = Field(default=828, alias="section_4.2.14.C_clause_total")
    subsection_coverage: dict[str, dict[str, int | float]] = Field(default_factory=dict)
    honesty_note: str = ""

    model_config = ConfigDict(extra="allow", populate_by_name=True)


class PartialEnginesCoverage(BaseModel):
    """Per-engine honesty blocks keyed by rule_id."""

    drug_indication_prose: PartialEngineCoverage | None = None
    material_bundling_prose: PartialEngineCoverage | None = None
    specialty_materials_prose: PartialEngineCoverage | None = None
    payment_method_2_2: PartialEngineCoverage | None = None
    copay_general_1_8: PartialEngineCoverage | None = None

    model_config = ConfigDict(extra="allow")


class GapCompositionSummary(BaseModel):
    """Scope-closure footnote: drug partial vs admin non-algorithmic clauses."""

    total_algorithmic_gaps: int = 0
    drug_indication_gap_rows: int = 0
    drug_indication_gap_pct_of_gaps: float = 0.0
    optimizer_gaps_excluding_drug: int = 0
    non_algorithmic_clause_rows: int = 0
    footnote_en: str = ""
    footnote_tr: str = ""

    model_config = ConfigDict(extra="allow")


class CoverageSummary(BaseModel):
    """Live pipeline-health summary for the Rule Database expert surface."""

    clauses: ClauseCoverageSummary = Field(default_factory=ClauseCoverageSummary)
    registry: RegistryCoverageSummary = Field(default_factory=RegistryCoverageSummary)
    partial_engines: PartialEnginesCoverage = Field(default_factory=PartialEnginesCoverage)
    gap_composition: GapCompositionSummary = Field(default_factory=GapCompositionSummary)
    meta: CoverageSummaryMeta = Field(default_factory=CoverageSummaryMeta)

    model_config = ConfigDict(extra="allow")


class RuleCatalogResponse(BaseModel):
    """GET /api/rules — full rule index with coverage + sources."""

    rules: list[RuleCatalogEntry]
    total: int
    artifacts_available: bool
    fact_check: FactCheckRollup
    coverage_summary: CoverageSummary = Field(default_factory=CoverageSummary)

    model_config = ConfigDict(extra="allow")


class MatchedRuleRef(BaseModel):
    """A rule id resolved to its registry label (clause → rule cross-link)."""

    rule_id: str
    rule_category_tr: str | None = None


class RuleClause(BaseModel):
    """One extracted SUT clause mapped to a rule, with provenance.

    Track E: ``clause_key`` / ``clause_coordinate`` are the stable public cites.
    ``paragraph_index`` is an opaque row-identity token for UI list keys only.
    """

    clause_key: str | None = None
    paragraph_index: int | None = None
    section_id: str | None = None
    section_title: str | None = None
    section_path: str | None = None
    chapter: str | None = None
    clause_type: str | None = None
    clause_number: int | None = None
    clause_letter: str | None = None
    clause_coordinate: str | None = None
    is_heading: bool = False
    text_tr: str | None = None
    annex_refs: list[str] = Field(default_factory=list)
    procedure_codes: list[str] = Field(default_factory=list)
    percentages: list[float] = Field(default_factory=list)
    amendment_refs: list[str] = Field(default_factory=list)
    deontic_modality: str | None = None
    source_effective_date: str | None = None
    coverage_status: str | None = None
    primary_rule_id: str | None = None
    primary_rule_category: str | None = None
    matched_rule_ids: list[str] = Field(default_factory=list)
    matched_rules: list[MatchedRuleRef] = Field(default_factory=list)
    is_primary: bool = False
    match_score: int = 0
    has_algorithmic_gap: bool = False
    has_rule_encoding: bool | None = None

    model_config = ConfigDict(extra="allow")


class RuleDetailResponse(BaseModel):
    """GET /api/rules/{rule_id} — rule metadata + extracted-clause drill-down."""

    rule: RuleCatalogEntry
    clauses: list[RuleClause]
    clause_total: int
    page: int
    per_page: int
    total_pages: int
    artifacts_available: bool

    model_config = ConfigDict(extra="allow")


class SectionClausesResponse(BaseModel):
    """GET /api/rules/sections/clauses — in-force clauses for one section."""

    clauses: list[RuleClause]
    clause_total: int
    page: int
    per_page: int
    total_pages: int
    artifacts_available: bool

    model_config = ConfigDict(extra="allow")


class SectionRollupEntry(BaseModel):
    """One SUT section with coverage gap rollup."""

    section_id: str | None = None
    section_title: str | None = None
    clause_count: int = 0
    worst_coverage_status: str | None = None
    gap_clause_count: int = 0
    primary_categories: list[str] = Field(default_factory=list)

    model_config = ConfigDict(extra="allow")


class SectionRollupResponse(BaseModel):
    """GET /api/rules/sections — paginated SUT section coverage rollup."""

    sections: list[SectionRollupEntry] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    per_page: int = 50
    total_pages: int = 0
    artifacts_available: bool = False
    unavailable_reason: str | None = None

    model_config = ConfigDict(extra="allow")


class ProseInventoryEngine(BaseModel):
    """One prose rule engine manifest entry."""

    rule_set_id: str
    file_name: str
    effective_date: str | None = None
    rule_count: int | None = None
    sut_section_prefixes: list[str] = Field(default_factory=list)
    sut_anchors: list[str] = Field(default_factory=list)

    model_config = ConfigDict(extra="allow")


class ProseInventoryResponse(BaseModel):
    """GET /api/rules/prose-inventory — prose rule engine manifest."""

    engines: list[ProseInventoryEngine] = Field(default_factory=list)
    total: int = 0
    artifacts_available: bool = False
    unavailable_reason: str | None = None

    model_config = ConfigDict(extra="allow")


class GateBSourceCite(BaseModel):
    """One resolved ``gate_b_sources`` cite (coordinate-first)."""

    ref: str
    clause_key: str | None = None
    clause_coordinate: str | None = None
    text_snippet: str | None = None

    model_config = ConfigDict(extra="allow")


class ProseRuleSourcesResponse(BaseModel):
    """GET /api/rules/prose-rules/{rule_set_id}/{rule_id}."""

    rule_set_id: str
    rule_id: str
    sut_section: str | None = None
    gate_b_sources: list[GateBSourceCite] = Field(default_factory=list)

    model_config = ConfigDict(extra="allow")


class ProseRulesSourcesListResponse(BaseModel):
    """GET /api/rules/prose-rules/{rule_set_id}."""

    rule_set_id: str
    rules: list[ProseRuleSourcesResponse] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    per_page: int = 50
    total_pages: int = 0
    artifacts_available: bool = True

    model_config = ConfigDict(extra="allow")


class DeferralEntry(BaseModel):
    """One deferral_table row for coordinate-first review.

    ``clause_key`` is the stable public identity (coord#hash).
    ``clause_coordinate`` is the human-readable SUT cite when known.
    """

    clause_key: str | None = None
    clause_coordinate: str | None = None
    section_id: str | None = None
    status: str
    defer_themes: list[str] = Field(default_factory=list)
    defer_reason: str = ""
    text_snippet: str | None = None

    model_config = ConfigDict(extra="allow")


class DeferralListResponse(BaseModel):
    """GET /api/rules/deferrals."""

    deferrals: list[DeferralEntry] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    per_page: int = 50
    total_pages: int = 0
    artifacts_available: bool = False

    model_config = ConfigDict(extra="allow")


class MedulaRejectionQueueRow(BaseModel):
    """One row in the MEDULA rejection triage queue."""

    rejection_event_id: str
    patient_id: str
    claim_id: str
    episode_id: str
    medula_stage: str
    sonuc_kodu: str
    hata_mesaji: str
    related_procedure_code: str | None = None
    rejection_timestamp: str | None = None
    related_line_type: str = ""
    related_line_id: str = ""
    playbook_matched: bool
    playbook_key: str | None = None
    sut_anchor: str | None = None
    rebill_permitted: bool | None = None
    corrective_steps_tr: list[str] = Field(default_factory=list)

    model_config = ConfigDict(extra="allow")


class MedulaRejectionQueueResponse(BaseModel):
    """GET /api/medula-rejections/queue — cohort rejection triage queue."""

    ingest_available: bool
    rows: list[MedulaRejectionQueueRow] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    page_size: int = 50
    facets: dict[str, list[str]] = Field(default_factory=dict)
    stats: dict[str, int] = Field(default_factory=dict)

    model_config = ConfigDict(extra="allow")
