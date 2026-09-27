import type { SutMaterialBundlingCoverageScope } from "@/lib/api/sut";

export interface VisitPricingSpecialty {
  code: string;
  name: string;
  section: string;
  prices_try: Record<string, number>;
}

export type SUTDataSourceMode = "synthetic_demo" | "real_claims" | "unavailable";

export interface SUTDataSourceMetadata {
  mode: SUTDataSourceMode;
  label: string;
  claim_source?: string | null;
  clinical_source?: string | null;
  is_synthetic: boolean | null;
  notice: string;
  unavailable_reason?: string | null;
  required_inputs_missing?: string[];
  error_type?: string | null;
  [key: string]: unknown;
}

export interface SUTDataSourceCarrier {
  data_source?: SUTDataSourceMetadata | null;
  dataSource?: SUTDataSourceMetadata | null;
}

export interface VisitPricingResponse {
  specialties: VisitPricingSpecialty[];
}

export interface MaterialEntry {
  sut_code: string;
  material_name: string;
  name: string;
  description: string;
  price_try: number;
  category: string;
  source: string;
}

export interface MaterialsBySpecialtyResponse {
  materials: MaterialEntry[];
  total: number;
  truncated: boolean;
  specialties: Array<{ label: string; name: string }>;
}

export interface SutPatientOutcomeData extends SUTDataSourceCarrier {
  patient_id?: string;
  sut_claim_totals?: ExactnessState & {
    patient_id: string;
    total_billed_try: number | null;
    total_expected_payable_try: number | null;
    claim_count: number;
    procedure_line_count: number;
    material_line_count: number;
    drug_line_count: number;
    lab_billed_line_count: number;
    source?: string;
  };
  sut_claim_summary?: ExactnessState & {
    source?: string;
    claim_count: number;
    procedure_line_count: number;
    material_line_count: number;
    drug_line_count: number;
    diagnosis_count: number;
    claims: Array<{
      claim_id: string;
      episode_id: string;
      claim_type: string;
      department: string;
      admission_date: string | null;
      claim_start_date: string | null;
      claim_end_date: string | null;
      primary_icd10: string;
      package_candidate: boolean;
      total_billed_try: number;
    }>;
    top_procedures: Array<{
      procedure_line_id: string;
      claim_id: string;
      episode_id: string;
      procedure_date: string | null;
      procedure_code: string;
      procedure_name: string;
      procedure_category: string;
      billed_amount_try: number | null;
      expected_payable_try: number | null;
      surcharge_applicable: boolean;
      copay_rate_applicable: boolean;
    }>;
    drug_claims: Array<{
      drug_claim_line_id: string;
      claim_id: string;
      drug_claim_date: string | null;
      drug_name: string;
      drug_code: string;
      billed_amount_try: number | null;
      expected_payable_try: number | null;
    }>;
    material_claims: Array<{
      material_line_id: string;
      claim_id: string;
      material_date: string | null;
      material_code: string;
      material_name: string;
      billed_amount_try: number | null;
      expected_payable_try: number | null;
    }>;
  };
}

export interface TopDisease {
  disease: string;
  count: number;
}

export interface TemporalPriceDelta {
  code: string;
  name: string;
  old_price: number;
  new_price: number;
  delta_pct: number;
  old_date: string;
  new_date: string;
}

export interface TemporalAnnexStats {
  n_codes: number;
  n_effective_dates: number;
  date_range: string[];
  effective_dates: string[];
  n_codes_with_changes: number;
  price_change_rate: number;
  mean_price_delta_pct: number;
  top_increases: TemporalPriceDelta[];
  top_decreases: TemporalPriceDelta[];
}

export interface TemporalPriceValidation {
  ek2b: TemporalAnnexStats;
  ek2c: TemporalAnnexStats;
  methodology: string;
}

export type ExactnessStatus =
  | "exact"
  | "unknown_date"
  | "missing_exact_inputs"
  | "partial_exact"
  | "not_applicable";

export interface ExactnessState {
  exactness_status?: ExactnessStatus;
  unavailable_reason?: string | null;
  required_inputs_missing?: string[];
}

export interface ChapterRiskSummary {
  chapter: string;
  n_patients: number;
  total_savings: number;
}

export interface DrgUnbundlingSummary extends ExactnessState {
  n_patients_checked: number | null;
  n_patients_with_risk: number | null;
  risk_rate: number | null;
  total_potential_savings: number | null;
  total_sourced_savings?: number | null;
  top_risky_chapters: ChapterRiskSummary[];
  methodology: string;
}

export interface ExemptionCategoryCount {
  category: string;
  count: number;
}

export interface ExemptionSource {
  category: string;
  rule_source?: string;
  evidence?: Record<string, unknown>;
}

export interface ExemptionCategoryGap {
  category: string;
  required_inputs_missing: string[];
}

