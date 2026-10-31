"""Tests for `scripts/synthetic/cohort/labs.py` and the `lab_clean.parquet` it makes.

The reference reader, the feed coverage per episode (with the real `detect_lab_capture_gaps`), the
value bands and the coherence rules R1 to R5 on the committed table, one drift per rule, the table structure,
the loaders and the engine, and the formulas pinned to numbers computed apart from the code.
The tests copy frames and never touch a tracked file.
"""

from __future__ import annotations

from collections.abc import Iterator
import json
from pathlib import Path
import re
from typing import Any

import polars as pl
import pytest
import yaml

from scripts.synthetic.cohort import (
    CLEAN_TABLE_FILES,
    CLINICAL_PATH,
    LAB_CLEAN_SCHEMA,
    BuildResult,
    LabCoherenceError,
    LabReferenceError,
    ShowcaseClinical,
    StoryProof,
    build_lab_clean,
    check_lab_coherence,
    clean_tables_digest,
    expected_lab_row_count,
    load_clinical,
    load_lab_reference,
)
from scripts.synthetic.cohort.build import DEFAULT_OUT_DIR
from scripts.synthetic.cohort.labs import (
    BILLED_LAB_CODES,
    _base_excess,
    _hco3,
    _sao2,
    base_excess_from_ph_hco3,
    ckd_epi_2021,
    ckd_epi_2021_expr,
    henderson_hasselbalch_hco3,
    severinghaus_sao2,
)
from src.bilun.cache.loaders import _normalize_lab
from src.bilun.domain.claims.loader import load_sut_claim_dataset
from src.bilun.domain.prose_rules.lab_capture_gap import detect_lab_capture_gaps
from tests.fixtures import synthetic_cohort as cohort

pytestmark = pytest.mark.unit

_REPO = Path(__file__).resolve().parents[3]
_OUT_DIR = DEFAULT_OUT_DIR
_CLAIMS_DIR = _OUT_DIR / "sut" / "claims"
_CLEAN_DIR = _OUT_DIR / "sut" / "clean"
_LAB_PARQUET = _CLEAN_DIR / "lab_clean.parquet"
_REGISTRY_JSON_PATH = _OUT_DIR / "cohort_registry.json"
_LAB_CSV = _REPO / "data" / "synthetic" / "reference" / "lab_reference.csv"


# The 17 lab codes billed in the cohort and the number of result parameters of each.
_PARAMETER_COUNTS: dict[str, int] = {
    "L100300": 1,  # ALT
    "L100320": 1,  # albumin (S18, at or under the 2.5 g/dl of SUT 4.2.27.Ç)
    "L101280": 1,  # AST
    "L101850": 1,  # CRP
    "L102090": 1,  # D-dimer
    "L102890": 1,  # glucose
    "L103120": 1,  # manual haematocrit (S10, beside a hemogram, as the planted fault)
    "L103900": 10,  # arterial blood gas
    "L104780": 2,  # creatinine and the derived eGFR
    "L104890": 1,  # lactate
    "L106150": 1,  # potassium
    "L106240": 1,  # procalcitonin
    "L106910": 1,  # sodium
    "L107010": 10,  # urinalysis: 2 numeric, 6 strips, 2 microscopy
    "L107020": 15,  # hemogram
    "L107360": 1,  # troponin I
    "L107420": 1,  # urea
}
LAB_ROWS = cohort.counts()["lab_clean.parquet"]  # the size of the table, from the registry
# patient 4: the stay's 52 rows and the control's (S39) 27: blood count 15, creatinine 2, urinalysis 10
# patient 12: the ER bill (S10) 16, a blood count 15 and the manual haematocrit 1, and the admission (S22) 15
# patient 15: the cirrhosis stay (S18) 16, a blood count 15 and the albumin 1, and the rebleed (S24) 30, two blood counts
# patient 5: the ER visit before her stay (S41) 17, a blood count 15 and the creatinine 2 (her two stays are packages)
_ROWS_PER_PATIENT: dict[int, int] = {1: 16, 2: 59, 3: 34, 4: 79, 5: 17, 6: 40, 7: 25, 8: 1, 9: 15, 10: 18, 12: 31, 15: 46}
_PATIENTS: dict[int, tuple[str, int]] = {
    1: ("M", 34),
    2: ("M", 81),
    3: ("F", 77),
    4: ("F", 86),
    5: ("F", 84),
    6: ("M", 79),
    7: ("F", 58),
    8: ("F", 47),
    9: ("F", 77),
    10: ("F", 76),
    12: ("M", 58),
    15: ("M", 63),
}

# Decimals of every parameter of the 17 codes: the most decimals among the limits and the state
# numbers of the CSV rows, at most 3 (eGFR bands do not count).
_DECIMALS: dict[str, int] = {
    "L100300|ALT": 0,
    "L100320|Albümin": 1,
    "L101280|AST": 0,
    "L101850|CRP (kantitatif)": 0,
    "L102090|D-dimer": 0,
    "L102890|Glukoz": 0,
    "L103120|Hematokrit (manuel)": 0,
    "L103900|pH": 2,
    "L103900|pCO2": 0,
    "L103900|pO2": 0,
    "L103900|HCO3": 0,
    "L103900|BE (baz fazlası)": 0,
    "L103900|SaO2": 0,
    "L103900|Laktat (kan gazı)": 1,
    "L103900|Sodyum (kan gazı)": 0,
    "L103900|Potasyum (kan gazı)": 1,
    "L103900|İyonize kalsiyum (kan gazı)": 2,
    "L104780|Kreatinin": 2,
    "L104890|Laktat": 1,
    "L104780|eGFR (CKD-EPI 2021, hesaplanan)": 0,
    "L106150|Potasyum": 1,
    "L106240|Prokalsitonin": 2,
    "L106910|Sodyum": 0,
    "L107010|Dansite (özgül ağırlık)": 3,
    "L107010|pH": 1,
    "L107010|Protein (strip)": 0,
    "L107010|Glukoz (strip)": 0,
    "L107010|Keton (strip)": 0,
    "L107010|Kan / hemoglobin (strip)": 0,
    "L107010|Lökosit esteraz (strip)": 0,
    "L107010|Nitrit (strip)": 0,
    "L107010|Mikroskopi: lökosit": 0,
    "L107010|Mikroskopi: eritrosit": 0,
    "L107020|WBC (Lökosit)": 1,
    "L107020|NEU# (Nötrofil)": 1,
    "L107020|LYM# (Lenfosit)": 1,
    "L107020|MONO# (Monosit)": 1,
    "L107020|EOS# (Eozinofil)": 2,
    "L107020|BASO# (Bazofil)": 1,
    "L107020|RBC (Eritrosit)": 1,
    "L107020|HGB (Hemoglobin)": 1,
    "L107020|HCT (Hematokrit)": 0,
    "L107020|MCV": 0,
    "L107020|MCH": 0,
    "L107020|MCHC": 1,
    "L107020|RDW-CV": 1,
    "L107020|PLT (Trombosit)": 0,
    "L107020|MPV": 1,
    "L107360|hs-Troponin I": 1,
    "L107420|Üre": 1,
}
# The generator prints these with a fixed number of decimals whatever the CSV says (rules R1 to R4).
_FIXED_DECIMALS: dict[str, int] = {
    "L107020|NEU# (Nötrofil)": 2,
    "L107020|LYM# (Lenfosit)": 2,
    "L107020|MONO# (Monosit)": 2,
    "L107020|EOS# (Eozinofil)": 2,
    "L107020|BASO# (Bazofil)": 2,
    "L103900|HCO3": 1,
    "L103900|BE (baz fazlası)": 1,
    "L103900|SaO2": 1,
}

