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

export interface CheckupLabEntry {
  name: string;
  [key: string]: unknown;
}

export interface CheckupProcedureEntry {
  [key: string]: unknown;
}

export interface CheckupCopaymentInfo {
  [key: string]: unknown;
}

export interface CheckupPricingResponse {
  labs: CheckupLabEntry[];
  procedures: CheckupProcedureEntry[];
  copayment: CheckupCopaymentInfo;
  katsayi: number;
}

export interface DRGEpisodeData {
  episode_id: number;
  primary_icd10: string;
  primary_icd10_chapter: string;
  description: string;
  los_days: number;
  lab_cost: number;
  visit_cost: number;
  rx_cost: number;
  procedure_cost: number;
  total_cost: number;
  drg_package_price: number | null;
  ek2c_group: string;
  admission_date: string | null;
  discharge_date: string | null;
  pricing_status?: ExactnessStatus | null;
  pricing_date?: string | null;
  unavailable_reason?: string | null;
  required_inputs_missing?: string[];
}

export interface DRGSummaryData {
  n_episodes: number;
  total_drg_cost: number;
  mean_episode_cost: number;
  most_expensive_drg: string;
  dominant_icd10_chapter: string;
  total_drg_package_price: number | null;
  fully_priced?: boolean;
  priced_episode_count?: number;
  unknown_date_episode_count?: number;
  pricing_status?: ExactnessStatus | null;
  unavailable_reason?: string | null;
  required_inputs_missing?: string[];
  episodes: DRGEpisodeData[];
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
  drg_summary: DRGSummaryData | null;
  consistency_warnings?: string[];
  expensive_analytics?: {
    state: "ready" | "missing" | "skipped";
    included: boolean;
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
  total_heuristic_savings?: number | null;
  has_heuristic_savings?: boolean;
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
  total_heuristic_savings?: number | null;
  has_heuristic_savings?: boolean;
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

export interface LabOptimization extends ExactnessState {
  normative_cost_try: number;
  hemogram_bundling_savings: number;
  flagged_tests: Array<{
    test_name: string;
    sut_code: string;
    gazette_price: number;
    flag_type: string;
    savings_try: number | null;
    detail?: string;
  }>;
}

export interface CopayOptimization extends ExactnessState {
  is_exempt: boolean;
  exemption_disease: string;
  exemption_range: string;
  /** Exemption gap benefits patient katılım waiver and SGK payable correction. */
  savings_beneficiary?: "patient_and_sgk";
  gap_kind?: "exemption_correction";
  visit_copay_savings_try: number;
  rx_copay_savings_try: number;
  /** Legacy: procedure/visit copay waived only (excludes Rx). */
  total_copay_savings_try: number;
  /** Visit + Rx patient copay that exemption may waive. */
  patient_copay_waived_total_try?: number;
  rate_corrections: Array<{
    procedure?: string;
    gazette_rate?: number;
    correction_try?: number;
    code?: string;
    name?: string;
    billed_try?: number;
    payable_try?: number;
    copay_component_try?: number;
    detail?: string;
  }>;
}

export interface BillingStrategyRecommendation extends ExactnessState {
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
    type?: "compliance_violation";
    billed_as_package?: boolean;
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
  gazette_ceiling_by_specialty: Record<string, number>;
  coverage_scope?: SutMaterialBundlingCoverageScope;
}

export interface BillingActionReport extends SUTDataSourceCarrier {
  patient_id: string;
  lab: LabOptimization;
  copay: CopayOptimization;
  billing_strategy: BillingStrategyRecommendation;
  materials: MaterialPreCheck;
  total_recoverable_try: number;
  action_count: number;
  priority: "high" | "medium" | "low";
  exactness_status?: ExactnessStatus;
  unavailable_reason?: string | null;
  required_inputs_missing?: string[];
}

export interface CohortRecoverySummary extends ExactnessState, SUTDataSourceCarrier {
  n_patients: number;
  total_lab_savings: number;
  total_copay_savings: number;
  total_strategy_savings: number;
  total_material_flags: number;
  grand_total_recoverable: number;
  top_patients: Array<{
    patient_id: string;
    total_recoverable_try: number;
    priority: string;
    action_count: number;
    top_action_type: string;
  }>;
  patient_summaries?: Array<{
    patient_id: string;
    total_recoverable_try: number;
    priority: string;
    action_count: number;
    top_action_type: string;
  }>;
  savings_by_category: Record<string, number>;
  priority_distribution: Record<string, number>;
}


