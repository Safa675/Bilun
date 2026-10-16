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
    _with_groups,
    norm,
    probe_days,
    run_all,
)
from scripts.synthetic.pathways.expand import SESSION_RATIOS
from scripts.synthetic.pathways.schema import CHECKS, DrugFlags, MaterialFlags
from src.bilun.domain.claims.models import DrugClaimLine, MaterialClaimLine

pytestmark = pytest.mark.unit

_REPO = Path(__file__).resolve().parents[3]
_DIR = _REPO / "data/synthetic/pathways"
_FILES = sorted(_DIR.glob("*.yaml"))
S1 = "appendicitis_lap_appendectomy_package"
S2 = "copd_exacerbation_pneumonia_ward"


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


@pytest.mark.parametrize("path", _FILES, ids=lambda p: p.stem)
def test_a_real_pathway_loads(path: Path) -> None:
    assert load_pathway(path).id == path.stem


@pytest.mark.parametrize("path", _FILES, ids=lambda p: p.stem)
def test_a_real_pathway_passes_every_check(path: Path, catalogs: Catalogs) -> None:
    assert run_all(load_pathway(path), catalogs) == []


def test_load_all_returns_every_real_pathway_by_id() -> None:
    assert set(load_all()) == {p.stem for p in _FILES}


def test_the_readme_names_every_check_id_or_its_family() -> None:
    readme = (_DIR / "README.md").read_text(encoding="utf-8")
    unnamed = [i for i in CHECKS if i not in readme and f"{i.split('.')[0]}.*" not in readme]
    assert unnamed == []


def test_a_broken_sibling_does_not_stop_the_good_file_from_loading(tmp_path: Path) -> None:
    good = tmp_path / f"{S1}.yaml"
    good.write_text((_DIR / f"{S1}.yaml").read_text(encoding="utf-8"), encoding="utf-8")
    (tmp_path / "broken.yaml").write_text("id: broken\nnonsense: [", encoding="utf-8")
    assert load_pathway(good).id == S1
    with pytest.raises(PathwayLoadError) as error:
        load_all(tmp_path)
    assert {p.file for p in error.value.problems} == {"broken.yaml"}


def test_errors_name_the_file_and_the_field(tmp_path: Path) -> None:
    raw = _raw(S2)
    next(x for x in raw["procedures"] if x["id"] == "bed")["qty"] = 0
    path = tmp_path / f"{S2}.yaml"
    path.write_text(yaml.safe_dump(raw, allow_unicode=True, sort_keys=False), encoding="utf-8")
    with pytest.raises(PathwayLoadError) as error:
        load_pathway(path)
    message = str(error.value)
    assert f"{S2}.yaml" in message
    assert "procedures[bed].qty" in message


def test_names_are_compared_after_whitespace_normalization(catalogs: Catalogs, tmp_path) -> None:
    raw = _raw(S2)
    next(x for x in raw["procedures"] if x["id"] == "bed")["name"] = "Standart   yatak \t tarifesi"
    assert _problems(raw, catalogs, tmp_path) == []
    assert norm("a \n b") == "a b"


def test_catalogs_are_read_once(catalogs: Catalogs) -> None:
    assert catalogs.ek2b is catalogs.ek2b
    assert catalogs.window == ("2026-02-01", "2026-09-30")


# --- tie-ins with the rest of the repository ---------------------------------------------------


def test_flag_names_are_fields_of_the_claim_line_dataclasses() -> None:
    material = {f.name for f in dataclasses.fields(MaterialClaimLine)}
    drug = {f.name for f in dataclasses.fields(DrugClaimLine)}
    assert set(MaterialFlags.model_fields) <= material
    assert set(DrugFlags.model_fields) <= drug


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

    clauses = pl.read_parquet(
        _REPO / "data/gazette/sut_clauses.parquet", columns=["clause_id", "text_tr"]
    )
    text = {r["clause_id"]: r["text_tr"] for r in clauses.iter_rows(named=True)}
    found = {
        letter: int(text[clause].split(";")[1].split("gün")[0])
        for letter, clause in zip("ABCDE", ["C000702", "C000703", "C000704", "C000705", "C000706"])
    }
    assert found == PACKAGE_WINDOW_DAYS


