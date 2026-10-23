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
    check_sessions,
    identity_problems,
    in_force,
    norm,
    pins_problems,
    probe_days,
    run_all,
)
from scripts.synthetic.pathways.expand import SESSION_RATIOS, expand
from scripts.synthetic.pathways.loader import hygiene
from scripts.synthetic.pathways.schema import (
    BLOOD_PACKAGE_SHARES,
    CHECKS,
    DrugFlags,
    MaterialFlags,
    Pathway,
    ProcedureFlags,
    pin_problems,
)
from src.bilun.domain.claims.models import DrugClaimLine, MaterialClaimLine, ProcedureClaimLine
from src.bilun.domain.materials.ek4a_as_of import ek4a_as_of
from src.bilun.domain.prose_rules.blood_component_isbt128 import is_valid_isbt128_barcode

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
S14 = "urosepsis_ward_stay_after_icu_transfer"  # a ward stay that arrives from an ICU bill: its bed starts the day after admission
S39 = "pyelonephritis_dementia_post_discharge_control"  # a control visit (poliklinik): one date, no stay
S45 = "parkinson_neurology_control_first_walker"  # a visit with an EK-3/C-2 device (slice G7b): the walker OP1106
S47 = "syncope_er_observation_under_24_hours"  # a stay of one date (nights 0): admission and discharge on 2026-02-25
S20 = "umbilical_hernia_day_case_package"  # the first gunubirlik pathway: a day case billed as the EK-2C package
S32 = "copd_exacerbation_post_discharge_control"  # S2's control visit: its examination carries the patient's share (G5b)
S33 = "copd_exacerbation_readmission_through_er"  # S2's readmission through the ER: the critical ER bed, then the ward
S34 = "copd_exacerbation_post_readmission_control"  # the control after it: its examination is the line of a G5a fault
S17 = "end_stage_kidney_disease_haemodialysis_month"  # a month of P704230 sessions as one gunubirlik claim with a span, and an ESA
S23 = "end_stage_kidney_disease_emergency_haemodialysis"  # one emergency session P704210, a package stay of one date
S22 = "gi_bleed_admission_colonoscopy"  # a colonoscopy session: the colonoscopy leads, the polypectomy is a chapter-7 add-on at 50 %


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


def test_only_the_pathways_of_patient_2_pin_the_chronic_report() -> None:
    """The report is a fact about the patient (its copay profile): S2's stay and its control (S32) carry it, every
    other pathway leaves it unknown."""
    pinned = {p.stem: load_pathway(p).showcase.chronic_health_report for p in _FILES}
    assert {stem: value for stem, value in pinned.items() if value is not None} == {
        S2: True,
        S32: True,
        S33: True,
        S34: True,
    }


def test_the_copay_share_of_a_line_reaches_its_expansion_and_no_other_line(catalogs: Catalogs) -> None:
    """S32's examination carries the patient's share (slice G5b); the expansion writes `copay_rate` on that line only."""
    pathway = load_pathway(_DIR / f"{S32}.yaml")
    (exam,) = pathway.procedures
    assert (exam.code, exam.copay.rate, exam.copay.basis) == ("520030", Decimal("0.20"), "judgment")
    assert [row["copay_rate"] for row in expand(pathway)["procedures"]] == ["0.20"]
    assert run_all(pathway, catalogs) == []
    with_copay = [p.stem for p in _FILES if any(x.copay is not None for x in load_pathway(p).procedures)]
    assert with_copay == [S32]
    assert all("copay_rate" not in row for p in _FILES if p.stem != S32 for row in expand(load_pathway(p))["procedures"])


@pytest.mark.parametrize(
    ("rate", "kind"),
    [
        (0, "schema.bad_value"),
        (1, "schema.bad_value"),
        (1.2, "schema.bad_value"),
        (-0.2, "schema.bad_value"),
        (0.125, "schema.bad_value"),  # the claim loader reads the rate to the cent
        ("x", "schema.bad_value"),
        (True, "schema.bad_value"),
    ],
)
def test_a_copay_rate_that_is_no_share_with_two_decimals_is_a_bad_value(rate: object, kind: str) -> None:
    raw = _raw(S32)
    raw["procedures"][0]["copay"]["rate"] = rate
    body = yaml.safe_dump(raw, allow_unicode=True, sort_keys=False)
    with pytest.raises(PathwayLoadError) as error:
        load_text(body, f"{S32}.yaml")
    assert [p.check for p in error.value.problems] == [kind]
    assert "procedures[exam].copay.rate" in str(error.value)


def test_a_copay_share_needs_its_basis_and_source() -> None:
    raw = _raw(S32)
    del raw["procedures"][0]["copay"]["source"]
    body = yaml.safe_dump(raw, allow_unicode=True, sort_keys=False)
    with pytest.raises(PathwayLoadError) as error:
        load_text(body, f"{S32}.yaml")
    assert [p.check for p in error.value.problems] == ["schema.missing_field"]


@pytest.mark.parametrize("value", [True, False])
def test_the_chronic_report_pin_is_a_bool_and_trips_no_check(value: bool, catalogs: Catalogs) -> None:
    raw = _raw(S3)
    raw["showcase"]["chronic_health_report"] = value
    body = yaml.safe_dump(raw, allow_unicode=True, sort_keys=False)
    pathway = load_text(body, f"{S3}.yaml")
    assert pathway.showcase.chronic_health_report is value
    assert run_all(pathway, catalogs) == []


@pytest.mark.parametrize("value", ["evet", "true", 1, 0])
def test_a_chronic_report_pin_that_is_not_a_bool_is_a_bad_value(value: object) -> None:
    raw = _raw(S3)
    raw["showcase"]["chronic_health_report"] = value
    body = yaml.safe_dump(raw, allow_unicode=True, sort_keys=False)
    with pytest.raises(PathwayLoadError) as error:
        load_text(body, f"{S3}.yaml")
    assert [p.check for p in error.value.problems] == ["schema.bad_value"]
    assert "showcase.chronic_health_report" in str(error.value)