_DIFFERENTIAL = (
    "NEU# (Nötrofil)",
    "LYM# (Lenfosit)",
    "MONO# (Monosit)",
    "EOS# (Eozinofil)",
    "BASO# (Bazofil)",
)
_EGFR = "eGFR (CKD-EPI 2021, hesaplanan)"
_LIMIT_COLUMNS = ("ref_low_male", "ref_high_male", "ref_low_female", "ref_high_female")


@pytest.fixture(autouse=True)
def _fresh_claims_cache() -> Iterator[None]:
    """`load_sut_claim_dataset` caches by arguments: every test starts and ends with an empty cache."""
    load_sut_claim_dataset.cache_clear()
    yield
    load_sut_claim_dataset.cache_clear()


@pytest.fixture(scope="module")
def built_showcase(committed_showcase: BuildResult) -> BuildResult:
    return committed_showcase


@pytest.fixture(scope="module")
def lab(built_showcase: BuildResult) -> pl.DataFrame:
    return built_showcase.clean_tables["lab_clean.parquet"]


@pytest.fixture(scope="module")
def ana(built_showcase: BuildResult) -> pl.DataFrame:
    return built_showcase.clean_tables["anadata_clean.parquet"]


@pytest.fixture(scope="module")
def procs(built_showcase: BuildResult) -> pl.DataFrame:
    return built_showcase.tables["procedure_claim_lines.parquet"]


@pytest.fixture(scope="module")
def csv_rows() -> pl.DataFrame:
    """The arterial rows of the 14 billed codes, straight from the CSV (independent of `labs.py`)."""
    raw = pl.read_csv(_LAB_CSV, infer_schema_length=0)
    return raw.filter(
        pl.col("ek2b_code").is_in(list(_PARAMETER_COUNTS))
        & (pl.col("test_key") != "blood_gas_venous")
    ).with_columns(
        (pl.col("ek2b_code") + "|" + pl.col("result_parameter")).alias("key"),
        pl.int_range(pl.len()).over("ek2b_code").alias("position"),
        *(pl.col(c).replace("", None).cast(pl.Float64).alias(c) for c in _LIMIT_COLUMNS),
    )


@pytest.fixture(scope="module")
def clinical_raw() -> dict[str, Any]:
    return yaml.safe_load(CLINICAL_PATH.read_text(encoding="utf-8"))


def _pid(patient_no: int) -> str:
    return f"SENTETIK-HASTA-{patient_no:04d}"


def _day() -> pl.Expr:
    return pl.col("tarih").dt.strftime("%Y-%m-%d")


def _set_cell(df: pl.DataFrame, index: int, column: str, value: Any) -> pl.DataFrame:
    """Copy of `df` with one cell replaced."""
    return df.with_columns(
        pl.when(pl.int_range(pl.len()) == index)
        .then(pl.lit(value, dtype=df.schema[column]))
        .otherwise(pl.col(column))
        .alias(column)
    )


# --- 3.1 Reference reader ------------------------------------------------------------------------


def test_reference_has_the_billed_codes_with_their_parameter_counts(procs: pl.DataFrame) -> None:
    ref = load_lab_reference()
    billed = set(procs.filter(pl.col("procedure_category") == "laboratuvar")["procedure_code"])
    assert billed == set(_PARAMETER_COUNTS) == set(BILLED_LAB_CODES)
    assert {code: len(ref.by_code[code]) for code in billed} == _PARAMETER_COUNTS
    assert len(ref.by_code) == 50  # every code of the CSV, not only the billed ones
    assert sum(_PARAMETER_COUNTS.values()) == 50
    # The venous variant shares the code L103900 and is not read as a second set of parameters.
    assert len(ref.billed_code_parameters) == sum(_PARAMETER_COUNTS.values()) + 10  # + the venous gas
    assert {s.test_key for s in ref.by_code["L103900"]} == {"blood_gas_arterial"}
    assert all(s.test_key != "blood_gas_venous" for s in ref.by_key.values())


def test_every_abnormal_state_item_parses_or_is_listed_as_unsupported() -> None:
    """No item of `abnormal_states` of a billed code is dropped silently (venous rows included)."""
    ref = load_lab_reference()
    raw = pl.read_csv(_LAB_CSV, infer_schema_length=0).filter(
        pl.col("ek2b_code").is_in(list(_PARAMETER_COUNTS))
    )
    assert raw.height == len(ref.billed_code_parameters) == sum(_PARAMETER_COUNTS.values()) + 10
    texts = raw["abnormal_states"].fill_null("").to_list()
    total_items = 0
    for spec, text in zip(ref.billed_code_parameters, texts, strict=True):
        items = [item for item in text.split("; ") if item.strip()]
        accounted = [s.raw_text for s in spec.parsed_states] + [
            u.raw_text for u in spec.unsupported_states
        ]
        assert sorted(accounted) == sorted(items), spec.key
        total_items += len(items)
    assert total_items == 187  # the albumin row's five states count since S18 bills albumin


def test_expected_lab_row_count_adds_the_parameters_of_each_billed_line() -> None:
    assert expected_lab_row_count([]) == 0
    assert expected_lab_row_count(["L107020", "L107020", "L100300"]) == 31
    assert expected_lab_row_count(["L107360", "L107360"]) == 2
    with pytest.raises(LabReferenceError, match="Unknown billed lab procedure_code 'L999999'"):
        expected_lab_row_count(["L999999"])


# --- 3.2 Feed coverage per episode ---------------------------------------------------------------


@pytest.fixture
def claims_dataset() -> Any:
    """The showcase claims as the application's claims loader returns them."""
    return load_sut_claim_dataset(_CLAIMS_DIR, mode="synthetic_demo")


def _billed_lab_lines(procs: pl.DataFrame) -> pl.DataFrame:
    return procs.filter(pl.col("procedure_category") == "laboratuvar").sort(
        ["patient_id", "procedure_date", "procedure_line_id"]
    )


def _expected_lab_keys(procs: pl.DataFrame, csv_rows: pl.DataFrame) -> pl.DataFrame:
    """The (patient, episode, day, code, parameter) rows the table must hold: lines times CSV parameters."""
    parameters = csv_rows.select(
        pl.col("ek2b_code").alias("procedure_code"),
        pl.col("result_parameter").alias("parametre"),
        "position",
    )
    return (
        _billed_lab_lines(procs)
        .join(parameters, on="procedure_code", how="inner")
        .sort(["patient_id", "procedure_date", "procedure_line_id", "position"])
        .select(
            pl.col("patient_id").alias("HASTA_ID"),
            pl.col("episode_id").alias("basvuru_id"),
            pl.col("procedure_date").alias("day"),
            pl.col("procedure_code").alias("SUB_CODE"),
            "parametre",
        )
    )


