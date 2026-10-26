"""Contract, mutation and hygiene tests for `scripts/synthetic/cohort/plausibility.py` (plan D5, slices E1 and E2).

Every id in `plausibility.CHECKS` has at least one in-memory mutation case below. A case seeds ONE
defect into a copy of the tables of the nine clean twins (the showcase bills without their fault)
and proves that exactly the target id trips, plus the ids in `also` that the defect unavoidably
trips too (each one is explained next to its case). The `labels.*` cases start from the committed
faulty bills and their registry instead (`on_faulty`): the fault records exist only there, and the
case must add nothing but its own finding to what the faulty bills already trip. Nothing here
writes a file.

A mutation edits the lines of a bill the way a generator would: when a priced line changes, the
header totals follow (`sync_totals`), so a case trips `money.totals` only when it means to.

A case proves more than the ids: the NUMBER of findings of the target id and of the others, that one
finding of the target id has the right `where` (the claim, the table and the line id) and the right
`message`, that the findings come in the order of the registry and then by `where` and `message`,
and that a `where` about a line names a line that is there. The table of boundary pairs (`PAIRS`,
section 3b) holds, for each limit of a rule, the input just inside (it must not trip), the input
just outside (it trips, with this many findings) and the neighbours that must stay quiet. The
findings must not depend on the order of the rows (section 3c), and the helpers every check uses are
tested on their own (section 3d).

The contract:
1. the nine clean twins raise no problem;
2. the committed faulty bills trip exactly the pinned ids (`EXPECTED_FAULT_TRIPS`);
3. every id has an implementation, a short meaning and a mutation case;
4. the committed Parquet files give the same result as the in-memory tables.
"""

from __future__ import annotations

import ast
from collections.abc import Callable
import copy
import dataclasses
from datetime import date, timedelta
from decimal import ROUND_HALF_EVEN, ROUND_HALF_UP, Decimal
import inspect
import json
from pathlib import Path
import re
import subprocess
import sys

import polars as pl
import pytest

from scripts.synthetic.cohort import DEFAULT_OUT_DIR, build_showcase
from scripts.synthetic.cohort.catalogs import CohortCatalogs
from scripts.synthetic.cohort.ids import (
    claim_id,
    diagnosis_id,
    drug_claim_line_id,
    episode_id,
    material_line_id,
    patient_id,
    prescription_id,
    procedure_line_id,
)
from scripts.synthetic.cohort.plausibility import (
    AGE_GATES,
    CHECK_FUNCTIONS,
    CHECKS,
    EK3C2_FROM,
    EK3F1_FROM,
    FEMALE_ONLY_WHOLE_WORDS,
    FEMALE_ONLY_WORDS,
    ICD_SEX_GATES,
    LADDER_QUARTERS,
    MALE_ONLY_WORDS,
    NAME_EXCEPTIONS,
    NO_CLAIM,
    REGISTRATION_FLAGS,
    REGISTRY_CHECKS,
    STRUCTURAL_FLAGS,
    SURGICAL_SPECIALTY_CODES,
    TABLE_ANADATA,
    TABLE_ANSWERS,
    TABLE_CLAIM_HEADERS,
    TABLE_COPAY,
    TABLE_DIAGNOSES,
    TABLE_DRUGS,
    TABLE_MATERIALS,
    TABLE_PERFORMED,
    TABLE_PROCEDURES,
    PlausibilityContext,
    PlausibilityError,
    Problem,
    _cents,
    _as_of,
    _claim_text,
    _days_text,
    _fold,
    _format,
    _in_blocks,
    _is_cent_price_of,
    _problems,
    _tl,
    _where,
    _words_pattern,
    _without_exceptions,
    check_drug_price,
    check_material_price,
    check_plausibility,
    check_procedure_price,
    fold_text,
    run_all,
)
from scripts.synthetic.cohort.tables import TABLE_FILES, build_tables
from scripts.synthetic.faults import FaultInjectionRecord, build_expected_rule_outputs
from tests.fixtures import synthetic_cohort as cohort
from tests.fixtures.synthetic_encounters import STANDARD_EXTRAS, Extra, with_encounters

pytestmark = pytest.mark.unit

_REPO = Path(__file__).resolve().parents[3]
_MODULE = _REPO / "scripts/synthetic/cohort/plausibility.py"
_CLAIMS_DIR = DEFAULT_OUT_DIR / "sut/claims"
_CLEAN_DIR = DEFAULT_OUT_DIR / "sut/clean"
_REGISTRY_FILE = DEFAULT_OUT_DIR / "cohort_registry.json"

# The ids a mutation case may name; written out so a typo in a case fails at collection time.
ICD = "patient.icd_valid"
SEX = "patient.sex_gate"
AGE = "patient.age_gate"
ARITH = "patient.age_arithmetic"
PATHWAY = "fit.pathway_membership"
DEPT = "fit.operation_department"
SETTING = "fit.operation_setting"
VISIT = "fit.visit_code"
BED = "stay.bed_coverage"
COMP = "stay.companion_coverage"
DATES = "stay.dates_in_window"
PERF = "bill.performed_billed"
PACKAGE = "package.mode"
PAIRING = "anaesthesia.operation_pairing"
GROUP = "anaesthesia.group"
OPLINK = "material.operation_link"
ANSWER_ROWS = "labels.answer_rows"
AMOUNTS = "labels.amounts"

# What the committed faulty bill of each story trips (checked by the orchestrator with a prototype).
# S4's missing companion, S6's dropped diagnosis and the wrong ratios of S8 and S9 are invisible to plausibility
# (only the engine sees them); S5's flag is the one fault slice E2 sees. A story that trips nothing
# is a fault only the engine finds, not a hole in the checks.
EXPECTED_FAULT_TRIPS: dict[str, set[str]] = {
    "S1": {"package.mode"},
    "S2": {"stay.bed_coverage"},
    "S3": {"anaesthesia.operation_pairing"},
    "S4": set(),
    "S5": {"material.stray_flag"},
    "S6": set(),
    "S7": {"bill.performed_billed"},
    "S8": set(),
    "S9": set(),  # 25 % of the second operation is on the ladder: only the engine sees it
    "S10": set(),  # the manual haematocrit beside the hemogram: a lab line of the sibling pathway, only the engine (claim_lab) sees it
    "S11": set(),  # half the price of the ICU package days: only the engine (icu_puani) sees it
    "S12": {"stay.bed_coverage"},  # the first three incubator days are not billed: a bed day is missing (as S2)
    "S14": {"stay.bed_coverage"},  # the ward bed on the day the ICU bill ends: the ICU bill's 510090 already pays it
    "S15": {"stay.bed_coverage"},  # the ward bed beside the cot on the admission day: two bed lines on one day
    "S17": set(),  # the ESA prescribed by general surgery: no check reads a prescriber, only the engine (drug_indication) sees it
    "S18": set(),  # the albumin without the specialist report: no check reads a drug's report, only the engine (drug_indication) sees it
    "S24": set(),  # the red-cell units without their ISBT 128 numbers: no check reads the number, only the engine (4.6) sees it
    "S22": set(),  # the polypectomy beside the colonoscopy is not billed: a line is missing, only the engine (procedure_addon_uplift) sees it
    "S33": set(),  # the enoxaparin strength keyed as the count (4000 syringes): no check bounds a drug count, only the engine (tablo15_11) sees it
    "S34": set(),  # the control examination flagged as a package component: no check reads a procedure flag, only the engine (tablo15_3) sees it
    "S38": set(),  # the neuromonitoring beside an instrumentation that is not on EK-2/D-4: a listed package at its price, only the engine (conditional_addon_ek2d) sees it
    "S40": set(),  # the examination fee of a second visit to the same branch within 10 days: only the engine (tablo15_2) sees it
    "S46": set(),  # a second walker inside the MIAT of the first: a listed device at its price on the examination, only the engine (MIAT) sees it
    "S42": set(),  # the red cells billed in full inside the package: the full price is on the ladder, only the engine (blood_component_partial_bill) sees it
    "S44": set(),  # romosozumab on a report of 12 months: no check reads a drug's report, only the engine (drug_indication) sees it
    "S20": {"package.mode"},  # the day case billed itemized: package_candidate without a package line (as S1)
    "S21": set(),  # the radiotherapy course keyed as totals: listed codes at their price, no check reads a course or a session, only the engine (radiation_oncology) sees it
    "S47": {"stay.bed_coverage"},  # the day bed of a stay of one date is not billed: its one bed day is missing
    "S49": set(),  # the CRP and the ultrasound beside the green-area examination: lines of the sibling pathway, only the engine (tablo15_7) sees it
    "S50": set(),  # the two EK-2B procedures beside the ERCP package in full: the full price is on the ladder, only the engine (drg_unbundling) sees it
}

# The ids of slice E1 and of slice E2; later slices add their own to CHECKS.
E1_CHECKS = {
    "patient.icd_valid", "patient.sex_gate", "patient.age_gate", "patient.age_arithmetic",
    "fit.pathway_membership", "fit.operation_department", "fit.operation_setting",
    "fit.visit_code", "stay.bed_coverage", "stay.companion_coverage", "stay.dates_in_window",
    "bill.performed_billed", "package.mode", "anaesthesia.operation_pairing", "anaesthesia.group",
}  # fmt: skip
E2_CHECKS = {
    "material.operation_link", "material.stray_flag", "price.procedure_in_force",
    "price.material_in_force", "price.drug_in_force", "money.line_arithmetic",
    "money.payable_equals_billed", "money.totals", "labels.answer_rows", "labels.amounts",
}  # fmt: skip

STORIES = tuple(range(1, cohort.patient_count() + 1))  # patient numbers; one bill each
PATIENT = {n: patient_id(n) for n in STORIES}
CLAIM = {n: claim_id(PATIENT[n], 1) for n in STORIES}
EPISODE = {n: episode_id(PATIENT[n], 1) for n in STORIES}
CATALOGS = CohortCatalogs()
WARD = claim_id(PATIENT[10], 2)  # the ward bill of patient 10 (S14), after the ICU bill (S11): the committed second bill
CONTROL_CLAIM = claim_id(PATIENT[4], 2)  # the control visit of patient 4 (S39, a clean bill), nine days after her stay (S4)
SECOND_VISIT_CLAIM = claim_id(PATIENT[4], 3)  # her second visit (S40), a week after the control
# the control visit of patient 2 (S32, a clean bill) three weeks after his stay (S2): its examination is the one line of the
# cohort with a patient share (the copay flag, rate 0.20: billed 85.73, payable 68.58)
S2_CONTROL = claim_id(PATIENT[2], 2)
# the neurology control of patient 6 (S45, a clean bill): its walker, EK-3/C-2 OP1106 (slice G7b), is the one material of
# the cohort that is no EK-3/F-1 line; it hangs on the examination of the visit
WALKER_CLAIM = claim_id(PATIENT[6], 2)


# --- fixtures -----------------------------------------------------------------------------------


@pytest.fixture(scope="module")
def built(committed_showcase):
    return committed_showcase


@pytest.fixture(scope="module")
def context() -> PlausibilityContext:
    return PlausibilityContext()


@pytest.fixture(scope="module")
def twins(built) -> dict[str, pl.DataFrame]:
    """The tables of the nine clean twins: the showcase bills as the pathways expand them."""
    return build_tables(
        built.clean_claims,
        answer_rows=(),
        copay_profiles=built.copay_profiles,
        medula_events=(),
    )


@pytest.fixture(scope="module")
def anadata(built) -> pl.DataFrame:
    return built.clean_tables[TABLE_ANADATA]


# --- mutation primitives (Polars, on copies) ----------------------------------------------------


@dataclasses.dataclass
class Data:
    """A working copy of the claims tables, of anadata_clean and (labels) of the registry.

    DataFrames are never mutated. `registry` is None for the clean twins: the `labels.*` ids then
    do not run.
    """

    tables: dict[str, pl.DataFrame]
    anadata: pl.DataFrame
    registry: dict | None = None

    def problems(self, context: PlausibilityContext, only=None) -> list[Problem]:
        return check_plausibility(
            self.tables,
            {TABLE_ANADATA: self.anadata},
            context=context,
            only=only,
            registry=self.registry,
        )


def of(story: int) -> pl.Expr:
    """The rows of one story's claim."""
    return pl.col("claim_id") == CLAIM[story]


def line(story: int, code: str, day: str | None = None) -> pl.Expr:
    """A procedure line of the story's claim, by code (and day)."""
    expr = of(story) & (pl.col("procedure_code") == code)
    return expr if day is None else expr & (pl.col("procedure_date") == day)


def _value(frame: pl.DataFrame, column: str, value: object) -> pl.Expr:
    return value if isinstance(value, pl.Expr) else pl.lit(value, dtype=frame.schema[column])


PRICED_TABLES = (TABLE_PROCEDURES, TABLE_MATERIALS, TABLE_DRUGS)


def _cents_of(column: str) -> pl.Expr:
    return (pl.col(column) * 100).round(0).cast(pl.Int64)


def sync_totals(data: Data) -> None:
    """Let the header totals follow the lines, as a generator that bills from its lines does.

    A total is rewritten only when it is a cent or more off the lines, so a claim a mutation did not
    touch keeps its stored value to the last bit.
    """
    sums = (
        pl.concat(
            [
                data.tables[table].select(
                    "claim_id",
                    _cents_of("billed_amount_try").alias("billed"),
                    _cents_of("expected_payable_try").alias("payable"),
                )
                for table in PRICED_TABLES
            ]
        )
        .group_by("claim_id")
        .agg(pl.col("billed").sum(), pl.col("payable").sum())
    )
    headers = data.tables[TABLE_CLAIM_HEADERS]
    joined = headers.join(sums, on="claim_id", how="left").with_columns(
        pl.col("billed", "payable").fill_null(0)
    )
    data.tables[TABLE_CLAIM_HEADERS] = joined.with_columns(
        pl.when(_cents_of("expected_total_billed_try") != pl.col("billed"))
        .then(pl.col("billed") / 100)
        .otherwise(pl.col("expected_total_billed_try"))
        .alias("expected_total_billed_try"),
        pl.when(_cents_of("expected_total_payable_try") != pl.col("payable"))
        .then(pl.col("payable") / 100)
        .otherwise(pl.col("expected_total_payable_try"))
        .alias("expected_total_payable_try"),
    ).select(headers.columns)


def edit(data: Data, table: str, where: pl.Expr, **changes: object) -> None:
    """Set columns on the rows `where` selects (at least one must match)."""
    frame = data.tables[table]
    assert frame.filter(where).height > 0, f"the mutation selects no row of {table}"
    data.tables[table] = frame.with_columns(
        [
            pl.when(where)
            .then(_value(frame, column, value))
            .otherwise(pl.col(column))
            .alias(column)
            for column, value in changes.items()
        ]
    )
    if table in PRICED_TABLES:
        sync_totals(data)


def drop(data: Data, table: str, where: pl.Expr) -> None:
    """Delete the rows `where` selects (at least one must match)."""
    frame = data.tables[table]
    assert frame.filter(where).height > 0, f"the mutation selects no row of {table}"
    data.tables[table] = frame.filter(~where)
    if table in PRICED_TABLES:
        sync_totals(data)


def add_row(data: Data, table: str, template: pl.Expr, **values: object) -> None:
    """Append a copy of the first row `template` selects, with `values` set."""
    frame = data.tables[table]
    seed = frame.filter(template).head(1)
    assert seed.height == 1, f"no template row in {table}"
    row = seed.with_columns([_value(frame, c, v).alias(c) for c, v in values.items()])
    data.tables[table] = pl.concat([frame, row])
    if table in PRICED_TABLES:
        sync_totals(data)


def reprice(data: Data, table: str, where: pl.Expr, price: float) -> None:
    """Bill the selected lines at `price` a unit: billed amount and payable follow (price x quantity)."""
    amount = (pl.lit(price) * pl.col("quantity")).round(2)
    edit(
        data,
        table,
        where,
        unit_price_try=price,
        billed_amount_try=amount,
        expected_payable_try=amount,
    )


def edit_patient(data: Data, story: int, birth_year: int | None = None, **changes: object) -> None:
    """Change the anadata_clean row of the story's bill (and, with `birth_year`, its patient's copay profile)."""
    here = pl.col("SQ_EPISODE") == EPISODE[story]
    assert data.anadata.filter(here).height == 1
    data.anadata = data.anadata.with_columns(
        [
            pl.when(here).then(_value(data.anadata, c, v)).otherwise(pl.col(c)).alias(c)
            for c, v in changes.items()
        ]
    )
    if birth_year is not None:
        edit(data, TABLE_COPAY, pl.col("patient_id") == PATIENT[story], birth_year=birth_year)


def age_patient(data: Data, story: int, age: int, year: int = 2026) -> None:
    """The story's patient is `age` on every one of its bills (the bills of the cohort are dated in `year`): the
    TANI_YASI of each of its anadata rows and the birth year of its copay profile agree."""
    rows = pl.col("HASTA_ID") == PATIENT[story]
    data.anadata = data.anadata.with_columns(
        pl.when(rows).then(_value(data.anadata, "TANI_YASI", age)).otherwise(pl.col("TANI_YASI")).alias("TANI_YASI")
    )
    edit(data, TABLE_COPAY, pl.col("patient_id") == PATIENT[story], birth_year=year - age)


def _category(code: str) -> str:
    """procedure_category as the composer sets it (bed codes: yatak)."""
    if code.startswith("P"):
        return "paket"
    if code.startswith("L"):
        return "laboratuvar"
    if code in {"510010", "510120", "510121", "510090", "530000"}:
        return "yatak"
    return "muayene" if code.startswith("52") else "islem"


def _next_seq(frame: pl.DataFrame, story: int, id_column: str) -> int:
    used = frame.filter(of(story))[id_column].str.slice(-3).cast(pl.Int64).max()
    return used + 1


def line_id_of(data: Data, story: int, code: str) -> str:
    return data.tables[TABLE_PROCEDURES].filter(line(story, code))["procedure_line_id"][0]


def add_procedure(
    data: Data, story: int, code: str, day: str, *, specialty: str | None = None, quantity: int = 1
) -> None:
    """A new billed line with a catalog name and price, a fresh id and the right category."""
    frame = data.tables[TABLE_PROCEDURES]
    priced = CATALOGS.procedure_row(code, day)
    amount = round(float(priced.price) * quantity, 2)
    extra = {"procedure_specialty_code": specialty} if specialty else {}
    add_row(
        data,
        TABLE_PROCEDURES,
        of(story),
        procedure_line_id=procedure_line_id(
            CLAIM[story], _next_seq(frame, story, "procedure_line_id")
        ),
        procedure_date=day,
        procedure_code=code,
        procedure_name=priced.name,
        procedure_category=_category(code),
        quantity=quantity,
        unit_price_try=float(priced.price),
        billed_amount_try=amount,
        expected_payable_try=amount,
        **extra,
    )


def clone_procedure(data: Data, story: int, where: pl.Expr, **changes: object) -> None:
    """A copy of a billed line of the story's claim under a fresh id (code and price stay)."""
    frame = data.tables[TABLE_PROCEDURES]
    new_id = procedure_line_id(CLAIM[story], _next_seq(frame, story, "procedure_line_id"))
    add_row(data, TABLE_PROCEDURES, of(story) & where, procedure_line_id=new_id, **changes)


def add_diagnosis(data: Data, story: int, icd10: str, day: str | None = None) -> None:
    """A secondary diagnosis on the story's claim (dated like the first one, or on `day`)."""
    frame = data.tables[TABLE_DIAGNOSES]
    new_id = diagnosis_id(CLAIM[story], _next_seq(frame, story, "diagnosis_id"))
    when = {"diagnosis_date": day} if day else {}
    add_row(
        data,
        TABLE_DIAGNOSES,
        of(story),
        diagnosis_id=new_id,
        icd10_code=icd10,
        is_primary=False,
        diagnosis_role="secondary",
        **when,
    )


def set_code(data: Data, story: int, old: str, new: str, on: str | None = None) -> None:
    """Bill another code on a line: the line takes the catalog price of the new code on its day.

    The story must have one line of the code `old` (on the day `on`, when it has several).
    """
    selected = line(story, old, on)
    day = data.tables[TABLE_PROCEDURES].filter(selected)["procedure_date"].item()
    price = float(CATALOGS.procedure_row(new, day).price)
    amount = (pl.lit(price) * pl.col("quantity")).round(2)
    edit(
        data,
        TABLE_PROCEDURES,
        selected,
        procedure_code=new,
        unit_price_try=price,
        billed_amount_try=amount,
        expected_payable_try=amount,
    )


def rename(data: Data, story: int, code: str, name: str) -> None:
    edit(data, TABLE_PROCEDURES, line(story, code), procedure_name=name)


def replace_op(data: Data, story: int, old: str, new: str, day: str) -> None:
    """The billed line `old` becomes the line `new` of the catalog: its name, its price on `day`."""
    priced = CATALOGS.procedure_row(new, day)
    price = float(priced.price)
    edit(
        data,
        TABLE_PROCEDURES,
        line(story, old),
        procedure_code=new,
        procedure_name=priced.name,
        unit_price_try=price,
        billed_amount_try=price,
        expected_payable_try=price,
    )


def set_age(data: Data, story: int, age: int, *, sex: str | None = None, year: int = 2026) -> None:
    """The story's patient is `age` in `year` (and of `sex`): TANI_YASI and the birth year agree."""
    changes: dict[str, object] = {"TANI_YASI": age}
    if sex:
        changes["CINSIYET"] = sex
    edit_patient(data, story, birth_year=year - age, **changes)


_DATE_COLUMNS = {
    TABLE_CLAIM_HEADERS: ["admission_date", "discharge_date", "claim_start_date", "claim_end_date"],
    TABLE_PROCEDURES: ["procedure_date"],
    TABLE_MATERIALS: ["material_date"],
    TABLE_DRUGS: ["drug_claim_date"],
    TABLE_DIAGNOSES: ["diagnosis_date"],
    TABLE_PERFORMED: ["service_date"],
}


def shift_claim(data: Data, story: int, days: int) -> None:
    """Move every date of the story's claim by `days`, in all the tables that carry a date."""
    for table, columns in _DATE_COLUMNS.items():
        moved = [
            pl.when(of(story))
            .then(pl.col(c).str.to_date("%Y-%m-%d").dt.offset_by(f"{days}d").cast(pl.String))
            .otherwise(pl.col(c))
            .alias(c)
            for c in columns
        ]
        data.tables[table] = data.tables[table].with_columns(moved)


# the key column of each table a finding can name a row of
ROW_KEYS = {
    "claim_diagnoses": "diagnosis_id",
    "procedure_claim_lines": "procedure_line_id",
    "material_claim_lines": "material_line_id",
    "drug_claim_lines": "drug_claim_line_id",
    "performed_procedure_lines": "performed_line_id",
    "expected_rule_outputs": "expected_output_id",
}


def row_at(story: int, table: str, selector: pl.Expr) -> Callable[[Data], str]:
    """The `where` of a finding about the first row `selector` selects, read before the defect."""

    def find(base: Data) -> str:
        name = table.removesuffix(".parquet")
        ids = base.tables[table].filter(selector)[ROW_KEYS[name]].sort()
        assert len(ids) > 0, f"no row of {name} selected"
        return f"{CLAIM[story]} {name}[{ids[0]}]"

    return find


def new_row_at(story: int, table: str) -> Callable[[Data], str]:
    """The `where` of a finding about the row a defect appends: the next id of the story's claim."""
    makers = {
        TABLE_PROCEDURES: procedure_line_id,
        TABLE_DIAGNOSES: diagnosis_id,
        TABLE_MATERIALS: material_line_id,
    }

    def find(base: Data) -> str:
        name = table.removesuffix(".parquet")
        frame = base.tables[table]
        return f"{CLAIM[story]} {name}[{makers[table](CLAIM[story], _next_seq(frame, story, ROW_KEYS[name]))}]"

    return find


_ROW_WHERE = re.compile(r"^(?P<claim>\S+) (?P<table>[a-z_]+)\[(?P<key>[^\]]*)\]$")


def names_a_real_row(problem: Problem, tables: dict[str, pl.DataFrame]) -> bool:
    """A finding about `claim table[key]` names a row of that table that belongs to that claim."""
    found = _ROW_WHERE.match(problem.where)
    if found is None or found["table"] not in ROW_KEYS:
        return True  # a finding about a claim, a day, a header or the registry: no row to look up
    frame = tables[found["table"] + ".parquet"]
    claim = (
        pl.col("claim_id").is_null()
        if found["claim"] == NO_CLAIM
        else pl.col("claim_id") == found["claim"]
    )
    key = pl.col(ROW_KEYS[found["table"]]) == found["key"]
    return frame.filter(claim & key).height > 0


def only_ids(found: list[Problem]) -> set[str]:
    return {problem.check for problem in found}


# --- the mutation cases ---------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class Case:
    """One seeded defect.

    `at` and `says` are fragments that one finding of the target id must carry in its `where` and its
    `message`: the case proves the right line and the right reason, not only the id (every case sets
    both). `at` may be a function of the data before the defect, for a line whose id is read there
    (`row_at`, `new_row_at`). `n` is the number of findings the defect adds to the target id, and
    `also_n` the number it adds to the `also` ids together (one for each id when it is None): a
    check that reports too much or too little is caught by the count. `on_faulty` starts from the
    committed faulty bills and their registry (the `labels.*` cases); the findings that already
    exist there are not counted.
    """

    check: str
    mutate: Callable[[Data], None]
    also: tuple[str, ...] = ()
    label: str = ""
    at: str | Callable[[Data], str] = ""
    says: str = ""
    on_faulty: bool = False
    n: int = 1
    also_n: int | None = None

    @property
    def name(self) -> str:
        return f"{self.check}-{self.label}" if self.label else self.check


def _s2_control_exam() -> pl.Expr:
    """The examination of patient 2's control visit (S32): the one line with a patient share."""
    return (pl.col("claim_id") == S2_CONTROL) & (pl.col("procedure_code") == "520030")


def _ward(code: str, day: str | None = None) -> pl.Expr:
    """A procedure line of the ward bill of patient 10 (S14), by code (and day)."""
    expr = (pl.col("claim_id") == WARD) & (pl.col("procedure_code") == code)
    return expr if day is None else expr & (pl.col("procedure_date") == day)


def _second_operation(d: Data) -> None:
    # a second chapter-6 operation on the day of S3's decompression, in a surgical branch
    add_procedure(d, 3, "603030", "2026-08-18", specialty="2400")


def _move_last_bed_after_discharge(d: Data) -> None:
    edit(d, TABLE_PROCEDURES, line(2, "510010", "2026-03-15"), procedure_date="2026-03-16")


def _bill_every_bed_day_as_a_day_bed(d: Data) -> None:
    # S2's seven ward-bed days (03-09 .. 03-15), each billed as the day bed at its catalog price
    days = d.tables[TABLE_PROCEDURES].filter(line(2, "510010"))["procedure_date"].to_list()
    for day in days:
        set_code(d, 2, "510010", "510120", day)


def _newborn_grown_to_34(d: Data) -> None:
    # S12's baby grown to 34 (the birth year follows, so only the age gate is wrong): P07.3, P59.9 and Z38.0. Its ward
    # bill S15 is left out of this world, so the defect stays on one bill (S15's P07.3 and P59.9 would trip as well)
    ward = pl.col("claim_id") == claim_id(PATIENT[11], 2)
    for table in (TABLE_CLAIM_HEADERS, TABLE_DIAGNOSES, TABLE_PROCEDURES):
        drop(d, table, ward)
    d.anadata = d.anadata.filter(pl.col("SQ_EPISODE") != episode_id(PATIENT[11], 2))
    age_patient(d, 11, 34)


def _adult_name_on_a_child(d: Data) -> None:
    # S1 becomes a 12-year-old on every bill (age and birth year agree, so only the name is wrong)
    age_patient(d, 1, 12)
    rename(d, 1, "P610131", "Erişkin tedavisel soğutma")


def _performed_line_a_day_late(d: Data) -> None:
    edit(
        d,
        TABLE_PERFORMED,
        (pl.col("claim_id") == CLAIM[7]) & (pl.col("procedure_code") == "530100"),
        service_date="2026-02-20",
    )


def _material_on(d: Data, code: str) -> None:
    # S5's first material, billed on the line `code` of S3's claim (S3's lines are dated 2026-08-18)
    add_row(
        d,
        TABLE_MATERIALS,
        of(5),
        material_line_id=material_line_id(CLAIM[3], 1),
        claim_id=CLAIM[3],
        patient_id=PATIENT[3],
        procedure_line_id=line_id_of(d, 3, code),
        material_date="2026-08-18",
    )


def _extra_material(d: Data) -> None:
    # S5's first material, billed on S3's decompression (a chapter-6 operation: the link is fine)
    _material_on(d, "615931")


def _extra_drug(d: Data) -> None:
    # S4's IV paracetamol (Paracerol), which S6's ward pathway does not hold, prescribed to S6
    add_row(
        d,
        TABLE_DRUGS,
        of(4) & (pl.col("barkod") == "8699606694649"),
        drug_claim_line_id=drug_claim_line_id(CLAIM[6], 99),
        prescription_id=prescription_id(CLAIM[6]),
        claim_id=CLAIM[6],
        patient_id=PATIENT[6],
        episode_id=EPISODE[6],
        drug_claim_date="2026-06-08",
    )


# --- helpers of the slice E2 cases ------------------------------------------------------------------


def mat(n: int) -> pl.Expr:
    """The n-th material line of S5's claim (the EK-3/F-1 implants of the hemiarthroplasty)."""
    return pl.col("material_line_id") == material_line_id(CLAIM[5], n)


def mat_at(n: int) -> str:
    """The `where` of a finding about S5's n-th material line, after the claim id."""
    return f"{CLAIM[5]} material_claim_lines[{material_line_id(CLAIM[5], n)}]"


def walker() -> pl.Expr:
    """The walker of S45's bill (EK-3/C-2 OP1106, its one material line)."""
    return pl.col("material_line_id") == material_line_id(WALKER_CLAIM, 1)


def walker_at() -> str:
    """The `where` of a finding about S45's walker."""
    return f"{WALKER_CLAIM} material_claim_lines[{material_line_id(WALKER_CLAIM, 1)}]"


def drug(story: int, n: int) -> pl.Expr:
    """The n-th drug line of the story's claim."""
    return pl.col("drug_claim_line_id") == drug_claim_line_id(CLAIM[story], n)


def fault_of(data: Data, story: int) -> dict:
    """The registry's fault record of the story's claim."""
    return next(fault for fault in data.registry["faults"] if fault["claim_id"] == CLAIM[story])


def relabel_answers(data: Data) -> None:
    """Rebuild expected_rule_outputs from the registry's records, as the generator does."""
    records = [FaultInjectionRecord.model_validate(fault) for fault in data.registry["faults"]]
    rows = build_expected_rule_outputs(records)
    data.tables[TABLE_ANSWERS] = build_tables((), answer_rows=rows, copay_profiles=())[
        TABLE_ANSWERS
    ]


def edit_fault(data: Data, story: int, *, relabel: bool = True, **changes: object) -> None:
    """Change the story's fault record in the registry.

    The answer rows follow the records, as in the generator (`relabel`); a record that no longer
    validates cannot be rebuilt into an answer row, so those cases keep the committed answer rows.
    """
    fault_of(data, story).update(changes)
    if relabel:
        relabel_answers(data)


def _record_names_a_claim_without_a_header(d: Data) -> None:
    # S3's record copied to a claim that has no header, with its answer row (rebuilt from the records)
    ghost = "F-SENTETIK-HASTA-0099-001"
    record = copy.deepcopy(fault_of(d, 3))
    record.update(
        claim_id=ghost,
        patient_id="SENTETIK-HASTA-0099",
        injection_id=f"INJ-{ghost}-{record['fault_id']}",
    )
    d.registry["faults"].append(record)
    relabel_answers(d)


def _forget_a_record(d: Data) -> None:
    # S6's record is gone from the registry, its answer row is not
    d.registry["faults"] = [f for f in d.registry["faults"] if f["claim_id"] != CLAIM[6]]


def _swap_two_answer_rows(d: Data) -> None:
    rows = d.tables[TABLE_ANSWERS]
    after = rows["claim_id"].to_list().index(CLAIM[3])  # S3's row and the one before it (S34's, the last bill of S2's patient)
    order = list(range(rows.height))
    order[after - 1], order[after] = after, after - 1
    d.tables[TABLE_ANSWERS] = rows[order]


I10_OF_2 = of(2) & (pl.col("icd10_code") == "I10")  # S2's primary diagnosis


def performed(story: int, code: str) -> pl.Expr:
    """The performed lines of the story's claim with this code."""
    return of(story) & (pl.col("procedure_code") == code)