def test_no_committed_pathway_sets_a_line_flag_of_slice_g5a_but_the_isbt128_numbers_of_s24_and_s42() -> None:
    """The flags of slice G5a are fault material: a clean bill bills no exam as a package component and no material
    that waits for an approval (S34's fault sets the first with `set_flag`). The ISBT 128 number of a blood line is
    the one clean flag: the red-cell units of S24 and S42 carry theirs (S24's fault clears them)."""
    transfused = {"decompensated_cirrhosis_variceal_rebleed_transfusion", "infected_hemiarthroplasty_removal_package"}
    for path in _FILES:
        pathway = load_pathway(path)
        blood = {"705371"} if path.stem in transfused else set()
        assert all(p.flags == ProcedureFlags() for p in pathway.procedures if p.code not in blood), path.stem
        assert all(p.flags.isbt128_barcode and not p.flags.is_package_included for p in pathway.procedures if p.code in blood)
        assert all(m.flags.requires_pre_auth is None for m in pathway.materials), path.stem
        assert all(row["flags"] == {} for row in expand(pathway)["procedures"] if row["code"] not in blood), path.stem


@pytest.mark.parametrize(
    ("flags", "expected"),
    [
        ({"is_package_included": True}, {"is_package_included": True}),
        ({"is_package_included": False}, {"is_package_included": False}),
        ({"isbt128_barcode": "=A9999261234560"}, {"isbt128_barcode": "=A9999261234560"}),
        ({}, {}),
    ],
)
def test_the_flags_of_a_procedure_line_reach_its_expansion_and_no_other_line(
    flags: dict, expected: dict, catalogs: Catalogs
) -> None:
    raw = _raw(S34)
    raw["procedures"][0]["flags"] = flags
    body = yaml.safe_dump(raw, allow_unicode=True, sort_keys=False)
    pathway = load_text(body, f"{S34}.yaml")
    assert [row["flags"] for row in expand(pathway)["procedures"]] == [expected]
    assert run_all(pathway, catalogs) == []
    s2 = load_pathway(_DIR / f"{S2}.yaml")
    assert all(row["flags"] == {} for row in expand(s2)["procedures"])


def test_a_material_may_be_flagged_as_waiting_for_an_approval(catalogs: Catalogs) -> None:
    raw = _raw(S5)
    raw["materials"][0].setdefault("flags", {})["requires_pre_auth"] = True
    body = yaml.safe_dump(raw, allow_unicode=True, sort_keys=False)
    pathway = load_text(body, f"{S5}.yaml")
    flagged = [m for m in expand(pathway)["materials"] if m["flags"].get("requires_pre_auth")]
    assert [m["code"] for m in flagged] == [pathway.materials[0].code]


@pytest.mark.parametrize(
    ("flags", "check", "where"),
    [
        ({"is_package_included": "evet"}, "schema.bad_value", "flags.is_package_included"),
        ({"isbt128_barcode": 1234}, "schema.bad_value", "flags.isbt128_barcode"),
        ({"package_component": True}, "schema.unknown_field", "flags.package_component"),
    ],
)
def test_a_procedure_flag_of_the_wrong_type_or_name_is_refused(flags: dict, check: str, where: str) -> None:
    raw = _raw(S34)
    raw["procedures"][0]["flags"] = flags
    body = yaml.safe_dump(raw, allow_unicode=True, sort_keys=False)
    with pytest.raises(PathwayLoadError) as error:
        load_text(body, f"{S34}.yaml")
    assert [p.check for p in error.value.problems] == [check]
    assert where in str(error.value)


def test_a_package_line_is_never_its_own_package_component() -> None:
    """`is_package_included` marks a component bundled into a package, never the package line (#260)."""
    raw = _raw(S1)
    raw["procedures"][0]["flags"] = {"is_package_included": True}
    assert raw["procedures"][0]["kind"] == "package"
    body = yaml.safe_dump(raw, allow_unicode=True, sort_keys=False)
    with pytest.raises(PathwayLoadError) as error:
        load_text(body, f"{S1}.yaml")
    assert [p.check for p in error.value.problems] == ["schema.line_shape"]
    assert "never the package line" in str(error.value)


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
    procedure = {f.name for f in dataclasses.fields(ProcedureClaimLine)}
    material = {f.name for f in dataclasses.fields(MaterialClaimLine)}
    drug = {f.name for f in dataclasses.fields(DrugClaimLine)}
    assert set(ProcedureFlags.model_fields) == {"is_package_included", "isbt128_barcode"} <= procedure
    assert "requires_pre_auth" in MaterialFlags.model_fields
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


def test_the_ek3c2_list_is_in_force_only_from_its_own_date(catalogs: Catalogs) -> None:
    """Slice G7b: the curated EK-3/C-2 list is the raw partition of 2026-01-24; its name is the device's alone."""
    from scripts.synthetic.pathways.checks import EK3C2_FROM

    occurrences = _frame([("OP1106", "WALKER (ALÜMİNYUM)(HAREKETLİ-SABİT-TERS)", "materials[walker]")], "code", "name", "where")
    assert EK3C2_FROM == "2026-01-24"
    assert (_REPO / "data/gazette/raw/annex=EK-3C-2/effective_date=2026-01-24").is_dir()
    assert identity_problems(occurrences, catalogs.ek3c2, ("2026-02-01", "2026-09-30"), "material") == []
    early = identity_problems(occurrences, catalogs.ek3c2, ("2026-01-01", "2026-01-31"), "material")
    assert [p.check for p in early] == ["material.in_force"]
    assert "2026-01-01" in early[0].message
    # each annex is its own list: the walker is no EK-3/F-1 code, the femoral stem no EK-3/C-2 code
    assert [p.check for p in identity_problems(occurrences, catalogs.ek3f1, ("2026-02-01", "2026-09-30"), "material")] == ["material.in_force"]
    assert catalogs.ek3("EK-3C-2") is catalogs.ek3c2 and catalogs.ek3("EK-3F-1") is catalogs.ek3f1


def test_only_an_ek3c2_material_writes_its_annex_on_the_expanded_row() -> None:
    """The annex is an optional golden key: S5's EK-3/F-1 rows carry none, S45's walker carries `EK-3C-2`."""
    (walker,) = expand(load_pathway(_DIR / f"{S45}.yaml"))["materials"]
    assert (walker["annex"], walker["material_type"]) == ("EK-3C-2", "ortez")
    assert walker["linked_procedure"] == {"code": "520030", "date": "2026-06-29"}  # the examination of the visit
    assert all("annex" not in row for row in expand(load_pathway(_DIR / f"{S5}.yaml"))["materials"])


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


