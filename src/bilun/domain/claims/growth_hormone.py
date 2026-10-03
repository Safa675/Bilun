"""Explicit, nullable Turner continuation inputs shared by ingest and evaluation."""

from __future__ import annotations

from math import isfinite
from typing import Any


GROWTH_HORMONE_FIELDS = (
    "gh_treatment_phase",
    "epiphyses_closed",
    "annual_growth_velocity_cm",
    "height_cm",
    "bone_age_years",
)


PWS_FIELDS = (
    "pws_genetic_diagnosis_confirmed",
    "pws_uncontrolled_diabetes",
    "pws_untreatable_obstructive_sleep_apnea",
    "pws_active_cancer",
    "pws_active_psychosis",
    "pws_progressive_scoliosis",
    "pws_severe_obesity_source_criterion_present",
)

# Phase-specific statutory lists, deliberately not inferred from all PWS inputs.
PWS_CONTINUATION_STOP_FIELDS = (
    "pws_uncontrolled_diabetes", "pws_untreatable_obstructive_sleep_apnea",
    "pws_active_cancer", "pws_active_psychosis", "pws_progressive_scoliosis",
)
PWS_INITIATION_EXCLUSION_FIELDS = (
    "pws_severe_obesity_source_criterion_present", "pws_uncontrolled_diabetes",
    "pws_untreatable_obstructive_sleep_apnea", "pws_active_cancer", "pws_active_psychosis",
)

CKD_GH_BOOLEAN_FIELDS = (
    "ckd_growth_disorder_confirmed",
    "ckd_persistent_severe_secondary_hyperparathyroidism",
    "ckd_proliferative_or_severe_nonproliferative_retinopathy",
    "ckd_first_post_transplant_year",
    "ckd_active_cancer",
)
CKD_GH_NUMERIC_FIELDS = ("ckd_parathyroid_hormone_pg_ml", "gh_daily_dose_mg_per_kg")

MECASERMIN_FIELDS = ("mecasermin_laron_syndrome_confirmed", "pretreatment_annual_growth_velocity_cm", "height_percentile", "mecasermin_daily_dose_mcg_per_kg")

PEDIATRIC_GH_INITIATION_FIELDS = ('gh_initiation_pathway', 'gh_reported_growth_age_band', 'gh_chronological_age_years', 'gh_pubertal_status', 'gh_pubertal_growth_assessment_completed', 'gh_birth_weight_for_gestational_age_sds', 'gh_birth_length_for_gestational_age_sds', 'gh_last_year_growth_velocity_sds', 'gh_current_height_sds', 'gh_parent_adjusted_height_sds', 'gh_sga_birth_status_confirmed')

PEDIATRIC_GH_SDS_FIELDS = ('gh_birth_weight_for_gestational_age_sds', 'gh_birth_length_for_gestational_age_sds', 'gh_last_year_growth_velocity_sds', 'gh_current_height_sds', 'gh_parent_adjusted_height_sds')

CKD_GROWTH_PATHWAY_FIELDS = ('ckd_height_age_sex_percentile', 'ckd_height_age_sex_sds', 'ckd_annual_growth_velocity_percentile', 'ckd_persistent_growth_failure_confirmed', 'ckd_post_transplant_one_year_elapsed', 'ckd_steroid_treatment_absent', 'ckd_spontaneous_growth_absent', 'ckd_nephropathic_cystinosis_related_confirmed')

GROWTH_HORMONE_INPUT_FIELDS = (
    *GROWTH_HORMONE_FIELDS, "gh_patient_group", "gh_height_reference_sex", *PWS_FIELDS,
    *CKD_GH_BOOLEAN_FIELDS, *CKD_GH_NUMERIC_FIELDS, *MECASERMIN_FIELDS, *PEDIATRIC_GH_INITIATION_FIELDS, *CKD_GROWTH_PATHWAY_FIELDS,
)

def validated_growth_hormone_value(field: str, value: Any) -> Any:
    """Do not coerce missing/invalid clinical evidence into a known measurement."""
    choices = {
        "gh_initiation_pathway": {"standard", "neurosecretory_bioinactive", "organic_or_surgical", "sga_case_1", "sga_case_2"},
        "gh_reported_growth_age_band": {"0_2_years", "2_1_4_years", "4_1_prepubertal", "pubertal"},
        "gh_pubertal_status": {"prepubertal", "pubertal"},
    }
    if field in choices:
        return value if isinstance(value, str) and value in choices[field] else None
    if field in CKD_GROWTH_PATHWAY_FIELDS:
        if field not in {"ckd_height_age_sex_percentile", "ckd_height_age_sex_sds", "ckd_annual_growth_velocity_percentile"}:
            return value if type(value) is bool else None
        if type(value) not in {int, float}:
            return None
        try:
            numeric = float(value)
        except (ValueError, OverflowError):
            return None
        if not isfinite(numeric):
            return None
        return numeric if field.endswith("_sds") or 0 <= numeric <= 100 else None
    if field in {"gh_pubertal_growth_assessment_completed", "gh_sga_birth_status_confirmed"}:
        return value if type(value) is bool else None
    if field in {*PEDIATRIC_GH_SDS_FIELDS, "gh_chronological_age_years"}:
        if type(value) not in {int, float}:
            return None
        try:
            numeric = float(value)
        except (ValueError, OverflowError):
            return None
        return numeric if isfinite(numeric) and (field != "gh_chronological_age_years" or numeric >= 0) else None
    if field == "gh_treatment_phase":
        return value if isinstance(value, str) and value in {"initiation", "continuation"} else None
    if field == "gh_patient_group":
        return value if isinstance(value, str) and value in {"pediatric", "adult"} else None
    if field == "gh_height_reference_sex":
        return value if isinstance(value, str) and value in {"female", "male"} else None
    if field in {"epiphyses_closed", "mecasermin_laron_syndrome_confirmed", *PWS_FIELDS, *CKD_GH_BOOLEAN_FIELDS}:
        return value if type(value) is bool else None
    if field in {"annual_growth_velocity_cm", "height_cm", "bone_age_years", "pretreatment_annual_growth_velocity_cm", "height_percentile", "mecasermin_daily_dose_mcg_per_kg", *CKD_GH_NUMERIC_FIELDS}:
        if type(value) not in {int, float}:
            return None
        try:
            numeric = float(value)
        except (ValueError, OverflowError):
            return None
        if not isfinite(numeric) or numeric < 0 or (field == "height_cm" and numeric == 0):
            return None
        if field == "height_percentile" and numeric > 100:
            return None
        return numeric
    raise ValueError(f"Unknown growth-hormone field: {field}")


def parse_growth_hormone_inputs(
    row: dict[str, Any], *, row_id: str = "", errors: list[str] | None = None
) -> dict[str, Any]:
    """Pass explicit evidence through; invalid cells stay unknown and are reported."""
    result = {}
    for field in GROWTH_HORMONE_INPUT_FIELDS:
        value = row.get(field)
        parsed = validated_growth_hormone_value(field, value)
        if value is not None and parsed is None and errors is not None:
            errors.append(f"{row_id} invalid {field}: expected explicit typed clinical evidence")
        result[field] = parsed
    return result
