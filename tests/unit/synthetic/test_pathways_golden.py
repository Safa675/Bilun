"""The golden clean and faulty bills, tests/fixtures/pathways/{golden,golden_faulty}/S1..S8.json.

Well-formedness is checked on the files alone: no harness, no engine. That the files equal a fresh
export of stories.py is `export_clean_lines.py --check`, run here in a subprocess (the harness
changes the working directory and loads the engine, so it never runs in the test process); that a
pathway reproduces its bill is the pathway round-trip test.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from collections.abc import Iterator
from datetime import date
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

REPO = Path(__file__).resolve().parents[3]
GOLDEN_DIR = REPO / "tests" / "fixtures" / "pathways" / "golden"
GOLDEN_FAULTY_DIR = REPO / "tests" / "fixtures" / "pathways" / "golden_faulty"
GOLDEN_DIRS = {"clean": GOLDEN_DIR, "faulty": GOLDEN_FAULTY_DIR}
EXPORTER = (
    REPO / "reports" / "synthetic-data" / "2026-10-15-showcase-proofs" / "export_clean_lines.py"
)
STORIES = [f"S{n}" for n in range(1, 9)]

TOP_KEYS = {
    "story",
    "format_version",
    "header",
    "diagnoses",
    "procedures",
    "materials",
    "drugs",
    "performed",
}
HEADER_KEYS = {
    "claim_type",
    "department",
    "admission_date",
    "discharge_date",
    "claim_start_date",
    "claim_end_date",
    "primary_icd10",
}
LINE_KEYS = {
    "diagnoses": {"icd10", "role", "date"},
    "procedures": {"code", "date", "qty", "specialty", "billed_ratio", "flags"},
    "materials": {
        "code",
        "date",
        "qty",
        "material_type",
        "linked_procedure",
        "billed_ratio",
        "flags",
    },
    "drugs": {"barcode", "date", "qty", "unit", "per_box", "flags"},
    "performed": {"code", "date", "source"},
}
# The order the format fixes for each list.
SORT_KEYS = {
    "diagnoses": lambda r: (r["role"] != "primary", r["icd10"]),
    "procedures": lambda r: (r["date"], r["code"], r["qty"], r["specialty"]),
    "materials": lambda r: (r["date"], r["code"], r["qty"]),
    "drugs": lambda r: (r["date"], r["barcode"], r["qty"]),
    "performed": lambda r: (r["date"], r["code"], r["source"]),
}


def _is_iso(value: object) -> bool:
    try:
        return isinstance(value, str) and date.fromisoformat(value).isoformat() == value
    except ValueError:
        return False


def _is_positive_int(value: object) -> bool:
    return type(value) is int and value > 0


def _keys(node: object) -> Iterator[str]:
    """Every dict key anywhere in a JSON document."""
    if isinstance(node, dict):
        for key, value in node.items():
            yield key
            yield from _keys(value)
    elif isinstance(node, list):
        for item in node:
            yield from _keys(item)


@pytest.fixture(
    params=[(variant, sid) for variant in GOLDEN_DIRS for sid in STORIES],
    ids=lambda item: f"{item[0]}-{item[1]}",
)
def golden(request: pytest.FixtureRequest) -> tuple[str, str, dict]:
    """(story, file text, parsed document); a missing or invalid file errors here."""
    variant, sid = request.param
    path = GOLDEN_DIRS[variant] / f"{sid}.json"
    text = path.read_text(encoding="utf-8")
    return sid, text, json.loads(text)


@pytest.mark.parametrize("directory", GOLDEN_DIRS.values(), ids=GOLDEN_DIRS.keys())
def test_eight_golden_files_exist(directory: Path) -> None:
    assert [s for s in STORIES if not (directory / f"{s}.json").is_file()] == []


@pytest.mark.parametrize("story", STORIES)
def test_each_faulty_golden_differs_from_its_clean_golden_and_names_its_story(story: str) -> None:
    clean_path = GOLDEN_DIR / f"{story}.json"
    faulty_path = GOLDEN_FAULTY_DIR / f"{story}.json"
    clean = json.loads(clean_path.read_text(encoding="utf-8"))
    faulty = json.loads(faulty_path.read_text(encoding="utf-8"))
    assert faulty["story"] == faulty_path.stem == story
    assert faulty != clean


def test_the_golden_files_equal_a_fresh_export_of_the_stories() -> None:
    """A pathway and its golden cannot be changed together: the golden is exported from stories.py."""
    run = subprocess.run(
        [sys.executable, str(EXPORTER), "--check"],
        cwd=REPO,
        capture_output=True,
        encoding="utf-8",
        timeout=300,
        check=False,
    )
    assert run.returncode == 0, (
        f"export_clean_lines.py --check exited {run.returncode}:\n{run.stdout}{run.stderr}"
    )


def test_json_is_in_the_canonical_form(golden) -> None:
    _, text, doc = golden
    assert text == json.dumps(doc, sort_keys=True, indent=2, ensure_ascii=False) + "\n"


def test_file_ends_with_one_newline(golden) -> None:
    text = golden[1]
    assert text.endswith("\n") and not text.endswith("\n\n")


def test_layout_and_format_version(golden) -> None:
    story, _, doc = golden
    assert set(doc) == TOP_KEYS
    assert doc["story"] == story
    assert type(doc["format_version"]) is int and doc["format_version"] == 1
    assert set(doc["header"]) == HEADER_KEYS
    for name, keys in LINE_KEYS.items():
        assert [row for row in doc[name] if set(row) != keys] == [], name
    for name in ("procedures", "materials", "drugs"):
        assert all(isinstance(row["flags"], dict) for row in doc[name]), name


def test_lists_are_sorted_as_the_format_says(golden) -> None:
    _, _, doc = golden
    for name, key in SORT_KEYS.items():
        assert doc[name] == sorted(doc[name], key=key), name


def test_one_primary_diagnosis_and_it_is_the_header_one(golden) -> None:
    _, _, doc = golden
    primaries = [d["icd10"] for d in doc["diagnoses"] if d["role"] == "primary"]
    assert primaries == [doc["header"]["primary_icd10"]]


def test_no_price_amount_or_total_keys(golden) -> None:
    # billed_ratio is the only money-derived key the format allows.
    _, _, doc = golden
    bad = {k for k in _keys(doc) if re.search("price|amount|total", k.lower())}
    assert sorted(bad) == []


def test_no_anon_text(golden) -> None:
    assert "ANON" not in golden[1]


def test_dates_are_iso(golden) -> None:
    _, _, doc = golden
    header = doc["header"]
    assert header["claim_type"] in {"yatis", "acil"}
    # Null admission and discharge only for the ER-only (acil) story.
    nullable = {"admission_date", "discharge_date"} if header["claim_type"] == "acil" else set()
    for key in ("admission_date", "discharge_date", "claim_start_date", "claim_end_date"):
        assert _is_iso(header[key]) or (header[key] is None and key in nullable), key
    for name in LINE_KEYS:
        assert [r["date"] for r in doc[name] if not _is_iso(r["date"])] == [], name
    links = [m["linked_procedure"] for m in doc["materials"] if m["linked_procedure"]]
    assert [link["date"] for link in links if not _is_iso(link["date"])] == []


def test_quantities_are_positive_ints(golden) -> None:
    _, _, doc = golden
    for name in ("procedures", "materials", "drugs"):
        assert [r["qty"] for r in doc[name] if not _is_positive_int(r["qty"])] == [], name
    assert [d["per_box"] for d in doc["drugs"] if not _is_positive_int(d["per_box"])] == []


def test_linked_procedures_point_into_the_same_file(golden) -> None:
    _, _, doc = golden
    procedures = {(p["code"], p["date"]) for p in doc["procedures"]}
    for material in doc["materials"]:
        link = material["linked_procedure"]
        if link is not None:
            assert set(link) == {"code", "date"}, material["code"]
            assert (link["code"], link["date"]) in procedures, material["code"]


def test_billed_ratio_has_four_decimals(golden) -> None:
    _, _, doc = golden
    for name in ("procedures", "materials"):
        bad = [
            r["billed_ratio"]
            for r in doc[name]
            if not (
                isinstance(r["billed_ratio"], str)
                and re.fullmatch(r"[0-9]\.[0-9]{4}", r["billed_ratio"])
            )
        ]
        assert bad == [], name
