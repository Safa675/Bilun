"""A listed ICD-10 code covers the leaves under it in the SKRS tree (#305).

The demo data codes diagnoses as SKRS leaves (review 2026-10-16, ICD answer 5), and SKRS splits the
musculoskeletal subcategories by site: M08.0 has the leaves M08.00-M08.09. A drug rule that lists
M08.0 (or the single range M79.7) must cover them, as a listed category (M45) already covers M45.9.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import replace
from datetime import date
from decimal import Decimal
from functools import lru_cache
from pathlib import Path

import pyarrow.parquet as pq
import pytest

from src.bilun.domain.billing.claim_drug_indication import validate_drug_indication_from_claims
from src.bilun.domain.claims.models import ClaimDiagnosis, ClaimHeader, DrugClaimLine
from src.bilun.domain.claims.patient_context import PatientClaimContext
from src.bilun.domain.icd10 import Icd10Cover, icd10_covers
from src.bilun.domain.prose_rules._drug_indication.matching import (
    _diagnosis_matches_specific_rule,
)
from src.bilun.domain.prose_rules.drug_indication import (
    check_drug_indication_for_context,
    evaluate_drug_indication_line_detailed,
    list_drug_indication_rules,
)

pytestmark = pytest.mark.unit

_ICD10_TR = Path(__file__).resolve().parents[4] / "data/reference/icd10_tr.parquet"

# The issue's table: every dotted listed code of the corpus that has SKRS children.
_PARENTS_BY_RULE = {
    "4.2.1.C.ankylosing_spondylitis_nsaids_failure_report": ("M46.0", "M46.8", "M46.9"),
    "4.2.1.C.juvenile_ra_das28_activity_scoring": ("M08.0",),
    "4.2.17.B.calcitonin_first_6mo_only": ("M48.5",),
    "4.2.17.calcitonin_vertebral_fracture_report": ("M48.5",),
    "4.2.35.B.chronic_msk_fibromyalgia_specialists": ("M79.0", "M79.7"),
    "4.2.35.neuropathic_pain_specialist_report": ("M79.2",),
    "4.2.35.pregabalin_fibromyalgia_board_6mo": ("M79.1", "M79.7"),
}
_PREGABALIN_RULE = "4.2.35.pregabalin_fibromyalgia_board_6mo"
_LYRICA = "LYRICA 75 MG 56 KAPSUL (PREGABALIN)"
_MIACALCIC = "MIACALCIC 200 IU NAZAL SPREY (KALSITONIN)"


@lru_cache(maxsize=1)
def _skrs() -> tuple[dict[str, dict], dict[str, tuple[str, ...]]]:
    rows = pq.read_table(_ICD10_TR).to_pylist()
    by_code = {row["code"]: row for row in rows}
    children: dict[str, list[str]] = defaultdict(list)
    for row in rows:
        if row["parent_code"]:
            children[row["parent_code"]].append(row["code"])
    return by_code, {code: tuple(sorted(kids)) for code, kids in children.items()}


def _descendants(code: str) -> list[str]:
    """Active SKRS diagnosis codes below ``code`` in the SKRS tree (by ``parent_code``)."""
    by_code, children = _skrs()
    out: list[str] = []
    stack = list(children.get(code, ()))
    while stack:
        child = stack.pop()
        row = by_code[child]
        if row["is_active"] and row["kind"] in {"category", "subcategory"}:
            out.append(child)
        stack.extend(children.get(child, ()))
    return sorted(out)


@lru_cache(maxsize=1)
def _rules_by_id() -> dict[str, dict]:
    return {str(rule["rule_id"]): rule for rule in list_drug_indication_rules()}


def _selectors(rule: dict) -> list[tuple[str, str]]:
    return [
        *(("icd10_codes", str(c).strip().upper()) for c in rule.get("icd10_codes") or [] if c),
        *(("icd10_ranges", str(c).strip().upper()) for c in rule.get("icd10_ranges") or [] if c),
    ]


def _single_code_selectors() -> list[tuple[str, str, str]]:
    """Every listed code and every single (non-hyphen) range of the corpus that SKRS knows."""
    by_code, _ = _skrs()
    out = {
        (rule_id, field, code)
        for rule_id, rule in _rules_by_id().items()
        for field, code in _selectors(rule)
        if "-" not in code and code in by_code
    }
    return sorted(out)


# ---------------------------------------------------------------------------
# The matcher
# ---------------------------------------------------------------------------


def test_the_issue_table_is_every_dotted_listed_code_with_skrs_children() -> None:
    """The nine parents of #305 are all the dotted selectors of the corpus that are not leaves."""
    by_code, _ = _skrs()
    found: dict[str, set[str]] = defaultdict(set)
    for rule_id, _field, code in _single_code_selectors():
        if "." in code and not by_code[code]["is_leaf"]:
            found[rule_id].add(code)
    assert {rule_id: tuple(sorted(codes)) for rule_id, codes in found.items()} == _PARENTS_BY_RULE


