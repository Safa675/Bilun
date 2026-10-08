"""
Pydantic request/response schemas for the BILUN API.
"""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from src.bilun.domain.claims.adult_gh import AdultGhEvidence, parse_adult_gh_evidence
from src.bilun.domain.claims.mds_evidence import MdsEvidence, parse_mds_evidence

from src.bilun.domain.claims.clinical_evidence import (
    AntifungalEvidence, IndicationEvidence, FollowupEvidence, EnteralEvidence, RavulizumabEvidence, RenalEvidence, SmaEvidence, parse_clinical_evidence,
)
from src.bilun.domain.claims.mesothelioma_evidence import (
    MesotheliomaEvidence, parse_mesothelioma_evidence,
)


class MaterialItem(BaseModel):
    """A single material line item in a claim."""

    name: str
    code: str = ""
    unit_price: float = 0.0
    quantity: int = 1
    billed_amount: float = 0.0
    # §4.2.33 anti-VEGF dose protocol (intravitreal injection counts) — optional,
    # only meaningful for ophthalmology drug claims; ignored otherwise.
    annual_application_count: int | None = None
    is_loading_phase: bool | None = None
    # §4.2.14.C oncology biomarker + prior-therapy gating — optional, only for
    # indication-gated oncology drug claims; ignored otherwise.
    biomarkers: list[dict[str, str]] | None = None
    prior_therapies: list[dict[str, str]] | None = None
    # Turner somatropin continuation evidence is optional and never defaulted.
    gh_treatment_phase: Literal["initiation", "continuation"] | None = None
    epiphyses_closed: bool | None = None
    annual_growth_velocity_cm: float | None = None
    height_cm: float | None = None
    bone_age_years: float | None = None
    gh_patient_group: Literal["pediatric", "adult"] | None = None
    gh_height_reference_sex: Literal["female", "male"] | None = None
    pws_genetic_diagnosis_confirmed: bool | None = None
    pws_uncontrolled_diabetes: bool | None = None
    pws_untreatable_obstructive_sleep_apnea: bool | None = None
    pws_active_cancer: bool | None = None
    pws_active_psychosis: bool | None = None
    pws_progressive_scoliosis: bool | None = None
    pws_severe_obesity_source_criterion_present: bool | None = None
    ckd_growth_disorder_confirmed: bool | None = None
    ckd_persistent_severe_secondary_hyperparathyroidism: bool | None = None
    ckd_proliferative_or_severe_nonproliferative_retinopathy: bool | None = None
    ckd_first_post_transplant_year: bool | None = None
    ckd_active_cancer: bool | None = None
    ckd_parathyroid_hormone_pg_ml: float | None = None
    gh_daily_dose_mg_per_kg: float | None = None
    mecasermin_laron_syndrome_confirmed: bool | None = None
    pretreatment_annual_growth_velocity_cm: float | None = None
    height_percentile: float | None = None
    mecasermin_daily_dose_mcg_per_kg: float | None = None
    gh_initiation_pathway: str | None = None
    gh_reported_growth_age_band: str | None = None
    gh_chronological_age_years: float | None = None
    gh_pubertal_status: str | None = Field(default=None, description='Clinician-recorded assessment using SUT §4.2.6.A-1(1)(b)(3): onset is testicular volume >=4 ml in boys or T2 thelarche in girls. Enter prepubertal/pubertal only when the recorded assessment uses that definition; otherwise leave unknown. Do not infer from age, diagnosis or height-reference sex; no raw measurements are requested.')
    gh_pubertal_growth_assessment_completed: bool | None = None
    gh_birth_weight_for_gestational_age_sds: float | None = None
    gh_birth_length_for_gestational_age_sds: float | None = None
    gh_last_year_growth_velocity_sds: float | None = None
    gh_current_height_sds: float | None = None
    gh_parent_adjusted_height_sds: float | None = None
    gh_sga_birth_status_confirmed: bool | None = None
    ckd_height_age_sex_percentile: float | None = None
    ckd_height_age_sex_sds: float | None = None
    ckd_annual_growth_velocity_percentile: float | None = None
    ckd_persistent_growth_failure_confirmed: bool | None = None
    ckd_post_transplant_one_year_elapsed: bool | None = None
    ckd_steroid_treatment_absent: bool | None = None
    ckd_spontaneous_growth_absent: bool | None = None
    ckd_nephropathic_cystinosis_related_confirmed: bool | None = None

    @field_validator(
        "gh_treatment_phase", "epiphyses_closed", "annual_growth_velocity_cm",
        "height_cm", "bone_age_years", "gh_patient_group",
        "gh_height_reference_sex",
        "pws_genetic_diagnosis_confirmed",
        "pws_uncontrolled_diabetes",
        "pws_untreatable_obstructive_sleep_apnea",
        "pws_active_cancer",
        "pws_active_psychosis",
        "pws_progressive_scoliosis", "pws_severe_obesity_source_criterion_present",
        "ckd_growth_disorder_confirmed",
        "ckd_persistent_severe_secondary_hyperparathyroidism",
        "ckd_proliferative_or_severe_nonproliferative_retinopathy",
        "ckd_first_post_transplant_year",
        "ckd_active_cancer",
        "ckd_parathyroid_hormone_pg_ml",
        "gh_daily_dose_mg_per_kg",
        "mecasermin_laron_syndrome_confirmed", "pretreatment_annual_growth_velocity_cm",
        "height_percentile", "mecasermin_daily_dose_mcg_per_kg",
        "gh_initiation_pathway",
        "gh_reported_growth_age_band",
        "gh_chronological_age_years",
        "gh_pubertal_status",
        "gh_pubertal_growth_assessment_completed",
        "gh_birth_weight_for_gestational_age_sds",
        "gh_birth_length_for_gestational_age_sds",
        "gh_last_year_growth_velocity_sds",
        "gh_current_height_sds",
        "gh_parent_adjusted_height_sds",
        "gh_sga_birth_status_confirmed",
        "ckd_height_age_sex_percentile",
        "ckd_height_age_sex_sds",
        "ckd_annual_growth_velocity_percentile",
        "ckd_persistent_growth_failure_confirmed",
        "ckd_post_transplant_one_year_elapsed",
        "ckd_steroid_treatment_absent",
        "ckd_spontaneous_growth_absent",
        "ckd_nephropathic_cystinosis_related_confirmed",
        mode="before",
    )
    @classmethod
    def validate_growth_hormone_evidence(cls, value, info):
        from src.bilun.domain.claims.growth_hormone import validated_growth_hormone_value

        if value is None:
            return None
        parsed = validated_growth_hormone_value(info.field_name, value)
        if parsed is None:
            raise ValueError(f"{info.field_name} requires explicit typed clinical evidence")
        return parsed

    # Strict typed interpretation happens at the shared clinical parser boundary;
    # malformed/unknown facts must remain unknown, never coerced to absent disease.
    sma_evidence: SmaEvidence | None = None
    antifungal_evidence: AntifungalEvidence | None = None
    renal_evidence: RenalEvidence | None = None
    followup_evidence: FollowupEvidence | None = None
    indication_evidence: IndicationEvidence | None = None
    enteral_evidence: EnteralEvidence | None = None
    ravulizumab_evidence: RavulizumabEvidence | None = None
    mesothelioma_evidence: MesotheliomaEvidence | None = None

    adult_gh_evidence: AdultGhEvidence | None = None
    mds_evidence: MdsEvidence | None = None

    @field_validator('adult_gh_evidence', mode='before')
    @classmethod
    def parse_adult_gh_evidence(cls, value):
        return parse_adult_gh_evidence(value)

    @field_validator('mds_evidence', mode='before')
    @classmethod
    def parse_mds_evidence(cls, value):
        return parse_mds_evidence(value)

    @field_validator('mesothelioma_evidence', mode='before')
    @classmethod
    def parse_mesothelioma_evidence(cls, value):
        return parse_mesothelioma_evidence(value)

    @field_validator('enteral_evidence', mode='before')
    @classmethod
    def parse_enteral_evidence(cls, value):
        return parse_clinical_evidence(value, EnteralEvidence)

    @field_validator('ravulizumab_evidence', mode='before')
    @classmethod
    def parse_ravulizumab_evidence(cls, value):
        return parse_clinical_evidence(value, RavulizumabEvidence)

    @field_validator('indication_evidence', mode='before')
    @classmethod
    def parse_indication_evidence(cls, value):
        return parse_clinical_evidence(value, IndicationEvidence)

    @field_validator("followup_evidence", mode="before")
    @classmethod
    def parse_followup_evidence(cls, value):
        return parse_clinical_evidence(value, FollowupEvidence)

    @field_validator('sma_evidence', mode='before')
    @classmethod
    def parse_sma_evidence(cls, value):
        return parse_clinical_evidence(value, SmaEvidence)

    @field_validator('antifungal_evidence', mode='before')
    @classmethod
    def parse_antifungal_evidence(cls, value):
        return parse_clinical_evidence(value, AntifungalEvidence)

    @field_validator('renal_evidence', mode='before')
    @classmethod
    def parse_renal_evidence(cls, value):
        return parse_clinical_evidence(value, RenalEvidence)



