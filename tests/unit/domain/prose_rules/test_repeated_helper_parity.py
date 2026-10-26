"""The private helpers that several prose-rule modules each carried answer exactly as before they were shared.

Each ``_old_*`` function below is a module's private helper as it stood at bff36b9, copied verbatim.
Where several modules carried the same body, one copy stands for all of them. Each test runs the
old copy and what the module calls now on the same inputs:

- ``_normalize_code`` (7 modules, three readings of the package ``P``; icu_puani wrapped every call
  in its ``_strip_p``) → ``claim_utils.clean_procedure_code`` with the module's ``PackagePrefix``;
- ``_line_billed`` (5 identical copies) → ``claim_utils.line_billed_amount``; material_uplift's
  ``bool`` variant is now ``_has_billed_amount`` on top of it, radiation_oncology keeps its own
  (it reads a missing amount as 0);
- ``_material_fields`` and ``_material_name_matches`` (material_bundling, specialty_materials)
  → ``material_lines``; dental_2_4_1 keeps its own name match (it reads negations);
- ``_branch_matches`` and ``_BRANCH_KEYWORDS`` (fatura_inceleme, fatura_inceleme_checklist) → the
  checklist imports fatura_inceleme's;
- ``_date_missing`` (clinical_mds, clinical_mesothelioma_documents, adult_gh_draft) and the tail of
  ``clinical_common.scope_missing`` → ``clinical_common.evidence_date_missing``.

``test_no_module_defines_the_merged_helper_again`` reads each module's source, so a copy cannot
come back unnoticed.
"""

from __future__ import annotations

import ast
import hashlib
import itertools
import math
from datetime import date
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from src.bilun.domain.prose_rules import (
    anestezi_puani,
    blood_component_isbt128,
    fatura_inceleme,
    fatura_inceleme_checklist,
    icu_bundled_leakage,
    icu_puani,
    material_uplift,
    refakatci,
    temporal_anomaly,
    yatak_icu_overlap,
)
from src.bilun.domain.prose_rules._drug_indication import clinical_common
from src.bilun.domain.prose_rules.claim_utils import (
    PackagePrefix,
    clean_procedure_code,
    line_billed_amount,
)
from src.bilun.domain.prose_rules.material_bundling import load_material_bundling_rules
from src.bilun.domain.prose_rules.material_lines import material_fields, material_name_matches
from src.bilun.domain.prose_rules.specialty_materials import load_specialty_materials_rules
from src.bilun.domain.turkish_fold import TurkishFold, fold_turkish

_REPO = Path(__file__).resolve().parents[4]
_PROSE_RULES = _REPO / "src" / "bilun" / "domain" / "prose_rules"


# ── the old copies (bff36b9, verbatim) ──────────────────────────────────────


# refakatci.py, icu_puani.py
def _old_normalize_code_keep(raw: str) -> str:
    return (
        str(raw or "")
        .strip()
        .replace(".", "")
        .replace(" ", "")
        .replace("-", "")
        .upper()
    )


# icu_puani.py (every _normalize_code call there was wrapped in _strip_p)
def _old_strip_p(normalized: str) -> str:
    return normalized[1:] if normalized.startswith("P") else normalized


def _old_normalize_code_icu_puani(raw: str) -> str:
    return _old_strip_p(_old_normalize_code_keep(raw))


# temporal_anomaly.py
def _old_normalize_code_temporal(raw: str | None) -> str:
    code = (
        str(raw or "")
        .strip()
        .replace(".", "")
        .replace(" ", "")
        .replace("-", "")
        .upper()
    )
    if code.startswith("P") and len(code) > 1 and code[1:].isdigit():
        return code[1:]
    return code


# anestezi_puani.py
def _old_normalize_code_anestezi(raw_code: str) -> str:
    code = (
        str(raw_code or "")
        .strip()
        .replace(".", "")
        .replace(" ", "")
        .replace("-", "")
        .upper()
    )
    if code.startswith("P") and len(code) > 1 and code[1:].isdigit():
        code = code[1:]
    return code


# blood_component_isbt128.py, yatak_icu_overlap.py, icu_bundled_leakage.py
def _old_normalize_code_always(raw: str) -> str:
    cleaned = (
        str(raw or "")
        .strip()
        .replace(".", "")
        .replace(" ", "")
        .replace("-", "")
        .upper()
    )
    return cleaned[1:] if cleaned.startswith("P") else cleaned


