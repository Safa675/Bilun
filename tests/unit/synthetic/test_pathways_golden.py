"""The golden clean and faulty bills, tests/fixtures/pathways/{golden,golden_faulty}/<story>.json.

A story has goldens exactly when `stories.py` builds it; a story without a fault (`CLEAN_ONLY`: S39) has a clean
golden and no faulty one; see tests/fixtures/pathway_goldens.py.

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

from tests.fixtures.pathway_goldens import (
    clean_only_in,
    clean_only_stories,
    faulty_golden_stories,
    golden_problems,
    golden_stories,
    stories_in,
)
from tests.fixtures import synthetic_cohort as cohort

pytestmark = pytest.mark.unit

REPO = Path(__file__).resolve().parents[3]
GOLDEN_DIR = REPO / "tests" / "fixtures" / "pathways" / "golden"
GOLDEN_FAULTY_DIR = REPO / "tests" / "fixtures" / "pathways" / "golden_faulty"
GOLDEN_DIRS = {"clean": GOLDEN_DIR, "faulty": GOLDEN_FAULTY_DIR}
EXPORTER = (
    REPO / "reports" / "synthetic-data" / "2026-10-15-showcase-proofs" / "export_clean_lines.py"
)
STORIES = golden_stories()
FAULTY_STORIES = faulty_golden_stories()
GOLDEN_STORIES = {"clean": STORIES, "faulty": FAULTY_STORIES}

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
# The optional keys of a line: a procedure line with a patient share (slice G5b, S32's examination) carries its
# `copay_rate`, a share above 0 and below 1 with two decimals ("0.20"); a line without one has no such key.
OPTIONAL_LINE_KEYS = {"procedures": {"copay_rate"}}
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
    params=[(variant, sid) for variant in GOLDEN_DIRS for sid in GOLDEN_STORIES[variant]],
    ids=lambda item: f"{item[0]}-{item[1]}",
)
def golden(request: pytest.FixtureRequest) -> tuple[str, str, dict]:
    """(story, file text, parsed document); a missing or invalid file errors here."""
    variant, sid = request.param
    path = GOLDEN_DIRS[variant] / f"{sid}.json"
    text = path.read_text(encoding="utf-8")
    return sid, text, json.loads(text)


def test_the_stories_with_goldens_are_the_cohort_stories_in_order() -> None:
    assert STORIES == cohort.stories()


@pytest.mark.parametrize("variant", GOLDEN_DIRS)
def test_every_story_has_its_golden_file_and_no_other_file_is_there(variant: str) -> None:
    directory, stories = GOLDEN_DIRS[variant], GOLDEN_STORIES[variant]
    assert [s for s in stories if not (directory / f"{s}.json").is_file()] == []
    assert sorted(p.name for p in directory.iterdir()) == sorted(f"{s}.json" for s in stories)


def test_a_story_has_a_faulty_golden_exactly_when_it_has_a_fault() -> None:
    """A bill without a fault (S23, S32, S39, S48) is a clean golden only; every other story's fault record has its faulty golden."""
    with_fault = {record["story"] for record in cohort.load_registry()["faults"]}
    assert set(FAULTY_STORIES) == with_fault
    assert clean_only_stories() == [s for s in STORIES if s not in with_fault] == ["S23", "S32", "S39", "S48"]
    assert FAULTY_STORIES == [s for s in STORIES if s not in clean_only_stories()]  # stories.py order


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ('CLEAN_ONLY: tuple[str, ...] = ("S39", "S77")\n', ["S39", "S77"]),
        ("CLEAN_ONLY = ['S39']\n", ["S39"]),
        ("CLEAN_ONLY = ()\n", []),
        ("STORIES = {}\n", []),  # no such name: no clean bill
        ("x = 1\nCLEAN_ONLY: tuple[str, ...] = ('S5',)\nSTORIES = {}\n", ["S5"]),
    ],
)
def test_the_clean_only_stories_are_read_from_stories_py_without_importing_it(source: str, expected: list[str]) -> None:
    assert clean_only_in(source) == expected


