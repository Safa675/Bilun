"""Care pathways round trip: a pathway expanded with its pins equals the golden clean bill.

The goldens (tests/fixtures/pathways/golden/S1..S8.json) are exported from the reviewed clean
variant of each story by a different script, so they cannot be fitted to the YAML. Cases are
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
from scripts.synthetic.pathways.schema import Pathway, pin_problems

pytestmark = pytest.mark.unit

_REPO = Path(__file__).resolve().parents[3]
_DIR = _REPO / "data/synthetic/pathways"
_GOLDEN = _REPO / "tests/fixtures/pathways/golden"
_FILES = sorted(_DIR.glob("*.yaml"))
_STORIES = [f"S{n}" for n in range(1, 9)]


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


@pytest.mark.parametrize("path", _FILES, ids=lambda p: p.stem)
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
    """Valid pin sets that differ from the showcase in one respect each."""
    pins = pathway.showcase
    out = [("admit shifted a day", pins.model_copy(update={"admit": _shift(pins.admit, 1)}))]
    if pathway.nights:
        for nights in (pathway.nights.min, pathway.nights.max):
            if nights != pins.nights:
                out.append((f"{nights} nights", pins.model_copy(update={"nights": nights})))
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
            other = (
                drug.course_days.max
                if pins.course_days[drug.id] != drug.course_days.max
                else drug.course_days.min
            )
            if other != pins.course_days[drug.id]:
                days = {**pins.course_days, drug.id: other}
                out.append(
                    (f"{drug.id} for {other} days", pins.model_copy(update={"course_days": days}))
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


@pytest.mark.parametrize("path", _FILES, ids=lambda p: p.stem)
def test_pins_outside_the_declared_ranges_are_refused(path: Path) -> None:
    pathway = load_pathway(path)
    too_old = pathway.showcase.model_copy(update={"age": pathway.patient.age.max + 1})
    with pytest.raises(ExpandError, match="pins.out_of_range"):
        expand(pathway, too_old)


def _stories_of_pathway_files() -> list[str]:
    """Each file's showcase story, read leniently: a broken file must not fail this test."""
    stories = []
    for path in _FILES:
        try:
            stories.append(yaml.safe_load(path.read_text(encoding="utf-8"))["showcase"]["story"])
        except (OSError, yaml.YAMLError, KeyError, TypeError):
            continue
    return stories


def test_every_golden_has_a_pathway_and_every_pathway_has_a_golden() -> None:
    goldens = {p.stem for p in _GOLDEN.glob("S*.json")}
    stories = _stories_of_pathway_files()
    assert goldens == set(_STORIES)
    assert len(stories) == len(set(stories)), "two pathways claim the same story"
    assert set(stories) - goldens == set(), "a pathway without a golden"
    assert goldens - set(stories) == set(), "a golden without a pathway"


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
    units = {d["barcode"]: d["qty"] for d in expand(pathway, pins)["drugs"]}
    assert units == {
        "8699809950696": 4,  # enoxaparin: one syringe per night
        "8699508270224": 5,  # ceftriaxone: 1 a day for 5 days
        "8699548270482": 10,  # clarithromycin: 2 a day for 5 days
        "8699541791007": 5,  # methylprednisolone: 1 a day for 5 days
        "8680741521174": 1,  # ipratropium + salbutamol: a fixed box
    }


def test_optional_items_are_in_only_when_pinned() -> None:
    pathway = load_pathway(_DIR / f"{S2}.yaml")
    codes = lambda bill: [d["icd10"] for d in bill["diagnoses"]]  # noqa: E731
    assert codes(expand(pathway)) == ["J44.0", "I10", "J18.9"]
    without = pathway.showcase.model_copy(update={"include": []})
    assert codes(expand(pathway, without)) == ["J44.0", "J18.9"]


def test_the_expander_is_small_and_has_no_pricing_or_randomness() -> None:
    source = Path(expand_module.__file__).read_text(encoding="utf-8")
    assert len(source.splitlines()) <= 250
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