def with_er_course(raw: dict, cat: Catalogs) -> None:  # on S7 and S39: a one-day course on a visit
    raw.setdefault("drugs", []).append(
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


def with_span(raw: dict, cat: Catalogs) -> None:  # on S39: a poliklinik session claim over 2..5 days after the first
    raw["span"] = {"min": 2, "max": 5, "basis": "judgment", "source": FIXTURE}
    raw["showcase"]["span"] = 3


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
    Case("schema.bad_enum", S39, lambda r, c: r.update(claim_type="ayaktan"), label="a claim type that is no visit either"),
    Case("schema.bad_enum", S45, lambda r, c: r["materials"][0].update(annex="EK-3C-3"), label="an EK-3 annex the cohort does not price"),
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
    Case("schema.unknown_reference", S45, lambda r, c: r["materials"][0].update(annex="EK-3F-1", material_type="implant"), label="an EK-3/F-1 material on an examination"),
    Case("schema.unknown_reference", S1, lambda r, c: r["materials"][0].update(annex="EK-3C-2", material_type="ortez"), prepare=with_material, label="an EK-3/C-2 device on a package"),
    Case("schema.unknown_reference", S2, lambda r, c: line(r, "anaesthesia").update(operations=["bed"]), prepare=with_anaesthesia, label="anaesthesia"),
    Case("schema.unknown_reference", S1, lambda r, c: line(r, "appendectomy_package").update(optional=chance()), prepare=with_material, label="a material on an optional package"),
    Case("schema.unknown_reference", S3, lambda r, c: line(r, "laminectomy").update(optional=chance()), prepare=with_two_operations, label="an anaesthesia line on an optional operation"),
    Case("schema.unknown_reference", S3, lambda r, c: line(r, "laminectomy").update(code="615931", name=ek2b_name(c, "615931")), prepare=with_two_operations, label="two operations with one code"),
    Case("schema.anchor_undefined", S2, lambda r, c: line(r, "bed").update(days="op"), label="op"),
    Case("schema.anchor_undefined", S3, lambda r, c: r.update(op_day="op+1"), label="op_day defined from op"),
    Case("schema.anchor_undefined", S1, lambda r, c: (r.update(claim_type="acil"), r.pop("nights"), line(r, "appendectomy_package").update(days="discharge")), label="discharge on an ER-only pathway"),
    Case("schema.anchor_undefined", S39, lambda r, c: line(r, "exam").update(days="discharge"), label="discharge on a poliklinik pathway"),
    Case("schema.anchor_undefined", S39, lambda r, c: (r.update(claim_type="gunubirlik"), line(r, "exam").update(days="discharge-1")), label="discharge on a gunubirlik pathway"),
    Case("schema.line_shape", S2, lambda r, c: line(r, "chest_xray").update(session_role="primary"), label="role on imaging"),
    Case("schema.line_shape", S45, lambda r, c: r["materials"][0].update(material_type="implant"), label="an EK-3/C-2 device typed as an implant"),
    Case("schema.line_shape", S1, lambda r, c: r["materials"][0].update(material_type="ortez"), prepare=with_material, label="an EK-3/F-1 material typed as an orthosis"),
    Case("schema.line_shape", S2, lambda r, c: line(r, "bed").update(group="B"), label="group on a bed"),
    Case("schema.line_shape", S22, lambda r, c: line(r, "admission_hemogram").update(session_role="primary"), label="a role on a lab line"),
    Case("schema.line_shape", S1, lambda r, c: line(r, "appendectomy_package").update(session_role="primary", days=["op", "op+1"]), label="a role on a two-day line"),
    Case("schema.line_shape", S2, lambda r, c: line(r, "cbc_crp")["items"].append(dict(line(r, "cbc_crp")["items"][0])), label="a panel with a code twice"),
    Case("schema.line_shape", S2, lambda r, c: line(r, "blood_gas").update(items=[{"code": "L106150", "name": "Potasyum (Serum/Plazma)"}, {"code": "L106910", "name": "Sodyum (Serum/Plazma)"}]), label="code and items"),
    Case("schema.quantity_form", S2, lambda r, c: drug(r, "ceftriaxone").update(qty=7)),
    Case("schema.diagnosis_primary", S2, lambda r, c: diagnosis(r, "J18.9").update(role="primary")),
    Case("schema.diagnosis_primary", S2, lambda r, c: diagnosis(r, "J44.0").update(optional=chance()), label="an optional primary"),
    Case("schema.stay_shape", S2, lambda r, c: r.pop("nights")),
    Case("schema.stay_shape", S7, lambda r, c: r.update(nights={"min": 1, "max": 2, "basis": "judgment", "source": FIXTURE}), label="nights on an ER-only pathway"),
    Case("schema.stay_shape", S7, lambda r, c: per_night_instead_of_course(r), prepare=with_er_course, label="a per_night drug on an ER-only visit"),
    Case("schema.stay_shape", S7, lambda r, c: r.update(arrives_from_icu=True), label="an ER-only pathway that arrives from an ICU"),
    Case("schema.stay_shape", S39, lambda r, c: r.update(nights={"min": 1, "max": 2, "basis": "judgment", "source": FIXTURE}), label="nights on a poliklinik pathway"),
    Case("schema.stay_shape", S39, lambda r, c: (r.update(claim_type="gunubirlik"), r.update(nights={"min": 1, "max": 2, "basis": "judgment", "source": FIXTURE})), label="nights on a gunubirlik pathway"),
    Case("schema.stay_shape", S39, lambda r, c: per_night_instead_of_course(r), prepare=with_er_course, label="a per_night drug on a poliklinik visit"),
    Case("schema.stay_shape", S39, lambda r, c: r.update(arrives_from_icu=True), label="a poliklinik pathway that arrives from an ICU"),
    Case("schema.stay_shape", S39, lambda r, c: r.update(claim_type="yatis"), label="a yatis pathway without nights (the visit type was the only thing that kept it a visit)"),
    # --- G3: a stay of one date (nights 0) and a session claim over several dates (span)
    Case("schema.stay_shape", S7, lambda r, c: r.update(span={"min": 2, "max": 4, "basis": "judgment", "source": FIXTURE}), label="a span on an ER visit"),
    Case("schema.stay_shape", S2, lambda r, c: r.update(span={"min": 2, "max": 4, "basis": "judgment", "source": FIXTURE}), label="a span on a stay"),
    Case("schema.stay_shape", S2, lambda r, c: r["nights"].update(min=0), label="a per_night drug on a stay that may have no night"),
    # --- catalog identity
    Case("procedure.in_force", S2, lambda r, c: line(r, "bed").update(code="510019"), label="no such code"),
    Case("procedure.in_force", S2, lambda r, c: swap_in(r, "nebulizer", "701068", c), label="listed from 2026-07-07"),
    Case("procedure.name", S2, lambda r, c: line(r, "bed").update(name="Standart yatak ücreti")),
    Case("procedure.name", S2, lambda r, c: r["performed"][0].update(name="Akciğer grafisi"), prepare=with_performed, label="performed line"),
    Case("procedure.in_force", S2, lambda r, c: r["performed"][0].update(code="801729"), prepare=with_performed, label="performed line"),
    Case("procedure.name", S1, lambda r, c: line(r, "appendectomy_package").update(name="Appendektomi"), label="package"),
    Case("procedure.kind", S2, lambda r, c: line(r, "nebulizer").update(kind="lab")),
    Case("procedure.kind", S22, lambda r, c: line(r, "polypectomy").update(code="530080", name="Damar yolu açılması"), label="a role on a procedure outside chapter 7"),
    Case("procedure.kind", S22, lambda r, c: line(r, "colonoscopy").update(code="530080", name="Damar yolu açılması"), also=("session.order",), label="the primary of a session outside chapter 7"),
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
    # --- G7b: an EK-3/C-2 device is read on its own list
    Case("material.in_force", S45, lambda r, c: r["materials"][0].update(code="AP2000"), label="an EK-3/F-1 code on the EK-3/C-2 list"),
    Case("material.name", S45, lambda r, c: r["materials"][0].update(name="WALKER (ALÜMİNYUM)"), label="an EK-3/C-2 name"),
    Case("material.name", S45, lambda r, c: r["materials"][0].update(name="WALKER (ALÜMİNYUM)(HAREKETLİ-SABİT-TERS) | Fiziksel tıp ve rehabilitasyon"), label="an EK-3/C-2 name with its description"),
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
    Case("session.primary", S22, lambda r, c: line(r, "polypectomy").update(session_role="primary"), label="two primary procedures of one colonoscopy"),
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
    Case("pins.out_of_range", S39, lambda r, c: set_pins(r, span=9), prepare=with_span, label="span"),
    Case("pins.out_of_range", S39, lambda r, c: set_pins(r, span=3), label="a span pin on a pathway without a span range"),
    Case("pins.missing", S39, lambda r, c: r["showcase"].pop("span"), prepare=with_span, label="span"),
    Case("pins.window", S39, lambda r, c: set_pins(r, admit="2026-09-28"), prepare=with_span, label="a span that ends after the window"),
    Case("pins.window", S2, lambda r, c: set_pins(r, admit="2026-01-15")),
    # --- days, sources, window
    Case("days.in_stay", S2, lambda r, c: line(r, "nebulizer").update(days="admit..discharge+1"), label="past the discharge day"),
    Case("days.in_stay", S2, lambda r, c: line(r, "chest_xray").update(days="admit+3..admit+1"), label="an empty range"),
    Case("days.in_stay", S2, lambda r, c: line(r, "chest_xray").update(days=["admit", "admit+5"]), label="outside the shortest stay only"),
    Case("days.in_stay", S39, lambda r, c: line(r, "urine_culture").update(days="admit+4"), prepare=with_span, label="outside the shortest span only"),
    Case("days.in_stay", S47, lambda r, c: line(r, "ecg").update(days="admit+1"), label="the day after a stay of one date"),
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
    # a ward stay that arrives from an ICU bill (S14): the bed lines cover admit+1..discharge, the transfer day is the ICU bill's
    Case("stay.coverage", S14, lambda r, c: line(r, "bed").update(days="admit..discharge"), label="an arrival whose bed also covers the transfer day"),
    Case("stay.coverage", S14, lambda r, c: line(r, "bed").update(days="admit+2..discharge"), label="an arrival whose bed starts a day late"),
    Case("stay.coverage", S14, lambda r, c: line(r, "bed").update(days="admit+1..discharge-1"), label="an arrival whose bed drops the discharge day"),
    Case("stay.coverage", S14, lambda r, c: line(r, "bed").update(days="admit+1..admit+3"), label="an arrival whose bed is fixed to the showcase nights", also=("days.in_stay",)),
    Case("stay.coverage", S14, lambda r, c: line(r, "companion").update(days="admit+1..discharge-1"), label="an arrival whose companion starts a day late"),
    Case("stay.coverage", S14, lambda r, c: r["procedures"].append(icu_line("cot", "newborn_bed", "510081", "Kot (beşik)", "admit+1")), label="a newborn bed on a stay that arrives from an ICU", also=()),
    Case("stay.coverage", S14, lambda r, c: r["procedures"].append(icu_line("icu_again", "icu_day", "510090", "Yoğun bakım", "admit")), label="an ICU line on a stay that arrives from an ICU", also=("icu.day_pattern",)),
    Case("stay.coverage", S2, lambda r, c: line(r, "bed").update(days="admit+1..discharge"), label="a bed that skips the admission day and arrives from nowhere"),
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
        pathway, SimpleNamespace(ek2c=ek2c, window=("2026-02-01", "2026-09-30"), code_sets={"dialysis_packages": {}})
    )
    assert [(p.check, "its window is 8 days" in p.message) for p in found] == [
        ("package.window", True)
    ]


