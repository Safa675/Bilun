"""Contract, mutation and hygiene tests for `scripts/synthetic/cohort/plausibility.py` (plan D5, slice E1).

Every id in `plausibility.CHECKS` has at least one in-memory mutation case below. A case seeds ONE
defect into a copy of the tables of the eight clean twins (the showcase bills without their fault)
and proves that exactly the target id trips, plus the ids in `also` that the defect unavoidably
trips too (each one is explained next to its case). Nothing here writes a file.

The contract:
1. the eight clean twins raise no problem;
2. the committed faulty bills trip exactly the pinned ids (`EXPECTED_FAULT_TRIPS`);
3. every id has an implementation, a short meaning and a mutation case;
4. the committed Parquet files give the same result as the in-memory tables.
"""

from __future__ import annotations

import ast
from collections.abc import Callable
import dataclasses
from pathlib import Path
import re

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
    FEMALE_ONLY_WORDS,
    MALE_ONLY_WORDS,
    NAME_EXCEPTIONS,
    SURGICAL_SPECIALTY_CODES,
    TABLE_ANADATA,
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
    _fold,
    check_plausibility,
    fold_text,
    run_all,
)
from scripts.synthetic.cohort.tables import TABLE_FILES, build_tables

pytestmark = pytest.mark.unit

_REPO = Path(__file__).resolve().parents[3]
_MODULE = _REPO / "scripts/synthetic/cohort/plausibility.py"
_CLAIMS_DIR = _REPO / "data/synthetic/showcase/sut/claims"
_CLEAN_DIR = _REPO / "data/synthetic/showcase/sut/clean"

# The ids a mutation case may name; written out so a typo in a case fails at collection time.
PATHWAY = "fit.pathway_membership"
DATES = "stay.dates_in_window"
PAIRING = "anaesthesia.operation_pairing"
PACKAGE = "package.mode"

# What the committed faulty bill of each story trips (checked by the orchestrator with a prototype).
# S4's missing companion, S6's dropped diagnosis and S8's wrong ratio are invisible to plausibility
# (only the engine sees them); E2 adds the S5 flag.
EXPECTED_FAULT_TRIPS: dict[str, set[str]] = {
    "S1": {"package.mode"},
    "S2": {"stay.bed_coverage"},
    "S3": {"anaesthesia.operation_pairing"},
    "S4": set(),
    "S5": set(),
    "S6": set(),
    "S7": {"bill.performed_billed"},
    "S8": set(),
}