def test_the_ek3f1_list_is_in_force_only_from_its_own_date(catalogs: Catalogs) -> None:
    from scripts.synthetic.pathways.checks import EK3F1_FROM, _frame, identity_problems

    name = "KALÇA | PRİMER | FEMORAL STEM | ÇİMENTOLU | ÇELİK | PARLATILMIŞ"
    occurrences = _frame([("AP2000", name, "materials[stem]")], "code", "name", "where")
    assert EK3F1_FROM == "2025-12-13"
    assert (
        identity_problems(occurrences, catalogs.ek3f1, ("2026-02-01", "2026-09-30"), "material")
        == []
    )
    early = identity_problems(occurrences, catalogs.ek3f1, ("2025-12-01", "2026-01-31"), "material")
    assert [p.check for p in early] == ["material.in_force"]


def test_anaesthesia_group_follows_the_band_table_in_force_on_each_day() -> None:
    totals = pl.DataFrame(
        {"day": ["2026-03-01", "2026-03-01", "2026-08-01", "2026-08-01", "2026-08-01"],
         "total": [33000.0, 6471.03, 33000.0, 6471.03, 0.0]}
    )  # fmt: skip
    bands = Catalogs().code_sets["surgical_group_bands"]
    groups = _with_groups(totals, bands)["group"].to_list()
    assert groups == ["A1", "B", "A2", "B", "E"]  # 33000 is A1 until 2026-04-16, A2 after


def test_probe_days_catch_every_catalog_boundary_inside_the_window() -> None:
    rows = pl.DataFrame(
        {"valid_from": ["2026-01-01", "2026-04-10"], "valid_to": ["2026-04-09", None]}
    )
    assert probe_days(rows, "2026-02-01", "2026-09-30") == [
        "2026-02-01",
        "2026-04-09",
        "2026-04-10",
        "2026-09-30",
    ]


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


def with_optional_indicated_drug(
    raw: dict, cat: Catalogs
) -> None:  # on S2: an indicated drug that is out
    with_indication(raw, cat)
    drug(raw, "ceftriaxone")["optional"] = {
        "probability": 0.5,
        "basis": "judgment",
        "source": FIXTURE,
    }


def with_performed(raw: dict, cat: Catalogs) -> None:  # on S2: an EMR log line
    raw["performed"] = [
        {
            "id": "xray_log",
            "code": "801720",
            "name": "Akciğer grafisi P.A. (Tek yön)",
            "day": "admit",
            "system": "emr",
            "basis": "judgment",
            "source": FIXTURE,
        }
    ]


def swap_in(raw: dict, ident: str, code: str, cat: Catalogs, **more) -> None:
    """Put another EK-2B code, with its catalog name, on a line."""
    line(raw, ident).update(code=code, name=ek2b_name(cat, code), **more)


def set_pins(raw: dict, **changes) -> None:
    raw["showcase"].update(changes)


