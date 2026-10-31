"""Care pathways: schema, loader and validity checks, with a mutation test for every check id.

Lesson 2026-10-07 (tasks/lessons.md): a guard is only as honest as its mutation tests. Every id in
schema.CHECKS has at least one case below. A case takes a real pathway (optionally enriched with a
valid construct the real files do not have yet), proves that this base is clean, applies one defect
and asserts that exactly the expected check ids fire: the defect must trip its own check and nothing
incidental. `also` names ids that a defect trips by necessity.
"""

from __future__ import annotations

import copy
import dataclasses
from collections.abc import Callable
from decimal import Decimal
from pathlib import Path

import polars as pl
import pytest
import yaml

from scripts.synthetic.pathways import PathwayLoadError, load_all, load_pathway
from scripts.synthetic.pathways.checks import (
    Catalogs,
    run_all,
)
from scripts.synthetic.pathways.expand import SESSION_RATIOS
from scripts.synthetic.pathways.schema import (
    CHECKS,
)

pytestmark = pytest.mark.unit

_REPO = Path(__file__).resolve().parents[3]
_DIR = _REPO / "data/synthetic/pathways"
_FILES = sorted(_DIR.glob("*.yaml"))
S1 = "appendicitis_lap_appendectomy_package"
S2 = "copd_exacerbation_pneumonia_ward"
S3 = "lumbar_stenosis_decompression_itemized"
S11 = "urosepsis_septic_shock_icu_stay"
S39 = "pyelonephritis_dementia_post_discharge_control"  # a control visit (poliklinik): one date, no stay


@pytest.fixture(scope="module")
def catalogs() -> Catalogs:
    return Catalogs()


def _raw(pathway_id: str) -> dict:
    return yaml.safe_load((_DIR / f"{pathway_id}.yaml").read_text(encoding="utf-8"))


def _problems(raw, cat, tmp_path, text=None, filename=None):
    """Dump `raw` to a file, load it, and return the load problems or the checks' problems."""
    body = yaml.safe_dump(raw, allow_unicode=True, sort_keys=False)
    path = tmp_path / f"{filename or raw['id']}.yaml"
    path.write_text(text(body) if text else body, encoding="utf-8")
    try:
        return run_all(load_pathway(path), cat)
    except PathwayLoadError as exc:
        return exc.problems


# --- the real files ----------------------------------------------------------------------------


def test_the_pathway_folder_has_pathways() -> None:
    assert {S1, S2} <= {p.stem for p in _FILES}


def _strays(directory: Path) -> list[str]:
    """Entries load_all never reads: everything but README.md and top-level *.yaml files."""
    kept = lambda p: p.is_file() and (p.suffix == ".yaml" or p.name == "README.md")  # noqa: E731
    return sorted(p.name for p in directory.iterdir() if not kept(p))


def test_the_pathway_folder_holds_only_the_readme_and_yaml_files() -> None:
    assert _strays(_DIR) == []


@pytest.mark.parametrize("path", _FILES, ids=lambda p: p.stem)
def test_a_real_pathway_loads(path: Path) -> None:
    assert load_pathway(path).id == path.stem


@pytest.mark.parametrize("path", _FILES, ids=lambda p: p.stem)
def test_a_real_pathway_passes_every_check(path: Path, catalogs: Catalogs) -> None:
    assert run_all(load_pathway(path), catalogs) == []


def test_load_all_returns_every_real_pathway_by_id() -> None:
    assert set(load_all()) == {p.stem for p in _FILES}


# --- tie-ins with the rest of the repository ---------------------------------------------------


def test_session_ratios_match_the_sut_text() -> None:
    clauses = pl.read_parquet(
        _REPO / "data/gazette/sut_clauses.parquet", columns=["clause_id", "text_tr", "is_in_force"]
    ).filter(pl.col("is_in_force"))
    percent = {
        row["clause_id"]: int(row["text_tr"].split("%")[1].split("'")[0].split("’")[0])
        for row in clauses.filter(
            pl.col("clause_id").is_in(["C000660", "C000661", "C000670", "C000671"])
        ).iter_rows(named=True)
    }
    assert percent == {"C000660": 30, "C000661": 50, "C000670": 25, "C000671": 50}
    share = {clause: Decimal(points) / 100 for clause, points in percent.items()}
    package, itemized = SESSION_RATIOS["package"], SESSION_RATIOS["itemized"]
    assert (package["same_incision"], package["separate_incision"]) == (
        share["C000670"],
        share["C000671"],
    )
    assert (itemized["same_incision"], itemized["separate_incision"]) == (
        share["C000660"],
        share["C000661"],
    )