export interface OptimizationSummary extends SUTDataSourceCarrier {
  copay_exemptions: {
    n_exempt_patients: number;
    n_exempt_ek1a_patients?: number;
    n_exempt_status_only_patients?: number;
    n_exempt_ek1a_and_status_patients?: number;
    n_total_patients: number;
    exemption_rate: number;
    exemption_by_category?: ExemptionCategoryCount[];
    top_diseases: TopDisease[];
    methodology: string;
    rule_source?: string;
    /** Bill-scoped exemption counts (present when claim data is available). */
    n_total_bills?: number;
    n_exempt_bills?: number;
    n_exempt_ek1a_bills?: number;
    n_exempt_status_only_bills?: number;
    n_exempt_ek1a_and_status_bills?: number;
    exemption_rate_bills?: number;
    exemption_by_category_bills?: ExemptionCategoryCount[];
  };
  surcharge_exposure: ExactnessState & {
    n_total_ek2g: number | null;
    mean_applicable_per_patient: number | null;
    max_applicable: number | null;
    cohort_coverage_rate: number | null;
    methodology: string;
  };
  copay_rate_exposure: ExactnessState & {
    n_total_ek2c1: number | null;
    mean_applicable_per_patient: number | null;
    cohort_mean_rate: number | null;
    rate_distribution: Record<string, number>;
    methodology: string;
  };
  temporal_price_validation?: TemporalPriceValidation;
  drg_unbundling?: DrgUnbundlingSummary;
  drug_discount_validation?: ExactnessState & {
    n_total_patients: number;
    n_drug_lines: number | null;
    n_evaluable_lines?: number | null;
    n_discounted_lines: number | null;
    n_violations: number | null;
    total_billed_try: number | null;
    total_expected_payable_try: number | null;
    total_expected_discount_try: number | null;
    mean_expected_discount_pct: number | null;
    top_violations: Record<string, unknown>[];
    methodology: string;
    rule_source?: string;
  };
}

export interface QualifyingDiagnosis {
  icd10: string;
  disease: string;
  range: string;
}

export interface CopayExemptionResult {
  exempt: boolean;
  n_qualifying: number;
  qualifying_diagnoses: QualifyingDiagnosis[];
  exemption_sources?: ExemptionSource[];
  categories_not_evaluated?: ExemptionCategoryGap[];
  primary_exemption_category?: string | null;
  action?: string | null;
}

export interface SurchargeRule {
  code: string;
  name: string;
  procedure_date?: string;
  rule_trace?: string;
  matched_chapters: string[];
}

export interface SurchargeExposureResult extends ExactnessState {
  n_applicable_procedures: number | null;
  n_total_ek2g: number | null;
  exposure_rate: number | null;
  applicable_rules: SurchargeRule[];
}

export interface CopayRateProcedure {
  code: string;
  name: string;
  rate_pct: number;
  mandated_rate_pct?: number | null;
  procedure_date?: string;
  rule_trace?: string;
  matched_chapters: string[];
}

export interface CopayRateExposureResult extends ExactnessState {
  n_applicable_procedures: number | null;
  n_total_ek2c1: number | null;
  procedures_with_rates: CopayRateProcedure[];
  mean_rate: number | null;
  rate_distribution: Record<string, number>;
}

export interface ChapterUnbundlingDetail {
  chapter: string;
  ek2c_group: string;
  package_floor_price: number;
  n_individual_procedures: number;
  individual_procedures_total: number;
  unbundling_risk: boolean;
  savings_if_packaged: number;
}

export interface PatientDrgUnbundling extends ExactnessState {
  has_unbundling_risk: boolean | null;
  n_chapters_analyzed: number | null;
  chapter_analysis: ChapterUnbundlingDetail[];
  total_potential_savings: number | null;
  total_sourced_savings?: number | null;
  patient_icd10_chapters?: string[];
}

export interface PatientOptimization extends SUTDataSourceCarrier {
  patient_id: string;
  n_diagnoses: number;
  diagnoses: string[];
  icd10_chapters: string[];
  copay_exemptions: CopayExemptionResult;
  surcharge_exposure: SurchargeExposureResult;
  copay_rate_exposure: CopayRateExposureResult;
  drg_unbundling?: PatientDrgUnbundling;
  /** Present when the payload is scoped to a single bill. */
  claim_id?: string;
  scope?: "bill";
}

export interface PatientAlertCopay {
  exempt: boolean;
  n_qualifying: number;
  qualifying_diagnoses: QualifyingDiagnosis[];
  exemption_sources?: ExemptionSource[];
  categories_not_evaluated?: ExemptionCategoryGap[];
  primary_exemption_category?: string | null;
  action: string | null;
}

export interface PatientAlertSurcharge extends ExactnessState {
  n_applicable: number | null;
  exposure_rate: number | null;
  top_rules: SurchargeRule[];
  action: string | null;
}

export interface PatientAlertCopayRate extends ExactnessState {
  n_applicable: number | null;
  n_violations?: number | null;
  mean_rate: number | null;
  top_procedures: CopayRateProcedure[];
  action: string | null;
}

export interface PatientAlertRow {
  patient_id: string;
  n_diagnoses: number;
  icd10_chapters: string[];
  copay_exemption: PatientAlertCopay;
  surcharge_exposure: PatientAlertSurcharge;
  copay_rate_exposure: PatientAlertCopayRate;
}

export type PatientAlertsCategory = "exemptions" | "surcharge" | "copay_rates";
export type PatientAlertsStatus = "all" | "exempt" | "not_exempt" | "flagged" | "clear";

