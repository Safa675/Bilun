"""Unit and mutation tests for `scripts/synthetic/cohort/labs.py` and the `lab_clean.parquet` it makes.

The reference reader, the feed coverage per episode (with the real `detect_lab_capture_gaps`), the
value bands, the coherence rules R1 to R5, the table structure, the generator errors, determinism and
the loaders. Each rule has an in-memory mutation that makes its check fail: the tests copy frames
and never touch a tracked file.

After the independent mutation review (sections 3.13 to 3.19): the validator's gaps (unit, descriptive
columns, decimals, the anadata link), one printed step of drift per rule with the exact row named,
the formulas pinned to numbers computed apart from the code, scripted draws that put a value on a
limit or make the Nth try the first good one, and exact pins of the generator's draws.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from datetime import datetime
import dataclasses
import hashlib
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
    PATIENT_ID_RE,
    BuildResult,
    CleanTableError,
    DerivedLabParameterError,
    LabCoherenceError,
    LabReferenceError,
    ParsedState,
    PatientClinical,
    ShowcaseClinical,
    StoryProof,
    UnsupportedLabStateError,
    UnsupportedState,
    build_clean_tables,
    build_lab_clean,
    build_showcase,
    check_lab_coherence,
    clean_tables_digest,
    draw_u,
    expected_lab_row_count,
    load_clinical,
    load_lab_reference,
    parse_abnormal_state_item,
    parse_abnormal_states,
    validate_clean_tables,
    write_showcase,
)
from scripts.synthetic.cohort.build import DEFAULT_OUT_DIR, main
from scripts.synthetic.cohort import labs as labs_module
from scripts.synthetic.cohort.clinical import PatientLabs
from scripts.synthetic.cohort.labs import (
    BILLED_LAB_CODES,
    _base_excess,
    _egfr_normal_band_for_age,
    _encounter_no,
    _generate_blood_gas_values,
    _generate_creatinine_and_egfr,
    _generate_hemogram_values,
    _hco3,
    _patient_no,
    _sao2,
    _state_for_occurrence,
    _value_in_own_state_ranges,
    base_excess_from_ph_hco3,
    ckd_epi_2021,
    ckd_epi_2021_expr,
    expected_lab_keys,
    draw_numeric_value,
    draw_strip_grade,
    henderson_hasselbalch_hco3,
    invert_ckd_epi_2021,
    load_lab_reference_df,
    severinghaus_sao2,
)
from scripts.synthetic.pathways.loader import hygiene
from src.bilun.cache.data_loader import load_anadata, load_labdata, load_recete
from src.bilun.cache.loaders import _normalize_lab, load_normalized_raw_data
from src.bilun.domain.claims.loader import load_sut_claim_dataset
from src.bilun.domain.prose_rules.lab_capture_gap import detect_lab_capture_gaps
from tests.fixtures import synthetic_cohort as cohort
from tests.fixtures.synthetic_encounters import Extra, with_encounters

pytestmark = pytest.mark.unit

_REPO = Path(__file__).resolve().parents[3]
_OUT_DIR = DEFAULT_OUT_DIR
_CLAIMS_DIR = _OUT_DIR / "sut" / "claims"
_CLEAN_DIR = _OUT_DIR / "sut" / "clean"
_LAB_PARQUET = _CLEAN_DIR / "lab_clean.parquet"
_REGISTRY_JSON_PATH = _OUT_DIR / "cohort_registry.json"
_LAB_CSV = _REPO / "data" / "synthetic" / "reference" / "lab_reference.csv"

_ANON_RE = re.compile(r"anon_|\banon[\s-]*[0-9]", re.IGNORECASE)
_CURRENCY_RE = re.compile(
    r"(?=[0-9.,]*[1-9])[0-9][0-9.,]*\s*(?:TL|TRY|₺)(?![A-Za-z])|₺\s*(?=[0-9.,]*[1-9])[0-9][0-9.,]*",
    re.IGNORECASE,
)

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


def _index_of(
    df: pl.DataFrame,
    patient_no: int,
    code: str,
    parameter: str,
    *,
    date: str | None = None,
    nth: int = 0,
) -> int:
    """Row position of the `nth` row of (patient, code, parameter[, date])."""
    condition = (
        (pl.col("HASTA_ID") == _pid(patient_no))
        & (pl.col("SUB_CODE") == code)
        & (pl.col("parametre") == parameter)
    )
    if date is not None:
        condition = condition & (_day() == date)
    return df.with_row_index("i").filter(condition)["i"][nth]


def _cell(
    df: pl.DataFrame,
    patient_no: int,
    date: str,
    code: str,
    parameter: str,
    column: str = "sonuc_sayisal",
    *,
    nth: int = 0,
) -> Any:
    return df[column][_index_of(df, patient_no, code, parameter, date=date, nth=nth)]


def _set_cell(df: pl.DataFrame, index: int, column: str, value: Any) -> pl.DataFrame:
    """Copy of `df` with one cell replaced."""
    return df.with_columns(
        pl.when(pl.int_range(pl.len()) == index)
        .then(pl.lit(value, dtype=df.schema[column]))
        .otherwise(pl.col(column))
        .alias(column)
    )


def _drop_rows(df: pl.DataFrame, *indexes: int) -> pl.DataFrame:
    return df.filter(~pl.int_range(pl.len()).is_in(list(indexes)))


def _swap_rows(df: pl.DataFrame, i: int, j: int) -> pl.DataFrame:
    """Copy of `df` with rows `i` and `j` (i < j) exchanged."""
    return pl.concat(
        [
            df.slice(0, i),
            df.slice(j, 1),
            df.slice(i + 1, j - i - 1),
            df.slice(i, 1),
            df.slice(j + 1),
        ]
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


def test_reference_parameters_follow_the_csv_order(csv_rows: pl.DataFrame) -> None:
    ref = load_lab_reference()
    for code in _PARAMETER_COUNTS:
        expected = csv_rows.filter(pl.col("ek2b_code") == code)["result_parameter"].to_list()
        assert [s.result_parameter for s in ref.by_code[code]] == expected, code
        assert [s.key for s in ref.by_code[code]] == [f"{code}|{p}" for p in expected], code


def test_reference_limits_units_and_strip_flag_equal_the_csv(csv_rows: pl.DataFrame) -> None:
    ref = load_lab_reference()
    specs = [s for code in _PARAMETER_COUNTS for s in ref.by_code[code]]
    from_reader = pl.DataFrame(
        {
            "key": [s.key for s in specs],
            "unit": [s.unit for s in specs],
            "ref_low_male": [s.ref_low_male for s in specs],
            "ref_high_male": [s.ref_high_male for s in specs],
            "ref_low_female": [s.ref_low_female for s in specs],
            "ref_high_female": [s.ref_high_female for s in specs],
            "strip": [s.is_qualitative_strip for s in specs],
        },
        schema_overrides={c: pl.Float64 for c in _LIMIT_COLUMNS},
    )
    from_csv = csv_rows.select(
        "key",
        pl.col("unit").fill_null(""),
        *_LIMIT_COLUMNS,
        (pl.col("normal_value_range") == "Negatif").alias("strip"),
    )
    assert from_reader.sort("key").equals(from_csv.sort("key"), null_equal=True)
    # Blank limit cells mean a one-sided limit: the 6 strips have none, eGFR has no upper limit.
    assert from_csv.filter(pl.col("strip")).height == 6
    egfr = from_csv.filter(pl.col("key") == f"L104780|{_EGFR}")
    assert egfr["ref_low_male"][0] == egfr["ref_low_female"][0] == 60.0
    assert egfr["ref_high_male"][0] is None and egfr["ref_high_female"][0] is None


def test_reference_decimals_are_the_pinned_ones() -> None:
    ref = load_lab_reference()
    decimals = {s.key: s.decimals for code in _PARAMETER_COUNTS for s in ref.by_code[code]}
    assert decimals == _DECIMALS
    assert max(decimals.values()) <= 3


def test_reference_egfr_age_bands() -> None:
    assert load_lab_reference().egfr_age_bands == (
        (18, 39, 95.0, 120.0),
        (40, 59, 85.0, 105.0),
        (60, 69, 75.0, 95.0),
        (70, 200, 70.0, 85.0),
    )


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


def test_unsupported_prose_states_of_the_billed_codes_are_these_four() -> None:
    ref = load_lab_reference()
    unsupported = [
        (s.test_key, s.key, u.raw_text)
        for s in ref.billed_code_parameters
        for u in s.unsupported_states
    ]
    assert unsupported == [
        (
            "hemogram",
            "L107020|BASO# (Bazofil)",
            "rarely abnormal (myeloproliferative disease out of scope)",
        ),
        ("creatinine", "L104780|Kreatinin", "aki (KDIGO): 1.5–3.0 × the patient's baseline"),
        (
            "blood_gas_venous",
            "L103900|pO2",
            "not interpreted (draw from normal_value_range in every state)",
        ),
        (
            "blood_gas_venous",
            "L103900|sO2 (venöz)",
            "not interpreted (draw from normal_value_range in every state)",
        ),
    ]


# Grammar forms found in the 14 billed codes: the form as written in the CSV, whether the row is a
# qualitative strip, what it parses to, and a mutated copy of the item that must be rejected.
_GRAMMAR_FORMS = [
    pytest.param(
        "anemia: M 3.0–4.4, F 2.8–3.9",
        False,
        {"kind": "sex_range", "name": "anemia", "sex_ranges": {"M": (3.0, 4.4), "F": (2.8, 3.9)}},
        "anemia: M 3.0–4.4, M 2.8–3.9",
        id="sex_specific_pair",
    ),
    pytest.param(
        "copd_polycythemia: M 17.6–20.0",
        False,
        {"kind": "sex_range", "sex_ranges": {"M": (17.6, 20.0)}},
        "copd_polycythemia: M 20.0–17.6",
        id="single_sex",
    ),
    pytest.param(
        "sepsis: 12.0–30.0 or 1.5–3.9",
        False,
        {"kind": "or_range", "low": 12.0, "high": 30.0, "alternatives": ((12.0, 30.0), (1.5, 3.9))},
        "sepsis: 12.0–30.0 or 1.5-3.9",
        id="or_takes_the_first",
    ),
    pytest.param(
        "metabolic_acidosis: -20 to -3",
        False,
        {"kind": "to_range", "low": -20.0, "high": -3.0},
        "metabolic_acidosis: -3 to -20",
        id="signed_negative",
    ),
    pytest.param(
        "metabolic_alkalosis: +3 to +12",
        False,
        {"kind": "to_range", "low": 3.0, "high": 12.0},
        "metabolic_alkalosis: +3 to + 12",
        id="signed_positive",
    ),
    pytest.param(
        "diabetic_or_hypertensive_nephropathy: Eser to +",
        True,
        {"kind": "grade_range", "grade_low": "Eser", "grade_high": "+"},
        "diabetic_or_hypertensive_nephropathy: + to Eser",
        id="grade_range",
    ),
    pytest.param(
        "sglt2_inhibitor_use: +++ to ++++ even with normal blood glucose",
        True,
        {"kind": "grade_range", "grade_low": "+++", "grade_high": "++++"},
        "sglt2_inhibitor_use: +++ to +++++ even with normal blood glucose",
        id="grade_range_with_remark",
    ),
    pytest.param(
        "nephrotic: +++",
        True,
        {"kind": "grade_single", "grade_low": "+++", "grade_high": "+++"},
        "nephrotic: ++++++",
        id="single_grade",
    ),
    pytest.param(
        "uti_enterobacterales (E. coli): Pozitif (often negative in true UTI)",
        True,
        {"kind": "grade_single", "name": "uti_enterobacterales", "grade_low": "Pozitif"},
        "uti_enterobacterales (E. coli): Positive",
        id="positive_with_parenthetical",
    ),
    pytest.param(
        "rhabdomyolysis: +++ with 0–2 RBC/HPF",
        True,
        {"kind": "grade_single", "grade_low": "+++"},
        "rhabdomyolysis: +++ with 0–2 RBC",
        id="grade_with_rbc_remark",
    ),
    pytest.param(
        "ckd_g3a: eGFR 45–59",
        False,
        {"kind": "egfr_band", "low": 45.0, "high": 59.0},
        "ckd_g3a: eGFR 59–45",
        id="egfr_band",
    ),
    pytest.param(
        "ckd_g5: eGFR 5–14 (on dialysis: pre-dialysis 4.5–10.0)",
        False,
        {"kind": "egfr_band", "low": 5.0, "high": 14.0},
        "ckd_g5: eGFR 5–14 on dialysis",
        id="egfr_band_with_parenthetical",
    ),
    pytest.param(
        "prediabetes_ifg: 100–125 (fasting)",
        False,
        {"kind": "num_range", "low": 100.0, "high": 125.0},
        "prediabetes_ifg: 100–125 fasting",
        id="trailing_parenthetical",
    ),
    pytest.param(
        "hyponatremia (hf, diuretic, siadh, elderly): 125–134",
        False,
        {
            "kind": "num_range",
            "name": "hyponatremia",
            "full_name": "hyponatremia (hf, diuretic, siadh, elderly)",
            "low": 125.0,
            "high": 134.0,
        },
        "hyponatremia (hf, diuretic, siadh, elderly) 125–134",
        id="name_with_parenthetical",
    ),
    pytest.param(
        "thalassemia_trait: 5.0–6.5 with MCV 60–75",
        False,
        {"kind": "num_range", "low": 5.0, "high": 6.5},
        "thalassemia_trait: 5.0–6.5 with MCV 60",
        id="with_mcv_remark",
    ),
    pytest.param(
        "uti: 10–100 (or 'bol')",
        False,
        {"kind": "num_range", "low": 10.0, "high": 100.0},
        "uti: 10–100 (or 'bol'",
        id="or_inside_a_parenthetical",
    ),
]


@pytest.mark.parametrize(("item", "strip", "expected", "_broken"), _GRAMMAR_FORMS)
def test_parse_abnormal_state_item_grammar_forms(
    item: str, strip: bool, expected: dict[str, Any], _broken: str
) -> None:
    parsed = parse_abnormal_state_item(item, is_qualitative_strip=strip)
    assert isinstance(parsed, ParsedState)
    assert parsed.raw_text == item
    for attribute, value in expected.items():
        assert getattr(parsed, attribute) == value, attribute


@pytest.mark.parametrize(("_item", "strip", "_expected", "broken"), _GRAMMAR_FORMS)
def test_mutation_a_broken_copy_of_each_grammar_form_is_rejected(
    _item: str, strip: bool, _expected: dict[str, Any], broken: str
) -> None:
    with pytest.raises(LabReferenceError):
        parse_abnormal_state_item(broken, is_qualitative_strip=strip, context="mutation")


def test_state_ranges_by_sex_and_the_missing_sex() -> None:
    both = parse_abnormal_state_item("anemia: M 3.0–4.4, F 2.8–3.9")
    male_only = parse_abnormal_state_item("copd_polycythemia: M 17.6–20.0")
    assert isinstance(both, ParsedState) and isinstance(male_only, ParsedState)
    assert both.range_for_sex("M") == (3.0, 4.4)
    assert both.range_for_sex("F") == (2.8, 3.9)
    assert male_only.range_for_sex("M") == (17.6, 20.0)
    with pytest.raises(LabCoherenceError, match="no range for sex 'F'"):
        male_only.range_for_sex("F")
    plain = parse_abnormal_state_item("bacterial_infection: 11.0–20.0")
    assert isinstance(plain, ParsedState)
    assert plain.range_for_sex("M") == plain.range_for_sex("F") == (11.0, 20.0)


@pytest.mark.parametrize(
    ("item", "name"),
    [
        ("rarely abnormal (myeloproliferative disease out of scope)", "rarely abnormal"),
        ("not interpreted (draw from normal_value_range in every state)", "not interpreted"),
        ("aki (KDIGO): 1.5–3.0 × the patient's baseline", "aki"),
    ],
)
def test_prose_without_a_range_is_unsupported_and_keeps_its_text(item: str, name: str) -> None:
    result = parse_abnormal_state_item(item)
    assert isinstance(result, UnsupportedState)
    assert result.name == name
    assert result.raw_text == item


@pytest.mark.parametrize(
    "item",
    [
        "",
        "no colon here",
        "anemia:",
        "x: 5–3",
        "x: 5–5",
        "x: 1–2–3",
        "x: eGFR 45",
        ": 5–6",
        "x: M 3–4, F",
        "x: 5–6 or 9–7",
    ],
)
def test_malformed_items_are_rejected(item: str) -> None:
    with pytest.raises(LabReferenceError):
        parse_abnormal_state_item(item, context="malformed")


def test_parse_abnormal_states_splits_on_semicolons_in_order() -> None:
    parsed, unsupported = parse_abnormal_states(
        "viral_or_mild_inflammation: 5–40; "
        "bacterial_infection (pneumonia, pyelonephritis, cellulitis): 50–250; "
        "rarely abnormal (out of scope)"
    )
    assert [p.name for p in parsed] == ["viral_or_mild_inflammation", "bacterial_infection"]
    assert [u.name for u in unsupported] == ["rarely abnormal"]
    assert parse_abnormal_states("") == ((), ())


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
_ORDINAL = ("Negatif", "Eser", "+", "++", "+++", "++++")


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


def _grade_band(abnormal_states: str, state: str) -> tuple[str, str]:
    rhs = re.sub(r"\s*\(.*$", "", _items(abnormal_states)[state])
    low, _, high = rhs.partition(" to ")
    return low, high or low


def _state_ranges(abnormal_states: str, sex: str) -> list[tuple[float, float]]:
    """Every numeric state range of a parameter for `sex` (the first alternative of an 'or')."""
    out: list[tuple[float, float]] = []
    for item in abnormal_states.split("; "):
        rhs = item.partition(": ")[2]
        if re.search(r"\b[MF] \d", rhs):
            match = re.search(rf"\b{sex} {_NUMBER}–{_NUMBER}", rhs)
        else:
            match = re.search(rf"{_NUMBER}\s*(?:–|to)\s*{_NUMBER}", rhs)
        if match:
            out.append((float(match.group(1)), float(match.group(2))))
    return out


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


def test_derived_red_cell_values_lie_inside_the_limits_or_the_own_state_ranges(
    annotated: pl.DataFrame,
) -> None:
    hemogram = annotated.filter(pl.col("SUB_CODE") == "L107020")
    drivers = hemogram.group_by("HASTA_ID", "k").agg(
        (
            pl.col("parametre").is_in(["HGB (Hemoglobin)", "MCV", "MCH"])
            & (pl.col("state") != "normal")
        )
        .any()
        .alias("driver_state")
    )
    derived = hemogram.filter(
        pl.col("parametre").is_in(["RBC (Eritrosit)", "HCT (Hematokrit)", "MCHC"])
    ).join(drivers, on=["HASTA_ID", "k"], how="left")
    inside = (pl.col("sonuc_sayisal") >= pl.col("lo")) & (pl.col("sonuc_sayisal") <= pl.col("hi"))
    assert derived.height == 57  # patient 15's three blood counts add nine, the blood counts of S41 and S36 three each
    # Without a state on HGB, MCV or MCH, the derived values are normal values.
    assert derived.filter(~pl.col("driver_state") & ~inside).is_empty()
    # With one (patients 3 and 9, postoperative HGB; patients 12 and 15, the HGB of a bleed and the small red cells of
    # a slow loss) a derived value may sit in one of its own state ranges.
    with_state = derived.filter(pl.col("driver_state") & ~inside)
    assert with_state["HASTA_ID"].unique(maintain_order=True).to_list() == [_pid(3), _pid(9), _pid(12), _pid(15)]
    for row in with_state.select("sonuc_sayisal", "abnormal_states", "sex").to_dicts():
        ranges = _state_ranges(row["abnormal_states"], row["sex"])
        assert any(lo <= row["sonuc_sayisal"] <= hi for lo, hi in ranges), row
    assert with_state["parametre"].to_list() == (
        ["RBC (Eritrosit)", "HCT (Hematokrit)"] * 2  # patients 3 and 9
        + ["RBC (Eritrosit)", "HCT (Hematokrit)"]  # patient 12, the ER bill: the anaemia ranges of the red cells
        + ["RBC (Eritrosit)", "HCT (Hematokrit)", "MCHC"]  # patient 12, the admission: and the iron-deficiency MCHC
        + ["RBC (Eritrosit)", "HCT (Hematokrit)", "MCHC"]  # patient 15, the cirrhosis stay (S18): the same
        + ["RBC (Eritrosit)", "HCT (Hematokrit)"] * 2  # patient 15, the rebleed (S24): its two counts, MCHC normal
    )


_PROFILES: dict[str, dict[str, tuple[float, float]]] = {
    "normal": {
        "NEU# (Nötrofil)": (55.0, 65.0),
        "LYM# (Lenfosit)": (25.0, 35.0),
        "MONO# (Monosit)": (4.0, 8.0),
        "EOS# (Eozinofil)": (1.0, 3.0),
        "BASO# (Bazofil)": (0.5, 1.0),
    },
    "bacterial_infection": {
        "NEU# (Nötrofil)": (75.0, 88.0),
        "LYM# (Lenfosit)": (8.0, 15.0),
        "MONO# (Monosit)": (3.0, 8.0),
        "EOS# (Eozinofil)": (0.0, 1.0),
        "BASO# (Bazofil)": (0.2, 0.6),
    },
    "steroid_use": {
        "NEU# (Nötrofil)": (80.0, 90.0),
        "LYM# (Lenfosit)": (5.0, 10.0),
        "MONO# (Monosit)": (3.0, 6.0),
        "EOS# (Eozinofil)": (0.0, 0.5),
        "BASO# (Bazofil)": (0.1, 0.4),
    },
}


def _share_bounds(profile: str, parameter: str) -> tuple[float, float]:
    """Smallest and largest share of WBC after the five percentages are scaled to sum 100."""
    ranges = _PROFILES[profile]
    low, high = ranges[parameter]
    others = [r for p, r in ranges.items() if p != parameter]
    return (
        low / (low + sum(h for _, h in others)),
        high / (high + sum(lo for lo, _ in others)),
    )


def test_the_differential_follows_the_profile_of_the_wbc_state(annotated: pl.DataFrame) -> None:
    hemogram = annotated.filter(pl.col("SUB_CODE") == "L107020")
    wide = hemogram.pivot(
        on="parametre", index=["HASTA_ID", "k"], values="sonuc_sayisal", aggregate_function="first"
    )
    wbc_state = (
        hemogram.filter(pl.col("parametre") == "WBC (Lökosit)")
        .select("HASTA_ID", "k", "state")
        .with_columns(
            pl.when(pl.col("state").is_in(list(_PROFILES)))
            .then(pl.col("state"))
            .otherwise(pl.lit("normal"))
            .alias("profile")
        )
    )
    sets = wide.join(wbc_state, on=["HASTA_ID", "k"], how="inner")
    assert sets.height == 19
    assert sorted(sets["profile"].to_list()) == (
        ["bacterial_infection"] * 5 + ["normal"] * 13 + ["steroid_use"]  # the blood counts of the control and of patients 3 (S36), 5, 12 and 15 have no WBC state
    )
    for profile in _PROFILES:
        group = sets.filter(pl.col("profile") == profile)
        for parameter in _DIFFERENTIAL:
            low, high = _share_bounds(profile, parameter)
            share = group[parameter] / group["WBC (Lökosit)"]
            assert ((share >= low - 0.01) & (share <= high + 0.01)).all(), (profile, parameter)
    # With no WBC state the five counts are normal values.
    normal = hemogram.filter(pl.col("parametre").is_in(list(_DIFFERENTIAL))).join(
        wbc_state.filter(pl.col("profile") == "normal"), on=["HASTA_ID", "k"], how="inner"
    )
    assert normal.height == 65  # patient 15's three counts add fifteen, the ER count of S41 and the pre-operative count of S36 five each
    assert normal.filter(
        (pl.col("sonuc_sayisal") < pl.col("lo")) | (pl.col("sonuc_sayisal") > pl.col("hi"))
    ).is_empty()


def test_strips_are_negative_unless_the_yaml_asks_for_a_grade(annotated: pl.DataFrame) -> None:
    strips = annotated.filter(pl.col("sonuc_nitel").is_not_null())
    assert strips.height == 12  # two urinalyses, patient 4 on 2026-05-11 (the stay) and 2026-05-25 (the control)
    assert strips.select("HASTA_ID", "day").unique().sort("day").rows() == [
        (_pid(4), "2026-05-11"),
        (_pid(4), "2026-05-25"),
    ]
    plain = strips.filter(pl.col("state") == "normal")
    # glucose, ketone, blood of the stay; all six strips of the control, whose entry asks for no state (cleared)
    assert plain["sonuc_nitel"].to_list() == ["Negatif"] * 9
    asked = strips.filter(pl.col("state") != "normal")
    assert asked.height == 3
    for row in asked.select("parametre", "state", "sonuc_nitel", "abnormal_states").to_dicts():
        low, high = _grade_band(row["abnormal_states"], row["state"])
        grade = row["sonuc_nitel"]
        if low == "Pozitif":
            assert grade == "Pozitif", row
        else:
            assert _ORDINAL.index(low) <= _ORDINAL.index(grade) <= _ORDINAL.index(high), row


def test_microscopy_counts_are_whole_numbers_inside_the_limits_or_the_state(
    annotated: pl.DataFrame,
) -> None:
    rows = annotated.filter(
        pl.col("parametre").is_in(["Mikroskopi: lökosit", "Mikroskopi: eritrosit"])
    )
    assert rows.height == 4  # the two urinalyses, patient 4 on 2026-05-11 and 2026-05-25
    assert ((rows["sonuc_sayisal"] % 1) == 0).all()
    erythrocytes = rows.filter(pl.col("parametre") == "Mikroskopi: eritrosit")
    assert (
        erythrocytes.filter(pl.col("sonuc_sayisal").is_between(pl.col("lo"), pl.col("hi"))).height
        == 2
    )


def test_no_numeric_value_is_nan_or_infinite(lab: pl.DataFrame) -> None:
    numeric = lab.filter(pl.col("sonuc_nitel").is_null())
    assert numeric.height == LAB_ROWS - 12  # the twelve urine strips (two urinalyses) have a grade, not a number
    assert numeric["sonuc_sayisal"].null_count() == 0
    assert numeric["sonuc_sayisal"].is_finite().all()
    assert (
        lab["ref_alt"].drop_nulls().is_finite().all()
        and lab["ref_ust"].drop_nulls().is_finite().all()
    )


def test_values_have_the_decimals_of_the_csv_or_the_fixed_ones_of_the_rules(
    annotated: pl.DataFrame,
) -> None:
    decimals = {**_DECIMALS, **_FIXED_DECIMALS}
    numeric = annotated.filter(pl.col("sonuc_sayisal").is_not_null()).with_columns(
        pl.col("key").replace_strict(decimals, return_dtype=pl.Int64).alias("decimals")
    )
    scaled = pl.col("sonuc_sayisal") * pl.lit(10.0).pow(pl.col("decimals"))
    off_grid = numeric.filter((scaled - scaled.round(0)).abs() > 1e-6)
    assert off_grid.is_empty(), off_grid.select("key", "sonuc_sayisal", "decimals")


def test_the_draws_of_independent_rows_follow_the_documented_formula(lab: pl.DataFrame) -> None:
    """Recompute five rows from SHA-256 and the CSV limits or the state ranges."""

    def u(patient_no: int, code: str, parameter: str, k: int) -> float:
        payload = f"{_pid(patient_no)}|{code}|{parameter}|{k}|0".encode()
        return int.from_bytes(hashlib.sha256(payload).digest()[:8], "big") / 2**64

    day1, day2, er = "2026-03-09", "2026-03-12", "2026-02-19"
    # normal: the central band 0.30 to 0.70 of the male limits (0, 41)
    assert _cell(lab, 2, day1, "L100300", "ALT") == round(
        41 * (0.30 + 0.40 * u(2, "L100300", "ALT", 1))
    )
    # normal, one decimal, female potassium limits 3.5 to 5.1
    assert _cell(lab, 7, er, "L106150", "Potasyum") == round(
        3.5 + 1.6 * (0.30 + 0.40 * u(7, "L106150", "Potasyum", 1)), 1
    )
    # state: the band 0.20 to 0.80 of the state range, bacterial_infection 50 to 250
    assert _cell(lab, 2, day1, "L101850", "CRP (kantitatif)") == round(
        50 + 200 * (0.20 + 0.60 * u(2, "L101850", "CRP (kantitatif)", 1))
    )
    # state with two decimals: copd_exacerbation pH 7.25 to 7.34
    assert _cell(lab, 2, day1, "L103900", "pH") == round(
        7.25 + 0.09 * (0.20 + 0.60 * u(2, "L103900", "pH", 1)), 2
    )
    # state: elderly_without_vte D-dimer 400 to 900
    assert _cell(lab, 7, er, "L102090", "D-dimer") == round(
        400 + 500 * (0.20 + 0.60 * u(7, "L102090", "D-dimer", 1))
    )
    # the k-th billed line draws its own value: both serial troponins, female limits (0, 15.6)
    for nth, k in ((0, 1), (1, 2)):
        expected = round(15.6 * (0.30 + 0.40 * u(7, "L107360", "hs-Troponin I", k)), 1)
        assert _cell(lab, 7, er, "L107360", "hs-Troponin I", nth=nth) == expected
    assert _cell(lab, 7, er, "L107360", "hs-Troponin I", nth=0) != _cell(
        lab, 7, er, "L107360", "hs-Troponin I", nth=1
    )


_DRAW_PAYLOADS = [
    ("SENTETIK-HASTA-0001", "L107020", "WBC (Lökosit)", 1, 0),
    ("SENTETIK-HASTA-0002", "L103900", "İyonize kalsiyum (kan gazı)", 2, 0),
    ("SENTETIK-HASTA-0007", "L107360", "hs-Troponin I", 2, 17),
]


@pytest.mark.parametrize(("patient", "code", "parameter", "k", "salt"), _DRAW_PAYLOADS)
def test_draw_u_is_the_first_8_bytes_of_sha256_over_the_pipe_joined_payload(
    patient: str, code: str, parameter: str, k: int, salt: int
) -> None:
    digest = hashlib.sha256(f"{patient}|{code}|{parameter}|{k}|{salt}".encode()).digest()
    expected = int.from_bytes(digest[:8], "big") / 2**64
    assert draw_u(patient, code, parameter, k, salt) == expected
    assert 0.0 <= expected < 1.0


def test_draw_u_depends_on_every_part_of_the_payload_and_nothing_else() -> None:
    base = draw_u("SENTETIK-HASTA-0001", "L107020", "WBC (Lökosit)", 1, 0)
    assert base == 0.24122513161751777  # pinned: no seed and no clock enter the draw
    variants = {
        draw_u("SENTETIK-HASTA-0002", "L107020", "WBC (Lökosit)", 1, 0),
        draw_u("SENTETIK-HASTA-0001", "L107360", "WBC (Lökosit)", 1, 0),
        draw_u("SENTETIK-HASTA-0001", "L107020", "MPV", 1, 0),
        draw_u("SENTETIK-HASTA-0001", "L107020", "WBC (Lökosit)", 2, 0),
        draw_u("SENTETIK-HASTA-0001", "L107020", "WBC (Lökosit)", 1, 1),
    }
    assert base not in variants and len(variants) == 5
    assert draw_u("SENTETIK-HASTA-0001", "L107020", "WBC (Lökosit)", 1, 0) == base


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
    pytest.param("L107020", _NEU, -0.01, "R1", _WBC, id="R1_neutrophils_-0.01"),
    pytest.param("L107020", _NEU, 0.04, "R1", _WBC, id="R1_neutrophils_+0.04"),
    pytest.param("L107020", _NEU, -0.04, "R1", _WBC, id="R1_neutrophils_-0.04"),
    pytest.param("L107020", _NEU, 1.0, "R1", _WBC, id="R1_neutrophils_+1"),
    pytest.param("L107020", "LYM# (Lenfosit)", 0.01, "R1", _WBC, id="R1_lymphocytes_+0.01"),
    pytest.param("L107020", "BASO# (Bazofil)", -0.01, "R1", _WBC, id="R1_basophils_-0.01"),
    pytest.param("L107020", _RBC, 0.1, "R2", _RBC, id="R2_rbc_+1_step"),
    pytest.param("L107020", _RBC, -0.1, "R2", _RBC, id="R2_rbc_-1_step"),
    pytest.param("L107020", _RBC, 0.5, "R2", _RBC, id="R2_rbc_+5_steps"),
    pytest.param("L107020", _HCT, 1.0, "R2", _HCT, id="R2_hct_+1_step"),
    pytest.param("L107020", _HCT, -1.0, "R2", _HCT, id="R2_hct_-1_step"),
    pytest.param("L107020", _HCT, 5.0, "R2", _HCT, id="R2_hct_+5_steps"),
    pytest.param("L107020", _MCHC, 0.1, "R2", _MCHC, id="R2_mchc_+1_step"),
    pytest.param("L107020", _MCHC, -0.1, "R2", _MCHC, id="R2_mchc_-1_step"),
    pytest.param("L107020", _MCHC, 2.0, "R2", _MCHC, id="R2_mchc_+20_steps"),
    pytest.param("L104780", _EGFR, 1.0, "R3", _EGFR, id="R3_egfr_+1_step"),
    pytest.param("L104780", _EGFR, -1.0, "R3", _EGFR, id="R3_egfr_-1_step"),
    pytest.param("L104780", _EGFR, 10.0, "R3", _EGFR, id="R3_egfr_+10_steps"),
    pytest.param("L103900", "HCO3", 0.1, "R4", "HCO3", id="R4_hco3_+1_step"),
    pytest.param("L103900", "HCO3", -0.1, "R4", "HCO3", id="R4_hco3_-1_step"),
    pytest.param("L103900", "HCO3", 3.0, "R4", "HCO3", id="R4_hco3_+30_steps"),
    pytest.param("L103900", _BE, 0.1, "R4", _BE, id="R4_be_+1_step"),
    pytest.param("L103900", _BE, -0.1, "R4", _BE, id="R4_be_-1_step"),
    pytest.param("L103900", _BE, 2.0, "R4", _BE, id="R4_be_+20_steps"),
    pytest.param("L103900", "SaO2", 0.1, "R4", "SaO2", id="R4_sao2_+1_step"),
    pytest.param("L103900", "SaO2", -0.1, "R4", "SaO2", id="R4_sao2_-1_step"),
    pytest.param("L103900", "SaO2", 3.0, "R4", "SaO2", id="R4_sao2_+30_steps"),
    # A driver value moved: the derived value that follows from it is the one that is named.
    pytest.param("L107020", "HGB (Hemoglobin)", 1.0, "R2", _RBC, id="driver_hgb_names_rbc"),
    pytest.param("L107020", "MCH", 2.0, "R2", _RBC, id="driver_mch_names_rbc"),
    pytest.param("L107020", "MCV", 5.0, "R2", _HCT, id="driver_mcv_names_hct"),
    pytest.param("L103900", "pH", 0.05, "R4", "HCO3", id="driver_ph_names_hco3"),
    pytest.param("L103900", "pCO2", 3.0, "R4", "HCO3", id="driver_pco2_names_hco3"),
    pytest.param("L103900", "pO2", 5.0, "R4", "SaO2", id="driver_po2_names_sao2"),
    pytest.param("L104780", "Kreatinin", 0.2, "R3", _EGFR, id="driver_creatinine_names_egfr"),
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


def test_troponin_i_uses_the_sex_specific_limit_of_the_csv(
    lab: pl.DataFrame, csv_rows: pl.DataFrame
) -> None:
    troponin = csv_rows.filter(pl.col("ek2b_code") == "L107360")
    assert (troponin["ref_high_male"][0], troponin["ref_high_female"][0]) == (34.2, 15.6)
    rows = lab.filter(pl.col("SUB_CODE") == "L107360")
    assert rows["HASTA_ID"].unique().to_list() == [_pid(7)]  # a woman
    # S7's two serial sets and the one of the observation S47
    assert rows["ref_ust"].to_list() == [15.6, 15.6, 15.6] and rows["ref_alt"].to_list() == [0.0, 0.0, 0.0]
    assert rows["anormal_mi"].to_list() == [False, False, False]
    # 20 ng/L is abnormal for her and would be normal against the male limit.
    index = _index_of(lab, 7, "L107360", "hs-Troponin I", nth=0)
    assert 15.6 < 20.0 < 34.2
    raised = _set_cell(lab, index, "sonuc_sayisal", 20.0)
    with pytest.raises(LabCoherenceError, match=r"R5"):
        check_lab_coherence(raised)
    check_lab_coherence(_set_cell(raised, index, "anormal_mi", True))


def test_requested_states_give_the_expected_flags_inside_the_csv_ranges(
    lab: pl.DataFrame,
) -> None:
    def value(patient_no: int, date: str, code: str, parameter: str, nth: int = 0) -> float:
        return _cell(lab, patient_no, date, code, parameter, nth=nth)

    def flag(patient_no: int, date: str, code: str, parameter: str, nth: int = 0) -> bool:
        return _cell(lab, patient_no, date, code, parameter, "anormal_mi", nth=nth)

    wbc = "WBC (Lökosit)"
    # Patient 2: a bacterial infection on day 1, steroid use on day 4; both are high.
    assert 11.0 <= value(2, "2026-03-09", "L107020", wbc) <= 20.0
    assert 10.5 <= value(2, "2026-03-12", "L107020", wbc) <= 15.0
    assert flag(2, "2026-03-09", "L107020", wbc) and flag(2, "2026-03-12", "L107020", wbc)
    # Patient 2 blood gas: respiratory acidosis with hypercapnia on day 1, normal pH and pCO2 on day 4.
    assert value(2, "2026-03-09", "L103900", "pH") < 7.35
    assert value(2, "2026-03-09", "L103900", "pCO2") > 45
    assert flag(2, "2026-03-09", "L103900", "pH") and flag(2, "2026-03-09", "L103900", "pCO2")
    assert 7.35 <= value(2, "2026-03-12", "L103900", "pH") <= 7.45
    assert 35 <= value(2, "2026-03-12", "L103900", "pCO2") <= 45
    assert not flag(2, "2026-03-12", "L103900", "pH") and not flag(
        2, "2026-03-12", "L103900", "pCO2"
    )
    # Patient 7: D-dimer above 500 ng/mL FEU, and a troponin that rules the infarct out.
    assert value(7, "2026-02-19", "L102090", "D-dimer") > 500
    assert flag(7, "2026-02-19", "L102090", "D-dimer")
    # Patient 4: CKD G3a (eGFR below 60 on both days), hyponatremia on day 1, leukocytosis only on day 1.
    egfr = "eGFR (CKD-EPI 2021, hesaplanan)"
    for day in ("2026-05-11", "2026-05-13"):
        assert value(4, day, "L104780", egfr) < 60 and flag(4, day, "L104780", egfr)
    assert value(4, "2026-05-11", "L106910", "Sodyum") < 136
    assert flag(4, "2026-05-11", "L106910", "Sodyum")
    assert value(4, "2026-05-11", "L107020", wbc) > 10 and flag(4, "2026-05-11", "L107020", wbc)
    assert 4 <= value(4, "2026-05-13", "L107020", wbc) <= 10
    assert not flag(4, "2026-05-13", "L107020", wbc)
    # Patient 1: CRP above its upper limit (5 mg/L).
    crp = "CRP (kantitatif)"
    assert value(1, "2026-07-15", "L101850", crp) > 5 and flag(1, "2026-07-15", "L101850", crp)
    # Patient 4's urinalysis strips: fever or UTI protein, esterase and nitrite are positive.
    for strip in ("Protein (strip)", "Lökosit esteraz (strip)", "Nitrit (strip)"):
        assert flag(4, "2026-05-11", "L107010", strip), strip
        assert _cell(lab, 4, "2026-05-11", "L107010", strip, "sonuc_nitel") != "Negatif"
    assert not flag(4, "2026-05-11", "L107010", "Glukoz (strip)")


@pytest.mark.parametrize(
    ("patient_no", "date", "code", "parameter", "column", "value", "message"),
    [
        pytest.param(
            1,
            "2026-07-15",
            "L101850",
            "CRP (kantitatif)",
            "anormal_mi",
            False,
            r"R5",
            id="numeric_flag_true_to_false",
        ),
        pytest.param(
            2,
            "2026-03-09",
            "L102890",
            "Glukoz",
            "anormal_mi",
            True,
            r"R5",
            id="numeric_flag_false_to_true",
        ),
        pytest.param(
            4,
            "2026-05-11",
            "L107010",
            "Nitrit (strip)",
            "anormal_mi",
            False,
            r"R5",
            id="strip_flag_true_to_false",
        ),
        pytest.param(
            4,
            "2026-05-11",
            "L107010",
            "Keton (strip)",
            "anormal_mi",
            True,
            r"R5",
            id="strip_flag_false_to_true",
        ),
        pytest.param(
            4,
            "2026-05-11",
            "L107010",
            "Protein (strip)",
            "sonuc_sayisal",
            1.0,
            r"R6",
            id="numeric_value_on_a_strip",
        ),
        pytest.param(
            4,
            "2026-05-11",
            "L107010",
            "Protein (strip)",
            "sonuc_nitel",
            "+++++",
            r"R6",
            id="invalid_strip_grade",
        ),
        pytest.param(
            4,
            "2026-05-11",
            "L107010",
            "Protein (strip)",
            "birim",
            "mg/dL",
            r"R6",
            id="unit_on_a_strip",
        ),
        pytest.param(
            4,
            "2026-05-11",
            "L107010",
            "Protein (strip)",
            "ref_ust",
            5.0,
            r"R6",
            id="limit_on_a_strip",
        ),
        pytest.param(
            2,
            "2026-03-09",
            "L102890",
            "Glukoz",
            "sonuc_nitel",
            "Negatif",
            r"R6",
            id="grade_on_a_numeric_row",
        ),
        pytest.param(
            2,
            "2026-03-09",
            "L102890",
            "Glukoz",
            "sonuc_sayisal",
            None,
            r"finite",
            id="numeric_row_without_value",
        ),
        pytest.param(
            2,
            "2026-03-09",
            "L102890",
            "Glukoz",
            "sonuc_sayisal",
            float("nan"),
            r"finite",
            id="nan_value",
        ),
        pytest.param(
            2,
            "2026-03-09",
            "L102890",
            "Glukoz",
            "sonuc_sayisal",
            float("inf"),
            r"finite",
            id="infinite_value",
        ),
    ],
)
def test_mutation_a_row_that_breaks_the_flag_or_strip_rules_is_rejected(
    lab: pl.DataFrame,
    ana: pl.DataFrame,
    patient_no: int,
    date: str,
    code: str,
    parameter: str,
    column: str,
    value: Any,
    message: str,
) -> None:
    index = _index_of(lab, patient_no, code, parameter, date=date)
    mutated = _set_cell(lab, index, column, value)
    caught = _rejected(mutated, ana)
    # `message` is the name of the rule; the row is the changed one.
    _assert_names_the_row(caught, lab, rule=message, row=index, code=code, parameter=parameter)


# --- 3.6 Structure --------------------------------------------------------------------------------


def test_the_table_has_exactly_the_lab_clean_schema(lab: pl.DataFrame) -> None:
    assert pl.Schema(lab.schema) == LAB_CLEAN_SCHEMA
    assert lab.columns == list(LAB_CLEAN_SCHEMA.names())
    assert lab.columns[2:4] == ["SUB_CODE", "parametre"]
    assert all(dtype != pl.Null for dtype in lab.schema.values())
    assert pl.Schema(pl.read_parquet(_LAB_PARQUET).schema) == LAB_CLEAN_SCHEMA


def test_row_attributes_follow_the_claim_and_the_csv(
    annotated: pl.DataFrame, built_showcase: BuildResult
) -> None:
    assert all(PATIENT_ID_RE.fullmatch(v) for v in annotated["HASTA_ID"].unique().to_list())
    assert annotated["kohort"].unique().to_list() == ["showcase"]
    year = pl.col("tarih").dt.year().cast(pl.String)
    assert annotated.filter(pl.col("donem").ne_missing(year)).is_empty()
    midnight = pl.col("tarih").dt.truncate("1d")
    assert annotated.filter(pl.col("tarih").ne_missing(midnight)).is_empty()
    # The episode is the claim's episode: a bill of the row's patient (a patient may have several bills).
    headers = built_showcase.tables["claim_headers.parquet"].select(
        pl.col("patient_id").alias("HASTA_ID"), pl.col("episode_id").alias("basvuru_id")
    )
    assert annotated.join(headers, on=["HASTA_ID", "basvuru_id"], how="anti").is_empty()
    # The body system: hemogram, manual haematocrit and D-dimer are haematology, everything else biochemistry.
    expected_system = (
        pl.when(pl.col("SUB_CODE").is_in(["L107020", "L103120", "L102090"]))
        .then(pl.lit("Hematoloji"))
        .otherwise(pl.lit("Biyokimya"))
    )
    assert annotated.filter(pl.col("organ_sistemi").ne_missing(expected_system)).is_empty()
    assert set(annotated["organ_sistemi"]) == {"Hematoloji", "Biyokimya"}
    # The unit is the CSV unit (empty where it is empty).
    assert annotated.filter(pl.col("birim").ne_missing(pl.col("csv_unit"))).is_empty()
    # Numeric rows carry the sex-specific CSV limits; qualitative rows carry none.
    numeric = annotated.filter(pl.col("sonuc_nitel").is_null())
    strips = annotated.filter(pl.col("sonuc_nitel").is_not_null())
    assert numeric.filter(
        pl.col("ref_alt").ne_missing(pl.col("raw_lo")) | pl.col("ref_ust").ne_missing(pl.col("hi"))
    ).is_empty()
    assert strips.filter(
        pl.col("sonuc_sayisal").is_not_null()
        | pl.col("birim").ne_missing(pl.lit(""))
        | pl.col("ref_alt").is_not_null()
        | pl.col("ref_ust").is_not_null()
    ).is_empty()
    assert strips["sonuc_nitel"].is_in([*_ORDINAL, "Pozitif"]).all()


def _swap_two_hemogram_rows(lab: pl.DataFrame) -> pl.DataFrame:
    return _swap_rows(
        lab,
        _index_of(lab, 1, "L107020", "RBC (Eritrosit)"),
        _index_of(lab, 1, "L107020", "HGB (Hemoglobin)"),
    )


def _drop_a_middle_row(lab: pl.DataFrame) -> pl.DataFrame:
    return _drop_rows(lab, _index_of(lab, 1, "L107020", "MCV"))


def _drop_the_last_row_of_a_set(lab: pl.DataFrame) -> pl.DataFrame:
    return _drop_rows(lab, _index_of(lab, 1, "L107020", "MPV"))


def _repeat_a_row(lab: pl.DataFrame) -> pl.DataFrame:
    index = _index_of(lab, 1, "L107020", "MCV")
    return pl.concat([lab.slice(0, index + 1), lab.slice(index, 1), lab.slice(index + 1)])


def _add_an_unknown_parameter(lab: pl.DataFrame) -> pl.DataFrame:
    return pl.concat(
        [lab, lab.tail(1).with_columns(pl.lit("Bilinmeyen parametre").alias("parametre"))]
    )


def _move_a_row_to_another_code(lab: pl.DataFrame) -> pl.DataFrame:
    return _set_cell(lab, _index_of(lab, 1, "L101850", "CRP (kantitatif)"), "SUB_CODE", "L100300")


def _add_a_hemogram_row_to_the_crp_set(lab: pl.DataFrame) -> pl.DataFrame:
    """Patient 1's neutrophil count, copied in right after the CRP row: the CRP result set now holds two codes."""
    crp = _index_of(lab, 1, "L101850", "CRP (kantitatif)")
    neutrophils = _index_of(lab, 1, "L107020", "NEU# (Nötrofil)")
    return pl.concat([lab.slice(0, crp + 1), lab.slice(neutrophils, 1), lab.slice(crp + 1)])


