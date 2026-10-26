"""Every Turkish text fold answers exactly as before it was moved onto ``src.bilun.domain.turkish_fold``.

Each ``_old_*`` function below is a module's private fold as it stood at fcea17b, copied verbatim.
Where several modules carried the same body, one copy stands for all of them (``_OLD_TABLE`` names
the modules). A caller now calls ``fold_turkish`` with its own ``TurkishFold`` (and ``strip``,
``text or ""`` and any step it kept after the fold); each row runs the old fold and that call on
the same inputs:

- a corpus of the repo's own strings: branch and department names, rule texts (SUT clauses, the
  prose rule files, MEDULA playbooks), drug, material, procedure and lab names, and the synthetic
  claims' text columns. Names are taken whole. Long texts (clause texts, descriptions, ICD-10
  names, rule strings over 200 characters) give their distinct words: every fold works letter by
  letter (``strip`` only at the ends, which the whole names and the edge strings cover), so the
  words carry every letter the whole texts do at a fraction of the run time;
- every code point of the Latin, Greek, Cyrillic, combining-mark and compatibility blocks, alone
  and between letters;
- edge strings: the four Turkish i's, decomposed letters, padding, Greek final sigma, ligatures.

``test_callers_use_the_pinned_fold`` reads each caller's source and pins the folds it uses, so a
caller cannot drift to another fold without this table changing with it.

The synthetic cohort keeps its own folds on purpose: the generator (``cohort/clean.py``) and the
plausibility checks (``cohort/plausibility*.py``, pinned engine-independent by their tests) must
not share the engine's logic, or an engine fault could hide in the data that tests it.
"""

from __future__ import annotations

import ast
import csv
import json
import unicodedata
from collections.abc import Callable
from functools import lru_cache
from pathlib import Path
from typing import Any

import polars as pl
import pytest
import yaml

from src.bilun.domain.constants import HEMOGRAM_TESTS
from src.bilun.domain.prose_rules._drug_indication.ingredient_names import fold_name
from src.bilun.domain.turkish_fold import TurkishFold, fold_turkish

_ROOT = Path(__file__).resolve().parents[3]


# --- The folds as they stood at fcea17b (verbatim) -------------------------------------------


def _old_turkish_lower(text: str) -> str:  # utils.turkish_lower
    return text.replace("İ", "i").replace("I", "ı").lower()


# dental_2_4_1, specialty_materials, material_bundling, scripts/sut/prose/drug_indication_gate_b
# (``_normalize_tr``) and scripts/sut/prose/gate_b_generic (``normalize_tr``) carried this body.
def _old_normalize_tr_str(text: str) -> str:
    folded = unicodedata.normalize("NFKD", str(text).casefold())
    return "".join(ch for ch in folded if not unicodedata.combining(ch))


# drug_combination (``_normalize_tr``) and scripts/sut/prose/tier_c_classify (``normalize_tr``).
def _old_normalize_tr_or_empty(text: str) -> str:
    folded = unicodedata.normalize("NFKD", str(text or "").casefold())
    return "".join(ch for ch in folded if not unicodedata.combining(ch))


# _drug_indication/matching.py
def _old_drug_indication_normalize_tr(text: str) -> str:
    lowered = str(text or "").replace("İ", "i").replace("I", "ı").casefold().replace("ı", "i")
    folded = unicodedata.normalize("NFKD", lowered)
    return "".join(ch for ch in folded if not unicodedata.combining(ch))


_OLD_APOSTROPHES = str.maketrans({"’": "'", "‘": "'", "`": "'", "´": "'"})


# _drug_indication/ingredient_names.py
def _old_fold_name(text: str | None) -> str:
    if not text:
        return ""
    return _old_drug_indication_normalize_tr(str(text).translate(_OLD_APOSTROPHES))


# claims/adapter.py
def _old_adapter_fold_tr(text: str) -> str:
    import unicodedata
    folded = unicodedata.normalize("NFKD", (text or "").casefold())
    folded = folded.replace("ı", "i").replace("İ", "i")
    return "".join(ch for ch in folded if not unicodedata.combining(ch))


# materials/catalog_lookup.py
def _old_catalog_lookup_fold_tr(text: str) -> str:
    return _old_turkish_lower(str(text)).replace("ı", "i")


# billing/claim_lab.py
def _old_fold_lab_name(name: Any) -> str:
    return _old_turkish_lower(str(name or "").strip()).replace("ı", "i")