def test_the_stays_tested_are_the_shortest_the_longest_and_the_showcase() -> None:
    assert _stay_cases(load_pathway(_DIR / f"{S2}.yaml")) == [4, 6, 9]
    assert _stay_cases(load_pathway(_DIR / f"{S7}.yaml")) == [None]
    assert _stay_cases(load_pathway(_DIR / f"{S39}.yaml")) == [None]  # a visit has no stay to test
    assert _stay_cases(load_pathway(_DIR / f"{S47}.yaml")) == [0]  # a stay of one date is a stay: 0 is no missing stay


# --- G3: a stay of one date (nights 0) and a session claim over several dates (span) ----------------------------


def test_a_stay_of_one_date_is_admitted_and_discharged_on_that_date_with_one_day_bed(catalogs: Catalogs, tmp_path) -> None:
    pathway = load_pathway(_DIR / f"{S47}.yaml")
    assert (pathway.claim_type, pathway.nights.min, pathway.nights.max, pathway.showcase.nights) == ("yatis", 0, 0, 0)
    assert run_all(pathway, catalogs) == []
    bill = expand(pathway)
    header = bill["header"]
    assert (header["admission_date"], header["discharge_date"]) == ("2026-02-25", "2026-02-25")
    assert (header["claim_start_date"], header["claim_end_date"]) == ("2026-02-25", "2026-02-25")
    assert [(r["code"], r["date"]) for r in bill["procedures"] if r["code"] in ("510010", "510120")] == [("510120", "2026-02-25")]
    assert {r["date"] for r in bill["procedures"]} == {"2026-02-25"}
    # a companion line has no night to cover; a bed line that stops before the discharge misses the one day
    raw = _raw(S47)
    raw["procedures"].append(
        {"id": "companion", "kind": "companion", "code": "510121", "name": "Refakat", "days": "admit..discharge-1",
         "basis": "judgment", "source": FIXTURE}
    )
    assert {p.check for p in _problems(raw, catalogs, tmp_path)} == {"days.in_stay"}
    raw = _raw(S47)
    line(raw, "day_bed").update(days="admit..discharge-1")
    assert {p.check for p in _problems(raw, catalogs, tmp_path)} == {"days.in_stay", "stay.coverage"}


