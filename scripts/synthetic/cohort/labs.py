"""Lab reference reader and deterministic coherent lab result generator (`lab_clean.parquet`)."""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, time
from functools import cached_property, lru_cache
import hashlib
from pathlib import Path
import re
from typing import Any, Literal

import polars as pl

from scripts.synthetic.pathways import Pathway, load_all

from .clinical import PatientClinical, PatientLabs, ShowcaseClinical, load_clinical
from .compose import ComposedClaim
from .ids import PATIENT_ID_RE
from .tables import TableSchemaError

REPO = Path(__file__).resolve().parents[3]
LAB_REFERENCE_PATH = REPO / "data" / "synthetic" / "reference" / "lab_reference.csv"

BILLED_LAB_CODES: frozenset[str] = frozenset(
    {
        "L100300",
        "L101280",
        "L101850",
        "L102090",
        "L102890",
        "L103900",
        "L104780",
        "L106150",
        "L106240",
        "L106910",
        "L107010",
        "L107020",
        "L107360",
        "L107420",
    }
)

STRIP_GRADES: tuple[str, ...] = ("Negatif", "Eser", "+", "++", "+++", "++++")
SINGLE_STRIP_GRADES: frozenset[str] = frozenset((*STRIP_GRADES[1:], "Pozitif"))

ORGAN_SISTEMI_BY_TEST_KEY: dict[str, str] = {
    "hemogram": "Hematoloji",
    "d_dimer": "Hematoloji",
    "alt": "Biyokimya",
    "ast": "Biyokimya",
    "crp": "Biyokimya",
    "glucose": "Biyokimya",
    "blood_gas_arterial": "Biyokimya",
    "blood_gas_venous": "Biyokimya",
    "creatinine": "Biyokimya",
    "potassium": "Biyokimya",
    "procalcitonin": "Biyokimya",
    "sodium": "Biyokimya",
    "urinalysis": "Biyokimya",
    "troponin_i": "Biyokimya",
    "urea": "Biyokimya",
}

DIFF_PARAMETER_NAMES: tuple[str, ...] = (
    "NEU# (Nötrofil)",
    "LYM# (Lenfosit)",
    "MONO# (Monosit)",
    "EOS# (Eozinofil)",
    "BASO# (Bazofil)",
)