# prose_rules/icu_puani.py
def _old_icu_puani_fold_tr(text: str) -> str:
    return (
        str(text or "")
        .translate(
            str.maketrans(
                {
                    "Ç": "c",
                    "ç": "c",
                    "Ğ": "g",
                    "ğ": "g",
                    "I": "i",
                    "İ": "i",
                    "ı": "i",
                    "Ö": "o",
                    "ö": "o",
                    "Ş": "s",
                    "ş": "s",
                    "Ü": "u",
                    "ü": "u",
                }
            )
        )
        .lower()
    )


_OLD_TR_FOLD_MAP = str.maketrans(
    {
        "ç": "c", "Ç": "c",
        "ğ": "g", "Ğ": "g",
        "ı": "i", "I": "i",
        "İ": "i",
        "ö": "o", "Ö": "o",
        "ş": "s", "Ş": "s",
        "ü": "u", "Ü": "u",
    }
)


# prose_rules/icu_bundled_leakage.py
def _old_icu_bundled_fold_tr(text: str) -> str:
    return str(text or "").translate(_OLD_TR_FOLD_MAP).lower()


# chatbot/medula_kb.py (``_normalize``)
def _old_medula_kb_normalize(text: str) -> str:
    return text.lower().strip()


# prose_rules/traffic_accident_billing.py (``_normalize``)
def _old_traffic_normalize(value: str) -> str:
    return str(value or "").strip().lower()


# api/routes/medula_rejections.py (``_normalize``)
def _old_medula_rejections_normalize(text: str | None) -> str:
    return (text or "").casefold().strip()


# prose_rules/medula_rejection.py (``_normalize``)
def _old_medula_rejection_normalize(text: str) -> str:
    return text.casefold().strip()


# optimization/copay_exemption_rules/occupational.py (``_normalize``); called on truthy values only
def _old_occupational_normalize(value: str) -> str:
    return str(value or "").strip().lower().replace(" ", "_")


# --- Old fold -> the call that replaced it ---------------------------------------------------

A = TurkishFold.ACCENTLESS
D = TurkishFold.ACCENTLESS_DOTLESS_I

# (id, old fold, its replacement as the callers now write it, inputs: "any" | "str" | "truthy")
_OLD_TABLE: tuple[tuple[str, Callable[[Any], str], Callable[[Any], str], str], ...] = (
    ("normalize_tr_str", _old_normalize_tr_str, lambda t: fold_turkish(t, A), "any"),
    ("normalize_tr_or_empty", _old_normalize_tr_or_empty, lambda t: fold_turkish(t or "", A), "any"),
    ("drug_indication", _old_drug_indication_normalize_tr, lambda t: fold_turkish(t or "", D), "any"),
    ("fold_name", _old_fold_name, fold_name, "any"),
    (
        "adapter",
        _old_adapter_fold_tr,
        lambda t: fold_turkish(t or "", A).replace("ı", "i"),
        "str",
    ),
    (
        "catalog_lookup",
        _old_catalog_lookup_fold_tr,
        lambda t: fold_turkish(t, TurkishFold.DOTTED_I),
        "any",
    ),
    (
        "claim_lab",
        _old_fold_lab_name,
        lambda t: fold_turkish(t or "", TurkishFold.DOTTED_I, strip=True),
        "any",
    ),
    ("icu_puani", _old_icu_puani_fold_tr, lambda t: fold_turkish(t or "", TurkishFold.ASCII), "any"),
    (
        "icu_bundled_leakage",
        _old_icu_bundled_fold_tr,
        lambda t: fold_turkish(t or "", TurkishFold.ASCII),
        "any",
    ),
    (
        "medula_kb",
        _old_medula_kb_normalize,
        lambda t: fold_turkish(t, TurkishFold.LOWER, strip=True),
        "str",
    ),
    (
        "traffic_accident_billing",
        _old_traffic_normalize,
        lambda t: fold_turkish(t or "", TurkishFold.LOWER, strip=True),
        "any",
    ),
    (
        "medula_rejections",
        _old_medula_rejections_normalize,
        lambda t: fold_turkish(t or "", TurkishFold.CASEFOLD, strip=True),
        "str",
    ),
    (
        "medula_rejection",
        _old_medula_rejection_normalize,
        lambda t: fold_turkish(t, TurkishFold.CASEFOLD, strip=True),
        "str",
    ),
    (
        "occupational",
        _old_occupational_normalize,
        lambda t: fold_turkish(t, TurkishFold.LOWER, strip=True).replace(" ", "_"),
        "truthy",
    ),
)

