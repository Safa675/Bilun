"""Care-pathway schema, version 1: pydantic models, the day grammar and the pin rules.

A pathway is one YAML file, data/synthetic/pathways/<id>.yaml (grammar and examples in the README
next to it). This module holds what can be decided from the file alone: field shapes, the day
grammar, cross-references between lines and the rules a pin set must obey. Whether a code is real,
in force and named as listed is checks.py. No prices, amounts or totals exist in this schema.

Every model forbids unknown fields. Custom errors carry the check id they belong to (the part
after "schema." in CHECKS), so the loader can report them under a stable id.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from typing import Annotated, Literal, Self

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)
from pydantic_core import PydanticCustomError

SCHEMA_VERSION = 1

# Every check id a Problem may carry, with a one-line meaning. A test requires one mutation per id.
CHECKS: dict[str, str] = {
    # loader.py: the file and the raw document
    "yaml.invalid": "unreadable YAML, a repeated key, or a document that is not a mapping",
    "hygiene.forbidden_key": "a key named price, amount, total or package_candidate",
    "hygiene.anon_text": "text that looks like an ANON identifier (ANON_7, anon-7, ANON 7), in any case",
    "hygiene.price_text": "a non-zero currency amount in any string (12 TL, 12 TRY, 12 or lira sign 12)",
    "hygiene.id_like_number": "an 11-digit number in free text (a national id has 11 digits; a barcode 13)",
    "schema.id_mismatch": "the file name is not <id>.yaml",
    # schema.py: raised by pydantic while the file loads
    "schema.unknown_field": "a field the schema does not define",
    "schema.missing_field": "a required field (including basis and source) is absent",
    "schema.bad_enum": "a value outside the allowed list",
    "schema.bad_value": "a value of the wrong type, pattern, length or size",
    "schema.day_expression": "not admit|op|discharge with +-N whole days, or a..b",
    "schema.range_order": "min above max, or a window that starts after it ends",
    "schema.probability": "a probability outside [0, 1]",
    "schema.duplicate_id": "two lines share an id, or a diagnosis is listed twice",
    "schema.unknown_reference": "a link, operation or dependency names a line that cannot serve",
    "schema.anchor_undefined": "op used without op_day, or discharge used on an ER-only pathway",
    "schema.line_shape": "a line carries fields its kind does not allow, or lacks required ones",
    "schema.quantity_form": "a drug has no quantity form or several",
    "schema.diagnosis_primary": "not exactly one primary diagnosis",
    "schema.stay_shape": "nights missing on a stay, or present on an ER-only pathway",
    # checks.py: against the catalogs
    "procedure.in_force": "an EK-2B/EK-2C code missing on some day of the window",
    "procedure.name": "a procedure name that is not the catalog name",
    "procedure.kind": "a line kind that does not fit the code's EK-2B chapter",
    "material.in_force": "an EK-3/F-1 code missing on some day of the window",
    "material.name": "a material name that is not the catalog name",
    "drug.in_force": "an EK-4A barcode missing on some day of the window",
    "drug.name": "a drug name that is not the EK-4A name",
    "drug.inn": "an inn that is not the crosswalk's active ingredient",
    "drug.indication": "an indication diagnosis that is not in the pathway's bill",
    "drug.course": "a drug course that does not fit inside the stay",
    "icd.exists": "an ICD-10 code missing from the SKRS table",
    "icd.active": "an inactive ICD-10 code",
    "icd.leaf": "an ICD-10 code that is not a leaf",
    "icd.name": "a diagnosis name that is not the table's name_tr",
    "icd.sex_gate": "an ICD-10 sex gate that the pathway's sex list contradicts",
    "lab.in_table": "an L-code absent from lab_reference.csv",
    "lab.name": "a lab name that is not the table's catalog_name",
    "specialty.exists": "an EK-2A branch code that does not exist",
    "package.mode": "a package pathway with a line a package includes, or the reverse",
    "package.window": "a stay that outlasts the package window of its group",
    "anaesthesia.group": "an anaesthesia group that the operation's puan does not give",
    "anaesthesia.code": "an anaesthesia code that does not belong to its group",
    "session.primary": "a session without exactly one primary operation",
    "session.order": "a primary operation that is not the highest puan",
    "pins.out_of_range": "a pin outside the declared range or list",
    "pins.unknown_id": "a pin that names an id the pathway does not have",
    "pins.not_optional": "an include pin on a line that is not optional",
    "pins.missing": "a pin the expansion needs and the showcase block lacks",
    "pins.window": "pinned dates outside the service window",
    "days.in_stay": "a day that falls outside the stay for some nights in range",
    "days.duplicate": "a line that lands twice on the same day",
    "stay.coverage": "a bed line off admit..discharge, or a companion line off admit..discharge-1",
    "source.clause_exists": "a cited SUT clause id that does not exist or is not in force",
    "source.sut_cites": "basis sut without a clause id or an annex in the source",
    "window.valid": "a window outside the default service window",
}


@dataclass(frozen=True)
class Problem:
    """One finding: a stable check id, where in the pathway, and what is wrong."""

    check: str
    where: str
    message: str
    file: str = ""

    def __post_init__(self) -> None:
        if self.check not in CHECKS:
            raise KeyError(f"unregistered check id {self.check!r}")

    def __str__(self) -> str:
        prefix = f"{self.file}: " if self.file else ""
        return f"{prefix}{self.check} at {self.where}: {self.message}"


# --- day grammar ------------------------------------------------------------------------------
# A day is an anchor (admit, op, discharge) with an optional whole-day offset; a range a..b is
# inclusive. Nothing else.

_POINT = re.compile(r"(admit|op|discharge)(?:([+-])([1-9][0-9]{0,2}))?")


def parse_point(expr: str) -> tuple[str, int]:
    """'admit+2' -> ('admit', 2); raises ValueError when expr is not one anchor with an offset."""
    match = _POINT.fullmatch(expr)
    if match is None:
        raise ValueError(expr)
    sign = -1 if match[2] == "-" else 1
    return match[1], sign * int(match[3] or 0)


def parse_days(expr: str) -> tuple[tuple[str, int], tuple[str, int]]:
    """'a..b' -> (start, end) points; a single point has start == end."""
    first, dots, last = expr.partition("..")
    start = parse_point(first)
    return start, (parse_point(last) if dots else start)


def resolve_days(expr: str, anchors: dict[str, int]) -> list[int]:
    """The day numbers (admit = 0) an expression covers, in order."""
    (a_name, a_delta), (b_name, b_delta) = parse_days(expr)
    return list(range(anchors[a_name] + a_delta, anchors[b_name] + b_delta + 1))


def _day_spec(value: str) -> str:
    try:
        parse_days(value)
    except ValueError:
        raise PydanticCustomError(
            "day_expression",
            "'{value}' is not a day expression (admit, op or discharge, +-N days, or a..b)",
            {"value": value},
        ) from None
    return value


def _day_point(value: str) -> str:
    if ".." in value:
        raise PydanticCustomError(
            "day_expression", "'{value}' must be a single day, not a range", {"value": value}
        )
    return value


def _iso_date(value: str) -> str:
    try:
        ok = date.fromisoformat(value).isoformat() == value
    except ValueError:
        ok = False
    if not ok:
        raise PydanticCustomError("date_format", "'{value}' is not YYYY-MM-DD", {"value": value})
    return value


# --- field types -------------------------------------------------------------------------------

Basis = Literal["sut", "ek2b_aciklama", "medula_kilavuz", "guideline", "judgment"]
Kind = Literal[
    "package", "operation", "bed", "companion", "anaesthesia", "exam", "lab", "imaging", "procedure"
]
SessionRole = Literal["primary", "same_incision", "separate_incision"]
Group = Literal["A1", "A2", "A3", "B", "C", "D", "E"]
Unit = Literal["box", "vial", "ampoule", "bottle", "bag", "syringe", "tablet", "capsule"]

Source = Annotated[str, StringConstraints(strip_whitespace=True, min_length=10, max_length=160)]
Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=400)]
Slug = Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9_]{1,39}$")]  # a line id
PathwayId = Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9_]{1,79}$")]  # the file name
Pending = Annotated[str, StringConstraints(pattern=r"^#[0-9]+( Q[0-9]+)?$")]
ProcCode = Annotated[str, StringConstraints(pattern=r"^[A-Z]?[0-9]{6}$")]
MaterialCode = Annotated[str, StringConstraints(pattern=r"^[A-Z]{2}[0-9]{4}$")]
Barcode = Annotated[str, StringConstraints(pattern=r"^[0-9]{13}$")]
IcdCode = Annotated[str, StringConstraints(pattern=r"^[A-Z][0-9]{2}(\.[0-9A-Z]{1,4})?$")]
Specialty = Annotated[str, StringConstraints(pattern=r"^[0-9]{4}$")]
IsoDate = Annotated[str, AfterValidator(_iso_date)]
DaySpec = Annotated[str, AfterValidator(_day_spec)]
DayPoint = Annotated[str, AfterValidator(_day_spec), AfterValidator(_day_point)]


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Sourced(_Model):
    """Provenance every clinical item and every range carries."""

    basis: Basis
    source: Source


class _Range(Sourced):
    min: int
    max: int

    @model_validator(mode="after")
    def _ordered(self) -> Self:
        if self.min > self.max:
            raise PydanticCustomError(
                "range_order", "min {lo} is above max {hi}", {"lo": self.min, "hi": self.max}
            )
        return self


class AgeRange(_Range):
    min: int = Field(ge=0, le=120)
    max: int = Field(ge=0, le=120)


class NightsRange(_Range):
    min: int = Field(ge=1, le=60)
    max: int = Field(ge=1, le=60)


class CourseRange(_Range):
    min: int = Field(ge=1, le=60)
    max: int = Field(ge=1, le=60)


class Chance(Sourced):
    """Marks an item optional; the showcase pins say whether it is in."""

    probability: float

    @field_validator("probability")
    @classmethod
    def _unit_interval(cls, value: float) -> float:
        if not 0.0 <= value <= 1.0:
            raise PydanticCustomError(
                "probability", "probability {value} is outside [0, 1]", {"value": value}
            )
        return value


class SexChoice(Sourced):
    values: list[Literal["M", "F"]] = Field(min_length=1)

    @field_validator("values")
    @classmethod
    def _unique(cls, values: list[str]) -> list[str]:
        if len(set(values)) != len(values):
            raise PydanticCustomError("duplicate_id", "a sex is listed twice", {})
        return values


class Patient(_Model):
    sex: SexChoice
    age: AgeRange


class Department(_Model):
    name: Name  # the string the bill header carries, as the stories write it
    specialty: Specialty  # EK-2A branch code every line gets unless it names its own


class Window(_Model):
    """A narrowed service window; every code must be in force on every day of it.

    It carries a `source` (why it is narrowed) but no `basis`: the reason is a catalog fact.
    """

    start: IsoDate
    end: IsoDate
    source: Source

    @model_validator(mode="after")
    def _ordered(self) -> Self:
        if self.start > self.end:
            raise PydanticCustomError(
                "range_order",
                "window starts {a} after it ends {b}",
                {"a": self.start, "b": self.end},
            )
        return self


class Diagnosis(Sourced):
    icd10: IcdCode
    name: Name
    role: Literal["primary", "secondary"]
    day: DayPoint
    optional: Chance | None = None
    pending: Pending | None = None


class Item(_Model):
    code: ProcCode
    name: Name


class Procedure(Sourced):
    """An EK-2B/EK-2C line. One entry yields one bill line per day and per item."""

    id: Slug
    kind: Kind
    code: ProcCode | None = None
    name: Name | None = None
    items: list[Item] | None = Field(default=None, min_length=2)  # a lab panel
    days: list[DaySpec] = Field(min_length=1)
    qty: int = Field(default=1, ge=1, le=99)  # per bill line
    specialty: Specialty | None = None  # default: the department's
    session_role: SessionRole | None = None
    group: Group | None = None  # anaesthesia: the expected EK-2B group
    operations: list[Slug] | None = Field(default=None, min_length=1)  # anaesthesia: its session
    optional: Chance | None = None
    pending: Pending | None = None

    @field_validator("days", mode="before")
    @classmethod
    def _listify(cls, value: object) -> object:
        return [value] if isinstance(value, str) else value

    @model_validator(mode="after")
    def _shape(self) -> Self:
        problem = self._shape_problem()
        if problem:
            raise PydanticCustomError("line_shape", "{problem}", {"problem": problem})
        return self

    def _shape_problem(self) -> str:
        if (self.code is None) != (self.name is None):
            return "code and name go together"
        if (self.code is None) == (self.items is None):
            return "give code and name, or items (a lab panel); not both, not neither"
        if self.items is not None and self.kind != "lab":
            return "items (a panel) are only for kind lab"
        if self.items is not None and len({i.code for i in self.items}) != len(self.items):
            return "a panel lists a code twice; use two lines for a repeated test"
        if self.kind == "anaesthesia":
            if self.group is None or self.operations is None:
                return "an anaesthesia line needs group and operations"
        elif self.group is not None or self.operations is not None:
            return "group and operations are only for kind anaesthesia"
        if self.session_role is not None:
            if self.kind not in ("package", "operation"):
                return "session_role is only for kind package or operation"
            if len(self.days) != 1 or ".." in self.days[0]:
                return "a line with a session_role has one single day"
        return ""


class MaterialFlags(_Model):
    """Optional MaterialClaimLine fields a story sets (src/bilun/domain/claims/models.py)."""

    titubb_registered: bool | None = None
    uts_registered: bool | None = None


class DrugFlags(_Model):
    """Optional DrugClaimLine fields a story sets (src/bilun/domain/claims/models.py)."""

    drug_specialty_board_report_present: bool | None = None
    prescriber_specialty: str | None = None
    drug_inpatient_supply: bool | None = None


class Material(Sourced):
    """An EK-3/F-1 line, billed next to a package or an operation it is linked to."""

    id: Slug
    code: MaterialCode
    name: Name
    material_type: Literal["implant", "consumable"]
    qty: int = Field(default=1, ge=1, le=99)
    day: DayPoint
    linked_to: Slug  # id of the package or operation line that used it
    flags: MaterialFlags = Field(default_factory=MaterialFlags)
    optional: Chance | None = None
    pending: Pending | None = None


class Drug(Sourced):
    """An EK-4A line: one bill line on the first day of the course with the whole quantity."""

    id: Slug
    barcode: Barcode
    name: Name
    inn: Name  # the crosswalk's active_ingredient
    unit: Unit
    per_box: int = Field(ge=1, le=1000)
    day: DayPoint  # first day of the course
    qty: int | None = Field(default=None, ge=1, le=999)  # form 1: a fixed number of units
    per_night: int | None = Field(default=None, ge=1, le=99)  # form 2: units x nights of stay
    per_day: int | None = Field(default=None, ge=1, le=99)  # form 3: units x course days
    course_days: CourseRange | None = None
    indication: IcdCode | None = None  # a diagnosis of this pathway that the drug treats
    flags: DrugFlags = Field(default_factory=DrugFlags)
    optional: Chance | None = None
    pending: Pending | None = None

    @model_validator(mode="after")
    def _one_quantity_form(self) -> Self:
        forms = [self.qty is not None, self.per_night is not None, self.per_day is not None]
        ok = sum(forms) == 1 and (self.per_day is not None) == (self.course_days is not None)
        if not ok:
            raise PydanticCustomError(
                "quantity_form",
                "give exactly one of qty, per_night, or per_day with course_days",
                {},
            )
        return self


class Performed(Sourced):
    """A procedure logged as performed (EMR or PACS); the clean bill bills it too."""

    id: Slug
    code: ProcCode
    name: Name
    day: DayPoint
    system: Literal["emr", "pacs"]
    optional: Chance | None = None
    pending: Pending | None = None


class Pins(_Model):
    """The choices that turn a pathway into one bill: the showcase block, or P4's draw."""

    story: Annotated[str, StringConstraints(pattern=r"^S[1-8]$")]
    sex: Literal["M", "F"]
    age: int = Field(ge=0, le=120)
    admit: IsoDate  # first day of the stay; for an ER-only pathway, the visit day
    nights: int | None = Field(default=None, ge=1, le=60)
    include: list[str] = Field(default_factory=list)  # optional ids that are in
    course_days: dict[Slug, int] = Field(default_factory=dict)  # drug id -> chosen course days


