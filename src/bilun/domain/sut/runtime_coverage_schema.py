"""Strict request-level observed coverage DTO shared by API and validator."""
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from .runtime_coverage_contract import (
    bounded_runtime_coverage, RUNTIME_COUNTERS, RUNTIME_SOURCE_COUNTERS,
    RUNTIME_FLAGS, RUNTIME_SOURCE_IDS,
)

FamilyIdentifier = Annotated[str, StringConstraints(pattern=r'^[a-z][a-z0-9_]{0,63}$')]
SourceIdentifier = Annotated[str, StringConstraints(pattern=r'^[CF][0-9]{6}$')]
ReceiptDigest = Annotated[str, StringConstraints(pattern=r'^[0-9a-f]{64}$')]


class RuntimeCoverageResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    schema_version: Literal[1]
    available: bool
    instrumented_families: list[FamilyIdentifier] = Field(max_length=8)
    unavailable_reason: str | None = Field(default=None, max_length=500)
    source_metrics_available: bool | None = None
    complete_clause_mapping_available: bool | None = None
    source_unavailable_reason: str | None = Field(default=None, max_length=500)
    complete_clause_mapping_unavailable_reason: str | None = Field(default=None, max_length=500)
    source_clause_ids: list[SourceIdentifier] | None = Field(default=None, max_length=256)
    fully_evaluated_source_clause_ids: list[SourceIdentifier] | None = Field(default=None, max_length=256)
    receipt_sha256: ReceiptDigest | None = None
    clinical_eligibility_complete: Literal[False] = False
    input_facts_available_count: int | None = Field(default=None, ge=0)
    input_facts_missing_count: int | None = Field(default=None, ge=0)
    predicate_attempted_count: int | None = Field(default=None, ge=0)
    predicate_evaluated_count: int | None = Field(default=None, ge=0)
    predicate_passed_count: int | None = Field(default=None, ge=0)
    predicate_failed_count: int | None = Field(default=None, ge=0)
    predicate_missing_inputs_count: int | None = Field(default=None, ge=0)
    routes_blocked_source_count: int | None = Field(default=None, ge=0)
    routes_blocked_inputs_count: int | None = Field(default=None, ge=0)
    routes_skipped_count: int | None = Field(default=None, ge=0)
    receipt_count: int | None = Field(default=None, ge=0)
    unresolved_source_ref_count: int | None = Field(default=None, ge=0)
    source_clauses_touched_count: int | None = Field(default=None, ge=0)
    source_clauses_fully_evaluated_count: int | None = Field(default=None, ge=0)

    @model_validator(mode="before")
    @classmethod
    def validate_measured_summary(cls, raw):
        if not isinstance(raw, dict) or type(raw.get('schema_version')) is not int or raw['schema_version'] != 1:
            raise ValueError('Invalid runtime coverage schema')
        bounded = bounded_runtime_coverage(raw)
        if bounded is None or (raw.get('available') is True and bounded.get('available') is not True):
            raise ValueError('Invalid measured runtime coverage summary')
        # The bounded serializer deduplicates identity lists. A strict DTO must
        # not validate that normalized copy and then retain conflicting raw
        # cardinalities (e.g. two IDs with a touched-clause count of one).
        for key in ('instrumented_families', *RUNTIME_SOURCE_IDS):
            values = raw.get(key)
            if (isinstance(values, list) and all(isinstance(v, str) for v in values)
                    and len(values) != len(set(values))):
                raise ValueError('Runtime identity lists must contain unique values')
        if (type(raw.get('clinical_eligibility_complete', False)) is not bool
                or raw.get('clinical_eligibility_complete', False) is not False):
            raise ValueError('Runtime observations cannot establish complete clinical eligibility')
        if raw.get('available') is False and any(raw.get(k) is not None for k in (
                *RUNTIME_COUNTERS, *RUNTIME_SOURCE_COUNTERS, *RUNTIME_FLAGS,
                *RUNTIME_SOURCE_IDS, 'receipt_sha256')):
            raise ValueError('Unavailable measurements must not include measurement or source claims')
        return raw
