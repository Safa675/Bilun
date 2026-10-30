"""Care pathways round trip: a pathway expanded with its pins equals the golden clean bill.

The goldens (tests/fixtures/pathways/golden/<story>.json, S1..S9) are exported from the reviewed clean
variant of each story by a different script, so they cannot be fitted to the YAML. A pathway of a story
that script does not build (a later story) has no golden and is not compared with one. Cases are
parametrized per pathway file and load their file inside the test: a broken sibling fails only its
own cases.
"""

from __future__ import annotations

import ast
import json
from datetime import date, timedelta
from pathlib import Path

import pytest
import yaml

import scripts.synthetic.pathways.expand as expand_module
from scripts.synthetic.pathways import PathwayLoadError, load_all, load_pathway, load_text
from scripts.synthetic.pathways.expand import ExpandError, expand
from scripts.synthetic.pathways.schema import Pathway, Pins, course_overrun, pin_problems
from tests.fixtures.pathway_goldens import golden_problems, golden_stories

pytestmark = pytest.mark.unit

_REPO = Path(__file__).resolve().parents[3]
_DIR = _REPO / "data/synthetic/pathways"
_GOLDEN = _REPO / "tests/fixtures/pathways/golden"
_FILES = sorted(_DIR.glob("*.yaml"))
_STORIES = golden_stories()


def _story_of(path: Path) -> str | None:
    """A file's showcase story, read leniently: a broken file has none and fails in its own cases."""
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))["showcase"]["story"]
    except (OSError, yaml.YAMLError, KeyError, TypeError):
        return None


_GOLDEN_FILES = [p for p in _FILES if _story_of(p) in _STORIES]


def _golden(story: str) -> dict:
    return json.loads((_GOLDEN / f"{story}.json").read_text(encoding="utf-8"))


def _diff(got: dict, want: dict) -> str:
    """The first differing entries, readable in a failure message."""
    lines = []
    for key in want:
        if got.get(key) == want[key]:
            continue
        if isinstance(want[key], list):
            extra = [x for x in got.get(key, []) if x not in want[key]]
            missing = [x for x in want[key] if x not in got.get(key, [])]
            lines.append(f"{key}: only in expansion {extra[:4]}; only in golden {missing[:4]}")
        else:
            lines.append(f"{key}: expansion {got.get(key)} != golden {want[key]}")
    return "\n".join(lines)


@pytest.mark.parametrize("path", _GOLDEN_FILES, ids=lambda p: p.stem)
def test_the_expansion_equals_the_golden_clean_bill(path: Path) -> None:
    pathway = load_pathway(path)
    got, want = expand(pathway), _golden(pathway.showcase.story)
    assert got == want, _diff(got, want)


@pytest.mark.parametrize("path", _FILES, ids=lambda p: p.stem)
def test_the_expansion_is_deterministic_and_leaves_the_pathway_alone(path: Path) -> None:
    pathway = load_pathway(path)
    before = pathway.model_dump()
    assert expand(pathway) == expand(pathway)
    assert pathway.model_dump() == before


def _variants(pathway: Pathway) -> list[tuple[str, object]]:
    """Valid pin sets that differ from the showcase in one optional item or one course each.

    Nights and admit are not here: they always change the header, so "the bill changed" proves
    nothing about them. The stay lines and the dates have their own tests below.
    """
    pins = pathway.showcase
    out = []
    optional = [d.icd10 for d in pathway.diagnoses if d.optional]
    optional += [
        x.id
        for x in (*pathway.procedures, *pathway.materials, *pathway.drugs, *pathway.performed)
        if x.optional
    ]
    for ident in optional:
        flipped = (
            [i for i in pins.include if i != ident]
            if ident in pins.include
            else [*pins.include, ident]
        )
        out.append((f"{ident} flipped", pins.model_copy(update={"include": flipped})))
    for drug in pathway.drugs:
        if drug.course_days and drug.id in pins.course_days:
            span, now = drug.course_days, pins.course_days[drug.id]
            fits = [  # the longest other course that still ends by the discharge
                n
                for n in range(span.min, span.max + 1)
                if n != now and course_overrun(pathway, drug, pins.nights, n) <= 0
            ]
            if fits:
                days = {**pins.course_days, drug.id: fits[-1]}
                out.append(
                    (
                        f"{drug.id} for {fits[-1]} days",
                        pins.model_copy(update={"course_days": days}),
                    )
                )
    return out


