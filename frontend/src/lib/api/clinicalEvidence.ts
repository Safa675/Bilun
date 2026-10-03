/** Explicit source-specific facts. Null never asserts a negative clinical finding. */
export interface SutGrowthHormoneEvidence {
  mecasermin_laron_syndrome_confirmed?: boolean | null;
  pretreatment_annual_growth_velocity_cm?: number | null;
  height_percentile?: number | null;
  mecasermin_daily_dose_mcg_per_kg?: number | null;
  ckd_growth_disorder_confirmed?: boolean | null;
  ckd_persistent_severe_secondary_hyperparathyroidism?: boolean | null;
  ckd_proliferative_or_severe_nonproliferative_retinopathy?: boolean | null;
  ckd_first_post_transplant_year?: boolean | null;
  ckd_active_cancer?: boolean | null;
  ckd_parathyroid_hormone_pg_ml?: number | null;
  gh_daily_dose_mg_per_kg?: number | null;
  pws_genetic_diagnosis_confirmed?: boolean | null;
  pws_uncontrolled_diabetes?: boolean | null;
  pws_untreatable_obstructive_sleep_apnea?: boolean | null;
  pws_active_cancer?: boolean | null;
  pws_active_psychosis?: boolean | null;
  pws_progressive_scoliosis?: boolean | null;
  pws_severe_obesity_source_criterion_present?: boolean | null;
  gh_patient_group?: "pediatric" | "adult" | null;
  gh_height_reference_sex?: "female" | "male" | null;
  gh_treatment_phase?: "initiation" | "continuation" | null;
  epiphyses_closed?: boolean | null;
  annual_growth_velocity_cm?: number | null;
  height_cm?: number | null;
  bone_age_years?: number | null;
}

export interface SutDatedClinicalEvidence {
  applies_on?: string | null;
  assessment_date?: string | null;
}

export interface SutSmaEvidence {
  applies_on?: string | null;
  assessment_date?: string | null;
  sma_type?: "newborn_screening" | "type_1" | "type_2" | "type_3" | null;
  brain_spinal_history_impeding_procedure?: boolean | null;
  csf_shunt_or_catheter?: boolean | null;
  bacterial_meningitis_history?: boolean | null;
  viral_encephalitis_history?: boolean | null;
  hypoxic_ischemic_encephalopathy?: boolean | null;
  hypoxic_birth_neurological_sequelae?: boolean | null;
  lumbar_puncture_suitability_documented?: boolean | null;
}

export interface SutAntifungalEvidence {
  applies_on?: string | null;
  assessment_date?: string | null;
  intent?: "prophylaxis" | "treatment" | null;
  indication?: "aspergillus_candida_prophylaxis" | "chromoblastomycosis" | "coccidioidomycosis" | "esophageal_candidiasis" | "fusariosis" | "invasive_aspergillosis" | "invasive_candidiasis" | "mycetoma" | "oropharyngeal_candidiasis" | "other" | null;
  formulation?: "oral_solution" | "oral_suspension" | "oral_tablet" | "parenteral" | null;
  adult?: boolean | null;
  anc_per_mm3?: number | null;
  anc_lab_result_present?: boolean | null;
  high_invasive_fungal_risk?: boolean | null;
  aml_or_mds?: boolean | null;
  remission_induction_chemotherapy?: boolean | null;
  prolonged_neutropenia_expected?: boolean | null;
  allogeneic_hsct?: boolean | null;
  autologous_hsct?: boolean | null;
  acute_lymphoblastic_leukemia?: boolean | null;
  gvhd_high_dose_immunosuppression?: boolean | null;
  oral_form_unusable?: boolean | null;
  current_neutropenia?: boolean | null;
  neutropenia_end_date?: string | null;
  mucositis?: boolean | null;
  expected_neutropenia_days?: number | null;
  hematological_malignancy?: boolean | null;
  bone_marrow_transplant?: boolean | null;
  hiv_positive?: boolean | null;
  immunodeficiency?: boolean | null;
  fluconazole_resistant?: boolean | null;
  amphotericin_b_refractory?: boolean | null;
  amphotericin_b_intolerant?: boolean | null;
  liposomal_amphotericin_b_refractory?: boolean | null;
  voriconazole_refractory?: boolean | null;
  itraconazole_refractory?: boolean | null;
  itraconazole_intolerant?: boolean | null;
  fluconazole_refractory?: boolean | null;
  fluconazole_intolerant?: boolean | null;
}

export interface SutRenalEvidence {
  applies_on?: string | null;
  assessment_date?: string | null;
  phase?: "continuation" | "initiation" | "restart" | null;
  indication?: "dialysis_shpt" | "other" | "phosphate_binding" | "primary_hpt" | "renal_nutrition" | null;
  dialysis?: boolean | null;
  other_phosphate_therapy_months?: number | null;
  calcium_phosphorus_product?: number | null;
  corrected_calcium_phosphorus_product?: number | null;
  pth_pg_ml?: number | null;
  adynamic_bone_disease?: boolean | null;
  kt_v?: number | null;
  phosphorus_mg_dl?: number | null;
  corrected_calcium_mg_dl?: number | null;
  parathyroidectomy_indicated?: boolean | null;
  parathyroidectomy_unsuitable_or_contraindicated?: boolean | null;
  asa_iv?: boolean | null;
  postsurgical_recurrence?: boolean | null;
  bisphosphonate_failed?: boolean | null;
  albumin_g_dl?: number | null;
  baseline_albumin_g_dl?: number | null;
  six_month_albumin_g_dl?: number | null;
  ckd_stage?: number | null;
  gfr_ml_min?: number | null;
  weight_loss_last_3_months_percent?: number | null;
  bmi?: number | null;
  therapy_months?: number | null;
}

export interface SutEnteralEvidence {
  applies_on?: string | null;
  assessment_date?: string | null;
  pediatric?: boolean | null;
  phase?: "initiation" | "renewal" | null;
  malnutrition_path?: "exemption" | "malnutrition" | null;
  neurological_disease?: boolean | null;
  malnutrition_criteria_met?: boolean | null;
  specialist_report_present?: boolean | null;
  report_author_specialty?: "other" | "pediatric_endocrinology" | "pediatric_endocrinology_metabolism" | "pediatric_gastroenterology" | "pediatric_metabolism" | "pediatric_neurology" | "pediatric_surgery" | "pediatrics" | null;
}

export interface SutRavulizumabEvidence {
  applies_on?: string | null;
  assessment_date?: string | null;
  indication?: "ahus" | "nmosd" | "pnh" | null;
  adult?: boolean | null;
  therapy_months?: number | null;
  edss?: number | null;
  edss_in_report?: boolean | null;
}

/** Bounded identifiers/statuses only; no raw medical values or payment conclusion. */
export interface SutClinicalRestriction {
  constraint_set: string;
  criterion_status: "not_evaluated" | "unknown" | "criterion_clear" | "restriction_not_met";
  missing_inputs: string[];
  checks: Array<{ field: string; status: "pass" | "fail" | "unknown" }>;
  source_refs: string[];
  clinical_eligibility_complete: false;
  verification_status: "ai_generated_pending_review";
  checks_truncated: boolean;
  source_refs_truncated: boolean;
}