export interface PatientAlertsSummary {
  n_total_patients: number;
  n_exempt_patients: number;
  exemption_rate: number;
  n_patients_with_surcharge_flags: number | null;
  n_patients_with_copay_rate_flags: number | null;
  total_surcharge_flags: number | null;
  total_copay_rate_flags: number | null;
  n_patients_with_surcharge_unavailable?: number | null;
  n_patients_with_copay_rate_unavailable?: number | null;
  surcharge_exactness_status?: ExactnessStatus;
  surcharge_unavailable_reason?: string | null;
  surcharge_required_inputs_missing?: string[];
  copay_rate_exactness_status?: ExactnessStatus;
  copay_rate_unavailable_reason?: string | null;
  copay_rate_required_inputs_missing?: string[];
}

export interface PatientAlertsPagination {
  total_matching: number;
  limit: number;
  offset: number;
  has_more: boolean;
}

export interface PatientAlertsQuery {
  category: PatientAlertsCategory;
  status: PatientAlertsStatus;
  search: string;
}

export interface PatientAlertsRequestParams {
  category?: PatientAlertsCategory;
  status?: PatientAlertsStatus;
  search?: string;
  limit?: number;
  offset?: number;
}

export interface PatientAlertsResponse extends SUTDataSourceCarrier {
  patients: PatientAlertRow[];
  summary: PatientAlertsSummary;
  pagination: PatientAlertsPagination;
  query: PatientAlertsQuery;
}

export type ComplianceIndexSurface =
  | "materials"
  | "drug_indication"
  | "lab"
  | "payment_methods"
  | "claim_compliance";

export type ClaimComplianceEvaluationStatus =
  | "evaluated"
  | "missing_inputs"
  | "unavailable";

export interface ClaimComplianceMoneyFields {
  amount_try?: number | null;
  billed_try?: number | null;
  payable_try?: number | null;
  savings_try?: number | null;
  recoverable_uplift_try?: number | null;
  compliance_savings_try?: number | null;
  risk_amount_try?: number | null;
  audit_exposure_try?: number | null;
}

export interface ClaimComplianceEvaluation {
  patient_id: string;
  claim_id: string | null;
  rule_id: string;
  status: ClaimComplianceEvaluationStatus;
  evaluation_status?: ClaimComplianceEvaluationStatus | null;
  required_inputs?: string[] | null;
  missing_inputs: string[];
}

/**
 * Serialized canonical claim-compliance finding.
 *
 * `finding_id` is optional only for old patient payloads. New payloads carry
 * the domain-generated id and the equal `action_id` compatibility alias;
 * consumers must prefer `finding_id` and use `action_id` only as a fallback.
 */
export interface ClaimComplianceFinding extends ClaimComplianceMoneyFields {
  finding_id?: string | null;
  action_id?: string | null;
  patient_id: string;
  claim_id: string | null;
  line_kind?: string | null;
  line_id?: string | null;
  rule_id: string;
  kind?: string | null;
  status?: string | null;
  finding_type?: "compliance";
  detail?: string | null;
  severity?: string | null;
  sut_section_id?: string | null;
  regulatory_source?: unknown;
  source_engine?: string | null;
  evaluation_status?: ClaimComplianceEvaluationStatus | null;
  applicability_status?: string | null;
  required_inputs?: string[] | null;
  missing_inputs?: string[] | null;
  surface?: "claim_compliance";
  source_surface?: string | null;
  procedure_line_id?: string | null;
  procedure_code?: string | null;
  procedure_name?: string | null;
  lab_billing_status?: string | null;
  drug_claim_line_id?: string | null;
  drug_code?: string | null;
  drug_name?: string | null;
  observed_icd10_codes?: string[] | null;
  matched_icd10_codes?: string[] | null;
  unmatched_icd10_codes?: string[] | null;
  eligible_routes?: DrugIndicationRouteEvidence[] | null;
  recommended_action_tr?: string | null;
  eligible_route_count?: number | null;
  eligible_routes_truncated?: boolean | null;
  observed_icd10_count?: number | null;
  observed_icd10_truncated?: boolean | null;
  material_line_id?: string | null;
  material_code?: string | null;
  material_name?: string | null;
  barcode_sut_mismatch?: boolean | null;
  titubb_uts_barcode_documentation_missing?: boolean | null;
}

export interface ClaimCompliance {
  findings: ClaimComplianceFinding[];
  evaluations: ClaimComplianceEvaluation[];
}

export interface ComplianceIndexRow extends ClaimComplianceMoneyFields {
  patient_id: string;
  claim_id?: string | null;
  surface: ComplianceIndexSurface;
  source_surface?: string | null;
  finding_id?: string | null;
  action_id?: string | null;
  rule_id?: string | null;
  line_kind?: string | null;
  line_id?: string | null;
  procedure_line_id?: string | null;
  kind?: string | null;
  status?: string | null;
  finding_type?: "compliance";
  detail?: string | null;
  severity?: string | null;
  regulatory_source?: unknown;
  source_engine?: string | null;
  evaluation_status?: ClaimComplianceEvaluationStatus | null;
  required_inputs?: string[] | null;
  missing_inputs?: string[] | null;
  procedure_code?: string | null;
  procedure_name?: string | null;
  lab_billing_status?: string | null;
  drug_claim_line_id?: string | null;
  material_code?: string | null;
  material_name?: string | null;
  drug_code?: string | null;
  drug_name?: string | null;
  material_line_id?: string | null;
  barcode_sut_mismatch?: boolean | null;
  titubb_uts_barcode_documentation_missing?: boolean | null;
  sut_section_id?: string | null;
}

