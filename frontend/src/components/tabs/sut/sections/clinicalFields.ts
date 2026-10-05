import type { SutIndicationEvidence } from "@/lib/api/clinicalEvidence";
import type { SutFollowupEvidence } from "@/lib/api/clinicalEvidence";
import type { SutEnteralEvidence, SutRavulizumabEvidence, SutMesotheliomaEvidence } from "@/lib/api/clinicalEvidence";
import type { SutGrowthHormoneEvidence, SutSmaEvidence, SutAntifungalEvidence, SutRenalEvidence } from "@/lib/api/clinicalEvidence";

export interface ClinicalField {
  name: string;
  kind: "boolean" | "number" | "date" | "select";
  options?: readonly string[];
  positiveOnly?: boolean;
  max?: number;
  signed?: boolean;
  integerOnly?: boolean;
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
  { name: "pws_severe_obesity_source_criterion_present", kind: "boolean" },
] satisfies Array<ClinicalField & { name: keyof SutGrowthHormoneEvidence }>;

export const ckdGrowthHormoneFields = [
  { name: "ckd_growth_disorder_confirmed", kind: "boolean" },
  { name: "ckd_persistent_severe_secondary_hyperparathyroidism", kind: "boolean" },
  { name: "ckd_proliferative_or_severe_nonproliferative_retinopathy", kind: "boolean" },
  { name: "ckd_first_post_transplant_year", kind: "boolean" },
  { name: "ckd_active_cancer", kind: "boolean" },
  { name: "ckd_parathyroid_hormone_pg_ml", kind: "number" },
  { name: "gh_daily_dose_mg_per_kg", kind: "number" },
] satisfies Array<ClinicalField & { name: keyof SutGrowthHormoneEvidence }>;

export const mecaserminFields = [
  { name: "mecasermin_laron_syndrome_confirmed", kind: "boolean" },
  { name: "pretreatment_annual_growth_velocity_cm", kind: "number" },
  { name: "height_percentile", kind: "number", max: 100 },
  { name: "mecasermin_daily_dose_mcg_per_kg", kind: "number" },
] satisfies Array<ClinicalField & { name: keyof SutGrowthHormoneEvidence }>;

export function optionalClinicalNumber(value: string, positiveOnly = false, max?: number, signed = false, integerOnly = false): number | null {
  if (!value.trim()) return null;
  const number = Number(value);
  return Number.isFinite(number) && (positiveOnly ? number > 0 : signed || number >= 0)
    && (max == null || number <= max) && (!integerOnly || Number.isSafeInteger(number)) ? number : null;
}

export const clinicalReviewFields = [
  "risdiplam_age_disease_assessment_standards_review", "histology_scoring_source_compatibility", "hbv_noninvasive_boolean_grouping",
  "documented_16_week_response",
  "historical_sut_version", "verified_source_for_service_date", "remaining_sut_clinical_criteria",
  "micafungin_prophylaxis_route", "itraconazole_source_neutrophil_unit_verification",
  "itraconazole_non_solution_EK4E_requirements", "source_supported_treatment_phase",
  "source_continuation_checkpoint", "supported_renal_indication", "single_supported_medicine_family",
  "phosphate_binding_indication", "renal_nutrition_indication", "valid_ckd_stage",
  "positive_baseline_albumin_g_dl",
  "pws_initiation_clinical_assessment", "pws_remaining_clinical_criteria",
  "exception_path_requires_review", "adult_path_requires_review", "six_month_edss_stop",
  "ckd_growth_initiation_clinical_assessment", "ckd_growth_continuation_clinical_assessment", "ckd_parathyroid_status_reconciliation",
  "mecasermin_source_version", "mecasermin_remaining_clinical_criteria",
  "gh_initiation_clinical_assessment", "gh_growth_stage_reconciliation",
  "ckd_height_source_notation_verification", "ckd_height_reference_reconciliation", "ckd_transplant_timing_reconciliation",
  "mesothelioma_documentary_interpretation_release",
] as const;