class Pathway(_Model):
    schema_version: Literal[1]
    id: PathwayId
    title: Name
    claim_type: Literal["yatis", "acil"]
    billing_mode: Literal["package", "itemized"]
    department: Department
    window: Window | None = None
    patient: Patient
    nights: NightsRange | None = None
    op_day: DayPoint | None = None
    diagnoses: list[Diagnosis] = Field(min_length=1)
    procedures: list[Procedure] = Field(min_length=1)
    materials: list[Material] = Field(default_factory=list)
    drugs: list[Drug] = Field(default_factory=list)
    performed: list[Performed] = Field(default_factory=list)
    notes: list[Annotated[str, StringConstraints(max_length=600)]] = Field(default_factory=list)
    showcase: Pins

    @model_validator(mode="after")
    def _structure(self) -> Self:
        for check, problem in (
            ("stay_shape", self._stay_problem()),
            ("diagnosis_primary", self._primary_problem()),
            ("duplicate_id", self._duplicate_problem()),
            ("unknown_reference", self._reference_problem()),
            ("anchor_undefined", self._anchor_problem()),
        ):
            if problem:
                raise PydanticCustomError(check, "{problem}", {"problem": problem})
        return self

    def _stay_problem(self) -> str:
        if self.claim_type == "yatis" and self.nights is None:
            return "a yatis pathway needs nights"
        if self.claim_type == "acil" and self.nights is not None:
            return "an acil (ER-only) pathway has no nights"
        if self.claim_type == "acil" and any(d.per_night for d in self.drugs):
            return "a per_night drug needs a stay"
        return ""

    def _primary_problem(self) -> str:
        primaries = [d for d in self.diagnoses if d.role == "primary"]
        if len(primaries) != 1:
            return f"{len(primaries)} primary diagnoses; exactly one is required"
        return "the primary diagnosis cannot be optional" if primaries[0].optional else ""

    def _duplicate_problem(self) -> str:
        ids = [x.id for x in (*self.procedures, *self.materials, *self.drugs, *self.performed)]
        icds = [d.icd10 for d in self.diagnoses]
        dup = sorted({i for i in ids if ids.count(i) > 1} | {i for i in icds if icds.count(i) > 1})
        return f"duplicate ids: {', '.join(dup)}" if dup else ""

    def _reference_problem(self) -> str:
        lines = {p.id: p for p in self.procedures}
        for m in self.materials:
            target = lines.get(m.linked_to)
            if target is None or target.kind not in ("package", "operation"):
                return f"material {m.id} is linked to {m.linked_to!r}, not a package or operation"
            if target.code is None or len(target.days) != 1 or ".." in target.days[0]:
                return f"material {m.id}: line {target.id} must be one code on one day"
            if target.optional and not m.optional:
                return f"material {m.id} depends on optional line {target.id}; make it optional"
        for p in self.procedures:
            for op_id in p.operations or []:
                target = lines.get(op_id)
                if target is None or target.kind != "operation":
                    return f"anaesthesia {p.id} names {op_id!r}, which is not an operation line"
                if target.optional and not p.optional:
                    return f"anaesthesia {p.id} depends on optional operation {op_id}"
            codes = [lines[i].code for i in p.operations or [] if i in lines]
            if len(set(codes)) != len(codes):
                return f"anaesthesia {p.id}: two operations with one code in a session are not supported"
        return ""

    def _anchor_problem(self) -> str:
        for where, expr in day_expressions(self):
            for anchor, _ in parse_days(expr):
                if anchor == "op" and self.op_day is None:
                    return f"{where} uses op, but the pathway has no op_day"
                if anchor == "op" and where == "op_day":
                    return "op_day cannot be defined from op"
                if anchor == "discharge" and self.claim_type == "acil":
                    return f"{where} uses discharge on an ER-only pathway"
        return ""


