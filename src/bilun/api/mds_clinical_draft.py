"""Standalone MDS draft contracts; no endpoint or claim integration is registered.

The default helper returns the source/interpretation-gated runtime observation.
Candidate inspection is a separate local review helper, never a request mode.
Both results remain incomplete drafts and cannot establish payment eligibility.
"""
from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from types import SimpleNamespace
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from src.bilun.domain.billing.drug_clinical_evidence import bounded_clinical_restrictions
from src.bilun.domain.claims.clinical_evidence import clinical_date
from src.bilun.domain.claims.mds_evidence import parse_mds_evidence
from src.bilun.domain.prose_rules._drug_indication.clinical_mds import (
    evaluate_mds_clinical_candidate,
    evaluate_mds_clinical_draft,
)
from src.bilun.domain.validation_contract import ValidationClinicalRestriction


class MdsClinicalDraftRequest(BaseModel):
    """Optional facts use the strict domain parser, without Pydantic coercion.

    ``mds_evidence`` uses the domain parser as its sole fact boundary:
    only the bounded domain dataclass or None can survive this validator. Any
    invalid individual fact stays unknown, including values in typed objects.
    Unknown top-level keys are rejected, so no request can enable a release.
    """

    model_config = ConfigDict(extra="forbid", strict=True)

    drug_name: str = Field(min_length=1, max_length=240)
    selected_rule_id: str | None = Field(default=None, max_length=240)
    drug_claim_date: date | None = None
    observed_icd10_codes: list[str] | None = Field(default=None, max_length=64)
    mds_evidence: Any = None

    @field_validator("drug_claim_date", mode="before")
    @classmethod
    def parse_service_date(cls, value: Any) -> date | None:
        return clinical_date(value)

    @field_validator("observed_icd10_codes", mode="before")
    @classmethod
    def parse_observed_codes(cls, value: Any) -> list[str] | None:
        if type(value) is not list or any(type(code) is not str for code in value):
            return None
        return value

    @field_validator("mds_evidence", mode="before")
    @classmethod
    def parse_evidence(cls, value: Any):
        return parse_mds_evidence(value)


class MdsClinicalDraftResponse(BaseModel):
    """Bounded review output with a permanent disconnected-draft label."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    review_status: Literal["review_required"] = "review_required"
    is_draft: Literal[True] = True
    clinical_eligibility_complete: Literal[False] = False
    integration_status: Literal["not_registered"] = "not_registered"
    inspection_kind: Literal["gated_runtime", "local_candidate"]
    restriction: ValidationClinicalRestriction | None = None


def _request(value: MdsClinicalDraftRequest | Mapping[str, Any]) -> MdsClinicalDraftRequest:
    # Revalidate model_construct/model_copy objects as well as ordinary mappings.
    # No previously constructed request can bypass exact clinical parsing.
    raw = ({name: getattr(value, name) for name in MdsClinicalDraftRequest.model_fields
            if hasattr(value, name)} if isinstance(value, MdsClinicalDraftRequest) else dict(value))
    return MdsClinicalDraftRequest.model_validate(raw)


def _evaluate(
    value: MdsClinicalDraftRequest | Mapping[str, Any], *, candidate: bool,
) -> MdsClinicalDraftResponse:
    request = _request(value)
    line = SimpleNamespace(
        drug_name=request.drug_name,
        drug_claim_date=request.drug_claim_date,
        mds_evidence=request.mds_evidence,
    )
    evaluator = evaluate_mds_clinical_candidate if candidate else evaluate_mds_clinical_draft
    outcome = evaluator(line, request.selected_rule_id, codes=request.observed_icd10_codes)
    bounded = bounded_clinical_restrictions([outcome] if outcome is not None else [])
    restriction = ValidationClinicalRestriction.model_validate(bounded[0].to_dict()) if bounded else None
    return MdsClinicalDraftResponse(
        inspection_kind="local_candidate" if candidate else "gated_runtime",
        restriction=restriction,
    )


def evaluate_mds_draft_request(
    value: MdsClinicalDraftRequest | Mapping[str, Any],
) -> MdsClinicalDraftResponse:
    """Return the gated runtime draft; no clinical predicate bypass is exposed."""
    return _evaluate(value, candidate=False)


def inspect_mds_candidate_request(
    value: MdsClinicalDraftRequest | Mapping[str, Any],
) -> MdsClinicalDraftResponse:
    """Inspect candidate semantics locally; even clear checks remain draft review.

    This function has no registered endpoint and is never called by the default
    helper, the existing claim validator, or a caller-selected request flag.
    """
    return _evaluate(value, candidate=True)
