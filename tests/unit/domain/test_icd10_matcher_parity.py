"""Every ICD-10 matcher answers exactly as before it was moved onto ``src.bilun.domain.icd10``.

Each ``_old_*`` function below is the matcher as it stood at 756eed3, copied verbatim. A caller now
reads the shared helper with its own ``Icd10Cover``; the tables run the old matcher and the caller on
the same inputs: every code and range of the rule data the caller reads, the codes around each one
(itself, its leaves, its parent, its sibling, a further dot segment, lower case and padded), the
active and passive SKRS codes of the categories the caller lists, the demo's diagnoses and malformed
edge cases.
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

import polars as pl
import pytest

from src.bilun.domain.drugs.ek4d_exempt import _diagnosis_matches_section, _section_index
from src.bilun.domain.icd10 import (
    Icd10Cover,
    icd10_any_code_covered,
    icd10_covers,
    icd10_in_range,
    normalize_icd10,
    normalize_icd10_list,
)
from src.bilun.domain.loaders.legacy import _load_ek1a_list
from src.bilun.domain.prose_rules import drug_combination, treatment_pricing
from src.bilun.domain.prose_rules._drug_indication.clinical_ravulizumab import (
    evaluate_ravulizumab_continuation,
)
from src.bilun.domain.prose_rules._drug_indication.matching import (
    _diagnosis_matches_specific_rule,
)
from src.bilun.domain.prose_rules.catalog_membership import (
    get_ek2d3_emergency_icd10_codes,
    get_ek2d3_icd10_codes,
)
from src.bilun.domain.prose_rules.drug_indication import list_drug_indication_rules

_ROOT = Path(__file__).resolve().parents[3]
_RULES_DIR = _ROOT / "data/gazette/prose_rules"

_EDGE_CODES: tuple[Any, ...] = (
    None,
    "",
    " ",
    "  m45.9 ",
    "M",
    "M.",
    "M4",
    "M45",
    "M45.",
    "M45.9",
    "M45.90",
    "M450",
    "M451.0",
    "1A",
    ".5",
    ".M45",
    "M45..9",
    "M86.4.9",
    "G36.0",
    "G36.0.1",
    "G36.01",
    "G36",
    "C84.A",
    "Z99999",
    "U07.1",
    "m08.01",
    "K52.21",
    "N18.3",
    "E75.21",
    "C49.5",
    "C49.51",
    "C49.5.1",
    "C49",
    "A15",
    "A19.9",
)


# --- the matchers as they stood at 756eed3 -------------------------------------------------------


def _old_icd10_in_range(code: str, start: str, end: str) -> bool:
    if not code or not start:
        return False

    code = code.strip().upper()
    start = start.strip().upper()
    end = end.strip().upper()

    if not code or not code[0].isalpha():
        return False

    code_letter = code[0]
    start_letter = start[0] if start else ""
    end_letter = end[0] if end else start_letter  # noqa: F841

    if code_letter != start_letter:
        return False

    if "." in start and start == end:
        return code == start or code.startswith(start + ".")

    if "." in start:
        return code.startswith(start.split(".")[0])

    m_code = re.match(r"[A-Z](\d{2,3})", code)
    m_start = re.match(r"[A-Z](\d{2,3})", start)
    m_end = re.match(r"[A-Z](\d{2,3})", end)

    if not m_code or not m_start or not m_end:
        return False

    code_num = int(m_code.group(1))
    start_num = int(m_start.group(1))
    end_num = int(m_end.group(1))

    return start_num <= code_num <= end_num


def _old_icd10_listed_covers(listed: str, code: str) -> bool:
    if code == listed:
        return True
    if "." in listed:
        return code.startswith(listed)
    return code.startswith(listed + ".")


def _old_diagnosis_matches_specific_rule(codes: list[str], rule: dict[str, Any]) -> bool:
    icd_codes = [str(c).strip().upper() for c in (rule.get("icd10_codes") or []) if c]
    icd_ranges = [str(r).strip().upper() for r in (rule.get("icd10_ranges") or []) if r]

    for raw in codes:
        code = str(raw or "").strip().upper()
        if not code:
            continue
        if code in icd_codes:
            return True
        for listed in icd_codes:
            if _old_icd10_listed_covers(listed, code):
                return True
        for span in icd_ranges:
            if "-" in span:
                start, end = span.split("-", 1)
                if _old_icd10_in_range(code, start, end):
                    return True
            elif _old_icd10_in_range(code, span, span) or _old_icd10_listed_covers(span, code):
                return True
    return False


def _old_ek4d_diagnosis_matches_section(diagnosis: str, bucket: dict[str, Any]) -> bool:
    code = str(diagnosis or "").strip().upper()
    if not code:
        return False
    if code in bucket["icd_codes"]:
        return True
    for listed in bucket["icd_codes"]:
        if listed and (code == listed or code.startswith(listed + ".")):
            return True
    for span in bucket["icd_ranges"]:
        start = str(span.get("start", "")).upper()
        end = str(span.get("end", start)).upper()
        if start and _old_icd10_in_range(code, start, end):
            return True
    return False


def _old_drug_combination_diagnosis_matches(codes: list[str], rule_codes: list[str]) -> bool:
    icd_codes = [str(c).strip().upper() for c in rule_codes if c]
    if not icd_codes:
        return True
    for raw in codes:
        code = str(raw or "").strip().upper()
        if not code:
            continue
        if code in icd_codes:
            return True
        for listed in icd_codes:
            if code.startswith(listed + ".") or code == listed:
                return True
    return False


def _old_treatment_pricing_diagnosis_matches(codes: list[str], rule_codes: list[str]) -> bool:
    listed = [str(c).strip().upper() for c in (rule_codes or []) if c]
    if not listed:
        return True
    for raw in codes or []:
        code = str(raw or "").strip().upper()
        if not code:
            continue
        if code in listed:
            return True
        for prefix in listed:
            if code == prefix or code.startswith(prefix + "."):
                return True
    return False


def _old_icd10_categories(codes: list[str]) -> set[str]:
    out: set[str] = set()
    for raw in codes or []:
        code = str(raw or "").strip().upper()
        if not code:
            continue
        for cat, prefixes in treatment_pricing._ICD10_CATEGORY_PREFIXES.items():
            for prefix in prefixes:
                if code == prefix or code.startswith(prefix + "."):
                    out.add(cat)
                    break
    return out


def _old_ravulizumab_has_nmosd_code(codes: list[str] | None) -> bool:
    return any(code == "G36.0" or code.startswith("G36.0.") for code in codes or [])


# --- the inputs -----------------------------------------------------------------------------------


@lru_cache(maxsize=1)
def _skrs_by_category() -> dict[str, tuple[str, ...]]:
    frame = pl.read_parquet(_ROOT / "data/synthetic/reference/icd10_tr.parquet", columns=["code"])
    by_category: dict[str, list[str]] = {}
    for code in frame["code"].drop_nulls().to_list():
        by_category.setdefault(code[:3].upper(), []).append(code)
    return {category: tuple(codes) for category, codes in by_category.items()}


@lru_cache(maxsize=1)
def _demo_codes() -> tuple[str, ...]:
    claims = _ROOT / "data/synthetic/sut/claims"
    rows = pl.read_parquet(claims / "claim_diagnoses.parquet", columns=["icd10_code"])["icd10_code"]
    primary = pl.read_parquet(claims / "claim_headers.parquet", columns=["primary_icd10"])
    return tuple(sorted(set(rows.drop_nulls()) | set(primary["primary_icd10"].drop_nulls())))


def _around(selector: str) -> set[str]:
    """The codes a matcher could confuse with ``selector``."""
    s = selector.strip().upper()
    out = {
        selector,
        s,
        s.lower(),
        f" {s} ",
        s + ".",
        s + "0",
        s + "9",
        s + ".1",
        s + ".12",
        s + ".1.2",
    }
    out.update({s[:3], s[:3] + ".9", s[:-1], s[:-2]})
    if s and s[-1].isdigit():
        out.add(s[:-1] + str((int(s[-1]) + 1) % 10))
    return {code for code in out if code}


def _categories(selector: str) -> set[str]:
    """The three-character categories a selector or a range ``A-B`` touches."""
    s = selector.strip().upper()
    if "-" not in s:
        return {s[:3]}
    start, end = (part.strip() for part in s.split("-", 1))
    m_start, m_end = re.match(r"([A-Z])(\d{2})", start), re.match(r"([A-Z])(\d{2})", end)
    if not m_start or not m_end:
        return {start[:3], end[:3]}
    if m_start.group(1) != m_end.group(1):
        return {start[:3], end[:3]}
    low, high = int(m_start.group(2)), int(m_end.group(2))
    return {f"{m_start.group(1)}{n:02d}" for n in range(low, high + 1)} | {start[:3], end[:3]}


def _probes(selectors: list[str]) -> list[Any]:
    """Every selector's neighbours, the SKRS codes of its categories, the demo codes, edge cases."""
    skrs = _skrs_by_category()
    out: set[str] = set(_demo_codes())
    for selector in selectors:
        for part in selector.split("-"):
            out.update(_around(part))
        for category in _categories(selector):
            out.update(skrs.get(category, ()))
    return [*_EDGE_CODES, *sorted(out)]


