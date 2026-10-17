"""Unit and mutation tests for `apply_fault` and `load_siblings` in scripts/synthetic/faults/."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from scripts.synthetic.faults import (
    DropDiagnosis,
    DropEntry,
    FaultApplyError,
    FaultSpec,
    SetBilledRatio,
    SetFlag,
    TruncateLineDays,
    apply_fault,
    load_registry,
    load_siblings,
)
from scripts.synthetic.pathways import Pathway, load_all
from scripts.synthetic.pathways.expand import expand

pytestmark = pytest.mark.unit

_REPO = Path(__file__).resolve().parents[3]
_GOLDEN_CLEAN = _REPO / "tests/fixtures/pathways/golden"
_GOLDEN_FAULTY = _REPO / "tests/fixtures/pathways/golden_faulty"

_ANNOTATION_KEYS = {
    "procedures": {"entry_id", "kind", "day_index"},
    "materials": {"entry_id"},
    "drugs": {"entry_id", "indication"},
    "performed": {"entry_id"},
}


@pytest.fixture(scope="module")
def pathways() -> dict[str, Pathway]:
    return load_all()


@pytest.fixture(scope="module")
def siblings() -> dict[str, Pathway]:
    return load_siblings()


@pytest.fixture(scope="module")
def faults() -> tuple[FaultSpec, ...]:
    return tuple(load_registry().faults)


def _fault_by_story(faults: tuple[FaultSpec, ...], story: str) -> FaultSpec:
    return next(f for f in faults if f.story == story)


def _golden(directory: Path, story: str) -> dict:
    return json.loads((directory / f"{story}.json").read_text(encoding="utf-8"))


def _strip_annotations(bill: dict) -> dict:
    out = dict(bill)
    for section, extra in _ANNOTATION_KEYS.items():
        out[section] = [{k: v for k, v in row.items() if k not in extra} for row in bill[section]]
    return out


# --- golden faulty equality & annotation stripping across all 8 faults -------------------------


@pytest.mark.parametrize("story", [f"S{n}" for n in range(1, 9)])
def test_apply_fault_equals_golden_faulty_and_differs_from_clean(
    story: str,
    faults: tuple[FaultSpec, ...],
    pathways: dict[str, Pathway],
    siblings: dict[str, Pathway],
) -> None:
    fault = _fault_by_story(faults, story)
    pathway = pathways[fault.target_pathway]

    clean_bill = expand(pathway)
    faulty_bill = apply_fault(fault, pathway, siblings=siblings)
    annotated_faulty = apply_fault(fault, pathway, siblings=siblings, annotate=True)

    assert clean_bill == _golden(_GOLDEN_CLEAN, story)
    assert faulty_bill == _golden(_GOLDEN_FAULTY, story)
    assert faulty_bill != clean_bill

    for section, extra in _ANNOTATION_KEYS.items():
        for row in faulty_bill[section]:
            assert set(row).isdisjoint(extra)
        for row in annotated_faulty[section]:
            assert extra <= set(row)

    assert _strip_annotations(annotated_faulty) == faulty_bill


# --- story-specific observable assertions ------------------------------------------------------


def test_story_specific_bill_contents(
    faults: tuple[FaultSpec, ...],
    pathways: dict[str, Pathway],
    siblings: dict[str, Pathway],
) -> None:
    def run(story: str) -> dict:
        f = _fault_by_story(faults, story)
        return apply_fault(f, pathways[f.target_pathway], siblings=siblings)

    # S1: replaced by the itemized sibling pathway's bill.
    s1 = run("S1")
    assert s1 == expand(siblings["appendicitis_lap_appendectomy_itemized"])

    # S2: exactly 4 510010 bed rows remain (down from 7).
    s2 = run("S2")
    assert [r["code"] for r in s2["procedures"]].count("510010") == 4

    # S3: no 550160 anaesthesia row.
    s3 = run("S3")
    assert "550160" not in {r["code"] for r in s3["procedures"]}

    # S4: no 510121 companion row.
    s4 = run("S4")
    assert "510121" not in {r["code"] for r in s4["procedures"]}

    # S5: AP2000 has uts_registered=False; the other two materials have uts_registered=True.
    s5 = run("S5")
    ap2000 = [m for m in s5["materials"] if m["code"] == "AP2000"]
    other_mats = [m for m in s5["materials"] if m["code"] != "AP2000"]
    assert len(ap2000) == 1 and ap2000[0]["flags"]["uts_registered"] is False
    assert len(other_mats) == 2 and all(m["flags"]["uts_registered"] is True for m in other_mats)

    # S6: no G20 diagnosis row.
    s6 = run("S6")
    assert "G20" not in {d["icd10"] for d in s6["diagnoses"]}

    # S7: no R101450 in billed procedures, but all 4 performed rows (including R101450) remain.
    s7 = run("S7")
    assert "R101450" not in {r["code"] for r in s7["procedures"]}
    assert len(s7["performed"]) == 4
    assert "R101450" in {r["code"] for r in s7["performed"]}

    # S8: P603840 has billed_ratio "1.0000".
    s8 = run("S8")
    hernia = [r for r in s8["procedures"] if r["code"] == "P603840"]
    assert len(hernia) == 1 and hernia[0]["billed_ratio"] == "1.0000"


# --- purity & determinism ----------------------------------------------------------------------


@pytest.mark.parametrize("story", [f"S{n}" for n in range(1, 9)])
def test_apply_fault_is_pure_and_deterministic(
    story: str,
    faults: tuple[FaultSpec, ...],
    pathways: dict[str, Pathway],
    siblings: dict[str, Pathway],
) -> None:
    fault = _fault_by_story(faults, story)
    pathway = pathways[fault.target_pathway]
    pins = copy.deepcopy(pathway.showcase)
    siblings_copy = dict(siblings)
    fault_before = fault.model_dump()
    pins_before = pins.model_dump()
    pathway_before = pathway.model_dump()
    siblings_before = {k: v.model_dump() for k, v in siblings_copy.items()}
    clean_before = expand(pathway)

    first = apply_fault(fault, pathway, pins, siblings=siblings_copy)
    second = apply_fault(fault, pathway, pins, siblings=siblings_copy)

    assert first == second
    assert fault.model_dump() == fault_before
    assert pins.model_dump() == pins_before
    assert pathway.model_dump() == pathway_before
    assert {k: v.model_dump() for k, v in siblings_copy.items()} == siblings_before
    assert expand(pathway) == clean_before


def test_in_memory_demo_forgetting_to_strip_annotations_or_mutating_input_is_caught(
    faults: tuple[FaultSpec, ...],
    pathways: dict[str, Pathway],
    siblings: dict[str, Pathway],
) -> None:
    s2_fault = _fault_by_story(faults, "S2")
    s2_pathway = pathways[s2_fault.target_pathway]

    # 1. If apply_fault forgot to strip annotations (returning annotate=True output), golden equality
    # and the disjoint-annotation-keys check both fail.
    unstripped = apply_fault(s2_fault, s2_pathway, siblings=siblings, annotate=True)
    assert unstripped != _golden(_GOLDEN_FAULTY, "S2")
    assert not set(unstripped["procedures"][0]).isdisjoint(_ANNOTATION_KEYS["procedures"])

    # 2. If a buggy apply_fault mutated its input (e.g. pins.include or fault.mutations), the
    # pre/post snapshot check in test_apply_fault_is_pure_and_deterministic catches it.
    pins = copy.deepcopy(s2_pathway.showcase)
    pins_before = pins.model_dump()
    pins.include.append("mutated_in_place")
    assert pins.model_dump() != pins_before


# --- in-memory mutation tests (changing a fault parameter breaks golden equality) --------------


def test_mutating_s2_keep_day_indices_in_memory_breaks_golden_equality(
    faults: tuple[FaultSpec, ...],
    pathways: dict[str, Pathway],
) -> None:
    s2_fault = _fault_by_story(faults, "S2")
    pathway = pathways[s2_fault.target_pathway]
    altered = s2_fault.model_copy(
        update={
            "mutations": [
                TruncateLineDays(
                    op="truncate_line_days",
                    section="procedures",
                    entry_id="bed",
                    keep_day_indices=[0, 1, 2],
                )
            ]
        }
    )
    assert apply_fault(altered, pathway) != _golden(_GOLDEN_FAULTY, "S2")


def test_mutating_s8_billed_ratio_in_memory_breaks_golden_equality(
    faults: tuple[FaultSpec, ...],
    pathways: dict[str, Pathway],
) -> None:
    s8_fault = _fault_by_story(faults, "S8")
    pathway = pathways[s8_fault.target_pathway]
    altered = s8_fault.model_copy(
        update={
            "mutations": [
                SetBilledRatio(
                    op="set_billed_ratio",
                    entry_id="hernia_package",
                    billed_ratio="0.5000",
                )
            ]
        }
    )
    assert apply_fault(altered, pathway) != _golden(_GOLDEN_FAULTY, "S8")


# --- error cases (precondition failures & no-op mutations) -------------------------------------


def test_error_target_pathway_mismatch(
    faults: tuple[FaultSpec, ...],
    pathways: dict[str, Pathway],
) -> None:
    s2_fault = _fault_by_story(faults, "S2")
    wrong_pathway = pathways["appendicitis_lap_appendectomy_package"]
    with pytest.raises(FaultApplyError, match="F_S2_BED_DAYS_UNDERBILLED.*target_pathway"):
        apply_fault(s2_fault, wrong_pathway)


def test_error_use_sibling_pathway_missing_or_identical_sibling(
    faults: tuple[FaultSpec, ...],
    pathways: dict[str, Pathway],
) -> None:
    s1_fault = _fault_by_story(faults, "S1")
    pathway = pathways[s1_fault.target_pathway]

    with pytest.raises(FaultApplyError, match="F_S1_PACKAGE_BILLED_ITEMIZED.*use_sibling_pathway"):
        apply_fault(s1_fault, pathway, siblings={})

    # If the sibling maps to an identical pathway, the op changes nothing and must fail.
    with pytest.raises(FaultApplyError, match="F_S1_PACKAGE_BILLED_ITEMIZED.*use_sibling_pathway"):
        apply_fault(
            s1_fault,
            pathway,
            siblings={"appendicitis_lap_appendectomy_itemized": pathway},
        )


def test_error_truncate_line_days_unknown_entry_missing_index_and_all_kept(
    faults: tuple[FaultSpec, ...],
    pathways: dict[str, Pathway],
) -> None:
    s2_fault = _fault_by_story(faults, "S2")
    pathway = pathways[s2_fault.target_pathway]

    unknown_entry = s2_fault.model_copy(
        update={
            "mutations": [
                TruncateLineDays(
                    op="truncate_line_days",
                    section="procedures",
                    entry_id="no_such_entry",
                    keep_day_indices=[0],
                )
            ]
        }
    )
    with pytest.raises(
        FaultApplyError, match="F_S2_BED_DAYS_UNDERBILLED.*truncate_line_days.*no_such_entry"
    ):
        apply_fault(unknown_entry, pathway)

    missing_index = s2_fault.model_copy(
        update={
            "mutations": [
                TruncateLineDays(
                    op="truncate_line_days",
                    section="procedures",
                    entry_id="bed",
                    keep_day_indices=[0, 1, 99],
                )
            ]
        }
    )
    with pytest.raises(FaultApplyError, match="F_S2_BED_DAYS_UNDERBILLED.*truncate_line_days.*bed"):
        apply_fault(missing_index, pathway)

    all_kept = s2_fault.model_copy(
        update={
            "mutations": [
                TruncateLineDays(
                    op="truncate_line_days",
                    section="procedures",
                    entry_id="bed",
                    keep_day_indices=[0, 1, 2, 3, 4, 5, 6],
                )
            ]
        }
    )
    with pytest.raises(
        FaultApplyError, match="F_S2_BED_DAYS_UNDERBILLED.*truncate_line_days.*keeps all rows"
    ):
        apply_fault(all_kept, pathway)


def test_error_drop_entry_unknown_entry(
    faults: tuple[FaultSpec, ...],
    pathways: dict[str, Pathway],
) -> None:
    s3_fault = _fault_by_story(faults, "S3")
    pathway = pathways[s3_fault.target_pathway]
    unknown = s3_fault.model_copy(
        update={
            "mutations": [DropEntry(op="drop_entry", section="procedures", entry_id="missing_proc")]
        }
    )
    with pytest.raises(
        FaultApplyError, match="F_S3_ANAESTHESIA_LINE_MISSING.*drop_entry.*missing_proc"
    ):
        apply_fault(unknown, pathway)


def test_error_set_flag_unknown_entry_and_existing_value(
    faults: tuple[FaultSpec, ...],
    pathways: dict[str, Pathway],
) -> None:
    s5_fault = _fault_by_story(faults, "S5")
    pathway = pathways[s5_fault.target_pathway]

    unknown = s5_fault.model_copy(
        update={
            "mutations": [
                SetFlag(
                    op="set_flag",
                    section="materials",
                    entry_id="missing_mat",
                    flag="uts_registered",
                    value=False,
                )
            ]
        }
    )
    with pytest.raises(FaultApplyError, match="F_S5_IMPLANT_UTS_INCOMPLETE.*set_flag.*missing_mat"):
        apply_fault(unknown, pathway)

    same_value = s5_fault.model_copy(
        update={
            "mutations": [
                SetFlag(
                    op="set_flag",
                    section="materials",
                    entry_id="femoral_stem",
                    flag="uts_registered",
                    value=True,
                )
            ]
        }
    )
    with pytest.raises(FaultApplyError, match="F_S5_IMPLANT_UTS_INCOMPLETE.*set_flag.*already has"):
        apply_fault(same_value, pathway)


def test_error_drop_diagnosis_primary_and_absent(
    faults: tuple[FaultSpec, ...],
    pathways: dict[str, Pathway],
) -> None:
    s6_fault = _fault_by_story(faults, "S6")
    pathway = pathways[s6_fault.target_pathway]

    primary = s6_fault.model_copy(
        update={"mutations": [DropDiagnosis(op="drop_diagnosis", icd10="J69.0")]}
    )
    with pytest.raises(
        FaultApplyError, match="F_S6_DRUG_INDICATION_NOT_CODED.*drop_diagnosis.*primary"
    ):
        apply_fault(primary, pathway)

    absent = s6_fault.model_copy(
        update={"mutations": [DropDiagnosis(op="drop_diagnosis", icd10="Z99.9")]}
    )
    with pytest.raises(
        FaultApplyError, match="F_S6_DRUG_INDICATION_NOT_CODED.*drop_diagnosis.*absent"
    ):
        apply_fault(absent, pathway)


def test_error_set_billed_ratio_unknown_entry_and_existing_ratio(
    faults: tuple[FaultSpec, ...],
    pathways: dict[str, Pathway],
) -> None:
    s8_fault = _fault_by_story(faults, "S8")
    pathway = pathways[s8_fault.target_pathway]

    unknown = s8_fault.model_copy(
        update={
            "mutations": [
                SetBilledRatio(op="set_billed_ratio", entry_id="missing_pkg", billed_ratio="1.0000")
            ]
        }
    )
    with pytest.raises(
        FaultApplyError, match="F_S8_SECOND_PACKAGE_FULL_RATE.*set_billed_ratio.*missing_pkg"
    ):
        apply_fault(unknown, pathway)

    existing_ratio = s8_fault.model_copy(
        update={
            "mutations": [
                SetBilledRatio(
                    op="set_billed_ratio", entry_id="hernia_package", billed_ratio="0.2500"
                )
            ]
        }
    )
    with pytest.raises(
        FaultApplyError, match="F_S8_SECOND_PACKAGE_FULL_RATE.*set_billed_ratio.*already has"
    ):
        apply_fault(existing_ratio, pathway)