export interface ComplianceIndexSurfaceSummary {
  n: number;
  billed_try: number | null;
  n_patients?: number;
}

export interface ClaimComplianceCohortSummary {
  counts: {
    evaluated: number;
    missing_inputs: number;
    unavailable: number;
  };
  non_evaluated_total: number;
  details: ClaimComplianceEvaluation[];
  details_truncated: boolean;
}

export interface ComplianceIndexPagination {
  total_matching: number;
  limit: number;
  offset: number;
  has_more: boolean;
}

export interface ComplianceIndexResponse extends SUTDataSourceCarrier {
  artifacts_available: boolean;
  n_patients: number | null;
  n_findings: number | null;
  n_patients_with_findings: number | null;
  billed_at_risk_try: number | null;
  by_surface: Record<string, ComplianceIndexSurfaceSummary>;
  rows: ComplianceIndexRow[];
  pagination?: ComplianceIndexPagination;
  claim_compliance?: ClaimComplianceCohortSummary | null;
}

export interface LabOptimization extends ExactnessState {
  normative_cost_try: number;
  hemogram_bundling_savings: number;
  session_fraction_savings?: number;
  flagged_tests: Array<{
    test_name: string;
    sut_code: string;
    gazette_price: number;
    flag_type: string;
    savings_try: number | null;
    detail?: string;
  }>;
}

/**
 * Structured SUT clause cite carried by billing findings (Track E identity).
 * `clause_key` (coord#hash) is the stable public cite and may be "" when the
 * coordinate could not be resolved; `clause_coordinate` remains the cite.
 * Display text is fetched from GET /api/rules/clauses/{clause_key}, never
 * duplicated here.
 */
export interface SutClauseReference {
  clause_key: string;
  clause_coordinate: string;
  source_type?:
    | "sut_clause"
    | "el_kitabi"
    | "algoritma_rehberi"
    | "kanun"
    | "rehber";
  rule_type?: string;
  annex?: string;
  statutory_law?: string;
}

export interface CopayOptimization extends ExactnessState {
  rule_source?: string;
  is_exempt: boolean;
  exemption_disease: string;
  exemption_range: string;
  exemption_sources?: ExemptionSource[];
  categories_not_evaluated?: ExemptionCategoryGap[];
  primary_exemption_category?: string | null;
  copay_primary_outcome?: "exempt" | "partial_exempt" | "rate_capped" | "none";
  /** Exemption gap benefits patient katılım waiver and SGK payable correction. */
  savings_beneficiary?: "patient_and_sgk";
  gap_kind?: "exemption_correction";
  visit_copay_savings_try: number;
  rx_copay_savings_try: number;
  /** Legacy: procedure/visit copay waived only (excludes Rx). */
  total_copay_savings_try: number;
  /** Visit + Rx patient copay that exemption may waive. */
  patient_copay_waived_total_try?: number;
  /** Total katılım payı on claim lines (before waiver). */
  patient_copay_try?: number;
  /** Total ilave ücret (§1.9) — informational, never waived. */
  ilave_ucret_total_try?: number;
  line_decomposition_status?: "exact" | "copay_only" | "missing_inputs";
  rx_copay_savings_by_ground?: Record<string, number>;
  rate_corrections: Array<{
    procedure?: string;
    gazette_rate?: number;
    correction_try?: number;
    code?: string;
    name?: string;
    billed_try?: number;
    payable_try?: number;
    copay_component_try?: number;
    ilave_ucret_try?: number;
    exemption_ground?: string;
    sut_section?: string;
    annex?: string;
    detail?: string;
    /** Waiver clause cite for this row (Track E). */
    clause_ref?: SutClauseReference | null;
    /** Backend-decided surcharge outcome; absent on informational rows. */
    ilave_ucret_status?:
      | "drug_prohibited"
      | "cancer_exempt"
      | "emergency_exempt"
      | "applicable"
      | "none";
    /** §1.9 surcharge clause cite backing ilave_ucret_status. */
    ilave_clause_ref?: SutClauseReference | null;
  }>;
}

export interface BillingStrategyRecommendation extends ExactnessState {
  optional_override_uplift_try?: number;
  recommendations: Array<{
    chapter?: string;
    chapter_description?: string;
    ek2c_group?: string;
    strategy?: "package" | "itemized";
    package_price?: number;
    itemized_estimate?: number;
    confidence?: "high" | "medium" | "low";
    claim_id?: string;
    procedure_code?: string;
    procedure_name?: string;
    recommendation?: "package" | "itemized" | "review_package_eligibility";
    recommendation_kind?: "mandatory_compliance" | "optional_override";
    payment_method_kind?:
      | "DRG_MANDATORY"
      | "DRG_OVERRIDABLE"
      | "ITEMIZED"
      | "NOT_IN_SUT";
    sut_section_id?: string;
    sut_section?: string;
    rule_id?: string;
    mandated_method?: string;
    package_total_try?: number;
    itemized_total_try?: number;
    detail?: string;
    savings_try?: number | null;
    savings_basis?: "heuristic" | "optional_override" | "claim_line";
    current_billing?: "package" | "itemized";
    catalog_as_of_date?: string | null;
    package_price_methodology?: string;
    type?: "compliance_violation" | "informational";
    billed_as_package?: boolean;
    recommended_package_code?: string | null;
    recoverable_uplift_try?: number | null;
    included_in_sgk_total?: boolean | null;
    /** Structured message contract (§2.2 surface). */
    message_code?: string;
    message_params?: Record<string, unknown>;
  }>;
}

