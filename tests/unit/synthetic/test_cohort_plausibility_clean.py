"""Contract, mutation and hygiene tests for `scripts/synthetic/cohort/plausibility_clean.py` (plan D5, slice E3).

Every id in `plausibility_clean.CHECKS` has at least one in-memory mutation case below. A case seeds
ONE defect into a copy of the committed showcase tables (the clean tables and the claims tables) and
proves that exactly the target id trips, plus the ids in `also` that the defect unavoidably trips too
(each one is explained next to its case), that the target gives the expected number of findings, and
that they say WHERE (the patient, the table and the key) and WHAT. Nothing here writes a file.

The contract:
1. the committed clean tables raise no problem with the committed claims tables;
2. with the claims tables of the eight clean twins, ten ids still raise none; the two ids that compare
   a clean table with the bill (`lab.result_sets_match_bill`, `rx.matches_billed_line`) raise exactly
   the lines that story S1's fault adds (the clean tables are built from the faulty bills), and the
   twin world (twin claims, clean tables without those lines) is clean for all ids;
3. every id has an implementation, a short meaning and a mutation case;
4. the committed Parquet files give the same result as the tables in memory;
5. the module imports neither the generator it tests nor the claims checks.
"""

from __future__ import annotations

import ast
from collections.abc import Callable
import dataclasses
from datetime import datetime
import math
from pathlib import Path
import re

import polars as pl
import pytest

from scripts.synthetic.cohort import build_showcase, plausibility_clean
from scripts.synthetic.cohort.ids import episode_id, patient_id
from scripts.synthetic.cohort.plausibility_clean import (
    BLOOD_GAS_CODE,
    CHECK_FUNCTIONS,
    CHECKS,
    CREATININE_CODE,
    DIFFERENTIAL_PARAMETERS,
    DOSE_UNITS,
    ENGLISH_UNITS,
    HEMOGRAM_CODE,
    LAB_HARD_BOUNDS,
    LAB_REFERENCE_PATH,
    LAB_STRIP_PARAMETERS,
    PARENTERAL_ROUTES,
    REQUIRED_RECETE_COLUMNS,
    ROUTE_WORDS,
    ROUTES,
    SEX_CODES,
    STRIP_GRADES,
    TABLE_ANADATA,
    TABLE_DRUGS,
    TABLE_HEADERS,
    TABLE_LAB,
    TABLE_PROCEDURES,
    TABLE_RECETE,
    VITALS_BOUNDS,
    CleanPlausibilityContext,
    CleanPlausibilityError,
    Problem,
    check_clean_plausibility,
    fold_text,
)
from scripts.synthetic.cohort.tables import TABLE_FILES, build_tables

pytestmark = pytest.mark.unit

_REPO = Path(__file__).resolve().parents[3]
_MODULE = _REPO / "scripts/synthetic/cohort/plausibility_clean.py"
_CLAIMS_DIR = _REPO / "data/synthetic/showcase/sut/claims"
_CLEAN_DIR = _REPO / "data/synthetic/showcase/sut/clean"
_CLEAN_FILES = (TABLE_ANADATA, TABLE_LAB, TABLE_RECETE)

# The ids a mutation case may name; written out so a typo in a case fails at collection time.
VALUE_BOUNDS = "lab.value_bounds"
HEMOGRAM = "lab.hemogram_relations"
FLAG_AND_LIMITS = "lab.flag_and_limits"
UNIT = "lab.unit_matches_reference"
SETS = "lab.result_sets_match_bill"
BLOOD_GAS = "lab.blood_gas_relations"
EGFR_RELATION = "lab.egfr_relation"
MATCHES = "rx.matches_billed_line"
ROUTE = "rx.route_vs_product"
DOSE = "rx.dose_unit"
REQUIRED = "rx.required_fields"
VITALS = "ana.vitals_bounds"

STORIES = tuple(range(1, 9))
PATIENT = {n: patient_id(n) for n in STORIES}
EPISODE = {n: episode_id(PATIENT[n], 1) for n in STORIES}

# The schema of lab_clean, written out so that the one-row frames of the boundary tests have it.
LAB_SCHEMA = {
    "HASTA_ID": pl.String,
    "basvuru_id": pl.String,
    "SUB_CODE": pl.String,
    "parametre": pl.String,
    "sonuc_sayisal": pl.Float64,
    "sonuc_nitel": pl.String,
    "birim": pl.String,
    "ref_alt": pl.Float64,
    "ref_ust": pl.Float64,
    "anormal_mi": pl.Boolean,
    "organ_sistemi": pl.String,
    "kohort": pl.String,
    "donem": pl.String,
    "tarih": pl.Datetime("ns"),
}


# --- fixtures -----------------------------------------------------------------------------------


@pytest.fixture(scope="module")
def built():
    return build_showcase()


@pytest.fixture(scope="module")
def context() -> CleanPlausibilityContext:
    return CleanPlausibilityContext()


@pytest.fixture(scope="module")
def twins(built) -> dict[str, pl.DataFrame]:
    """The claims tables of the eight clean twins: the showcase bills without their fault."""
    return build_tables(
        built.clean_claims,
        answer_rows=(),
        copay_profiles=built.copay_profiles,
        medula_events=(),
    )


@pytest.fixture(scope="module")
def clean(built) -> dict[str, pl.DataFrame]:
    return dict(built.clean_tables)


# --- mutation primitives (Polars, on copies) ----------------------------------------------------


@dataclasses.dataclass
class Data:
    """A working copy of the claims tables and the clean tables; DataFrames are never mutated."""

    tables: dict[str, pl.DataFrame]
    clean: dict[str, pl.DataFrame]

    def problems(self, context: CleanPlausibilityContext, only=None) -> list[Problem]:
        return check_clean_plausibility(self.tables, self.clean, context=context, only=only)

    def store(self, table: str) -> dict[str, pl.DataFrame]:
        return self.clean if table.endswith("_clean.parquet") else self.tables


def fresh(built, clean) -> Data:
    """The committed faulty claims tables with the committed clean tables, ready to be mutated."""
    return Data(dict(built.tables), dict(clean))


def day(iso: str) -> datetime:
    return datetime.fromisoformat(iso)


def _value(frame: pl.DataFrame, column: str, value: object) -> pl.Expr:
    return value if isinstance(value, pl.Expr) else pl.lit(value, dtype=frame.schema[column])


