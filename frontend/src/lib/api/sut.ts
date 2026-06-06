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
  CheckupPricingResponse,
  SutPatientOutcomeData,
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
}

export interface SutClaimRequest {
  claim_id: string;
  procedure_code: string;
  materials: SutMaterialItem[];
}

export interface SutViolation {
  rule: string;
  severity: string;
  material_name: string;
  message: string;
  savings_try: number;
  risk_amount: number;
}

export interface SutMaterialEstimate {
  material_code: string;
  material_name: string;
  unit_price: number;
  quantity: number;
  total_price: number;
  is_reimbursable: boolean;
  is_bundled: boolean;
  source: string;
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
}

export interface SutValidationResult {
  claim_id: string;
  coverage_scope?: SutMaterialBundlingCoverageScope;
  is_valid: boolean;
  total_claim_amount: number;
  total_savings_try: number;
  total_risk_try: number;
  n_bundling_violations: number;
  n_exclusion_violations: number;
  validation_time_ms: number;
  summary: string;
  violations: SutViolation[];
  material_estimates: SutMaterialEstimate[];
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
  effective_date: string;
}

export interface SutExclusionCategory {
  section: string;
  material_code: string | null;
  material_name: string;
  description: string;
  effective_date: string;
}

export interface SutBundledConsumablesResult {
  coverage_scope?: SutMaterialBundlingCoverageScope;
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
  return postJSON<SutValidationResult, SutClaimRequest>(
    "/api/validate-claim",
    claim,
    options,
  );
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

export async function getPatientOptimization(
  patientId: string,
  options?: RequestInit,
): Promise<PatientOptimization> {
  return requestJSON<PatientOptimization>(
    `/api/patient/${encodeURIComponent(patientId)}/optimization`,
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

export async function getPatientBillingReport(
  patientId: string,
  options?: RequestInit,
): Promise<BillingActionReport> {
  return requestJSON<BillingActionReport>(
    `/api/billing-report/${encodeURIComponent(patientId)}`,
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

export interface SpecialtyMeta {
  label: string;
  name: string;
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

export interface PriceHistoryEntry {
  effective_date: string;
  price_try: number;
  puan?: number;
}

export async function getPriceHistory(
  code: string,
  options?: RequestInit,
): Promise<{ code: string; name: string; history: PriceHistoryEntry[] }> {
  return requestJSON<{ code: string; name: string; history: PriceHistoryEntry[] }>(
    `/api/price-history/${encodeURIComponent(code)}`,
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

export async function getCheckupPricing(options?: RequestInit): Promise<CheckupPricingResponse> {
  return requestJSON<CheckupPricingResponse>("/api/checkup-pricing", options);
}


