import type { SutEnteralEvidence, SutRavulizumabEvidence } from "@/lib/api/clinicalEvidence";
import type { SutGrowthHormoneEvidence, SutSmaEvidence, SutAntifungalEvidence, SutRenalEvidence } from "@/lib/api/clinicalEvidence";

export interface ClinicalField {
  name: string;
  kind: "boolean" | "number" | "date" | "select";
  options?: readonly string[];
  positiveOnly?: boolean;
  max?: number;
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

export function optionalClinicalNumber(value: string, positiveOnly = false, max?: number): number | null {
  if (!value.trim()) return null;
  const number = Number(value);
  return Number.isFinite(number) && (positiveOnly ? number > 0 : number >= 0)
    && (max == null || number <= max) ? number : null;
}

export const clinicalReviewFields = [
  "historical_sut_version", "verified_source_for_service_date", "remaining_sut_clinical_criteria",
  "micafungin_prophylaxis_route", "itraconazole_source_neutrophil_unit_verification",
  "itraconazole_non_solution_EK4E_requirements", "source_supported_treatment_phase",
  "source_continuation_checkpoint", "supported_renal_indication", "single_supported_medicine_family",
  "phosphate_binding_indication", "renal_nutrition_indication", "valid_ckd_stage",
  "positive_baseline_albumin_g_dl",
  "pws_initiation_clinical_assessment", "pws_remaining_clinical_criteria",
  "exception_path_requires_review", "adult_path_requires_review", "six_month_edss_stop",
] as const;

export const smaFields = [
  { name: "applies_on", kind: "date" },
  { name: "assessment_date", kind: "date" },
  { name: "sma_type", kind: "select", options: ["newborn_screening", "type_1", "type_2", "type_3"] },
  { name: "brain_spinal_history_impeding_procedure", kind: "boolean" },
  { name: "csf_shunt_or_catheter", kind: "boolean" },
  { name: "bacterial_meningitis_history", kind: "boolean" },
  { name: "viral_encephalitis_history", kind: "boolean" },
  { name: "hypoxic_ischemic_encephalopathy", kind: "boolean" },
  { name: "hypoxic_birth_neurological_sequelae", kind: "boolean" },
  { name: "lumbar_puncture_suitability_documented", kind: "boolean" },
] satisfies Array<ClinicalField & { name: keyof SutSmaEvidence }>;

export const antifungalFields = [
  { name: "applies_on", kind: "date" },
  { name: "assessment_date", kind: "date" },
  { name: "intent", kind: "select", options: ["prophylaxis", "treatment"] },
  { name: "indication", kind: "select", options: ["aspergillus_candida_prophylaxis", "chromoblastomycosis", "coccidioidomycosis", "esophageal_candidiasis", "fusariosis", "invasive_aspergillosis", "invasive_candidiasis", "mycetoma", "oropharyngeal_candidiasis", "other"] },
  { name: "formulation", kind: "select", options: ["oral_solution", "oral_suspension", "oral_tablet", "parenteral"] },
  { name: "adult", kind: "boolean" },
  { name: "anc_per_mm3", kind: "number" },
  { name: "anc_lab_result_present", kind: "boolean" },
  { name: "high_invasive_fungal_risk", kind: "boolean" },
  { name: "aml_or_mds", kind: "boolean" },
  { name: "remission_induction_chemotherapy", kind: "boolean" },
  { name: "prolonged_neutropenia_expected", kind: "boolean" },
  { name: "allogeneic_hsct", kind: "boolean" },
  { name: "autologous_hsct", kind: "boolean" },
  { name: "acute_lymphoblastic_leukemia", kind: "boolean" },
  { name: "gvhd_high_dose_immunosuppression", kind: "boolean" },
  { name: "oral_form_unusable", kind: "boolean" },
  { name: "current_neutropenia", kind: "boolean" },
  { name: "neutropenia_end_date", kind: "date" },
  { name: "mucositis", kind: "boolean" },
  { name: "expected_neutropenia_days", kind: "number" },
  { name: "hematological_malignancy", kind: "boolean" },
  { name: "bone_marrow_transplant", kind: "boolean" },
  { name: "hiv_positive", kind: "boolean" },
  { name: "immunodeficiency", kind: "boolean" },
  { name: "fluconazole_resistant", kind: "boolean" },
  { name: "amphotericin_b_refractory", kind: "boolean" },
  { name: "amphotericin_b_intolerant", kind: "boolean" },
  { name: "liposomal_amphotericin_b_refractory", kind: "boolean" },
  { name: "voriconazole_refractory", kind: "boolean" },
  { name: "itraconazole_refractory", kind: "boolean" },
  { name: "itraconazole_intolerant", kind: "boolean" },
  { name: "fluconazole_refractory", kind: "boolean" },
  { name: "fluconazole_intolerant", kind: "boolean" },
] satisfies Array<ClinicalField & { name: keyof SutAntifungalEvidence }>;

export const renalFields = [
  { name: "applies_on", kind: "date" },
  { name: "assessment_date", kind: "date" },
  { name: "phase", kind: "select", options: ["continuation", "initiation", "restart"] },
  { name: "indication", kind: "select", options: ["dialysis_shpt", "other", "phosphate_binding", "primary_hpt", "renal_nutrition"] },
  { name: "dialysis", kind: "boolean" },
  { name: "other_phosphate_therapy_months", kind: "number" },
  { name: "calcium_phosphorus_product", kind: "number" },
  { name: "corrected_calcium_phosphorus_product", kind: "number" },
  { name: "pth_pg_ml", kind: "number" },
  { name: "adynamic_bone_disease", kind: "boolean" },
  { name: "kt_v", kind: "number" },
  { name: "phosphorus_mg_dl", kind: "number" },
  { name: "corrected_calcium_mg_dl", kind: "number" },
  { name: "parathyroidectomy_indicated", kind: "boolean" },
  { name: "parathyroidectomy_unsuitable_or_contraindicated", kind: "boolean" },
  { name: "asa_iv", kind: "boolean" },
  { name: "postsurgical_recurrence", kind: "boolean" },
  { name: "bisphosphonate_failed", kind: "boolean" },
  { name: "albumin_g_dl", kind: "number" },
  { name: "baseline_albumin_g_dl", kind: "number" },
  { name: "six_month_albumin_g_dl", kind: "number" },
  { name: "ckd_stage", kind: "number" },
  { name: "gfr_ml_min", kind: "number" },
  { name: "weight_loss_last_3_months_percent", kind: "number" },
  { name: "bmi", kind: "number" },
  { name: "therapy_months", kind: "number" },
] satisfies Array<ClinicalField & { name: keyof SutRenalEvidence }>;

export function clinicalMissingInputLabel(field: string, t: (key: string) => string): string | null {
  const [root, detail] = field.split(".");
  const groups: Record<string, string> = {
    sma_evidence: "sma", antifungal_evidence: "antifungal", renal_evidence: "renal",
    enteral_evidence: "enteral", ravulizumab_evidence: "ravulizumab",
  };
  if (groups[root]) {
    const groupLabel = t(`sections.claimValidator.clinical.groups.${groups[root]}`);
    return detail ? `${groupLabel}: ${t(`sections.claimValidator.clinical.fields.${detail}`)}` : groupLabel;
  }
  if ([...growthHormoneFields, ...praderWilliFields].some(row => row.name === root) || clinicalReviewFields.some(name => name === root)) {
    return t(`sections.claimValidator.clinical.fields.${root}`);
  }
  return null;
}

export const enteralFields = [
  { name: "applies_on", kind: "date" },
  { name: "assessment_date", kind: "date" },
  { name: "pediatric", kind: "boolean" },
  { name: "phase", kind: "select", options: ["initiation", "renewal"] },
  { name: "malnutrition_path", kind: "select", options: ["exemption", "malnutrition"] },
  { name: "neurological_disease", kind: "boolean" },
  { name: "malnutrition_criteria_met", kind: "boolean" },
  { name: "specialist_report_present", kind: "boolean" },
  { name: "report_author_specialty", kind: "select", options: ["other", "pediatric_endocrinology", "pediatric_endocrinology_metabolism", "pediatric_gastroenterology", "pediatric_metabolism", "pediatric_neurology", "pediatric_surgery", "pediatrics"] },
] satisfies Array<ClinicalField & { name: keyof SutEnteralEvidence }>;

export const ravulizumabFields = [
  { name: "applies_on", kind: "date" },
  { name: "assessment_date", kind: "date" },
  { name: "indication", kind: "select", options: ["ahus", "nmosd", "pnh"] },
  { name: "adult", kind: "boolean" },
  { name: "therapy_months", kind: "number" },
  { name: "edss", kind: "number", max: 10 },
  { name: "edss_in_report", kind: "boolean" },
] satisfies Array<ClinicalField & { name: keyof SutRavulizumabEvidence }>;