# blood_uplift.py, drg_unbundling.py, transplant_package_scope.py, procedure_addon_uplift.py,
# session_uplift.py
def _old_line_billed(line: Any) -> float:
    return float(line.billed_amount_try)


# material_uplift.py
def _old_line_billed_bool(line: Any) -> bool:
    return float(line.billed_amount_try) > 0


# material_bundling.py, specialty_materials.py
def _old_material_fields(mat: dict[str, Any]) -> tuple[str, str, float]:
    name = str(mat.get("name") or mat.get("material_name") or "").strip()
    code = str(mat.get("code") or mat.get("material_code") or "").strip().upper()
    unit_price = float(mat.get("unit_price") or mat.get("billed_amount_try") or 0)
    return name, code, unit_price


# material_bundling.py, specialty_materials.py
def _old_material_name_matches(material_name: str, keywords: list[str]) -> bool:
    normalized = fold_turkish(material_name, TurkishFold.ACCENTLESS)
    if not normalized:
        return False
    for keyword in keywords:
        if fold_turkish(keyword, TurkishFold.ACCENTLESS) in normalized:
            return True
    return False


# fatura_inceleme.py, fatura_inceleme_checklist.py (the docstrings differed, the bodies did not)
def _old_branch_matches(
    rule_branch: str | None, context: dict[str, Any], branch_keywords: dict[str, list[str]]
) -> bool:
    if rule_branch is None:
        return True
    keywords = branch_keywords.get(rule_branch, [])
    if not keywords:
        return False
    dept = (context.get("department") or "").lower()
    specialty = (context.get("provider_specialty") or "").lower()
    combined = f"{dept} {specialty}"
    return any(kw in combined for kw in keywords)


# sha256 of ``repr(fatura_inceleme_checklist._BRANCH_KEYWORDS)`` at bff36b9; fatura_inceleme's
# dict had the same repr, so the checklist now reads that one.
_OLD_CHECKLIST_BRANCH_KEYWORDS_SHA256 = "6ebbf7f180866503a296ac30a1722b22acf286c091663a03575fa2e2b3e2f124"


# clinical_mds.py, clinical_mesothelioma_documents.py, adult_gh_draft.py (each with its _PREFIX)
def _old_date_missing(evidence: Any, service: date | None, prefix: str) -> list[str]:
    if service is None:
        return ["drug_claim_date"]
    missing = []
    if getattr(evidence, "applies_on", None) != service:
        missing.append(prefix + ".applies_on")
    assessed = getattr(evidence, "assessment_date", None)
    if assessed is None or assessed > service:
        missing.append(prefix + ".assessment_date")
    return missing


# ── inputs ──────────────────────────────────────────────────────────────────

_CODE_ALPHABET = ("P", "p", "5", "0", ".", "-", " ", "A", "a", "ı", "ß", "\t")


def _code_inputs() -> list[Any]:
    """Every string of up to 4 characters over the alphabet, the modules' own codes spelt 6 ways, oddities."""
    strings = [
        "".join(chars)
        for length in range(5)
        for chars in itertools.product(_CODE_ALPHABET, repeat=length)
    ]
    own_codes = set(blood_component_isbt128._BLOOD_COMPONENT_CODES)
    own_codes |= set(icu_bundled_leakage._BUNDLED_SERVICE_CODES)
    own_codes |= set(refakatci._ICU_PROCEDURE_CODES) | {refakatci._REFAKATCI_CODE}
    own_codes |= set(icu_puani.ICU_PACKAGE_CODES) | set(icu_puani._TIER_3_PACKAGE_CODES)
    own_codes |= set(icu_puani._TIER_3_SUPPORT_PROCEDURE_CODES) | {yatak_icu_overlap._BED_CODE}
    for code in sorted(own_codes):
        strings += [
            code,
            f"P{code}",
            f"p{code}",
            f" {code[:3]}.{code[3:]} ",
            f"{code[:3]} {code[3:]}",
            f"{code[:3]}-{code[3:]}".lower(),
        ]
    return [*strings, None, 0, "PAKET", "P", "PP510010", "P510010A", "p 510.010", "İ510010"]


