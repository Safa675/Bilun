import { postJSON, requestJSON } from "./request";
import type {
  OptimizationSummary,
  PatientOptimization,
  PatientAlertsResponse,
  PatientAlertsRequestParams,
  BillingActionReport,
  CohortRecoverySummary,
  SUTDataSourceMetadata,
  VisitPricingResponse,
  MaterialsBySpecialtyResponse,
  SutPatientOutcomeData,
  PatientClaimDetail,
  PatientClaimsListResponse,
  MedulaRejectionIngestStatus,
  MedulaRejectionQueueResponse,
  ComplianceIndexResponse,
} from "../domains/sut";
import type { PatientMeta, PatientSearchResponse } from "../domains/patient";

function buildPatientAlertsPath(params: PatientAlertsRequestParams = {}): string {
  const query = new URLSearchParams();
  query.set("category", params.category ?? "exemptions");
  query.set("status", params.status ?? "all");
  query.set("limit", String(params.limit ?? 100));
  query.set("offset", String(params.offset ?? 0));

  const search = params.search?.trim();
  if (search) {
    query.set("search", search);
  }

  return `/api/patient-alerts?${query.toString()}`;
}

export interface SutMaterialItem {
  name: string;
  unit_price: number;
  quantity: number;
  code?: string;
  // §4.2.33 anti-VEGF dose protocol (intravitreal injection counts).
  // Optional; only meaningful when validate-claim runs drug_indication checks.
  annual_application_count?: number;
  is_loading_phase?: boolean;
  // §4.2.14.C oncology biomarker + prior-therapy gating.
  // biomarkers: [{ marker: "HER2", status: "3+" }]
  biomarkers?: Array<{ marker: string; status: string }>;
  // prior_therapies: [{ drug_or_class: "imatinib", outcome: "resistant" }]
  prior_therapies?: Array<{ drug_or_class: string; outcome: string }>;
}

export interface SutDrugContext {
  /** Primary ICD-10 diagnosis code (required for drug_indication checks). */
  primary_icd10: string;
  /** Prescriber's medical specialty (e.g. "tıbbi onkoloji", "göz hastalıkları"). */
  prescriber_specialty: string;
  /** Whether a specialty board report (sağlık kurulu raporu) is present. */
  board_report_present?: boolean | null;
  /** Report validity in months (e.g. 3, 6). */
  report_duration_months?: number | null;
}

export interface SutClaimRequest {
  claim_id: string;
  procedure_code: string;
  materials: SutMaterialItem[];
  /** Optional drug indication context. When present, validate-claim runs §4.2.14.C
   * oncology + §4.2.33 anti-VEGF checks (indication, prescriber, biomarker, dose). */
  drug_context?: SutDrugContext;
}

export interface SutViolation {
  rule: string;
  severity: string;
  material_name: string;
  message: string;
  savings_try: number;
  risk_amount: number;
}

export interface SutMaterialLine {
  material_code: string;
  material_name: string;
  unit_price: number;
  quantity: number;
  total_price: number;
  is_reimbursable: boolean | null;
  is_bundled: boolean | null;
  source: string;
  exactness_status: string;
  notes: string;
}

export interface SutMaterialBundlingCoverageScope {
  prose_rule_id: string;
  prose_section_prefixes: string[];
  prose_engine_status: string;
  prose_coverage_tier?: string;
  prose_rules_implemented?: number;
  prose_effective_date?: string;
  implemented_annexes: string[];
  ek3b1_row_count: number;
  ek3b2_row_count: number;
  p2_plan_path: string;
  medula_overlap_classification?: string;
  medula_boundary_doc?: string;
  medula_savings_note?: string;
  gate_b_deferred_clauses?: number;
  kdv_pricing_clauses?: number;
  kdv_pricing_module?: string;
}

export interface SutSpecialtyProseCoverageScope {
  prose_rule_id: string;
  prose_section_prefixes: string[];
  prose_engine_status: string;
  prose_coverage_tier?: string;
  prose_rules_implemented?: number;
  prose_effective_date?: string;
  encoded_corpus_rows?: number;
  implemented_annexes?: string[];
  l44_plan_path?: string;
  medula_overlap_classification?: string;
  medula_savings_note?: string;
}