def day_expressions(pathway: Pathway) -> list[tuple[str, str]]:
    """Every day expression in the pathway as (where, expression)."""
    out = [("op_day", pathway.op_day)] if pathway.op_day else []
    out += [(f"procedures[{p.id}].days", d) for p in pathway.procedures for d in p.days]
    out += [(f"diagnoses[{d.icd10}].day", d.day) for d in pathway.diagnoses]
    for name in ("materials", "drugs", "performed"):
        out += [(f"{name}[{x.id}].day", x.day) for x in getattr(pathway, name)]
    return out


def anchors_for(pathway: Pathway, nights: int | None) -> dict[str, int]:
    """Day numbers of the anchors for a stay of `nights` (admit = 0)."""
    anchors = {"admit": 0}
    if pathway.claim_type == "yatis" and nights is not None:
        anchors["discharge"] = nights
    if pathway.op_day is not None:
        anchors["op"] = resolve_days(pathway.op_day, anchors)[0]
    return anchors


def course_overrun(pathway: Pathway, drug: Drug, nights: int | None, days: int) -> int:
    """Days by which a course of `days` days from the drug's first day outlasts the stay (<= 0: fits)."""
    first = resolve_days(drug.day, anchors_for(pathway, nights))[0]
    return first + days - 1 - (nights or 0)


