"""Unit and mutation tests for `apply_fault` and `load_siblings` in scripts/synthetic/faults/."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

import scripts.synthetic.faults.mutate as mutate_mod
from scripts.synthetic.faults import (
    DropDiagnosis,
    DropEntry,
    FaultApplyError,
    FaultSpec,
    SetBilledRatio,
    SetFlag,
    SetQuantity,
    TruncateLineDays,
    apply_fault,
    fault_window,
    load_registry,
    load_siblings,
)
from scripts.synthetic.pathways import Pathway, load_all
from scripts.synthetic.pathways.expand import expand
from tests.fixtures.pathway_goldens import faulty_golden_stories

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


@pytest.mark.parametrize("story", faulty_golden_stories())  # every story with a fault, not the first eight only
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
    fault_snapshot = copy.deepcopy(fault)
    pins_snapshot = copy.deepcopy(pins)
    pathway_snapshot = copy.deepcopy(pathway)
    siblings_snapshot = copy.deepcopy(siblings_copy)
    clean_before = expand(pathway)

    first = apply_fault(fault, pathway, pins, siblings=siblings_copy)
    second = apply_fault(fault, pathway, pins, siblings=siblings_copy)

    assert first == second
    assert fault == fault_snapshot
    assert pins == pins_snapshot
    assert pathway == pathway_snapshot
    assert siblings_copy == siblings_snapshot
    assert expand(pathway) == clean_before


def test_strip_annotations_monkeypatched_to_identity_fails_golden_equality(
    monkeypatch: pytest.MonkeyPatch,
    faults: tuple[FaultSpec, ...],
    pathways: dict[str, Pathway],
    siblings: dict[str, Pathway],
) -> None:
    monkeypatch.setattr(mutate_mod, "_strip_annotations", lambda bill: bill)
    s2_fault = _fault_by_story(faults, "S2")
    s2_pathway = pathways[s2_fault.target_pathway]

    unstripped = apply_fault(s2_fault, s2_pathway, siblings=siblings)
    assert unstripped != _golden(_GOLDEN_FAULTY, "S2")
    assert not set(unstripped["procedures"][0]).isdisjoint(_ANNOTATION_KEYS["procedures"])


# --- custom pins, op ordering, drop_entry across sections & windows ---------------------------


def test_pins_override_is_honoured_by_truncate_line_days(
    faults: tuple[FaultSpec, ...],
    pathways: dict[str, Pathway],
) -> None:
    fault = _fault_by_story(faults, "S2")
    pathway = pathways[fault.target_pathway]
    pins = pathway.showcase.model_copy(update={"nights": 8})
    bill = expand(pathway, pins, annotate=True)
    bill["procedures"] = [
        r for r in bill["procedures"] if r["entry_id"] != "bed" or r["day_index"] < 4
    ]
    assert apply_fault(fault, pathway, pins) == _strip_annotations(bill)


def test_pins_override_is_honoured_by_use_sibling_pathway(
    faults: tuple[FaultSpec, ...],
    pathways: dict[str, Pathway],
    siblings: dict[str, Pathway],
) -> None:
    fault = _fault_by_story(faults, "S1")
    pathway = pathways[fault.target_pathway]
    pins = pathway.showcase.model_copy(update={"admit": "2026-06-01"})
    sibling = siblings["appendicitis_lap_appendectomy_itemized"]
    assert apply_fault(fault, pathway, pins, siblings=siblings) == expand(sibling, pins)


def test_mutations_execute_in_declared_order(
    faults: tuple[FaultSpec, ...],
    pathways: dict[str, Pathway],
) -> None:
    fault = _fault_by_story(faults, "S2")
    pathway = pathways[fault.target_pathway]
    drop_then_truncate = fault.model_copy(
        update={
            "mutations": [
                DropEntry(op="drop_entry", section="procedures", entry_id="bed"),
                TruncateLineDays(
                    op="truncate_line_days",
                    section="procedures",
                    entry_id="bed",
                    keep_day_indices=[0, 1, 2, 3],
                ),
            ]
        }
    )
    with pytest.raises(FaultApplyError, match="truncate_line_days.*bed"):
        apply_fault(drop_then_truncate, pathway)


@pytest.mark.parametrize(
    ("story", "section", "entry", "key", "gone"),
    [
        ("S5", "materials", "femoral_stem", "code", "AP2000"),
        ("S6", "drugs", "pk_merz", "barcode", "8699708690525"),
        ("S7", "performed", "ct_angiography_pacs", "code", "R101450"),
    ],
)
def test_drop_entry_removes_target_in_every_section(
    story: str,
    section: str,
    entry: str,
    key: str,
    gone: str,
    faults: tuple[FaultSpec, ...],
    pathways: dict[str, Pathway],
) -> None:
    fault = _fault_by_story(faults, story)
    pathway = pathways[fault.target_pathway]
    altered = fault.model_copy(
        update={"mutations": [DropEntry(op="drop_entry", section=section, entry_id=entry)]}
    )
    bill = apply_fault(altered, pathway)
    assert gone not in {r[key] for r in bill[section]}
    assert gone in {r[key] for r in expand(pathway)[section]}


def test_fault_window_and_stay_bounds_enforcement(
    faults: tuple[FaultSpec, ...],
    pathways: dict[str, Pathway],
    siblings: dict[str, Pathway],
) -> None:
    s1_fault = _fault_by_story(faults, "S1")
    s1_pathway = pathways[s1_fault.target_pathway]
    s2_fault = _fault_by_story(faults, "S2")
    s2_pathway = pathways[s2_fault.target_pathway]

    assert fault_window(s1_fault, s1_pathway, siblings=siblings) == ("2026-04-16", "2026-09-30")
    assert s2_pathway.window is not None
    assert fault_window(s2_fault, s2_pathway) == (s2_pathway.window.start, s2_pathway.window.end)

    # S1: 2026-03-02 is before the sibling window start (2026-04-16) and must raise.
    with pytest.raises(FaultApplyError, match="outside the window"):
        apply_fault(
            s1_fault,
            s1_pathway,
            s1_pathway.showcase.model_copy(update={"admit": "2026-03-02"}),
            siblings=siblings,
        )

    # S1: first valid admit day (2026-04-16) works.
    first_ok = apply_fault(
        s1_fault,
        s1_pathway,
        s1_pathway.showcase.model_copy(update={"admit": "2026-04-16"}),
        siblings=siblings,
    )
    assert first_ok["header"]["admission_date"] == "2026-04-16"

    # S1: showcase nights=2, window ends 2026-09-30 -> last valid admit is 2026-09-28; 2026-09-29 raises.
    last_ok = apply_fault(
        s1_fault,
        s1_pathway,
        s1_pathway.showcase.model_copy(update={"admit": "2026-09-28"}),
        siblings=siblings,
    )
    assert last_ok["header"]["discharge_date"] == "2026-09-30"
    with pytest.raises(FaultApplyError, match="outside the window"):
        apply_fault(
            s1_fault,
            s1_pathway,
            s1_pathway.showcase.model_copy(update={"admit": "2026-09-29"}),
            siblings=siblings,
        )

    # S2: showcase nights=6, window ends 2026-08-28 -> last valid admit is 2026-08-22; 2026-08-23 raises.
    s2_last_ok = apply_fault(
        s2_fault,
        s2_pathway,
        s2_pathway.showcase.model_copy(update={"admit": "2026-08-22"}),
    )
    assert s2_last_ok["header"]["discharge_date"] == "2026-08-28"
    with pytest.raises(FaultApplyError, match="outside the window"):
        apply_fault(
            s2_fault,
            s2_pathway,
            s2_pathway.showcase.model_copy(update={"admit": "2026-08-23"}),
        )


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


def test_error_drop_entry_dangling_material_link_on_s5(
    faults: tuple[FaultSpec, ...],
    pathways: dict[str, Pathway],
) -> None:
    s5_fault = _fault_by_story(faults, "S5")
    pathway = pathways[s5_fault.target_pathway]
    dangling = s5_fault.model_copy(
        update={
            "mutations": [
                DropEntry(
                    op="drop_entry",
                    section="procedures",
                    entry_id="hemiarthroplasty_package",
                )
            ]
        }
    )
    with pytest.raises(FaultApplyError, match="dangling link"):
        apply_fault(dangling, pathway)


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


def test_the_window_of_a_fault_on_a_session_claim_is_checked_to_the_end_of_its_span(
    faults: tuple[FaultSpec, ...], pathways: dict[str, Pathway]
) -> None:
    """G3: a session claim ends on admit+span; a fault on it may not move that last day past the window."""
    import yaml

    from scripts.synthetic.pathways import load_text

    control = "pyelonephritis_dementia_post_discharge_control"  # S39, a poliklinik visit, given a span of 3 here
    raw = yaml.safe_load((Path(__file__).resolve().parents[3] / f"data/synthetic/pathways/{control}.yaml").read_text(encoding="utf-8"))
    raw["span"] = {"min": 1, "max": 5, "basis": "judgment", "source": "Test fixture only: a session claim over days."}
    raw["showcase"]["span"] = 3
    pathway = load_text(yaml.safe_dump(raw, allow_unicode=True, sort_keys=False), f"{control}.yaml")
    dropping = _fault_by_story(faults, "S22")  # a drop_entry fault, pointed at the culture of the control
    fault = dropping.model_copy(
        update={
            "target_pathway": control,
            "mutations": [dropping.mutations[0].model_copy(update={"entry_id": "urine_culture"})],
        }
    )
    fits = apply_fault(fault, pathway, pathway.showcase.model_copy(update={"admit": "2026-09-27"}))
    assert fits["header"]["claim_end_date"] == "2026-09-30"  # admit + 3, the last day of the window
    with pytest.raises(FaultApplyError, match="outside the window"):
        apply_fault(fault, pathway, pathway.showcase.model_copy(update={"admit": "2026-09-28"}))


# --- slice G6: a drug count no pathway can hold; slice G5a: a flag on a procedure line ------------------


def test_set_quantity_sets_the_count_of_the_drug_line_and_nothing_else(
    faults: tuple[FaultSpec, ...], pathways: dict[str, Pathway]
) -> None:
    """S33: the strength of the enoxaparin syringe (4000 anti-Xa IU) keyed as its count."""
    fault = _fault_by_story(faults, "S33")
    (op,) = fault.mutations
    assert isinstance(op, SetQuantity) and (op.section, op.entry_id, op.qty) == ("drugs", "enoxaparin", 4000)
    pathway = pathways[fault.target_pathway]
    clean, faulty = expand(pathway), apply_fault(fault, pathway)
    assert [d["qty"] for d in clean["drugs"]] == [4]  # one syringe a day for the four days of the stay
    assert [d["qty"] for d in faulty["drugs"]] == [4000]
    assert {**faulty, "drugs": clean["drugs"]} == clean  # every other row and the header are the clean bill's
    assert [{k: v for k, v in d.items() if k != "qty"} for d in faulty["drugs"]] == [
        {k: v for k, v in d.items() if k != "qty"} for d in clean["drugs"]
    ]


def test_error_set_quantity_unknown_entry_and_a_count_set_twice(
    faults: tuple[FaultSpec, ...], pathways: dict[str, Pathway]
) -> None:
    fault = _fault_by_story(faults, "S33")
    pathway = pathways[fault.target_pathway]
    unknown = fault.model_copy(
        update={"mutations": [SetQuantity(op="set_quantity", section="drugs", entry_id="heparin", qty=4000)]}
    )
    with pytest.raises(FaultApplyError, match="F_S33_ENOXAPARIN_STRENGTH_KEYED_AS_QUANTITY.*set_quantity.*heparin"):
        apply_fault(unknown, pathway)
    twice = fault.model_copy(update={"mutations": [fault.mutations[0], fault.mutations[0]]})
    with pytest.raises(FaultApplyError, match="set_quantity.*already has qty=4000"):
        apply_fault(twice, pathway)


@pytest.mark.parametrize("qty", [999, 1, 100_000, True, 4000.0])
def test_a_set_quantity_count_inside_the_pathway_bound_or_not_a_whole_number_is_refused(qty: object) -> None:
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        SetQuantity(op="set_quantity", section="drugs", entry_id="enoxaparin", qty=qty)


def test_set_flag_on_a_procedure_line_flags_that_line_only(
    faults: tuple[FaultSpec, ...], pathways: dict[str, Pathway]
) -> None:
    """S34: the control's examination flagged as a component of a package (vakabaşı); no other field moves."""
    fault = _fault_by_story(faults, "S34")
    (op,) = fault.mutations
    assert isinstance(op, SetFlag) and (op.section, op.entry_id, op.flag, op.value) == (
        "procedures",
        "exam",
        "is_package_included",
        True,
    )
    pathway = pathways[fault.target_pathway]
    clean, faulty = expand(pathway), apply_fault(fault, pathway)
    assert [p["flags"] for p in clean["procedures"]] == [{}]
    assert [p["flags"] for p in faulty["procedures"]] == [{"is_package_included": True}]
    assert [{**p, "flags": {}} for p in faulty["procedures"]] == clean["procedures"]
    again = fault.model_copy(update={"mutations": [op, op]})
    with pytest.raises(FaultApplyError, match="set_flag.*already has is_package_included=True"):
        apply_fault(again, pathway)