export interface SutLegacyValidationResult {
  claim_id: string;
  coverage_scope?: SutMaterialBundlingCoverageScope;
  specialty_coverage_scope?: SutSpecialtyProseCoverageScope;
  is_valid: boolean;
  total_claim_amount: number;
  total_savings_try: number;
  total_risk_try: number;
  n_bundling_violations: number;
  n_exclusion_violations: number;
  validation_time_ms: number;
  summary: string;
  violations: SutViolation[];
  material_lines: SutMaterialLine[];
}

export interface SutValidationEvidence {
  evidence_id: string;
  rule: string;
  rule_id?: string | null;
  material_name: string;
  message: string;
  disposition: string;
  reason?: string | null;
  source_status: string;
}

export interface SutAnnexAssessment {
  /** Only this annex match; false does not establish payment entitlement. */
  matched: boolean | null;
  source_reason: string | null;
}

export interface SutMaterialApplicability {
  material_index: number;
  material_id: string;
  material_name: string;
  material_code: string | null;
  ek3b1: SutAnnexAssessment;
  ek3b2: SutAnnexAssessment;
}

export interface SutValidationResult {
  contract_version: 2;
  request_id: string;
  claim_id: string;
  validation_status: "violations_found" | "review_required" | "partially_evaluated" | "no_violations_in_evaluated_scope";
  is_valid: boolean | null;
  violations: SutValidationEvidence[];
  advisories: SutValidationEvidence[];
  material_applicability: SutMaterialApplicability[];
  coverage: {
    evaluation_count: number;
    unresolved_count: number;
    authored_rule_count: number;
    disposition_counts: Record<string, number>;
    scope: string;
  };
  provenance: Record<string, unknown>;
  summary: string;
  validation_time_ms: number;
}

export interface SutMaterialPricing {
  material_code: string;
  material_name: string;
  price_try: number;
  source: string;
  description: string;
}

export interface SutMaterialPricingResult {
  query: string;
  n_matches: number;
  materials: SutMaterialPricing[];
}

export interface SutBundledItem {
  item_name: string;
  description: string;
  bundled_in: string;
  effective_date: string | null;
  evaluation_status: "not_evaluated";
}

export interface SutExclusionCategory {
  section: string;
  material_code: string | null;
  material_name: string;
  description: string;
  effective_date: string | null;
  evaluation_status: "not_evaluated";
}

export interface SutBundledConsumablesResult {
  coverage_scope?: SutMaterialBundlingCoverageScope;
  specialty_coverage_scope?: SutSpecialtyProseCoverageScope;
  bundled_consumables: { count: number; items: SutBundledItem[] };
  exclusion_categories: { count: number; categories: SutExclusionCategory[] };
}

export interface SutProcedureEntry {
  code: string;
  name: string;
  description: string;
  price_try: number;
}

export interface SutProcedureInfo {
  match_type: "exact" | "prefix_stripped" | "prefix_search" | "none";
  entry: SutProcedureEntry | null;
  candidates: SutProcedureEntry[];
}

export async function getSutPatients(
  options?: RequestInit,
): Promise<{
  patients: string[];
  total: number;
  patient_meta: PatientMeta[];
  cache_mode?: string;
  data_source?: SUTDataSourceMetadata | null;
  dataSource?: SUTDataSourceMetadata | null;
}> {
  return requestJSON<{
    patients: string[];
    total: number;
    patient_meta: PatientMeta[];
    cache_mode?: string;
    data_source?: SUTDataSourceMetadata | null;
    dataSource?: SUTDataSourceMetadata | null;
  }>(
    "/api/patients",
    options,
  );
}

export async function searchSutPatients(
  q: string,
  limit: number = 20,
  options?: RequestInit,
): Promise<PatientSearchResponse> {
  const params = new URLSearchParams({ q, limit: String(limit) });
  return requestJSON<PatientSearchResponse>(
    `/api/patients/search?${params}`,
    options,
  );
}

export async function getSutPatientOutcome(
  patientId: string,
  options?: RequestInit,
): Promise<SutPatientOutcomeData> {
  return requestJSON<SutPatientOutcomeData>(
    `/api/patient/${encodeURIComponent(patientId)}/outcome`,
    options,
  );
}

export async function getSutProcedureInfo(
  code: string,
  options?: RequestInit,
): Promise<SutProcedureInfo> {
  return requestJSON<SutProcedureInfo>(
    `/api/procedure/${encodeURIComponent(code)}`,
    options,
  );
}

