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
from datetime import date
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import polars as pl
import pytest
import yaml

from scripts.synthetic.pathways import PathwayLoadError, load_all, load_pathway, load_text
from scripts.synthetic.pathways.checks import (
    Catalogs,
    _frame,
    _stay_cases,
    _with_groups,
    check_anaesthesia,
    check_package_mode,
    check_package_window,
    check_pins,
    identity_problems,
    in_force,
    norm,
    pins_problems,
    probe_days,
    run_all,
)
from scripts.synthetic.pathways.expand import SESSION_RATIOS
from scripts.synthetic.pathways.loader import hygiene
from scripts.synthetic.pathways.schema import CHECKS, DrugFlags, MaterialFlags
from src.bilun.domain.claims.models import DrugClaimLine, MaterialClaimLine
from src.bilun.domain.materials.ek4a_as_of import ek4a_as_of

pytestmark = pytest.mark.unit

_REPO = Path(__file__).resolve().parents[3]
_DIR = _REPO / "data/synthetic/pathways"
_FILES = sorted(_DIR.glob("*.yaml"))
S1 = "appendicitis_lap_appendectomy_package"
S2 = "copd_exacerbation_pneumonia_ward"
S3 = "lumbar_stenosis_decompression_itemized"
S5 = "femoral_neck_fracture_cemented_hemiarthroplasty_package"
S6 = "aspiration_pneumonia_parkinson_ward"
S7 = "pleuritic_chest_pain_er_pulmonary_embolism_ruled_out"
S11 = "urosepsis_septic_shock_icu_stay"
S12 = "late_preterm_newborn_incubator_stay"


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


def test_a_yml_file_a_subfolder_or_another_file_is_a_stray(tmp_path: Path) -> None:
    for name in ("README.md", "fine.yaml", "wrong.yml", "notes.txt", "fine.yaml.bak"):
        (tmp_path / name).write_text("x", encoding="utf-8")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "deep.yaml").write_text("x", encoding="utf-8")
    assert _strays(tmp_path) == ["fine.yaml.bak", "notes.txt", "sub", "wrong.yml"]


@pytest.mark.parametrize("path", _FILES, ids=lambda p: p.stem)
def test_a_real_pathway_loads(path: Path) -> None:
    assert load_pathway(path).id == path.stem


@pytest.mark.parametrize("path", _FILES, ids=lambda p: p.stem)
def test_a_real_pathway_passes_every_check(path: Path, catalogs: Catalogs) -> None:
    assert run_all(load_pathway(path), catalogs) == []


def test_load_all_returns_every_real_pathway_by_id() -> None:
    assert set(load_all()) == {p.stem for p in _FILES}


@pytest.mark.parametrize("story", ["S1", "S8", "S9", "S10", "S25", "S99", "S100"])
def test_a_showcase_story_is_s_and_a_number_with_no_upper_limit(story: str) -> None:
    raw = _raw(S3)
    raw["showcase"]["story"] = story
    body = yaml.safe_dump(raw, allow_unicode=True, sort_keys=False)
    assert load_text(body, f"{S3}.yaml").showcase.story == story


@pytest.mark.parametrize(
    "story", ["S0", "S01", "S", "s9", "T9", "S9a", "S-1", " S9", "S 9", "S9 ", "9", "S1.5", ""]
)
def test_a_malformed_showcase_story_is_a_bad_value(story: str) -> None:
    raw = _raw(S3)
    raw["showcase"]["story"] = story
    body = yaml.safe_dump(raw, allow_unicode=True, sort_keys=False)
    with pytest.raises(PathwayLoadError) as error:
        load_text(body, f"{S3}.yaml")
    assert [p.check for p in error.value.problems] == ["schema.bad_value"]
    assert "showcase.story" in str(error.value)


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


@pytest.mark.parametrize(
    "text",
    [
        "an error row of 0 TL (never_principal_diagnosis_blocklist)",  # a zero amount is not a price
        "0,00 TRY",
        "barcode 8699508270224, code 510010, lab L103900, on 2026-03-09",
        "500 mg twice a day for 5 days, 2 g once, 40 mg a day",
        "a 1 TLC panel and 3 trying days",  # TL and TRY count only as whole words
        "ANONYMOUS and anonymised data; a canon 5",
        "a 12-digit number 123456789012 and a 10-digit one 1234567890",
    ],
)
def test_hygiene_lets_ordinary_text_through(text: str) -> None:
    assert hygiene({"notes": [text]}, text) == []


def test_hygiene_names_the_key_or_value_it_found_not_only_the_file() -> None:
    raw = {"notes": ["see ANON_77", "12 TL"], "ANON_1": 1, "unit_price": 3}
    found = {(p.check, p.where) for p in hygiene(raw)}
    assert found == {
        ("hygiene.anon_text", "notes[0]"),
        ("hygiene.price_text", "notes[1]"),
        ("hygiene.anon_text", "ANON_1"),
        ("hygiene.forbidden_key", "unit_price"),
    }


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


def test_the_ek3f1_list_is_in_force_only_from_its_own_date(catalogs: Catalogs) -> None:
    from scripts.synthetic.pathways.checks import EK3F1_FROM

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


def test_ek4a_valid_until_is_exclusive_as_the_engine_reads_it(catalogs: Catalogs) -> None:
    """EK-4A rows are half-open [valid_from, valid_until): KLACID 500 MG IV ends on 2026-08-29."""
    klacid = "8699548270482"
    for day, listed in (("2026-08-27", True), ("2026-08-28", True), ("2026-08-29", False)):
        ours = in_force(catalogs.ek4a, [klacid], [day]).item(0, "n") > 0
        engine = bool(ek4a_as_of(date.fromisoformat(day)).by_barcode(klacid))
        assert (ours, engine) == (listed, listed), day


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


def ek2b_name_on(cat: Catalogs, code: str, day: str) -> str:
    """The catalog name on a day (the multiple-operation anaesthesia codes rename with the band table)."""
    current = (pl.col("valid_from") <= day) & (
        pl.col("valid_to").is_null() | (pl.col("valid_to") >= day)
    )
    return cat.ek2b.filter((pl.col("code") == code) & current)["name"].item()


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


