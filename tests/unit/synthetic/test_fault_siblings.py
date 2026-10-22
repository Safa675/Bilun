"""Tests for fault-sibling pathways in data/synthetic/faults/siblings/."""

from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

import pytest
import yaml

from scripts.synthetic.pathways import load_pathway, load_text
from scripts.synthetic.pathways.checks import Catalogs, run_all
from scripts.synthetic.pathways.expand import expand
from tests.fixtures.pathway_goldens import golden_stories

pytestmark = pytest.mark.unit

_REPO = Path(__file__).resolve().parents[3]
_SIBLINGS_DIR = _REPO / "data/synthetic/faults/siblings"
_PATHWAYS_DIR = _REPO / "data/synthetic/pathways"
_GOLDEN_FAULTY = _REPO / "tests/fixtures/pathways/golden_faulty"
_FILES = sorted(_SIBLINGS_DIR.glob("*.yaml"))


def _has_faulty_golden(path: Path) -> bool:
    """A sibling of a story that stories.py builds is compared with the faulty golden; any other is not."""
    return yaml.safe_load(path.read_text(encoding="utf-8"))["showcase"]["story"] in golden_stories()


_GOLDEN_SIBLINGS = [p for p in _FILES if _has_faulty_golden(p)]
S1_SIBLING = "appendicitis_lap_appendectomy_itemized"
S10_SIBLING = "gi_bleed_melena_er_visit_manual_hct_billed"
S14_SIBLING = "urosepsis_ward_stay_transfer_day_billed"
S40_SIBLING = "pyelonephritis_dementia_second_visit_exam_billed"
S20_SIBLING = "umbilical_hernia_day_case_itemized"
S46_SIBLING = "parkinson_physiatry_visit_second_walker_billed"


@pytest.fixture(scope="module")
def catalogs() -> Catalogs:
    return Catalogs()


def _faulty_golden(story: str) -> dict:
    return json.loads((_GOLDEN_FAULTY / f"{story}.json").read_text(encoding="utf-8"))


def _mutated_s1_sibling(edit) -> object:
    raw = yaml.safe_load((_SIBLINGS_DIR / f"{S1_SIBLING}.yaml").read_text(encoding="utf-8"))
    edit(raw)
    body = yaml.safe_dump(raw, allow_unicode=True, sort_keys=False)
    return load_text(body, f"{S1_SIBLING}.yaml")


def test_siblings_folder_has_the_s1_and_s14_siblings_and_only_yaml_files() -> None:
    assert {p.stem for p in _FILES} >= {S1_SIBLING, S14_SIBLING}
    strays = [p.name for p in _SIBLINGS_DIR.iterdir() if not (p.is_file() and p.suffix == ".yaml")]
    assert strays == []


@pytest.mark.parametrize("path", _FILES, ids=lambda p: p.stem)
def test_sibling_pathway_loads(path: Path) -> None:
    assert load_pathway(path).id == path.stem


@pytest.mark.parametrize("path", _FILES, ids=lambda p: p.stem)
def test_sibling_pathway_passes_every_check(path: Path, catalogs: Catalogs) -> None:
    assert run_all(load_pathway(path), catalogs) == []


@pytest.mark.parametrize("path", _GOLDEN_SIBLINGS, ids=lambda p: p.stem)
def test_sibling_expansion_equals_faulty_golden(path: Path) -> None:
    pathway = load_pathway(path)
    assert expand(pathway) == _faulty_golden(pathway.showcase.story)


def test_changing_a_drug_quantity_in_memory_makes_faulty_golden_equality_fail() -> None:
    def edit(raw: dict) -> None:
        next(d for d in raw["drugs"] if d["id"] == "paracetamol")["qty"] = 4

    pathway = _mutated_s1_sibling(edit)
    assert expand(pathway) != _faulty_golden(pathway.showcase.story)


