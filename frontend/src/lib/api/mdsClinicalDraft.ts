import type { SutClinicalRestriction } from "./clinicalEvidence";

/** Isolated MDS facts. Units, dates and treatment phase must be explicit. */
export interface MdsEvidence {
  applies_on?: string | null;
  assessment_date?: string | null;
  indication?: "mds_anemia" | "ckd_anemia" | "other" | null;
  substance?: "epoetin_alfa" | "epoetin_beta" | null;
  phase?: "initiation" | "continuation" | "restart" | null;
  hb_value?: number | null;
  hb_unit?: "g/dL" | null;
  hb_date?: string | null;
  blast_value?: number | null;
  blast_unit?: "%" | null;
  blast_date?: string | null;
  serum_epo_value?: number | null;
  serum_epo_unit?: "mu/ml" | null;
  serum_epo_date?: string | null;
  weekly_dose_value?: number | null;
  weekly_dose_unit?: "IU/kg/week" | null;
  specialist_report_present?: boolean | null;
  report_author_specialty?: "hematology" | "internal_medicine" | "other" | null;
  report_date?: string | null;
  prescribed_by_specialist?: boolean | null;
  prescribed_by_specialty?: "hematology" | "internal_medicine" | "other" | null;
  usage_dose_documented_in_report?: boolean | null;
  usage_duration_documented_in_report?: boolean | null;
  lab_results_dates_documented_in_prescription_or_report?: boolean | null;
  hemogram_date?: string | null;
  hemogram_result_documented_in_prescription?: boolean | null;
  hemogram_date_documented_in_prescription?: boolean | null;
  /** Explicit calendar months; no conversion from days. */
  prescribed_supply_months?: number | null;
}

export interface MdsClinicalDraftRequest {
  drug_name: string;
  selected_rule_id?: string | null;
  drug_claim_date?: string | null;
  observed_icd10_codes?: string[] | null;
  mds_evidence?: MdsEvidence | null;
}

/** No endpoint is registered and no clinical interpretation is released. */
export interface MdsClinicalDraftResponse {
  review_status: "review_required";
  is_draft: true;
  clinical_eligibility_complete: false;
  integration_status: "not_registered";
  inspection_kind: "gated_runtime" | "local_candidate";
  restriction: SutClinicalRestriction | null;
}

/** Parse form text only. Transport below accepts native numbers exclusively. */
export function optionalMdsNumber(value: string): number | null {
  const text = value.trim();
  if (!/^(?:\d+(?:\.\d*)?|\.\d+)$/.test(text)) return null;
  const number = Number(text);
  return Number.isFinite(number) && number >= 0 ? number : null;
}

export function optionalMdsDate(value: unknown): string | null {
  if (typeof value !== "string" || !/^\d{4}-\d{2}-\d{2}$/.test(value)) return null;
  const [year, month, day] = value.split("-").map(Number);
  if (year < 1 || month < 1 || month > 12 || day < 1) return null;
  const leap = year % 4 === 0 && (year % 100 !== 0 || year % 400 === 0);
  const days = [31, leap ? 29 : 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];
  return day <= days[month - 1] ? value : null;
}

const numberFields = [
  "hb_value", "blast_value", "serum_epo_value", "weekly_dose_value", "prescribed_supply_months",
] as const;
const dateFields = [
  "applies_on", "assessment_date", "hb_date", "blast_date", "serum_epo_date", "report_date", "hemogram_date",
] as const;
const booleanFields = [
  "specialist_report_present", "usage_dose_documented_in_report", "usage_duration_documented_in_report",
  "hemogram_result_documented_in_prescription", "hemogram_date_documented_in_prescription", "prescribed_by_specialist",
  "lab_results_dates_documented_in_prescription_or_report",
] as const;
const choices = {
  indication: ["mds_anemia", "ckd_anemia", "other"],
  substance: ["epoetin_alfa", "epoetin_beta"],
  phase: ["initiation", "continuation", "restart"],
  hb_unit: ["g/dL"],
  blast_unit: ["%"],
  serum_epo_unit: ["mu/ml"],
  weekly_dose_unit: ["IU/kg/week"],
  report_author_specialty: ["hematology", "internal_medicine", "other"],
  prescribed_by_specialty: ["hematology", "internal_medicine", "other"],
} as const;

/** Whitelist clinical fields without coercion, aliases, inferred units or dates. */
export function mdsEvidencePayload(value: unknown): MdsEvidence | null {
  if (value == null || typeof value !== "object" || Array.isArray(value)) return null;
  const source = value as Record<string, unknown>;
  const result: Record<string, number | string | boolean | null> = {};
  for (const field of numberFields) {
    const fact = source[field];
    result[field] = typeof fact === "number" && Number.isFinite(fact) && fact >= 0 ? fact : null;
  }
  for (const field of dateFields) result[field] = optionalMdsDate(source[field]);
  for (const field of booleanFields) result[field] = typeof source[field] === "boolean" ? source[field] : null;
  for (const [field, options] of Object.entries(choices)) {
    const fact = source[field];
    result[field] = typeof fact === "string" && (options as readonly string[]).includes(fact) ? fact : null;
  }
  return result as MdsEvidence;
}

/** Local request preparation only. Intentionally performs no network request. */
export function buildMdsClinicalDraftRequest(value: MdsClinicalDraftRequest): MdsClinicalDraftRequest {
  return {
    drug_name: typeof value.drug_name === "string" ? value.drug_name : "",
    selected_rule_id: typeof value.selected_rule_id === "string" ? value.selected_rule_id : null,
    drug_claim_date: optionalMdsDate(value.drug_claim_date),
    observed_icd10_codes: Array.isArray(value.observed_icd10_codes)
      && value.observed_icd10_codes.every(code => typeof code === "string") ? [...value.observed_icd10_codes] : null,
    mds_evidence: mdsEvidencePayload(value.mds_evidence),
  };
}