def test_nights_and_their_pin_take_zero_and_a_stay_without_a_pin_is_still_missing_it() -> None:
    pathway = load_pathway(_DIR / f"{S47}.yaml")
    assert pin_problems(pathway, pathway.showcase) == []
    pins = pathway.showcase.model_copy(update={"nights": None})
    assert [(p.check, p.where) for p in pin_problems(pathway, pins)] == [("pins.missing", "showcase.nights")]
    two = load_pathway(_DIR / f"{S2}.yaml")
    found = [(p.check, p.where) for p in pin_problems(two, two.showcase.model_copy(update={"nights": 0}))]
    assert found[0] == ("pins.out_of_range", "showcase.nights")  # 0 is outside S2's 4..9: refused like any other number


def test_a_session_claim_spans_its_dates_without_a_stay(catalogs: Catalogs, tmp_path) -> None:
    raw = _raw(S39)
    with_span(raw, catalogs)
    line(raw, "urine_culture").update(days="admit+2")  # the culture read on a later session day
    body = yaml.safe_dump(raw, allow_unicode=True, sort_keys=False)
    pathway = load_text(body, f"{S39}.yaml")
    assert run_all(pathway, catalogs) == []
    bill = expand(pathway)
    header = bill["header"]
    assert (header["admission_date"], header["discharge_date"]) == (None, None)  # a visit, not a stay
    assert (header["claim_start_date"], header["claim_end_date"]) == ("2026-05-25", "2026-05-28")  # admit + span 3
    assert {r["code"]: r["date"] for r in bill["procedures"]}["905671"] == "2026-05-27"
    longer = expand(pathway, pathway.showcase.model_copy(update={"span": 5}))
    assert longer["header"]["claim_end_date"] == "2026-05-30" and longer["procedures"] == bill["procedures"]
    # a span is a pin of a pathway with a span range only, and the range is what it is checked against
    assert [p.check for p in pin_problems(pathway, pathway.showcase.model_copy(update={"span": None}))] == ["pins.missing"]
    plain = load_pathway(_DIR / f"{S39}.yaml")
    assert [p.check for p in pin_problems(plain, plain.showcase.model_copy(update={"span": 2}))] == ["pins.out_of_range"]


def test_a_drug_course_may_run_to_the_last_day_of_a_session_claim(catalogs: Catalogs, tmp_path) -> None:
    raw = _raw(S39)
    with_span(raw, catalogs)
    with_er_course(raw, catalogs)  # a per_day course on the visit (fixture)
    d = raw["drugs"][-1]
    d["course_days"].update(min=1, max=4)
    raw["showcase"]["course_days"] = {d["id"]: 4}
    body = yaml.safe_dump(raw, allow_unicode=True, sort_keys=False)
    pathway = load_text(body, f"{S39}.yaml")
    # a 4-day course fits the pinned span of 3 (days 0..3); a span of 2 ends a day before it (the shortest course, 1
    # day, fits every span, so the checks of the file pass)
    assert run_all(pathway, catalogs) == []
    assert pin_problems(pathway, pathway.showcase) == []
    assert [p.check for p in pin_problems(pathway, pathway.showcase.model_copy(update={"span": 2}))] == ["drug.course"]


# --- the visit grammar (G1): acil, poliklinik and gunubirlik are visits, yatis is the only stay ---------------


@pytest.mark.parametrize("claim_type", ["acil", "poliklinik", "gunubirlik"])
def test_every_claim_type_but_yatis_is_a_visit_with_one_date_and_no_stay(
    claim_type: str, catalogs: Catalogs, tmp_path
) -> None:
    raw = _raw(S39)
    raw["claim_type"] = claim_type
    assert _problems(raw, catalogs, tmp_path) == []
    bill = expand(load_text(yaml.safe_dump(raw, allow_unicode=True, sort_keys=False), f"{S39}.yaml"))
    assert bill["header"] == {
        "claim_type": claim_type,
        "department": "İç Hastalıkları",
        "admission_date": None,
        "discharge_date": None,
        "claim_start_date": "2026-05-25",
        "claim_end_date": "2026-05-25",
        "primary_icd10": "N10",
    }
    assert {line["date"] for line in bill["procedures"]} == {"2026-05-25"}  # the visit day is the only day


def test_the_claim_types_a_pathway_may_have_are_the_stay_and_the_three_visits() -> None:
    from typing import get_args

    from scripts.synthetic.pathways.schema import Pathway

    assert get_args(Pathway.model_fields["claim_type"].annotation) == ("yatis", "acil", "poliklinik", "gunubirlik")


@pytest.mark.parametrize("claim_type", ["acil", "poliklinik", "gunubirlik"])
def test_the_defects_of_a_visit_name_its_claim_type(claim_type: str) -> None:
    raw = _raw(S39)
    raw["claim_type"] = claim_type
    raw["nights"] = {"min": 1, "max": 2, "basis": "judgment", "source": FIXTURE}
    with pytest.raises(PathwayLoadError) as error:
        load_text(yaml.safe_dump(raw, allow_unicode=True, sort_keys=False), f"{S39}.yaml")
    assert [p.check for p in error.value.problems] == ["schema.stay_shape"]
    assert f"a {claim_type} pathway has no nights" in str(error.value)
    del raw["nights"]
    raw["arrives_from_icu"] = True
    with pytest.raises(PathwayLoadError) as error:
        load_text(yaml.safe_dump(raw, allow_unicode=True, sort_keys=False), f"{S39}.yaml")
    assert f"a {claim_type} pathway cannot arrive from an ICU" in str(error.value)
    del raw["arrives_from_icu"]
    line(raw, "exam")["days"] = "discharge"
    with pytest.raises(PathwayLoadError) as error:
        load_text(yaml.safe_dump(raw, allow_unicode=True, sort_keys=False), f"{S39}.yaml")
    assert [p.check for p in error.value.problems] == ["schema.anchor_undefined"]
    assert f"uses discharge on a {claim_type} pathway" in str(error.value)