CASES: list[Case] = [
    # --- patient.icd_valid. A code that is not in the pathway is also outside its expansion.
    Case(
        ICD,
        lambda d: edit(d, TABLE_DIAGNOSES, I10_OF_2, icd10_code="J99.99"),
        also=(PATHWAY,),
        label="unknown_code",
        at=row_at(2, TABLE_DIAGNOSES, I10_OF_2),
        says="diagnosis J99.99 dated 2026-03-09: the code is not in icd10_tr",
    ),
    Case(
        ICD,
        # Z22.5: inactive, and passive since 2026-02-16, before S2's diagnosis date
        lambda d: edit(d, TABLE_DIAGNOSES, I10_OF_2, icd10_code="Z22.5"),
        also=(PATHWAY,),
        label="inactive_and_passive_code",
        at=row_at(2, TABLE_DIAGNOSES, I10_OF_2),
        says="diagnosis Z22.5 dated 2026-03-09: the code is inactive, has been passive since 2026-02-16",
    ),
    Case(
        ICD,
        # K35 is the category of K35.9 (acute appendicitis): not a leaf
        lambda d: edit(d, TABLE_DIAGNOSES, of(1), icd10_code="K35"),
        also=(PATHWAY,),
        label="not_a_leaf",
        at=row_at(1, TABLE_DIAGNOSES, of(1)),
        says="diagnosis K35 dated 2026-07-14: the code is not a leaf code",
    ),
    Case(
        ICD,
        # F99 exists since 2026-07-22; S2's diagnosis is dated 2026-03-09
        lambda d: edit(d, TABLE_DIAGNOSES, I10_OF_2, icd10_code="F99"),
        also=(PATHWAY,),
        label="created_after_the_diagnosis_date",
        at=row_at(2, TABLE_DIAGNOSES, I10_OF_2),
        says="diagnosis F99 dated 2026-03-09: the code was created on 2026-07-22, after the diagnosis date",
    ),
    # --- patient.sex_gate. The name cases rename a billed line: the check reads the name only.
    Case(
        SEX,
        lambda d: add_diagnosis(d, 1, "C53.9"),  # cervix carcinoma on S1, a man
        also=(PATHWAY,),
        label="icd_gate_female_code_on_a_man",
        at=new_row_at(1, TABLE_DIAGNOSES),
        says="diagnosis C53.9 is limited to sex F but the patient is M",
    ),
    Case(
        SEX,
        lambda d: add_diagnosis(d, 3, "C61"),  # prostate carcinoma on S3, a woman
        also=(PATHWAY,),
        label="icd_gate_male_code_on_a_woman",
        at=new_row_at(3, TABLE_DIAGNOSES),
        says="diagnosis C61 is limited to sex M but the patient is F",
    ),
    Case(
        SEX,
        # the icd10_tr `sex` column gates no code outside chapters C and D: the ICD-10 blocks do
        lambda d: add_diagnosis(d, 3, "N41.0"),  # acute prostatitis on S3, a woman
        also=(PATHWAY,),
        label="icd_block_male_code_on_a_woman",
        at=new_row_at(3, TABLE_DIAGNOSES),
        says="diagnosis N41.0 is limited to sex M but the patient is F",
    ),
    Case(
        SEX,
        lambda d: add_diagnosis(d, 1, "N80.0"),  # endometriosis of the uterus on S1, a man
        also=(PATHWAY,),
        label="icd_block_female_code_on_a_man",
        at=new_row_at(1, TABLE_DIAGNOSES),
        says="diagnosis N80.0 is limited to sex F but the patient is M",
    ),
    Case(
        SEX,
        lambda d: add_diagnosis(d, 2, "E28.2"),  # polycystic ovary syndrome on S2, a man
        also=(PATHWAY,),
        label="icd_block_ovarian_dysfunction_on_a_man",
        at=new_row_at(2, TABLE_DIAGNOSES),
        says="diagnosis E28.2 is limited to sex F but the patient is M",
    ),
    Case(
        SEX,
        lambda d: add_diagnosis(d, 8, "N43.3"),  # hydrocele on S8, a woman
        also=(PATHWAY,),
        label="icd_block_hydrocele_on_a_woman",
        at=new_row_at(8, TABLE_DIAGNOSES),
        says="diagnosis N43.3 is limited to sex M but the patient is F",
    ),
    Case(
        SEX,
        lambda d: add_diagnosis(d, 1, "Z34.0"),  # supervision of a normal pregnancy, a man
        also=(PATHWAY,),
        label="icd_block_pregnancy_contact_on_a_man",
        at=new_row_at(1, TABLE_DIAGNOSES),
        says="diagnosis Z34.0 is limited to sex F but the patient is M",
    ),
    Case(
        SEX,
        lambda d: rename(d, 1, "P610131", "Vajinal histerektomi"),
        label="name_female_word_on_a_man",
        at=row_at(1, TABLE_PROCEDURES, line(1, "P610131")),
        says="procedure P610131 (Vajinal histerektomi) is a female-only word (vajin) but the patient is M",
    ),
    Case(
        SEX,
        lambda d: rename(d, 3, "L104780", "Prostat spesifik antijen (PSA), total"),
        label="name_male_word_on_a_woman",
        at=row_at(3, TABLE_PROCEDURES, line(3, "L104780")),
        says="procedure L104780 (Prostat spesifik antijen (PSA), total) is a male-only word (prostat) but the patient is F",
    ),
    Case(
        SEX,
        lambda d: rename(d, 1, "P610131", "Over detorsiyonu"),
        label="name_whole_word_over_on_a_man",
        at=row_at(1, TABLE_PROCEDURES, line(1, "P610131")),
        says="(Over detorsiyonu) is a female-only word (over) but the patient is M",
    ),
    Case(
        SEX,
        lambda d: rename(d, 3, "L104780", "SÜNNET DERİSİ"),  # upper-case Turkish letters
        label="name_upper_case_turkish_word_on_a_woman",
        at=row_at(3, TABLE_PROCEDURES, line(3, "L104780")),
        says="(SÜNNET DERİSİ) is a male-only word (sunnet) but the patient is F",
    ),
    Case(
        SEX,
        lambda d: (edit_patient(d, 2, CINSIYET="?"), rename(d, 2, "L101850", "Testis biyopsisi")),
        label="name_word_for_a_patient_of_unknown_sex",
        n=2,  # S2 bills the code L101850 on two lines
        at=row_at(2, TABLE_PROCEDURES, line(2, "L101850")),
        says="(Testis biyopsisi) is a male-only word (testis) but the patient is of unknown sex",
    ),
    Case(
        SEX,
        lambda d: (
            edit_patient(d, 2, CINSIYET="?"),
            rename(d, 2, "L101850", "Vajinal histerektomi"),
        ),
        label="name_female_word_for_a_patient_of_unknown_sex",
        n=2,  # S2 bills the code L101850 on two lines
        at=row_at(2, TABLE_PROCEDURES, line(2, "L101850")),
        says="(Vajinal histerektomi) is a female-only word (vajin) but the patient is of unknown sex",
    ),
    Case(
        SEX,
        lambda d: rename(d, 3, "L104780", "İnguinal orşiyektomi, tek taraf"),  # a catalog name
        label="name_catalog_word_orsiyektomi_on_a_woman",
        at=row_at(3, TABLE_PROCEDURES, line(3, "L104780")),
        says="(İnguinal orşiyektomi, tek taraf) is a male-only word (orsiyektomi) but the patient is F",
    ),
    Case(
        SEX,
        lambda d: rename(d, 8, "P603840", "Hipospadias onarımı, distal"),  # a catalog name
        label="name_catalog_word_hipospadias_on_a_woman",
        at=row_at(8, TABLE_PROCEDURES, line(8, "P603840")),
        says="(Hipospadias onarımı, distal) is a male-only word (hipospad) but the patient is F",
    ),
    Case(
        SEX,
        lambda d: rename(d, 6, "L101850", "Kolposkopi"),  # a catalog name, S6 is a man
        label="name_catalog_word_kolposkopi_on_a_man",
        n=2,  # S6 bills the code L101850 on two lines
        at=row_at(6, TABLE_PROCEDURES, line(6, "L101850")),
        says="(Kolposkopi) is a female-only word (kolposkop) but the patient is M",
    ),
    # --- patient.age_gate
    Case(
        AGE,
        lambda d: add_diagnosis(d, 2, "P07.3"),  # a perinatal code on an 81-year-old
        also=(PATHWAY,),
        label="perinatal_code_on_an_adult",
        at=new_row_at(2, TABLE_DIAGNOSES),
        says="P07.3 is a perinatal condition (ICD chapter P) and needs age at most 1; the patient is M aged 81",
    ),
    Case(
        AGE,
        lambda d: add_diagnosis(d, 1, "O80.9"),  # a pregnancy code on a man aged 34
        also=(PATHWAY,),
        label="pregnancy_code_on_a_man",
        at=new_row_at(1, TABLE_DIAGNOSES),
        says="O80.9 is a pregnancy condition (ICD chapter O) and needs sex F, age 10..55; the patient is M aged 34",
    ),
    Case(
        AGE,
        lambda d: add_diagnosis(d, 7, "O80.9"),  # a pregnancy code on a woman aged 58
        also=(PATHWAY,),
        label="pregnancy_code_on_a_woman_past_55",
        at=new_row_at(7, TABLE_DIAGNOSES),
        says="needs sex F, age 10..55; the patient is F aged 58",
    ),
    Case(
        AGE,
        lambda d: add_diagnosis(d, 3, "Z38.0"),  # a liveborn code on a 77-year-old
        also=(PATHWAY,),
        label="liveborn_code_on_an_adult",
        at=new_row_at(3, TABLE_DIAGNOSES),
        says="Z38.0 is a liveborn infant code (Z38) and needs age at most 1; the patient is F aged 77",
    ),
    Case(
        AGE,
        _newborn_grown_to_34,
        label="the_newborn_stay_of_a_34_year_old",
        n=3,
        at=row_at(11, TABLE_DIAGNOSES, of(11) & (pl.col("icd10_code") == "P07.3")),
        says="P07.3 is a perinatal condition (ICD chapter P) and needs age at most 1; the patient is M aged 34",
    ),
    Case(
        AGE,
        lambda d: rename(d, 2, "L101850", "Yenidoğan monitörizasyonu"),
        label="newborn_name_on_an_adult",
        n=2,  # S2 bills the code L101850 on two lines
        at=row_at(2, TABLE_PROCEDURES, line(2, "L101850")),
        says="Yenidoğan monitörizasyonu is a newborn or infant procedure and needs age at most 1; the patient is M aged 81",
    ),
    Case(
        AGE,
        lambda d: rename(d, 2, "L101850", "Çocuk odyometresi (Komple)"),
        label="child_name_on_an_adult",
        n=2,
        at=row_at(2, TABLE_PROCEDURES, line(2, "L101850")),
        says="Çocuk odyometresi (Komple) is a paediatric procedure and needs age at most 17; the patient is M aged 81",
    ),
    Case(
        AGE,
        _adult_name_on_a_child,
        label="adult_name_on_a_child",
        at=row_at(1, TABLE_PROCEDURES, line(1, "P610131")),
        says="Erişkin tedavisel soğutma is an adult procedure and needs age at least 18; the patient is M aged 12",
    ),
    Case(
        AGE,
        lambda d: rename(d, 2, "L101850", "Yeni doğan fundoskopik inceleme"),  # a catalog name
        label="newborn_name_in_two_words_on_an_adult",
        n=2,
        at=row_at(2, TABLE_PROCEDURES, line(2, "L101850")),
        says="Yeni doğan fundoskopik inceleme is a newborn or infant procedure and needs age at most 1",
    ),
    Case(
        AGE,
        lambda d: rename(d, 2, "L101850", "Göz içi basıncı ölçümü, bebek için"),  # a catalog name
        label="infant_name_on_an_adult",
        n=2,
        at=row_at(2, TABLE_PROCEDURES, line(2, "L101850")),
        says="Göz içi basıncı ölçümü, bebek için is a newborn or infant procedure and needs age at most 1",
    ),
    Case(
        AGE,
        lambda d: rename(d, 2, "L101850", "Pelvipedal alçı (10 yaş altı)"),  # a catalog name
        label="under_ten_name_on_an_adult",
        n=2,
        at=row_at(2, TABLE_PROCEDURES, line(2, "L101850")),
        says="Pelvipedal alçı (10 yaş altı) is a procedure for a child under 10 and needs age at most 9",
    ),
    Case(
        AGE,
        lambda d: rename(
            d, 2, "L101850", "2 yaş altı doğumsal kalp hastalıklarında tanısal kalp kateterizasyonu"
        ),
        label="under_two_name_on_an_adult",
        n=2,
        at=row_at(2, TABLE_PROCEDURES, line(2, "L101850")),
        says="is a procedure for a child under 2 and needs age at most 1",
    ),
    # --- patient.age_arithmetic
    Case(
        ARITH,
        lambda d: edit_patient(d, 2, TANI_YASI=82),
        label="tani_yasi_one_year_off",
        at=CLAIM[2],
        says="TANI_YASI is 82; the claim year is 2026 and the birth year 1945, which makes the age 81",
    ),
    Case(
        ARITH,
        # patient 9: one bill (patient 3 has four since WP16: the profile is the patient's, so every bill would say it)
        lambda d: edit(d, TABLE_COPAY, pl.col("patient_id") == PATIENT[9], birth_year=1950),
        label="birth_year_one_year_off",
        at=CLAIM[9],
        says="TANI_YASI is 77; the claim year is 2026 and the birth year 1950, which makes the age 76",
    ),
    Case(
        ARITH,
        # patient 9: one bill, which the program does not extend (patient 5 has five since WP15, one finding each)
        lambda d: edit(d, TABLE_COPAY, pl.col("patient_id") == PATIENT[9], birth_year=None),
        label="no_birth_year",
        at=CLAIM[9],
        says="TANI_YASI is 77; the claim year is 2026 and the birth year missing, which makes the age unknown",
    ),
    Case(
        ARITH,
        lambda d: setattr(d, "anadata", d.anadata.filter(pl.col("HASTA_ID") != PATIENT[9])),
        label="no_anadata_row",
        at=CLAIM[9],
        says="TANI_YASI is missing; the claim year is 2026 and the birth year 1949, which makes the age 77",
    ),
    Case(
        ARITH,
        lambda d: drop(d, TABLE_COPAY, pl.col("patient_id") == PATIENT[9]),
        label="no_copay_profile_row",
        at=CLAIM[9],
        says="the birth year missing, which makes the age unknown",
    ),  # patient 9 has one bill: a patient with several (patient 4 has three) is found wrong in each of them
    # --- fit.pathway_membership. The extra lines are valid in themselves.
    Case(
        PATHWAY,
        lambda d: add_procedure(d, 7, "530350", "2026-02-19"),  # a nebuliser from the COPD ward
        label="extra_procedure",
        at=new_row_at(7, TABLE_PROCEDURES),
        says="procedure code 530350 is not in the expansion of pleuritic_chest_pain_er_pulmonary_embolism_ruled_out",
    ),
    Case(
        PATHWAY,
        _extra_material,
        label="extra_material",
        at=f"{CLAIM[3]} material_claim_lines[{material_line_id(CLAIM[3], 1)}]",
        says="material code AP1880 is not in the expansion of lumbar_stenosis_decompression_itemized",
    ),
    Case(
        PATHWAY,
        _extra_drug,
        label="extra_drug",
        at=f"{CLAIM[6]} drug_claim_lines[{drug_claim_line_id(CLAIM[6], 99)}]",
        says="drug code 8699606694649 is not in the expansion of aspiration_pneumonia_parkinson_ward",
    ),
    Case(
        PATHWAY,
        lambda d: add_diagnosis(d, 4, "E11.9"),
        label="extra_diagnosis",
        at=new_row_at(4, TABLE_DIAGNOSES),
        says="diagnosis code E11.9 is not in the expansion of pyelonephritis_dementia_delirium_ward",
    ),
    Case(
        PATHWAY,
        lambda d: edit(d, TABLE_CLAIM_HEADERS, of(2), scenario_tag="no_such_pathway"),
        label="scenario_tag_is_no_pathway",
        at=CLAIM[2],  # one finding about the claim, not one for each of its codes
        says="scenario_tag no_such_pathway is not a care pathway of data/synthetic/pathways",
    ),
    Case(
        PATHWAY,
        lambda d: edit(d, TABLE_CLAIM_HEADERS, of(4), scenario_tag=None),
        label="scenario_tag_is_missing",
        at=CLAIM[4],
        says="scenario_tag (missing) is not a care pathway of data/synthetic/pathways",
    ),
    # --- fit.operation_department
    Case(
        DEPT,
        lambda d: edit(d, TABLE_PROCEDURES, line(3, "615931"), procedure_specialty_code="1000"),
        label="operation_in_internal_medicine",
        at=row_at(3, TABLE_PROCEDURES, line(3, "615931")),
        says="operation 615931 (Dar spinal kanalda unilateral dekompresyon) has the specialty 1000, which is not a surgical EK-2A branch",
    ),
    Case(
        DEPT,
        lambda d: edit(d, TABLE_PROCEDURES, line(5, "P612320"), procedure_specialty_code="1000"),
        label="package_operation_in_internal_medicine",
        at=row_at(5, TABLE_PROCEDURES, line(5, "P612320")),
        says="operation P612320 (Büyük eklem parsiyel protezleri, primer) has the specialty 1000",
    ),
    Case(
        DEPT,
        lambda d: edit(d, TABLE_PROCEDURES, line(3, "615931"), procedure_specialty_code="9999"),
        label="operation_in_an_unknown_branch",
        at=row_at(3, TABLE_PROCEDURES, line(3, "615931")),
        says="has the specialty 9999, which is not a surgical EK-2A branch",
    ),
    Case(
        DEPT,
        lambda d: edit(d, TABLE_PROCEDURES, line(3, "615931"), procedure_specialty_code=None),
        label="operation_without_a_branch",
        at=row_at(3, TABLE_PROCEDURES, line(3, "615931")),
        says="has the specialty (none), which is not a surgical EK-2A branch",
    ),
    # --- fit.operation_setting. A visit claim has no stay: start equals end, no admission date.
    Case(
        SETTING,
        lambda d: edit(d, TABLE_CLAIM_HEADERS, of(3), claim_type="poliklinik"),
        also=(DATES,),  # the decompression claim still has its three-day stay
        label="band_b_operation_on_a_poliklinik_claim",
        at=row_at(3, TABLE_PROCEDURES, line(3, "615931")),
        says="major operation 615931 (Dar spinal kanalda unilateral dekompresyon, group B) on a claim of type poliklinik",
    ),
    Case(
        SETTING,
        lambda d: edit(d, TABLE_CLAIM_HEADERS, of(5), claim_type="acil"),
        also=(DATES,),  # the hemiarthroplasty claim still has its six-day stay
        label="band_b_package_on_an_acil_claim",
        at=row_at(5, TABLE_PROCEDURES, line(5, "P612320")),
        says="major operation P612320 (Büyük eklem parsiyel protezleri, primer, group B) on a claim of type acil",
    ),
    # --- fit.visit_code
    Case(
        VISIT,
        lambda d: edit(d, TABLE_CLAIM_HEADERS, of(7), claim_type="poliklinik"),
        label="acil_visit_on_a_poliklinik_claim",
        at=row_at(7, TABLE_PROCEDURES, line(7, "520020")),
        says="examination 520020 on a claim of type poliklinik; 520030 is the examination of that type",
    ),
    Case(
        VISIT,
        lambda d: set_code(d, 7, "520020", "520030"),
        also=(PATHWAY,),  # 520030 is not a line of the ER pathway
        label="poliklinik_visit_on_an_acil_claim",
        at=row_at(7, TABLE_PROCEDURES, line(7, "520020")),
        says="examination 520030 on a claim of type acil; 520020 or 520021 is the examination of that type",
    ),
    Case(
        VISIT,
        lambda d: set_code(d, 6, "520010", "520030"),
        also=(PATHWAY,),  # 520030 is not a line of the ward pathway
        label="poliklinik_visit_on_a_yatis_claim",
        at=row_at(6, TABLE_PROCEDURES, line(6, "520010")),
        says="examination 520030 on a claim of type yatis; 520010 is the examination of that type",
    ),
    # --- stay.bed_coverage (S2: 6 nights, 7 bed lines)
    Case(
        BED,
        lambda d: drop(d, TABLE_PROCEDURES, line(2, "510010", "2026-03-12")),
        label="missing_day",
        at=CLAIM[2],
        says="no bed line on 1 of 7 day(s): 2026-03-12",
    ),
    Case(
        BED,
        lambda d: clone_procedure(d, 2, line(2, "510010", "2026-03-10")),
        label="duplicate_day",
        at=CLAIM[2],
        says="more than one bed line on: 2026-03-10",
    ),
    Case(
        BED,
        _move_last_bed_after_discharge,
        also=(DATES,),  # a bed line after discharge also lies outside the claim window
        label="day_after_discharge",
        n=2,  # the line is outside the stay, and the discharge day has no bed
        at=CLAIM[2],
        says="bed line(s) outside admission..discharge: 2026-03-16",
    ),
    Case(
        BED,
        # no day is removed: a bed line after discharge is the only defect
        lambda d: add_procedure(d, 2, "510010", "2026-03-16"),
        also=(DATES,),  # the line also lies outside the claim window
        label="extra_bed_line_the_day_after_discharge",
        at=CLAIM[2],
        says="bed line(s) outside admission..discharge: 2026-03-16",
    ),
    Case(
        BED,
        lambda d: add_procedure(d, 2, "510010", "2026-03-08"),
        also=(DATES,),
        label="extra_bed_line_the_day_before_admission",
        at=CLAIM[2],
        says="bed line(s) outside admission..discharge: 2026-03-08",
    ),
    Case(
        BED,
        lambda d: edit(d, TABLE_PROCEDURES, line(2, "510010", "2026-03-11"), quantity=2),
        label="quantity_two",
        at=row_at(2, TABLE_PROCEDURES, line(2, "510010", "2026-03-11")),
        says="bed line 510010 has the quantity 2; a bed line is one day",
    ),
    Case(
        BED,
        lambda d: edit(
            d,
            TABLE_PROCEDURES,
            line(2, "510010", "2026-03-11"),
            quantity=0,
            billed_amount_try=0.0,
            expected_payable_try=0.0,
        ),
        label="quantity_zero",
        at=row_at(2, TABLE_PROCEDURES, line(2, "510010", "2026-03-11")),
        says="bed line 510010 has the quantity 0; a bed line is one day",
    ),
    Case(
        BED,
        lambda d: edit(d, TABLE_PROCEDURES, line(2, "510010", "2026-03-11"), quantity=None),
        also=(
            "money.line_arithmetic",
        ),  # no quantity: the billed amount is no unit price x quantity
        label="quantity_missing",
        at=row_at(2, TABLE_PROCEDURES, line(2, "510010", "2026-03-11")),
        says="bed line 510010 has the quantity (none); a bed line is one day",
    ),
    Case(
        BED,
        # the day bed is for a day case: S2 stays six nights
        lambda d: set_code(d, 2, "510010", "510120", "2026-03-11"),
        also=(PATHWAY,),  # 510120 is not a line of the ward pathway
        label="day_bed_on_a_longer_stay",
        at=row_at(2, TABLE_PROCEDURES, line(2, "510010", "2026-03-11")),
        says="day bed line 510120 on the stay 2026-03-09..2026-03-15; the day bed is for a day case",
    ),
    Case(
        BED,
        _bill_every_bed_day_as_a_day_bed,
        also=(PATHWAY,),
        label="whole_stay_billed_as_day_beds",
        n=7,  # a finding for each of the seven bed lines; every day still has its line
        also_n=7,  # and the pathway has no day bed on any of them
        at=row_at(2, TABLE_PROCEDURES, line(2, "510010", "2026-03-09")),
        says="day bed line 510120 on the stay 2026-03-09..2026-03-15; the day bed is for a day case",
    ),
    # --- stay.bed_coverage on a newborn stay (S12: 5 nights, 6 incubator lines 07-10 .. 07-15)
    Case(
        BED,
        lambda d: drop(d, TABLE_PROCEDURES, line(11, "510070", "2026-07-12")),
        label="newborn_missing_day",
        at=CLAIM[11],
        says="no bed line on 1 of 6 day(s): 2026-07-12",
    ),
    Case(
        BED,
        lambda d: clone_procedure(d, 11, line(11, "510070", "2026-07-11")),
        label="newborn_duplicate_day",
        at=CLAIM[11],
        says="more than one bed line on: 2026-07-11",
    ),
    Case(
        BED,
        # the ward bed and the incubator are alternatives for one day (EK-2B: the same text)
        lambda d: add_procedure(d, 11, "510010", "2026-07-12"),
        also=(PATHWAY,),  # 510010 is not a line of the newborn pathway
        label="newborn_ward_bed_beside_the_incubator",
        at=CLAIM[11],
        says="more than one bed line on: 2026-07-12",
    ),
    Case(
        BED,
        lambda d: add_procedure(d, 11, "510070", "2026-07-16"),
        also=(DATES,),  # a bed line after discharge also lies outside the claim window
        label="newborn_day_after_discharge",
        at=CLAIM[11],
        says="bed line(s) outside admission..discharge: 2026-07-16",
    ),
    Case(
        BED,
        lambda d: edit(d, TABLE_PROCEDURES, line(11, "510070", "2026-07-12"), quantity=2),
        label="newborn_quantity_two",
        at=row_at(11, TABLE_PROCEDURES, line(11, "510070", "2026-07-12")),
        says="bed line 510070 has the quantity 2; a bed line is one day",
    ),
    # --- stay.bed_coverage on a ward stay that begins on the day the ICU bill ends (S14: 06-07 .. 06-10, beds 06-08 .. 06-10)
    Case(
        BED,
        lambda d: add_row(
            d,
            TABLE_PROCEDURES,
            _ward("510010", "2026-06-08"),
            procedure_line_id=procedure_line_id(WARD, 99),
            procedure_date="2026-06-07",
        ),
        label="ward_bed_on_the_icu_exit_day",
        at=f"{WARD} procedure_claim_lines[{procedure_line_id(WARD, 99)}]",
        says="bed line 510010 on 2026-06-07, the day the patient leaves the ICU stay F-SENTETIK-HASTA-0010-001",
    ),
    Case(
        BED,
        lambda d: drop(d, TABLE_PROCEDURES, _ward("510010", "2026-06-09")),
        label="ward_after_icu_missing_day",
        at=WARD,
        says="no bed line on 1 of 3 day(s): 2026-06-09",
    ),
    Case(
        BED,
        lambda d: add_row(
            d,
            TABLE_PROCEDURES,
            _ward("510010", "2026-06-08"),
            procedure_line_id=procedure_line_id(WARD, 99),
            procedure_date="2026-06-10",
        ),
        label="ward_after_icu_duplicate_day",
        at=WARD,
        says="more than one bed line on: 2026-06-10",
    ),
    # --- stay.companion_coverage (S2: companions on the six nights 03-09 .. 03-14)
    Case(
        COMP,
        lambda d: edit(d, TABLE_PROCEDURES, line(2, "510121", "2026-03-11"), quantity=2),
        label="quantity_two",
        at=row_at(2, TABLE_PROCEDURES, line(2, "510121", "2026-03-11")),
        says="companion line has the quantity 2",
    ),
    Case(
        COMP,
        lambda d: edit(
            d,
            TABLE_PROCEDURES,
            line(2, "510121", "2026-03-11"),
            quantity=0,
            billed_amount_try=0.0,
            expected_payable_try=0.0,
        ),
        label="quantity_zero",
        at=row_at(2, TABLE_PROCEDURES, line(2, "510121", "2026-03-11")),
        says="companion line has the quantity 0",
    ),
    Case(
        COMP,
        lambda d: edit(d, TABLE_PROCEDURES, line(2, "510121", "2026-03-11"), quantity=None),
        also=(
            "money.line_arithmetic",
        ),  # no quantity: the billed amount is no unit price x quantity
        label="quantity_missing",
        at=row_at(2, TABLE_PROCEDURES, line(2, "510121", "2026-03-11")),
        says="companion line has the quantity (none)",
    ),
    Case(
        COMP,
        lambda d: clone_procedure(d, 2, line(2, "510121", "2026-03-10")),
        label="two_on_one_day",
        at=CLAIM[2],
        says="more than one companion line on: 2026-03-10",
    ),
    Case(
        COMP,
        lambda d: edit(
            d, TABLE_PROCEDURES, line(2, "510121", "2026-03-14"), procedure_date="2026-03-15"
        ),
        label="on_the_discharge_day",
        at=row_at(2, TABLE_PROCEDURES, line(2, "510121", "2026-03-14")),
        says="companion line dated 2026-03-15 is outside the nights 2026-03-09..2026-03-14 of the stay",
    ),
    Case(
        COMP,
        lambda d: edit(
            d, TABLE_PROCEDURES, line(2, "510121", "2026-03-09"), procedure_date="2026-03-08"
        ),
        also=(DATES,),  # a companion before admission also lies outside the claim window
        label="before_admission",
        at=row_at(2, TABLE_PROCEDURES, line(2, "510121", "2026-03-09")),
        says="companion line dated 2026-03-08 is outside the nights 2026-03-09..2026-03-14 of the stay",
    ),
    Case(
        COMP,
        lambda d: add_procedure(d, 7, "510121", "2026-02-19"),
        also=(PATHWAY,),  # the ER pathway has no companion line
        label="on_a_claim_without_a_stay",
        at=new_row_at(7, TABLE_PROCEDURES),
        says="companion line dated 2026-02-19 is outside the nights (no admission)..(no discharge) of the stay",
    ),
    # --- stay.dates_in_window
    Case(
        DATES,
        lambda d: edit(d, TABLE_CLAIM_HEADERS, of(2), claim_end_date="2026-03-16"),
        label="yatis_claim_ends_after_discharge",
        at=CLAIM[2],
        says="claim of type yatis starts on admission and ends on discharge: admission 2026-03-09, discharge 2026-03-15, start 2026-03-09, end 2026-03-16",
    ),
    Case(
        DATES,
        lambda d: edit(d, TABLE_CLAIM_HEADERS, of(7), admission_date="2026-02-19"),
        label="acil_claim_with_an_admission_date",
        at=CLAIM[7],
        says="claim of type acil is one day, with no admission and no discharge: admission 2026-02-19, discharge none",
    ),
    Case(
        DATES,
        lambda d: edit(d, TABLE_CLAIM_HEADERS, of(7), claim_end_date="2026-02-20"),
        label="acil_claim_over_two_days",
        at=CLAIM[7],
        says="claim of type acil is one day, with no admission and no discharge: admission none, discharge none, start 2026-02-19, end 2026-02-20",
    ),
    Case(
        DATES,
        lambda d: edit(d, TABLE_CLAIM_HEADERS, of(7), discharge_date="2026-02-19"),
        label="acil_claim_with_a_discharge_date_only",
        at=CLAIM[7],
        says="claim of type acil is one day, with no admission and no discharge: admission none, discharge 2026-02-19",
    ),
    Case(
        DATES,
        lambda d: edit(
            d, TABLE_PROCEDURES, line(4, "L101850", "2026-05-13"), procedure_date="2026-05-20"
        ),
        label="procedure_line_after_the_claim",
        at=row_at(4, TABLE_PROCEDURES, line(4, "L101850", "2026-05-13")),
        says="dated 2026-05-20 outside the claim window 2026-05-11..2026-05-16",
    ),
    Case(
        DATES,
        lambda d: edit(
            d, TABLE_PROCEDURES, line(4, "L101850", "2026-05-13"), procedure_date="13.05.2026"
        ),
        label="procedure_date_is_not_an_iso_date",
        at=row_at(4, TABLE_PROCEDURES, line(4, "L101850", "2026-05-13")),
        says="dated 13.05.2026 outside the claim window 2026-05-11..2026-05-16",
    ),
    Case(
        DATES,
        lambda d: edit(d, TABLE_MATERIALS, of(5), material_date="2026-09-20"),
        also=(OPLINK,),  # a material on another day than the operation it hangs on
        label="material_line_after_the_claim",
        n=3,  # S5 has three material lines
        also_n=3,
        at=f"{CLAIM[5]} material_claim_lines[{material_line_id(CLAIM[5], 1)}]",
        says="dated 2026-09-20 outside the claim window 2026-09-03..2026-09-08",
    ),
    Case(
        DATES,
        lambda d: edit(d, TABLE_DRUGS, of(2), drug_claim_date="2026-03-20"),
        label="drug_line_after_the_claim",
        n=5,  # S2 has five drug lines
        at=f"{CLAIM[2]} drug_claim_lines[{drug_claim_line_id(CLAIM[2], 1)}]",
        says="dated 2026-03-20 outside the claim window 2026-03-09..2026-03-15",
    ),
    Case(
        DATES,
        lambda d: edit(d, TABLE_DIAGNOSES, of(2), diagnosis_date="2026-03-20"),
        label="diagnosis_after_the_claim",
        n=3,  # S2 has three diagnoses
        at=f"{CLAIM[2]} claim_diagnoses[{diagnosis_id(CLAIM[2], 1)}]",
        says="dated 2026-03-20 outside the claim window 2026-03-09..2026-03-15",
    ),
    Case(
        DATES,
        _performed_line_a_day_late,
        also=(PERF,),  # the billed 530100 line is on the 19th
        label="performed_line_after_the_claim",
        at=row_at(7, TABLE_PERFORMED, performed(7, "530100")),
        says="dated 2026-02-20 outside the claim window 2026-02-19..2026-02-19",
    ),
    # --- bill.performed_billed
    Case(
        PERF,
        lambda d: drop(d, TABLE_PROCEDURES, line(7, "R101450")),  # the CT angiography of story S7
        label="billed_line_deleted",
        at=row_at(7, TABLE_PERFORMED, performed(7, "R101450")),
        says="performed R101450 (BT anjiografi, pulmoner arter) on 2026-02-19 has no billed procedure line",
    ),
    Case(
        PERF,
        lambda d: edit(
            d,
            TABLE_PERFORMED,
            performed(7, "530080"),
            procedure_code="530350",
        ),
        label="performed_code_is_not_billed",
        at=row_at(7, TABLE_PERFORMED, performed(7, "530080")),
        says="performed 530350 (Damar yolu açılması) on 2026-02-19 has no billed procedure line",
    ),
    # --- package.mode
    Case(
        PACKAGE,
        lambda d: edit(d, TABLE_CLAIM_HEADERS, of(1), package_candidate=False),
        label="candidate_false_on_a_package_claim",
        at=CLAIM[1],
        says="package_candidate is false but the claim has 1 package line(s)",
    ),
    Case(
        PACKAGE,
        lambda d: edit(d, TABLE_CLAIM_HEADERS, of(8), package_candidate=False),
        label="candidate_false_on_a_claim_with_two_packages",
        at=CLAIM[8],
        says="package_candidate is false but the claim has 2 package line(s)",
    ),
    Case(
        PACKAGE,
        lambda d: edit(d, TABLE_CLAIM_HEADERS, of(2), package_candidate=True),
        label="candidate_true_on_an_itemised_claim",
        at=CLAIM[2],
        says="package_candidate is true but the claim has 0 package line(s)",
    ),
    Case(
        PACKAGE,
        lambda d: edit(d, TABLE_CLAIM_HEADERS, of(2), package_candidate=None),
        label="candidate_missing",
        at=CLAIM[2],
        says="package_candidate is missing but the claim has 0 package line(s)",
    ),
    Case(
        PACKAGE,
        lambda d: add_procedure(d, 5, "510010", "2026-09-04"),
        also=(PATHWAY,),  # a ward bed is not a line of the hemiarthroplasty package
        label="bed_line_on_a_package_claim",
        at=new_row_at(5, TABLE_PROCEDURES),
        says="bed line 510010 on a package claim; the beds are inside the package",
    ),
    Case(
        PACKAGE,
        lambda d: add_procedure(d, 5, "550160", "2026-09-04", specialty="3100"),
        # anaesthesia.operation_pairing says the same ("a package has none"); 550160 is no line
        # of the hemiarthroplasty package
        also=(PAIRING, PATHWAY),
        label="anaesthesia_line_on_a_package_claim",
        at=new_row_at(5, TABLE_PROCEDURES),
        says="anaesthesia line 550160 on a package claim; the anaesthesia is inside the package",
    ),
    # --- anaesthesia.operation_pairing (S3: decompression 615931 and anaesthesia 550160 on 08-18)
    Case(
        PAIRING,
        lambda d: drop(d, TABLE_PROCEDURES, line(3, "550160")),
        label="anaesthesia_line_deleted",
        at=f"{CLAIM[3]} day[2026-08-18]",
        says="1 operation line(s) and 0 anaesthesia line(s); one anaesthesia line per operation day, none else",
    ),
    Case(
        PAIRING,
        lambda d: clone_procedure(d, 3, line(3, "550160"), procedure_date="2026-08-19"),
        label="anaesthesia_without_an_operation",
        at=f"{CLAIM[3]} day[2026-08-19]",
        says="0 operation line(s) and 1 anaesthesia line(s); one anaesthesia line per operation day, none else",
    ),
    Case(
        PAIRING,
        lambda d: clone_procedure(d, 3, line(3, "550160")),
        label="two_anaesthesia_lines_on_an_operation_day",
        at=f"{CLAIM[3]} day[2026-08-18]",
        says="1 operation line(s) and 2 anaesthesia line(s); one anaesthesia line per operation day, none else",
    ),
    Case(
        PAIRING,
        lambda d: add_procedure(d, 8, "550160", "2026-09-15", specialty="3100"),
        # package.mode says the same; 550160 is no line of the two-package pathway
        also=(PACKAGE, PATHWAY),
        label="anaesthesia_line_on_a_package_claim",
        at=new_row_at(8, TABLE_PROCEDURES),
        says="anaesthesia line 550160 on a package claim; a package has none",
    ),
    # --- anaesthesia.group
    Case(
        GROUP,
        lambda d: set_code(d, 3, "550160", "550170"),  # the code of group C, the puan is group B
        also=(PATHWAY,),
        label="single_code_of_another_group",
        at=row_at(3, TABLE_PROCEDURES, line(3, "550160")),
        says="anaesthesia 550170 on 2026-08-18: 1 operation(s) with puan 6471.03 are group B, which is 550160",
    ),
    Case(
        GROUP,
        lambda d: set_code(d, 3, "550160", "550230"),  # B, but the "several operations" code
        also=(PATHWAY,),
        label="several_operations_code_for_one_operation",
        at=row_at(3, TABLE_PROCEDURES, line(3, "550160")),
        says="anaesthesia 550230 on 2026-08-18: 1 operation(s) with puan 6471.03 are group B, which is 550160",
    ),
    Case(
        GROUP,
        _second_operation,
        also=(PATHWAY,),  # two operations need the "several operations" code; 603030 is no line
        label="single_code_for_two_operations",
        at=row_at(3, TABLE_PROCEDURES, line(3, "550160")),
        says="anaesthesia 550160 on 2026-08-18: 2 operation(s) with puan 8089.42 are group B, which is 550230",
    ),
    # --- material.operation_link (S5's three materials hang on its package P612320, dated 09-04)
    Case(
        OPLINK,
        lambda d: edit(
            d, TABLE_MATERIALS, mat(1), procedure_line_id=procedure_line_id(CLAIM[5], 99)
        ),
        label="no_such_procedure_line",
        at=mat_at(1),
        says=f"its procedure_line_id {procedure_line_id(CLAIM[5], 99)} is no procedure line of this claim",
    ),
    Case(
        OPLINK,
        lambda d: edit(d, TABLE_MATERIALS, mat(1), procedure_line_id=None),
        label="no_procedure_line_id",
        at=mat_at(1),
        says="material AP1880: it has no procedure_line_id",
    ),
    Case(
        OPLINK,
        # a real line, but of S3's claim: a material hangs on a line of its own claim
        lambda d: edit(d, TABLE_MATERIALS, mat(1), procedure_line_id=line_id_of(d, 3, "615931")),
        label="line_of_another_claim",
        at=mat_at(1),
        says="is no procedure line of this claim",
    ),
    Case(
        OPLINK,
        lambda d: _material_on(d, "550160"),
        also=(PATHWAY,),  # S5's material is no line of S3's pathway
        label="hangs_on_the_anaesthesia_line",
        at=f"{CLAIM[3]} material_claim_lines[{material_line_id(CLAIM[3], 1)}]",
        says="the line 550160 (",
    ),
    Case(
        OPLINK,
        lambda d: edit(d, TABLE_MATERIALS, mat(1), material_date="2026-09-05"),
        label="dated_the_day_after_the_operation",
        at=mat_at(1),
        says="it is dated 2026-09-05 but the line P612320 it hangs on is dated 2026-09-04",
    ),
    # --- material.operation_link of slice G7b: an EK-3/C-2 device hangs on the examination of its visit
    Case(
        OPLINK,
        lambda d: edit(d, TABLE_MATERIALS, walker(), specialty_category="EK-3F-1"),
        also=("price.material_in_force",),  # OP1106 is no code of the EK-3/F-1 list either
        label="a_walker_read_as_an_ek3f1_material_hangs_on_an_examination",
        at=walker_at(),
        says="material OP1106: the line 520030 (Normal poliklinik muayenesi, category muayene) it hangs on is not an operation",
    ),
    Case(
        OPLINK,
        lambda d: edit(d, TABLE_MATERIALS, mat(2), specialty_category="EK-3C-2"),
        also=("price.material_in_force",),  # AP2000 is no code of the EK-3/C-2 list
        label="an_ek3c2_device_on_a_package",
        at=mat_at(2),
        says="the EK-3/C-2 device hangs on is not an examination",
    ),
    # --- material.stray_flag
    Case(
        "material.stray_flag",
        lambda d: edit(d, TABLE_MATERIALS, mat(1), diagnosis_bundled_no_separate_bill=True),
        label="defect_flag_true",
        at=mat_at(1),
        says="diagnosis_bundled_no_separate_bill is true",
    ),
    Case(
        "material.stray_flag",
        lambda d: edit(d, TABLE_MATERIALS, mat(3), titubb_registered=False),
        label="registration_flag_false",
        at=mat_at(3),
        says="titubb_registered is false",
    ),
    Case(
        "material.stray_flag",
        lambda d: edit(d, TABLE_MATERIALS, mat(1), foreign_facility=True, uts_registered=False),
        label="two_flags_in_one_line",
        at=mat_at(1),
        says="uts_registered is false, foreign_facility is true",
    ),
    # --- price.procedure_in_force (a lab test, the ER CT angiography, the EK-2C package)
    Case(
        "price.procedure_in_force",
        lambda d: reprice(d, TABLE_PROCEDURES, line(4, "L101850", "2026-05-13"), 17.46),
        label="changed_unit_price",
        at=f"{CLAIM[4]} procedure_claim_lines[",
        says="procedure L101850 dated 2026-05-13: unit price 17.46 but the price in force is 16.46",
    ),
    Case(
        "price.procedure_in_force",
        # 1034.74 is the price of the list that ended on 2025-12-31; the 2026 list bills 1138.22
        lambda d: reprice(d, TABLE_PROCEDURES, line(7, "R101450"), 1034.74),
        label="price_of_the_list_before_the_2026_update",
        at=f"{CLAIM[7]} procedure_claim_lines[",
        says="procedure R101450 dated 2026-02-19: unit price 1034.74 but the price in force is 1138.22",
    ),
    Case(
        "price.procedure_in_force",
        lambda d: reprice(d, TABLE_PROCEDURES, line(5, "P612320"), 18000.0),
        label="package_price",
        at=f"{CLAIM[5]} procedure_claim_lines[",
        says="procedure P612320 dated 2026-09-04: unit price 18000.00 but the price in force is 18390.79",
    ),
    Case(
        "price.procedure_in_force",
        lambda d: edit(
            d, TABLE_PROCEDURES, line(4, "L101850", "2026-05-13"), procedure_code="L999999"
        ),
        also=(PATHWAY,),  # L999999 is no line of the pathway
        label="code_without_a_price",
        at=f"{CLAIM[4]} procedure_claim_lines[",
        says="procedure L999999 dated 2026-05-13 has no price in force on that day (unit price 16.46)",
    ),
    # --- price.material_in_force
    Case(
        "price.material_in_force",
        lambda d: reprice(d, TABLE_MATERIALS, mat(2), 6566.27),
        label="changed_unit_price",
        at=mat_at(2),
        says="material AP2000 dated 2026-09-04 has the unit price 6566.27 but the list price is 6465.27",
    ),
    Case(
        "price.material_in_force",
        lambda d: edit(d, TABLE_MATERIALS, mat(3), material_code="AP9999"),
        also=(PATHWAY,),  # AP9999 is no material of the hemiarthroplasty pathway
        label="code_not_in_the_list",
        at=mat_at(3),
        says="material AP9999 dated 2026-09-04 is not in the EK-3/F-1 list",
    ),
    Case(
        "price.material_in_force",
        lambda d: edit(d, TABLE_MATERIALS, mat(1), material_date="2025-12-12"),
        # a material dated before the claim begins, and not on the day of its operation
        also=(DATES, OPLINK),
        label="dated_the_day_before_the_list_starts",
        at=mat_at(1),
        says="is before the list is in force (from 2025-12-13)",
    ),
    # --- price.material_in_force of slice G7b: the walker of S45 is priced on the EK-3/C-2 list
    Case(
        "price.material_in_force",
        lambda d: reprice(d, TABLE_MATERIALS, walker(), 322.56),
        label="a_walker_at_the_price_of_the_ek3c2_list_s_other_walker",
        at=walker_at(),
        says="material OP1106 dated 2026-06-29 has the unit price 322.56 but the list price is 252.00",
    ),
    Case(
        "price.material_in_force",
        lambda d: edit(d, TABLE_MATERIALS, walker(), material_date="2026-01-23"),
        also=(DATES, OPLINK),  # dated before the visit, and not on the day of its examination
        label="a_walker_dated_the_day_before_the_ek3c2_list_starts",
        at=walker_at(),
        says="is before the list is in force (from 2026-01-24)",
    ),
    Case(
        "price.material_in_force",
        lambda d: edit(d, TABLE_MATERIALS, walker(), specialty_category="EK-3C-5"),
        also=(OPLINK,),  # only an EK-3/C-2 device may hang on an examination: any other line must hang on an operation
        label="a_material_of_an_ek3_list_the_cohort_does_not_read",
        at=walker_at(),
        says="material OP1106 dated 2026-06-29 is not in the EK-3/C-5 list",
    ),
    # --- price.drug_in_force (S6's first drug is Neofleks, barcode 8697637690128)
    Case(
        "price.drug_in_force",
        lambda d: edit(d, TABLE_DRUGS, drug(6, 1), barkod="1000000000000"),
        also=(PATHWAY,),  # the barcode is no drug of the ward pathway
        label="barcode_not_in_ek4a",
        at=f"{CLAIM[6]} drug_claim_lines[{drug_claim_line_id(CLAIM[6], 1)}]",
        says="(barcode 1000000000000) is not in the EK-4A history",
    ),
    Case(
        "price.drug_in_force",
        lambda d: edit(d, TABLE_DRUGS, drug(6, 1), drug_claim_date="2019-01-01"),
        also=(DATES,),  # a drug line dated years before the claim
        label="dated_before_the_row_starts",
        at=f"{CLAIM[6]} drug_claim_lines[{drug_claim_line_id(CLAIM[6], 1)}]",
        says="(barcode 8697637690128) dated 2019-01-01 has no EK-4A row in force on that day",
    ),
    # --- money.line_arithmetic
    Case(
        "money.line_arithmetic",
        lambda d: edit(
            d,
            TABLE_PROCEDURES,
            line(4, "L101850", "2026-05-13"),
            billed_amount_try=4.94,  # 16.46 x 0.3
            expected_payable_try=4.94,
        ),
        label="ratio_of_0_3",
        at=f"{CLAIM[4]} procedure_claim_lines[",
        says="billed 4.94 is not the unit price 16.46 x quantity 1 x 1, 0.5 or 0.25 (16.46, 8.23 or 4.12)",
    ),
    Case(
        "money.line_arithmetic",
        # three units billed as one (a quantity of 2 would read as a half-price second operation)
        lambda d: edit(d, TABLE_PROCEDURES, line(4, "L101850", "2026-05-13"), quantity=3),
        label="quantity_not_billed",
        at=f"{CLAIM[4]} procedure_claim_lines[",
        says="billed 16.46 is not the unit price 16.46 x quantity 3 x 1, 0.5 or 0.25 (49.38, 24.69 or 12.35)",
    ),
    Case(
        "money.line_arithmetic",
        lambda d: edit(d, TABLE_MATERIALS, mat(3), quantity=3),
        label="material_quantity_not_billed",
        at=mat_at(3),
        says="billed 985.70 is not the unit price 492.85 x quantity 3",
    ),
    Case(
        "money.line_arithmetic",
        # the share of red cells inside a package (C000694) on an itemized bill: S24's two units at 36 %
        lambda d: edit(
            d,
            TABLE_PROCEDURES,
            (pl.col("claim_id") == claim_id(PATIENT[15], 2)) & (pl.col("procedure_code") == "705371"),
            billed_amount_try=1606.55,
            expected_payable_try=1606.55,
        ),
        label="blood_share_on_an_itemized_bill",
        at=f"{claim_id(PATIENT[15], 2)} procedure_claim_lines[",
        says="billed 1606.55 is not the unit price 4462.64 x quantity 1 x 1, 0.5 or 0.25",
        n=2,
    ),
    Case(
        "money.line_arithmetic",
        lambda d: edit(d, TABLE_DRUGS, drug(6, 1), billed_amount_try=5.0, expected_payable_try=5.0),
        label="drug_billed_at_a_zero_price",
        at=f"{CLAIM[6]} drug_claim_lines[{drug_claim_line_id(CLAIM[6], 1)}]",
        says="billed 5.00 is not the unit price 0.00",
    ),
    # --- money.payable_equals_billed
    Case(
        "money.payable_equals_billed",
        lambda d: edit(
            d, TABLE_PROCEDURES, line(4, "L101850", "2026-05-13"), expected_payable_try=13.17
        ),
        label="copay_taken_off_a_procedure",
        at=f"{CLAIM[4]} procedure_claim_lines[",
        says="expected_payable_try is 13.17 but billed_amount_try is 16.46",
    ),
    Case(
        "money.payable_equals_billed",
        lambda d: edit(d, TABLE_MATERIALS, mat(1), expected_payable_try=0.0),
        label="material_not_payable",
        at=mat_at(1),
        says="expected_payable_try is 0.00 but billed_amount_try is 5391.89",
    ),
    Case(
        "money.payable_equals_billed",
        lambda d: edit(d, TABLE_DRUGS, drug(6, 1), expected_payable_try=None),
        label="drug_payable_missing",
        at=f"{CLAIM[6]} drug_claim_lines[{drug_claim_line_id(CLAIM[6], 1)}]",
        says="expected_payable_try is (none) but billed_amount_try is 0.00",
    ),
    # the line with a patient share (S32's examination): it pays billed x (1 - rate), and flag and rate go together
    Case(
        "money.payable_equals_billed",
        lambda d: edit(d, TABLE_PROCEDURES, _s2_control_exam(), expected_payable_try=85.73),
        label="copay_line_paid_in_full",
        at=f"{S2_CONTROL} procedure_claim_lines[",
        says="expected_payable_try is 85.73 but billed_amount_try 85.73 less the copay share 0.20 is 68.58",
    ),
    Case(
        "money.payable_equals_billed",
        lambda d: edit(d, TABLE_PROCEDURES, _s2_control_exam(), expected_payable_try=68.57),
        label="copay_line_a_cent_short",
        at=f"{S2_CONTROL} procedure_claim_lines[",
        says="expected_payable_try is 68.57 but billed_amount_try 85.73 less the copay share 0.20 is 68.58",
    ),
    Case(
        "money.payable_equals_billed",
        lambda d: edit(d, TABLE_PROCEDURES, _s2_control_exam(), copay_rate=None),
        label="copay_flag_without_a_rate",
        at=f"{S2_CONTROL} procedure_claim_lines[",
        says="copay_rate_applicable is true but copay_rate is (none)",
    ),
    Case(
        "money.payable_equals_billed",
        lambda d: edit(d, TABLE_PROCEDURES, _s2_control_exam(), copay_rate=1.0, expected_payable_try=0.0),
        label="copay_rate_of_the_whole_line",
        at=f"{S2_CONTROL} procedure_claim_lines[",
        says="copay_rate_applicable is true but copay_rate is 1.00",
    ),
    Case(
        "money.payable_equals_billed",
        lambda d: edit(d, TABLE_PROCEDURES, line(4, "L101850", "2026-05-13"), copay_rate=0.2),
        label="copay_rate_without_the_flag",
        at=f"{CLAIM[4]} procedure_claim_lines[",
        says="copay_rate is 0.20 but copay_rate_applicable is false",
    ),
    Case(
        "money.payable_equals_billed",
        lambda d: edit(d, TABLE_PROCEDURES, _s2_control_exam(), copay_rate_applicable=False),
        label="copay_flag_dropped_from_a_shared_line",
        at=f"{S2_CONTROL} procedure_claim_lines[",
        says="expected_payable_try is 68.58 but billed_amount_try is 85.73; a line pays what it bills",
        n=2,  # the payable of an unflagged line, and a rate without its flag
    ),
    # --- money.totals (S3's clean twin bills 5607.55)
    Case(
        "money.totals",
        lambda d: edit(
            d,
            TABLE_CLAIM_HEADERS,
            of(3),
            expected_total_billed_try=pl.col("expected_total_billed_try") + 1.0,
        ),
        label="billed_total_one_lira_off",
        at=CLAIM[3],
        says="expected_total_billed_try is 5608.55 but the billed amounts of the claim's lines add up to 5607.55",
    ),
    Case(
        "money.totals",
        lambda d: edit(
            d,
            TABLE_CLAIM_HEADERS,
            of(3),
            expected_total_payable_try=pl.col("expected_total_payable_try") - 0.01,
        ),
        label="payable_total_one_cent_off",
        at=CLAIM[3],
        says="expected_total_payable_try is 5607.54 but the payable amounts of the claim's lines add up to 5607.55",
    ),
    Case(
        "money.totals",
        lambda d: edit(d, TABLE_CLAIM_HEADERS, of(3), expected_total_billed_try=None),
        label="billed_total_missing",
        at=CLAIM[3],
        says="expected_total_billed_try is (none) but",
    ),
    # --- labels.answer_rows (from the faulty bills and their registry)
    Case(
        ANSWER_ROWS,
        lambda d: edit(d, TABLE_ANSWERS, of(2), expected_status="kismi_red"),
        label="status_changed",
        on_faulty=True,
        at=f"{CLAIM[2]} expected_rule_outputs[",
        says="expected_status is kismi_red but the fault record gives eksik_faturalama",
    ),
    Case(
        ANSWER_ROWS,
        lambda d: drop(d, TABLE_ANSWERS, of(4)),
        label="row_deleted",
        on_faulty=True,
        at=f"{CLAIM[4]} expected_rule_outputs[",
        says="the fault record F_S4_COMPANION_NOT_BILLED has no answer row",
    ),
    Case(
        ANSWER_ROWS,
        lambda d: add_row(
            d, TABLE_ANSWERS, of(1), expected_output_id=f"BEK-{CLAIM[1]}-F_S1_ANOTHER_FAULT"
        ),
        label="extra_row",
        on_faulty=True,
        at=f"{CLAIM[1]} expected_rule_outputs[BEK-{CLAIM[1]}-F_S1_ANOTHER_FAULT]",
        says="no fault record of the claim produces this answer row",
    ),
    Case(
        ANSWER_ROWS,
        _forget_a_record,
        label="record_deleted_row_kept",
        on_faulty=True,
        at=f"{CLAIM[6]} expected_rule_outputs[",
        says="the claim has no fault record, so nothing explains this answer row",
    ),
    Case(
        ANSWER_ROWS,
        _record_names_a_claim_without_a_header,
        label="record_names_a_claim_without_a_header",
        on_faulty=True,
        at="F-SENTETIK-HASTA-0099-001 registry faults[F_S3_ANAESTHESIA_LINE_MISSING]",
        says="the fault record names a claim that has no header",
    ),
    Case(
        ANSWER_ROWS,
        _swap_two_answer_rows,
        label="rows_out_of_order",
        on_faulty=True,
        at=f"{CLAIM[3]} expected_rule_outputs[",
        says="the row is out of order",
    ),
    Case(
        ANSWER_ROWS,
        lambda d: add_row(d, TABLE_ANSWERS, of(2)),
        label="row_twice",
        on_faulty=True,
        at=f"{CLAIM[2]} expected_rule_outputs[",
        says="2 rows share this answer id",
    ),
    # --- labels.amounts (the records are edited together with their answer rows, as a generator
    # that made the mistake would; a record that no longer validates cannot be rebuilt into one)
    Case(
        AMOUNTS,
        # revenue_uplift S2: the amount follows the wrong total, so only the total is wrong
        lambda d: edit_fault(d, 2, billed_faulty_try="2596.14", amount_try="667.04"),
        label="wrong_faulty_total",
        n=2,  # the wrong total differs from the header total and from the sum of the lines
        on_faulty=True,
        at=f"{CLAIM[2]} registry faults[F_S2_BED_DAYS_UNDERBILLED]",
        says="billed_faulty_try is 2596.14 but expected_total_billed_try of the claim is 2596.13",
    ),
    Case(
        AMOUNTS,
        lambda d: edit_fault(d, 5, line_id=material_line_id(CLAIM[5], 9)),
        label="dangling_line_id",
        on_faulty=True,
        at=f"{CLAIM[5]} registry faults[F_S5_IMPLANT_UTS_INCOMPLETE]",
        says=f"line_id {material_line_id(CLAIM[5], 9)} is no line of material_claim_lines of this claim",
    ),
    Case(
        AMOUNTS,
        # a drug line that exists, but in S4's claim
        lambda d: edit_fault(d, 6, line_id=drug_claim_line_id(CLAIM[4], 1)),
        label="line_of_another_claim",
        on_faulty=True,
        at=f"{CLAIM[6]} registry faults[F_S6_DRUG_INDICATION_NOT_CODED]",
        says="is no line of drug_claim_lines of this claim",
    ),
    Case(
        AMOUNTS,
        lambda d: edit_fault(d, 3, relabel=False, amount_try="928.09"),
        # the record no longer validates (revenue_uplift = clean - faulty), so no record explains S3's row
        also=(ANSWER_ROWS,),
        label="revenue_uplift_amount",
        also_n=2,  # the answer table: the entry that no longer validates, and the row it leaves unexplained
        on_faulty=True,
        at=f"{CLAIM[3]} registry faults[F_S3_ANAESTHESIA_LINE_MISSING]",
        says="revenue_uplift amount_try is 928.09 but must be 928.08 (billed_clean_try - billed_faulty_try)",
    ),
    Case(
        AMOUNTS,
        lambda d: edit_fault(d, 8, amount_try="5377.21"),
        label="deduction_risk_amount_off_the_growth",
        on_faulty=True,
        at=f"{CLAIM[8]} registry faults[F_S8_SECOND_PACKAGE_FULL_RATE]",
        says="deduction_risk amount_try is 5377.21 but must be 5377.20",
    ),
    Case(
        AMOUNTS,
        # the bill did not grow, so the risk is the target line itself (AP2000, 6465.27)
        lambda d: edit_fault(d, 5, amount_try="6465.28"),
        label="deduction_risk_amount_off_the_line",
        on_faulty=True,
        at=f"{CLAIM[5]} registry faults[F_S5_IMPLANT_UTS_INCOMPLETE]",
        says="deduction_risk amount_try is 6465.28 but must be 6465.27",
    ),
    Case(
        AMOUNTS,
        lambda d: edit_fault(d, 6, amount_try="1.00"),
        label="compliance_error_with_an_amount",
        on_faulty=True,
        at=f"{CLAIM[6]} registry faults[F_S6_DRUG_INDICATION_NOT_CODED]",
        says="compliance_error amount_try is 1.00 but must be 0.00 (zero)",
    ),
    Case(
        AMOUNTS,
        lambda d: edit_fault(d, 1, relabel=False, line_id=procedure_line_id(CLAIM[1], 1)),
        also=(ANSWER_ROWS,),  # a fatura record with a line id does not validate
        label="fatura_with_a_line_id",
        also_n=2,  # the answer table: the entry that no longer validates, and the row it leaves unexplained
        on_faulty=True,
        at=f"{CLAIM[1]} registry faults[F_S1_PACKAGE_BILLED_ITEMIZED]",
        says=f"line_id {procedure_line_id(CLAIM[1], 1)} must be empty for line_type fatura",
    ),
    Case(
        AMOUNTS,
        lambda d: edit_fault(d, 5, relabel=False, line_id=""),
        also=(ANSWER_ROWS,),  # a malzeme record without a line id does not validate
        label="line_type_without_a_line_id",
        also_n=2,  # the answer table: the entry that no longer validates, and the row it leaves unexplained
        on_faulty=True,
        at=f"{CLAIM[5]} registry faults[F_S5_IMPLANT_UTS_INCOMPLETE]",
        says="line_type malzeme needs the line_id of its target line",
    ),
    Case(
        AMOUNTS,
        lambda d: edit_fault(d, 4, relabel=False, effect_kind="refund"),
        also=(ANSWER_ROWS,),  # an effect kind outside the three does not validate
        label="unknown_effect_kind",
        also_n=2,  # the answer table: the entry that no longer validates, and the row it leaves unexplained
        on_faulty=True,
        at=f"{CLAIM[4]} registry faults[F_S4_COMPANION_NOT_BILLED]",
        says="effect_kind refund is none of revenue_uplift, deduction_risk, compliance_error",
    ),
]