# (mutation, rule, row it is reported at, code and parameter written in that row, end of the message).
# The row is the lowest one that breaks the rule, and the message names what the row holds.


def _wbc_row_of_patient_1(lab: pl.DataFrame) -> int:
    return _index_of(lab, 1, "L107020", "WBC (Lökosit)")


_STRUCTURE_CASES = [
    pytest.param(
        _swap_two_hemogram_rows,
        "result set",
        lambda lab: _index_of(lab, 1, "L107020", "RBC (Eritrosit)"),
        ("L107020", "HGB (Hemoglobin)"),
        "the parameter is number 6 of its result set but is number 7 in the CSV",
        id="swap_two_rows",
    ),
    pytest.param(
        _drop_a_middle_row,
        "result set",
        _wbc_row_of_patient_1,
        ("L107020", "WBC (Lökosit)"),
        "the result set has 14 rows but the CSV has 15 parameters for L107020",
        id="drop_a_row_inside_a_set",
    ),
    pytest.param(
        _drop_the_last_row_of_a_set,
        "result set",
        _wbc_row_of_patient_1,
        ("L107020", "WBC (Lökosit)"),
        "the result set has 14 rows but the CSV has 15 parameters for L107020",
        id="drop_the_last_row_of_a_set",
    ),
    pytest.param(
        _repeat_a_row,
        "result set",
        _wbc_row_of_patient_1,
        ("L107020", "WBC (Lökosit)"),
        "the result set has 16 rows but the CSV has 15 parameters for L107020",
        id="repeat_a_row",
    ),
    pytest.param(
        _add_a_hemogram_row_to_the_crp_set,
        "result set",
        lambda lab: _index_of(lab, 1, "L101850", "CRP (kantitatif)"),
        ("L101850", "CRP (kantitatif)"),
        "the result set mixes lab codes",
        id="two_codes_in_one_set",
    ),
    pytest.param(
        _add_an_unknown_parameter,
        "unknown parameter",
        lambda lab: lab.height,
        (None, "Bilinmeyen parametre"),
        "the parameter is not in lab_reference.csv",
        id="add_an_unknown_parameter",
    ),
    pytest.param(
        _move_a_row_to_another_code,
        "unknown parameter",
        lambda lab: _index_of(lab, 1, "L101850", "CRP (kantitatif)"),
        ("L100300", "CRP (kantitatif)"),
        "the parameter is not in lab_reference.csv",
        id="parameter_under_the_wrong_code",
    ),
]