def _actual_lab_keys(lab: pl.DataFrame) -> pl.DataFrame:
    return lab.select("HASTA_ID", "basvuru_id", _day().alias("day"), "SUB_CODE", "parametre")


def _codes_by_episode(df: pl.DataFrame, episode: str, code: str) -> dict[str, list[str]]:
    grouped = df.group_by(episode).agg(pl.col(code).unique().sort())
    return dict(zip(grouped[episode].to_list(), grouped[code].to_list(), strict=True))


def test_the_lab_codes_of_each_episode_are_the_billed_lab_codes(
    lab: pl.DataFrame, procs: pl.DataFrame, built_showcase: BuildResult
) -> None:
    episodes = built_showcase.tables["claim_headers.parquet"]["episode_id"].to_list()
    assert len(episodes) == cohort.claim_count()
    billed = _codes_by_episode(_billed_lab_lines(procs), "episode_id", "procedure_code")
    fed = _codes_by_episode(lab, "basvuru_id", "SUB_CODE")
    for episode in episodes:
        assert fed.get(episode, []) == billed.get(episode, []), episode
    # Patient 8's two stays are package bills: no billed lab line, so no lab row either; its one lab row is the CRP of
    # its ER visit (S49), the faulty line billed beside the flat-fee green-area examination. Patient 5's two stays are
    # packages too; its lab rows are those of its ER visit (S41), the one bill of the patient that bills a lab line.
    eighth = lab.filter(pl.col("HASTA_ID") == _pid(8))
    assert (set(eighth["basvuru_id"]), set(eighth["SUB_CODE"])) == ({"B-SENTETIK-HASTA-0008-002"}, {"L101850"})
    assert set(procs.filter((pl.col("procedure_category") == "laboratuvar") & (pl.col("patient_id") == _pid(8)))[
        "claim_id"
    ]) == {"F-SENTETIK-HASTA-0008-002"}
    fifth = lab.filter(pl.col("HASTA_ID") == _pid(5))
    assert set(fifth["basvuru_id"]) == {"B-SENTETIK-HASTA-0005-002"}
    assert set(procs.filter((pl.col("procedure_category") == "laboratuvar") & (pl.col("patient_id") == _pid(5)))[
        "claim_id"
    ]) == {"F-SENTETIK-HASTA-0005-002"}
    assert set(lab["HASTA_ID"]) == {_pid(n) for n in _ROWS_PER_PATIENT}


def test_each_billed_lab_line_has_exactly_one_result_set(
    lab: pl.DataFrame, procs: pl.DataFrame, csv_rows: pl.DataFrame
) -> None:
    first = csv_rows.filter(pl.col("position") == 0).select(
        pl.col("ek2b_code").alias("SUB_CODE"), pl.col("result_parameter").alias("first_parameter")
    )
    sets = (
        lab.join(first, on="SUB_CODE", how="left")
        .filter(pl.col("parametre") == pl.col("first_parameter"))
        .group_by("basvuru_id", _day().alias("day"), "SUB_CODE")
        .len()
        .rename({"len": "result_sets"})
    )
    lines = (
        _billed_lab_lines(procs)
        .group_by(
            pl.col("episode_id").alias("basvuru_id"),
            pl.col("procedure_date").alias("day"),
            pl.col("procedure_code").alias("SUB_CODE"),
        )
        .len()
        .rename({"len": "billed_lines"})
    )
    both = sets.join(lines, on=["basvuru_id", "day", "SUB_CODE"], how="full", coalesce=True)
    mismatched = both.filter(
        pl.col("result_sets").is_null()
        | pl.col("billed_lines").is_null()
        | (pl.col("result_sets") != pl.col("billed_lines"))
    )
    assert mismatched.is_empty(), mismatched
    # Serial troponin I: two billed lines on one day (S7's ER bill), two result sets; the observation S47 bills one.
    troponin = both.filter(pl.col("SUB_CODE") == "L107360").sort("basvuru_id")
    assert troponin.select("billed_lines", "result_sets").rows() == [(2, 2), (1, 1)]


def test_the_table_is_the_billed_lines_times_their_csv_parameters(
    lab: pl.DataFrame, procs: pl.DataFrame, csv_rows: pl.DataFrame
) -> None:
    expected = _expected_lab_keys(procs, csv_rows)
    assert _actual_lab_keys(lab).equals(expected)
    assert lab.height == expected.height == LAB_ROWS
    # The same total from the application of the reference to the billed codes.
    assert expected_lab_row_count(_billed_lab_lines(procs)["procedure_code"].to_list()) == LAB_ROWS
    per_patient = lab.group_by("HASTA_ID").len().sort("HASTA_ID")
    assert dict(zip(per_patient["HASTA_ID"], per_patient["len"], strict=True)) == {
        _pid(n): rows for n, rows in _ROWS_PER_PATIENT.items()
    }


def _gaps(
    feed: pl.DataFrame, claims_dataset: Any, claim_id: str, drop_line: str | None = None
) -> list[dict[str, Any]]:
    """The real `detect_lab_capture_gaps` for one claim, as `claim_procedure_capture_gap` calls it."""
    claim = claims_dataset.claims[claim_id]
    lines = [
        line
        for line in claims_dataset.procedure_lines_by_claim.get(claim_id, ())
        if line.procedure_line_id != drop_line
    ]
    return detect_lab_capture_gaps(
        feed.filter(pl.col("visit_id") == claim.episode_id),
        lines,
        claim.episode_id,
        service_date=claim.claim_start_date or claim.admission_date,
    )


def test_the_real_capture_gap_detector_finds_no_gap_for_any_episode(
    lab: pl.DataFrame, claims_dataset: Any
) -> None:
    feed = _normalize_lab(lab)
    assert feed.columns == [
        "patient_id",
        "visit_id",
        "date",
        "test_name",
        "value",
        "ref_min",
        "ref_max",
    ]
    assert len(claims_dataset.claims) == cohort.claim_count()
    for claim_id in claims_dataset.claims:
        assert _gaps(feed, claims_dataset, claim_id) == [], claim_id