# --- 1. the registry -------------------------------------------------------------------------------


def test_every_check_id_has_a_function_a_short_meaning_and_a_mutation_case() -> None:
    assert set(CHECK_FUNCTIONS) == set(CHECKS)
    assert {case.check for case in CASES} == set(CHECKS)
    for check, meaning in CHECKS.items():
        assert 0 < len(meaning) <= 120, f"{check}: the meaning has {len(meaning)} characters"
    assert E1_CHECKS | E2_CHECKS <= set(CHECKS)
    assert not E1_CHECKS & E2_CHECKS
    assert len(E2_CHECKS) == 10
    assert all(re.fullmatch(r"[a-z]+\.[a-z_]+", check) for check in CHECKS)


def test_the_registry_ids_are_the_labels_ids_and_every_case_names_its_finding() -> None:
    assert REGISTRY_CHECKS == {"labels.answer_rows", "labels.amounts"}
    assert REGISTRY_CHECKS <= E2_CHECKS
    for case in CASES:
        assert case.at and case.says, f"{case.name} must say where and what it expects"
        assert case.n >= 1, case.name
        assert (case.also_n is None) or (case.also and case.also_n >= len(case.also)), case.name
        if case.check in E2_CHECKS:
            assert (case.check in REGISTRY_CHECKS) == case.on_faulty, case.name
        else:
            assert not case.on_faulty, case.name


def test_cases_name_registered_ids_only() -> None:
    for case in CASES:
        assert case.check in CHECKS
        assert set(case.also) <= set(CHECKS), case.name
        assert case.check not in case.also, case.name
    assert len({case.name for case in CASES}) == len(CASES), "two cases share a name"


def test_a_problem_carries_a_registered_id_and_its_claim() -> None:
    with pytest.raises(KeyError, match="unregistered check id"):
        Problem("not.a.registered.check", "somewhere", "bad")
    problem = Problem("package.mode", f"{CLAIM[1]} procedure_claim_lines[x]", "m")
    assert problem.claim_id == CLAIM[1]
    assert Problem("package.mode", CLAIM[2], "m").claim_id == CLAIM[2]
    assert str(problem).startswith("package.mode at ")


def test_run_all_is_check_plausibility() -> None:
    assert run_all is check_plausibility


# --- 2. the clean twins and the committed faulty bills -----------------------------------------------


def trips_by_claim(found: list[Problem]) -> dict[str, set[str]]:
    trips: dict[str, set[str]] = {}
    for problem in found:
        trips.setdefault(problem.claim_id, set()).add(problem.check)
    return trips


@pytest.fixture(scope="module")
def clean_problems(twins, anadata, context) -> list[Problem]:
    return check_plausibility(twins, {TABLE_ANADATA: anadata}, context=context)


@pytest.fixture(scope="module")
def faulty_problems(built, anadata, context) -> list[Problem]:
    """The faulty bills, with the registry: the `labels.*` ids run too."""
    return check_plausibility(
        built.tables, {TABLE_ANADATA: anadata}, context=context, registry=built.registry
    )


@pytest.mark.parametrize("story", STORIES, ids=[f"S{n}" for n in STORIES])
def test_a_clean_twin_raises_no_problem(story, clean_problems, twins) -> None:
    mine = [str(p) for p in clean_problems if p.claim_id == CLAIM[story]]
    assert mine == []
    assert twins[TABLE_CLAIM_HEADERS].filter(of(story)).height == 1