@pytest.mark.parametrize(("mutate", "rule", "row_of", "written", "message"), _STRUCTURE_CASES)
def test_mutation_a_broken_result_set_names_the_rule_the_row_and_what_is_wrong(
    lab: pl.DataFrame,
    ana: pl.DataFrame,
    mutate: Callable[[pl.DataFrame], pl.DataFrame],
    rule: str,
    row_of: Callable[[pl.DataFrame], int],
    written: tuple[str | None, str],
    message: str,
) -> None:
    mutated = mutate(lab)
    row = row_of(lab)
    code = written[0] or lab["SUB_CODE"][-1]  # an added row copies the last one
    caught = _rejected(mutated, ana)
    _assert_names_the_row(caught, mutated, rule=rule, row=row, code=code, parameter=written[1])
    assert str(caught.value).endswith(message)


def _glucose_for_the_package_patient(lab: pl.DataFrame) -> pl.DataFrame:
    """A coherent one-row result set for patient 5, whose package bill has no billed lab line."""
    row = lab.filter(
        (pl.col("HASTA_ID") == _pid(7)) & (pl.col("SUB_CODE") == "L102890")
    ).with_columns(
        pl.lit(_pid(5)).alias("HASTA_ID"), pl.lit("B-SENTETIK-HASTA-0005-001").alias("basvuru_id")
    )
    assert row.height == 1
    return pl.concat([lab, row])


def _remove_a_whole_result_set(lab: pl.DataFrame) -> pl.DataFrame:
    return _drop_rows(lab, _index_of(lab, 1, "L101850", "CRP (kantitatif)"))


def _move_a_result_set_one_day(lab: pl.DataFrame) -> pl.DataFrame:
    return _set_cell(
        lab, _index_of(lab, 1, "L101850", "CRP (kantitatif)"), "tarih", datetime(2026, 7, 16)
    )


def _move_a_result_set_to_another_patient(lab: pl.DataFrame) -> pl.DataFrame:
    """Patient 1's CRP set under patient 2 and patient 2's episode (both men, so the limits agree)."""
    index = _index_of(lab, 1, "L101850", "CRP (kantitatif)")
    return _set_cell(
        _set_cell(lab, index, "HASTA_ID", _pid(2)), index, "basvuru_id", "B-SENTETIK-HASTA-0002-001"
    )


def _move_a_result_set_to_another_episode(lab: pl.DataFrame) -> pl.DataFrame:
    return _set_cell(
        lab,
        _index_of(lab, 1, "L101850", "CRP (kantitatif)"),
        "basvuru_id",
        "B-SENTETIK-HASTA-0007-001",
    )


@pytest.mark.parametrize(
    "mutate",
    [
        pytest.param(
            _glucose_for_the_package_patient,
            id="extra_row_for_an_episode_without_a_billed_lab_line",
        ),
        pytest.param(_remove_a_whole_result_set, id="missing_result_set"),
        pytest.param(_drop_a_middle_row, id="missing_row_inside_a_result_set"),
        pytest.param(_move_a_result_set_one_day, id="wrong_date"),
        pytest.param(_move_a_result_set_to_another_episode, id="wrong_episode"),
        pytest.param(_move_a_result_set_to_another_patient, id="wrong_patient_and_episode"),
    ],
)
def test_mutation_validate_clean_tables_rejects_rows_that_do_not_match_the_billed_lines(
    built_showcase: BuildResult, mutate: Callable[[pl.DataFrame], pl.DataFrame]
) -> None:
    clean = built_showcase.clean_tables
    validate_clean_tables(clean, built_showcase.tables)  # the untouched set is valid
    mutated = {**clean, "lab_clean.parquet": mutate(clean["lab_clean.parquet"])}
    with pytest.raises(CleanTableError, match=r"lab_clean"):
        validate_clean_tables(mutated, built_showcase.tables)


# --- 3.7 Generator errors from the clinical YAML ---------------------------------------------------


def _with_states(
    patient_no: int, add: dict[str, Any] | None = None, *, drop: tuple[str, ...] = ()
) -> ShowcaseClinical:
    """The real clinical document with `labs.states` of one patient changed (in memory only)."""
    base = load_clinical()
    patients: list[PatientClinical] = []
    for patient in base.patients:
        if (patient.patient_no, patient.encounter_no) == (patient_no, 1):  # the patient's first bill
            assert patient.labs is not None
            states = {k: v for k, v in patient.labs.states.items() if k not in drop}
            states.update(add or {})
            labs = patient.labs.model_copy(update={"states": states})
            patient = patient.model_copy(update={"labs": labs})
        patients.append(patient)
    return base.model_copy(update={"patients": patients})


def _without_blood_gas(patient_no: int, *, whole_block: bool) -> ShowcaseClinical:
    base = load_clinical()
    patients: list[PatientClinical] = []
    for patient in base.patients:
        if (patient.patient_no, patient.encounter_no) == (patient_no, 1):  # the patient's first bill
            assert patient.labs is not None
            labs: PatientLabs | None = (
                None if whole_block else patient.labs.model_copy(update={"blood_gas": None})
            )
            patient = patient.model_copy(update={"labs": labs})
        patients.append(patient)
    return base.model_copy(update={"patients": patients})


def _build(built_showcase: BuildResult, clinical: ShowcaseClinical) -> pl.DataFrame:
    return build_lab_clean(built_showcase.claims, clinical=clinical, schema=LAB_CLEAN_SCHEMA)


def test_the_committed_clinical_yaml_builds_the_committed_table(
    built_showcase: BuildResult, lab: pl.DataFrame
) -> None:
    assert _build(built_showcase, load_clinical()).equals(lab)


@pytest.mark.parametrize(
    ("patient_no", "key", "state"),
    [
        pytest.param(1, "L107020|RBC (Eritrosit)", "anemia", id="RBC"),
        pytest.param(1, "L107020|HCT (Hematokrit)", "anemia", id="HCT"),
        pytest.param(1, "L107020|MCHC", "iron_deficiency", id="MCHC"),
        pytest.param(1, "L107020|NEU# (Nötrofil)", "chemo_neutropenia", id="neutrophil_count"),
        pytest.param(1, "L107020|LYM# (Lenfosit)", "viral_lymphocytosis", id="lymphocyte_count"),
        pytest.param(
            1, "L107020|MONO# (Monosit)", "chronic_infection/recovery", id="monocyte_count"
        ),
        pytest.param(1, "L107020|EOS# (Eozinofil)", "parasitic", id="eosinophil_count"),
        pytest.param(2, "L103900|HCO3", "dka", id="HCO3"),
        pytest.param(2, "L103900|BE (baz fazlası)", "metabolic_acidosis", id="base_excess"),
        pytest.param(2, "L103900|SaO2", "hypoxemia", id="SaO2"),
        pytest.param(7, f"L104780|{_EGFR}", "ckd_g3a", id="eGFR"),
    ],
)
def test_mutation_a_state_on_a_derived_parameter_raises(
    built_showcase: BuildResult, patient_no: int, key: str, state: str
) -> None:
    clinical = _with_states(patient_no, {key: state})
    with pytest.raises(DerivedLabParameterError, match=re.escape(key.split("|", 1)[1])):
        _build(built_showcase, clinical)


@pytest.mark.parametrize(
    ("patient_no", "key", "state"),
    [
        pytest.param(
            1, "L107020|BASO# (Bazofil)", "rarely abnormal", id="prose_state_of_the_basophil_count"
        ),
        pytest.param(4, "L104780|Kreatinin", "aki", id="prose_state_of_the_creatinine"),
    ],
)
def test_mutation_an_unsupported_prose_state_raises_only_when_the_yaml_references_it(
    built_showcase: BuildResult, patient_no: int, key: str, state: str
) -> None:
    ref = load_lab_reference()
    spec = ref.by_key[key]
    assert state in spec.unsupported_by_id and state not in spec.states_by_id
    assert spec.has_state_in_csv(state)
    # Loading the reference and the committed YAML (which does not mention it) is fine.
    assert _build(built_showcase, load_clinical()).height == LAB_ROWS
    with pytest.raises(UnsupportedLabStateError, match=re.escape(state)):
        _build(built_showcase, _with_states(patient_no, {key: state}))
    with pytest.raises(UnsupportedLabStateError):
        spec.resolve_state(state)


def test_resolve_state_normal_is_none_and_an_unknown_state_is_an_error() -> None:
    spec = load_lab_reference().by_key["L101850|CRP (kantitatif)"]
    assert spec.resolve_state("normal") is None
    resolved = spec.resolve_state("bacterial_infection")
    assert isinstance(resolved, ParsedState) and (resolved.low, resolved.high) == (50.0, 250.0)
    with pytest.raises(LabReferenceError, match="unknown state 'nonexistent'"):
        spec.resolve_state("nonexistent")


def test_mutation_an_unknown_state_or_key_raises_a_reference_error(
    built_showcase: BuildResult,
) -> None:
    with pytest.raises(LabReferenceError, match="unknown state 'nonexistent'"):
        _build(built_showcase, _with_states(1, {"L101850|CRP (kantitatif)": "nonexistent"}))
    with pytest.raises(LabReferenceError, match="unknown lab state key 'L999999\\|Nope'"):
        _build(built_showcase, _with_states(1, {"L999999|Nope": "normal"}))


@pytest.mark.parametrize("whole_block", [False, True], ids=["blood_gas_missing", "no_labs_block"])
def test_mutation_a_billed_blood_gas_without_blood_gas_raises(
    built_showcase: BuildResult, whole_block: bool
) -> None:
    clinical = _without_blood_gas(2, whole_block=whole_block)
    with pytest.raises(LabCoherenceError, match=r"L103900.*blood_gas='arterial'"):
        _build(built_showcase, clinical)


def test_a_state_list_is_applied_per_occurrence_and_its_last_entry_repeats(
    built_showcase: BuildResult, lab: pl.DataFrame
) -> None:
    ph = "pH"
    first, second = "2026-03-09", "2026-03-12"
    # The committed list [copd_exacerbation, normal]: the first gas is acidotic, the second is not.
    assert _cell(lab, 2, first, "L103900", ph) < 7.35
    assert 7.35 <= _cell(lab, 2, second, "L103900", ph) <= 7.45
    # A list of length 1 repeats its only entry, so the second gas uses the first state too.
    one = _build(built_showcase, _with_states(2, {"L103900|pH": ["copd_exacerbation"]}))
    assert _cell(one, 2, first, "L103900", ph) == _cell(lab, 2, first, "L103900", ph)
    assert 7.25 <= _cell(one, 2, second, "L103900", ph) <= 7.34
    assert _cell(one, 2, second, "L103900", ph) != _cell(lab, 2, second, "L103900", ph)
    assert _cell(one, 2, second, "L103900", ph, "anormal_mi") is True
    # A scalar applies to every occurrence of the code.
    scalar = _build(
        built_showcase, _with_states(2, {"L101850|CRP (kantitatif)": "bacterial_infection"})
    )
    for day in (first, second):
        assert 50 <= _cell(scalar, 2, day, "L101850", "CRP (kantitatif)") <= 250
    # Only the keys named in the YAML change: every other row of patient 2 is the same.
    other = pl.col("parametre") != "pH"
    assert one.filter(
        (pl.col("HASTA_ID") == _pid(2)) & other & (pl.col("SUB_CODE") == "L100300")
    ).equals(
        lab.filter((pl.col("HASTA_ID") == _pid(2)) & other & (pl.col("SUB_CODE") == "L100300"))
    )


def test_occurrences_are_ordered_by_date_then_line_id_for_the_serial_troponin(
    built_showcase: BuildResult,
) -> None:
    """Patient 7 bills troponin I twice on one day: the list's first entry is the first line."""
    states = ["chronic_myocardial_injury", "normal"]
    table = _build(built_showcase, _with_states(7, {"L107360|hs-Troponin I": states}))
    first = _cell(table, 7, "2026-02-19", "L107360", "hs-Troponin I", nth=0)
    second = _cell(table, 7, "2026-02-19", "L107360", "hs-Troponin I", nth=1)
    assert 16.0 <= first <= 60.0  # the female range of chronic_myocardial_injury (M 35-80, F 16-60)
    assert 0.0 <= second <= 15.6
    assert _cell(table, 7, "2026-02-19", "L107360", "hs-Troponin I", "anormal_mi", nth=0) is True
    assert _cell(table, 7, "2026-02-19", "L107360", "hs-Troponin I", "anormal_mi", nth=1) is False
    # The two serial lines are the two last billed lines of the ER claim, in line-id order.
    lines = built_showcase.tables["procedure_claim_lines.parquet"].filter(
        (pl.col("claim_id") == cohort.role("showcase_S7").claim_id) & (pl.col("procedure_code") == "L107360")
    )
    assert lines["procedure_line_id"].to_list() == sorted(lines["procedure_line_id"].to_list())
    assert lines.height == 2


def test_a_state_of_the_wrong_sex_is_an_error(built_showcase: BuildResult) -> None:
    """`copd_polycythemia` of HGB has only a male range: asking for it for a woman is refused."""
    spec = load_lab_reference().by_key["L107020|HGB (Hemoglobin)"]
    state = spec.resolve_state("copd_polycythemia")
    assert isinstance(state, ParsedState) and state.sex_ranges == {"M": (17.6, 20.0)}
    clinical = _with_states(3, {"L107020|HGB (Hemoglobin)": "copd_polycythemia"})
    with pytest.raises(LabCoherenceError, match="no range for sex 'F'"):
        _build(built_showcase, clinical)


def test_mutation_a_state_for_a_lab_the_claim_does_not_bill_raises(
    built_showcase: BuildResult,
) -> None:
    """Patient 1 has no ALT line: a state for it would be ignored silently, so it is an error."""
    clinical = _with_states(1, {"L100300|ALT": "acute_hepatitis"})
    with pytest.raises(
        LabCoherenceError, match=r"'L100300\|ALT' is for L100300, which the claim does not bill"
    ):
        _build(built_showcase, clinical)


