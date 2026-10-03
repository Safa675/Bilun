"""Strict, optional source-specific clinical evidence; absent facts stay unknown.

``applies_on`` is the clinician's explicit service-date scope. ``assessment_date``
records when the assessment was made. Neither is inferred from the wall clock.
Numerical field names declare units; this layer never converts ambiguous units.
"""
from __future__ import annotations

from dataclasses import dataclass, fields
from datetime import date
import json
import math
import re
from typing import Any, TypeVar


def clinical_date(value: Any) -> date | None:
    if type(value) is date:
        return value
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


@dataclass(frozen=True)
class SmaEvidence:
    applies_on: date | None = None
    assessment_date: date | None = None
    sma_type: str | None = None  # type_1, type_2, type_3, newborn_screening
    brain_spinal_history_impeding_procedure: bool | None = None
    csf_shunt_or_catheter: bool | None = None
    bacterial_meningitis_history: bool | None = None
    viral_encephalitis_history: bool | None = None
    hypoxic_ischemic_encephalopathy: bool | None = None
    hypoxic_birth_neurological_sequelae: bool | None = None
    lumbar_puncture_suitability_documented: bool | None = None
    risdiplam_treatment_period: str | None = None  # not_started, during_treatment
    # Both monitoring and assessment are documented; adequacy/cadence are not inferred.
    risdiplam_motor_monitoring_assessment_documented: bool | None = None
    risdiplam_cognitive_monitoring_assessment_documented: bool | None = None
    risdiplam_nutritional_monitoring_assessment_documented: bool | None = None
    risdiplam_respiratory_monitoring_assessment_documented: bool | None = None
    risdiplam_rehabilitation_monitoring_assessment_documented: bool | None = None
    risdiplam_orthopedic_monitoring_assessment_documented: bool | None = None
    risdiplam_monitoring_assessment_in_health_board_report: bool | None = None


@dataclass(frozen=True)
class AntifungalEvidence:
    applies_on: date | None = None
    assessment_date: date | None = None
    intent: str | None = None  # treatment, prophylaxis
    indication: str | None = None
    formulation: str | None = None  # oral_solution, oral_suspension, oral_tablet, parenteral
    adult: bool | None = None
    anc_per_mm3: float | None = None
    anc_lab_result_present: bool | None = None
    high_invasive_fungal_risk: bool | None = None
    aml_or_mds: bool | None = None
    remission_induction_chemotherapy: bool | None = None
    prolonged_neutropenia_expected: bool | None = None
    neutropenia_development_expected: bool | None = None
    allogeneic_hsct: bool | None = None
    autologous_hsct: bool | None = None
    acute_lymphoblastic_leukemia: bool | None = None
    gvhd_high_dose_immunosuppression: bool | None = None
    oral_form_unusable: bool | None = None
    current_neutropenia: bool | None = None
    neutropenia_end_date: date | None = None
    mucositis: bool | None = None
    expected_neutropenia_days: float | None = None
    hematological_malignancy: bool | None = None
    bone_marrow_transplant: bool | None = None
    hiv_positive: bool | None = None
    immunodeficiency: bool | None = None
    fluconazole_resistant: bool | None = None
    amphotericin_b_refractory: bool | None = None
    amphotericin_b_intolerant: bool | None = None
    liposomal_amphotericin_b_refractory: bool | None = None
    voriconazole_refractory: bool | None = None
    itraconazole_refractory: bool | None = None
    itraconazole_intolerant: bool | None = None
    fluconazole_refractory: bool | None = None
    fluconazole_intolerant: bool | None = None


@dataclass(frozen=True)
class RenalEvidence:
    applies_on: date | None = None
    assessment_date: date | None = None
    phase: str | None = None  # initiation, continuation, restart
    indication: str | None = None  # dialysis_shpt, primary_hpt, renal_nutrition, phosphate_binding
    dialysis: bool | None = None
    other_phosphate_therapy_months: float | None = None
    # Report explicitly documents the source-required >=3 months of prior therapy.
    prior_phosphate_therapy_documented_in_report: bool | None = None
    calcium_phosphorus_product: float | None = None
    corrected_calcium_phosphorus_product: float | None = None
    pth_pg_ml: float | None = None
    adynamic_bone_disease: bool | None = None
    kt_v: float | None = None
    phosphorus_mg_dl: float | None = None
    corrected_calcium_mg_dl: float | None = None
    parathyroidectomy_indicated: bool | None = None
    parathyroidectomy_unsuitable_or_contraindicated: bool | None = None
    asa_iv: bool | None = None
    postsurgical_recurrence: bool | None = None
    bisphosphonate_failed: bool | None = None
    albumin_g_dl: float | None = None
    baseline_albumin_g_dl: float | None = None
    six_month_albumin_g_dl: float | None = None
    ckd_stage: float | None = None
    gfr_ml_min: float | None = None
    weight_loss_last_3_months_percent: float | None = None
    bmi: float | None = None
    therapy_months: float | None = None



