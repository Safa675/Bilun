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
from decimal import Decimal
from typing import Annotated, Literal, Self

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    StrictInt,
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
    "schema.anchor_undefined": "op used without op_day, or discharge used on a pathway without a stay (acil, poliklinik, gunubirlik)",
    "schema.line_shape": "a line carries fields its kind does not allow, or lacks required ones",
    "schema.quantity_form": "a drug has no quantity form or several",
    "schema.diagnosis_primary": "not exactly one primary diagnosis",
    "schema.stay_shape": "nights missing on a stay, or present on a pathway without a stay (acil, poliklinik, gunubirlik), or an arrival from an ICU on one; a span off gunubirlik and poliklinik; a per_night drug on a stay that may have no night",
    # checks.py: against the catalogs
    "procedure.in_force": "an EK-2B/EK-2C code missing on some day of the window",
    "procedure.name": "a procedure name that is not the catalog name",
    "procedure.kind": "a line kind that does not fit the code's EK-2B chapter (radiotherapy is chapter 8.1, imaging the rest of group 8), an ICU kind on a code that is not an ICU day or package, or a newborn_bed on a code that is not the incubator or the cot",
    "material.in_force": "an EK-3 code missing from its annex's list (EK-3/F-1 or EK-3/C-2) on some day of the window",
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
    "package.mode": "a package pathway with a line a package includes (an ICU line too), or the reverse; an ICU package is no surgical package; a drug beside haemodialysis session packages only; a blood component of C000694 is billed apart at its share",
    "package.window": "a stay that outlasts the package window of its group (an ICU or a haemodialysis session package has no group and no window)",
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
    "stay.coverage": "a bed line off admit..discharge, or a companion line off admit..discharge-1; on a newborn stay the ward and newborn bed lines together cover admit..discharge once each; on an ICU stay the bed and ICU lines cover admit..discharge-1 once each and the discharge day (the transfer day) holds no ICU line, and no newborn bed line sits beside it",
    "icu.day_pattern": "an ICU stay whose 510090 lines are not on the first and the last ICU day, or whose package lines are not on every day between",
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
# `imaging` and `radiotherapy` share EK-2B chapter group 8 (radyolojik görüntüleme ve tedavi): a radiotherapy line is a
# code of its chapter 8.1 (radyasyon onkolojisi: the clinical evaluation, design, planning, dose calculation, devices and
# the applications of a course, EK-2/B 8.1.1 to 8.1.6), an imaging line any other code of the group (slice of WP19).
Kind = Literal[
    "package",
    "operation",
    "bed",
    "newborn_bed",
    "icu_day",
    "icu_package",
    "companion",
    "anaesthesia",
    "exam",
    "lab",
    "imaging",
    "radiotherapy",
    "procedure",
]
# The two kinds of an intensive-care stay: the EK-2B day rate 510090 and an EK-2C ICU package
# (P552001-3, P552006-8). They are bed-day lines of their own (SUT 2.4.4.H), not surgical packages.
ICU_KINDS: tuple[str, ...] = ("icu_day", "icu_package")
# The kinds of the one bed line a calendar day of an ordinary stay carries: the ward bed (510010) and
# the newborn bed (Kuvöz 510070, Kot 510081). EK-2B gives the three the same text (yemek + yatak + vizit),
# so they are alternatives for one patient-day (src/bilun/domain/billing/claim_yatak_newborn_overlap.py).
BED_KINDS: tuple[str, ...] = ("bed", "newborn_bed")
SessionRole = Literal["primary", "same_incision", "separate_incision"]
# The kinds of a line of one session (SUT 2.2.2.A(5), C000659 to C000662: several procedures in one session,
# the later ones paid at a share of their puan): a surgical package or operation, and a procedure of EK-2B
# chapter 7 (an add-on such as the polypectomy of a colonoscopy; `check_procedure_kinds` ties the kind
# `procedure` to that chapter when it carries a role).
SESSION_KINDS: tuple[str, ...] = ("package", "operation", "procedure")
# The share of its list amount a blood component is billed at on the bill of an EK-2C package (slice G14): the package
# includes the blood (C007927, SUT 4.6.(4)), except these components, which the provider bills apart at a share of
# their puan (C000694, SUT 2.2.2.B-1.(1).e; C007927). On an itemized bill a blood component is billed in full (EK-2/B,
# C007926). `expand` bills a line with one of these codes on a package pathway at its share.
BLOOD_PACKAGE_SHARES: dict[str, Decimal] = {
    "705371": Decimal("0.36"),
    "705430": Decimal("0.36"),
    "705440": Decimal("0.36"),
    "705372": Decimal("0.24"),
    "705373": Decimal("0.24"),
    "705441": Decimal("0.20"),
    "705442": Decimal("0.28"),
    "705443": Decimal("0.28"),
}
Group = Literal["A1", "A2", "A3", "B", "C", "D", "E"]
Unit = Literal["box", "vial", "ampoule", "bottle", "bag", "syringe", "tablet", "capsule"]

