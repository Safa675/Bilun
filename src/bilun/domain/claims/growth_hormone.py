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

GROWTH_HORMONE_INPUT_FIELDS = (
    *GROWTH_HORMONE_FIELDS, "gh_patient_group", "gh_height_reference_sex", *PWS_FIELDS,
    *CKD_GH_BOOLEAN_FIELDS, *CKD_GH_NUMERIC_FIELDS, *MECASERMIN_FIELDS,
)

def validated_growth_hormone_value(field: str, value: Any) -> Any:
    """Do not coerce missing/invalid clinical evidence into a known measurement."""
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