def included(item: object, pins: Pins) -> bool:
    """True when an item (line or diagnosis) is in the bill the pins describe."""
    optional = getattr(item, "optional", None)
    ident = getattr(item, "id", None) or getattr(item, "icd10", None)
    return optional is None or ident in pins.include


def pin_problems(pathway: Pathway, pins: Pins) -> list[Problem]:
    """Rules a pin set must obey, independent of any catalog: ranges, ids, and a drug course that
    ends by the discharge of the pinned stay. (The window is checked in checks.py.)"""
    out: list[Problem] = []

    def add(check: str, where: str, message: str) -> None:
        out.append(Problem(check, where, message))

    if pins.sex not in pathway.patient.sex.values:
        add(
            "pins.out_of_range",
            "showcase.sex",
            f"{pins.sex} is not in {pathway.patient.sex.values}",
        )
    age = pathway.patient.age
    if not age.min <= pins.age <= age.max:
        add("pins.out_of_range", "showcase.age", f"{pins.age} is outside {age.min}..{age.max}")
    if pathway.nights is None:
        if pins.nights is not None:
            add("pins.out_of_range", "showcase.nights", "an ER-only pathway has no nights")
    elif pins.nights is None:
        add("pins.missing", "showcase.nights", "a stay needs nights")
    elif not pathway.nights.min <= pins.nights <= pathway.nights.max:
        low, high = pathway.nights.min, pathway.nights.max
        add("pins.out_of_range", "showcase.nights", f"{pins.nights} is outside {low}..{high}")

    items = (*pathway.procedures, *pathway.materials, *pathway.drugs, *pathway.performed)
    optional = {x.id for x in items if x.optional} | {
        d.icd10 for d in pathway.diagnoses if d.optional
    }
    known = {x.id for x in items} | {d.icd10 for d in pathway.diagnoses}
    for ident in pins.include:
        if ident not in known:
            add("pins.unknown_id", "showcase.include", f"{ident!r} is not an id of this pathway")
        elif ident not in optional:
            add("pins.not_optional", "showcase.include", f"{ident!r} is not optional")

    drugs = {d.id: d for d in pathway.drugs}
    stay_known = pathway.nights is None or pins.nights is not None  # else pins.missing says so
    for ident, days in pins.course_days.items():
        drug = drugs.get(ident)
        if drug is None or drug.course_days is None:
            add("pins.unknown_id", "showcase.course_days", f"{ident!r} has no course_days range")
            continue
        if not drug.course_days.min <= days <= drug.course_days.max:
            low, high = drug.course_days.min, drug.course_days.max
            add(
                "pins.out_of_range",
                f"showcase.course_days.{ident}",
                f"{days} is outside {low}..{high}",
            )
        late = course_overrun(pathway, drug, pins.nights, days) if stay_known else 0
        if late > 0 and included(drug, pins):
            add(
                "drug.course",
                f"showcase.course_days.{ident}",
                f"{days} days end {late} day(s) after the discharge (stay of {pins.nights or 0} nights)",
            )
    for drug in pathway.drugs:
        if drug.course_days and included(drug, pins) and drug.id not in pins.course_days:
            add("pins.missing", f"showcase.course_days.{drug.id}", "the drug is in; pin its days")
    return out