Source = Annotated[str, StringConstraints(strip_whitespace=True, min_length=10, max_length=160)]
Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=400)]
Slug = Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9_]{1,39}$")]  # a line id
PathwayId = Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9_]{1,79}$")]  # the file name
# A showcase story: S and a number from 1 up, with no upper limit (S1..S8 are the first cohort,
# later stories are added one pathway at a time).
Story = Annotated[str, StringConstraints(pattern=r"^S[1-9][0-9]*$")]
Pending = Annotated[str, StringConstraints(pattern=r"^#[0-9]+( Q[0-9]+)?$")]
ProcCode = Annotated[str, StringConstraints(pattern=r"^[A-Z]?[0-9]{6}$")]
MaterialCode = Annotated[str, StringConstraints(pattern=r"^[A-Z]{2}[0-9]{4}$")]
Barcode = Annotated[str, StringConstraints(pattern=r"^[0-9]{13}$")]
# The EK-3 annex a material line is priced on (slice G7b): EK-3/F-1, the arthroplasty materials an operation uses,
# or EK-3/C-2, the external orthoses and prostheses given on a specialist report (a walker, OP1106).
Ek3Annex = Literal["EK-3F-1", "EK-3C-2"]
# What a material line of each annex is (`material_type`) and the kind of line it hangs on (`linked_to`): an
# EK-3/F-1 material is used in a package or an operation; an EK-3/C-2 device is prescribed at a visit, so it hangs
# on the examination of its bill (the claim loader wants every material line linked to a procedure line).
MATERIAL_TYPES: dict[str, tuple[str, ...]] = {"EK-3F-1": ("implant", "consumable"), "EK-3C-2": ("ortez", "protez")}
MATERIAL_LINK_KINDS: dict[str, tuple[str, ...]] = {"EK-3F-1": ("package", "operation"), "EK-3C-2": ("exam",)}
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
    # 0 nights: admitted and discharged on the same date (a stay under 24 hours, billed with the day bed 510120)
    min: int = Field(ge=0, le=60)
    max: int = Field(ge=0, le=60)


class SpanRange(_Range):
    """The days after the first day that a gunubirlik or poliklinik session claim runs (its last day is admit+span)."""

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


class Complaint(Sourced):
    """What the patient (or a relative) says on arrival: the `YAKINMA` of the clean tables.

    In the patient's words, never a diagnosis name or an ICD code (plausibility `ana.complaint_not_diagnosis`;
    practitioner review of 2026-10-30, plans/data/2026-10-30-synthetic-billing-realism-plan.md, A4).
    """

    text: Annotated[str, StringConstraints(strip_whitespace=True, min_length=10, max_length=300)]


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


class Copay(Sourced):
    """The patient's share of a line (SUT 1.8): the line is billed in full and SGK pays billed x (1 - rate).

    The composer sets `copay_rate_applicable`, `copay_rate` and the payable of the line from it (slice G5b);
    every other line pays what it bills. A rate is a share above 0 and below 1 with at most 2 decimals (0.20),
    because the claim loader reads `copay_rate` to the cent (`optional_money`).
    """

    rate: Annotated[Decimal, Field(gt=0, lt=1, decimal_places=2)]