export async function validateSutClaim(
  claim: SutClaimRequest,
  options?: RequestInit,
): Promise<SutValidationResult> {
  const headers = new Headers(options?.headers);
  headers.set("X-Bilun-Validation-Contract", "2");
  const result = await postJSON<SutValidationResult, SutClaimRequest>(
    "/api/validate-claim",
    claim,
    { ...options, headers: Object.fromEntries(headers.entries()) },
  );
  if (!result || result.contract_version !== 2) {
    throw new Error(
      "Doğrulama sürümü uyumsuz. Sayfayı yenileyin veya istemciyi güncelleyin. / " +
      "Validation version mismatch. Reload the page or upgrade this client.",
    );
  }
  return result;
}

export async function getSutMaterialPricing(
  codeOrName: string,
  options?: RequestInit,
): Promise<SutMaterialPricingResult> {
  return requestJSON<SutMaterialPricingResult>(
    `/api/material/${encodeURIComponent(codeOrName)}/pricing`,
    options,
  );
}

export async function getSutBundledConsumables(
  options?: RequestInit,
): Promise<SutBundledConsumablesResult> {
  return requestJSON<SutBundledConsumablesResult>(
    "/api/bundled-consumables",
    options,
  );
}

export async function getOptimizationSummary(
  options?: RequestInit,
): Promise<OptimizationSummary> {
  return requestJSON<OptimizationSummary>(
    "/api/optimization-summary",
    options,
  );
}

export async function getMedulaRejectionIngestStatus(
  options?: RequestInit,
): Promise<MedulaRejectionIngestStatus> {
  return requestJSON<MedulaRejectionIngestStatus>(
    "/api/medula-rejections/ingest-status",
    options,
  );
}

export async function getMedulaRejectionQueue(
  params?: {
    page?: number;
    page_size?: number;
    sonuc_kodu?: string;
    medula_stage?: string;
    rebill_permitted?: boolean;
    playbook_matched?: boolean;
    q?: string;
  },
  options?: RequestInit,
): Promise<MedulaRejectionQueueResponse> {
  const query = new URLSearchParams();
  if (params?.page) query.set("page", String(params.page));
  if (params?.page_size) query.set("page_size", String(params.page_size));
  if (params?.sonuc_kodu) query.set("sonuc_kodu", params.sonuc_kodu);
  if (params?.medula_stage) query.set("medula_stage", params.medula_stage);
  if (params?.rebill_permitted !== undefined) {
    query.set("rebill_permitted", String(params.rebill_permitted));
  }
  if (params?.playbook_matched !== undefined) {
    query.set("playbook_matched", String(params.playbook_matched));
  }
  if (params?.q) query.set("q", params.q);
  const queryString = query.toString();
  return requestJSON<MedulaRejectionQueueResponse>(
    `/api/medula-rejections/queue${queryString ? `?${queryString}` : ""}`,
    options,
  );
}

export async function getPatientOptimization(
  patientId: string,
  options?: RequestInit,
): Promise<PatientOptimization> {
  return requestJSON<PatientOptimization>(
    `/api/patient/${encodeURIComponent(patientId)}/optimization`,
    options,
  );
}

export async function getBillOptimization(
  patientId: string,
  claimId: string,
  options?: RequestInit,
): Promise<PatientOptimization> {
  return requestJSON<PatientOptimization>(
    `/api/patient/${encodeURIComponent(patientId)}/bills/${encodeURIComponent(claimId)}/optimization`,
    options,
  );
}

export async function getPatientAlerts(
  params: PatientAlertsRequestParams = {},
  options?: RequestInit,
): Promise<PatientAlertsResponse> {
  return requestJSON<PatientAlertsResponse>(
    buildPatientAlertsPath(params),
    options,
  );
}