def _amount_lines() -> list[Any]:
    amounts = [0, 1, -1, 2.5, Decimal("0"), Decimal("0.00"), Decimal("12.34"), Decimal("-0.01"),
               "3.5", "0", True, False, float("inf"), float("nan"), 10**20]
    return [SimpleNamespace(billed_amount_try=amount) for amount in amounts]


def _same_float(a: float, b: float) -> bool:
    return (math.isnan(a) and math.isnan(b)) or a == b


def _material_keyword_lists() -> list[list[str]]:
    lists = []
    for ruleset in (load_specialty_materials_rules(), load_material_bundling_rules()):
        for rule in ruleset["rules"]:
            keywords = (rule.get("condition") or {}).get("material_name_any")
            if keywords:
                lists.append(list(keywords))
    return lists


def _material_names(keyword_lists: list[list[str]]) -> list[str]:
    words = sorted({kw for kws in keyword_lists for kw in kws})
    names = ["", " ", "x", "İĞNE", "ıĞNE", "Şeker", "GAZLI BEZ"]
    for word in words:
        names += [word, word.upper(), f"Steril {word} 10 cm", fold_turkish(word, TurkishFold.ASCII)]
    return names


# ── the tests ───────────────────────────────────────────────────────────────

_CODE_ROWS = [
    ("refakatci", refakatci, _old_normalize_code_keep, PackagePrefix.KEEP),
    ("icu_puani", icu_puani, _old_normalize_code_icu_puani, PackagePrefix.ALWAYS),
    ("temporal_anomaly", temporal_anomaly, _old_normalize_code_temporal, PackagePrefix.BEFORE_DIGITS),
    ("anestezi_puani", anestezi_puani, _old_normalize_code_anestezi, PackagePrefix.BEFORE_DIGITS),
    ("blood_component_isbt128", blood_component_isbt128, _old_normalize_code_always, PackagePrefix.ALWAYS),
    ("yatak_icu_overlap", yatak_icu_overlap, _old_normalize_code_always, PackagePrefix.ALWAYS),
    ("icu_bundled_leakage", icu_bundled_leakage, _old_normalize_code_always, PackagePrefix.ALWAYS),
]


@pytest.mark.parametrize(("name", "module", "old", "prefix"), _CODE_ROWS, ids=[r[0] for r in _CODE_ROWS])
def test_clean_procedure_code_answers_as_the_old_normalize_code(name, module, old, prefix) -> None:
    inputs = _code_inputs()
    assert len(inputs) > 20_000
    changed = 0
    for raw in inputs:
        expected = old(raw)
        assert clean_procedure_code(raw, prefix) == expected, (name, raw)
        changed += expected != raw
    assert changed > 20_000
    # The module reads its own prefix (pinned on the source by the caller test below).
    assert f"PackagePrefix.{prefix.name}" in (_PROSE_RULES / f"{name}.py").read_text(encoding="utf-8")


def test_the_three_package_prefix_readings_differ() -> None:
    assert [clean_procedure_code("p510.010", p) for p in PackagePrefix] == ["P510010", "510010", "510010"]
    assert [clean_procedure_code("PAKET", p) for p in PackagePrefix] == ["PAKET", "PAKET", "AKET"]


def test_line_billed_amount_answers_as_the_old_line_billed() -> None:
    for line in _amount_lines():
        assert _same_float(line_billed_amount(line), _old_line_billed(line)), line
        assert material_uplift._has_billed_amount(line) is _old_line_billed_bool(line), line
    for bad in (SimpleNamespace(billed_amount_try=None), SimpleNamespace(), SimpleNamespace(billed_amount_try="x")):
        for fn in (line_billed_amount, _old_line_billed, material_uplift._has_billed_amount):
            with pytest.raises((TypeError, ValueError, AttributeError)):
                fn(bad)


def test_material_fields_answer_as_the_old_copy() -> None:
    values = [None, "", " ", 0, " ab-1 ", "Gazlı bez", 12, 3.5, Decimal("7.25"), "0"]
    keys = ("name", "material_name", "code", "material_code")
    count = 0
    for name, material_name, code, material_code in itertools.product(values, repeat=4):
        mat = dict(zip(keys, (name, material_name, code, material_code), strict=True))
        for price_keys in ((), ("unit_price",), ("billed_amount_try",), ("unit_price", "billed_amount_try")):
            for price in (None, 0, 4.5, Decimal("2.10")):
                priced = {**mat, **{k: price for k in price_keys}}
                assert material_fields(priced) == _old_material_fields(priced), priced
                count += 1
    assert count > 100_000


