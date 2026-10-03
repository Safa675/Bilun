"""Bounded public provenance for an admitted clinical source version, never payment."""
from typing import Literal
from datetime import date, datetime
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator


class ClinicalSourceAuthorityEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    schema_version: Literal[1] = 1
    status: Literal["admitted", "review_required"]
    reason: Literal["covered", "missing_service_date", "uncovered_service_date",
                    "source_authority_unavailable", "source_content_changed", "known_successor"]
    family_id: str = Field(min_length=1, max_length=80)
    version_id: str | None = Field(default=None, max_length=120)
    service_date: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    legal_effective_from: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    admission_basis: Literal["established_history", "observed_snapshot", "reviewed_continuity"] | None = None
    admitted_from: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    admitted_through: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    source_observed_on: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    official_review_checked_at: str | None = Field(default=None, max_length=40)
    source_docx_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    review_id: str | None = Field(default=None, max_length=120)
    next_action: str = Field(max_length=400)
    scope: Literal["named_clinical_report_checks_only"] = "named_clinical_report_checks_only"
    clinical_eligibility_complete: Literal[False] = False
    verification_status: Literal["ai_generated_pending_review"] = "ai_generated_pending_review"

    @model_validator(mode="before")
    @classmethod
    def exact_discriminators(cls, value):
        if isinstance(value, dict):
            if 'schema_version' in value and type(value['schema_version']) is not int:
                raise ValueError('Source schema version must be an integer, not boolean/float')
            if 'clinical_eligibility_complete' in value and type(value['clinical_eligibility_complete']) is not bool:
                raise ValueError('Clinical eligibility flag must be an actual boolean')
        return value

    @model_validator(mode="after")
    def coherent_admission(self):
        for value in (self.service_date, self.legal_effective_from, self.admitted_from,
                      self.admitted_through, self.source_observed_on):
            if value is not None:
                date.fromisoformat(value)
        if self.official_review_checked_at is not None:
            checked = datetime.fromisoformat(self.official_review_checked_at.replace("Z", "+00:00"))
            if checked.tzinfo is None:
                raise ValueError("Official observation must include its timezone")
        if self.admitted_from and self.admitted_through and self.admitted_from > self.admitted_through:
            raise ValueError("Reversed admission window")
        if self.status == "admitted":
            if (self.reason != "covered" or self.admission_basis is None or not self.version_id
                    or not self.service_date or not self.admitted_from or not self.admitted_through
                    or not self.source_observed_on or not self.source_docx_sha256
                    or not self.admitted_from <= self.service_date <= self.admitted_through):
                raise ValueError("Admitted provenance needs a complete covering source window")
            if self.admission_basis == "reviewed_continuity" and (
                    not self.review_id or not self.official_review_checked_at):
                raise ValueError("Continuity requires official review evidence")
            if self.admission_basis == 'reviewed_continuity' and self.admitted_from < self.source_observed_on:
                raise ValueError('Continuity cannot invent pre-observation history')
            if self.admission_basis == 'observed_snapshot' and not self.admitted_from == self.admitted_through == self.source_observed_on:
                raise ValueError('Snapshot provenance must describe one observed date')
            if self.admission_basis == 'established_history' and self.legal_effective_from is None:
                raise ValueError('Historical provenance needs its established lower bound')
            if self.legal_effective_from and self.service_date < self.legal_effective_from:
                raise ValueError('Admitted service predates its legal lower bound')
            if self.admission_basis == 'reviewed_continuity':
                through = checked.astimezone(ZoneInfo('Europe/Istanbul')).date().isoformat()
                if self.admitted_through > through:
                    raise ValueError('Public continuity cannot exceed the official review day')
        elif self.reason == "covered" or self.admission_basis is not None:
            raise ValueError("A review-required source cannot claim admitted coverage")
        return self


def bounded_source_authority(value):
    """Reject arbitrary/raw fields instead of passing extra data into public contracts."""
    if value is None:
        return None
    try:
        return ClinicalSourceAuthorityEvidence.model_validate(value).model_dump()
    except (ValidationError, TypeError):
        return None