def test_mutation_removing_one_billed_lab_line_gives_exactly_one_gap_with_its_code(
    lab: pl.DataFrame, procs: pl.DataFrame, claims_dataset: Any
) -> None:
    feed = _normalize_lab(lab)
    checked = 0
    for claim_id in claims_dataset.claims:
        lab_lines = [
            line
            for line in claims_dataset.procedure_lines_by_claim.get(claim_id, ())
            if line.procedure_category == "laboratuvar"
        ]
        for line in lab_lines:
            if sum(other.procedure_code == line.procedure_code for other in lab_lines) != 1:
                continue  # another line of that code still covers the result rows
            gaps = _gaps(feed, claims_dataset, claim_id, drop_line=line.procedure_line_id)
            assert [g["procedure_code"] for g in gaps] == [line.procedure_code], (
                line.procedure_line_id
            )
            assert gaps[0]["type"] == "lab_performed_not_submitted"
            assert gaps[0]["source"] == "lab"
            checked += 1
    # Every (episode, code) pair billed exactly once was tried: 2 + 6 + 2 + 10 + 7 + 6 + 1 + 4 + 3 + 2 + 2 + 2 + 2 + 1
    # pairs (patient 4: 7 on the stay and 3 on the control; patient 12: 2 on the ER bill, 1 on the admission; patient 7:
    # the troponin and the D-dimer of the observation S47; patient 15: the blood count and the albumin of S18, the rebleed
    # bills two counts; patient 5: the blood count and the creatinine of its ER visit S41; patient 3: the blood count and
    # the creatinine of its pre-operative visit S36; patient 8: the CRP of its ER visit S49).
    once = _billed_lab_lines(procs).group_by("episode_id", "procedure_code").len()
    assert checked == once.filter(pl.col("len") == 1).height == 50


# --- 3.3 Values ----------------------------------------------------------------------------------

# Parameters whose value follows from others (rules R1 to R4): their band is checked by the rule.
_DERIVED = {
    *_DIFFERENTIAL,
    "RBC (Eritrosit)",
    "HCT (Hematokrit)",
    "MCHC",
    "HCO3",
    "BE (baz fazlası)",
    "SaO2",
    _EGFR,
}
_NUMBER = r"([-+]?\d+(?:\.\d+)?)"


def _items(abnormal_states: str) -> dict[str, str]:
    """`abnormal_states` of the CSV as {state name or full name: range text}."""
    out: dict[str, str] = {}
    for item in abnormal_states.split("; "):
        name, _, rhs = item.partition(": ")
        out[name] = rhs
        out[name.split(" (")[0]] = rhs
    return out


def _numeric_band(abnormal_states: str, state: str) -> tuple[float, float]:
    rhs = _items(abnormal_states)[state]
    match = re.search(rf"(?:eGFR )?{_NUMBER}\s*(?:–|to)\s*{_NUMBER}", rhs)
    assert match is not None, (state, rhs)
    return float(match.group(1)), float(match.group(2))


def _state_schedule(clinical_raw: dict[str, Any]) -> pl.DataFrame:
    """The YAML states as one row per (patient, bill, key): the entry list (a scalar is a list of one).

    A bill has the lab states of its own entry (`encounter_no`, 1 when the entry has none).
    """
    rows = [
        {
            "HASTA_ID": _pid(patient["patient_no"]),
            "encounter": patient.get("encounter_no", 1),
            "key": key,
            "entries": [entry] if isinstance(entry, str) else list(entry),
        }
        for patient in clinical_raw["patients"]
        for key, entry in ((patient.get("labs") or {}).get("states") or {}).items()
    ]
    return pl.DataFrame(
        rows,
        schema={
            "HASTA_ID": pl.String,
            "encounter": pl.Int64,
            "key": pl.String,
            "entries": pl.List(pl.String),
        },
    )


@pytest.fixture(scope="module")
def annotated(
    lab: pl.DataFrame, csv_rows: pl.DataFrame, clinical_raw: dict[str, Any]
) -> pl.DataFrame:
    """Every lab row with its occurrence k, the state the YAML asks for and its sex-specific limits.

    `k` counts the occurrences of a parameter over the patient's bills; `kb` counts them inside the bill, which is
    how the entry list of the bill's own YAML entry is read (the control of patient 4 has its own entry).
    """
    first = csv_rows.filter(pl.col("position") == 0).select(
        pl.col("ek2b_code").alias("SUB_CODE"), pl.col("result_parameter").alias("first_parameter")
    )
    people = pl.DataFrame(
        {
            "HASTA_ID": [_pid(n) for n in _PATIENTS],
            "sex": [sex for sex, _ in _PATIENTS.values()],
            "age": [age for _, age in _PATIENTS.values()],
        }
    )
    limits = csv_rows.select(
        "key",
        *_LIMIT_COLUMNS,
        "abnormal_states",
        "normal_value_range",
        pl.col("unit").fill_null("").alias("csv_unit"),
    )
    entry_index = (
        pl.min_horizontal(pl.col("kb").cast(pl.Int64), pl.col("entries").list.len().cast(pl.Int64))
        - 1
    )
    return (
        lab.with_row_index("row")
        .join(first, on="SUB_CODE", how="left")
        .with_columns(pl.col("basvuru_id").str.extract(r"-(\d{3})$", 1).cast(pl.Int64).alias("encounter"))
        .with_columns(
            (pl.col("parametre") == pl.col("first_parameter"))
            .cast(pl.Int64)
            .cum_sum()
            .over(["HASTA_ID", "SUB_CODE"])
            .alias("k"),
            (pl.col("parametre") == pl.col("first_parameter"))
            .cast(pl.Int64)
            .cum_sum()
            .over(["HASTA_ID", "SUB_CODE", "encounter"])
            .alias("kb"),
            (pl.col("SUB_CODE") + "|" + pl.col("parametre")).alias("key"),
            _day().alias("day"),
        )
        .join(_state_schedule(clinical_raw), on=["HASTA_ID", "encounter", "key"], how="left")
        .with_columns(
            pl.when(pl.col("entries").is_null())
            .then(pl.lit("normal"))
            .otherwise(pl.col("entries").list.get(entry_index))
            .alias("state")
        )
        .join(people, on="HASTA_ID", how="left")
        .join(limits, on="key", how="left")
        .with_columns(
            pl.when(pl.col("sex") == "M")
            .then(pl.col("ref_low_male"))
            .otherwise(pl.col("ref_low_female"))
            .alias("raw_lo"),
            pl.when(pl.col("sex") == "M")
            .then(pl.col("ref_high_male"))
            .otherwise(pl.col("ref_high_female"))
            .alias("hi"),
        )
        .with_columns(pl.col("raw_lo").fill_null(0.0).alias("lo"))
        .sort("row")
    )


def test_the_requested_states_are_the_ones_of_the_yaml(annotated: pl.DataFrame) -> None:
    """The test's own reading of the YAML: which rows ask for a state, and which state."""
    asked = annotated.filter(pl.col("state") != "normal")
    pairs = (
        asked.group_by("HASTA_ID", "key", "k")
        .agg(pl.col("state").first())
        .sort("HASTA_ID", "key", "k")
    )
    got = dict(
        zip(
            zip(pairs["HASTA_ID"], pairs["key"], pairs["k"], strict=True),
            pairs["state"],
            strict=True,
        )
    )
    assert got[(_pid(2), "L107020|WBC (Lökosit)", 1)] == "bacterial_infection"
    assert got[(_pid(2), "L107020|WBC (Lökosit)", 2)] == "steroid_use"
    assert (
        got[(_pid(4), "L104780|Kreatinin", 1)]
        == got[(_pid(4), "L104780|Kreatinin", 2)]
        == got[(_pid(4), "L104780|Kreatinin", 3)]  # the control (S39) has the same state in its own entry
        == "ckd_g3a"
    )
    assert (_pid(2), "L103900|pH", 2) not in got  # the second entry is `normal`
    assert got[(_pid(2), "L103900|pO2", 2)] == "chronic_copd_room_air"
    assert {h for h, _, _ in got} == {_pid(n) for n in (1, 2, 3, 4, 6, 7, 9, 10, 12, 15)}


