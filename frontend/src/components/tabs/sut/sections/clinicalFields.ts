import type { SutGrowthHormoneEvidence } from "@/lib/api/clinicalEvidence";

export interface ClinicalField {
  name: string;
  kind: "boolean" | "number" | "date" | "select";
  options?: readonly string[];
  positiveOnly?: boolean;
}

export const growthHormoneFields = [
  { name: "gh_patient_group", kind: "select", options: ["pediatric", "adult"] },
  { name: "gh_height_reference_sex", kind: "select", options: ["female", "male"] },
  { name: "gh_treatment_phase", kind: "select", options: ["initiation", "continuation"] },
  { name: "epiphyses_closed", kind: "boolean" },
  { name: "annual_growth_velocity_cm", kind: "number" },
  { name: "height_cm", kind: "number", positiveOnly: true },
  { name: "bone_age_years", kind: "number" },
] satisfies Array<ClinicalField & { name: keyof SutGrowthHormoneEvidence }>;

export const praderWilliFields = [
  { name: "pws_genetic_diagnosis_confirmed", kind: "boolean" },
  { name: "pws_uncontrolled_diabetes", kind: "boolean" },
  { name: "pws_untreatable_obstructive_sleep_apnea", kind: "boolean" },
  { name: "pws_active_cancer", kind: "boolean" },
  { name: "pws_active_psychosis", kind: "boolean" },
  { name: "pws_progressive_scoliosis", kind: "boolean" },
] satisfies Array<ClinicalField & { name: keyof SutGrowthHormoneEvidence }>;

export function optionalClinicalNumber(value: string, positiveOnly = false): number | null {
  if (!value.trim()) return null;
  const number = Number(value);
  return Number.isFinite(number) && (positiveOnly ? number > 0 : number >= 0) ? number : null;
}

export const clinicalReviewFields = ["historical_sut_version", "pws_initiation_clinical_assessment", "pws_remaining_clinical_criteria"] as const;

export function clinicalMissingInputLabel(field: string, t: (key: string) => string): string | null {
  if ([...growthHormoneFields, ...praderWilliFields].some(row => row.name === field) || clinicalReviewFields.some(name => name === field)) {
    return t(`sections.claimValidator.clinical.fields.${field}`);
  }
  return null;
}