export interface MaterialPreCheck extends ExactnessState {
  pre_auth_required: Array<{
    sut_code: string;
    material_name: string;
    price_try: number;
    note: string;
  }>;
  miat_restricted: Array<{
    sut_code: string;
    material_name: string;
    miat_period: string;
    price_try: number;
    note: string;
  }>;
  miat_interval_violations?: Array<{
    sut_code: string;
    material_name: string;
    miat_period: string;
    last_use_date?: string;
    days_since_last_use?: number;
    minimum_interval_days?: number;
    price_try: number;
    savings_try: number | null;
    note: string;
  }>;
  bundled_separate_billing?: Array<{
    sut_code: string;
    material_name: string;
    price_try: number;
    note: string;
  }>;
  prose_bundling_violations?: Array<{
    rule_id?: string;
    material_name?: string;
    material_code?: string;
    message?: string;
    severity?: string;
    risk_amount?: number;
  }>;
  specialty_prose_violations?: Array<{
    rule_id?: string;
    material_name?: string;
    material_code?: string;
    message?: string;
    severity?: string;
    risk_amount?: number;
    material_outcome?: string;
  }>;
  kdv_price_reviews?: Array<{
    sut_code?: string;
    material_name?: string;
    billed_try?: number;
    gazette_ex_vat_try?: number;
    gazette_ceiling_try?: number;
    kdv_applied?: boolean;
    kdv_rate?: number;
    note?: string;
  }>;
  gazette_ceiling_by_specialty: Record<string, number>;
  coverage_scope?: SutMaterialBundlingCoverageScope;
  specialty_coverage_scope?: import("@/lib/api/sut").SutSpecialtyProseCoverageScope;
}

export interface ProcedureCaptureGap extends ExactnessState {
  opportunities: Array<{
    type?: string;
    claim_id?: string;
    performed_line_id?: string;
    procedure_code?: string;
    procedure_name?: string;
    service_date?: string;
    source?: string;
    actual_billed_try?: number;
    list_price_try?: number;
    recoverable_gap_try?: number;
    price_methodology?: string;
    savings_basis?: string;
    savings_category?: string;
    included_in_sgk_total?: boolean;
    sut_section_id?: string;
    detail?: string;
  }>;
  total_gap_try?: number;
  confirmed_gap_try?: number;
}

export interface ProcedureAddonUplift extends ExactnessState {
  rule_source?: string;
  opportunities: Array<{
    type?: string;
    claim_id?: string;
    trigger_procedure_code?: string;
    trigger_procedure_name?: string;
    expected_addon_procedure_code?: string;
    expected_addon_procedure_name?: string;
    session_date?: string;
    addon_factor?: number;
    list_price_try?: number;
    actual_billed_try?: number;
    recoverable_uplift_try?: number;
    price_methodology?: string;
    savings_basis?: string;
    savings_category?: string;
    sut_section_id?: string;
    detail?: string;
  }>;
  total_uplift_try?: number;
  confirmed_uplift_try?: number;
}

export interface MaterialUplift extends ExactnessState {
  rule_source?: string;
  opportunities: Array<{
    type?: string;
    claim_id?: string;
    procedure_line_id?: string;
    procedure_code?: string;
    procedure_name?: string;
    material_code?: string;
    material_name?: string;
    actual_billed_try?: number;
    recoverable_uplift_try?: number;
    list_price_try?: number;
    price_methodology?: string;
    savings_basis?: string;
    savings_category?: string;
    sut_section_id?: string;
    detail?: string;
    /** Structured message contract (§2.2 surface). */
    message_code?: string;
    message_params?: Record<string, unknown>;
  }>;
  total_uplift_try?: number;
  confirmed_uplift_try?: number;
}

export interface BloodComponentUplift extends ExactnessState {
  rule_source?: string;
  opportunities: Array<{
    type?: string;
    claim_id?: string;
    procedure_code?: string;
    procedure_name?: string;
    allowed_fraction?: number;
    max_billable_try?: number;
    actual_billed_try?: number;
    recoverable_uplift_try?: number;
    savings_basis?: string;
    savings_category?: string;
    sut_section_id?: string;
    detail?: string;
  }>;
  total_uplift_try?: number;
  confirmed_uplift_try?: number;
}

export interface DrgUpliftRecommendation extends ExactnessState {
  rule_source?: string;
  opportunities: Array<{
    type?: string;
    claim_id?: string;
    payment_method_kind?: string;
    current_billing?: string;
    itemized_total_try?: number;
    package_total_try?: number;
    recoverable_uplift_try?: number;
    savings_basis?: string;
    savings_category?: string;
    sut_section_id?: string;
    detail?: string;
  }>;
  total_uplift_try?: number;
  confirmed_uplift_try?: number;
}