def _shift(iso: str, days: int) -> str:
    return (date.fromisoformat(iso) + timedelta(days=days)).isoformat()


@pytest.mark.parametrize("path", _FILES, ids=lambda p: p.stem)
def test_a_changed_pin_changes_the_expansion(path: Path) -> None:
    pathway = load_pathway(path)
    base = expand(pathway)
    for label, pins in _variants(pathway):
        assert pin_problems(pathway, pins) == [], label
        assert expand(pathway, pins) != base, label


def _pins_at(pathway: Pathway, nights: int) -> Pins:
    """The showcase pins for another stay. Every pinned course gets its shortest length, which fits."""
    pins = pathway.showcase
    courses = {d.id: d.course_days.min for d in pathway.drugs if d.id in pins.course_days}
    return pins.model_copy(update={"nights": nights, "course_days": courses})


def _assert_stay_lines_scale(pathway: Pathway) -> None:
    """Each bed and companion line gains exactly one bill line per extra night."""
    low, high = pathway.nights.min, pathway.nights.max
    short, long = expand(pathway, _pins_at(pathway, low)), expand(pathway, _pins_at(pathway, high))
    for line in pathway.procedures:
        if line.kind in ("bed", "companion"):
            count = lambda bill: sum(row["code"] == line.code for row in bill["procedures"])  # noqa: E731
            gained = count(long) - count(short)
            assert gained == high - low, (
                f"{line.id}: {gained} lines more for {high - low} more nights"
            )


@pytest.mark.parametrize("path", _FILES, ids=lambda p: p.stem)
def test_the_bed_and_companion_lines_scale_with_the_nights(path: Path) -> None:
    pathway = load_pathway(path)
    if pathway.nights is None:
        pytest.skip("an ER-only pathway has no stay")
    _assert_stay_lines_scale(pathway)


def test_a_bed_line_fixed_to_the_showcase_nights_fails_the_scaling_test() -> None:
    """The old "a changed pin changes the bill" test passed such a line: the header changed anyway."""
    pathway = _variant(S3, lambda raw: _line(raw, "bed").update(days="admit..admit+2"))
    with pytest.raises(AssertionError, match=r"bed: 0 lines more for 2 more nights"):
        _assert_stay_lines_scale(pathway)


_DATE_KEYS = {"date", "admission_date", "discharge_date", "claim_start_date", "claim_end_date"}


def _moved(node: object, days: int) -> object:
    """A bill with every date moved by `days`."""
    if isinstance(node, dict):
        return {
            key: _shift(value, days) if key in _DATE_KEYS and value else _moved(value, days)
            for key, value in node.items()
        }
    return [_moved(item, days) for item in node] if isinstance(node, list) else node


@pytest.mark.parametrize("path", _FILES, ids=lambda p: p.stem)
def test_a_later_admission_moves_every_date_and_nothing_else(path: Path) -> None:
    pathway = load_pathway(path)
    later = pathway.showcase.model_copy(update={"admit": _shift(pathway.showcase.admit, 3)})
    assert expand(pathway, later) == _moved(expand(pathway), 3)


@pytest.mark.parametrize("path", _FILES, ids=lambda p: p.stem)
def test_pins_outside_the_declared_ranges_are_refused(path: Path) -> None:
    pathway = load_pathway(path)
    too_old = pathway.showcase.model_copy(update={"age": pathway.patient.age.max + 1})
    with pytest.raises(ExpandError, match="pins.out_of_range"):
        expand(pathway, too_old)