@pytest.mark.parametrize("bad", ["CLEAN_ONLY = 1\n", "CLEAN_ONLY = (1, 2)\n", "CLEAN_ONLY = ('S1', x)\n", "CLEAN_ONLY = {'S1'}\n"])
def test_a_clean_only_that_is_not_a_tuple_of_strings_is_refused(bad: str) -> None:
    with pytest.raises(ValueError, match="CLEAN_ONLY"):
        clean_only_in(bad)


def test_stories_are_read_from_the_stories_dict_without_importing_it() -> None:
    source = 'import nothing_real\nSTORIES = {"S1": s1, "S10": s10}\n'
    assert stories_in(source) == ["S1", "S10"]
    for bad in ("x = 1\n", "STORIES = [1, 2]\n", "STORIES = {1: a}\n", "STORIES = {**other}\n"):
        with pytest.raises(ValueError, match="STORIES"):
            stories_in(bad)


@pytest.mark.parametrize(
    ("goldens", "pathways", "built", "expected"),
    [
        ({"S1", "S2"}, ["S1", "S2"], ["S1", "S2"], []),
        # a pathway of a story that stories.py does not build has no golden and is fine
        ({"S1", "S2"}, ["S1", "S2", "S10", "S11"], ["S1", "S2"], []),
        (
            {"S1"},
            ["S1"],
            ["S1", "S2"],
            [
                "story of stories.py without a golden: ['S2']",
                "golden without a pathway: ['S2']",
            ],
        ),
        (
            {"S1", "S2"},
            ["S1", "S2"],
            ["S1", "S2", "S3"],
            [
                "story of stories.py without a golden: ['S3']",
                "golden without a pathway: ['S3']",
            ],
        ),
        (
            {"S1", "S3"},
            ["S1"],
            ["S1"],
            ["golden without a story in stories.py: ['S3']"],
        ),
        ({"S1", "S2"}, ["S1"], ["S1", "S2"], ["golden without a pathway: ['S2']"]),
        ({"S1"}, ["S1", "S1"], ["S1"], ["two pathways claim the same story"]),
        ({"S1"}, ["S1"], ["S1", "S1"], ["stories.py builds a story twice"]),
    ],
)
def test_goldens_pathways_and_stories_py_must_pair_up(
    goldens: set[str], pathways: list[str], built: list[str], expected: list[str]
) -> None:
    assert golden_problems(goldens, pathways, built) == expected


@pytest.mark.parametrize("story", FAULTY_STORIES)
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
        optional = OPTIONAL_LINE_KEYS.get(name, set())
        assert [row for row in doc[name] if not keys <= set(row) <= keys | optional] == [], name
    for name in ("procedures", "materials", "drugs"):
        assert all(isinstance(row["flags"], dict) for row in doc[name]), name
    rates = [row["copay_rate"] for row in doc["procedures"] if "copay_rate" in row]
    assert all(re.fullmatch(r"0\.[0-9]{2}", rate) and rate != "0.00" for rate in rates), rates


def test_only_the_examination_of_s32_carries_a_copay_rate(golden) -> None:
    story, _, doc = golden
    rates = [(row["code"], row["copay_rate"]) for row in doc["procedures"] if "copay_rate" in row]
    assert rates == ([("520030", "0.20")] if story == "S32" else [])


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
    assert header["claim_type"] in {"yatis", "acil", "poliklinik", "gunubirlik"}
    # Null admission and discharge only for a visit (acil, poliklinik, gunubirlik): it has no stay.
    nullable = {"admission_date", "discharge_date"} if header["claim_type"] != "yatis" else set()
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


# --- S14: the story bill has the ICU bill of S11 as history (a cross-bill rule needs it) -----------------------