export interface MedulaRejectionPlaybook extends ExactnessState {
  entries: Array<{
    playbook_id?: string;
    rejection_event_id?: string;
    claim_id?: string;
    medula_stage?: string;
    sonuc_kodu?: string;
    hata_kodu?: string;
    hata_mesaji?: string;
    related_procedure_code?: string;
    related_procedure_line_id?: string;
    related_line_type?: string;
    related_line_id?: string;
    sut_anchor?: string;
    problem_summary_tr?: string;
    problem_summary_en?: string;
    corrective_steps_tr?: string[];
    corrective_steps_en?: string[];
    rebill_permitted?: boolean;
    rebill_stage?: string;
    recommendation_kind?: string;
    included_in_sgk_total?: boolean;
    savings_category?: string;
  }>;
  entry_count?: number;
  rebill_permitted_count?: number;
}

export interface ClaimSubmissionChecklist extends ExactnessState {
  items: Array<{
    checklist_id?: string;
    trigger_key?: string;
    playbook_key?: string;
    sonuc_kodu_risk?: string;
    severity?: string;
    claim_id?: string;
    line_type?: string;
    line_id?: string;
    line_code?: string;
    line_name?: string;
    reminder_tr?: string;
    reminder_en?: string;
    sut_anchor?: string;
    preventive_steps_tr?: string[];
    preventive_steps_en?: string[];
    recommendation_kind?: string;
    included_in_sgk_total?: boolean;
    savings_category?: string;
  }>;
  item_count?: number;
  error_count?: number;
}

export interface DrugIndicationRouteEvidence {
  rule_id?: string | null;
  sut_section?: string | null;
  icd10_codes?: string[];
  icd10_ranges?: string[];
  regulatory_summary_tr?: string | null;
  report_required?: boolean | null;
  report_duration_months?: number | null;
  report_specialties?: string[];
  prescriber_specialties?: string[];
  indication_label_tr?: string | null;
  icd10_code_count?: number;
  icd10_codes_truncated?: boolean;
  icd10_range_count?: number;
  icd10_ranges_truncated?: boolean;
}

export interface DrugIndicationFinding {
  finding_id?: string | null;
  patient_id?: string | null;
  claim_id?: string | null;
  drug_claim_line_id?: string | null;
  drug_name?: string | null;
  drug_code?: string | null;
  finding_kind?: string | null;
  severity?: string | null;
  applicability_status?: string | null;
  evaluation_status?: string | null;
  observed_icd10_codes?: string[];
  matched_icd10_codes?: string[];
  unmatched_icd10_codes?: string[];
  eligible_routes?: DrugIndicationRouteEvidence[];
  selected_rule_id?: string | null;
  explanation_tr?: string | null;
  recommended_action_tr?: string | null;
  required_inputs?: string[];
  missing_inputs?: string[];
  eligible_route_count?: number;
  eligible_routes_truncated?: boolean;
  observed_icd10_count?: number;
  observed_icd10_truncated?: boolean;
}

export interface DrugIndicationLineEvaluation {
  patient_id?: string | null;
  claim_id?: string | null;
  drug_claim_line_id?: string | null;
  drug_name?: string | null;
  drug_code?: string | null;
  applicability_status?: string | null;
  evaluation_status?: string | null;
  observed_icd10_codes?: string[];
  matched_icd10_codes?: string[];
  unmatched_icd10_codes?: string[];
  eligible_routes?: DrugIndicationRouteEvidence[];
  selected_rule_id?: string | null;
  finding_id?: string | null;
  finding_kind?: string | null;
  required_inputs?: string[];
  missing_inputs?: string[];
  eligible_route_count?: number;
  eligible_routes_truncated?: boolean;
  observed_icd10_count?: number;
  observed_icd10_truncated?: boolean;
}

export interface DrugIndicationReview extends ExactnessState {
  violations: Array<{
    drug_claim_line_id?: string;
    claim_id?: string;
    drug_name?: string;
    drug_code?: string;
    rule_id?: string;
    sut_section?: string;
    primary_icd10?: string;
    violation_kind?: string;
    severity?: string;
    message_tr?: string;
    finding_id?: string;
    applicability_status?: string;
    evaluation_status?: string;
    observed_icd10_codes?: string[];
    matched_icd10_codes?: string[];
    unmatched_icd10_codes?: string[];
  }>;
  findings?: DrugIndicationFinding[];
  evaluations?: DrugIndicationLineEvaluation[];
  violation_count?: number;
  error_count?: number;
  coverage_scope?: Record<string, unknown>;
  rule_source?: string;
}

export interface DrgPackageAdequacyReview extends ExactnessState {
  rule_source?: string;
  opportunities: Array<{
    claim_id?: string;
    primary_icd10?: string;
    clinical_procedure_codes?: string[];
    current_package_code?: string;
    current_package_footprint?: string[];
    candidate_package_code?: string;
    candidate_package_footprint?: string[];
    current_package_price_try?: number;
    candidate_package_price_try?: number;
    recoverable_uplift_try?: number;
    recommendation_kind?: string;
    review_kind?: string;
    included_in_sgk_total?: boolean;
    savings_category?: string;
    sut_section_id?: string;
    detail?: string;
  }>;
  total_uplift_try?: number;
  confirmed_uplift_try?: number;
  review_uplift_try?: number;
  review_opportunity_count?: number;
}

