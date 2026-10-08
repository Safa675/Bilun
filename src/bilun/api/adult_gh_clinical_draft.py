"""Local inspection contract for the adult somatropin draft.

The helper exposes candidate clinical checks for review. It has no router and
does not release clinical evaluation or certify reimbursement eligibility.
The existing claim route separately carries the source/interpretation-gated observation.
"""
from __future__ import annotations

from datetime import date
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictStr, field_validator

from src.bilun.domain.claims.adult_gh import AdultGhEvidence, parse_adult_gh_evidence
from src.bilun.domain.claims.clinical_evidence import clinical_date
from src.bilun.domain.prose_rules.adult_gh_draft import (
    evaluate_adult_gh_closed_epiphysis,
    evaluate_adult_gh_closed_epiphysis_candidate,
)


class AdultGhClinicalDraftRequest(BaseModel):
    """Explicit service and patient scope; malformed clinical facts stay unknown."""

    model_config = ConfigDict(extra="forbid", frozen=True, revalidate_instances="always")

    drug_name: StrictStr
    selected_rule_id: StrictStr
    drug_claim_date: date | None = None
    gh_patient_group: Literal["adult", "pediatric"] | None = None
    epiphyses_closed: bool | None = None
    gh_treatment_phase: Literal["initiation", "continuation"] | None = None
    adult_gh_evidence: AdultGhEvidence | None = None

    @field_validator("drug_claim_date", mode="before")
    @classmethod
    def _service_date(cls, value: Any) -> date | None:
        return clinical_date(value)

    @field_validator("gh_patient_group", mode="before")
    @classmethod
    def _patient_group(cls, value: Any) -> str | None:
        return value if type(value) is str and value in {"adult", "pediatric"} else None

    @field_validator("epiphyses_closed", mode="before")
    @classmethod
    def _epiphyses_closed(cls, value: Any) -> bool | None:
        return value if type(value) is bool else None

    @field_validator("gh_treatment_phase", mode="before")
    @classmethod
    def _treatment_phase(cls, value: Any) -> str | None:
        return value if type(value) is str and value in {"initiation", "continuation"} else None

    @field_validator("adult_gh_evidence", mode="before")
    @classmethod
    def _evidence(cls, value: Any) -> AdultGhEvidence | None:
        return parse_adult_gh_evidence(value)


class AdultGhClinicalDraftResponse(BaseModel):
    """Review envelope with fixed, non-requestable release gates."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["adult_gh_clinical_draft.v1"] = "adult_gh_clinical_draft.v1"
    drug_name: str
    selected_rule_id: str
    drug_claim_date: date | None
    gh_patient_group: Literal["adult", "pediatric"] | None
    epiphyses_closed: bool | None
    gh_treatment_phase: Literal["initiation", "continuation"] | None
    runtime_enabled: Literal[False] = False
    clinical_eligibility_complete: Literal[False] = False
    runtime_result: dict[str, Any] | None
    candidate_result: dict[str, Any] | None = Field(
        description=(
            "Illustrative checks against pinned paragraph text; this result does not establish "
            "source applicability on the service date or payment eligibility."
        ),
    )
    pending_requirements: tuple[
        Literal["adult_gh_source_date_admission"],
        Literal["adult_gh_independent_clinical_interpretation"],
    ] = (
        "adult_gh_source_date_admission",
        "adult_gh_independent_clinical_interpretation",
    )


def review_adult_gh_clinical_draft(
    request: AdultGhClinicalDraftRequest,
) -> AdultGhClinicalDraftResponse:
    """Evaluate the dated candidate alongside its still-closed runtime gate.

    Revalidation also protects callers supplying an existing typed request.
    Candidate ``criterion_clear`` describes only the bounded draft predicates;
    it does not establish historical source applicability. The response always
    retains incomplete eligibility and pending release work.
    """
    validated = AdultGhClinicalDraftRequest.model_validate(request)
    return AdultGhClinicalDraftResponse(
        drug_name=validated.drug_name,
        selected_rule_id=validated.selected_rule_id,
        drug_claim_date=validated.drug_claim_date,
        gh_patient_group=validated.gh_patient_group,
        epiphyses_closed=validated.epiphyses_closed,
        gh_treatment_phase=validated.gh_treatment_phase,
        runtime_result=evaluate_adult_gh_closed_epiphysis(
            validated, validated.selected_rule_id,
        ),
        candidate_result=evaluate_adult_gh_closed_epiphysis_candidate(
            validated, validated.selected_rule_id,
        ),
    )