def test_every_listed_code_of_the_corpus_covers_each_of_its_skrs_descendants() -> None:
    selectors = _single_code_selectors()
    assert len(selectors) > 1000
    uncovered = {
        (rule_id, field, listed): missing
        for rule_id, field, listed in selectors
        if (
            missing := [
                code
                for code in _descendants(listed)
                if not _diagnosis_matches_specific_rule([code], _rules_by_id()[rule_id])
            ]
        )
    }
    assert uncovered == {}


@pytest.mark.parametrize(
    ("rule_id", "listed"),
    [(rule_id, parent) for rule_id, parents in _PARENTS_BY_RULE.items() for parent in parents],
)
def test_each_parent_of_the_issue_covers_its_ten_leaves(rule_id: str, listed: str) -> None:
    leaves = _descendants(listed)
    assert leaves == [f"{listed}{digit}" for digit in range(10)]
    rule = _rules_by_id()[rule_id]
    assert [code for code in leaves if not _diagnosis_matches_specific_rule([code], rule)] == []


@pytest.mark.parametrize(
    ("code", "rule_ids"),
    [
        ("M08.01", ("4.2.1.C.juvenile_ra_das28_activity_scoring",)),
        ("M46.01", ("4.2.1.C.ankylosing_spondylitis_nsaids_failure_report",)),
        (
            "M48.51",
            ("4.2.17.B.calcitonin_first_6mo_only", "4.2.17.calcitonin_vertebral_fracture_report"),
        ),
        ("M79.01", ("4.2.35.B.chronic_msk_fibromyalgia_specialists",)),
        ("M79.11", (_PREGABALIN_RULE,)),
        ("M79.21", ("4.2.35.neuropathic_pain_specialist_report",)),
        ("M79.71", ("4.2.35.B.chronic_msk_fibromyalgia_specialists", _PREGABALIN_RULE)),
    ],
)
def test_the_acceptance_leaves_match_their_rules(code: str, rule_ids: tuple[str, ...]) -> None:
    matched = {
        rule_id
        for rule_id in _PARENTS_BY_RULE
        if _diagnosis_matches_specific_rule([code], _rules_by_id()[rule_id])
    }
    assert matched == set(rule_ids)


@pytest.mark.parametrize("field", ["icd10_codes", "icd10_ranges"])
@pytest.mark.parametrize(
    "parent", sorted({p for parents in _PARENTS_BY_RULE.values() for p in parents})
)
def test_a_parent_covers_only_its_own_subtree_in_its_category(field: str, parent: str) -> None:
    """Siblings, cousins and the category itself stay outside: M08.0 does not cover M08.1 or M08."""
    by_code, _ = _skrs()
    rule = {field: [parent]}
    inside = {parent, *_descendants(parent)}
    category = parent.split(".")[0]
    same_category = [
        code
        for code, row in by_code.items()
        if row["is_active"]
        and row["kind"] in {"category", "subcategory"}
        and code.split(".")[0] == category
    ]
    assert len(same_category) > len(inside)
    covered = {code for code in same_category if _diagnosis_matches_specific_rule([code], rule)}
    assert covered == inside