def test_the_clean_twins_are_all_there_and_all_clean(clean_problems, twins) -> None:
    assert twins[TABLE_CLAIM_HEADERS].height == cohort.claim_count()
    assert [str(p) for p in clean_problems] == []


@pytest.mark.parametrize("story", sorted(EXPECTED_FAULT_TRIPS))
def test_a_faulty_bill_trips_the_pinned_ids(story, built, faulty_problems) -> None:
    encounters = built.registry["encounters"]
    story_of = {e["claim_id"]: e["story"] for e in encounters if not e["is_clean"]}
    assert sorted(story_of.values()) == sorted(EXPECTED_FAULT_TRIPS)  # one pinned entry per faulty bill
    claim = next(claim for claim, name in story_of.items() if name == story)
    tripped = {p.check for p in faulty_problems if p.claim_id == claim}
    assert tripped == EXPECTED_FAULT_TRIPS[story], [str(p) for p in faulty_problems]
    # a bill without a fault is a clean bill: the checks find nothing on it
    clean_claims = {e["claim_id"] for e in encounters if e["is_clean"]}
    assert [str(p) for p in faulty_problems if p.claim_id in clean_claims] == []


def test_the_committed_files_give_the_result_of_the_tables_in_memory(
    built, anadata, context
) -> None:
    on_disk = {name: pl.read_parquet(_CLAIMS_DIR / name) for name in TABLE_FILES}
    clean_on_disk = {TABLE_ANADATA: pl.read_parquet(_CLEAN_DIR / TABLE_ANADATA)}
    registry = json.loads(_REGISTRY_FILE.read_text(encoding="utf-8"))
    from_files = check_plausibility(on_disk, clean_on_disk, context=context, registry=registry)
    from_memory = check_plausibility(
        built.tables, {TABLE_ANADATA: anadata}, context=context, registry=built.registry
    )
    assert from_files == from_memory
    assert {p.check for p in from_files} == set().union(*EXPECTED_FAULT_TRIPS.values())


def test_the_committed_bills_and_their_committed_registry_trip_no_labels_id(context) -> None:
    """One answer row and one fault record per bill agree with the committed bills (labels.*)."""
    on_disk = {name: pl.read_parquet(_CLAIMS_DIR / name) for name in TABLE_FILES}
    clean_on_disk = {TABLE_ANADATA: pl.read_parquet(_CLEAN_DIR / TABLE_ANADATA)}
    registry = json.loads(_REGISTRY_FILE.read_text(encoding="utf-8"))
    assert len(registry["faults"]) == len(cohort.load_registry()["faults"])
    assert on_disk[TABLE_ANSWERS].height == len(registry["faults"])
    found = check_plausibility(
        on_disk, clean_on_disk, context=context, registry=registry, only=sorted(REGISTRY_CHECKS)
    )
    assert [str(p) for p in found] == []


def test_a_registry_without_fault_records_leaves_the_committed_answer_rows_unexplained(
    built, anadata, context
) -> None:
    found = check_plausibility(
        built.tables, {TABLE_ANADATA: anadata}, context=context, registry={"faults": []}
    )
    labels = [p for p in found if p.check in REGISTRY_CHECKS]
    assert {p.check for p in labels} == {ANSWER_ROWS}
    assert sorted(p.claim_id for p in labels) == sorted(
        built.tables[TABLE_ANSWERS]["claim_id"].to_list()
    )  # one row per answer row: a bill without a fault has none
    assert all("the claim has no fault record" in p.message for p in labels)


def test_the_labels_run_only_with_a_registry(built, anadata, context) -> None:
    """Without the registry the labels ids are skipped, even when `only` asks for them."""
    tables = {TABLE_ANADATA: anadata}
    assert (
        check_plausibility(built.tables, tables, context=context, only=sorted(REGISTRY_CHECKS))
        == []
    )
    empty = check_plausibility(
        built.tables, tables, context=context, only=sorted(REGISTRY_CHECKS), registry={"faults": []}
    )
    assert {p.check for p in empty} == {ANSWER_ROWS}
    # a clean twin set has no answer rows, so a registry without records is consistent with it
    twin_tables = build_tables(
        built.clean_claims,
        answer_rows=(),
        copay_profiles=built.copay_profiles,
        medula_events=(),
    )
    assert (
        check_plausibility(
            twin_tables,
            tables,
            context=context,
            only=sorted(REGISTRY_CHECKS),
            registry={"faults": []},
        )
        == []
    )


def test_billed_clean_try_is_the_total_of_the_clean_twin(built, twins) -> None:
    """The module cannot see the clean twins; this test proves the records' clean totals."""
    totals = {
        claim: f"{total:.2f}"
        for claim, total in zip(
            twins[TABLE_CLAIM_HEADERS]["claim_id"],
            twins[TABLE_CLAIM_HEADERS]["expected_total_billed_try"],
            strict=True,
        )
    }
    faults = built.registry["faults"]
    assert len(faults) == len(cohort.load_registry()["faults"])
    # a record per faulty bill; a bill without a fault has a clean twin and no record
    assert {fault["claim_id"]: fault["billed_clean_try"] for fault in faults} == {
        fault["claim_id"]: totals[fault["claim_id"]] for fault in faults
    }


# --- 3. the mutation cases -------------------------------------------------------------------------


def faulty_data(built, anadata) -> Data:
    """The committed faulty bills with a copy of their registry: the base of the `labels.*` cases."""
    return Data(dict(built.tables), anadata, copy.deepcopy(built.registry))


def fresh(case: Case, built, twins, anadata) -> Data:
    """A new working copy for a case: the clean twins, or (`on_faulty`) the faulty bills + registry."""
    return faulty_data(built, anadata) if case.on_faulty else Data(dict(twins), anadata)


def test_the_base_of_a_defect_case_has_the_findings_of_the_module_fixtures(
    built, twins, anadata, context, clean_problems, faulty_problems
) -> None:
    """A case's base (`fresh`) finds what `clean_problems` or `faulty_problems` found, so the cases read those."""
    for on_faulty, problems in ((False, clean_problems), (True, faulty_problems)):
        case = next(case for case in CASES if case.on_faulty is on_faulty)
        assert fresh(case, built, twins, anadata).problems(context) == problems, on_faulty


@pytest.mark.parametrize("case", CASES, ids=lambda c: c.name)
def test_a_defect_trips_its_own_check_and_what_it_must(
    case: Case, built, twins, anadata, context, clean_problems, faulty_problems
) -> None:
    # the findings of the base, `fresh(case, built, twins, anadata).problems(context)`, computed once per module
    before = list(faulty_problems if case.on_faulty else clean_problems)
    if case.on_faulty:
        # the faulty bills trip the pinned ids already; the case may add only its own finding
        assert {p.check for p in before} == set().union(*EXPECTED_FAULT_TRIPS.values())
    else:
        assert before == [], "the base (the nine clean twins) must be clean"
    broken = fresh(case, built, twins, anadata)
    at = case.at(broken) if callable(case.at) else case.at  # read before the defect is seeded
    case.mutate(broken)
    found = [p for p in broken.problems(context) if p not in before]
    assert only_ids(found) == {case.check, *case.also}, [str(p) for p in found]
    # a mutation touches one claim, and so does what it trips
    assert len({problem.claim_id for problem in found}) == 1, [str(p) for p in found]
    # every finding says where and what, whatever value the defect left empty
    assert all(isinstance(p.where, str) and p.where.startswith("F-") for p in found)
    assert all(isinstance(p.message, str) and p.message for p in found), [str(p) for p in found]
    # the number of findings: a check that says too much or too little is wrong
    mine = [p for p in found if p.check == case.check]
    others = len(found) - len(mine)
    assert len(mine) == case.n, [str(p) for p in mine]
    assert others == (len(case.also) if case.also_n is None else case.also_n), [
        str(p) for p in found
    ]
    # the finding of the target id is the right one: the right place, the right reason. An `at`
    # that is only a claim id is a finding about the claim itself; a longer one is a fragment
    assert any(
        (p.where == at if " " not in at else at in p.where) and case.says in p.message for p in mine
    ), [str(p) for p in mine]
    # the findings come in the order of the registry, then by where and message
    order = {check: index for index, check in enumerate(CHECKS)}
    keys = [(order[p.check], p.where, p.message) for p in found]
    assert keys == sorted(keys), [str(p) for p in found]
    # and a finding about a line names a line that is there
    assert all(
        names_a_real_row(p, broken.tables) for p in found if p.check not in REGISTRY_CHECKS
    ), [str(p) for p in found]


# --- 3b. the boundary pairs ------------------------------------------------------------------------
#
# One table of inputs ported from the independent review of slice E1: for each rule the input just
# inside (valid), the input just outside (it trips) and the variants that must not trip. A pair
# names the E1 ids its input trips (exactly those, among the E1 ids, or among `only` when it is set,
# because its neighbours do not matter there) and the number of findings they report. The base is
# the eight clean twins.


@dataclasses.dataclass(frozen=True)
class Pair:
    """One boundary input: the data change, the ids it trips (none: a valid input) and how many findings."""

    name: str
    mutate: Callable[[Data], None]
    trips: tuple[str, ...] = ()
    n: int = 0
    only: str | None = None
    at: str | Callable[[Data], str] = ""  # a fragment of the `where` of a finding (see `_names`)
    says: str = ""  # a fragment of the `message` of that finding

    def __post_init__(self) -> None:
        assert bool(self.trips) == bool(self.n), f"{self.name}: trips and n go together"
        assert bool(self.at) <= bool(self.says), f"{self.name}: `at` needs `says`"


def _aged(story, age, *, icd=None, name=None, code="L101850", sex=None):
    """The story's patient is `age` (and of `sex`), with a diagnosis or a renamed line."""

    def mutate(d: Data) -> None:
        set_age(d, story, age, sex=sex)
        if icd:
            add_diagnosis(d, story, icd)
        if name:
            rename(d, story, code, name)

    return mutate


def _setting(story, claim_type, new_code, day="2026-08-18"):
    """The story's operation becomes `new_code` on a claim of `claim_type`."""

    def mutate(d: Data) -> None:
        edit(d, TABLE_CLAIM_HEADERS, of(story), claim_type=claim_type)
        replace_op(d, story, "615931", new_code, day)

    return mutate


def _shifted_setting(shift, claim_type, new_code, day):
    def mutate(d: Data) -> None:
        shift_claim(d, 3, shift)
        _setting(3, claim_type, new_code, day)(d)

    return mutate


def _drop_anadata_row(d: Data, story: int) -> None:
    d.anadata = d.anadata.filter(pl.col("HASTA_ID") != PATIENT[story])


def _every_table_empty(d: Data) -> None:
    for name in list(d.tables):
        d.tables[name] = d.tables[name].clear()
    d.anadata = d.anadata.clear()


def _several_defects_on_four_claims(d: Data) -> None:
    drop(d, TABLE_PROCEDURES, line(2, "510010", "2026-03-11"))
    drop(d, TABLE_PROCEDURES, line(2, "510010", "2026-03-13"))
    drop(d, TABLE_PROCEDURES, line(3, "550160"))
    drop(d, TABLE_PROCEDURES, line(7, "R101450"))
    edit(d, TABLE_CLAIM_HEADERS, of(1), package_candidate=False)


def _tag_of(story: int, other: int) -> Callable[[Data], None]:
    """The story's scenario tag becomes the tag of another story."""

    def mutate(d: Data) -> None:
        tag = d.tables[TABLE_CLAIM_HEADERS].filter(of(other))["scenario_tag"][0]
        edit(d, TABLE_CLAIM_HEADERS, of(story), scenario_tag=tag)

    return mutate


def _one_day_stay(d: Data) -> None:
    # S2 shrinks to the one date 03-09: a stay of no night, with its one bed line
    edit(d, TABLE_CLAIM_HEADERS, of(2), discharge_date="2026-03-09", claim_end_date="2026-03-09")
    drop(d, TABLE_PROCEDURES, of(2) & (pl.col("procedure_date") > "2026-03-09"))


def _one_night_stay(d: Data) -> None:
    # S2 shrinks to the two dates 03-09 and 03-10: a stay of one night
    edit(d, TABLE_CLAIM_HEADERS, of(2), discharge_date="2026-03-10", claim_end_date="2026-03-10")
    drop(d, TABLE_PROCEDURES, of(2) & (pl.col("procedure_date") > "2026-03-10"))


def _day_case_with_a_day_bed(d: Data) -> None:
    _one_day_stay(d)
    set_code(d, 2, "510010", "510120")