def test_drawn_values_without_a_state_lie_inside_the_sex_specific_limits(
    annotated: pl.DataFrame,
) -> None:
    rows = annotated.filter(
        (pl.col("state") == "normal")
        & ~pl.col("parametre").is_in(list(_DERIVED))
        & pl.col("sonuc_sayisal").is_not_null()
    )
    outside = rows.filter(
        (pl.col("sonuc_sayisal") < pl.col("lo")) | (pl.col("sonuc_sayisal") > pl.col("hi"))
    )
    assert outside.is_empty(), outside.select("HASTA_ID", "key", "sonuc_sayisal", "lo", "hi")
    # 288 numeric rows = 128 derived + 33 drawn from a state + 127 drawn without one (S47 adds a troponin without a
    # state and a D-dimer with one); patient 15's three blood counts add 12 without a state (WBC, RDW-CV, PLT, MPV),
    # patient 5's ER visit (S41) 8: its blood count's 7 (WBC, HGB, MCV, MCH, RDW-CV, PLT, MPV) and its creatinine,
    # patient 3's pre-operative visit (S36) 8 more the same way, and patient 8's ER visit (S49) 1, its CRP.
    assert rows.height == 156


def test_drawn_values_with_a_state_lie_inside_the_state_range(annotated: pl.DataFrame) -> None:
    rows = annotated.filter(
        (pl.col("state") != "normal")
        & ~pl.col("parametre").is_in(list(_DERIVED))
        & pl.col("sonuc_sayisal").is_not_null()
        & (pl.col("parametre") != "Kreatinin")  # the creatinine state is an eGFR band, see below
    )
    pairs = rows.select("key", "state", "abnormal_states").unique()
    bands = pl.DataFrame(
        [
            {"key": key, "state": state, "band_lo": lo, "band_hi": hi}
            for key, state, abnormal in zip(
                pairs["key"], pairs["state"], pairs["abnormal_states"], strict=True
            )
            for lo, hi in [_numeric_band(abnormal, state)]
        ],
        schema={"key": pl.String, "state": pl.String, "band_lo": pl.Float64, "band_hi": pl.Float64},
    )
    banded = rows.join(bands, on=["key", "state"], how="left")
    assert banded["band_lo"].null_count() == 0
    outside = banded.filter(
        (pl.col("sonuc_sayisal") < pl.col("band_lo"))
        | (pl.col("sonuc_sayisal") > pl.col("band_hi"))
    )
    assert outside.is_empty(), outside.select(
        "HASTA_ID", "key", "state", "sonuc_sayisal", "band_lo", "band_hi"
    )
    assert rows.height == 43  # numeric rows drawn from a state band (patient 15: HGB, MCV, MCH of three counts and the albumin)
    # The bands are the ones the brief names for the two stories with a list of states.
    assert bands.filter(
        (pl.col("key") == "L107020|WBC (Lökosit)") & (pl.col("state") == "bacterial_infection")
    ).select("band_lo", "band_hi").rows() == [(11.0, 20.0)]
    assert bands.filter(
        (pl.col("key") == "L107020|WBC (Lökosit)") & (pl.col("state") == "steroid_use")
    ).select("band_lo", "band_hi").rows() == [(10.5, 15.0)]


def _egfr_age_bands(csv_rows: pl.DataFrame) -> list[tuple[int, int, float, float]]:
    text = csv_rows.filter(pl.col("key") == f"L104780|{_EGFR}")["normal_value_range"][0]
    low_bands = [
        (int(a), int(b), float(c), float(d))
        for a, b, c, d in re.findall(r"(\d+)–(\d+): (\d+)–(\d+)", text)
    ]
    over = re.search(r"≥(\d+): (\d+)–(\d+)", text)
    assert over is not None and len(low_bands) == 3, text
    return [*low_bands, (int(over.group(1)), 200, float(over.group(2)), float(over.group(3)))]


def test_creatinine_and_egfr_follow_the_age_band_or_the_state_band(
    annotated: pl.DataFrame, csv_rows: pl.DataFrame
) -> None:
    creatinine = annotated.filter(pl.col("SUB_CODE") == "L104780")
    scr = creatinine.filter(pl.col("parametre") == "Kreatinin").select(
        "HASTA_ID", "k", "age", "state", "lo", "hi", pl.col("sonuc_sayisal").alias("scr")
    )
    egfr = creatinine.filter(pl.col("parametre") == _EGFR).select(
        "HASTA_ID", "k", pl.col("sonuc_sayisal").alias("egfr")
    )
    sets = scr.join(egfr, on=["HASTA_ID", "k"], how="inner")
    assert sets.height == scr.height == egfr.height == 9  # 2 + 1 + 1 + 1 + 1 + 1 + 1 days of creatinine (+1: S41, +1: S36)
    band_lo = pl.lit(None, dtype=pl.Float64)
    band_hi = pl.lit(None, dtype=pl.Float64)
    for age_lo, age_hi, e_lo, e_hi in reversed(_egfr_age_bands(csv_rows)):
        in_band = pl.col("age").is_between(age_lo, age_hi)
        band_lo = pl.when(in_band).then(pl.lit(e_lo)).otherwise(band_lo)
        band_hi = pl.when(in_band).then(pl.lit(e_hi)).otherwise(band_hi)
    sets = sets.with_columns(band_lo.alias("band_lo"), band_hi.alias("band_hi"))

    normal = sets.filter(pl.col("state") == "normal")
    assert normal.height == 6  # the creatinines of S41 and S36 have no state
    # A normal creatinine stays inside its sex-specific limits and its eGFR inside the age band.
    assert normal.filter((pl.col("scr") < pl.col("lo")) | (pl.col("scr") > pl.col("hi"))).is_empty()
    assert normal.filter(
        (pl.col("egfr") < pl.col("band_lo")) | (pl.col("egfr") > pl.col("band_hi"))
    ).is_empty()
    # `ckd_g3a` is the eGFR band 45 to 59 of the CSV, for the three days of patient 4 (the control has its own entry).
    stage = sets.filter(pl.col("state") != "normal")
    assert stage.select("HASTA_ID", "state").unique().rows() == [(_pid(4), "ckd_g3a")]
    assert stage.height == 3
    abnormal = csv_rows.filter(pl.col("key") == "L104780|Kreatinin")["abnormal_states"][0]
    low, high = _numeric_band(abnormal, "ckd_g3a")
    assert (low, high) == (45.0, 59.0)
    assert stage.filter((pl.col("egfr") < low) | (pl.col("egfr") > high)).is_empty()