def _stories_of_pathway_files() -> list[str]:
    """Each file's showcase story, read leniently: a broken file must not fail this test."""
    return [story for story in map(_story_of, _FILES) if story is not None]


def test_every_golden_has_a_pathway_and_every_pathway_of_a_golden_story_has_its_golden() -> None:
    goldens = {p.stem for p in _GOLDEN.glob("S*.json")}
    assert golden_problems(goldens, _stories_of_pathway_files(), _STORIES) == []
    # every pathway of a story that stories.py builds is compared with its golden above
    stories = _stories_of_pathway_files()
    assert sorted(_story_of(p) for p in _GOLDEN_FILES) == sorted(s for s in stories if s in goldens)
    assert {"S9"} <= set(stories)  # the first story after S8 is built (stories.py) and has a pathway


def test_a_pathway_of_a_later_story_needs_no_golden(tmp_path: Path) -> None:
    """The first story that stories.py does not build can have a pathway and no golden."""
    raw = yaml.safe_load((_DIR / f"{S3}.yaml").read_text(encoding="utf-8"))
    raw["id"], raw["showcase"]["story"] = "later_story_pathway", "S99"
    later = load_text(yaml.safe_dump(raw, allow_unicode=True, sort_keys=False), "later_story_pathway.yaml")
    stories = [*_stories_of_pathway_files(), later.showcase.story]
    goldens = {p.stem for p in _GOLDEN.glob("S*.json")}
    assert golden_problems(goldens, stories, _STORIES) == []
    assert later.showcase.story not in _STORIES


def test_a_broken_sibling_fails_only_its_own_case(tmp_path: Path) -> None:
    for path in _FILES:
        (tmp_path / path.name).write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
    (tmp_path / "broken_one.yaml").write_text(
        "id: broken_one\nschema_version: 1\n", encoding="utf-8"
    )
    good = load_pathway(tmp_path / _FILES[0].name)
    assert expand(good) == _golden(good.showcase.story)
    with pytest.raises(PathwayLoadError) as error:
        load_all(tmp_path)
    assert {p.file for p in error.value.problems} == {"broken_one.yaml"}


# --- expander branches the first two pathways do not reach -------------------------------------
# S3..S8 reach them through their own round trips; until they land, small variants of S1 and S2 do.

S1 = "appendicitis_lap_appendectomy_package"
S2 = "copd_exacerbation_pneumonia_ward"
S3 = "lumbar_stenosis_decompression_itemized"
FIXTURE = "Test fixture only: a construct the real files do not have yet."


def _variant(base: str, edit) -> Pathway:
    raw = yaml.safe_load((_DIR / f"{base}.yaml").read_text(encoding="utf-8"))
    edit(raw)
    return load_text(yaml.safe_dump(raw, allow_unicode=True, sort_keys=False), "variant.yaml")


def _line(raw: dict, ident: str) -> dict:
    return next(x for x in raw["procedures"] if x["id"] == ident)


def _with_material(raw: dict) -> None:
    raw["materials"] = [
        {
            "id": "femoral_stem",
            "code": "AP2000",
            "name": "KALÇA | PRİMER | FEMORAL STEM | ÇİMENTOLU | ÇELİK | PARLATILMIŞ",
            "material_type": "implant",
            "qty": 2,
            "day": "op",
            "linked_to": "appendectomy_package",
            "flags": {"titubb_registered": True, "uts_registered": False},
            "basis": "judgment",
            "source": FIXTURE,
        }
    ]


def _operation(ident: str, code: str, role: str, kind: str = "package") -> dict:
    return {
        "id": ident, "kind": kind, "code": code, "name": "Test fixture", "days": "op",
        "session_role": role, "basis": "judgment", "source": FIXTURE,
    }  # fmt: skip