PAIRS: list[Pair] = [
    # --- patient.icd_valid
    Pair(
        "icd: a code created on the diagnosis day is valid (F99, created 2026-07-22)",
        lambda d: add_diagnosis(d, 1, "F99", "2026-07-22"),
        only=ICD,
    ),
    Pair(
        "icd: a code created the day after the diagnosis (F99 on 2026-07-21)",
        lambda d: add_diagnosis(d, 1, "F99", "2026-07-21"),
        (ICD,),
        1,
        only=ICD,
        at=new_row_at(1, TABLE_DIAGNOSES),
        says="diagnosis F99 dated 2026-07-21: the code was created on 2026-07-22, after the diagnosis date",
    ),
    Pair(
        "icd: a range heading is no leaf (A00-A09)",
        lambda d: edit(d, TABLE_DIAGNOSES, I10_OF_2, icd10_code="A00-A09"),
        (ICD, PATHWAY),
        2,
    ),
    Pair(
        "icd: a lower-case code is not the code (i10)",
        lambda d: edit(d, TABLE_DIAGNOSES, I10_OF_2, icd10_code="i10"),
        (ICD, PATHWAY),
        2,
        at=row_at(2, TABLE_DIAGNOSES, I10_OF_2),
        says="diagnosis i10 dated 2026-03-09: the code is not in icd10_tr",
    ),
    Pair(
        "icd: a code with a trailing space",
        lambda d: edit(d, TABLE_DIAGNOSES, I10_OF_2, icd10_code="I10 "),
        (ICD, PATHWAY),
        2,
    ),
    Pair(
        "icd: a missing code",
        lambda d: edit(d, TABLE_DIAGNOSES, I10_OF_2, icd10_code=None),
        (ICD, PATHWAY),
        2,
        at=row_at(2, TABLE_DIAGNOSES, I10_OF_2),
        says="diagnosis (none) dated 2026-03-09: the code is not in icd10_tr",
    ),
    Pair(
        "icd: a code passive on the diagnosis day (U06.9, passive since 2025-07-02)",
        lambda d: add_diagnosis(d, 2, "U06.9"),
        (ICD,),
        1,
        only=ICD,
    ),
    # --- patient.sex_gate: a code of the icd10_tr column, and a code of the ICD-10 blocks only
    Pair(
        "sex: a woman with cervix carcinoma in situ D06.9 is valid",
        lambda d: add_diagnosis(d, 3, "D06.9"),
        only=SEX,
    ),
    Pair(
        "sex: a man with cervix carcinoma in situ D06.9 (a code of the icd10_tr column)",
        lambda d: add_diagnosis(d, 1, "D06.9"),
        (SEX, PATHWAY),
        2,
    ),
    Pair(
        "sex: a woman with acute prostatitis N41.0",
        lambda d: add_diagnosis(d, 3, "N41.0"),
        (SEX, PATHWAY),
        2,
    ),
    Pair(
        "sex: a man with acute prostatitis N41.0 is valid",
        lambda d: add_diagnosis(d, 1, "N41.0"),
        only=SEX,
    ),
    Pair(
        "sex: a man with endometriosis N80.0",
        lambda d: add_diagnosis(d, 1, "N80.0"),
        (SEX, PATHWAY),
        2,
    ),
    Pair(
        "sex: a woman with endometriosis N80.0 is valid",
        lambda d: add_diagnosis(d, 3, "N80.0"),
        only=SEX,
    ),
    Pair(
        "sex: a man with polycystic ovary syndrome E28.2",
        lambda d: add_diagnosis(d, 2, "E28.2"),
        (SEX, PATHWAY),
        2,
    ),
    Pair(
        "sex: a woman with polycystic ovary syndrome E28.2 is valid",
        lambda d: add_diagnosis(d, 8, "E28.2"),
        only=SEX,
    ),
    Pair(
        "sex: a woman with hydrocele N43.3",
        lambda d: add_diagnosis(d, 8, "N43.3"),
        (SEX, PATHWAY),
        2,
    ),
    Pair(
        "sex: a man with hydrocele N43.3 is valid",
        lambda d: add_diagnosis(d, 6, "N43.3"),
        only=SEX,
    ),
    Pair(
        "sex: a woman with scrotal varices I86.1",
        lambda d: add_diagnosis(d, 3, "I86.1"),
        (SEX, PATHWAY),
        2,
    ),
    Pair(
        "sex: a man with scrotal varices I86.1 is valid",
        lambda d: add_diagnosis(d, 1, "I86.1"),
        only=SEX,
    ),
    Pair(
        "sex: a woman with other varicose veins I86.0 is no sex gate (only I86.1 is)",
        lambda d: add_diagnosis(d, 3, "I86.0"),
        only=SEX,
    ),
    Pair(
        "sex: a woman with an undescended testis Q53.1",
        lambda d: add_diagnosis(d, 4, "Q53.1"),
        (SEX, PATHWAY),
        2,
    ),
    Pair(
        "sex: a man with a congenital malformation of the uterus Q51.0",
        lambda d: add_diagnosis(d, 1, "Q51.0"),
        (SEX, PATHWAY),
        2,
    ),
    Pair(
        "sex: a code of a male block that icd10_tr does not know (N41.77) on a woman",
        lambda d: add_diagnosis(d, 3, "N41.77"),
        (ICD, SEX, PATHWAY),
        3,
        at=new_row_at(3, TABLE_DIAGNOSES),
        says="diagnosis N41.77 is limited to sex M but the patient is F",
    ),
    Pair(
        "sex: a man with a delivery outcome Z37.0",
        lambda d: add_diagnosis(d, 1, "Z37.0"),
        (SEX, PATHWAY),
        2,
    ),
    Pair(
        "sex: a man with a postpartum examination Z39.0",
        lambda d: add_diagnosis(d, 1, "Z39.0"),
        (SEX, PATHWAY),
        2,
    ),
    Pair(
        "sex: a man with a liveborn infant code Z38.0 is no sex gate",
        lambda d: add_diagnosis(d, 1, "Z38.0"),
        only=SEX,
    ),
    Pair(
        "sex: a man with a urinary infection N39.0 is no sex gate (N39 lies between the blocks)",
        lambda d: add_diagnosis(d, 1, "N39.0"),
        only=SEX,
    ),
    Pair(
        "sex: a man with a breast disease N63 is no sex gate (N60-N64 lie between the blocks)",
        lambda d: add_diagnosis(d, 1, "N63"),
        only=SEX,
    ),
    Pair(
        "sex: a patient of unknown sex with N41.0 trips (the gate cannot be met)",
        lambda d: (edit_patient(d, 1, CINSIYET="?"), add_diagnosis(d, 1, "N41.0")),
        (SEX, PATHWAY),
        2,
        at=new_row_at(1, TABLE_DIAGNOSES),
        says="diagnosis N41.0 is limited to sex M but the patient is of unknown sex",
    ),
    Pair(
        "sex: a duplicated anadata row of the patient does not duplicate a finding",
        lambda d: (
            setattr(
                d,
                "anadata",
                pl.concat([d.anadata, d.anadata.filter(pl.col("HASTA_ID") == PATIENT[3])]),
            ),
            rename(d, 3, "L104780", "Prostat iğne biyopsisi"),
        ),
        (SEX,),
        1,
    ),
    # patient 9, a woman with one bill: without her anadata row every bill of hers has no age (patient 3 has four since WP16)
    Pair(
        "sex: a patient missing from anadata with a male-gated C61",
        lambda d: (_drop_anadata_row(d, 9), add_diagnosis(d, 9, "C61")),
        (SEX, ARITH, PATHWAY),
        3,
    ),
    Pair(
        "sex: a patient missing from anadata with a male-only name",
        lambda d: (_drop_anadata_row(d, 9), rename(d, 9, "L107020", "Prostat iğne biyopsisi")),
        (SEX, ARITH),
        2,
    ),
    # --- patient.sex_gate: the names of the catalog that the word lists must catch
    Pair(
        "sex: a woman with the catalog name 'Fimozis açılması'",
        lambda d: rename(d, 7, "L102890", "Fimozis açılması"),
        (SEX,),
        1,
    ),
    Pair(
        "sex: a woman with the catalog name 'Testiküler fiksasyon, iki taraf'",
        lambda d: rename(d, 7, "L102890", "Testiküler fiksasyon, iki taraf"),
        (SEX,),
        1,
    ),
    Pair(
        "sex: a woman with the catalog name 'Prostat spesifik antijen (PSA), total'",
        lambda d: rename(d, 7, "L102890", "Prostat spesifik antijen (PSA), total"),
        (SEX,),
        1,
    ),
    Pair(
        "sex: a man with the catalog name 'Histerosalpingografi (HSG)'",
        lambda d: rename(d, 2, "L101850", "Histerosalpingografi (HSG)"),
        (SEX,),
        2,
    ),
    Pair(
        "sex: a man with the catalog name 'Obstetrik US'",
        lambda d: rename(d, 6, "L101850", "Obstetrik US"),
        (SEX,),
        2,
    ),
    Pair(
        "sex: a man with the catalog name 'Epidural anestezi ile vajinal doğum'",
        lambda d: rename(d, 6, "801720", "Epidural anestezi ile vajinal doğum"),
        (SEX,),
        2,
    ),
    Pair(
        "sex: a man with the catalog name 'Transvajinal US'",
        lambda d: rename(d, 6, "801720", "Transvajinal US"),
        (SEX,),
        2,
    ),
    Pair(
        "sex: a man with the catalog name 'Ultrason eşliğinde çoğul gebeliklerde fetal redüksiyon'",
        lambda d: rename(d, 2, "L101850", "Ultrason eşliğinde çoğul gebeliklerde fetal redüksiyon"),
        (SEX,),
        2,
    ),
    Pair(
        "sex: a man with the name 'Hepatik recover testi' is valid ('over' is a whole word only)",
        lambda d: rename(d, 1, "P610131", "Hepatik recover testi"),
        only=SEX,
    ),
    Pair(
        "sex: a woman with a name of the catalog that has a sex word only in an exception",
        lambda d: rename(d, 3, "L104780", "Sperm yıkama"),
        only=SEX,
    ),
    Pair(
        "sex: a code CINSIYET 'M' (neither E nor K) without any sex content is valid",
        lambda d: edit_patient(d, 1, CINSIYET="M"),
        only=SEX,
    ),
    # --- patient.age_gate: both sides of every limit
    *[
        Pair(
            f"age: O80.9 on a woman aged {age}" + ("" if ok else " (outside 10..55)"),
            _aged(8, age, icd="O80.9"),
            () if ok else (AGE,),
            0 if ok else 1,
            only=AGE,
        )
        for age, ok in ((9, False), (10, True), (55, True), (56, False))
    ],
    *[
        Pair(
            f"age: perinatal P07.3 on a patient aged {age}" + ("" if ok else " (over 1)"),
            _aged(1, age, icd="P07.3"),
            () if ok else (AGE,),
            0 if ok else 1,
            only=AGE,
        )
        for age, ok in ((0, True), (1, True), (2, False))
    ],
    *[
        Pair(
            f"age: liveborn Z38.0 on a patient aged {age}" + ("" if ok else " (over 1)"),
            _aged(1, age, icd="Z38.0"),
            () if ok else (AGE,),
            0 if ok else 1,
            only=AGE,
        )
        for age, ok in ((1, True), (2, False))
    ],
    *[
        Pair(
            f"age: 'Çocuk odyometresi (Komple)' on a patient aged {age}"
            + ("" if ok else " (over 17)"),
            _aged(2, age, name="Çocuk odyometresi (Komple)"),
            () if ok else (AGE,),
            0 if ok else 2,  # S2 bills the code L101850 on two lines
            only=AGE,
        )
        for age, ok in ((17, True), (18, False))
    ],
    *[
        Pair(
            f"age: 'Erişkin tedavisel soğutma' on a patient aged {age}"
            + ("" if ok else " (under 18)"),
            _aged(2, age, name="Erişkin tedavisel soğutma"),
            () if ok else (AGE,),
            0 if ok else 2,
            only=AGE,
        )
        for age, ok in ((17, False), (18, True))
    ],
    *[
        Pair(
            f"age: 'Yenidoğan monitörizasyonu' on a patient aged {age}"
            + ("" if ok else " (over 1)"),
            _aged(2, age, name="Yenidoğan monitörizasyonu"),
            () if ok else (AGE,),
            0 if ok else 2,
            only=AGE,
        )
        for age, ok in ((0, True), (1, True), (2, False))
    ],
    *[
        Pair(
            f"age: 'Pelvipedal alçı (10 yaş altı)' on a patient aged {age}"
            + ("" if ok else " (over 9)"),
            _aged(2, age, name="Pelvipedal alçı (10 yaş altı)"),
            () if ok else (AGE,),
            0 if ok else 2,
            only=AGE,
        )
        for age, ok in ((9, True), (10, False))
    ],
    *[
        Pair(
            f"age: '2 yaş altı doğumsal kalp hastalıklarında ...' on a patient aged {age}"
            + ("" if ok else " (over 1)"),
            _aged(
                2, age, name="2 yaş altı doğumsal kalp hastalıklarında tanısal kalp kateterizasyonu"
            ),
            () if ok else (AGE,),
            0 if ok else 2,
            only=AGE,
        )
        for age, ok in ((1, True), (2, False))
    ],
    Pair(
        "age: a name '12 yaş altı' is not the name '2 yaş altı' (a whole word)",
        _aged(2, 5, name="Pelvipedal alçı (12 yaş altı)"),
        only=AGE,
    ),
    Pair(
        "age: 'Göz muayenesi, bebek için, genel anestezi altında' on a patient aged 2",
        _aged(2, 2, name="Göz muayenesi, bebek için, genel anestezi altında"),
        (AGE,),
        2,
        only=AGE,
    ),
    Pair(
        "age: 'Göz muayenesi, bebek için, genel anestezi altında' on a patient aged 1 is valid",
        _aged(2, 1, name="Göz muayenesi, bebek için, genel anestezi altında"),
        only=AGE,
    ),
    Pair(
        "age: 'Çocuklarda görme muayeneleri' on an 81-year-old (the word inside a word)",
        lambda d: rename(d, 2, "L101850", "Çocuklarda görme muayeneleri"),
        (AGE,),
        2,
    ),
    Pair(
        "age: 'Yeni doğan fundoskopik inceleme' on an 81-year-old (two words)",
        lambda d: rename(d, 2, "L101850", "Yeni doğan fundoskopik inceleme"),
        (AGE,),
        2,
    ),
    Pair(
        "age: P702682, the ÇÖZGEM child and youth centre (Çocuk ve Genç), on a patient aged 18 is valid",
        lambda d: (
            set_age(d, 2, 18),
            rename(
                d,
                2,
                "L101850",
                "Çok Disiplinli Çocuk ve Genç Ruh Sağlığı Merkezleri (ÇÖZGEM) hizmetleri",
            ),
        ),
        only=AGE,
    ),
    Pair(
        "age: the newborn add-on 'Yeni doğan/geriatrik (75 yaş üstü ...)' on an 81-year-old is valid",
        lambda d: rename(
            d, 2, "L101850", "Yeni doğan/geriatrik (75 yaş üstü ve ASA 3-4) anestezi puanı B grubu"
        ),
        only=AGE,
    ),
    Pair(
        "age: a patient of 12 with 'Yenidoğan/Çocuk/Erişkin tedavisel soğutma' is valid (the longer exception first)",
        lambda d: (
            set_age(d, 2, 12),
            rename(d, 2, "L101850", "Yenidoğan/Çocuk/Erişkin tedavisel soğutma"),
        ),
        only=AGE,
    ),
    Pair(
        "age: O80.9 on a patient of unknown sex (CINSIYET '?') aged 30",
        _aged(8, 30, icd="O80.9", sex="?"),
        (AGE,),
        1,
        only=AGE,
        at=new_row_at(8, TABLE_DIAGNOSES),
        says="needs sex F, age 10..55; the patient is of unknown sex aged 30",
    ),
    Pair(
        "age: O80.9 on a man whose age is missing (the sex alone trips the gate)",
        lambda d: (add_diagnosis(d, 1, "O80.9"), edit_patient(d, 1, TANI_YASI=None)),
        (AGE,),
        1,
        only=AGE,
        at=new_row_at(1, TABLE_DIAGNOSES),
        says="needs sex F, age 10..55; the patient is M aged unknown",
    ),
    Pair(
        "age: O80.9 on a patient missing from anadata (no sex, no age)",
        # patient 9 has one bill (patient 8 has four since WP17): one claim without its anadata row
        lambda d: (_drop_anadata_row(d, 9), add_diagnosis(d, 9, "O80.9")),
        (AGE, ARITH, PATHWAY),
        3,
        at=new_row_at(9, TABLE_DIAGNOSES),
        says="needs sex F, age 10..55; the patient is of unknown sex aged unknown",
    ),
    Pair(
        "age: a code 'XO80.9' with an O inside it is no pregnancy code",
        lambda d: add_diagnosis(d, 1, "XO80.9"),
        only=AGE,
    ),
    Pair(
        "age: a perinatal code on a patient missing from anadata cannot be judged",
        lambda d: (add_diagnosis(d, 9, "P07.3"), _drop_anadata_row(d, 9)),
        (ARITH, PATHWAY),
        2,
    ),
    Pair(
        "age: an adult name on a patient missing from anadata cannot be judged",
        lambda d: (_drop_anadata_row(d, 2), rename(d, 2, "L101850", "Erişkin tedavisel soğutma")),
        only=AGE,
    ),
    # --- patient.age_arithmetic: the year of claim_start_date, not of claim_end_date
    Pair(
        "arith: a claim crossing New Year, the age by the START year is valid",
        lambda d: (shift_claim(d, 2, -70), set_age(d, 2, 80, year=2025)),
        only=ARITH,
    ),
    Pair(
        "arith: a claim crossing New Year, the age by the END year",
        lambda d: (shift_claim(d, 2, -70), set_age(d, 2, 81, year=2026)),
        (ARITH,),
        1,
        only=ARITH,
        at=CLAIM[2],
        says="TANI_YASI is 81; the claim year is 2025 and the birth year 1945, which makes the age 80",
    ),
    Pair(
        "arith: a missing TANI_YASI",
        lambda d: edit_patient(d, 4, TANI_YASI=None),
        (ARITH,),
        1,
        only=ARITH,
    ),
    Pair(
        "arith: a missing copay profile row",
        lambda d: drop(d, TABLE_COPAY, pl.col("patient_id") == PATIENT[9]),
        (ARITH,),
        1,
        only=ARITH,
    ),
    # --- fit.pathway_membership
    Pair(
        "path: a missing scenario tag is one finding about the claim",
        lambda d: edit(d, TABLE_CLAIM_HEADERS, of(4), scenario_tag=None),
        (PATHWAY,),
        1,
        only=PATHWAY,
        at=CLAIM[4],
        says="scenario_tag (missing) is not a care pathway",
    ),
    Pair(
        "path: a scenario tag that is no pathway is one finding about the claim",
        lambda d: edit(d, TABLE_CLAIM_HEADERS, of(2), scenario_tag="no_such_pathway"),
        (PATHWAY,),
        1,
        only=PATHWAY,
    ),
    Pair(
        "path: the scenario tag of another story (every code that is not in its pathway)",
        _tag_of(6, 2),
        (PATHWAY,),
        11,
        only=PATHWAY,
    ),
    Pair(
        "path: a material code equal to a procedure code of the pathway (the family counts)",
        lambda d: edit(d, TABLE_MATERIALS, mat(1), material_code="P612320"),
        (PATHWAY,),
        1,
        only=PATHWAY,
        at=f"{CLAIM[5]} material_claim_lines[{material_line_id(CLAIM[5], 1)}]",
        says="material code P612320 is not in the expansion of",
    ),
    Pair(
        "path: a procedure line of a claim that has no header is named by the dates check",
        lambda d: add_row(
            d,
            TABLE_PROCEDURES,
            of(2),
            claim_id="F-SENTETIK-HASTA-0099-001",
            procedure_line_id="ISL-F-SENTETIK-HASTA-0099-001-001",
        ),
        (DATES,),
        1,
        at="F-SENTETIK-HASTA-0099-001 procedure_claim_lines[ISL-F-SENTETIK-HASTA-0099-001-001]",
        says="dated 2026-03-09 outside the claim window (no header)..(no header)",
    ),
    # --- fit.operation_department
    Pair(
        "dept: a package operation in anaesthesiology (P609235 by 3100)",
        lambda d: edit(d, TABLE_PROCEDURES, line(8, "P609235"), procedure_specialty_code="3100"),
        (DEPT,),
        1,
        only=DEPT,
    ),
    Pair(
        "dept: an appendectomy package by urology is valid (2700 is a surgical branch)",
        lambda d: edit(d, TABLE_PROCEDURES, line(1, "P610131"), procedure_specialty_code="2700"),
        only=DEPT,
    ),
    Pair(
        "dept: the hemodialysis package P704230 in internal medicine is no operation",
        lambda d: add_procedure(d, 8, "P704230", "2026-09-15", specialty="1000"),
        only=DEPT,
    ),
    Pair(
        "dept: the palliative care package P560000 in internal medicine is no operation",
        lambda d: add_procedure(d, 8, "P560000", "2026-09-15", specialty="1000"),
        only=DEPT,
    ),
    Pair(
        "dept: an operation branch with a trailing space ('2400 ')",
        lambda d: edit(d, TABLE_PROCEDURES, line(3, "615931"), procedure_specialty_code="2400 "),
        (DEPT,),
        1,
        only=DEPT,
    ),
    Pair(
        "dept: an operation in internal medicine on a poliklinik claim trips the setting too",
        lambda d: (
            edit(d, TABLE_CLAIM_HEADERS, of(3), claim_type="poliklinik"),
            edit(d, TABLE_PROCEDURES, line(3, "615931"), procedure_specialty_code="1000"),
        ),
        (DEPT, SETTING, DATES),
        3,
    ),
    # --- fit.operation_setting: every major group, the minor ones, and the day a price row or the bands change
    Pair(
        "setting: an A1 operation (608540) on an acil claim",
        _setting(3, "acil", "608540"),
        (SETTING,),
        1,
        only=SETTING,
    ),
    Pair(
        "setting: an A2 operation (612490) on an acil claim",
        _setting(3, "acil", "612490"),
        (SETTING,),
        1,
        only=SETTING,
    ),
    Pair(
        "setting: an A3 operation (606290) on a poliklinik claim",
        _setting(3, "poliklinik", "606290"),
        (SETTING,),
        1,
        only=SETTING,
    ),
    Pair(
        "setting: a B operation (609810) on an acil claim",
        _setting(3, "acil", "609810"),
        (SETTING,),
        1,
        only=SETTING,
    ),
    Pair(
        "setting: a C operation (618480) on an acil claim is minor",
        _setting(3, "acil", "618480"),
        only=SETTING,
    ),
    Pair(
        "setting: a D operation (608390) on a poliklinik claim is minor",
        _setting(3, "poliklinik", "608390"),
        only=SETTING,
    ),
    Pair(
        "setting: a B operation on a yatis claim is valid",
        lambda d: replace_op(d, 3, "615931", "609810", "2026-08-18"),
        only=SETTING,
    ),
    Pair(
        "setting: 610131 on a poliklinik claim on 2026-04-15 is group B before the bands change",
        _shifted_setting(-125, "poliklinik", "610131", "2026-04-15"),
        (SETTING,),
        1,
        only=SETTING,
    ),
    Pair(
        "setting: 610131 on a poliklinik claim on 2026-04-16 is group C after the bands change",
        _shifted_setting(-124, "poliklinik", "610131", "2026-04-16"),
        only=SETTING,
    ),
    Pair(
        "setting: 615931 on the first day of the last price row (2026-07-07)",
        lambda d: (
            shift_claim(d, 3, -42),
            edit(d, TABLE_CLAIM_HEADERS, of(3), claim_type="poliklinik"),
        ),
        (SETTING,),
        1,
        only=SETTING,
    ),
    Pair(
        "setting: 615931 on the last day of the middle price row (2026-07-06)",
        lambda d: (
            shift_claim(d, 3, -43),
            edit(d, TABLE_CLAIM_HEADERS, of(3), claim_type="poliklinik"),
        ),
        (SETTING,),
        1,
        only=SETTING,
    ),
    Pair(
        "setting: 615931 on the first day of the middle price row (2026-01-31)",
        lambda d: (
            shift_claim(d, 3, -199),
            edit(d, TABLE_CLAIM_HEADERS, of(3), claim_type="poliklinik"),
        ),
        (SETTING,),
        1,
        only=SETTING,
    ),
    *[
        Pair(
            f"setting: the EK-2C package P612320 on an acil claim dated {day} ({why})",
            lambda d, day=day: (
                shift_claim(d, 5, (date.fromisoformat(day) - date(2026, 9, 4)).days),
                edit(d, TABLE_CLAIM_HEADERS, of(5), claim_type="acil"),
            ),
            (SETTING,),
            1,
            only=SETTING,
        )
        for day, why in (
            ("2026-01-30", "the last day of the row before"),
            ("2026-01-31", "the first day of the middle row"),
            ("2026-07-06", "the last day of the middle row"),
            ("2026-07-07", "the first day of the last row"),
        )
    ],
    # --- fit.visit_code
    Pair(
        "visit: the acil visit 520020 on a yatis claim",
        lambda d: set_code(d, 6, "520010", "520020"),
        (VISIT, PATHWAY),
        2,
    ),
    Pair(
        "visit: the consultation 520010 on an acil claim",
        lambda d: set_code(d, 7, "520020", "520010"),
        (VISIT, PATHWAY),
        2,
    ),
    Pair(
        # an examination code of the acil type since S49 (C000370, C000438): only S7's pathway does not hold it
        "visit: the green-area visit 520021 on an acil claim is an acil examination",
        lambda d: set_code(d, 7, "520020", "520021"),
        (PATHWAY,),
        1,
    ),
    Pair(
        "visit: a health board report 520050 as an examination on a yatis claim",
        lambda d: set_code(d, 6, "520010", "520050"),
        (VISIT, PATHWAY),
        2,
    ),
    Pair(
        "visit: a second acil visit on the same day is valid",
        lambda d: add_procedure(d, 7, "520020", "2026-02-19", specialty="4400"),
        only=VISIT,
    ),
    # --- stay.bed_coverage
    Pair(
        "bed: an extra bed line the day after discharge",
        lambda d: add_procedure(d, 2, "510010", "2026-03-16"),
        (BED, DATES),
        2,
    ),
    Pair(
        "bed: an extra bed line the day before admission",
        lambda d: add_procedure(d, 2, "510010", "2026-03-08"),
        (BED, DATES),
        2,
    ),
    Pair(
        "bed: two bed lines outside the stay are listed in date order",
        lambda d: (
            add_procedure(d, 2, "510010", "2026-03-16"),
            add_procedure(d, 2, "510010", "2026-03-08"),
        ),
        (BED, DATES),
        3,
        at=CLAIM[2],
        says="bed line(s) outside admission..discharge: 2026-03-08, 2026-03-16",
    ),
    Pair(
        "bed: the admission-day bed line missing",
        lambda d: drop(d, TABLE_PROCEDURES, line(2, "510010", "2026-03-09")),
        (BED,),
        1,
    ),
    Pair(
        "bed: the discharge-day bed line missing",
        lambda d: drop(d, TABLE_PROCEDURES, line(2, "510010", "2026-03-15")),
        (BED,),
        1,
    ),
    Pair(
        "bed: every ward bed line removed (the companions remain)",
        lambda d: drop(d, TABLE_PROCEDURES, of(2) & (pl.col("procedure_code") == "510010")),
        (BED,),
        1,
    ),
    Pair(
        "bed: a quantity of 3",
        lambda d: edit(d, TABLE_PROCEDURES, line(2, "510010", "2026-03-11"), quantity=3),
        (BED,),
        1,
    ),
    Pair(
        "bed: a ward bed and a day bed on the same day",
        lambda d: add_procedure(d, 2, "510120", "2026-03-11"),
        (BED, PATHWAY),
        3,
    ),
    # the ICU stay is patient 10 (story S11): 510090 on 06-02 and 06-06, P552002 on 06-03..06-05, the
    # discharge day 06-07 is the transfer day and carries no ICU line
    Pair(
        "bed: a ward bed and an ICU day fee on the same day",
        lambda d: add_procedure(d, 10, "510010", "2026-06-06"),
        (BED, PATHWAY),
        3,  # two bed lines on the day, a ward bed on an ICU stay, a code outside the pathway
    ),
    Pair(
        "bed: an ICU package day missing between the end days",
        lambda d: drop(d, TABLE_PROCEDURES, line(10, "P552002", "2026-06-04")),
        (BED,),
        1,
    ),
    Pair(
        "bed: an ICU day fee on the transfer day",
        lambda d: add_procedure(d, 10, "510090", "2026-06-07"),
        (BED,),
        1,
    ),
    Pair(
        "bed: a bed line with a date that is not a date",
        lambda d: edit(
            d, TABLE_PROCEDURES, line(2, "510010", "2026-03-11"), procedure_date="11.03.2026"
        ),
        (BED, DATES),
        3,
    ),
    # an ICU package is a bed day, and it does not make a package claim: only the pathway objects
    Pair(
        "bed: the newborn ICU package P552006 on an ICU day is a bed day, not a package",
        lambda d: edit(
            d,
            TABLE_PROCEDURES,
            line(10, "P552002", "2026-06-04"),
            procedure_code="P552006",
            procedure_category="paket",
        ),
        (PATHWAY,),
        1,
    ),
    Pair(
        "bed: the adult ICU package P552003 on an ICU day is a bed day, not a package",
        lambda d: edit(
            d,
            TABLE_PROCEDURES,
            line(10, "P552002", "2026-06-04"),
            procedure_code="P552003",
            procedure_category="paket",
        ),
        (PATHWAY,),
        1,
    ),
    Pair(
        "bed: a stay of one date with its one bed line is valid",
        _one_day_stay,
        only=BED,
    ),
    Pair(
        "bed: a day bed on a day case (admission and discharge on the same date) is valid",
        _day_case_with_a_day_bed,
        only=BED,
    ),
    Pair(
        "bed: a ward bed on a day case is valid too",
        lambda d: (_one_day_stay(d), set_code(d, 2, "510010", "510010")),
        only=BED,
    ),
    Pair(
        "bed: a stay of one night with ward beds on both dates is valid",
        _one_night_stay,
        only=BED,
    ),
    Pair(
        "bed: a day bed on the first date of a stay of one night is a defect of the line",
        lambda d: (_one_night_stay(d), set_code(d, 2, "510010", "510120", "2026-03-09")),
        (BED,),
        1,
        only=BED,
        at=row_at(2, TABLE_PROCEDURES, line(2, "510010", "2026-03-09")),
        says="day bed line 510120 on the stay 2026-03-09..2026-03-10; the day bed is for a day case",
    ),
    Pair(
        "bed: a day bed on a day case with the quantity 2",
        lambda d: (
            _day_case_with_a_day_bed(d),
            edit(d, TABLE_PROCEDURES, line(2, "510120"), quantity=2),
        ),
        (BED,),
        1,
        only=BED,
    ),
    Pair(
        "bed: discharge before admission (the dates reversed on the header)",
        lambda d: edit(
            d,
            TABLE_CLAIM_HEADERS,
            of(2),
            admission_date="2026-03-15",
            discharge_date="2026-03-09",
            claim_start_date="2026-03-15",
            claim_end_date="2026-03-09",
        ),
        (BED, COMP, DATES),
        52,
    ),
    Pair(
        "bed: a stay without an admission date has no days to cover (the beds are not outside it)",
        lambda d: edit(d, TABLE_CLAIM_HEADERS, of(2), admission_date=None),
        (COMP, DATES),
        7,
    ),
    Pair(
        "bed: two days without a bed line are listed in order",
        lambda d: drop(
            d,
            TABLE_PROCEDURES,
            of(2)
            & pl.col("procedure_date").is_in(["2026-03-13", "2026-03-10"])
            & (pl.col("procedure_code") == "510010"),
        ),
        (BED,),
        1,
        at=CLAIM[2],
        says="no bed line on 2 of 7 day(s): 2026-03-10, 2026-03-13",
    ),
    # --- stay.companion_coverage
    Pair(
        "companion: a date that is not a date",
        lambda d: edit(
            d, TABLE_PROCEDURES, line(2, "510121", "2026-03-11"), procedure_date="11.03.2026"
        ),
        (COMP, DATES),
        2,
    ),
    Pair(
        "companion: a stay without a discharge date",
        lambda d: edit(d, TABLE_CLAIM_HEADERS, of(2), discharge_date=None),
        (COMP, DATES),
        7,
    ),
    Pair(
        "companion: an extra companion on a package claim night is no companion defect",
        lambda d: add_procedure(d, 5, "510121", "2026-09-05"),
        only=COMP,
    ),
    # --- stay.dates_in_window
    Pair(
        "dates: a stay without a discharge date",
        lambda d: edit(d, TABLE_CLAIM_HEADERS, of(2), discharge_date=None),
        (COMP, DATES),
        7,
    ),
    Pair(
        "dates: a stay that ends one day before discharge",
        lambda d: edit(d, TABLE_CLAIM_HEADERS, of(2), claim_end_date="2026-03-14"),
        (DATES,),
        2,
    ),
    Pair(
        "dates: a stay that starts one day after admission",
        lambda d: edit(d, TABLE_CLAIM_HEADERS, of(2), claim_start_date="2026-03-10"),
        (DATES,),
        25,
    ),
    Pair(
        "dates: an acil claim with an empty text as its admission date (an empty text is no missing date)",
        lambda d: edit(d, TABLE_CLAIM_HEADERS, of(7), admission_date=""),
        (DATES,),
        1,
    ),
    Pair(
        "dates: a drug line the day before the claim starts",
        lambda d: edit(
            d,
            TABLE_DRUGS,
            of(2) & (pl.col("barkod") == "8699508270224"),
            drug_claim_date="2026-03-08",
        ),
        (DATES,),
        1,
    ),
    Pair(
        "dates: the material lines on the end date are valid",
        lambda d: edit(d, TABLE_MATERIALS, of(5), material_date="2026-09-08"),
        only=DATES,
    ),
    Pair(
        "dates: the material lines the day after the end date",
        lambda d: edit(d, TABLE_MATERIALS, of(5), material_date="2026-09-09"),
        (DATES,),
        3,
    ),
    Pair(
        "dates: the material lines the day before the start date",
        lambda d: edit(d, TABLE_MATERIALS, of(5), material_date="2026-09-02"),
        (DATES,),
        3,
    ),
    Pair(
        "dates: a diagnosis without a date",
        lambda d: edit(d, TABLE_DIAGNOSES, I10_OF_2, diagnosis_date=None),
        (DATES,),
        1,
        at=row_at(2, TABLE_DIAGNOSES, I10_OF_2),
        says="dated (missing) outside the claim window",
    ),
    Pair(
        "dates: a claim start date that is not a date",
        lambda d: edit(d, TABLE_CLAIM_HEADERS, of(4), claim_start_date="garbage"),
        (DATES, ARITH),
        36,
    ),
    Pair(
        "dates: a start date that is not a date is named in the finding about the claim",
        lambda d: edit(d, TABLE_CLAIM_HEADERS, of(4), claim_start_date="garbage"),
        (DATES,),
        35,  # the claim, and the 34 lines and diagnoses that are outside a window with no start
        only=DATES,
        at=CLAIM[4],
        says="admission 2026-05-11, discharge 2026-05-16, start none, end 2026-05-16",
    ),
    Pair(
        "dates: an end date that is not a date is named in the finding about the claim",
        lambda d: edit(d, TABLE_CLAIM_HEADERS, of(4), claim_end_date="garbage"),
        (DATES,),
        35,  # the claim, and the same 34 lines and diagnoses outside a window with no end
        only=DATES,
        at=CLAIM[4],
        says="admission 2026-05-11, discharge 2026-05-16, start 2026-05-11, end none",
    ),
    Pair(
        "arith: a start date that is not a date leaves the claim year unknown",
        lambda d: edit(d, TABLE_CLAIM_HEADERS, of(4), claim_start_date="garbage"),
        (ARITH,),
        1,
        only=ARITH,
        at=CLAIM[4],
        says="TANI_YASI is 86; the claim year is unknown and the birth year 1940, which makes the age unknown",
    ),
    Pair(
        "dates: an acil claim whose start date is not a date",
        lambda d: edit(d, TABLE_CLAIM_HEADERS, of(7), claim_start_date="garbage"),
        (DATES, ARITH),
        22,
    ),
    Pair(
        "dates: a performed line the day after the claim",
        lambda d: edit(
            d, TABLE_PERFORMED, pl.col("procedure_code") == "530080", service_date="2026-02-20"
        ),
        (DATES, PERF),
        2,
    ),
    Pair(
        "dates: a claim of type poliklinik shaped like the acil claim is valid for the window rule",
        lambda d: edit(d, TABLE_CLAIM_HEADERS, of(7), claim_type="poliklinik"),
        (VISIT,),
        1,
    ),
    Pair(
        "dates: a claim of another type has no window rule",
        lambda d: edit(d, TABLE_CLAIM_HEADERS, of(7), claim_type="ayaktan"),
    ),
    # --- bill.performed_billed
    Pair(
        "perf: a performed line filed under another claim",
        lambda d: edit(d, TABLE_PERFORMED, pl.col("procedure_code") == "530080", claim_id=CLAIM[6]),
        (PERF, DATES),
        2,
    ),
    Pair(
        "perf: a performed line without a service date",
        lambda d: edit(d, TABLE_PERFORMED, pl.col("procedure_code") == "530100", service_date=None),
        (PERF, DATES),
        2,
    ),
    Pair(
        "perf: a duplicated performed row is valid",
        lambda d: add_row(
            d,
            TABLE_PERFORMED,
            pl.col("procedure_code") == "530080",
            performed_line_id="EMR-F-SENTETIK-HASTA-0007-001-099",
        ),
        only=PERF,
    ),
    Pair(
        "perf: a billed line of quantity 0 still bills the performed line",
        lambda d: edit(d, TABLE_PROCEDURES, line(7, "530080"), quantity=0),
        only=PERF,
    ),
    Pair(
        "perf: a performed code in lower case is another code",
        lambda d: edit(
            d, TABLE_PERFORMED, pl.col("procedure_code") == "R101450", procedure_code="r101450"
        ),
        (PERF,),
        1,
    ),
    # --- package.mode
    Pair(
        "pkg: a package line filed as an islem",
        lambda d: edit(d, TABLE_PROCEDURES, line(1, "P610131"), procedure_category="islem"),
        (PACKAGE, BED, PAIRING),
        3,
    ),
    Pair(
        "pkg: a second package line is valid",
        lambda d: add_procedure(d, 5, "P609235", "2026-09-04", specialty="1900"),
        only=PACKAGE,
    ),
    Pair(
        "pkg: a companion line on a package claim",
        lambda d: add_procedure(d, 8, "510121", "2026-09-15"),
        (PACKAGE, PATHWAY),
        2,
    ),
    Pair(
        "pkg: an ICU day fee on a package claim",
        lambda d: add_procedure(d, 5, "510090", "2026-09-04"),
        (PACKAGE, PATHWAY),
        2,
    ),
    Pair(
        "pkg: the several-operations anaesthesia code on a package claim",
        lambda d: add_procedure(d, 5, "550230", "2026-09-04", specialty="3100"),
        (PACKAGE, PAIRING, PATHWAY),
        3,
    ),
    # --- anaesthesia.operation_pairing
    Pair(
        "pair: a second anaesthesia line of another group on the operation day",
        lambda d: add_procedure(d, 3, "550170", "2026-08-18", specialty="3100"),
        (PAIRING, GROUP, PATHWAY),
        3,
    ),
    Pair(
        "pair: an anaesthesia line on the discharge day, without an operation",
        lambda d: add_procedure(d, 3, "550160", "2026-08-20", specialty="3100"),
        (PAIRING,),
        1,
    ),
    Pair(
        "pair: the anaesthesia a day late leaves two days wrong",
        lambda d: edit(d, TABLE_PROCEDURES, line(3, "550160"), procedure_date="2026-08-19"),
        (PAIRING,),
        2,
    ),
    Pair(
        "pair: a code that is no anaesthesia code (550165) leaves the operation day without one",
        lambda d: edit(d, TABLE_PROCEDURES, line(3, "550160"), procedure_code="550165"),
        (PAIRING, PATHWAY),
        2,
    ),
    Pair(
        "pair: a second operation on another day with its own anaesthesia is valid",
        lambda d: (
            add_procedure(d, 3, "609810", "2026-08-19", specialty="1900"),
            add_procedure(d, 3, "550160", "2026-08-19", specialty="3100"),
        ),
        only=PAIRING,
    ),
    # --- anaesthesia.group: the total puan of the day decides, by the bands in force that day
    Pair(
        "group: two operations (615931 + 609810, puan 12477.99, group A3) with the A3 code of several operations are valid",
        lambda d: (
            add_procedure(d, 3, "609810", "2026-08-18", specialty="1900"),
            set_code(d, 3, "550160", "550220"),
        ),
        only=GROUP,
    ),
    Pair(
        "group: the same two operations with the code of several operations of the larger group B",
        lambda d: (
            add_procedure(d, 3, "609810", "2026-08-18", specialty="1900"),
            set_code(d, 3, "550160", "550230"),
        ),
        (GROUP,),
        1,
        only=GROUP,
        says="2 operation(s) with puan 12477.99 are group A3, which is 550220",
    ),
    Pair(
        "group: 610131 on 2026-04-16 with the C code is valid (the new bands)",
        lambda d: (
            shift_claim(d, 3, -124),
            replace_op(d, 3, "615931", "610131", "2026-04-16"),
            set_code(d, 3, "550160", "550170"),
        ),
        only=GROUP,
    ),
    Pair(
        "group: 610131 on 2026-04-15 with the C code (the old bands say B)",
        lambda d: (
            shift_claim(d, 3, -125),
            replace_op(d, 3, "615931", "610131", "2026-04-15"),
            set_code(d, 3, "550160", "550170"),
        ),
        (GROUP,),
        1,
        only=GROUP,
    ),
    Pair(
        "group: 610131 on 2026-04-15 with the B code is valid (the old bands)",
        lambda d: (shift_claim(d, 3, -125), replace_op(d, 3, "615931", "610131", "2026-04-15")),
        only=GROUP,
    ),
    Pair(
        "group: 610131 on 2026-04-16 with the B code (the new bands say C)",
        lambda d: (shift_claim(d, 3, -124), replace_op(d, 3, "615931", "610131", "2026-04-16")),
        (GROUP,),
        1,
        only=GROUP,
    ),
    Pair(
        "group: an A1 operation (608540) with the A1 code is valid",
        lambda d: (
            replace_op(d, 3, "615931", "608540", "2026-08-18"),
            set_code(d, 3, "550160", "550130"),
        ),
        only=GROUP,
    ),
    Pair(
        "group: an A1 operation (608540) with the B code",
        lambda d: replace_op(d, 3, "615931", "608540", "2026-08-18"),
        (GROUP,),
        1,
        only=GROUP,
    ),
    Pair(
        "group: an E operation (621350) with the E code is valid",
        lambda d: (
            replace_op(d, 3, "615931", "621350", "2026-08-18"),
            set_code(d, 3, "550160", "550190"),
        ),
        only=GROUP,
    ),
    Pair(
        "group: an operation dated 2020-03-01, before EK-2B has a price, cannot be judged",
        lambda d: shift_claim(d, 3, -(date(2026, 8, 18) - date(2020, 3, 1)).days),
        only=GROUP,
    ),
    Pair(
        "group: an operation with no price in force (617710, repealed 2026-01-30) cannot be judged",
        lambda d: edit(d, TABLE_PROCEDURES, line(3, "615931"), procedure_code="617710"),
        only=GROUP,
    ),
    # --- the checks do not break on rows they cannot place
    Pair("robust: every table empty (no rows, the same columns)", _every_table_empty),
    Pair(
        "robust: a procedure line with no claim id is named by the placeholder",
        lambda d: add_row(d, TABLE_PROCEDURES, of(2), claim_id=None),
        (DATES,),
        1,
        at=f"{NO_CLAIM} procedure_claim_lines[",
        says="dated 2026-03-09 outside the claim window (no header)..(no header)",
    ),
    Pair(
        "robust: a header with no claim id is named by the placeholder",
        lambda d: (
            edit(d, TABLE_CLAIM_HEADERS, of(4), claim_id=None),
            edit_patient(d, 4, TANI_YASI=1),
        ),
        (ARITH, COMP, DATES),
        40,
    ),
    Pair(
        "robust: a procedure line with no code",
        lambda d: add_row(
            d,
            TABLE_PROCEDURES,
            of(2),
            procedure_code=None,
            procedure_line_id="ISL-F-SENTETIK-HASTA-0002-001-099",
        ),
        (PATHWAY,),
        1,
        at=f"{CLAIM[2]} procedure_claim_lines[ISL-F-SENTETIK-HASTA-0002-001-099]",
        says="procedure code (none) is not in the expansion of",
    ),
    Pair(
        "robust: a claim without any procedure line leaves its performed lines unbilled",
        lambda d: drop(d, TABLE_PROCEDURES, of(7)),
        (PERF,),
        4,
    ),
]


def _at_of(at: str | Callable[[Data], str], base: Data) -> str:
    """A `where` fragment: the text itself, or the one a function reads from the data before the defect."""
    return at(base) if callable(at) else at


def _names(problem: Problem, at: str, says: str) -> bool:
    """The finding is about `at` and says `says`. An `at` that is only a claim id (it has no space) is a
    finding about the claim itself; a longer one is a fragment of the `where`."""
    where_fits = problem.where == at if " " not in at else at in problem.where
    return where_fits and says in problem.message


@pytest.mark.parametrize("pair", PAIRS, ids=lambda p: p.name)
def test_a_boundary_input_trips_exactly_its_ids(pair: Pair, twins, anadata, context) -> None:
    data = Data(dict(twins), anadata)
    at = _at_of(pair.at, data)
    pair.mutate(data)
    examined = [pair.only] if pair.only else sorted(E1_CHECKS)
    found = data.problems(context, only=examined)
    assert only_ids(found) == set(pair.trips), [str(p) for p in found]
    assert len(found) == pair.n, [str(p) for p in found]
    if pair.at:
        assert any(_names(p, at, pair.says) for p in found), [str(p) for p in found]
    order = {check: index for index, check in enumerate(CHECKS)}
    keys = [(order[p.check], p.where, p.message) for p in found]
    assert keys == sorted(keys), [str(p) for p in found]
    assert all(names_a_real_row(p, data.tables) for p in found), [str(p) for p in found]


def test_the_boundary_pairs_cover_both_sides_of_every_limit_and_have_unique_names() -> None:
    assert len({pair.name for pair in PAIRS}) == len(PAIRS), "two pairs share a name"
    valid = [pair for pair in PAIRS if not pair.trips]
    invalid = [pair for pair in PAIRS if pair.trips]
    assert len(valid) >= 50 and len(invalid) >= 100, (len(valid), len(invalid))
    # every E1 id is tripped by at least one pair
    for check in sorted(E1_CHECKS):
        assert any(check in pair.trips for pair in PAIRS), check


# --- 3c. the order of the findings does not depend on the order of the rows ---------------------------


def _messy(twins, anadata) -> Data:
    """Defects that give several findings to one check, on several claims and in several tables."""
    data = Data(dict(twins), anadata)
    # a missing bed day, an anaesthesia, a billed line, a flag
    _several_defects_on_four_claims(data)
    _tag_of(6, 2)(data)  # eleven codes outside the pathway of S6
    # three diagnoses outside the window
    edit(data, TABLE_DIAGNOSES, of(2), diagnosis_date="2026-03-20")
    edit(data, TABLE_MATERIALS, of(5), material_date="2026-09-20")  # three materials, three dates
    add_diagnosis(data, 1, "C53.9")  # a sex gate and a code outside the pathway
    add_diagnosis(data, 3, "N41.0")  # a second one, from the ICD-10 blocks
    add_diagnosis(data, 2, "P07.3")  # an age gate
    add_diagnosis(data, 1, "O80.9")  # a second one
    clone_procedure(data, 2, line(2, "510121", "2026-03-10"))  # two companions on a night
    clone_procedure(data, 2, line(2, "510121", "2026-03-12"))  # and on another
    edit(data, TABLE_PROCEDURES, line(2, "510121", "2026-03-13"), quantity=0)
    clone_procedure(data, 2, line(2, "510010", "2026-03-10"))  # two beds on a day
    edit(data, TABLE_PROCEDURES, line(2, "510010", "2026-03-14"), quantity=2)
    add_procedure(data, 3, "550160", "2026-08-19", specialty="3100")  # an orphan anaesthesia
    return data


def _row_order(frame: pl.DataFrame, how: str) -> pl.DataFrame:
    if how == "reversed":
        return frame.reverse()
    return frame.sample(fraction=1.0, shuffle=True, seed=int(how))


@pytest.mark.parametrize("how", ["reversed", "1", "2", "3"])
def test_the_findings_do_not_depend_on_the_order_of_the_rows(how, twins, anadata, context) -> None:
    data = _messy(twins, anadata)
    expected = data.problems(context)
    per_check: dict[str, int] = {}
    for problem in expected:
        per_check[problem.check] = per_check.get(problem.check, 0) + 1
    assert len(expected) >= 35, len(expected)
    assert sum(1 for count in per_check.values() if count >= 2) >= 6, per_check
    shuffled = Data(
        {name: _row_order(frame, how) for name, frame in data.tables.items()},
        _row_order(data.anadata, how),
    )
    assert shuffled.problems(context) == expected


def test_the_findings_of_the_faulty_bills_and_their_registry_do_not_depend_on_the_row_order(
    built, anadata, context
) -> None:
    data = faulty_data(built, anadata)
    expected = data.problems(context)
    assert expected
    for how in ("reversed", "5"):
        # the answer rows follow the fault records in order: that order is the contract, not noise
        shuffled = Data(
            {
                name: frame if name == TABLE_ANSWERS else _row_order(frame, how)
                for name, frame in data.tables.items()
            },
            _row_order(data.anadata, how),
            copy.deepcopy(data.registry),
        )
        assert shuffled.problems(context) == expected, how


# --- 3d. the helpers every check uses ----------------------------------------------------------------


def test_format_joins_the_pieces_names_a_missing_value_and_counts_its_placeholders() -> None:
    frame = pl.DataFrame({"a": ["x", None, "z"], "b": [1, 2, None]})
    got = frame.select(
        _format("{}-{}", pl.col("a"), pl.col("b")).alias("two"),
        _format("start {} end", pl.col("a")).alias("one"),
        _format("{}", pl.col("b")).alias("only"),
        _format("{}{}", pl.col("a"), pl.col("a")).alias("touching"),
        _format("no placeholder").alias("none"),
    )
    assert got["two"].to_list() == ["x-1", "(none)-2", "z-(none)"]
    assert got["one"].to_list() == ["start x end", "start (none) end", "start z end"]
    assert got["only"].to_list() == ["1", "2", "(none)"]
    assert got["touching"].to_list() == ["xx", "(none)(none)", "zz"]
    assert got["none"].to_list() == ["no placeholder"] * 3
    with pytest.raises(ValueError, match="1 placeholders for 2 values"):
        _format("{}", pl.col("a"), pl.col("b"))
    with pytest.raises(ValueError, match="2 placeholders for 1 values"):
        _format("{} {}", pl.col("a"))


def test_format_survives_the_whole_icd_table_cut_down_to_a_few_rows(context) -> None:
    """`pl.format` of two columns panicked in polars 2.0.0 on exactly this: 15,000 rows, 63 left."""
    icd = context.icd.select("code", "sex")
    codes = icd.select(pl.col("code").alias("icd10_code"), pl.lit("M").alias("patient_sex"))
    joined = codes.join(icd, left_on="icd10_code", right_on="code", how="left")
    few = joined.filter(pl.col("sex").is_not_null() & (pl.col("sex") != pl.col("patient_sex")))
    assert joined.height > 15000 and 10 < few.height < 500
    got = few.select(
        _format("{} is limited to {}", pl.col("icd10_code"), pl.col("sex")).alias("text")
    )
    assert got["text"].to_list() == [
        f"{code} is limited to {sex}"
        for code, sex in zip(few["icd10_code"], few["sex"], strict=True)
    ]


def _copies(frame: pl.DataFrame, copy: int) -> pl.DataFrame:
    """The frame with every id column renamed for copy number `copy`: a patient and a claim of its own."""
    ids = [
        column
        for column, dtype in frame.schema.items()
        if dtype == pl.String and (column.endswith("_id") or column in {"HASTA_ID", "SQ_EPISODE"})
    ]
    return frame.with_columns([(pl.col(c) + pl.lit(f"-c{copy}")).alias(c) for c in ids])