def test_no_numeric_value_is_nan_or_infinite(lab: pl.DataFrame) -> None:
    numeric = lab.filter(pl.col("sonuc_nitel").is_null())
    assert numeric.height == LAB_ROWS - 12  # the twelve urine strips (two urinalyses) have a grade, not a number
    assert numeric["sonuc_sayisal"].null_count() == 0
    assert numeric["sonuc_sayisal"].is_finite().all()
    assert (
        lab["ref_alt"].drop_nulls().is_finite().all()
        and lab["ref_ust"].drop_nulls().is_finite().all()
    )


# --- 3.4 Coherence rules R1 to R4 -----------------------------------------------------------------


def _wide(lab: pl.DataFrame, csv_rows: pl.DataFrame, code: str) -> pl.DataFrame:
    """One row per result set of `code`, one column per parameter, in table order."""
    first = csv_rows.filter((pl.col("ek2b_code") == code) & (pl.col("position") == 0))[
        "result_parameter"
    ][0]
    return (
        lab.filter(pl.col("SUB_CODE") == code)
        .with_columns((pl.col("parametre") == first).cast(pl.Int64).cum_sum().alias("set"))
        .pivot(
            on="parametre",
            index=["set", "HASTA_ID", "basvuru_id"],
            values="sonuc_sayisal",
            aggregate_function="first",
        )
        .sort("set")
    )


def _ckd_epi_2021(scr: pl.Expr, age: pl.Expr, female: pl.Expr) -> pl.Expr:
    """CKD-EPI 2021 (race-free) as a Polars expression, from the formula in the creatinine CSV row."""
    kappa = pl.when(female).then(0.7).otherwise(0.9)
    alpha = pl.when(female).then(-0.241).otherwise(-0.302)
    ratio = scr / kappa
    return (
        142.0
        * pl.min_horizontal(ratio, pl.lit(1.0)).pow(alpha)
        * pl.max_horizontal(ratio, pl.lit(1.0)).pow(-1.2)
        * pl.lit(0.9938).pow(age)
        * pl.when(female).then(1.012).otherwise(1.0)
    )


def test_r1_the_five_differential_counts_sum_to_the_wbc(
    lab: pl.DataFrame, csv_rows: pl.DataFrame
) -> None:
    hemograms = _wide(lab, csv_rows, "L107020")
    assert hemograms.height == 19
    gap = (pl.sum_horizontal(*_DIFFERENTIAL) - pl.col("WBC (Lökosit)")).abs()
    assert hemograms.select(gap.max().alias("gap"))["gap"][0] <= 0.05


def test_r2_rbc_hct_and_mchc_follow_hgb_mcv_and_mch_to_the_rounding_of_their_decimals(
    lab: pl.DataFrame, csv_rows: pl.DataFrame
) -> None:
    hemograms = _wide(lab, csv_rows, "L107020")
    residuals = hemograms.select(
        (pl.col("RBC (Eritrosit)") - pl.col("HGB (Hemoglobin)") * 10 / pl.col("MCH"))
        .abs()
        .max()
        .alias("rbc"),
        (pl.col("HCT (Hematokrit)") - pl.col("MCV") * pl.col("RBC (Eritrosit)") / 10)
        .abs()
        .max()
        .alias("hct"),
        (pl.col("MCHC") - pl.col("HGB (Hemoglobin)") / pl.col("HCT (Hematokrit)") * 100)
        .abs()
        .max()
        .alias("mchc"),
    )
    # Half a unit of the last printed decimal: 0.1 for RBC and MCHC, 1 for HCT.
    assert residuals["rbc"][0] <= 0.05 + 1e-9
    assert residuals["hct"][0] <= 0.5 + 1e-9
    assert residuals["mchc"][0] <= 0.05 + 1e-9


def test_r3_egfr_is_ckd_epi_2021_of_the_creatinine_age_and_sex(
    lab: pl.DataFrame, csv_rows: pl.DataFrame, ana: pl.DataFrame
) -> None:
    people = ana.select(
        pl.col("SQ_EPISODE").alias("basvuru_id"),
        pl.col("TANI_YASI").alias("age"),
        (pl.col("CINSIYET") == "K").alias("female"),
    )
    sets = _wide(lab, csv_rows, "L104780").join(people, on="basvuru_id", how="left")
    assert sets.height == 9
    expected = _ckd_epi_2021(pl.col("Kreatinin"), pl.col("age"), pl.col("female"))
    residual = sets.select((pl.col(_EGFR) - expected).abs().max().alias("r"))["r"][0]
    assert residual <= 0.5 + 1e-9  # the eGFR is printed as an integer
    # Pin: the formula reproduces the textbook value, a 58-year-old woman with Scr 0.74 -> 94.
    textbook = pl.DataFrame({"scr": [0.74], "age": [58], "female": [True]}).select(
        _ckd_epi_2021(pl.col("scr"), pl.col("age"), pl.col("female")).alias("egfr")
    )["egfr"][0]
    assert round(textbook) == 94


def test_r4_the_blood_gas_derived_values_follow_ph_pco2_and_po2(
    lab: pl.DataFrame, csv_rows: pl.DataFrame
) -> None:
    gases = _wide(lab, csv_rows, "L103900")
    assert gases.height == 2
    hco3 = 0.0307 * pl.col("pCO2") * pl.lit(10.0).pow(pl.col("pH") - 6.1)
    base_excess = 0.93 * (pl.col("HCO3") - 24.4 + 14.8 * (pl.col("pH") - 7.4))
    sao2 = 100.0 / (1.0 + 23400.0 / (pl.col("pO2").pow(3) + 150.0 * pl.col("pO2")))
    residuals = gases.select(
        (pl.col("HCO3") - hco3).abs().max().alias("hco3"),
        (pl.col("BE (baz fazlası)") - base_excess).abs().max().alias("be"),
        (pl.col("SaO2") - sao2).abs().max().alias("sao2"),
    )
    # Each is printed with one decimal: half a unit of it.
    assert residuals["hco3"][0] <= 0.05 + 1e-9
    assert residuals["be"][0] <= 0.05 + 1e-9
    assert residuals["sao2"][0] <= 0.05 + 1e-9
    # Pin the first gas by hand: pH 7.30, pCO2 58 -> HCO3 28.2, BE 2.2; pO2 56 -> SaO2 88.7.
    first = gases.row(0, named=True)
    assert (first["pH"], first["pCO2"], first["pO2"]) == (7.3, 58.0, 56.0)
    assert (first["HCO3"], first["BE (baz fazlası)"], first["SaO2"]) == (28.2, 2.2, 88.7)


def test_the_committed_table_passes_check_lab_coherence(
    lab: pl.DataFrame, ana: pl.DataFrame
) -> None:
    check_lab_coherence(lab, ana_df=ana)
    check_lab_coherence(lab)  # without anadata only the rules that need no age or sex run
    check_lab_coherence(lab.clear(), ana_df=ana)  # an empty table is coherent


