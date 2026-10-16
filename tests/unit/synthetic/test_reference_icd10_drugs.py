"""The SKRS ICD-10 table and the EK-4A drug crosswalk: schema, keys, source facts and provenance."""

from __future__ import annotations

import os
import re
from datetime import date
from pathlib import Path

import polars as pl
import pytest
import yaml
from polars.testing import assert_frame_equal

from scripts.synthetic.reference.build_icd10_and_drugs import (
    CROSSWALK_PATH,
    EK4A_PATH,
    ICD10_KINDS,
    ICD10_PATH,
    MATCH_SOURCES,
    SOURCES_PATH,
    USED,
    build,
    verified_inputs,
    with_kind_and_leaf,
    write_outputs,
)

pytestmark = pytest.mark.unit

_REPO = Path(__file__).resolve().parents[3]
_DOWNLOADS = os.environ.get("BILUN_REFERENCE_DOWNLOADS")
_ICD10_SCHEMA = {
    "code": pl.String, "name_tr": pl.String, "parent_code": pl.String, "level": pl.Int8,
    "is_active": pl.Boolean, "high_risk_pregnancy": pl.Boolean, "created_on": pl.Date,
    "updated_on": pl.Date, "passive_on": pl.Date, "sex": pl.String, "kind": pl.String, "is_leaf": pl.Boolean,
}
_CROSSWALK_SCHEMA = {
    "barcode": pl.String, "kamu_no": pl.String, "ek4a_name": pl.String, "equivalence_group": pl.String,
    "titck_product_name": pl.String, "active_ingredient": pl.String, "atc_code": pl.String,
    "atc_name": pl.String, "in_ruhsat_2026_02": pl.Boolean, "in_ruhsat_2026_09": pl.Boolean,
    "erecete_status_2026_02": pl.String, "erecete_status_2026_09": pl.String, "match_source": pl.String,
}
# SKRS code shapes by kind: chapter/block ranges, morphology ranges, categories, subcategories (4th
# and 5th character), ICD-O morphology codes and their groups. Three SKRS codes fit none of them
# (kind "other"). Restated, not imported, so the tests recompute `kind` on their own.
_CODE_SHAPES = {
    "range": r"^[A-Z]\d{2}-[A-Z]\d{2}$", "morphology_range": r"^M\d{3}-M\d{3}$", "category": r"^[A-Z]\d{2}$",
    "subcategory": r"^[A-Z]\d{2}\.\d{1,2}$", "morphology": r"^M\d{4}/\d$", "morphology_group": r"^M\d{3}$",
}
_ODD_CODES = {"CM-AL", "M86.4.9", "ZX01"}
_KIND_COUNTS = {"subcategory": 12_707, "category": 2_020, "morphology": 717, "range": 293,
                "morphology_group": 32, "morphology_range": 32, "other": 3}


@pytest.fixture(scope="module")
def icd10() -> pl.DataFrame:
    return pl.read_parquet(ICD10_PATH)


@pytest.fixture(scope="module")
def crosswalk() -> pl.DataFrame:
    return pl.read_parquet(CROSSWALK_PATH)


@pytest.fixture(scope="module")
def sources() -> dict:
    return yaml.safe_load(SOURCES_PATH.read_text("utf-8"))


def _row(frame: pl.DataFrame, key: str, value: str) -> dict:
    rows = frame.filter(pl.col(key) == value)
    assert rows.height == 1, (key, value, rows.height)
    return rows.row(0, named=True)


def test_icd10_schema_and_counts(icd10) -> None:
    assert icd10.schema == pl.Schema(_ICD10_SCHEMA)
    assert icd10.height == 15_804  # 15,805 SKRS rows minus the root "0"
    assert icd10["is_active"].sum() == 15_799
    assert set(icd10.filter(~pl.col("is_active"))["code"]) == {"CM-AL", "U06", "U06.1", "U06.9", "Z22.5"}
    assert icd10["high_risk_pregnancy"].sum() == 29
    assert icd10.filter(pl.col("updated_on") < pl.col("created_on")).is_empty()


def test_icd10_codes_are_unique_and_well_formed(icd10) -> None:
    assert icd10["code"].is_unique().all()
    shaped = pl.any_horizontal(pl.col("code").str.contains(p) for p in _CODE_SHAPES.values())
    assert set(icd10.filter(~shaped)["code"]) == _ODD_CODES