export async function getComplianceIndex(
  params?: {
    surface?: string;
    patientId?: string | string[];
    limit?: number;
    offset?: number;
  },
  options?: RequestInit,
): Promise<ComplianceIndexResponse> {
  const maxGetQueryLength = 6000;
  const query = new URLSearchParams();
  if (params?.surface) query.set("surface", params.surface);
  if (params?.limit != null) query.set("limit", String(params.limit));
  if (params?.offset != null) query.set("offset", String(params.offset));
  const patientIds = Array.isArray(params?.patientId)
    ? params.patientId
    : params?.patientId
      ? [params.patientId]
      : [];
  for (const id of patientIds) {
    query.append("patient_id", id);
  }
  const queryString = query.toString();
  if (queryString.length > maxGetQueryLength && patientIds.length > 0) {
    return postJSON<ComplianceIndexResponse, {
      surface?: string;
      patient_id: string[];
      limit?: number;
      offset?: number;
    }>(
      "/api/compliance-index",
      {
        ...(params?.surface ? { surface: params.surface } : {}),
        patient_id: patientIds,
        ...(params?.limit != null ? { limit: params.limit } : {}),
        ...(params?.offset != null ? { offset: params.offset } : {}),
      },
      options,
    );
  }
  return requestJSON<ComplianceIndexResponse>(
    queryString ? `/api/compliance-index?${queryString}` : "/api/compliance-index",
    options,
  );
}

export async function getPatientBillingReport(
  patientId: string,
  options?: RequestInit,
): Promise<BillingActionReport> {
  return requestJSON<BillingActionReport>(
    `/api/billing-report/${encodeURIComponent(patientId)}`,
    options,
  );
}

export async function getBillBillingReport(
  patientId: string,
  claimId: string,
  options?: RequestInit,
): Promise<BillingActionReport> {
  return requestJSON<BillingActionReport>(
    `/api/billing-report/${encodeURIComponent(patientId)}/bills/${encodeURIComponent(claimId)}`,
    options,
  );
}

export async function getPatientClaims(
  patientId: string,
  options?: RequestInit,
): Promise<PatientClaimsListResponse> {
  return requestJSON<PatientClaimsListResponse>(
    `/api/patients/${encodeURIComponent(patientId)}/claims`,
    options,
  );
}

export async function getPatientClaimDetail(
  patientId: string,
  claimId: string,
  options?: RequestInit,
): Promise<PatientClaimDetail> {
  return requestJSON<PatientClaimDetail>(
    `/api/patients/${encodeURIComponent(patientId)}/claims/${encodeURIComponent(claimId)}`,
    options,
  );
}

export async function getRevenueRecovery(
  options?: RequestInit,
): Promise<CohortRecoverySummary> {
  return requestJSON<CohortRecoverySummary>(
    "/api/revenue-recovery",
    options,
  );
}

export async function getVisitPricing(options?: RequestInit): Promise<VisitPricingResponse> {
  return requestJSON<VisitPricingResponse>("/api/visit-pricing", options);
}

export interface DrugEntry {
  drug_name: string;
  equivalence_group?: string;
  discount_status?: string;
  discount_tier_1?: number;
  passivation_date?: string;
  [key: string]: unknown;
}

export async function getDrugCatalog(
  params?: { q?: string; page?: number; per_page?: number },
  options?: RequestInit,
): Promise<{ drugs: DrugEntry[]; total: number; page: number; total_pages: number }> {
  const qs = new URLSearchParams();
  if (params?.q) qs.set("q", params.q);
  if (params?.page) qs.set("page", String(params.page));
  if (params?.per_page) qs.set("per_page", String(params.per_page));
  const query = qs.toString();
  return requestJSON<{ drugs: DrugEntry[]; total: number; page: number; total_pages: number }>(
    `/api/drugs${query ? `?${query}` : ""}`,
    options,
  );
}

export type RuleCoverageStatus =
  | "implemented"
  | "partial"
  | "missing"
  | "needs_claim_lines"
  | "non_algorithmic";

export type FactCheckVerdict =
  | "COMPLIANT"
  | "PARTIAL"
  | "HEURISTIC"
  | "NEEDS_CLAIM_LINES"
  | "WRONG"
  | "OUT_OF_SCOPE";

export type MedulaOverlap =
  | "ADDITIVE"
  | "PARTIAL_OVERLAP"
  | "MEDULA_DUPLICATE"
  | "NOT_APPLICABLE";

export interface RuleSources {
  sut_sections: string[];
  annexes: string[];
}

export interface RuleCatalogEntry {
  rule_id: string;
  rule_category: string;
  rule_category_tr: string;
  coverage_status: RuleCoverageStatus;
  description: string;
  description_tr: string;
  sources: RuleSources;
  keywords: string[];
  domain_modules: string[];
  matched_clause_count: number;
  has_clause_mapping: boolean;
  fact_check_verdict?: FactCheckVerdict | null;
  medula_overlap?: MedulaOverlap | null;
  fact_check_units?: string[];
  fact_check_note?: string | null;
}

