"""Contract and mutation tests for `scripts/synthetic/cohort/plausibility.py` (plan D5, slices E1 and E2).

Every id in `plausibility.CHECKS` has one in-memory mutation case below (docs/testing-policy.md). A case seeds
one defect into a copy of the tables of the clean twins (the showcase bills without their fault) and proves that
exactly the target id trips, plus the ids in `also` that the defect unavoidably trips too (each one is explained
next to its case), with the right number of findings, `where` and `message`. The `labels.*` cases start from the
committed faulty bills and their registry instead (`on_faulty`). Nothing here writes a file.

A mutation edits the lines of a bill the way a generator would: when a priced line changes, the
header totals follow (`sync_totals`), so a case trips `money.totals` only when it means to.

The contract:
1. the clean twins raise no problem;
2. the committed faulty bills trip exactly the pinned ids (`EXPECTED_FAULT_TRIPS`);
3. every id has an implementation, a short meaning and a mutation case;
4. the committed Parquet files give the same result as the in-memory tables.
"""

from __future__ import annotations

from collections.abc import Callable
import copy
import dataclasses
import json
import re

import polars as pl
import pytest

from scripts.synthetic.cohort import DEFAULT_OUT_DIR
from scripts.synthetic.cohort.catalogs import CohortCatalogs
from scripts.synthetic.cohort.ids import (
    claim_id,
    diagnosis_id,
    drug_claim_line_id,
    episode_id,
    material_line_id,
    patient_id,
    procedure_line_id,
)
from scripts.synthetic.cohort.plausibility import (
    CHECK_FUNCTIONS,
    CHECKS,
    NO_CLAIM,
    REGISTRY_CHECKS,
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
    check_plausibility,
    run_all,
)
from scripts.synthetic.cohort.tables import TABLE_FILES, build_tables
from scripts.synthetic.faults import FaultInjectionRecord, build_expected_rule_outputs
from tests.fixtures import synthetic_cohort as cohort

pytestmark = pytest.mark.unit

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
DAILY = "stay.drug_daily_lines"
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
    "S1": set(),  # the mandated package billed hizmet başı: only the engine (claim_strategy, #269) sees it
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
    "S33": {"stay.drug_daily_lines"},  # the enoxaparin strength keyed as the count: 4000, not 1, on each of its days
    "S34": set(),  # the control examination flagged as a package component: no check reads a procedure flag, only the engine (tablo15_3) sees it
    "S38": set(),  # the neuromonitoring beside an instrumentation that is not on EK-2/D-4: a listed package at its price, only the engine (conditional_addon_ek2d) sees it
    "S40": set(),  # the examination fee of a second visit to the same branch within 10 days: only the engine (tablo15_2) sees it
    "S46": set(),  # a second walker inside the MIAT of the first: a listed device at its price on the examination, only the engine (MIAT) sees it
    "S42": set(),  # the red cells billed in full inside the package: the full price is on the ladder, only the engine (blood_component_partial_bill) sees it
    "S44": set(),  # romosozumab on a report of 12 months: no check reads a drug's report, only the engine (drug_indication) sees it
    "S20": set(),  # the day case billed itemized: only the engine sees it (as S1)
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


# --- helpers of the slice E2 cases ------------------------------------------------------------------


def mat(n: int) -> pl.Expr:
    """The n-th material line of S5's claim (the EK-3/F-1 implants of the hemiarthroplasty)."""
    return pl.col("material_line_id") == material_line_id(CLAIM[5], n)