def test_a_yatis_pathway_keeps_its_discharge_anchor_and_a_visit_pin_of_nights_is_refused() -> None:
    stay = _raw(S2)
    assert load_text(yaml.safe_dump(stay, allow_unicode=True, sort_keys=False), f"{S2}.yaml").claim_type == "yatis"
    pathway = load_pathway(_DIR / f"{S39}.yaml")
    assert pin_problems(pathway, pathway.showcase) == []
    pinned = pathway.showcase.model_copy(update={"nights": 2})
    (problem,) = pin_problems(pathway, pinned)
    assert (problem.check, problem.where, problem.message) == (
        "pins.out_of_range", "showcase.nights", "a poliklinik pathway has no nights"
    )  # fmt: skip


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


def test_a_stay_that_arrives_from_an_icu_bill_has_its_bed_from_the_day_after_admission(catalogs: Catalogs, tmp_path) -> None:
    raw = _raw(S14)
    assert raw["arrives_from_icu"] is True and line(raw, "bed")["days"] == "admit+1..discharge"
    assert _problems(raw, catalogs, tmp_path) == []
    # the transfer day's bed is the ICU bill's: a bed on it is the defect, and the message names the days that are right
    line(raw, "bed").update(days="admit..discharge")
    assert stay_coverage_messages(raw, catalogs, tmp_path) == [
        (
            "procedures[bed]",
            "a bed line must cover admit+1..discharge; "
            "2 nights: days [0, 1, 2], expected [1, 2]; 3 nights: days [0, 1, 2, 3], expected [1, 2, 3]; "
            "8 nights: days [0, 1, 2, 3, 4, 5, 6, 7, 8], expected [1, 2, 3, 4, 5, 6, 7, 8]",
        )
    ]
    # the flag moves the bed only: the companion still covers every night, and without the flag the bed covers every day
    line(raw, "bed").update(days="admit+1..discharge")
    line(raw, "companion").update(days="admit+1..discharge-1")
    assert [m for _, m in stay_coverage_messages(raw, catalogs, tmp_path)][0].startswith("a companion line must cover admit..discharge-1;")
    raw = _raw(S14)
    raw.pop("arrives_from_icu")
    assert [m for _, m in stay_coverage_messages(raw, catalogs, tmp_path)][0].startswith("a bed line must cover admit..discharge;")


def test_a_stay_that_arrives_from_an_icu_bill_names_an_icu_or_newborn_line_as_the_defect(catalogs: Catalogs, tmp_path) -> None:
    for kind, code, name in (("newborn_bed", "510081", "Kot (beşik)"), ("icu_day", "510090", "Yoğun bakım")):
        raw = _raw(S14)
        raw["procedures"].append(icu_line("extra", kind, code, name, "admit+1"))
        messages = [m for where, m in stay_coverage_messages(raw, catalogs, tmp_path) if where == "arrives_from_icu"]
        assert messages == ["a ward stay that arrives from an ICU bill has no ICU or newborn bed line of its own"], (kind, messages)
    assert [w for w, _ in stay_coverage_messages(_raw(S14), catalogs, tmp_path)] == []


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


@pytest.mark.parametrize("base", [S7, S39], ids=["acil", "poliklinik"])
def test_an_icu_line_on_a_visit_needs_a_stay(base: str, catalogs: Catalogs, tmp_path) -> None:
    raw = _raw(base)
    raw["procedures"].append(icu_line("icu_visit", "icu_day", "510090", "Yoğun bakım", "admit"))
    assert stay_coverage_messages(raw, catalogs, tmp_path) == [
        ("procedures[icu_visit]", "an ICU line needs a stay, not a visit")
    ]