export interface RuleClause {
  clause_key: string | null;
  paragraph_index: number | null;
  section_id: string | null;
  section_title: string | null;
  section_path: string | null;
  chapter: string | null;
  clause_type: string | null;
  clause_number: number | null;
  clause_letter: string | null;
  clause_coordinate: string | null;
  is_heading: boolean;
  text_tr: string | null;
  annex_refs: string[];
  procedure_codes: string[];
  percentages: number[];
  amendment_refs: string[];
  deontic_modality: string | null;
  source_effective_date: string | null;
  coverage_status: string | null;
  primary_rule_id: string | null;
  primary_rule_category: string | null;
  matched_rule_ids: string[];
  matched_rules: { rule_id: string; rule_category_tr: string | null }[];
  is_primary: boolean;
  match_score: number;
  has_algorithmic_gap: boolean;
  has_rule_encoding: boolean | null;
}

export interface FactCheckVerdictCounts {
  COMPLIANT: number;
  PARTIAL: number;
  HEURISTIC: number;
  NEEDS_CLAIM_LINES: number;
  WRONG: number;
  OUT_OF_SCOPE: number;
}

export interface FactCheckAuditUnitSummary {
  unit_id: string;
  title: string;
  verdict: FactCheckVerdict;
  medula_overlap: MedulaOverlap;
  linked_rule_ids: string[];
  note?: string | null;
}

export interface FactCheckRollup {
  audit_closed: string;
  total_units: number;
  by_verdict: FactCheckVerdictCounts;
  units: FactCheckAuditUnitSummary[];
}

export interface CoverageStatusCount {
  status: string;
  count: number;
}

export interface TopGapCategory {
  category: string;
  count: number;
}

export interface ClauseCoverageSummary {
  total_extracted: number;
  by_status: CoverageStatusCount[];
  algorithmic_gaps: number;
  algorithmic_gap_pct: number;
  top_gap_categories: TopGapCategory[];
  clause_type_breakdown: Record<string, number>;
  numbered_clause_count: number;
  prose_clause_count: number;
  structural_clause_count: number;
}

export interface ZeroClauseMatch {
  rule_id: string;
  coverage_status: string;
  rule_category: string;
  rule_category_tr: string;
  description_tr: string;
}

export interface RegistryCoverageSummary {
  total_rules: number;
  by_status: CoverageStatusCount[];
  implemented_rules: number;
  partial_rules: number;
  missing_rules: number;
  needs_claim_lines_rules: number;
  non_algorithmic_rules: number;
  zero_clause_matches: ZeroClauseMatch[];
  rules_without_mapping: ZeroClauseMatch[];
}

export interface CoverageSummaryMeta {
  generated_at: string | null;
  artifacts_available: boolean;
  clauses_source_available: boolean;
  unavailable_reason: string | null;
}

export interface PartialEngineCoverage {
  rule_id: string;
  registry_status: string;
  prose_engine_status: string;
  classified_clause_rows: number;
  encoded_clause_rows: number;
  deferred_gap_rows?: number;
  true_gap_rows?: number;
  algorithmic_gap_rows: number;
  unencoded_gap_rows: number;
  encoded_clause_pct: number;
  gap_pct_of_classified: number;
  prose_rules_on_disk: number;
  tier_b_rule_count?: number;
  encode_tier_c_deferred_count?: number;
  manifest_traced_clause_count?: number | null;
  corpus_export_rows?: number | null;
  kdv_pricing_clauses?: number | null;
  "section_4.2.14.C_clause_total"?: number;
  subsection_coverage?: Record<
    string,
    { encoded_clause_count: number; clause_total: number; encoded_clause_pct: number }
  >;
  honesty_note?: string;
}

export interface PartialEnginesCoverage {
  drug_indication_prose?: PartialEngineCoverage;
  material_bundling_prose?: PartialEngineCoverage;
  specialty_materials_prose?: PartialEngineCoverage;
  payment_method_2_2?: PartialEngineCoverage;
  copay_general_1_8?: PartialEngineCoverage;
}

export interface GapCompositionSummary {
  total_algorithmic_gaps: number;
  drug_indication_gap_rows: number;
  drug_indication_gap_pct_of_gaps: number;
  optimizer_gaps_excluding_drug: number;
  non_algorithmic_clause_rows: number;
  footnote_en: string;
  footnote_tr: string;
}

