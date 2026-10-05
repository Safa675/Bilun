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
  gh_initiation_pathway?: "standard" | "neurosecretory_bioinactive" | "organic_or_surgical" | "sga_case_1" | "sga_case_2" | null;
  gh_reported_growth_age_band?: "0_2_years" | "2_1_4_years" | "4_1_prepubertal" | "pubertal" | null;
  gh_chronological_age_years?: number | null;
  /** Clinician-recorded assessment using SUT §4.2.6.A-1(1)(b)(3): onset is testicular volume >=4 ml in boys or T2 thelarche in girls. Enter prepubertal/pubertal only when the recorded assessment uses that definition; otherwise leave unknown. Do not infer from age, diagnosis or height-reference sex; no raw measurements are requested. */
  gh_pubertal_status?: "prepubertal" | "pubertal" | null;
  gh_pubertal_growth_assessment_completed?: boolean | null;
  gh_birth_weight_for_gestational_age_sds?: number | null;
  gh_birth_length_for_gestational_age_sds?: number | null;
  gh_last_year_growth_velocity_sds?: number | null;
  gh_current_height_sds?: number | null;
  gh_parent_adjusted_height_sds?: number | null;
  gh_sga_birth_status_confirmed?: boolean | null;
  ckd_height_age_sex_percentile?: number | null;
  ckd_height_age_sex_sds?: number | null;
  ckd_annual_growth_velocity_percentile?: number | null;
  ckd_persistent_growth_failure_confirmed?: boolean | null;
  ckd_post_transplant_one_year_elapsed?: boolean | null;
  ckd_steroid_treatment_absent?: boolean | null;
  ckd_spontaneous_growth_absent?: boolean | null;
  ckd_nephropathic_cystinosis_related_confirmed?: boolean | null;
}

export interface SutDatedClinicalEvidence {
  applies_on?: string | null;
  assessment_date?: string | null;
}

/** Experimental documentary facts only; source/date admission and independent interpretation remain pending. */
export interface SutMesotheliomaEvidence extends SutDatedClinicalEvidence {
  /** Explicit recorded site; C45 alone does not establish pleural disease. */
  diagnosis_site?: "pleural" | "nonpleural" | "unknown" | null;
  board_report_present?: boolean | null;
  /** Recorded distinct specialists, an integer; composition is never inferred from report presence. */
  report_distinct_specialist_count?: number | null;
  treatment_protocol_documented_in_report?: boolean | null;
  /** Explicit specialist-prescribing fact, separate from the generic specialty string. */
  prescribed_by_specialist?: boolean | null;
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
  risdiplam_treatment_period?: "not_started" | "during_treatment" | null;
  risdiplam_motor_monitoring_assessment_documented?: boolean | null;
  risdiplam_cognitive_monitoring_assessment_documented?: boolean | null;
  risdiplam_nutritional_monitoring_assessment_documented?: boolean | null;
  risdiplam_respiratory_monitoring_assessment_documented?: boolean | null;
  risdiplam_rehabilitation_monitoring_assessment_documented?: boolean | null;
  risdiplam_orthopedic_monitoring_assessment_documented?: boolean | null;
  risdiplam_monitoring_assessment_in_health_board_report?: boolean | null;
}