def test_deleting_a_bed_day_in_memory_makes_faulty_golden_equality_fail() -> None:
    def edit(raw: dict) -> None:
        next(p for p in raw["procedures"] if p["id"] == "bed")["days"] = "admit..discharge-1"

    pathway = _mutated_s1_sibling(edit)
    assert expand(pathway) != _faulty_golden(pathway.showcase.story)


def test_the_sibling_of_s1_is_compared_with_a_faulty_golden_and_a_later_story_would_not_be(
    tmp_path: Path,
) -> None:
    assert [p.stem for p in _GOLDEN_SIBLINGS] == [S1_SIBLING, S10_SIBLING, S46_SIBLING, S40_SIBLING, S20_SIBLING, S14_SIBLING]
    raw = yaml.safe_load((_SIBLINGS_DIR / f"{S1_SIBLING}.yaml").read_text(encoding="utf-8"))
    raw["showcase"]["story"] = "S99"
    later = tmp_path / "later.yaml"
    later.write_text(yaml.safe_dump(raw, allow_unicode=True, sort_keys=False), encoding="utf-8")
    assert _has_faulty_golden(later) is False


# --- S46: the physiatry visit. The sibling is the target pathway with a second walker inside the MIAT of the first ---


def test_the_s46_sibling_bills_a_second_walker_and_nothing_else_differs() -> None:
    """The twin differs by a line, not by a date (a sibling is expanded with the same pins): the walker of slice G7b."""
    target = load_pathway(_PATHWAYS_DIR / "parkinson_physiatry_visit.yaml")
    sibling = load_pathway(_SIBLINGS_DIR / f"{S46_SIBLING}.yaml")
    first = load_pathway(_PATHWAYS_DIR / "parkinson_neurology_control_first_walker.yaml")
    clean, faulty = expand(target), expand(sibling)
    for part in ("header", "diagnoses", "procedures", "drugs", "performed"):
        assert clean[part] == faulty[part], part
    assert clean["materials"] == []
    (walker,) = faulty["materials"]
    (first_walker,) = expand(first)["materials"]
    # the same EK-3/C-2 device as the control of S45, on the examination of this visit, 42 days later
    assert {k: v for k, v in walker.items() if k not in ("date", "linked_procedure")} == {
        k: v for k, v in first_walker.items() if k not in ("date", "linked_procedure")
    }
    assert (walker["code"], walker["annex"], walker["date"], first_walker["date"]) == ("OP1106", "EK-3C-2", "2026-08-10", "2026-06-29")
    assert walker["linked_procedure"] == {"code": "520030", "date": "2026-08-10"}
    assert (date(2026, 8, 10) - date(2026, 6, 29)).days == 42
    assert target.showcase == sibling.showcase and (target.showcase.sex, target.showcase.age) == (first.showcase.sex, first.showcase.age)


# --- S14: the ward bill after the ICU bill. The sibling is the target pathway with the transfer day billed ---


def _s14_pair():
    target = load_pathway(_PATHWAYS_DIR / "urosepsis_ward_stay_after_icu_transfer.yaml")
    sibling = load_pathway(_SIBLINGS_DIR / f"{S14_SIBLING}.yaml")
    return target, sibling


def test_the_s14_sibling_bills_the_transfer_day_bed_and_nothing_else_differs() -> None:
    target, sibling = _s14_pair()
    assert (target.arrives_from_icu, sibling.arrives_from_icu) == (True, False)
    clean, faulty = expand(target), expand(sibling)
    for part in ("header", "diagnoses", "materials", "drugs", "performed"):
        assert clean[part] == faulty[part], part
    assert [p for p in clean["procedures"] if p not in faulty["procedures"]] == []
    extra = [p for p in faulty["procedures"] if p not in clean["procedures"]]
    assert [(p["code"], p["date"]) for p in extra] == [("510010", "2026-06-07")]  # the day the ICU bill ends
    assert len(clean["procedures"]) == 6 and len(faulty["procedures"]) == 7