def with_er_course(raw: dict, cat: Catalogs) -> None:  # on S7: a one-day course on an ER-only visit
    raw["drugs"].append(
        {
            "id": "antibiotic",
            "barcode": "8699508270224",
            "name": "IESEF 1 G IV ENJEKSIYONLUK COZELTI TOZU",
            "inn": "seftriakson",
            "unit": "vial",
            "per_box": 1,
            "day": "admit",
            "per_day": 1,
            "course_days": {"min": 1, "max": 1, "basis": "judgment", "source": FIXTURE},
            "basis": "judgment",
            "source": FIXTURE,
        }
    )
    set_pins(raw, course_days={"antibiotic": 1})


def chance(probability: float = 0.5) -> dict:
    return {"probability": probability, "basis": "judgment", "source": FIXTURE}


def set_anaesthesia(raw: dict, cat: Catalogs, mode: str, group: str) -> None:
    code = cat.code_sets["anaesthesia"][mode][group]
    name = ek2b_name_on(cat, code, raw["showcase"]["admit"])
    line(raw, "anaesthesia").update(group=group, code=code, name=name)


def with_two_operations(raw: dict, cat: Catalogs) -> None:  # on S3: two operations, one anaesthesia
    """615931 (6,471 puan) and 616020 (3,109) sum to group A3 under both band tables; alone, B or lower."""
    line(raw, "decompression")["session_role"] = "primary"
    raw["procedures"].append(
        {
            "id": "laminectomy",
            "kind": "operation",
            "code": "616020",
            "name": ek2b_name(cat, "616020"),
            "days": "op",
            "session_role": "same_incision",
            "basis": "judgment",
            "source": FIXTURE,
        }
    )
    line(raw, "anaesthesia")["operations"] = ["decompression", "laminectomy"]
    set_anaesthesia(raw, cat, "multiple_operations", "A3")
    # the multiple-operation codes carry the band table in their name, which changes on 2026-04-16
    raw["window"] = {"start": "2026-04-16", "end": "2026-09-30", "source": FIXTURE}


def with_optional_second_primary(raw: dict, cat: Catalogs) -> None:  # on S1: out of the bill
    with_second_package(raw, cat)
    line(raw, "hernia_package").update(session_role="primary", optional=chance())


def per_night_instead_of_course(raw: dict) -> None:  # on with_er_course: a stay-only form
    for key in ("per_day", "course_days"):
        drug(raw, "antibiotic").pop(key)
    drug(raw, "antibiotic")["per_night"] = 1
    set_pins(raw, course_days={})


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


def fixed_nights(raw: dict, nights: int = 5) -> None:
    """One stay length, so that a day range that is empty at the shortest stay does not hide the defect."""
    raw["nights"].update(min=nights, max=nights)
    set_pins(raw, nights=nights)


def second_icu_tier(raw: dict, cat: Catalogs) -> None:
    """Split the ICU package days between two tiers: P552002 on the first two, P552003 on the third."""
    line(raw, "icu_package").update(days="admit+1..admit+2")
    raw["procedures"].append(
        {
            "id": "icu_package_3",
            "kind": "icu_package",
            "code": "P552003",
            "name": cat.ek2c.filter(pl.col("code") == "P552003")["name"].unique().item(),
            "days": "admit+3..discharge-2",
            "basis": "judgment",
            "source": FIXTURE,
        }
    )


def icu_line(ident: str, kind: str, code: str, name: str, days) -> dict:
    return {"id": ident, "kind": kind, "code": code, "name": name, "days": days, "basis": "judgment", "source": FIXTURE}


def optional_and_pinned_in(raw: dict, icd: str) -> None:
    """Make a diagnosis optional and put it in the showcase bill."""
    diagnosis(raw, icd)["optional"] = {"probability": 0.9, "basis": "judgment", "source": FIXTURE}
    set_pins(raw, include=[*raw["showcase"]["include"], icd])


