"""Tests for `apply_fault` in scripts/synthetic/faults/."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from scripts.synthetic.faults import (
    FaultApplyError,
    FaultSpec,
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


# --- custom pins, op ordering, drop_entry across sections & windows ---------------------------


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