def test_a_material_links_to_its_procedure_and_carries_quantity_and_flags() -> None:
    bill = expand(_variant(S1, _with_material))
    assert bill["materials"] == [
        {
            "code": "AP2000",
            "date": "2026-07-14",
            "qty": 2,
            "material_type": "implant",
            "linked_procedure": {"code": "P610131", "date": "2026-07-14"},
            "billed_ratio": "1.0000",
            "flags": {"titubb_registered": True, "uts_registered": False},
        }
    ]


def test_a_material_whose_procedure_is_out_of_the_bill_is_refused() -> None:
    def edit(raw: dict) -> None:
        _with_material(raw)
        chance = {"probability": 0.5, "basis": "judgment", "source": FIXTURE}
        _line(raw, "appendectomy_package")["optional"] = chance
        raw["materials"][0]["optional"] = chance
        raw["showcase"]["include"] = ["femoral_stem"]

    with pytest.raises(ExpandError, match="not in the bill"):
        expand(_variant(S1, edit))


@pytest.mark.parametrize(
    ("role", "package_ratio", "itemized_ratio"),
    [("same_incision", "0.2500", "0.3000"), ("separate_incision", "0.5000", "0.5000")],
)
def test_session_roles_set_the_billed_ratio_from_the_sut_table(role, package_ratio, itemized_ratio):
    def packages(raw: dict) -> None:
        _line(raw, "appendectomy_package")["session_role"] = "primary"
        raw["procedures"].append(_operation("hernia_package", "P603840", role))

    def operations(raw: dict) -> None:
        raw["op_day"] = "admit+1"
        raw["procedures"] += [
            _operation("first_operation", "615931", "primary", "operation"),
            _operation("second_operation", "603840", role, "operation"),
        ]

    ratios = {p["code"]: p["billed_ratio"] for p in expand(_variant(S1, packages))["procedures"]}
    assert ratios == {"P610131": "1.0000", "P603840": package_ratio}
    ratios = {p["code"]: p["billed_ratio"] for p in expand(_variant(S2, operations))["procedures"]}
    assert (ratios["615931"], ratios["603840"]) == ("1.0000", itemized_ratio)


@pytest.mark.parametrize(("role", "ratio"), [("same_incision", "0.3000"), ("separate_incision", "0.5000")])
def test_an_ek2b_line_beside_a_package_takes_the_share_of_an_ek2b_line(role: str, ratio: str) -> None:
    """S50 (slice G15): the ERCP package leads its session in full; the sphincterotomy and the stone extraction through it
    are billed beside the package at the share of an EK-2B line (SUT 2.2.2.B(3)(c), (ç): C000672 30 %, C000673 50 %),
    not at the 25 % of a second package (C000670)."""

    def edit(raw: dict) -> None:
        for ident in ("sphincterotomy", "stone_extraction"):
            _line(raw, ident)["session_role"] = role

    ratios = {p["code"]: p["billed_ratio"] for p in expand(_variant("retained_common_bile_duct_stone_ercp_package", edit))["procedures"]}
    assert ratios == {"P701360": "1.0000", "701370": ratio, "701440": ratio}


def test_an_er_only_pathway_has_no_admission_or_discharge() -> None:
    def edit(raw: dict) -> None:
        raw.update(claim_type="acil", billing_mode="itemized")
        raw.pop("nights")
        raw["showcase"].pop("nights")

    bill = expand(_variant(S1, edit))
    header = bill["header"]
    assert (header["admission_date"], header["discharge_date"]) == (None, None)
    assert header["claim_start_date"] == header["claim_end_date"] == "2026-07-14"
    assert {p["date"] for p in bill["procedures"]} == {"2026-07-14"}


def test_performed_lines_carry_their_system() -> None:
    def edit(raw: dict) -> None:
        raw["performed"] = [
            {
                "id": "xray_log",
                "code": "801720",
                "name": "Akciğer grafisi P.A. (Tek yön)",
                "day": "admit+4",
                "system": "pacs",
                "basis": "judgment",
                "source": FIXTURE,
            }  # fmt: skip
        ]

    bill = expand(_variant(S2, edit))
    assert bill["performed"] == [{"code": "801720", "date": "2026-03-13", "source": "pacs"}]