def test_mutation_a_state_list_longer_than_the_billed_lines_raises(
    built_showcase: BuildResult,
) -> None:
    """Patient 7 has one hemogram: a list of two states has an entry that no line can use."""
    clinical = _with_states(7, {"L107020|WBC (Lökosit)": ["bacterial_infection", "normal"]})
    with pytest.raises(
        LabCoherenceError,
        match=r"2 states for 'L107020\|WBC \(Lökosit\)', but the claim bills L107020 1 time",
    ):
        _build(built_showcase, clinical)
    # A list as long as the billed lines is fine, and so is a shorter one (its last entry repeats).
    _build(
        built_showcase,
        _with_states(2, {"L107020|WBC (Lökosit)": ["bacterial_infection", "normal"]}),
    )
    _build(built_showcase, _with_states(2, {"L107020|WBC (Lökosit)": ["bacterial_infection"]}))


# --- 3.8 Determinism and --check -------------------------------------------------------------------


def test_two_builds_give_the_same_lab_table_digest_and_registry(
    built_showcase: BuildResult,
) -> None:
    second = build_showcase()
    assert second.clean_tables["lab_clean.parquet"].equals(
        built_showcase.clean_tables["lab_clean.parquet"]
    )
    assert clean_tables_digest(second.clean_tables) == clean_tables_digest(
        built_showcase.clean_tables
    )
    assert second.registry == built_showcase.registry
    assert second == built_showcase


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


def test_two_cli_builds_write_the_same_lab_bytes_and_the_committed_file_the_same_content(
    tmp_path: Path,
) -> None:
    assert main(["--out", str(tmp_path / "a")]) == 0
    assert main(["--out", str(tmp_path / "b")]) == 0
    a_path = tmp_path / "a" / "sut" / "clean" / "lab_clean.parquet"
    b_path = tmp_path / "b" / "sut" / "clean" / "lab_clean.parquet"
    # Two fresh builds in one environment write the same bytes. The committed file was written by another
    # Polars version, whose writer may lay the same table out in other bytes, so it is compared by content.
    assert a_path.read_bytes() == b_path.read_bytes()
    fresh, committed = pl.read_parquet(a_path), pl.read_parquet(_LAB_PARQUET)
    assert dict(fresh.schema) == dict(committed.schema)
    assert fresh.sort(fresh.columns).equals(committed.sort(committed.columns), null_equal=True)


def test_mutation_check_exits_1_when_a_lab_value_or_the_lab_count_changes(
    built_showcase: BuildResult,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    lab: pl.DataFrame,
) -> None:
    copy_dir = tmp_path / "dataset_copy"
    write_showcase(built_showcase, copy_dir)
    assert main(["--out", str(copy_dir), "--check"]) == 0
    capsys.readouterr()

    # (a) one value of lab_clean
    lab_path = copy_dir / "sut" / "clean" / "lab_clean.parquet"
    index = _index_of(lab, 2, "L100300", "ALT")
    _set_cell(lab, index, "sonuc_sayisal", 17.0).write_parquet(lab_path)
    assert main(["--out", str(copy_dir), "--check"]) == 1
    assert "lab_clean.parquet" in capsys.readouterr().err
    lab.write_parquet(lab_path)
    assert main(["--out", str(copy_dir), "--check"]) == 0
    capsys.readouterr()

    # (b) the lab count in the registry, then its digest
    registry_path = copy_dir / "cohort_registry.json"
    original = registry_path.read_text(encoding="utf-8")
    for field, bad in (("clean_counts", 206), ("clean_tables_digest", "0" * 64)):
        registry = json.loads(original)
        registry[field]["lab_clean.parquet"] = bad
        registry_path.write_text(
            json.dumps(registry, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        assert main(["--out", str(copy_dir), "--check"]) == 1, field
        assert "cohort_registry.json" in capsys.readouterr().err
    registry_path.write_text(original, encoding="utf-8")
    assert main(["--out", str(copy_dir), "--check"]) == 0


# --- 3.9 Loaders and engine ------------------------------------------------------------------------


def test_cache_loaders_accept_the_lab_table(built_showcase: BuildResult) -> None:
    raw = load_labdata(_LAB_PARQUET)
    assert raw.height == LAB_ROWS
    _, lab_df, _ = load_normalized_raw_data(
        load_anadata_fn=lambda include_text=True: load_anadata(
            path=_CLEAN_DIR / "anadata_clean.parquet", include_text=include_text
        ),
        load_labdata_fn=lambda: load_labdata(path=_LAB_PARQUET),
        load_recete_fn=lambda: load_recete(path=_CLEAN_DIR / "recete_clean.parquet"),
    )
    assert lab_df.height == LAB_ROWS
    assert lab_df.columns == [
        "patient_id",
        "visit_id",
        "date",
        "test_name",
        "value",
        "ref_min",
        "ref_max",
    ]
    # test_name is the lower-cased L-code, visit_id the claim's episode, and only strips lack a value.
    assert set(lab_df["test_name"]) == {code.lower() for code in _PARAMETER_COUNTS}
    episodes = set(built_showcase.tables["claim_headers.parquet"]["episode_id"])
    assert set(lab_df["visit_id"]) <= episodes
    assert lab_df["value"].null_count() == 12


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


# --- 3.10 Hygiene ----------------------------------------------------------------------------------


def _strings(node: Any) -> list[str]:
    if isinstance(node, str):
        return [node]
    if isinstance(node, dict):
        return [s for k, v in node.items() for s in (*_strings(k), *_strings(v))]
    if isinstance(node, list):
        return [s for v in node for s in _strings(v)]
    return []


def test_the_new_yaml_blocks_and_the_lab_table_carry_no_anon_or_currency_text(
    lab: pl.DataFrame, clinical_raw: dict[str, Any]
) -> None:
    text = CLINICAL_PATH.read_text(encoding="utf-8")
    assert hygiene(clinical_raw, text) == []
    blocks = {
        "drug_routes": clinical_raw["drug_routes"],
        "labs": [p["labs"] for p in clinical_raw["patients"] if "labs" in p],
    }
    for name, block in blocks.items():
        for string in _strings(block):
            assert not _ANON_RE.search(string), (name, string)
            assert not _CURRENCY_RE.search(string), (name, string)
    assert not _ANON_RE.search(text) and not _CURRENCY_RE.search(text)
    for column, dtype in lab.schema.items():
        if dtype == pl.String:
            for value in lab[column].drop_nulls().unique().to_list():
                assert not _ANON_RE.search(value), (column, value)
                assert not _CURRENCY_RE.search(value), (column, value)
    # The identifiers are the synthetic ones.
    assert all(PATIENT_ID_RE.fullmatch(v) for v in lab["HASTA_ID"].unique().to_list())


# --- 3.11 The vectorised check: what it reports, how tight it is, and the shared formulas -----------


def test_the_error_names_the_rule_the_row_the_patient_the_code_and_the_parameter(
    lab: pl.DataFrame, ana: pl.DataFrame
) -> None:
    index = _index_of(lab, 1, "L101850", "CRP (kantitatif)")
    flag_flipped = _set_cell(lab, index, "anormal_mi", False)
    with pytest.raises(LabCoherenceError) as caught:
        check_lab_coherence(flag_flipped, ana_df=ana)
    assert str(caught.value).startswith(
        f"lab_clean R5 at row {index} (SENTETIK-HASTA-0001 L101850|CRP (kantitatif)): "
    )
    # A derived rule names the derived parameter's own row, not the first row of its set.
    rbc = _index_of(lab, 2, "L107020", "RBC (Eritrosit)", date="2026-03-09")
    rbc_changed = _set_cell(lab, rbc, "sonuc_sayisal", lab["sonuc_sayisal"][rbc] + 0.2)
    with pytest.raises(LabCoherenceError) as caught:
        check_lab_coherence(rbc_changed, ana_df=ana)
    assert str(caught.value).startswith(
        f"lab_clean R2 at row {rbc} (SENTETIK-HASTA-0002 L107020|RBC (Eritrosit)): RBC "
    )


def test_the_lowest_offending_row_is_the_one_reported(lab: pl.DataFrame, ana: pl.DataFrame) -> None:
    later = _index_of(lab, 4, "L107010", "Nitrit (strip)")
    earlier = _index_of(lab, 1, "L101850", "CRP (kantitatif)")
    assert earlier < later
    both = _set_cell(_set_cell(lab, later, "anormal_mi", False), earlier, "anormal_mi", False)
    with pytest.raises(LabCoherenceError, match=rf"R5 at row {earlier} "):
        check_lab_coherence(both, ana_df=ana)
    # Several rules on one row: the finite value is reported before the flag that goes with it.
    index = _index_of(lab, 2, "L102890", "Glukoz")
    nan_value = _set_cell(lab, index, "sonuc_sayisal", float("nan"))
    with pytest.raises(LabCoherenceError, match=rf"finite at row {index} "):
        check_lab_coherence(nan_value, ana_df=ana)


def test_a_structure_error_is_reported_before_a_row_error(
    lab: pl.DataFrame, ana: pl.DataFrame
) -> None:
    """The stages run in order: unknown parameters, result sets, rows, derived values."""
    flipped = _set_cell(lab, _index_of(lab, 1, "L101850", "CRP (kantitatif)"), "anormal_mi", False)
    broken = _drop_rows(flipped, _index_of(flipped, 4, "L107010", "pH"))
    with pytest.raises(LabCoherenceError, match=r"result set at row "):
        check_lab_coherence(broken, ana_df=ana)
    with pytest.raises(LabCoherenceError, match=r"R5 at row "):
        check_lab_coherence(flipped, ana_df=ana)


def test_mutation_the_limits_must_be_the_sex_specific_ones_of_the_csv(
    lab: pl.DataFrame, ana: pl.DataFrame
) -> None:
    index = _index_of(lab, 7, "L107360", "hs-Troponin I", nth=0)
    male_limit = _set_cell(lab, index, "ref_ust", 34.2)  # the value 4.9 stays normal either way
    caught = _rejected(male_limit, ana)
    _assert_names_the_row(
        caught, lab, rule="R5", row=index, code="L107360", parameter="hs-Troponin I"
    )
    assert str(caught.value).endswith(
        "the limits [0.0, 34.2] are not the sex-specific limits [0.0, 15.6] of the CSV"
    )
    check_lab_coherence(male_limit)  # without the age and sex of the episode this cannot be seen
    potassium = _index_of(lab, 7, "L106150", "Potasyum")
    caught = _rejected(_set_cell(lab, potassium, "ref_alt", 3.4), ana)
    _assert_names_the_row(
        caught, lab, rule="R5", row=potassium, code="L106150", parameter="Potasyum"
    )
    assert str(caught.value).endswith(
        "the limits [3.4, 5.1] are not the sex-specific limits [3.5, 5.1] of the CSV"
    )
    # An episode without an anadata row has no sex: its limits cannot be checked, so it is an error.
    other_episodes = ana.filter(pl.col("SQ_EPISODE") != "B-SENTETIK-HASTA-0001-001")
    first = _first_row_of(lab, 1)
    caught = _rejected(lab, other_episodes)
    _assert_names_the_row(
        caught,
        lab,
        rule="R5",
        row=first,
        code=lab["SUB_CODE"][first],
        parameter=lab["parametre"][first],
    )
    assert str(caught.value).endswith(
        "no anadata row for the episode: the sex-specific limits cannot be checked"
    )


def test_mutation_the_unit_must_be_the_csv_unit(lab: pl.DataFrame, ana: pl.DataFrame) -> None:
    index = _index_of(lab, 2, "L102890", "Glukoz")
    caught = _rejected(_set_cell(lab, index, "birim", "mmol/L"), ana)
    _assert_names_the_row(caught, lab, rule="R6", row=index, code="L102890", parameter="Glukoz")
    assert str(caught.value).endswith("unit mmol/L differs from the CSV unit mg/dL")
    ph = _index_of(lab, 2, "L103900", "pH", date="2026-03-09")  # the blood-gas pH has no unit
    caught = _rejected(_set_cell(lab, ph, "birim", "mmHg"), ana)
    _assert_names_the_row(caught, lab, rule="R6", row=ph, code="L103900", parameter="pH")
    assert str(caught.value).endswith("unit mmHg differs from the CSV unit ")


def test_mutation_one_result_set_cannot_mix_patients_episodes_or_dates(
    lab: pl.DataFrame, ana: pl.DataFrame
) -> None:
    """The set is reported at its first row, the WBC; the changed row is inside it."""
    index = _index_of(lab, 2, "L107020", "MCV", date="2026-03-09")
    first = _index_of(lab, 2, "L107020", "WBC (Lökosit)", date="2026-03-09")
    for column, value in (
        ("tarih", datetime(2026, 3, 10)),
        ("basvuru_id", "B-SENTETIK-HASTA-0007-001"),
        ("HASTA_ID", _pid(7)),
    ):
        caught = _rejected(_set_cell(lab, index, column, value), ana)
        _assert_names_the_row(
            caught, lab, rule="result set", row=first, code="L107020", parameter="WBC (Lökosit)"
        )
        assert str(caught.value).endswith("the result set mixes patients, episodes or dates")


def test_the_scalar_formulas_and_their_polars_expressions_agree() -> None:
    """The generator uses the float functions, the check the expressions: same numbers."""
    grid = pl.DataFrame(
        {
            "scr": [0.45, 0.6, 0.7, 0.74, 0.9, 1.03, 1.11, 1.5, 2.4, 4.0],
            "age": [18, 34, 58, 77, 79, 81, 86, 95, 60, 45],
            "female": [True, False, True, True, False, False, True, False, True, False],
        }
    )
    expression = grid.select(
        ckd_epi_2021_expr(pl.col("scr"), pl.col("age"), pl.col("female")).alias("egfr")
    )["egfr"].to_list()
    scalar = [
        ckd_epi_2021(scr, age, "F" if female else "M")
        for scr, age, female in zip(grid["scr"], grid["age"], grid["female"], strict=True)
    ]
    assert expression == pytest.approx(scalar, rel=1e-12)
    # Blood gas: the expression form of the formulas is the scalar form with Polars operands.
    gas = pl.DataFrame(
        {
            "ph": [7.25, 7.3, 7.41, 7.5],
            "pco2": [30.0, 58.0, 40.0, 25.0],
            "po2": [45.0, 56.0, 66.0, 95.0],
        }
    )
    hco3 = gas.select(_hco3(pl.col("ph"), pl.col("pco2")).alias("v"))["v"].to_list()
    sao2 = gas.select(_sao2(pl.col("po2")).alias("v"))["v"].to_list()
    assert hco3 == pytest.approx([_hco3(p, c) for p, c in zip(gas["ph"], gas["pco2"], strict=True)])
    assert sao2 == pytest.approx([_sao2(o) for o in gas["po2"]])
    assert round(_hco3(7.30, 58.0), 1) == henderson_hasselbalch_hco3(7.30, 58.0) == 28.2
    assert base_excess_from_ph_hco3(7.30, 28.2) == 2.2
    assert severinghaus_sao2(56.0) == 88.7


def test_the_formulas_reproduce_textbook_values() -> None:
    """Published values, so a changed constant cannot hide behind the one-decimal rounding of the data."""
    # Severinghaus: the half-saturation pressure of haemoglobin is about 27 mmHg.
    assert [severinghaus_sao2(p) for p in (27.0, 40.0, 60.0, 100.0)] == [50.4, 74.9, 90.6, 97.7]
    # Henderson-Hasselbalch: pH 7.40 with pCO2 40 mmHg is a bicarbonate of 24.5 mmol/L.
    assert henderson_hasselbalch_hco3(7.40, 40.0) == 24.5
    assert henderson_hasselbalch_hco3(7.10, 20.0) == 6.1
    # The base excess is 0 at pH 7.40 and a standard bicarbonate of 24.4 mmol/L.
    assert base_excess_from_ph_hco3(7.40, 24.4) == 0.0
    assert base_excess_from_ph_hco3(7.30, 18.0) == -7.3
    # CKD-EPI 2021, race-free: a 60-year-old with a creatinine of 1.0 mg/dL (Inker 2021).
    assert round(ckd_epi_2021(1.0, 60, "F")) == 64
    assert round(ckd_epi_2021(1.0, 60, "M")) == 86
    assert ckd_epi_2021(0.9, 40, "M") == pytest.approx(142 * 0.9938**40)


def test_the_parameter_table_is_the_reference_as_a_frame() -> None:
    table = load_lab_reference().parameter_table
    assert table.columns == [
        "SUB_CODE",
        "parametre",
        "csv_unit",
        "is_strip",
        "ref_low_male",
        "ref_high_male",
        "ref_low_female",
        "ref_high_female",
        "organ",
        "decimals",
        "position",
        "n_params",
    ]
    assert table.height == 87  # 97 CSV rows minus the 10 of the venous blood gas
    # The organ system of the generator: haematology for the hemogram, the manual haematocrit and the D-dimer, biochemistry for
    # every other test of the reference, the 35 codes that are not billed here included.
    organs = table.group_by("organ").agg(pl.col("SUB_CODE").unique().sort()).sort("organ")
    assert organs["organ"].to_list() == ["Biyokimya", "Hematoloji"]
    assert organs.filter(pl.col("organ") == "Hematoloji")["SUB_CODE"][0].to_list() == [
        "L102090",
        "L103120",
        "L107020",
    ]
    assert organs.filter(pl.col("organ") == "Biyokimya")["SUB_CODE"][0].len() == 47
    # The printed decimals: the ones of the CSV, except the eight values that rules R1 and R4 fix.
    keys = table.select(pl.concat_str("SUB_CODE", "parametre", separator="|").alias("key"))["key"]
    printed = dict(zip(keys, table["decimals"], strict=True))
    assert {key: printed[key] for key in _DECIMALS} == {**_DECIMALS, **_FIXED_DECIMALS}
    assert table.filter(pl.col("SUB_CODE") == "L107020")["position"].to_list() == list(range(15))
    sizes = table.group_by("SUB_CODE").agg(pl.col("n_params").unique()).sort("SUB_CODE")
    assert all(len(v) == 1 for v in sizes["n_params"])
    counts = dict(zip(sizes["SUB_CODE"], sizes["n_params"].list.first(), strict=True))
    assert {c: counts[c] for c in _PARAMETER_COUNTS} == _PARAMETER_COUNTS
    assert table.filter(pl.col("is_strip"))["parametre"].to_list() == [
        "Protein (strip)",
        "Glukoz (strip)",
        "Keton (strip)",
        "Kan / hemoglobin (strip)",
        "Lökosit esteraz (strip)",
        "Nitrit (strip)",
    ]
    assert load_lab_reference().position_of("L104780", _EGFR) == 1


def test_expected_lab_keys_is_the_billed_lines_times_the_parameters(
    procs: pl.DataFrame, lab: pl.DataFrame
) -> None:
    keys = expected_lab_keys(procs)
    assert keys.columns == ["HASTA_ID", "basvuru_id", "day", "SUB_CODE", "parametre"]
    assert keys.height == LAB_ROWS
    assert keys.equals(
        lab.select("HASTA_ID", "basvuru_id", _day().alias("day"), "SUB_CODE", "parametre")
    )
    unknown = (
        procs.filter(pl.col("procedure_category") == "laboratuvar")
        .head(1)
        .with_columns(pl.lit("L999999").alias("procedure_code"))
    )
    with pytest.raises(LabReferenceError, match="unknown lab code 'L999999'"):
        expected_lab_keys(pl.concat([procs, unknown]))
    assert expected_lab_keys(procs.filter(pl.col("procedure_category") != "laboratuvar")).is_empty()


def _put_the_crp_set_after_the_hemogram(lab: pl.DataFrame) -> pl.DataFrame:
    crp = _index_of(lab, 1, "L101850", "CRP (kantitatif)")
    return pl.concat(
        [lab.slice(0, crp), lab.slice(crp + 1, 15), lab.slice(crp, 1), lab.slice(crp + 16)]
    )


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        pytest.param(
            _glucose_for_the_package_patient,
            rf"{LAB_ROWS + 1} rows for {LAB_ROWS} expected; 1 unexpected, first SENTETIK-HASTA-0005 B-SENTETIK-HASTA-0005-001 2026-02-19 L102890\|Glukoz",
            id="extra_row",
        ),
        pytest.param(
            _remove_a_whole_result_set,
            rf"{LAB_ROWS - 1} rows for {LAB_ROWS} expected; 1 missing, first SENTETIK-HASTA-0001 B-SENTETIK-HASTA-0001-001 2026-07-15 L101850\|CRP \(kantitatif\)",
            id="missing_result_set",
        ),
        pytest.param(
            _move_a_result_set_one_day,
            r"1 missing, first .* 2026-07-15 L101850.*1 unexpected, first .* 2026-07-16 L101850",
            id="wrong_date",
        ),
        pytest.param(
            _move_a_result_set_to_another_patient,
            r"1 missing, first SENTETIK-HASTA-0001 B-SENTETIK-HASTA-0001-001 .*1 unexpected, first SENTETIK-HASTA-0002 B-SENTETIK-HASTA-0002-001",
            id="wrong_patient_and_episode",
        ),
        pytest.param(
            _put_the_crp_set_after_the_hemogram,
            rf"{LAB_ROWS} rows for {LAB_ROWS} expected; the rows are in a different order",
            id="same_rows_in_another_order",
        ),
    ],
)
def test_mutation_the_mismatch_message_says_what_is_missing_unexpected_or_out_of_order(
    built_showcase: BuildResult, mutate: Callable[[pl.DataFrame], pl.DataFrame], message: str
) -> None:
    clean = built_showcase.clean_tables
    mutated = {**clean, "lab_clean.parquet": mutate(clean["lab_clean.parquet"])}
    with pytest.raises(
        CleanTableError,
        match=r"lab_clean\.parquet rows do not match the billed lab lines .*" + message,
    ):
        validate_clean_tables(mutated, built_showcase.tables)


