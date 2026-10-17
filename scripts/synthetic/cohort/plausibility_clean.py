"""Plausibility checks for the clean clinical tables (plan D5, slice E3: labs, prescriptions, vitals).

The checks read `lab_clean`, `recete_clean` and `anadata_clean` of one dataset and, where a check
compares a clean table with the bill, the claims tables `claim_headers`, `procedure_claim_lines` and
`drug_claim_lines`. They report what a clinician or an auditor would call implausible: a lab value no
patient can have, a hemogram or a blood gas that contradicts its own arithmetic, a flag or a unit
that is not the reference's, result sets that do not match the billed lab lines, a route that
contradicts the product, a dose that is not a count and a Turkish unit, a vital sign out of range.

`check_clean_plausibility(tables, clean_tables)` is a pure function of the tables it is given: it
knows no fault and calls no engine. It has one small function per check id (`CHECK_FUNCTIONS`) and
runs all of them, or only the ids of `only`. `CHECKS` is the stable registry of ids; a test requires
a mutation case for each id.

INDEPENDENCE. The checks do not import or reuse the generator they test (`cohort.labs`,
`cohort.clean`, `cohort.clinical`) nor the claims checks of `cohort.plausibility`. The reference
limits and units are read from `data/synthetic/reference/lab_reference.csv` with Polars; every
judgment (hard bounds, tolerances, word lists, vocabularies) is a named constant below with its
source. A test scans the imports of this module.

OWNERSHIP. Each defect has one home. A check that needs a value another check owns skips what it
cannot evaluate (a null, a NaN or an unknown sex) and leaves the report to the owner: NaN and
missing results belong to `lab.value_bounds`, an incomplete result set to
`lab.result_sets_match_bill`, a sex that is neither E nor K to `ana.vitals_bounds`.

`Problem.where` starts with the patient id (then `table[key]`, after a space). The reference data
(the lab reference CSV) is read once, lazily, by a `CleanPlausibilityContext`. Everything is
vectorised Polars; a `Problem` is built only from the finished findings.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from functools import cached_property, lru_cache
from pathlib import Path
import re

import polars as pl

from scripts.synthetic.pathways.schema import Problem as _PathwayProblem

REPO = Path(__file__).resolve().parents[3]

TABLE_LAB = "lab_clean.parquet"
TABLE_RECETE = "recete_clean.parquet"
TABLE_ANADATA = "anadata_clean.parquet"
TABLE_HEADERS = "claim_headers.parquet"
TABLE_PROCEDURES = "procedure_claim_lines.parquet"
TABLE_DRUGS = "drug_claim_lines.parquet"

LAB_REFERENCE_PATH = "data/synthetic/reference/lab_reference.csv"

# The columns each table must have; a table without one is reported by name, not by a Polars error.
REQUIRED_COLUMNS: dict[str, tuple[str, ...]] = {
    TABLE_LAB: (
        "HASTA_ID", "basvuru_id", "SUB_CODE", "parametre", "sonuc_sayisal", "sonuc_nitel", "birim",
        "ref_alt", "ref_ust", "anormal_mi", "kohort", "donem", "tarih",
    ),
    TABLE_RECETE: (
        "HASTA_ID", "RECETE_TARIH", "RF_EPISODE", "ilac_adi", "ilac_adi_ham", "dozaj_ham",
        "verilis_yolu", "miktar", "kohort", "donem",
    ),
    TABLE_ANADATA: (
        "HASTA_ID", "SQ_EPISODE", "TANI_YASI", "CINSIYET", "KB-S", "KB-D", "Nabiz", "SPO2", "Boy",
        "Kilo", "BMI",
    ),
    TABLE_HEADERS: ("claim_id", "patient_id", "episode_id"),
    TABLE_PROCEDURES: (
        "claim_id", "patient_id", "episode_id", "procedure_line_id", "procedure_date",
        "procedure_code", "procedure_category",
    ),
    TABLE_DRUGS: (
        "drug_claim_line_id", "patient_id", "episode_id", "drug_claim_date", "drug_name",
        "quantity",
    ),
}  # fmt: skip

# Every check id a plausibility Problem may carry, with a one-line meaning (at most 120 characters).
# A meta-test requires an implementation and an in-memory mutation case for each id.
CHECKS: dict[str, str] = {
    # lab: the values, their arithmetic, their flags and units, and their link to the bill
    "lab.value_bounds": "a lab value outside the hard interval of its parameter, a NaN, an unknown parameter or a bad strip grade",
    "lab.hemogram_relations": "a hemogram whose differential does not sum to the WBC or whose HCT, HGB, RBC, MCV and MCH disagree",
    "lab.flag_and_limits": "an abnormal flag that disagrees with value and limits, or limits that differ from the reference for the sex",
    "lab.unit_matches_reference": "a lab unit that is not the unit the reference lists for the parameter (a strip row has none)",
    "lab.result_sets_match_bill": "lab result sets that do not match the billed lab lines one to one, or sets with missing or extra rows",
    "lab.blood_gas_relations": "a blood gas whose HCO3, base excess or SaO2 contradicts its pH, pCO2 and pO2",
    "lab.egfr_relation": "an eGFR that is not the CKD-EPI 2021 value of the creatinine, age and sex of its result set",
    # rx: the prescription rows against the bill, the product and the dose format
    "rx.matches_billed_line": "prescription rows that do not match the billed drug lines one to one (patient, date, name, quantity)",
    "rx.route_vs_product": "a missing or unknown route, or a route that contradicts the product name (injection, tablet, nebule, LMWH)",
    "rx.dose_unit": "a dozaj_ham that is not a positive count and one Turkish unit word, or whose count differs from miktar",
    "rx.required_fields": "a null or blank in a required prescription column (patient, date, episode, names, dose, route, miktar, kohort, donem)",
    # ana: the vital signs
    "ana.vitals_bounds": "a vital sign, age or sex out of bounds, a diastolic not below the systolic, or a BMI that is not Kilo/Boy^2",
}

# --- judgment tables -------------------------------------------------------------------------
# These are decisions of the author, not facts of the SUT. A committed row that trips a bound or a
# word must be reported, not silently widened.

# Parameter names and codes of the checks that relate parameters of one result set. A test requires
# every name to occur in the reference CSV.
HEMOGRAM_CODE = "L107020"
WBC = "WBC (Lökosit)"
DIFFERENTIAL_PARAMETERS: tuple[str, ...] = (
    "NEU# (Nötrofil)",
    "LYM# (Lenfosit)",
    "MONO# (Monosit)",
    "EOS# (Eozinofil)",
    "BASO# (Bazofil)",
)
RBC = "RBC (Eritrosit)"
HGB = "HGB (Hemoglobin)"
HCT = "HCT (Hematokrit)"
MCV = "MCV"
MCH = "MCH"
BLOOD_GAS_CODE = "L103900"
PH = "pH"
PCO2 = "pCO2"
PO2 = "pO2"
HCO3 = "HCO3"
BASE_EXCESS = "BE (baz fazlası)"
SAO2 = "SaO2"
CREATININE_CODE = "L104780"
CREATININE = "Kreatinin"
EGFR = "eGFR (CKD-EPI 2021, hesaplanan)"
URINALYSIS_CODE = "L107010"

# lab.value_bounds: the HARD interval of every parameter, keyed by (SUB_CODE, parametre) because pH is
# both a blood-gas and a urine parameter. These are NOT clinical thresholds: a value outside can only
# be a bug (a negative glucose, a potassium of 40 mmol/L). Source: the clinical review
# reports/synthetic-data/2026-10-17-c2-lab-clinical-review.md section (f). The review has no row for
# the venous saturation `sO2 (venöz)`; the interval 10..100 is this module's decision (a venous
# saturation is lower than an arterial one and never above 100). The five differential counts are
# also capped by the WBC of their own result set (see DIFFERENTIAL_PARAMETERS).
LAB_HARD_BOUNDS: dict[tuple[str, str], tuple[float, float]] = {
    # hemogram L107020 (10^3/µL, 10^6/µL, g/dL, %, fL, pg)
    (HEMOGRAM_CODE, WBC): (0.1, 100.0),
    (HEMOGRAM_CODE, "NEU# (Nötrofil)"): (0.0, 100.0),
    (HEMOGRAM_CODE, "LYM# (Lenfosit)"): (0.0, 100.0),
    (HEMOGRAM_CODE, "MONO# (Monosit)"): (0.0, 100.0),
    (HEMOGRAM_CODE, "EOS# (Eozinofil)"): (0.0, 100.0),
    (HEMOGRAM_CODE, "BASO# (Bazofil)"): (0.0, 100.0),
    (HEMOGRAM_CODE, RBC): (1.0, 8.5),
    (HEMOGRAM_CODE, HGB): (3.0, 23.0),
    (HEMOGRAM_CODE, HCT): (10.0, 70.0),
    (HEMOGRAM_CODE, MCV): (50.0, 130.0),
    (HEMOGRAM_CODE, MCH): (15.0, 45.0),
    (HEMOGRAM_CODE, "MCHC"): (28.0, 36.5),
    (HEMOGRAM_CODE, "RDW-CV"): (10.0, 40.0),
    (HEMOGRAM_CODE, "PLT (Trombosit)"): (2.0, 1500.0),
    (HEMOGRAM_CODE, "MPV"): (4.0, 16.0),
    # single-parameter tests
    ("L101850", "CRP (kantitatif)"): (0.0, 500.0),
    ("L106240", "Prokalsitonin"): (0.0, 500.0),
    ("L102090", "D-dimer"): (0.0, 35000.0),
    ("L107360", "hs-Troponin I"): (0.0, 100000.0),
    ("L102890", "Glukoz"): (20.0, 1500.0),
    ("L107420", "Üre"): (3.0, 400.0),
    (CREATININE_CODE, CREATININE): (0.2, 25.0),
    (CREATININE_CODE, EGFR): (1.0, 150.0),
    ("L106910", "Sodyum"): (100.0, 175.0),
    ("L106150", "Potasyum"): (1.5, 9.0),
    ("L100300", "ALT"): (1.0, 20000.0),
    ("L101280", "AST"): (1.0, 20000.0),
    # blood gas L103900 (arterial and venous)
    (BLOOD_GAS_CODE, PH): (6.60, 7.80),
    (BLOOD_GAS_CODE, PCO2): (8.0, 150.0),
    (BLOOD_GAS_CODE, PO2): (15.0, 650.0),
    (BLOOD_GAS_CODE, HCO3): (2.0, 55.0),
    (BLOOD_GAS_CODE, BASE_EXCESS): (-35.0, 35.0),
    (BLOOD_GAS_CODE, SAO2): (30.0, 100.0),
    (BLOOD_GAS_CODE, "sO2 (venöz)"): (10.0, 100.0),
    (BLOOD_GAS_CODE, "Laktat (kan gazı)"): (0.2, 30.0),
    (BLOOD_GAS_CODE, "İyonize kalsiyum (kan gazı)"): (0.40, 2.20),
    (BLOOD_GAS_CODE, "Sodyum (kan gazı)"): (100.0, 175.0),
    (BLOOD_GAS_CODE, "Potasyum (kan gazı)"): (1.5, 9.0),
    # urinalysis L107010: the numeric parameters (the strips are in LAB_STRIP_PARAMETERS)
    (URINALYSIS_CODE, "Dansite (özgül ağırlık)"): (1.001, 1.045),
    (URINALYSIS_CODE, PH): (4.5, 9.0),
    (URINALYSIS_CODE, "Mikroskopi: lökosit"): (0.0, 500.0),
    (URINALYSIS_CODE, "Mikroskopi: eritrosit"): (0.0, 500.0),
}  # fmt: skip

# lab.value_bounds: the qualitative urine strips (the rows of the reference with no numeric limit)
# and the grades they may have. Source: the same review, section (f), "strips".
LAB_STRIP_PARAMETERS: tuple[tuple[str, str], ...] = (
    (URINALYSIS_CODE, "Protein (strip)"),
    (URINALYSIS_CODE, "Glukoz (strip)"),
    (URINALYSIS_CODE, "Keton (strip)"),
    (URINALYSIS_CODE, "Kan / hemoglobin (strip)"),
    (URINALYSIS_CODE, "Lökosit esteraz (strip)"),
    (URINALYSIS_CODE, "Nitrit (strip)"),
)
STRIP_GRADES: tuple[str, ...] = ("Negatif", "Eser", "+", "++", "+++", "++++", "Pozitif")
STRIP_NORMAL = "Negatif"

# lab.hemogram_relations: coarse, textbook tolerances, independent of how the values were rounded.
DIFFERENTIAL_TOLERANCE = 0.05  # the five counts sum to the WBC within 0.05 (10^3/µL)
HCT_PER_HGB_RANGE = (2.74, 3.57)  # 100 / MCHC for MCHC 36.5 .. 28 g/dL
INDEX_TOLERANCE = 0.03  # RBC x MCV / 10 within 3 % of HCT, RBC x MCH / 10 within 3 % of HGB

# lab.blood_gas_relations: the textbook relations and their coarse tolerances.
HENDERSON_PK = 6.1  # pH = pK + log10(HCO3 / (0.0307 x pCO2))
HENDERSON_SOLUBILITY = 0.0307  # mmol/L per mmHg of CO2
HCO3_TOLERANCE = 1.0  # mmol/L
# base excess (van Slyke): BE = 0.93 x (HCO3 - 24.4 + 14.8 x (pH - 7.4))
BASE_EXCESS_SLOPE = 0.93
BASE_EXCESS_HCO3_NORMAL = 24.4
BASE_EXCESS_PH_SLOPE = 14.8
BASE_EXCESS_PH_NORMAL = 7.4
BASE_EXCESS_TOLERANCE = 3.0  # mmol/L
# oxygen saturation (Severinghaus): SaO2 = 100 / (1 + 23400 / (pO2^3 + 150 x pO2))
SEVERINGHAUS_NUMERATOR = 23400.0
SEVERINGHAUS_LINEAR = 150.0
SAO2_TOLERANCE = 3.0  # percentage points

# lab.egfr_relation: CKD-EPI 2021 (Inker 2021), as written in the notes of the creatinine rows of the
# reference CSV: A = 142 x 0.9938^age (x 1.012 if female); kappa 0.7 F / 0.9 M; alpha -0.241 F / -0.302 M.
CKD_EPI_BASE = 142.0
CKD_EPI_AGE_FACTOR = 0.9938
CKD_EPI_FEMALE_FACTOR = 1.012
CKD_EPI_KAPPA = {"E": 0.9, "K": 0.7}
CKD_EPI_ALPHA = {"E": -0.302, "K": -0.241}
CKD_EPI_HIGH_EXPONENT = -1.200
EGFR_TOLERANCE = 1.0  # mL/dk/1.73m²

# lab.result_sets_match_bill: the cohort name of the showcase dataset (another dataset names its own in
# the context) and the category of the billed lab lines.
KOHORT = "showcase"
LAB_CATEGORY = "laboratuvar"

# rx.route_vs_product: the CLOSED vocabulary of routes, as `recete_clean` spells them (plain "I" in
# Intravenöz, capital dotted İ in the others; do not invent other spellings).
ROUTE_INTRAVENOUS = "Intravenöz"
ROUTE_IM_IV = "İntramusküler/İntravenöz"
ROUTE_SUBCUTANEOUS = "Subkütan"
ROUTE_ORAL = "Ağızdan (Oral)"
ROUTE_INHALATION = "İnhalasyon"
PARENTERAL_ROUTES: tuple[str, ...] = (ROUTE_INTRAVENOUS, ROUTE_IM_IV, ROUTE_SUBCUTANEOUS)
ROUTES: tuple[str, ...] = (*PARENTERAL_ROUTES, ROUTE_ORAL, ROUTE_INHALATION)

# rx.route_vs_product: words of a product name (`ilac_adi` and the raw TITCK name `ilac_adi_ham`),
# folded to lower case without Turkish letters. Judgment, from the names in recete_clean. The strong
# injection words always count; the container words (vial, ampoule, bag, and the abbreviations of the
# billed names) count only when no inhalation or oral word is present, because a nebule is sold in
# a vial and a tablet in a bottle. "inside" matches inside a word, "whole" only as a whole word.
ROUTE_WORDS: dict[str, tuple[str, ...]] = {
    "injection_inside": ("enjeksiyon", "enjektor", "infuzyon", "pp-torba", "i.v.", "im/iv"),
    "injection_whole": ("iv",),
    "container_whole": ("flakon", "flk", "ampul", "amp", "enj", "inf", "torba"),
    "oral_inside": ("tablet", "kapsul", "film kapli"),
    "oral_whole": ("tb",),
    "inhalation_inside": ("nebul", "inhalasyon"),
    # low-molecular-weight heparins (brand and generic names on the Turkish market): subcutaneous only
    "lmwh_inside": (
        "clexane", "enoksaparin", "enoxaparin", "fraxiparine", "fraksiparin", "nadroparin",
        "fragmin", "dalteparin",
    ),
}  # fmt: skip

# rx.dose_unit: `dozaj_ham` is "<positive integer> <unit>"; the unit is one Turkish word of the closed
# list (with and without Turkish letters, as the committed rows spell them); the English words that
# a translation would leave behind are defects.
DOSE_UNITS: tuple[str, ...] = (
    "kutu", "flakon", "şişe", "sise", "ampul", "torba", "enjektör", "enjektor", "tablet",
    "kapsül", "kapsul",
)  # fmt: skip
ENGLISH_UNITS: tuple[str, ...] = (
    "bottle", "vial", "bag", "box", "capsule", "ampoule", "syringe",
)  # fmt: skip

# rx.required_fields: the columns of `recete_clean` that may never be null or blank. (doz_mg,
# doz_birimi, siklik and gun are null in some committed rows and are not required.)
REQUIRED_RECETE_COLUMNS: tuple[str, ...] = (
    "HASTA_ID", "RECETE_TARIH", "RF_EPISODE", "ilac_adi", "ilac_adi_ham", "dozaj_ham",
    "verilis_yolu", "miktar", "kohort", "donem",
)  # fmt: skip

# ana.vitals_bounds: hard bounds (inclusive) of the vital signs and the age; units as in the table
# (mmHg, /dk, %, cm, kg, years). Judgment: outside can only be a bug. The diastolic must also be
# below the systolic and the BMI must be Kilo / (Boy / 100)^2 within BMI_TOLERANCE.
VITALS_BOUNDS: dict[str, tuple[float, float]] = {
    "KB-S": (70.0, 260.0),
    "KB-D": (30.0, 150.0),
    "Nabiz": (30.0, 220.0),
    "SPO2": (50.0, 100.0),
    "Boy": (120.0, 210.0),
    "Kilo": (30.0, 200.0),
    "TANI_YASI": (0.0, 110.0),
}
BMI_TOLERANCE = 0.1
SEX_CODES: tuple[str, ...] = ("E", "K")  # E = erkek (male columns), K = kadın (female columns)

_EPS = 1e-9  # float noise on a comparison that sits exactly on its limit


# --- the Problem ------------------------------------------------------------------------------


@dataclass(frozen=True)
class Problem(_PathwayProblem):
    """One finding: a stable check id, where (the patient id, then a detail) and what is wrong."""

    def __post_init__(self) -> None:
        if self.check not in CHECKS:
            raise KeyError(f"unregistered check id {self.check!r}")

    @property
    def patient_id(self) -> str:
        """The patient a finding is about: `where` starts with it."""
        return self.where.split(" ", 1)[0]


class CleanPlausibilityError(ValueError):
    """The tables handed to `check_clean_plausibility` lack a table or a column the checks read."""


# --- Turkish-insensitive text --------------------------------------------------------------------

_TURKISH = str.maketrans("ıçğöşü", "icgosu")
_COMBINING_DOT = chr(0x0307)  # lower-casing the capital dotted I gives an i followed by this mark


def fold_text(text: str) -> str:
    """Lower case without Turkish letters: `İV` and `iv`, `ENJEKTÖR` and `enjektor` compare equal."""
    return text.lower().replace(_COMBINING_DOT, "").translate(_TURKISH)


def _fold(expr: pl.Expr) -> pl.Expr:
    """`fold_text` as an expression."""
    folded = expr.str.to_lowercase().str.replace_all(_COMBINING_DOT, "", literal=True)
    for turkish, plain in zip("ıçğöşü", "icgosu", strict=True):
        folded = folded.str.replace_all(turkish, plain, literal=True)
    return folded


def _words_pattern(words: Iterable[str], *, whole: bool = False) -> str:
    """A regex that finds any of `words` (folded), inside words or, with `whole`, as whole words."""
    alternatives = "|".join(sorted({re.escape(fold_text(w)).replace("\\ ", " ") for w in words}))
    return rf"\b(?:{alternatives})\b" if whole else f"(?:{alternatives})"


_INJECTION_PATTERN = (
    f"{_words_pattern(ROUTE_WORDS['injection_inside'])}"
    f"|{_words_pattern(ROUTE_WORDS['injection_whole'], whole=True)}"
)
_CONTAINER_PATTERN = _words_pattern(ROUTE_WORDS["container_whole"], whole=True)
_ORAL_PATTERN = (
    f"{_words_pattern(ROUTE_WORDS['oral_inside'])}"
    f"|{_words_pattern(ROUTE_WORDS['oral_whole'], whole=True)}"
)
_INHALATION_PATTERN = _words_pattern(ROUTE_WORDS["inhalation_inside"])
_LMWH_PATTERN = _words_pattern(ROUTE_WORDS["lmwh_inside"])


# --- the reference data -----------------------------------------------------------------------

_LIMIT_COLUMNS = ("ref_low_male", "ref_high_male", "ref_low_female", "ref_high_female")


class CleanPlausibilityContext:
    """The reference data the checks compare with; each part is read once, on first use."""

    def __init__(
        self,
        root: Path = REPO,
        *,
        lab_reference: pl.DataFrame | None = None,
        kohort: str = KOHORT,
    ) -> None:
        self.root = Path(root)
        self._lab_reference = lab_reference
        self.kohort = kohort

    @cached_property
    def lab_reference(self) -> pl.DataFrame:
        """One row per CSV row: code, variant (test_key), parameter, unit, the four limits, position.

        A blank limit is null; a row with no limit at all is `qualitative` (a urine strip); `unit` is
        '' for a blank unit; `variant_rank` orders the variants of a code by their first CSV row.
        """
        if self._lab_reference is not None:
            return self._lab_reference
        raw = pl.read_csv(
            self.root / LAB_REFERENCE_PATH,
            columns=["test_key", "ek2b_code", "result_parameter", "unit", *_LIMIT_COLUMNS],
            schema_overrides=dict.fromkeys(_LIMIT_COLUMNS, pl.Float64),
        )
        return (
            raw.select(
                pl.col("ek2b_code").alias("code"),
                pl.col("test_key").alias("variant"),
                pl.col("result_parameter").alias("parameter"),
                pl.col("unit").fill_null("").alias("unit"),
                pl.col("ref_low_male").alias("low_m"),
                pl.col("ref_high_male").alias("high_m"),
                pl.col("ref_low_female").alias("low_f"),
                pl.col("ref_high_female").alias("high_f"),
                pl.all_horizontal([pl.col(c).is_null() for c in _LIMIT_COLUMNS]).alias(
                    "qualitative"
                ),
            )
            .with_row_index("position")
            .with_columns(pl.col("position").min().over("code", "variant").alias("variant_rank"))
        )

    @cached_property
    def lab_variants(self) -> pl.DataFrame:
        """code, variant, size: how many rows one result set of each variant has."""
        return self.lab_reference.group_by("code", "variant").agg(pl.len().alias("size"))


@lru_cache(maxsize=1)
def default_context() -> CleanPlausibilityContext:
    """The context `check_clean_plausibility` uses when it is given none (shared, so data load once)."""
    return CleanPlausibilityContext()


# --- small expression helpers ------------------------------------------------------------------


def _format(template: str, *args: pl.Expr) -> pl.Expr:
    """`pl.format`, writing `(none)` for a missing value: `pl.format` makes the whole text null."""
    return pl.format(template, *[arg.cast(pl.String).fill_null("(none)") for arg in args])


def _reasons(*parts: pl.Expr) -> pl.Expr:
    """The `parts` that apply (a part is null when it does not), joined; '' when none does."""
    return pl.concat_str(*parts, separator="; ", ignore_nulls=True)


def _shown(expr: pl.Expr) -> pl.Expr:
    """A text for a message: an empty string reads `(empty)`, a null reads `(none)`."""
    return pl.when(expr == "").then(pl.lit("(empty)")).otherwise(expr.fill_null("(none)"))


def _finite(expr: pl.Expr) -> pl.Expr:
    """The number, or null when it is null, NaN or infinite (those belong to lab.value_bounds)."""
    return pl.when(expr.is_finite()).then(expr)


def _same(left: pl.Expr, right: pl.Expr) -> pl.Expr:
    """Two limits are equal: both missing, or both numbers within float noise."""
    both_missing = left.is_null() & right.is_null()
    return both_missing | ((left - right).abs() <= _EPS).fill_null(False)


def _problems(check: str, found: pl.DataFrame) -> list[Problem]:
    """Problems for findings with the columns `where` and `message`, in a stable order."""
    ordered = found.select(pl.col("where").fill_null("(none)"), "message").sort("where", "message")
    return [
        Problem(check, where, message)
        for where, message in zip(ordered["where"], ordered["message"], strict=True)
    ]


# A lab result set is the rows of one billed lab line: (patient, episode, day, code), and, when a
# code is billed twice on a day (hs-troponin I), the n-th row of every parameter forms the n-th set.
SET_KEY = ("HASTA_ID", "basvuru_id", "day", "SUB_CODE")
SET_ID = (*SET_KEY, "copy")


def _set_text() -> pl.Expr:
    """The key of a result set as text: `episode|day|code`, with `#2` for the second set of a key."""
    return _format(
        "{}|{}|{}{}",
        pl.col("basvuru_id"),
        pl.col("day"),
        pl.col("SUB_CODE"),
        pl.when(pl.col("copy") > 0).then(_format("#{}", pl.col("copy") + 1)).otherwise(pl.lit("")),
    )


def _set_where() -> pl.Expr:
    """`where` of a finding about a result set: the patient, then `lab_clean[episode|day|code]`."""
    return _format("{} lab_clean[{}]", pl.col("HASTA_ID"), _set_text())


def _lab_row_where() -> pl.Expr:
    """`where` of a finding about one lab row: the set key and the parameter."""
    return _format("{} lab_clean[{}|{}]", pl.col("HASTA_ID"), _set_text(), pl.col("parametre"))


# --- the tables of one run ---------------------------------------------------------------------


class _Clean:
    """The tables of one run and the frames several checks share, each built on first use."""

    def __init__(
        self,
        tables: Mapping[str, pl.DataFrame],
        clean_tables: Mapping[str, pl.DataFrame],
        ctx: CleanPlausibilityContext,
    ) -> None:
        self.tables = tables
        self.clean_tables = clean_tables
        self.ctx = ctx

    def table(self, name: str) -> pl.DataFrame:
        """A claims table, or (the `*_clean.parquet` files) a clean table, by file name."""
        source = self.clean_tables if name.endswith("_clean.parquet") else self.tables
        if name not in source:
            raise CleanPlausibilityError(f"table {name} is missing; the checks read it")
        frame = source[name]
        lacking = [column for column in REQUIRED_COLUMNS[name] if column not in frame.columns]
        if lacking:
            raise CleanPlausibilityError(f"table {name} lacks the column(s) {lacking}")
        return frame

    @cached_property
    def lab(self) -> pl.DataFrame:
        """lab_clean with the `day`, the `copy` of its set and the set's `wbc`.

        `wbc` is the WBC of the set when it lies inside its own hard interval, else null: a WBC that is
        itself a defect (and is reported as one) must not make every count "above the WBC".
        """
        frame = self.table(TABLE_LAB).with_columns(pl.col("tarih").dt.date().alias("day"))
        frame = frame.with_columns(pl.int_range(pl.len()).over(*SET_KEY, "parametre").alias("copy"))
        value = pl.col("sonuc_sayisal")
        low, high = LAB_HARD_BOUNDS[(HEMOGRAM_CODE, WBC)]
        wbc = pl.when((pl.col("parametre") == WBC) & value.is_between(low, high)).then(value).max()
        return frame.with_columns(wbc.over(*SET_ID).alias("wbc"))

    @cached_property
    def set_variants(self) -> pl.DataFrame:
        """SET_ID and `variant`: the reference variant (test_key) each result set is read against.

        The variant of a code is the one that lists most of the set's parameters (blood gases are
        arterial or venous); a tie goes to the variant that comes first in the CSV.
        """
        reference = self.ctx.lab_reference.select("code", "variant", "parameter", "variant_rank")
        hits = (
            self.lab.select(*SET_ID, "parametre")
            .join(reference, left_on=["SUB_CODE", "parametre"], right_on=["code", "parameter"])
            .group_by(*SET_ID, "variant", "variant_rank")
            .agg(pl.len().alias("hits"))
        )
        return (
            hits.sort(["hits", "variant_rank"], descending=[True, False])
            .unique(subset=list(SET_ID), keep="first", maintain_order=True)
            .select(*SET_ID, "variant")
        )

    @cached_property
    def lab_rows(self) -> pl.DataFrame:
        """The lab rows with their set's `variant` and the reference row: `ref_unit`, limits, `in_ref`."""
        reference = self.ctx.lab_reference.select(
            pl.col("code").alias("SUB_CODE"),
            "variant",
            pl.col("parameter").alias("parametre"),
            pl.col("unit").alias("ref_unit"),
            "low_m",
            "high_m",
            "low_f",
            "high_f",
            "qualitative",
            pl.lit(True).alias("in_ref"),
        )
        rows = self.lab.join(self.set_variants, on=list(SET_ID), how="left")
        return rows.join(reference, on=["SUB_CODE", "variant", "parametre"], how="left")

    @cached_property
    def sets(self) -> pl.DataFrame:
        """One row per result set: SET_ID, `rows`, `variant`, `variant_size`."""
        grouped = self.lab_rows.group_by(*SET_ID).agg(
            pl.len().alias("rows"), pl.col("variant").first()
        )
        sizes = self.ctx.lab_variants.select(
            pl.col("code").alias("SUB_CODE"), "variant", pl.col("size").alias("variant_size")
        )
        return grouped.join(sizes, on=["SUB_CODE", "variant"], how="left")

    @cached_property
    def sexes(self) -> pl.DataFrame:
        """HASTA_ID and `sex` (E or K); null when the patient has none or two different ones."""
        sex = pl.col("CINSIYET")
        valid = sex.filter(sex.is_in(list(SEX_CODES)))
        return (
            self.table(TABLE_ANADATA)
            .group_by("HASTA_ID")
            .agg(valid.n_unique().alias("kinds"), valid.first().alias("first"))
            .select("HASTA_ID", pl.when(pl.col("kinds") == 1).then(pl.col("first")).alias("sex"))
        )

    @cached_property
    def ages(self) -> pl.DataFrame:
        """HASTA_ID, SQ_EPISODE and `age` (TANI_YASI), one row per patient episode."""
        return (
            self.table(TABLE_ANADATA)
            .select("HASTA_ID", "SQ_EPISODE", pl.col("TANI_YASI").alias("age"))
            .unique(subset=["HASTA_ID", "SQ_EPISODE"], keep="first", maintain_order=True)
        )

    def wide(self, code: str, parameters: Mapping[str, str]) -> pl.DataFrame:
        """One row per result set of `code`, one column per parameter (alias -> parametre).

        A value that is null, NaN or infinite is null here; those are reported by lab.value_bounds.
        """
        value = pl.col("sonuc_sayisal")
        wide = (
            self.lab.filter(pl.col("SUB_CODE") == code)
            .group_by(*SET_ID)
            .agg(
                [
                    value.filter(pl.col("parametre") == name).first().alias(alias)
                    for alias, name in parameters.items()
                ]
            )
        )
        return wide.with_columns([_finite(pl.col(alias)) for alias in parameters])