export const mesotheliomaFields = [
  { name: "applies_on", kind: "date" },
  { name: "assessment_date", kind: "date" },
  { name: "diagnosis_site", kind: "select", options: ["pleural", "nonpleural", "unknown"] },
  { name: "board_report_present", kind: "boolean" },
  { name: "report_distinct_specialist_count", kind: "number", integerOnly: true },
  { name: "treatment_protocol_documented_in_report", kind: "boolean" },
  { name: "prescribed_by_specialist", kind: "boolean" },
] satisfies Array<ClinicalField & { name: keyof SutMesotheliomaEvidence }>;

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
  { name: "risdiplam_treatment_period", kind: "select", options: ["not_started", "during_treatment"] },
  { name: "risdiplam_motor_monitoring_assessment_documented", kind: "boolean" },
  { name: "risdiplam_cognitive_monitoring_assessment_documented", kind: "boolean" },
  { name: "risdiplam_nutritional_monitoring_assessment_documented", kind: "boolean" },
  { name: "risdiplam_respiratory_monitoring_assessment_documented", kind: "boolean" },
  { name: "risdiplam_rehabilitation_monitoring_assessment_documented", kind: "boolean" },
  { name: "risdiplam_orthopedic_monitoring_assessment_documented", kind: "boolean" },
  { name: "risdiplam_monitoring_assessment_in_health_board_report", kind: "boolean" },
] satisfies Array<ClinicalField & { name: keyof SutSmaEvidence }>;