def _condition_codes(path: Path, keys: tuple[str, ...]) -> list[list[Any]]:
    found: list[list[Any]] = []

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                if key in keys and isinstance(value, list):
                    found.append(value)
                walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(json.loads(path.read_text(encoding="utf-8"))["rules"])
    return found


_COMBINATION_LISTS = _condition_codes(
    _RULES_DIR / "drug_combination_4_2.json", ("diagnosis_any", "indication_not_in")
)
_PRICING_LISTS = _condition_codes(
    _RULES_DIR / "treatment_pricing_2_4.json", ("diagnosis_any", "diagnosis_in", "diagnosis_not_in")
)


def _with_edge_lists(lists: list[list[Any]]) -> list[list[Any]]:
    return [
        *lists,
        sorted(get_ek2d3_icd10_codes()),
        sorted(get_ek2d3_emergency_icd10_codes()),
        [],
        [None, ""],
        [" "],
        [" k50 ", "M08.0", "C84.A"],
    ]


# --- the tables -----------------------------------------------------------------------------------


def test_the_rule_data_is_present() -> None:
    assert len(list_drug_indication_rules()) > 900
    assert len(_section_index()) == 15
    assert len(_load_ek1a_list()) > 90
    assert len(_COMBINATION_LISTS) > 20 and len(_PRICING_LISTS) > 15
    assert len(get_ek2d3_icd10_codes()) > 50
    assert len(_demo_codes()) > 40