def test_mutation_two_copies_of_one_key_are_counted_not_merged(built_showcase: BuildResult) -> None:
    """Patient 7's two troponin I result sets have the same key: losing one of them is seen."""
    clean = built_showcase.clean_tables
    lab = clean["lab_clean.parquet"]
    second = _index_of(lab, 7, "L107360", "hs-Troponin I", nth=1)
    mutated = {**clean, "lab_clean.parquet": _drop_rows(lab, second)}
    with pytest.raises(
        CleanTableError,
        match=rf"{LAB_ROWS - 1} rows for {LAB_ROWS} expected; 1 missing, first .* L107360\|hs-Troponin I",
    ):
        validate_clean_tables(mutated, built_showcase.tables)
    duplicated = pl.concat([lab, lab.slice(second, 1)])
    with pytest.raises(CleanTableError, match=r"1 unexpected"):
        validate_clean_tables({**clean, "lab_clean.parquet": duplicated}, built_showcase.tables)


def test_the_readme_describes_the_rules_the_code_implements() -> None:
    readme = (_OUT_DIR / "README.md").read_text(encoding="utf-8")
    # The killed run wrote the HCT, the base excess and the saturation wrongly.
    for wrong in ("HGB × 3", "Van Slyke", "sO2"):
        assert wrong not in readme, wrong
    for right in (
        "HCT = MCV·RBC/10",
        "RBC = HGB·10/MCH",
        "MCHC = HGB/HCT·100",
        "CKD-EPI 2021",
        "0.0307·pCO2·10^(pH−6.1)",
        "0.93·(HCO3−24.4+14.8·(pH−7.4))",
        "Severinghaus",
        "SHA-256",
        "issue #309",
        "no automatic trend",
        "Patients 13 and 14 have none because their bills are packages",
        "patient 8 only the CRP of her ER visit (S49",
        "cultures and serology are not L-codes",
    ):
        assert right in readme, right
    assert "`verilis_yolu`" in readme and "`drug_routes`" in readme


# --- 3.12 Branches: what the reader and the generator refuse ---------------------------------------


def _raw_csv() -> pl.DataFrame:
    return pl.read_csv(_LAB_CSV, infer_schema_length=0)


def _edit_cell(raw: pl.DataFrame, key: str, column: str, value: str) -> pl.DataFrame:
    """`raw` with one cell of the (non-venous) row `key` = `code|parameter` replaced."""
    code, parameter = key.split("|", 1)
    is_row = (
        (pl.col("ek2b_code") == code)
        & (pl.col("result_parameter") == parameter)
        & (pl.col("test_key") != "blood_gas_venous")
    )
    return raw.with_columns(
        pl.when(is_row).then(pl.lit(value)).otherwise(pl.col(column)).alias(column)
    )


def test_the_reader_accepts_the_csv_as_it_is_and_gives_the_same_reference() -> None:
    again = load_lab_reference_df(_raw_csv())
    assert [s.key for s in again.all_parameters] == [
        s.key for s in load_lab_reference().all_parameters
    ]
    assert again.by_code.keys() == load_lab_reference().by_code.keys()


@pytest.mark.parametrize(
    ("edit", "message"),
    [
        pytest.param(
            lambda raw: _edit_cell(raw, "L100300|ALT", "ref_high_male", "abc"),
            r"invalid numeric limit in lab_reference.csv",
            id="limit_is_not_a_number",
        ),
        pytest.param(
            lambda raw: _edit_cell(raw, "L100300|ALT", "abnormal_states", "acute_hepatitis: 300–"),
            r"L100300\|ALT.*unrecognized range syntax",
            id="billed_code_with_a_broken_state",
        ),
        pytest.param(
            lambda raw: raw.filter(pl.col("ek2b_code") != "L100300"),
            r"Missing billed lab codes in reference: \['L100300'\]",
            id="a_billed_code_is_gone",
        ),
        pytest.param(
            lambda raw: raw.filter(pl.col("result_parameter") != _EGFR),
            r"Missing eGFR age bands row",
            id="the_egfr_row_is_gone",
        ),
        pytest.param(
            lambda raw: _edit_cell(raw, f"L104780|{_EGFR}", "normal_value_range", "by age"),
            r"cannot parse eGFR age bands",
            id="the_egfr_bands_are_unreadable",
        ),
    ],
)
def test_mutation_a_broken_reference_csv_is_refused(
    edit: Callable[[pl.DataFrame], pl.DataFrame], message: str
) -> None:
    with pytest.raises(LabReferenceError, match=message):
        load_lab_reference_df(edit(_raw_csv()))


def test_a_broken_state_of_an_unbilled_code_is_kept_as_one_unsupported_state() -> None:
    """Only the 14 billed codes are parsed strictly; another code with prose it cannot read is listed."""
    ferritin = load_lab_reference().by_key["L102410|Ferritin"]
    assert ferritin.parsed_states == ()
    assert [u.raw_text for u in ferritin.unsupported_states] == [ferritin.abnormal_states_raw]
    assert ferritin.has_state_in_csv(ferritin.abnormal_states_raw)


def test_spec_helpers_refuse_what_they_cannot_serve() -> None:
    ref = load_lab_reference()
    egfr = ref.by_key[f"L104780|{_EGFR}"]
    with pytest.raises(LabReferenceError, match="missing upper reference limit"):
        egfr.normal_draw_limits("M")
    assert egfr.ref_limits("F") == (60.0, None)
    with pytest.raises(LabReferenceError, match="Unsupported sex 'X'"):
        egfr.ref_limits("X")
    crp = ref.by_key["L101850|CRP (kantitatif)"]
    assert crp.has_state_in_csv("normal") and crp.has_state_in_csv("bacterial_infection")
    assert not crp.has_state_in_csv("nonexistent")
    # A numeric draw needs a numeric state and a strip draw needs a grade.
    protein = ref.by_key["L107010|Protein (strip)"]
    with pytest.raises(LabCoherenceError, match="has no numeric range"):
        draw_numeric_value(protein, patient_id=_pid(4), sex="F", k=1, state_id="fever_or_uti")
    with pytest.raises(LabCoherenceError, match="expected strip grade state"):
        draw_strip_grade(crp, patient_id=_pid(4), k=1, state_id="bacterial_infection")
    assert draw_strip_grade(protein, patient_id=_pid(4), k=1) == "Negatif"
    assert draw_strip_grade(protein, patient_id=_pid(4), k=1, state_id="fever_or_uti") == "Eser"


def test_invert_ckd_epi_2021_is_the_inverse_of_ckd_epi_2021_in_both_branches() -> None:
    for sex in ("M", "F"):
        for age in (18, 34, 58, 77, 95):
            for egfr in (8.0, 29.0, 52.0, 77.0, 94.0, 110.0, 125.0):
                scr = invert_ckd_epi_2021(egfr, age, sex)
                assert ckd_epi_2021(scr, age, sex) == pytest.approx(egfr, rel=1e-9), (
                    sex,
                    age,
                    egfr,
                )


def test_state_for_occurrence_repeats_the_last_entry_and_defaults_to_normal() -> None:
    states = {"scalar": "a", "pair": ["a", "b"], "empty": []}
    assert [_state_for_occurrence(states, "scalar", k) for k in (1, 2, 3)] == ["a", "a", "a"]
    assert [_state_for_occurrence(states, "pair", k) for k in (1, 2, 3)] == ["a", "b", "b"]
    assert _state_for_occurrence(states, "empty", 1) == "normal"
    assert _state_for_occurrence(states, "absent", 1) == "normal"


def test_a_derived_red_cell_value_may_sit_in_a_state_range_of_its_own_sex() -> None:
    rbc = load_lab_reference().by_key["L107020|RBC (Eritrosit)"]
    assert _value_in_own_state_ranges(rbc, 3.5, "F")  # anemia, F 2.8 to 3.9
    assert _value_in_own_state_ranges(rbc, 2.9, "F")
    assert not _value_in_own_state_ranges(rbc, 2.9, "M")  # anemia, M 3.0 to 4.4
    assert _value_in_own_state_ranges(rbc, 6.7, "M")  # polycythemia, M 6.0 to 6.8
    assert not _value_in_own_state_ranges(rbc, 6.7, "F")  # that state has no female range
    assert not _value_in_own_state_ranges(rbc, 9.0, "M")


def test_mutation_red_cell_indices_that_cannot_agree_raise_after_50_tries(
    built_showcase: BuildResult,
) -> None:
    """A polycythemic HGB with an iron-deficient MCH gives an RBC that no band holds (RBC fails)."""
    states = {"L107020|HGB (Hemoglobin)": "copd_polycythemia", "L107020|MCH": "iron_deficiency"}
    with pytest.raises(
        LabCoherenceError,
        match=r"L107020 RBC \(Eritrosit\): red-cell indices failed to converge in 50 tries",
    ):
        _build(built_showcase, _with_states(6, states))
    # A macrocytic MCV gives an HCT that a woman's bands do not hold (RBC passes, HCT fails).
    with pytest.raises(
        LabCoherenceError,
        match=r"L107020 HCT \(Hematokrit\): red-cell indices failed to converge in 50 tries",
    ):
        _build(built_showcase, _with_states(4, {"L107020|MCV": "b12_or_folate_deficiency"}))
    # The same state for a man still finds a draw whose HCT sits in his hemoconcentration range.
    _build(built_showcase, _with_states(6, {"L107020|MCV": "b12_or_folate_deficiency"}))


def test_a_creatinine_state_that_is_not_an_egfr_band_is_drawn_as_a_creatinine(
    built_showcase: BuildResult, ana: pl.DataFrame
) -> None:
    """`sarcopenic_elderly` is a creatinine range (0.40 to 0.60); the eGFR follows from it."""
    table = _build(built_showcase, _with_states(7, {"L104780|Kreatinin": "sarcopenic_elderly"}))
    scr = _cell(table, 7, "2026-02-19", "L104780", "Kreatinin")
    assert 0.40 <= scr <= 0.60
    assert _cell(table, 7, "2026-02-19", "L104780", "Kreatinin", "anormal_mi") is True  # below 0.51
    check_lab_coherence(table, ana_df=ana)  # and the eGFR is the CKD-EPI value of that creatinine


def test_a_normal_creatinine_that_no_band_allows_raises_after_50_tries() -> None:
    specs = load_lab_reference().by_code["L104780"]
    # An eGFR band of 20 to 30 needs a creatinine far above the female limit of 0.95 mg/dL.
    with pytest.raises(
        LabCoherenceError, match="normal draw outside sex-specific limits after 50 tries"
    ):
        _generate_creatinine_and_egfr(
            specs,
            patient_id=_pid(3),
            age=77,
            sex="F",
            k=1,
            states_map={},
            egfr_age_bands=((18, 200, 20.0, 30.0),),
        )
    with pytest.raises(LabCoherenceError, match="No normal eGFR age band for age 10"):
        _egfr_normal_band_for_age(10, load_lab_reference().egfr_age_bands)


def test_the_generator_takes_the_clinical_document_in_every_form(
    built_showcase: BuildResult, lab: pl.DataFrame
) -> None:
    document = load_clinical()
    forms = {
        "none (read from the file)": None,
        "document": document,
        "sequence of patients": list(document.patients),
        "mapping of encounters": {(p.patient_no, p.encounter_no): p for p in document.patients},
        "mapping of lab blocks": {(p.patient_no, p.encounter_no): p.labs for p in document.patients},
        # keyed by the patient number alone, a mapping names the patient's first encounter
        "mapping of patient numbers": {p.patient_no: p for p in document.patients if p.encounter_no == 1},
        "mapping of lab blocks by patient number": {
            p.patient_no: p.labs for p in document.patients if p.encounter_no == 1
        },
    }
    # A mapping keyed by the patient number alone names the patient's first encounter only, so it can hold the
    # first bills of the cohort (the control of patient 4 has an entry of its own): those are what it builds.
    first_bills = [c for c in built_showcase.claims if c.header.claim_id.endswith("-001")]
    first_rows = lab.filter(pl.col("basvuru_id").str.ends_with("-001"))
    by_patient_number = {"mapping of patient numbers", "mapping of lab blocks by patient number"}
    for name, clinical in forms.items():
        claims, expected = (first_bills, first_rows) if name in by_patient_number else (built_showcase.claims, lab)
        built = build_lab_clean(claims, clinical=clinical, schema=LAB_CLEAN_SCHEMA)
        assert built.equals(expected), name
    # keyed by the patient number alone, the control of patient 4 would be drawn with the stay's states: not the table
    wrongly = build_lab_clean(
        built_showcase.claims, clinical=forms["mapping of patient numbers"], schema=LAB_CLEAN_SCHEMA
    )
    assert not wrongly.equals(lab)
    # Without lab blocks a billed blood gas has no `blood_gas` and the build says so.
    with pytest.raises(LabCoherenceError, match="blood_gas"):
        build_lab_clean(built_showcase.claims, clinical={}, schema=LAB_CLEAN_SCHEMA)


def test_the_generator_refuses_a_bad_patient_id_or_a_lab_code_the_csv_lacks(
    built_showcase: BuildResult,
) -> None:
    with pytest.raises(LabReferenceError, match="Invalid patient_id format 'ANON'"):
        _patient_no("ANON")
    assert _encounter_no("F-SENTETIK-HASTA-0004-002") == 2
    with pytest.raises(LabReferenceError, match="invalid claim_id 'X-1'"):
        _encounter_no("X-1")  # a claim whose sequence cannot be read is a reader error, not a bare ValueError
    claim = next(
        c for c in built_showcase.claims if any(p.procedure_category == "laboratuvar" for p in c.procedures)
    )
    lab_index = next(
        i for i, line in enumerate(claim.procedures) if line.procedure_category == "laboratuvar"
    )
    procedures = list(claim.procedures)
    procedures[lab_index] = dataclasses.replace(procedures[lab_index], procedure_code="L999999")
    broken = dataclasses.replace(claim, procedures=tuple(procedures))
    with pytest.raises(LabReferenceError, match=r"lab code 'L999999' not in lab_reference.csv"):
        build_lab_clean([broken], clinical=load_clinical(), schema=LAB_CLEAN_SCHEMA)


def test_a_table_with_no_derived_result_set_is_coherent(
    lab: pl.DataFrame, ana: pl.DataFrame
) -> None:
    only_alt = lab.filter(pl.col("SUB_CODE") == "L100300")
    assert only_alt.height == 3  # patients 2, 4 and 6
    check_lab_coherence(only_alt, ana_df=ana)
    only_strips = lab.filter(pl.col("SUB_CODE") == "L107010")
    check_lab_coherence(only_strips, ana_df=ana)


def test_build_clean_tables_reports_generator_errors_as_clean_table_errors(
    built_showcase: BuildResult,
) -> None:
    for clinical, message in (
        (_with_states(2, {"L103900|HCO3": "dka"}), "not allowed"),
        (_with_states(4, {"L104780|Kreatinin": "aki"}), "unsupported prose state"),
        (_with_states(1, {"L101850|CRP (kantitatif)": "nonexistent"}), "unknown state"),
        (_without_blood_gas(2, whole_block=True), "blood_gas"),
    ):
        with pytest.raises(CleanTableError, match=message):
            build_clean_tables(built_showcase.claims, clinical=clinical)


def test_validate_clean_tables_reports_an_unknown_lab_code_of_the_claims(
    built_showcase: BuildResult,
) -> None:
    procs = built_showcase.tables["procedure_claim_lines.parquet"]
    index = procs.with_row_index("i").filter(pl.col("procedure_category") == "laboratuvar")["i"][0]
    unknown = _set_cell(procs, index, "procedure_code", "L999999")
    tables = {**built_showcase.tables, "procedure_claim_lines.parquet": unknown}
    with pytest.raises(CleanTableError, match="unknown lab code 'L999999'"):
        validate_clean_tables(built_showcase.clean_tables, tables)


# --- 3.13 Gaps the independent review found in the validator --------------------------------------


def _ana_with(ana: pl.DataFrame, patient_no: int, column: str, value: Any) -> pl.DataFrame:
    """Copy of the anadata table with one cell of one patient's row replaced."""
    return ana.with_columns(
        pl.when(pl.col("HASTA_ID") == _pid(patient_no))
        .then(pl.lit(value, dtype=ana.schema[column]))
        .otherwise(pl.col(column))
        .alias(column)
    )


def _first_row_of(lab: pl.DataFrame, patient_no: int) -> int:
    """Row index of the first lab row of a patient."""
    return lab.with_row_index("i").filter(pl.col("HASTA_ID") == _pid(patient_no))["i"][0]


def _rejected(
    lab: pl.DataFrame, ana: pl.DataFrame | None
) -> pytest.ExceptionInfo[LabCoherenceError]:
    """The error `check_lab_coherence` raises for `lab`; the test fails when there is none."""
    with pytest.raises(LabCoherenceError) as caught:
        check_lab_coherence(lab, ana_df=ana)
    return caught


@pytest.mark.parametrize("with_anadata", [True, False], ids=["with_anadata", "alone"])
@pytest.mark.parametrize(
    ("patient_no", "code", "parameter", "csv_unit"),
    [
        pytest.param(2, "L102890", "Glukoz", "mg/dL", id="number"),
        pytest.param(4, "L107010", "Nitrit (strip)", "", id="strip"),
    ],
)
def test_mutation_a_missing_unit_is_rejected_on_a_number_and_on_a_strip(
    lab: pl.DataFrame,
    ana: pl.DataFrame,
    patient_no: int,
    code: str,
    parameter: str,
    csv_unit: str,
    with_anadata: bool,
) -> None:
    index = _index_of(lab, patient_no, code, parameter)
    caught = _rejected(_set_cell(lab, index, "birim", None), ana if with_anadata else None)
    _assert_names_the_row(caught, lab, rule="R6", row=index, code=code, parameter=parameter)
    assert str(caught.value).endswith(f"unit null differs from the CSV unit {csv_unit}")


@pytest.mark.parametrize("with_anadata", [True, False], ids=["with_anadata", "alone"])
@pytest.mark.parametrize(
    ("parameter", "code", "column", "value", "detail"),
    [
        pytest.param(
            "Glukoz",
            "L102890",
            "organ_sistemi",
            None,
            "organ_sistemi null is not Biyokimya",
            id="organ_null",
        ),
        pytest.param(
            "Glukoz",
            "L102890",
            "organ_sistemi",
            "Hematoloji",
            "organ_sistemi Hematoloji is not Biyokimya",
            id="organ_haematology_on_a_biochemistry_row",
        ),
        pytest.param(
            "MCV",
            "L107020",
            "organ_sistemi",
            "Biyokimya",
            "organ_sistemi Biyokimya is not Hematoloji",
            id="organ_biochemistry_on_a_hemogram_row",
        ),
        pytest.param(
            "Glukoz", "L102890", "kohort", None, "kohort null is not showcase", id="kohort_null"
        ),
        pytest.param(
            "Glukoz",
            "L102890",
            "kohort",
            "other",
            "kohort other is not showcase",
            id="kohort_other",
        ),
        pytest.param(
            "Glukoz",
            "L102890",
            "donem",
            None,
            "donem null is not the year of tarih 2026-03-09 00:00:00",
            id="donem_null",
        ),
        pytest.param(
            "Glukoz",
            "L102890",
            "donem",
            "2025",
            "donem 2025 is not the year of tarih 2026-03-09 00:00:00",
            id="donem_of_another_year",
        ),
        pytest.param(
            "Glukoz",
            "L102890",
            "tarih",
            datetime(2026, 3, 9, 13, 0),
            "tarih 2026-03-09 13:00:00 is not a date at midnight",
            id="tarih_at_13_hours",
        ),
        pytest.param(
            "Glukoz",
            "L102890",
            "tarih",
            datetime(2026, 3, 9, 0, 0, 1),
            "tarih 2026-03-09 00:00:01 is not a date at midnight",
            id="tarih_one_second_after_midnight",
        ),
        pytest.param(
            "Glukoz",
            "L102890",
            "tarih",
            None,
            "tarih null is not a date at midnight",
            id="tarih_null",
        ),
    ],
)
def test_mutation_the_descriptive_columns_must_be_the_ones_the_generator_writes(
    lab: pl.DataFrame,
    ana: pl.DataFrame,
    parameter: str,
    code: str,
    column: str,
    value: Any,
    detail: str,
    with_anadata: bool,
) -> None:
    index = _index_of(lab, 2, code, parameter, date="2026-03-09")
    caught = _rejected(_set_cell(lab, index, column, value), ana if with_anadata else None)
    _assert_names_the_row(caught, lab, rule="columns", row=index, code=code, parameter=parameter)
    assert str(caught.value).endswith(detail)