def test_the_s14_story_bill_reads_the_faulty_icu_bill_as_history_and_the_rule_fires_on_the_faulty_ward_bill_only() -> None:
    """Run in a subprocess like the golden export: the proof harness changes the working directory when it is imported."""
    code = (
        "import json, sys\n"
        "sys.path.insert(0, 'reports/synthetic-data/2026-10-15-showcase-proofs')\n"
        "from stories import s14\n"
        "from src.bilun.domain.prose_rules.yatak_icu_overlap import detect_yatak_icu_overlap\n"
        "out = {}\n"
        "for variant in ('clean', 'faulty'):\n"
        "    ctx = s14(variant).ctx()\n"
        "    rows = detect_yatak_icu_overlap(list(ctx.history.claims), list(ctx.history.procedure_lines))\n"
        "    icu = sum(p.billed_amount_try for p in ctx.history.procedure_lines if p.claim_id == 'C-SH11')\n"
        "    out[variant] = {'active': [c.claim_id for c in ctx.claims], 'icu_billed': str(icu),\n"
        "                    'history': sorted(c.claim_id for c in ctx.history.claims),\n"
        "                    'patients': sorted({c.patient_id for c in ctx.history.claims}),\n"
        "                    'rows': [(r['claim_id'], r['overlap_date'], r['risk_amount_try']) for r in rows]}\n"
        "print(json.dumps(out))\n"
    )
    done = subprocess.run([sys.executable, "-c", code], cwd=REPO, capture_output=True, text=True, check=True)
    out = json.loads(done.stdout.strip().splitlines()[-1])
    for variant in ("clean", "faulty"):
        assert out[variant]["icu_billed"] == "8072.73"  # the history is S11's faulty bill, the one the cohort holds
        assert out[variant]["active"] == ["C-SH14"]
        assert out[variant]["history"] == ["C-SH11", "C-SH14"]
        assert out[variant]["patients"] == ["SH-11"]  # the ward bill is the patient of S11
    assert out["clean"]["rows"] == []
    assert out["faulty"]["rows"] == [["C-SH14", "2026-06-07", 222.36]]


# --- S39 and S40: the story bills of patient 4's follow-ups; the second visit has the stay and the control as history ----


def test_the_s40_story_bill_reads_the_stay_and_the_control_as_history_and_the_rule_fires_on_the_faulty_visit_only() -> None:
    """Run in a subprocess like the golden export: the proof harness changes the working directory when it is imported."""
    code = (
        "import json, sys\n"
        "sys.path.insert(0, 'reports/synthetic-data/2026-10-15-showcase-proofs')\n"
        "from stories import s40\n"
        "from src.bilun.domain.prose_rules.common_billing_errors import detect_duplicate_exam_10day\n"
        "out = {}\n"
        "for variant in ('clean', 'faulty'):\n"
        "    ctx = s40(variant).ctx()\n"
        "    rows = detect_duplicate_exam_10day(list(ctx.history.claims), list(ctx.history.procedure_lines))\n"
        "    out[variant] = {'active': [c.claim_id for c in ctx.claims],\n"
        "                    'history': sorted(c.claim_id for c in ctx.history.claims),\n"
        "                    'patients': sorted({c.patient_id for c in ctx.history.claims}),\n"
        "                    'rows': [(r['claim_id'], r['prior_claim_id'], str(r['procedure_date']), r['gap_days']) for r in rows]}\n"
        "print(json.dumps(out))\n"
    )
    done = subprocess.run([sys.executable, "-c", code], cwd=REPO, capture_output=True, text=True, check=True)
    out = json.loads(done.stdout.strip().splitlines()[-1])
    for variant in ("clean", "faulty"):
        assert out[variant]["active"] == ["C-SH40"]
        assert out[variant]["history"] == ["C-SH04", "C-SH39", "C-SH40"]  # the stay, the control, this visit
        assert out[variant]["patients"] == ["SH-04"]  # the patient of story S4
    assert out["clean"]["rows"] == []  # no examination fee on the second visit: nothing to find
    assert out["faulty"]["rows"] == [["C-SH40", "C-SH39", "2026-06-01", 7]]