def test_drug_indication_matches_as_before() -> None:
    compared = matched = 0
    for rule in list_drug_indication_rules():
        selectors = [
            str(s)
            for s in [*(rule.get("icd10_codes") or []), *(rule.get("icd10_ranges") or [])]
            if s
        ]
        probes = _probes(selectors)
        for code in probes:
            answer = _diagnosis_matches_specific_rule([code], rule)
            assert answer is _old_diagnosis_matches_specific_rule([code], rule), (
                rule.get("rule_id"),
                code,
            )
            matched += answer
        assert _diagnosis_matches_specific_rule(
            probes, rule
        ) is _old_diagnosis_matches_specific_rule(probes, rule)
        compared += len(probes)
    assert compared > 100_000 and matched > 10_000


def test_drug_indication_hand_built_rules_match_as_before() -> None:
    rules = [
        {
            "icd10_codes": [" m08.0 ", None, "", "M45"],
            "icd10_ranges": ["M79.7", " m05-m06 ", "C49.5-C49.9"],
        },
        {"icd10_codes": [], "icd10_ranges": ["K52.2", "A15-A19", "M-M", "-", "C84.A"]},
        {"icd10_codes": ["G36.0", "1A"], "icd10_ranges": None},
    ]
    for rule in rules:
        selectors = [
            str(s) for s in [*(rule["icd10_codes"] or []), *(rule["icd10_ranges"] or [])] if s
        ]
        for code in _probes(selectors):
            assert _diagnosis_matches_specific_rule(
                [code], rule
            ) is _old_diagnosis_matches_specific_rule([code], rule), (rule, code)


def test_ek4d_sections_match_as_before() -> None:
    compared = matched = 0
    for section_id, bucket in _section_index().items():
        selectors = [*bucket["icd_codes"]]
        for span in bucket["icd_ranges"]:
            selectors += [str(span.get("start", "")), str(span.get("end", span.get("start", "")))]
            selectors.append(f"{span.get('start', '')}-{span.get('end', span.get('start', ''))}")
        for code in _probes([s for s in selectors if s]):
            answer = _diagnosis_matches_section(code, bucket)
            assert answer is _old_ek4d_diagnosis_matches_section(code, bucket), (section_id, code)
            compared += 1
            matched += answer
    assert compared > 10_000 and matched > 1_000


def test_ek4d_hand_built_bucket_matches_as_before() -> None:
    bucket = {
        "icd_codes": frozenset({"M86.3", "M05", "G36.0", ""}),
        "icd_ranges": [
            {"start": "a15", "end": "A19"},
            {"start": "P37.0"},
            {"start": ""},
            {"start": "C49.5", "end": "C49.9"},
        ],
    }
    for code in _probes(["M86.3", "M05", "G36.0", "A15-A19", "P37.0", "C49.5-C49.9"]):
        assert _diagnosis_matches_section(code, bucket) is _old_ek4d_diagnosis_matches_section(
            code, bucket
        ), code


