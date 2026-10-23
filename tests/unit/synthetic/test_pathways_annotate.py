"""Tests for `expand(pathway, pins=None, *, annotate=False)` in scripts/synthetic/pathways/expand.py."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.synthetic.pathways import load_pathway
from scripts.synthetic.pathways.expand import expand
from scripts.synthetic.pathways.schema import included

pytestmark = pytest.mark.unit

_REPO = Path(__file__).resolve().parents[3]
_DIR = _REPO / "data/synthetic/pathways"
_GOLDEN = _REPO / "tests/fixtures/pathways/golden"
_FILES = sorted(_DIR.glob("*.yaml"))

_ADDED_KEYS = {
    "procedures": {"entry_id", "kind", "day_index"},
    "materials": {"entry_id"},
    "drugs": {"entry_id", "indication"},
    "performed": {"entry_id"},
}


def _golden(story: str) -> dict:
    return json.loads((_GOLDEN / f"{story}.json").read_text(encoding="utf-8"))


def _strip_annotations(bill: dict) -> dict:
    stripped = dict(bill)
    for section, extra in _ADDED_KEYS.items():
        stripped[section] = [
            {k: v for k, v in row.items() if k not in extra} for row in bill[section]
        ]
    return stripped


@pytest.mark.parametrize("path", _FILES, ids=lambda p: p.stem)
def test_default_and_annotate_false_equal_clean_golden(path: Path) -> None:
    pathway = load_pathway(path)
    default = expand(pathway)
    explicit_false = expand(pathway, annotate=False)
    assert default == explicit_false == _golden(pathway.showcase.story)


@pytest.mark.parametrize("path", _FILES, ids=lambda p: p.stem)
def test_stripping_annotations_gives_the_default_expansion_exactly(path: Path) -> None:
    pathway = load_pathway(path)
    default = expand(pathway)
    annotated = expand(pathway, annotate=True)
    assert json.loads(json.dumps(annotated)) == annotated
    for section, extra in _ADDED_KEYS.items():
        for row in annotated[section]:
            assert extra <= set(row), f"{section} row missing annotation keys: {row}"
    assert _strip_annotations(annotated) == default


@pytest.mark.parametrize("path", _FILES, ids=lambda p: p.stem)
def test_every_entry_id_is_an_included_line_and_day_indices_are_ordered(path: Path) -> None:
    pathway = load_pathway(path)
    pins = pathway.showcase
    annotated = expand(pathway, annotate=True)

    for section in _ADDED_KEYS:
        lines = getattr(pathway, section)
        all_ids = {line.id for line in lines}
        included_ids = {line.id for line in lines if included(line, pins)}
        seen_ids = {row["entry_id"] for row in annotated[section]}
        assert seen_ids <= all_ids, section
        assert seen_ids == included_ids, section

    kinds = {line.id: line.kind for line in pathway.procedures}
    by_entry: dict[str, list[dict]] = {}
    for row in annotated["procedures"]:
        assert row["kind"] == kinds[row["entry_id"]]
        by_entry.setdefault(row["entry_id"], []).append(row)

    for entry_id, rows in by_entry.items():
        # Rows are already sorted by date; for a multi-code lab panel, every code on the same date
        # shares the same day_index and distinct (date, day_index) pairs are 0..n-1 in date order.
        dates = [r["date"] for r in rows]
        assert dates == sorted(dates), entry_id
        pairs = list(dict.fromkeys((r["date"], r["day_index"]) for r in rows))
        assert [d for d, _ in pairs] == sorted({r["date"] for r in rows}), entry_id
        assert [idx for _, idx in pairs] == list(range(len(pairs))), entry_id


def test_s2_bed_day_indices_and_lab_panel_day_indices() -> None:
    s2 = load_pathway(_DIR / "copd_exacerbation_pneumonia_ward.yaml")
    annotated = expand(s2, annotate=True)
    bed_rows = [r for r in annotated["procedures"] if r["entry_id"] == "bed"]
    assert [r["day_index"] for r in bed_rows] == list(range(7))
    assert [r["date"] for r in bed_rows] == sorted(r["date"] for r in bed_rows)

    panel_rows = [r for r in annotated["procedures"] if r["entry_id"] == "cbc_crp"]
    assert [(r["date"], r["code"], r["day_index"]) for r in panel_rows] == [
        ("2026-03-09", "L101850", 0),
        ("2026-03-09", "L107020", 0),
        ("2026-03-12", "L101850", 1),
        ("2026-03-12", "L107020", 1),
    ]


def test_drug_rows_carry_indication_s6_pk_merz_is_g20_s17_darbepoetin_is_n18_s18_albumin_is_k74_s44_romosozumab_is_m81_others_null() -> None:
    indications: list[tuple[str, str, str | None]] = []
    for path in _FILES:
        pathway = load_pathway(path)
        annotated = expand(pathway, annotate=True)
        for row in annotated["drugs"]:
            assert "indication" in row
            indications.append((pathway.showcase.story, row["entry_id"], row["indication"]))

    named = [item for item in indications if item[2] is not None]
    others = [item for item in indications if item[2] is None]
    assert sorted(named) == [
        ("S17", "darbepoetin", "N18.0"),
        ("S18", "albumin", "K74.6"),
        ("S44", "romosozumab", "M81.09"),
        ("S6", "pk_merz", "G20"),
    ]
    assert others and all(ind is None for _, _, ind in others)