def test_package_windows_match_the_sut_text() -> None:
    from scripts.synthetic.pathways.checks import PACKAGE_WINDOW_DAYS

    clauses = {"A": "C000702", "B": "C000703", "C": "C000704", "D": "C000705", "E": "C000706"}
    wanted = pl.DataFrame({"letter": list(clauses), "clause_id": list(clauses.values())})
    days = (  # "...; 15 gün ..." in the clause text
        pl.scan_parquet(_REPO / "data/gazette/sut_clauses.parquet")
        .join(wanted.lazy(), on="clause_id")
        .select(
            "letter",
            pl.col("text_tr")
            .str.split(";")
            .list.get(1)
            .str.split("gün")
            .list.get(0)
            .str.strip_chars()
            .cast(pl.Int64)
            .alias("days"),
        )
        .sort("letter")
        .collect()
    )
    assert days["letter"].to_list() == list(PACKAGE_WINDOW_DAYS)
    assert days["days"].to_list() == list(PACKAGE_WINDOW_DAYS.values())


# --- mutation cases ----------------------------------------------------------------------------

Edit = Callable[[dict, Catalogs], None]


@dataclasses.dataclass(frozen=True)
class Case:
    check: str  # the id the defect must trip
    base: str  # pathway id
    mutate: Edit | None = None
    prepare: Edit | None = None  # adds a valid construct the real files lack, before the defect
    text: Callable[[str], str] | None = None  # a defect in the YAML text itself
    filename: str | None = None
    also: tuple[str, ...] = ()  # ids the defect trips by necessity
    label: str = ""

    @property
    def name(self) -> str:
        return f"{self.check}-{self.label}" if self.label else self.check


def line(raw: dict, ident: str) -> dict:
    return next(x for x in raw["procedures"] if x["id"] == ident)


def drug(raw: dict, ident: str) -> dict:
    return next(x for x in raw["drugs"] if x["id"] == ident)


def diagnosis(raw: dict, icd: str) -> dict:
    return next(x for x in raw["diagnoses"] if x["icd10"] == icd)


def icd_name(cat: Catalogs, code: str) -> str:
    return cat.icd.filter(pl.col("code") == code)["name_tr"].item()


def ek2b_name(cat: Catalogs, code: str) -> str:
    return cat.ek2b.filter(pl.col("code") == code)["name"].unique().item()


FIXTURE = "Test fixture only: a construct the real files do not have yet."


def with_material(raw: dict, cat: Catalogs) -> None:  # on S1: a linked EK-3/F-1 material
    raw["materials"] = [
        {
            "id": "femoral_stem",
            "code": "AP2000",
            "name": "KALÇA | PRİMER | FEMORAL STEM | ÇİMENTOLU | ÇELİK | PARLATILMIŞ",
            "material_type": "implant",
            "day": "op",
            "linked_to": "appendectomy_package",
            "flags": {"titubb_registered": True, "uts_registered": True},
            "basis": "judgment",
            "source": FIXTURE,
        }
    ]


def with_second_package(raw: dict, cat: Catalogs) -> None:  # on S1: two packages in one session
    line(raw, "appendectomy_package")["session_role"] = "primary"
    raw["procedures"].append(
        {
            "id": "hernia_package",
            "kind": "package",
            "code": "P603840",
            "name": "Greftsiz umblikal herni onarımı",
            "days": "op",
            "session_role": "same_incision",
            "basis": "sut",
            "source": "C000670 (SUT 2.2.2.B(3)): a second package in one session. " + FIXTURE,
        }
    )


def with_anaesthesia(raw: dict, cat: Catalogs) -> None:  # on S2: an itemized operation + its group
    raw["procedures"] += [
        {
            "id": "decompression",
            "kind": "operation",
            "code": "615931",
            "name": "Dar spinal kanalda unilateral dekompresyon",
            "days": "admit+1",
            "basis": "judgment",
            "source": FIXTURE,
        },
        {
            "id": "anaesthesia",
            "kind": "anaesthesia",
            "code": "550160",
            "name": "Anestezi B grubu",
            "group": "B",
            "operations": ["decompression"],
            "days": "admit+1",
            "specialty": "3100",
            "basis": "judgment",
            "source": FIXTURE,
        },
    ]


def with_indication(raw: dict, cat: Catalogs) -> None:  # on S2: a drug that names its diagnosis
    drug(raw, "ceftriaxone")["indication"] = "J18.9"