class DrugContext(BaseModel):
    """Claim-level drug indication context (optional, only for drug claims).

    When present, the validate-claim endpoint runs the drug_indication engine
    (§4.2.14.C oncology + §4.2.33 anti-VEGF) against each material line.
    Line-level fields (biomarkers, dose counts) stay on MaterialItem.
    """

    service_date: date | None = None

    @field_validator("service_date", mode="before")
    @classmethod
    def validate_service_date(cls, value: object) -> date | None:
        from src.bilun.domain.prose_rules._drug_indication.temporal import parse_service_date

        if value is None:
            return None
        parsed = parse_service_date(value)
        if parsed is None:
            raise ValueError("service_date must be an ISO calendar date (YYYY-MM-DD)")
        return parsed

    primary_icd10: str = ""
    prescriber_specialty: str = ""
    board_report_present: bool | None = None
    report_duration_months: int | None = None

    @field_validator("report_duration_months", mode="before")
    @classmethod
    def keep_boolean_report_duration_unknown(cls, value):
        # A report-duration boolean is not the observed count 0 or 1.
        return None if type(value) is bool else value


class ClaimValidationRequest(BaseModel):
    """Request body for POST /api/validate-claim."""

    claim_id: str = ""
    procedure_code: str = ""
    materials: list[MaterialItem] = []
    drug_context: DrugContext | None = None