def test_three_hundred_copies_of_the_bills_give_the_findings_of_the_small_table(
    twins, anadata, context
) -> None:
    """The same defects in one claim of a table of 36,000 procedure lines: the same findings.

    The copies are clean claims of their own; the defects sit in the first copy, which keeps the
    original ids. A check that breaks on a larger table (polars 2.0.0 panicked in the sex gate on
    thousands of diagnoses with a few findings) fails here, and so does one that lets the other
    claims change a finding.
    """
    copies = 300
    big = {
        name: pl.concat([frame, *[_copies(frame, k) for k in range(1, copies)]])
        for name, frame in twins.items()
    }
    big_anadata = pl.concat([anadata, *[_copies(anadata, k) for k in range(1, copies)]])
    assert big[TABLE_PROCEDURES].height > 30000 and big[TABLE_DIAGNOSES].height > 6000
    e1 = sorted(E1_CHECKS)
    assert Data(dict(big), big_anadata).problems(context, only=e1) == []
    expected = _messy(twins, anadata).problems(context, only=e1)
    assert len(expected) >= 30
    assert _messy(big, big_anadata).problems(context, only=e1) == expected


def test_the_findings_of_a_check_are_sorted_and_a_missing_where_is_named() -> None:
    found = pl.DataFrame(
        {"where": ["F-2", None, "F-1 b", "F-1 a", "F-1 a"], "message": ["m", "n", "z", "y", "x"]}
    )
    got = _problems("package.mode", found)
    assert [(p.where, p.message) for p in got] == [
        (NO_CLAIM, "n"),
        ("F-1 a", "x"),
        ("F-1 a", "y"),
        ("F-1 b", "z"),
        ("F-2", "m"),
    ]
    assert all(p.check == "package.mode" for p in got)


def test_a_where_names_the_claim_the_table_and_the_line_and_a_missing_claim_is_the_same_text_everywhere() -> (
    None
):
    frame = pl.DataFrame(
        {"claim_id": ["F-1", None], "table": ["t_one", "t_two"], "line": ["L-1", None]}
    )
    got = frame.select(
        _where("claim_id", "procedure_claim_lines", "line").alias("fixed"),
        _where("claim_id", pl.col("table"), "line").alias("column"),
        _claim_text().alias("claim"),
    )
    assert got["fixed"].to_list() == [
        "F-1 procedure_claim_lines[L-1]",
        f"{NO_CLAIM} procedure_claim_lines[(none)]",
    ]
    assert got["column"].to_list() == ["F-1 t_one[L-1]", f"{NO_CLAIM} t_two[(none)]"]
    assert got["claim"].to_list() == ["F-1", NO_CLAIM]
    assert NO_CLAIM == "(no-claim-id)"


def test_the_days_of_a_finding_are_listed_in_date_order() -> None:
    frame = pl.DataFrame(
        {
            "group": [1, 1, 1, 2],
            "day": [date(2026, 3, 12), date(2026, 3, 9), date(2026, 3, 10), date(2026, 1, 1)],
        }
    )
    got = frame.group_by("group", maintain_order=True).agg(_days_text())
    assert got["day"].to_list() == ["2026-03-09, 2026-03-10, 2026-03-12", "2026-01-01"]


def test_a_block_holds_the_codes_between_its_ends_judged_on_as_many_characters_as_the_ends_have() -> (
    None
):
    codes = [
        "N40", "N40.1", "N53", "N54", "N39.0", "D07.3", "D07.4", "D07.6", "D07.7", "D07",
        "E29.0", "E2", "I86.1", "I86.0", "n41.0", "", None,
    ]  # fmt: skip
    blocks = ("N40-N53", "D07.4-D07.6", "E29", "I86.1")
    got = pl.DataFrame({"code": codes}).select(_in_blocks(pl.col("code"), blocks).alias("in"))
    assert got["in"].to_list() == [
        True, True, True, False, False, False, True, True, False, False,
        True, False, True, False, False, False, False,
    ]  # fmt: skip


def test_a_phrase_keeps_its_spaces_in_a_word_pattern_and_a_whole_word_has_both_edges() -> None:
    assert _words_pattern(["Tüp ligasyonu", "tup ligasyonu"]) == "(?:tup ligasyonu)"
    assert _words_pattern(["over"], whole=True) == r"\b(?:over)\b"
    names = pl.DataFrame(
        {"f": ["tup ligasyonu", "tup  ligasyonu", "recover", "over", "cross over", "overdoz"]}
    )
    phrase = names.filter(pl.col("f").str.contains(_words_pattern(["tüp ligasyonu"])))
    assert phrase["f"].to_list() == ["tup ligasyonu"]
    whole = names.filter(pl.col("f").str.contains(_words_pattern(["over"], whole=True)))
    assert whole["f"].to_list() == ["over", "cross over"]  # not inside recover, not before doz


def test_as_of_takes_one_row_of_the_history_in_force_on_the_day_and_none_outside() -> None:
    """Rows are in force from `valid_from` to `valid_to` inclusive (no `valid_to`: still open)."""
    frame = pl.DataFrame(
        {
            "code": ["A", "A", "A", "A", "B", "B", "C"],
            "day": [
                "2026-01-10",  # two rows of A are in force: one is taken
                "2026-02-01",  # A: the closed row ended on 01-31, the open ones are in force
                "2025-12-31",  # A: before every row
                "2026-01-31",  # A: the last day of the closed row
                "2026-01-09",  # B: the last day of its only row
                "2026-01-10",  # B: the day after its only row
                "2026-01-10",  # C: not in the history
            ],
        }
    ).with_row_index("_n")
    history = pl.DataFrame(
        {
            "code": ["A", "A", "A", "B"],
            "valid_from": ["2026-01-01", "2026-01-01", "2026-02-01", "2026-01-01"],
            "valid_to": ["2026-01-31", None, None, "2026-01-09"],
            "puan": [1.0, 2.0, 3.0, 4.0],
        }
    )
    got = _as_of(frame, history, {"puan": "points"}, code="code", day="day")
    assert got.height == frame.height  # one row for each row of the frame, never two
    assert got["_n"].to_list() == list(range(7))
    points = got["points"].to_list()
    assert points[0] in (1.0, 2.0)
    assert points[1] in (2.0, 3.0)
    assert points[2] is None
    assert points[3] in (1.0, 2.0)
    assert points[4] == 4.0
    assert points[5] is None
    assert points[6] is None


def test_an_exception_phrase_is_blanked_as_written_not_as_a_pattern() -> None:
    names = pl.DataFrame({"n": ["abc", "a.c", "a.c b"]})
    got = names.select(_without_exceptions(pl.col("n"), ["a.c"]).alias("f"))["f"].to_list()
    assert got == ["abc", " ", "  b"]


def test_the_longest_exception_is_blanked_first_and_a_subset_of_phrases_can_be_given() -> None:
    name = pl.DataFrame({"n": ["Yenidoğan/Çocuk/Erişkin tedavisel soğutma"]})
    both = name.select(_without_exceptions(_fold(pl.col("n"))).alias("f"))["f"][0]
    assert "eriskin" not in both and "cocuk" not in both and "yenidogan" not in both
    shorter_only = name.select(
        _without_exceptions(_fold(pl.col("n")), ["Yenidoğan/Çocuk"]).alias("f")
    )["f"][0]
    assert "eriskin" in shorter_only  # the shorter phrase alone leaves the adult word
    none = name.select(_without_exceptions(_fold(pl.col("n")), []).alias("f"))["f"][0]
    assert none == "yenidogan/cocuk/eriskin tedavisel sogutma"


def test_a_missing_value_is_named_in_the_message_not_dropped(twins, anadata, context) -> None:
    data = Data(dict(twins), anadata)
    edit(data, TABLE_PROCEDURES, line(3, "615931"), procedure_specialty_code=None)
    (problem,) = data.problems(context, only="fit.operation_department")
    assert problem.message.endswith(
        "has the specialty (none), which is not a surgical EK-2A branch"
    )


def test_the_mutations_leave_the_shared_tables_and_the_registry_untouched(
    built, twins, anadata
) -> None:
    before = {name: frame.clone() for name, frame in twins.items()}
    faulty_before = {name: frame.clone() for name, frame in built.tables.items()}
    registry_before = copy.deepcopy(built.registry)
    for case in CASES:
        case.mutate(fresh(case, built, twins, anadata))
    assert all(twins[name].equals(frame) for name, frame in before.items())
    assert all(built.tables[name].equals(frame) for name, frame in faulty_before.items())
    assert built.registry == registry_before


# --- 4. the meaning of the checks, beyond the mutation cases ---------------------------------------


def run_only(data: Data, context: PlausibilityContext, check: str) -> list[Problem]:
    return data.problems(context, only=check)


def test_only_restricts_the_run_and_unknown_ids_are_refused(twins, anadata, context) -> None:
    data = Data(dict(twins), anadata)
    drop(data, TABLE_PROCEDURES, line(3, "550160"))
    assert only_ids(data.problems(context, only="anaesthesia.operation_pairing")) == {PAIRING}
    assert data.problems(context, only=["stay.bed_coverage", PACKAGE]) == []
    assert data.problems(context, only=[]) == []
    with pytest.raises(KeyError, match="unregistered"):
        data.problems(context, only=["stay.bed_coverage", "stay.no_such_check"])


def test_a_missing_table_is_reported_by_name(twins, anadata, context) -> None:
    tables = {name: frame for name, frame in twins.items() if name != TABLE_DRUGS}
    with pytest.raises(PlausibilityError, match="drug_claim_lines"):
        check_plausibility(
            tables, {TABLE_ANADATA: anadata}, context=context, only="fit.pathway_membership"
        )
    with pytest.raises(PlausibilityError, match="anadata_clean"):
        check_plausibility(dict(twins), {}, context=context, only="patient.sex_gate")


def test_the_problems_come_in_the_order_of_the_registry(built, anadata, context) -> None:
    found = check_plausibility(built.tables, {TABLE_ANADATA: anadata}, context=context)
    order = {check: index for index, check in enumerate(CHECKS)}
    assert [order[p.check] for p in found] == sorted(order[p.check] for p in found)


def test_an_absent_companion_is_not_a_defect(twins, anadata, context) -> None:
    data = Data(dict(twins), anadata)
    drop(data, TABLE_PROCEDURES, pl.col("procedure_code") == "510121")
    assert run_only(data, context, "stay.companion_coverage") == []


def test_icu_days_are_the_bed_days_of_an_icu_stay_and_an_icu_package_makes_no_package_claim(
    twins, anadata, context
) -> None:
    """S11's twin: 510090 on the first and the last ICU day, P552002 between, nothing on the transfer day."""
    data = Data(dict(twins), anadata)
    for check in ("stay.bed_coverage", PACKAGE):
        assert run_only(data, context, check) == [], check
    header = twins[TABLE_CLAIM_HEADERS].filter(of(10))
    assert header["package_candidate"].to_list() == [False]  # the ICU package is no surgical package
    lines = twins[TABLE_PROCEDURES].filter(of(10))
    assert lines.filter(pl.col("procedure_code") == "P552002").height == 3
    icu = lines.filter(pl.col("procedure_code").is_in(["510090", "P552002"]))
    assert "2026-06-07" not in icu["procedure_date"].to_list()  # the transfer day
    assert header["discharge_date"].to_list() == ["2026-06-07"]


def test_the_incubator_and_the_cot_are_bed_day_codes_but_no_icu_day(context) -> None:
    """510070 and 510081 are the newborn beds: one bed day each, and a newborn ward is no ICU stay."""
    assert context.code_sets["beds"]["incubator"]["code"] == "510070"
    assert context.code_sets["beds"]["cot"]["code"] == "510081"
    assert {"510070", "510081"} <= set(context.bed_day_codes)
    assert not {"510070", "510081"} & set(context.icu_day_codes)
    assert not {"510070", "510081"} & set(context.icu_codes)
    assert {"510010", "510120", "510090"} <= set(context.bed_day_codes)  # the other bed codes stay


def test_a_newborn_stay_in_the_incubator_is_a_stay_with_a_bed_on_every_day(twins, anadata, context) -> None:
    """S12's twin: 510070 on all six calendar days, the discharge day included, no ICU line."""
    data = Data(dict(twins), anadata)
    assert run_only(data, context, "stay.bed_coverage") == []
    lines = twins[TABLE_PROCEDURES].filter(of(11))
    days = lines.filter(pl.col("procedure_code") == "510070")["procedure_date"].sort().to_list()
    assert days == [f"2026-07-{d}" for d in range(10, 16)]
    assert twins[TABLE_CLAIM_HEADERS].filter(of(11))["discharge_date"].to_list() == ["2026-07-15"]


def test_a_cot_is_a_bed_day_like_the_incubator(twins, anadata, context) -> None:
    data = Data(dict(twins), anadata)
    set_code(data, 11, "510070", "510081", "2026-07-12")
    assert run_only(data, context, "stay.bed_coverage") == []


def test_a_newborn_bed_on_an_icu_stay_is_a_ward_bed_on_an_icu_stay(twins, anadata, context) -> None:
    """An ICU package makes the claim an ICU stay; the incubator lines are then ward beds beside ICU lines."""
    data = Data(dict(twins), anadata)
    add_procedure(data, 11, "P552006", "2026-07-11")
    found = run_only(data, context, "stay.bed_coverage")
    ward = [p for p in found if "ward bed line 510070 on an ICU stay" in p.message]
    assert len(ward) == 6, [str(p) for p in found]


def _ward_findings(data: Data, context) -> list[str]:
    """What stay.bed_coverage says about the ward bill of patient 10 (claim-level findings carry the claim id as `where`)."""
    return [p.message for p in run_only(data, context, "stay.bed_coverage") if p.claim_id == WARD]


def test_a_ward_stay_after_an_icu_bill_has_no_bed_on_the_icu_exit_day_and_is_clean(twins, anadata, context) -> None:
    """S14's twin: admitted on 06-07, the day the ICU bill ends; its beds are 06-08 .. 06-10, the companions 06-07 .. 06-09."""
    data = Data(dict(twins), anadata)
    assert _ward_findings(data, context) == []
    lines = twins[TABLE_PROCEDURES].filter(pl.col("claim_id") == WARD)
    assert sorted(lines.filter(pl.col("procedure_code") == "510010")["procedure_date"]) == [
        "2026-06-08", "2026-06-09", "2026-06-10",
    ]  # fmt: skip
    header = twins[TABLE_CLAIM_HEADERS].filter(pl.col("claim_id") == WARD)
    assert header["admission_date"].to_list() == ["2026-06-07"]
    icu = twins[TABLE_CLAIM_HEADERS].filter(pl.col("claim_id") == CLAIM[10])
    assert icu["discharge_date"].to_list() == ["2026-06-07"]  # the day the ICU bill ends is the ward bill's first day


def test_the_committed_faulty_ward_bill_bills_the_bed_on_the_icu_exit_day(built, anadata, context) -> None:
    """The fault of S14, seen by the data check alone: the one finding is the bed line of 06-07."""
    data = Data(dict(built.tables), anadata)
    found = [p for p in run_only(data, context, "stay.bed_coverage") if p.claim_id == WARD]
    assert len(found) == 1, [str(p) for p in found]
    assert "bed line 510010 on 2026-06-07, the day the patient leaves the ICU stay" in found[0].message
    assert "double billing" in found[0].message


def test_a_ward_stay_needs_its_first_day_bed_when_no_icu_stay_ends_that_day(twins, anadata, context) -> None:
    """Without the ICU lines the first bill is no ICU stay: nothing pays 06-07, so the ward bill needs a bed there."""
    data = Data(dict(twins), anadata)
    drop(data, TABLE_PROCEDURES, (pl.col("claim_id") == CLAIM[10]) & pl.col("procedure_code").is_in(["510090", "P552002"]))
    assert _ward_findings(data, context) == ["no bed line on 1 of 4 day(s): 2026-06-07"]


def test_an_icu_stay_that_ended_the_day_before_is_no_transfer_day(twins, anadata, context) -> None:
    data = Data(dict(twins), anadata)
    edit(data, TABLE_CLAIM_HEADERS, pl.col("claim_id") == CLAIM[10], discharge_date="2026-06-06")
    assert _ward_findings(data, context) == ["no bed line on 1 of 4 day(s): 2026-06-07"]


def test_an_icu_stay_of_another_patient_is_no_transfer_day(twins, anadata, context) -> None:
    data = Data(dict(twins), anadata)
    edit(data, TABLE_CLAIM_HEADERS, pl.col("claim_id") == WARD, patient_id=PATIENT[9])
    assert _ward_findings(data, context) == ["no bed line on 1 of 4 day(s): 2026-06-07"]


def test_an_icu_stay_is_not_its_own_transfer_day(twins, anadata, context) -> None:
    """An ICU stay that ends the day it began is not preceded by itself: its ward bed is a ward bed on an ICU stay, nothing more."""
    data = Data(dict(twins), anadata)
    edit(data, TABLE_CLAIM_HEADERS, pl.col("claim_id") == CLAIM[10], admission_date="2026-06-07")
    add_row(data, TABLE_PROCEDURES, line(10, "510090", "2026-06-02"), procedure_line_id=procedure_line_id(CLAIM[10], 99), procedure_code="510010", procedure_date="2026-06-07")
    own = [p.message for p in run_only(data, context, "stay.bed_coverage") if p.claim_id == CLAIM[10]]
    assert any("ward bed line 510010 on an ICU stay" in message for message in own), own
    assert not any("double billing" in message for message in own), own


def test_two_icu_stays_ending_on_the_same_day_name_the_first_one_once(twins, anadata, context) -> None:
    """Two ICU bills end on 06-07: a ward bed on that day is one double billing, named after the first ICU bill."""
    data = Data(dict(twins), anadata)
    other = claim_id(PATIENT[10], 3)
    add_row(data, TABLE_CLAIM_HEADERS, pl.col("claim_id") == CLAIM[10], claim_id=other, episode_id=episode_id(PATIENT[10], 3))
    add_row(data, TABLE_PROCEDURES, line(10, "510090", "2026-06-02"), claim_id=other, procedure_line_id=procedure_line_id(other, 1))
    add_row(
        data, TABLE_PROCEDURES, _ward("510010", "2026-06-08"),
        procedure_line_id=procedure_line_id(WARD, 99), procedure_date="2026-06-07",
    )  # fmt: skip
    found = [p for p in run_only(data, context, "stay.bed_coverage") if p.claim_id == WARD]
    assert len(found) == 1, [str(p) for p in found]
    assert f"the ICU stay {CLAIM[10]};" in found[0].message


def test_the_day_bed_is_the_code_set_day_bed_and_a_bed_day_code(context) -> None:
    """510120 is for a day case; on a longer stay it is a defect of its own (see the pairs)."""
    assert context.day_bed_code == "510120"
    assert context.day_bed_code in context.bed_day_codes
    assert context.code_sets["beds"]["day_bed"]["name"] == "Gündüz yatak tarifesi"
    assert context.code_sets["beds"]["ward_day"]["code"] == "510010"
    assert context.code_sets["beds"]["ward_day"]["code"] != context.day_bed_code


def test_the_one_day_bed_of_the_cohort_is_on_the_clean_twin_of_the_stay_of_one_date(built, twins) -> None:
    """S47's clean twin bills the day bed of its stay of one date; its faulty (committed) bill leaves it out."""
    day_beds = twins[TABLE_PROCEDURES].filter(pl.col("procedure_code") == "510120")
    assert day_beds.select("claim_id", "procedure_date").rows() == [(OBSERVATION_CLAIM, "2026-02-25")]
    assert built.tables[TABLE_PROCEDURES].filter(pl.col("procedure_code") == "510120").height == 0


def test_a_minor_operation_on_an_acil_claim_is_not_a_major_one(twins, anadata, context) -> None:
    data = Data(dict(twins), anadata)
    add_procedure(data, 7, "610680", "2026-02-19", specialty="2600")  # a short arm splint, group E
    assert run_only(data, context, "fit.operation_setting") == []
    assert run_only(data, context, "fit.operation_department") == []


def test_a_pregnancy_code_on_a_woman_in_the_age_range_is_fine(twins, anadata, context) -> None:
    data = Data(dict(twins), anadata)
    add_diagnosis(data, 8, "O80.9")  # S8 is a woman aged 47
    assert run_only(data, context, "patient.age_gate") == []
    assert run_only(data, context, "patient.icd_valid") == []


def test_the_band_table_in_force_on_the_day_decides_the_anaesthesia_group(
    built, anadata, context
) -> None:
    """610131 (puan 5096.64) is group C from 2026-04-16 and was group B before: 550170 is C's code."""
    first = Data(dict(built.tables), anadata)
    assert first.problems(context, only="anaesthesia.group") == []

    def earlier(column: str) -> pl.Expr:
        shifted = pl.col(column).str.to_date("%Y-%m-%d").dt.offset_by("-122d").cast(pl.String)
        return pl.when(pl.col("claim_id") == CLAIM[1]).then(shifted).otherwise(pl.col(column))

    dates = {
        TABLE_CLAIM_HEADERS: [
            "admission_date",
            "discharge_date",
            "claim_start_date",
            "claim_end_date",
        ],
        TABLE_PROCEDURES: ["procedure_date"],
        TABLE_MATERIALS: ["material_date"],
        TABLE_DRUGS: ["drug_claim_date"],
        TABLE_DIAGNOSES: ["diagnosis_date"],
        TABLE_PERFORMED: ["service_date"],
    }
    moved = Data(dict(built.tables), anadata)
    for table, columns in dates.items():
        moved.tables[table] = moved.tables[table].with_columns([earlier(c) for c in columns])
    assert moved.tables[TABLE_CLAIM_HEADERS].filter(of(1))["claim_start_date"][0] == "2026-03-14"
    found = moved.problems(context)
    assert trips_by_claim(found)[CLAIM[1]] == {"package.mode", "anaesthesia.group"}
    assert "puan 5096.64 are group B" in str(
        next(p for p in found if p.check == "anaesthesia.group")
    )


def test_a_code_is_passive_from_its_passive_date_on(twins, anadata, context) -> None:
    """Z22.5 is passive since 2026-02-16; with every code active, only that date decides."""
    active = PlausibilityContext()
    vars(active)["icd"] = context.icd.with_columns(pl.lit(True).alias("is_active"))
    for day, passive in {"2026-02-15": False, "2026-02-16": True, "2026-02-17": True}.items():
        data = Data(dict(twins), anadata)
        seven = of(7) & (pl.col("icd10_code") == "R06.0")
        edit(data, TABLE_DIAGNOSES, seven, icd10_code="Z22.5", diagnosis_date=day)
        found = data.problems(active, only="patient.icd_valid")
        assert bool(found) is passive, day
        assert all("has been passive since 2026-02-16" in p.message for p in found)


def test_without_a_context_the_shared_default_is_used(twins, anadata) -> None:
    assert check_plausibility(twins, {TABLE_ANADATA: anadata}) == []


def test_s1_faulty_bill_fits_the_pathway_through_its_sibling(built, anadata, context) -> None:
    """The itemised bill of S1 holds codes that the package pathway does not: its sibling does."""
    vocabulary = context.vocabulary
    package = vocabulary.filter(pl.col("scenario_tag") == "appendicitis_lap_appendectomy_package")
    assert "510010" in package["code"].to_list()
    assert context.sibling_ids == {
        "appendicitis_lap_appendectomy_package": ["appendicitis_lap_appendectomy_itemized"],
        "pyelonephritis_dementia_second_visit_ultrasound": ["pyelonephritis_dementia_second_visit_exam_billed"],
        "parkinson_physiatry_visit": ["parkinson_physiatry_visit_second_walker_billed"],
        "urosepsis_ward_stay_after_icu_transfer": ["urosepsis_ward_stay_transfer_day_billed"],
        "gi_bleed_melena_er_visit": ["gi_bleed_melena_er_visit_manual_hct_billed"],
        "umbilical_hernia_day_case_package": ["umbilical_hernia_day_case_itemized"],
        "lumbar_instability_posterior_instrumentation_package": [
            "lumbar_instability_posterior_instrumentation_neuromonitoring_billed"
        ],
        "cholelithiasis_biliary_colic_er_green_area": ["cholelithiasis_biliary_colic_er_green_area_tests_billed"],
        "late_preterm_newborn_cot_ward_stay": ["late_preterm_newborn_cot_ward_stay_standard_bed_billed"],
        "cervical_cancer_radiotherapy_course": ["cervical_cancer_radiotherapy_course_keyed_as_totals"],
    }
    data = Data(dict(built.tables), anadata)
    assert data.problems(context, only="fit.pathway_membership") == []


# --- 4b. slice E2: the meaning of the checks, beyond the mutation cases -----------------------------


def test_the_flag_columns_are_the_boolean_columns_but_the_structural_one(twins) -> None:
    schema = twins[TABLE_MATERIALS].schema
    booleans = [column for column, dtype in schema.items() if dtype == pl.Boolean]
    assert set(STRUCTURAL_FLAGS) | set(REGISTRATION_FLAGS) <= set(booleans)
    flags = [column for column in booleans if column not in STRUCTURAL_FLAGS]
    assert len(flags) == 86, "a new Boolean column of material_claim_lines needs a healthy value"
    # requires_pre_auth is a compliance flag since a pathway can set it (slice G5a): healthy when false
    assert STRUCTURAL_FLAGS == ("is_bundled",) and "requires_pre_auth" in flags
    assert REGISTRATION_FLAGS == ("titubb_registered", "uts_registered")


def test_missing_flags_and_structural_flags_are_healthy(twins, anadata, context) -> None:
    data = Data(dict(twins), anadata)
    edit(
        data,
        TABLE_MATERIALS,
        mat(1),
        is_bundled=True,  # structural: what the line is, not a compliance flag
        requires_pre_auth=None,  # a missing flag is not a stray one
        titubb_registered=None,
        uts_registered=None,
        foreign_facility=None,
        medical_necessity_board_report=False,
    )
    assert data.problems(context, only="material.stray_flag") == []


def test_a_material_that_waits_for_an_approval_is_a_stray_flag(twins, anadata, context) -> None:
    """Slice G5a: a pathway may set `requires_pre_auth`; on a bill it is the material no board has approved (Tablo 15 #15)."""
    data = Data(dict(twins), anadata)
    edit(data, TABLE_MATERIALS, mat(1), requires_pre_auth=True)
    (problem,) = data.problems(context, only="material.stray_flag")
    assert problem.where == mat_at(1)
    assert problem.message.endswith("has flag(s) off the healthy value: requires_pre_auth is true")


def test_the_committed_faulty_s5_bill_has_exactly_one_stray_flag(built, anadata, context) -> None:
    data = Data(dict(built.tables), anadata)
    (problem,) = data.problems(context, only="material.stray_flag")
    assert problem.where == mat_at(2)
    assert (
        problem.message
        == "material AP2000 has flag(s) off the healthy value: uts_registered is false"
    )


def test_the_engine_is_asked_once_for_each_code_and_day_and_p_codes_go_to_ek2c(
    monkeypatch, twins, anadata, context
) -> None:
    from src.bilun.domain.pricing import temporal

    asked: dict[str, list[tuple[str, date]]] = {"ek2b": [], "ek2c": []}

    def ek2b(code: str, day: date) -> float:
        asked["ek2b"].append((code, day))
        return 1.0

    def ek2c(code: str, day: date) -> float:
        asked["ek2c"].append((code, day))
        return 2.0

    monkeypatch.setattr(temporal, "get_ek2b_price_for_date", ek2b)
    monkeypatch.setattr(temporal, "get_ek2c_price_for_date", ek2c)
    found = Data(dict(twins), anadata).problems(context, only="price.procedure_in_force")
    lines = twins[TABLE_PROCEDURES]
    # no line is billed at 1.00 or 2.00: the prices that count are the engine's, whatever they are
    assert len(found) == lines.height
    packages = lines.filter(pl.col("procedure_code").str.starts_with("P")).height
    assert sum("the price in force is 2.00" in p.message for p in found) == packages > 0
    assert sum("the price in force is 1.00" in p.message for p in found) == lines.height - packages
    assert all(code.startswith("P") for code, _ in asked["ek2c"])
    assert not any(code.startswith("P") for code, _ in asked["ek2b"])
    pairs = asked["ek2b"] + asked["ek2c"]
    assert len(pairs) == len(set(pairs))  # once for each pair, not once for each line
    assert len(pairs) == lines.select("procedure_code", "procedure_date").unique().height
    assert all(isinstance(day, date) for _, day in pairs)


def test_the_price_of_a_list_is_the_price_of_the_day_it_is_in_force(
    twins, anadata, context
) -> None:
    """The CT angiography R101450 cost 1034.74 until 2025-12-31 and 1138.22 from 2026-01-01."""
    history = pl.read_parquet(
        _REPO / "data/gazette/curated/ek2b_catalog_history.parquet",
        columns=["code", "valid_from", "valid_to", "price_try"],
    ).filter(pl.col("code") == "R101450")

    def price_on(day: str) -> list[float]:
        in_force = (pl.col("valid_from") <= day) & (
            pl.col("valid_to").is_null() | (pl.col("valid_to") >= day)
        )
        return history.filter(in_force)["price_try"].unique().to_list()

    assert price_on("2025-12-31") == [1034.74]
    assert price_on("2026-01-01") == [1138.22]
    for day, trips in {"2025-12-31": False, "2026-01-01": True}.items():
        data = Data(dict(twins), anadata)
        edit(data, TABLE_PROCEDURES, line(7, "R101450"), procedure_date=day)
        reprice(data, TABLE_PROCEDURES, line(7, "R101450"), 1034.74)
        assert bool(data.problems(context, only="price.procedure_in_force")) is trips, day


@pytest.mark.parametrize(
    ("day", "trips"), [("2025-12-12", True), ("2025-12-13", False), ("2026-09-04", False)]
)
def test_the_ek3f1_list_is_in_force_from_its_yurutluk_date(
    day, trips, twins, anadata, context
) -> None:
    data = Data(dict(twins), anadata)
    edit(data, TABLE_MATERIALS, mat(1), material_date=day)
    assert bool(data.problems(context, only="price.material_in_force")) is trips


def test_the_ek3f1_start_is_the_yurutluk_date_of_the_list() -> None:
    from scripts.synthetic.pathways.checks import EK3F1_FROM as PATHWAY_CHECKS_EK3F1_FROM

    assert EK3F1_FROM.isoformat() == PATHWAY_CHECKS_EK3F1_FROM == "2025-12-13"
    assert (_REPO / "data/gazette/raw/annex=EK-3F-1/effective_date=2025-12-13").is_dir()


def test_the_ek3f1_list_has_one_price_per_code(context) -> None:
    ek3f1 = context.ek3.filter(pl.col("annex") == "EK-3F-1")
    assert ek3f1["sut_code"].n_unique() == ek3f1.height > 300
    assert ek3f1["price_try"].null_count() == 0


def test_the_ek3c2_list_has_one_price_per_code_and_starts_on_its_yururluk_date(context) -> None:
    """Slice G7b: the second EK-3 list the check reads, the raw partition annex=EK-3C-2/effective_date=2026-01-24."""
    from scripts.synthetic.cohort.catalogs import EK3C2_FROM as GENERATOR_EK3C2_FROM
    from scripts.synthetic.pathways.checks import EK3C2_FROM as PATHWAY_CHECKS_EK3C2_FROM

    ek3c2 = context.ek3.filter(pl.col("annex") == "EK-3C-2")
    assert ek3c2["sut_code"].n_unique() == ek3c2.height > 400
    # a row of the list without a price (16 of them) is read as not listed: no material can be billed at its price
    assert ek3c2.filter(pl.col("price_try").is_not_null()).height > 400
    assert ek3c2.filter(pl.col("sut_code") == "OP1106")["price_try"].to_list() == [252.0]
    assert set(ek3c2["list_from"].to_list()) == {EK3C2_FROM} and EK3C2_FROM == date(2026, 1, 24)
    assert EK3C2_FROM.isoformat() == PATHWAY_CHECKS_EK3C2_FROM == GENERATOR_EK3C2_FROM
    assert (_REPO / "data/gazette/raw/annex=EK-3C-2/effective_date=2026-01-24").is_dir()