# Each caller module and the (fold, strip) pairs its ``fold_turkish`` calls use.
_CALLER_FOLDS: dict[str, set[tuple[str, bool]]] = {
    "src/bilun/domain/prose_rules/dental_2_4_1.py": {("ACCENTLESS", False)},
    "src/bilun/domain/billing/broad_rule_classification.py": {("ACCENTLESS", False)},
    # specialty_materials and material_bundling share material_lines' name match (WP42).
    "src/bilun/domain/prose_rules/material_lines.py": {("ACCENTLESS", False)},
    "src/bilun/domain/prose_rules/drug_combination.py": {("ACCENTLESS", False)},
    "scripts/sut/prose/drug_indication_gate_b.py": {("ACCENTLESS", False)},
    "scripts/sut/prose/gate_b_generic.py": {("ACCENTLESS", False)},
    "scripts/sut/prose/gate_b_audit.py": {("ACCENTLESS", False)},
    "scripts/sut/prose/tier_c_classify.py": {("ACCENTLESS", False)},
    "scripts/sut/extract_tier_c_drug_rules.py": {("ACCENTLESS", False)},
    "src/bilun/domain/claims/adapter.py": {("ACCENTLESS", False)},
    "src/bilun/domain/prose_rules/_drug_indication/matching.py": {("ACCENTLESS_DOTLESS_I", False)},
    "src/bilun/domain/prose_rules/_drug_indication/routing.py": {("ACCENTLESS_DOTLESS_I", False)},
    "src/bilun/domain/prose_rules/_drug_indication/clinical_indications.py": {
        ("ACCENTLESS_DOTLESS_I", False)
    },
    "src/bilun/domain/prose_rules/_drug_indication/ingredient_names.py": {
        ("ACCENTLESS_DOTLESS_I", False)
    },
    "src/bilun/domain/materials/catalog_lookup.py": {("DOTTED_I", False)},
    "src/bilun/domain/billing/claim_lab.py": {("DOTTED_I", True)},
    "src/bilun/domain/prose_rules/icu_puani.py": {("ASCII", False)},
    "src/bilun/domain/prose_rules/icu_bundled_leakage.py": {("ASCII", False)},
    "src/bilun/chatbot/medula_kb.py": {("LOWER", True)},
    "src/bilun/domain/prose_rules/traffic_accident_billing.py": {("LOWER", True)},
    "src/bilun/domain/optimization/copay_exemption_rules/occupational.py": {("LOWER", True)},
    "src/bilun/api/routes/medula_rejections.py": {("CASEFOLD", True)},
    "src/bilun/domain/prose_rules/medula_rejection.py": {("CASEFOLD", True)},
}

_RETIRED_NAMES = {"_normalize_tr", "normalize_tr", "_fold_tr", "_fold_lab_name", "_normalize"}


# --- Inputs ----------------------------------------------------------------------------------

_EDGE_STRINGS: tuple[str, ...] = (
    "",
    " ",
    "\t\n",
    "İ",
    "I",
    "ı",
    "i",
    "İSTANBUL ISPARTA ıspanak iğne",
    "İZMİR",  # a decomposed İ
    "i̇",
    "̇",
    "Ş Ç Ğ Ü Ö ş ç ğ ü ö",
    "Şeker Ğöz",  # decomposed ş, ğ, ö
    "  Göğüs Hastalıkları  ",
    "\tKARDİYOLOJİ\n",
    " Nefroloji ",
    "ÂLÎ ÛMÎT",
    "é É ñ ß ẞ",
    "ﬁ ² ½ ㎏ µ",
    "Σ ΑΣ ΑΣΑ",
    "\U0001d6a4",  # mathematical italic small dotless i
    "ǅ ǈ",
    "İMPLANT, ALTIN İÇERMEYEN; platin içeren",
    "NEBÜLİZATÖR / Monitörizasyon - Mekanik ventilatör",
    "PEGİLE İNTERFERON ALFA-2A 180 MCG (peginterferon)",
    "’ ‘ ` ´ '",
)
_EDGE_VALUES: tuple[Any, ...] = (None, 0, False)
_BLOCKS = (
    (0x0000, 0x0530),  # Basic Latin to Cyrillic Supplement, with the combining marks
    (0x1D00, 0x2000),  # phonetic extensions, Latin Extended Additional, Greek Extended
    (0x2070, 0x2190),  # super- and subscripts, letterlike symbols, number forms
    (0xFB00, 0xFB50),  # alphabetic presentation forms (ligatures)
    (0x1D6A0, 0x1D6B0),  # mathematical dotless i and j
)


