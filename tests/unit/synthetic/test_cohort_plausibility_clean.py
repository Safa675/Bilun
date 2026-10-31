"""Contract and mutation tests for `scripts/synthetic/cohort/plausibility_clean.py` (plan D5, slice E3).

Every id in `plausibility_clean.CHECKS` has one in-memory mutation case below (docs/testing-policy.md): a case
seeds one defect into a copy of the committed showcase tables and proves that exactly the target id trips, plus
the ids in `also` that the defect unavoidably trips too. Nothing here writes a file.

The contract:
1. the committed clean tables raise no problem with the committed claims tables;
2. the twin world (the clean twins' claims, the clean tables without the lines the fault adds) is clean for all ids;
3. every id has an implementation, a short meaning and a mutation case;
4. the committed Parquet files give the same result as the tables in memory.
"""

from __future__ import annotations

from collections.abc import Callable
import dataclasses
from datetime import datetime
from pathlib import Path
import re

import polars as pl
import pytest

from scripts.synthetic.cohort import DEFAULT_OUT_DIR
from scripts.synthetic.cohort.ids import claim_id, episode_id, patient_id
from scripts.synthetic.cohort.plausibility_clean import (
    BLOOD_GAS_CODE,
    CHECK_FUNCTIONS,
    CHECKS,
    CREATININE_CODE,
    HEMOGRAM_CODE,
    LAB_HARD_BOUNDS,
    LAB_REFERENCE_PATH,
    LAB_STRIP_PARAMETERS,
    TABLE_ANADATA,
    TABLE_DRUGS,
    TABLE_HEADERS,
    TABLE_LAB,
    TABLE_PROCEDURES,
    TABLE_RECETE,
    CleanPlausibilityContext,
    CleanPlausibilityError,
    Problem,
    check_clean_plausibility,
)
from scripts.synthetic.cohort.tables import TABLE_FILES, build_tables
from tests.fixtures import synthetic_cohort as cohort

pytestmark = pytest.mark.unit

_REPO = Path(__file__).resolve().parents[3]
_CLAIMS_DIR = DEFAULT_OUT_DIR / "sut/claims"
_CLEAN_DIR = DEFAULT_OUT_DIR / "sut/clean"
_CLEAN_FILES = (TABLE_ANADATA, TABLE_LAB, TABLE_RECETE)
# The sizes of the committed tables, from the registry; the content pins below stay literal.
LAB_ROWS = cohort.counts()["lab_clean.parquet"]
RX_ROWS = cohort.counts()["recete_clean.parquet"]

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
COMPLAINT = "ana.complaint_not_diagnosis"

STORIES = tuple(range(1, cohort.patient_count() + 1))  # patient numbers; one bill each
PATIENT = {n: patient_id(n) for n in STORIES}
EPISODE = {n: episode_id(PATIENT[n], 1) for n in STORIES}


# --- fixtures -----------------------------------------------------------------------------------


@pytest.fixture(scope="module")
def built(committed_showcase):
    return committed_showcase


@pytest.fixture(scope="module")
def context() -> CleanPlausibilityContext:
    return CleanPlausibilityContext()


@pytest.fixture(scope="module")
def twins(built) -> dict[str, pl.DataFrame]:
    """The claims tables of the nine clean twins: the showcase bills without their fault."""
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


def lab(
    story: int,
    on: str | None = None,
    code: str | None = None,
    parameter: str | None = None,
) -> pl.Expr:
    """The lab rows of a story's bill, optionally of one day, one code and one parameter."""
    expr = pl.col("basvuru_id") == EPISODE[story]
    if on is not None:
        expr = expr & (pl.col("tarih") == day(on))
    if code is not None:
        expr = expr & (pl.col("SUB_CODE") == code)
    if parameter is not None:
        expr = expr & (pl.col("parametre") == parameter)
    return expr


def rx(story: int, name: str) -> pl.Expr:
    """The prescription row of a story's bill whose billed name starts with `name`: a course drug has a
    row a day (review of 2026-10-30, A3), and this is the one of its first day."""
    drug = (pl.col("RF_EPISODE") == EPISODE[story]) & pl.col("ilac_adi").str.starts_with(name)
    return drug & (pl.col("RECETE_TARIH") == pl.col("RECETE_TARIH").filter(drug).min())