def mat_at(n: int) -> str:
    """The `where` of a finding about S5's n-th material line, after the claim id."""
    return f"{CLAIM[5]} material_claim_lines[{material_line_id(CLAIM[5], n)}]"


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
    # --- patient.sex_gate. The name cases rename a billed line: the check reads the name only.
    Case(
        SEX,
        lambda d: add_diagnosis(d, 1, "C53.9"),  # cervix carcinoma on S1, a man
        also=(PATHWAY,),
        label="icd_gate_female_code_on_a_man",
        at=new_row_at(1, TABLE_DIAGNOSES),
        says="diagnosis C53.9 is limited to sex F but the patient is M",
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
    # --- patient.age_arithmetic
    Case(
        ARITH,
        lambda d: edit_patient(d, 2, TANI_YASI=82),
        label="tani_yasi_one_year_off",
        at=CLAIM[2],
        says="TANI_YASI is 82; the claim year is 2026 and the birth year 1945, which makes the age 81",
    ),
    # --- fit.pathway_membership. The extra lines are valid in themselves.
    Case(
        PATHWAY,
        lambda d: add_procedure(d, 7, "530350", "2026-02-19"),  # a nebuliser from the COPD ward
        label="extra_procedure",
        at=new_row_at(7, TABLE_PROCEDURES),
        says="procedure code 530350 is not in the expansion of pleuritic_chest_pain_er_pulmonary_embolism_ruled_out",
    ),
    # --- fit.operation_department
    Case(
        DEPT,
        lambda d: edit(d, TABLE_PROCEDURES, line(3, "615931"), procedure_specialty_code="1000"),
        label="operation_in_internal_medicine",
        at=row_at(3, TABLE_PROCEDURES, line(3, "615931")),
        says="operation 615931 (Dar spinal kanalda unilateral dekompresyon) has the specialty 1000, which is not a surgical EK-2A branch",
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
    # --- fit.visit_code
    Case(
        VISIT,
        lambda d: edit(d, TABLE_CLAIM_HEADERS, of(7), claim_type="poliklinik"),
        label="acil_visit_on_a_poliklinik_claim",
        at=row_at(7, TABLE_PROCEDURES, line(7, "520020")),
        says="examination 520020 on a claim of type poliklinik; 520030 is the examination of that type",
    ),
    # --- stay.bed_coverage (S2: 6 nights, 7 bed lines)
    Case(
        BED,
        lambda d: drop(d, TABLE_PROCEDURES, line(2, "510010", "2026-03-12")),
        label="missing_day",
        at=CLAIM[2],
        says="no bed line on 1 of 7 day(s): 2026-03-12",
    ),
    # --- stay.companion_coverage (S2: companions on the six nights 03-09 .. 03-14)
    Case(
        COMP,
        lambda d: edit(d, TABLE_PROCEDURES, line(2, "510121", "2026-03-11"), quantity=2),
        label="quantity_two",
        at=row_at(2, TABLE_PROCEDURES, line(2, "510121", "2026-03-11")),
        says="companion line has the quantity 2",
    ),
    # --- stay.dates_in_window
    Case(
        DATES,
        lambda d: edit(d, TABLE_CLAIM_HEADERS, of(2), claim_end_date="2026-03-16"),
        label="yatis_claim_ends_after_discharge",
        at=CLAIM[2],
        says="claim of type yatis starts on admission and ends on discharge: admission 2026-03-09, discharge 2026-03-15, start 2026-03-09, end 2026-03-16",
    ),
    # --- stay.control_in_package_period (S1's package, group C: the period runs to 2026-07-31; S31 is its control)
    Case(
        "stay.control_in_package_period",
        lambda d: (
            edit(d, TABLE_CLAIM_HEADERS, pl.col("claim_id") == "F-SENTETIK-HASTA-0001-003", claim_start_date="2026-07-31", claim_end_date="2026-07-31"),
            edit(d, TABLE_PROCEDURES, pl.col("claim_id") == "F-SENTETIK-HASTA-0001-003", procedure_date="2026-07-31"),
            edit(d, TABLE_DIAGNOSES, pl.col("claim_id") == "F-SENTETIK-HASTA-0001-003", diagnosis_date="2026-07-31"),
        ),
        label="the_control_inside_the_period",
        at="F-SENTETIK-HASTA-0001-003 procedure_claim_lines[",
        says="inside the 10 days after the package's discharge of 2026-07-21 (C000714)",
    ),
    # --- stay.entry_visit (S4's stay and its ER visit S54; review of 2026-10-30, A1)
    Case(
        "stay.entry_visit",
        lambda d: edit(d, TABLE_CLAIM_HEADERS, pl.col("claim_id") == "F-SENTETIK-HASTA-0004-004", claim_type="gunubirlik"),
        label="the_visit_before_the_stay_is_not_a_visit",
        at=CLAIM[4],
        says="the stay admitted on 2026-05-11 has no acil bill that day or the day before",
    ),
    # --- stay.drug_daily_lines (S2's ceftriaxone: one vial a day, 2026-03-09..03-15; review of 2026-10-30, A3)
    Case(
        DAILY,
        lambda d: (
            edit(d, TABLE_DRUGS, of(2) & (pl.col("barkod") == "8699508270224") & (pl.col("drug_claim_date") == "2026-03-09"), quantity=7.0),
            drop(d, TABLE_DRUGS, of(2) & (pl.col("barkod") == "8699508270224") & (pl.col("drug_claim_date") != "2026-03-09")),
        ),
        label="whole_course_on_one_line",
        at=CLAIM[2] + " drug_claim_lines[",
        says="has the quantity 7.0 on one line; its daily quantity is 1.0",
    ),
    # --- bill.performed_billed
    Case(
        PERF,
        lambda d: drop(d, TABLE_PROCEDURES, line(7, "R101450")),  # the CT angiography of story S7
        label="billed_line_deleted",
        at=row_at(7, TABLE_PERFORMED, performed(7, "R101450")),
        says="performed R101450 (BT anjiografi, pulmoner arter) on 2026-02-19 has no billed procedure line",
    ),
    # --- package.mode
    Case(
        PACKAGE,
        lambda d: add_procedure(d, 1, "510010", "2026-07-14"),
        label="bed_line_on_a_package_claim",
        at=new_row_at(1, TABLE_PROCEDURES),
        says="bed line 510010 on a package claim; the beds are inside the package",
    ),
    # --- anaesthesia.operation_pairing (S3: decompression 615931 and anaesthesia 550160 on 08-18)
    Case(
        PAIRING,
        lambda d: drop(d, TABLE_PROCEDURES, line(3, "550160")),
        label="anaesthesia_line_deleted",
        at=f"{CLAIM[3]} day[2026-08-18]",
        says="1 operation line(s) and 0 anaesthesia line(s); one anaesthesia line per operation day, none else",
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
    # --- material.stray_flag
    Case(
        "material.stray_flag",
        lambda d: edit(d, TABLE_MATERIALS, mat(1), diagnosis_bundled_no_separate_bill=True),
        label="defect_flag_true",
        at=mat_at(1),
        says="diagnosis_bundled_no_separate_bill is true",
    ),
    # --- price.procedure_in_force (a lab test, the ER CT angiography, the EK-2C package)
    Case(
        "price.procedure_in_force",
        lambda d: reprice(d, TABLE_PROCEDURES, line(4, "L101850", "2026-05-13"), 17.46),
        label="changed_unit_price",
        at=f"{CLAIM[4]} procedure_claim_lines[",
        says="procedure L101850 dated 2026-05-13: unit price 17.46 but the price in force is 16.46",
    ),
    # --- price.material_in_force
    Case(
        "price.material_in_force",
        lambda d: reprice(d, TABLE_MATERIALS, mat(2), 6566.27),
        label="changed_unit_price",
        at=mat_at(2),
        says="material AP2000 dated 2026-09-04 has the unit price 6566.27 but the list price is 6465.27",
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
    # --- labels.answer_rows (from the faulty bills and their registry)
    Case(
        ANSWER_ROWS,
        lambda d: edit(d, TABLE_ANSWERS, of(2), expected_status="kismi_red"),
        label="status_changed",
        on_faulty=True,
        at=f"{CLAIM[2]} expected_rule_outputs[",
        says="expected_status is kismi_red but the fault record gives eksik_faturalama",
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


@pytest.fixture(scope="module")
def clean_problems(twins, anadata, context) -> list[Problem]:
    return check_plausibility(twins, {TABLE_ANADATA: anadata}, context=context)


@pytest.fixture(scope="module")
def faulty_problems(built, anadata, context) -> list[Problem]:
    """The faulty bills, with the registry: the `labels.*` ids run too."""
    return check_plausibility(
        built.tables, {TABLE_ANADATA: anadata}, context=context, registry=built.registry
    )


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


# --- 4. the meaning of the checks, beyond the mutation cases ---------------------------------------


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