class ProcedureFlags(_Model):
    """Optional ProcedureClaimLine fields a story sets, without money (slice G5a; src/bilun/domain/claims/models.py).

    `is_package_included` marks a line as a component bundled into a package (never the package line itself, #260):
    an outpatient examination flagged so is the vakabaşı error (El Kitabı Tablo 15 #3). `isbt128_barcode` is the
    ISBT 128 number MEDULA records for a blood component line (SUT 4.6).
    """

    is_package_included: bool | None = None
    isbt128_barcode: str | None = None


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
    copay: Copay | None = None  # the patient's share of every bill line of the entry (slice G5b)
    flags: ProcedureFlags = Field(default_factory=ProcedureFlags)  # line flags without money (slice G5a)
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
        if self.kind == "package" and self.flags.is_package_included:
            return "is_package_included marks a component bundled into a package, never the package line"
        if self.session_role is not None:
            if self.kind not in SESSION_KINDS:
                return "session_role is only for kind package, operation or procedure"
            if len(self.days) != 1 or ".." in self.days[0]:
                return "a line with a session_role has one single day"
        return ""


class MaterialFlags(_Model):
    """Optional MaterialClaimLine fields a story sets (src/bilun/domain/claims/models.py)."""

    titubb_registered: bool | None = None
    uts_registered: bool | None = None
    # the material needs an approval (a board decision) before it is billed (El Kitabı Tablo 15 #15; slice G5a)
    requires_pre_auth: bool | None = None


class DrugFlags(_Model):
    """Optional DrugClaimLine fields a story sets (src/bilun/domain/claims/models.py)."""

    drug_specialty_board_report_present: bool | None = None
    prescriber_specialty: str | None = None
    drug_inpatient_supply: bool | None = None
    # the months the drug's health report covers (slice G9): the engine compares it with the report duration a SUT
    # rule names (SUT 4.2.9.A-1: one month for an ESA in chronic kidney disease)
    drug_report_duration_months: Annotated[StrictInt, Field(ge=1, le=24)] | None = None


class Material(Sourced):
    """An EK-3 line: an EK-3/F-1 material billed next to the package or operation that used it, or an EK-3/C-2
    device billed with the examination of the visit that prescribed it (`annex`, slice G7b)."""

    id: Slug
    code: MaterialCode
    name: Name
    annex: Ek3Annex = "EK-3F-1"
    material_type: Literal["implant", "consumable", "ortez", "protez"]
    qty: int = Field(default=1, ge=1, le=99)
    day: DayPoint
    linked_to: Slug  # id of the line it hangs on: the package or operation (EK-3/F-1), the examination (EK-3/C-2)
    flags: MaterialFlags = Field(default_factory=MaterialFlags)
    optional: Chance | None = None
    pending: Pending | None = None

    @model_validator(mode="after")
    def _shape(self) -> Self:
        if self.material_type not in MATERIAL_TYPES[self.annex]:
            allowed = " or ".join(MATERIAL_TYPES[self.annex])
            problem = f"an {self.annex} material is {allowed}, not {self.material_type}"
            raise PydanticCustomError("line_shape", "{problem}", {"problem": problem})
        return self


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

    story: Story
    sex: Literal["M", "F"]
    age: int = Field(ge=0, le=120)
    admit: IsoDate  # first day of the stay; for a pathway without a stay (acil, poliklinik, gunubirlik), the visit day
    nights: int | None = Field(default=None, ge=0, le=60)  # 0: admission and discharge on one date
    # the last day of a gunubirlik or poliklinik session claim is admit+span (a pathway with a `span` range)
    span: int | None = Field(default=None, ge=1, le=60)
    include: list[str] = Field(default_factory=list)  # optional ids that are in
    course_days: dict[Slug, int] = Field(default_factory=dict)  # drug id -> chosen course days
    # A fact about the patient, not the bill: the patient's copay profile row `has_chronic_health_report`
    # (EK-1/A, SUT §1.8.5(7)). None: not known, the engine claims no EK-1/A waiver.
    chronic_health_report: StrictBool | None = None  # a number or a string is refused


