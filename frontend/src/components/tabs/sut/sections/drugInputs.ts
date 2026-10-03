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
    gh_patient_group, gh_height_reference_sex,
    pws_genetic_diagnosis_confirmed, pws_uncontrolled_diabetes, pws_untreatable_obstructive_sleep_apnea,
    pws_active_cancer, pws_active_psychosis, pws_progressive_scoliosis,
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
    pws_genetic_diagnosis_confirmed: pws_genetic_diagnosis_confirmed ?? null,
    pws_uncontrolled_diabetes: pws_uncontrolled_diabetes ?? null,
    pws_untreatable_obstructive_sleep_apnea: pws_untreatable_obstructive_sleep_apnea ?? null,
    pws_active_cancer: pws_active_cancer ?? null,
    pws_active_psychosis: pws_active_psychosis ?? null,
    pws_progressive_scoliosis: pws_progressive_scoliosis ?? null,
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