def test_icd10_parents_exist_and_only_top_rows_have_none(icd10) -> None:
    parents = icd10.filter(pl.col("parent_code").is_not_null())
    assert parents["parent_code"].is_in(icd10["code"].implode()).all()
    top = icd10.filter(pl.col("parent_code").is_null())
    assert set(top["code"]) == set(icd10.filter(pl.col("level") == 0)["code"]) | {"CM-AL"}
    assert top.filter(pl.col("level") == 0).height == 23


def test_kind_is_the_code_shape_and_is_leaf_the_tree(icd10) -> None:
    for kind, shape in _CODE_SHAPES.items():  # `kind` names a shape exactly where the code fits it
        assert (icd10["code"].str.contains(shape) == (icd10["kind"] == kind)).all(), kind
    assert set(icd10.filter(pl.col("kind") == "other")["code"]) == _ODD_CODES
    parents = icd10.select(pl.col("parent_code").alias("code")).drop_nulls().unique()
    assert set(icd10.join(parents, on="code", how="anti")["code"]) == set(icd10.filter("is_leaf")["code"])


def test_kind_and_leaf_counts(icd10) -> None:
    assert dict(icd10["kind"].value_counts().rows()) == _KIND_COUNTS
    assert dict(icd10["is_leaf"].value_counts().rows()) == {True: 13_555, False: 2_249}
    # Review 2026-10-16, ICD/drug Q5: 12,817 of the 14,723 active diagnosis codes are leaves.
    diagnoses = icd10.filter(pl.col("kind").is_in(["category", "subcategory"]) & pl.col("is_active"))
    assert (diagnoses.height, diagnoses["is_leaf"].sum()) == (14_723, 12_817)


@pytest.mark.parametrize(
    ("code", "kind", "is_leaf"),
    [
        # The review's story diagnoses (2026-10-16, Q12) are leaves; M48.0 is the parent of M48.06.
        ("K35.9", "subcategory", True),
        ("M48.06", "subcategory", True),
        ("S72.00", "subcategory", True),
        ("M81.09", "subcategory", True),
        ("M48.0", "subcategory", False),
        ("A00", "category", False),
        ("A00-B99", "range", False),
        ("M800-M998", "morphology_range", False),
        ("M800", "morphology_group", False),
        ("M8000/0", "morphology", True),
        ("ZX01", "other", True),
    ],
)
def test_known_codes_have_their_kind_and_leaf_flag(icd10, code: str, kind: str, is_leaf: bool) -> None:
    row = _row(icd10, "code", code)
    assert (row["kind"], row["is_leaf"]) == (kind, is_leaf)


def test_builder_refuses_a_code_that_fits_two_kinds(monkeypatch) -> None:
    monkeypatch.setitem(ICD10_KINDS, "overlapping", r"^[A-Z]\d{2}")  # also fits A00 and A00-B99
    table = pl.DataFrame({"code": ["A00", "A00-B99"], "parent_code": ["A00-B99", None]})
    with pytest.raises(ValueError, match=r"fitting two kinds: \['A00', 'A00-B99'\]"):
        with_kind_and_leaf(table)


def test_sex_comes_only_from_the_skrs_cancer_codes(icd10) -> None:
    counts = dict(icd10["sex"].value_counts().rows())
    assert counts == {"F": 63, "M": 34, None: 15_707}
    categories = {sex: set(icd10.filter(pl.col("sex") == sex)["code"].str.slice(0, 3)) for sex in ("F", "M")}
    assert categories["F"] == {f"C5{i}" for i in range(1, 9)} | {"D06", "D07", "D25", "D26", "D27", "D28", "D39"}
    assert categories["M"] == {"C60", "C61", "C62", "C63", "D07", "D29", "D40"}


@pytest.mark.parametrize(
    ("code", "name", "sex"),
    [
        ("A00", "KOLERA", None),
        ("J18.9", "PNÖMONİ, TANIMLANMAMIŞ", None),
        ("C61", "PROSTAT MALİGN NEOPLAZMI", "M"),
        ("C53", "SERVİKS UTERİ MALİGN NEOPLAZMI", "F"),
        ("C50", "MEME MALİGN NEOPLAZMI", None),  # breast: not sex-coded in SKRS
        ("N40", "BENİGN PROSTAT HİPERPLAZİSİ", None),  # male-only in practice, not flagged
        ("U07.3", "COVID-19", None),
        ("U07.1", "MERS COV HASTALIĞI", None),  # SKRS meaning, not WHO's COVID-19 code
    ],
)
def test_known_codes_keep_their_skrs_names(icd10, code: str, name: str, sex: str | None) -> None:
    row = _row(icd10, "code", code)
    assert (row["name_tr"], row["sex"], row["is_active"]) == (name, sex, True)