# --- lab ---------------------------------------------------------------------------------------


@lru_cache(maxsize=1)
def _bounds_frame() -> pl.DataFrame:
    """SUB_CODE, parametre, lo, hi: LAB_HARD_BOUNDS as a frame."""
    keys = list(LAB_HARD_BOUNDS)
    return pl.DataFrame(
        {
            "SUB_CODE": [code for code, _ in keys],
            "parametre": [name for _, name in keys],
            "lo": [LAB_HARD_BOUNDS[key][0] for key in keys],
            "hi": [LAB_HARD_BOUNDS[key][1] for key in keys],
        },
        schema={
            "SUB_CODE": pl.String,
            "parametre": pl.String,
            "lo": pl.Float64,
            "hi": pl.Float64,
        },
    )


@lru_cache(maxsize=1)
def _strip_frame() -> pl.DataFrame:
    """SUB_CODE, parametre, is_strip: LAB_STRIP_PARAMETERS as a frame."""
    return pl.DataFrame(
        {
            "SUB_CODE": [code for code, _ in LAB_STRIP_PARAMETERS],
            "parametre": [name for _, name in LAB_STRIP_PARAMETERS],
            "is_strip": [True] * len(LAB_STRIP_PARAMETERS),
        },
        schema={"SUB_CODE": pl.String, "parametre": pl.String, "is_strip": pl.Boolean},
    )