@pytest.mark.parametrize(
    ("patient_no", "date", "code", "parameter", "value", "decimals"),
    [
        pytest.param(2, "2026-03-09", "L100300", "ALT", 17.3, 0, id="ALT_17.3"),
        pytest.param(
            2, "2026-03-09", "L100300", "ALT", 17.0001, 0, id="ALT_a_tenth_of_a_thousandth"
        ),
        pytest.param(2, "2026-03-09", "L103900", "pH", 7.3001, 2, id="pH_a_hundredth_of_a_step"),
        pytest.param(
            4, "2026-05-11", "L107010", "Mikroskopi: lökosit", 31.5, 0, id="microscopy_31.5"
        ),
        pytest.param(2, "2026-03-09", "L103900", "pH", 7.305, 2, id="pH_three_decimals"),
        pytest.param(2, "2026-03-09", "L107020", "WBC (Lökosit)", 16.05, 1, id="WBC_two_decimals"),
        pytest.param(2, "2026-03-09", "L107020", _NEU, 12.945, 2, id="count_three_decimals"),
        pytest.param(2, "2026-03-09", "L107020", _HCT, 45.5, 0, id="HCT_one_decimal"),
        pytest.param(7, "2026-02-19", "L104780", _EGFR, 94.5, 0, id="eGFR_one_decimal"),
        pytest.param(2, "2026-03-09", "L103900", "HCO3", 28.25, 1, id="HCO3_two_decimals"),
        pytest.param(2, "2026-03-09", "L103900", "SaO2", 88.75, 1, id="SaO2_two_decimals"),
        pytest.param(
            7, "2026-02-19", "L107360", "hs-Troponin I", 4.95, 1, id="troponin_two_decimals"
        ),
    ],
)
def test_mutation_a_value_printed_with_more_decimals_than_its_parameter_is_rejected(
    lab: pl.DataFrame,
    ana: pl.DataFrame,
    patient_no: int,
    date: str,
    code: str,
    parameter: str,
    value: float,
    decimals: int,
) -> None:
    index = _index_of(lab, patient_no, code, parameter, date=date)
    caught = _rejected(_with_value(lab, index, value), ana)
    _assert_names_the_row(caught, lab, rule="decimals", row=index, code=code, parameter=parameter)
    assert str(caught.value).endswith(f"sonuc_sayisal {value} has more than {decimals} decimals")


def test_float_noise_is_not_a_decimal(lab: pl.DataFrame, ana: pl.DataFrame) -> None:
    """0.1 + 0.2 is 0.30000000000000004: the digits float arithmetic adds far out do not count."""
    alt = _index_of(lab, 2, "L100300", "ALT")
    noisy = _with_value(lab, alt, float(lab["sonuc_sayisal"][alt]) + 1e-12)
    assert noisy["sonuc_sayisal"][alt] != lab["sonuc_sayisal"][alt]
    check_lab_coherence(noisy, ana_df=ana)
    ph = _index_of(lab, 2, "L103900", "pH", date="2026-03-09")
    check_lab_coherence(_with_value(lab, ph, 7.3 + (0.1 + 0.2 - 0.3)), ana_df=ana)


def test_values_with_fewer_decimals_than_their_parameter_are_fine(
    lab: pl.DataFrame, ana: pl.DataFrame
) -> None:
    """The pH of the blood gas has two decimals; 7.3 is 7.30. A number is not judged by its text."""
    check_lab_coherence(
        _with_value(lab, _index_of(lab, 2, "L103900", "pH", date="2026-03-09"), 7.3), ana_df=ana
    )
    glucose = _index_of(lab, 2, "L102890", "Glukoz")
    check_lab_coherence(
        _with_value(lab, glucose, float(lab["sonuc_sayisal"][glucose]) + 3.0), ana_df=ana
    )


@pytest.mark.parametrize("code", ["x", "e", "", None, "k", "M", "KADIN"])
def test_mutation_a_sex_code_that_is_not_e_or_k_is_rejected(
    lab: pl.DataFrame, ana: pl.DataFrame, code: str | None
) -> None:
    """Patient 1 has no creatinine, so before this rule a bad code was read as male without a word."""
    row = _first_row_of(lab, 1)
    caught = _rejected(lab, _ana_with(ana, 1, "CINSIYET", code))
    _assert_names_the_row(
        caught, lab, rule="R5", row=row, code=lab["SUB_CODE"][row], parameter=lab["parametre"][row]
    )
    assert str(caught.value).endswith(
        f"CINSIYET {'null' if code is None else code} of the episode is neither E nor K: "
        "the sex-specific limits cannot be read"
    )


def test_mutation_a_missing_age_is_an_error_where_the_egfr_needs_it(
    lab: pl.DataFrame, ana: pl.DataFrame
) -> None:
    no_age = _ana_with(ana, 4, "TANI_YASI", None)
    first = _index_of(lab, 4, "L104780", "Kreatinin", nth=0)
    caught = _rejected(lab, no_age)
    _assert_names_the_row(caught, lab, rule="R3", row=first, code="L104780", parameter="Kreatinin")
    assert str(caught.value).endswith(
        "no age (TANI_YASI) for the episode: eGFR cannot be recomputed"
    )
    # Patient 1 has no creatinine line: the age is not used, so a missing one is not this check's business.
    check_lab_coherence(lab, ana_df=_ana_with(ana, 1, "TANI_YASI", None))


def test_mutation_a_row_of_another_patient_than_the_episode_is_rejected(
    lab: pl.DataFrame, ana: pl.DataFrame
) -> None:
    crp = _index_of(lab, 1, "L101850", "CRP (kantitatif)")
    for other in (_pid(2), None):
        caught = _rejected(_set_cell(lab, crp, "HASTA_ID", other), ana)
        # The message names the patient written in the row, the one that is wrong.
        expected = f"lab_clean anadata at row {crp} ({other or 'null'} L101850|CRP (kantitatif)): "
        assert str(caught.value).startswith(expected), str(caught.value)
        assert str(caught.value).endswith(
            f"the row is for patient {other or 'null'} but anadata_clean has patient "
            f"{_pid(1)} for the episode"
        )
    # Two patients exchanging all their lab rows (their episodes stay) is the same error, at the first row.
    swapped = lab.with_columns(
        pl.when(pl.col("HASTA_ID") == _pid(2))
        .then(pl.lit(_pid(6)))
        .when(pl.col("HASTA_ID") == _pid(6))
        .then(pl.lit(_pid(2)))
        .otherwise(pl.col("HASTA_ID"))
        .alias("HASTA_ID")
    )
    caught = _rejected(swapped, ana)
    first = _first_row_of(lab, 2)
    assert str(caught.value).startswith(f"lab_clean anadata at row {first} ({_pid(6)} ")


def test_mutation_the_limits_must_be_the_sex_specific_ones_even_where_the_csv_has_none(
    lab: pl.DataFrame, ana: pl.DataFrame
) -> None:
    """A limit that is present where the CSV has none (eGFR has no upper one) or absent where it has one."""
    egfr = _index_of(lab, 4, "L104780", _EGFR, date="2026-05-11")
    caught = _rejected(_set_cell(lab, egfr, "ref_ust", 100.0), ana)
    _assert_names_the_row(caught, lab, rule="R5", row=egfr, code="L104780", parameter=_EGFR)
    assert str(caught.value).endswith(
        "the limits [60.0, 100.0] are not the sex-specific limits [60.0, null] of the CSV"
    )
    troponin = _index_of(lab, 7, "L107360", "hs-Troponin I", nth=0)
    caught = _rejected(_set_cell(lab, troponin, "ref_alt", None), ana)
    _assert_names_the_row(
        caught, lab, rule="R5", row=troponin, code="L107360", parameter="hs-Troponin I"
    )
    assert str(caught.value).endswith(
        "the limits [null, 15.6] are not the sex-specific limits [0.0, 15.6] of the CSV"
    )


@pytest.mark.parametrize(
    "bad", [float("nan"), float("inf"), float("-inf")], ids=["nan", "inf", "-inf"]
)
@pytest.mark.parametrize("column", ["ref_alt", "ref_ust"])
@pytest.mark.parametrize("with_anadata", [True, False], ids=["with_anadata", "alone"])
def test_mutation_a_limit_that_is_not_finite_is_rejected_first(
    lab: pl.DataFrame, ana: pl.DataFrame, bad: float, column: str, with_anadata: bool
) -> None:
    index = _index_of(lab, 7, "L107360", "hs-Troponin I", nth=0)
    caught = _rejected(_set_cell(lab, index, column, bad), ana if with_anadata else None)
    _assert_names_the_row(
        caught, lab, rule="finite", row=index, code="L107360", parameter="hs-Troponin I"
    )
    assert str(caught.value).endswith("the reference limits must be finite")


@pytest.mark.parametrize("column", ["ref_alt", "ref_ust"])
def test_mutation_a_strip_has_no_limit_of_either_side(
    lab: pl.DataFrame, ana: pl.DataFrame, column: str
) -> None:
    index = _index_of(lab, 4, "L107010", "Protein (strip)")
    caught = _rejected(_set_cell(lab, index, column, 0.0), ana)
    _assert_names_the_row(
        caught, lab, rule="R6", row=index, code="L107010", parameter="Protein (strip)"
    )
    assert str(caught.value).endswith("a strip has no reference limits")


def _egfr_ten_higher(clean: dict[str, pl.DataFrame]) -> dict[str, pl.DataFrame]:
    lab = clean["lab_clean.parquet"]
    egfr = _index_of(lab, 7, "L104780", _EGFR)
    higher = _with_value(lab, egfr, float(lab["sonuc_sayisal"][egfr]) + 10.0)
    return {**clean, "lab_clean.parquet": higher}


def _anadata_changed(
    clean: dict[str, pl.DataFrame], patient_no: int, column: str, value: Any
) -> dict[str, pl.DataFrame]:
    ana = _ana_with(clean["anadata_clean.parquet"], patient_no, column, value)
    return {**clean, "anadata_clean.parquet": ana}


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        pytest.param(_egfr_ten_higher, r"lab_clean R3 at row .*eGFR", id="a_wrong_eGFR"),
        pytest.param(
            lambda clean: _anadata_changed(clean, 1, "CINSIYET", "K"),
            r"lab_clean R5 at row .*sex-specific limits",
            id="a_flipped_sex",
        ),
        pytest.param(
            lambda clean: _anadata_changed(clean, 4, "CINSIYET", "X"),
            r"lab_clean R5 at row .*neither E nor K",
            id="a_sex_code_X",
        ),
        pytest.param(
            lambda clean: _anadata_changed(clean, 4, "TANI_YASI", None),
            r"lab_clean R3 at row .*no age",
            id="no_age",
        ),
    ],
)
def test_validate_clean_tables_runs_the_coherence_check_with_the_anadata(
    built_showcase: BuildResult,
    mutate: Callable[[dict[str, pl.DataFrame]], dict[str, pl.DataFrame]],
    message: str,
) -> None:
    """With and without the claims: the coherence check sees the anadata either way."""
    clean = built_showcase.clean_tables
    validate_clean_tables(clean)
    validate_clean_tables(clean, built_showcase.tables)
    tampered = mutate(clean)
    with pytest.raises(CleanTableError, match=message):
        validate_clean_tables(tampered)
    with pytest.raises(CleanTableError, match=message):
        validate_clean_tables(tampered, built_showcase.tables)


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


@pytest.mark.parametrize(
    ("egfr", "age", "sex", "expected"),
    [
        (60.0, 60, "M", 1.3519886371748253),
        (125.0, 30, "F", 0.5756447373561503),
        (45.0, 86, "F", 1.1796127244355594),
        (90.0, 40, "M", 1.069663357634239),
        (130.0, 25, "M", 0.7204757010914428),
        (20.0, 70, "F", 2.519058857893674),
    ],
)
def test_the_inverse_of_ckd_epi_2021_equals_the_exact_value_in_both_branches(
    egfr: float, age: int, sex: str, expected: float
) -> None:
    """An eGFR above A = 142·0.9938^age (·1.012 for women) is inverted with alpha, below it with -1.2."""
    assert _close(invert_ckd_epi_2021(egfr, age, sex), expected)


# --- 3.15 Guards for the mutants the independent review left alive (reader, ranges, age bands) --------


@pytest.mark.parametrize(
    ("item", "strip", "message"),
    [
        pytest.param("x: 5–5", False, "numeric range low >= high", id="numeric"),
        pytest.param("x: eGFR 5–5", False, "eGFR band low >= high", id="egfr_band"),
        pytest.param("x: M 3–3", False, "sex-specific range low >= high", id="sex_range"),
        pytest.param("x: M 3–4, F 5–5", False, "sex-specific range low >= high", id="second_sex"),
        pytest.param(
            "x: 5–5 or 6–7", False, "alternative range low >= high", id="first_alternative"
        ),
        pytest.param(
            "x: 5–6 or 7–7", False, "alternative range low >= high", id="second_alternative"
        ),
        pytest.param("x: 3 to 3", False, "'to' range low >= high", id="to_range"),
        pytest.param("x: -3 to -3", False, "'to' range low >= high", id="signed_to_range"),
        pytest.param("x: + to +", True, "strip grade range out of order", id="same_grade"),
        pytest.param("x: ++ to +", True, "strip grade range out of order", id="reversed_grades"),
    ],
)
def test_a_range_whose_two_ends_are_equal_is_rejected_in_every_grammar_form(
    item: str, strip: bool, message: str
) -> None:
    with pytest.raises(LabReferenceError, match=re.escape(message)):
        parse_abnormal_state_item(item, is_qualitative_strip=strip, context="equal ends")


def test_abnormal_states_are_separated_by_a_semicolon_and_a_space() -> None:
    parsed, unsupported = parse_abnormal_states("a: 1–2; b: 3–4")
    assert [state.name for state in parsed] == ["a", "b"] and unsupported == ()
    # A semicolon with no space after it is no separator: it is one item, and that item is malformed.
    with pytest.raises(LabReferenceError):
        parse_abnormal_states("a: 1–2;b: 3–4", context="no space")
    # A semicolon inside a parenthesis is not a separator either (the item loses its remark).
    parsed, _ = parse_abnormal_states("a: 1–2 (x;y); b: 3–4")
    assert [state.name for state in parsed] == ["a", "b"]


def test_a_missing_low_limit_means_zero_in_a_normal_draw() -> None:
    raw = _edit_cell(_raw_csv(), "L100300|ALT", "ref_low_male", "")
    spec = load_lab_reference_df(raw).by_key["L100300|ALT"]
    assert spec.ref_low_male is None and spec.ref_high_male == 41.0
    assert spec.normal_draw_limits("M") == (0.0, 41.0)
    u = draw_u(_pid(3), "L100300", "ALT", 1, 0)
    assert draw_numeric_value(spec, patient_id=_pid(3), sex="M", k=1) == round(
        41.0 * (0.30 + 0.40 * u)
    )


def test_a_row_is_a_strip_only_when_it_has_no_limit_at_all_and_is_negatif() -> None:
    raw = _raw_csv()
    limits = ("ref_low_male", "ref_high_male", "ref_low_female", "ref_high_female")
    # A number with no limit at all is no strip: it has to say Negatif as well.
    without_limits = raw
    for column in limits:
        without_limits = _edit_cell(without_limits, "L100300|ALT", column, "")
    assert not load_lab_reference_df(without_limits).by_key["L100300|ALT"].is_qualitative_strip
    # And a row that says Negatif but has limits is no strip: it has to have no limit as well.
    negatif = _edit_cell(raw, "L100300|ALT", "normal_value_range", "Negatif")
    assert not load_lab_reference_df(negatif).by_key["L100300|ALT"].is_qualitative_strip
    strips = [
        spec.result_parameter
        for spec in load_lab_reference_df(raw).by_code["L107010"]
        if spec.is_qualitative_strip
    ]
    assert len(strips) == 6


@pytest.mark.parametrize(
    ("key", "ranges"),
    [
        ("L107020|RBC (Eritrosit)", 5),
        ("L107020|HCT (Hematokrit)", 4),
        ("L107020|MCHC", 2),
        ("L107020|HGB (Hemoglobin)", 9),
    ],
)
def test_the_end_points_of_every_state_range_belong_to_the_state(key: str, ranges: int) -> None:
    """`ranges` is the number of (state, sex) ranges of the parameter: a state with one sex counts once."""
    spec = load_lab_reference().by_key[key]
    checked = 0
    for state in spec.parsed_states:
        for sex in ("M", "F"):
            if state.kind == "sex_range" and sex not in state.sex_ranges:
                continue
            low, high = state.range_for_sex(sex)
            assert _value_in_own_state_ranges(spec, low, sex), (state.name, sex, low)
            assert _value_in_own_state_ranges(spec, high, sex), (state.name, sex, high)
            checked += 1
    assert checked == ranges


def test_a_value_just_outside_the_state_ranges_is_not_in_them() -> None:
    rbc = load_lab_reference().by_key["L107020|RBC (Eritrosit)"]
    # anemia F 2.8-3.9, M 3.0-4.4; thalassemia_trait 5.0-6.5; polycythemia M 6.0-6.8
    for sex, value in (
        ("F", 2.79),
        ("F", 3.91),
        ("F", 4.99),
        ("F", 6.51),
        ("M", 2.99),
        ("M", 6.81),
    ):
        assert not _value_in_own_state_ranges(rbc, value, sex), (sex, value)
    for sex, value in (("F", 2.8), ("F", 3.9), ("F", 5.0), ("F", 6.5), ("M", 3.0), ("M", 6.8)):
        assert _value_in_own_state_ranges(rbc, value, sex), (sex, value)


@pytest.mark.parametrize(
    ("age", "band"),
    [
        (18, (95.0, 120.0)),
        (39, (95.0, 120.0)),
        (40, (85.0, 105.0)),
        (59, (85.0, 105.0)),
        (60, (75.0, 95.0)),
        (69, (75.0, 95.0)),
        (70, (70.0, 85.0)),
        (200, (70.0, 85.0)),
    ],
)
def test_the_egfr_age_bands_include_both_of_their_edges(
    age: int, band: tuple[float, float]
) -> None:
    assert _egfr_normal_band_for_age(age, load_lab_reference().egfr_age_bands) == band


@pytest.mark.parametrize("age", [0, 17, 201])
def test_an_age_outside_every_egfr_band_is_an_error(age: int) -> None:
    with pytest.raises(LabCoherenceError, match=f"No normal eGFR age band for age {age}"):
        _egfr_normal_band_for_age(age, load_lab_reference().egfr_age_bands)


# --- 3.16 Scripted draws: the retry loops, the limits they accept and the states that drive them -------
#
# `labs.draw_numeric_value` and `labs.draw_u` are replaced by functions that return chosen numbers, so
# that a test can put a derived value exactly on a limit or make the Nth try the first good one. Every
# other draw stays real. The numbers of the scripted triples were found by trying the formulas of the
# rules R2 and R3; each test asserts what it relies on.

_RBC_P, _HCT_P, _MCHC_P = "RBC (Eritrosit)", "HCT (Hematokrit)", "MCHC"


def _script_red_cells(
    monkeypatch: pytest.MonkeyPatch, by_salt: Callable[[int], tuple[float, float, float]]
) -> list[int]:
    """HGB, MCV and MCH of the hemogram come from `by_salt(salt)`; returns the list of salts asked for HGB."""
    asked: list[int] = []
    drivers = {"L107020|HGB (Hemoglobin)": 0, "L107020|MCV": 1, "L107020|MCH": 2}

    def scripted(
        spec: Any, *, patient_id: str, sex: str, k: int, state_id: str = "normal", salt: int = 0
    ) -> float:
        index = drivers.get(spec.key)
        if index is None:
            return draw_numeric_value(
                spec, patient_id=patient_id, sex=sex, k=k, state_id=state_id, salt=salt
            )
        if index == 0:
            asked.append(salt)
        return by_salt(salt)[index]

    monkeypatch.setattr(labs_module, "draw_numeric_value", scripted)
    return asked


def _script_u(monkeypatch: pytest.MonkeyPatch, by_salt: Callable[[int], float]) -> list[int]:
    """Every `draw_u` returns `by_salt(salt)`; returns the list of salts asked for."""
    asked: list[int] = []

    def scripted(patient_id: str, code: str, parameter: str, k: int, salt: int = 0) -> float:
        asked.append(salt)
        return by_salt(salt)

    monkeypatch.setattr(labs_module, "draw_u", scripted)
    return asked


def _hemogram(
    states_map: dict[str, Any] | None = None, sex: str = "M", patient_no: int = 1
) -> dict[str, float]:
    return _generate_hemogram_values(
        load_lab_reference().by_code["L107020"],
        patient_id=_pid(patient_no),
        sex=sex,
        k=1,
        states_map=states_map or {},
    )


_RED_GOOD = (14.7, 91.0, 30.0)  # RBC 4.9, HCT 45, MCHC 32.7: inside the male limits
_RED_BAD = (20.0, 90.0, 20.0)  # RBC 10.0: outside them


def test_the_red_cell_draw_tries_exactly_50_salts(monkeypatch: pytest.MonkeyPatch) -> None:
    asked = _script_red_cells(monkeypatch, lambda salt: _RED_GOOD if salt >= 49 else _RED_BAD)
    values = _hemogram()
    assert asked == list(range(50))  # salts 0 to 49: the 50th try is the first good one
    assert (values[_RBC_P], values[_HCT_P], values[_MCHC_P]) == (4.9, 45.0, 32.7)
    asked = _script_red_cells(monkeypatch, lambda salt: _RED_GOOD if salt >= 50 else _RED_BAD)
    with pytest.raises(LabCoherenceError, match=r"red-cell indices failed to converge in 50 tries"):
        _hemogram()
    assert asked == list(range(50))  # and there is no 51st