DIFF_PROFILES: dict[str, dict[str, tuple[float, float]]] = {
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

RED_CELL_DERIVED_PARAMS: frozenset[str] = frozenset(
    {
        "RBC (Eritrosit)",
        "HCT (Hematokrit)",
        "MCHC",
    }
)

BLOOD_GAS_DERIVED_PARAMS: frozenset[str] = frozenset(
    {
        "HCO3",
        "BE (baz fazlası)",
        "SaO2",
    }
)

EGFR_PARAM_NAME = "eGFR (CKD-EPI 2021, hesaplanan)"
CREATININE_PARAM_NAME = "Kreatinin"

_TRAILING_PAREN_RE = re.compile(r"\s*\([^()]*\)\s*$")
_TRAILING_WITH_RE = re.compile(
    r"\s+(?:even\s+)?with\s+(?:MCV\s+\d+–\d+|normal\s+blood\s+glucose|\d+–\d+\s+RBC/HPF)\s*$"
)
_EGFR_BAND_RE = re.compile(r"^eGFR\s+(\d+(?:\.\d+)?)–(\d+(?:\.\d+)?)$")
_SEX_PART_RE = re.compile(r"^([MF])\s+([+-]?\d+(?:\.\d+)?)–([+-]?\d+(?:\.\d+)?)$")
_ENDASH_RANGE_RE = re.compile(r"^([+-]?\d+(?:\.\d+)?)–([+-]?\d+(?:\.\d+)?)$")
_TO_RANGE_RE = re.compile(r"^([+-]?\d+(?:\.\d+)?)\s+to\s+([+-]?\d+(?:\.\d+)?)$")
_EGFR_AGE_BANDS_RE = re.compile(
    r"^age\s+18–39:\s*(\d+)–(\d+);\s*40–59:\s*(\d+)–(\d+);\s*60–69:\s*(\d+)–(\d+);\s*≥70:\s*(\d+)–(\d+)"
)


class LabReferenceError(TableSchemaError):
    """Raised when `lab_reference.csv` or an `abnormal_states` item violates the strict grammar."""


class UnsupportedLabStateError(TableSchemaError):
    """Raised when a clinical YAML `labs.states` entry references an unsupported prose state."""


class DerivedLabParameterError(TableSchemaError):
    """Raised when a clinical YAML `labs.states` entry specifies a state on a derived parameter."""


class LabCoherenceError(TableSchemaError):
    """Raised when derived lab values fail coherence rules or exceed the 50-try salt limit."""


StateGrammarKind = Literal[
    "num_range",
    "to_range",
    "sex_range",
    "or_range",
    "egfr_band",
    "grade_range",
    "grade_single",
]


@dataclass(frozen=True)
class ParsedState:
    """One parsed `name: range` item from `abnormal_states` in `lab_reference.csv`."""

    name: str
    full_name: str
    raw_text: str
    kind: StateGrammarKind
    low: float | None = None
    high: float | None = None
    sex_ranges: dict[str, tuple[float, float]] = field(default_factory=dict)
    alternatives: tuple[tuple[float, float], ...] = ()
    grade_low: str | None = None
    grade_high: str | None = None
    number_tokens: tuple[str, ...] = ()

    def range_for_sex(self, sex: str) -> tuple[float, float]:
        """Return `(low, high)` for `sex` (`'M'` or `'F'`)."""
        if self.kind == "sex_range":
            if sex not in self.sex_ranges:
                raise LabCoherenceError(
                    f"State {self.name!r} ({self.raw_text!r}) has no range for sex {sex!r}"
                )
            return self.sex_ranges[sex]
        if self.low is None or self.high is None:
            raise LabCoherenceError(f"State {self.name!r} has no numeric range")
        return self.low, self.high


@dataclass(frozen=True)
class UnsupportedState:
    """Prose item in `abnormal_states` without a standalone numeric/grade/eGFR range."""

    name: str
    full_name: str
    raw_text: str


@dataclass(frozen=True)
class LabParameterSpec:
    """One parameter row from `data/synthetic/reference/lab_reference.csv`."""

    test_key: str
    ek2b_code: str
    catalog_name: str
    result_parameter: str
    unit: str
    ref_low_male: float | None
    ref_high_male: float | None
    ref_low_female: float | None
    ref_high_female: float | None
    normal_value_range: str
    abnormal_states_raw: str
    decimals: int
    is_qualitative_strip: bool
    parsed_states: tuple[ParsedState, ...]
    unsupported_states: tuple[UnsupportedState, ...]
    states_by_id: dict[str, ParsedState]
    unsupported_by_id: dict[str, UnsupportedState]

    @property
    def key(self) -> str:
        return f"{self.ek2b_code}|{self.result_parameter}"

    def ref_limits(self, sex: str) -> tuple[float | None, float | None]:
        if sex == "M":
            return self.ref_low_male, self.ref_high_male
        if sex == "F":
            return self.ref_low_female, self.ref_high_female
        raise LabReferenceError(f"Unsupported sex {sex!r}")

    def normal_draw_limits(self, sex: str) -> tuple[float, float]:
        lo, hi = self.ref_limits(sex)
        resolved_lo = 0.0 if lo is None else lo
        if hi is None:
            raise LabReferenceError(
                f"{self.key}: missing upper reference limit for sex {sex!r} normal draw"
            )
        return resolved_lo, hi

    def has_state_in_csv(self, state_id: str) -> bool:
        if state_id == "normal":
            return True
        return state_id in self.states_by_id or state_id in self.unsupported_by_id

    def resolve_state(self, state_id: str) -> ParsedState | None:
        if state_id == "normal":
            return None
        if state_id in self.unsupported_by_id:
            unsup = self.unsupported_by_id[state_id]
            raise UnsupportedLabStateError(
                f"{self.key}: state {state_id!r} ({unsup.raw_text!r}) is an unsupported prose state"
            )
        if state_id not in self.states_by_id:
            raise LabReferenceError(
                f"{self.key}: unknown state {state_id!r} (available: {sorted(self.states_by_id)})"
            )
        return self.states_by_id[state_id]


@dataclass(frozen=True)
class LabReference:
    """Loaded and parsed lab reference table (`data/synthetic/reference/lab_reference.csv`)."""

    all_parameters: tuple[LabParameterSpec, ...]
    billed_code_parameters: tuple[LabParameterSpec, ...]
    by_code: dict[str, tuple[LabParameterSpec, ...]]
    by_key: dict[str, LabParameterSpec]
    egfr_age_bands: tuple[tuple[int, int, float, float], ...]

    def position_of(self, code: str, parameter: str) -> int:
        """Position of `parameter` among the CSV parameters of `code` (0 is the first)."""
        return [s.result_parameter for s in self.by_code[code]].index(parameter)

    @cached_property
    def parameter_table(self) -> pl.DataFrame:
        """The active parameters (arterial blood gas only) in CSV order, one row each.

        `SUB_CODE` and `parametre` are the keys of `lab_clean`; `position` counts from 0 inside the
        code and `n_params` is the number of parameters of the code, so a result set of the
        code is `n_params` consecutive rows with `position` 0, 1, 2, and so on.
        """
        specs = [spec for group in self.by_code.values() for spec in group]
        return pl.DataFrame(
            {
                "SUB_CODE": [s.ek2b_code for s in specs],
                "parametre": [s.result_parameter for s in specs],
                "csv_unit": [s.unit for s in specs],
                "is_strip": [s.is_qualitative_strip for s in specs],
                "ref_low_male": [s.ref_low_male for s in specs],
                "ref_high_male": [s.ref_high_male for s in specs],
                "ref_low_female": [s.ref_low_female for s in specs],
                "ref_high_female": [s.ref_high_female for s in specs],
            },
            schema={
                "SUB_CODE": pl.String,
                "parametre": pl.String,
                "csv_unit": pl.String,
                "is_strip": pl.Boolean,
                "ref_low_male": pl.Float64,
                "ref_high_male": pl.Float64,
                "ref_low_female": pl.Float64,
                "ref_high_female": pl.Float64,
            },
        ).with_columns(
            pl.int_range(pl.len()).over("SUB_CODE").alias("position"),
            pl.len().over("SUB_CODE").alias("n_params"),
        )


def _count_decimals(num_str: str) -> int:
    cleaned = num_str.strip().lstrip("+-")
    if "." not in cleaned:
        return 0
    return len(cleaned.split(".", 1)[1])


def parse_abnormal_state_item(
    item: str,
    *,
    is_qualitative_strip: bool = False,
    context: str = "",
) -> ParsedState | UnsupportedState:
    """Strictly parse a single `; `-separated item from `abnormal_states`."""
    text = item.strip()
    if not text:
        raise LabReferenceError(f"{context}: empty abnormal_states item")

    if ":" not in text:
        low_text = text.lower()
        if low_text.startswith(("not interpreted", "rarely abnormal")) and not re.search(
            r"\d", text
        ):
            short = text.split(" (", 1)[0].strip()
            return UnsupportedState(name=short, full_name=text, raw_text=text)
        raise LabReferenceError(f"{context}: abnormal_states item missing colon: {text!r}")

    raw_name, raw_rhs = text.split(":", 1)
    full_name = raw_name.strip()
    short_name = full_name.split(" (", 1)[0].strip()
    if not short_name:
        raise LabReferenceError(f"{context}: empty state name in {text!r}")

    rhs = raw_rhs.strip()
    if not rhs:
        raise LabReferenceError(f"{context}: empty range for state {full_name!r}")

    if "baseline" in rhs or "below " in rhs:
        return UnsupportedState(name=short_name, full_name=full_name, raw_text=text)

    rhs = _TRAILING_PAREN_RE.sub("", rhs).strip()
    rhs = _TRAILING_WITH_RE.sub("", rhs).strip()

    if (
        is_qualitative_strip
        or rhs in SINGLE_STRIP_GRADES
        or any(rhs.startswith(f"{g} to ") for g in STRIP_GRADES)
    ):
        if " to " in rhs:
            g_lo, g_hi = (part.strip() for part in rhs.split(" to ", 1))
            if g_lo not in STRIP_GRADES or g_hi not in STRIP_GRADES:
                raise LabReferenceError(f"{context}: invalid strip grade range {rhs!r} in {text!r}")
            if STRIP_GRADES.index(g_lo) >= STRIP_GRADES.index(g_hi):
                raise LabReferenceError(
                    f"{context}: strip grade range out of order {rhs!r} in {text!r}"
                )
            return ParsedState(
                name=short_name,
                full_name=full_name,
                raw_text=text,
                kind="grade_range",
                grade_low=g_lo,
                grade_high=g_hi,
            )
        if rhs in SINGLE_STRIP_GRADES:
            return ParsedState(
                name=short_name,
                full_name=full_name,
                raw_text=text,
                kind="grade_single",
                grade_low=rhs,
                grade_high=rhs,
            )
        raise LabReferenceError(f"{context}: invalid strip grade state {rhs!r} in {text!r}")

    if rhs.startswith("eGFR"):
        m_egfr = _EGFR_BAND_RE.fullmatch(rhs)
        if m_egfr is None:
            raise LabReferenceError(f"{context}: malformed eGFR band {rhs!r} in {text!r}")
        s_lo, s_hi = m_egfr.group(1), m_egfr.group(2)
        lo, hi = float(s_lo), float(s_hi)
        if lo >= hi:
            raise LabReferenceError(f"{context}: eGFR band low >= high in {rhs!r} ({text!r})")
        return ParsedState(
            name=short_name,
            full_name=full_name,
            raw_text=text,
            kind="egfr_band",
            low=lo,
            high=hi,
            number_tokens=(s_lo, s_hi),
        )

    if rhs.startswith(("M ", "F ")) or re.match(r"^[A-Z]\s+\d", rhs):
        parts = [p.strip() for p in rhs.split(",")]
        sex_ranges: dict[str, tuple[float, float]] = {}
        tokens: list[str] = []
        for part in parts:
            m_sex = _SEX_PART_RE.fullmatch(part)
            if m_sex is None:
                raise LabReferenceError(
                    f"{context}: malformed sex-specific range {part!r} in {text!r}"
                )
            sex_key, s_lo, s_hi = m_sex.group(1), m_sex.group(2), m_sex.group(3)
            lo, hi = float(s_lo), float(s_hi)
            if lo >= hi:
                raise LabReferenceError(
                    f"{context}: sex-specific range low >= high in {part!r} ({text!r})"
                )
            if sex_key in sex_ranges:
                raise LabReferenceError(f"{context}: duplicate sex key {sex_key!r} in {text!r}")
            sex_ranges[sex_key] = (lo, hi)
            tokens.extend((s_lo, s_hi))
        first_lo, first_hi = next(iter(sex_ranges.values()))
        return ParsedState(
            name=short_name,
            full_name=full_name,
            raw_text=text,
            kind="sex_range",
            low=first_lo,
            high=first_hi,
            sex_ranges=sex_ranges,
            number_tokens=tuple(tokens),
        )

    if " or " in rhs:
        raw_alts = [a.strip() for a in rhs.split(" or ")]
        alts: list[tuple[float, float]] = []
        tokens = []
        for alt in raw_alts:
            m_alt = _ENDASH_RANGE_RE.fullmatch(alt)
            if m_alt is None:
                raise LabReferenceError(f"{context}: malformed alternative {alt!r} in {text!r}")
            s_lo, s_hi = m_alt.group(1), m_alt.group(2)
            lo, hi = float(s_lo), float(s_hi)
            if lo >= hi:
                raise LabReferenceError(
                    f"{context}: alternative range low >= high in {alt!r} ({text!r})"
                )
            alts.append((lo, hi))
            tokens.extend((s_lo, s_hi))
        return ParsedState(
            name=short_name,
            full_name=full_name,
            raw_text=text,
            kind="or_range",
            low=alts[0][0],
            high=alts[0][1],
            alternatives=tuple(alts),
            number_tokens=tuple(tokens),
        )

    if " to " in rhs:
        m_to = _TO_RANGE_RE.fullmatch(rhs)
        if m_to is None:
            raise LabReferenceError(f"{context}: malformed signed 'to' range {rhs!r} in {text!r}")
        s_lo, s_hi = m_to.group(1), m_to.group(2)
        lo, hi = float(s_lo), float(s_hi)
        if lo >= hi:
            raise LabReferenceError(f"{context}: 'to' range low >= high in {rhs!r} ({text!r})")
        return ParsedState(
            name=short_name,
            full_name=full_name,
            raw_text=text,
            kind="to_range",
            low=lo,
            high=hi,
            number_tokens=(s_lo, s_hi),
        )

    m_num = _ENDASH_RANGE_RE.fullmatch(rhs)
    if m_num is None:
        raise LabReferenceError(f"{context}: unrecognized range syntax {rhs!r} in {text!r}")
    s_lo, s_hi = m_num.group(1), m_num.group(2)
    lo, hi = float(s_lo), float(s_hi)
    if lo >= hi:
        raise LabReferenceError(f"{context}: numeric range low >= high in {rhs!r} ({text!r})")
    return ParsedState(
        name=short_name,
        full_name=full_name,
        raw_text=text,
        kind="num_range",
        low=lo,
        high=hi,
        number_tokens=(s_lo, s_hi),
    )


def parse_abnormal_states(
    abnormal_states_raw: str,
    *,
    is_qualitative_strip: bool = False,
    context: str = "",
) -> tuple[tuple[ParsedState, ...], tuple[UnsupportedState, ...]]:
    """Parse a semicolon-separated `abnormal_states` string into parsed and unsupported items."""
    raw = (abnormal_states_raw or "").strip()
    if not raw:
        return (), ()
    items = [part.strip() for part in raw.split("; ") if part.strip()]
    parsed_list: list[ParsedState] = []
    unsup_list: list[UnsupportedState] = []
    for item in items:
        res = parse_abnormal_state_item(
            item,
            is_qualitative_strip=is_qualitative_strip,
            context=context,
        )
        if isinstance(res, ParsedState):
            parsed_list.append(res)
        else:
            unsup_list.append(res)
    return tuple(parsed_list), tuple(unsup_list)


_CSV_COLUMNS: tuple[str, ...] = (
    "test_key",
    "ek2b_code",
    "catalog_name",
    "result_parameter",
    "unit",
    "ref_low_male",
    "ref_high_male",
    "ref_low_female",
    "ref_high_female",
    "normal_value_range",
    "abnormal_states",
)
_LIMIT_COLUMNS: tuple[str, ...] = (
    "ref_low_male",
    "ref_high_male",
    "ref_low_female",
    "ref_high_female",
)


def _parse_egfr_age_bands(normal_range_text: str) -> tuple[tuple[int, int, float, float], ...]:
    m = _EGFR_AGE_BANDS_RE.match(normal_range_text.strip())
    if m is None:
        raise LabReferenceError(
            f"L104780|{EGFR_PARAM_NAME}: cannot parse eGFR age bands from {normal_range_text!r}"
        )
    g = [float(x) for x in m.groups()]
    return (
        (18, 39, g[0], g[1]),
        (40, 59, g[2], g[3]),
        (60, 69, g[4], g[5]),
        (70, 200, g[6], g[7]),
    )


def _typed_csv(df: pl.DataFrame) -> pl.DataFrame:
    """The CSV with trimmed text, Float64 limits, the strip flag and the decimals of the limits.

    Blank cells are empty strings (blank limits become null). The decimals of a limit are the digits
    after its decimal point. A limit that is not a number is an error.
    """
    text = df.select(
        *(pl.col(c).cast(pl.String).fill_null("").str.strip_chars() for c in _CSV_COLUMNS)
    )
    limit_values = [
        pl.col(c).replace("", None).cast(pl.Float64, strict=False) for c in _LIMIT_COLUMNS
    ]
    not_a_number = text.filter(
        pl.any_horizontal(
            *(
                (pl.col(c) != "") & v.is_null()
                for c, v in zip(_LIMIT_COLUMNS, limit_values, strict=True)
            )
        )
    )
    if not not_a_number.is_empty():
        first = not_a_number.select("ek2b_code", "result_parameter", *_LIMIT_COLUMNS)
        raise LabReferenceError(f"invalid numeric limit in lab_reference.csv: {first.head(1)}")
    return text.with_columns(
        pl.max_horizontal(
            *(
                pl.col(c).str.extract(r"\.(\d+)$", 1).str.len_chars().fill_null(0)
                for c in _LIMIT_COLUMNS
            )
        ).alias("limit_decimals"),
        (
            (pl.concat_str(*_LIMIT_COLUMNS) == "") & (pl.col("normal_value_range") == "Negatif")
        ).alias("is_strip"),
    ).with_columns(*(v.alias(c) for c, v in zip(_LIMIT_COLUMNS, limit_values, strict=True)))


def _parse_states_of(
    abnormal_states: str, *, is_strip: bool, billed: bool, context: str
) -> tuple[tuple[ParsedState, ...], tuple[UnsupportedState, ...]]:
    """The grammar of the 14 billed codes is strict; another code with prose it cannot read is unsupported."""
    try:
        return parse_abnormal_states(
            abnormal_states, is_qualitative_strip=is_strip, context=context
        )
    except LabReferenceError:
        if billed:
            raise
        return (), (UnsupportedState(abnormal_states, abnormal_states, abnormal_states),)


def _build_parameter_spec(line: Mapping[str, Any]) -> LabParameterSpec:
    """One frozen spec from one typed CSV line (see `_typed_csv`)."""
    code, param, test_key = line["ek2b_code"], line["result_parameter"], line["test_key"]
    context = f"{code}|{param} ({test_key})"
    parsed_states, unsupported_states = _parse_states_of(
        line["abnormal_states"],
        is_strip=line["is_strip"],
        billed=code in BILLED_LAB_CODES,
        context=context,
    )
    state_tokens = (
        token for st in parsed_states if st.kind != "egfr_band" for token in st.number_tokens
    )
    decimals = min(3, max((line["limit_decimals"], *map(_count_decimals, state_tokens))))

    states_by_id: dict[str, ParsedState] = {}
    for st in parsed_states:
        states_by_id[st.name] = st
        states_by_id[st.full_name] = st

    unsupported_by_id: dict[str, UnsupportedState] = {}
    for unsup in unsupported_states:
        unsupported_by_id[unsup.name] = unsup
        unsupported_by_id[unsup.full_name] = unsup
        unsupported_by_id[unsup.raw_text] = unsup

    return LabParameterSpec(
        test_key=test_key,
        ek2b_code=code,
        catalog_name=line["catalog_name"],
        result_parameter=param,
        unit=line["unit"],
        ref_low_male=line["ref_low_male"],
        ref_high_male=line["ref_high_male"],
        ref_low_female=line["ref_low_female"],
        ref_high_female=line["ref_high_female"],
        normal_value_range=line["normal_value_range"],
        abnormal_states_raw=line["abnormal_states"],
        decimals=decimals,
        is_qualitative_strip=line["is_strip"],
        parsed_states=parsed_states,
        unsupported_states=unsupported_states,
        states_by_id=states_by_id,
        unsupported_by_id=unsupported_by_id,
    )


def load_lab_reference_df(df: pl.DataFrame) -> LabReference:
    """Parse a Polars DataFrame of `lab_reference.csv` into `LabReference`."""
    typed = _typed_csv(df)
    # Polars has trimmed and typed the table. What is left is the grammar of the `abnormal_states`
    # cells, a per-string parser, and one frozen spec object per CSV line (96 lines, built once).
    names = typed.columns
    all_specs = tuple(
        _build_parameter_spec(dict(zip(names, cells, strict=True)))
        for cells in zip(*typed.iter_columns(), strict=True)
    )
    billed_specs = tuple(s for s in all_specs if s.ek2b_code in BILLED_LAB_CODES)

    by_code_lists: dict[str, list[LabParameterSpec]] = {}
    by_key: dict[str, LabParameterSpec] = {}
    for s in all_specs:
        if s.test_key == "blood_gas_venous":
            continue  # the venous variant shares the code L103900 and is not read as a second set
        by_code_lists.setdefault(s.ek2b_code, []).append(s)
        by_key[s.key] = s

    missing_codes = sorted(BILLED_LAB_CODES - set(by_code_lists))
    if missing_codes:
        raise LabReferenceError(f"Missing billed lab codes in reference: {missing_codes}")
    egfr_row = by_key.get(f"L104780|{EGFR_PARAM_NAME}")
    if egfr_row is None:
        raise LabReferenceError("Missing eGFR age bands row in reference")

    return LabReference(
        all_parameters=all_specs,
        billed_code_parameters=billed_specs,
        by_code={k: tuple(v) for k, v in by_code_lists.items()},
        by_key=by_key,
        egfr_age_bands=_parse_egfr_age_bands(egfr_row.normal_value_range),
    )


@lru_cache(maxsize=4)
def load_lab_reference(path: Path | str = LAB_REFERENCE_PATH) -> LabReference:
    """Load and parse `data/synthetic/reference/lab_reference.csv` with Polars."""
    csv_path = Path(path)
    df = pl.read_csv(csv_path, infer_schema_length=0)
    return load_lab_reference_df(df)


def draw_u(patient_id: str, code: str, parameter: str, k: int, salt: int = 0) -> float:
    """Deterministic uniform draw in `[0, 1)` from SHA-256 of `patient_id|code|parameter|k|salt`."""
    payload = f"{patient_id}|{code}|{parameter}|{k}|{salt}".encode()
    digest8 = hashlib.sha256(payload).digest()[:8]
    return int.from_bytes(digest8, "big") / float(2**64)


def round_param(value: float, decimals: int) -> float:
    """Round `value` to `decimals` (0..3) as a Python float."""
    if decimals <= 0:
        return float(round(value))
    return round(value, decimals)


def draw_numeric_value(
    spec: LabParameterSpec,
    *,
    patient_id: str,
    sex: str,
    k: int,
    state_id: str = "normal",
    salt: int = 0,
) -> float:
    """Draw a numeric value for `spec` in its normal central band or state band."""
    u = draw_u(patient_id, spec.ek2b_code, spec.result_parameter, k, salt)
    parsed = spec.resolve_state(state_id)
    if parsed is None:
        lo, hi = spec.normal_draw_limits(sex)
        raw = lo + (hi - lo) * (0.30 + 0.40 * u)
    else:
        lo, hi = parsed.range_for_sex(sex)
        raw = lo + (hi - lo) * (0.20 + 0.60 * u)
    return round_param(raw, spec.decimals)


def draw_strip_grade(
    spec: LabParameterSpec,
    *,
    patient_id: str,
    k: int,
    state_id: str = "normal",
    salt: int = 0,
) -> str:
    """Draw a qualitative urinalysis strip grade (R6)."""
    parsed = spec.resolve_state(state_id)
    if parsed is None:
        return "Negatif"
    if parsed.kind == "grade_single":
        assert parsed.grade_low is not None
        return parsed.grade_low
    if parsed.kind == "grade_range":
        assert parsed.grade_low is not None and parsed.grade_high is not None
        i_lo = STRIP_GRADES.index(parsed.grade_low)
        i_hi = STRIP_GRADES.index(parsed.grade_high)
        u = draw_u(patient_id, spec.ek2b_code, spec.result_parameter, k, salt)
        idx = round(i_lo + (i_hi - i_lo) * (0.20 + 0.60 * u))
        idx = max(i_lo, min(i_hi, idx))
        return STRIP_GRADES[idx]
    raise LabCoherenceError(f"{spec.key}: expected strip grade state, got {parsed.kind!r}")


def is_abnormal_numeric(value: float, ref_alt: float | None, ref_ust: float | None) -> bool:
    """Return True when `value` is strictly below `ref_alt` or strictly above `ref_ust` (R5)."""
    if ref_alt is not None and value < ref_alt:
        return True
    if ref_ust is not None and value > ref_ust:
        return True
    return False


def is_abnormal_strip(grade: str) -> bool:
    """Return True when a qualitative strip grade is not `'Negatif'` (R5)."""
    return grade != "Negatif"


def ckd_epi_2021(scr: float, age: int, sex: str) -> float:
    """Compute CKD-EPI 2021 race-free eGFR from serum creatinine `scr`, `age`, and `sex`."""
    kappa = 0.7 if sex == "F" else 0.9
    alpha = -0.241 if sex == "F" else -0.302
    sex_factor = 1.012 if sex == "F" else 1.0
    ratio = scr / kappa
    return (
        142.0
        * (min(ratio, 1.0) ** alpha)
        * (max(ratio, 1.0) ** -1.200)
        * (0.9938**age)
        * sex_factor
    )


def ckd_epi_2021_expr(scr: pl.Expr, age: pl.Expr, female: pl.Expr) -> pl.Expr:
    """`ckd_epi_2021` on columns: `scr` and `age` expressions, `female` a Boolean expression."""
    kappa = pl.when(female).then(0.7).otherwise(0.9)
    alpha = pl.when(female).then(-0.241).otherwise(-0.302)
    ratio = scr / kappa
    return (
        142.0
        * pl.min_horizontal(ratio, pl.lit(1.0)).pow(alpha)
        * pl.max_horizontal(ratio, pl.lit(1.0)).pow(-1.200)
        * pl.lit(0.9938).pow(age)
        * pl.when(female).then(1.012).otherwise(1.0)
    )


def invert_ckd_epi_2021(target_egfr: float, age: int, sex: str) -> float:
    """Invert CKD-EPI 2021 equation to obtain serum creatinine `Scr` from `target_egfr` (R3)."""
    kappa = 0.7 if sex == "F" else 0.9
    alpha = -0.241 if sex == "F" else -0.302
    sex_factor = 1.012 if sex == "F" else 1.0
    a_val = 142.0 * (0.9938**age) * sex_factor
    if target_egfr >= a_val:
        return kappa * ((target_egfr / a_val) ** (1.0 / alpha))
    return kappa * ((target_egfr / a_val) ** (-1.0 / 1.200))


# The three blood-gas formulas are written once with plain arithmetic, so they run on floats (the
# generator) and on Polars expressions (the coherence check).
def _hco3(ph: Any, pco2: Any) -> Any:
    return 0.0307 * pco2 * 10.0 ** (ph - 6.1)


def _base_excess(ph: Any, hco3: Any) -> Any:
    return 0.93 * (hco3 - 24.4 + 14.8 * (ph - 7.4))


def _sao2(po2: Any) -> Any:
    return 100.0 / (1.0 + 23400.0 / (po2**3 + 150.0 * po2))


def henderson_hasselbalch_hco3(ph: float, pco2: float) -> float:
    """Compute arterial `HCO3 = 0.0307 * pCO2 * 10^(pH - 6.1)` rounded to 1 decimal (R4)."""
    return round(_hco3(ph, pco2), 1)


def base_excess_from_ph_hco3(ph: float, hco3: float) -> float:
    """Compute arterial `BE = 0.93 * (HCO3 - 24.4 + 14.8 * (pH - 7.4))` rounded to 1 decimal (R4)."""
    return round(_base_excess(ph, hco3), 1)


def severinghaus_sao2(po2: float) -> float:
    """Compute arterial `SaO2 = 100 / (1 + 23400 / (pO2^3 + 150 * pO2))` rounded to 1 decimal (R4)."""
    return round(_sao2(po2), 1)


def _state_for_occurrence(
    states_map: Mapping[str, str | Sequence[str]],
    key: str,
    k: int,
) -> str:
    if key not in states_map:
        return "normal"
    entry = states_map[key]
    if isinstance(entry, str):
        return entry
    if not entry:
        return "normal"
    idx = min(k - 1, len(entry) - 1)
    return str(entry[idx])


def _value_in_own_state_ranges(spec: LabParameterSpec, value: float, sex: str) -> bool:
    for st in spec.parsed_states:
        if st.kind == "sex_range" and sex not in st.sex_ranges:
            continue
        lo, hi = st.range_for_sex(sex)
        if lo <= value <= hi:
            return True
    return False


def _generate_hemogram_values(
    specs: Sequence[LabParameterSpec],
    *,
    patient_id: str,
    sex: str,
    k: int,
    states_map: Mapping[str, str | Sequence[str]],
) -> dict[str, float]:
    spec_by_param = {s.result_parameter: s for s in specs}

    for derived_p in RED_CELL_DERIVED_PARAMS:
        st = _state_for_occurrence(states_map, f"L107020|{derived_p}", k)
        if st != "normal":
            raise DerivedLabParameterError(
                f"{patient_id} L107020|{derived_p}: state {st!r} not allowed (driven by HGB, MCV, MCH)"
            )

    for diff_p in DIFF_PARAMETER_NAMES:
        st = _state_for_occurrence(states_map, f"L107020|{diff_p}", k)
        if st != "normal":
            spec_by_param[diff_p].resolve_state(st)
            raise DerivedLabParameterError(
                f"{patient_id} L107020|{diff_p}: state {st!r} not allowed (derived from WBC differential)"
            )

    wbc_spec = spec_by_param["WBC (Lökosit)"]
    wbc_state = _state_for_occurrence(states_map, wbc_spec.key, k)
    wbc_val = draw_numeric_value(
        wbc_spec,
        patient_id=patient_id,
        sex=sex,
        k=k,
        state_id=wbc_state,
        salt=0,
    )

    profile_key = wbc_state if wbc_state in DIFF_PROFILES else "normal"
    profile = DIFF_PROFILES[profile_key]
    raw_pcts: dict[str, float] = {}
    for diff_p in DIFF_PARAMETER_NAMES:
        p_lo, p_hi = profile[diff_p]
        u_p = draw_u(patient_id, "L107020", diff_p, k, 0)
        raw_pcts[diff_p] = p_lo + (p_hi - p_lo) * u_p
    pct_sum = sum(raw_pcts.values())
    diff_counts: dict[str, float] = {}
    for diff_p in DIFF_PARAMETER_NAMES:
        scaled_pct = raw_pcts[diff_p] * 100.0 / pct_sum
        diff_counts[diff_p] = round(wbc_val * scaled_pct / 100.0, 2)
    other_sum = sum(v for p, v in diff_counts.items() if p != "NEU# (Nötrofil)")
    diff_counts["NEU# (Nötrofil)"] = round(wbc_val - other_sum, 2)

    hgb_spec = spec_by_param["HGB (Hemoglobin)"]
    mcv_spec = spec_by_param["MCV"]
    mch_spec = spec_by_param["MCH"]
    rbc_spec = spec_by_param["RBC (Eritrosit)"]
    hct_spec = spec_by_param["HCT (Hematokrit)"]
    mchc_spec = spec_by_param["MCHC"]

    hgb_state = _state_for_occurrence(states_map, hgb_spec.key, k)
    mcv_state = _state_for_occurrence(states_map, mcv_spec.key, k)
    mch_state = _state_for_occurrence(states_map, mch_spec.key, k)
    any_driver_state = hgb_state != "normal" or mcv_state != "normal" or mch_state != "normal"

    rbc_lo, rbc_hi = rbc_spec.normal_draw_limits(sex)
    hct_lo, hct_hi = hct_spec.normal_draw_limits(sex)
    mchc_lo, mchc_hi = mchc_spec.normal_draw_limits(sex)

    red_values: dict[str, float] | None = None
    last_failed_param = "RBC (Eritrosit)"
    for salt in range(50):
        hgb = draw_numeric_value(
            hgb_spec, patient_id=patient_id, sex=sex, k=k, state_id=hgb_state, salt=salt
        )
        mcv = draw_numeric_value(
            mcv_spec, patient_id=patient_id, sex=sex, k=k, state_id=mcv_state, salt=salt
        )
        mch = draw_numeric_value(
            mch_spec, patient_id=patient_id, sex=sex, k=k, state_id=mch_state, salt=salt
        )
        rbc = round_param(hgb * 10.0 / mch, rbc_spec.decimals)
        hct = round_param(mcv * rbc / 10.0, hct_spec.decimals)
        mchc = round_param(hgb / hct * 100.0, mchc_spec.decimals)

        rbc_ok = (rbc_lo <= rbc <= rbc_hi) or (
            any_driver_state and _value_in_own_state_ranges(rbc_spec, rbc, sex)
        )
        if not rbc_ok:
            last_failed_param = "RBC (Eritrosit)"
            continue
        hct_ok = (hct_lo <= hct <= hct_hi) or (
            any_driver_state and _value_in_own_state_ranges(hct_spec, hct, sex)
        )
        if not hct_ok:
            last_failed_param = "HCT (Hematokrit)"
            continue
        mchc_ok = (mchc_lo <= mchc <= mchc_hi) or (
            any_driver_state and _value_in_own_state_ranges(mchc_spec, mchc, sex)
        )
        if not mchc_ok:
            last_failed_param = "MCHC"
            continue

        red_values = {
            "RBC (Eritrosit)": rbc,
            "HGB (Hemoglobin)": hgb,
            "HCT (Hematokrit)": hct,
            "MCV": mcv,
            "MCH": mch,
            "MCHC": mchc,
        }
        break

    if red_values is None:
        raise LabCoherenceError(
            f"{patient_id} L107020 {last_failed_param}: red-cell indices failed to converge in 50 tries"
        )

    out: dict[str, float] = {
        "WBC (Lökosit)": wbc_val,
        **diff_counts,
        **red_values,
    }
    for indep_name in ("RDW-CV", "PLT (Trombosit)", "MPV"):
        indep_spec = spec_by_param[indep_name]
        indep_state = _state_for_occurrence(states_map, indep_spec.key, k)
        out[indep_name] = draw_numeric_value(
            indep_spec,
            patient_id=patient_id,
            sex=sex,
            k=k,
            state_id=indep_state,
            salt=0,
        )
    return out


def _egfr_normal_band_for_age(
    age: int,
    bands: Sequence[tuple[int, int, float, float]],
) -> tuple[float, float]:
    for age_lo, age_hi, egfr_lo, egfr_hi in bands:
        if age_lo <= age <= age_hi:
            return egfr_lo, egfr_hi
    raise LabCoherenceError(f"No normal eGFR age band for age {age}")


def _generate_creatinine_and_egfr(
    specs: Sequence[LabParameterSpec],
    *,
    patient_id: str,
    age: int,
    sex: str,
    k: int,
    states_map: Mapping[str, str | Sequence[str]],
    egfr_age_bands: Sequence[tuple[int, int, float, float]],
) -> dict[str, float]:
    spec_by_param = {s.result_parameter: s for s in specs}
    scr_spec = spec_by_param[CREATININE_PARAM_NAME]
    egfr_spec = spec_by_param[EGFR_PARAM_NAME]

    egfr_direct_state = _state_for_occurrence(states_map, egfr_spec.key, k)
    if egfr_direct_state != "normal":
        raise DerivedLabParameterError(
            f"{patient_id} {egfr_spec.key}: state {egfr_direct_state!r} not allowed (derived from Kreatinin)"
        )

    scr_state = _state_for_occurrence(states_map, scr_spec.key, k)
    parsed_state = scr_spec.resolve_state(scr_state)

    if parsed_state is None:
        egfr_lo, egfr_hi = _egfr_normal_band_for_age(age, egfr_age_bands)
        scr_lo, scr_hi = scr_spec.normal_draw_limits(sex)
        scr_val: float | None = None
        for salt in range(50):
            u = draw_u(patient_id, "L104780", CREATININE_PARAM_NAME, k, salt)
            target_egfr = egfr_lo + (egfr_hi - egfr_lo) * (0.30 + 0.40 * u)
            candidate_scr = round(invert_ckd_epi_2021(target_egfr, age, sex), 2)
            if scr_lo <= candidate_scr <= scr_hi:
                scr_val = candidate_scr
                break
        if scr_val is None:
            raise LabCoherenceError(
                f"{patient_id} L104780 Kreatinin: normal draw outside sex-specific limits after 50 tries"
            )
    elif parsed_state.kind == "egfr_band":
        assert parsed_state.low is not None and parsed_state.high is not None
        u = draw_u(patient_id, "L104780", CREATININE_PARAM_NAME, k, 0)
        target_egfr = parsed_state.low + (parsed_state.high - parsed_state.low) * (0.20 + 0.60 * u)
        scr_val = round(invert_ckd_epi_2021(target_egfr, age, sex), 2)
    else:
        lo, hi = parsed_state.range_for_sex(sex)
        u = draw_u(patient_id, "L104780", CREATININE_PARAM_NAME, k, 0)
        scr_val = round(lo + (hi - lo) * (0.20 + 0.60 * u), 2)

    egfr_val = float(round(ckd_epi_2021(scr_val, age, sex)))
    return {
        CREATININE_PARAM_NAME: scr_val,
        EGFR_PARAM_NAME: egfr_val,
    }


def _generate_blood_gas_values(
    specs: Sequence[LabParameterSpec],
    *,
    patient_id: str,
    sex: str,
    k: int,
    blood_gas_type: str | None,
    states_map: Mapping[str, str | Sequence[str]],
) -> dict[str, float]:
    if blood_gas_type != "arterial":
        raise LabCoherenceError(
            f"{patient_id} L103900: billed blood gas requires labs.blood_gas='arterial', got {blood_gas_type!r}"
        )

    spec_by_param = {s.result_parameter: s for s in specs}
    for derived_p in BLOOD_GAS_DERIVED_PARAMS:
        st = _state_for_occurrence(states_map, f"L103900|{derived_p}", k)
        if st != "normal":
            raise DerivedLabParameterError(
                f"{patient_id} L103900|{derived_p}: state {st!r} not allowed (derived)"
            )

    ph_spec = spec_by_param["pH"]
    pco2_spec = spec_by_param["pCO2"]
    po2_spec = spec_by_param["pO2"]

    ph = draw_numeric_value(
        ph_spec,
        patient_id=patient_id,
        sex=sex,
        k=k,
        state_id=_state_for_occurrence(states_map, ph_spec.key, k),
        salt=0,
    )
    pco2 = draw_numeric_value(
        pco2_spec,
        patient_id=patient_id,
        sex=sex,
        k=k,
        state_id=_state_for_occurrence(states_map, pco2_spec.key, k),
        salt=0,
    )
    po2 = draw_numeric_value(
        po2_spec,
        patient_id=patient_id,
        sex=sex,
        k=k,
        state_id=_state_for_occurrence(states_map, po2_spec.key, k),
        salt=0,
    )

    hco3 = henderson_hasselbalch_hco3(ph, pco2)
    be = base_excess_from_ph_hco3(ph, hco3)
    sao2 = severinghaus_sao2(po2)

    out: dict[str, float] = {
        "pH": ph,
        "pCO2": pco2,
        "pO2": po2,
        "HCO3": hco3,
        "BE (baz fazlası)": be,
        "SaO2": sao2,
    }
    for indep_name in (
        "Laktat (kan gazı)",
        "Sodyum (kan gazı)",
        "Potasyum (kan gazı)",
        "İyonize kalsiyum (kan gazı)",
    ):
        indep_spec = spec_by_param[indep_name]
        indep_state = _state_for_occurrence(states_map, indep_spec.key, k)
        out[indep_name] = draw_numeric_value(
            indep_spec,
            patient_id=patient_id,
            sex=sex,
            k=k,
            state_id=indep_state,
            salt=0,
        )
    return out


def _resolve_labs_map(
    clinical: ShowcaseClinical | Sequence[PatientClinical] | Mapping[int, Any] | None,
) -> dict[int, PatientLabs | None]:
    if clinical is None:
        loaded = load_clinical()
        return {p.patient_no: p.labs for p in loaded.patients}
    if isinstance(clinical, ShowcaseClinical):
        return {p.patient_no: p.labs for p in clinical.patients}
    if isinstance(clinical, Mapping):
        out: dict[int, PatientLabs | None] = {}
        for k, v in clinical.items():
            if isinstance(v, PatientClinical):
                out[int(k)] = v.labs
            elif isinstance(v, PatientLabs):
                out[int(k)] = v
            else:
                out[int(k)] = None
        return out
    return {p.patient_no: p.labs for p in clinical}


def _patient_no(pid: str) -> int:
    match = PATIENT_ID_RE.fullmatch(pid)
    if match is None:
        raise LabReferenceError(f"Invalid patient_id format {pid!r}")
    return int(pid.rsplit("-", 1)[1])


def expected_lab_row_count(
    procedure_codes: Sequence[str],
    *,
    reference: LabReference | None = None,
) -> int:
    """Return total expected `lab_clean.parquet` rows for a sequence of billed lab `procedure_codes`."""
    ref = reference if reference is not None else load_lab_reference()
    per_code = ref.parameter_table.group_by("SUB_CODE").len()
    codes = pl.DataFrame({"SUB_CODE": list(procedure_codes)}, schema={"SUB_CODE": pl.String})
    counted = codes.join(per_code, on="SUB_CODE", how="left")
    unknown = counted.filter(pl.col("len").is_null())
    if not unknown.is_empty():
        raise LabReferenceError(f"Unknown billed lab procedure_code {unknown['SUB_CODE'][0]!r}")
    return int(counted["len"].sum())


def expected_lab_keys(
    procedure_lines: pl.DataFrame, *, reference: LabReference | None = None
) -> pl.DataFrame:
    """The result rows the billed lab lines call for, as a key frame in the order of `lab_clean`.

    One row per (billed lab line, CSV parameter of its code), with `HASTA_ID`, `basvuru_id`, `day`
    (the line date as `YYYY-MM-DD`), `SUB_CODE` and `parametre`. Lines are ordered by patient, date
    and line id, the parameters of a line by their position in the CSV.
    """
    ref = reference if reference is not None else load_lab_reference()
    table = ref.parameter_table
    lines = procedure_lines.filter(pl.col("procedure_category") == "laboratuvar")
    unknown = lines.join(
        table.select("SUB_CODE").unique(),
        left_on="procedure_code",
        right_on="SUB_CODE",
        how="anti",
    )
    if not unknown.is_empty():
        raise LabReferenceError(
            f"procedure_claim_lines.parquet: unknown lab code {unknown['procedure_code'][0]!r}"
        )
    return (
        lines.join(
            table.select("SUB_CODE", "parametre", "position"),
            left_on="procedure_code",
            right_on="SUB_CODE",
            how="inner",
        )
        .sort("patient_id", "procedure_date", "procedure_line_id", "position")
        .select(
            pl.col("patient_id").alias("HASTA_ID"),
            pl.col("episode_id").alias("basvuru_id"),
            pl.col("procedure_date").cast(pl.String).alias("day"),
            pl.col("procedure_code").alias("SUB_CODE"),
            "parametre",
        )
    )


def _check_billed_codes(patient_id: str, lab_lines: Sequence[Any], ref: LabReference) -> None:
    """Every billed lab line is a code of the reference."""
    for line in lab_lines:
        if line.procedure_code not in ref.by_code:
            raise LabReferenceError(
                f"{patient_id} ({line.procedure_line_id}): lab code {line.procedure_code!r} "
                "not in lab_reference.csv"
            )


def _check_state_keys(
    patient_id: str,
    states_map: Mapping[str, str | Sequence[str]],
    billed_times: Mapping[str, int],
    ref: LabReference,
) -> None:
    """Each state key names a CSV parameter of a lab the claim bills, and a list has no surplus entry."""
    for key, entry in states_map.items():
        if key not in ref.by_key:
            raise LabReferenceError(
                f"{patient_id}: unknown lab state key {key!r} (not in lab_reference.csv)"
            )
        code = ref.by_key[key].ek2b_code
        times = billed_times.get(code, 0)
        if times == 0:
            raise LabCoherenceError(
                f"{patient_id}: state key {key!r} is for {code}, which the claim does not bill"
            )
        if not isinstance(entry, str) and len(entry) > times:
            raise LabCoherenceError(
                f"{patient_id}: {len(entry)} states for {key!r}, but the claim bills {code} "
                f"{times} time(s); a list has one entry per billed line"
            )


def build_lab_clean(
    claims: Sequence[ComposedClaim],
    *,
    clinical: ShowcaseClinical | Sequence[PatientClinical] | Mapping[int, Any] | None = None,
    pathways: Mapping[str, Pathway] | None = None,
    reference: LabReference | None = None,
    schema: pl.Schema,
) -> pl.DataFrame:
    """Build `lab_clean.parquet` deterministically for `claims`."""
    ref = reference if reference is not None else load_lab_reference()
    pathways_map = pathways if pathways is not None else load_all()
    labs_by_no = _resolve_labs_map(clinical)

    rows: list[dict[str, Any]] = []

    for claim in claims:
        header = claim.header
        pid = header.patient_id
        pno = _patient_no(pid)
        pathway = pathways_map[header.scenario_tag]
        pins = pathway.showcase
        age = pins.age
        sex = pins.sex

        patient_labs = labs_by_no.get(pno)
        states_map: Mapping[str, str | Sequence[str]] = (
            patient_labs.states if patient_labs is not None else {}
        )
        blood_gas_type = patient_labs.blood_gas if patient_labs is not None else None

        lab_lines = sorted(
            (p for p in claim.procedures if p.procedure_category == "laboratuvar"),
            key=lambda p: (p.procedure_date, p.procedure_line_id),
        )
        _check_billed_codes(pid, lab_lines, ref)
        _check_state_keys(pid, states_map, Counter(p.procedure_code for p in lab_lines), ref)

        occurrence_by_code: dict[str, int] = {}
        for line in lab_lines:
            code = line.procedure_code
            k = occurrence_by_code.get(code, 0) + 1
            occurrence_by_code[code] = k

            specs = ref.by_code[code]
            line_dt = datetime.combine(line.procedure_date, time.min)
            donem = str(line.procedure_date.year)

            precomputed_numeric: dict[str, float] | None = None
            if code == "L107020":
                precomputed_numeric = _generate_hemogram_values(
                    specs,
                    patient_id=pid,
                    sex=sex,
                    k=k,
                    states_map=states_map,
                )
            elif code == "L104780":
                precomputed_numeric = _generate_creatinine_and_egfr(
                    specs,
                    patient_id=pid,
                    age=age,
                    sex=sex,
                    k=k,
                    states_map=states_map,
                    egfr_age_bands=ref.egfr_age_bands,
                )
            elif code == "L103900":
                precomputed_numeric = _generate_blood_gas_values(
                    specs,
                    patient_id=pid,
                    sex=sex,
                    k=k,
                    blood_gas_type=blood_gas_type,
                    states_map=states_map,
                )

            for spec in specs:
                organ = ORGAN_SISTEMI_BY_TEST_KEY.get(spec.test_key, "Biyokimya")
                if spec.is_qualitative_strip:
                    st_id = _state_for_occurrence(states_map, spec.key, k)
                    grade = draw_strip_grade(
                        spec,
                        patient_id=pid,
                        k=k,
                        state_id=st_id,
                        salt=0,
                    )
                    rows.append(
                        {
                            "HASTA_ID": pid,
                            "basvuru_id": line.episode_id,
                            "SUB_CODE": code,
                            "parametre": spec.result_parameter,
                            "sonuc_sayisal": None,
                            "sonuc_nitel": grade,
                            "birim": "",
                            "ref_alt": None,
                            "ref_ust": None,
                            "anormal_mi": is_abnormal_strip(grade),
                            "organ_sistemi": organ,
                            "kohort": "showcase",
                            "donem": donem,
                            "tarih": line_dt,
                        }
                    )
                else:
                    if precomputed_numeric is not None:
                        val = precomputed_numeric[spec.result_parameter]
                    else:
                        st_id = _state_for_occurrence(states_map, spec.key, k)
                        val = draw_numeric_value(
                            spec,
                            patient_id=pid,
                            sex=sex,
                            k=k,
                            state_id=st_id,
                            salt=0,
                        )
                    ref_alt, ref_ust = spec.ref_limits(sex)
                    rows.append(
                        {
                            "HASTA_ID": pid,
                            "basvuru_id": line.episode_id,
                            "SUB_CODE": code,
                            "parametre": spec.result_parameter,
                            "sonuc_sayisal": float(val),
                            "sonuc_nitel": None,
                            "birim": spec.unit,
                            "ref_alt": ref_alt,
                            "ref_ust": ref_ust,
                            "anormal_mi": is_abnormal_numeric(val, ref_alt, ref_ust),
                            "organ_sistemi": organ,
                            "kohort": "showcase",
                            "donem": donem,
                            "tarih": line_dt,
                        }
                    )

    return pl.DataFrame(rows, schema=schema, strict=True)


# Tolerances of the derived values: half a unit of the last printed decimal, which is the rounding
# error of a value derived from the (already rounded) values stored next to it. R1 is the 0.05
# of the design.
_EPS = 1e-9
R1_TOLERANCE = 0.05
R2_RBC_TOLERANCE = 0.05  # RBC has one decimal
R2_HCT_TOLERANCE = 0.5  # HCT is a whole number
R2_MCHC_TOLERANCE = 0.05  # MCHC has one decimal
R3_EGFR_TOLERANCE = 0.5  # eGFR is a whole number
R4_TOLERANCE = 0.05  # HCO3, BE and SaO2 have one decimal


def _fmt(template: str, *args: str | pl.Expr) -> pl.Expr:
    """`pl.format` that prints a missing value as `null` (plain `pl.format` turns the message into null)."""
    parts = [
        (pl.col(a) if isinstance(a, str) else a).cast(pl.String).fill_null("null") for a in args
    ]
    return pl.format(template, *parts)


def _flag(
    frame: pl.DataFrame,
    rule: str,
    order: int,
    mask: pl.Expr,
    detail: pl.Expr,
    row: pl.Expr | None = None,
) -> pl.DataFrame:
    """The rows of `frame` where `mask` holds, as violations of `rule` (row, rule, order, detail)."""
    return frame.filter(mask.fill_null(False)).select(
        (pl.col("row") if row is None else row).cast(pl.Int64).alias("row"),
        pl.lit(rule).alias("rule"),
        pl.lit(order, dtype=pl.Int64).alias("order"),
        detail.cast(pl.String).alias("detail"),
    )


def _raise_first(found: list[pl.DataFrame], rows: pl.DataFrame) -> None:
    """Raise `LabCoherenceError` for the violation at the lowest row (listed order within a row)."""
    if not found:
        return
    violations = pl.concat(found)
    if violations.is_empty():
        return
    first = (
        violations.sort("row", "order")
        .head(1)
        .join(
            rows.select("row", "HASTA_ID", "SUB_CODE", "parametre").cast({"row": pl.Int64}),
            on="row",
        )
    )
    message = first.select(
        _fmt(
            "lab_clean {} at row {} ({} {}|{}): {}",
            "rule",
            "row",
            "HASTA_ID",
            "SUB_CODE",
            "parametre",
            "detail",
        )
    ).item()
    raise LabCoherenceError(message)


def _annotate(lab_df: pl.DataFrame, ref: LabReference, ana_df: pl.DataFrame | None) -> pl.DataFrame:
    """`lab_df` with its row number, the reference columns of its parameter and age and sex of the episode."""
    rows = lab_df.with_row_index("row").join(
        ref.parameter_table, on=["SUB_CODE", "parametre"], how="left"
    )
    if ana_df is not None:
        people = ana_df.select(
            pl.col("SQ_EPISODE").alias("basvuru_id"),
            pl.col("TANI_YASI").alias("age"),
            (pl.col("CINSIYET") == "K").alias("female"),
        ).unique(subset="basvuru_id", keep="first", maintain_order=True)
        rows = rows.join(people, on="basvuru_id", how="left")
    return rows.sort("row")


def _with_result_sets(rows: pl.DataFrame) -> pl.DataFrame:
    """Number the result sets: one starts at each first CSV parameter of a code."""
    return rows.with_columns(
        (pl.col("position") == 0).cast(pl.Int64).cum_sum().alias("block")
    ).with_columns(
        pl.int_range(pl.len()).over("block").alias("at"),
        pl.len().over("block").alias("size"),
        pl.col("row").min().over("block").alias("row0"),
        pl.struct("HASTA_ID", "basvuru_id", "tarih").n_unique().over("block").alias("owners"),
        pl.col("SUB_CODE").n_unique().over("block").alias("codes"),
    )


def _result_set_violations(rows: pl.DataFrame) -> list[pl.DataFrame]:
    """A result set is the consecutive rows of one billed line: all CSV parameters of its code, in order."""
    reason = (
        pl.when(pl.col("codes") > 1)
        .then(pl.lit("the result set mixes lab codes"))
        .when(pl.col("owners") > 1)
        .then(pl.lit("the result set mixes patients, episodes or dates"))
        .when(pl.col("size") != pl.col("n_params"))
        .then(
            _fmt(
                "the result set has {} rows but the CSV has {} parameters for {}",
                "size",
                "n_params",
                "SUB_CODE",
            )
        )
        .when(pl.col("at") != pl.col("position"))
        .then(
            _fmt(
                "the parameter is number {} of its result set but is number {} in the CSV",
                "at",
                "position",
            )
        )
    )
    return [_flag(rows, "result set", 1, reason.is_not_null(), reason)]


def _row_violations(rows: pl.DataFrame, *, with_people: bool) -> list[pl.DataFrame]:
    """Row shape and unit (R6), finite values, the limits and the `anormal_mi` flag (R5)."""
    value, grade = pl.col("sonuc_sayisal"), pl.col("sonuc_nitel")
    low, high = pl.col("ref_alt"), pl.col("ref_ust")
    strip, flag, unit = pl.col("is_strip"), pl.col("anormal_mi"), pl.col("birim")
    finite = value.is_finite().fill_null(False)
    outside = (value < low).fill_null(False) | (value > high).fill_null(False)
    checks: list[tuple[str, pl.Expr, pl.Expr]] = [
        ("R6", strip & value.is_not_null(), _fmt("a strip has no number, got {}", value)),
        (
            "R6",
            strip & ~grade.is_in(list(SINGLE_STRIP_GRADES | {"Negatif"})).fill_null(False),
            _fmt("invalid strip grade {}", grade),
        ),
        (
            "R6",
            strip & (low.is_not_null() | high.is_not_null()),
            pl.lit("a strip has no reference limits"),
        ),
        ("R6", ~strip & grade.is_not_null(), _fmt("a number has no grade, got {}", grade)),
        (
            "R6",
            unit != pl.col("csv_unit"),
            _fmt("unit {} differs from the CSV unit {}", unit, pl.col("csv_unit")),
        ),
        (
            "finite",
            ~strip & ~finite,
            _fmt("sonuc_sayisal must be a finite number, got {}", value),
        ),
        (
            "finite",
            ~strip
            & ((low.is_not_null() & ~low.is_finite()) | (high.is_not_null() & ~high.is_finite())),
            pl.lit("the reference limits must be finite"),
        ),
        ("R5", flag.is_null(), pl.lit("anormal_mi must not be null")),
        (
            "R5",
            strip & (flag != (grade != "Negatif")),
            _fmt("anormal_mi={} for the strip grade {}", flag, grade),
        ),
        (
            "R5",
            ~strip & (flag != outside),
            _fmt(
                "anormal_mi={} but the value {} is against ref_alt={} and ref_ust={}",
                flag,
                value,
                low,
                high,
            ),
        ),
    ]
    if with_people:
        female = pl.col("female")
        sex_low = pl.when(female).then(pl.col("ref_low_female")).otherwise(pl.col("ref_low_male"))
        sex_high = (
            pl.when(female).then(pl.col("ref_high_female")).otherwise(pl.col("ref_high_male"))
        )
        checks += [
            (
                "R5",
                female.is_null(),
                pl.lit("no anadata row for the episode: the sex-specific limits cannot be checked"),
            ),
            (
                "R5",
                ~strip
                & female.is_not_null()
                & (low.ne_missing(sex_low) | high.ne_missing(sex_high)),
                _fmt(
                    "the limits [{}, {}] are not the sex-specific limits [{}, {}] of the CSV",
                    low,
                    high,
                    sex_low,
                    sex_high,
                ),
            ),
        ]
    return [
        _flag(rows, rule, 10 + order, mask, detail)
        for order, (rule, mask, detail) in enumerate(checks)
    ]


def _result_sets_of(rows: pl.DataFrame, code: str) -> pl.DataFrame:
    """One row per result set of `code`, one column per parameter (named after it), `row0` first row."""
    subset = rows.filter(pl.col("SUB_CODE") == code)
    if subset.is_empty():
        return subset
    index = [c for c in ("block", "row0", "age", "female") if c in subset.columns]
    return subset.pivot(
        on="parametre", index=index, values="sonuc_sayisal", aggregate_function="first"
    )


def _differs(actual: pl.Expr, expected: pl.Expr, tolerance: float) -> pl.Expr:
    return (actual - expected).abs() > tolerance + _EPS


def _hemogram_violations(sets: pl.DataFrame, ref: LabReference) -> list[pl.DataFrame]:
    """R1: the five counts sum to the WBC. R2: RBC, HCT and MCHC follow HGB, MCV and MCH."""
    wbc, hgb, mcv, mch = (pl.col(p) for p in ("WBC (Lökosit)", "HGB (Hemoglobin)", "MCV", "MCH"))
    rbc, hct, mchc = (pl.col(p) for p in ("RBC (Eritrosit)", "HCT (Hematokrit)", "MCHC"))
    counts = pl.sum_horizontal(*(pl.col(p) for p in DIFF_PARAMETER_NAMES))
    expected_rbc, expected_hct, expected_mchc = (
        hgb * 10.0 / mch,
        mcv * rbc / 10.0,
        hgb / hct * 100.0,
    )

    def at(parameter: str) -> pl.Expr:
        return pl.col("row0") + ref.position_of("L107020", parameter)

    return [
        _flag(
            sets,
            "R1",
            30,
            _differs(counts, wbc, R1_TOLERANCE),
            _fmt("the five counts sum to {} but WBC is {}", counts.round(2), wbc),
            at("WBC (Lökosit)"),
        ),
        _flag(
            sets,
            "R2",
            31,
            _differs(rbc, expected_rbc, R2_RBC_TOLERANCE),
            _fmt("RBC {} differs from HGB*10/MCH = {}", rbc, expected_rbc.round(3)),
            at("RBC (Eritrosit)"),
        ),
        _flag(
            sets,
            "R2",
            32,
            _differs(hct, expected_hct, R2_HCT_TOLERANCE),
            _fmt("HCT {} differs from MCV*RBC/10 = {}", hct, expected_hct.round(3)),
            at("HCT (Hematokrit)"),
        ),
        _flag(
            sets,
            "R2",
            33,
            _differs(mchc, expected_mchc, R2_MCHC_TOLERANCE),
            _fmt("MCHC {} differs from HGB/HCT*100 = {}", mchc, expected_mchc.round(3)),
            at("MCHC"),
        ),
    ]


def _creatinine_violations(sets: pl.DataFrame, ref: LabReference) -> list[pl.DataFrame]:
    """R3: eGFR is CKD-EPI 2021 of the creatinine, the age and the sex."""
    egfr, scr = pl.col(EGFR_PARAM_NAME), pl.col(CREATININE_PARAM_NAME)
    expected = ckd_epi_2021_expr(scr, pl.col("age"), pl.col("female"))
    return [
        _flag(
            sets,
            "R3",
            40,
            _differs(egfr, expected, R3_EGFR_TOLERANCE),
            _fmt(
                "eGFR {} differs from CKD-EPI 2021 of creatinine {} = {}",
                egfr,
                scr,
                expected.round(2),
            ),
            pl.col("row0") + ref.position_of("L104780", EGFR_PARAM_NAME),
        )
    ]


def _blood_gas_violations(sets: pl.DataFrame, ref: LabReference) -> list[pl.DataFrame]:
    """R4: HCO3 from pH and pCO2, base excess from pH and HCO3, SaO2 from pO2 (Severinghaus)."""
    ph, pco2, po2 = pl.col("pH"), pl.col("pCO2"), pl.col("pO2")
    hco3, be, sao2 = pl.col("HCO3"), pl.col("BE (baz fazlası)"), pl.col("SaO2")
    expected_hco3, expected_be, expected_sao2 = _hco3(ph, pco2), _base_excess(ph, hco3), _sao2(po2)

    def at(parameter: str) -> pl.Expr:
        return pl.col("row0") + ref.position_of("L103900", parameter)

    return [
        _flag(
            sets,
            "R4",
            50,
            _differs(hco3, expected_hco3, R4_TOLERANCE),
            _fmt("HCO3 {} differs from Henderson-Hasselbalch = {}", hco3, expected_hco3.round(3)),
            at("HCO3"),
        ),
        _flag(
            sets,
            "R4",
            51,
            _differs(be, expected_be, R4_TOLERANCE),
            _fmt(
                "BE {} differs from 0.93*(HCO3-24.4+14.8*(pH-7.4)) = {}", be, expected_be.round(3)
            ),
            at("BE (baz fazlası)"),
        ),
        _flag(
            sets,
            "R4",
            52,
            _differs(sao2, expected_sao2, R4_TOLERANCE),
            _fmt("SaO2 {} differs from Severinghaus = {}", sao2, expected_sao2.round(3)),
            at("SaO2"),
        ),
    ]


def _derived_violations(rows: pl.DataFrame, ref: LabReference) -> list[pl.DataFrame]:
    out: list[pl.DataFrame] = []
    for code, rules, needs_people in (
        ("L107020", _hemogram_violations, False),
        ("L104780", _creatinine_violations, True),
        ("L103900", _blood_gas_violations, False),
    ):
        sets = _result_sets_of(rows, code)
        if sets.is_empty() or (needs_people and "age" not in sets.columns):
            continue
        out += rules(sets, ref)
    return out


def check_lab_coherence(
    lab_df: pl.DataFrame,
    *,
    ana_df: pl.DataFrame | None = None,
    reference: LabReference | None = None,
) -> None:
    """Raise `LabCoherenceError` for the first incoherent row of `lab_df`, with rule, row, patient and parameter.

    Four stages, each reporting its lowest row: (1) every `SUB_CODE`/`parametre` is a parameter of the
    reference; (2) the rows form result sets, each one billed line with all CSV parameters of its code in
    order; (3) every row: shape and unit (R6), finite values, `anormal_mi` against the limits (R5);
    (4) derived values: the differential sums to the WBC (R1), RBC, HCT and MCHC follow HGB, MCV and MCH
    (R2), eGFR is CKD-EPI 2021 (R3), HCO3, base excess and SaO2 follow the blood gas (R4).
    `ana_df` gives the age and sex of each episode; without it R3 and the check that the limits are
    the sex-specific ones of the CSV do not run.
    """
    if lab_df.is_empty():
        return
    ref = reference if reference is not None else load_lab_reference()
    rows = _annotate(lab_df, ref, ana_df)
    unknown = _flag(
        rows,
        "unknown parameter",
        0,
        pl.col("position").is_null(),
        pl.lit("the parameter is not in lab_reference.csv"),
    )
    _raise_first([unknown], rows)
    rows = _with_result_sets(rows)
    _raise_first(_result_set_violations(rows), rows)
    _raise_first(_row_violations(rows, with_people=ana_df is not None), rows)
    _raise_first(_derived_violations(rows, ref), rows)