def check_value_bounds(bill: _Clean) -> list[Problem]:
    """lab.value_bounds: a numeric result is finite and inside its hard interval; a strip has a grade."""
    rows = bill.lab.join(_bounds_frame(), on=["SUB_CODE", "parametre"], how="left").join(
        _strip_frame(), on=["SUB_CODE", "parametre"], how="left"
    )
    value, grade = pl.col("sonuc_sayisal"), pl.col("sonuc_nitel")
    low, high, wbc = pl.col("lo"), pl.col("hi"), pl.col("wbc")
    numeric = low.is_not_null()
    strip = pl.col("is_strip").fill_null(False)
    differential = (pl.col("SUB_CODE") == HEMOGRAM_CODE) & pl.col("parametre").is_in(
        list(DIFFERENTIAL_PARAMETERS)
    )
    why = _reasons(
        pl.when(~numeric & ~strip).then(pl.lit("is not a parameter of LAB_HARD_BOUNDS")),
        pl.when(numeric & value.is_null()).then(pl.lit("has no numeric result")),
        pl.when(numeric & value.is_nan()).then(pl.lit("is NaN")),
        pl.when(numeric & value.is_infinite()).then(pl.lit("is infinite")),
        pl.when(numeric & value.is_finite() & ((value < low) | (value > high))).then(
            _format("is outside the hard interval {}..{}", low, high)
        ),
        pl.when(numeric & differential & value.is_finite() & (value > wbc)).then(
            _format("is above the WBC {} of its result set", wbc)
        ),
        pl.when(strip & grade.is_null()).then(pl.lit("has no grade")),
        pl.when(strip & grade.is_not_null() & ~grade.is_in(list(STRIP_GRADES))).then(
            _format(
                "has the grade {}, which is not one of {}", grade, pl.lit(", ".join(STRIP_GRADES))
            )
        ),
    )
    found = (
        rows.with_columns(why.alias("why"))
        .filter(pl.col("why") != "")
        .select(
            _lab_row_where().alias("where"),
            _format(
                "{} = {}: {}",
                pl.col("parametre"),
                pl.coalesce(value.cast(pl.String), grade),
                pl.col("why"),
            ).alias("message"),
        )
    )
    return _problems("lab.value_bounds", found)