# The male limits are RBC 4.5 to 5.9, HCT 40 to 52 and MCHC 32.0 to 36.0. Each scripted (HGB, MCV, MCH)
# gives the printed (RBC, HCT, MCHC) next to it: one value exactly on a limit, or one printed step beyond.
_ON_A_LIMIT = [
    pytest.param((13.4, 91.0, 30.0), (4.5, 41.0, 32.7), id="RBC_on_the_lower_limit"),
    pytest.param((13.5, 70.0, 23.0), (5.9, 41.0, 32.9), id="RBC_on_the_upper_limit"),
    pytest.param((12.9, 71.0, 23.0), (5.6, 40.0, 32.2), id="HCT_on_the_lower_limit"),
    pytest.param((16.7, 92.0, 30.0), (5.6, 52.0, 32.1), id="HCT_on_the_upper_limit"),
    pytest.param((13.1, 72.0, 23.0), (5.7, 41.0, 32.0), id="MCHC_on_the_lower_limit"),
    pytest.param((15.1, 72.0, 26.0), (5.8, 42.0, 36.0), id="MCHC_on_the_upper_limit"),
]
_ONE_STEP_BEYOND = [
    pytest.param((13.2, 93.0, 30.0), (4.4, 41.0, 32.2), id="RBC_below"),
    pytest.param((13.7, 70.0, 23.0), (6.0, 42.0, 32.6), id="RBC_above"),
    pytest.param((12.5, 72.0, 23.0), (5.4, 39.0, 32.1), id="HCT_below"),
    pytest.param((17.0, 93.0, 30.0), (5.7, 53.0, 32.1), id="HCT_above"),
    pytest.param((13.4, 72.0, 23.0), (5.8, 42.0, 31.9), id="MCHC_below"),
    pytest.param((14.8, 72.0, 26.0), (5.7, 41.0, 36.1), id="MCHC_above"),
]


@pytest.mark.parametrize(("triple", "derived"), _ON_A_LIMIT)
def test_a_derived_red_cell_value_exactly_on_a_limit_is_accepted_at_the_first_try(
    monkeypatch: pytest.MonkeyPatch, triple: tuple[float, float, float], derived: tuple[float, ...]
) -> None:
    asked = _script_red_cells(monkeypatch, lambda salt: triple)
    values = _hemogram()
    assert asked == [0]
    assert (values[_RBC_P], values[_HCT_P], values[_MCHC_P]) == derived


@pytest.mark.parametrize(("triple", "derived"), _ONE_STEP_BEYOND)
def test_a_derived_red_cell_value_one_printed_step_beyond_a_limit_is_never_accepted(
    monkeypatch: pytest.MonkeyPatch, triple: tuple[float, float, float], derived: tuple[float, ...]
) -> None:
    asked = _script_red_cells(monkeypatch, lambda salt: triple)
    with pytest.raises(LabCoherenceError, match=r"red-cell indices failed to converge in 50 tries"):
        _hemogram()
    assert asked == list(range(50))
    # What the scripted draws give is what the table says: the same formulas, read off the rule R2.
    hgb, mcv, mch = triple
    rbc = round(hgb * 10.0 / mch, 1)
    hct = float(round(mcv * rbc / 10.0))
    assert (rbc, hct, round(hgb / hct * 100.0, 1)) == derived


# A state on ONE of HGB, MCV and MCH lets a derived value sit in one of its own state ranges; the same
# draws with no state at all are refused. (HGB, MCV, MCH) and the (RBC, HCT, MCHC) they give.
@pytest.mark.parametrize(
    ("key", "state", "triple", "derived"),
    [
        pytest.param(
            "L107020|HGB (Hemoglobin)",
            "iron_deficiency_anemia",
            (8.0, 80.0, 27.0),
            (3.0, 24.0, 33.3),
            id="hgb",
        ),
        pytest.param(
            "L107020|MCV",
            "b12_or_folate_deficiency",
            (13.0, 101.0, 28.0),
            (4.6, 46.0, 28.3),
            id="mcv",
        ),
        pytest.param(
            "L107020|MCH", "iron_deficiency", (13.0, 80.0, 24.0), (5.4, 43.0, 30.2), id="mch"
        ),
    ],
)
def test_a_state_on_any_one_driver_lets_the_derived_values_sit_in_their_own_state_ranges(
    monkeypatch: pytest.MonkeyPatch,
    key: str,
    state: str,
    triple: tuple[float, float, float],
    derived: tuple[float, ...],
) -> None:
    asked = _script_red_cells(monkeypatch, lambda salt: triple)
    values = _hemogram({key: state})
    assert asked == [0]
    assert (values[_RBC_P], values[_HCT_P], values[_MCHC_P]) == derived
    asked.clear()
    with pytest.raises(LabCoherenceError, match=r"red-cell indices failed to converge in 50 tries"):
        _hemogram()  # no state on a driver: the same values are outside the normal limits
    assert asked == list(range(50))


# --- creatinine ---

_CREATININE_BAND = ((18, 200, 40.0, 100.0),)  # a target eGFR of 58 (u = 0) to 82 (u = 1)


def _creatinine(
    *,
    sex: str,
    age: int,
    bands: tuple[tuple[int, int, float, float], ...],
    states_map: dict[str, Any] | None = None,
    patient_no: int = 3,
) -> dict[str, float]:
    return _generate_creatinine_and_egfr(
        load_lab_reference().by_code["L104780"],
        patient_id=_pid(patient_no),
        age=age,
        sex=sex,
        k=1,
        states_map=states_map or {},
        egfr_age_bands=bands,
    )


def test_the_normal_creatinine_draw_tries_exactly_50_salts(monkeypatch: pytest.MonkeyPatch) -> None:
    """A woman of 77: a target eGFR of 58 gives a creatinine of 1.00 (above her limit 0.95), 82 gives 0.75."""
    assert round(invert_ckd_epi_2021(58.0, 77, "F"), 2) == 1.0
    good = round(invert_ckd_epi_2021(82.0, 77, "F"), 2)
    assert 0.51 <= good <= 0.95
    asked = _script_u(monkeypatch, lambda salt: 1.0 if salt >= 49 else 0.0)
    values = _creatinine(sex="F", age=77, bands=_CREATININE_BAND)
    assert asked == list(range(50))
    assert values == {"Kreatinin": good, _EGFR: float(round(ckd_epi_2021(good, 77, "F")))}
    asked = _script_u(monkeypatch, lambda salt: 1.0 if salt >= 50 else 0.0)
    with pytest.raises(
        LabCoherenceError, match="normal draw outside sex-specific limits after 50 tries"
    ):
        _creatinine(sex="F", age=77, bands=_CREATININE_BAND)
    assert asked == list(range(50))


@pytest.mark.parametrize(
    ("sex", "age", "limit"),
    [
        pytest.param("F", 77, 0.95, id="woman_upper"),
        pytest.param("F", 77, 0.51, id="woman_lower"),
        pytest.param("M", 60, 1.17, id="man_upper"),
        pytest.param("M", 60, 0.67, id="man_lower"),
    ],
)
def test_a_normal_creatinine_may_sit_exactly_on_a_limit_of_its_sex(
    sex: str, age: int, limit: float
) -> None:
    egfr = ckd_epi_2021(limit, age, sex)
    values = _creatinine(sex=sex, age=age, bands=((18, 200, egfr, egfr),))
    assert values["Kreatinin"] == limit
    assert values[_EGFR] == float(round(egfr))


def _sha_u(patient_no: int, code: str, parameter: str, k: int = 1, salt: int = 0) -> float:
    """The draw of the design, written again here: first 8 bytes of SHA-256 of the pipe-joined payload."""
    payload = f"{_pid(patient_no)}|{code}|{parameter}|{k}|{salt}".encode()
    return int.from_bytes(hashlib.sha256(payload).digest()[:8], "big") / 2**64


@pytest.mark.parametrize(
    ("sex", "age", "egfr_band"), [("F", 60, (75.0, 95.0)), ("M", 60, (75.0, 95.0))]
)
def test_a_normal_creatinine_inverts_the_central_band_of_the_age_band_of_the_egfr(
    sex: str, age: int, egfr_band: tuple[float, float]
) -> None:
    """Target eGFR = low + (high - low)(0.30 + 0.40 u); creatinine = its inverse to 2 decimals; eGFR from that."""
    limits = (0.51, 0.95) if sex == "F" else (0.67, 1.17)
    for patient_no in range(1, 81):
        values = _creatinine(
            sex=sex, age=age, bands=load_lab_reference().egfr_age_bands, patient_no=patient_no
        )
        u = _sha_u(patient_no, "L104780", "Kreatinin")
        target = egfr_band[0] + (egfr_band[1] - egfr_band[0]) * (0.30 + 0.40 * u)
        expected = round(invert_ckd_epi_2021(target, age, sex), 2)
        assert limits[0] <= expected <= limits[1], patient_no  # no retry needed for this band
        assert values["Kreatinin"] == expected, patient_no
        assert values[_EGFR] == float(round(ckd_epi_2021(expected, age, sex))), patient_no


def test_a_creatinine_state_given_as_an_egfr_band_is_inverted_from_the_state_band() -> None:
    """`ckd_g3a` is eGFR 45 to 59: target = 45 + 14 (0.20 + 0.60 u), drawn from the first salt."""
    for patient_no in range(1, 81):
        values = _creatinine(
            sex="F",
            age=86,
            bands=load_lab_reference().egfr_age_bands,
            states_map={"L104780|Kreatinin": "ckd_g3a"},
            patient_no=patient_no,
        )
        u = _sha_u(patient_no, "L104780", "Kreatinin")
        expected = round(invert_ckd_epi_2021(45.0 + 14.0 * (0.20 + 0.60 * u), 86, "F"), 2)
        assert values["Kreatinin"] == expected, patient_no
        assert values[_EGFR] == float(round(ckd_epi_2021(expected, 86, "F"))), patient_no


def test_a_creatinine_state_given_in_mg_dl_is_drawn_inside_the_band_with_two_decimals() -> None:
    """`sarcopenic_elderly` is 0.40 to 0.60 mg/dL: the creatinine is that draw to 2 decimals."""
    for patient_no in range(1, 81):
        values = _creatinine(
            sex="F",
            age=70,
            bands=load_lab_reference().egfr_age_bands,
            states_map={"L104780|Kreatinin": "sarcopenic_elderly"},
            patient_no=patient_no,
        )
        u = _sha_u(patient_no, "L104780", "Kreatinin")
        assert values["Kreatinin"] == round(0.40 + 0.20 * (0.20 + 0.60 * u), 2), patient_no


# --- strips ---


@pytest.mark.parametrize(
    ("key", "state", "grades"),
    [
        pytest.param(
            "L107010|Kan / hemoglobin (strip)",
            "glomerulonephritis",  # + to +++
            {0.0: "+", 0.4: "++", 0.99: "+++"},
            id="plus_to_three_plus",
        ),
        pytest.param(
            "L107010|Protein (strip)",
            "diabetic_or_hypertensive_nephropathy",  # Eser to +
            {0.0: "Eser", 0.4: "Eser", 0.9: "+"},
            id="eser_to_plus",
        ),
        pytest.param(
            "L107010|Glukoz (strip)",
            "dka",  # +++ to ++++
            {0.0: "+++", 0.4: "+++", 0.9: "++++"},
            id="three_plus_to_four_plus",
        ),
    ],
)
def test_a_strip_grade_is_the_rounded_point_of_the_state_range_at_the_draw(
    monkeypatch: pytest.MonkeyPatch, key: str, state: str, grades: dict[float, str]
) -> None:
    """index = round(low + (high - low) (0.20 + 0.60 u)) on the scale Negatif, Eser, +, ++, +++, ++++."""
    spec = load_lab_reference().by_key[key]
    for u, grade in grades.items():
        _script_u(monkeypatch, lambda salt, u=u: u)
        assert draw_strip_grade(spec, patient_id=_pid(4), k=1, state_id=state) == grade, (state, u)


def test_strip_grades_follow_the_state_range_for_every_strip_state_and_many_patients() -> None:
    checked = 0
    for spec in load_lab_reference().by_code["L107010"]:
        for state in spec.parsed_states:
            if state.kind not in ("grade_range", "grade_single"):
                continue
            for patient_no in range(1, 41):
                got = draw_strip_grade(spec, patient_id=_pid(patient_no), k=1, state_id=state.name)
                if state.kind == "grade_single":
                    expected = state.grade_low
                else:
                    low = _ORDINAL.index(state.grade_low)
                    high = _ORDINAL.index(state.grade_high)
                    u = _sha_u(patient_no, "L107010", spec.result_parameter)
                    expected = _ORDINAL[round(low + (high - low) * (0.20 + 0.60 * u))]
                assert got == expected, (spec.result_parameter, state.name, patient_no)
                checked += 1
    assert checked == 40 * 16  # 16 grade states in the six strips: 4 + 3 + 3 + 4 + 1 + 1


# --- 3.17 Exact pins of the generator: the differential, the independent draws, the line order --------

_WBC_STATE_BAND = {  # the CSV ranges of the three WBC states used below (sepsis: the first alternative)
    "bacterial_infection": (11.0, 20.0),
    "steroid_use": (10.5, 15.0),
    "sepsis": (12.0, 30.0),
}
# The differential profile each WBC state reads from: a state with no profile of its own reads as normal.
_PROFILE_OF_STATE = {
    "normal": "normal",
    "bacterial_infection": "bacterial_infection",
    "steroid_use": "steroid_use",
    "sepsis": "normal",
}


def _expected_differential(patient_no: int, wbc_state: str) -> tuple[float, dict[str, float]]:
    """WBC and the five counts of rule R1, from the SHA-256 draws and the profile bounds of the design."""
    u = _sha_u(patient_no, "L107020", "WBC (Lökosit)")
    if wbc_state == "normal":
        wbc = round(4.0 + 6.0 * (0.30 + 0.40 * u), 1)
    else:
        low, high = _WBC_STATE_BAND[wbc_state]
        wbc = round(low + (high - low) * (0.20 + 0.60 * u), 1)
    profile = _PROFILES[_PROFILE_OF_STATE[wbc_state]]
    raw = {
        name: profile[name][0]
        + (profile[name][1] - profile[name][0]) * _sha_u(patient_no, "L107020", name)
        for name in _DIFFERENTIAL
    }
    total = sum(raw.values())
    counts = {name: round(wbc * (raw[name] * 100.0 / total) / 100.0, 2) for name in _DIFFERENTIAL}
    others = sum(value for name, value in counts.items() if name != _NEU)
    counts[_NEU] = round(wbc - others, 2)
    return wbc, counts


@pytest.mark.parametrize("wbc_state", ["normal", "bacterial_infection", "steroid_use", "sepsis"])
def test_the_differential_is_the_documented_function_of_the_wbc_its_state_and_the_draws(
    wbc_state: str,
) -> None:
    """Every bound of every profile counts: moving one changes the counts of some patient."""
    states = {} if wbc_state == "normal" else {"L107020|WBC (Lökosit)": wbc_state}
    for patient_no in range(1, 81):
        values = _hemogram(states, patient_no=patient_no)
        wbc, counts = _expected_differential(patient_no, wbc_state)
        assert values["WBC (Lökosit)"] == wbc, patient_no
        assert {name: values[name] for name in _DIFFERENTIAL} == counts, patient_no
        # R1: the neutrophils take up the rounding, so the five counts sum to the WBC up to float noise.
        assert abs(sum(values[name] for name in _DIFFERENTIAL) - wbc) < 1e-9, patient_no


def test_the_independent_values_are_drawn_from_the_first_salt() -> None:
    """RDW-CV, platelets, MPV and the independent blood-gas values: `lo + (hi - lo)(0.30 + 0.40 u)`, salt 0."""
    reference = load_lab_reference()
    hemogram = (
        ("RDW-CV", 11.5, 14.5, 1),
        ("PLT (Trombosit)", 150.0, 400.0, 0),
        ("MPV", 7.5, 11.5, 1),
    )
    gas = (
        ("pH", 7.35, 7.45, 2),
        ("pCO2", 35.0, 45.0, 0),
        ("pO2", 80.0, 100.0, 0),
        ("Laktat (kan gazı)", 0.5, 1.6, 1),
        ("Sodyum (kan gazı)", 136.0, 145.0, 0),
        ("Potasyum (kan gazı)", 3.4, 4.5, 1),
        ("İyonize kalsiyum (kan gazı)", 1.12, 1.32, 2),
    )

    def central(
        patient_no: int, code: str, name: str, low: float, high: float, decimals: int
    ) -> float:
        value = low + (high - low) * (0.30 + 0.40 * _sha_u(patient_no, code, name))
        return float(round(value)) if decimals == 0 else round(value, decimals)

    for patient_no in range(1, 41):
        values = _hemogram(patient_no=patient_no)
        for name, low, high, decimals in hemogram:
            assert values[name] == central(patient_no, "L107020", name, low, high, decimals), (
                patient_no,
                name,
            )
        drawn = _generate_blood_gas_values(
            reference.by_code["L103900"],
            patient_id=_pid(patient_no),
            sex="M",
            k=1,
            blood_gas_type="arterial",
            states_map={},
        )
        for name, low, high, decimals in gas:
            assert drawn[name] == central(patient_no, "L103900", name, low, high, decimals), (
                patient_no,
                name,
            )
        # and the three derived values follow pH, pCO2 and pO2
        assert drawn["HCO3"] == round(_hco3(drawn["pH"], drawn["pCO2"]), 1)
        assert drawn["BE (baz fazlası)"] == round(_base_excess(drawn["pH"], drawn["HCO3"]), 1)
        assert drawn["SaO2"] == round(_sao2(drawn["pO2"]), 1)


def test_occurrences_follow_the_date_even_when_the_line_ids_say_otherwise(
    built_showcase: BuildResult, lab: pl.DataFrame
) -> None:
    """Patient 2 bills the CRP on two days: if the later line has the smaller id, the first sample is still the first day's."""
    claims = list(built_showcase.claims)
    position = next(i for i, claim in enumerate(claims) if claim.header.patient_id == _pid(2))
    claim = claims[position]
    crp = [i for i, line in enumerate(claim.procedures) if line.procedure_code == "L101850"]
    assert len(crp) == 2
    first, second = (claim.procedures[i] for i in crp)
    assert first.procedure_date < second.procedure_date
    assert first.procedure_line_id < second.procedure_line_id
    procedures = list(claim.procedures)
    procedures[crp[0]] = dataclasses.replace(first, procedure_line_id=second.procedure_line_id)
    procedures[crp[1]] = dataclasses.replace(second, procedure_line_id=first.procedure_line_id)
    claims[position] = dataclasses.replace(claim, procedures=tuple(procedures))
    rebuilt = build_lab_clean(claims, clinical=load_clinical(), schema=LAB_CLEAN_SCHEMA)
    # The rows of one day follow the line ids, so the two tables list the day's results in another order
    # (that is what makes this a real change); the rows themselves are the same, and so are the CRP values
    # of the two days: the first sample of a code is the one of the first day.
    assert not rebuilt.equals(lab)
    assert rebuilt.sort(lab.columns).equals(lab.sort(lab.columns))

    def crp_values(table: pl.DataFrame) -> list[float]:
        crp = table.filter((pl.col("HASTA_ID") == _pid(2)) & (pl.col("SUB_CODE") == "L101850"))
        return crp.sort("tarih")["sonuc_sayisal"].to_list()

    assert crp_values(rebuilt) == crp_values(lab)


def test_two_derived_states_name_the_first_in_csv_order_whatever_the_hash_seed(
    built_showcase: BuildResult,
) -> None:
    """The derived parameters are tuples (a set's order depends on the hash seed): the first asked is named."""
    assert isinstance(labs_module.RED_CELL_DERIVED_PARAMS, tuple)
    assert isinstance(labs_module.BLOOD_GAS_DERIVED_PARAMS, tuple)
    cases = [
        (1, "L107020", ["RBC (Eritrosit)", "HCT (Hematokrit)", "MCHC"], "RBC (Eritrosit)"),
        (1, "L107020", ["MCHC", "HCT (Hematokrit)"], "HCT (Hematokrit)"),
        (2, "L103900", ["SaO2", "BE (baz fazlası)", "HCO3"], "HCO3"),
        (2, "L103900", ["SaO2", "BE (baz fazlası)"], "BE (baz fazlası)"),
    ]
    for patient_no, code, asked, named in cases:
        states = {f"{code}|{name}": "anemia" for name in asked}
        with pytest.raises(DerivedLabParameterError) as caught:
            _build(built_showcase, _with_states(patient_no, states))
        assert f"{code}|{named}: state" in str(caught.value), (asked, str(caught.value))


# --- 3.18 Exactly on a tolerance, and what the coherence check alone cannot see ---------------------


def _set_values(
    lab: pl.DataFrame, patient_no: int, code: str, values: dict[str, float]
) -> pl.DataFrame:
    """Copy of `lab` with several values of patient `patient_no`'s first set of `code` changed, flags kept right."""
    changed = lab
    for parameter, value in values.items():
        changed = _with_value(changed, _index_of(lab, patient_no, code, parameter), value)
    return changed