def _with_value(lab: pl.DataFrame, index: int, value: float) -> pl.DataFrame:
    """Copy of `lab` with one value changed and the `anormal_mi` of that row recomputed from its own limits.

    The flag stays right, so only a derivation rule can notice the change.
    """
    low, high = lab["ref_alt"][index], lab["ref_ust"][index]
    flag = (low is not None and value < low) or (high is not None and value > high)
    return _set_cell(_set_cell(lab, index, "sonuc_sayisal", value), index, "anormal_mi", bool(flag))


def _set_rows(lab: pl.DataFrame, code: str, parameter: str) -> list[int]:
    """Row index of `parameter` in every result set of `code`, in table order."""
    rows = lab.with_row_index("i").filter(
        (pl.col("SUB_CODE") == code) & (pl.col("parametre") == parameter)
    )
    return rows["i"].to_list()


def _assert_names_the_row(
    error: pytest.ExceptionInfo[LabCoherenceError],
    lab: pl.DataFrame,
    *,
    rule: str,
    row: int,
    code: str,
    parameter: str,
) -> None:
    """The message starts with the rule, the row number, the patient of that row, the code and the parameter."""
    expected = f"lab_clean {rule} at row {row} ({lab['HASTA_ID'][row]} {code}|{parameter}): "
    assert str(error.value).startswith(expected), str(error.value)


# A derived value moved by one printed step (R1: 0.01, and also 0.04) in each direction, a driver value
# moved, and a few big moves. (code, changed parameter, change, rule, parameter the message names.) The
# rule names the derived value's own row, not the first row of its set.
_WBC, _RBC, _HCT, _MCHC, _BE = (
    "WBC (Lökosit)",
    "RBC (Eritrosit)",
    "HCT (Hematokrit)",
    "MCHC",
    "BE (baz fazlası)",
)
_NEU = "NEU# (Nötrofil)"
_DRIFT_CASES = [
    pytest.param("L107020", _NEU, 0.01, "R1", _WBC, id="R1_neutrophils_+0.01"),
    pytest.param("L107020", _RBC, 0.1, "R2", _RBC, id="R2_rbc_+1_step"),
    pytest.param("L104780", _EGFR, 1.0, "R3", _EGFR, id="R3_egfr_+1_step"),
    pytest.param("L103900", "HCO3", 0.1, "R4", "HCO3", id="R4_hco3_+1_step"),
]
_SETS_PER_CODE = {"L107020": 19, "L104780": 9, "L103900": 2}  # the control of patient 4 and the two bills of patient 12 add one blood count each, patient 15 three, the ER visit of patient 5 (S41) and the pre-operative visit of patient 3 (S36) a blood count and a creatinine each


@pytest.mark.parametrize(("code", "changed", "change", "rule", "reported"), _DRIFT_CASES)
def test_mutation_a_drift_of_a_derived_value_names_the_rule_and_its_row_in_every_result_set(
    lab: pl.DataFrame,
    ana: pl.DataFrame,
    code: str,
    changed: str,
    change: float,
    rule: str,
    reported: str,
) -> None:
    reference = load_lab_reference()
    shift = reference.position_of(code, reported) - reference.position_of(code, changed)
    decimals = {**_DECIMALS, **_FIXED_DECIMALS}[f"{code}|{changed}"]
    indexes = _set_rows(lab, code, changed)
    assert len(indexes) == _SETS_PER_CODE[code]
    for index in indexes:
        mutated = _with_value(lab, index, round(lab["sonuc_sayisal"][index] + change, decimals))
        with pytest.raises(LabCoherenceError) as caught:
            check_lab_coherence(mutated, ana_df=ana)
        _assert_names_the_row(
            caught, lab, rule=rule, row=index + shift, code=code, parameter=reported
        )


# --- 3.5 anormal_mi (R5) --------------------------------------------------------------------------


def test_r5_anormal_mi_is_below_ref_alt_or_above_ref_ust_or_a_strip_other_than_negatif(
    lab: pl.DataFrame,
) -> None:
    numeric = lab.filter(pl.col("sonuc_nitel").is_null())
    below = pl.col("sonuc_sayisal") < pl.col("ref_alt")
    above = pl.col("sonuc_sayisal") > pl.col("ref_ust")
    expected = below.fill_null(False) | above.fill_null(False)
    assert numeric.filter(pl.col("anormal_mi").ne_missing(expected)).is_empty()
    strips = lab.filter(pl.col("sonuc_nitel").is_not_null())
    not_negative = pl.col("sonuc_nitel") != "Negatif"
    assert strips.filter(pl.col("anormal_mi").ne_missing(not_negative)).is_empty()
    # Both outcomes occur, so the test is not vacuous: 61 numeric rows and 3 strips are abnormal.
    abnormal_numeric = numeric.select(expected.sum()).item()
    abnormal_strips = strips.filter(not_negative).height
    # the control's creatinine and eGFR (CKD G3a) add two; patient 12's bleed adds ten; S47's D-dimer (above 500) one;
    # patient 15 seventeen (the albumin, and RBC, HGB, HCT, MCV, MCH of three counts with the first count's MCHC)
    assert (abnormal_numeric, abnormal_strips) == (79, 3)
    assert lab["anormal_mi"].sum() == 82
    assert 0 < lab["anormal_mi"].sum() < lab.height == LAB_ROWS


# --- 3.6 Structure --------------------------------------------------------------------------------


def test_the_table_has_exactly_the_lab_clean_schema(lab: pl.DataFrame) -> None:
    assert pl.Schema(lab.schema) == LAB_CLEAN_SCHEMA
    assert lab.columns == list(LAB_CLEAN_SCHEMA.names())
    assert lab.columns[2:4] == ["SUB_CODE", "parametre"]
    assert all(dtype != pl.Null for dtype in lab.schema.values())
    assert pl.Schema(pl.read_parquet(_LAB_PARQUET).schema) == LAB_CLEAN_SCHEMA


# (mutation, rule, row it is reported at, code and parameter written in that row, end of the message).
# The row is the lowest one that breaks the rule, and the message names what the row holds.


# --- 3.7 Generator errors from the clinical YAML ---------------------------------------------------


def _build(built_showcase: BuildResult, clinical: ShowcaseClinical) -> pl.DataFrame:
    return build_lab_clean(built_showcase.claims, clinical=clinical, schema=LAB_CLEAN_SCHEMA)


def test_the_committed_clinical_yaml_builds_the_committed_table(
    built_showcase: BuildResult, lab: pl.DataFrame
) -> None:
    assert _build(built_showcase, load_clinical()).equals(lab)


# --- 3.8 Determinism and --check -------------------------------------------------------------------


