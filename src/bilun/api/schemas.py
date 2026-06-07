"""Response schemas for /api/* endpoints.

One file for the whole BILUN domain (7 route submodules, 15 endpoints).
Kept permissive (``extra="allow"``) — many endpoints serve pre-computed
canonical-cache payloads whose shape evolves with the analytics build,
and several pricing endpoints pass through gazette-derived dicts.
"""

from __future__ import annotations

from typing import Literal
from typing import Any

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
_MISSING_PRICING_METADATA_REASON = (
    "Pricing exactness metadata was not provided by the bilun payload."
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
    is_valid: bool
    total_claim_amount: float
    total_savings_try: float
    total_risk_try: float
    n_bundling_violations: int
    n_exclusion_violations: int
    validation_time_ms: float | None = None
    summary: Any  # rule_engine returns either a one-liner string or a dict
    violations: list[dict[str, Any]]
    material_estimates: list[dict[str, Any]]

    model_config = ConfigDict(extra="allow")


class BundledConsumablesResponse(BaseModel):
    coverage_scope: MaterialBundlingCoverageScope | dict[str, Any] | None = None
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


class CheckupPricingResponse(BaseModel):
    labs: list[dict[str, Any]] | dict[str, Any]
    procedures: list[dict[str, Any]]
    copayment: dict[str, Any]
    katsayi: Any

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


class ExpensiveAnalyticsState(BaseModel):
    state: Literal["ready", "missing", "skipped"] = "skipped"
    included: bool = False

    model_config = ConfigDict(extra="allow")


class DRGEpisodeResponse(BaseModel):
    episode_id: int | None = None
    primary_icd10: str = ""
    primary_icd10_chapter: str = ""
    description: str = ""
    los_days: float = 0.0
    lab_cost: float = 0.0
    visit_cost: float = 0.0
    rx_cost: float = 0.0
    procedure_cost: float = 0.0
    total_cost: float = 0.0
    drg_package_price: float | None = None
    ek2c_group: str = ""
    admission_date: str | None = None
    discharge_date: str | None = None
    pricing_status: ExactnessStatus
    pricing_date: str | None = None
    unavailable_reason: str | None = None
    required_inputs_missing: list[str] = Field(default_factory=list)

    model_config = ConfigDict(extra="allow")

    @model_validator(mode="after")
    def _validate_pricing_required_inputs(self) -> "DRGEpisodeResponse":
        _ensure_required_inputs_for_status(
            status=self.pricing_status,
            required_inputs_missing=self.required_inputs_missing,
            status_field="pricing_status",
        )
        return self


class DRGSummaryResponse(BaseModel):
    n_episodes: int = 0
    total_drg_cost: float = 0.0
    mean_episode_cost: float = 0.0
    most_expensive_drg: str = "N/A"
    dominant_icd10_chapter: str = "N/A"
    total_drg_package_price: float | None = None
    fully_priced: bool = True
    priced_episode_count: int = 0
    unknown_date_episode_count: int = 0
    pricing_status: ExactnessStatus
    unavailable_reason: str | None = None
    required_inputs_missing: list[str] = Field(default_factory=list)
    episodes: list[DRGEpisodeResponse] = Field(default_factory=list)

    model_config = ConfigDict(extra="allow")

    @model_validator(mode="after")
    def _validate_pricing_required_inputs(self) -> "DRGSummaryResponse":
        _ensure_required_inputs_for_status(
            status=self.pricing_status,
            required_inputs_missing=self.required_inputs_missing,
            status_field="pricing_status",
        )
        return self


class BillingExactnessResponse(BaseModel):
    exactness_status: ExactnessStatus = "missing_exact_inputs"
    unavailable_reason: str | None = None
    required_inputs_missing: list[str] = Field(default_factory=list)

    model_config = ConfigDict(extra="allow")

    @model_validator(mode="after")
    def _validate_exactness_required_inputs(self) -> "BillingExactnessResponse":
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


class LabOptimizationResponse(BillingExactnessResponse):
    normative_cost_try: float = 0.0
    hemogram_bundling_savings: float = 0.0
    flagged_tests: list[dict[str, Any]] = Field(default_factory=list)


class CopayOptimizationResponse(BillingExactnessResponse):
    is_exempt: bool = False
    exemption_disease: str = ""
    exemption_range: str = ""
    savings_beneficiary: str = "patient_and_sgk"
    gap_kind: str = "exemption_correction"
    visit_copay_savings_try: float = 0.0
    rx_copay_savings_try: float = 0.0
    total_copay_savings_try: float = 0.0
    patient_copay_waived_total_try: float = 0.0
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


class GazetteRepricingOpportunityResponse(BillingExactnessResponse):
    opportunities: list[dict[str, Any]] = Field(default_factory=list)
    total_repricing_try: float = 0.0
    confirmed_repricing_try: float = 0.0
    review_repricing_try: float = 0.0


class MedulaRejectionPlaybookResponse(BillingExactnessResponse):
    entries: list[dict[str, Any]] = Field(default_factory=list)
    entry_count: int = 0
    rebill_permitted_count: int = 0


class MaterialPreCheckResponse(BillingExactnessResponse):
    pre_auth_required: list[dict[str, Any]] = Field(default_factory=list)
    miat_restricted: list[dict[str, Any]] = Field(default_factory=list)
    miat_interval_violations: list[dict[str, Any]] = Field(default_factory=list)
    bundled_separate_billing: list[dict[str, Any]] = Field(default_factory=list)
    prose_bundling_violations: list[dict[str, Any]] = Field(default_factory=list)
    specialty_prose_violations: list[dict[str, Any]] = Field(default_factory=list)
    kdv_price_reviews: list[dict[str, Any]] = Field(default_factory=list)
    gazette_ceiling_by_specialty: dict[str, float] = Field(default_factory=dict)
    coverage_scope: MaterialBundlingCoverageScope | dict[str, Any] | None = None


class BilunPatientOutcomeResponse(BaseModel):
    """BILUN patient outcome payload.

    Kept permissive so the analytics-cache BILUN overlay can evolve without
    coupling this route to IHP outcome fields.
    """

    patient_id: str
    drg_summary: DRGSummaryResponse | None = None
    consistency_warnings: list[str] = Field(default_factory=list)
    expensive_analytics: ExpensiveAnalyticsState = Field(
        default_factory=ExpensiveAnalyticsState
    )
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
    gazette_repricing: GazetteRepricingOpportunityResponse = Field(
        default_factory=GazetteRepricingOpportunityResponse
    )
    medula_rejection_playbook: MedulaRejectionPlaybookResponse = Field(
        default_factory=MedulaRejectionPlaybookResponse
    )
    materials: MaterialPreCheckResponse = Field(default_factory=MaterialPreCheckResponse)
    sgk_uplift_try: float = 0.0
    compliance_adjustment_try: float = 0.0
    audit_exposure_try: float = 0.0
    capture_gap_try: float = 0.0
    package_adequacy_review_try: float = 0.0
    gazette_repricing_try: float = 0.0
    medula_playbook_entry_count: int = 0
    total_recoverable_try: float = 0.0
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
    def _validate_exactness_required_inputs(self) -> "BillingReportResponse":
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