@dataclass(frozen=True)
class EnteralEvidence:
    applies_on: date | None = None
    assessment_date: date | None = None
    pediatric: bool | None = None
    phase: str | None = None  # initiation, renewal
    malnutrition_path: str | None = None  # malnutrition, exemption
    neurological_disease: bool | None = None
    malnutrition_criteria_met: bool | None = None
    # Initiation report content; distinct from whether clinical criteria are met.
    malnutrition_conditions_documented_in_report: bool | None = None
    specialist_report_present: bool | None = None
    report_author_specialty: str | None = None


@dataclass(frozen=True)
class RavulizumabEvidence:
    applies_on: date | None = None
    assessment_date: date | None = None
    indication: str | None = None  # nmosd, pnh, ahus
    adult: bool | None = None
    therapy_months: float | None = None
    edss: float | None = None
    edss_in_report: bool | None = None

@dataclass(frozen=True)
class FollowupEvidence:
    applies_on: date | None = None
    assessment_date: date | None = None
    phase: str | None = None
    indication: str | None = None
    treatment_start_date: date | None = None
    baseline_assessment_date: date | None = None
    response_assessment_date: date | None = None
    week16_checkpoint_documented: bool | None = None
    baseline_easi: float | None = None
    response_easi: float | None = None
    baseline_dlqi: float | None = None
    response_dlqi: float | None = None
    baseline_pruritus_nrs: float | None = None
    response_pruritus_nrs: float | None = None
    previous_report_date: date | None = None
    current_report_date: date | None = None
    previous_fvc_percent_predicted: float | None = None
    current_fvc_percent_predicted: float | None = None
    fvc_assessment_outside_exacerbation: bool | None = None
    report_documents_fvc_response: bool | None = None


@dataclass(frozen=True)
class IndicationEvidence:
    applies_on: date | None = None
    assessment_date: date | None = None
    phase: str | None = None
    indication: str | None = None
    administration_route: str | None = None
    age_group: str | None = None
    hypogammaglobulinemia: bool | None = None
    recurrent_bacterial_infections: bool | None = None
    prophylactic_antibiotics_failed: bool | None = None
    prophylactic_antibiotics_contraindicated: bool | None = None
    allogeneic_hsct_before_or_after: bool | None = None
    report_author_specialty: str | None = None
    prescribed_supply_months: float | None = None
    hbv_dna_iu_ml: float | None = None
    biopsy_scoring_system: str | None = None
    biopsy_hai: float | None = None
    biopsy_fibrosis_stage: float | None = None
    first_alt_uln_ratio: float | None = None
    second_alt_uln_ratio: float | None = None
    first_alt_date: date | None = None
    second_alt_date: date | None = None
    fib4_score: float | None = None
    apri_score: float | None = None
    hcv_rna_positive: bool | None = None
    hcv_genotype_result_present: bool | None = None
    osteoporosis_diagnosed: bool | None = None
    high_fracture_risk: bool | None = None
    long_term_glucocorticoid_treatment: bool | None = None
    glucocorticoid_associated_bone_loss: bool | None = None
    bisphosphonate_intolerant: bool | None = None
    bisphosphonate_inadequate_response: bool | None = None
    bisphosphonate_renal_contraindication: bool | None = None