_EPISODE_COLUMN = {TABLE_ANADATA: "SQ_EPISODE", TABLE_LAB: "basvuru_id", TABLE_RECETE: "RF_EPISODE"}


def bill_row(story: int, table: str) -> pl.Expr:
    """The rows of the story's (first) bill in a clean table: a patient may have other bills, with rows of their own."""
    return pl.col(_EPISODE_COLUMN[table]) == EPISODE[story]


def lab_where(story: int, on: str, code: str, parameter: str | None = None) -> str:
    """`Problem.where` of a finding about a result set, or (with `parameter`) about one row of it."""
    text = f"{PATIENT[story]} lab_clean[{EPISODE[story]}|{on}|{code}"
    return f"{text}|{parameter}]" if parameter else f"{text}]"


def rx_where(story: int, on: str) -> str:
    """The start of `Problem.where` of a finding about the prescription rows of a day."""
    return f"{PATIENT[story]} recete_clean[{EPISODE[story]}|{on}|"


def only_ids(found: list[Problem]) -> set[str]:
    return {problem.check for problem in found}


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
GLUCOSE_2 = lab_where(2, DAY_2, GLUCOSE_CODE, "Glukoz")
IESEF = "IESEF 1 G IV ENJEKSIYONLUK COZELTI TOZU"
VITALS_2 = f"{PATIENT[2]} anadata_clean[{EPISODE[2]}]"


def _lab_value(story, on, code, parameter, **changes) -> Callable[[Data], None]:
    """Change columns of one lab row."""
    return lambda d: edit(d, TABLE_LAB, lab(story, on, code, parameter), **changes)


def _vital(story: int, **changes) -> Callable[[Data], None]:
    return lambda d: edit(d, TABLE_ANADATA, bill_row(story, TABLE_ANADATA), **changes)


def _recete(story: int, name: str, **changes) -> Callable[[Data], None]:
    return lambda d: edit(d, TABLE_RECETE, rx(story, name), **changes)


def _blank_column(column: str) -> Callable[[Data], None]:
    return lambda d: edit(d, TABLE_RECETE, bill_row(7, TABLE_RECETE), **{column: "  "})


# S7's single prescription row (PARTEMOL, 1 flakon) carries the required-field cases; a null in a
# column that the other checks read trips them too (each `also` says which).
_REQUIRED_START = f"{PATIENT[7]} recete_clean[{EPISODE[7]}|"