# The ids of slice E1; later slices add their own to CHECKS.
E1_CHECKS = {
    "patient.icd_valid", "patient.sex_gate", "patient.age_gate", "patient.age_arithmetic",
    "fit.pathway_membership", "fit.operation_department", "fit.operation_setting",
    "fit.visit_code", "stay.bed_coverage", "stay.companion_coverage", "stay.dates_in_window",
    "bill.performed_billed", "package.mode", "anaesthesia.operation_pairing", "anaesthesia.group",
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
    """A working copy of the claims tables and of anadata_clean; DataFrames are never mutated."""

    tables: dict[str, pl.DataFrame]
    anadata: pl.DataFrame

    def problems(self, context: PlausibilityContext, only=None) -> list[Problem]:
        return check_plausibility(
            self.tables, {TABLE_ANADATA: self.anadata}, context=context, only=only
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


def drop(data: Data, table: str, where: pl.Expr) -> None:
    """Delete the rows `where` selects (at least one must match)."""
    frame = data.tables[table]
    assert frame.filter(where).height > 0, f"the mutation selects no row of {table}"
    data.tables[table] = frame.filter(~where)


def add_row(data: Data, table: str, template: pl.Expr, **values: object) -> None:
    """Append a copy of the first row `template` selects, with `values` set."""
    frame = data.tables[table]
    seed = frame.filter(template).head(1)
    assert seed.height == 1, f"no template row in {table}"
    row = seed.with_columns([_value(frame, c, v).alias(c) for c, v in values.items()])
    data.tables[table] = pl.concat([frame, row])


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
    edit(data, TABLE_PROCEDURES, line(story, old), procedure_code=new)


def rename(data: Data, story: int, code: str, name: str) -> None:
    edit(data, TABLE_PROCEDURES, line(story, code), procedure_name=name)


def only_ids(found: list[Problem]) -> set[str]:
    return {problem.check for problem in found}


# --- the mutation cases ---------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class Case:
    check: str
    mutate: Callable[[Data], None]
    also: tuple[str, ...] = ()
    label: str = ""

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


def _extra_material(d: Data) -> None:
    # S5's first material, billed on S3's decompression
    add_row(
        d,
        TABLE_MATERIALS,
        of(5),
        material_line_id=material_line_id(CLAIM[3], 1),
        claim_id=CLAIM[3],
        patient_id=PATIENT[3],
        procedure_line_id=line_id_of(d, 3, "615931"),
        material_date="2026-08-18",
    )


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
]


# --- 1. the registry -------------------------------------------------------------------------------


def test_every_check_id_has_a_function_a_short_meaning_and_a_mutation_case() -> None:
    assert set(CHECK_FUNCTIONS) == set(CHECKS)
    assert {case.check for case in CASES} == set(CHECKS)
    for check, meaning in CHECKS.items():
        assert 0 < len(meaning) <= 120, f"{check}: the meaning has {len(meaning)} characters"
    assert E1_CHECKS <= set(CHECKS)
    assert all(re.fullmatch(r"[a-z]+\.[a-z_]+", check) for check in CHECKS)


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
    return check_plausibility(built.tables, {TABLE_ANADATA: anadata}, context=context)


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
    from_files = check_plausibility(on_disk, clean_on_disk, context=context)
    from_memory = check_plausibility(built.tables, {TABLE_ANADATA: anadata}, context=context)
    assert from_files == from_memory
    assert {p.check for p in from_files} == set().union(*EXPECTED_FAULT_TRIPS.values())


# --- 3. the mutation cases -------------------------------------------------------------------------


@pytest.mark.parametrize("case", CASES, ids=lambda c: c.name)
def test_a_defect_trips_its_own_check_and_what_it_must(case: Case, twins, anadata, context) -> None:
    base = Data(dict(twins), anadata)
    assert base.problems(context) == [], "the base (the eight clean twins) must be clean"
    broken = Data(dict(twins), anadata)
    case.mutate(broken)
    found = broken.problems(context)
    assert only_ids(found) == {case.check, *case.also}, [str(p) for p in found]
    # a mutation touches one claim, and so does what it trips
    assert len({problem.claim_id for problem in found}) == 1, [str(p) for p in found]
    # every finding says where and what, whatever value the defect left empty
    assert all(isinstance(p.where, str) and p.where.startswith("F-") for p in found)
    assert all(isinstance(p.message, str) and p.message for p in found), [str(p) for p in found]


def test_a_missing_value_is_named_in_the_message_not_dropped(twins, anadata, context) -> None:
    data = Data(dict(twins), anadata)
    edit(data, TABLE_PROCEDURES, line(3, "615931"), procedure_specialty_code=None)
    (problem,) = data.problems(context, only="fit.operation_department")
    assert problem.message.endswith(
        "has the specialty (none), which is not a surgical EK-2A branch"
    )


def test_the_mutations_leave_the_clean_tables_untouched(twins, anadata, context) -> None:
    before = {name: frame.clone() for name, frame in twins.items()}
    for case in CASES:
        case.mutate(Data(dict(twins), anadata))
    assert all(twins[name].equals(frame) for name, frame in before.items())


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


def test_the_module_imports_no_pandas_and_no_engine() -> None:
    imported: list[str] = []
    for node in ast.walk(_module_tree()):
        if isinstance(node, ast.Import):
            imported += [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.append(node.module)
    assert "polars" in imported
    for module in imported:
        assert not module.startswith("pandas"), module
        assert not module.startswith("reports"), module
        assert "prose_rules" not in module, module
        assert "domain.billing" not in module, module


def test_the_module_names_no_anonymised_identifier() -> None:
    needle = "ANON" + "_"
    assert needle not in _MODULE.read_text(encoding="utf-8").upper()


def test_the_module_writes_no_file() -> None:
    """The checks only read: no table, no report, no cache is written."""
    text = _MODULE.read_text(encoding="utf-8")
    assert "write_parquet" not in text
    assert "write_csv" not in text
    assert ".write_text(" not in text