@pytest.mark.parametrize("field", ["icd10_codes", "icd10_ranges"])
@pytest.mark.parametrize(
    ("listed", "code", "covered"),
    [
        # today's exact and dotted matches stay
        ("M08.0", "M08.0", True),
        ("M45", "M45", True),
        ("M45", "M45.9", True),
        ("M45", "M45.90", True),
        ("E75.21", "E75.21", True),
        # a dotted code covers every longer code under it (#305)
        ("M08.0", "M08.00", True),
        ("M08.0", "M08.01", True),
        ("M08.0", "M08.09", True),
        ("M79.7", "M79.70", True),
        ("M79.7", "m79.71 ", True),
        ("E75.2", "E75.21", True),
        # never its parent, a sibling or a sibling's leaf
        ("M08.0", "M08", False),
        ("M08.0", "M08.1", False),
        ("M08.0", "M08.10", False),
        ("M79.1", "M79.2", False),
        ("M79.1", "M79.21", False),
        ("E75.21", "E75.2", False),
        ("E75.21", "E75.22", False),
        # a category covers dotted codes only, not a code that merely starts with its letters
        ("M45", "M450", False),
        ("M45", "M451.0", False),
        ("M08", "M08.01", True),
        # another letter or an empty code is never covered
        ("M08.0", "N08.01", False),
        ("M08.0", "", False),
    ],
)
def test_listed_code_cover_on_both_selector_fields(
    field: str, listed: str, code: str, covered: bool
) -> None:
    assert _diagnosis_matches_specific_rule([code], {field: [listed]}) is covered


@pytest.mark.parametrize(
    ("listed", "code", "covered"),
    [
        ("M45", "M45", True),
        ("M45", "M45.9", True),
        ("M45", "M450", False),
        ("M08.0", "M08.0", True),
        ("M08.0", "M08.01", True),
        ("M08.0", "M08", False),
        ("M08.0", "M08.1", False),
        ("M08.01", "M08.0", False),
    ],
)
def test_the_cover_helper_on_its_own(listed: str, code: str, covered: bool) -> None:
    assert icd10_covers(listed, code, cover=Icd10Cover.LEAVES) is covered


@pytest.mark.parametrize(
    ("span", "code", "covered"),
    [
        ("M05-M06", "M06.01", True),
        ("M05-M06", "M05", True),
        ("M05-M06", "M07.01", False),
        ("C81-C96", "C84.A0", True),
    ],
)
def test_hyphen_ranges_keep_their_category_comparison(span: str, code: str, covered: bool) -> None:
    assert _diagnosis_matches_specific_rule([code], {"icd10_ranges": [span]}) is covered


def test_a_leaf_matches_when_any_of_several_codes_is_under_a_parent() -> None:
    rule = {"icd10_codes": ["E11", "M08.0"]}
    assert _diagnosis_matches_specific_rule(["I10", None, "", "M08.04"], rule) is True
    assert _diagnosis_matches_specific_rule(["I10", "M08.14"], rule) is False


# ---------------------------------------------------------------------------
# One drug line through the engine
# ---------------------------------------------------------------------------


def _claim(primary_icd10: str) -> ClaimHeader:
    return ClaimHeader(
        claim_id="C-305",
        patient_id="P-305",
        episode_id="E-305",
        claim_type="ayakta",
        facility_tier="3",
        provider_type="kamu",
        department="romatoloji",
        admission_date=date(2026, 3, 2),
        discharge_date=date(2026, 3, 2),
        claim_start_date=date(2026, 3, 2),
        claim_end_date=date(2026, 3, 2),
        primary_icd10=primary_icd10,
        expected_total_billed_try=Decimal("0"),
        expected_total_payable_try=Decimal("0"),
        expected_denial_reason="",
        scenario_tag="test-305",
    )


def _line(drug_name: str = _LYRICA, *, report_present: bool | None = True) -> DrugClaimLine:
    return DrugClaimLine(
        drug_claim_line_id="D-305",
        prescription_id="RX-305",
        claim_id="C-305",
        patient_id="P-305",
        episode_id="E-305",
        drug_claim_date=date(2026, 3, 2),
        drug_name=drug_name,
        drug_code="",
        barkod="",
        equivalence_group="",
        quantity=1,
        unit_price_try=Decimal("0"),
        billed_amount_try=Decimal("0"),
        expected_payable_try=Decimal("0"),
        discount_tier_expected=Decimal("0"),
        denial_reason_expected="",
        rule_trace_expected="",
        drug_specialty_board_report_present=report_present,
        drug_report_duration_months=6,
        prescriber_specialty="romatoloji",
    )


def _diagnosis(code: str, *, primary: bool) -> ClaimDiagnosis:
    return ClaimDiagnosis(
        diagnosis_id=f"DX-{code}",
        claim_id="C-305",
        patient_id="P-305",
        episode_id="E-305",
        icd10_code=code,
        is_primary=primary,
        diagnosis_role="birincil" if primary else "ek",
        diagnosis_date=date(2026, 3, 2),
        exemption_eligible=False,
    )