export interface CareSettingReview extends ExactnessState {
  rule_source?: string;
  opportunities: Array<{
    claim_id?: string;
    claim_type?: string;
    ambiguity_reason?: string;
    actual_care_setting?: string;
    alternate_care_setting?: string;
    actual_best_try?: number;
    alternate_best_try?: number;
    actual_payment_method_kind?: string;
    alternate_payment_method_kind?: string;
    package_total_try?: number;
    itemized_total_try?: number;
    recoverable_uplift_try?: number;
    recommendation_kind?: string;
    review_kind?: string;
    included_in_sgk_total?: boolean;
    savings_category?: string;
    sut_section_id?: string;
    detail?: string;
  }>;
  total_uplift_try?: number;
  confirmed_uplift_try?: number;
  review_uplift_try?: number;
  review_opportunity_count?: number;
}

export interface SessionPricingUplift extends ExactnessState {
  rule_source?: string;
  opportunities: Array<{
    type?: string;
    claim_id?: string;
    procedure_code?: string;
    procedure_name?: string;
    session_date?: string;
    primary_procedure_code?: string;
    expected_billed_try?: number;
    actual_billed_try?: number;
    recoverable_uplift_try?: number;
    review_kind?: string | null;
    included_in_sgk_total?: boolean;
    sut_section_id?: string;
    detail?: string;
  }>;
  total_uplift_try?: number;
  confirmed_uplift_try?: number;
  review_uplift_try?: number;
  review_opportunity_count?: number;
}

export interface RecommendedActionItem {
  action_id: string;
  surface: string;
  kind: string;
  claim_id?: string | null;
  procedure_code?: string | null;
  procedure_name?: string | null;
  material_code?: string | null;
  drug_code?: string | null;
  drug_name?: string | null;
  drug_claim_line_id?: string | null;
  finding_id?: string | null;
  severity?: string | null;
  applicability_status?: string | null;
  evaluation_status?: string | null;
  observed_icd10_codes?: string[] | null;
  matched_icd10_codes?: string[] | null;
  unmatched_icd10_codes?: string[] | null;
  eligible_routes?: DrugIndicationRouteEvidence[] | null;
  eligible_route_count?: number | null;
  eligible_routes_truncated?: boolean | null;
  observed_icd10_count?: number | null;
  observed_icd10_truncated?: boolean | null;
  recommended_action_tr?: string | null;
  sgk_uplift_try?: number | null;
  audit_risk_try?: number | null;
  compliance_savings_try?: number | null;
  billed_try?: number | null;
  material_name?: string | null;
  detail?: string | null;
  sut_section_id?: string | null;
  /** Clause cite backing this action row (Track E); clause_key may be "". */
  clause_ref?: SutClauseReference | null;
  /** Backend classification for UI badges; absent on legacy payloads. */
  finding_type?: "compliance" | "opportunity" | "informational" | null;
  /** Structured message contract (§2.2 surface): localize via i18n code. */
  message_code?: string | null;
  message_params?: Record<string, unknown> | null;
}

export interface BillingActionReport extends SUTDataSourceCarrier {
  patient_id: string;
  lab: LabOptimization;
  copay: CopayOptimization;
  billing_strategy: BillingStrategyRecommendation;
  session_uplift?: SessionPricingUplift;
  drg_uplift?: DrgUpliftRecommendation;
  blood_uplift?: BloodComponentUplift;
  material_uplift?: MaterialUplift;
  care_setting_review?: CareSettingReview;
  procedure_addon_uplift?: ProcedureAddonUplift;
  procedure_capture_gap?: ProcedureCaptureGap;
  drg_package_adequacy?: DrgPackageAdequacyReview;
  medula_rejection_playbook?: MedulaRejectionPlaybook;
  claim_submission_checklist?: ClaimSubmissionChecklist;
  drug_indication?: DrugIndicationReview;
  claim_compliance?: ClaimCompliance | null;
  claim_reviews?: import("./waveaEvidence").WaveAEvidenceBlock;
  financial_findings?: import("./waveaEvidence").WaveAEvidenceBlock;
  wavea_coverage?: import("./waveaEvidence").WaveACoverage | null;
  materials: MaterialPreCheck;
  sgk_uplift_try?: number;
  compliance_adjustment_try?: number;
  audit_exposure_try?: number;
  capture_gap_try?: number;
  package_adequacy_review_try?: number;
  medula_playbook_entry_count?: number;
  claim_submission_checklist_count?: number;
  drug_indication_violation_count?: number;
  total_recoverable_try: number;
  recommended_actions?: RecommendedActionItem[];
  action_count: number;
  priority: "high" | "medium" | "low";
  exactness_status?: ExactnessStatus;
  unavailable_reason?: string | null;
  required_inputs_missing?: string[];
  /** Present when the payload is scoped to a single bill. */
  claim_id?: string;
  scope?: "bill";
}

export interface PatientRecoverySummaryRow {
  patient_id: string;
  total_recoverable_try: number;
  sgk_uplift_try?: number;
  compliance_adjustment_try?: number;
  exemption_gap_try?: number;
  total_opportunity_try?: number;
  priority: string;
  action_count: number;
  top_action_type: string;
}