def test_ek1a_ranges_match_as_before() -> None:
    ek1a = _load_ek1a_list()
    spans = sorted(
        {(str(s), str(e)) for s, e in zip(ek1a["icd10_start"], ek1a["icd10_end"], strict=True)}
    )
    spans += [
        ("C49.5", "C49.5"),
        ("C49.5", "C49.9"),
        ("a15 ", " a19"),
        ("M", "M"),
        ("1A", "1A"),
        ("", "A19"),
    ]
    compared = matched = 0
    for start, end in spans:
        probes = _probes([start, end, f"{start}-{end}"])
        for code in probes:
            if code is None:
                continue
            answer = icd10_in_range(code, start, end)
            assert answer is _old_icd10_in_range(code, start, end), (start, end, code)
            compared += 1
            matched += answer
    assert compared > 10_000 and matched > 1_000


@pytest.mark.parametrize(
    ("new", "old", "lists"),
    [
        (
            drug_combination._diagnosis_matches,
            _old_drug_combination_diagnosis_matches,
            _COMBINATION_LISTS,
        ),
        (
            treatment_pricing._diagnosis_matches,
            _old_treatment_pricing_diagnosis_matches,
            _PRICING_LISTS,
        ),
    ],
    ids=["drug_combination", "treatment_pricing"],
)
def test_prose_rule_diagnosis_lists_match_as_before(new, old, lists) -> None:
    matched = 0
    for rule_codes in _with_edge_lists(lists):
        probes = _probes([str(c) for c in rule_codes if c])
        for code in probes:
            answer = new([code], rule_codes)
            assert answer is old([code], rule_codes), (rule_codes, code)
            matched += answer
        assert new(probes, rule_codes) is old(probes, rule_codes)
        assert new([], rule_codes) is old([], rule_codes)
    assert matched > 100


def test_treatment_pricing_categories_as_before() -> None:
    prefixes = [p for group in treatment_pricing._ICD10_CATEGORY_PREFIXES.values() for p in group]
    probes = _probes(prefixes) + ["M77.1", "M72.2", "M75.1", "M", "7", "M.1"]
    for code in probes:
        assert treatment_pricing._icd10_categories([code]) == _old_icd10_categories([code]), code
    assert treatment_pricing._icd10_categories(probes) == _old_icd10_categories(probes)
    assert treatment_pricing._icd10_categories([]) == _old_icd10_categories([]) == set()


def test_ravulizumab_nmosd_code_as_before() -> None:
    from types import SimpleNamespace

    line = SimpleNamespace(ravulizumab_evidence=None, drug_claim_date=None)
    for code in _probes(["G36.0"]):
        if code is None:
            continue
        codes = [code]
        old_skips = not _old_ravulizumab_has_nmosd_code(codes)
        # With no evidence the evaluator returns None exactly when no code is the NMOSD code.
        assert (evaluate_ravulizumab_continuation(line, codes) is None) is old_skips, code


# --- the helper on its own ------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("listed", "code", "exact", "leaves"),
    [
        ("M45", "M45", True, True),
        ("M45", "M45.9", True, True),
        ("M45", "M45.90", True, True),
        ("M45", "M450", False, False),
        ("M08.0", "M08.01", False, True),
        ("M08.0", "M08.0.1", True, True),
        ("M08.0", "M08.1", False, False),
        ("M08.0", "M08", False, False),
        ("E75.21", "E75.2", False, False),
        ("", "M45", False, False),
        ("", ".5", True, True),
    ],
)
def test_icd10_covers_by_reading(listed: str, code: str, exact: bool, leaves: bool) -> None:
    assert icd10_covers(listed, code, cover=Icd10Cover.EXACT) is exact
    assert icd10_covers(listed, code, cover=Icd10Cover.LEAVES) is leaves
    assert icd10_covers(listed, code, cover=Icd10Cover.LEAVES) is _old_icd10_listed_covers(
        listed, code
    )


def test_normalisation_and_any_code() -> None:
    assert normalize_icd10(None) == normalize_icd10("") == ""
    assert normalize_icd10(" m45.9 ") == "M45.9"
    assert normalize_icd10_list([" k50 ", None, "", " ", 0]) == ["K50", ""]
    assert normalize_icd10_list(None) == []
    assert icd10_any_code_covered([None, " ", " m45.9"], ["M45"], cover=Icd10Cover.EXACT) is True
    assert icd10_any_code_covered(None, ["M45"], cover=Icd10Cover.EXACT) is False
    assert icd10_any_code_covered(["M08.01"], ["M08.0"], cover=Icd10Cover.EXACT) is False
    assert icd10_any_code_covered(["M08.01"], ["M08.0"], cover=Icd10Cover.LEAVES) is True