CASES = [
    # --- the file and the raw document
    Case("yaml.invalid", S2, text=lambda t: t + "\nid: copd_exacerbation_pneumonia_ward\n", label="repeated key"),
    Case("yaml.invalid", S2, text=lambda t: "- a\n- list\n", label="not a mapping"),
    Case("hygiene.forbidden_key", S2, lambda r, c: line(r, "bed").update(price=12)),
    Case("hygiene.forbidden_key", S2, lambda r, c: line(r, "bed").update(amount=12), label="amount"),
    Case("hygiene.forbidden_key", S2, lambda r, c: line(r, "bed").update(total=12), label="total"),
    Case("hygiene.forbidden_key", S2, lambda r, c: r.update(package_candidate=True), label="package_candidate"),
    Case("hygiene.forbidden_key", S2, lambda r, c: line(r, "bed").update(Unit_Price=12), label="in any case"),
    Case("hygiene.anon_text", S2, lambda r, c: r.update(notes=["see ANON_77"]), label="value"),
    Case("hygiene.anon_text", S2, lambda r, c: r.update(notes=["see anon_77"]), label="lowercase"),
    Case("hygiene.anon_text", S2, lambda r, c: r.update(notes=["see ANON-77"]), label="hyphen"),
    Case("hygiene.anon_text", S2, lambda r, c: r.update(notes=["see ANON 77"]), label="space"),
    Case("hygiene.anon_text", S2, lambda r, c: r.update(notes=["see ANON77"]), label="no separator"),
    Case("hygiene.anon_text", S2, lambda r, c: r.update(notes=["an anon_ prefix"]), label="prefix only"),
    Case("hygiene.anon_text", S2, lambda r, c: line(r, "bed").update(ANON_7=1), label="key"),
    Case("hygiene.anon_text", S2, text=lambda t: "# ANON_77\n" + t, label="comment"),
    Case("hygiene.anon_text", S2, text=lambda t: "# anon 77\n" + t, label="lowercase comment"),
    Case("hygiene.price_text", S2, lambda r, c: r.update(notes=["the bed costs 222,36 TL"]), label="TL"),
    Case("hygiene.price_text", S2, lambda r, c: r.update(notes=["a stay of 12.500 TRY"]), label="TRY"),
    Case("hygiene.price_text", S2, lambda r, c: r.update(notes=["about \u20ba1.250"]), label="sign first"),
    Case("hygiene.price_text", S2, lambda r, c: r.update(notes=["about 1250\u20ba"]), label="sign last"),
    Case("hygiene.price_text", S2, lambda r, c: line(r, "bed").update(source="Kılavuz p.62, C000648: 222 tl a day."), label="in a source"),
    Case("hygiene.price_text", S2, text=lambda t: "# 40 TL\n" + t, label="comment"),
    Case("hygiene.id_like_number", S2, lambda r, c: r.update(notes=["patient 12345678901 came in"]), label="in a note"),
    Case("hygiene.id_like_number", S2, lambda r, c: line(r, "bed").update(source="Kılavuz p.62 (12345678901)"), label="in a source"),
    Case("hygiene.id_like_number", S2, text=lambda t: "# 12345678901\n" + t, label="comment"),
    Case("schema.id_mismatch", S2, filename="another_name"),
    # --- schema
    Case("schema.unknown_field", S2, lambda r, c: line(r, "bed").update(quantity=3)),
    Case("schema.missing_field", S2, lambda r, c: line(r, "bed").pop("days"), label="days"),
    Case("schema.missing_field", S2, lambda r, c: line(r, "bed").pop("basis"), label="basis"),
    Case("schema.missing_field", S2, lambda r, c: line(r, "bed").pop("source"), label="source"),
    Case("schema.missing_field", S2, lambda r, c: r["nights"].pop("source"), label="range source"),
    Case("schema.missing_field", S2, lambda r, c: r["window"].pop("source", None), label="window source"),
    Case("schema.bad_enum", S2, lambda r, c: r.update(claim_type="yatiss"), label="claim_type"),
    Case("schema.bad_enum", S2, lambda r, c: line(r, "bed").update(basis="hearsay"), label="basis"),
    Case("schema.bad_value", S2, lambda r, c: drug(r, "enoxaparin").update(barcode="123")),
    Case("schema.bad_value", S2, lambda r, c: set_pins(r, admit="20260309"), label="a compact date"),
    Case("schema.bad_value", S2, text=lambda t: t.replace("admit: '2026-03-09'", "admit: 2026-03-09"), label="an unquoted date"),
    Case("schema.bad_value", S2, text=lambda t: t.replace("code: '510010'", "code: 510010"), label="an unquoted code"),
    Case("schema.bad_value", S2, lambda r, c: line(r, "bed").update(source="x" * 161), label="a source over 160 characters"),
    Case("schema.bad_value", S2, lambda r, c: r["window"].update(source="x" * 161), label="a window source over 160 characters"),
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
    Case("schema.unknown_reference", S1, lambda r, c: line(r, "appendectomy_package").update(optional=chance()), prepare=with_material, label="a material on an optional package"),
    Case("schema.unknown_reference", S3, lambda r, c: line(r, "laminectomy").update(optional=chance()), prepare=with_two_operations, label="an anaesthesia line on an optional operation"),
    Case("schema.unknown_reference", S3, lambda r, c: line(r, "laminectomy").update(code="615931", name=ek2b_name(c, "615931")), prepare=with_two_operations, label="two operations with one code"),
    Case("schema.anchor_undefined", S2, lambda r, c: line(r, "bed").update(days="op"), label="op"),
    Case("schema.anchor_undefined", S3, lambda r, c: r.update(op_day="op+1"), label="op_day defined from op"),
    Case("schema.anchor_undefined", S1, lambda r, c: (r.update(claim_type="acil"), r.pop("nights"), line(r, "appendectomy_package").update(days="discharge")), label="discharge on an ER-only pathway"),
    Case("schema.line_shape", S2, lambda r, c: line(r, "chest_xray").update(session_role="primary"), label="role on imaging"),
    Case("schema.line_shape", S2, lambda r, c: line(r, "bed").update(group="B"), label="group on a bed"),
    Case("schema.line_shape", S1, lambda r, c: line(r, "appendectomy_package").update(session_role="primary", days=["op", "op+1"]), label="a role on a two-day line"),
    Case("schema.line_shape", S2, lambda r, c: line(r, "cbc_crp")["items"].append(dict(line(r, "cbc_crp")["items"][0])), label="a panel with a code twice"),
    Case("schema.line_shape", S2, lambda r, c: line(r, "blood_gas").update(items=[{"code": "L106150", "name": "Potasyum (Serum/Plazma)"}, {"code": "L106910", "name": "Sodyum (Serum/Plazma)"}]), label="code and items"),
    Case("schema.quantity_form", S2, lambda r, c: drug(r, "ceftriaxone").update(qty=7)),
    Case("schema.diagnosis_primary", S2, lambda r, c: diagnosis(r, "J18.9").update(role="primary")),
    Case("schema.diagnosis_primary", S2, lambda r, c: diagnosis(r, "J44.0").update(optional=chance()), label="an optional primary"),
    Case("schema.stay_shape", S2, lambda r, c: r.pop("nights")),
    Case("schema.stay_shape", S7, lambda r, c: r.update(nights={"min": 1, "max": 2, "basis": "judgment", "source": FIXTURE}), label="nights on an ER-only pathway"),
    Case("schema.stay_shape", S7, lambda r, c: per_night_instead_of_course(r), prepare=with_er_course, label="a per_night drug on an ER-only visit"),
    # --- catalog identity
    Case("procedure.in_force", S2, lambda r, c: line(r, "bed").update(code="510019"), label="no such code"),
    Case("procedure.in_force", S2, lambda r, c: swap_in(r, "nebulizer", "701068", c), label="listed from 2026-07-07"),
    Case("procedure.name", S2, lambda r, c: line(r, "bed").update(name="Standart yatak ücreti")),
    Case("procedure.name", S2, lambda r, c: r["performed"][0].update(name="Akciğer grafisi"), prepare=with_performed, label="performed line"),
    Case("procedure.in_force", S2, lambda r, c: r["performed"][0].update(code="801729"), prepare=with_performed, label="performed line"),
    Case("procedure.name", S1, lambda r, c: line(r, "appendectomy_package").update(name="Appendektomi"), label="package"),
    Case("procedure.kind", S2, lambda r, c: line(r, "nebulizer").update(kind="lab")),
    Case("procedure.kind", S11, lambda r, c: line(r, "icu_end_days").update(code="510010", name="Standart yatak tarifesi"), label="an icu_day on the ward bed"),
    Case("procedure.kind", S11, lambda r, c: line(r, "icu_package").update(code="P610131", name=c.ek2c.filter(pl.col("code") == "P610131")["name"].unique().item()), label="an icu_package on a surgical package"),
    Case("procedure.kind", S11, lambda r, c: line(r, "icu_package").update(code="510090", name="Yoğun bakım"), label="an icu_package on the day rate"),
    Case("procedure.kind", S2, lambda r, c: line(r, "bed").update(code="510090", name="Yoğun bakım"), label="a ward bed on the ICU day rate"),
    Case("procedure.kind", S12, lambda r, c: line(r, "incubator").update(code="510010", name="Standart yatak tarifesi"), label="a newborn_bed on the ward bed"),
    Case("procedure.kind", S12, lambda r, c: line(r, "incubator").update(code="510090", name="Yoğun bakım"), label="a newborn_bed on the ICU day rate"),
    Case("procedure.kind", S12, lambda r, c: line(r, "incubator").update(code="510121", name="Refakat"), label="a newborn_bed on the companion code"),
    Case("procedure.kind", S12, lambda r, c: line(r, "incubator").update(kind="bed"), label="the incubator declared as a ward bed"),
    Case("procedure.kind", S12, lambda r, c: line(r, "pediatric_consult").update(code="510070", name="Kuvöz"), label="an exam on the incubator code"),
    Case("material.in_force", S1, lambda r, c: r["materials"][0].update(code="AP9999"), prepare=with_material),
    Case("material.name", S1, lambda r, c: r["materials"][0].update(name="KALÇA | FEMORAL STEM"), prepare=with_material),
    Case("drug.in_force", S2, lambda r, c: r.pop("window"), label="repealed on 2026-08-29"),
    Case("drug.in_force", S2, lambda r, c: r["window"].update(end="2026-08-29"), label="valid_until is exclusive"),
    Case("drug.in_force", S2, lambda r, c: drug(r, "enoxaparin").update(barcode="8699999999999"), label="no such barcode", also=("drug.inn",)),
    Case("drug.name", S2, lambda r, c: drug(r, "enoxaparin").update(name="CLEXANE 40 MG")),
    Case("drug.inn", S2, lambda r, c: drug(r, "enoxaparin").update(inn="heparin sodyum")),
    Case("drug.indication", S2, lambda r, c: drug(r, "ceftriaxone").update(indication="G20"), prepare=with_indication, label="not a diagnosis"),
    Case("drug.indication", S2, lambda r, c: drug(r, "ceftriaxone").update(indication="G20"), prepare=with_optional_indicated_drug, label="not a diagnosis, drug out of the bill"),
    Case("drug.indication", S2, lambda r, c: (drug(r, "ceftriaxone").update(indication="I10"), r["showcase"].update(include=[])), prepare=with_indication, label="optional and out"),
    Case("drug.indication", S6, lambda r, c: optional_and_pinned_in(r, "G20"), label="the indication is optional, pinned in"),
    Case("drug.course", S2, lambda r, c: set_pins(r, nights=4), label="course past discharge"),
    Case("drug.course", S2, lambda r, c: drug(r, "enoxaparin").update(day="admit+1"), label="per_night not from admit"),
    Case("drug.course", S2, lambda r, c: drug(r, "ceftriaxone")["course_days"].update(min=6, max=7), label="shortest course past the shortest stay"),
    Case("drug.course", S7, lambda r, c: (drug(r, "antibiotic")["course_days"].update(max=3), set_pins(r, course_days={"antibiotic": 2})), prepare=with_er_course, label="a 2-day course on an ER-only visit"),
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
    Case("package.mode", S11, lambda r, c: r.update(billing_mode="package"), label="ICU lines in a package bill"),
    Case("package.mode", S12, lambda r, c: r.update(billing_mode="package"), label="a newborn bed in a package bill"),
    Case("package.window", S1, lambda r, c: r["nights"].update(max=12), label="a stay past the 8-day window"),
    Case("package.window", S1, lambda r, c: line(r, "appendectomy_package").update(code="P552001", name=c.ek2c.filter(pl.col("code") == "P552001")["name"].unique().item()), label="a package without a group"),
    Case("anaesthesia.group", S2, lambda r, c: line(r, "anaesthesia").update(group="C", code="550170", name="Anestezi C grubu"), prepare=with_anaesthesia),
    Case("anaesthesia.code", S2, lambda r, c: line(r, "anaesthesia").update(code="550170", name="Anestezi C grubu"), prepare=with_anaesthesia),
    Case("anaesthesia.code", S3, lambda r, c: set_anaesthesia(r, c, "single", "A3"), prepare=with_two_operations, label="the single-operation code for two operations"),
    Case("anaesthesia.group", S3, lambda r, c: set_anaesthesia(r, c, "multiple_operations", "B"), prepare=with_two_operations, label="two operations, the group of the larger one"),
    Case("procedure.in_force", S3, lambda r, c: swap_in(r, "laminectomy", "609231", c), prepare=with_two_operations, label="a second operation listed from 2026-07-07"),
    Case("session.primary", S1, lambda r, c: line(r, "hernia_package").update(session_role="primary"), prepare=with_second_package, label="two primaries"),
    Case("session.primary", S1, lambda r, c: line(r, "appendectomy_package").update(session_role="same_incision"), prepare=with_second_package, label="none"),
    Case("session.primary", S1, lambda r, c: set_pins(r, include=["hernia_package"]), prepare=with_optional_second_primary, label="an optional second primary that is in the bill"),
    Case("session.order", S1, lambda r, c: (line(r, "appendectomy_package").update(session_role="same_incision"), line(r, "hernia_package").update(session_role="primary")), prepare=with_second_package),
    # --- pins
    Case("pins.out_of_range", S2, lambda r, c: set_pins(r, age=120), label="age"),
    Case("pins.out_of_range", S2, lambda r, c: set_pins(r, nights=10), label="nights"),
    Case("pins.out_of_range", S2, lambda r, c: r["patient"]["sex"].update(values=["F"]), label="sex"),
    Case("pins.out_of_range", S2, lambda r, c: set_pins(r, course_days={"ceftriaxone": 8, "clarithromycin": 5, "methylprednisolone": 5}), label="course days", also=("drug.course",)),
    Case("pins.unknown_id", S2, lambda r, c: set_pins(r, include=["I10", "nowhere"])),
    Case("pins.not_optional", S2, lambda r, c: set_pins(r, include=["I10", "bed"])),
    Case("pins.missing", S2, lambda r, c: r["showcase"].pop("course_days")),
    Case("pins.missing", S2, lambda r, c: r["showcase"].pop("nights"), label="nights: no course is tested against a missing stay"),
    Case("pins.window", S2, lambda r, c: set_pins(r, admit="2026-01-15")),
    # --- days, sources, window
    Case("days.in_stay", S2, lambda r, c: line(r, "nebulizer").update(days="admit..discharge+1"), label="past the discharge day"),
    Case("days.in_stay", S2, lambda r, c: line(r, "chest_xray").update(days="admit+3..admit+1"), label="an empty range"),
    Case("days.in_stay", S2, lambda r, c: line(r, "chest_xray").update(days=["admit", "admit+5"]), label="outside the shortest stay only"),
    Case("days.duplicate", S2, lambda r, c: line(r, "chest_xray").update(days=["admit", "admit..admit+4"])),
    Case("days.duplicate", S2, lambda r, c: line(r, "chest_xray").update(days=["admit+1", "discharge-8"]), also=("days.in_stay",), label="a collision at the longest stay only"),
    Case("stay.coverage", S3, lambda r, c: line(r, "bed").update(days="admit..admit+2"), label="a bed line fixed to the showcase nights"),
    Case("stay.coverage", S2, lambda r, c: line(r, "companion").update(days="admit..admit+4"), label="a companion line fixed to 5 nights"),
    Case("stay.coverage", S2, lambda r, c: line(r, "bed").update(days="admit..discharge-1"), label="a bed line that drops the discharge day"),
    Case("stay.coverage", S2, lambda r, c: line(r, "companion").update(days="admit..discharge"), label="a companion line on the discharge day"),
    # --- an intensive-care stay: the ICU lines are the bed lines of the bill (days 0..N-1, not the transfer day)
    Case("stay.coverage", S11, lambda r, c: line(r, "icu_end_days").update(days=["admit", "discharge-2"]), label="an ICU stay that stops a day early", also=("icu.day_pattern",)),
    Case("stay.coverage", S11, lambda r, c: line(r, "icu_end_days").update(days=["admit", "discharge"]), label="a 510090 on the transfer day", also=("icu.day_pattern",)),
    Case("stay.coverage", S11, lambda r, c: r["procedures"].append(icu_line("icu_again", "icu_package", "P552002", "İkinci basamak yoğun bakım hastası", "admit+1")), label="two ICU lines on one day", also=("icu.day_pattern",)),
    Case("stay.coverage", S11, lambda r, c: r["procedures"].append(icu_line("icu_transfer", "icu_package", "P552002", "İkinci basamak yoğun bakım hastası", "discharge")), label="an ICU line on the transfer day, every other day covered", also=("icu.day_pattern",)),
    Case("stay.coverage", S11, lambda r, c: r["procedures"].append({"id": "bed", "kind": "bed", "code": "510010", "name": "Standart yatak tarifesi", "days": "admit..discharge", "basis": "judgment", "source": FIXTURE}), label="a ward bed beside ICU lines"),
    Case("stay.coverage", S7, lambda r, c: r["procedures"].append(icu_line("icu_visit", "icu_day", "510090", "Yoğun bakım", "admit")), label="an ICU line on an ER-only visit"),
    # --- a newborn stay: the ward and the newborn bed lines are the day's one bed (days 0..N, the discharge day included)
    Case("stay.coverage", S12, lambda r, c: line(r, "incubator").update(days="admit..discharge-1"), label="an incubator that drops the discharge day"),
    Case("stay.coverage", S12, lambda r, c: line(r, "incubator").update(days="admit..admit+3"), label="an incubator line fixed to 4 nights"),
    Case("stay.coverage", S12, lambda r, c: line(r, "incubator").update(days=["admit", "admit+2..discharge"]), label="a day with no bed line in the middle"),
    Case("stay.coverage", S12, lambda r, c: line(r, "incubator").update(days="admit..discharge+1"), label="an incubator past the discharge day", also=("days.in_stay",)),
    Case("stay.coverage", S12, lambda r, c: r["procedures"].append(icu_line("cot", "newborn_bed", "510081", "Kot (beşik)", "admit..discharge")), label="a cot beside the incubator on every day"),
    Case("stay.coverage", S12, lambda r, c: r["procedures"].append(icu_line("cot", "newborn_bed", "510081", "Kot (beşik)", "discharge")), label="a cot on the incubator's discharge day"),
    Case("stay.coverage", S12, lambda r, c: r["procedures"].append({"id": "bed", "kind": "bed", "code": "510010", "name": "Standart yatak tarifesi", "days": "admit..discharge", "basis": "judgment", "source": FIXTURE}), label="a ward bed beside the incubator"),
    Case("stay.coverage", S12, lambda r, c: r["procedures"].append(icu_line("icu_again", "icu_package", "P552002", "İkinci basamak yoğun bakım hastası", "admit+1")), label="an ICU line beside the incubator", also=("icu.day_pattern",)),
    Case("stay.coverage", S7, lambda r, c: r["procedures"].append(icu_line("incubator_visit", "newborn_bed", "510070", "Kuvöz", "admit")), label="a newborn bed on an ER-only visit"),
    Case("icu.day_pattern", S11, lambda r, c: (fixed_nights(r), line(r, "icu_end_days").update(days=["admit", "admit+1", "discharge-1"]), line(r, "icu_package").update(days="admit+2..discharge-2")), label="a 510090 on a middle day"),
    Case("icu.day_pattern", S11, lambda r, c: (fixed_nights(r), line(r, "icu_end_days").update(days="admit"), line(r, "icu_package").update(days="admit+1..discharge-1")), label="no 510090 on the last day"),
    Case("icu.day_pattern", S11, lambda r, c: (fixed_nights(r), line(r, "icu_package").update(days="admit+1..admit+2")), label="a package day missing between the end days", also=("stay.coverage",)),
    Case("icu.day_pattern", S11, lambda r, c: (fixed_nights(r), second_icu_tier(r, c)), label="two package tiers in one stay"),
    Case("source.clause_exists", S2, lambda r, c: line(r, "bed").update(source="Kılavuz p.62; C999999 says so in some other place."), label="no such clause"),
    Case("source.clause_exists", S2, lambda r, c: line(r, "bed").update(source="Kılavuz p.62; C000644 (repealed text of 2.2.2(1))."), label="not in force"),
    Case("source.clause_exists", S2, lambda r, c: r["window"].update(source="KLACID 500 MG IV leaves EK-4A on 2026-08-29, as C999999 says."), label="a window source"),
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
            ("2026-02-01", "2026-08-28"), "2026-03-09", "A1", False, id="spans the switch, A1"
        ),
        pytest.param(
            ("2026-02-01", "2026-08-28"), "2026-03-09", "A2", False, id="spans the switch, A2"
        ),
        pytest.param(
            ("2026-02-01", "2026-04-15"), "2026-03-09", "A1", True, id="before the switch, A1"
        ),
        pytest.param(
            ("2026-02-01", "2026-04-15"), "2026-03-09", "A2", False, id="before the switch, A2"
        ),
        pytest.param(
            ("2026-04-16", "2026-08-28"), "2026-05-04", "A2", True, id="after the switch, A2"
        ),
        pytest.param(
            ("2026-04-16", "2026-08-28"), "2026-05-04", "A1", False, id="after the switch, A1"
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
    raw["window"] = {"start": window[0], "end": window[1], "source": FIXTURE}
    raw["showcase"]["admit"] = admit
    fired = {p.check for p in _problems(raw, catalogs, tmp_path)}
    assert fired == (set() if clean else {"anaesthesia.group"})


# --- the edges of the checks -------------------------------------------------------------------


@pytest.mark.parametrize(
    ("base", "longest", "fires"),
    [
        pytest.param(S1, 7, False, id="C: 7 nights from the package day are 8 days"),
        pytest.param(S1, 8, True, id="C: 8 nights are 9 days"),
        pytest.param(S5, 10, False, id="B: 10 nights from day 1 are 10 days"),
        pytest.param(S5, 11, True, id="B: 11 nights are 11 days"),
    ],
)
def test_the_package_window_counts_from_the_package_day(
    base, longest, fires, catalogs: Catalogs, tmp_path
) -> None:
    """Group C allows 8 days (C000704), group B 10 (C000703); the package day is day one."""
    raw = _raw(base)
    raw["nights"]["max"] = longest
    found = {p.check for p in _problems(raw, catalogs, tmp_path)}
    assert found == ({"package.window"} if fires else set())


def test_a_package_whose_group_changes_inside_the_window_gets_the_shorter_allowance() -> None:
    raw = _raw(S1)
    raw["nights"]["max"] = 8  # 9 days from the package day: too long for C (8), fine for B (10)
    pathway = load_text(yaml.safe_dump(raw, allow_unicode=True, sort_keys=False), "variant.yaml")
    ek2c = pl.DataFrame(
        {
            "code": ["P610131", "P610131"],
            "name": ["x", "x"],
            "group": ["B", "C"],
            "puan": [1.0, 1.0],
            "valid_from": ["2026-01-01", "2026-06-01"],
            "valid_to": ["2026-05-31", None],
        }
    )
    found = check_package_window(
        pathway, SimpleNamespace(ek2c=ek2c, window=("2026-02-01", "2026-09-30"))
    )
    assert [(p.check, "its window is 8 days" in p.message) for p in found] == [
        ("package.window", True)
    ]


def test_the_stays_tested_are_the_shortest_the_longest_and_the_showcase() -> None:
    assert _stay_cases(load_pathway(_DIR / f"{S2}.yaml")) == [4, 6, 9]
    assert _stay_cases(load_pathway(_DIR / f"{S7}.yaml")) == [None]


@pytest.mark.parametrize(
    ("start", "end", "fires"),
    [
        pytest.param("2026-03-09", "2026-03-15", False, id="the stay fills the window"),
        pytest.param("2026-03-10", "2026-03-15", True, id="admitted a day before the window"),
        pytest.param("2026-03-09", "2026-03-14", True, id="discharged a day after the window"),
    ],
)
def test_the_stay_may_fill_the_window_but_not_leave_it(
    start, end, fires, catalogs, tmp_path
) -> None:
    raw = _raw(S2)  # admitted 2026-03-09 for 6 nights
    raw["window"] = {"start": start, "end": end, "source": FIXTURE}
    found = {p.check for p in _problems(raw, catalogs, tmp_path)}
    assert found == ({"pins.window"} if fires else set())


def test_the_pins_of_an_encounter_obey_the_rules_of_the_pathways_own(catalogs: Catalogs) -> None:
    """`pins_problems` is `check_pins` for any pins: a recipe's pins for one encounter are judged alike."""
    pathway = load_pathway(_DIR / f"{S2}.yaml")  # admitted 2026-03-09 for 6 nights, age 81, a man
    assert check_pins(pathway, catalogs) == pins_problems(pathway, pathway.showcase, catalogs) == []
    later = pathway.showcase.model_copy(update={"admit": "2026-05-04", "nights": 7})
    assert pins_problems(pathway, later, catalogs) == []  # the same pathway on another date and for another stay
    for update, check in (
        ({"admit": "2026-01-15"}, "pins.window"),
        ({"admit": "2026-09-28", "nights": 6}, "pins.window"),  # leaves the window on the far side
        ({"age": 120}, "pins.out_of_range"),
        ({"nights": 10}, "pins.out_of_range"),
        ({"include": ["I10", "nowhere"]}, "pins.unknown_id"),
        ({"include": ["I10", "bed"]}, "pins.not_optional"),
    ):
        found = pins_problems(pathway, pathway.showcase.model_copy(update=update), catalogs)
        assert check in {p.check for p in found}, (update, [str(p) for p in found])
    # the pins given are the pins judged: the pathway's own are fine all the while
    assert check_pins(pathway, catalogs) == []


def test_a_window_equal_to_the_default_is_not_wider_than_it(catalogs: Catalogs, tmp_path) -> None:
    raw = _raw(S1)
    raw["window"] = {"start": catalogs.window[0], "end": catalogs.window[1], "source": FIXTURE}
    assert _problems(raw, catalogs, tmp_path) == []


@pytest.mark.parametrize(
    "edit",
    [
        pytest.param(lambda r: set_pins(r, age=55), id="the youngest pinned age"),
        pytest.param(lambda r: set_pins(r, age=90), id="the oldest pinned age"),
        pytest.param(lambda r: set_pins(r, nights=9), id="the longest pinned stay"),
        pytest.param(
            lambda r: set_pins(
                r,
                nights=4,
                course_days={"ceftriaxone": 5, "clarithromycin": 5, "methylprednisolone": 5},
            ),
            id="the shortest pinned stay with the shortest courses",
        ),
        pytest.param(
            lambda r: diagnosis(r, "I10")["optional"].update(probability=0.0), id="probability 0"
        ),
        pytest.param(
            lambda r: diagnosis(r, "I10")["optional"].update(probability=1.0), id="probability 1"
        ),
    ],
)
def test_a_value_on_the_edge_of_its_range_is_accepted(edit, catalogs: Catalogs, tmp_path) -> None:
    raw = _raw(S2)
    edit(raw)
    assert _problems(raw, catalogs, tmp_path) == []


def test_an_sut_source_may_cite_an_annex_instead_of_a_clause(catalogs: Catalogs, tmp_path) -> None:
    raw = _raw(S2)
    line(raw, "companion").update(
        source="EK-2B 510121 (Refakat): the doctor's order, as the story says."
    )
    assert _problems(raw, catalogs, tmp_path) == []


def test_probe_days_include_the_day_after_a_row_ends_when_a_gap_follows() -> None:
    rows = pl.DataFrame(
        {"valid_from": ["2026-01-01", "2026-05-01"], "valid_to": ["2026-04-09", None]}
    )
    assert probe_days(rows, "2026-02-01", "2026-09-30") == [
        "2026-02-01",
        "2026-04-09",
        "2026-04-10",
        "2026-05-01",
        "2026-09-30",
    ]


def _bed_rows(*rows: tuple[str, str | None, str]) -> tuple[pl.DataFrame, pl.DataFrame]:
    catalog = _frame(
        [("510010", name, start, end) for start, end, name in rows],
        *"code name valid_from valid_to".split(),
    )
    named = _frame(
        [("510010", "Standart yatak tarifesi", "procedures[bed]")], "code", "name", "where"
    )
    return catalog, named


def test_a_gap_in_the_catalog_inside_the_window_is_a_missing_code() -> None:
    catalog, named = _bed_rows(
        ("2026-01-01", "2026-04-09", "Standart yatak tarifesi"),
        ("2026-05-01", None, "Standart yatak tarifesi"),
    )
    found = identity_problems(named, catalog, ("2026-02-01", "2026-09-30"), "procedure")
    assert [(p.check, "2026-04-10" in p.message) for p in found] == [("procedure.in_force", True)]


def test_two_catalog_names_in_force_on_one_day_are_a_name_problem() -> None:
    catalog, named = _bed_rows(
        ("2026-01-01", None, "Standart yatak tarifesi"),
        ("2026-01-01", None, "Standart yatak tarifesi ücreti"),
    )
    found = identity_problems(named, catalog, ("2026-02-01", "2026-09-30"), "procedure")
    assert [p.check for p in found] == ["procedure.name"]


def test_a_band_table_in_the_middle_of_the_window_is_probed(catalogs: Catalogs) -> None:
    """The window's edges lie in the first and the last table; only the switch days reach the middle."""
    sets = copy.deepcopy(catalogs.code_sets)
    first, last = sets["surgical_group_bands"]
    middle = {"effective_from": "2026-03-01", "lower_bounds": {**first["lower_bounds"], "B": 7000}}
    sets["surgical_group_bands"] = [first, middle, {**last, "effective_from": "2026-06-01"}]
    ek2b = (
        pl.DataFrame(  # 6,471 puan: group B in the first and last table, group C in the middle one
            {
                "code": ["615931"],
                "name": ["Dar spinal kanalda unilateral dekompresyon"],
                "puan": [6471.03],
                "valid_from": ["2020-01-01"],
                "valid_to": [None],
            },
            schema_overrides={"valid_to": pl.String},
        )
    )
    fake = SimpleNamespace(code_sets=sets, window=catalogs.window, ek2b=ek2b)
    found = check_anaesthesia(load_pathway(_DIR / f"{S3}.yaml"), fake)
    assert [(p.check, "on 2026-03-01 " in p.message) for p in found] == [
        ("anaesthesia.group", True)
    ]


# --- the edges of the newborn grammar ---------------------------------------------------------------


def test_a_cot_is_a_newborn_bed_too(catalogs: Catalogs, tmp_path) -> None:
    """The cot 510081 is the other newborn bed: a stay may bill it on every day instead of the incubator."""
    raw = _raw(S12)
    line(raw, "incubator").update(code="510081", name="Kot (beşik)")
    assert _problems(raw, catalogs, tmp_path) == []


def test_a_newborn_stay_may_change_beds_between_days(catalogs: Catalogs, tmp_path) -> None:
    """Incubator on the first three days, the ward bed on the rest (the shape of the ward bill after a newborn stay)."""
    raw = _raw(S12)
    line(raw, "incubator").update(days="admit..admit+2")
    raw["procedures"].append(
        {"id": "bed", "kind": "bed", "code": "510010", "name": "Standart yatak tarifesi",
         "days": "admit+3..discharge", "basis": "judgment", "source": FIXTURE}
    )  # fmt: skip
    assert _problems(raw, catalogs, tmp_path) == []
    # the days must fit at every stay length: a ward bed fixed to the showcase's 5 nights does not
    line(raw, "bed").update(days="admit+3..admit+5")
    assert {p.check for p in _problems(raw, catalogs, tmp_path)} == {"stay.coverage", "days.in_stay"}


def stay_coverage_messages(raw: dict, catalogs: Catalogs, tmp_path) -> list[tuple[str, str]]:
    return sorted((p.where, p.message) for p in _problems(raw, catalogs, tmp_path) if p.check == "stay.coverage")


def test_a_newborn_stay_names_the_missing_and_the_doubled_bed_days(catalogs: Catalogs, tmp_path) -> None:
    raw = _raw(S12)
    fixed_nights(raw, 5)
    line(raw, "incubator").update(days="admit..discharge-2")  # days 0..3 of 0..5: days 4 and 5 have no bed
    raw["procedures"].append(icu_line("cot", "newborn_bed", "510081", "Kot (beşik)", "admit+3..admit+4"))  # day 3 twice
    assert stay_coverage_messages(raw, catalogs, tmp_path) == [
        (
            "procedures[incubator, cot]",
            "ward and newborn bed lines must cover admit..discharge once each; "
            "5 nights: no bed line on days [5], two bed lines on days [3]",
        )
    ]


def test_a_newborn_bed_beside_icu_lines_is_a_defect_of_its_own_and_the_bed_rule_stands_aside(
    catalogs: Catalogs, tmp_path
) -> None:
    """On an ICU stay the ICU lines are the beds: the incubator is named as a defect, and the union rule is not run."""
    raw = _raw(S12)
    fixed_nights(raw, 5)
    line(raw, "incubator").update(days="admit..discharge-1")  # on a newborn stay this would be named; here the ICU rule speaks
    raw["procedures"].append(icu_line("icu_again", "icu_package", "P552002", "İkinci basamak yoğun bakım hastası", "admit+1"))
    found = stay_coverage_messages(raw, catalogs, tmp_path)
    assert [where for where, _ in found] == ["procedures[icu_again]", "procedures[incubator]"]
    assert dict(found)["procedures[incubator]"] == (
        "a newborn bed line on an ICU stay: the ICU lines are the bed lines of the bill"
    )
    assert dict(found)["procedures[icu_again]"].startswith("ICU lines must cover admit..discharge-1 once each")
    assert not any("ward and newborn bed lines" in message for _, message in found)


def test_a_ward_bed_beside_icu_lines_keeps_its_own_wording(catalogs: Catalogs, tmp_path) -> None:
    raw = _raw(S11)
    raw["procedures"].append({"id": "bed", "kind": "bed", "code": "510010", "name": "Standart yatak tarifesi",
                              "days": "admit..discharge", "basis": "judgment", "source": FIXTURE})  # fmt: skip
    assert dict(stay_coverage_messages(raw, catalogs, tmp_path))["procedures[bed]"] == (
        "a ward bed line on an ICU stay: the ICU lines are the bed lines of the bill"
    )


def test_a_newborn_bed_on_an_er_visit_needs_a_stay(catalogs: Catalogs, tmp_path) -> None:
    raw = _raw(S7)
    raw["procedures"].append(icu_line("incubator_visit", "newborn_bed", "510070", "Kuvöz", "admit"))
    assert stay_coverage_messages(raw, catalogs, tmp_path) == [
        ("procedures[incubator_visit]", "a newborn bed line needs a stay, not an ER visit")
    ]


def test_a_package_bill_names_the_newborn_bed_as_a_line_the_package_includes(catalogs: Catalogs) -> None:
    """In a package bill the incubator line is inside the package, named apart from the companion and the exam."""
    raw = _raw(S12)
    raw["billing_mode"] = "package"
    pathway = load_text(yaml.safe_dump(raw, allow_unicode=True, sort_keys=False), f"{S12}.yaml")
    problems = {p.where: p.message for p in check_package_mode(pathway, catalogs)}
    assert set(problems) == {"procedures[incubator]", "procedures[companion]", "procedures[pediatric_consult]"}
    assert problems["procedures[incubator]"].startswith("a newborn_bed line is inside the package")


def test_the_newborn_bed_is_the_incubator_or_the_cot_of_the_code_sets() -> None:
    sets = yaml.safe_load((_REPO / "data/synthetic/reference/code_sets.yaml").read_text(encoding="utf-8"))
    assert (sets["beds"]["incubator"]["code"], sets["beds"]["cot"]["code"]) == ("510070", "510081")


def test_a_newborn_bed_and_a_ward_bed_are_the_bed_kinds() -> None:
    from scripts.synthetic.pathways.schema import BED_KINDS, ICU_KINDS

    assert BED_KINDS == ("bed", "newborn_bed")
    assert not set(BED_KINDS) & set(ICU_KINDS)


# --- the edges of the ICU grammar --------------------------------------------------------------------


@pytest.mark.parametrize(
    ("nights", "end_days"),
    [
        pytest.param(1, "admit", id="one night: the first ICU day is the last"),
        pytest.param(2, ["admit", "discharge-1"], id="two nights: no day between"),
    ],
)
def test_a_short_icu_stay_has_the_end_days_and_no_package_day(
    nights, end_days, catalogs: Catalogs, tmp_path
) -> None:
    raw = _raw(S11)
    raw["procedures"] = [p for p in raw["procedures"] if p["id"] != "icu_package"]
    line(raw, "icu_end_days").update(days=end_days)
    fixed_nights(raw, nights)
    assert _problems(raw, catalogs, tmp_path) == []


def test_a_one_night_stay_cannot_use_the_two_end_days(catalogs: Catalogs, tmp_path) -> None:
    """[admit, discharge-1] is day 0 twice at one night: a line may not land twice on a day."""
    raw = _raw(S11)
    raw["procedures"] = [p for p in raw["procedures"] if p["id"] != "icu_package"]
    fixed_nights(raw, 1)
    found = {p.check for p in _problems(raw, catalogs, tmp_path)}
    assert found == {"days.duplicate", "stay.coverage", "icu.day_pattern"}  # the one line is on day 0 twice


def test_the_package_window_leaves_an_icu_package_alone(catalogs: Catalogs) -> None:
    """An ICU package has no EK-2C group, so it has no window; the same code as a surgical package has none either."""
    raw = _raw(S11)
    raw["billing_mode"] = "package"
    pathway = load_text(yaml.safe_dump(raw, allow_unicode=True, sort_keys=False), f"{S11}.yaml")
    assert check_package_window(pathway, catalogs) == []
    line(raw, "icu_package")["kind"] = "package"
    as_package = load_text(yaml.safe_dump(raw, allow_unicode=True, sort_keys=False), f"{S11}.yaml")
    found = check_package_window(as_package, catalogs)
    assert [p.check for p in found] == ["package.window"] and "no group in EK-2C" in found[0].message


def test_a_package_bill_names_each_icu_line_as_a_line_the_package_includes(catalogs: Catalogs) -> None:
    """In a package bill an ICU line of either kind is inside the package, not only a lab or a drug."""
    raw = _raw(S11)
    raw["billing_mode"] = "package"
    pathway = load_text(yaml.safe_dump(raw, allow_unicode=True, sort_keys=False), f"{S11}.yaml")
    named = {p.where for p in check_package_mode(pathway, catalogs)}
    assert {"procedures[icu_end_days]", "procedures[icu_package]"} <= named