def test_drug_quantities_follow_the_nights_and_the_pinned_course_days() -> None:
    pathway = load_pathway(_DIR / f"{S2}.yaml")
    pins = pathway.showcase.model_copy(
        update={
            "nights": 4,
            "course_days": {"ceftriaxone": 5, "clarithromycin": 5, "methylprednisolone": 5},
        }
    )
    drugs = expand(pathway, pins)["drugs"]
    units: dict[str, int] = {}
    for d in drugs:
        units[d["barcode"]] = units.get(d["barcode"], 0) + d["qty"]
    # a course drug is one line a day of its daily units (review of 2026-10-30, A3)
    assert [d["qty"] for d in drugs if d["barcode"] == "8699548270482"] == [2, 2, 2, 2, 2]
    assert units == {
        "8699809950696": 4,  # enoxaparin: one syringe per night
        "8699508270224": 5,  # ceftriaxone: 1 a day for 5 days
        "8699548270482": 10,  # clarithromycin: 2 a day for 5 days
        "8699541791007": 5,  # methylprednisolone: 1 a day for 5 days
        "8680741521174": 1,  # ipratropium + salbutamol: a fixed box
    }


def test_a_pinned_course_that_outlasts_the_pinned_stay_is_refused() -> None:
    pathway = load_pathway(_DIR / f"{S2}.yaml")
    # the showcase pins ceftriaxone for 7 days: it ends on the discharge day of 6 nights, not of 4
    four_nights = pathway.showcase.model_copy(update={"nights": 4})
    with pytest.raises(ExpandError, match=r"drug\.course.*ceftriaxone"):
        expand(pathway, four_nights)
    courses = {**four_nights.course_days, "ceftriaxone": 5}
    fits = four_nights.model_copy(update={"course_days": courses})
    assert expand(pathway, fits)["header"]["discharge_date"] == "2026-03-13"


def test_optional_items_are_in_only_when_pinned() -> None:
    pathway = load_pathway(_DIR / f"{S2}.yaml")
    codes = lambda bill: [d["icd10"] for d in bill["diagnoses"]]  # noqa: E731
    assert codes(expand(pathway)) == ["J44.0", "I10", "J18.9"]
    without = pathway.showcase.model_copy(update={"include": []})
    assert codes(expand(pathway, without)) == ["J44.0", "J18.9"]


def test_the_expander_has_no_pricing_or_randomness() -> None:
    source = Path(expand_module.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    modules = {
        node.module if isinstance(node, ast.ImportFrom) else alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import | ast.ImportFrom)
        for alias in getattr(node, "names", [])
    }
    assert modules <= {"__future__", "datetime", "decimal", "schema"} | {None}, modules
    names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
    names |= {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
    assert not {
        n for n in names if any(w in n.lower() for w in ("price", "amount", "random", "open"))
    }


def test_a_chapter_7_procedure_of_a_session_takes_the_ratio_of_its_role() -> None:
    """S22: the colonoscopy leads its session, the polypectomy through it is billed at its role's share (SUT 2.2.2.A(5))."""

    def session(pathway: Pathway) -> dict[str, str]:
        return {p["code"]: p["billed_ratio"] for p in expand(pathway)["procedures"] if p["code"] in ("701450", "701460")}

    s22 = load_pathway(_DIR / "gi_bleed_admission_colonoscopy.yaml")
    assert {line.id: (line.kind, line.session_role) for line in s22.procedures if line.session_role} == {
        "colonoscopy": ("procedure", "primary"),
        "polypectomy": ("procedure", "separate_incision"),
    }
    assert session(s22) == {"701450": "1.0000", "701460": "0.5000"}

    def same_incision(raw: dict) -> None:
        _line(raw, "polypectomy")["session_role"] = "same_incision"

    assert session(_variant("gi_bleed_admission_colonoscopy", same_incision)) == {"701450": "1.0000", "701460": "0.3000"}