def _strings_of(value: Any, sink: set[str]) -> None:
    if isinstance(value, str):
        sink.add(value)
    elif isinstance(value, dict):
        for key, item in value.items():
            sink.add(str(key))
            _strings_of(item, sink)
    elif isinstance(value, list):
        for item in value:
            _strings_of(item, sink)


def _words(texts: set[str]) -> set[str]:
    """The distinct words of ``texts``."""
    return {word for text in texts for word in text.split()}


def _short_whole_long_in_words(texts: set[str]) -> set[str]:
    short = {text for text in texts if len(text) <= 200}
    return short | _words(texts - short)


def _column_strings(path: Path, columns: tuple[str, ...] | None = None) -> set[str]:
    frame = pl.read_parquet(path)
    names = columns or tuple(name for name, dtype in frame.schema.items() if dtype == pl.String)
    found: set[str] = set()
    for name in names:
        found.update(value for value in frame[name].unique().to_list() if value is not None)
    return found


@lru_cache(maxsize=1)
def _corpus() -> dict[str, frozenset[str]]:
    gazette = _ROOT / "data/gazette"
    curated = gazette / "curated"
    reference = _ROOT / "data/synthetic/reference"
    claims = _ROOT / "data/synthetic/sut/claims"
    claim_tables = (
        "claim_headers",
        "claim_diagnoses",
        "drug_claim_lines",
        "material_claim_lines",
        "procedure_claim_lines",
        "performed_procedure_lines",
        "medula_rejection_events",
        "patient_copay_profiles",
    )

    branches = _column_strings(curated / "ek2a_outpatient_visits.parquet", ("specialty_name",))
    branches |= _column_strings(claims / "claim_headers.parquet", ("department",))
    pathway_strings: set[str] = set()
    for path in sorted((_ROOT / "data/synthetic/pathways").glob("*.yaml")):
        _strings_of(yaml.safe_load(path.read_text(encoding="utf-8")), pathway_strings)

    rule_texts = _column_strings(gazette / "sut_clauses.parquet", ("section_title",))
    rule_texts |= _words(_column_strings(gazette / "sut_clauses.parquet", ("text_tr",)))
    rule_texts |= _short_whole_long_in_words(
        _column_strings(gazette / "fatura_inceleme_clauses.parquet")
    )
    rule_strings: set[str] = set()
    for path in sorted((gazette / "prose_rules").glob("*.json")):
        _strings_of(json.loads(path.read_text(encoding="utf-8")), rule_strings)
    for path in sorted((_ROOT / "data/medula").glob("*.json")):
        _strings_of(json.loads(path.read_text(encoding="utf-8")), rule_strings)
    rule_texts |= _short_whole_long_in_words(rule_strings)

    drugs = _column_strings(curated / "ek4a_drugs.parquet", ("drug_name",))
    drugs |= _column_strings(curated / "ek4d_copay_exempt_entries.parquet", ("drug_name_tr",))
    drugs |= _column_strings(reference / "drug_crosswalk.parquet", ("active_ingredient",))

    materials: set[str] = set()
    descriptions: set[str] = set()
    for path in sorted(curated.glob("ek3*.parquet")):
        frame_columns = pl.read_parquet_schema(path)
        names = tuple(name for name in ("material_name", "item_name") if name in frame_columns)
        materials |= _column_strings(path, names)
        if "description" in frame_columns:
            descriptions |= _column_strings(path, ("description",))
    materials |= _words(descriptions)

    procedures = _column_strings(curated / "ek2c_catalog_history.parquet", ("name",))
    procedures |= _words(_column_strings(curated / "ek2c_catalog_history.parquet", ("description",)))
    procedures |= _column_strings(curated / "ek2b_catalog_history.parquet", ("name",))
    procedures |= _words(_column_strings(reference / "icd10_tr.parquet", ("name_tr",)))
    procedures |= _column_strings(curated / "ek1a_chronic_exemptions.parquet", ("disease_name_tr",))
    with (reference / "lab_reference.csv").open(encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            procedures.update((row["catalog_name"], row["result_parameter"]))
    procedures |= set(HEMOGRAM_TESTS)

    synthetic_claims: set[str] = set()
    for table in claim_tables:
        synthetic_claims |= _column_strings(claims / f"{table}.parquet")

    return {
        "branches": frozenset(branches | pathway_strings),
        "rule_texts": frozenset(rule_texts),
        "drugs": frozenset(drugs),
        "materials": frozenset(materials),
        "procedures": frozenset(procedures),
        "synthetic_claims": frozenset(synthetic_claims),
    }


@lru_cache(maxsize=1)
def _inputs() -> tuple[str, ...]:
    code_points = [chr(cp) for start, end in _BLOCKS for cp in range(start, end)]
    around = [f"a{ch}Σ{ch}" for ch in code_points]
    every = set().union(*_corpus().values()) | set(_EDGE_STRINGS) | set(code_points) | set(around)
    return tuple(sorted(every))


# --- Tests -----------------------------------------------------------------------------------


def test_the_corpus_is_the_repos_turkish_text() -> None:
    corpus = _corpus()
    minimum = {
        "branches": 100,
        "rule_texts": 10_000,
        "drugs": 10_000,
        "materials": 3_000,
        "procedures": 10_000,
        "synthetic_claims": 300,
    }
    assert {name: len(texts) >= minimum[name] for name, texts in corpus.items()} == dict.fromkeys(
        minimum, True
    )
    letters = {ch for texts in corpus.values() for text in texts for ch in text}
    assert set("İIıiŞşÇçĞğÜüÖö") <= letters
    assert any(unicodedata.combining(ch) for ch in letters)  # decomposed Turkish letters occur


@pytest.mark.parametrize(("name", "old", "new", "domain"), _OLD_TABLE, ids=[r[0] for r in _OLD_TABLE])
def test_the_new_fold_reproduces_the_old_one(
    name: str, old: Callable[[Any], str], new: Callable[[Any], str], domain: str
) -> None:
    inputs: tuple[Any, ...] = _inputs()
    if domain == "any":
        inputs = (*inputs, *_EDGE_VALUES)
    elif domain == "truthy":
        inputs = tuple(text for text in inputs if text)
    olds = [old(text) for text in inputs]
    news = [new(text) for text in inputs]
    mismatches = [(text, o, n) for text, o, n in zip(inputs, olds, news, strict=True) if o != n]
    assert mismatches == []
    changed = sum(1 for text, o in zip(inputs, olds, strict=True) if o != text)
    assert changed > 10_000  # the corpus exercises the fold, it is not already folded


def test_the_folds_differ_where_the_callers_did() -> None:
    # The variants are kept apart on purpose; these are the differences they keep.
    assert fold_turkish("ılık", TurkishFold.ACCENTLESS) == "ılık"
    assert fold_turkish("ılık", TurkishFold.ACCENTLESS_DOTLESS_I) == "ilik"
    assert fold_turkish("Şeker", TurkishFold.DOTTED_I) == "şeker"
    assert fold_turkish("Şeker", TurkishFold.ASCII) == "seker"
    assert fold_turkish("Café", TurkishFold.ASCII) == "café"
    assert fold_turkish("Café", TurkishFold.ACCENTLESS) == "cafe"
    assert fold_turkish("İzmir", TurkishFold.LOWER) == "i̇zmir"
    assert fold_turkish("Straße", TurkishFold.CASEFOLD) == "strasse"
    assert fold_turkish("Straße", TurkishFold.LOWER) == "straße"
    assert fold_turkish(" X ", TurkishFold.LOWER) == " x "
    assert fold_turkish(" X ", TurkishFold.LOWER, strip=True) == "x"
    assert fold_turkish(None, TurkishFold.ACCENTLESS) == "none"
    assert fold_turkish("\U0001d6a4", TurkishFold.ACCENTLESS_DOTLESS_I) == "ı"


def _fold_calls(tree: ast.AST) -> list[tuple[str, bool]]:
    calls = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and getattr(node.func, "id", None) == "fold_turkish":
            how = node.args[1]
            assert isinstance(how, ast.Attribute) and getattr(how.value, "id", None) == "TurkishFold"
            strip = any(
                kw.arg == "strip" and isinstance(kw.value, ast.Constant) and kw.value.value is True
                for kw in node.keywords
            )
            calls.append((how.attr, strip))
    return calls


@pytest.mark.parametrize("module", sorted(_CALLER_FOLDS))
def test_callers_use_the_pinned_fold(module: str) -> None:
    tree = ast.parse((_ROOT / module).read_text(encoding="utf-8"))
    calls = _fold_calls(tree)
    assert calls, module
    assert set(calls) == _CALLER_FOLDS[module]
    defined = {node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)}
    assert defined & _RETIRED_NAMES == set()