def swap_in(raw: dict, ident: str, code: str, cat: Catalogs, **more) -> None:
    """Put another EK-2B code, with its catalog name, on a line."""
    line(raw, ident).update(code=code, name=ek2b_name(cat, code), **more)


def set_pins(raw: dict, **changes) -> None:
    raw["showcase"].update(changes)


def with_span(raw: dict, cat: Catalogs) -> None:  # on S39: a poliklinik session claim over 2..5 days after the first
    raw["span"] = {"min": 2, "max": 5, "basis": "judgment", "source": FIXTURE}
    raw["showcase"]["span"] = 3


def fixed_nights(raw: dict, nights: int = 5) -> None:
    """One stay length, so that a day range that is empty at the shortest stay does not hide the defect."""
    raw["nights"].update(min=nights, max=nights)
    set_pins(raw, nights=nights)


CASES = [
    # --- the file and the raw document
    Case("yaml.invalid", S2, text=lambda t: t + "\nid: copd_exacerbation_pneumonia_ward\n", label="repeated key"),
    Case("hygiene.forbidden_key", S2, lambda r, c: line(r, "bed").update(price=12)),
    Case("hygiene.anon_text", S2, lambda r, c: r.update(notes=["see ANON_77"]), label="value"),
    Case("hygiene.price_text", S2, lambda r, c: r.update(notes=["the bed costs 222,36 TL"]), label="TL"),
    Case("hygiene.id_like_number", S2, lambda r, c: r.update(notes=["patient 12345678901 came in"]), label="in a note"),
    Case("schema.id_mismatch", S2, filename="another_name"),
    # --- schema
    Case("schema.unknown_field", S2, lambda r, c: line(r, "bed").update(quantity=3)),
    Case("schema.missing_field", S2, lambda r, c: line(r, "bed").pop("days"), label="days"),
    Case("schema.bad_enum", S2, lambda r, c: r.update(claim_type="yatiss"), label="claim_type"),
    Case("schema.bad_value", S2, lambda r, c: drug(r, "enoxaparin").update(barcode="123")),
    Case("schema.day_expression", S2, lambda r, c: line(r, "bed").update(days="admit+x"), label="text"),
    Case("schema.range_order", S2, lambda r, c: r["nights"].update(min=9, max=4), label="nights"),
    Case("schema.probability", S2, lambda r, c: diagnosis(r, "I10")["optional"].update(probability=1.5)),
    Case("schema.duplicate_id", S2, lambda r, c: line(r, "nebulizer").update(id="bed"), label="line"),
    Case("schema.unknown_reference", S1, lambda r, c: r["materials"][0].update(linked_to="nowhere"), prepare=with_material, label="material"),
    Case("schema.anchor_undefined", S2, lambda r, c: line(r, "bed").update(days="op"), label="op"),
    Case("schema.line_shape", S2, lambda r, c: line(r, "chest_xray").update(session_role="primary"), label="role on imaging"),
    Case("schema.quantity_form", S2, lambda r, c: drug(r, "ceftriaxone").update(qty=7)),
    Case("schema.diagnosis_primary", S2, lambda r, c: diagnosis(r, "J18.9").update(role="primary")),
    Case("schema.stay_shape", S2, lambda r, c: r.pop("nights")),
    # --- catalog identity
    Case("procedure.in_force", S2, lambda r, c: line(r, "bed").update(code="510019"), label="no such code"),
    Case("procedure.name", S2, lambda r, c: line(r, "bed").update(name="Standart yatak ücreti")),
    Case("procedure.kind", S2, lambda r, c: line(r, "nebulizer").update(kind="lab")),
    Case("material.in_force", S1, lambda r, c: r["materials"][0].update(code="AP9999"), prepare=with_material),
    Case("material.name", S1, lambda r, c: r["materials"][0].update(name="KALÇA | FEMORAL STEM"), prepare=with_material),
    Case("drug.in_force", S2, lambda r, c: r.pop("window"), label="repealed on 2026-08-29"),
    Case("drug.name", S2, lambda r, c: drug(r, "enoxaparin").update(name="CLEXANE 40 MG")),
    Case("drug.inn", S2, lambda r, c: drug(r, "enoxaparin").update(inn="heparin sodyum")),
    Case("drug.indication", S2, lambda r, c: drug(r, "ceftriaxone").update(indication="G20"), prepare=with_indication, label="not a diagnosis"),
    Case("drug.course", S2, lambda r, c: set_pins(r, nights=4), label="course past discharge"),
    # --- ICD-10
    Case("icd.exists", S2, lambda r, c: diagnosis(r, "J18.9").update(icd10="Q99.99")),
    Case("icd.active", S2, lambda r, c: diagnosis(r, "J18.9").update(icd10="U06.9", name=icd_name(c, "U06.9"))),
    Case("icd.leaf", S2, lambda r, c: diagnosis(r, "J18.9").update(icd10="J18", name=icd_name(c, "J18"))),
    Case("icd.name", S2, lambda r, c: diagnosis(r, "J18.9").update(name="PNÖMONİ")),
    Case("icd.sex_gate", S2, lambda r, c: diagnosis(r, "J18.9").update(icd10="C53.0", name=icd_name(c, "C53.0"))),
    # --- labs, specialties
    Case("lab.in_table", S2, lambda r, c: swap_in(r, "blood_gas", "L100010", c)),
    Case("lab.name", S2, lambda r, c: line(r, "cbc_crp")["items"][0].update(name="Hemogram"), also=("procedure.name",)),
    Case("specialty.exists", S2, lambda r, c: line(r, "chest_xray").update(specialty="9999")),
    # --- billing logic
    Case("package.mode", S1, lambda r, c: r["procedures"].append({"id": "bed", "kind": "bed", "code": "510010", "name": "Standart yatak tarifesi", "days": "admit..discharge", "basis": "judgment", "source": FIXTURE}), label="bed in a package"),
    Case("package.window", S1, lambda r, c: r["nights"].update(max=12), label="a stay past the 8-day window"),
    Case("anaesthesia.group", S2, lambda r, c: line(r, "anaesthesia").update(group="C", code="550170", name="Anestezi C grubu"), prepare=with_anaesthesia),
    Case("anaesthesia.code", S2, lambda r, c: line(r, "anaesthesia").update(code="550170", name="Anestezi C grubu"), prepare=with_anaesthesia),
    Case("session.primary", S1, lambda r, c: line(r, "hernia_package").update(session_role="primary"), prepare=with_second_package, label="two primaries"),
    Case("session.order", S1, lambda r, c: (line(r, "appendectomy_package").update(session_role="same_incision"), line(r, "hernia_package").update(session_role="primary")), prepare=with_second_package),
    # --- pins
    Case("pins.out_of_range", S2, lambda r, c: set_pins(r, age=120), label="age"),
    Case("pins.unknown_id", S2, lambda r, c: set_pins(r, include=["I10", "nowhere"])),
    Case("pins.not_optional", S2, lambda r, c: set_pins(r, include=["I10", "bed"])),
    Case("pins.missing", S2, lambda r, c: r["showcase"].pop("course_days")),
    Case("pins.window", S39, lambda r, c: set_pins(r, admit="2026-09-28"), prepare=with_span, label="a span that ends after the window"),
    # --- days, sources, window
    Case("days.in_stay", S2, lambda r, c: line(r, "nebulizer").update(days="admit..discharge+1"), label="past the discharge day"),
    Case("days.duplicate", S2, lambda r, c: line(r, "chest_xray").update(days=["admit", "admit..admit+4"])),
    Case("stay.coverage", S3, lambda r, c: line(r, "bed").update(days="admit..admit+2"), label="a bed line fixed to the showcase nights"),
    Case("icu.day_pattern", S11, lambda r, c: (fixed_nights(r), line(r, "icu_end_days").update(days=["admit", "admit+1", "discharge-1"]), line(r, "icu_package").update(days="admit+2..discharge-2")), label="a 510090 on a middle day"),
    Case("source.clause_exists", S2, lambda r, c: line(r, "bed").update(source="Kılavuz p.62; C999999 says so in some other place."), label="no such clause"),
    Case("source.sut_cites", S2, lambda r, c: line(r, "companion").update(source="Doctor's order and a refakatçi belgesi, as the story says."), label="sut without a clause"),
    Case("window.valid", S2, lambda r, c: r["window"].update(start="2026-01-15")),
]  # fmt: skip


@pytest.mark.parametrize("case", CASES, ids=lambda c: c.name)
def test_a_defect_trips_its_own_check_and_nothing_else(case: Case, catalogs: Catalogs, tmp_path):
    base = _raw(case.base)
    if case.prepare:
        case.prepare(base, catalogs)
    assert _problems(base, catalogs, tmp_path) == [], "the base must be clean"
    broken = copy.deepcopy(base)
    if case.mutate:
        case.mutate(broken, catalogs)
    found = _problems(broken, catalogs, tmp_path, case.text, case.filename)
    assert {p.check for p in found} == {case.check, *case.also}, [str(p) for p in found]


def test_every_check_id_has_a_mutation_case() -> None:
    assert {case.check for case in CASES} == set(CHECKS)