def test_a_derived_value_exactly_half_a_printed_step_away_is_accepted(
    lab: pl.DataFrame, ana: pl.DataFrame
) -> None:
    """HGB 9.1, MCH 20, MCV 90: RBC = 4.55, HCT = 40.5 (with RBC 4.5), MCHC = 22.75 (with HCT 40).

    Each of these formula values is exactly half a printed step from two printed numbers, so both are
    right (that is where a rounding rule is ambiguous). One more step is wrong, see the drift cases.
    """
    drivers = {"HGB (Hemoglobin)": 9.1, "MCH": 20.0, "MCV": 90.0}
    # (RBC, HCT, MCHC): three ties; the RBC tie alone, with the HCT of RBC 4.6; the RBC and HCT ties.
    for rbc, hct, mchc in ((4.5, 40.0, 22.8), (4.6, 41.0, 22.2), (4.5, 41.0, 22.2)):
        tied = _set_values(
            lab,
            1,
            "L107020",
            {**drivers, "RBC (Eritrosit)": rbc, "HCT (Hematokrit)": hct, "MCHC": mchc},
        )
        check_lab_coherence(tied, ana_df=ana)
    # RBC 4.7 is 0.15 away (three half-steps): rejected, at the RBC row.
    far = _set_values(
        lab,
        1,
        "L107020",
        {**drivers, "RBC (Eritrosit)": 4.7, "HCT (Hematokrit)": 42.0, "MCHC": 21.7},
    )
    caught = _rejected(far, ana)
    row = _index_of(lab, 1, "L107020", "RBC (Eritrosit)")
    _assert_names_the_row(
        caught, lab, rule="R2", row=row, code="L107020", parameter="RBC (Eritrosit)"
    )


def _two_men_exchange_a_crp_set(lab: pl.DataFrame) -> pl.DataFrame:
    """Patient 1's CRP set and patient 2's first one change owners (patient and episode): two men, so the limits agree."""
    one = _index_of(lab, 1, "L101850", "CRP (kantitatif)")
    two = _index_of(lab, 2, "L101850", "CRP (kantitatif)", date="2026-03-09")
    moved = _set_cell(
        _set_cell(lab, one, "HASTA_ID", _pid(2)), one, "basvuru_id", "B-SENTETIK-HASTA-0002-001"
    )
    return _set_cell(
        _set_cell(moved, two, "HASTA_ID", _pid(1)), two, "basvuru_id", "B-SENTETIK-HASTA-0001-001"
    )


def _a_second_crp_set_for_patient_1(lab: pl.DataFrame) -> pl.DataFrame:
    return pl.concat([lab, lab.slice(_index_of(lab, 1, "L101850", "CRP (kantitatif)"), 1)])


def _sets_sorted_by_code(lab: pl.DataFrame) -> pl.DataFrame:
    return lab.sort("SUB_CODE", maintain_order=True)  # the sets stay whole, their order changes


@pytest.mark.parametrize(
    "mutate",
    [
        pytest.param(_two_men_exchange_a_crp_set, id="two_sets_change_owners"),
        pytest.param(_move_a_result_set_one_day, id="a_set_on_another_day"),
        pytest.param(_glucose_for_the_package_patient, id="an_extra_set"),
        pytest.param(_remove_a_whole_result_set, id="a_missing_set"),
        pytest.param(_a_second_crp_set_for_patient_1, id="a_duplicated_set"),
        pytest.param(_put_the_crp_set_after_the_hemogram, id="sets_in_another_order"),
        pytest.param(_sets_sorted_by_code, id="all_sets_sorted_by_code"),
    ],
)
def test_the_coherence_check_alone_cannot_see_a_coherent_set_that_nobody_billed(
    built_showcase: BuildResult, mutate: Callable[[pl.DataFrame], pl.DataFrame]
) -> None:
    """Pinned limit, written in the docstrings: only the check against the billed lines finds these.

    `check_lab_coherence`, `validate_clean_tables(clean)` and `clean_tables_digest` (which validates
    without claims) all accept the table; `validate_clean_tables(clean, claims)` refuses it.
    """
    clean = built_showcase.clean_tables
    mutated = {**clean, "lab_clean.parquet": mutate(clean["lab_clean.parquet"])}
    assert not mutated["lab_clean.parquet"].equals(clean["lab_clean.parquet"])
    check_lab_coherence(mutated["lab_clean.parquet"], ana_df=clean["anadata_clean.parquet"])
    validate_clean_tables(mutated)
    assert (
        clean_tables_digest(mutated)["lab_clean.parquet"]
        != (clean_tables_digest(clean)["lab_clean.parquet"])
    )
    with pytest.raises(
        CleanTableError, match=r"lab_clean\.parquet rows do not match the billed lab lines"
    ):
        validate_clean_tables(mutated, built_showcase.tables)


def test_a_result_set_under_the_episode_of_another_patient_is_an_anadata_error(
    lab: pl.DataFrame, ana: pl.DataFrame
) -> None:
    """Moving only the episode of patient 1's CRP set to patient 7's: the episode belongs to patient 7."""
    index = _index_of(lab, 1, "L101850", "CRP (kantitatif)")
    caught = _rejected(_set_cell(lab, index, "basvuru_id", "B-SENTETIK-HASTA-0007-001"), ana)
    _assert_names_the_row(
        caught, lab, rule="anadata", row=index, code="L101850", parameter="CRP (kantitatif)"
    )
    assert str(caught.value).endswith(
        f"the row is for patient {_pid(1)} but anadata_clean has patient {_pid(7)} for the episode"
    )


# --- 3.19 Every numeric state of every billed parameter, for both sexes, against a second reading ------


def _band_from_the_text(abnormal_states: str, state: str, sex: str) -> tuple[float, float] | None:
    """The range of `state` for `sex`, read from the raw CSV text with regular expressions (not the parser).

    None when the state has a range for the other sex only (`copd_polycythemia: M 17.6–20.0` for a woman).
    """
    for item in abnormal_states.split("; "):
        name, rest = item.split(": ", 1)
        if state not in (name, name.split(" (")[0]):
            continue
        rest = re.sub(r"\s*\([^()]*\)\s*$", "", rest)
        rest = re.sub(r"\s+with .*$", "", rest)
        if re.search(r"\b[MF] \d", rest):
            match = re.search(rf"\b{sex} {_NUMBER}–{_NUMBER}", rest)
        else:
            match = re.search(rf"{_NUMBER}\s*(?:–|to)\s*{_NUMBER}", rest)
        return (float(match.group(1)), float(match.group(2))) if match else None
    raise KeyError(state)


def test_every_numeric_parameter_state_and_sex_is_drawn_by_the_documented_formula() -> None:
    """The normal draw (central band of the limits) and the state draw (band 0.20 to 0.80 of the range)."""
    checked = refused = 0
    for spec in load_lab_reference().billed_code_parameters:
        if spec.test_key == "blood_gas_venous" or spec.is_qualitative_strip:
            continue
        for sex in ("M", "F"):
            low, high = spec.ref_limits(sex)
            for k in (1, 2, 3):
                patient_no = (k * 37) % 9000 + 10
                u = _sha_u(patient_no, spec.ek2b_code, spec.result_parameter, k)
                if high is not None:  # the eGFR has no upper limit, so no normal draw
                    raw = (low or 0.0) + (high - (low or 0.0)) * (0.30 + 0.40 * u)
                    expected = round(raw, spec.decimals) if spec.decimals else float(round(raw))
                    got = draw_numeric_value(spec, patient_id=_pid(patient_no), sex=sex, k=k)
                    assert got == expected, (spec.key, sex, k)
                    checked += 1
            for state in spec.parsed_states:
                if state.kind in ("egfr_band", "grade_range", "grade_single"):
                    continue
                band = _band_from_the_text(spec.abnormal_states_raw, state.name, sex)
                for k in (1, 2, 3):
                    patient_no = (k * 53) % 9000 + 10
                    patient = _pid(patient_no)
                    if band is None:  # a state with a range for the other sex only is refused
                        with pytest.raises(LabCoherenceError, match="has no range for sex"):
                            draw_numeric_value(
                                spec, patient_id=patient, sex=sex, k=k, state_id=state.name
                            )
                        refused += 1
                        continue
                    u = _sha_u(patient_no, spec.ek2b_code, spec.result_parameter, k)
                    raw = band[0] + (band[1] - band[0]) * (0.20 + 0.60 * u)
                    expected = round(raw, spec.decimals) if spec.decimals else float(round(raw))
                    got = draw_numeric_value(
                        spec, patient_id=patient, sex=sex, k=k, state_id=state.name
                    )
                    assert got == expected, (spec.key, state.name, sex, k)
                    assert band[0] - 1e-9 <= got <= band[1] + 1e-9, (spec.key, state.name, sex, k)
                    checked += 1
    assert (checked, refused) == (1074, 18)  # the albumin's states and its normal band since S18 bills it


# --- 3.20 Several bills of one patient: the draws, the pins and the order of the rows -----------------
#
# Patient 2 gets a second COPD stay as its fifth bill (a blood gas, its own lab states: none, so every value is normal;
# its committed bills 2 to 4, the control S32, the readmission S33 and the control S34, bill no test),
# patient 3 a pyelonephritis stay of the same age and sex as the patient (the pathway's own showcase age is 86,
# the patient's 77) as its fifth bill (its committed second to fourth bills are S36 to S38), dated BEFORE every
# committed bill of hers, patient 4 a stay one day after its first (the lab days interleave). Nothing here is committed.

_COPD = "copd_exacerbation_pneumonia_ward"
_PYELO = "pyelonephritis_dementia_delirium_ward"
_ALL_NORMAL = {"blood_gas": "arterial", "states": {}, "basis": "judgment", "source": "Test fixture only."}
_CLAIM_2_5, _CLAIM_3_5 = "F-SENTETIK-HASTA-0002-007", "F-SENTETIK-HASTA-0003-005"
# patient 4 has three committed bills (the stay, the control S39, the second visit S40): the extra stay is its fourth
_CLAIM_4_2, _CLAIM_4_4 = "F-SENTETIK-HASTA-0004-002", "F-SENTETIK-HASTA-0004-005"


@pytest.fixture(scope="module")
def extra_bills() -> BuildResult:
    recipes, clinical = with_encounters(
        Extra(2, 7, _COPD, {"admit": "2026-05-11", "story": "S92"}, labs=_ALL_NORMAL),
        Extra(3, 5, _PYELO, {"story": "S93", "age": 77, "sex": "F"}),
        Extra(4, 5, _PYELO, {"admit": "2026-05-12", "story": "S90"}),
    )
    return build_showcase(recipes=recipes, clinical=clinical)


def _record_salts(monkeypatch: pytest.MonkeyPatch) -> list[int]:
    """Every `draw_u` of the generator, with its salt written down (they all go through it)."""
    asked: list[int] = []
    real = labs_module.draw_u

    def recorder(patient_id: str, code: str, parameter: str, k: int, salt: int = 0) -> float:
        asked.append(salt)
        return real(patient_id, code, parameter, k, salt)

    monkeypatch.setattr(labs_module, "draw_u", recorder)
    return asked


@pytest.mark.parametrize(
    ("claim_id", "base"),
    [
        pytest.param("F-SENTETIK-HASTA-0002-001", 0, id="2.1_blood_gas_first_bill"),
        pytest.param(_CLAIM_2_5, 6000, id="2.7_blood_gas"),
        pytest.param("F-SENTETIK-HASTA-0003-001", 0, id="3.1"),
        pytest.param(_CLAIM_3_5, 4000, id="3.5_creatinine"),
        pytest.param("F-SENTETIK-HASTA-0004-001", 0, id="4.1"),
        pytest.param(_CLAIM_4_2, 1000, id="4.2_the_committed_control"),
        pytest.param(_CLAIM_4_4, 4000, id="4.5"),
    ],
)
def test_the_draws_of_a_claim_use_the_salts_of_its_sequence_and_no_others(
    extra_bills: BuildResult, monkeypatch: pytest.MonkeyPatch, claim_id: str, base: int
) -> None:
    claim = next(c for c in extra_bills.claims if c.header.claim_id == claim_id)
    asked = _record_salts(monkeypatch)
    build_lab_clean([claim], clinical=extra_bills.clinical, schema=LAB_CLEAN_SCHEMA)
    assert asked and base in asked  # the first try of a draw is the base itself
    assert set(asked) <= set(range(base, base + 50)), sorted(set(asked))  # and no draw of another claim's salts
    assert labs_module.CLAIM_SALT_STEP >= 50  # the retries of one claim never reach the next claim's salts


@pytest.mark.parametrize(
    "kind",
    ["hemogram", "hemogram_with_a_state", "creatinine", "creatinine_egfr_band", "creatinine_range", "blood_gas"],
)
def test_every_generator_starts_at_the_salt_it_is_given(kind: str, monkeypatch: pytest.MonkeyPatch) -> None:
    ref = load_lab_reference()
    patient = _pid(3)
    creatinine_states = {
        "creatinine_egfr_band": {"L104780|Kreatinin": "ckd_g3a"},
        "creatinine_range": {"L104780|Kreatinin": "sarcopenic_elderly"},
    }

    def draw(salt_base: int) -> dict[str, float]:
        if kind.startswith("hemogram"):
            states = {"L107020|WBC (Lökosit)": "bacterial_infection"} if kind.endswith("state") else {}
            return _generate_hemogram_values(
                ref.by_code["L107020"], patient_id=patient, sex="F", k=1, states_map=states, salt_base=salt_base
            )
        if kind.startswith("creatinine"):
            return _generate_creatinine_and_egfr(
                ref.by_code["L104780"],
                patient_id=patient,
                age=77,
                sex="F",
                k=1,
                states_map=creatinine_states.get(kind, {}),
                egfr_age_bands=ref.egfr_age_bands,
                salt_base=salt_base,
            )
        return _generate_blood_gas_values(
            ref.by_code["L103900"], patient_id=patient, sex="F", k=1, blood_gas_type="arterial", states_map={}, salt_base=salt_base
        )

    asked = _record_salts(monkeypatch)
    at_zero = draw(0)
    assert set(asked) <= set(range(50)) and 0 in asked
    asked.clear()
    at_base = draw(5000)
    assert set(asked) <= set(range(5000, 5050)) and 5000 in asked, sorted(set(asked))
    assert at_base != at_zero  # another claim of the same patient draws other values for the same code


def test_the_lab_rows_of_two_bills_come_out_in_the_order_the_feed_check_states(
    extra_bills: BuildResult, csv_rows: pl.DataFrame
) -> None:
    lab_table = extra_bills.clean_tables["lab_clean.parquet"]
    procs = extra_bills.tables["procedure_claim_lines.parquet"]
    assert _actual_lab_keys(lab_table).equals(_expected_lab_keys(procs, csv_rows))
    # whatever the order the claims are handed over in, the rows come out in that order
    claims = list(extra_bills.claims)
    forward = build_lab_clean(claims, clinical=extra_bills.clinical, schema=LAB_CLEAN_SCHEMA)
    assert forward.equals(lab_table)
    assert build_lab_clean(claims[::-1], clinical=extra_bills.clinical, schema=LAB_CLEAN_SCHEMA).equals(forward)
    # patient 4's two stays (the first and the extra fourth bill) overlap by days, so its rows alternate between the
    # bills: by patient and date
    # (the claim cannot be the order), and a precursor (patient 3's fifth bill, dated before all of hers) comes first
    p4 = lab_table.filter(pl.col("HASTA_ID") == _pid(4))
    assert p4["tarih"].is_sorted()
    episodes = p4["basvuru_id"].to_list()
    assert sum(a != b for a, b in zip(episodes, episodes[1:], strict=False)) > 1
    p3 = lab_table.filter(pl.col("HASTA_ID") == _pid(3))
    assert p3["basvuru_id"][0] == "B-SENTETIK-HASTA-0003-005" and p3["basvuru_id"][-1] == "B-SENTETIK-HASTA-0003-001"


def test_the_lab_values_of_a_second_bill_differ_from_the_first_and_the_first_stays_as_it_was(
    extra_bills: BuildResult, lab: pl.DataFrame
) -> None:
    lab_table = extra_bills.clean_tables["lab_clean.parquet"]
    for patient_no, second in ((3, "B-SENTETIK-HASTA-0003-005"), (4, "B-SENTETIK-HASTA-0004-005")):
        mine = lab_table.filter(pl.col("HASTA_ID") == _pid(patient_no))
        first = mine.filter(pl.col("basvuru_id") != second)
        committed = lab.filter(pl.col("HASTA_ID") == _pid(patient_no))
        assert first.equals(committed), patient_no  # adding a bill moves nothing of the first one
        key = ["SUB_CODE", "parametre"]
        paired = (
            first.select(*key, "sonuc_sayisal")
            .join(mine.filter(pl.col("basvuru_id") == second).select(*key, "sonuc_sayisal"), on=key, suffix="_2nd")
            .drop_nulls()
            .unique(subset=key)
        )
        assert paired.height > 0 and (paired["sonuc_sayisal"] != paired["sonuc_sayisal_2nd"]).any(), patient_no


def test_a_bill_has_the_lab_states_of_its_own_entry(extra_bills: BuildResult, lab: pl.DataFrame) -> None:
    """Patient 2's first stay has a bacterial WBC; the extra stay (its fifth bill) has no states, so its WBC rows are normal."""
    lab_table = extra_bills.clean_tables["lab_clean.parquet"]
    wbc = lab_table.filter((pl.col("HASTA_ID") == _pid(2)) & (pl.col("parametre") == "WBC (Lökosit)"))
    by_bill = {
        episode: rows["anormal_mi"].to_list() for (episode,), rows in wbc.group_by("basvuru_id", maintain_order=True)
    }
    assert any(by_bill["B-SENTETIK-HASTA-0002-001"]) and not any(by_bill["B-SENTETIK-HASTA-0002-007"])
    for later in ("002", "003", "004"):  # the control (S32), the readmission (S33) and its control (S34) bill no test
        assert f"B-SENTETIK-HASTA-0002-{later}" not in by_bill
    # blood gas: the entry says arterial for the second stay too, so the set is there
    assert lab_table.filter(pl.col("basvuru_id") == "B-SENTETIK-HASTA-0002-007")["SUB_CODE"].is_in(["L103900"]).any()


def test_a_later_bill_of_another_pathway_is_judged_at_the_age_of_its_pins(extra_bills: BuildResult) -> None:
    """Patient 3 is 77; the pathway of its extra fifth bill has an 86-year-old showcase patient, the pins say 77."""
    lab_table = extra_bills.clean_tables["lab_clean.parquet"]
    rows = lab_table.filter(pl.col("basvuru_id") == "B-SENTETIK-HASTA-0003-005")
    creatinine = rows.filter(pl.col("parametre") == "Kreatinin")["sonuc_sayisal"].to_list()
    egfr = rows.filter(pl.col("parametre") == _EGFR)["sonuc_sayisal"].to_list()
    assert creatinine and len(creatinine) == len(egfr)
    assert egfr == [float(round(ckd_epi_2021(scr, 77, "F"))) for scr in creatinine]
    assert egfr != [float(round(ckd_epi_2021(scr, 86, "F"))) for scr in creatinine]  # the pathway's age would differ
    ana = extra_bills.clean_tables["anadata_clean.parquet"].filter(pl.col("HASTA_ID") == _pid(3))
    assert dict(zip(ana["SQ_EPISODE"], ana["TANI_YASI"], strict=True)) == {
        "B-SENTETIK-HASTA-0003-001": 77,
        "B-SENTETIK-HASTA-0003-002": 77,  # the committed S36, S37 and S38
        "B-SENTETIK-HASTA-0003-003": 77,
        "B-SENTETIK-HASTA-0003-004": 77,
        "B-SENTETIK-HASTA-0003-005": 77,  # the extra
    }
    claim = next(c for c in extra_bills.claims if c.header.claim_id == _CLAIM_3_5)
    assert claim.pins is not None and (claim.pins.age, claim.pins.sex) == (77, "F")


def test_a_mapping_keyed_by_patient_number_names_the_first_encounter_only(extra_bills: BuildResult) -> None:
    """The old form of the argument still works for a one-bill patient; for a patient with two it is the first."""
    by_number = {p.patient_no: p for p in extra_bills.clinical.patients if p.encounter_no == 1}
    by_pair = {(p.patient_no, p.encounter_no): p for p in extra_bills.clinical.patients}
    claims = extra_bills.claims
    a = build_lab_clean(claims, clinical=by_pair, schema=LAB_CLEAN_SCHEMA)
    assert a.equals(extra_bills.clean_tables["lab_clean.parquet"])
    # patient 2's extra stay (its third bill) has no entry in this form, and a billed blood gas without one is refused
    with pytest.raises(LabCoherenceError, match="blood_gas"):
        build_lab_clean(claims, clinical=by_number, schema=LAB_CLEAN_SCHEMA)
    # for a patient with one bill the two forms are the same thing (patients 1 and 9 bill tests on their one bill)
    one_bill = [c for c in claims if c.header.patient_id in {_pid(1), _pid(9)}]
    assert build_lab_clean(one_bill, clinical=by_number, schema=LAB_CLEAN_SCHEMA).equals(
        build_lab_clean(one_bill, clinical=by_pair, schema=LAB_CLEAN_SCHEMA)
    )


def test_the_albumin_of_s18_lies_at_or_under_the_sut_infusion_threshold(lab: pl.DataFrame) -> None:
    """S18's albumin is billed (L100320) on the admission day in the state `cirrhosis_at_infusion_threshold` (1.8 to
    2.5 g/dl), so the value always satisfies SUT 4.2.27.Ç.(1) (C006389: albumin at 2.5 g/dl or less)."""
    albumin = lab.filter(pl.col("SUB_CODE") == "L100320")
    assert albumin["HASTA_ID"].to_list() == ["SENTETIK-HASTA-0015"]
    assert albumin["basvuru_id"].to_list() == ["B-SENTETIK-HASTA-0015-001"]
    (value,) = albumin["sonuc_sayisal"].to_list()
    assert 1.8 <= value <= 2.5 and albumin["anormal_mi"].to_list() == [True]