export const antifungalFields = [
  { name: "applies_on", kind: "date" },
  { name: "assessment_date", kind: "date" },
  { name: "intent", kind: "select", options: ["prophylaxis", "treatment"] },
  { name: "indication", kind: "select", options: ["aspergillus_candida_prophylaxis", "chromoblastomycosis", "coccidioidomycosis", "esophageal_candidiasis", "fusariosis", "invasive_aspergillosis", "invasive_candidiasis", "mycetoma", "oropharyngeal_candidiasis", "deep_fungal_infection_prophylaxis", "other"] },
  { name: "formulation", kind: "select", options: ["oral_solution", "oral_suspension", "oral_tablet", "parenteral"] },
  { name: "adult", kind: "boolean" },
  { name: "anc_per_mm3", kind: "number" },
  { name: "anc_lab_result_present", kind: "boolean" },
  { name: "high_invasive_fungal_risk", kind: "boolean" },
  { name: "aml_or_mds", kind: "boolean" },
  { name: "remission_induction_chemotherapy", kind: "boolean" },
  { name: "prolonged_neutropenia_expected", kind: "boolean" },
  { name: "neutropenia_development_expected", kind: "boolean" },
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
  { name: "prior_phosphate_therapy_documented_in_report", kind: "boolean" },
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
    followup_evidence: "followup", indication_evidence: "indication", sma_evidence: "sma", antifungal_evidence: "antifungal", renal_evidence: "renal",
    enteral_evidence: "enteral", ravulizumab_evidence: "ravulizumab",
    mesothelioma_evidence: "mesothelioma",
  };
  if (groups[root]) {
    const groupLabel = t(`sections.claimValidator.clinical.groups.${groups[root]}`);
    return detail ? `${groupLabel}: ${t(`sections.claimValidator.clinical.fields.${detail}`)}` : groupLabel;
  }
  if ([...growthHormoneFields, ...praderWilliFields, ...ckdGrowthHormoneFields, ...mecaserminFields, ...pediatricInitiationFields, ...ckdGrowthPathwayFields].some(row => row.name === root) || clinicalReviewFields.some(name => name === root)) {
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
  { name: "malnutrition_conditions_documented_in_report", kind: "boolean" },
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

export const followupFields = [
  { name: "applies_on", kind: "date" },
  { name: "assessment_date", kind: "date" },
  { name: "phase", kind: "select", options: ["continuation", "initiation", "restart"] },
  { name: "indication", kind: "select", options: ["atopic_dermatitis", "other", "progressive_fibrosing_ild", "systemic_sclerosis_ild"] },
  { name: "treatment_start_date", kind: "date" },
  { name: "baseline_assessment_date", kind: "date" },
  { name: "response_assessment_date", kind: "date" },
  { name: "week16_checkpoint_documented", kind: "boolean" },
  { name: "baseline_easi", kind: "number", max: 72 },
  { name: "response_easi", kind: "number", max: 72 },
  { name: "baseline_dlqi", kind: "number", max: 30 },
  { name: "response_dlqi", kind: "number", max: 30 },
  { name: "baseline_pruritus_nrs", kind: "number", max: 10 },
  { name: "response_pruritus_nrs", kind: "number", max: 10 },
  { name: "previous_report_date", kind: "date" },
  { name: "current_report_date", kind: "date" },
  { name: "previous_fvc_percent_predicted", kind: "number" },
  { name: "current_fvc_percent_predicted", kind: "number" },
  { name: "fvc_assessment_outside_exacerbation", kind: "boolean" },
  { name: "report_documents_fvc_response", kind: "boolean" },
] satisfies Array<ClinicalField & { name: keyof SutFollowupEvidence }>;

export const indicationFields = [
  { name: "applies_on", kind: "date" },
  { name: "assessment_date", kind: "date" },
  { name: "phase", kind: "select", options: ["continuation", "initiation", "restart"] },
  { name: "indication", kind: "select", options: ["glucocorticoid_bone_loss", "hbv_initiation_path_a", "other", "pediatric_chronic_hcv", "sc_ig_allogeneic_hsct", "sc_ig_cll", "sc_ig_mm"] },
  { name: "administration_route", kind: "select", options: ["intramuscular", "intravenous", "oral", "other", "subcutaneous"] },
  { name: "age_group", kind: "select", options: ["adult", "age_2_18", "child", "other"] },
  { name: "hypogammaglobulinemia", kind: "boolean" },
  { name: "recurrent_bacterial_infections", kind: "boolean" },
  { name: "prophylactic_antibiotics_failed", kind: "boolean" },
  { name: "prophylactic_antibiotics_contraindicated", kind: "boolean" },
  { name: "allogeneic_hsct_before_or_after", kind: "boolean" },
  { name: "report_author_specialty", kind: "select", options: ["hematology", "other", "pediatric_hematology_oncology"] },
  { name: "prescribed_supply_months", kind: "number" },
  { name: "hbv_dna_iu_ml", kind: "number" },
  { name: "biopsy_scoring_system", kind: "select", options: ["ishak_modified_hai", "knodell_hai", "metavir", "other"] },
  { name: "biopsy_hai", kind: "number", max: 22 },
  { name: "biopsy_fibrosis_stage", kind: "number", max: 6 },
  { name: "first_alt_uln_ratio", kind: "number" },
  { name: "second_alt_uln_ratio", kind: "number" },
  { name: "first_alt_date", kind: "date" },
  { name: "second_alt_date", kind: "date" },
  { name: "fib4_score", kind: "number" },
  { name: "apri_score", kind: "number" },
  { name: "hcv_rna_positive", kind: "boolean" },
  { name: "hcv_genotype_result_present", kind: "boolean" },
  { name: "osteoporosis_diagnosed", kind: "boolean" },
  { name: "high_fracture_risk", kind: "boolean" },
  { name: "long_term_glucocorticoid_treatment", kind: "boolean" },
  { name: "glucocorticoid_associated_bone_loss", kind: "boolean" },
  { name: "bisphosphonate_intolerant", kind: "boolean" },
  { name: "bisphosphonate_inadequate_response", kind: "boolean" },
  { name: "bisphosphonate_renal_contraindication", kind: "boolean" },
] satisfies Array<ClinicalField & { name: keyof SutIndicationEvidence }>;

export const pediatricInitiationFields = [
  { name: "gh_initiation_pathway", kind: "select", options: ["standard", "neurosecretory_bioinactive", "organic_or_surgical", "sga_case_1", "sga_case_2"] },
  { name: "gh_reported_growth_age_band", kind: "select", options: ["0_2_years", "2_1_4_years", "4_1_prepubertal", "pubertal"] },
  { name: "gh_chronological_age_years", kind: "number" },
  { name: "gh_pubertal_status", kind: "select", options: ["prepubertal", "pubertal"] },
  { name: "gh_pubertal_growth_assessment_completed", kind: "boolean" },
  { name: "gh_birth_weight_for_gestational_age_sds", kind: "number", signed: true },
  { name: "gh_birth_length_for_gestational_age_sds", kind: "number", signed: true },
  { name: "gh_last_year_growth_velocity_sds", kind: "number", signed: true },
  { name: "gh_current_height_sds", kind: "number", signed: true },
  { name: "gh_parent_adjusted_height_sds", kind: "number", signed: true },
  { name: "gh_sga_birth_status_confirmed", kind: "boolean" },
] satisfies Array<ClinicalField & { name: keyof SutGrowthHormoneEvidence }>;

export const ckdGrowthPathwayFields = [
  { name: "ckd_height_age_sex_percentile", kind: "number", max: 100 },
  { name: "ckd_height_age_sex_sds", kind: "number", signed: true },
  { name: "ckd_annual_growth_velocity_percentile", kind: "number", max: 100 },
  { name: "ckd_persistent_growth_failure_confirmed", kind: "boolean" },
  { name: "ckd_post_transplant_one_year_elapsed", kind: "boolean" },
  { name: "ckd_steroid_treatment_absent", kind: "boolean" },
  { name: "ckd_spontaneous_growth_absent", kind: "boolean" },
  { name: "ckd_nephropathic_cystinosis_related_confirmed", kind: "boolean" },
] satisfies Array<ClinicalField & { name: keyof SutGrowthHormoneEvidence }>;