def check_hemogram_relations(bill: _Clean) -> list[Problem]:
    """lab.hemogram_relations: differential sum, HCT/HGB, RBC x MCV / 10 and RBC x MCH / 10."""
    counts = ("neu", "lym", "mono", "eos", "baso")
    names = {"wbc": WBC, "rbc": RBC, "hgb": HGB, "hct": HCT, "mcv": MCV, "mch": MCH}
    names.update(zip(counts, DIFFERENTIAL_PARAMETERS, strict=True))
    wide = bill.wide(HEMOGRAM_CODE, names)
    c = pl.col
    total = c("neu") + c("lym") + c("mono") + c("eos") + c("baso")
    low, high = HCT_PER_HGB_RANGE
    sum_off = (total - c("wbc")).abs() > DIFFERENTIAL_TOLERANCE + _EPS
    ratio_off = (c("hct") < low * c("hgb") - _EPS) | (c("hct") > high * c("hgb") + _EPS)
    hct_from_mcv = c("rbc") * c("mcv") / 10
    hgb_from_mch = c("rbc") * c("mch") / 10
    mcv_off = (hct_from_mcv - c("hct")).abs() > INDEX_TOLERANCE * c("hct").abs() + _EPS
    mch_off = (hgb_from_mch - c("hgb")).abs() > INDEX_TOLERANCE * c("hgb").abs() + _EPS
    percent = f"{INDEX_TOLERANCE * 100:g} %"
    findings = [
        wide.filter(sum_off).select(
            _set_where().alias("where"),
            _format(
                "the five differential counts sum to {} but the WBC is {} (tolerance {})",
                total.round(3),
                c("wbc"),
                pl.lit(DIFFERENTIAL_TOLERANCE),
            ).alias("message"),
        ),
        wide.filter(ratio_off).select(
            _set_where().alias("where"),
            _format(
                "HCT {} / HGB {} = {} is outside {}..{}",
                c("hct"),
                c("hgb"),
                pl.when(c("hgb") > 0).then((c("hct") / c("hgb")).round(3)),
                pl.lit(low),
                pl.lit(high),
            ).alias("message"),
        ),
        wide.filter(mcv_off).select(
            _set_where().alias("where"),
            _format(
                "RBC {} x MCV {} / 10 = {} but HCT is {} (more than " + percent + " apart)",
                c("rbc"),
                c("mcv"),
                hct_from_mcv.round(2),
                c("hct"),
            ).alias("message"),
        ),
        wide.filter(mch_off).select(
            _set_where().alias("where"),
            _format(
                "RBC {} x MCH {} / 10 = {} but HGB is {} (more than " + percent + " apart)",
                c("rbc"),
                c("mch"),
                hgb_from_mch.round(2),
                c("hgb"),
            ).alias("message"),
        ),
    ]
    return _problems("lab.hemogram_relations", pl.concat(findings))


