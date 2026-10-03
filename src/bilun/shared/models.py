"""
Pydantic request/response schemas for the BILUN API.
"""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, field_validator

from src.bilun.domain.claims.clinical_evidence import (
    AntifungalEvidence, RenalEvidence, SmaEvidence, parse_clinical_evidence,
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

    @field_validator(
        "gh_treatment_phase", "epiphyses_closed", "annual_growth_velocity_cm",
        "height_cm", "bone_age_years", "gh_patient_group",
        "gh_height_reference_sex",
        "pws_genetic_diagnosis_confirmed",
        "pws_uncontrolled_diabetes",
        "pws_untreatable_obstructive_sleep_apnea",
        "pws_active_cancer",
        "pws_active_psychosis",
        "pws_progressive_scoliosis",
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


class ClaimValidationRequest(BaseModel):
    """Request body for POST /api/validate-claim."""

    claim_id: str = ""
    procedure_code: str = ""
    materials: list[MaterialItem] = []
    drug_context: DrugContext | None = None