CASES = [
    # --- the file and the raw document
    Case("yaml.invalid", S2, text=lambda t: t + "\nid: copd_exacerbation_pneumonia_ward\n", label="repeated key"),
    Case("yaml.invalid", S2, text=lambda t: "- a\n- list\n", label="not a mapping"),
    Case("hygiene.forbidden_key", S2, lambda r, c: line(r, "bed").update(price=12)),
    Case("hygiene.anon_text", S2, lambda r, c: r.update(notes=["see ANON_77"]), label="value"),
    Case("hygiene.anon_text", S2, text=lambda t: "# ANON_77\n" + t, label="comment"),
    Case("schema.id_mismatch", S2, filename="another_name"),
    # --- schema
    Case("schema.unknown_field", S2, lambda r, c: line(r, "bed").update(quantity=3)),
    Case("schema.missing_field", S2, lambda r, c: line(r, "bed").pop("days"), label="days"),
    Case("schema.missing_field", S2, lambda r, c: line(r, "bed").pop("basis"), label="basis"),
    Case("schema.missing_field", S2, lambda r, c: line(r, "bed").pop("source"), label="source"),
    Case("schema.missing_field", S2, lambda r, c: r["nights"].pop("source"), label="range source"),
    Case("schema.bad_enum", S2, lambda r, c: r.update(claim_type="yatiss"), label="claim_type"),
    Case("schema.bad_enum", S2, lambda r, c: line(r, "bed").update(basis="hearsay"), label="basis"),
    Case("schema.bad_value", S2, lambda r, c: drug(r, "enoxaparin").update(barcode="123")),
    Case("schema.bad_value", S2, text=lambda t: t.replace("admit: '2026-03-09'", "admit: 2026-03-09"), label="an unquoted date"),
    Case("schema.bad_value", S2, text=lambda t: t.replace("code: '510010'", "code: 510010"), label="an unquoted code"),
    Case("schema.bad_value", S2, lambda r, c: line(r, "bed").update(source="x" * 161), label="a source over 160 characters"),
    Case("schema.day_expression", S2, lambda r, c: line(r, "bed").update(days="admit+x"), label="text"),
    Case("schema.day_expression", S2, lambda r, c: line(r, "bed").update(days="admit..discharge-"), label="range"),
    Case("schema.day_expression", S2, lambda r, c: diagnosis(r, "I10").update(day="admit..admit+1"), label="a range for a point"),
    Case("schema.range_order", S2, lambda r, c: r["nights"].update(min=9, max=4), label="nights"),
    Case("schema.range_order", S2, lambda r, c: r["window"].update(start="2026-08-30"), label="window"),
    Case("schema.probability", S2, lambda r, c: diagnosis(r, "I10")["optional"].update(probability=1.5)),
    Case("schema.duplicate_id", S2, lambda r, c: line(r, "nebulizer").update(id="bed"), label="line"),
    Case("schema.duplicate_id", S2, lambda r, c: diagnosis(r, "J18.9").update(icd10="I10"), label="diagnosis"),
    Case("schema.unknown_reference", S1, lambda r, c: r["materials"][0].update(linked_to="nowhere"), prepare=with_material, label="material"),
    Case("schema.unknown_reference", S2, lambda r, c: line(r, "anaesthesia").update(operations=["bed"]), prepare=with_anaesthesia, label="anaesthesia"),
    Case("schema.anchor_undefined", S2, lambda r, c: line(r, "bed").update(days="op"), label="op"),
    Case("schema.anchor_undefined", S1, lambda r, c: (r.update(claim_type="acil"), r.pop("nights"), line(r, "appendectomy_package").update(days="discharge")), label="discharge on an ER-only pathway"),
    Case("schema.line_shape", S2, lambda r, c: line(r, "chest_xray").update(session_role="primary"), label="role on imaging"),
    Case("schema.line_shape", S2, lambda r, c: line(r, "bed").update(group="B"), label="group on a bed"),
    Case("schema.line_shape", S2, lambda r, c: line(r, "blood_gas").update(items=[{"code": "L106150", "name": "Potasyum (Serum/Plazma)"}, {"code": "L106910", "name": "Sodyum (Serum/Plazma)"}]), label="code and items"),
    Case("schema.quantity_form", S2, lambda r, c: drug(r, "ceftriaxone").update(qty=7)),
    Case("schema.diagnosis_primary", S2, lambda r, c: diagnosis(r, "J18.9").update(role="primary")),
    Case("schema.stay_shape", S2, lambda r, c: r.pop("nights")),
    # --- catalog identity
    Case("procedure.in_force", S2, lambda r, c: line(r, "bed").update(code="510019"), label="no such code"),
    Case("procedure.in_force", S2, lambda r, c: swap_in(r, "nebulizer", "701068", c), label="listed from 2026-07-07"),
    Case("procedure.name", S2, lambda r, c: line(r, "bed").update(name="Standart yatak ücreti")),
    Case("procedure.name", S2, lambda r, c: r["performed"][0].update(name="Akciğer grafisi"), prepare=with_performed, label="performed line"),
    Case("procedure.in_force", S2, lambda r, c: r["performed"][0].update(code="801729"), prepare=with_performed, label="performed line"),
    Case("procedure.name", S1, lambda r, c: line(r, "appendectomy_package").update(name="Appendektomi"), label="package"),
    Case("procedure.kind", S2, lambda r, c: line(r, "nebulizer").update(kind="lab")),
    Case("material.in_force", S1, lambda r, c: r["materials"][0].update(code="AP9999"), prepare=with_material),
    Case("material.name", S1, lambda r, c: r["materials"][0].update(name="KALÇA | FEMORAL STEM"), prepare=with_material),
    Case("drug.in_force", S2, lambda r, c: r.pop("window"), label="repealed on 2026-08-29"),
    Case("drug.in_force", S2, lambda r, c: drug(r, "enoxaparin").update(barcode="8699999999999"), label="no such barcode", also=("drug.inn",)),
    Case("drug.name", S2, lambda r, c: drug(r, "enoxaparin").update(name="CLEXANE 40 MG")),
    Case("drug.inn", S2, lambda r, c: drug(r, "enoxaparin").update(inn="heparin sodyum")),
    Case("drug.indication", S2, lambda r, c: drug(r, "ceftriaxone").update(indication="G20"), prepare=with_indication, label="not a diagnosis"),
    Case("drug.indication", S2, lambda r, c: drug(r, "ceftriaxone").update(indication="G20"), prepare=with_optional_indicated_drug, label="not a diagnosis, drug out of the bill"),
    Case("drug.indication", S2, lambda r, c: (drug(r, "ceftriaxone").update(indication="I10"), r["showcase"].update(include=[])), prepare=with_indication, label="optional and out"),
    Case("drug.course", S2, lambda r, c: set_pins(r, nights=4), label="course past discharge"),
    Case("drug.course", S2, lambda r, c: drug(r, "enoxaparin").update(day="admit+1"), label="per_night not from admit"),
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
    Case("package.mode", S1, lambda r, c: r.setdefault("drugs", []).append({"id": "ceftriaxone", "barcode": "8699508270224", "name": "IESEF 1 G IV ENJEKSIYONLUK COZELTI TOZU", "inn": "seftriakson", "unit": "vial", "per_box": 1, "day": "admit", "qty": 1, "basis": "judgment", "source": FIXTURE}), label="drug in a package"),
    Case("package.mode", S2, lambda r, c: r["procedures"].append({"id": "package", "kind": "package", "code": "P610131", "name": "Appendektomi, laparoskopik", "days": "admit", "basis": "judgment", "source": FIXTURE}), label="package in an itemized bill"),
    Case("package.window", S1, lambda r, c: r["nights"].update(max=12), label="a stay past the 8-day window"),
    Case("package.window", S1, lambda r, c: line(r, "appendectomy_package").update(code="P552001", name=c.ek2c.filter(pl.col("code") == "P552001")["name"].unique().item()), label="a package without a group"),
    Case("anaesthesia.group", S2, lambda r, c: line(r, "anaesthesia").update(group="C", code="550170", name="Anestezi C grubu"), prepare=with_anaesthesia),
    Case("anaesthesia.code", S2, lambda r, c: line(r, "anaesthesia").update(code="550170", name="Anestezi C grubu"), prepare=with_anaesthesia),
    Case("session.primary", S1, lambda r, c: line(r, "hernia_package").update(session_role="primary"), prepare=with_second_package, label="two primaries"),
    Case("session.primary", S1, lambda r, c: line(r, "appendectomy_package").update(session_role="same_incision"), prepare=with_second_package, label="none"),
    Case("session.order", S1, lambda r, c: (line(r, "appendectomy_package").update(session_role="same_incision"), line(r, "hernia_package").update(session_role="primary")), prepare=with_second_package),
    # --- pins
    Case("pins.out_of_range", S2, lambda r, c: set_pins(r, age=120), label="age"),
    Case("pins.out_of_range", S2, lambda r, c: set_pins(r, nights=10), label="nights"),
    Case("pins.out_of_range", S2, lambda r, c: r["patient"]["sex"].update(values=["F"]), label="sex"),
    Case("pins.out_of_range", S2, lambda r, c: set_pins(r, course_days={"ceftriaxone": 8, "clarithromycin": 5, "methylprednisolone": 5}), label="course days", also=("drug.course",)),
    Case("pins.unknown_id", S2, lambda r, c: set_pins(r, include=["I10", "nowhere"])),
    Case("pins.not_optional", S2, lambda r, c: set_pins(r, include=["I10", "bed"])),
    Case("pins.missing", S2, lambda r, c: r["showcase"].pop("course_days")),
    Case("pins.window", S2, lambda r, c: set_pins(r, admit="2026-01-15")),
    # --- days, sources, window
    Case("days.in_stay", S2, lambda r, c: line(r, "bed").update(days="admit..discharge+1")),
    Case("days.duplicate", S2, lambda r, c: line(r, "chest_xray").update(days=["admit", "admit..admit+4"])),
    Case("source.clause_exists", S2, lambda r, c: line(r, "bed").update(source="Kılavuz p.62; C999999 says so in some other place."), label="no such clause"),
    Case("source.clause_exists", S2, lambda r, c: line(r, "bed").update(source="Kılavuz p.62; C000644 (repealed text of 2.2.2(1))."), label="not in force"),
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


@pytest.mark.parametrize(
    ("window", "admit", "group", "clean"),
    [
        pytest.param(
            ("2026-02-01", "2026-08-29"), "2026-03-09", "A1", False, id="spans the switch, A1"
        ),
        pytest.param(
            ("2026-02-01", "2026-08-29"), "2026-03-09", "A2", False, id="spans the switch, A2"
        ),
        pytest.param(
            ("2026-02-01", "2026-04-15"), "2026-03-09", "A1", True, id="before the switch, A1"
        ),
        pytest.param(
            ("2026-02-01", "2026-04-15"), "2026-03-09", "A2", False, id="before the switch, A2"
        ),
        pytest.param(
            ("2026-04-16", "2026-08-29"), "2026-05-04", "A2", True, id="after the switch, A2"
        ),
        pytest.param(
            ("2026-04-16", "2026-08-29"), "2026-05-04", "A1", False, id="after the switch, A1"
        ),
    ],
)
def test_the_anaesthesia_group_must_hold_on_both_sides_of_the_band_switch(
    window, admit, group, clean, catalogs: Catalogs, tmp_path
) -> None:
    """609440 has puan 33,528: group A1 under the 2024-08-07 bands, A2 under those of 2026-04-16."""
    raw = _raw(S2)
    with_anaesthesia(raw, catalogs)
    code = catalogs.code_sets["anaesthesia"]["single"][group]
    line(raw, "decompression").update(code="609440", name=ek2b_name(catalogs, "609440"))
    line(raw, "anaesthesia").update(group=group, code=code, name=ek2b_name(catalogs, code))
    raw["window"] = {"start": window[0], "end": window[1]}
    raw["showcase"]["admit"] = admit
    fired = {p.check for p in _problems(raw, catalogs, tmp_path)}
    assert fired == (set() if clean else {"anaesthesia.group"})