class Pathway(_Model):
    schema_version: Literal[1]
    id: PathwayId
    title: Name
    # yatis is a stay (nights 0 is a stay of one date); acil, poliklinik and gunubirlik are visits: no nights, no
    # discharge, one date, or for a gunubirlik or poliklinik session claim the days admit..admit+span (`span`)
    claim_type: Literal["yatis", "acil", "poliklinik", "gunubirlik"]
    billing_mode: Literal["package", "itemized"]
    department: Department
    window: Window | None = None
    patient: Patient
    nights: NightsRange | None = None
    span: SpanRange | None = None  # a session claim over several dates (gunubirlik, poliklinik)
    op_day: DayPoint | None = None
    # The stay begins on the day the patient leaves an ICU bill of the same patient: that day's bed is paid by
    # the ICU bill (EK-2B 510090 covers yemek + yatak + vizit; src/bilun/domain/prose_rules/yatak_icu_overlap.py),
    # so the bed lines of this bill cover admit+1..discharge. A sibling without the flag bills the transfer day.
    arrives_from_icu: bool = False
    complaint: Complaint
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
        stay = self.claim_type == "yatis"
        if stay and self.nights is None:
            return "a yatis pathway needs nights"
        if not stay and self.nights is not None:
            return f"a {self.claim_type} pathway has no nights"
        if not stay and any(d.per_night for d in self.drugs):
            return "a per_night drug needs a stay"
        if stay and self.nights.min == 0 and any(d.per_night for d in self.drugs):
            return "a per_night drug needs a night; this stay may have none (nights.min 0)"
        if self.span is not None and self.claim_type not in ("gunubirlik", "poliklinik"):
            return f"a {self.claim_type} pathway has no span (a span is for gunubirlik and poliklinik session claims)"
        if not stay and self.arrives_from_icu:
            return f"a {self.claim_type} pathway cannot arrive from an ICU"
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
            kinds = MATERIAL_LINK_KINDS[m.annex]
            if target is None or target.kind not in kinds:
                return f"material {m.id} is linked to {m.linked_to!r}, not a {' or '.join(kinds)} line"
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
                if anchor == "discharge" and self.claim_type != "yatis":
                    return f"{where} uses discharge on a {self.claim_type} pathway"
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
    """Days by which a course of `days` days from the drug's first day outlasts the stay (<= 0: fits).

    `nights` is the last day of the bill: the nights of a stay, the span of a session claim, None for one date.
    """
    first = resolve_days(drug.day, anchors_for(pathway, nights))[0]
    return first + days - 1 - (nights or 0)


def last_day(pathway: Pathway, pins: Pins) -> int:
    """The day number of the bill's last day (admit = 0): the nights of a stay, the span of a session claim, else 0."""
    if pathway.nights is not None:
        return pins.nights or 0
    if pathway.span is not None:
        return pins.span or 0
    return 0


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
            add("pins.out_of_range", "showcase.nights", f"a {pathway.claim_type} pathway has no nights")
    elif pins.nights is None:
        add("pins.missing", "showcase.nights", "a stay needs nights")
    elif not pathway.nights.min <= pins.nights <= pathway.nights.max:
        low, high = pathway.nights.min, pathway.nights.max
        add("pins.out_of_range", "showcase.nights", f"{pins.nights} is outside {low}..{high}")
    if pathway.span is None:
        if pins.span is not None:
            add("pins.out_of_range", "showcase.span", f"a {pathway.claim_type} pathway without a span range has no span")
    elif pins.span is None:
        add("pins.missing", "showcase.span", "a session claim over several dates needs its span")
    elif not pathway.span.min <= pins.span <= pathway.span.max:
        low, high = pathway.span.min, pathway.span.max
        add("pins.out_of_range", "showcase.span", f"{pins.span} is outside {low}..{high}")

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
    # else pins.missing says so
    stay_known = (pathway.nights is None or pins.nights is not None) and (pathway.span is None or pins.span is not None)
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
        late = course_overrun(pathway, drug, last_day(pathway, pins), days) if stay_known else 0
        if late > 0 and included(drug, pins):
            add(
                "drug.course",
                f"showcase.course_days.{ident}",
                f"{days} days end {late} day(s) after the last day of the bill (day {last_day(pathway, pins)})",
            )
    for drug in pathway.drugs:
        if drug.course_days and included(drug, pins) and drug.id not in pins.course_days:
            add("pins.missing", f"showcase.course_days.{drug.id}", "the drug is in; pin its days")
    return out