export interface CoverageSummary {
  clauses: ClauseCoverageSummary;
  registry: RegistryCoverageSummary;
  partial_engines?: PartialEnginesCoverage;
  gap_composition?: GapCompositionSummary;
  meta: CoverageSummaryMeta;
}

export interface RuleCatalogResponse {
  rules: RuleCatalogEntry[];
  total: number;
  artifacts_available: boolean;
  fact_check: FactCheckRollup;
  coverage_summary: CoverageSummary;
}

export interface RuleDetailResponse {
  rule: RuleCatalogEntry;
  clauses: RuleClause[];
  clause_total: number;
  page: number;
  per_page: number;
  total_pages: number;
  artifacts_available: boolean;
}

export interface ProseInventoryEngine {
  rule_set_id: string;
  file_name: string;
  effective_date: string | null;
  rule_count: number | null;
  sut_section_prefixes: string[];
  sut_anchors: string[];
}

export interface ProseInventoryResponse {
  engines: ProseInventoryEngine[];
  total: number;
  artifacts_available: boolean;
  unavailable_reason: string | null;
}

export interface SectionRollupEntry {
  section_id: string | null;
  section_title: string | null;
  clause_count: number;
  worst_coverage_status: string | null;
  gap_clause_count: number;
  primary_categories: string[];
}

/** Stable React/list key: section_id alone is not unique in coverage rollups. */
export function sectionRollupRowKey(
  section: Pick<SectionRollupEntry, "section_id" | "section_title">,
): string {
  return `${section.section_id ?? "unknown"}::${section.section_title ?? ""}`;
}

export interface SectionRollupResponse {
  sections: SectionRollupEntry[];
  total: number;
  page: number;
  per_page: number;
  total_pages: number;
  artifacts_available: boolean;
  unavailable_reason: string | null;
}

export async function getRuleCatalog(options?: RequestInit): Promise<RuleCatalogResponse> {
  return requestJSON<RuleCatalogResponse>("/api/rules", options);
}

export async function getRuleDetail(
  ruleId: string,
  params?: { page?: number; per_page?: number },
  options?: RequestInit,
): Promise<RuleDetailResponse> {
  const qs = new URLSearchParams();
  if (params?.page) qs.set("page", String(params.page));
  if (params?.per_page) qs.set("per_page", String(params.per_page));
  const query = qs.toString();
  return requestJSON<RuleDetailResponse>(
    `/api/rules/${encodeURIComponent(ruleId)}${query ? `?${query}` : ""}`,
    options,
  );
}

export async function getRuleSections(
  params?: { page?: number; per_page?: number; q?: string; min_gap_count?: number; consolidate?: boolean },
  options?: RequestInit,
): Promise<SectionRollupResponse> {
  const qs = new URLSearchParams();
  if (params?.page) qs.set("page", String(params.page));
  if (params?.per_page) qs.set("per_page", String(params.per_page));
  if (params?.q) qs.set("q", params.q);
  if (params?.min_gap_count !== undefined) qs.set("min_gap_count", String(params.min_gap_count));
  if (params?.consolidate) qs.set("consolidate", "true");
  const query = qs.toString();
  return requestJSON<SectionRollupResponse>(
    `/api/rules/sections${query ? `?${query}` : ""}`,
    options,
  );
}

export interface SectionClausesResponse {
  clauses: RuleClause[];
  clause_total: number;
  page: number;
  per_page: number;
  total_pages: number;
  artifacts_available: boolean;
}

export async function getSectionClauses(
  params: { section_id: string; section_title?: string | null; page?: number; per_page?: number },
  options?: RequestInit,
): Promise<SectionClausesResponse> {
  const qs = new URLSearchParams();
  qs.set("section_id", params.section_id);
  if (params.section_title) qs.set("section_title", params.section_title);
  if (params.page) qs.set("page", String(params.page));
  if (params.per_page) qs.set("per_page", String(params.per_page));
  return requestJSON<SectionClausesResponse>(
    `/api/rules/sections/clauses?${qs.toString()}`,
    options,
  );
}

