import type { SutMaterialItem } from "@/lib/api/sut";

/** Blank optional numbers are unknown, never an observed zero. */
export function optionalCount(value: string): number | null {
  if (!value.trim()) return null;
  const number = Number(value);
  return Number.isInteger(number) && number >= 0 ? number : null;
}

export function drugMaterialPayload(material: SutMaterialItem, enabled: boolean): SutMaterialItem {
  const { annual_application_count, is_loading_phase, biomarkers, prior_therapies,
    gh_treatment_phase, epiphyses_closed, annual_growth_velocity_cm, height_cm, bone_age_years,
    gh_patient_group, gh_height_reference_sex, sma_evidence, antifungal_evidence, renal_evidence,
    pws_genetic_diagnosis_confirmed, pws_uncontrolled_diabetes, pws_untreatable_obstructive_sleep_apnea,
    pws_active_cancer, pws_active_psychosis, pws_progressive_scoliosis, pws_severe_obesity_source_criterion_present,
    enteral_evidence, ravulizumab_evidence, followup_evidence,
    ckd_growth_disorder_confirmed, ckd_persistent_severe_secondary_hyperparathyroidism,
    ckd_proliferative_or_severe_nonproliferative_retinopathy, ckd_first_post_transplant_year,
    ckd_active_cancer, ckd_parathyroid_hormone_pg_ml, gh_daily_dose_mg_per_kg,
    mecasermin_laron_syndrome_confirmed, pretreatment_annual_growth_velocity_cm,
    height_percentile, mecasermin_daily_dose_mcg_per_kg,
    ...base } = material;
  if (!enabled) return base;
  return {
    ...base,
    annual_application_count: annual_application_count ?? null,
    is_loading_phase: is_loading_phase ?? null,
    gh_treatment_phase: gh_treatment_phase ?? null,
    gh_patient_group: gh_patient_group ?? null,
    gh_height_reference_sex: gh_height_reference_sex ?? null,
    epiphyses_closed: epiphyses_closed ?? null,
    annual_growth_velocity_cm: annual_growth_velocity_cm ?? null,
    height_cm: height_cm ?? null,
    bone_age_years: bone_age_years ?? null,
    sma_evidence: sma_evidence ?? null,
    antifungal_evidence: antifungal_evidence ?? null,
    renal_evidence: renal_evidence ?? null,
    followup_evidence: followup_evidence ?? null,
    enteral_evidence: enteral_evidence ?? null,
    ravulizumab_evidence: ravulizumab_evidence ?? null,
    pws_genetic_diagnosis_confirmed: pws_genetic_diagnosis_confirmed ?? null,
    pws_uncontrolled_diabetes: pws_uncontrolled_diabetes ?? null,
    pws_untreatable_obstructive_sleep_apnea: pws_untreatable_obstructive_sleep_apnea ?? null,
    pws_active_cancer: pws_active_cancer ?? null,
    pws_active_psychosis: pws_active_psychosis ?? null,
    pws_progressive_scoliosis: pws_progressive_scoliosis ?? null,
    pws_severe_obesity_source_criterion_present: pws_severe_obesity_source_criterion_present ?? null,
    ckd_growth_disorder_confirmed: ckd_growth_disorder_confirmed ?? null,
    ckd_persistent_severe_secondary_hyperparathyroidism: ckd_persistent_severe_secondary_hyperparathyroidism ?? null,
    ckd_proliferative_or_severe_nonproliferative_retinopathy: ckd_proliferative_or_severe_nonproliferative_retinopathy ?? null,
    ckd_first_post_transplant_year: ckd_first_post_transplant_year ?? null,
    ckd_active_cancer: ckd_active_cancer ?? null,
    ckd_parathyroid_hormone_pg_ml: ckd_parathyroid_hormone_pg_ml ?? null,
    gh_daily_dose_mg_per_kg: gh_daily_dose_mg_per_kg ?? null,
    mecasermin_laron_syndrome_confirmed: mecasermin_laron_syndrome_confirmed ?? null,
    pretreatment_annual_growth_velocity_cm: pretreatment_annual_growth_velocity_cm ?? null,
    height_percentile: height_percentile ?? null,
    mecasermin_daily_dose_mcg_per_kg: mecasermin_daily_dose_mcg_per_kg ?? null,
    // Incomplete edits are unknown facts, not negative clinical findings.
    biomarkers: biomarkers?.filter(row => row.marker.trim() && row.status.trim())
      .map(row => ({ marker: row.marker.trim(), status: row.status.trim() })) ?? null,
    // Keep an unfinished therapy identity: the evaluator treats it as unknown.
    // Dropping it next to unrelated known therapies would assert a mismatch.
    prior_therapies: prior_therapies?.map(row => ({
      drug_or_class: row.drug_or_class.trim(), outcome: row.outcome.trim(),
    })) ?? null,
  };
}