def test_known_rows_keep_their_tree_and_dates(icd10) -> None:
    assert _row(icd10, "code", "E10.4")["parent_code"] == "E10"  # "E10 " in the source
    assert _row(icd10, "code", "I45.81")["parent_code"] == "CM-AL"
    chapter = _row(icd10, "code", "A00-B99")
    assert (chapter["level"], chapter["parent_code"]) == (0, None)
    hepatitis = _row(icd10, "code", "Z22.5")
    assert (hepatitis["is_active"], hepatitis["passive_on"]) == (False, date(2026, 2, 16))
    assert _row(icd10, "code", "O24")["high_risk_pregnancy"] is True


def test_crosswalk_has_one_row_per_ek4a_barcode(crosswalk) -> None:
    assert crosswalk.schema == pl.Schema(_CROSSWALK_SCHEMA)
    ek4a = pl.read_parquet(EK4A_PATH, columns=["barcode", "kamu_no", "drug_name"])
    assert crosswalk.height == ek4a.height == 8_078
    assert crosswalk["barcode"].is_unique().all()
    joined = ek4a.join(crosswalk, on="barcode", how="full", coalesce=True)
    assert joined.filter(pl.col("kamu_no").ne_missing(pl.col("kamu_no_right"))
                         | pl.col("drug_name").ne_missing(pl.col("ek4a_name"))).is_empty()


def test_crosswalk_value_formats(crosswalk) -> None:
    assert crosswalk["barcode"].str.contains(r"^\d{13}$").all()
    atc = crosswalk.filter(pl.col("atc_code").is_not_null())["atc_code"]
    full = atc.filter(atc.str.len_chars() == 7)
    assert full.str.contains(r"^[A-Z]\d{2}[A-Z]{2}\d{2}$").all()
    assert atc.filter(atc.str.len_chars() != 7).str.contains(r"^[A-Z]\d{2}[A-Z]{1,2}$").all()
    for column in ("erecete_status_2026_02", "erecete_status_2026_09"):
        assert set(crosswalk[column].drop_nulls()) == {"Aktif", "Pasif"}
    assert set(crosswalk["match_source"]) == set(MATCH_SOURCES)
    assert crosswalk.filter(pl.col("atc_name").is_not_null() & pl.col("atc_code").is_null()).is_empty()


def test_match_source_agrees_with_the_fields(crosswalk) -> None:
    titck = ("titck_product_name", "active_ingredient", "atc_code")
    listed = pl.any_horizontal(pl.col("in_ruhsat_2026_02", "in_ruhsat_2026_09")) | pl.any_horizontal(
        pl.col("erecete_status_2026_02", "erecete_status_2026_09").is_not_null())
    unmatched = crosswalk.filter(pl.col("match_source") == "unmatched")
    assert unmatched.filter(listed | pl.any_horizontal(pl.col(titck).is_not_null())).is_empty()
    assert crosswalk.filter((pl.col("match_source") == "barcode") & ~listed).is_empty()
    ambiguous = crosswalk.filter(pl.col("match_source") == "barcode, licence ambiguous")
    assert ambiguous.filter(pl.any_horizontal(pl.col("titck_product_name", "active_ingredient").is_not_null())
                            | ~(pl.col("in_ruhsat_2026_02") | pl.col("in_ruhsat_2026_09"))).is_empty()
    ek4a = pl.read_parquet(EK4A_PATH, columns=["barcode", "old_barcodes"])
    via_old = crosswalk.filter(pl.col("match_source").str.contains("old_barcode")).join(ek4a, on="barcode")
    assert via_old.height == 12 and (via_old["old_barcodes"] != "").all()


