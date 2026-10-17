"""Contract, mutation and hygiene tests for `scripts/synthetic/cohort/plausibility.py` (plan D5, slices E1 and E2).

Every id in `plausibility.CHECKS` has at least one in-memory mutation case below. A case seeds ONE
defect into a copy of the tables of the eight clean twins (the showcase bills without their fault)
and proves that exactly the target id trips, plus the ids in `also` that the defect unavoidably
trips too (each one is explained next to its case). The `labels.*` cases start from the committed
faulty bills and their registry instead (`on_faulty`): the fault records exist only there, and the
case must add nothing but its own finding to what the faulty bills already trip. Nothing here
writes a file.

A mutation edits the lines of a bill the way a generator would: when a priced line changes, the
header totals follow (`sync_totals`), so a case trips `money.totals` only when it means to.

The contract:
1. the eight clean twins raise no problem;
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

from scripts.synthetic.cohort import build_showcase
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
    EK3F1_FROM,
    FEMALE_ONLY_WORDS,
    LADDER_QUARTERS,
    MALE_ONLY_WORDS,
    NAME_EXCEPTIONS,
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
    _fold,
    _is_cent_price_of,
    _tl,
    check_drug_price,
    check_material_price,
    check_plausibility,
    check_procedure_price,
    fold_text,
    run_all,
)
from scripts.synthetic.cohort.tables import TABLE_FILES, build_tables
from scripts.synthetic.faults import FaultInjectionRecord, build_expected_rule_outputs

pytestmark = pytest.mark.unit

_REPO = Path(__file__).resolve().parents[3]
_MODULE = _REPO / "scripts/synthetic/cohort/plausibility.py"
_SHOWCASE_DIR = _REPO / "data/synthetic/showcase"
_CLAIMS_DIR = _SHOWCASE_DIR / "sut/claims"
_CLEAN_DIR = _SHOWCASE_DIR / "sut/clean"
_REGISTRY_FILE = _SHOWCASE_DIR / "cohort_registry.json"

# The ids a mutation case may name; written out so a typo in a case fails at collection time.
PATHWAY = "fit.pathway_membership"
DATES = "stay.dates_in_window"
PAIRING = "anaesthesia.operation_pairing"
PACKAGE = "package.mode"
OPLINK = "material.operation_link"
ANSWER_ROWS = "labels.answer_rows"
AMOUNTS = "labels.amounts"

# What the committed faulty bill of each story trips (checked by the orchestrator with a prototype).
# S4's missing companion, S6's dropped diagnosis and S8's wrong ratio are invisible to plausibility
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

STORIES = tuple(range(1, 9))
PATIENT = {n: patient_id(n) for n in STORIES}
CLAIM = {n: claim_id(PATIENT[n], 1) for n in STORIES}
EPISODE = {n: episode_id(PATIENT[n], 1) for n in STORIES}
CATALOGS = CohortCatalogs()


# --- fixtures -----------------------------------------------------------------------------------


@pytest.fixture(scope="module")
def built():
    return build_showcase()


@pytest.fixture(scope="module")
def context() -> PlausibilityContext:
    return PlausibilityContext()


@pytest.fixture(scope="module")
def twins(built) -> dict[str, pl.DataFrame]:
    """The tables of the eight clean twins: the showcase bills as the pathways expand them."""
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
    """Change anadata_clean (and, with `birth_year`, the copay profile) of the story's patient."""
    here = pl.col("HASTA_ID") == PATIENT[story]
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


def add_diagnosis(data: Data, story: int, icd10: str) -> None:
    frame = data.tables[TABLE_DIAGNOSES]
    new_id = diagnosis_id(CLAIM[story], _next_seq(frame, story, "diagnosis_id"))
    add_row(
        data,
        TABLE_DIAGNOSES,
        of(story),
        diagnosis_id=new_id,
        icd10_code=icd10,
        is_primary=False,
        diagnosis_role="secondary",
    )


def set_code(data: Data, story: int, old: str, new: str) -> None:
    """Bill another code on a line: the line takes the catalog price of the new code on its day."""
    day = data.tables[TABLE_PROCEDURES].filter(line(story, old))["procedure_date"].item()
    price = float(CATALOGS.procedure_row(new, day).price)
    amount = (pl.lit(price) * pl.col("quantity")).round(2)
    edit(
        data,
        TABLE_PROCEDURES,
        line(story, old),
        procedure_code=new,
        unit_price_try=price,
        billed_amount_try=amount,
        expected_payable_try=amount,
    )