export interface SutAntifungalEvidence {
  applies_on?: string | null;
  assessment_date?: string | null;
  intent?: "prophylaxis" | "treatment" | null;
  indication?: "aspergillus_candida_prophylaxis" | "chromoblastomycosis" | "coccidioidomycosis" | "esophageal_candidiasis" | "fusariosis" | "invasive_aspergillosis" | "invasive_candidiasis" | "mycetoma" | "oropharyngeal_candidiasis" | "deep_fungal_infection_prophylaxis" | "other" | null;
  formulation?: "oral_solution" | "oral_suspension" | "oral_tablet" | "parenteral" | null;
  adult?: boolean | null;
  anc_per_mm3?: number | null;
  anc_lab_result_present?: boolean | null;
  high_invasive_fungal_risk?: boolean | null;
  aml_or_mds?: boolean | null;
  remission_induction_chemotherapy?: boolean | null;
  prolonged_neutropenia_expected?: boolean | null;
  neutropenia_development_expected?: boolean | null;
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
  /** Report documents at least three months of prior phosphate-lowering therapy. */
  prior_phosphate_therapy_documented_in_report?: boolean | null;
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
  /** Initiating specialist report states the malnutrition conditions. */
  malnutrition_conditions_documented_in_report?: boolean | null;
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

/** Admission is restricted to the named necessary clinical/report checks. */
export interface SutClinicalSourceAuthority {
  schema_version: 1;
  status: "admitted" | "review_required";
  reason: "covered" | "missing_service_date" | "uncovered_service_date" | "source_authority_unavailable" | "source_content_changed" | "known_successor";
  family_id: string;
  version_id?: string | null;
  service_date?: string | null;
  legal_effective_from?: string | null;
  admission_basis?: "established_history" | "observed_snapshot" | "reviewed_continuity" | null;
  admitted_from?: string | null;
  admitted_through?: string | null;
  source_observed_on?: string | null;
  official_review_checked_at?: string | null;
  source_docx_sha256?: string | null;
  review_id?: string | null;
  next_action: string;
  scope: "named_clinical_report_checks_only";
  clinical_eligibility_complete: false;
  verification_status: "ai_generated_pending_review";
}

/** Bounded identifiers/statuses only; no raw medical values or payment conclusion. */
export interface SutClinicalRestriction {
  source_authority?: SutClinicalSourceAuthority | null;
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

export interface SutFollowupEvidence {
  applies_on?: string | null;
  assessment_date?: string | null;
  phase?: "continuation" | "initiation" | "restart" | null;
  indication?: "atopic_dermatitis" | "other" | "progressive_fibrosing_ild" | "systemic_sclerosis_ild" | null;
  treatment_start_date?: string | null;
  baseline_assessment_date?: string | null;
  response_assessment_date?: string | null;
  week16_checkpoint_documented?: boolean | null;
  baseline_easi?: number | null;
  response_easi?: number | null;
  baseline_dlqi?: number | null;
  response_dlqi?: number | null;
  baseline_pruritus_nrs?: number | null;
  response_pruritus_nrs?: number | null;
  previous_report_date?: string | null;
  current_report_date?: string | null;
  previous_fvc_percent_predicted?: number | null;
  current_fvc_percent_predicted?: number | null;
  fvc_assessment_outside_exacerbation?: boolean | null;
  report_documents_fvc_response?: boolean | null;
}

export interface SutIndicationEvidence {
  applies_on?: string | null;
  assessment_date?: string | null;
  phase?: "continuation" | "initiation" | "restart" | null;
  indication?: "glucocorticoid_bone_loss" | "hbv_initiation_path_a" | "other" | "pediatric_chronic_hcv" | "sc_ig_allogeneic_hsct" | "sc_ig_cll" | "sc_ig_mm" | null;
  administration_route?: "intramuscular" | "intravenous" | "oral" | "other" | "subcutaneous" | null;
  age_group?: "adult" | "age_2_18" | "child" | "other" | null;
  hypogammaglobulinemia?: boolean | null;
  recurrent_bacterial_infections?: boolean | null;
  prophylactic_antibiotics_failed?: boolean | null;
  prophylactic_antibiotics_contraindicated?: boolean | null;
  allogeneic_hsct_before_or_after?: boolean | null;
  report_author_specialty?: "hematology" | "other" | "pediatric_hematology_oncology" | null;
  prescribed_supply_months?: number | null;
  hbv_dna_iu_ml?: number | null;
  biopsy_scoring_system?: "ishak_modified_hai" | "knodell_hai" | "metavir" | "other" | null;
  biopsy_hai?: number | null;
  biopsy_fibrosis_stage?: number | null;
  first_alt_uln_ratio?: number | null;
  second_alt_uln_ratio?: number | null;
  first_alt_date?: string | null;
  second_alt_date?: string | null;
  fib4_score?: number | null;
  apri_score?: number | null;
  hcv_rna_positive?: boolean | null;
  hcv_genotype_result_present?: boolean | null;
  osteoporosis_diagnosed?: boolean | null;
  high_fracture_risk?: boolean | null;
  long_term_glucocorticoid_treatment?: boolean | null;
  glucocorticoid_associated_bone_loss?: boolean | null;
  bisphosphonate_intolerant?: boolean | null;
  bisphosphonate_inadequate_response?: boolean | null;
  bisphosphonate_renal_contraindication?: boolean | null;
}