def test_coverage_stays_at_or_above_the_measured_values(crosswalk) -> None:
    measured = {
        "matched": (pl.col("match_source") != "unmatched", 8_048),
        "in a licence list": (pl.col("in_ruhsat_2026_02") | pl.col("in_ruhsat_2026_09"), 7_696),
        "in the 2026-09 e-reçete list": (pl.col("erecete_status_2026_09").is_not_null(), 7_264),
        "active ingredient": (pl.col("active_ingredient").is_not_null(), 7_692),
        "ATC code": (pl.col("atc_code").is_not_null(), 8_047),
        "seven-character ATC": (pl.col("atc_code").str.len_chars() == 7, 7_703),
        "ATC name": (pl.col("atc_name").is_not_null(), 7_269),
    }
    low = {label: (crosswalk.filter(expr).height, floor) for label, (expr, floor) in measured.items()
           if crosswalk.filter(expr).height < floor}
    assert not low, low


@pytest.mark.parametrize(
    ("barcode", "ingredient", "atc_code", "atc_name", "match_source"),
    [
        # e-reçete ATC wins: the licence list still has the pre-2023 code N03AX16.
        ("8699514150695", "pregabalin", "N02BF02", "pregabalin", "barcode"),
        ("8699546010028", "asetilsalisilik asit", "B01AC06", "acetylsalicylic acid", "barcode"),
        # The licence list gives this barcode to JANUVIA and DELSTRIGO; EK-4A and e-reçete say DELSTRIGO.
        ("8699636091524", None, "J05AR24", "lamivudine, tenofovir disoproxil and doravirine",
         "barcode, licence ambiguous"),
        # Current barcode in no list; its EK-4A old barcode is in the licence list (ATC there, no name).
        ("8681085010553", "Gayafenezin + Terbütalin Sülfat", "R03CC53", None, "old_barcode"),
    ],
)
def test_known_drugs_cross_to_their_ingredient_and_atc(
    crosswalk, barcode: str, ingredient: str | None, atc_code: str, atc_name: str | None, match_source: str
) -> None:
    row = _row(crosswalk, "barcode", barcode)
    assert (row["active_ingredient"], row["atc_code"], row["atc_name"], row["match_source"]) == (
        ingredient, atc_code, atc_name, match_source)


def test_sources_are_listed_with_their_hashes_and_terms(sources) -> None:
    required = {"path", "publisher", "title", "page_url", "file_url", "downloaded", "bytes", "sha256",
                "terms", "used_by"}
    entries = sources["sources"]
    for key, entry in entries.items():
        assert required <= entry.keys(), key
        assert re.fullmatch(r"[0-9a-f]{64}", entry["sha256"]), key
        assert isinstance(entry["bytes"], int) and entry["bytes"] > 0, key
        assert entry["downloaded"] == date(2026, 10, 15), key
        assert entry["page_url"].startswith("https://") and entry["file_url"].startswith("https://"), key
    assert entries["icd10_who_2019"]["committed_derivatives"] == "none"
    assert entries["icd10_who_2019"]["used_by"] == []
    outputs = sources["outputs"]
    assert set(outputs) == {ICD10_PATH.name, CROSSWALK_PATH.name}
    for name, output in outputs.items():
        assert (_REPO / "data/synthetic/reference" / name).exists(), name
        assert output["inputs"] and all(name in entries[key]["used_by"] for key in output["inputs"]), name
        assert all((_REPO / path).exists() for path in output["repo_inputs"]), name
    assert {key for output in outputs.values() for key in output["inputs"]} == set(USED)


def test_builder_refuses_a_downloads_folder_inside_the_repo() -> None:
    with pytest.raises(ValueError, match="inside the repo"):
        verified_inputs(_REPO / "data")


def test_builder_refuses_a_file_that_does_not_match_its_hash(tmp_path: Path, sources) -> None:
    first = sources["sources"][USED[0]]
    target = tmp_path / first["path"]
    target.parent.mkdir(parents=True)
    target.write_bytes(b"x" * first["bytes"])
    with pytest.raises(ValueError, match="sha256 differs"):
        verified_inputs(tmp_path)


@pytest.mark.skipif(not _DOWNLOADS, reason="set BILUN_REFERENCE_DOWNLOADS to the downloads folder to rebuild")
def test_committed_tables_match_a_fresh_build(tmp_path: Path, icd10, crosswalk) -> None:
    fresh_icd10, fresh_crosswalk, _ = build(Path(_DOWNLOADS))
    assert_frame_equal(fresh_icd10, icd10)
    assert_frame_equal(fresh_crosswalk, crosswalk)
    written = write_outputs(fresh_icd10, fresh_crosswalk, tmp_path)
    for fresh, committed in zip(written, (ICD10_PATH, CROSSWALK_PATH), strict=True):
        assert fresh.read_bytes() == committed.read_bytes(), fresh.name
