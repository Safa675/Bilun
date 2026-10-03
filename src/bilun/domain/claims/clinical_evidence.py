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


_ENUMS = {
    SmaEvidence: {'sma_type': {'type_1', 'type_2', 'type_3', 'newborn_screening'}},
    AntifungalEvidence: {
        'intent': {'treatment', 'prophylaxis'},
        'formulation': {'oral_solution', 'oral_suspension', 'oral_tablet', 'parenteral'},
        'indication': {'invasive_candidiasis', 'esophageal_candidiasis',
                       'aspergillus_candida_prophylaxis', 'oropharyngeal_candidiasis',
                       'invasive_aspergillosis', 'fusariosis', 'chromoblastomycosis',
                       'mycetoma', 'coccidioidomycosis', 'other'},
    },
    RenalEvidence: {
        'phase': {'initiation', 'continuation', 'restart'},
        'indication': {'dialysis_shpt', 'primary_hpt', 'renal_nutrition', 'phosphate_binding', 'other'},
    },
}

_E = TypeVar('_E', SmaEvidence, AntifungalEvidence, RenalEvidence)


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
            parsed[f.name] = _finite_nonnegative(raw)
        elif f.type == 'str | None':
            parsed[f.name] = raw if isinstance(raw, str) and raw in _ENUMS.get(cls, {}).get(f.name, ()) else None
    return cls(**parsed)