export interface CohortRecoverySummary extends ExactnessState, SUTDataSourceCarrier {
  n_patients: number;
  total_lab_savings: number;
  total_copay_savings: number;
  total_strategy_savings: number;
  total_session_uplift?: number;
  total_drg_uplift?: number;
  total_blood_uplift?: number;
  total_optional_override_uplift?: number;
  n_optional_override_patients?: number;
  n_drg_uplift_patients?: number;
  n_blood_uplift_patients?: number;
  total_material_uplift?: number;
  n_material_uplift_patients?: number;
  total_procedure_addon_uplift?: number;
  n_procedure_addon_patients?: number;
  total_strategy_uplift?: number;
  total_compliance_adjustment?: number;
  total_sgk_uplift?: number;
  total_audit_exposure?: number;
  total_capture_gap?: number;
  total_package_adequacy_review?: number;
  total_medula_playbook_entries?: number;
  medula_rejection_ingest_available?: boolean;
  total_material_flags: number;
  grand_total_recoverable: number;
  top_patients: Array<PatientRecoverySummaryRow>;
  patient_summaries?: Array<PatientRecoverySummaryRow>;
  savings_by_category: Record<string, number>;
  priority_distribution: Record<string, number>;
}

// ── Patient claim selector / invoice detail ──────────────────────────────────

export interface PatientClaimSummary extends SUTDataSourceCarrier {
  claim_id: string;
  episode_id: string;
  claim_type: string;
  admission_date: string | null;
  discharge_date: string | null;
  claim_start_date: string;
  claim_end_date: string;
  primary_icd10: string;
  expected_total_billed_try: number;
  expected_total_payable_try: number;
  expected_denial_reason?: string;
  scenario_tag?: string;
  /** Per-bill recoverable amount from cache; null when rollups unavailable. */
  recoverable_try?: number | null;
  priority?: "high" | "medium" | "low" | null;
}

export interface ClaimProcedureLine {
  procedure_line_id: string;
  procedure_date: string;
  procedure_code: string;
  procedure_name: string;
  procedure_category: string;
  quantity: number;
  unit_price_try: number;
  billed_amount_try: number;
  expected_payable_try: number;
  is_package_included: boolean;
  package_code?: string;
  denial_reason_expected?: string;
  rule_trace_expected?: string;
}

export interface ClaimMaterialLine {
  material_line_id: string;
  material_date: string;
  material_code: string;
  material_name: string;
  material_type: string;
  specialty_category: string;
  quantity: number;
  unit_price_try: number;
  billed_amount_try: number;
  expected_payable_try: number;
  is_bundled: boolean;
  requires_pre_auth: boolean;
  denial_reason_expected?: string;
  rule_trace_expected?: string;
}

export interface ClaimDrugLine {
  drug_claim_line_id: string;
  prescription_id: string;
  drug_claim_date: string;
  drug_name: string;
  drug_code: string;
  barkod: string;
  equivalence_group: string;
  quantity: number;
  unit_price_try: number;
  billed_amount_try: number;
  expected_payable_try: number;
  discount_tier_expected: number;
  denial_reason_expected?: string;
  rule_trace_expected?: string;
}

export interface PatientClaimDetail extends SUTDataSourceCarrier {
  claim_id: string;
  patient_id: string;
  episode_id: string;
  claim_type: string;
  facility_tier: string;
  provider_type: string;
  department: string;
  admission_date: string | null;
  discharge_date: string | null;
  claim_start_date: string;
  claim_end_date: string;
  primary_icd10: string;
  package_candidate: boolean;
  expected_total_billed_try: number;
  expected_total_payable_try: number;
  expected_denial_reason?: string;
  scenario_tag?: string;
  occupational_context?: string;
  procedures: ClaimProcedureLine[];
  materials: ClaimMaterialLine[];
  drugs: ClaimDrugLine[];
}

export interface PatientClaimsListResponse extends SUTDataSourceCarrier {
  patient_id: string;
  claims: PatientClaimSummary[];
  total: number;
}

// ── MEDULA rejection queue ───────────────────────────────────────────────────

export interface MedulaRejectionQueueRow {
  rejection_event_id: string;
  patient_id: string;
  claim_id: string;
  episode_id: string;
  medula_stage: string;
  sonuc_kodu: string;
  hata_mesaji: string;
  related_procedure_code?: string | null;
  rejection_timestamp?: string | null;
  related_line_type?: string;
  related_line_id?: string;
  playbook_matched: boolean;
  playbook_key?: string | null;
  sut_anchor?: string | null;
  rebill_permitted?: boolean | null;
  corrective_steps_tr: string[];
}

export interface MedulaRejectionQueueResponse extends SUTDataSourceCarrier {
  ingest_available: boolean;
  rows: MedulaRejectionQueueRow[];
  total: number;
  page: number;
  page_size: number;
  facets?: {
    sonuc_kodu?: string[];
    medula_stage?: string[];
  };
  stats?: {
    n_events?: number;
    n_matched?: number;
    n_rebill_permitted?: number;
  };
}

export interface MedulaRejectionIngestStatus {
  ingest_available: boolean;
}
