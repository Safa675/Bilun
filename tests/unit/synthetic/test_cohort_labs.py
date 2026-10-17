"""Unit and mutation tests for `scripts/synthetic/cohort/labs.py` and the `lab_clean.parquet` it makes.

The reference reader, the feed coverage per episode (with the real `detect_lab_capture_gaps`), the
value bands, the coherence rules R1 to R5, the table structure, the generator errors, determinism and
the loaders. Each rule has an in-memory mutation that makes its check fail: the tests copy frames
and never touch a tracked file.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
import dataclasses
import hashlib
import json
from pathlib import Path
import re
import shutil
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
    prove_showcase,
    validate_clean_tables,
)
from scripts.synthetic.cohort.build import DEFAULT_OUT_DIR, main
from scripts.synthetic.cohort.clinical import PatientLabs
from scripts.synthetic.cohort.engine_proof import load_showcase_dataset
from scripts.synthetic.cohort.labs import (
    BILLED_LAB_CODES,
    _egfr_normal_band_for_age,
    _generate_creatinine_and_egfr,
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
from src.bilun.cache.context import load_sut_build_context
from src.bilun.cache.data_loader import load_anadata, load_labdata, load_recete
from src.bilun.cache.loaders import _normalize_lab, load_normalized_raw_data
import src.bilun.domain.claims.config as claims_config
from src.bilun.domain.claims.loader import load_sut_claim_dataset
from src.bilun.domain.prose_rules.lab_capture_gap import detect_lab_capture_gaps

pytestmark = pytest.mark.unit

_REPO = Path(__file__).resolve().parents[3]
_SHOWCASE_DIR = DEFAULT_OUT_DIR
_CLAIMS_DIR = _SHOWCASE_DIR / "sut" / "claims"
_CLEAN_DIR = _SHOWCASE_DIR / "sut" / "clean"
_LAB_PARQUET = _CLEAN_DIR / "lab_clean.parquet"
_REGISTRY_JSON_PATH = _SHOWCASE_DIR / "cohort_registry.json"
_LAB_CSV = _REPO / "data" / "synthetic" / "reference" / "lab_reference.csv"

_ANON_RE = re.compile(r"anon_|\banon[\s-]*[0-9]", re.IGNORECASE)
_CURRENCY_RE = re.compile(
    r"(?=[0-9.,]*[1-9])[0-9][0-9.,]*\s*(?:TL|TRY|₺)(?![A-Za-z])|₺\s*(?=[0-9.,]*[1-9])[0-9][0-9.,]*",
    re.IGNORECASE,
)

# The 14 lab codes billed in the 8 claims and the number of result parameters of each.
_PARAMETER_COUNTS: dict[str, int] = {
    "L100300": 1,  # ALT
    "L101280": 1,  # AST
    "L101850": 1,  # CRP
    "L102090": 1,  # D-dimer
    "L102890": 1,  # glucose
    "L103900": 10,  # arterial blood gas
    "L104780": 2,  # creatinine and the derived eGFR
    "L106150": 1,  # potassium
    "L106240": 1,  # procalcitonin
    "L106910": 1,  # sodium
    "L107010": 10,  # urinalysis: 2 numeric, 6 strips, 2 microscopy
    "L107020": 15,  # hemogram
    "L107360": 1,  # troponin I
    "L107420": 1,  # urea
}
_ROWS_PER_PATIENT: dict[int, int] = {1: 16, 2: 59, 3: 17, 4: 52, 6: 40, 7: 23}
_PATIENTS: dict[int, tuple[str, int]] = {
    1: ("M", 34),
    2: ("M", 81),
    3: ("F", 77),
    4: ("F", 86),
    5: ("F", 84),
    6: ("M", 79),
    7: ("F", 58),
    8: ("F", 47),
}

# Decimals of every parameter of the 14 codes: the most decimals among the limits and the state
# numbers of the CSV rows, at most 3 (eGFR bands do not count).
_DECIMALS: dict[str, int] = {
    "L100300|ALT": 0,
    "L101280|AST": 0,
    "L101850|CRP (kantitatif)": 0,
    "L102090|D-dimer": 0,
    "L102890|Glukoz": 0,
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
def _allow_showcase_synthetic_claims_dir(monkeypatch: pytest.MonkeyPatch) -> None:
    """Allow `load_sut_claim_dataset` and `load_sut_build_context` in `synthetic_demo` mode to read showcase."""
    monkeypatch.setattr(claims_config, "SYNTHETIC_SUT_DIR", _SHOWCASE_DIR / "sut")
    monkeypatch.setattr(
        claims_config, "DEFAULT_SYNTHETIC_CLEAN_DIR", _SHOWCASE_DIR / "sut" / "clean"
    )
    load_sut_claim_dataset.cache_clear()
    yield
    load_sut_claim_dataset.cache_clear()


@pytest.fixture(scope="module")
def built_showcase() -> BuildResult:
    return build_showcase()


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


def test_reference_has_the_14_billed_codes_with_their_parameter_counts(procs: pl.DataFrame) -> None:
    ref = load_lab_reference()
    billed = set(procs.filter(pl.col("procedure_category") == "laboratuvar")["procedure_code"])
    assert billed == set(_PARAMETER_COUNTS) == set(BILLED_LAB_CODES)
    assert {code: len(ref.by_code[code]) for code in billed} == _PARAMETER_COUNTS
    assert len(ref.by_code) == 49  # every code of the CSV, not only the billed ones
    assert sum(_PARAMETER_COUNTS.values()) == 47
    # The venous variant shares the code L103900 and is not read as a second set of parameters.
    assert len(ref.billed_code_parameters) == 57
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
    assert raw.height == len(ref.billed_code_parameters) == 57
    texts = raw["abnormal_states"].fill_null("").to_list()
    total_items = 0
    for spec, text in zip(ref.billed_code_parameters, texts, strict=True):
        items = [item for item in text.split("; ") if item.strip()]
        accounted = [s.raw_text for s in spec.parsed_states] + [
            u.raw_text for u in spec.unsupported_states
        ]
        assert sorted(accounted) == sorted(items), spec.key
        total_items += len(items)
    assert total_items == 174


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
    assert len(episodes) == 8
    billed = _codes_by_episode(_billed_lab_lines(procs), "episode_id", "procedure_code")
    fed = _codes_by_episode(lab, "basvuru_id", "SUB_CODE")
    for episode in episodes:
        assert fed.get(episode, []) == billed.get(episode, []), episode
    # Patients 5 and 8 are package bills: no billed lab line, so no lab row either.
    for patient_no in (5, 8):
        assert _pid(patient_no) not in set(
            procs.filter(pl.col("procedure_category") == "laboratuvar")["patient_id"]
        )
        assert lab.filter(pl.col("HASTA_ID") == _pid(patient_no)).is_empty()
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
    # Serial troponin I: two billed lines on one day, two result sets.
    troponin = both.filter(pl.col("SUB_CODE") == "L107360")
    assert troponin.select("billed_lines", "result_sets").rows() == [(2, 2)]


def test_the_table_is_the_billed_lines_times_their_csv_parameters(
    lab: pl.DataFrame, procs: pl.DataFrame, csv_rows: pl.DataFrame
) -> None:
    expected = _expected_lab_keys(procs, csv_rows)
    assert _actual_lab_keys(lab).equals(expected)
    assert lab.height == expected.height == 207
    # The same total from the application of the reference to the billed codes.
    assert expected_lab_row_count(_billed_lab_lines(procs)["procedure_code"].to_list()) == 207
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
    assert len(claims_dataset.claims) == 8
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
    # Every (episode, code) pair billed exactly once was tried: 2 + 6 + 2 + 7 + 7 + 6 pairs.
    once = _billed_lab_lines(procs).group_by("episode_id", "procedure_code").len()
    assert checked == once.filter(pl.col("len") == 1).height == 30


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
    """The YAML states as one row per (patient, key): the entry list (a scalar is a list of one)."""
    rows = [
        {
            "HASTA_ID": _pid(patient["patient_no"]),
            "key": key,
            "entries": [entry] if isinstance(entry, str) else list(entry),
        }
        for patient in clinical_raw["patients"]
        for key, entry in ((patient.get("labs") or {}).get("states") or {}).items()
    ]
    return pl.DataFrame(
        rows, schema={"HASTA_ID": pl.String, "key": pl.String, "entries": pl.List(pl.String)}
    )


@pytest.fixture(scope="module")
def annotated(
    lab: pl.DataFrame, csv_rows: pl.DataFrame, clinical_raw: dict[str, Any]
) -> pl.DataFrame:
    """Every lab row with its occurrence k, the state the YAML asks for and its sex-specific limits."""
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
        pl.min_horizontal(pl.col("k").cast(pl.Int64), pl.col("entries").list.len().cast(pl.Int64))
        - 1
    )
    return (
        lab.with_row_index("row")
        .join(first, on="SUB_CODE", how="left")
        .with_columns(
            (pl.col("parametre") == pl.col("first_parameter"))
            .cast(pl.Int64)
            .cum_sum()
            .over(["HASTA_ID", "SUB_CODE"])
            .alias("k"),
            (pl.col("SUB_CODE") + "|" + pl.col("parametre")).alias("key"),
            _day().alias("day"),
        )
        .join(_state_schedule(clinical_raw), on=["HASTA_ID", "key"], how="left")
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
        == "ckd_g3a"
    )
    assert (_pid(2), "L103900|pH", 2) not in got  # the second entry is `normal`
    assert got[(_pid(2), "L103900|pO2", 2)] == "chronic_copd_room_air"
    assert {h for h, _, _ in got} == {_pid(n) for n in (1, 2, 3, 4, 6, 7)}


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
    # 201 numeric rows = 86 derived + 22 drawn from a state + 93 drawn without one.
    assert rows.height == 93


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
    assert rows.height == 22  # numeric rows drawn from a state band
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
    assert sets.height == scr.height == egfr.height == 6  # 2 + 1 + 1 + 1 + 1 days of creatinine
    band_lo = pl.lit(None, dtype=pl.Float64)
    band_hi = pl.lit(None, dtype=pl.Float64)
    for age_lo, age_hi, e_lo, e_hi in reversed(_egfr_age_bands(csv_rows)):
        in_band = pl.col("age").is_between(age_lo, age_hi)
        band_lo = pl.when(in_band).then(pl.lit(e_lo)).otherwise(band_lo)
        band_hi = pl.when(in_band).then(pl.lit(e_hi)).otherwise(band_hi)
    sets = sets.with_columns(band_lo.alias("band_lo"), band_hi.alias("band_hi"))

    normal = sets.filter(pl.col("state") == "normal")
    assert normal.height == 4
    # A normal creatinine stays inside its sex-specific limits and its eGFR inside the age band.
    assert normal.filter((pl.col("scr") < pl.col("lo")) | (pl.col("scr") > pl.col("hi"))).is_empty()
    assert normal.filter(
        (pl.col("egfr") < pl.col("band_lo")) | (pl.col("egfr") > pl.col("band_hi"))
    ).is_empty()
    # `ckd_g3a` is the eGFR band 45 to 59 of the CSV, for both days of patient 4.
    stage = sets.filter(pl.col("state") != "normal")
    assert stage.select("HASTA_ID", "state").unique().rows() == [(_pid(4), "ckd_g3a")]
    assert stage.height == 2
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
    assert derived.height == 27
    # Without a state on HGB, MCV or MCH, the derived values are normal values.
    assert derived.filter(~pl.col("driver_state") & ~inside).is_empty()
    # With one (patient 3, postoperative HGB) a derived value may sit in one of its own state ranges.
    with_state = derived.filter(pl.col("driver_state") & ~inside)
    assert with_state["HASTA_ID"].unique().to_list() == [_pid(3)]
    for row in with_state.select("sonuc_sayisal", "abnormal_states", "sex").to_dicts():
        ranges = _state_ranges(row["abnormal_states"], row["sex"])
        assert any(lo <= row["sonuc_sayisal"] <= hi for lo, hi in ranges), row
    assert with_state["parametre"].to_list() == ["RBC (Eritrosit)", "HCT (Hematokrit)"]


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
    assert sets.height == 9
    assert sorted(sets["profile"].to_list()) == (
        ["bacterial_infection"] * 4 + ["normal"] * 4 + ["steroid_use"]
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
    assert normal.height == 20
    assert normal.filter(
        (pl.col("sonuc_sayisal") < pl.col("lo")) | (pl.col("sonuc_sayisal") > pl.col("hi"))
    ).is_empty()


def test_strips_are_negative_unless_the_yaml_asks_for_a_grade(annotated: pl.DataFrame) -> None:
    strips = annotated.filter(pl.col("sonuc_nitel").is_not_null())
    assert strips.height == 6  # one urinalysis, patient 4 on 2026-05-11
    assert strips.select("HASTA_ID", "day").unique().rows() == [(_pid(4), "2026-05-11")]
    plain = strips.filter(pl.col("state") == "normal")
    assert plain["sonuc_nitel"].to_list() == ["Negatif"] * 3  # glucose, ketone, blood
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
    assert rows.height == 2  # the single urinalysis, patient 4 on 2026-05-11
    assert ((rows["sonuc_sayisal"] % 1) == 0).all()
    erythrocytes = rows.filter(pl.col("parametre") == "Mikroskopi: eritrosit")
    assert (
        erythrocytes.filter(pl.col("sonuc_sayisal").is_between(pl.col("lo"), pl.col("hi"))).height
        == 1
    )


def test_no_numeric_value_is_nan_or_infinite(lab: pl.DataFrame) -> None:
    numeric = lab.filter(pl.col("sonuc_nitel").is_null())
    assert numeric.height == 201
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
    assert hemograms.height == 9
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
    assert sets.height == 6
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


# (id, patient, date, code, parameter, change, message). The changed value keeps its `anormal_mi`
# flag right, so only the derivation rule can notice.
_DERIVATION_MUTATIONS = [
    pytest.param(
        2, "2026-03-09", "L107020", "NEU# (Nötrofil)", 1.0, r"R1", id="R1_neutrophil_count"
    ),
    pytest.param(2, "2026-03-09", "L107020", "RBC (Eritrosit)", 0.5, r"R2.*RBC", id="R2_rbc"),
    pytest.param(2, "2026-03-09", "L107020", "HCT (Hematokrit)", 5.0, r"R2.*HCT", id="R2_hct"),
    pytest.param(2, "2026-03-09", "L107020", "MCHC", 2.0, r"R2.*MCHC", id="R2_mchc"),
    pytest.param(7, "2026-02-19", "L104780", _EGFR, 10.0, r"R3.*eGFR", id="R3_egfr"),
    pytest.param(2, "2026-03-09", "L103900", "HCO3", 3.0, r"R4.*HCO3", id="R4_hco3"),
    pytest.param(
        2, "2026-03-09", "L103900", "BE (baz fazlası)", 2.0, r"R4.*BE", id="R4_base_excess"
    ),
    pytest.param(2, "2026-03-09", "L103900", "SaO2", 3.0, r"R4.*SaO2", id="R4_sao2"),
]


@pytest.mark.parametrize(
    ("patient_no", "date", "code", "parameter", "change", "message"), _DERIVATION_MUTATIONS
)
def test_mutation_a_changed_derived_value_breaks_its_rule(
    lab: pl.DataFrame,
    ana: pl.DataFrame,
    patient_no: int,
    date: str,
    code: str,
    parameter: str,
    change: float,
    message: str,
) -> None:
    index = _index_of(lab, patient_no, code, parameter, date=date)
    mutated = _set_cell(lab, index, "sonuc_sayisal", lab["sonuc_sayisal"][index] + change)
    with pytest.raises(LabCoherenceError, match=message):
        check_lab_coherence(mutated, ana_df=ana)


# --- 3.5 anormal_mi (R5) --------------------------------------------------------------------------


def test_r5_anormal_mi_is_below_ref_alt_or_above_ref_ust_or_a_strip_other_than_negatif(
    lab: pl.DataFrame,
) -> None:
    numeric = lab.filter(pl.col("sonuc_nitel").is_null())
    below = pl.col("sonuc_sayisal") < pl.col("ref_alt")
    above = pl.col("sonuc_sayisal") > pl.col("ref_ust")
    expected = below.fill_null(False) | above.fill_null(False)
    assert numeric.filter(pl.col("anormal_mi") != expected).is_empty()
    strips = lab.filter(pl.col("sonuc_nitel").is_not_null())
    not_negative = pl.col("sonuc_nitel") != "Negatif"
    assert strips.filter(pl.col("anormal_mi") != not_negative).is_empty()
    # Both outcomes occur, so the test is not vacuous: 40 numeric rows and 3 strips are abnormal.
    abnormal_numeric = numeric.select(expected.sum()).item()
    abnormal_strips = strips.filter(not_negative).height
    assert (abnormal_numeric, abnormal_strips) == (40, 3)
    assert lab["anormal_mi"].sum() == 43
    assert 0 < lab["anormal_mi"].sum() < lab.height == 207


def test_troponin_i_uses_the_sex_specific_limit_of_the_csv(
    lab: pl.DataFrame, csv_rows: pl.DataFrame
) -> None:
    troponin = csv_rows.filter(pl.col("ek2b_code") == "L107360")
    assert (troponin["ref_high_male"][0], troponin["ref_high_female"][0]) == (34.2, 15.6)
    rows = lab.filter(pl.col("SUB_CODE") == "L107360")
    assert rows["HASTA_ID"].unique().to_list() == [_pid(7)]  # a woman
    assert rows["ref_ust"].to_list() == [15.6, 15.6] and rows["ref_alt"].to_list() == [0.0, 0.0]
    assert rows["anormal_mi"].to_list() == [False, False]
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
    with pytest.raises(LabCoherenceError, match=message):
        check_lab_coherence(mutated, ana_df=ana)


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
    assert annotated.filter(pl.col("donem") != pl.col("tarih").dt.year().cast(pl.String)).is_empty()
    assert annotated.filter(pl.col("tarih") != pl.col("tarih").dt.truncate("1d")).is_empty()
    # The episode is the claim's episode.
    headers = built_showcase.tables["claim_headers.parquet"].select(
        pl.col("patient_id").alias("HASTA_ID"), pl.col("episode_id").alias("episode")
    )
    joined = annotated.join(headers, on="HASTA_ID", how="left")
    assert joined.filter(pl.col("basvuru_id") != pl.col("episode")).is_empty()
    # The body system: hemogram and D-dimer are haematology, everything else biochemistry.
    expected_system = (
        pl.when(pl.col("SUB_CODE").is_in(["L107020", "L102090"]))
        .then(pl.lit("Hematoloji"))
        .otherwise(pl.lit("Biyokimya"))
    )
    assert annotated.filter(pl.col("organ_sistemi") != expected_system).is_empty()
    assert set(annotated["organ_sistemi"]) == {"Hematoloji", "Biyokimya"}
    # The unit is the CSV unit (empty where it is empty).
    assert annotated.filter(pl.col("birim") != pl.col("csv_unit")).is_empty()
    # Numeric rows carry the sex-specific CSV limits; qualitative rows carry none.
    numeric = annotated.filter(pl.col("sonuc_nitel").is_null())
    strips = annotated.filter(pl.col("sonuc_nitel").is_not_null())
    assert numeric.filter(
        pl.col("ref_alt").ne_missing(pl.col("raw_lo")) | pl.col("ref_ust").ne_missing(pl.col("hi"))
    ).is_empty()
    assert strips.filter(
        pl.col("sonuc_sayisal").is_not_null()
        | (pl.col("birim") != "")
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


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        pytest.param(_swap_two_hemogram_rows, r"result set", id="swap_two_rows"),
        pytest.param(_drop_a_middle_row, r"result set", id="drop_a_row_inside_a_set"),
        pytest.param(_drop_the_last_row_of_a_set, r"result set", id="drop_the_last_row_of_a_set"),
        pytest.param(_repeat_a_row, r"result set", id="repeat_a_row"),
        pytest.param(
            _add_an_unknown_parameter, r"unknown parameter", id="add_an_unknown_parameter"
        ),
        pytest.param(
            _move_a_row_to_another_code, r"unknown parameter", id="parameter_under_the_wrong_code"
        ),
    ],
)
def test_mutation_a_broken_result_set_is_rejected(
    lab: pl.DataFrame,
    ana: pl.DataFrame,
    mutate: Callable[[pl.DataFrame], pl.DataFrame],
    message: str,
) -> None:
    with pytest.raises(LabCoherenceError, match=message):
        check_lab_coherence(mutate(lab), ana_df=ana)


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
        if patient.patient_no == patient_no:
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
        if patient.patient_no == patient_no:
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
    assert _build(built_showcase, load_clinical()).height == 207
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
    # The two serial lines are the two last billed lines of the claim, in line-id order.
    lines = built_showcase.tables["procedure_claim_lines.parquet"].filter(
        (pl.col("patient_id") == _pid(7)) & (pl.col("procedure_code") == "L107360")
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
    assert registry["clean_counts"]["lab_clean.parquet"] == lab.height == 207
    assert (
        registry["clean_tables_digest"]["lab_clean.parquet"]
        == clean_tables_digest(
            {name: pl.read_parquet(_CLEAN_DIR / name) for name in CLEAN_TABLE_FILES}
        )["lab_clean.parquet"]
    )


def test_two_cli_builds_write_the_same_lab_bytes(tmp_path: Path) -> None:
    assert main(["--out", str(tmp_path / "a")]) == 0
    assert main(["--out", str(tmp_path / "b")]) == 0
    a = (tmp_path / "a" / "sut" / "clean" / "lab_clean.parquet").read_bytes()
    b = (tmp_path / "b" / "sut" / "clean" / "lab_clean.parquet").read_bytes()
    assert a == b == _LAB_PARQUET.read_bytes()


def test_mutation_check_exits_1_when_a_lab_value_or_the_lab_count_changes(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], lab: pl.DataFrame
) -> None:
    copy_dir = tmp_path / "showcase_copy"
    shutil.copytree(_SHOWCASE_DIR, copy_dir)
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
    assert raw.height == 207
    _, lab_df, _ = load_normalized_raw_data(
        load_anadata_fn=lambda include_text=True: load_anadata(
            path=_CLEAN_DIR / "anadata_clean.parquet", include_text=include_text
        ),
        load_labdata_fn=lambda: load_labdata(path=_LAB_PARQUET),
        load_recete_fn=lambda: load_recete(path=_CLEAN_DIR / "recete_clean.parquet"),
    )
    assert lab_df.height == 207
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
    assert lab_df["value"].null_count() == 6


def test_the_full_build_context_runs_and_no_report_has_a_lab_capture_gap() -> None:
    context = load_sut_build_context(
        billing_workers=1,
        sut_data_mode="synthetic_demo",
        sut_claims_dir=_CLAIMS_DIR,
        sut_clean_dir=_CLEAN_DIR,
    )
    assert context["lab_df_pl"].height == 207
    reports = context["billing_reports"]
    assert sorted(reports) == [_pid(n) for n in range(1, 9)]
    for patient_id, report in reports.items():
        gap = report.procedure_capture_gap
        assert gap.exactness_status == "exact", patient_id
        assert [o for o in gap.opportunities if o.get("source") == "lab"] == [], patient_id
    # Patient 7's one capture gap is the unbilled CT angiography of the S7 fault, from PACS.
    seven = reports[_pid(7)].procedure_capture_gap.opportunities
    assert [(o["source"], o["procedure_code"]) for o in seven] == [("pacs", "R101450")]


def test_the_engine_proof_over_the_committed_files_reports_no_mismatch(
    built_showcase: BuildResult,
) -> None:
    proofs = prove_showcase(built_showcase, dataset=load_showcase_dataset(_CLAIMS_DIR))
    assert len(proofs) == 8
    assert [sp.mismatches for sp in proofs] == [()] * 8


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


# A change far too small for the old tolerances (1.0 for HCO3, 0.5 for MCHC, 1.0 for eGFR), and bigger
# than the rounding of the printed decimals. The flag of the changed row stays right.
@pytest.mark.parametrize(
    ("patient_no", "date", "code", "parameter", "change", "message"),
    [
        pytest.param(2, "2026-03-09", "L107020", "NEU# (Nötrofil)", 0.1, r"R1", id="R1_0.1"),
        pytest.param(
            2, "2026-03-09", "L107020", "RBC (Eritrosit)", 0.2, r"R2.*RBC", id="R2_rbc_0.2"
        ),
        pytest.param(
            2, "2026-03-09", "L107020", "HCT (Hematokrit)", 1.5, r"R2.*HCT", id="R2_hct_1.5"
        ),
        pytest.param(2, "2026-03-09", "L107020", "MCHC", 0.2, r"R2.*MCHC", id="R2_mchc_0.2"),
        pytest.param(7, "2026-02-19", "L104780", _EGFR, 2.0, r"R3.*eGFR", id="R3_egfr_2"),
        pytest.param(2, "2026-03-09", "L103900", "HCO3", 0.2, r"R4.*HCO3", id="R4_hco3_0.2"),
        pytest.param(
            2, "2026-03-09", "L103900", "BE (baz fazlası)", 0.2, r"R4.*BE", id="R4_be_0.2"
        ),
        pytest.param(2, "2026-03-09", "L103900", "SaO2", 0.2, r"R4.*SaO2", id="R4_sao2_0.2"),
    ],
)
def test_mutation_a_small_change_of_a_derived_value_is_caught(
    lab: pl.DataFrame,
    ana: pl.DataFrame,
    patient_no: int,
    date: str,
    code: str,
    parameter: str,
    change: float,
    message: str,
) -> None:
    index = _index_of(lab, patient_no, code, parameter, date=date)
    mutated = _set_cell(lab, index, "sonuc_sayisal", lab["sonuc_sayisal"][index] + change)
    with pytest.raises(LabCoherenceError, match=message):
        check_lab_coherence(mutated, ana_df=ana)


def test_mutation_a_change_of_a_driver_value_is_caught_at_the_derived_value(
    lab: pl.DataFrame, ana: pl.DataFrame
) -> None:
    """HGB, MCV, MCH, pH, pCO2, pO2 and the creatinine are the inputs: moving one breaks its output."""
    cases = [
        (2, "L107020", "HGB (Hemoglobin)", 1.0, r"R2.*RBC"),
        (2, "L107020", "MCH", 2.0, r"R2.*RBC"),
        (2, "L107020", "MCV", 5.0, r"R2.*HCT"),
        (2, "L103900", "pCO2", 3.0, r"R4.*HCO3"),
        (2, "L103900", "pO2", 5.0, r"R4.*SaO2"),
        (7, "L104780", "Kreatinin", 0.2, r"R3.*eGFR"),
    ]
    for patient_no, code, parameter, change, message in cases:
        index = _index_of(lab, patient_no, code, parameter, nth=0)
        value = lab["sonuc_sayisal"][index] + change
        mutated = _set_cell(lab, index, "sonuc_sayisal", value)
        # Keep the flag of the changed row right, so that only the derivation can notice.
        low, high = lab["ref_alt"][index], lab["ref_ust"][index]
        flag = (low is not None and value < low) or (high is not None and value > high)
        mutated = _set_cell(mutated, index, "anormal_mi", bool(flag))
        with pytest.raises(LabCoherenceError, match=message):
            check_lab_coherence(mutated, ana_df=ana)


def test_mutation_the_limits_must_be_the_sex_specific_ones_of_the_csv(
    lab: pl.DataFrame, ana: pl.DataFrame
) -> None:
    index = _index_of(lab, 7, "L107360", "hs-Troponin I", nth=0)
    male_limit = _set_cell(lab, index, "ref_ust", 34.2)  # the value 4.9 stays normal either way
    with pytest.raises(
        LabCoherenceError,
        match=r"R5 at row .*the limits \[0.0, 34.2\] are not the sex-specific limits \[0.0, 15.6\]",
    ):
        check_lab_coherence(male_limit, ana_df=ana)
    check_lab_coherence(male_limit)  # without the age and sex of the episode this cannot be seen
    low_limit = _set_cell(lab, _index_of(lab, 7, "L106150", "Potasyum"), "ref_alt", 3.4)
    with pytest.raises(LabCoherenceError, match=r"R5 at row .*sex-specific limits"):
        check_lab_coherence(low_limit, ana_df=ana)
    # An episode without an anadata row has no sex: its limits cannot be checked, so it is an error.
    other_episodes = ana.filter(pl.col("SQ_EPISODE") != "B-SENTETIK-HASTA-0001-001")
    with pytest.raises(LabCoherenceError, match=r"R5 at row .*no anadata row"):
        check_lab_coherence(lab, ana_df=other_episodes)


def test_mutation_the_unit_must_be_the_csv_unit(lab: pl.DataFrame, ana: pl.DataFrame) -> None:
    index = _index_of(lab, 2, "L102890", "Glukoz")
    with pytest.raises(
        LabCoherenceError, match=r"R6 at row .*unit mmol/L differs from the CSV unit mg/dL"
    ):
        check_lab_coherence(_set_cell(lab, index, "birim", "mmol/L"), ana_df=ana)
    ph = _index_of(lab, 2, "L103900", "pH", date="2026-03-09")  # the blood-gas pH has no unit
    with pytest.raises(
        LabCoherenceError, match=r"R6 at row .*unit mmHg differs from the CSV unit $"
    ):
        check_lab_coherence(_set_cell(lab, ph, "birim", "mmHg"), ana_df=ana)


def test_mutation_one_result_set_cannot_mix_patients_episodes_or_dates(
    lab: pl.DataFrame, ana: pl.DataFrame
) -> None:
    index = _index_of(lab, 2, "L107020", "MCV", date="2026-03-09")
    moved_day = _set_cell(lab, index, "tarih", datetime(2026, 3, 10))
    with pytest.raises(
        LabCoherenceError, match=r"result set at row .*mixes patients, episodes or dates"
    ):
        check_lab_coherence(moved_day, ana_df=ana)
    other_episode = _set_cell(lab, index, "basvuru_id", "B-SENTETIK-HASTA-0007-001")
    with pytest.raises(
        LabCoherenceError, match=r"result set at row .*mixes patients, episodes or dates"
    ):
        check_lab_coherence(other_episode, ana_df=ana)
    other_patient = _set_cell(lab, index, "HASTA_ID", _pid(7))
    with pytest.raises(
        LabCoherenceError, match=r"result set at row .*mixes patients, episodes or dates"
    ):
        check_lab_coherence(other_patient, ana_df=ana)


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
        "position",
        "n_params",
    ]
    assert table.height == 86  # 96 CSV rows minus the 10 of the venous blood gas
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
    assert keys.height == 207
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
            r"208 rows for 207 expected; 1 unexpected, first SENTETIK-HASTA-0005 B-SENTETIK-HASTA-0005-001 2026-02-19 L102890\|Glukoz",
            id="extra_row",
        ),
        pytest.param(
            _remove_a_whole_result_set,
            r"206 rows for 207 expected; 1 missing, first SENTETIK-HASTA-0001 B-SENTETIK-HASTA-0001-001 2026-07-15 L101850\|CRP \(kantitatif\)",
            id="missing_result_set",
        ),
        pytest.param(
            _move_a_result_set_one_day,
            r"1 missing, first .* 2026-07-15 L101850.*1 unexpected, first .* 2026-07-16 L101850",
            id="wrong_date",
        ),
        pytest.param(
            _move_a_result_set_to_another_episode,
            r"1 missing, first SENTETIK-HASTA-0001 B-SENTETIK-HASTA-0001-001 .*1 unexpected, first SENTETIK-HASTA-0001 B-SENTETIK-HASTA-0007-001",
            id="wrong_episode",
        ),
        pytest.param(
            _put_the_crp_set_after_the_hemogram,
            r"207 rows for 207 expected; the rows are in a different order",
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
        match=r"206 rows for 207 expected; 1 missing, first .* L107360\|hs-Troponin I",
    ):
        validate_clean_tables(mutated, built_showcase.tables)
    duplicated = pl.concat([lab, lab.slice(second, 1)])
    with pytest.raises(CleanTableError, match=r"1 unexpected"):
        validate_clean_tables({**clean, "lab_clean.parquet": duplicated}, built_showcase.tables)


def test_the_readme_describes_the_rules_the_code_implements() -> None:
    readme = (_SHOWCASE_DIR / "README.md").read_text(encoding="utf-8")
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
        "Patients 5 and 8 have none because their bills are packages",
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
        "mapping of patients": {p.patient_no: p for p in document.patients},
        "mapping of lab blocks": {p.patient_no: p.labs for p in document.patients},
    }
    for name, clinical in forms.items():
        built = build_lab_clean(built_showcase.claims, clinical=clinical, schema=LAB_CLEAN_SCHEMA)
        assert built.equals(lab), name
    # Without lab blocks a billed blood gas has no `blood_gas` and the build says so.
    with pytest.raises(LabCoherenceError, match="blood_gas"):
        build_lab_clean(built_showcase.claims, clinical={}, schema=LAB_CLEAN_SCHEMA)


def test_the_generator_refuses_a_bad_patient_id_or_a_lab_code_the_csv_lacks(
    built_showcase: BuildResult,
) -> None:
    with pytest.raises(LabReferenceError, match="Invalid patient_id format 'ANON'"):
        _patient_no("ANON")
    claim = built_showcase.claims[0]
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