export async function listClauses(
  params?: {
    q?: string;
    page?: number;
    per_page?: number;
    coverage_status?: string;
    has_gap?: boolean;
    has_encoding?: boolean;
    primary_rule_id?: string;
    exclude_non_algorithmic?: boolean;
    exclude_headings?: boolean;
  },
  options?: RequestInit,
): Promise<SectionClausesResponse> {
  const qs = new URLSearchParams();
  if (params?.q) qs.set("q", params.q);
  if (params?.page) qs.set("page", String(params.page));
  if (params?.per_page) qs.set("per_page", String(params.per_page));
  if (params?.coverage_status) qs.set("coverage_status", params.coverage_status);
  if (params?.has_gap !== undefined) qs.set("has_gap", String(params.has_gap));
  if (params?.has_encoding !== undefined) qs.set("has_encoding", String(params.has_encoding));
  if (params?.primary_rule_id) qs.set("primary_rule_id", params.primary_rule_id);
  if (params?.exclude_non_algorithmic) qs.set("exclude_non_algorithmic", "true");
  if (params?.exclude_headings) qs.set("exclude_headings", "true");
  const query = qs.toString();
  return requestJSON<SectionClausesResponse>(
    `/api/rules/clauses${query ? `?${query}` : ""}`,
    options,
  );
}

export async function getClause(clauseId: string, options?: RequestInit): Promise<RuleClause> {
  return requestJSON<RuleClause>(`/api/rules/clauses/${encodeURIComponent(clauseId)}`, options);
}

export async function getProseInventory(options?: RequestInit): Promise<ProseInventoryResponse> {
  return requestJSON<ProseInventoryResponse>("/api/rules/prose-inventory", options);
}

export interface GateBSourceCite {
  ref: string;
  clause_key: string | null;
  clause_coordinate: string | null;
  text_snippet: string | null;
}

export interface ProseRuleSources {
  rule_set_id: string;
  rule_id: string;
  sut_section: string | null;
  gate_b_sources: GateBSourceCite[];
}

export interface ProseRulesSourcesListResponse {
  rule_set_id: string;
  rules: ProseRuleSources[];
  total: number;
  page: number;
  per_page: number;
  total_pages: number;
  artifacts_available: boolean;
}

export async function listProseRuleSources(
  ruleSetId: string,
  params?: { page?: number; per_page?: number },
  options?: RequestInit,
): Promise<ProseRulesSourcesListResponse> {
  const qs = new URLSearchParams();
  if (params?.page) qs.set("page", String(params.page));
  if (params?.per_page) qs.set("per_page", String(params.per_page));
  const query = qs.toString();
  return requestJSON<ProseRulesSourcesListResponse>(
    `/api/rules/prose-rules/${encodeURIComponent(ruleSetId)}${query ? `?${query}` : ""}`,
    options,
  );
}

export interface DeferralEntry {
  clause_key: string | null;
  clause_coordinate: string | null;
  section_id: string | null;
  status: string;
  defer_themes: string[];
  defer_reason: string;
  text_snippet: string | null;
}

export interface DeferralListResponse {
  deferrals: DeferralEntry[];
  total: number;
  page: number;
  per_page: number;
  total_pages: number;
  artifacts_available: boolean;
}

export async function listDeferrals(
  params?: { q?: string; status?: string; page?: number; per_page?: number },
  options?: RequestInit,
): Promise<DeferralListResponse> {
  const qs = new URLSearchParams();
  if (params?.q) qs.set("q", params.q);
  if (params?.status) qs.set("status", params.status);
  if (params?.page) qs.set("page", String(params.page));
  if (params?.per_page) qs.set("per_page", String(params.per_page));
  const query = qs.toString();
  return requestJSON<DeferralListResponse>(
    `/api/rules/deferrals${query ? `?${query}` : ""}`,
    options,
  );
}

export async function getMaterialsBySpecialty(
  specialty?: string,
  options?: RequestInit,
): Promise<MaterialsBySpecialtyResponse> {
  const qs = specialty ? `?specialty=${encodeURIComponent(specialty)}` : "";
  return requestJSON<MaterialsBySpecialtyResponse>(
    `/api/materials/by-specialty${qs}`,
    options,
  );
}

export interface LabPriceEntry {
  test_name: string;
  sut_code: string;
  price_try: number;
}

export async function getLabPrices(options?: RequestInit): Promise<{ tests: LabPriceEntry[]; total: number }> {
  return requestJSON<{ tests: LabPriceEntry[]; total: number }>(
    "/api/lab-prices",
    options,
  );
}