def test_the_s14_pathways_pin_the_patient_of_s11_and_start_on_the_day_its_bill_ends() -> None:
    icu = load_pathway(_PATHWAYS_DIR / "urosepsis_septic_shock_icu_stay.yaml")
    target, sibling = _s14_pair()
    exit_day = date.fromisoformat(icu.showcase.admit) + timedelta(days=icu.showcase.nights)
    for ward in (target, sibling):
        assert ward.showcase.admit == exit_day.isoformat() == "2026-06-07"
        assert (ward.showcase.sex, ward.showcase.age) == (icu.showcase.sex, icu.showcase.age) == ("F", 76)
        assert ward.showcase.story == "S14" and icu.showcase.story == "S11"
        assert ward.patient.sex.values == icu.patient.sex.values
        assert (ward.patient.age.min, ward.patient.age.max) == (icu.patient.age.min, icu.patient.age.max) == (60, 90)
    # the ward bill's diagnoses are already on the ICU bill, so the patient's union list does not grow
    icu_codes = {d.icd10 for d in icu.diagnoses}
    assert {d.icd10 for d in target.diagnoses} <= icu_codes == {"A41.9", "R57.8", "N39.0"}


def test_the_s14_target_has_no_lab_line_because_the_cross_bill_rules_read_the_whole_history() -> None:
    """The ICU bill bills every test of the episode on 06-02: the same test on another bill within seven days is a duplicate."""
    target, sibling = _s14_pair()
    for pathway in (target, sibling):
        assert {line.kind for line in pathway.procedures} == {"bed", "companion"}
        assert not (pathway.materials or pathway.drugs or pathway.performed)


# --- S10: the ER visit of patient 12. The sibling is the target pathway with the manual haematocrit billed ---


def _s10_pair():
    target = load_pathway(_PATHWAYS_DIR / "gi_bleed_melena_er_visit.yaml")
    sibling = load_pathway(_SIBLINGS_DIR / f"{S10_SIBLING}.yaml")
    return target, sibling


def test_the_s10_sibling_bills_the_manual_haematocrit_beside_the_hemogram_and_nothing_else_differs() -> None:
    target, sibling = _s10_pair()
    clean, faulty = expand(target), expand(sibling)
    for part in ("header", "diagnoses", "materials", "drugs", "performed"):
        assert clean[part] == faulty[part], part
    assert [p for p in clean["procedures"] if p not in faulty["procedures"]] == []
    extra = [p for p in faulty["procedures"] if p not in clean["procedures"]]
    assert [(p["code"], p["date"], p["qty"], p["billed_ratio"]) for p in extra] == [
        ("L103120", "2026-05-09", 1, "1.0000")
    ]  # the one line the fault adds, on the day of the visit
    assert {p["code"] for p in clean["procedures"]} == {"520020", "L107020"}  # one hemogram is the correct bill
    assert len(clean["procedures"]) == 2 and len(faulty["procedures"]) == 3


def test_the_s10_pathways_are_one_acil_visit_and_pin_the_same_man_as_the_admission_after_it() -> None:
    target, sibling = _s10_pair()
    admission = load_pathway(_PATHWAYS_DIR / "gi_bleed_admission_colonoscopy.yaml")
    for visit in (target, sibling):
        assert visit.claim_type == "acil" and visit.nights is None  # a visit: one date, no stay
        assert visit.showcase.story == "S10" and visit.showcase.admit == "2026-05-09"
        assert (visit.showcase.sex, visit.showcase.age) == (admission.showcase.sex, admission.showcase.age) == ("M", 58)
        assert visit.patient.sex.values == admission.patient.sex.values
        assert (visit.patient.age.min, visit.patient.age.max) == (admission.patient.age.min, admission.patient.age.max)
    assert admission.showcase.story == "S22" and admission.showcase.admit == "2026-05-11"  # two days later