def rename(data: Data, story: int, code: str, name: str) -> None:
    edit(data, TABLE_PROCEDURES, line(story, code), procedure_name=name)


def only_ids(found: list[Problem]) -> set[str]:
    return {problem.check for problem in found}


# --- the mutation cases ---------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class Case:
    """One seeded defect.

    `at` and `says` are fragments that one finding of the target id must carry in its `where` and its
    `message`: the case proves the right line and the right reason, not only the id (every slice E2
    case sets both). `on_faulty` starts from the committed faulty bills and their registry (the
    `labels.*` cases); the findings that already exist there are not counted.
    """

    check: str
    mutate: Callable[[Data], None]
    also: tuple[str, ...] = ()
    label: str = ""
    at: str = ""
    says: str = ""
    on_faulty: bool = False

    @property
    def name(self) -> str:
        return f"{self.check}-{self.label}" if self.label else self.check


def _second_operation(d: Data) -> None:
    # a second chapter-6 operation on the day of S3's decompression, in a surgical branch
    add_procedure(d, 3, "603030", "2026-08-18", specialty="2400")


def _move_last_bed_after_discharge(d: Data) -> None:
    edit(d, TABLE_PROCEDURES, line(2, "510010", "2026-03-15"), procedure_date="2026-03-16")


def _adult_name_on_a_child(d: Data) -> None:
    # S1 becomes a 12-year-old (age and birth year agree, so only the name is wrong)
    edit_patient(d, 1, birth_year=2014, TANI_YASI=12)
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
    """The n-th material line of S5's claim (the only claim with materials)."""
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
    d.tables[TABLE_ANSWERS] = rows[[0, 2, 1, *range(3, rows.height)]]  # S2's and S3's rows swap