CASES: list[Case] = [
    # --- lab.value_bounds. The flags of the changed rows are kept consistent with the new values.
    Case(
        VALUE_BOUNDS,
        _lab_value(2, DAY_2, GLUCOSE_CODE, "Glukoz", sonuc_sayisal=-5.0, anormal_mi=True),
        where=GLUCOSE_2,
        says=("Glukoz = -5.0", "outside the hard interval 20.0..1500.0"),
        label="negative_glucose",
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
    # --- lab.flag_and_limits
    Case(
        FLAG_AND_LIMITS,
        _lab_value(2, DAY_2, GLUCOSE_CODE, "Glukoz", anormal_mi=True),
        where=GLUCOSE_2,
        says="anormal_mi is true but the value 89.0 against the limits 70.0..100.0 makes it false",
        label="flipped_flag",
    ),
    # --- lab.unit_matches_reference
    Case(
        UNIT,
        _lab_value(2, DAY_2, GLUCOSE_CODE, "Glukoz", birim="mmol/L"),
        where=GLUCOSE_2,
        says="Glukoz has the unit mmol/L, the reference lists mg/dL",
        label="wrong_unit",
    ),
    # --- lab.result_sets_match_bill
    Case(
        SETS,
        lambda d: drop(d, TABLE_LAB, lab(2, DAY_2, HEMOGRAM_CODE, "MPV")),
        where=HEMOGRAM_2,
        says=("14 row(s)", "lists 15", "missing MPV"),
        label="dropped_row",
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
    # --- lab.egfr_relation (S2: a man of 81, creatinine 0.98, eGFR 77)
    Case(
        EGFR_RELATION,
        _lab_value(2, DAY_2, CREATININE_CODE, "Kreatinin", sonuc_sayisal=1.6, anormal_mi=True),
        where=EGFR_2,
        says="eGFR 77.0 but creatinine 1.6, age 81 and sex E give 43.0",
        label="creatinine_changed_alone",
    ),
    # --- rx.matches_billed_line. The changed rows keep their dose text consistent with miktar.
    Case(
        MATCHES,
        _recete(2, "PREDNOL-L", miktar=2, dozaj_ham="2 ampul"),
        where=PATIENT[2],
        says=("(miktar 2) has no billed drug line", "(quantity 1) has no prescription row"),
        n=2,
        label="quantity_changed",
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
    # --- rx.dose_unit
    Case(
        DOSE,
        _recete(1, "IESEF", dozaj_ham="1 bottle"),
        where=rx_where(1, "2026-07-14") + "IESEF",
        says="dozaj_ham 1 bottle: uses the English unit word bottle",
        label="english_unit_word",
    ),
    Case(
        REQUIRED,
        _blank_column("ilac_adi_ham"),
        where=_REQUIRED_START,
        says="missing required column(s): ilac_adi_ham",
        label="blank_raw_name",
    ),
    # --- ana.complaint_not_diagnosis (S2's stay: J44.0 is its primary; the review of 2026-10-30, A4)
    Case(
        COMPLAINT,
        _vital(2, YAKINMA="Nefes darlığı arttı; J44.0 tanılı hasta."),
        where=VITALS_2,
        says="YAKINMA names the ICD-10 code J44.0",
        label="icd_code_in_complaint",
    ),
    # --- ana.vitals_bounds (S2: KB-S 142, KB-D 84, SpO2 88, 170 cm, 68 kg, BMI 23.5)
    Case(
        VITALS,
        _vital(2, **{"KB-D": 148}),
        where=VITALS_2,
        says="KB-D 148 is not below KB-S 142",
        label="diastolic_above_systolic",
    ),
]


# --- 1. the registry -------------------------------------------------------------------------------


def test_every_check_id_has_a_function_a_short_meaning_and_a_mutation_case() -> None:
    assert set(CHECK_FUNCTIONS) == set(CHECKS)
    assert {case.check for case in CASES} == set(CHECKS)
    assert len(CHECKS) == 13
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


def test_the_committed_clean_tables_raise_no_problem(committed_problems, clean) -> None:
    assert [str(p) for p in committed_problems] == []
    # the tables are the ones of the brief: they are not empty, so "no problem" is not "no data"
    assert {name: clean[name].height for name in _CLEAN_FILES} == {
        TABLE_ANADATA: cohort.claim_count(),  # one anadata row per bill
        TABLE_LAB: LAB_ROWS,
        TABLE_RECETE: RX_ROWS,
    }


def test_the_package_bills_of_patients_5_and_8_have_no_lab_rows(built, clean) -> None:
    """S5, S8, patient 5's readmission S42 and patient 8's ERCP admission S50 are package bills: no billed lab line, no
    lab row. The lab rows of each patient are those of its ER visit (S41, S49), the one bill of the patient that bills
    tests (S49's CRP is the faulty line of its bill)."""
    labs = clean[TABLE_LAB]
    stays = ((5, 1), (5, 3), (8, 1), (8, 3))
    package_claims = [claim_id(PATIENT[n], k) for n, k in stays]
    headers = built.tables[TABLE_HEADERS].filter(pl.col("claim_id").is_in(package_claims))
    assert headers["package_candidate"].to_list() == [True, True, True, True]
    billed = built.tables[TABLE_PROCEDURES].filter(pl.col("procedure_category") == "laboratuvar")
    assert billed.filter(pl.col("claim_id").is_in(package_claims)).height == 0
    assert labs.filter(pl.col("basvuru_id").is_in([episode_id(PATIENT[n], k) for n, k in stays])).height == 0
    for n in (5, 8):
        assert set(labs.filter(pl.col("HASTA_ID") == PATIENT[n])["basvuru_id"]) == {episode_id(PATIENT[n], 2)}
        assert set(billed.filter(pl.col("patient_id") == PATIENT[n])["claim_id"]) == {claim_id(PATIENT[n], 2)}


def test_the_twin_world_is_clean_for_every_id(twins, clean, context) -> None:
    """Twin claims and clean tables without S1's lab and prescription rows, S10's manual haematocrit and S49's CRP, and
    with S33's enoxaparin at the twin's count: nothing depends on the fault."""
    twin_clean = {
        name: (frame.filter(pl.col(_EPISODE_COLUMN[name]) != EPISODE[1]) if name != TABLE_ANADATA else frame)
        for name, frame in clean.items()
    }
    twin_clean[TABLE_LAB] = twin_clean[TABLE_LAB].filter(
        ~((pl.col("basvuru_id") == EPISODE[12]) & (pl.col("SUB_CODE") == "L103120"))
        & ~((pl.col("basvuru_id") == episode_id(PATIENT[8], 2)) & (pl.col("SUB_CODE") == "L101850"))
    )
    s33 = (pl.col("RF_EPISODE") == "B-SENTETIK-HASTA-0002-003") & (pl.col("miktar") == 4000)
    assert twin_clean[TABLE_RECETE].filter(s33).height == 4
    twin_clean[TABLE_RECETE] = twin_clean[TABLE_RECETE].with_columns(
        pl.when(s33).then(pl.lit(1, dtype=pl.Int64)).otherwise(pl.col("miktar")).alias("miktar"),
        pl.when(s33).then(pl.lit("1 enjektör")).otherwise(pl.col("dozaj_ham")).alias("dozaj_ham"),
    )
    # S1 has 16 lab rows; S10's bill and S49's bill one set of one row each that only the faulty bill bills
    assert twin_clean[TABLE_LAB].height == LAB_ROWS - 16 - 1 - 1
    assert twin_clean[TABLE_RECETE].height == RX_ROWS - 3  # and 3 prescription rows
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


def test_the_base_of_a_defect_case_has_the_findings_of_the_module_fixture(
    built, clean, context, committed_problems
) -> None:
    """A case's base (`fresh`) finds what `committed_problems` found, so the cases read that."""
    assert fresh(built, clean).problems(context) == committed_problems


@pytest.mark.parametrize("case", CASES, ids=lambda c: c.name)
def test_a_defect_trips_its_own_check_and_what_it_must(
    case: Case, built, clean, context, committed_problems
) -> None:
    # the findings of the base, `fresh(built, clean).problems(context)`, computed once per module
    assert committed_problems == [], "the base (the committed tables) must be clean"
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


# --- 6. the judgment tables --------------------------------------------------------------------------


@pytest.fixture(scope="module")
def reference() -> pl.DataFrame:
    """The reference CSV read here, apart from the module under test."""
    limits = ["ref_low_male", "ref_high_male", "ref_low_female", "ref_high_female"]
    return pl.read_csv(
        _REPO / LAB_REFERENCE_PATH, schema_overrides=dict.fromkeys(limits, pl.Float64)
    ).with_columns(pl.col("unit").fill_null(""))


def test_the_hard_bounds_cover_every_parameter_of_the_billed_codes(reference, clean) -> None:
    """Every parameter of the 17 billed codes, not only those that occur, has an entry."""
    codes = set(clean[TABLE_LAB]["SUB_CODE"])
    assert len(codes) == 17
    listed = reference.filter(pl.col("ek2b_code").is_in(sorted(codes)))
    wanted = set(zip(listed["ek2b_code"], listed["result_parameter"], strict=True))
    assert wanted == set(LAB_HARD_BOUNDS) | set(LAB_STRIP_PARAMETERS)
    assert len(wanted) == 51 and len(LAB_HARD_BOUNDS) == 45 and len(LAB_STRIP_PARAMETERS) == 6
    assert not set(LAB_HARD_BOUNDS) & set(LAB_STRIP_PARAMETERS)
    occurring = set(zip(clean[TABLE_LAB]["SUB_CODE"], clean[TABLE_LAB]["parametre"], strict=True))
    assert len(occurring) == 50 and occurring <= wanted
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