_ENUMS = {
    IndicationEvidence: {
        'phase': {'initiation', 'continuation', 'restart'},
        'indication': {'sc_ig_cll', 'sc_ig_mm', 'sc_ig_allogeneic_hsct',
                       'hbv_initiation_path_a', 'pediatric_chronic_hcv', 'glucocorticoid_bone_loss', 'other'},
        'administration_route': {'subcutaneous', 'intravenous', 'intramuscular', 'oral', 'other'},
        'age_group': {'adult', 'age_2_18', 'child', 'other'},
        'biopsy_scoring_system': {'ishak_modified_hai', 'knodell_hai', 'metavir', 'other'},
        'report_author_specialty': {'hematology', 'pediatric_hematology_oncology', 'other'},
    },

    FollowupEvidence: {
        'phase': {'initiation', 'continuation', 'restart'},
        'indication': {'atopic_dermatitis', 'progressive_fibrosing_ild', 'systemic_sclerosis_ild', 'other'},
    },
    EnteralEvidence: {
        'phase': {'initiation', 'renewal'},
        'malnutrition_path': {'malnutrition', 'exemption'},
        'report_author_specialty': {'pediatrics', 'pediatric_surgery', 'pediatric_gastroenterology',
            'pediatric_neurology', 'pediatric_metabolism', 'pediatric_endocrinology',
            'pediatric_endocrinology_metabolism', 'other'},
    },
    RavulizumabEvidence: {'indication': {'nmosd', 'pnh', 'ahus'}},
    SmaEvidence: {'sma_type': {'type_1', 'type_2', 'type_3', 'newborn_screening'},
                  'risdiplam_treatment_period': {'not_started', 'during_treatment'}},
    AntifungalEvidence: {
        'intent': {'treatment', 'prophylaxis'},
        'formulation': {'oral_solution', 'oral_suspension', 'oral_tablet', 'parenteral'},
        'indication': {'invasive_candidiasis', 'esophageal_candidiasis',
                       'aspergillus_candida_prophylaxis', 'oropharyngeal_candidiasis',
                       'invasive_aspergillosis', 'fusariosis', 'chromoblastomycosis',
                       'mycetoma', 'coccidioidomycosis', 'deep_fungal_infection_prophylaxis', 'other'},
    },
    RenalEvidence: {
        'phase': {'initiation', 'continuation', 'restart'},
        'indication': {'dialysis_shpt', 'primary_hpt', 'renal_nutrition', 'phosphate_binding', 'other'},
    },
}

# Instrument domains, independently checked against primary EASI/DLQI/NRS guides.
_NUMERIC_MAX = {FollowupEvidence: {
    'baseline_easi': 72, 'response_easi': 72,
    'baseline_dlqi': 30, 'response_dlqi': 30,
    'baseline_pruritus_nrs': 10, 'response_pruritus_nrs': 10,
}}

_E = TypeVar('_E', SmaEvidence, AntifungalEvidence, RenalEvidence, EnteralEvidence, RavulizumabEvidence, FollowupEvidence, IndicationEvidence)


def _finite_nonnegative(raw: Any) -> float | None:
    if type(raw) not in (int, float):
        return None
    try:
        value = float(raw)
    except (ValueError, OverflowError):
        return None
    return value if math.isfinite(value) and value >= 0 else None


def parse_clinical_evidence(value: Any, cls: type[_E]) -> _E | None:
    """Accept a mapping/JSON object; malformed individual facts become unknown.

    Exact booleans prevent "false", 0, NaN or an empty object becoming an asserted
    absence. A typed caller is revalidated too, rather than bypassing the boundary.
    """
    if isinstance(value, cls):
        value = {f.name: getattr(value, f.name) for f in fields(cls)}
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except (ValueError, TypeError):
            return None
    if not isinstance(value, dict):
        return None
    parsed: dict[str, Any] = {}
    for f in fields(cls):
        raw = value.get(f.name)
        if f.type == 'date | None':
            parsed[f.name] = clinical_date(raw)
        elif f.type == 'bool | None':
            parsed[f.name] = raw if type(raw) is bool else None
        elif f.type == 'float | None':
            number = _finite_nonnegative(raw)
            parsed[f.name] = None if cls is RavulizumabEvidence and f.name == 'edss' and number is not None and number > 10 else number
            maximum = _NUMERIC_MAX.get(cls, {}).get(f.name)
            if parsed[f.name] is not None and maximum is not None and parsed[f.name] > maximum:
                parsed[f.name] = None
        elif f.type == 'str | None':
            parsed[f.name] = raw if isinstance(raw, str) and raw in _ENUMS.get(cls, {}).get(f.name, ()) else None
    if cls is IndicationEvidence:
        # Do not confuse different ordinal systems or silently reinterpret a
        # fibrosis stage as an activity score. Unknown scales stay unknown.
        method = parsed.get('biopsy_scoring_system')
        hai_max = {'ishak_modified_hai': 18, 'knodell_hai': 22}.get(method)
        fibrosis_max = {'ishak_modified_hai': 6, 'knodell_hai': 4, 'metavir': 4}.get(method)
        for name, maximum in (('biopsy_hai', hai_max), ('biopsy_fibrosis_stage', fibrosis_max)):
            if maximum is None or (parsed.get(name) is not None and parsed[name] > maximum):
                parsed[name] = None
    return cls(**parsed)