def test_material_name_matches_answers_as_the_old_copy() -> None:
    keyword_lists = _material_keyword_lists()
    names = _material_names(keyword_lists)
    assert len(keyword_lists) > 100 and len(names) > 1_000
    hits = 0
    for name in names:
        for keywords in (*keyword_lists, [], [""]):
            expected = _old_material_name_matches(name, keywords)
            assert material_name_matches(name, keywords) is expected, (name, keywords)
            hits += expected
    assert hits > 1_000


def test_the_checklist_reads_fatura_inceleme_branch_keywords_as_before() -> None:
    keywords = fatura_inceleme._BRANCH_KEYWORDS
    assert hashlib.sha256(repr(keywords).encode()).hexdigest() == _OLD_CHECKLIST_BRANCH_KEYWORDS_SHA256
    assert fatura_inceleme_checklist._branch_matches is fatura_inceleme._branch_matches
    departments = sorted({kw for kws in keywords.values() for kw in kws})
    departments += [d.upper() for d in departments] + ["", "Dahiliye Polikliniği", "KBB", "Acil Servis"]
    contexts = [{}] + [
        {"department": dept, "provider_specialty": spec}
        for dept in (*departments, None)
        for spec in (None, "", "Kardiyoloji", "göğüs")
    ]
    hits = 0
    for branch in (None, "BİLİNMEYEN", *keywords):
        for context in contexts:
            expected = _old_branch_matches(branch, context, keywords)
            assert fatura_inceleme._branch_matches(branch, context) is expected, (branch, context)
            hits += expected
    assert hits > 1_000


_DATES = (None, date(2024, 1, 1), date(2024, 1, 2), date(2024, 1, 3))


def test_evidence_date_missing_answers_as_the_old_date_missing() -> None:
    evidences = [None, SimpleNamespace()] + [
        SimpleNamespace(applies_on=applies, assessment_date=assessed)
        for applies in _DATES
        for assessed in _DATES
    ]
    for prefix in ("mds_evidence", "mesothelioma_evidence", "adult_gh_evidence"):
        for evidence in evidences:
            for service in _DATES:
                assert clinical_common.evidence_date_missing(evidence, prefix, service) == _old_date_missing(
                    evidence, service, prefix
                ), (prefix, evidence, service)


# Each module and the private helpers it no longer defines.
_MERGED = {
    "refakatci.py": {"_normalize_code"},
    "icu_puani.py": {"_normalize_code", "_strip_p"},
    "temporal_anomaly.py": {"_normalize_code"},
    "anestezi_puani.py": {"_normalize_code"},
    "blood_component_isbt128.py": {"_normalize_code"},
    "yatak_icu_overlap.py": {"_normalize_code"},
    "icu_bundled_leakage.py": {"_normalize_code"},
    "blood_uplift.py": {"_line_billed"},
    "drg_unbundling.py": {"_line_billed"},
    "transplant_package_scope.py": {"_line_billed"},
    "procedure_addon_uplift.py": {"_line_billed"},
    "session_uplift.py": {"_line_billed"},
    "material_uplift.py": {"_line_billed"},
    "material_bundling.py": {"_material_fields", "_material_name_matches"},
    "specialty_materials.py": {"_material_fields", "_material_name_matches"},
    "fatura_inceleme_checklist.py": {"_branch_matches", "_BRANCH_KEYWORDS"},
    "_drug_indication/clinical_mds.py": {"_date_missing"},
    "_drug_indication/clinical_mesothelioma_documents.py": {"_date_missing"},
    "adult_gh_draft.py": {"_date_missing"},
}


@pytest.mark.parametrize("relpath", sorted(_MERGED))
def test_no_module_defines_the_merged_helper_again(relpath: str) -> None:
    tree = ast.parse((_PROSE_RULES / relpath).read_text(encoding="utf-8"))
    defined = {node.name for node in tree.body if isinstance(node, (ast.FunctionDef, ast.ClassDef))}
    defined |= {
        target.id
        for node in tree.body
        if isinstance(node, (ast.Assign, ast.AnnAssign))
        for target in (node.targets if isinstance(node, ast.Assign) else [node.target])
        if isinstance(target, ast.Name)
    }
    assert not (defined & _MERGED[relpath])