def test_every_cent_a_list_price_can_be_billed_at_fits_and_no_other_does(context) -> None:
    """The 345 EK-3/F-1 prices: 141 have more than six decimals, 3 sit a float hair below a tie.

    AP1090 is 15076.214999999998 (meant as 15076.215): `Decimal(str(price))` half up bills 15076.21,
    an exact half up 15076.22, and both are the list price to the cent. The module's whole-number
    rule is compared with a Decimal reference on every price and seven neighbouring cents.
    """
    prices = context.ek3.filter(pl.col("annex") == "EK-3F-1")["price_try"].to_list()
    assert 15076.214999999998 in prices
    exact = [Decimal(repr(price)) for price in prices]
    half_up = [d.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP) for d in exact]
    micro = [d.quantize(Decimal("0.000001"), rounding=ROUND_HALF_EVEN) for d in exact]
    frame = pl.DataFrame({"price": prices})
    fits = lambda billed: _is_cent_price_of(pl.col("price"), billed)  # noqa: E731
    # the cent the generator bills (`Decimal(str(price))` half up), Python's round, the float itself
    frame = frame.with_columns(
        pl.Series("generator", [float(d) for d in half_up]),
        pl.Series("python_round", [round(price, 2) for price in prices]),
    )
    got = frame.select(
        fits(pl.col("generator")).alias("generator"),
        fits(pl.col("python_round")).alias("python_round"),
        fits(pl.col("price")).alias("unrounded"),
    )
    assert got["generator"].all() and got["python_round"].all() and got["unrounded"].all()
    for step in range(-3, 4):
        billed = [h + Decimal(step) / 100 for h in half_up]
        reference = [abs(b - m) <= Decimal("0.005") for b, m in zip(billed, micro, strict=True)]
        shown = frame.with_columns(pl.Series("billed", [float(b) for b in billed]))
        module = shown.select(fits(pl.col("billed")).alias("fits"))["fits"].to_list()
        assert module == reference, step
        if abs(step) >= 2:
            assert not any(module), step  # two cents away from the half-up cent: never the price
    # AP1090: the intended tie 15076.215 fits 15076.21 and 15076.22, not their neighbours
    tie = pl.DataFrame(
        {"price": [15076.214999999998] * 4, "billed": [15076.20, 15076.21, 15076.22, 15076.23]}
    )
    got = tie.select(_is_cent_price_of(pl.col("price"), pl.col("billed")))["price"].to_list()
    assert got == [False, True, True, False]


def _raw_ek4a() -> pl.DataFrame:
    """The EK-4A history straight from its curated file, dates parsed here and not by the module."""
    return pl.read_parquet(
        _REPO / "data/gazette/curated/ek4a_history.parquet",
        columns=["barcode", "valid_from", "valid_until"],
    ).with_columns(
        pl.col("valid_from").str.to_date("%Y-%m-%d"), pl.col("valid_until").str.to_date("%Y-%m-%d")
    )


def test_the_ek4a_history_is_the_curated_file_with_its_dates_parsed(context) -> None:
    raw = _raw_ek4a()
    assert context.ek4a.equals(raw)
    assert raw.schema["valid_from"] == raw.schema["valid_until"] == pl.Date
    assert raw["valid_from"].null_count() == 0
    assert raw["valid_until"].null_count() > 0  # the open rows


def test_an_ek4a_row_is_in_force_until_the_day_before_its_valid_until(
    twins, anadata, context
) -> None:
    """valid_until is exclusive: a drug dated on that day is no longer covered by the row."""
    closed = (
        _raw_ek4a()
        .group_by("barcode")
        .agg(
            pl.len().alias("rows"),
            pl.col("valid_until").is_null().any().alias("open"),
            pl.col("valid_from").min().alias("starts"),
            pl.col("valid_until").max().alias("ends"),
        )
        .filter((pl.col("rows") == 1) & ~pl.col("open"))
        .sort("barcode")
    )
    assert closed.height > 0
    only_row = closed.row(0, named=True)
    barcode, starts, ends = only_row["barcode"], only_row["starts"], only_row["ends"]
    one_day = timedelta(days=1)
    for day, trips in {
        starts - one_day: True,
        starts: False,
        ends - one_day: False,
        ends: True,
    }.items():
        data = Data(dict(twins), anadata)
        edit(data, TABLE_DRUGS, drug(6, 1), barkod=barcode, drug_claim_date=day.isoformat())
        assert bool(data.problems(context, only="price.drug_in_force")) is trips, (barcode, day)


def test_a_price_fits_its_nearest_cent_and_a_tie_fits_either_neighbour() -> None:
    frame = pl.DataFrame(
        {
            "price": [
                10.005, 10.005, 10.0049, 10.0049, 5391.8865, 5391.8865, 492.848125, 0.125, 0.125,
                None, 1.0, 0.0049, float("nan"),
            ],
            "billed": [
                10.01, 10.00, 10.00, 10.01, 5391.89, 5391.88, 492.85, 0.13, 0.12,
                1.0, None, 0.0, 1.0,
            ],
        }
    )  # fmt: skip
    got = frame.select(_is_cent_price_of(pl.col("price"), pl.col("billed")))["price"].to_list()
    # in order: a tie fits both neighbours (x2), the nearest cent fits and a cent away does not
    # (x2 each), the long list price, two ties at 0.125, no number (x3), a hair under half a cent
    assert got == [
        True, True, True, False, True, False, True, True, True, None, None, True, None,
    ]  # fmt: skip
    cents = pl.DataFrame({"x": [12.3, 0.1 + 0.2, None, float("nan"), float("inf"), -0.05]})
    assert cents.select(_cents(pl.col("x")))["x"].to_list() == [1230, 30, None, None, None, -5]
    texts = pl.DataFrame({"x": ["12.30", "abc", None]})
    assert texts.select(_cents(pl.col("x")))["x"].to_list() == [1230, None, None]
    shown = pl.DataFrame({"c": [539189, 5, 0, -5, None]}).select(_tl(pl.col("c")).alias("c"))
    assert shown["c"].to_list() == ["5391.89", "0.05", "0.00", "-0.05", None]


def test_the_ladder_is_the_full_price_a_half_and_a_quarter(twins) -> None:
    assert LADDER_QUARTERS == (4, 2, 1)
    s8 = twins[TABLE_PROCEDURES].filter(of(8))
    ratio = (s8["billed_amount_try"] / (s8["unit_price_try"] * s8["quantity"])).round(4).to_list()
    assert sorted(ratio) == [0.25, 1.0]  # the clean S8 twin bills its second package at a quarter
    s9 = twins[TABLE_PROCEDURES].filter(of(9))
    ratio = (s9["billed_amount_try"] / (s9["unit_price_try"] * s9["quantity"])).round(4).to_list()
    assert sorted(set(ratio)) == [0.5, 1.0]  # the clean S9 twin bills its second operation at a half
    assert ratio.count(0.5) == 1


@pytest.mark.parametrize(
    ("quantity", "billed", "fits"),
    [
        (1, 16.46, True),  # the full price
        (1, 8.23, True),  # a half
        (1, 4.12, True),  # a quarter, 4.115 rounded up ...
        (1, 4.11, True),  # ... or down: a tie of half a cent is accepted either way
        (1, 4.10, False),
        (1, 4.94, False),  # a ratio of 0.3
        (1, 0.0, False),
        (2, 32.92, True),
        (2, 16.46, True),  # a half of two units: the ladder cannot tell it from one unit billed
        (3, 16.46, False),
    ],
)
def test_a_line_bills_the_full_price_or_a_rung_of_the_ladder(
    quantity, billed, fits, twins, anadata, context
) -> None:
    data = Data(dict(twins), anadata)
    where = line(4, "L101850", "2026-05-13")
    edit(
        data,
        TABLE_PROCEDURES,
        where,
        quantity=quantity,
        billed_amount_try=billed,
        expected_payable_try=billed,
    )
    assert (data.problems(context, only="money.line_arithmetic") == []) is fits


# S42's two red-cell units on the removal package of patient 5 (slice G14): the clean twin bills them at 36 % of 4462.64
S42_PACKAGE_BLOOD = (pl.col("claim_id") == claim_id(PATIENT[5], 3)) & (pl.col("procedure_code") == "705371")


@pytest.mark.parametrize(
    ("billed", "fits"),
    [
        (1606.55, True),  # 36 % of 4462.64 = 1606.5504: the share, to the cent
        (1606.56, False),  # more than half a cent off the share
        (4462.64, True),  # the full price stays on the ladder: billing it in full is S42's fault, the engine's to find
        (2231.32, True),  # a half (the ladder)
        (1071.04, False),  # 24 %, the share of another component
    ],
)
def test_a_blood_component_on_a_package_claim_bills_its_share_or_a_rung_of_the_ladder(
    billed, fits, twins, anadata, context
) -> None:
    data = Data(dict(twins), anadata)
    assert data.tables[TABLE_PROCEDURES].filter(S42_PACKAGE_BLOOD)["billed_amount_try"].to_list() == [1606.55, 1606.55]
    edit(data, TABLE_PROCEDURES, S42_PACKAGE_BLOOD, billed_amount_try=billed, expected_payable_try=billed)
    assert (data.problems(context, only="money.line_arithmetic") == []) is fits


# S50's sphincterotomy on the ERCP package of patient 8 (slice G15): the clean twin bills it at 30 % of 1079.36 (C000672)
S50_BESIDE_THE_PACKAGE = (pl.col("claim_id") == claim_id(PATIENT[8], 3)) & (pl.col("procedure_code") == "701370")


@pytest.mark.parametrize(
    ("billed", "fits"),
    [
        (323.81, True),  # 30 % of 1079.36 = 323.808: the share beside the package, to the cent
        (323.82, False),  # more than half a cent off the share
        (1079.36, True),  # the full price stays on the ladder: billing it in full is S50's fault, the engine's to find
        (539.68, True),  # a half: the separate incision of C000673 (and the ladder)
        (388.57, False),  # 36 %, the share of red cells
    ],
)
def test_a_procedure_line_on_a_package_claim_bills_30_percent_or_a_rung_of_the_ladder(
    billed, fits, twins, anadata, context
) -> None:
    data = Data(dict(twins), anadata)
    assert data.tables[TABLE_PROCEDURES].filter(S50_BESIDE_THE_PACKAGE)["billed_amount_try"].to_list() == [323.81]
    edit(data, TABLE_PROCEDURES, S50_BESIDE_THE_PACKAGE, billed_amount_try=billed, expected_payable_try=billed)
    assert (data.problems(context, only="money.line_arithmetic") == []) is fits


def test_an_er_claim_bills_the_er_or_the_green_area_examination_and_a_clinic_claim_neither(twins, anadata, context) -> None:
    """fit.visit_code: S49's green-area examination 520021 fits its ER claim (SUT 1.8.5.(5), 1.9.3.(a): C000370,
    C000438); filed on a clinic claim it does not."""
    data = Data(dict(twins), anadata)
    green = (pl.col("claim_id") == claim_id(PATIENT[8], 2)) & (pl.col("procedure_category") == "muayene")
    assert data.tables[TABLE_PROCEDURES].filter(green)["procedure_code"].to_list() == ["520021"]
    assert run_only(data, context, VISIT) == []
    edit(data, TABLE_CLAIM_HEADERS, pl.col("claim_id") == claim_id(PATIENT[8], 2), claim_type="poliklinik")
    (problem,) = run_only(data, context, VISIT)
    assert problem.message == "examination 520021 on a claim of type poliklinik; 520030 is the examination of that type"


def test_only_a_procedure_line_on_a_package_claim_may_bill_30_percent(twins, anadata, context) -> None:
    """The 30 % beside a package is for an EK-2B procedure (category `islem`): the same line filed as a lab test, or the
    package line itself at 30 %, is off the ladder (the 30 % of an itemized bill is `ratio_of_0_3`)."""
    data = Data(dict(twins), anadata)
    edit(data, TABLE_PROCEDURES, S50_BESIDE_THE_PACKAGE, procedure_category="laboratuvar")
    (problem,) = data.problems(context, only="money.line_arithmetic")
    assert problem.where.startswith(f"{claim_id(PATIENT[8], 3)} procedure_claim_lines[")
    assert "billed 323.81 is not the unit price 1079.36 x quantity 1 x 1, 0.5 or 0.25" in problem.message
    data = Data(dict(twins), anadata)
    package = (pl.col("claim_id") == claim_id(PATIENT[8], 3)) & (pl.col("procedure_code") == "P701360")
    edit(data, TABLE_PROCEDURES, package, billed_amount_try=2933.88, expected_payable_try=2933.88)  # 30 % of 9779.61
    assert [p.claim_id for p in data.problems(context, only="money.line_arithmetic")] == [claim_id(PATIENT[8], 3)]
    # a procedure line of an itemized claim: S9's second operation at 30 % is not on the ladder (no committed itemized
    # bill uses the same-incision 30 % of C000660; the 30 % rung is a package claim's)
    data = Data(dict(twins), anadata)
    second = (pl.col("claim_id") == claim_id(PATIENT[9], 1)) & (pl.col("procedure_code") == "615995")
    edit(data, TABLE_PROCEDURES, second, billed_amount_try=909.60, expected_payable_try=909.60)  # 30 % of 3032.00
    (problem,) = data.problems(context, only="money.line_arithmetic")
    assert problem.claim_id == claim_id(PATIENT[9], 1) and "billed 909.60 is not the unit price 3032.00" in problem.message


def test_the_one_line_with_a_patient_share_pays_billed_less_it_and_the_header_follows(built, anadata, context) -> None:
    """S32's examination (slice G5b) is the only line whose payable is not its billed amount, and the money checks
    pass on it: 85.73 billed, 20 %, 68.58 payable; the header's payable total is the sum of the lines'."""
    procedures = built.tables[TABLE_PROCEDURES]
    shared = procedures.filter(pl.col("copay_rate_applicable"))
    assert shared.select("claim_id", "procedure_code", "billed_amount_try", "expected_payable_try", "copay_rate").rows() == [
        (S2_CONTROL, "520030", 85.73, 68.58, 0.2)
    ]
    assert procedures.filter(~pl.col("copay_rate_applicable"))["copay_rate"].null_count() == procedures.height - 1
    priced = pl.concat(
        [built.tables[t].select("billed_amount_try", "expected_payable_try") for t in (TABLE_PROCEDURES, TABLE_MATERIALS, TABLE_DRUGS)]
    )
    assert priced.filter(pl.col("billed_amount_try") != pl.col("expected_payable_try")).height == 1
    header = built.tables[TABLE_CLAIM_HEADERS].filter(pl.col("claim_id") == S2_CONTROL)
    assert header.select("expected_total_billed_try", "expected_total_payable_try").row(0) == (85.73, 68.58)
    data = Data(dict(built.tables), anadata)
    assert data.problems(context, only=["money.line_arithmetic", "money.payable_equals_billed", "money.totals"]) == []


@pytest.mark.parametrize(
    ("billed", "rate", "payable", "fits"),
    [
        (85.73, 0.20, 68.58, True),  # 68.584
        (85.73, 0.20, 68.59, False),
        (12.35, 0.10, 11.12, True),  # 11.115: half up, in whole cents (a float would give 11.114999...)
        (12.35, 0.10, 11.11, False),
        (0.05, 0.50, 0.03, True),  # 0.025: half up
        (0.05, 0.50, 0.02, False),
        (100.00, 0.99, 1.00, True),
    ],
)
def test_a_line_with_a_patient_share_pays_billed_less_the_share_half_up_to_the_cent(
    billed, rate, payable, fits, twins, anadata, context
) -> None:
    data = Data(dict(twins), anadata)
    edit(data, TABLE_PROCEDURES, _s2_control_exam(), billed_amount_try=billed, copay_rate=rate, expected_payable_try=payable)
    assert (data.problems(context, only="money.payable_equals_billed") == []) is fits
    # the composer's arithmetic is the same: Decimal, half up
    expected = (Decimal(str(billed)) * (1 - Decimal(str(rate)))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    assert (expected == Decimal(str(payable)).quantize(Decimal("0.01"))) is fits


def test_money_agrees_to_the_cent_not_to_the_float(twins, anadata, context) -> None:
    data = Data(dict(twins), anadata)
    where = line(4, "L101850", "2026-05-13")
    edit(data, TABLE_PROCEDURES, where, billed_amount_try=16.464, expected_payable_try=16.456)
    edit(
        data,
        TABLE_CLAIM_HEADERS,
        of(3),
        expected_total_billed_try=pl.col("expected_total_billed_try") + 0.004,
        expected_total_payable_try=pl.col("expected_total_payable_try") - 0.004,
    )
    money = ["money.line_arithmetic", "money.payable_equals_billed", "money.totals"]
    assert data.problems(context, only=money) == []


def test_a_missing_value_never_crashes_a_slice_e2_check_and_is_named(
    twins, anadata, context
) -> None:
    data = Data(dict(twins), anadata)
    edit(
        data,
        TABLE_MATERIALS,
        mat(1),
        material_code=None,
        material_date=None,
        procedure_line_id=None,
        quantity=None,
        unit_price_try=None,
        billed_amount_try=None,
        expected_payable_try=None,
    )
    edit(
        data,
        TABLE_PROCEDURES,
        line(4, "L101850", "2026-05-13"),
        procedure_code=None,
        procedure_date=None,
        quantity=None,
        unit_price_try=None,
        billed_amount_try=None,
        expected_payable_try=None,
    )
    edit(
        data,
        TABLE_DRUGS,
        drug(6, 1),
        drug_name=None,
        barkod=None,
        drug_claim_date=None,
        quantity=None,
        unit_price_try=None,
        billed_amount_try=None,
        expected_payable_try=None,
    )
    found = data.problems(context, only=sorted(E2_CHECKS - REGISTRY_CHECKS))
    assert {p.check for p in found} >= {
        "material.operation_link",
        "price.material_in_force",
        "money.line_arithmetic",
        "money.payable_equals_billed",
    }
    assert all(p.where and p.message and "None" not in p.message for p in found), [
        str(p) for p in found
    ]
    assert "(none)" in " ".join(p.message for p in found)


def test_a_check_that_reads_the_money_does_not_need_the_generators_catalogs(twins, anadata) -> None:
    """The price, money and flag checks run on a context that refuses to open any catalog."""

    class NoCatalogs(PlausibilityContext):
        @property
        def catalogs(self):  # type: ignore[override]
            raise AssertionError("a price or money check reached for the catalogs")

    ids = [
        "material.stray_flag",
        "price.procedure_in_force",
        "price.material_in_force",
        "price.drug_in_force",
        "money.line_arithmetic",
        "money.payable_equals_billed",
        "money.totals",
    ]
    found = check_plausibility(
        twins, {TABLE_ANADATA: anadata}, context=NoCatalogs(), only=ids, registry={"faults": []}
    )
    assert found == []


# --- 4c. the labels: edge cases of the registry and of the answer table ---------------------------


def _answer_rows_of(data: Data, context: PlausibilityContext) -> list[Problem]:
    return data.problems(context, only=ANSWER_ROWS)


def test_an_entry_that_is_no_valid_record_is_reported_with_its_reason_not_raised(
    built, anadata, context
) -> None:
    data = faulty_data(built, anadata)
    edit_fault(data, 3, relabel=False, amount_try="928.09")
    row_problem, entry_problem = _answer_rows_of(data, context)  # sorted by where: rows, registry
    assert entry_problem.where == f"{CLAIM[3]} registry faults[4]"  # after S1, S2 and the two faulty later bills of S2's patient
    assert entry_problem.message == (
        "the entry is no valid fault record: revenue_uplift amount_try '928.09' must equal "
        "billed_clean_try - billed_faulty_try (928.08)"
    )
    assert row_problem.message == (
        "the claim's fault entry is no valid record, so nothing explains this answer row"
    )


def test_a_registry_without_a_list_of_faults_is_one_finding_and_leaves_every_row_unexplained(
    built, anadata, context
) -> None:
    data = Data(dict(built.tables), anadata, {"schema_version": 1})
    found = _answer_rows_of(data, context)
    assert [p.where for p in found][0] == "(registry)"
    assert found[0].message == "the registry has no list of faults"
    assert len(found) == 1 + len(cohort.load_registry()["faults"])  # one row per answer row; a clean bill (S39) has none
    assert data.problems(context, only=AMOUNTS) == []  # nothing to compare


def test_a_fault_entry_that_is_not_even_a_mapping_or_has_no_claim_is_reported(
    built, anadata, context
) -> None:
    data = faulty_data(built, anadata)
    first = len(data.registry["faults"])  # the index of the first appended entry
    data.registry["faults"].append("not a record")
    data.registry["faults"].append({"fault_id": "F_X", "billed_faulty_try": None})
    found = data.problems(context, only=sorted(REGISTRY_CHECKS))
    wheres = [p.where for p in found]
    assert f"(no-claim-id) registry faults[{first}]" in wheres
    assert f"(no-claim-id) registry faults[{first + 1}]" in wheres
    assert all(p.message and "None" not in p.message for p in found)
    # the last entry is a mapping without values: labels.amounts names each missing value
    assert any(p.check == AMOUNTS and "(none)" in p.message for p in found)


def test_two_records_for_one_claim_and_fault_produce_no_answer_key(built, anadata, context) -> None:
    data = faulty_data(built, anadata)
    data.registry["faults"].append(copy.deepcopy(fault_of(data, 2)))
    (problem,) = _answer_rows_of(data, context)
    assert problem.where == "(registry)"
    assert problem.message.startswith("the fault records produce no answer key: duplicate")


def test_the_answer_table_has_the_columns_of_the_answer_key_in_their_order(
    built, anadata, context
) -> None:
    data = faulty_data(built, anadata)
    reordered = data.tables[TABLE_ANSWERS].select(
        data.tables[TABLE_ANSWERS].columns[1], data.tables[TABLE_ANSWERS].columns[0],
        *data.tables[TABLE_ANSWERS].columns[2:],
    )  # fmt: skip
    data.tables[TABLE_ANSWERS] = reordered
    (problem,) = _answer_rows_of(data, context)
    assert problem.where == "(expected_rule_outputs)"
    assert problem.message.startswith("the columns are ['scenario_tag', 'expected_output_id'")
    # a column that is gone cannot be compared: one finding, no noise from the rows
    data.tables[TABLE_ANSWERS] = reordered.drop("assertion_notes")
    (problem,) = _answer_rows_of(data, context)
    assert problem.where == "(expected_rule_outputs)"


def test_answer_money_is_compared_in_cents(built, anadata, context) -> None:
    data = faulty_data(built, anadata)
    edit(data, TABLE_ANSWERS, of(1), expected_savings_try=pl.col("expected_savings_try") + 0.004)
    assert _answer_rows_of(data, context) == []
    edit(data, TABLE_ANSWERS, of(1), expected_savings_try=pl.col("expected_savings_try") + 0.01)
    (problem,) = _answer_rows_of(data, context)
    assert "expected_savings_try is 4122.13" in problem.message
    assert "the fault record gives 4122.12" in problem.message


def test_every_answer_row_names_the_fault_of_its_record_and_none_is_payable(built) -> None:
    answers = built.tables[TABLE_ANSWERS]
    assert answers["expected_payable_try"].null_count() == answers.height == len(built.registry["faults"])
    assert [e["claim_id"] for e in built.registry["faults"]] == answers["claim_id"].to_list()


# --- 5. the judgment tables --------------------------------------------------------------------------


BRIEF_ICD_BLOCKS = {
    "M": {"C60-C63", "D07.4-D07.6", "N40-N53", "E29", "Q53-Q56", "I86.1"},
    "F": {"C51-C58", "D06", "D07.0-D07.3", "N70-N98", "E28", "Q50-Q52", "Z32-Z37", "Z39"},
}


def test_the_icd_sex_blocks_hold_the_blocks_of_the_brief() -> None:
    assert set(ICD_SEX_GATES) == {"M", "F"}
    for sex, blocks in BRIEF_ICD_BLOCKS.items():
        assert blocks <= set(ICD_SEX_GATES[sex]), sex


def test_every_icd_sex_block_holds_a_leaf_code_of_icd10_tr(context) -> None:
    leaves = context.icd.filter(pl.col("is_leaf"))
    assert leaves.height > 13000
    for sex, blocks in ICD_SEX_GATES.items():
        for block in blocks:
            held = leaves.filter(_in_blocks(pl.col("code"), [block]))
            assert held.height > 0, f"no leaf code of icd10_tr is in the block {block} ({sex})"


def test_the_icd_sex_blocks_agree_with_the_sex_column_and_add_to_it(context) -> None:
    icd = context.icd
    male = icd.filter(_in_blocks(pl.col("code"), ICD_SEX_GATES["M"]))
    female = icd.filter(_in_blocks(pl.col("code"), ICD_SEX_GATES["F"]))
    assert male.join(female, on="code").height == 0  # no code is in a block of each sex
    # where a block and the column both gate a code, they gate it for the same sex
    assert set(male["sex"].drop_nulls()) <= {"M"}
    assert set(female["sex"].drop_nulls()) <= {"F"}
    leaf_column = icd.filter(pl.col("is_leaf") & pl.col("sex").is_not_null())
    assert leaf_column.height == 83  # the column gates 83 leaf codes, all in chapters C and D
    only_by_a_block = pl.concat([male, female]).filter(pl.col("is_leaf") & pl.col("sex").is_null())
    assert only_by_a_block.height > 300  # the blocks gate more than three times as many again
    # the column gates codes that no block holds (the benign neoplasms D25-D29, D39, D40)
    in_a_block = _in_blocks(pl.col("code"), [*ICD_SEX_GATES["M"], *ICD_SEX_GATES["F"]])
    assert icd.filter(pl.col("sex").is_not_null() & ~in_a_block).height > 0


def test_the_one_diagnosis_of_the_bills_in_a_sex_block_is_the_cervical_cancer_of_a_woman(built, twins, anadata) -> None:
    """S21's C53.9 (C51-C58, the female genital organs) is the cohort's one diagnosis in a sex block: on a woman."""
    (s21,) = cohort.scenario("S21").claim_ids
    for tables in (twins, built.tables):
        for sex, blocks in ICD_SEX_GATES.items():
            held = tables[TABLE_DIAGNOSES].filter(_in_blocks(pl.col("icd10_code"), blocks))
            assert list(zip(held["claim_id"], held["icd10_code"], strict=True)) == (
                [(s21, "C53.9")] if sex == "F" else []
            )
    episode = anadata.filter(pl.col("SQ_EPISODE") == s21.replace("F-", "B-", 1))
    assert episode["CINSIYET"].to_list() == ["K"]


# The blocks of the brief written the other way: one prefix for each category (or subcategory), with
# no range to read. The sex gate is compared with it on every code of icd10_tr.
ORACLE_ICD_PREFIXES = {
    "M": [
        *(f"C{n}" for n in range(60, 64)),
        "D07.4", "D07.5", "D07.6",
        *(f"N{n}" for n in range(40, 54)),
        "E29",
        *(f"Q{n}" for n in range(53, 57)),
        "I86.1",
    ],
    "F": [
        *(f"C{n}" for n in range(51, 59)),
        "D06", "D07.0", "D07.1", "D07.2", "D07.3",
        *(f"N{n}" for n in range(70, 99)),
        "E28",
        *(f"Q{n}" for n in range(50, 53)),
        *(f"Z{n}" for n in range(32, 38)),
        "Z39",
    ],
}  # fmt: skip


@pytest.mark.parametrize(("story", "patient_sex", "other"), [(1, "M", "F"), (3, "F", "M")])
def test_the_sex_gate_flags_every_code_of_icd10_tr_that_the_prefixes_and_the_column_gate(
    story, patient_sex, other, twins, anadata, context
) -> None:
    """Every code of the table on a patient of one sex: the flagged codes are the oracle's, no more."""
    icd = context.icd.select("code", "sex")
    prefix_sex = pl.coalesce(
        *[
            pl.when(pl.any_horizontal([pl.col("code").str.starts_with(p) for p in prefixes])).then(
                pl.lit(sex)
            )
            for sex, prefixes in ORACLE_ICD_PREFIXES.items()
        ]
    )
    oracle = icd.with_columns(pl.coalesce(pl.col("sex"), prefix_sex).alias("gate"))
    expected = set(oracle.filter(pl.col("gate") == other)["code"])
    assert len(expected) > 100  # the prefixes and the column gate a good part of the table

    data = Data(dict(twins), anadata)
    template = data.tables[TABLE_DIAGNOSES].filter(of(story)).head(1).drop("icd10_code")
    every_code = template.join(icd.select(pl.col("code").alias("icd10_code")), how="cross")
    data.tables[TABLE_DIAGNOSES] = pl.concat(
        [
            data.tables[TABLE_DIAGNOSES].filter(~of(story)),
            every_code.select(data.tables[TABLE_DIAGNOSES].columns),
        ]
    )
    found = data.problems(context, only=SEX)
    flagged = {re.match(r"diagnosis (\S+) is limited to sex", p.message)[1] for p in found}
    assert flagged == expected
    assert len(found) == len(flagged)  # one finding for each code
    assert {p.message.rsplit(" ", 1)[-1] for p in found} == {patient_sex}


def test_the_surgical_branches_exist_in_ek2a_under_their_names(context) -> None:
    names = {
        "1900": "Genel Cerrahi",
        "1901": "El Cerrahisi (Genel Cerrahi)",
        "1910": "Cerrahi Onkoloji",
        "1975": "Gastroenteroloji Cerrahisi",
        "2000": "Çocuk Cerrahisi",
        "2200": "Göğüs Cerrahisi",
        "2300": "Kalp ve Damar Cerrahisi",
        "2387": "Çocuk Kalp ve Damar Cerrahisi",
        "2400": "Beyin ve Sinir Cerrahisi",
        "2500": "Plastik, Rekonstrüktif ve Estetik Cerrahi",
        "2579": "El Cerrahisi (Plastik, Rekonstrüktif ve Estetik Cerrahi)",
        "2600": "Ortopedi ve Travmatoloji",
        "2679": "El Cerrahisi (Ortopedi ve Travmatoloji)",
        "2700": "Üroloji",
        "2781": "Çocuk Ürolojisi",
        "2800": "Kulak Burun Boğaz Hastalıkları",
        "2900": "Göz Hastalıkları",
        "3000": "Kadın Hastalıkları ve Doğum",
        "3010": "Jinekolojik Onkoloji Cerrahisi",
        "5100": "Ağız, Diş ve Çene Cerrahisi",
        "5350": "Ağız, Yüz ve Çene Cerrahisi",
    }
    assert set(names) == set(SURGICAL_SPECIALTY_CODES)
    ek2a = pl.read_parquet(
        _REPO / "data/gazette/curated/ek2a_outpatient_visits.parquet",
        columns=["specialty_code", "specialty_name"],
    )
    on_file = dict(zip(ek2a["specialty_code"], ek2a["specialty_name"], strict=True))
    assert {code: on_file.get(code) for code in names} == names
    assert set(names) <= context.specialties
    # the clinics of the stories that are not surgical stay out
    assert not {"1000", "1171", "3100", "3300", "4400"} & set(SURGICAL_SPECIALTY_CODES)


# The words and gates of the brief of slice E1, and the ones the independent review of the catalog
# added: the lists hold them all, and may hold more.
BRIEF_MALE_WORDS = {
    "prostat", "penil", "penis", "penektomi", "testis", "orşiektomi", "orsiektomi", "skrotum",
    "hidrosel", "varikosel", "vazektomi", "sünnet", "sunnet", "epididim",
}  # fmt: skip
BRIEF_FEMALE_WORDS = {
    "uterus", "rahim", "histerektomi", "histeroskopi", "vajin", "vulva", "serviks", "ooferektomi",
    "salpenjektomi", "jinekolojik", "gebelik", "doğum", "sezaryen", "inseminasyon", "kürtaj",
}  # fmt: skip
REVIEW_MALE_WORDS = {
    "orşiyektomi", "orşiyopeksi", "fimoz", "hipospad", "epispad", "peyronie", "testik", "seminal",
    "sperm", "vazovazo", "ejakül",
}  # fmt: skip
REVIEW_FEMALE_WORDS = {
    "histerosalping", "kolposkop", "bartholin", "obstetrik", "amniyo", "abortus", "endometri",
    "miyom", "myom", "plasenta", "tüp ligasyonu",
}  # fmt: skip
BRIEF_AGE_GATES = [
    ("icd", ("P",), None, 1, None),
    ("icd", ("O",), 10, 55, "F"),
    ("icd", ("Z38",), None, 1, None),
    ("name", ("yenidoğan", "neonatal", "prematüre"), None, 1, None),
    ("name", ("pediatrik", "çocuk"), None, 17, None),
    ("name", ("erişkin",), 18, None, None),
]


def test_the_age_gates_hold_the_brief_and_the_review_gates() -> None:
    for source, words, low, high, sex in BRIEF_AGE_GATES:
        assert any(
            (g.source, g.min_age, g.max_age, g.sex) == (source, low, high, sex)
            and set(words) <= set(g.words)
            for g in AGE_GATES
        ), words
    newborn = next(g for g in AGE_GATES if "yenidoğan" in g.words)
    assert {"yeni doğan", "bebek"} <= set(newborn.words)
    assert newborn.max_age == 1 and not newborn.whole
    under = {g.words: (g.max_age, g.whole) for g in AGE_GATES if g.words[0].endswith("yaş altı")}
    assert under == {("2 yaş altı",): (1, True), ("10 yaş altı",): (9, True)}
    assert [g.limits for g in AGE_GATES][:2] == ["age at most 1", "sex F, age 10..55"]
    assert all(g.source in {"icd", "name"} for g in AGE_GATES)


def test_the_sex_word_lists_hold_the_brief_and_the_review_words() -> None:
    assert BRIEF_MALE_WORDS | REVIEW_MALE_WORDS <= set(MALE_ONLY_WORDS)
    assert BRIEF_FEMALE_WORDS | REVIEW_FEMALE_WORDS <= set(FEMALE_ONLY_WORDS)
    assert FEMALE_ONLY_WHOLE_WORDS == ("over",)
    # no word is on both sides, and none is a bare stem that sits inside another word (orşi: torsiyon)
    male = {fold_text(w) for w in MALE_ONLY_WORDS}
    female = {fold_text(w) for w in (*FEMALE_ONLY_WORDS, *FEMALE_ONLY_WHOLE_WORDS)}
    assert not male & female
    assert "orsi" not in male and "orsiyektomi" in male


@pytest.mark.parametrize(
    ("name", "story", "trips"),
    [
        # a female patient is story 3, a male one story 1
        ("Over detorsiyonu", 1, True),
        ("OVER (+ /- TUBA), NEOPLASTİK DEĞİL", 1, True),
        ("Overdoz tedavisi", 1, False),  # "over" is a whole word only
        ("Venöz sisteme cross-over ven grefti", 1, False),
        ("Vajinal doğum", 1, True),
        ("Doğumsal kalp hastalığında tanısal kalp kateterizasyonu", 1, False),
        ("İnvajinasyonda manüel redüksiyon (laparoskopik)", 1, False),
        ("Vezikovajinal fistül onarımı", 1, True),
        ("Prostat iğne biyopsisi", 3, True),
        ("PROSTAT SPESİFİK ANTİJEN", 3, True),
        ("Penil arter basınç ölçümü (PBI)", 3, True),
        ("Penisilin G IgE antikoru", 3, False),
        ("Penis rezeksiyonu parsiyel", 3, True),
        ("Ailesel Meme/Over Kanseri (BRCA1 ve BRCA2 Geni Dizi Analizi)", 1, False),
        ("Sünnet", 3, True),
        ("Orşiektomi", 3, True),
        ("Appendektomi, laparoskopik", 3, False),
        # the names of the catalog that the review found uncaught, and the traps next to them
        ("Skrotal orşiyektomi, tek taraf", 3, True),
        ("Laparoskopik orşiyopeksi", 3, True),
        ("Apendiks epiploika torsiyonu", 3, False),  # orşi- alone would sit inside torsiyon
        ("Kolonda detorsiyon ve peksi operasyonları", 3, False),
        ("Meme rekonstrüksiyonu,Latissimus dorsi kas deri flebi ve implant ile", 3, False),
        ("Fimozis açılması", 3, True),
        ("Parafimozis redüksiyonu", 3, True),
        ("Hipospadias onarımı, perineal", 3, True),
        ("Epispadias onarımı", 3, True),
        ("Üretroplastiler, hipospadias-epispadias dışı", 3, False),  # in either sex
        ("Peyronie plak eksizyonu, greft ile", 3, True),
        ("Testiküler fiksasyon, tek taraf", 3, True),
        ("Testiküler sperm ekstraksiyonu (TESE)", 3, True),
        ("Seminal vezikülektomi", 3, True),
        ("Spermiogram (tam otomatize)", 3, True),
        ("Sperm mar testi", 3, True),
        ("Antisperm antibody (ASA)", 3, False),  # also done on a woman's serum
        ("Sperm yıkama", 3, False),  # IUI and IVF steps are billed on either partner's file
        ("Sperm- oosit hazırlanması ve inkübasyonu", 3, False),
        ("Özel sperm tektiki", 3, False),
        ("Vazovazostomi", 3, True),
        ("Ejakülatör kanal rezeksiyonu", 3, True),
        ("Histerosalpingografi (HSG)", 1, True),
        ("Kolposkopi", 1, True),
        ("Bartholin kisti çıkarılması", 1, True),
        ("Obstetrik renkli Doppler US", 1, True),
        ("Amniyosentez", 1, True),
        ("Alfa-Fetoprotein (AFP) (Amniyotik sıvı)", 1, True),
        ("Abortus", 1, True),
        ("Endometriyal biyopsi", 1, True),
        ("Polip, servikal/endometrial", 1, True),
        ("Mikrocerrahi ile miyomektomi, her biri", 1, True),
        ("Myomektomi", 1, True),
        ("Plasenta", 1, True),
        ("Postpartum tüp ligasyonu", 1, True),
        ("Tüp ligasyonu", 1, True),
        ("Hepatik recover testi", 1, False),
    ],
)
def test_sex_words_in_names(name, story, trips, twins, anadata, context) -> None:
    data = Data(dict(twins), anadata)
    code = "P610131" if story == 1 else "L104780"
    rename(data, story, code, name)
    assert bool(run_only(data, context, "patient.sex_gate")) is trips, name


@pytest.mark.parametrize(
    ("name", "trips"),
    [
        ("Yenidoğan monitörizasyonu", True),
        ("YENİDOĞAN OTOAKUSTİK EMİSYONU", True),
        ("Prematüre retinopatisinde lazer tedavisi", True),
        ("Neonatal TSH (Kuru kan)", True),
        ("Çocuk odyometresi (Komple)", True),
        ("Pediatrik eritrosit süspansiyonu", True),
        ("Yenidoğan/Çocuk TPN hazırlama ve uygulaması", False),
        ("Yenidoğan/Çocuk/ErişkinTedavisel soğutma (Terapötik hipotermi)", False),
        ("Rutin EEG (Çocuk-büyük)", False),
        ("Sağlam çocuk doğmasına yönelik invitro fertilizasyon (IVF)", False),
        ("Tam Kan Sayımı (Hemogram)", False),
        # the names of the catalog that the review found uncaught, and the traps next to them
        ("Yeni doğan fundoskopik inceleme", True),
        ("Bebek fadiatop IgE antikoru", True),
        ("Gonyoskopi ve kornea çapı ölçümü, bebek için", True),
        ("Pelvipedal alçı (10 yaş altı)", True),
        ("2 yaş altı doğumsal kalp hastalıklarında tanısal kalp kateterizasyonu", True),
        ("Pelvipedal alçı (10 yaş üstü )", False),  # a limit from below, not a child gate
        ("Elektrokardiyogram, < 4 yaş çocuk", True),
        ("Yeni doğan/geriatrik (75 yaş üstü ve ASA 3-4) anestezi puanı A1 grubu", False),
        ("Geriatrik rehabilitasyon", False),
        ("Çok Disiplinli Çocuk ve Genç Ruh Sağlığı Merkezleri (ÇÖZGEM) hizmetleri", False),
        ("Çocuklarda görme muayeneleri", True),
    ],
)
def test_age_words_in_names_on_an_adult(name, trips, twins, anadata, context) -> None:
    data = Data(dict(twins), anadata)
    rename(data, 2, "L101850", name)  # S2 is 81
    assert bool(run_only(data, context, "patient.age_gate")) is trips, name


def test_the_name_exceptions_occur_in_the_catalogs(context) -> None:
    catalogs = context.catalogs
    names = pl.concat([catalogs.ek2b.select("name"), catalogs.ek2c.select("name")]).unique()
    folded = [fold_text(n) for n in names["name"].to_list()]
    for phrase in NAME_EXCEPTIONS:
        assert any(fold_text(phrase) in name for name in folded), phrase


# Four words match no EK-2B or EK-2C name today: the catalog spells orşiyektomi, and no name has rahim
# or salpenjektomi. They stay in the lists as a defence for a name outside the catalog. The adult
# gate (erişkin) matches none either. This set is exact: a word that comes alive, or dies, fails.
DEAD_WORDS = frozenset({"orşiektomi", "orsiektomi", "rahim", "salpenjektomi", "erişkin"})


def _catalog_names(context: PlausibilityContext) -> pl.DataFrame:
    """The distinct names of EK-2B and EK-2C (history included), as the checks fold them."""
    catalogs = context.catalogs
    names = pl.concat([catalogs.ek2b.select("name"), catalogs.ek2c.select("name")]).unique()
    return names.with_columns(_fold(pl.col("name")).alias("folded"))


def _word_patterns() -> dict[str, str]:
    """word -> regex, for every sex word and every age name word of the module."""
    patterns = {word: _words_pattern([word]) for word in (*MALE_ONLY_WORDS, *FEMALE_ONLY_WORDS)}
    patterns.update({w: _words_pattern([w], whole=True) for w in FEMALE_ONLY_WHOLE_WORDS})
    for gate in AGE_GATES:
        if gate.source == "name":
            patterns.update({w: _words_pattern([w], whole=gate.whole) for w in gate.words})
    return patterns


def _any_of(words: list[str]) -> str:
    patterns = _word_patterns()
    return "|".join(patterns[word] for word in words)


def test_every_word_matches_a_catalog_name_but_the_documented_dead_ones(context) -> None:
    names = _catalog_names(context).with_columns(
        _without_exceptions(pl.col("folded")).alias("blanked")
    )
    assert names.height > 7000
    dead = {
        word
        for word, pattern in _word_patterns().items()
        if names.filter(pl.col("blanked").str.contains(pattern)).height == 0
    }
    assert dead == DEAD_WORDS


def test_every_name_exception_changes_the_verdict_of_a_catalog_name(context) -> None:
    """Each phrase blanks a sex or age word out of a name that would trip without it."""
    names = _catalog_names(context)
    everything = "|".join(_word_patterns().values())
    with_all = names.with_columns(
        _without_exceptions(pl.col("folded")).str.contains(everything).alias("trips")
    )
    assert with_all["trips"].sum() > 200  # the words do mark the catalog
    for phrase in NAME_EXCEPTIONS:
        others = [other for other in NAME_EXCEPTIONS if other != phrase]
        without_phrase = names.with_columns(
            _without_exceptions(pl.col("folded"), others).str.contains(everything).alias("trips")
        )
        needed = (without_phrase["trips"] & ~with_all["trips"]).sum()
        assert needed > 0, f"the exception {phrase!r} changes the verdict of no name"


def test_no_catalog_name_trips_two_words_that_contradict(context) -> None:
    names = _catalog_names(context).with_columns(
        _without_exceptions(pl.col("folded")).alias("blanked")
    )
    male = _any_of(list(MALE_ONLY_WORDS))
    female = _any_of([*FEMALE_ONLY_WORDS, *FEMALE_ONLY_WHOLE_WORDS])
    adult_words = [
        w for g in AGE_GATES if g.source == "name" and g.min_age is not None for w in g.words
    ]
    child_words = [
        w for g in AGE_GATES if g.source == "name" and g.max_age is not None for w in g.words
    ]
    adult, child = _any_of(adult_words), _any_of(child_words)
    assert adult_words == ["erişkin"] and "çocuk" in child_words
    has = lambda pattern: pl.col("blanked").str.contains(pattern)  # noqa: E731
    assert names.filter(has(male) & has(female)).height == 0
    assert names.filter(has(adult) & has(child)).height == 0
    assert names.filter(has(adult)).height == 0  # no catalog name has an adult word today


def test_the_catalog_names_that_hold_a_sex_word_are_many_and_the_sexes_are_apart(context) -> None:
    names = _catalog_names(context).with_columns(
        _without_exceptions(pl.col("folded")).alias("blanked")
    )
    male = names.filter(pl.col("blanked").str.contains(_any_of(list(MALE_ONLY_WORDS))))
    female = names.filter(
        pl.col("blanked").str.contains(_any_of([*FEMALE_ONLY_WORDS, *FEMALE_ONLY_WHOLE_WORDS]))
    )
    assert male.height > 100 and female.height > 90
    assert male.join(female, on="name").height == 0


def test_the_age_words_hold_the_catalog_names_the_review_found(context) -> None:
    """The seven age names that the first lists missed, each caught by its own gate."""
    names = _catalog_names(context).with_columns(
        _without_exceptions(pl.col("folded")).alias("blanked")
    )
    expected = {
        "yeni doğan": {"Yeni doğan fundoskopik inceleme"},
        "bebek": {
            "Bebek fadiatop IgE antikoru",
            "Gonyoskopi ve kornea çapı ölçümü, bebek için",
            "Göz içi basıncı ölçümü, bebek için",
            "Göz muayenesi, bebek için, genel anestezi altında",
        },
        "2 yaş altı": {"2 yaş altı doğumsal kalp hastalıklarında tanısal kalp kateterizasyonu"},
        "10 yaş altı": {"Pelvipedal alçı (10 yaş altı)"},
    }
    for word, found in expected.items():
        gate = next(g for g in AGE_GATES if g.source == "name" and word in g.words)
        pattern = _words_pattern([word], whole=gate.whole)
        held = names.filter(pl.col("blanked").str.contains(pattern))
        assert set(held["name"]) == found, word


def test_folding_makes_turkish_capitals_comparable() -> None:
    assert fold_text("SÜNNET") == fold_text("sunnet") == "sunnet"
    assert fold_text("İÇ HASTALIKLARI") == "ic hastaliklari"
    assert fold_text("Çocuk ve Erişkin") == "cocuk ve eriskin"
    assert fold_text("ISI") == "isi"


def test_the_expression_folds_like_the_function() -> None:
    samples = ["SÜNNET", "İÇ HASTALIKLARI", "Çocuk ve Erişkin", "ISI", "Orşiektomi", "ığüşöçİ"]
    folded = pl.DataFrame({"name": samples}).select(_fold(pl.col("name")))["name"].to_list()
    assert folded == [fold_text(sample) for sample in samples]


# --- 6. the reference data ---------------------------------------------------------------------------


def test_the_context_reads_nothing_until_it_is_used() -> None:
    fresh = PlausibilityContext()
    assert not any(key in vars(fresh) for key in ("icd", "vocabulary", "pathways", "catalogs"))
    first = fresh.icd
    assert fresh.icd is first
    assert {"known", "created_on", "passive_on", "sex", "is_leaf", "is_active"} <= set(
        first.columns
    )


def test_the_vocabulary_holds_every_pathway_with_its_four_families(context) -> None:
    vocabulary = context.vocabulary
    assert set(vocabulary["family"]) == {"procedure", "material", "drug", "diagnosis"}
    assert set(vocabulary["scenario_tag"]) == set(context.pathways)
    assert vocabulary.height == vocabulary.unique().height


# --- 7. hygiene of the module ----------------------------------------------------------------------


_FORBIDDEN_ATTRIBUTES = {
    "iter_rows", "rows", "row", "to_dicts", "to_dict", "iterrows", "itertuples",
    "map_elements", "map_rows", "apply",
}  # fmt: skip


def _module_tree() -> ast.Module:
    return ast.parse(_MODULE.read_text(encoding="utf-8"), filename=str(_MODULE))


def test_the_module_has_no_row_wise_dataframe_calls() -> None:
    attributes = {node.attr for node in ast.walk(_module_tree()) if isinstance(node, ast.Attribute)}
    assert attributes & _FORBIDDEN_ATTRIBUTES == set()


def _imports(tree: ast.Module) -> list[ast.Import | ast.ImportFrom]:
    return [node for node in ast.walk(tree) if isinstance(node, ast.Import | ast.ImportFrom)]


def _imported_modules(tree: ast.Module) -> list[str]:
    modules: list[str] = []
    for node in _imports(tree):
        if isinstance(node, ast.Import):
            modules += [alias.name for alias in node.names]
        elif node.module:
            modules.append(node.module)
    return modules


def test_the_module_imports_no_pandas_and_of_the_engine_only_its_two_price_lookups() -> None:
    tree = _module_tree()
    imported = _imported_modules(tree)
    assert "polars" in imported
    for module in imported:
        assert not module.startswith("pandas"), module
        assert not module.startswith("reports"), module
        assert "prose_rules" not in module, module
        assert "domain.billing" not in module, module
    engine = [
        node
        for node in _imports(tree)
        if isinstance(node, ast.ImportFrom) and (node.module or "").startswith("src.bilun")
    ]
    assert [(node.module, sorted(a.name for a in node.names)) for node in engine] == [
        (
            "src.bilun.domain.pricing.temporal",
            ["get_ek2b_price_for_date", "get_ek2c_price_for_date"],
        )
    ]
    # ... imported inside `_engine_price`, so the engine (which loads pandas) is read only when
    # a price is asked for
    (lookup,) = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == "_engine_price"
    ]
    assert engine[0] in list(ast.walk(lookup))