def test_the_committed_lab_parquet_equals_a_fresh_build(lab: pl.DataFrame) -> None:
    committed = pl.read_parquet(_LAB_PARQUET)
    assert dict(committed.schema) == dict(lab.schema)
    assert committed.equals(lab, null_equal=True)
    registry = json.loads(_REGISTRY_JSON_PATH.read_text(encoding="utf-8"))
    assert registry["clean_counts"]["lab_clean.parquet"] == lab.height == LAB_ROWS
    assert (
        registry["clean_tables_digest"]["lab_clean.parquet"]
        == clean_tables_digest(
            {name: pl.read_parquet(_CLEAN_DIR / name) for name in CLEAN_TABLE_FILES}
        )["lab_clean.parquet"]
    )


# --- 3.9 Loaders and engine ------------------------------------------------------------------------


def test_the_full_build_context_runs_and_no_report_has_a_lab_capture_gap(demo_build_context: dict[str, Any]) -> None:
    """`load_sut_build_context(billing_workers=1, sut_data_mode="synthetic_demo")` over the committed claims and clean
    tables (`demo_build_context` of `tests/conftest.py`, built once per session)."""
    context = demo_build_context
    assert context["lab_df_pl"].height == cohort.counts()["lab_clean.parquet"]
    reports = context["billing_reports"]
    assert sorted(reports) == cohort.patient_ids()
    for patient_id, report in reports.items():
        gap = report.procedure_capture_gap
        assert gap.exactness_status == "exact", patient_id
        assert [o for o in gap.opportunities if o.get("source") == "lab"] == [], patient_id
    # Patient 7's one capture gap is the unbilled CT angiography of the S7 fault, from PACS.
    seven = reports[_pid(7)].procedure_capture_gap.opportunities
    assert [(o["source"], o["procedure_code"]) for o in seven] == [("pacs", "R101450")]


def test_the_engine_proof_over_the_committed_files_reports_no_mismatch(
    showcase_proofs: tuple[StoryProof, ...],
) -> None:
    """`prove_showcase(build_showcase(), dataset=load_showcase_dataset(<committed claims>))` (`showcase_proofs` of
    `tests/conftest.py`, built once per session)."""
    proofs = showcase_proofs
    faults = len(cohort.load_registry()["faults"])  # a proof for each bill that carries a fault
    assert len(proofs) == faults
    assert [sp.mismatches for sp in proofs] == [()] * faults


# --- 3.14 The formulas pinned to numbers computed apart from the code --------------------------------
#
# The reference numbers below come from exact rational arithmetic (SaO2) and 60-digit Decimal arithmetic
# (the powers), not from floats. The printed values hide constants (one decimal for the blood gas, whole
# numbers for the eGFR), so the unrounded results are compared, to 1e-9.


def _close(actual: float, expected: float) -> bool:
    return abs(actual - expected) < 1e-9


@pytest.mark.parametrize(
    ("po2", "expected"),
    [
        (27.0, 50.35325568073324),
        (40.0, 74.94646680942184),
        (56.0, 88.71832452655534),
        (60.0, 90.57971014492753),
        (100.0, 97.74653312788907),
        (150.0, 99.31596948171534),
    ],
)
def test_the_severinghaus_saturation_equals_the_exact_value(po2: float, expected: float) -> None:
    assert _close(_sao2(po2), expected)
    assert _close(
        pl.DataFrame({"p": [po2]}).select(_sao2(pl.col("p")).alias("v"))["v"][0], expected
    )
    assert severinghaus_sao2(po2) == round(expected, 1)


@pytest.mark.parametrize(
    ("ph", "pco2", "expected"),
    [
        (7.30, 58.0, 28.220608184962586),
        (7.41, 40.0, 25.07254196054182),
        (7.10, 20.0, 6.14),
        (7.50, 25.0, 19.278728361836027),
        (6.95, 80.0, 17.38714846447443),
    ],
)
def test_the_henderson_hasselbalch_bicarbonate_equals_the_exact_value(
    ph: float, pco2: float, expected: float
) -> None:
    assert _close(_hco3(ph, pco2), expected)
    frame = pl.DataFrame({"ph": [ph], "pco2": [pco2]})
    assert _close(frame.select(_hco3(pl.col("ph"), pl.col("pco2")).alias("v"))["v"][0], expected)
    assert henderson_hasselbalch_hco3(ph, pco2) == round(expected, 1)


@pytest.mark.parametrize(
    ("ph", "hco3", "expected"),
    [
        (7.30, 28.2, 2.1576),
        (7.41, 25.1, 0.78864),
        (7.00, 10.0, -18.8976),
        (7.50, 30.0, 6.5844),
    ],
)
def test_the_base_excess_equals_the_exact_value(ph: float, hco3: float, expected: float) -> None:
    assert _close(_base_excess(ph, hco3), expected)
    frame = pl.DataFrame({"ph": [ph], "hco3": [hco3]})
    assert _close(
        frame.select(_base_excess(pl.col("ph"), pl.col("hco3")).alias("v"))["v"][0], expected
    )
    assert base_excess_from_ph_hco3(ph, hco3) == round(expected, 1)


@pytest.mark.parametrize(
    ("scr", "age", "sex", "expected"),
    [
        (0.6, 40, "F", 116.29545162194957),
        (0.74, 58, "F", 93.72382425083177),
        (0.95, 60, "F", 68.58951360663686),
        (1.0, 60, "M", 86.16262077966904),
        (1.2, 77, "M", 62.28511576608984),
        (0.45, 25, "F", 136.83212731612383),
        (2.4, 70, "M", 28.317527720588547),
        (0.5, 30, "M", 140.7182460142157),
        (0.7, 50, "F", 105.29760114914392),
        (0.9, 50, "M", 104.04901299322522),
    ],
)
def test_ckd_epi_2021_equals_the_exact_value_for_both_sexes_and_both_branches(
    scr: float, age: int, sex: str, expected: float
) -> None:
    """The creatinine below and above kappa (0.7 for women, 0.9 for men) use two different exponents."""
    assert _close(ckd_epi_2021(scr, age, sex), expected)
    frame = pl.DataFrame({"scr": [scr], "age": [age], "female": [sex == "F"]})
    expression = ckd_epi_2021_expr(pl.col("scr"), pl.col("age"), pl.col("female"))
    assert _close(frame.select(expression.alias("v"))["v"][0], expected)


# --- 3.20 The albumin the SUT asks for ---------------------------------------------------------------


def test_the_albumin_of_s18_lies_at_or_under_the_sut_infusion_threshold(lab: pl.DataFrame) -> None:
    """S18's albumin is billed (L100320) on the admission day in the state `cirrhosis_at_infusion_threshold` (1.8 to
    2.5 g/dl), so the value always satisfies SUT 4.2.27.Ç.(1) (C006389: albumin at 2.5 g/dl or less)."""
    albumin = lab.filter(pl.col("SUB_CODE") == "L100320")
    assert albumin["HASTA_ID"].to_list() == ["SENTETIK-HASTA-0015"]
    assert albumin["basvuru_id"].to_list() == ["B-SENTETIK-HASTA-0015-001"]
    (value,) = albumin["sonuc_sayisal"].to_list()
    assert 1.8 <= value <= 2.5 and albumin["anormal_mi"].to_list() == [True]