def check_flag_and_limits(bill: _Clean) -> list[Problem]:
    """lab.flag_and_limits: the flag follows value and limits; the limits are the reference's for the sex."""
    rows = bill.lab_rows.join(bill.sexes, on="HASTA_ID", how="left")
    c = pl.col
    value, flag, grade = c("sonuc_sayisal"), c("anormal_mi"), c("sonuc_nitel")
    strip = grade.is_not_null()
    female = c("sex") == "K"
    no_limit = pl.lit(None, dtype=pl.Float64)

    def by_sex(male: str, female_: str) -> pl.Expr:
        return pl.when(female).then(c(female_)).otherwise(c(male))

    # a missing low limit means 0; a qualitative row (a strip) has no limit at all
    expected_low = (
        pl.when(c("qualitative")).then(no_limit).otherwise(by_sex("low_m", "low_f").fill_null(0.0))
    )
    expected_high = pl.when(c("qualitative")).then(no_limit).otherwise(by_sex("high_m", "high_f"))
    sex_free = _same(c("low_m"), c("low_f")) & _same(c("high_m"), c("high_f"))
    verifiable = c("in_ref").fill_null(False) & (c("sex").is_not_null() | sex_free)
    value_abnormal = (value < c("ref_alt")).fill_null(False) | (value > c("ref_ust")).fill_null(
        False
    )
    grade_abnormal = grade != STRIP_NORMAL
    why = _reasons(
        pl.when(flag.is_null()).then(pl.lit("anormal_mi is missing")),
        pl.when(
            ~strip & _finite(value).is_not_null() & flag.is_not_null() & (flag != value_abnormal)
        ).then(
            _format(
                "anormal_mi is {} but the value {} against the limits {}..{} makes it {}",
                flag,
                value,
                c("ref_alt"),
                c("ref_ust"),
                value_abnormal,
            )
        ),
        pl.when(strip & value.is_not_null()).then(
            _format("the strip row carries the number {}", value)
        ),
        pl.when(strip & flag.is_not_null() & (flag != grade_abnormal)).then(
            _format("the grade {} makes anormal_mi {}, not {}", grade, grade_abnormal, flag)
        ),
        pl.when(
            verifiable & ~(_same(c("ref_alt"), expected_low) & _same(c("ref_ust"), expected_high))
        ).then(
            _format(
                "the limits are {}..{} but the reference gives {}..{} for sex {}",
                c("ref_alt"),
                c("ref_ust"),
                expected_low,
                expected_high,
                c("sex"),
            )
        ),
    )
    found = (
        rows.with_columns(why.alias("why"))
        .filter(c("why") != "")
        .select(_lab_row_where().alias("where"), c("why").alias("message"))
    )
    return _problems("lab.flag_and_limits", found)