def edit(data: Data, table: str, where: pl.Expr, **changes: object) -> None:
    """Set columns on the rows `where` selects (at least one must match)."""
    store = data.store(table)
    frame = store[table]
    assert frame.filter(where).height > 0, f"the mutation selects no row of {table}"
    store[table] = frame.with_columns(
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
    store = data.store(table)
    frame = store[table]
    assert frame.filter(where).height > 0, f"the mutation selects no row of {table}"
    store[table] = frame.filter(~where)


def add_row(data: Data, table: str, template: pl.Expr, **values: object) -> None:
    """Append a copy of the first row `template` selects, with `values` set."""
    store = data.store(table)
    frame = store[table]
    seed = frame.filter(template).head(1)
    assert seed.height == 1, f"no template row in {table}"
    row = seed.with_columns([_value(frame, c, v).alias(c) for c, v in values.items()])
    store[table] = pl.concat([frame, row])


def lab(
    story: int,
    on: str | None = None,
    code: str | None = None,
    parameter: str | None = None,
) -> pl.Expr:
    """The lab rows of a story's patient, optionally of one day, one code and one parameter."""
    expr = pl.col("HASTA_ID") == PATIENT[story]
    if on is not None:
        expr = expr & (pl.col("tarih") == day(on))
    if code is not None:
        expr = expr & (pl.col("SUB_CODE") == code)
    if parameter is not None:
        expr = expr & (pl.col("parametre") == parameter)
    return expr


def rx(story: int, name: str) -> pl.Expr:
    """The prescription row of a story's patient whose billed name starts with `name`."""
    return (pl.col("HASTA_ID") == PATIENT[story]) & pl.col("ilac_adi").str.starts_with(name)


def patient_row(story: int) -> pl.Expr:
    return pl.col("HASTA_ID") == PATIENT[story]


def lab_where(story: int, on: str, code: str, parameter: str | None = None) -> str:
    """`Problem.where` of a finding about a result set, or (with `parameter`) about one row of it."""
    text = f"{PATIENT[story]} lab_clean[{EPISODE[story]}|{on}|{code}"
    return f"{text}|{parameter}]" if parameter else f"{text}]"


def rx_where(story: int, on: str) -> str:
    """The start of `Problem.where` of a finding about the prescription rows of a day."""
    return f"{PATIENT[story]} recete_clean[{EPISODE[story]}|{on}|"


def only_ids(found: list[Problem]) -> set[str]:
    return {problem.check for problem in found}


def lab_frame(*rows: dict) -> pl.DataFrame:
    """A small lab_clean table: a CRP row of patient 2 on 2026-03-09, with `rows` laid over it."""
    base = {
        "HASTA_ID": PATIENT[2],
        "basvuru_id": EPISODE[2],
        "SUB_CODE": "L101850",
        "parametre": "CRP (kantitatif)",
        "sonuc_sayisal": 10.0,
        "sonuc_nitel": None,
        "birim": "mg/L",
        "ref_alt": 0.0,
        "ref_ust": 5.0,
        "anormal_mi": True,
        "organ_sistemi": "Biyokimya",
        "kohort": "showcase",
        "donem": "2026",
        "tarih": day("2026-03-09"),
    }
    return pl.DataFrame([{**base, **row} for row in rows], schema=LAB_SCHEMA)


def run_lab(frame: pl.DataFrame, check: str, context: CleanPlausibilityContext) -> list[Problem]:
    """One check over a lab table alone (the value checks read nothing else)."""
    return check_clean_plausibility({}, {TABLE_LAB: frame}, context=context, only=check)


# --- the mutation cases ---------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class Case:
    """One defect and what must be seen of it.

    `where` is a fragment that every finding of the target id contains, `says` the fragments that the
    messages of the target id contain, `n` how many findings the target id gives, `also` the other ids
    the defect unavoidably trips, `patients` how many patients the findings name.
    """

    check: str
    mutate: Callable[[Data], None]
    where: str
    says: tuple[str, ...] | str = ()
    n: int = 1
    also: tuple[str, ...] = ()
    patients: int = 1
    label: str = ""

    @property
    def name(self) -> str:
        return f"{self.check}-{self.label}" if self.label else self.check

    @property
    def fragments(self) -> tuple[str, ...]:
        return (self.says,) if isinstance(self.says, str) else self.says


DAY_2 = "2026-03-09"  # the first lab day of patient 2 (S2): most of the cases change a row of it
GLUCOSE_CODE = "L102890"  # a numeric row with the limits 70..100 and the unit mg/dL
HEMOGRAM_2 = lab_where(2, DAY_2, HEMOGRAM_CODE)  # patient 2's hemogram of 2026-03-09
GAS_2 = lab_where(2, DAY_2, BLOOD_GAS_CODE)  # patient 2's arterial blood gas of 2026-03-09
EGFR_2 = lab_where(2, DAY_2, CREATININE_CODE)  # patient 2's creatinine set of 2026-03-09
HGB, RBC = "HGB (Hemoglobin)", "RBC (Eritrosit)"
EGFR = "eGFR (CKD-EPI 2021, hesaplanan)"
GLUCOSE_2 = lab_where(2, DAY_2, GLUCOSE_CODE, "Glukoz")
IESEF = "IESEF 1 G IV ENJEKSIYONLUK COZELTI TOZU"
PARTEMOL = "PARTEMOL 1 G/100 ML INF ICIN COZ ICEREN 1 FLK"
VITALS_2 = f"{PATIENT[2]} anadata_clean[{EPISODE[2]}]"


def _lab_value(story, on, code, parameter, **changes) -> Callable[[Data], None]:
    """Change columns of one lab row."""
    return lambda d: edit(d, TABLE_LAB, lab(story, on, code, parameter), **changes)


def _vital(story: int, **changes) -> Callable[[Data], None]:
    return lambda d: edit(d, TABLE_ANADATA, patient_row(story), **changes)


def _recete(story: int, name: str, **changes) -> Callable[[Data], None]:
    return lambda d: edit(d, TABLE_RECETE, rx(story, name), **changes)


def _null_column(column: str) -> Callable[[Data], None]:
    return lambda d: edit(d, TABLE_RECETE, patient_row(7), **{column: None})


def _blank_column(column: str) -> Callable[[Data], None]:
    return lambda d: edit(d, TABLE_RECETE, patient_row(7), **{column: "  "})


# S7's single prescription row (PARTEMOL, 1 flakon) carries the required-field cases; a null in a
# column that the other checks read trips them too (each `also` says which).
_REQUIRED_START = f"{PATIENT[7]} recete_clean[{EPISODE[7]}|"
REQUIRED_NULL_CASES = [
    Case(
        REQUIRED,
        _null_column(column),
        where=where,
        says=f"missing required column(s): {column}",
        also=also,
        patients=patients,
        label=f"null_{column}",
    )
    for column, where, also, patients in (
        ("HASTA_ID", "(none) recete_clean[", (MATCHES,), 2),
        ("RECETE_TARIH", _REQUIRED_START, (MATCHES,), 1),
        ("RF_EPISODE", f"{PATIENT[7]} recete_clean[(none)|", (MATCHES,), 1),
        ("ilac_adi", _REQUIRED_START, (MATCHES,), 1),
        ("ilac_adi_ham", _REQUIRED_START, (), 1),
        ("dozaj_ham", _REQUIRED_START, (DOSE,), 1),
        ("verilis_yolu", _REQUIRED_START, (ROUTE,), 1),
        ("miktar", _REQUIRED_START, (MATCHES, DOSE), 1),
        ("kohort", _REQUIRED_START, (), 1),
        ("donem", _REQUIRED_START, (), 1),
    )
]


def _second_troponin_removed(d: Data) -> None:
    # S7's two troponin I sets share their key (patient, episode, day, code); the second has 7.2
    drop(d, TABLE_LAB, lab(7, "2026-02-19", "L107360") & (pl.col("sonuc_sayisal") == 7.2))


def _package_claim_with_labs(d: Data) -> None:
    # S5 is a package bill: a CRP result copied to it, dated inside its stay
    add_row(
        d,
        TABLE_LAB,
        lab(2, "2026-03-12", "L101850"),
        HASTA_ID=PATIENT[5],
        basvuru_id=EPISODE[5],
        tarih=day("2026-09-04"),
    )


def _wrong_episode_on_a_set(d: Data) -> None:
    edit(d, TABLE_LAB, lab(3, "2026-08-19", HEMOGRAM_CODE), basvuru_id="B-SENTETIK-HASTA-0003-002")


CASES: list[Case] = [
    # --- lab.value_bounds. The flags of the changed rows are kept consistent with the new values.
    Case(
        VALUE_BOUNDS,
        _lab_value(2, DAY_2, GLUCOSE_CODE, "Glukoz", sonuc_sayisal=-5.0, anormal_mi=True),
        where=GLUCOSE_2,
        says=("Glukoz = -5.0", "outside the hard interval 20.0..1500.0"),
        label="negative_glucose",
    ),
    Case(
        VALUE_BOUNDS,
        _lab_value(4, "2026-05-11", "L106150", "Potasyum", sonuc_sayisal=40.0, anormal_mi=True),
        where=lab_where(4, "2026-05-11", "L106150", "Potasyum"),
        says=("Potasyum = 40.0", "outside the hard interval 1.5..9.0"),
        label="potassium_40",
    ),
    Case(
        VALUE_BOUNDS,
        _lab_value(2, DAY_2, GLUCOSE_CODE, "Glukoz", parametre="Glukoz (serum)"),
        where=lab_where(2, DAY_2, GLUCOSE_CODE, "Glukoz (serum)"),
        says="is not a parameter of LAB_HARD_BOUNDS",
        also=(SETS,),  # the set has lost its glucose and holds a row the reference does not list
        label="unknown_parameter",
    ),
    Case(
        VALUE_BOUNDS,
        _lab_value(2, DAY_2, "L107420", "Üre", sonuc_sayisal=float("nan")),
        where=lab_where(2, DAY_2, "L107420", "Üre"),
        says=("Üre = NaN", "is NaN"),
        label="nan",
    ),
    Case(
        VALUE_BOUNDS,
        _lab_value(2, DAY_2, "L107420", "Üre", sonuc_sayisal=float("inf")),
        where=lab_where(2, DAY_2, "L107420", "Üre"),
        says=("Üre = inf", "is infinite"),
        label="infinity",
    ),
    Case(
        VALUE_BOUNDS,
        _lab_value(2, DAY_2, "L107420", "Üre", sonuc_sayisal=None),
        where=lab_where(2, DAY_2, "L107420", "Üre"),
        says=("Üre = (none)", "has no numeric result"),
        label="no_result",
    ),
    Case(
        VALUE_BOUNDS,
        # S1's neutrophils 11.06 become 15.0, above the WBC 14.1 of the set (flag stays true)
        _lab_value(1, "2026-07-15", HEMOGRAM_CODE, "NEU# (Nötrofil)", sonuc_sayisal=15.0),
        where=lab_where(1, "2026-07-15", HEMOGRAM_CODE, "NEU# (Nötrofil)"),
        says="is above the WBC 14.1 of its result set",
        also=(HEMOGRAM,),  # a count above the WBC cannot leave the differential at the WBC
        label="count_above_the_wbc",
    ),
    Case(
        VALUE_BOUNDS,
        _lab_value(4, "2026-05-11", "L107010", "Protein (strip)", sonuc_nitel="Orta"),
        where=lab_where(4, "2026-05-11", "L107010", "Protein (strip)"),
        says="has the grade Orta, which is not one of Negatif, Eser, +, ++, +++, ++++, Pozitif",
        label="strip_grade_not_in_the_list",
    ),
    Case(
        VALUE_BOUNDS,
        _lab_value(4, "2026-05-11", "L107010", "Glukoz (strip)", sonuc_nitel=None),
        where=lab_where(4, "2026-05-11", "L107010", "Glukoz (strip)"),
        says="has no grade",
        label="strip_without_a_grade",
    ),
    # --- lab.hemogram_relations (S2's hemogram of 2026-03-09: WBC 16.0, differential 12.94 2.15
    # 0.82 0.02 0.07, RBC 5.1, HGB 15.2, HCT 45.0, MCV 89, MCH 30). Each change stays inside the
    # limits of the row, so its flag does not change.
    Case(
        HEMOGRAM,
        _lab_value(2, DAY_2, HEMOGRAM_CODE, "LYM# (Lenfosit)", sonuc_sayisal=3.0),
        where=HEMOGRAM_2,
        says="the five differential counts sum to 16.85 but the WBC is 16.0",
        label="one_differential_count_changed",
    ),
    Case(
        HEMOGRAM,
        _lab_value(2, DAY_2, HEMOGRAM_CODE, "WBC (Lökosit)", sonuc_sayisal=13.5),
        where=HEMOGRAM_2,
        says="the five differential counts sum to 16.0 but the WBC is 13.5",
        label="wbc_changed_alone",
    ),
    Case(
        HEMOGRAM,
        _lab_value(2, DAY_2, HEMOGRAM_CODE, HGB, sonuc_sayisal=17.0),
        where=HEMOGRAM_2,
        says=("HCT 45.0 / HGB 17.0 = 2.647", "RBC 5.1 x MCH 30.0 / 10 = 15.3 but HGB is 17.0"),
        n=2,  # HCT/HGB falls below 2.74 and the red-cell index no longer gives the HGB
        label="hgb_changed_alone",
    ),
    Case(
        HEMOGRAM,
        _lab_value(2, DAY_2, HEMOGRAM_CODE, "HCT (Hematokrit)", sonuc_sayisal=41.0),
        where=HEMOGRAM_2,
        says=("HCT 41.0 / HGB 15.2", "RBC 5.1 x MCV 89.0 / 10 = 45.39 but HCT is 41.0"),
        n=2,
        label="hct_changed_alone",
    ),
    Case(
        HEMOGRAM,
        _lab_value(2, DAY_2, HEMOGRAM_CODE, RBC, sonuc_sayisal=4.6),
        where=HEMOGRAM_2,
        says=("RBC 4.6 x MCV 89.0", "RBC 4.6 x MCH 30.0"),
        n=2,
        label="rbc_changed_alone",
    ),
    Case(
        HEMOGRAM,
        _lab_value(2, DAY_2, HEMOGRAM_CODE, "MCV", sonuc_sayisal=98.0),
        where=HEMOGRAM_2,
        says="RBC 5.1 x MCV 98.0 / 10 = 49.98 but HCT is 45.0",
        label="mcv_changed_alone",
    ),
    Case(
        HEMOGRAM,
        _lab_value(2, DAY_2, HEMOGRAM_CODE, "MCH", sonuc_sayisal=33.0),
        where=HEMOGRAM_2,
        says="RBC 5.1 x MCH 33.0 / 10 = 16.83 but HGB is 15.2",
        label="mch_changed_alone",
    ),
    # --- lab.flag_and_limits
    Case(
        FLAG_AND_LIMITS,
        _lab_value(2, DAY_2, GLUCOSE_CODE, "Glukoz", anormal_mi=True),
        where=GLUCOSE_2,
        says="anormal_mi is true but the value 89.0 against the limits 70.0..100.0 makes it false",
        label="flipped_flag",
    ),
    Case(
        FLAG_AND_LIMITS,
        # BASO# 0.1 sits exactly on its upper limit 0.1: not abnormal
        _lab_value(4, "2026-05-11", HEMOGRAM_CODE, "BASO# (Bazofil)", anormal_mi=True),
        where=lab_where(4, "2026-05-11", HEMOGRAM_CODE, "BASO# (Bazofil)"),
        says="makes it false",
        label="flag_on_a_value_at_its_upper_limit",
    ),
    Case(
        FLAG_AND_LIMITS,
        _lab_value(2, DAY_2, GLUCOSE_CODE, "Glukoz", anormal_mi=None),
        where=GLUCOSE_2,
        says="anormal_mi is missing",
        label="missing_flag",
    ),
    Case(
        FLAG_AND_LIMITS,
        # S3 is a woman (limits 12.0..15.5): the male limits on her HGB 10.8, flag unchanged
        _lab_value(3, "2026-08-19", HEMOGRAM_CODE, HGB, ref_alt=13.0, ref_ust=17.5),
        where=lab_where(3, "2026-08-19", HEMOGRAM_CODE, HGB),
        says="the limits are 13.0..17.5 but the reference gives 12.0..15.5 for sex K",
        label="male_limits_on_a_woman",
    ),
    Case(
        FLAG_AND_LIMITS,
        # S2 is a man (limits 13.0..17.5): the female limits on his HGB 15.2, flag unchanged
        _lab_value(2, DAY_2, HEMOGRAM_CODE, HGB, ref_alt=12.0, ref_ust=15.5),
        where=lab_where(2, DAY_2, HEMOGRAM_CODE, HGB),
        says="the limits are 12.0..15.5 but the reference gives 13.0..17.5 for sex E",
        label="female_limits_on_a_man",
    ),
    Case(
        FLAG_AND_LIMITS,
        _lab_value(2, DAY_2, CREATININE_CODE, EGFR, ref_ust=200.0),
        where=lab_where(2, DAY_2, CREATININE_CODE, EGFR),
        says="the limits are 60.0..200.0 but the reference gives 60.0..(none)",
        label="upper_limit_on_a_lower_limit_only_row",
    ),
    Case(
        FLAG_AND_LIMITS,
        _lab_value(4, "2026-05-11", "L107010", "Protein (strip)", anormal_mi=False),
        where=lab_where(4, "2026-05-11", "L107010", "Protein (strip)"),
        says="the grade Eser makes anormal_mi true, not false",
        label="strip_flag_false_on_a_trace",
    ),
    Case(
        FLAG_AND_LIMITS,
        _lab_value(4, "2026-05-11", "L107010", "Glukoz (strip)", anormal_mi=True),
        where=lab_where(4, "2026-05-11", "L107010", "Glukoz (strip)"),
        says="the grade Negatif makes anormal_mi false, not true",
        label="strip_flag_true_on_a_negative",
    ),
    Case(
        FLAG_AND_LIMITS,
        _lab_value(4, "2026-05-11", "L107010", "Keton (strip)", sonuc_sayisal=1.0),
        where=lab_where(4, "2026-05-11", "L107010", "Keton (strip)"),
        says="the strip row carries the number 1.0",
        label="number_on_a_strip_row",
    ),
    Case(
        FLAG_AND_LIMITS,
        _lab_value(4, "2026-05-11", "L107010", "Nitrit (strip)", ref_alt=0.0),
        where=lab_where(4, "2026-05-11", "L107010", "Nitrit (strip)"),
        says="the limits are 0.0..(none) but the reference gives (none)..(none)",
        label="limit_on_a_strip_row",
    ),
    # --- lab.unit_matches_reference
    Case(
        UNIT,
        _lab_value(2, DAY_2, GLUCOSE_CODE, "Glukoz", birim="mmol/L"),
        where=GLUCOSE_2,
        says="Glukoz has the unit mmol/L, the reference lists mg/dL",
        label="wrong_unit",
    ),
    Case(
        UNIT,
        _lab_value(4, "2026-05-11", "L107010", "Keton (strip)", birim="mg/dL"),
        where=lab_where(4, "2026-05-11", "L107010", "Keton (strip)"),
        says="strip row has the unit mg/dL; a strip result has none",
        label="unit_on_a_strip_row",
    ),
    Case(
        UNIT,
        _lab_value(2, DAY_2, "L107420", "Üre", birim=None),
        where=lab_where(2, DAY_2, "L107420", "Üre"),
        says="Üre has the unit (none), the reference lists mg/dL",
        label="null_unit",
    ),
    Case(
        UNIT,
        _lab_value(2, DAY_2, GLUCOSE_CODE, "Glukoz", birim=""),
        where=GLUCOSE_2,
        says="Glukoz has the unit (empty), the reference lists mg/dL",
        label="empty_unit_where_the_reference_has_one",
    ),
    Case(
        UNIT,
        _lab_value(2, DAY_2, BLOOD_GAS_CODE, "pH", birim="mmHg"),
        where=lab_where(2, DAY_2, BLOOD_GAS_CODE, "pH"),
        says="pH has the unit mmHg, the reference lists (empty)",
        label="unit_where_the_reference_has_none",
    ),
    # --- lab.result_sets_match_bill
    Case(
        SETS,
        lambda d: drop(d, TABLE_LAB, lab(2, DAY_2, HEMOGRAM_CODE, "MPV")),
        where=HEMOGRAM_2,
        says=("14 row(s)", "lists 15", "missing MPV"),
        label="dropped_row",
    ),
    Case(
        SETS,
        # without its SaO2 the gas fits the arterial and the venous variant alike (nine shared
        # parameters); the tie goes to the arterial one, the first in the reference
        lambda d: drop(d, TABLE_LAB, lab(2, DAY_2, BLOOD_GAS_CODE, "SaO2")),
        where=GAS_2,
        says=("9 row(s)", "variant blood_gas_arterial lists 10", "missing SaO2"),
        label="dropped_saturation_row_of_a_gas",
    ),
    Case(
        SETS,
        # a CRP result on a day with no billed CRP line
        lambda d: add_row(d, TABLE_LAB, lab(4, "2026-05-13", "L101850"), tarih=day("2026-05-12")),
        where=lab_where(4, "2026-05-12", "L101850"),
        says="has 1 row(s) and no billed lab line",
        label="extra_result_set",
    ),
    Case(
        SETS,
        # a second CRP result on a day with one billed CRP line
        lambda d: add_row(d, TABLE_LAB, lab(2, "2026-03-12", "L101850")),
        where=f"{PATIENT[2]} lab_clean[{EPISODE[2]}|2026-03-12|L101850#2]",
        says="has 1 row(s) and no billed lab line",
        label="second_set_for_one_billed_line",
    ),
    Case(
        SETS,
        # S3's creatinine set (creatinine and eGFR) moved by a day: no set for the billed line, a set
        # for no billed line
        lambda d: edit(
            d, TABLE_LAB, lab(3, "2026-08-19", CREATININE_CODE), tarih=day("2026-08-20")
        ),
        where=PATIENT[3],
        says=("has no result set in lab_clean", "has 2 row(s) and no billed lab line"),
        n=2,
        label="wrong_date",
    ),
    Case(
        SETS,
        # only S3's eGFR row moved: the set lacks it, and the stray row is a set of its own
        lambda d: edit(
            d, TABLE_LAB, lab(3, "2026-08-19", CREATININE_CODE, EGFR), tarih=day("2026-08-20")
        ),
        where=PATIENT[3],
        says=("missing eGFR (CKD-EPI 2021, hesaplanan)", "has 1 row(s) and no billed lab line"),
        n=2,
        label="wrong_date_on_one_row",
    ),
    Case(
        SETS,
        _wrong_episode_on_a_set,
        where=PATIENT[3],
        says=("has no result set in lab_clean", "B-SENTETIK-HASTA-0003-002"),
        n=2,
        label="wrong_episode_id",
    ),
    Case(
        SETS,
        # S3's creatinine set without a date: no set for the billed line, a set for no billed line,
        # and the two rows' donem cannot be the year of a missing date
        lambda d: edit(d, TABLE_LAB, lab(3, "2026-08-19", CREATININE_CODE), tarih=None),
        where=PATIENT[3],
        says=(
            "has no result set in lab_clean",
            "on (none) (episode B-SENTETIK-HASTA-0003-001) has 2 row(s) and no billed lab line",
            "donem is 2026 but tarih is in (none)",
        ),
        n=4,
        label="no_date",
    ),
    Case(
        SETS,
        _package_claim_with_labs,
        where=lab_where(5, "2026-09-04", "L101850"),
        says="has 1 row(s) and no billed lab line",
        label="rows_for_a_package_claim",
    ),
    Case(
        SETS,
        _second_troponin_removed,
        where=f"{PATIENT[7]} procedure_claim_lines[ISL-",
        says="billed lab line L107360 on 2026-02-19",
        label="second_troponin_set_removed",
    ),
    Case(
        SETS,
        _lab_value(2, DAY_2, GLUCOSE_CODE, "Glukoz", kohort="cohort"),
        where=GLUCOSE_2,
        says="kohort is cohort, not showcase",
        label="wrong_kohort",
    ),
    Case(
        SETS,
        _lab_value(2, DAY_2, GLUCOSE_CODE, "Glukoz", donem="2025"),
        where=GLUCOSE_2,
        says="donem is 2025 but tarih is in 2026",
        label="wrong_donem",
    ),
    Case(
        SETS,
        _lab_value(2, DAY_2, GLUCOSE_CODE, "Glukoz", kohort=None),
        where=GLUCOSE_2,
        says="kohort is (none), not showcase",
        label="null_kohort",
    ),
    Case(
        SETS,
        # S3's hemogram without an episode id: no set for the billed line, a set for no billed line
        lambda d: edit(d, TABLE_LAB, lab(3, "2026-08-19", HEMOGRAM_CODE), basvuru_id=None),
        where=PATIENT[3],
        says=(
            "has no result set in lab_clean",
            "(episode (none)) has 15 row(s) and no billed lab line",
        ),
        n=2,
        label="no_episode_id",
    ),
    # --- lab.blood_gas_relations (S2's gas of 2026-03-09: pH 7.3, pCO2 58, pO2 56, HCO3 28.2, BE 2.2,
    # SaO2 88.7); the changed rows keep their flags correct
    Case(
        BLOOD_GAS,
        _lab_value(2, DAY_2, BLOOD_GAS_CODE, "HCO3", sonuc_sayisal=27.0),
        where=GAS_2,
        says="HCO3 27.0 but pCO2 58.0 and pH 7.3 give 28.22",
        label="hco3_changed",
    ),
    Case(
        BLOOD_GAS,
        _lab_value(2, DAY_2, BLOOD_GAS_CODE, "SaO2", sonuc_sayisal=95.0, anormal_mi=False),
        where=GAS_2,
        says="SaO2 95.0 but pO2 56.0 gives 88.72",
        label="sao2_changed",
    ),
    Case(
        BLOOD_GAS,
        _lab_value(2, DAY_2, BLOOD_GAS_CODE, "pH", sonuc_sayisal=7.4, anormal_mi=False),
        where=GAS_2,
        says="HCO3 28.2 but pCO2 58.0 and pH 7.4 give",
        label="ph_changed",
    ),
    Case(
        BLOOD_GAS,
        _lab_value(2, DAY_2, BLOOD_GAS_CODE, "pCO2", sonuc_sayisal=45.0, anormal_mi=False),
        where=GAS_2,
        says="HCO3 28.2 but pCO2 45.0 and pH 7.3 give",
        label="pco2_changed",
    ),
    Case(
        BLOOD_GAS,
        _lab_value(2, DAY_2, BLOOD_GAS_CODE, "pO2", sonuc_sayisal=70.0),
        where=GAS_2,
        says="SaO2 88.7 but pO2 70.0 gives",
        label="po2_changed",
    ),
    Case(
        BLOOD_GAS,
        _lab_value(2, DAY_2, BLOOD_GAS_CODE, "BE (baz fazlası)", sonuc_sayisal=6.0),
        where=GAS_2,
        says="base excess 6.0 but HCO3 28.2 and pH 7.3 give 2.16",
        label="base_excess_changed",
    ),
    # --- lab.egfr_relation (S2: a man of 81, creatinine 0.98, eGFR 77)
    Case(
        EGFR_RELATION,
        _lab_value(2, DAY_2, CREATININE_CODE, "Kreatinin", sonuc_sayisal=1.6, anormal_mi=True),
        where=EGFR_2,
        says="eGFR 77.0 but creatinine 1.6, age 81 and sex E give 43.0",
        label="creatinine_changed_alone",
    ),
    Case(
        EGFR_RELATION,
        _lab_value(2, DAY_2, CREATININE_CODE, EGFR, sonuc_sayisal=60.0),
        where=EGFR_2,
        says="eGFR 60.0 but creatinine 0.98, age 81 and sex E give 77.5",
        label="egfr_changed_alone",
    ),
    Case(
        EGFR_RELATION,
        _vital(2, TANI_YASI=60),
        where=EGFR_2,
        says="age 60",
        label="age_changed",
    ),
    Case(
        EGFR_RELATION,
        _vital(3, CINSIYET="E"),
        where=lab_where(3, "2026-08-19", CREATININE_CODE),
        says="sex E",
        also=(FLAG_AND_LIMITS,),  # S3's limits are the female ones, her sex is now male
        label="sex_changed",
    ),
    # --- rx.matches_billed_line. The changed rows keep their dose text consistent with miktar.
    Case(
        MATCHES,
        _recete(2, "PREDNOL-L", miktar=6, dozaj_ham="6 ampul"),
        where=PATIENT[2],
        says=("(miktar 6) has no billed drug line", "(quantity 5) has no prescription row"),
        n=2,
        label="quantity_changed",
    ),
    Case(
        MATCHES,
        _recete(7, "PARTEMOL", miktar=0),
        where=PATIENT[7],
        says=("(miktar 0) has no billed drug line", "(quantity 1) has no prescription row"),
        n=2,
        also=(DOSE,),  # dozaj_ham says 1 flakon, miktar says 0
        label="zero_quantity",
    ),
    Case(
        MATCHES,
        lambda d: drop(d, TABLE_RECETE, rx(6, "MADOPAR")),
        where=f"{PATIENT[6]} drug_claim_lines[ILC-",
        says="billed drug line MADOPAR 125 MG 30 TB on 2026-06-10 (quantity 20) has no prescription row",
        label="row_deleted",
    ),
    Case(
        MATCHES,
        lambda d: add_row(d, TABLE_RECETE, rx(7, "PARTEMOL")),
        where=rx_where(7, "2026-02-19"),
        says=f"prescription row {PARTEMOL} on 2026-02-19 (miktar 1) has no billed drug line",
        label="extra_row",
    ),
    Case(
        MATCHES,
        _recete(3, "EQIZOLIN", RECETE_TARIH=pl.col("RECETE_TARIH") + pl.duration(days=1)),
        where=PATIENT[3],
        says=("on 2026-08-19 (miktar 2) has no billed drug line", "on 2026-08-18 (quantity 2)"),
        n=2,
        label="date_moved",
    ),
    Case(
        MATCHES,
        _recete(4, "PARACEROL", ilac_adi=PARTEMOL),
        where=PATIENT[4],
        says=("has no billed drug line", "PARACEROL 10 MG/ML IV INF ICIN COZ ICEREN 100 ML 12 FLK"),
        n=2,
        label="product_name_changed",
    ),
    Case(
        MATCHES,
        _recete(2, "KLACID", RF_EPISODE="B-SENTETIK-HASTA-0002-002"),
        where=PATIENT[2],
        says="has no billed drug line of the same patient, episode, date, name and quantity",
        n=2,
        label="wrong_episode_id",
    ),
    # --- rx.route_vs_product
    Case(
        ROUTE,
        _recete(2, "CLEXANE", verilis_yolu="Ağızdan (Oral)"),
        where=rx_where(2, "2026-03-09") + "CLEXANE",
        says=(
            "route Ağızdan (Oral) for CLEXANE",
            "has a parenteral route",
            "a low-molecular-weight heparin has the route Subkütan",
        ),
        label="clexane_as_oral",
    ),
    Case(
        ROUTE,
        _recete(2, "CLEXANE", verilis_yolu="Intravenöz"),
        where=rx_where(2, "2026-03-09") + "CLEXANE",
        says="a low-molecular-weight heparin has the route Subkütan",
        label="clexane_as_intravenous",
    ),
    Case(
        ROUTE,
        _recete(6, "MADOPAR", verilis_yolu="Intravenöz"),
        where=rx_where(6, "2026-06-10") + "MADOPAR",
        says="a tablet or capsule product has the route Ağızdan (Oral)",
        label="tablet_as_intravenous",
    ),
    Case(
        ROUTE,
        _recete(2, "IESEF", verilis_yolu=None),
        where=rx_where(2, "2026-03-09") + "IESEF",
        says="the route is missing",
        also=(REQUIRED,),  # a required column is empty
        label="null_route",
    ),
    Case(
        ROUTE,
        _recete(2, "IESEF", verilis_yolu="IV"),
        where=rx_where(2, "2026-03-09") + "IESEF",
        says="the route IV is not in the closed vocabulary",
        label="route_spelling_outside_the_vocabulary",
    ),
    Case(
        ROUTE,
        _recete(2, "IPRAVENT", verilis_yolu="Ağızdan (Oral)"),
        where=rx_where(2, "2026-03-09") + "IPRAVENT",
        says="a nebule or inhalation product has the route İnhalasyon",
        label="nebule_as_oral",
    ),
    Case(
        ROUTE,
        _recete(2, "IPRAVENT", verilis_yolu="Intravenöz"),
        where=rx_where(2, "2026-03-09") + "IPRAVENT",
        says="a nebule or inhalation product has the route İnhalasyon",
        label="nebule_as_intravenous",
    ),
    Case(
        ROUTE,
        _recete(2, "IESEF", verilis_yolu="İnhalasyon"),
        where=rx_where(2, "2026-03-09") + "IESEF",
        says="an injection, infusion, vial or bag product has a parenteral route",
        label="injection_as_inhalation",
    ),
    Case(
        ROUTE,
        _recete(
            6, "MADOPAR", ilac_adi_ham="MADOPAR 125 MG TABLET VE ENJEKSIYONLUK COZELTI, 30 ADET"
        ),
        where=rx_where(6, "2026-06-10") + "MADOPAR",
        says="the name states both an injection and a tablet or capsule",
        label="name_states_a_tablet_and_an_injection",
    ),
    # --- rx.dose_unit
    Case(
        DOSE,
        _recete(1, "IESEF", dozaj_ham="1 bottle"),
        where=rx_where(1, "2026-07-14") + "IESEF",
        says="dozaj_ham 1 bottle: uses the English unit word bottle",
        label="english_unit_word",
    ),
    Case(
        DOSE,
        _recete(2, "IESEF", dozaj_ham="8 flakon"),
        where=rx_where(2, "2026-03-09") + "IESEF",
        says="the count 8 differs from miktar 7",
        label="count_differs_from_miktar",
    ),
    Case(
        DOSE,
        _recete(2, "IESEF", dozaj_ham="7"),
        where=rx_where(2, "2026-03-09") + "IESEF",
        says="is not a positive count and one unit word, like '5 flakon'",
        label="no_unit",
    ),
    Case(
        DOSE,
        _recete(2, "IESEF", dozaj_ham="7 vials"),
        where=rx_where(2, "2026-03-09") + "IESEF",
        says="uses the unit word vials, which is not in the closed list of Turkish units",
        label="unit_word_outside_the_list",
    ),
    Case(
        DOSE,
        _recete(2, "IESEF", dozaj_ham="0 flakon"),
        where=rx_where(2, "2026-03-09") + "IESEF",
        says="is not a positive count",
        label="zero_count",
    ),
    Case(
        DOSE,
        _recete(2, "IESEF", dozaj_ham="07 flakon"),
        where=rx_where(2, "2026-03-09") + "IESEF",
        says="is not a positive count",
        label="count_with_a_leading_zero",
    ),
    Case(
        DOSE,
        _recete(2, "IESEF", dozaj_ham="7  flakon"),
        where=rx_where(2, "2026-03-09") + "IESEF",
        says="is not a positive count",
        label="two_spaces",
    ),
    Case(
        DOSE,
        _recete(2, "IESEF", dozaj_ham="7 Flakon"),
        where=rx_where(2, "2026-03-09") + "IESEF",
        says="uses the unit word Flakon, which is not in the closed list",
        label="capital_unit_word",
    ),
    Case(
        DOSE,
        _recete(2, "IESEF", dozaj_ham=None),
        where=rx_where(2, "2026-03-09") + "IESEF",
        says="dozaj_ham is missing",
        also=(REQUIRED,),  # a required column is empty
        label="null_dose",
    ),
    # --- rx.required_fields: a null in each required column (cases built above) and two blanks
    *REQUIRED_NULL_CASES,
    Case(
        REQUIRED,
        _blank_column("ilac_adi_ham"),
        where=_REQUIRED_START,
        says="missing required column(s): ilac_adi_ham",
        label="blank_raw_name",
    ),
    Case(
        REQUIRED,
        lambda d: edit(d, TABLE_RECETE, patient_row(7), kohort=""),
        where=_REQUIRED_START,
        says="missing required column(s): kohort",
        label="empty_kohort",
    ),
    # --- ana.vitals_bounds (S2: KB-S 142, KB-D 84, SpO2 88, 170 cm, 68 kg, BMI 23.5)
    Case(
        VITALS,
        _vital(2, **{"KB-D": 148}),
        where=VITALS_2,
        says="KB-D 148 is not below KB-S 142",
        label="diastolic_above_systolic",
    ),
    Case(
        VITALS,
        _vital(2, BMI=31.0),
        where=VITALS_2,
        says="BMI 31.0 differs from Kilo / (Boy / 100)^2 = 23.5",
        label="bmi_inconsistent",
    ),
    Case(
        VITALS,
        _vital(2, SPO2=120),
        where=VITALS_2,
        says="SPO2 120 is outside 50..100",
        label="spo2_120",
    ),
    Case(
        VITALS,
        _vital(4, Nabiz=None),
        where=f"{PATIENT[4]} anadata_clean[{EPISODE[4]}]",
        says="Nabiz is missing",
        label="missing_pulse",
    ),
    Case(
        VITALS,
        _vital(2, BMI=None),
        where=VITALS_2,
        says="BMI is missing",
        label="missing_bmi",
    ),
    Case(
        VITALS,
        _vital(2, Boy=0),
        where=VITALS_2,
        says="Boy 0 is outside 120..210",
        label="zero_height",
    ),
    Case(
        VITALS,
        _vital(3, CINSIYET="?"),
        where=f"{PATIENT[3]} anadata_clean[{EPISODE[3]}]",
        says="CINSIYET ? is neither E nor K",
        label="sex_neither_e_nor_k",
    ),
    Case(
        VITALS,
        # a second episode of S3 that says she is a man: both rows name the contradiction
        lambda d: add_row(
            d, TABLE_ANADATA, patient_row(3), SQ_EPISODE="B-SENTETIK-HASTA-0003-002", CINSIYET="E"
        ),
        where=f"{PATIENT[3]} anadata_clean[",
        says="CINSIYET differs between the episodes of the patient",
        n=2,
        label="sex_differs_between_episodes",
    ),
]


# --- 1. the registry -------------------------------------------------------------------------------


def test_every_check_id_has_a_function_a_short_meaning_and_a_mutation_case() -> None:
    assert set(CHECK_FUNCTIONS) == set(CHECKS)
    assert {case.check for case in CASES} == set(CHECKS)
    assert len(CHECKS) == 12
    for check, meaning in CHECKS.items():
        assert 0 < len(meaning) <= 120, f"{check}: the meaning has {len(meaning)} characters"
    assert all(re.fullmatch(r"[a-z]+\.[a-z_]+", check) for check in CHECKS)
    assert {check.split(".")[0] for check in CHECKS} == {"lab", "rx", "ana"}


def test_cases_name_registered_ids_only() -> None:
    for case in CASES:
        assert case.check in CHECKS
        assert set(case.also) <= set(CHECKS), case.name
        assert case.check not in case.also, case.name
        assert case.n >= 1 and case.patients >= 1, case.name
        assert case.where and case.fragments, case.name
    assert len({case.name for case in CASES}) == len(CASES), "two cases share a name"


def test_a_problem_carries_a_registered_id_and_its_patient() -> None:
    with pytest.raises(KeyError, match="unregistered check id"):
        Problem("not.a.registered.check", "somewhere", "bad")
    problem = Problem(VALUE_BOUNDS, f"{PATIENT[1]} lab_clean[x]", "m")
    assert problem.patient_id == PATIENT[1]
    assert Problem(VITALS, PATIENT[2], "m").patient_id == PATIENT[2]
    assert str(problem).startswith("lab.value_bounds at ")


# --- 2. the committed tables and the clean twins -------------------------------------------------------


@pytest.fixture(scope="module")
def committed_problems(built, clean, context) -> list[Problem]:
    return check_clean_plausibility(built.tables, clean, context=context)


@pytest.mark.parametrize("check", list(CHECKS))
def test_a_check_is_clean_on_the_committed_tables(check, built, clean, context) -> None:
    found = check_clean_plausibility(built.tables, clean, context=context, only=check)
    assert [str(p) for p in found] == []


def test_the_committed_clean_tables_raise_no_problem(committed_problems, clean) -> None:
    assert [str(p) for p in committed_problems] == []
    # the tables are the ones of the brief: they are not empty, so "no problem" is not "no data"
    assert {name: clean[name].height for name in _CLEAN_FILES} == {
        TABLE_ANADATA: 8,
        TABLE_LAB: 207,
        TABLE_RECETE: 19,
    }


def test_patients_5_and_8_are_package_bills_with_no_lab_rows(built, clean) -> None:
    labs = clean[TABLE_LAB]
    assert labs.filter(pl.col("HASTA_ID").is_in([PATIENT[5], PATIENT[8]])).height == 0
    headers = built.tables[TABLE_HEADERS].filter(
        pl.col("patient_id").is_in([PATIENT[5], PATIENT[8]])
    )
    assert headers["package_candidate"].to_list() == [True, True]
    billed = built.tables[TABLE_PROCEDURES].filter(pl.col("procedure_category") == "laboratuvar")
    assert billed.filter(pl.col("patient_id").is_in([PATIENT[5], PATIENT[8]])).height == 0


def test_the_twin_claims_differ_from_the_faulty_ones_only_by_the_lines_story_s1_adds(
    built, twins
) -> None:
    """S1's fault bills two lab lines and three drug lines on a package claim; the clean tables mirror them."""
    only_faulty_labs = (
        built.tables[TABLE_PROCEDURES]
        .filter(pl.col("procedure_category") == "laboratuvar")
        .join(
            twins[TABLE_PROCEDURES].select("procedure_line_id"),
            on="procedure_line_id",
            how="anti",
        )
    )
    assert sorted(only_faulty_labs["procedure_code"]) == ["L101850", "L107020"]
    assert set(only_faulty_labs["patient_id"]) == {PATIENT[1]}
    only_faulty_drugs = built.tables[TABLE_DRUGS].join(
        twins[TABLE_DRUGS].select("drug_claim_line_id"), on="drug_claim_line_id", how="anti"
    )
    assert only_faulty_drugs.height == 3
    assert set(only_faulty_drugs["patient_id"]) == {PATIENT[1]}
    assert twins[TABLE_DRUGS].height == 16 and built.tables[TABLE_DRUGS].height == 19


def test_with_the_twin_claims_ten_ids_still_raise_nothing_and_two_name_the_lines_of_s1(
    twins, clean, context
) -> None:
    """The clean tables are built from the faulty bills, so against the twin they hold S1's extra lines."""
    found = check_clean_plausibility(twins, clean, context=context)
    assert only_ids(found) == {SETS, MATCHES}
    assert {p.patient_id for p in found} == {PATIENT[1]}
    labs = [p for p in found if p.check == SETS]
    drugs = [p for p in found if p.check == MATCHES]
    assert [p.where for p in labs] == [
        lab_where(1, "2026-07-15", "L101850"),
        lab_where(1, "2026-07-15", HEMOGRAM_CODE),
    ]
    assert all("no billed lab line" in p.message for p in labs)
    assert len(drugs) == 3 and all("has no billed drug line" in p.message for p in drugs)


def test_the_twin_world_is_clean_for_every_id(twins, clean, context) -> None:
    """Twin claims and clean tables without S1's lab and prescription rows: nothing depends on the fault."""
    twin_clean = {
        name: (frame.filter(pl.col("HASTA_ID") != PATIENT[1]) if name != TABLE_ANADATA else frame)
        for name, frame in clean.items()
    }
    assert twin_clean[TABLE_LAB].height == 207 - 16
    assert twin_clean[TABLE_RECETE].height == 19 - 3
    found = check_clean_plausibility(twins, twin_clean, context=context)
    assert [str(p) for p in found] == []


def test_the_committed_files_give_the_result_of_the_tables_in_memory(built, clean, context) -> None:
    on_disk = {name: pl.read_parquet(_CLAIMS_DIR / name) for name in TABLE_FILES}
    clean_on_disk = {name: pl.read_parquet(_CLEAN_DIR / name) for name in _CLEAN_FILES}
    assert all(clean_on_disk[name].equals(clean[name], null_equal=True) for name in _CLEAN_FILES), (
        "the committed clean files are not the tables of the build"
    )
    assert check_clean_plausibility(on_disk, clean_on_disk, context=context) == []
    # the same defect gives the same findings in both worlds
    for tables, clean_tables in ((on_disk, clean_on_disk), (built.tables, clean)):
        data = Data(dict(tables), dict(clean_tables))
        edit(
            data,
            TABLE_LAB,
            lab(2, DAY_2, GLUCOSE_CODE, "Glukoz"),
            sonuc_sayisal=-5.0,
            anormal_mi=True,
        )
        edit(data, TABLE_RECETE, rx(2, "IESEF"), dozaj_ham="8 flakon")
        found = [str(p) for p in data.problems(context)]
        assert len(found) == 2 and found[0].startswith("lab.value_bounds at ")
        assert found[1].startswith("rx.dose_unit at ")
        if tables is on_disk:
            on_disk_found = found
        else:
            assert found == on_disk_found


# --- 3. the mutation cases -------------------------------------------------------------------------


@pytest.mark.parametrize("case", CASES, ids=lambda c: c.name)
def test_a_defect_trips_its_own_check_and_what_it_must(case: Case, built, clean, context) -> None:
    base = fresh(built, clean)
    assert base.problems(context) == [], "the base (the committed tables) must be clean"
    broken = fresh(built, clean)
    case.mutate(broken)
    found = broken.problems(context)
    message = [str(p) for p in found]
    assert only_ids(found) == {case.check, *case.also}, message
    mine = [p for p in found if p.check == case.check]
    assert len(mine) == case.n, message
    assert all(case.where in p.where for p in mine), message
    for fragment in case.fragments:
        assert any(fragment in p.message for p in mine), (fragment, message)
    # a mutation touches one patient (two for a row whose patient id is gone), and so do its findings
    assert len({p.patient_id for p in found}) == case.patients, message
    # every finding says where and what, whatever value the defect left empty
    assert all(p.where.startswith(p.patient_id + " ") or p.where == p.patient_id for p in found)
    assert all(isinstance(p.message, str) and p.message for p in found), message
    assert not any("None" in p.message or "null" in p.message for p in found), message


def _all_rows_of(table: str, built, clean, context, check: str, **changes) -> list[Problem]:
    """`check` over the clean tables after `changes` (column -> expression) were laid over every row of `table`."""
    broken = {**clean, table: clean[table].with_columns(**changes)}
    return check_clean_plausibility(built.tables, broken, context=context, only=check)


_NUMERIC = pl.col("sonuc_nitel").is_null()
LAB_ROW_BREAKS = {
    # every numeric result impossible: 201 findings, one per row; every strip with a bad grade: 6
    "value": (
        VALUE_BOUNDS,
        {"sonuc_sayisal": pl.when(_NUMERIC).then(-1e9).otherwise(pl.col("sonuc_sayisal"))},
        201,
    ),
    "grade": (
        VALUE_BOUNDS,
        {"sonuc_nitel": pl.when(~_NUMERIC).then(pl.lit("zzz")).otherwise(pl.col("sonuc_nitel"))},
        6,
    ),
    "flag": (FLAG_AND_LIMITS, {"anormal_mi": ~pl.col("anormal_mi")}, 207),
    "limit": (FLAG_AND_LIMITS, {"ref_ust": pl.lit(12345.0)}, 207),
    "unit": (UNIT, {"birim": pl.lit("x/y")}, 207),
    "kohort": (SETS, {"kohort": pl.lit("x")}, 207),
    "donem": (SETS, {"donem": pl.lit("1999")}, 207),
}


@pytest.mark.parametrize("kind", LAB_ROW_BREAKS)
def test_every_committed_lab_row_is_looked_at_by_the_row_checks(
    kind, built, clean, context
) -> None:
    """Break all rows at once: one finding per row, so no row escapes (a check that skipped one would miss it)."""
    check, changes, expected = LAB_ROW_BREAKS[kind]
    found = _all_rows_of(TABLE_LAB, built, clean, context, check, **changes)
    assert len(found) == expected, [str(p) for p in found[:3]]
    assert len({p.where for p in found}) == expected, "two findings about one row"


RECETE_ROW_BREAKS = {
    # a row without a line and a line without a row, for each of the 19 rows
    "miktar_matches": (MATCHES, {"miktar": pl.col("miktar") + 1}, 19 * 2),
    "miktar_dose": (DOSE, {"miktar": pl.col("miktar") + 1}, 19),
    "inhalation": (ROUTE, {"verilis_yolu": pl.lit("İnhalasyon")}, 18),  # all but the nebule
    "oral": (ROUTE, {"verilis_yolu": pl.lit("Ağızdan (Oral)")}, 18),  # all but the tablet
    **{f"null_{column}": (REQUIRED, {column: None}, 19) for column in REQUIRED_RECETE_COLUMNS},
}


@pytest.mark.parametrize("kind", RECETE_ROW_BREAKS)
def test_every_committed_prescription_row_is_looked_at(kind, built, clean, context) -> None:
    check, changes, expected = RECETE_ROW_BREAKS[kind]
    schema = clean[TABLE_RECETE].schema
    typed = {
        column: pl.lit(None, dtype=schema[column]) if expr is None else expr
        for column, expr in changes.items()
    }
    found = _all_rows_of(TABLE_RECETE, built, clean, context, check, **typed)
    assert len(found) == expected, [str(p) for p in found[:3]]


VITAL_BREAKS = {
    "SPO2": 20, "KB-S": 300, "KB-D": 20, "Nabiz": 250, "Boy": 100, "Kilo": 250.0, "TANI_YASI": 120,
    "BMI": 99.0, "CINSIYET": "?",
}  # fmt: skip


@pytest.mark.parametrize("column", VITAL_BREAKS)
def test_every_committed_vital_row_is_looked_at(column, built, clean, context) -> None:
    schema = clean[TABLE_ANADATA].schema
    broken = {column: pl.lit(VITAL_BREAKS[column], dtype=schema[column])}
    found = _all_rows_of(TABLE_ANADATA, built, clean, context, VITALS, **broken)
    assert len(found) == 8, [str(p) for p in found[:3]]


def test_the_mutations_leave_the_clean_tables_untouched(built, clean) -> None:
    before = {name: frame.clone() for name, frame in clean.items()}
    claims_before = {name: frame.clone() for name, frame in built.tables.items()}
    for case in CASES:
        case.mutate(fresh(built, clean))
    assert all(clean[name].equals(frame, null_equal=True) for name, frame in before.items())
    assert all(built.tables[n].equals(f, null_equal=True) for n, f in claims_before.items())


def test_every_mutation_case_of_a_branch_is_there() -> None:
    """The branches the brief names, each with a case."""
    labels = {(case.check, case.label) for case in CASES}
    wanted = {
        (VALUE_BOUNDS, "negative_glucose"),
        (VALUE_BOUNDS, "potassium_40"),
        (VALUE_BOUNDS, "unknown_parameter"),
        (VALUE_BOUNDS, "nan"),
        (HEMOGRAM, "one_differential_count_changed"),
        (HEMOGRAM, "hgb_changed_alone"),
        (FLAG_AND_LIMITS, "flipped_flag"),
        (FLAG_AND_LIMITS, "male_limits_on_a_woman"),
        (FLAG_AND_LIMITS, "strip_flag_false_on_a_trace"),
        (FLAG_AND_LIMITS, "number_on_a_strip_row"),
        (UNIT, "wrong_unit"),
        (UNIT, "unit_on_a_strip_row"),
        (SETS, "dropped_row"),
        (SETS, "extra_result_set"),
        (SETS, "wrong_date"),
        (SETS, "wrong_episode_id"),
        (SETS, "rows_for_a_package_claim"),
        (SETS, "second_troponin_set_removed"),
        (BLOOD_GAS, "hco3_changed"),
        (BLOOD_GAS, "sao2_changed"),
        (EGFR_RELATION, "creatinine_changed_alone"),
        (MATCHES, "quantity_changed"),
        (MATCHES, "row_deleted"),
        (MATCHES, "extra_row"),
        (ROUTE, "clexane_as_oral"),
        (ROUTE, "tablet_as_intravenous"),
        (ROUTE, "null_route"),
        (DOSE, "english_unit_word"),
        (DOSE, "count_differs_from_miktar"),
        (REQUIRED, "null_ilac_adi"),
        (VITALS, "diastolic_above_systolic"),
        (VITALS, "bmi_inconsistent"),
        (VITALS, "spo2_120"),
    }
    assert wanted <= labels
    for column in REQUIRED_RECETE_COLUMNS:
        assert (REQUIRED, f"null_{column}") in labels


# --- 4. the entry point ----------------------------------------------------------------------------


def test_only_restricts_the_run_and_unknown_ids_are_refused(built, clean, context) -> None:
    data = fresh(built, clean)
    edit(data, TABLE_LAB, lab(2, DAY_2, GLUCOSE_CODE, "Glukoz"), birim="mmol/L")
    edit(data, TABLE_RECETE, rx(2, "IESEF"), dozaj_ham="8 flakon")
    assert only_ids(data.problems(context)) == {UNIT, DOSE}
    assert only_ids(data.problems(context, only=UNIT)) == {UNIT}
    assert only_ids(data.problems(context, only=[UNIT, DOSE, VITALS])) == {UNIT, DOSE}
    assert data.problems(context, only=[VITALS, SETS]) == []
    assert data.problems(context, only=[]) == []
    with pytest.raises(KeyError, match="unregistered"):
        data.problems(context, only=[UNIT, "lab.no_such_check"])


def test_a_check_reads_only_the_tables_it_needs(built, clean, context) -> None:
    labs_only = check_clean_plausibility(
        {}, {TABLE_LAB: clean[TABLE_LAB]}, context=context, only=[VALUE_BOUNDS, HEMOGRAM, BLOOD_GAS]
    )
    assert labs_only == []
    recete_only = check_clean_plausibility(
        {}, {TABLE_RECETE: clean[TABLE_RECETE]}, context=context, only=[ROUTE, DOSE, REQUIRED]
    )
    assert recete_only == []


def test_a_missing_table_or_column_is_reported_by_name(built, clean, context) -> None:
    with pytest.raises(CleanPlausibilityError, match="drug_claim_lines"):
        check_clean_plausibility(
            {k: v for k, v in built.tables.items() if k != TABLE_DRUGS},
            clean,
            context=context,
            only=MATCHES,
        )
    with pytest.raises(CleanPlausibilityError, match="anadata_clean"):
        check_clean_plausibility(built.tables, {}, context=context, only=VITALS)
    with pytest.raises(
        CleanPlausibilityError, match=r"lab_clean.parquet lacks the column\(s\) \['birim'\]"
    ):
        check_clean_plausibility(
            {}, {TABLE_LAB: clean[TABLE_LAB].drop("birim")}, context=context, only=UNIT
        )
    with pytest.raises(CleanPlausibilityError, match="lab_clean"):
        check_clean_plausibility(built.tables, {}, context=context, only=SETS)


def test_the_problems_come_in_the_order_of_the_registry(built, clean, context) -> None:
    data = fresh(built, clean)
    edit(data, TABLE_ANADATA, patient_row(2), SPO2=120)
    edit(data, TABLE_RECETE, rx(2, "IESEF"), dozaj_ham="8 flakon")
    edit(data, TABLE_LAB, lab(2, DAY_2, GLUCOSE_CODE, "Glukoz"), birim="mmol/L")
    edit(data, TABLE_LAB, lab(2, DAY_2, "L107420", "Üre"), sonuc_sayisal=-1.0, anormal_mi=True)
    found = data.problems(context)
    order = {check: index for index, check in enumerate(CHECKS)}
    assert [order[p.check] for p in found] == sorted(order[p.check] for p in found)
    assert [p.check for p in found] == [VALUE_BOUNDS, UNIT, DOSE, VITALS]
    assert [p.where for p in found if p.check == VALUE_BOUNDS] == [
        lab_where(2, DAY_2, "L107420", "Üre")
    ]


def test_empty_tables_are_no_crash_and_name_what_is_billed_without_a_row(
    built, clean, context
) -> None:
    empty_clean = {name: frame.head(0) for name, frame in clean.items()}
    empty_claims = {name: frame.head(0) for name, frame in built.tables.items()}
    assert check_clean_plausibility(empty_claims, empty_clean, context=context) == []
    # 48 billed lab lines without a result set and 19 billed drug lines without a prescription row
    found = check_clean_plausibility(built.tables, empty_clean, context=context)
    assert only_ids(found) == {SETS, MATCHES} and len(found) == 48 + 19
    # and the other way round: 48 result sets and 19 prescription rows without a bill
    found = check_clean_plausibility(empty_claims, clean, context=context)
    assert only_ids(found) == {SETS, MATCHES} and len(found) == 48 + 19
    assert sum("no billed lab line" in p.message for p in found) == 48


def test_without_a_context_the_shared_default_is_used(built, clean) -> None:
    assert check_clean_plausibility(built.tables, clean) == []


def test_a_missing_value_is_named_in_the_message_not_dropped(built, clean, context) -> None:
    data = fresh(built, clean)
    edit(data, TABLE_LAB, lab(2, DAY_2, CREATININE_CODE, EGFR), ref_ust=100.0)
    (problem,) = data.problems(context, only=FLAG_AND_LIMITS)
    assert problem.message.endswith("but the reference gives 60.0..(none) for sex E")
    data = fresh(built, clean)
    edit(data, TABLE_ANADATA, patient_row(2), CINSIYET=None)
    (problem,) = data.problems(context, only=VITALS)
    assert problem.message == "CINSIYET (none) is neither E nor K"


# --- 5. the comparisons, one by one: just inside, just outside, zero and null -------------------------

BOUND_ITEMS = [
    (code, parameter, low, high) for (code, parameter), (low, high) in LAB_HARD_BOUNDS.items()
]


def bound_problems(code, parameter, value, context) -> list[Problem]:
    frame = lab_frame({"SUB_CODE": code, "parametre": parameter, "sonuc_sayisal": value})
    return run_lab(frame, VALUE_BOUNDS, context)


@pytest.mark.parametrize(
    ("code", "parameter", "low", "high"),
    BOUND_ITEMS,
    ids=[f"{c}-{p}" for c, p, _, _ in BOUND_ITEMS],
)
def test_a_value_is_inside_its_hard_interval_up_to_the_limits(
    code, parameter, low, high, context
) -> None:
    step = (high - low) * 1e-3
    for inside in (low, high, (low + high) / 2, low + step, high - step):
        assert bound_problems(code, parameter, inside, context) == [], inside
    for outside in (low - step, high + step):
        (problem,) = bound_problems(code, parameter, outside, context)
        assert "outside the hard interval" in problem.message, outside
        assert problem.where == lab_where(2, DAY_2, code, parameter)
    # zero is a defect exactly when the interval starts above it
    assert bool(bound_problems(code, parameter, 0.0, context)) is (low > 0), (code, parameter)
    # a missing, NaN or infinite result is always a defect
    for value, said in (
        (None, "no numeric result"),
        (math.nan, "NaN"),
        (math.inf, "infinite"),
        (-math.inf, "infinite"),
    ):
        (problem,) = bound_problems(code, parameter, value, context)
        assert said in problem.message, (parameter, value)


@pytest.mark.parametrize("parameter", DIFFERENTIAL_PARAMETERS)
def test_a_differential_count_is_capped_by_the_wbc_of_its_own_set(parameter, context) -> None:
    def run(count: float | None, wbc: float | None = 10.0, other_day: bool = False):
        rows = []
        if wbc is not None:
            rows.append(
                {"SUB_CODE": HEMOGRAM_CODE, "parametre": "WBC (Lökosit)", "sonuc_sayisal": wbc}
            )
        count_row = {"SUB_CODE": HEMOGRAM_CODE, "parametre": parameter, "sonuc_sayisal": count}
        if other_day:
            count_row["tarih"] = day("2026-03-10")
        rows.append(count_row)
        return run_lab(lab_frame(*rows), VALUE_BOUNDS, context)

    assert run(10.0) == [] and run(9.99) == [] and run(0.0) == []
    (problem,) = run(10.01)
    assert "above the WBC 10.0 of its result set" in problem.message
    assert problem.where == lab_where(2, DAY_2, HEMOGRAM_CODE, parameter)
    (problem,) = run(-0.01)
    assert "outside the hard interval 0.0..100.0" in problem.message
    assert [p.message for p in run(None)] == [f"{parameter} = (none): has no numeric result"]
    assert run(50.0, wbc=None) == [], "without a WBC only the absolute interval applies"
    assert run(50.0, wbc=10.0, other_day=True) == [], "the WBC of another day is not the cap"
    # a WBC that is itself a defect caps nothing: the count is not "above" it, only the WBC is reported
    assert [p.message for p in run(10.01, wbc=math.nan)] == ["WBC (Lökosit) = NaN: is NaN"]
    for wbc in (-5.0, 0.0, 0.05, 100.01):
        (problem,) = run(0.08, wbc=wbc)
        assert problem.where == lab_where(2, DAY_2, HEMOGRAM_CODE, "WBC (Lökosit)"), wbc
        assert "outside the hard interval 0.1..100.0" in problem.message, wbc
    (problem,) = run(0.08, wbc=math.inf)
    assert problem.message == "WBC (Lökosit) = inf: is infinite"


@pytest.mark.parametrize(("code", "parameter"), LAB_STRIP_PARAMETERS)
def test_a_strip_has_one_of_the_grades(code, parameter, context) -> None:
    def run(grade: str | None) -> list[Problem]:
        row = {
            "SUB_CODE": code,
            "parametre": parameter,
            "sonuc_sayisal": None,
            "sonuc_nitel": grade,
            "birim": "",
            "ref_alt": None,
            "ref_ust": None,
            "anormal_mi": grade != "Negatif",
        }
        return run_lab(lab_frame(row), VALUE_BOUNDS, context)

    for grade in STRIP_GRADES:
        assert run(grade) == [], grade
    for grade in ("Orta", "negatif", "", " +", "+++++"):
        (problem,) = run(grade)
        assert f"has the grade {grade}, which is not one of" in problem.message
    (problem,) = run(None)
    assert problem.message == f"{parameter} = (none): has no grade"


def test_the_strip_grades_are_the_ones_of_the_review() -> None:
    assert STRIP_GRADES == ("Negatif", "Eser", "+", "++", "+++", "++++", "Pozitif")


def hemogram_frame(**values: float | None) -> pl.DataFrame:
    """A consistent hemogram (WBC 10 = 6 + 2 + 1 + 0.5 + 0.5; RBC 5, HGB 15, HCT 45, MCV 90, MCH 30)."""
    base: dict[str, float | None] = {
        "WBC (Lökosit)": 10.0,
        "NEU# (Nötrofil)": 6.0,
        "LYM# (Lenfosit)": 2.0,
        "MONO# (Monosit)": 1.0,
        "EOS# (Eozinofil)": 0.5,
        "BASO# (Bazofil)": 0.5,
        "RBC (Eritrosit)": 5.0,
        "HGB (Hemoglobin)": 15.0,
        "HCT (Hematokrit)": 45.0,
        "MCV": 90.0,
        "MCH": 30.0,
    }
    aliases = {"wbc": "WBC (Lökosit)", "rbc": "RBC (Eritrosit)", "hgb": "HGB (Hemoglobin)"}
    aliases |= {"hct": "HCT (Hematokrit)", "mcv": "MCV", "mch": "MCH"}
    aliases |= {"neu": "NEU# (Nötrofil)", "lym": "LYM# (Lenfosit)", "mono": "MONO# (Monosit)"}
    aliases |= {"eos": "EOS# (Eozinofil)", "baso": "BASO# (Bazofil)"}
    base.update({aliases[name]: value for name, value in values.items()})
    return lab_frame(
        *[
            {"SUB_CODE": HEMOGRAM_CODE, "parametre": name, "sonuc_sayisal": value}
            for name, value in base.items()
            if value is not None
        ]
    )


def hemogram_problems(frame: pl.DataFrame, context) -> list[Problem]:
    return run_lab(frame, HEMOGRAM, context)


def test_a_consistent_hemogram_raises_nothing(context) -> None:
    assert hemogram_problems(hemogram_frame(), context) == []


@pytest.mark.parametrize(
    ("lym", "trips"), [(2.04, False), (1.96, False), (2.06, True), (1.94, True), (0.0, True)]
)
def test_the_differential_sums_to_the_wbc_within_005(lym, trips, context) -> None:
    found = hemogram_problems(hemogram_frame(lym=lym), context)
    assert bool(found) is trips, lym
    if trips:
        assert "the five differential counts sum to" in found[0].message


@pytest.mark.parametrize(
    ("hgb", "hct", "trips"),
    [
        (10.0, 27.4, False),  # 2.74, the limit
        (10.0, 27.5, False),
        (10.0, 27.3, True),
        (10.0, 35.7, False),  # 3.57, the limit
        (10.0, 35.6, False),
        (10.0, 35.8, True),
        (0.0, 45.0, True),  # a zero HGB: any HCT is too high
        (0.0, 0.0, False),  # zero and zero: the ratio holds (value_bounds reports both)
    ],
)
def test_hct_per_hgb_is_in_the_mchc_window(hgb, hct, trips, context) -> None:
    # MCV and MCH follow from the red-cell count so that only the ratio can trip
    frame = hemogram_frame(hgb=hgb, hct=hct, mcv=hct * 10 / 5.0, mch=hgb * 10 / 5.0)
    found = hemogram_problems(frame, context)
    assert bool(found) is trips, (hgb, hct)
    if trips:
        assert [p.message[:4] for p in found] == ["HCT "], found
        assert "is outside 2.74..3.57" in found[0].message


@pytest.mark.parametrize(
    ("factor", "trips"), [(1.029, False), (0.971, False), (1.031, True), (0.969, True)]
)
def test_the_red_cell_indices_give_hct_and_hgb_within_3_percent(factor, trips, context) -> None:
    mcv = hemogram_problems(hemogram_frame(mcv=90.0 * factor), context)
    mch = hemogram_problems(hemogram_frame(mch=30.0 * factor), context)
    assert bool(mcv) is trips and bool(mch) is trips, factor
    assert all("x MCV" in p.message for p in mcv)
    assert all("x MCH" in p.message for p in mch)


@pytest.mark.parametrize("missing", ["wbc", "lym", "rbc", "hgb", "hct", "mcv", "mch"])
def test_a_relation_with_a_missing_member_is_skipped_not_reported(missing, context) -> None:
    """A missing row is the business of result_sets_match_bill, a missing number of value_bounds."""
    assert hemogram_problems(hemogram_frame(**{missing: None}), context) == []
    for bad in (math.nan, math.inf):
        # the member is reported by lab.value_bounds; the relations that use it are skipped
        frame = hemogram_frame(**{missing: bad})
        assert hemogram_problems(frame, context) == [], (missing, bad)


def test_the_hemogram_relations_are_checked_per_set(context) -> None:
    good = hemogram_frame()
    bad = hemogram_frame(mcv=99.0).with_columns(
        pl.lit(day("2026-03-10"), dtype=pl.Datetime("ns")).alias("tarih")
    )
    found = hemogram_problems(pl.concat([good, bad]), context)
    assert [p.where for p in found] == [lab_where(2, "2026-03-10", HEMOGRAM_CODE)]


def test_zero_in_the_hemogram_relations(context) -> None:
    """Zero counts and a zero WBC hold the sum; a zero red-cell count breaks both indices."""
    counts = {"wbc": 0.0, "neu": 0.0, "lym": 0.0, "mono": 0.0, "eos": 0.0, "baso": 0.0}
    assert hemogram_problems(hemogram_frame(**counts), context) == []
    (problem,) = hemogram_problems(hemogram_frame(wbc=0.0), context)
    assert problem.message.startswith("the five differential counts sum to 10.0 but the WBC is 0.0")
    found = hemogram_problems(hemogram_frame(rbc=0.0), context)
    assert sorted(p.message.split(" = ")[0] for p in found) == [
        "RBC 0.0 x MCH 30.0 / 10",
        "RBC 0.0 x MCV 90.0 / 10",
    ]


def gas_frame(**values: float | None) -> pl.DataFrame:
    """S2's arterial gas of 2026-03-09 (pH 7.3, pCO2 58, pO2 56, HCO3 28.2, BE 2.2, SaO2 88.7)."""
    base = {"pH": 7.3, "pCO2": 58.0, "pO2": 56.0, "HCO3": 28.2, "BE (baz fazlası)": 2.2}
    base["SaO2"] = 88.7
    base.update(values)
    return lab_frame(
        *[
            {"SUB_CODE": BLOOD_GAS_CODE, "parametre": name, "sonuc_sayisal": value}
            for name, value in base.items()
            if value is not None
        ]
    )


def gas_problems(**values: float | None) -> list[Problem]:
    return run_lab(gas_frame(**values), BLOOD_GAS, CleanPlausibilityContext())


def test_the_committed_gas_values_satisfy_the_relations() -> None:
    assert gas_problems() == []


@pytest.mark.parametrize(
    ("name", "shift", "trips"),
    [
        ("HCO3", 0.9, False), ("HCO3", -0.9, False), ("HCO3", 1.1, True), ("HCO3", -1.1, True),
        ("BE (baz fazlası)", 2.9, False), ("BE (baz fazlası)", -2.9, False),
        ("BE (baz fazlası)", 3.1, True), ("BE (baz fazlası)", -3.1, True),
        ("SaO2", 2.9, False), ("SaO2", -2.9, False), ("SaO2", 3.1, True), ("SaO2", -3.1, True),
    ],
)  # fmt: skip
def test_the_gas_tolerances_are_1_3_and_3(name, shift, trips) -> None:
    base = {"HCO3": 28.2, "BE (baz fazlası)": 2.2, "SaO2": 88.7}
    found = gas_problems(**{name: base[name] + shift})
    assert bool(found) is trips, (name, shift)
    if trips:
        words = {"HCO3": "HCO3 ", "BE (baz fazlası)": "base excess", "SaO2": "SaO2 "}
        assert [p.message.startswith(words[name]) for p in found] == [True]


def test_the_gas_relations_with_zero_and_missing_values() -> None:
    # pCO2 0 gives an HCO3 of 0; pO2 0 gives an SaO2 of 0 (the relation holds for 0 and 0)
    assert [p.message[:5] for p in gas_problems(pCO2=0.0)] == ["HCO3 "]
    assert [p.message[:5] for p in gas_problems(pO2=0.0)] == ["SaO2 "]
    assert gas_problems(pO2=0.0, SaO2=0.0) == []
    # pCO2 0 and HCO3 0 hold the first relation, but the base excess of HCO3 0 is -24.1, not 2.2
    assert [p.message[:11] for p in gas_problems(pCO2=0.0, HCO3=0.0)] == ["base excess"]
    # a missing or NaN input skips the relations that use it
    assert gas_problems(pH=None) == []
    assert gas_problems(pCO2=math.nan) == []
    assert gas_problems(pO2=None) == []
    assert gas_problems(SaO2=None) == []
    assert gas_problems(**{"BE (baz fazlası)": None}) == []


def test_a_venous_gas_has_no_saturation_relation_but_keeps_the_other_two(context) -> None:
    """The venous saturation is not tied to pO2 (the Severinghaus curve is the arterial one)."""
    venous = lab_frame(
        {"SUB_CODE": BLOOD_GAS_CODE, "parametre": "sO2 (venöz)", "sonuc_sayisal": 20.0}
    )
    assert run_lab(gas_frame(SaO2=None).vstack(venous), BLOOD_GAS, context) == []
    off = gas_frame(SaO2=None, HCO3=31.0).vstack(venous)
    assert [p.message[:5] for p in run_lab(off, BLOOD_GAS, context)] == ["HCO3 "]


def ckd_epi(creatinine: float, age: int, sex: str) -> float:
    """CKD-EPI 2021 as the notes of the creatinine rows write it (the test's own oracle)."""
    female = sex == "K"
    kappa, alpha = (0.7, -0.241) if female else (0.9, -0.302)
    ratio = creatinine / kappa
    value = 142 * min(ratio, 1) ** alpha * max(ratio, 1) ** -1.200 * 0.9938**age
    return value * 1.012 if female else value


def egfr_problems(clean, context, creatinine, egfr, age=60, sex="E") -> list[Problem]:
    """S2's creatinine set with the given values, for a patient of that age and sex."""
    patient = pl.col("HASTA_ID") == PATIENT[2]
    anadata = clean[TABLE_ANADATA].with_columns(
        pl.when(patient)
        .then(pl.lit(age, dtype=pl.Int64))
        .otherwise(pl.col("TANI_YASI"))
        .alias("TANI_YASI"),
        pl.when(patient).then(pl.lit(sex)).otherwise(pl.col("CINSIYET")).alias("CINSIYET"),
    )
    rows = [
        {"SUB_CODE": CREATININE_CODE, "parametre": "Kreatinin", "sonuc_sayisal": creatinine},
        {"SUB_CODE": CREATININE_CODE, "parametre": EGFR, "sonuc_sayisal": egfr},
    ]
    frame = lab_frame(*[row for row in rows if row["sonuc_sayisal"] is not None])
    return check_clean_plausibility(
        {}, {TABLE_LAB: frame, TABLE_ANADATA: anadata}, context=context, only=EGFR_RELATION
    )


@pytest.mark.parametrize(
    ("sex", "age", "creatinine"),
    [
        ("E", 30, 0.7),  # creatinine / kappa below 1: the alpha branch
        ("E", 30, 1.2),  # above 1: the -1.200 branch
        ("K", 30, 0.5),
        ("K", 70, 1.0),
        ("E", 81, 0.98),
        ("K", 0, 0.3),
    ],
)
def test_egfr_within_1_of_ckd_epi_2021_in_both_branches(
    sex, age, creatinine, clean, context
) -> None:
    expected = ckd_epi(creatinine, age, sex)
    assert egfr_problems(clean, context, creatinine, round(expected), age, sex) == []
    for shift, trips in ((0.9, False), (-0.9, False), (1.1, True), (-1.1, True)):
        found = egfr_problems(clean, context, creatinine, expected + shift, age, sex)
        assert bool(found) is trips, (shift, expected)
        if trips:
            assert found[0].message.startswith("eGFR ")


def test_egfr_relation_skips_what_it_cannot_evaluate(clean, context) -> None:
    assert egfr_problems(clean, context, 0.0, 77.0) == [], "creatinine 0 is value_bounds' business"
    assert egfr_problems(clean, context, -1.0, 77.0) == []
    assert egfr_problems(clean, context, None, 77.0) == []
    assert egfr_problems(clean, context, 0.98, None) == []
    assert egfr_problems(clean, context, math.nan, 77.0) == []
    assert egfr_problems(clean, context, 0.98, math.inf) == []
    assert egfr_problems(clean, context, 0.98, 77.0, sex="?") == [], (
        "ana.vitals_bounds names the sex"
    )


def test_egfr_relation_without_an_age_or_an_anadata_row_is_skipped(clean, context) -> None:
    frame = lab_frame(
        {"SUB_CODE": CREATININE_CODE, "parametre": "Kreatinin", "sonuc_sayisal": 0.98},
        {"SUB_CODE": CREATININE_CODE, "parametre": EGFR, "sonuc_sayisal": 10.0},
    )
    no_age = clean[TABLE_ANADATA].with_columns(
        pl.when(pl.col("HASTA_ID") == PATIENT[2])
        .then(None)
        .otherwise(pl.col("TANI_YASI"))
        .alias("TANI_YASI")
    )
    for anadata in (no_age, clean[TABLE_ANADATA].filter(pl.col("HASTA_ID") != PATIENT[2])):
        found = check_clean_plausibility(
            {}, {TABLE_LAB: frame, TABLE_ANADATA: anadata}, context=context, only=EGFR_RELATION
        )
        assert found == []


# --- flags, limits, units and result sets, beyond the mutation cases ------------------------------------


def flag_problems(data: Data, context) -> list[Problem]:
    return data.problems(context, only=FLAG_AND_LIMITS)


@pytest.mark.parametrize(
    ("value", "flag", "trips"),
    [
        (5.0, False, False),  # exactly on the upper limit 5: not abnormal
        (5.0, True, True),
        (5.01, True, False),
        (5.01, False, True),
        (0.0, False, False),  # exactly on the lower limit 0: not abnormal
        (0.0, True, True),
        (-0.01, True, False),
        (-0.01, False, True),
        (2.5, False, False),
        (2.5, True, True),
    ],
)
def test_the_flag_is_true_exactly_outside_the_limits(
    value, flag, trips, built, clean, context
) -> None:
    data = fresh(built, clean)  # S2's CRP of 2026-03-12: limits 0..5
    edit(data, TABLE_LAB, lab(2, "2026-03-12", "L101850"), sonuc_sayisal=value, anormal_mi=flag)
    assert bool(flag_problems(data, context)) is trips


@pytest.mark.parametrize(
    ("value", "flag", "trips"),
    [(200.0, False, False), (200.0, True, True), (60.0, False, False), (59.9, True, False),
     (59.9, False, True), (0.0, True, False), (0.0, False, True)],
)  # fmt: skip
def test_a_null_upper_limit_does_not_count(value, flag, trips, built, clean, context) -> None:
    data = fresh(built, clean)  # S2's eGFR: the lower limit is 60 and there is no upper one
    edit(
        data, TABLE_LAB, lab(2, DAY_2, CREATININE_CODE, EGFR), sonuc_sayisal=value, anormal_mi=flag
    )
    assert bool(flag_problems(data, context)) is trips


def test_a_non_finite_value_is_left_to_value_bounds(built, clean, context) -> None:
    for value in (math.nan, math.inf, None):
        for flag in (True, False):
            data = fresh(built, clean)
            edit(
                data,
                TABLE_LAB,
                lab(2, DAY_2, GLUCOSE_CODE, "Glukoz"),
                sonuc_sayisal=value,
                anormal_mi=flag,
            )
            assert flag_problems(data, context) == [], (value, flag)


def test_a_missing_low_limit_means_zero(built, clean, context) -> None:
    """The reference may leave a lower limit blank; the table then holds 0."""
    blank = context.lab_reference.with_columns(
        pl.when(pl.col("parameter") == "CRP (kantitatif)").then(None).otherwise(pl.col(c)).alias(c)
        for c in ("low_m", "low_f")
    )
    blank_context = CleanPlausibilityContext(lab_reference=blank)
    data = fresh(built, clean)  # S2's CRP rows have ref_alt 0.0
    assert flag_problems(data, blank_context) == []
    edit(data, TABLE_LAB, lab(2, DAY_2, "L101850", "CRP (kantitatif)"), ref_alt=None)
    (problem,) = flag_problems(data, blank_context)
    assert "the limits are (none)..5.0 but the reference gives 0.0..5.0" in problem.message
    edit(data, TABLE_LAB, lab(2, DAY_2, "L101850", "CRP (kantitatif)"), ref_alt=1.0)
    (problem,) = flag_problems(data, blank_context)
    assert "the limits are 1.0..5.0 but the reference gives 0.0..5.0" in problem.message


def test_an_unknown_sex_checks_the_limits_that_do_not_depend_on_it(built, clean, context) -> None:
    data = fresh(built, clean)
    edit(data, TABLE_ANADATA, patient_row(2), CINSIYET="?")
    assert flag_problems(data, context) == [], (
        "sex-dependent limits cannot be checked, none is wrong"
    )
    # CRP has the same limits for both sexes: a wrong limit is still a defect
    edit(
        data, TABLE_LAB, lab(2, DAY_2, "L101850", "CRP (kantitatif)"), ref_ust=6.0, anormal_mi=True
    )
    (problem,) = flag_problems(data, context)
    assert problem.where == lab_where(2, DAY_2, "L101850", "CRP (kantitatif)")
    # HGB has sex-dependent limits: the same kind of error is not visible without the sex
    edit(data, TABLE_LAB, lab(2, DAY_2, HEMOGRAM_CODE, "HGB (Hemoglobin)"), ref_alt=11.0)
    assert len(flag_problems(data, context)) == 1


def test_the_sex_of_a_patient_comes_from_every_episode_of_the_patient(
    built, clean, context
) -> None:
    data = fresh(built, clean)
    second = clean[TABLE_ANADATA].filter(patient_row(3)).with_columns(
        pl.lit("B-SENTETIK-HASTA-0003-002").alias("SQ_EPISODE")
    )  # fmt: skip
    data.clean[TABLE_ANADATA] = pl.concat([clean[TABLE_ANADATA], second])
    assert data.problems(context) == [], "two episodes with the same sex change nothing"
    # contradicting sexes: the sex is unknown to the lab checks, which skip what depends on it, and
    # ana.vitals_bounds names the contradiction on both rows
    contradicting = second.with_columns(pl.lit("E").alias("CINSIYET"))
    for rows in (
        [clean[TABLE_ANADATA], contradicting],  # the true sex first
        [contradicting, clean[TABLE_ANADATA]],  # the other one first: the order decides nothing
    ):
        data.clean[TABLE_ANADATA] = pl.concat(rows)
        assert only_ids(data.problems(context)) == {VITALS}
        assert {p.message for p in data.problems(context)} == {
            "CINSIYET differs between the episodes of the patient"
        }


def test_the_age_comes_from_the_episode_of_the_result_set(built, clean, context) -> None:
    """S2 has a second episode at another age; its result sets are judged at that age, not at 81."""
    data = fresh(built, clean)
    second = clean[TABLE_ANADATA].filter(patient_row(2)).with_columns(
        pl.lit("B-SENTETIK-HASTA-0002-002").alias("SQ_EPISODE"),
        pl.lit(40, dtype=pl.Int64).alias("TANI_YASI"),
    )  # fmt: skip
    data.clean[TABLE_ANADATA] = pl.concat([clean[TABLE_ANADATA], second])
    assert data.problems(context, only=EGFR_RELATION) == [], "the 81-year-old episode is untouched"
    # a creatinine set of the second episode: 0.98 mg/dL in a man of 40 gives an eGFR of 97, not 77
    labs = data.clean[TABLE_LAB]
    again = labs.filter(lab(2, DAY_2, CREATININE_CODE)).with_columns(
        pl.lit("B-SENTETIK-HASTA-0002-002").alias("basvuru_id")
    )
    data.clean[TABLE_LAB] = pl.concat([labs, again])
    found = data.problems(context, only=EGFR_RELATION)
    assert [p.where for p in found] == [
        f"{PATIENT[2]} lab_clean[B-SENTETIK-HASTA-0002-002|{DAY_2}|{CREATININE_CODE}]"
    ]
    assert "age 40" in found[0].message


def test_a_product_name_matches_the_billed_one_without_regard_to_case_letters_and_spaces(
    built, clean, context
) -> None:
    """The name is compared folded: lower case, Turkish letters as plain ones, white space collapsed."""
    for spelled in (
        "iesef 1 g iv enjeksiyonluk cozeltI tozu",
        "  IESEF 1 G   IV ENJEKSIYONLUK COZELTI TOZU ",
        "İESEF 1 G IV ENJEKSİYONLUK ÇÖZELTİ TOZU",
    ):
        data = fresh(built, clean)
        edit(data, TABLE_RECETE, rx(2, "IESEF"), ilac_adi=spelled)
        assert data.problems(context, only=MATCHES) == [], spelled
    data = fresh(built, clean)
    edit(data, TABLE_RECETE, rx(2, "IESEF"), ilac_adi="IESEF 2 G IV ENJEKSIYONLUK COZELTI TOZU")
    assert len(data.problems(context, only=MATCHES)) == 2


def test_a_unit_is_compared_exactly(built, clean, context) -> None:
    for unit in ("MG/DL", "mg/dl", " mg/dL", "mg/dL "):
        data = fresh(built, clean)
        edit(data, TABLE_LAB, lab(2, DAY_2, GLUCOSE_CODE, "Glukoz"), birim=unit)
        assert len(data.problems(context, only=UNIT)) == 1, unit


def venous_gas(story: int, on: str, context) -> pl.DataFrame:
    """A complete venous gas set (the reference's `blood_gas_venous` rows) with a plausible content."""
    values = {
        "pH": 7.37, "pCO2": 46.0, "pO2": 40.0, "HCO3": 26.3, "BE (baz fazlası)": 1.4,
        "sO2 (venöz)": 70.0, "Laktat (kan gazı)": 1.2, "Sodyum (kan gazı)": 140.0,
        "Potasyum (kan gazı)": 4.0, "İyonize kalsiyum (kan gazı)": 1.2,
    }  # fmt: skip
    reference = context.lab_reference.filter(
        (pl.col("code") == BLOOD_GAS_CODE) & (pl.col("variant") == "blood_gas_venous")
    )
    value = pl.col("parameter").replace_strict(values, return_dtype=pl.Float64)
    male = PATIENT[story] == PATIENT[2]  # S2 is a man (E), S3 a woman (K)
    low, high = ("low_m", "high_m") if male else ("low_f", "high_f")
    return reference.select(
        pl.lit(PATIENT[story]).alias("HASTA_ID"),
        pl.lit(EPISODE[story]).alias("basvuru_id"),
        pl.lit(BLOOD_GAS_CODE).alias("SUB_CODE"),
        pl.col("parameter").alias("parametre"),
        value.alias("sonuc_sayisal"),
        pl.lit(None, dtype=pl.String).alias("sonuc_nitel"),
        pl.col("unit").alias("birim"),
        pl.col(low).alias("ref_alt"),
        pl.col(high).alias("ref_ust"),
        ((value < pl.col(low)) | (value > pl.col(high))).alias("anormal_mi"),
        pl.lit("Biyokimya").alias("organ_sistemi"),
        pl.lit("showcase").alias("kohort"),
        pl.lit(on[:4]).alias("donem"),
        pl.lit(day(on)).dt.cast_time_unit("ns").alias("tarih"),
    )


def test_a_venous_gas_in_place_of_the_arterial_one_passes_every_check(
    built, clean, context
) -> None:
    """The reference has two variants of the gas code; the set is read against the one it is."""
    data = fresh(built, clean)
    arterial = lab(2, DAY_2, BLOOD_GAS_CODE)
    labs = data.clean[TABLE_LAB]
    data.clean[TABLE_LAB] = pl.concat(
        [
            labs.filter(~arterial),
            venous_gas(2, DAY_2, context).select(labs.columns).cast(labs.schema),
        ]
    )
    assert data.clean[TABLE_LAB].height == 207
    assert [str(p) for p in data.problems(context)] == []
    # the arterial limits on a venous set are wrong for it
    arterial_limits = labs.filter(arterial).select("parametre", "ref_alt", "ref_ust")
    mixed = data.clean[TABLE_LAB].join(arterial_limits, on="parametre", how="left", suffix="_a")
    mixed = mixed.with_columns(
        pl.when(arterial).then(pl.col("ref_alt_a").fill_null(pl.col("ref_alt"))).otherwise(pl.col("ref_alt")).alias("ref_alt"),
        pl.when(arterial).then(pl.col("ref_ust_a").fill_null(pl.col("ref_ust"))).otherwise(pl.col("ref_ust")).alias("ref_ust"),
    ).select(labs.columns)  # fmt: skip
    data.clean[TABLE_LAB] = mixed
    found = data.problems(context, only=FLAG_AND_LIMITS)
    assert found and all("for sex E" in p.message for p in found)


def test_a_set_with_the_saturation_of_the_other_variant_is_read_against_that_variant(
    built, clean, context
) -> None:
    """Nine arterial parameters and one venous: the venous variant lists all ten, so it wins."""
    data = fresh(built, clean)
    renamed = lab(2, DAY_2, BLOOD_GAS_CODE, "SaO2")
    edit(data, TABLE_LAB, renamed, parametre="sO2 (venöz)")
    found = data.problems(context)
    assert only_ids(found) == {FLAG_AND_LIMITS}, "complete as a venous set, with arterial limits"
    assert lab_where(2, DAY_2, BLOOD_GAS_CODE, "sO2 (venöz)") in {p.where for p in found}
    assert all("but the reference gives" in p.message for p in found)


def test_a_set_whose_code_is_not_in_the_reference_cannot_be_compared(built, clean, context) -> None:
    unbilled = fresh(built, clean)
    edit(unbilled, TABLE_LAB, lab(2, DAY_2, "L106240"), SUB_CODE="L999999")
    assert [p.message for p in unbilled.problems(context, only=SETS)] == [
        f"result set of L999999 on {DAY_2} (episode {EPISODE[2]}) has 1 row(s) and no billed lab line",
        f"billed lab line L106240 on {DAY_2} (episode {EPISODE[2]}) has no result set in lab_clean",
    ]
    # billed under that code too, the set matches the bill but has nothing to be compared with
    billed = fresh(built, clean)
    edit(billed, TABLE_LAB, lab(2, DAY_2, "L106240"), SUB_CODE="L999999")
    edit(
        billed,
        TABLE_PROCEDURES,
        (pl.col("patient_id") == PATIENT[2]) & (pl.col("procedure_code") == "L106240"),
        procedure_code="L999999",
    )
    (problem,) = billed.problems(context, only=SETS)
    assert problem.where == lab_where(2, DAY_2, "L999999")
    assert problem.message == (
        "result set has 1 row(s), the reference variant (none) lists (none): "
        "no parameter of the set belongs to the reference of L999999"
    )


def test_the_troponin_is_billed_twice_on_one_day_and_gives_two_result_sets(built, clean) -> None:
    """The facts that the cases `second_troponin_set_removed` and `second_set_for_one_billed_line` use."""
    billed = built.tables[TABLE_PROCEDURES].filter(pl.col("procedure_category") == "laboratuvar")
    troponin = billed.filter(pl.col("procedure_code") == "L107360")
    assert troponin.height == 2 and troponin["procedure_date"].n_unique() == 1
    assert clean[TABLE_LAB].filter(lab(7, "2026-02-19", "L107360")).height == 2
    assert (
        billed.height == 48
        and clean[TABLE_LAB].select("HASTA_ID", "tarih", "SUB_CODE").n_unique() == 47
    )


# --- prescriptions, beyond the mutation cases --------------------------------------------------------


def recete_frame(clean, **changes) -> pl.DataFrame:
    """S7's single prescription row (PARTEMOL, 1 flakon) with `changes` laid over it."""
    row = clean[TABLE_RECETE].filter(patient_row(7))
    assert row.height == 1
    return row.with_columns(
        [pl.lit(value, dtype=row.schema[column]).alias(column) for column, value in changes.items()]
    )


def recete_problems(frame: pl.DataFrame, check: str, context) -> list[Problem]:
    return check_clean_plausibility({}, {TABLE_RECETE: frame}, context=context, only=check)


@pytest.mark.parametrize(
    ("dose", "miktar", "said"),
    [
        ("1 kutu", 1, None), ("5 flakon", 5, None), ("3 şişe", 3, None), ("3 sise", 3, None),
        ("5 ampul", 5, None), ("3 torba", 3, None), ("6 enjektör", 6, None),
        ("6 enjektor", 6, None), ("20 tablet", 20, None), ("2 kapsül", 2, None),
        ("2 kapsul", 2, None), ("10 kutu", 10, None), ("1000 tablet", 1000, None),
        ("1 box", 1, "uses the English unit word box"),
        ("1 vial", 1, "uses the English unit word vial"),
        ("3 bag", 3, "uses the English unit word bag"),
        ("2 capsule", 2, "uses the English unit word capsule"),
        ("5 ampoule", 5, "uses the English unit word ampoule"),
        ("6 syringe", 6, "uses the English unit word syringe"),
        ("1 bottle", 1, "uses the English unit word bottle"),
        ("0 kutu", 1, "is not a positive count"),
        ("-1 kutu", 1, "is not a positive count"),
        ("1,5 kutu", 1, "is not a positive count"),
        ("1.5 kutu", 1, "is not a positive count"),
        ("01 kutu", 1, "is not a positive count"),
        ("kutu 1", 1, "is not a positive count"),
        ("1 kutu x", 1, "is not a positive count"),
        ("1kutu", 1, "is not a positive count"),
        ("", 1, "is not a positive count"),
        ("1 kutu", 2, "the count 1 differs from miktar 2"),
        ("1 kutu", 0, "the count 1 differs from miktar 0"),
        ("1 kutu", None, "the count 1 differs from miktar (none)"),
        ("99999999999999999999 kutu", 1, "differs from miktar 1"),
    ],
)  # fmt: skip
def test_a_dose_is_a_positive_count_and_a_turkish_unit_equal_to_miktar(
    dose, miktar, said, clean, context
) -> None:
    frame = recete_frame(clean, dozaj_ham=dose, miktar=miktar)
    found = recete_problems(frame, DOSE, context)
    if said is None:
        assert found == []
    else:
        assert len(found) == 1 and said in found[0].message, (dose, [str(p) for p in found])
        if "English" in said:
            assert "closed list" not in found[0].message, "an English word is not also 'unknown'"


def test_the_dose_units_are_turkish_and_the_english_ones_are_defects(clean) -> None:
    units = set(DOSE_UNITS)
    assert not units & set(ENGLISH_UNITS)
    assert set(ENGLISH_UNITS) == {"bottle", "vial", "bag", "box", "capsule", "ampoule", "syringe"}
    assert {"kutu", "flakon", "şişe", "ampul", "torba", "enjektör", "tablet"} <= units
    used = set(clean[TABLE_RECETE]["dozaj_ham"].str.extract(r"^\d+ (\S+)$", 1))
    assert used <= units and used, used


ENJ = "ENJEKSIYONLUK COZELTI"
ROUTE_ITEMS = [
    # (ilac_adi, ilac_adi_ham, route, trips)
    ("IESEF 1 G IV " + ENJ, "IESEF 1 G IV ENJEKSİYONLUK ÇÖZELTİ", "Intravenöz", False),
    ("IESEF 1 G IV " + ENJ, "IESEF 1 G IV ENJEKSİYONLUK ÇÖZELTİ", "İntramusküler/İntravenöz", False),
    ("IESEF 1 G IV " + ENJ, "IESEF 1 G IV ENJEKSİYONLUK ÇÖZELTİ", "Subkütan", False),
    ("IESEF 1 G IV " + ENJ, "IESEF 1 G IV ENJEKSİYONLUK ÇÖZELTİ", "Ağızdan (Oral)", True),
    ("IESEF 1 G IV " + ENJ, "IESEF 1 G IV ENJEKSİYONLUK ÇÖZELTİ", "İnhalasyon", True),
    ("X 5 MG 30 TB", "X 5 MG TABLET, 30 ADET", "Ağızdan (Oral)", False),
    ("X 5 MG 30 TB", "X 5 MG TABLET, 30 ADET", "Intravenöz", True),
    ("X 5 MG 30 TB", "X 5 MG TABLET, 30 ADET", "Subkütan", True),
    ("X 5 MG 30 TB", "X 5 MG TABLET, 30 ADET", "İnhalasyon", True),
    ("Y 20 KAP", "Y 20 MG SERT KAPSÜL, 20 ADET", "Ağızdan (Oral)", False),
    ("Y 20 KAP", "Y 20 MG SERT KAPSÜL, 20 ADET", "İntramusküler/İntravenöz", True),
    ("Z 10 MG 28 FK TB", "Z 10 MG FİLM KAPLI TABLET", "Ağızdan (Oral)", False),
    ("Z 10 MG 28 FK TB", "Z 10 MG FİLM KAPLI TABLET", "Intravenöz", True),
    ("B 0.5 MG NEBUL", "B 0,5 MG/2 ML NEBÜL, 20 ADET", "İnhalasyon", False),
    ("B 0.5 MG NEBUL", "B 0,5 MG/2 ML NEBÜL, 20 ADET", "Ağızdan (Oral)", True),
    ("B 0.5 MG NEBUL", "B 0,5 MG/2 ML NEBÜL, 20 ADET", "Intravenöz", True),
    # a nebuliser solution sold in vials: the vial does not make it an injection
    ("IPRAVENT NEBULIZAYON (20 FLAKON)", "İPRAVENT NEBÜLİZASYON İÇİN İNHALASYON ÇÖZELTİSİ, 20 FLAKON", "İnhalasyon", False),
    ("IPRAVENT NEBULIZAYON (20 FLAKON)", "İPRAVENT NEBÜLİZASYON İÇİN İNHALASYON ÇÖZELTİSİ, 20 FLAKON", "Intravenöz", True),
    # a tablet sold in a bottle: the bottle does not make it a vial
    ("W 500 MG 30 TB", "W 500 MG 30 TABLET FLAKON", "Ağızdan (Oral)", False),
    ("W 500 MG 30 TB", "W 500 MG 30 TABLET FLAKON", "Intravenöz", True),
    # container words alone (vial, ampoule, bag) make a parenteral product
    ("Q 1 FLK", "Q 1 FLAKON", "Intravenöz", False),
    ("Q 1 FLK", "Q 1 FLAKON", "Ağızdan (Oral)", True),
    ("R 2 ML AMP", "R 2 ML AMPUL", "İntramusküler/İntravenöz", False),
    ("R 2 ML AMP", "R 2 ML AMPUL", "Ağızdan (Oral)", True),
    ("S %0,9 TORBA", "S %0,9 PP-TORBA 500 ML", "Intravenöz", False),
    ("S %0,9 TORBA", "S %0,9 PP-TORBA 500 ML", "Ağızdan (Oral)", True),
    # each container word alone, with no injection word beside it
    ("T %5 SOLUSYON", "T %5 SOLÜSYON, 500 ML TORBA", "Intravenöz", False),
    ("T %5 SOLUSYON", "T %5 SOLÜSYON, 500 ML TORBA", "Ağızdan (Oral)", True),
    ("R 2 ML", "R 2 ML AMPUL", "İntramusküler/İntravenöz", False),
    ("R 2 ML", "R 2 ML AMPUL", "Ağızdan (Oral)", True),
    ("Q 1 ADET", "Q 1 ADET FLAKON", "Ağızdan (Oral)", True),
    # the injection words, written the way the names write them
    ("A IV 5 MG", "A 5 MG", "Intravenöz", False),
    ("A IV 5 MG", "A 5 MG", "Ağızdan (Oral)", True),
    ("A I.V. 5 MG", "A I.V. 5 MG", "Intravenöz", False),
    ("A I.V. 5 MG", "A I.V. 5 MG", "Ağızdan (Oral)", True),
    ("A 5 MG IM/IV", "A 5 MG IM/IV", "Ağızdan (Oral)", True),
    ("A 5 MG ENJ", "A 5 MG", "Ağızdan (Oral)", True),
    ("A INF 5 MG", "A 5 MG", "Ağızdan (Oral)", True),
    ("ENJEKTÖR", "KULLANIMA HAZIR ENJEKTÖR", "Subkütan", False),
    ("İNFÜZYON ÇÖZELTİSİ", "İNFÜZYON ÇÖZELTİSİ, 1000 ML", "Intravenöz", False),
    ("İNFÜZYON ÇÖZELTİSİ", "İNFÜZYON ÇÖZELTİSİ, 1000 ML", "Ağızdan (Oral)", True),
    # a word inside another word is not the word
    ("CLIVIA 5 MG 30 TB", "CLIVIA 5 MG TABLET", "Ağızdan (Oral)", False),
    ("TABLETLI SURUP", "SURUP", "Ağızdan (Oral)", False),
    # low-molecular-weight heparins are subcutaneous
    ("CLEXANE 4000 ENJ", "CLEXANE ENJEKSİYONLUK ÇÖZELTİ", "Subkütan", False),
    ("CLEXANE 4000 ENJ", "CLEXANE ENJEKSİYONLUK ÇÖZELTİ", "Intravenöz", True),
    ("CLEXANE 4000 ENJ", "CLEXANE ENJEKSİYONLUK ÇÖZELTİ", "İntramusküler/İntravenöz", True),
    ("FRAXIPARINE 0.4 ML", "FRAXIPARINE 0,4 ML ENJEKTÖR", "Intravenöz", True),
    ("ENOKSAPARIN 40 MG", "ENOKSAPARİN ENJEKTÖR", "Subkütan", False),
    # a name with no word of any class: any route of the vocabulary is accepted
    ("ABC 5 MG", "ABC 5 MG", "Intravenöz", False),
    ("ABC 5 MG", "ABC 5 MG", "Ağızdan (Oral)", False),
    ("ABC 5 MG", "ABC 5 MG", "İnhalasyon", False),
    # the two classes together are a contradiction whatever the route
    ("W TABLET", "W TABLET ENJEKSIYON", "Ağızdan (Oral)", True),
    ("W TABLET", "W TABLET ENJEKSIYON", "Intravenöz", True),
]  # fmt: skip


@pytest.mark.parametrize(
    ("name", "raw", "route", "trips"),
    ROUTE_ITEMS,
    ids=[f"{name[:22]}-{route}" for name, _, route, _ in ROUTE_ITEMS],
)
def test_the_route_fits_the_words_of_the_product_name(
    name, raw, route, trips, clean, context
) -> None:
    frame = recete_frame(clean, ilac_adi=name, ilac_adi_ham=raw, verilis_yolu=route)
    assert bool(recete_problems(frame, ROUTE, context)) is trips


def test_a_route_outside_the_vocabulary_or_missing_is_a_defect_whatever_the_name(
    clean, context
) -> None:
    for route in ("Oral", "IV", "intravenöz", "İntravenöz", "Ağızdan", "", " "):
        found = recete_problems(recete_frame(clean, verilis_yolu=route), ROUTE, context)
        assert len(found) == 1 and "is not in the closed vocabulary" in found[0].message, route
    found = recete_problems(recete_frame(clean, verilis_yolu=None), ROUTE, context)
    assert [p.message.split(": ", 1)[1] for p in found] == ["the route is missing"]


def test_the_route_words_are_folded_ascii_and_each_occurs_in_a_product_name(clean) -> None:
    for kind, words in ROUTE_WORDS.items():
        assert words, kind
        for word in words:
            assert word == fold_text(word), (kind, word)
            assert word.isascii() and word == word.strip(), (kind, word)
    names = " ".join(
        fold_text(f"{a} {b}") for a, b in zip(clean[TABLE_RECETE]["ilac_adi"], clean[TABLE_RECETE]["ilac_adi_ham"], strict=True)
    )  # fmt: skip
    for word in (
        "enjeksiyon",
        "enjektor",
        "infuzyon",
        "pp-torba",
        "i.v.",
        "im/iv",
        "nebul",
        "tablet",
        "clexane",
    ):
        assert word in names, word
    assert re.search(r"\biv\b", names)


def test_the_route_vocabulary_is_what_the_committed_table_uses(clean) -> None:
    used = set(clean[TABLE_RECETE]["verilis_yolu"])
    assert used == set(ROUTES)
    assert set(PARENTERAL_ROUTES) == {"Intravenöz", "İntramusküler/İntravenöz", "Subkütan"}
    # the spellings are the committed ones: a plain capital I in Intravenöz, a dotted İ in the others
    assert "Intravenöz".startswith("I") and "İntramusküler/İntravenöz".startswith("İ")


def test_the_required_columns_are_the_ten_of_the_brief() -> None:
    assert REQUIRED_RECETE_COLUMNS == (
        "HASTA_ID", "RECETE_TARIH", "RF_EPISODE", "ilac_adi", "ilac_adi_ham", "dozaj_ham",
        "verilis_yolu", "miktar", "kohort", "donem",
    )  # fmt: skip


def test_the_columns_that_may_be_null_are_not_required(clean, context) -> None:
    frame = clean[TABLE_RECETE]
    for column in ("gun", "doz_mg", "doz_birimi", "siklik"):
        assert frame[column].null_count() > 0, column
        assert column not in REQUIRED_RECETE_COLUMNS
    all_null = frame.with_columns(
        pl.lit(None, dtype=pl.Int64).alias("gun"),
        pl.lit(None, dtype=pl.Int64).alias("siklik"),
        pl.lit(None, dtype=pl.String).alias("doz_birimi"),
    )
    assert recete_problems(all_null, REQUIRED, context) == []


def test_zero_is_not_missing_and_a_blank_is(clean, context) -> None:
    assert recete_problems(recete_frame(clean, miktar=0), REQUIRED, context) == []
    for blank in ("", " ", "\t"):
        found = recete_problems(recete_frame(clean, dozaj_ham=blank), REQUIRED, context)
        assert len(found) == 1 and found[0].message.endswith(": dozaj_ham"), repr(blank)


# --- vitals, beyond the mutation cases -------------------------------------------------------------


def vitals_frame(clean, **changes) -> pl.DataFrame:
    """S2's anadata row with a consistent set of vital signs and `changes` laid over it."""
    values = {
        "KB-S": 200,
        "KB-D": 40,
        "Nabiz": 80,
        "SPO2": 97,
        "Boy": 170,
        "Kilo": 70.0,
        "TANI_YASI": 60,
    }
    values.update(changes)
    if "BMI" not in changes and values["Boy"] and values["Kilo"] is not None:
        values["BMI"] = round(values["Kilo"] / (values["Boy"] / 100) ** 2, 1)
    row = clean[TABLE_ANADATA].filter(patient_row(2))
    return row.with_columns(
        [pl.lit(value, dtype=row.schema[column]).alias(column) for column, value in values.items()]
    )


def vitals_problems(frame: pl.DataFrame, context) -> list[Problem]:
    return check_clean_plausibility({}, {TABLE_ANADATA: frame}, context=context, only=VITALS)


def test_a_consistent_set_of_vital_signs_raises_nothing(clean, context) -> None:
    assert vitals_problems(vitals_frame(clean), context) == []


@pytest.mark.parametrize(
    ("column", "low", "high"), [(c, lo, hi) for c, (lo, hi) in VITALS_BOUNDS.items()]
)
def test_a_vital_sign_is_inside_its_bounds_up_to_the_limits(
    column, low, high, clean, context
) -> None:
    def run(value):
        return vitals_problems(vitals_frame(clean, **{column: value}), context)

    def shown(value: float) -> str:
        return f"{value:.1f}" if column == "Kilo" else f"{value:g}"

    for inside in (low, high, (low + high) / 2):
        assert run(inside) == [], (column, inside)
    for outside in (low - 1, high + 1):
        (problem,) = run(outside)
        assert problem.message == f"{column} {shown(outside)} is outside {low:g}..{high:g}"
    # zero is a defect exactly when the lower bound is above it
    assert bool(run(0)) is (low > 0), column
    # a missing value is named, not skipped
    assert [p.message for p in run(None)] == [f"{column} is missing"]


def test_the_diastolic_pressure_is_below_the_systolic(clean, context) -> None:
    assert vitals_problems(vitals_frame(clean, **{"KB-S": 100, "KB-D": 99}), context) == []
    (problem,) = vitals_problems(vitals_frame(clean, **{"KB-S": 100, "KB-D": 100}), context)
    assert problem.message == "KB-D 100 is not below KB-S 100"
    (problem,) = vitals_problems(vitals_frame(clean, **{"KB-S": 100, "KB-D": 101}), context)
    assert problem.message == "KB-D 101 is not below KB-S 100"


@pytest.mark.parametrize(
    ("bmi", "trips"), [(24.3, False), (24.14, False), (24.33, True), (24.1, True), (24.2, False)]
)
def test_bmi_is_kilo_over_height_squared_within_a_tenth(bmi, trips, clean, context) -> None:
    # 70 kg and 170 cm: 24.2214
    assert bool(vitals_problems(vitals_frame(clean, BMI=bmi), context)) is trips


def test_a_zero_height_gives_one_finding_not_an_infinite_bmi(clean, context) -> None:
    (problem,) = vitals_problems(vitals_frame(clean, Boy=0), context)
    assert problem.message == "Boy 0 is outside 120..210"


def test_the_sex_is_e_or_k(clean, context) -> None:
    for sex in SEX_CODES:
        assert (
            vitals_problems(
                vitals_frame(clean).with_columns(pl.lit(sex).alias("CINSIYET")), context
            )
            == []
        )
    for sex in ("e", "M", "F", "", None):
        found = vitals_problems(
            vitals_frame(clean).with_columns(pl.lit(sex, dtype=pl.String).alias("CINSIYET")),
            context,
        )
        assert len(found) == 1 and "is neither E nor K" in found[0].message, sex


def test_several_defects_of_one_row_are_one_finding(clean, context) -> None:
    frame = vitals_frame(clean, SPO2=120, Nabiz=10)
    (problem,) = vitals_problems(frame, context)
    assert problem.message == "Nabiz 10 is outside 30..220; SPO2 120 is outside 50..100"


# --- 6. the judgment tables --------------------------------------------------------------------------


@pytest.fixture(scope="module")
def reference() -> pl.DataFrame:
    """The reference CSV read here, apart from the module under test."""
    limits = ["ref_low_male", "ref_high_male", "ref_low_female", "ref_high_female"]
    return pl.read_csv(
        _REPO / LAB_REFERENCE_PATH, schema_overrides=dict.fromkeys(limits, pl.Float64)
    ).with_columns(pl.col("unit").fill_null(""))


def test_the_hard_bounds_are_the_table_of_the_clinical_review() -> None:
    """Section (f) of reports/synthetic-data/2026-10-17-c2-lab-clinical-review.md, by parametre.

    A widened bound is a visible change here: a committed row that trips a bound is reported, not
    made to pass. `sO2 (venöz)` is the one entry that the review does not have.
    """
    hemogram = {
        "WBC (Lökosit)": (0.1, 100),
        "NEU# (Nötrofil)": (0, 100),  # also capped by the WBC of the set
        "LYM# (Lenfosit)": (0, 100),
        "MONO# (Monosit)": (0, 100),
        "EOS# (Eozinofil)": (0, 100),
        "BASO# (Bazofil)": (0, 100),
        "RBC (Eritrosit)": (1.0, 8.5),
        "HGB (Hemoglobin)": (3.0, 23.0),
        "HCT (Hematokrit)": (10, 70),
        "MCV": (50, 130),
        "MCH": (15, 45),
        "MCHC": (28, 36.5),
        "RDW-CV": (10, 40),
        "PLT (Trombosit)": (2, 1500),
        "MPV": (4, 16),
    }
    gas = {
        "pH": (6.60, 7.80),
        "pCO2": (8, 150),
        "pO2": (15, 650),
        "HCO3": (2, 55),
        "BE (baz fazlası)": (-35, 35),
        "SaO2": (30, 100),
        "sO2 (venöz)": (10, 100),  # not in the review: this module's decision
        "Laktat (kan gazı)": (0.2, 30),
        "İyonize kalsiyum (kan gazı)": (0.40, 2.20),
        "Sodyum (kan gazı)": (100, 175),
        "Potasyum (kan gazı)": (1.5, 9.0),
    }
    urine = {
        "Dansite (özgül ağırlık)": (1.001, 1.045),
        "pH": (4.5, 9.0),
        "Mikroskopi: lökosit": (0, 500),
        "Mikroskopi: eritrosit": (0, 500),
    }
    single = {
        ("L101850", "CRP (kantitatif)"): (0, 500),
        ("L106240", "Prokalsitonin"): (0, 500),
        ("L102090", "D-dimer"): (0, 35000),
        ("L107360", "hs-Troponin I"): (0, 100000),
        ("L102890", "Glukoz"): (20, 1500),
        ("L107420", "Üre"): (3, 400),
        ("L104780", "Kreatinin"): (0.2, 25),
        ("L104780", "eGFR (CKD-EPI 2021, hesaplanan)"): (1, 150),
        ("L106910", "Sodyum"): (100, 175),
        ("L106150", "Potasyum"): (1.5, 9.0),
        ("L100300", "ALT"): (1, 20000),
        ("L101280", "AST"): (1, 20000),
    }
    expected = {("L107020", name): bounds for name, bounds in hemogram.items()}
    expected |= {("L103900", name): bounds for name, bounds in gas.items()}
    expected |= {("L107010", name): bounds for name, bounds in urine.items()}
    expected |= single
    assert LAB_HARD_BOUNDS == expected
    assert len(expected) == 15 + 11 + 4 + 12


def test_the_tolerances_and_constants_are_the_ones_of_the_brief() -> None:
    assert plausibility_clean.DIFFERENTIAL_TOLERANCE == 0.05
    assert plausibility_clean.HCT_PER_HGB_RANGE == (2.74, 3.57)
    assert plausibility_clean.INDEX_TOLERANCE == 0.03
    assert (plausibility_clean.HENDERSON_PK, plausibility_clean.HENDERSON_SOLUBILITY) == (
        6.1,
        0.0307,
    )
    assert plausibility_clean.HCO3_TOLERANCE == 1.0
    assert plausibility_clean.BASE_EXCESS_SLOPE == 0.93
    assert plausibility_clean.BASE_EXCESS_HCO3_NORMAL == 24.4
    assert plausibility_clean.BASE_EXCESS_PH_SLOPE == 14.8
    assert plausibility_clean.BASE_EXCESS_PH_NORMAL == 7.4
    assert plausibility_clean.BASE_EXCESS_TOLERANCE == 3.0
    assert plausibility_clean.SEVERINGHAUS_NUMERATOR == 23400.0
    assert plausibility_clean.SEVERINGHAUS_LINEAR == 150.0
    assert plausibility_clean.SAO2_TOLERANCE == 3.0
    assert plausibility_clean.EGFR_TOLERANCE == 1.0
    assert plausibility_clean.BMI_TOLERANCE == 0.1
    assert plausibility_clean.CKD_EPI_BASE == 142.0
    assert plausibility_clean.CKD_EPI_AGE_FACTOR == 0.9938
    assert plausibility_clean.CKD_EPI_FEMALE_FACTOR == 1.012
    assert plausibility_clean.CKD_EPI_KAPPA == {"E": 0.9, "K": 0.7}
    assert plausibility_clean.CKD_EPI_ALPHA == {"E": -0.302, "K": -0.241}
    assert plausibility_clean.CKD_EPI_HIGH_EXPONENT == -1.200
    assert plausibility_clean.KOHORT == "showcase"
    assert plausibility_clean.LAB_CATEGORY == "laboratuvar"


def test_the_vital_bounds_are_the_table_of_the_brief() -> None:
    assert VITALS_BOUNDS == {
        "KB-S": (70, 260),
        "KB-D": (30, 150),
        "Nabiz": (30, 220),
        "SPO2": (50, 100),
        "Boy": (120, 210),
        "Kilo": (30, 200),
        "TANI_YASI": (0, 110),
    }
    assert SEX_CODES == ("E", "K")


def test_the_route_words_are_the_judgment_of_the_module() -> None:
    assert ROUTE_WORDS == {
        "injection_inside": ("enjeksiyon", "enjektor", "infuzyon", "pp-torba", "i.v.", "im/iv"),
        "injection_whole": ("iv",),
        "container_whole": ("flakon", "flk", "ampul", "amp", "enj", "inf", "torba"),
        "oral_inside": ("tablet", "kapsul", "film kapli"),
        "oral_whole": ("tb",),
        "inhalation_inside": ("nebul", "inhalasyon"),
        "lmwh_inside": (
            "clexane", "enoksaparin", "enoxaparin", "fraxiparine", "fraksiparin", "nadroparin",
            "fragmin", "dalteparin",
        ),
    }  # fmt: skip
    assert DOSE_UNITS == (
        "kutu", "flakon", "şişe", "sise", "ampul", "torba", "enjektör", "enjektor", "tablet",
        "kapsül", "kapsul",
    )  # fmt: skip


def test_the_lab_schema_of_the_tests_is_the_committed_one(clean) -> None:
    assert dict(clean[TABLE_LAB].schema) == LAB_SCHEMA


def test_the_hard_bounds_cover_every_parameter_of_the_billed_codes(reference, clean) -> None:
    """Every parameter of the 14 billed codes, not only those that occur, has an entry."""
    codes = set(clean[TABLE_LAB]["SUB_CODE"])
    assert len(codes) == 14
    listed = reference.filter(pl.col("ek2b_code").is_in(sorted(codes)))
    wanted = set(zip(listed["ek2b_code"], listed["result_parameter"], strict=True))
    assert wanted == set(LAB_HARD_BOUNDS) | set(LAB_STRIP_PARAMETERS)
    assert len(wanted) == 48 and len(LAB_HARD_BOUNDS) == 42 and len(LAB_STRIP_PARAMETERS) == 6
    assert not set(LAB_HARD_BOUNDS) & set(LAB_STRIP_PARAMETERS)
    occurring = set(zip(clean[TABLE_LAB]["SUB_CODE"], clean[TABLE_LAB]["parametre"], strict=True))
    assert len(occurring) == 47 and occurring <= wanted
    assert wanted - occurring == {(BLOOD_GAS_CODE, "sO2 (venöz)")}


def test_the_hard_intervals_are_ordered_and_contain_the_reference_limits(reference) -> None:
    """A normal range is never a bug. The reference writes 0 for "no lower limit" (ALT, AST: 0..41)."""
    for (code, parameter), (low, high) in LAB_HARD_BOUNDS.items():
        assert low < high, (code, parameter)
        rows = reference.filter(
            (pl.col("ek2b_code") == code) & (pl.col("result_parameter") == parameter)
        )
        assert rows.height >= 1, (code, parameter)
        for column in ("ref_low_male", "ref_high_male", "ref_low_female", "ref_high_female"):
            for limit in rows[column].drop_nulls():
                no_lower_limit = column.startswith("ref_low") and limit == 0.0
                assert low <= limit <= high or no_lower_limit, (code, parameter, column, limit)


def test_the_strip_parameters_are_the_qualitative_rows_of_the_reference(reference) -> None:
    columns = ["ref_low_male", "ref_high_male", "ref_low_female", "ref_high_female"]
    qualitative = reference.filter(pl.all_horizontal([pl.col(c).is_null() for c in columns]))
    assert set(zip(qualitative["ek2b_code"], qualitative["result_parameter"], strict=True)) == set(
        LAB_STRIP_PARAMETERS
    )
    assert set(qualitative["normal_value_range"]) == {"Negatif"}


def test_the_named_parameters_exist_under_their_codes_in_the_reference(reference) -> None:
    names = {
        plausibility_clean.HEMOGRAM_CODE: [
            plausibility_clean.WBC,
            *plausibility_clean.DIFFERENTIAL_PARAMETERS,
            plausibility_clean.RBC,
            plausibility_clean.HGB,
            plausibility_clean.HCT,
            plausibility_clean.MCV,
            plausibility_clean.MCH,
        ],
        plausibility_clean.BLOOD_GAS_CODE: [
            plausibility_clean.PH,
            plausibility_clean.PCO2,
            plausibility_clean.PO2,
            plausibility_clean.HCO3,
            plausibility_clean.BASE_EXCESS,
            plausibility_clean.SAO2,
        ],
        plausibility_clean.CREATININE_CODE: [
            plausibility_clean.CREATININE,
            plausibility_clean.EGFR,
        ],
    }
    for code, parameters in names.items():
        listed = set(reference.filter(pl.col("ek2b_code") == code)["result_parameter"])
        assert set(parameters) <= listed, code
    assert (plausibility_clean.HEMOGRAM_CODE, plausibility_clean.BLOOD_GAS_CODE) == (
        "L107020",
        "L103900",
    )
    assert (plausibility_clean.CREATININE_CODE, plausibility_clean.URINALYSIS_CODE) == (
        "L104780",
        "L107010",
    )


def test_the_reference_has_the_set_sizes_the_notes_give(reference) -> None:
    """Multi-parameter tests emit every parameter under their one line: hemogram 15, urinalysis 10, gas 10."""
    sizes = reference.group_by("ek2b_code", "test_key").len()
    size = {
        (c, k): n
        for c, k, n in zip(sizes["ek2b_code"], sizes["test_key"], sizes["len"], strict=True)
    }
    assert size[("L107020", "hemogram")] == 15
    assert size[("L107010", "urinalysis")] == 10
    assert size[("L103900", "blood_gas_arterial")] == size[("L103900", "blood_gas_venous")] == 10


def test_the_context_reads_nothing_until_it_is_used() -> None:
    fresh_context = CleanPlausibilityContext()
    assert not any(key in vars(fresh_context) for key in ("lab_reference", "lab_variants"))
    first = fresh_context.lab_reference
    assert fresh_context.lab_reference is first
    assert {"code", "variant", "parameter", "unit", "low_m", "high_m", "qualitative"} <= set(
        first.columns
    )
    assert first.height == 96 and first["qualitative"].sum() == 6
    assert not first.select("code", "variant", "parameter").is_duplicated().any()
    assert first.filter(pl.col("unit") == "").height == 10
    assert fresh_context.lab_variants.height == 50


def test_the_context_names_the_cohort_of_the_dataset(built, clean) -> None:
    other = CleanPlausibilityContext(kohort="cohort")
    found = check_clean_plausibility(built.tables, clean, context=other, only=SETS)
    assert len(found) == 207
    assert {p.message for p in found} == {"kohort is showcase, not cohort"}
    relabelled = {
        **clean,
        TABLE_LAB: clean[TABLE_LAB].with_columns(pl.lit("cohort").alias("kohort")),
    }
    assert check_clean_plausibility(built.tables, relabelled, context=other, only=SETS) == []


def test_the_context_takes_a_reference_by_hand(built, clean) -> None:
    empty = CleanPlausibilityContext(lab_reference=CleanPlausibilityContext().lab_reference.head(0))
    for check in (UNIT, FLAG_AND_LIMITS):
        found = check_clean_plausibility(built.tables, clean, context=empty, only=check)
        assert found == [], f"{check}: no reference row, nothing to compare with"
    # but no set can be read against an empty reference: each of the 48 billed lines has one
    found = check_clean_plausibility(built.tables, clean, context=empty, only=SETS)
    assert len(found) == 48
    assert all("no parameter of the set belongs to the reference of" in p.message for p in found)


def test_the_fold_makes_turkish_capitals_comparable() -> None:
    assert fold_text("İNFÜZYON") == "infuzyon" == fold_text("infuzyon")
    assert fold_text("ENJEKTÖR") == "enjektor"
    assert fold_text("ŞİŞE") == "sise" and fold_text("ışık") == "isik"
    assert fold_text("I.V.") == "i.v."
    assert fold_text("Ağızdan") == "agizdan"


# --- 7. hygiene and independence of the module ------------------------------------------------------


_FORBIDDEN_ATTRIBUTES = {
    "iter_rows", "rows", "row", "to_dicts", "to_dict", "iterrows", "itertuples", "map_elements",
    "map_rows", "apply", "iter_columns", "iter_slices", "to_list", "to_numpy", "to_pandas",
}  # fmt: skip


def _module_tree() -> ast.Module:
    return ast.parse(_MODULE.read_text(encoding="utf-8"), filename=str(_MODULE))


def _imported_names(tree: ast.Module) -> list[tuple[str, int]]:
    """Every name the module imports, fully qualified, with the import level (0 = absolute)."""
    names: list[tuple[str, int]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names += [(alias.name, 0) for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            base = node.module or ""
            names.append((base, node.level))
            names += [(f"{base}.{alias.name}".strip("."), node.level) for alias in node.names]
    return names


def test_the_module_has_no_row_wise_dataframe_calls() -> None:
    attributes = {node.attr for node in ast.walk(_module_tree()) if isinstance(node, ast.Attribute)}
    assert attributes & _FORBIDDEN_ATTRIBUTES == set()


def test_the_module_is_independent_of_the_generator_and_the_claims_checks() -> None:
    """It reads the reference CSV itself and imports nothing of the cohort package."""
    imported = _imported_names(_module_tree())
    assert any(name == "polars" for name, _ in imported)
    for name, level in imported:
        assert level == 0, f"relative import of {name!r}"
        assert not name.startswith("scripts.synthetic.cohort"), name
        for generator in ("labs", "clean", "clinical", "plausibility"):
            assert f"cohort.{generator}" not in name, name
    text = _MODULE.read_text(encoding="utf-8")
    assert "importlib" not in text and "__import__" not in text
    # the only repository module it imports is the base class of the finding
    repository = {name for name, _ in imported if name.startswith(("scripts", "src", "tests"))}
    assert {n.split(" ")[0] for n in repository} <= {
        "scripts.synthetic.pathways.schema",
        "scripts.synthetic.pathways.schema.Problem",
    }, repository


def test_the_module_imports_no_pandas_and_no_engine() -> None:
    imported = [name for name, _ in _imported_names(_module_tree())]
    assert "polars" in imported
    for module in imported:
        assert not module.startswith("pandas"), module
        assert not module.startswith("numpy"), module
        assert not module.startswith("reports"), module
        assert "prose_rules" not in module, module
        assert "domain.billing" not in module, module
        assert not module.startswith("src.bilun"), module


def test_the_module_and_its_tests_name_no_anonymised_identifier() -> None:
    needle = "ANON" + "_"
    assert needle not in _MODULE.read_text(encoding="utf-8").upper()
    assert needle not in Path(__file__).read_text(encoding="utf-8").upper()


def test_the_module_writes_no_file() -> None:
    """The checks only read: no table, no report, no cache is written."""
    text = _MODULE.read_text(encoding="utf-8")
    assert "write_parquet" not in text
    assert "write_csv" not in text
    assert ".write_text(" not in text
    assert "open(" not in text


def test_the_module_has_no_python_loop_over_a_dataframe() -> None:
    """The only loops are over constants (tables of words, bounds, columns) and the finished findings."""
    loops = [node for node in ast.walk(_module_tree()) if isinstance(node, ast.For)]
    sources = [ast.unparse(node.iter) for node in loops]
    assert sources == [
        "zip('ıçğöşü', 'icgosu', strict=True)",  # the Turkish letters of the fold
        "REQUIRED_RECETE_COLUMNS",
        "VITALS_BOUNDS.items()",
    ], sources
