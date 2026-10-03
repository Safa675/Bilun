/** Explicit source-specific facts. Null never asserts a negative clinical finding. */
export interface SutGrowthHormoneEvidence {
  pws_genetic_diagnosis_confirmed?: boolean | null;
  pws_uncontrolled_diabetes?: boolean | null;
  pws_untreatable_obstructive_sleep_apnea?: boolean | null;
  pws_active_cancer?: boolean | null;
  pws_active_psychosis?: boolean | null;
  pws_progressive_scoliosis?: boolean | null;
  gh_patient_group?: "pediatric" | "adult" | null;
  gh_height_reference_sex?: "female" | "male" | null;
  gh_treatment_phase?: "initiation" | "continuation" | null;
  epiphyses_closed?: boolean | null;
  annual_growth_velocity_cm?: number | null;
  height_cm?: number | null;
  bone_age_years?: number | null;
}