def test_a_newborn_bed_on_an_er_visit_needs_a_stay(catalogs: Catalogs, tmp_path) -> None:
    raw = _raw(S7)
    raw["procedures"].append(icu_line("incubator_visit", "newborn_bed", "510070", "Kuvöz", "admit"))
    assert stay_coverage_messages(raw, catalogs, tmp_path) == [
        ("procedures[incubator_visit]", "a newborn bed line needs a stay, not a visit")
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



# --- slice G9: the report duration of a drug; the haemodialysis session packages -----------------------


def test_the_report_duration_of_a_drug_reaches_its_expansion_and_only_s17_and_s44_set_it(catalogs: Catalogs) -> None:
    """The ESA of S17 is billed on a one-month nephrology report (SUT 4.2.9.A-1): the pathway says so (slice G9)."""
    pathway = load_pathway(_DIR / f"{S17}.yaml")
    (esa,) = pathway.drugs
    assert (esa.flags.drug_report_duration_months, esa.flags.prescriber_specialty) == (1, "Nefroloji")
    (row,) = expand(pathway)["drugs"]
    assert row["flags"] == {
        "drug_report_duration_months": 1,
        "drug_specialty_board_report_present": True,
        "prescriber_specialty": "Nefroloji",
    }
    assert run_all(pathway, catalogs) == []
    setting = [p.stem for p in _FILES if any(d.flags.drug_report_duration_months for d in load_pathway(p).drugs)]
    assert setting == [S17, S44]  # S44's romosozumab: the first report of 24 weeks, which the engine reads as 6 months


@pytest.mark.parametrize("months", [0, 25, -1, True, "1", 1.5])
def test_a_report_duration_that_is_no_whole_number_of_months_from_1_to_24_is_a_bad_value(months: object) -> None:
    raw = _raw(S17)
    drug(raw, "darbepoetin")["flags"]["drug_report_duration_months"] = months
    body = yaml.safe_dump(raw, allow_unicode=True, sort_keys=False)
    with pytest.raises(PathwayLoadError) as error:
        load_text(body, f"{S17}.yaml")
    assert [p.check for p in error.value.problems] == ["schema.bad_value"]
    assert "drugs[darbepoetin].flags.drug_report_duration_months" in str(error.value)


def test_a_bill_of_haemodialysis_sessions_may_hold_a_drug_and_no_other_package_bill_may(catalogs: Catalogs) -> None:
    """The session price includes the tests, the complication drugs, heparin and the day bed (C000969, C004117), not
    an ESA: a bill of session packages only may carry the ESA; a surgical package beside them takes that away."""
    pathway = load_pathway(_DIR / f"{S17}.yaml")
    assert check_package_mode(pathway, catalogs) == []
    raw = _raw(S17)
    raw["procedures"].append(
        {"id": "appendectomy", "kind": "package", "code": "P610131", "name": "Appendektomi, laparoskopik",
         "days": "admit", "basis": "judgment", "source": FIXTURE}
    )
    mixed = load_text(yaml.safe_dump(raw, allow_unicode=True, sort_keys=False), f"{S17}.yaml")
    problems = {p.where: p.message for p in check_package_mode(mixed, catalogs)}
    assert set(problems) == {"drugs[darbepoetin]"} and problems["drugs[darbepoetin]"].startswith("drugs are inside the package")


def test_the_package_window_leaves_a_haemodialysis_session_alone(catalogs: Catalogs, monkeypatch) -> None:
    """P704210 and P704230 have no EK-2C group: a session is one day, so no window; without the code set they would
    be packages without a group."""
    pathway = load_pathway(_DIR / f"{S23}.yaml")
    assert check_package_window(pathway, catalogs) == []
    assert run_all(pathway, catalogs) == []
    sets = {**catalogs.code_sets, "dialysis_packages": {}}
    monkeypatch.setitem(catalogs.__dict__, "code_sets", sets)
    found = check_package_window(pathway, catalogs)
    assert [p.check for p in found] == ["package.window"] and "P704210 has no group in EK-2C" in found[0].message
    assert [p.where for p in check_package_mode(load_pathway(_DIR / f"{S17}.yaml"), catalogs)] == ["drugs[darbepoetin]"]


def test_the_haemodialysis_session_packages_are_the_chronic_and_the_emergency_code() -> None:
    sets = yaml.safe_load((_REPO / "data/synthetic/reference/code_sets.yaml").read_text(encoding="utf-8"))
    assert {k: v["code"] for k, v in sets["dialysis_packages"].items()} == {"chronic": "P704230", "emergency": "P704210"}


# --- S18 and S24 (WP13): the albumin of a cirrhotic inpatient, the ISBT 128 numbers of two red-cell units ---------

S18 = "decompensated_cirrhosis_gi_bleed_albumin"  # albumin on the specialist report, supplied during the stay
S24 = "decompensated_cirrhosis_variceal_rebleed_transfusion"  # two red-cell units, one ISBT 128 number each


def test_s24_and_s42_set_isbt128_numbers_one_valid_and_distinct_number_per_red_cell_unit(catalogs: Catalogs) -> None:
    pathway = load_pathway(_DIR / f"{S24}.yaml")
    units = [p for p in pathway.procedures if p.code == "705371"]
    numbers = [p.flags.isbt128_barcode for p in units]
    assert [(p.id, p.kind, p.days) for p in units] == [
        ("red_cells_unit_1", "procedure", ["admit"]),
        ("red_cells_unit_2", "procedure", ["admit"]),
    ]
    assert len(set(numbers)) == 2 and all(is_valid_isbt128_barcode(number) for number in numbers)
    rows = [p for p in expand(pathway)["procedures"] if p["code"] == "705371"]
    assert [r["flags"] for r in rows] == [{"isbt128_barcode": number} for number in numbers]
    assert run_all(pathway, catalogs) == []
    setting = [p.stem for p in _FILES if any(x.flags.isbt128_barcode for x in load_pathway(p).procedures)]
    assert setting == [S24, S42]
    s42 = [p.flags.isbt128_barcode for p in load_pathway(_DIR / f"{S42}.yaml").procedures if p.code == "705371"]
    assert len(set(s42)) == 2 and all(is_valid_isbt128_barcode(number) for number in s42)
    assert not set(s42) & set(numbers)  # S42's units are other units than S24's


def test_s18_bills_three_days_of_albumin_from_day_two_on_the_report(catalogs: Catalogs) -> None:
    pathway = load_pathway(_DIR / f"{S18}.yaml")
    (albumin,) = pathway.drugs
    assert (albumin.flags.drug_specialty_board_report_present, albumin.flags.drug_inpatient_supply) == (True, True)
    assert (albumin.indication, albumin.per_day, albumin.day) == ("K74.6", 1, "admit+1")
    (row,) = expand(pathway)["drugs"]
    assert (row["date"], row["qty"], row["unit"]) == ("2026-06-16", 3, "bottle")
    labs = [(p.id, [i.code for i in p.items or []]) for p in pathway.procedures if p.kind == "lab"]
    assert labs == [("admission_labs", ["L107020", "L100320"])]  # the albumin level the SUT asks for, on the admission day
    assert run_all(pathway, catalogs) == []


# --- S41 to S44 (WP15): the blood of a package bill (slice G14), the report months of romosozumab -----------------

S42 = "infected_hemiarthroplasty_removal_package"  # the removal package P612500 and two red-cell units at their share
S44 = "severe_osteoporosis_geriatrics_romosozumab"  # romosozumab on a health-board report of 6 months


def test_the_blood_shares_are_the_ones_of_sut_c000694() -> None:
    """SUT 2.2.2.B-1.(1).e (C000694) and 4.6.(4) (C007927): 36 % for 705371, 705430 and 705440, 24 % for 705372 and 705373,
    20 % for 705441, 28 % for 705442 and 705443."""
    assert {code: str(share) for code, share in BLOOD_PACKAGE_SHARES.items()} == {
        "705371": "0.36", "705430": "0.36", "705440": "0.36", "705372": "0.24", "705373": "0.24",
        "705441": "0.20", "705442": "0.28", "705443": "0.28",
    }  # fmt: skip


def test_a_package_bill_bills_its_red_cells_at_their_share_and_an_itemized_bill_in_full(catalogs: Catalogs) -> None:
    pathway = load_pathway(_DIR / f"{S42}.yaml")
    assert pathway.billing_mode == "package"
    rows = {(r["code"], r["flags"].get("isbt128_barcode", "")): r["billed_ratio"] for r in expand(pathway)["procedures"]}
    assert rows == {
        ("705371", "=X99992610002100"): "0.3600",
        ("705371", "=X99992610002200"): "0.3600",
        ("P612500", ""): "1.0000",
    }
    assert check_package_mode(pathway, catalogs) == [] and run_all(pathway, catalogs) == []
    itemized = load_pathway(_DIR / f"{S24}.yaml")  # the same code on an itemized bill: EK-2/B in full (C007926)
    assert {r["billed_ratio"] for r in expand(itemized)["procedures"] if r["code"] == "705371"} == {"1.0000"}


def test_a_package_bill_holds_a_blood_component_and_no_other_procedure(catalogs: Catalogs) -> None:
    """`package.mode` lets a component of C000694 stand on a package bill; any other procedure line stays refused, a
    blood component of another kind too."""
    raw = _raw(S42)
    raw["procedures"].append(
        {"id": "ecg", "kind": "procedure", "code": "530100", "name": "Elektrokardiyogram", "days": "admit",
         "basis": "judgment", "source": FIXTURE}
    )
    pathway = load_text(yaml.safe_dump(raw, allow_unicode=True, sort_keys=False), f"{S42}.yaml")
    assert {p.where for p in check_package_mode(pathway, catalogs)} == {"procedures[ecg]"}
    raw = _raw(S42)
    raw["procedures"][1]["kind"] = "lab"
    pathway = load_text(yaml.safe_dump(raw, allow_unicode=True, sort_keys=False), f"{S42}.yaml")
    assert {p.where for p in check_package_mode(pathway, catalogs)} == {"procedures[red_cells_unit_1]"}


def test_s44_starts_romosozumab_on_a_report_of_six_months_prescribed_by_geriatrics(catalogs: Catalogs) -> None:
    pathway = load_pathway(_DIR / f"{S44}.yaml")
    (romosozumab,) = pathway.drugs
    assert (romosozumab.barcode, romosozumab.inn, romosozumab.indication) == ("8699862950244", "Romosozumab", "M81.09")
    (row,) = expand(pathway)["drugs"]
    assert row["flags"] == {
        "drug_report_duration_months": 6,
        "drug_specialty_board_report_present": True,
        "prescriber_specialty": "Geriatri",
    }
    assert (row["qty"], row["unit"], row["per_box"]) == (2, "syringe", 2)  # 210 mg: one box of two syringes, one month
    assert (pathway.department.name, pathway.department.specialty) == ("Geriatri", "1073")
    assert run_all(pathway, catalogs) == []


def test_the_walker_visit_of_patient_5_is_another_branch_than_its_orthopaedic_packages() -> None:
    """SUT 2.2.2.B-3.(1) (C000713, C000714): an outpatient examination of the same branch within 10 days of a package
    discharge (the end of the group's window counting as the discharge) is inside the package. Both stays of patient 5
    (S5, S42) are orthopaedic packages whose periods reach past the code-set window, so S43's walker visit and S44's
    geriatrics visit go to other branches; an orthopaedic control would carry the dormant fault of F1 b3 (#337)."""
    stays = [load_pathway(_DIR / f"{pid}.yaml") for pid in ("femoral_neck_fracture_cemented_hemiarthroplasty_package", S42)]
    visits = [load_pathway(_DIR / f"{pid}.yaml") for pid in ("femoral_neck_fracture_physiatry_first_walker", S44)]
    assert {p.department.specialty for p in stays} == {"2600"} and all(p.billing_mode == "package" for p in stays)
    assert [(p.claim_type, p.department.specialty) for p in visits] == [("poliklinik", "1800"), ("poliklinik", "1073")]


# --- S49 to S51 (WP17): the EK-2B lines of an EK-2C package's session (slice G15) ---------------------------------

S50 = "retained_common_bile_duct_stone_ercp_package"  # the ERCP package P701360, sphincterotomy and stone extraction beside it


def _s50(edit) -> Pathway:
    raw = _raw(S50)
    edit(raw)
    return load_text(yaml.safe_dump(raw, allow_unicode=True, sort_keys=False), f"{S50}.yaml")


def test_a_package_bill_holds_the_ek2b_lines_of_its_package_session_and_no_other(catalogs: Catalogs) -> None:
    """`package.mode` lets an EK-2B procedure or operation with the role same_incision or separate_incision stand on a
    package bill when a package line leads the session (SUT 2.2.2.B(3)(c), (ç): C000672, C000673; slice G15); without
    that role, or with no package leading the session, the line stays refused."""
    pathway = load_pathway(_DIR / f"{S50}.yaml")
    assert check_package_mode(pathway, catalogs) == [] and run_all(pathway, catalogs) == []
    for edit in (
        lambda r: line(r, "sphincterotomy").update(session_role="separate_incision"),  # C000673: 50 %
        lambda r: line(r, "sphincterotomy").update(kind="operation"),  # an EK-2B operation of the session
    ):
        assert check_package_mode(_s50(edit), catalogs) == []
    refused = {
        "no role": lambda r: line(r, "sphincterotomy").pop("session_role"),
        "a second primary": lambda r: line(r, "sphincterotomy").update(session_role="primary"),
    }
    for label, edit in refused.items():
        assert {p.where for p in check_package_mode(_s50(edit), catalogs)} == {"procedures[sphincterotomy]"}, label
    no_lead = _s50(lambda r: line(r, "ercp_package").pop("session_role"))
    assert {p.where for p in check_package_mode(no_lead, catalogs)} == {
        "procedures[sphincterotomy]",
        "procedures[stone_extraction]",
    }


def test_the_session_order_reads_the_puan_of_each_code_from_its_own_list(catalogs: Catalogs) -> None:
    """A session of a package bill may hold EK-2B lines beside the package: the package's puan comes from EK-2C, the
    other lines' from EK-2B (slice G15). An EK-2B line above the package puts the package below another operation, and
    the whole session goes itemized (C000672)."""
    pathway = load_pathway(_DIR / f"{S50}.yaml")
    assert check_sessions(pathway, catalogs) == []  # P701360 16491.75 leads 701370 and 701440
    name = catalogs.ek2b.filter(pl.col("code") == "701017")["name"].unique().item()  # puan 17535.52 since 2026-01-01
    (problem,) = check_sessions(_s50(lambda r: line(r, "stone_extraction").update(code="701017", name=name)), catalogs)
    assert problem.check == "session.order" and problem.where == "procedures[ercp_package, sphincterotomy, stone_extraction]"
    assert "the primary P701360 (puan 16491.75) is below another operation (17535.52)" in problem.message