def check_unit_matches_reference(bill: _Clean) -> list[Problem]:
    """lab.unit_matches_reference: `birim` is the unit of the reference row ('' when it lists none)."""
    rows = bill.lab_rows.filter(pl.col("in_ref").fill_null(False))
    unit, reference = pl.col("birim"), pl.col("ref_unit")
    strip = pl.col("qualitative").fill_null(False) | pl.col("sonuc_nitel").is_not_null()
    found = rows.filter(unit.is_null() | (unit != reference)).select(
        _lab_row_where().alias("where"),
        pl.when(strip)
        .then(_format("strip row has the unit {}; a strip result has none", _shown(unit)))
        .otherwise(
            _format(
                "{} has the unit {}, the reference lists {}",
                pl.col("parametre"),
                _shown(unit),
                _shown(reference),
            )
        )
        .alias("message"),
    )
    return _problems("lab.unit_matches_reference", found)


def check_result_sets_match_bill(bill: _Clean) -> list[Problem]:
    """lab.result_sets_match_bill: one result set per billed lab line, each with its reference rows."""
    procedures = bill.table(TABLE_PROCEDURES).filter(pl.col("procedure_category") == LAB_CATEGORY)
    headers = bill.table(TABLE_HEADERS).select(
        "claim_id",
        pl.col("patient_id").alias("header_patient"),
        pl.col("episode_id").alias("header_episode"),
    )
    billed = (
        procedures.join(headers, on="claim_id", how="left")
        .select(
            "procedure_line_id",
            pl.coalesce("header_patient", "patient_id").alias("HASTA_ID"),
            pl.coalesce("header_episode", "episode_id").alias("basvuru_id"),
            pl.col("procedure_date").str.to_date("%Y-%m-%d", strict=False).alias("day"),
            pl.col("procedure_code").alias("SUB_CODE"),
        )
        .with_columns(pl.int_range(pl.len()).over(*SET_KEY).alias("copy"))
    )
    sets = bill.sets
    joined = billed.join(sets, on=list(SET_ID), how="full", coalesce=True)

    no_set = joined.filter(pl.col("rows").is_null()).select(
        _format(
            "{} procedure_claim_lines[{}]", pl.col("HASTA_ID"), pl.col("procedure_line_id")
        ).alias("where"),
        _format(
            "billed lab line {} on {} (episode {}) has no result set in lab_clean",
            pl.col("SUB_CODE"),
            pl.col("day"),
            pl.col("basvuru_id"),
        ).alias("message"),
    )
    no_bill = joined.filter(pl.col("procedure_line_id").is_null()).select(
        _set_where().alias("where"),
        _format(
            "result set of {} on {} (episode {}) has {} row(s) and no billed lab line",
            pl.col("SUB_CODE"),
            pl.col("day"),
            pl.col("basvuru_id"),
            pl.col("rows"),
        ).alias("message"),
    )

    # the parameters of the set's reference variant that the set lacks, and the rows it should not have
    variant_rows = bill.ctx.lab_reference.select(
        pl.col("code").alias("SUB_CODE"), "variant", pl.col("parameter").alias("parametre")
    )
    missing = (
        sets.select(*SET_ID, "variant")
        .join(variant_rows, on=["SUB_CODE", "variant"])
        .join(bill.lab.select(*SET_ID, "parametre"), on=[*SET_ID, "parametre"], how="anti")
        .group_by(*SET_ID)
        .agg(pl.col("parametre").sort().str.join(", ").alias("missing"))
    )
    unexpected = (
        bill.lab_rows.filter(pl.col("in_ref").is_null())
        .group_by(*SET_ID)
        .agg(pl.col("parametre").sort().str.join(", ").alias("unexpected"))
    )
    incomplete = (
        joined.filter(pl.col("rows").is_not_null() & pl.col("procedure_line_id").is_not_null())
        .join(missing, on=list(SET_ID), how="left")
        .join(unexpected, on=list(SET_ID), how="left")
        .filter(
            pl.col("variant").is_null()
            | pl.col("missing").is_not_null()
            | pl.col("unexpected").is_not_null()
        )
        .select(
            _set_where().alias("where"),
            _format(
                "result set has {} row(s), the reference variant {} lists {}: {}",
                pl.col("rows"),
                pl.col("variant"),
                pl.col("variant_size"),
                _reasons(
                    pl.when(pl.col("variant").is_null()).then(
                        _format(
                            "no parameter of the set belongs to the reference of {}",
                            pl.col("SUB_CODE"),
                        )
                    ),
                    pl.when(pl.col("missing").is_not_null()).then(
                        _format("missing {}", pl.col("missing"))
                    ),
                    pl.when(
                        pl.col("variant").is_not_null() & pl.col("unexpected").is_not_null()
                    ).then(_format("unexpected {}", pl.col("unexpected"))),
                ),
            ).alias("message"),
        )
    )

    # kohort and donem of every row
    year = pl.col("tarih").dt.year().cast(pl.String)
    kohort = bill.ctx.kohort
    wrong_kohort = (pl.col("kohort") != kohort).fill_null(True)
    wrong_donem = (pl.col("donem") != year).fill_null(True)
    labelled = bill.lab.filter(wrong_kohort | wrong_donem).select(
        _lab_row_where().alias("where"),
        _reasons(
            pl.when(wrong_kohort).then(
                _format("kohort is {}, not {}", pl.col("kohort"), pl.lit(kohort))
            ),
            pl.when(wrong_donem).then(
                _format("donem is {} but tarih is in {}", pl.col("donem"), year)
            ),
        ).alias("message"),
    )
    return _problems(
        "lab.result_sets_match_bill", pl.concat([no_set, no_bill, incomplete, labelled])
    )


