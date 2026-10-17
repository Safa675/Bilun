"""Tests for fault-sibling pathways in data/synthetic/faults/siblings/."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from scripts.synthetic.pathways import load_pathway, load_text
from scripts.synthetic.pathways.checks import Catalogs, run_all
from scripts.synthetic.pathways.expand import expand

pytestmark = pytest.mark.unit

_REPO = Path(__file__).resolve().parents[3]
_SIBLINGS_DIR = _REPO / "data/synthetic/faults/siblings"
_GOLDEN_FAULTY = _REPO / "tests/fixtures/pathways/golden_faulty"
_FILES = sorted(_SIBLINGS_DIR.glob("*.yaml"))
S1_SIBLING = "appendicitis_lap_appendectomy_itemized"


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


def test_siblings_folder_has_s1_itemized_sibling_and_only_yaml_files() -> None:
    assert {p.stem for p in _FILES} >= {S1_SIBLING}
    strays = [p.name for p in _SIBLINGS_DIR.iterdir() if not (p.is_file() and p.suffix == ".yaml")]
    assert strays == []


@pytest.mark.parametrize("path", _FILES, ids=lambda p: p.stem)
def test_sibling_pathway_loads(path: Path) -> None:
    assert load_pathway(path).id == path.stem


@pytest.mark.parametrize("path", _FILES, ids=lambda p: p.stem)
def test_sibling_pathway_passes_every_check(path: Path, catalogs: Catalogs) -> None:
    assert run_all(load_pathway(path), catalogs) == []


@pytest.mark.parametrize("path", _FILES, ids=lambda p: p.stem)
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