CASES: list[Case] = [
    # --- patient.icd_valid. A code that is not in the pathway is also outside its expansion.
    Case(
        "patient.icd_valid",
        lambda d: edit(
            d, TABLE_DIAGNOSES, of(2) & (pl.col("icd10_code") == "I10"), icd10_code="J99.99"
        ),
        also=(PATHWAY,),
        label="unknown_code",
    ),
    Case(
        "patient.icd_valid",
        # Z22.5: inactive, and passive since 2026-02-16, before S2's diagnosis date
        lambda d: edit(
            d, TABLE_DIAGNOSES, of(2) & (pl.col("icd10_code") == "I10"), icd10_code="Z22.5"
        ),
        also=(PATHWAY,),
        label="inactive_and_passive_code",
    ),
    Case(
        "patient.icd_valid",
        # K35 is the category of K35.9 (acute appendicitis): not a leaf
        lambda d: edit(d, TABLE_DIAGNOSES, of(1), icd10_code="K35"),
        also=(PATHWAY,),
        label="not_a_leaf",
    ),
    Case(
        "patient.icd_valid",
        # F99 exists since 2026-07-22; S2's diagnosis is dated 2026-03-09
        lambda d: edit(
            d, TABLE_DIAGNOSES, of(2) & (pl.col("icd10_code") == "I10"), icd10_code="F99"
        ),
        also=(PATHWAY,),
        label="created_after_the_diagnosis_date",
    ),
    # --- patient.sex_gate. The name cases rename a billed line: the check reads the name only.
    Case(
        "patient.sex_gate",
        lambda d: add_diagnosis(d, 1, "C53.9"),  # cervix carcinoma on S1, a man
        also=(PATHWAY,),
        label="icd_gate_female_code_on_a_man",
    ),
    Case(
        "patient.sex_gate",
        lambda d: add_diagnosis(d, 3, "C61"),  # prostate carcinoma on S3, a woman
        also=(PATHWAY,),
        label="icd_gate_male_code_on_a_woman",
    ),
    Case(
        "patient.sex_gate",
        lambda d: rename(d, 1, "P610131", "Vajinal histerektomi"),
        label="name_female_word_on_a_man",
    ),
    Case(
        "patient.sex_gate",
        lambda d: rename(d, 3, "L104780", "Prostat spesifik antijen (PSA), total"),
        label="name_male_word_on_a_woman",
    ),
    Case(
        "patient.sex_gate",
        lambda d: rename(d, 1, "P610131", "Over detorsiyonu"),
        label="name_whole_word_over_on_a_man",
    ),
    Case(
        "patient.sex_gate",
        lambda d: rename(d, 3, "L104780", "SÜNNET DERİSİ"),  # upper-case Turkish letters
        label="name_upper_case_turkish_word_on_a_woman",
    ),
    Case(
        "patient.sex_gate",
        lambda d: (edit_patient(d, 2, CINSIYET="?"), rename(d, 2, "L101850", "Testis biyopsisi")),
        label="name_word_for_a_patient_of_unknown_sex",
    ),
    # --- patient.age_gate
    Case(
        "patient.age_gate",
        lambda d: add_diagnosis(d, 2, "P07.3"),  # a perinatal code on an 81-year-old
        also=(PATHWAY,),
        label="perinatal_code_on_an_adult",
    ),
    Case(
        "patient.age_gate",
        lambda d: add_diagnosis(d, 1, "O80.9"),  # a pregnancy code on a man aged 34
        also=(PATHWAY,),
        label="pregnancy_code_on_a_man",
    ),
    Case(
        "patient.age_gate",
        lambda d: add_diagnosis(d, 7, "O80.9"),  # a pregnancy code on a woman aged 58
        also=(PATHWAY,),
        label="pregnancy_code_on_a_woman_past_55",
    ),
    Case(
        "patient.age_gate",
        lambda d: add_diagnosis(d, 3, "Z38.0"),  # a liveborn code on a 77-year-old
        also=(PATHWAY,),
        label="liveborn_code_on_an_adult",
    ),
    Case(
        "patient.age_gate",
        lambda d: rename(d, 2, "L101850", "Yenidoğan monitörizasyonu"),
        label="newborn_name_on_an_adult",
    ),
    Case(
        "patient.age_gate",
        lambda d: rename(d, 2, "L101850", "Çocuk odyometresi (Komple)"),
        label="child_name_on_an_adult",
    ),
    Case("patient.age_gate", _adult_name_on_a_child, label="adult_name_on_a_child"),
    # --- patient.age_arithmetic
    Case(
        "patient.age_arithmetic",
        lambda d: edit_patient(d, 2, TANI_YASI=82),
        label="tani_yasi_one_year_off",
    ),
    Case(
        "patient.age_arithmetic",
        lambda d: edit(d, TABLE_COPAY, pl.col("patient_id") == PATIENT[3], birth_year=1950),
        label="birth_year_one_year_off",
    ),
    Case(
        "patient.age_arithmetic",
        lambda d: edit(d, TABLE_COPAY, pl.col("patient_id") == PATIENT[5], birth_year=None),
        label="no_birth_year",
    ),
    Case(
        "patient.age_arithmetic",
        lambda d: setattr(d, "anadata", d.anadata.filter(pl.col("HASTA_ID") != PATIENT[4])),
        label="no_anadata_row",
    ),
    # --- fit.pathway_membership. The extra lines are valid in themselves.
    Case(
        PATHWAY,
        lambda d: add_procedure(d, 7, "530350", "2026-02-19"),  # a nebuliser from the COPD ward
        label="extra_procedure",
    ),
    Case(PATHWAY, _extra_material, label="extra_material"),
    Case(PATHWAY, _extra_drug, label="extra_drug"),
    Case(PATHWAY, lambda d: add_diagnosis(d, 4, "E11.9"), label="extra_diagnosis"),
    Case(
        PATHWAY,
        lambda d: edit(d, TABLE_CLAIM_HEADERS, of(2), scenario_tag="no_such_pathway"),
        label="scenario_tag_is_no_pathway",
    ),
    # --- fit.operation_department
    Case(
        "fit.operation_department",
        lambda d: edit(d, TABLE_PROCEDURES, line(3, "615931"), procedure_specialty_code="1000"),
        label="operation_in_internal_medicine",
    ),
    Case(
        "fit.operation_department",
        lambda d: edit(d, TABLE_PROCEDURES, line(5, "P612320"), procedure_specialty_code="1000"),
        label="package_operation_in_internal_medicine",
    ),
    Case(
        "fit.operation_department",
        lambda d: edit(d, TABLE_PROCEDURES, line(3, "615931"), procedure_specialty_code="9999"),
        label="operation_in_an_unknown_branch",
    ),
    Case(
        "fit.operation_department",
        lambda d: edit(d, TABLE_PROCEDURES, line(3, "615931"), procedure_specialty_code=None),
        label="operation_without_a_branch",
    ),
    # --- fit.operation_setting. A visit claim has no stay: start equals end, no admission date.
    Case(
        "fit.operation_setting",
        lambda d: edit(d, TABLE_CLAIM_HEADERS, of(3), claim_type="poliklinik"),
        also=(DATES,),  # the decompression claim still has its three-day stay
        label="band_b_operation_on_a_poliklinik_claim",
    ),
    Case(
        "fit.operation_setting",
        lambda d: edit(d, TABLE_CLAIM_HEADERS, of(5), claim_type="acil"),
        also=(DATES,),  # the hemiarthroplasty claim still has its six-day stay
        label="band_b_package_on_an_acil_claim",
    ),
    # --- fit.visit_code
    Case(
        "fit.visit_code",
        lambda d: edit(d, TABLE_CLAIM_HEADERS, of(7), claim_type="poliklinik"),
        label="acil_visit_on_a_poliklinik_claim",
    ),
    Case(
        "fit.visit_code",
        lambda d: set_code(d, 7, "520020", "520030"),
        also=(PATHWAY,),  # 520030 is not a line of the ER pathway
        label="poliklinik_visit_on_an_acil_claim",
    ),
    Case(
        "fit.visit_code",
        lambda d: set_code(d, 6, "520010", "520030"),
        also=(PATHWAY,),  # 520030 is not a line of the ward pathway
        label="poliklinik_visit_on_a_yatis_claim",
    ),
    # --- stay.bed_coverage (S2: 6 nights, 7 bed lines)
    Case(
        "stay.bed_coverage",
        lambda d: drop(d, TABLE_PROCEDURES, line(2, "510010", "2026-03-12")),
        label="missing_day",
    ),
    Case(
        "stay.bed_coverage",
        lambda d: clone_procedure(d, 2, line(2, "510010", "2026-03-10")),
        label="duplicate_day",
    ),
    Case(
        "stay.bed_coverage",
        _move_last_bed_after_discharge,
        also=(DATES,),  # a bed line after discharge also lies outside the claim window
        label="day_after_discharge",
    ),
    Case(
        "stay.bed_coverage",
        lambda d: edit(d, TABLE_PROCEDURES, line(2, "510010", "2026-03-11"), quantity=2),
        label="quantity_two",
    ),
    # --- stay.companion_coverage (S2: companions on the six nights 03-09 .. 03-14)
    Case(
        "stay.companion_coverage",
        lambda d: edit(d, TABLE_PROCEDURES, line(2, "510121", "2026-03-11"), quantity=2),
        label="quantity_two",
    ),
    Case(
        "stay.companion_coverage",
        lambda d: clone_procedure(d, 2, line(2, "510121", "2026-03-10")),
        label="two_on_one_day",
    ),
    Case(
        "stay.companion_coverage",
        lambda d: edit(
            d, TABLE_PROCEDURES, line(2, "510121", "2026-03-14"), procedure_date="2026-03-15"
        ),
        label="on_the_discharge_day",
    ),
    Case(
        "stay.companion_coverage",
        lambda d: edit(
            d, TABLE_PROCEDURES, line(2, "510121", "2026-03-09"), procedure_date="2026-03-08"
        ),
        also=(DATES,),  # a companion before admission also lies outside the claim window
        label="before_admission",
    ),
    Case(
        "stay.companion_coverage",
        lambda d: add_procedure(d, 7, "510121", "2026-02-19"),
        also=(PATHWAY,),  # the ER pathway has no companion line
        label="on_a_claim_without_a_stay",
    ),
    # --- stay.dates_in_window
    Case(
        DATES,
        lambda d: edit(d, TABLE_CLAIM_HEADERS, of(2), claim_end_date="2026-03-16"),
        label="yatis_claim_ends_after_discharge",
    ),
    Case(
        DATES,
        lambda d: edit(d, TABLE_CLAIM_HEADERS, of(7), admission_date="2026-02-19"),
        label="acil_claim_with_an_admission_date",
    ),
    Case(
        DATES,
        lambda d: edit(d, TABLE_CLAIM_HEADERS, of(7), claim_end_date="2026-02-20"),
        label="acil_claim_over_two_days",
    ),
    Case(
        DATES,
        lambda d: edit(
            d, TABLE_PROCEDURES, line(4, "L101850", "2026-05-13"), procedure_date="2026-05-20"
        ),
        label="procedure_line_after_the_claim",
    ),
    Case(
        DATES,
        lambda d: edit(
            d, TABLE_PROCEDURES, line(4, "L101850", "2026-05-13"), procedure_date="13.05.2026"
        ),
        label="procedure_date_is_not_an_iso_date",
    ),
    Case(
        DATES,
        lambda d: edit(d, TABLE_MATERIALS, of(5), material_date="2026-09-20"),
        also=(OPLINK,),  # a material on another day than the operation it hangs on
        label="material_line_after_the_claim",
    ),
    Case(
        DATES,
        lambda d: edit(d, TABLE_DRUGS, of(2), drug_claim_date="2026-03-20"),
        label="drug_line_after_the_claim",
    ),
    Case(
        DATES,
        lambda d: edit(d, TABLE_DIAGNOSES, of(2), diagnosis_date="2026-03-20"),
        label="diagnosis_after_the_claim",
    ),
    Case(
        DATES,
        _performed_line_a_day_late,
        also=("bill.performed_billed",),  # the billed 530100 line is on the 19th
        label="performed_line_after_the_claim",
    ),
    # --- bill.performed_billed
    Case(
        "bill.performed_billed",
        lambda d: drop(d, TABLE_PROCEDURES, line(7, "R101450")),  # the CT angiography of story S7
        label="billed_line_deleted",
    ),
    Case(
        "bill.performed_billed",
        lambda d: edit(
            d,
            TABLE_PERFORMED,
            (pl.col("claim_id") == CLAIM[7]) & (pl.col("procedure_code") == "530080"),
            procedure_code="530350",
        ),
        label="performed_code_is_not_billed",
    ),
    # --- package.mode
    Case(
        PACKAGE,
        lambda d: edit(d, TABLE_CLAIM_HEADERS, of(1), package_candidate=False),
        label="candidate_false_on_a_package_claim",
    ),
    Case(
        PACKAGE,
        lambda d: edit(d, TABLE_CLAIM_HEADERS, of(2), package_candidate=True),
        label="candidate_true_on_an_itemised_claim",
    ),
    Case(
        PACKAGE,
        lambda d: add_procedure(d, 5, "510010", "2026-09-04"),
        also=(PATHWAY,),  # a ward bed is not a line of the hemiarthroplasty package
        label="bed_line_on_a_package_claim",
    ),
    Case(
        PACKAGE,
        lambda d: add_procedure(d, 5, "550160", "2026-09-04", specialty="3100"),
        # anaesthesia.operation_pairing says the same ("a package has none"); 550160 is no line
        # of the hemiarthroplasty package
        also=(PAIRING, PATHWAY),
        label="anaesthesia_line_on_a_package_claim",
    ),
    # --- anaesthesia.operation_pairing (S3: decompression 615931 and anaesthesia 550160 on 08-18)
    Case(
        PAIRING,
        lambda d: drop(d, TABLE_PROCEDURES, line(3, "550160")),
        label="anaesthesia_line_deleted",
    ),
    Case(
        PAIRING,
        lambda d: clone_procedure(d, 3, line(3, "550160"), procedure_date="2026-08-19"),
        label="anaesthesia_without_an_operation",
    ),
    Case(
        PAIRING,
        lambda d: clone_procedure(d, 3, line(3, "550160")),
        label="two_anaesthesia_lines_on_an_operation_day",
    ),
    Case(
        PAIRING,
        lambda d: add_procedure(d, 8, "550160", "2026-09-15", specialty="3100"),
        # package.mode says the same; 550160 is no line of the two-package pathway
        also=(PACKAGE, PATHWAY),
        label="anaesthesia_line_on_a_package_claim",
    ),
    # --- anaesthesia.group
    Case(
        "anaesthesia.group",
        lambda d: set_code(d, 3, "550160", "550170"),  # the code of group C, the puan is group B
        also=(PATHWAY,),
        label="single_code_of_another_group",
    ),
    Case(
        "anaesthesia.group",
        lambda d: set_code(d, 3, "550160", "550230"),  # B, but the "several operations" code
        also=(PATHWAY,),
        label="several_operations_code_for_one_operation",
    ),
    Case(
        "anaesthesia.group",
        _second_operation,
        also=(PATHWAY,),  # two operations need the "several operations" code; 603030 is no line
        label="single_code_for_two_operations",
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
        says="it is dated 2026-09-05 but the operation P612320 it hangs on is dated 2026-09-04",
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
        # 1034.75 is the price of the list that ended on 2025-12-31; the 2026 list bills 1138.22
        lambda d: reprice(d, TABLE_PROCEDURES, line(7, "R101450"), 1034.75),
        label="price_of_the_list_before_the_2026_update",
        at=f"{CLAIM[7]} procedure_claim_lines[",
        says="procedure R101450 dated 2026-02-19: unit price 1034.75 but the price in force is 1138.22",
    ),
    Case(
        "price.procedure_in_force",
        lambda d: reprice(d, TABLE_PROCEDURES, line(5, "P612320"), 18000.0),
        label="package_price",
        at=f"{CLAIM[5]} procedure_claim_lines[",
        says="procedure P612320 dated 2026-09-04: unit price 18000.00 but the price in force is 18390.80",
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
    # --- money.totals (S3's clean twin bills 5607.62)
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
        says="expected_total_billed_try is 5608.62 but the billed amounts of the claim's lines add up to 5607.62",
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
        says="expected_total_payable_try is 5607.61 but the payable amounts of the claim's lines add up to 5607.62",
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
        lambda d: edit_fault(d, 2, billed_faulty_try="2596.36", amount_try="667.07"),
        label="wrong_faulty_total",
        on_faulty=True,
        at=f"{CLAIM[2]} registry faults[F_S2_BED_DAYS_UNDERBILLED]",
        says="billed_faulty_try is 2596.36 but expected_total_billed_try of the claim is 2596.35",
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
        lambda d: edit_fault(d, 3, relabel=False, amount_try="928.10"),
        # the record no longer validates (revenue_uplift = clean - faulty), so no record explains S3's row
        also=(ANSWER_ROWS,),
        label="revenue_uplift_amount",
        on_faulty=True,
        at=f"{CLAIM[3]} registry faults[F_S3_ANAESTHESIA_LINE_MISSING]",
        says="revenue_uplift amount_try is 928.10 but must be 928.09 (billed_clean_try - billed_faulty_try)",
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
        on_faulty=True,
        at=f"{CLAIM[1]} registry faults[F_S1_PACKAGE_BILLED_ITEMIZED]",
        says=f"line_id {procedure_line_id(CLAIM[1], 1)} must be empty for line_type fatura",
    ),
    Case(
        AMOUNTS,
        lambda d: edit_fault(d, 5, relabel=False, line_id=""),
        also=(ANSWER_ROWS,),  # a malzeme record without a line id does not validate
        label="line_type_without_a_line_id",
        on_faulty=True,
        at=f"{CLAIM[5]} registry faults[F_S5_IMPLANT_UTS_INCOMPLETE]",
        says="line_type malzeme needs the line_id of its target line",
    ),
    Case(
        AMOUNTS,
        lambda d: edit_fault(d, 4, relabel=False, effect_kind="refund"),
        also=(ANSWER_ROWS,),  # an effect kind outside the three does not validate
        label="unknown_effect_kind",
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


def test_the_registry_ids_are_the_labels_ids_and_every_slice_e2_case_names_its_finding() -> None:
    assert REGISTRY_CHECKS == {"labels.answer_rows", "labels.amounts"}
    assert REGISTRY_CHECKS <= E2_CHECKS
    for case in CASES:
        if case.check in E2_CHECKS:
            assert case.at and case.says, f"{case.name} must say where and what it expects"
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


def test_the_eight_clean_twins_are_all_there_and_all_clean(clean_problems, twins) -> None:
    assert twins[TABLE_CLAIM_HEADERS].height == 8
    assert [str(p) for p in clean_problems] == []


@pytest.mark.parametrize("story", sorted(EXPECTED_FAULT_TRIPS))
def test_a_faulty_bill_trips_the_pinned_ids(story, built, faulty_problems) -> None:
    story_of = {e["claim_id"]: e["story"] for e in built.registry["encounters"]}
    assert sorted(story_of.values()) == sorted(EXPECTED_FAULT_TRIPS)
    claim = next(claim for claim, name in story_of.items() if name == story)
    tripped = {p.check for p in faulty_problems if p.claim_id == claim}
    assert tripped == EXPECTED_FAULT_TRIPS[story], [str(p) for p in faulty_problems]


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
    """The eight answer rows and eight fault records agree with the committed bills (labels.*)."""
    on_disk = {name: pl.read_parquet(_CLAIMS_DIR / name) for name in TABLE_FILES}
    clean_on_disk = {TABLE_ANADATA: pl.read_parquet(_CLEAN_DIR / TABLE_ANADATA)}
    registry = json.loads(_REGISTRY_FILE.read_text(encoding="utf-8"))
    assert len(registry["faults"]) == 8
    assert on_disk[TABLE_ANSWERS].height == 8
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
    assert sorted(p.claim_id for p in labels) == sorted(CLAIM.values())  # one row per claim
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
    assert len(faults) == 8
    assert {fault["claim_id"]: fault["billed_clean_try"] for fault in faults} == totals


# --- 3. the mutation cases -------------------------------------------------------------------------


def faulty_data(built, anadata) -> Data:
    """The committed faulty bills with a copy of their registry: the base of the `labels.*` cases."""
    return Data(dict(built.tables), anadata, copy.deepcopy(built.registry))


def fresh(case: Case, built, twins, anadata) -> Data:
    """A new working copy for a case: the clean twins, or (`on_faulty`) the faulty bills + registry."""
    return faulty_data(built, anadata) if case.on_faulty else Data(dict(twins), anadata)


@pytest.mark.parametrize("case", CASES, ids=lambda c: c.name)
def test_a_defect_trips_its_own_check_and_what_it_must(
    case: Case, built, twins, anadata, context
) -> None:
    before = fresh(case, built, twins, anadata).problems(context)
    if case.on_faulty:
        # the faulty bills trip the pinned ids already; the case may add only its own finding
        assert {p.check for p in before} == set().union(*EXPECTED_FAULT_TRIPS.values())
    else:
        assert before == [], "the base (the eight clean twins) must be clean"
    broken = fresh(case, built, twins, anadata)
    case.mutate(broken)
    found = [p for p in broken.problems(context) if p not in before]
    assert only_ids(found) == {case.check, *case.also}, [str(p) for p in found]
    # a mutation touches one claim, and so does what it trips
    assert len({problem.claim_id for problem in found}) == 1, [str(p) for p in found]
    # every finding says where and what, whatever value the defect left empty
    assert all(isinstance(p.where, str) and p.where.startswith("F-") for p in found)
    assert all(isinstance(p.message, str) and p.message for p in found), [str(p) for p in found]
    # and the finding of the target id is the right one: the right place, the right reason
    mine = [p for p in found if p.check == case.check]
    assert any(case.at in p.where and case.says in p.message for p in mine), [str(p) for p in mine]


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


def test_icu_days_count_as_bed_days_and_an_icu_package_does_not_make_a_package_claim(
    twins, anadata, context
) -> None:
    data = Data(dict(twins), anadata)
    # S2's third day billed as an ICU day fee, its fourth as an ICU package
    edit(data, TABLE_PROCEDURES, line(2, "510010", "2026-03-11"), procedure_code="510090")
    edit(
        data,
        TABLE_PROCEDURES,
        line(2, "510010", "2026-03-12"),
        procedure_code="P552001",
        procedure_category="paket",
    )
    for check in ("stay.bed_coverage", PACKAGE):
        assert run_only(data, context, check) == [], check


def test_a_day_bed_line_counts_as_a_bed_day(twins, anadata, context) -> None:
    data = Data(dict(twins), anadata)
    edit(data, TABLE_PROCEDURES, line(2, "510010", "2026-03-11"), procedure_code="510120")
    assert run_only(data, context, "stay.bed_coverage") == []


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
        "appendicitis_lap_appendectomy_package": ["appendicitis_lap_appendectomy_itemized"]
    }
    data = Data(dict(built.tables), anadata)
    assert data.problems(context, only="fit.pathway_membership") == []


# --- 4b. slice E2: the meaning of the checks, beyond the mutation cases -----------------------------


def test_the_flag_columns_are_the_boolean_columns_but_the_two_structural_ones(twins) -> None:
    schema = twins[TABLE_MATERIALS].schema
    booleans = [column for column, dtype in schema.items() if dtype == pl.Boolean]
    assert set(STRUCTURAL_FLAGS) | set(REGISTRATION_FLAGS) <= set(booleans)
    flags = [column for column in booleans if column not in STRUCTURAL_FLAGS]
    assert len(flags) == 85, "a new Boolean column of material_claim_lines needs a healthy value"
    assert STRUCTURAL_FLAGS == ("is_bundled", "requires_pre_auth")
    assert REGISTRATION_FLAGS == ("titubb_registered", "uts_registered")


def test_missing_flags_and_structural_flags_are_healthy(twins, anadata, context) -> None:
    data = Data(dict(twins), anadata)
    edit(
        data,
        TABLE_MATERIALS,
        mat(1),
        is_bundled=True,  # structural: what the line is, not a compliance flag
        requires_pre_auth=True,
        titubb_registered=None,  # a missing flag is not a stray one
        uts_registered=None,
        foreign_facility=None,
        medical_necessity_board_report=False,
    )
    assert data.problems(context, only="material.stray_flag") == []


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
    """The CT angiography R101450 cost 1034.75 until 2025-12-31 and 1138.22 from 2026-01-01."""
    history = pl.read_parquet(
        _REPO / "data/gazette/curated/ek2b_catalog_history.parquet",
        columns=["code", "valid_from", "valid_to", "price_try"],
    ).filter(pl.col("code") == "R101450")

    def price_on(day: str) -> list[float]:
        in_force = (pl.col("valid_from") <= day) & (
            pl.col("valid_to").is_null() | (pl.col("valid_to") >= day)
        )
        return history.filter(in_force)["price_try"].unique().to_list()

    assert price_on("2025-12-31") == [1034.75]
    assert price_on("2026-01-01") == [1138.22]
    for day, trips in {"2025-12-31": False, "2026-01-01": True}.items():
        data = Data(dict(twins), anadata)
        edit(data, TABLE_PROCEDURES, line(7, "R101450"), procedure_date=day)
        reprice(data, TABLE_PROCEDURES, line(7, "R101450"), 1034.75)
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
    ek3f1 = context.ek3f1
    assert ek3f1["sut_code"].n_unique() == ek3f1.height > 300
    assert ek3f1["price_try"].null_count() == 0


def test_every_cent_a_list_price_can_be_billed_at_fits_and_no_other_does(context) -> None:
    """The 345 EK-3/F-1 prices: 141 have more than six decimals, 3 sit a float hair below a tie.

    AP1090 is 15076.214999999998 (meant as 15076.215): `Decimal(str(price))` half up bills 15076.21,
    an exact half up 15076.22, and both are the list price to the cent. The module's whole-number
    rule is compared with a Decimal reference on every price and seven neighbouring cents.
    """
    prices = context.ek3f1["price_try"].to_list()
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
    edit_fault(data, 3, relabel=False, amount_try="928.10")
    row_problem, entry_problem = _answer_rows_of(data, context)  # sorted by where: rows, registry
    assert entry_problem.where == f"{CLAIM[3]} registry faults[2]"
    assert entry_problem.message == (
        "the entry is no valid fault record: revenue_uplift amount_try '928.10' must equal "
        "billed_clean_try - billed_faulty_try (928.09)"
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
    assert len(found) == 1 + 8
    assert data.problems(context, only=AMOUNTS) == []  # nothing to compare


def test_a_fault_entry_that_is_not_even_a_mapping_or_has_no_claim_is_reported(
    built, anadata, context
) -> None:
    data = faulty_data(built, anadata)
    data.registry["faults"].append("not a record")
    data.registry["faults"].append({"fault_id": "F_X", "billed_faulty_try": None})
    found = data.problems(context, only=sorted(REGISTRY_CHECKS))
    wheres = [p.where for p in found]
    assert "(no-claim-id) registry faults[8]" in wheres
    assert "(no-claim-id) registry faults[9]" in wheres
    assert all(p.message and "None" not in p.message for p in found)
    # the nine-th entry is a mapping without values: labels.amounts names each missing value
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
    assert "expected_savings_try is 4122.07" in problem.message
    assert "the fault record gives 4122.06" in problem.message


def test_every_answer_row_names_the_fault_of_its_record_and_none_is_payable(built) -> None:
    answers = built.tables[TABLE_ANSWERS]
    assert answers["expected_payable_try"].null_count() == answers.height == 8
    assert [e["claim_id"] for e in built.registry["faults"]] == answers["claim_id"].to_list()


# --- 5. the judgment tables --------------------------------------------------------------------------


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


def test_the_age_gates_are_the_table_of_the_brief() -> None:
    table = [(g.source, g.words, g.min_age, g.max_age, g.sex) for g in AGE_GATES]
    assert table == [
        ("icd", ("P",), None, 1, None),
        ("icd", ("O",), 10, 55, "F"),
        ("icd", ("Z38",), None, 1, None),
        ("name", ("yenidoğan", "neonatal", "prematüre"), None, 1, None),
        ("name", ("pediatrik", "çocuk"), None, 17, None),
        ("name", ("erişkin",), 18, None, None),
    ]
    assert [g.limits for g in AGE_GATES][:2] == ["age at most 1", "sex F, age 10..55"]


def test_the_sex_word_lists_are_the_judgment_of_the_brief() -> None:
    assert set(MALE_ONLY_WORDS) == {
        "prostat", "penil", "penis", "penektomi", "testis", "orşiektomi", "orsiektomi",
        "skrotum", "hidrosel", "varikosel", "vazektomi", "sünnet", "sunnet", "epididim",
    }  # fmt: skip
    assert set(FEMALE_ONLY_WORDS) == {
        "uterus", "rahim", "histerektomi", "histeroskopi", "vajin", "vulva", "serviks",
        "ooferektomi", "salpenjektomi", "jinekolojik", "gebelik", "doğum", "sezaryen",
        "inseminasyon", "kürtaj",
    }  # fmt: skip


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