def check_blood_gas_relations(bill: _Clean) -> list[Problem]:
    """lab.blood_gas_relations: HCO3 from pH and pCO2, base excess from HCO3 and pH, SaO2 from pO2."""
    wide = bill.wide(
        BLOOD_GAS_CODE,
        {"ph": PH, "pco2": PCO2, "po2": PO2, "hco3": HCO3, "be": BASE_EXCESS, "sao2": SAO2},
    )
    c = pl.col
    hco3_expected = HENDERSON_SOLUBILITY * c("pco2") * pl.lit(10.0).pow(c("ph") - HENDERSON_PK)
    be_expected = BASE_EXCESS_SLOPE * (
        c("hco3")
        - BASE_EXCESS_HCO3_NORMAL
        + BASE_EXCESS_PH_SLOPE * (c("ph") - BASE_EXCESS_PH_NORMAL)
    )
    sao2_expected = 100.0 / (
        1.0 + SEVERINGHAUS_NUMERATOR / (c("po2").pow(3) + SEVERINGHAUS_LINEAR * c("po2"))
    )
    findings = [
        wide.filter((c("hco3") - hco3_expected).abs() > HCO3_TOLERANCE + _EPS).select(
            _set_where().alias("where"),
            _format(
                "HCO3 {} but pCO2 {} and pH {} give {} (tolerance {} mmol/L)",
                c("hco3"),
                c("pco2"),
                c("ph"),
                hco3_expected.round(2),
                pl.lit(HCO3_TOLERANCE),
            ).alias("message"),
        ),
        wide.filter((c("be") - be_expected).abs() > BASE_EXCESS_TOLERANCE + _EPS).select(
            _set_where().alias("where"),
            _format(
                "base excess {} but HCO3 {} and pH {} give {} (tolerance {} mmol/L)",
                c("be"),
                c("hco3"),
                c("ph"),
                be_expected.round(2),
                pl.lit(BASE_EXCESS_TOLERANCE),
            ).alias("message"),
        ),
        wide.filter((c("sao2") - sao2_expected).abs() > SAO2_TOLERANCE + _EPS).select(
            _set_where().alias("where"),
            _format(
                "SaO2 {} but pO2 {} gives {} (tolerance {} points)",
                c("sao2"),
                c("po2"),
                sao2_expected.round(2),
                pl.lit(SAO2_TOLERANCE),
            ).alias("message"),
        ),
    ]
    return _problems("lab.blood_gas_relations", pl.concat(findings))


def check_egfr_relation(bill: _Clean) -> list[Problem]:
    """lab.egfr_relation: eGFR is CKD-EPI 2021 of the set's creatinine, the patient's age and sex."""
    wide = (
        bill.wide(CREATININE_CODE, {"scr": CREATININE, "egfr": EGFR})
        .join(bill.ages, left_on=["HASTA_ID", "basvuru_id"], right_on=["HASTA_ID", "SQ_EPISODE"])
        .join(bill.sexes, on="HASTA_ID")
    )
    c = pl.col
    female = c("sex") == "K"
    kappa = pl.when(female).then(CKD_EPI_KAPPA["K"]).otherwise(CKD_EPI_KAPPA["E"])
    alpha = pl.when(female).then(CKD_EPI_ALPHA["K"]).otherwise(CKD_EPI_ALPHA["E"])
    base = (
        CKD_EPI_BASE
        * pl.lit(CKD_EPI_AGE_FACTOR).pow(c("age"))
        * pl.when(female).then(CKD_EPI_FEMALE_FACTOR).otherwise(1.0)
    )
    ratio = c("scr") / kappa
    expected = (
        base
        * pl.min_horizontal(ratio, 1.0).pow(alpha)
        * pl.max_horizontal(ratio, 1.0).pow(CKD_EPI_HIGH_EXPONENT)
    )
    found = wide.filter(
        c("sex").is_not_null()
        & (c("scr") > 0)
        & ((c("egfr") - expected).abs() > EGFR_TOLERANCE + _EPS)
    ).select(
        _set_where().alias("where"),
        _format(
            "eGFR {} but creatinine {}, age {} and sex {} give {} (tolerance {})",
            c("egfr"),
            c("scr"),
            c("age"),
            c("sex"),
            expected.round(1),
            pl.lit(EGFR_TOLERANCE),
        ).alias("message"),
    )
    return _problems("lab.egfr_relation", found)


# --- rx ----------------------------------------------------------------------------------------


def _name_key(name: pl.Expr) -> pl.Expr:
    """A product name as it is compared: folded, with its white space collapsed."""
    return _fold(name).str.replace_all(r"\s+", " ").str.strip_chars()


def check_matches_billed_line(bill: _Clean) -> list[Problem]:
    """rx.matches_billed_line: the prescription rows and the billed drug lines pair off one to one."""
    key = ("patient", "episode", "day", "name", "quantity")
    prescribed = (
        bill.table(TABLE_RECETE)
        .select(
            pl.col("HASTA_ID").alias("patient"),
            pl.col("RF_EPISODE").alias("episode"),
            pl.col("RECETE_TARIH").dt.date().alias("day"),
            _name_key(pl.col("ilac_adi")).alias("name"),
            pl.col("miktar").alias("quantity"),
            pl.col("ilac_adi").alias("prescribed_name"),
        )
        .with_columns(pl.int_range(pl.len()).over(*key).alias("copy"))
    )
    billed = (
        bill.table(TABLE_DRUGS)
        .select(
            pl.col("patient_id").alias("patient"),
            pl.col("episode_id").alias("episode"),
            pl.col("drug_claim_date").str.to_date("%Y-%m-%d", strict=False).alias("day"),
            _name_key(pl.col("drug_name")).alias("name"),
            pl.col("quantity"),
            pl.col("drug_claim_line_id"),
            pl.col("drug_name").alias("billed_name"),
        )
        .with_columns(pl.int_range(pl.len()).over(*key).alias("copy"))
    )
    joined = prescribed.join(billed, on=[*key, "copy"], how="full", coalesce=True)
    unbilled = joined.filter(pl.col("drug_claim_line_id").is_null()).select(
        _format(
            "{} recete_clean[{}|{}|{}]",
            pl.col("patient"),
            pl.col("episode"),
            pl.col("day"),
            pl.col("prescribed_name"),
        ).alias("where"),
        _format(
            "prescription row {} on {} (miktar {}) has no billed drug line of the same patient, "
            "episode, date, name and quantity",
            pl.col("prescribed_name"),
            pl.col("day"),
            pl.col("quantity"),
        ).alias("message"),
    )
    unprescribed = joined.filter(pl.col("prescribed_name").is_null()).select(
        _format("{} drug_claim_lines[{}]", pl.col("patient"), pl.col("drug_claim_line_id")).alias(
            "where"
        ),
        _format(
            "billed drug line {} on {} (quantity {}) has no prescription row in recete_clean",
            pl.col("billed_name"),
            pl.col("day"),
            pl.col("quantity"),
        ).alias("message"),
    )
    return _problems("rx.matches_billed_line", pl.concat([unbilled, unprescribed]))


def _recete_where() -> pl.Expr:
    """`where` of a finding about one prescription row: the patient, then `recete_clean[...]`."""
    return _format(
        "{} recete_clean[{}|{}|{}]",
        pl.col("HASTA_ID"),
        pl.col("RF_EPISODE"),
        pl.col("RECETE_TARIH").dt.date(),
        pl.col("ilac_adi"),
    )