def test_the_s39_story_bill_is_a_clean_bill_with_no_faulty_variant() -> None:
    code = (
        "import json, sys\n"
        "sys.path.insert(0, 'reports/synthetic-data/2026-10-15-showcase-proofs')\n"
        "from stories import CLEAN_ONLY, STORIES, s39\n"
        "try:\n"
        "    s39('faulty')\n"
        "    refused = False\n"
        "except ValueError:\n"
        "    refused = True\n"
        "ctx = s39('clean').ctx()\n"
        "print(json.dumps({'clean_only': list(CLEAN_ONLY), 'in_stories': 'S39' in STORIES, 'refused': refused,\n"
        "                  'history': sorted(c.claim_id for c in ctx.history.claims),\n"
        "                  'codes': sorted(p.procedure_code for p in ctx.procedure_lines)}))\n"
    )
    done = subprocess.run([sys.executable, "-c", code], cwd=REPO, capture_output=True, text=True, check=True)
    out = json.loads(done.stdout.strip().splitlines()[-1])
    assert out["clean_only"] == ["S23", "S32", "S39", "S48"] and out["in_stories"] is True and out["refused"] is True
    assert out["history"] == ["C-SH04", "C-SH39"]  # the stay of the same patient is its history
    assert out["codes"] == ["520030", "905671", "L104780", "L107010", "L107020"]  # the visit, the culture, three tests


def test_the_s32_story_bill_is_a_clean_bill_whose_examination_carries_the_patients_share() -> None:
    """The hand-built control of S2 (the second, independent version of the pathway's bill): no faulty variant, the
    stay of S2 as its history, one examination with the copay flag, rate 0.20, billed 85.73 and payable 68.58."""
    code = (
        "import json, sys\n"
        "sys.path.insert(0, 'reports/synthetic-data/2026-10-15-showcase-proofs')\n"
        "from stories import CLEAN_ONLY, STORIES, s32\n"
        "try:\n"
        "    s32('faulty')\n"
        "    refused = False\n"
        "except ValueError:\n"
        "    refused = True\n"
        "bill = s32('clean')\n"
        "ctx, head = bill.ctx(), bill.header()\n"
        "print(json.dumps({'in_stories': 'S32' in STORIES and 'S32' in CLEAN_ONLY, 'refused': refused,\n"
        "                  'history': sorted(c.claim_id for c in ctx.history.claims),\n"
        "                  'lines': [(p.procedure_code, p.copay_rate_applicable, str(p.copay_rate), str(p.billed_amount_try),\n"
        "                             str(p.expected_payable_try)) for p in ctx.procedure_lines],\n"
        "                  'totals': [str(head.expected_total_billed_try), str(head.expected_total_payable_try)]}))\n"
    )
    done = subprocess.run([sys.executable, "-c", code], cwd=REPO, capture_output=True, text=True, check=True)
    out = json.loads(done.stdout.strip().splitlines()[-1])
    assert out["in_stories"] is True and out["refused"] is True
    assert out["history"] == ["C-SH02", "C-SH32"]  # the stay of the same patient is its history
    assert out["lines"] == [["520030", True, "0.20", "85.73", "68.58"]]
    assert out["totals"] == ["85.73", "68.58"]  # the payable total follows the line


def test_the_proof_script_proves_every_story_with_a_fault_and_reads_the_row_of_s40_as_its_target() -> None:
    code = (
        "import json, sys\n"
        "sys.path.insert(0, 'reports/synthetic-data/2026-10-15-showcase-proofs')\n"
        "import prove\n"
        "row = {'rule_id': 'tablo15_2_duplicate_exam_10day', 'gap_days': 7}\n"
        "print(json.dumps({'stories': prove.default_stories(),\n"
        "                  'fires': prove.target_amount('S40', [row]),\n"
        "                  'silent': prove.target_amount('S40', []),\n"
        "                  'other_rule': prove.target_amount('S40', [{'rule_id': 'x'}])}))\n"
    )
    done = subprocess.run([sys.executable, "-c", code], cwd=REPO, capture_output=True, text=True, check=True)
    out = json.loads(done.stdout.strip().splitlines()[-1])
    assert out["stories"] == FAULTY_STORIES  # S39 has no proof
    assert out["fires"] == 0.0 and out["silent"] is None and out["other_rule"] is None  # a row without money is the finding
