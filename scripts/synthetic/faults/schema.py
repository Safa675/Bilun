"""Fault-registry schema, version 1: pydantic models, mutation grammar and check-id registry.

The fault registry (data/synthetic/faults/fault_registry.yaml) declares the controlled billing
mutations that turn a clean expanded pathway bill into a faulty bill, together with the expected
engine finding and SUT provenance. No prices, amounts or totals exist in this schema.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated, Literal, Self

from pydantic import (
    Field,
    StrictBool,
    StrictInt,
    StrictStr,
    StringConstraints,
    field_validator,
    model_validator,
)
from pydantic_core import PydanticCustomError

from scripts.synthetic.pathways.schema import (
    Basis,
    IcdCode,
    Name,
    PathwayId,
    Problem as _PathwayProblem,
    Slug,
    Source,
    Sourced,
    Story,
    _Model,
)

SCHEMA_VERSION = 1

# The stories every registry must cover: the first cohort. A story is `S` and a number from 1 up
# (`Story`); later stories (S9 on) are added with their pathway and are not required here.
SHOWCASE_STORIES: tuple[str, ...] = ("S1", "S2", "S3", "S4", "S5", "S6", "S7", "S8")

MUTATION_OPS: tuple[str, ...] = (
    "use_sibling_pathway",
    "truncate_line_days",
    "drop_entry",
    "set_flag",
    "drop_diagnosis",
    "set_billed_ratio",
    "set_quantity",
)

# Every check id a fault-registry Problem may carry. A meta-test requires a mutation case for each.
CHECKS: tuple[str, ...] = (
    # loader.py: YAML syntax and raw-document hygiene
    "yaml.invalid",
    "hygiene.forbidden_key",
    "hygiene.anon_text",
    "hygiene.price_text",
    "hygiene.id_like_number",
    # schema.py: raised by pydantic while the registry loads
    "schema.unknown_field",
    "schema.missing_field",
    "schema.bad_enum",
    "schema.bad_value",
    "schema.sibling_alone",
    "schema.target_entry_shape",
    # checks.py: cross-pathway, catalog, detector and coverage checks
    "fault.target_pathway",
    "fault.entry_id",
    "fault.keep_day_indices",
    "fault.flag",
    "fault.drop_diagnosis",
    "fault.breaks_indication",
    "fault.billed_ratio_target",
    "fault.target_entry_id",
    "fault.evidence_entry_ids",
    "fault.applies",
    "fault.sut_clauses",
    "fault.source_cites",
    "fault.detectors",
    "fault.duplicate_id",
    "fault.duplicate_story",
    "fault.story_coverage",
    "fault.op_coverage",
)


@dataclass(frozen=True)
class Problem(_PathwayProblem):
    """One finding in the fault registry: a stable check id, where in the registry, and why."""

    def __post_init__(self) -> None:
        if self.check not in CHECKS:
            raise KeyError(f"unregistered check id {self.check!r}")


FaultId = Annotated[str, StringConstraints(pattern=r"^F_S[1-9][0-9]*_[A-Z][A-Z0-9_]{1,63}$")]
BilledRatio = Annotated[str, StringConstraints(pattern=r"^\d\.\d{4}$")]
ClauseId = Annotated[str, StringConstraints(pattern=r"^C[0-9]{6}$")]
DetectorRef = Annotated[
    str, StringConstraints(pattern=r"^[A-Za-z0-9_./-]+\.py:[A-Za-z_][A-Za-z0-9_]*$")
]
EngineRule = Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9_]{1,63}$")]
SutSection = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=40)]
FlagName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=64)]
FindingId = Annotated[
    StrictStr, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)
]


class UseSiblingPathway(_Model):
    """Replace the clean bill with `expand(sibling_pathway, same pins)`; must be the sole op."""

    op: Literal["use_sibling_pathway"]
    sibling_pathway_id: PathwayId


class TruncateLineDays(_Model):
    """Keep only the rows of a procedure line whose 0-based `day_index` is in `keep_day_indices`."""

    op: Literal["truncate_line_days"]
    section: Literal["procedures"]
    entry_id: Slug
    keep_day_indices: list[Annotated[int, Field(ge=0, strict=True)]] = Field(min_length=1)

    @field_validator("keep_day_indices")
    @classmethod
    def _distinct(cls, values: list[int]) -> list[int]:
        if len(set(values)) != len(values):
            raise PydanticCustomError(
                "bad_value", "keep_day_indices must be distinct non-negative integers", {}
            )
        return values


class DropEntry(_Model):
    """Remove every expanded row belonging to `entry_id` in `section`."""

    op: Literal["drop_entry"]
    section: Literal["procedures", "materials", "drugs", "performed"]
    entry_id: Slug


class SetFlag(_Model):
    """Set `flags[flag] = value` on every expanded row of `entry_id` in `section`; an empty text clears the flag.

    A value is a yes/no, a text or a whole number (`drug_report_duration_months`, slice G9: S44's report of 12 months);
    `fault.flag` holds it to the flag's own type."""

    op: Literal["set_flag"]
    section: Literal["procedures", "materials", "drugs"]
    entry_id: Slug
    flag: FlagName
    value: StrictBool | StrictInt | StrictStr


class DropDiagnosis(_Model):
    """Remove a secondary diagnosis row (`icd10`) from `diagnoses`."""

    op: Literal["drop_diagnosis"]
    icd10: IcdCode
    breaks_indication: StrictBool = False


class SetBilledRatio(_Model):
    """Set `billed_ratio` on every expanded row of procedure line `entry_id`."""

    op: Literal["set_billed_ratio"]
    entry_id: Slug
    billed_ratio: BilledRatio


# The largest unit count a pathway drug line holds (`Drug.qty`, 1..999); the engine reads a count above it as a
# unit confusion (El Kitabı Tablo 15 #11, `detect_drug_quantity_error`).
PATHWAY_MAX_DRUG_QTY = 999


class SetQuantity(_Model):
    """Set `qty` on every expanded row of drug line `entry_id` to a count no pathway can hold (above 999).

    The fault of a strength keyed as the count (4,000 for four syringes of 4000 anti-Xa IU): a count inside the
    pathway bound is a pathway's (or a sibling's), not a fault's.
    """

    op: Literal["set_quantity"]
    section: Literal["drugs"]
    entry_id: Slug
    qty: Annotated[int, Field(gt=PATHWAY_MAX_DRUG_QTY, le=99_999, strict=True)]


MutationOp = Annotated[
    UseSiblingPathway
    | TruncateLineDays
    | DropEntry
    | SetFlag
    | DropDiagnosis
    | SetBilledRatio
    | SetQuantity,
    Field(discriminator="op"),
]


class ExpectedFinding(_Model):
    """Expected engine finding and answer-key shape produced by a fault."""

    engine_rule: EngineRule
    detectors: list[DetectorRef] = Field(min_length=1)
    sut_section: SutSection
    sut_clauses: list[ClauseId] = Field(min_length=1)
    effect_kind: Literal["revenue_uplift", "deduction_risk", "compliance_error"]
    line_type: Literal["fatura", "islem", "malzeme", "ilac"]
    target_entry_id: Slug | None = None
    expected_status: Literal["eksik_faturalama", "kismi_red"]
    evidence_entry_ids: list[Slug] = Field(default_factory=list)
    finding_ids: list[FindingId] = Field(default_factory=list)

    @model_validator(mode="after")
    def _target_shape(self) -> Self:
        if self.line_type == "fatura" and self.target_entry_id is not None:
            raise PydanticCustomError(
                "target_entry_shape",
                "target_entry_id must be null when line_type is 'fatura'",
                {},
            )
        if self.line_type != "fatura" and self.target_entry_id is None:
            raise PydanticCustomError(
                "target_entry_shape",
                "target_entry_id is required when line_type is '{line_type}'",
                {"line_type": self.line_type},
            )
        return self


ExpectedFindingSpec = ExpectedFinding


class FaultSpec(Sourced):
    """One declarative billing fault, its mutation operations, expected finding and provenance."""

    fault_id: FaultId
    story: Story | None = None
    title: Name
    target_pathway: PathwayId
    mutations: list[MutationOp] = Field(min_length=1)
    expected_finding: ExpectedFinding
    basis: Basis
    source: Source

    @model_validator(mode="after")
    def _sibling_is_sole_mutation(self) -> Self:
        if any(m.op == "use_sibling_pathway" for m in self.mutations) and len(self.mutations) > 1:
            raise PydanticCustomError(
                "sibling_alone",
                "use_sibling_pathway must be the only mutation of its fault",
                {},
            )
        return self


class FaultRegistry(_Model):
    """Top-level fault registry document (`data/synthetic/faults/fault_registry.yaml`)."""

    schema_version: Literal[1]
    faults: list[FaultSpec] = Field(min_length=1)