def check_route_vs_product(bill: _Clean) -> list[Problem]:
    """rx.route_vs_product: the route is in the vocabulary and fits what the product name says."""
    text = _fold(pl.concat_str("ilac_adi", "ilac_adi_ham", separator=" ", ignore_nulls=True))
    route = pl.col("verilis_yolu")
    inhalation = text.str.contains(_INHALATION_PATTERN)
    oral = text.str.contains(_ORAL_PATTERN)
    injection = text.str.contains(_INJECTION_PATTERN)
    container = text.str.contains(_CONTAINER_PATTERN)
    # a nebule or an inhalation solution wins over the vial it is sold in; a container word counts
    # as a parenteral product only when the name says no tablet and no inhalation
    inhaled = inhalation
    swallowed = oral & ~injection & ~inhalation
    injected = (injection | (container & ~oral)) & ~inhalation
    both = injection & oral & ~inhalation
    known = route.is_in(list(ROUTES))
    why = _reasons(
        pl.when(route.is_null()).then(pl.lit("the route is missing")),
        pl.when(route.is_not_null() & ~known).then(
            _format(
                "the route {} is not in the closed vocabulary ({})",
                route,
                pl.lit(", ".join(ROUTES)),
            )
        ),
        pl.when(both).then(pl.lit("the name states both an injection and a tablet or capsule")),
        pl.when(known & inhaled & (route != ROUTE_INHALATION)).then(
            _format("a nebule or inhalation product has the route {}", pl.lit(ROUTE_INHALATION))
        ),
        pl.when(known & injected & ~route.is_in(list(PARENTERAL_ROUTES))).then(
            _format(
                "an injection, infusion, vial or bag product has a parenteral route ({})",
                pl.lit(", ".join(PARENTERAL_ROUTES)),
            )
        ),
        pl.when(known & swallowed & (route != ROUTE_ORAL)).then(
            _format("a tablet or capsule product has the route {}", pl.lit(ROUTE_ORAL))
        ),
        pl.when(known & text.str.contains(_LMWH_PATTERN) & (route != ROUTE_SUBCUTANEOUS)).then(
            _format("a low-molecular-weight heparin has the route {}", pl.lit(ROUTE_SUBCUTANEOUS))
        ),
    )
    found = (
        bill.table(TABLE_RECETE)
        .with_columns(why.alias("why"))
        .filter(pl.col("why") != "")
        .select(
            _recete_where().alias("where"),
            _format("route {} for {}: {}", route, pl.col("ilac_adi"), pl.col("why")).alias(
                "message"
            ),
        )
    )
    return _problems("rx.route_vs_product", found)


def check_dose_unit(bill: _Clean) -> list[Problem]:
    """rx.dose_unit: `dozaj_ham` is '<positive count> <Turkish unit>' and the count is `miktar`."""
    dose = pl.col("dozaj_ham")
    shape = r"^([1-9][0-9]*) ([^ ]+)$"
    well_formed = dose.str.contains(shape)
    count = dose.str.extract(shape, 1)
    unit = dose.str.extract(shape, 2)
    english = unit.is_in(list(ENGLISH_UNITS))
    why = _reasons(
        pl.when(dose.is_null()).then(pl.lit("dozaj_ham is missing")),
        pl.when(dose.is_not_null() & ~well_formed).then(
            pl.lit("is not a positive count and one unit word, like '5 flakon'")
        ),
        pl.when(well_formed & english).then(_format("uses the English unit word {}", unit)),
        pl.when(well_formed & ~english & ~unit.is_in(list(DOSE_UNITS))).then(
            _format("uses the unit word {}, which is not in the closed list of Turkish units", unit)
        ),
        pl.when(
            well_formed & (count.cast(pl.Int64, strict=False) != pl.col("miktar")).fill_null(True)
        ).then(_format("the count {} differs from miktar {}", count, pl.col("miktar"))),
    )
    found = (
        bill.table(TABLE_RECETE)
        .with_columns(why.alias("why"))
        .filter(pl.col("why") != "")
        .select(
            _recete_where().alias("where"),
            _format("dozaj_ham {}: {}", dose, pl.col("why")).alias("message"),
        )
    )
    return _problems("rx.dose_unit", found)


def check_required_fields(bill: _Clean) -> list[Problem]:
    """rx.required_fields: no null (and no blank text) in the required prescription columns."""
    frame = bill.table(TABLE_RECETE)
    absent = []
    for column in REQUIRED_RECETE_COLUMNS:
        missing = pl.col(column).is_null()
        if frame.schema[column] == pl.String:
            missing = missing | (pl.col(column).str.strip_chars() == "").fill_null(False)
        absent.append(pl.when(missing).then(pl.lit(column)))
    found = (
        frame.with_columns(pl.concat_str(*absent, separator=", ", ignore_nulls=True).alias("why"))
        .filter(pl.col("why") != "")
        .select(
            _recete_where().alias("where"),
            _format("missing required column(s): {}", pl.col("why")).alias("message"),
        )
    )
    return _problems("rx.required_fields", found)


# --- ana ---------------------------------------------------------------------------------------


def check_vitals_bounds(bill: _Clean) -> list[Problem]:
    """ana.vitals_bounds: vital signs and age inside their bounds, diastolic below systolic, BMI."""
    parts: list[pl.Expr] = []
    for column, (low, high) in VITALS_BOUNDS.items():
        value = pl.col(column)
        parts.append(pl.when(value.is_null()).then(pl.lit(f"{column} is missing")))
        parts.append(
            pl.when((value < low) | (value > high)).then(
                _format(f"{column} {{}} is outside {low:g}..{high:g}", value)
            )
        )
    diastolic, systolic = pl.col("KB-D"), pl.col("KB-S")
    parts.append(
        pl.when(diastolic >= systolic).then(
            _format("KB-D {} is not below KB-S {}", diastolic, systolic)
        )
    )
    height, weight, bmi = pl.col("Boy"), pl.col("Kilo"), pl.col("BMI")
    computed = weight / (height / 100.0).pow(2)
    parts.append(pl.when(bmi.is_null()).then(pl.lit("BMI is missing")))
    parts.append(
        pl.when((height > 0) & ((bmi - computed).abs() > BMI_TOLERANCE + _EPS)).then(
            _format("BMI {} differs from Kilo / (Boy / 100)^2 = {}", bmi, computed.round(1))
        )
    )
    sex = pl.col("CINSIYET")
    parts.append(
        pl.when(~sex.is_in(list(SEX_CODES)).fill_null(False)).then(
            _format("CINSIYET {} is neither E nor K", sex)
        )
    )
    parts.append(
        pl.when(sex.n_unique().over("HASTA_ID") > 1).then(
            pl.lit("CINSIYET differs between the episodes of the patient")
        )
    )
    found = (
        bill.table(TABLE_ANADATA)
        .with_columns(_reasons(*parts).alias("why"))
        .filter(pl.col("why") != "")
        .select(
            _format("{} anadata_clean[{}]", pl.col("HASTA_ID"), pl.col("SQ_EPISODE")).alias(
                "where"
            ),
            pl.col("why").alias("message"),
        )
    )
    return _problems("ana.vitals_bounds", found)


# --- the registry and the entry point ------------------------------------------------------------

CHECK_FUNCTIONS: dict[str, Callable[[_Clean], list[Problem]]] = {
    "lab.value_bounds": check_value_bounds,
    "lab.hemogram_relations": check_hemogram_relations,
    "lab.flag_and_limits": check_flag_and_limits,
    "lab.unit_matches_reference": check_unit_matches_reference,
    "lab.result_sets_match_bill": check_result_sets_match_bill,
    "lab.blood_gas_relations": check_blood_gas_relations,
    "lab.egfr_relation": check_egfr_relation,
    "rx.matches_billed_line": check_matches_billed_line,
    "rx.route_vs_product": check_route_vs_product,
    "rx.dose_unit": check_dose_unit,
    "rx.required_fields": check_required_fields,
    "ana.vitals_bounds": check_vitals_bounds,
}


def check_clean_plausibility(
    tables: Mapping[str, pl.DataFrame],
    clean_tables: Mapping[str, pl.DataFrame],
    *,
    context: CleanPlausibilityContext | None = None,
    only: Iterable[str] | str | None = None,
) -> list[Problem]:
    """Every plausibility problem of the clean tables `clean_tables` against the claims `tables`.

    `only` restricts the run to some check ids; a check reads only the tables it needs, so a run with
    `only` needs only those. The problems come in the order of `CHECKS`, then by `where`.
    """
    if only is None:
        selected = list(CHECKS)
    else:
        wanted = {only} if isinstance(only, str) else set(only)
        unknown = sorted(wanted - set(CHECKS))
        if unknown:
            raise KeyError(f"unregistered check id(s) {unknown}")
        selected = [check for check in CHECKS if check in wanted]
    bill = _Clean(tables, clean_tables, context if context is not None else default_context())
    return [problem for check in selected for problem in CHECK_FUNCTIONS[check](bill)]