def _evaluate(primary_icd10: str, drug_name: str = _LYRICA, **line_kwargs) -> dict:
    return evaluate_drug_indication_line_detailed(
        drug_line=_line(drug_name, **line_kwargs),
        claim=_claim(primary_icd10),
        diagnoses=[],
    )


def _outcome(result: dict) -> tuple:
    violation = result.get("violation") or {}
    return (
        result.get("applicability_status"),
        result.get("evaluation_status"),
        result.get("selected_rule_id"),
        tuple(result.get("eligible_route_rule_ids") or ()),
        violation.get("violation_kind"),
        violation.get("severity"),
        violation.get("rule_id"),
    )


def test_the_pregabalin_probe_with_a_leaf_gives_no_finding() -> None:
    """#305's probe: LYRICA with a valid board report and specialty, primary M79.70."""
    parent = _evaluate("M79.7")
    leaf = _evaluate("M79.70")

    assert parent["violation"] is None
    assert leaf["violation"] is None
    assert leaf["selected_rule_id"] == _PREGABALIN_RULE
    assert leaf["matched_icd10_codes"] == ["M79.70"]
    assert leaf["unmatched_icd10_codes"] == []


@pytest.mark.parametrize(
    ("drug_name", "parent"),
    [(_LYRICA, "M79.7"), (_LYRICA, "M79.1"), (_LYRICA, "M79.2"), (_MIACALCIC, "M48.5")],
)
@pytest.mark.parametrize("report_present", [True, False])
def test_each_leaf_evaluates_like_its_parent(
    drug_name: str, parent: str, report_present: bool
) -> None:
    """The leaf takes the parent's route, so the rule's own checks (the report) apply to it."""
    expected = _outcome(_evaluate(parent, drug_name, report_present=report_present))
    assert expected[4] != "indication_mismatch"
    for leaf in _descendants(parent):
        assert _outcome(_evaluate(leaf, drug_name, report_present=report_present)) == expected, leaf


def test_a_leaf_without_the_board_report_gets_the_rules_report_finding() -> None:
    result = _evaluate("M79.70", report_present=False)
    assert result["selected_rule_id"] == _PREGABALIN_RULE
    assert result["violation"]["violation_kind"] != "indication_mismatch"
    assert result["violation"]["rule_id"] == _PREGABALIN_RULE


def test_a_leaf_under_an_unlisted_parent_is_still_an_indication_mismatch() -> None:
    result = _evaluate("M79.60")
    assert result["violation"]["violation_kind"] == "indication_mismatch"
    assert result["violation"]["severity"] == "error"
    assert result["matched_icd10_codes"] == []
    assert result["unmatched_icd10_codes"] == ["M79.60"]


# ---------------------------------------------------------------------------
# A small hand-built bill
# ---------------------------------------------------------------------------


def _bill(secondary: str) -> PatientClaimContext:
    return PatientClaimContext(
        patient_id="P-305",
        claims=(_claim("I10"),),
        procedure_lines=(),
        material_lines=(),
        drug_lines=(_line(),),
        diagnoses=(_diagnosis("I10", primary=True), _diagnosis(secondary, primary=False)),
    )


def test_a_bill_with_the_fibromyalgia_leaf_as_secondary_diagnosis_is_clean() -> None:
    ctx = _bill("M79.71")
    assert check_drug_indication_for_context(ctx) == []
    review = validate_drug_indication_from_claims(ctx)
    assert review.violation_count == 0
    assert review.error_count == 0


def test_the_same_bill_with_a_leaf_under_an_unlisted_parent_keeps_its_error() -> None:
    ctx = _bill("M79.61")
    violations = check_drug_indication_for_context(ctx)
    assert [v["violation_kind"] for v in violations] == ["indication_mismatch"]
    review = validate_drug_indication_from_claims(ctx)
    assert review.violation_count == 1
    assert review.error_count == 1


def test_the_bill_names_the_leaf_it_matched() -> None:
    ctx = replace(_bill("M79.71"), drug_lines=(_line(report_present=False),))
    violations = check_drug_indication_for_context(ctx)
    assert len(violations) == 1
    assert violations[0]["rule_id"] == _PREGABALIN_RULE
    assert violations[0]["matched_icd10_codes"] == ["M79.71"]