def test_importing_the_module_loads_neither_pandas_nor_the_engine() -> None:
    code = (
        "import sys; sys.path.insert(0, sys.argv[1]); "
        "import scripts.synthetic.cohort.plausibility; "
        "print('pandas' in sys.modules, 'src.bilun.domain.pricing.temporal' in sys.modules)"
    )
    done = subprocess.run(
        [sys.executable, "-c", code, str(_REPO)], capture_output=True, text=True, check=True
    )
    assert done.stdout.split() == ["False", "False"], done.stderr


def test_the_module_does_not_use_the_generators_catalogs() -> None:
    """INDEPENDENCE: no `CohortCatalogs`, no import from the cohort generator."""
    tree = _module_tree()
    names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
    names |= {node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)}
    assert "CohortCatalogs" not in names
    assert not [m for m in _imported_modules(tree) if m.startswith("scripts.synthetic.cohort")]
    # the three price checks read the context's EK-3/F-1 and EK-4A frames, never its catalogs
    for function in (check_procedure_price, check_material_price, check_drug_price):
        source = inspect.getsource(function)
        assert "catalogs" not in source and "Catalogs" not in source, function.__name__


def test_the_module_names_no_anonymised_identifier() -> None:
    needle = "ANON" + "_"
    assert needle not in _MODULE.read_text(encoding="utf-8").upper()


def test_the_module_writes_no_file() -> None:
    """The checks only read: no table, no report, no cache is written."""
    text = _MODULE.read_text(encoding="utf-8")
    assert "write_parquet" not in text
    assert "write_csv" not in text
    assert ".write_text(" not in text


# --- 5. Several bills of one patient --------------------------------------------------------------------
#
# Patients 4 and 7 get one more bill (`STANDARD_EXTRAS`: patient 4's fourth, a stay a day after the first; patient
# 7's earlier visit, nine days before) and patient 9 a second bill of its pathway with other optional items pinned
# (decompression with its single anaesthesia, where the pathway's own pins have the foraminoplasty and the multiple
# one). Built in memory; nothing is committed from them.

_S9_PATHWAY = "lumbar_stenosis_decompression_foraminoplasty_itemized"


@pytest.fixture(scope="module")
def two_bills():
    recipes, clinical = with_encounters(
        *STANDARD_EXTRAS,
        Extra(9, 2, _S9_PATHWAY, {"admit": "2026-06-01", "story": "S94", "include": ["anaesthesia_single"]}),
    )
    return build_showcase(recipes=recipes, clinical=clinical)


def _claims_findings(result, *, tables=None, registry=None, anadata=None, only=None) -> list[Problem]:
    return check_plausibility(
        tables if tables is not None else result.tables,
        {TABLE_ANADATA: anadata if anadata is not None else result.clean_tables[TABLE_ANADATA]},
        registry=registry if registry is not None else result.registry,
        only=only,
    )


def test_more_bills_of_a_patient_raise_no_finding_that_the_cohort_does_not_raise(
    two_bills, built, faulty_problems
) -> None:
    found = _claims_findings(two_bills)
    assert {p.check for p in found} == set().union(*EXPECTED_FAULT_TRIPS.values())
    assert sorted(str(p) for p in found) == sorted(str(p) for p in faulty_problems)  # the same, bill for bill
    extra = {"F-SENTETIK-HASTA-0004-004", "F-SENTETIK-HASTA-0007-004", "F-SENTETIK-HASTA-0009-002"}
    assert not [p for p in found if p.claim_id in extra]


def test_the_age_of_every_bill_is_the_year_of_its_claim_minus_the_patients_birth_year(two_bills) -> None:
    check = ["patient.age_arithmetic"]
    assert _claims_findings(two_bills, only=check) == []
    ana = two_bills.clean_tables[TABLE_ANADATA]
    # a second bill that is a year older than its patient's one birth year
    wrong = ana.with_columns(
        pl.when(pl.col("SQ_EPISODE") == "B-SENTETIK-HASTA-0004-004")
        .then(pl.col("TANI_YASI") + 1)
        .otherwise(pl.col("TANI_YASI"))
        .alias("TANI_YASI")
    )
    found = _claims_findings(two_bills, anadata=wrong, only=check)
    assert [(p.check, p.claim_id) for p in found] == [("patient.age_arithmetic", "F-SENTETIK-HASTA-0004-004")]
    # a profile a year off is wrong for every bill of its patient (the stay, S39, S40 and the extra), and for no other
    profiles = two_bills.tables[TABLE_COPAY].with_columns(
        pl.when(pl.col("patient_id") == PATIENT[4])
        .then(pl.col("birth_year") + 1)
        .otherwise(pl.col("birth_year"))
        .alias("birth_year")
    )
    found = _claims_findings(two_bills, tables={**two_bills.tables, TABLE_COPAY: profiles}, only=check)
    assert sorted(p.claim_id for p in found) == [f"F-SENTETIK-HASTA-0004-00{n}" for n in (1, 2, 3, 4)]


def test_a_bill_that_overrides_its_pins_is_judged_by_the_expansion_with_those_pins(two_bills) -> None:
    check = ["fit.pathway_membership"]
    assert _claims_findings(two_bills, only=check) == []
    second = next(e for e in two_bills.registry["encounters"] if e["claim_id"] == "F-SENTETIK-HASTA-0009-002")
    assert second["pins"] == {"story": "S94", "admit": "2026-06-01", "include": ["anaesthesia_single"]}
    # a registry that does not say so judges the same bill by the pathway's own pins: its anaesthesia line is foreign
    old = copy.deepcopy(two_bills.registry)
    for encounter in old["encounters"]:
        encounter.pop("pins", None)
    (problem,) = _claims_findings(two_bills, registry=old, only=check)
    assert problem.claim_id == "F-SENTETIK-HASTA-0009-002"
    assert "procedure code 550160 is not in the expansion of " + _S9_PATHWAY in problem.message
    # pins that do not fit the code still count: another pin on the same bill, a code it does not expand
    wrong = copy.deepcopy(two_bills.registry)
    next(e for e in wrong["encounters"] if e["claim_id"] == "F-SENTETIK-HASTA-0009-002")["pins"] = {
        "story": "S94",
        "include": ["foraminoplasty"],
    }
    (problem,) = _claims_findings(two_bills, registry=wrong, only=check)
    assert "550160" in problem.message
    # the bills with no override are judged as they always were
    assert all(p.claim_id == "F-SENTETIK-HASTA-0009-002" for p in _claims_findings(two_bills, registry=old, only=check))


def test_a_bill_without_a_fault_has_no_answer_row_and_no_record_and_the_labels_agree(two_bills) -> None:
    labels = sorted(REGISTRY_CHECKS)
    assert _claims_findings(two_bills, only=labels) == []
    faults = len(cohort.load_registry()["faults"])  # three more bills, no more faults
    assert two_bills.tables[TABLE_ANSWERS].height == len(two_bills.registry["faults"]) == faults
    assert len(two_bills.tables[TABLE_CLAIM_HEADERS]) == cohort.claim_count() + 3
    # a record for a bill that has none would be an answer row the tables do not hold
    bad = copy.deepcopy(two_bills.registry)
    bad["faults"].append({**bad["faults"][0], "claim_id": "F-SENTETIK-HASTA-0004-004", "patient_id": PATIENT[4]})
    found = _claims_findings(two_bills, registry=bad, only=labels)
    assert ANSWER_ROWS in {p.check for p in found}
    assert {p.claim_id for p in found} == {"F-SENTETIK-HASTA-0004-004"}


# --- 6. The first visits of the committed cohort: the control (S39) and the second visit (S40) of patient 4 -----------


def _lines_of(tables: dict[str, pl.DataFrame], claim: str) -> list[tuple[str, str, str]]:
    """(code, day, EK-2A branch) of the billed lines of a claim, by code."""
    frame = tables[TABLE_PROCEDURES].filter(pl.col("claim_id") == claim).sort("procedure_code")
    return [(r["procedure_code"], r["procedure_date"], r["procedure_specialty_code"]) for r in frame.iter_rows(named=True)]


def test_the_two_outpatient_bills_of_patient_4_are_visits_of_one_date(built, twins) -> None:
    for tables in (built.tables, twins):
        headers = tables[TABLE_CLAIM_HEADERS].filter(pl.col("claim_id").is_in([CONTROL_CLAIM, SECOND_VISIT_CLAIM]))
        headers = headers.sort("claim_id")
        assert headers["claim_type"].to_list() == ["poliklinik", "poliklinik"]
        assert headers["department"].to_list() == ["İç Hastalıkları", "İç Hastalıkları"]
        assert headers["admission_date"].null_count() == headers["discharge_date"].null_count() == 2  # a visit has no stay
        assert headers["claim_start_date"].to_list() == headers["claim_end_date"].to_list() == ["2026-05-25", "2026-06-01"]
        assert headers["primary_icd10"].to_list() == ["N10", "N10"]  # the principal diagnosis of the patient's list
        assert _lines_of(tables, CONTROL_CLAIM) == [  # the control: the visit, the culture, three tests
            ("520030", "2026-05-25", "1000"),
            ("905671", "2026-05-25", "1000"),
            ("L104780", "2026-05-25", "1000"),
            ("L107010", "2026-05-25", "1000"),
            ("L107020", "2026-05-25", "1000"),
        ]
    # the second visit: the fault is the examination fee, the one line the clean twin does not bill
    assert _lines_of(built.tables, SECOND_VISIT_CLAIM) == [("520030", "2026-06-01", "1000"), ("803580", "2026-06-01", "3300")]
    assert _lines_of(twins, SECOND_VISIT_CLAIM) == [("803580", "2026-06-01", "3300")]


def test_the_outpatient_bills_raise_no_finding_of_the_data_check_whether_faulty_or_clean(built, twins, anadata, context) -> None:
    for tables in (built.tables, twins):
        found = Data(dict(tables), anadata).problems(context)
        assert [str(p) for p in found if p.claim_id in (CONTROL_CLAIM, SECOND_VISIT_CLAIM)] == []


def test_a_visit_that_has_a_discharge_date_is_no_visit(built, anadata, context) -> None:
    data = Data(dict(built.tables), anadata)
    edit(data, TABLE_CLAIM_HEADERS, pl.col("claim_id") == CONTROL_CLAIM, discharge_date="2026-05-26")
    (problem,) = [p for p in run_only(data, context, "stay.dates_in_window") if p.claim_id == CONTROL_CLAIM]
    assert "claim of type poliklinik is one day or a span of days, with no admission and no discharge" in problem.message


def test_a_visit_billed_with_the_consultation_code_is_found_by_the_visit_rule(built, anadata, context) -> None:
    data = Data(dict(built.tables), anadata)
    edit(data, TABLE_PROCEDURES, (pl.col("claim_id") == CONTROL_CLAIM) & (pl.col("procedure_code") == "520030"), procedure_code="520010")
    (problem,) = [p for p in run_only(data, context, VISIT) if p.claim_id == CONTROL_CLAIM]
    assert "examination 520010 on a claim of type poliklinik; 520030 is the examination of that type" in problem.message


def test_each_bill_of_a_patient_with_three_bills_is_judged_by_its_own_age(built, anadata, context) -> None:
    """An age a year off on the second visit is wrong for that bill only; a birth year a year off, for all three."""
    wrong = anadata.with_columns(
        pl.when(pl.col("SQ_EPISODE") == episode_id(PATIENT[4], 3)).then(87).otherwise(pl.col("TANI_YASI")).alias("TANI_YASI")
    )
    found = Data(dict(built.tables), wrong).problems(context, only=ARITH)
    assert [p.claim_id for p in found] == [SECOND_VISIT_CLAIM]
    data = Data(dict(built.tables), anadata)
    edit(data, TABLE_COPAY, pl.col("patient_id") == PATIENT[4], birth_year=1941)
    assert sorted(p.claim_id for p in run_only(data, context, ARITH)) == [CLAIM[4], CONTROL_CLAIM, SECOND_VISIT_CLAIM]


# --- 7. G3: a stay of one date (S47) and the window of a visit (a session claim may span dates) ------------------------

OBSERVATION_CLAIM = claim_id(PATIENT[7], 2)  # S47: patient 7's observation under 24 hours, admitted and discharged 02-25
DAY_CASE_CLAIM = claim_id(patient_id(13), 1)  # S20: the day case of patient 13 (gunubirlik)


def test_a_stay_of_one_date_has_one_day_bed_and_its_faulty_bill_misses_it(built, twins, anadata, context) -> None:
    for tables in (built.tables, twins):
        (header,) = tables[TABLE_CLAIM_HEADERS].filter(pl.col("claim_id") == OBSERVATION_CLAIM).iter_rows(named=True)
        assert (header["claim_type"], header["admission_date"], header["discharge_date"]) == ("yatis", "2026-02-25", "2026-02-25")
    beds = twins[TABLE_PROCEDURES].filter((pl.col("claim_id") == OBSERVATION_CLAIM) & pl.col("procedure_code").is_in(["510010", "510120"]))
    assert beds.select("procedure_code", "procedure_date", "quantity").rows() == [("510120", "2026-02-25", 1)]
    twin = Data(dict(twins), anadata)
    assert [p for p in run_only(twin, context, "stay.bed_coverage") if p.claim_id == OBSERVATION_CLAIM] == []
    faulty = Data(dict(built.tables), anadata)
    (problem,) = [p for p in run_only(faulty, context, "stay.bed_coverage") if p.claim_id == OBSERVATION_CLAIM]
    assert problem.message == "no bed line on 1 of 1 day(s): 2026-02-25"
    # the day bed on a stay of two dates is a defect of its own
    edit(twin, TABLE_CLAIM_HEADERS, pl.col("claim_id") == OBSERVATION_CLAIM, discharge_date="2026-02-26", claim_end_date="2026-02-26")
    found = [p.message for p in run_only(twin, context, "stay.bed_coverage") if p.claim_id == OBSERVATION_CLAIM]
    assert any("the day bed is for a day case" in m for m in found), found


@pytest.mark.parametrize(
    ("claim", "changes", "fits"),
    [
        pytest.param(CONTROL_CLAIM, {"claim_end_date": "2026-05-28"}, True, id="poliklinik_span"),
        pytest.param(DAY_CASE_CLAIM, {"claim_end_date": "2026-06-19"}, True, id="gunubirlik_span"),
        pytest.param(DAY_CASE_CLAIM, {}, True, id="gunubirlik_one_date"),
        pytest.param(CONTROL_CLAIM, {"claim_end_date": "2026-05-24"}, False, id="poliklinik_ends_before_it_starts"),
        pytest.param(DAY_CASE_CLAIM, {"admission_date": "2026-06-17"}, False, id="gunubirlik_with_an_admission"),
        pytest.param(DAY_CASE_CLAIM, {"discharge_date": "2026-06-17"}, False, id="gunubirlik_with_a_discharge"),
        pytest.param(OBSERVATION_CLAIM, {"discharge_date": None}, False, id="stay_of_one_date_without_its_discharge"),
    ],
)
def test_a_session_claim_may_span_dates_and_an_er_visit_is_one_date(claim, changes, fits, twins, anadata, context) -> None:
    data = Data(dict(twins), anadata)
    if changes:
        edit(data, TABLE_CLAIM_HEADERS, pl.col("claim_id") == claim, **changes)
    found = [p for p in run_only(data, context, "stay.dates_in_window") if p.claim_id == claim]
    assert (found == []) is fits, [str(p) for p in found]


def test_an_er_visit_over_two_dates_is_refused_with_the_rule_of_its_type(twins, anadata, context) -> None:
    er = cohort.role("showcase_S7").claim_id
    data = Data(dict(twins), anadata)
    edit(data, TABLE_CLAIM_HEADERS, pl.col("claim_id") == er, claim_end_date="2026-02-20")
    (problem,) = [p for p in run_only(data, context, "stay.dates_in_window") if p.claim_id == er]
    assert "is one day, with no admission and no discharge" in problem.message
    edit(data, TABLE_CLAIM_HEADERS, pl.col("claim_id") == CONTROL_CLAIM, claim_end_date="2026-05-24")
    # the header (its lines, now after the window's end, are findings of their own)
    (problem,) = [p for p in run_only(data, context, "stay.dates_in_window") if p.where == CONTROL_CLAIM]
    assert "is one day or a span of days, with no admission and no discharge" in problem.message
