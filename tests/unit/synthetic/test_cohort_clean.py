"""Acceptance, schema, loader, smoke and hygiene tests for `scripts/synthetic/cohort/clean.py`."""

from __future__ import annotations

from collections.abc import Iterator
import json
import re
from typing import Any

import polars as pl
import pytest

from scripts.synthetic.cohort import (
    ANADATA_CLEAN_SCHEMA,
    CLEAN_TABLE_FILES,
    CLINICAL_PATH,
    EPISODE_ID_RE,
    LAB_CLEAN_SCHEMA,
    PATIENT_ID_RE,
    RECETE_CLEAN_SCHEMA,
    BuildResult,
    clean_table_schemas,
    clean_tables_digest,
    load_clinical,
)
from scripts.synthetic.cohort.build import DEFAULT_OUT_DIR
from scripts.synthetic.pathways.loader import hygiene
from src.bilun.cache.data_loader import load_anadata, load_labdata, load_recete
from src.bilun.cache.loaders import load_normalized_raw_data, resolve_patient_ids
from src.bilun.domain.claims.loader import load_sut_claim_dataset
from tests.fixtures import synthetic_cohort as cohort

pytestmark = pytest.mark.unit

_OUT_DIR = DEFAULT_OUT_DIR
_CLEAN_DIR = _OUT_DIR / "sut" / "clean"
_REGISTRY_JSON_PATH = _OUT_DIR / "cohort_registry.json"


# Column names and dtypes of the three clean tables of the former 50-patient set, which the cache
# loaders (`src/bilun/cache/data_loader.py`) were written against. The files are in git history only;
# the schemas are pinned here so that the v3 tables keep the contract.
_FORMER_CLEAN_SCHEMAS: dict[str, pl.Schema] = {
    "anadata_clean.parquet": pl.Schema(
        {
            "HASTA_ID": pl.String(),
            "SQ_EPISODE": pl.String(),
            "EPISODE_TARIH": pl.Datetime("ns"),
            "TANI_YASI": pl.Int64(),
            "CINSIYET": pl.String(),
            "KB-S": pl.Int64(),
            "KB-D": pl.Int64(),
            "Nabiz": pl.Int64(),
            "SPO2": pl.Int64(),
            "Boy": pl.Int64(),
            "Kilo": pl.Float64(),
            "BMI": pl.Float64(),
            "ILK_TANI_SON_TANI_GUN_FARKI": pl.Int64(),
            "TOPLAM_GELIS_SAYISI": pl.Int64(),
            "GELIS_SAYISI": pl.Int64(),
            "GELIS_TIPI": pl.String(),
            "SERVISADI": pl.String(),
            "TANIKODU": pl.String(),
            "TUM_EPS_TANILAR": pl.String(),
            "TANI_TIPI": pl.String(),
            "TANITARIH": pl.Datetime("ns"),
            "MIN_TANI_TARIH": pl.Datetime("ns"),
            "MAX_TANI_TARIH": pl.Datetime("ns"),
            "Hipertansiyon Hastada": pl.Boolean(),
            "Kalp Damar Hastada": pl.Boolean(),
            "Diyabet Hastada": pl.Boolean(),
            "Kan Hastaliklari Hastada": pl.Boolean(),
            "YAKINMA": pl.String(),
            "OYKU": pl.String(),
            "Muayene Notu": pl.String(),
            "Tedavi Notu": pl.String(),
            "kohort": pl.String(),
            "donem": pl.String(),
        }
    ),
    "recete_clean.parquet": pl.Schema(
        {
            "HASTA_ID": pl.String(),
            "RECETE_TARIH": pl.Datetime("ns"),
            "RF_EPISODE": pl.String(),
            "ilac_adi": pl.String(),
            "ilac_adi_ham": pl.String(),
            "dozaj_ham": pl.String(),
            "verilis_yolu": pl.String(),
            "gun": pl.Int64(),
            "doz_mg": pl.Int64(),
            "doz_birimi": pl.String(),
            "siklik": pl.Int64(),
            "miktar": pl.Int64(),
            "kohort": pl.String(),
            "donem": pl.String(),
        }
    ),
    "lab_clean.parquet": pl.Schema(
        {
            "HASTA_ID": pl.String(),
            "basvuru_id": pl.String(),
            "SUB_CODE": pl.String(),
            "sonuc_sayisal": pl.Float64(),
            "sonuc_nitel": pl.String(),
            "birim": pl.String(),
            "ref_alt": pl.Float64(),
            "ref_ust": pl.Float64(),
            "anormal_mi": pl.Boolean(),
            "organ_sistemi": pl.String(),
            "kohort": pl.String(),
            "donem": pl.String(),
            "tarih": pl.Datetime("ns"),
        }
    ),
}

_ANON_RE = re.compile(r"anon_|\banon[\s-]*[0-9]", re.IGNORECASE)
_CURRENCY_RE = re.compile(
    r"(?=[0-9.,]*[1-9])[0-9][0-9.,]*\s*(?:TL|TRY|\u20ba)(?![A-Za-z])|\u20ba\s*(?=[0-9.,]*[1-9])[0-9][0-9.,]*",
    re.IGNORECASE,
)


@pytest.fixture(autouse=True)
def _fresh_claims_cache() -> Iterator[None]:
    """`load_sut_claim_dataset` caches by arguments: every test starts and ends with an empty cache."""
    load_sut_claim_dataset.cache_clear()
    yield
    load_sut_claim_dataset.cache_clear()


@pytest.fixture(scope="module")
def built_showcase(committed_showcase: BuildResult) -> BuildResult:
    return committed_showcase


# --- 2. Clean table schemas & content rules -----------------------------------------------------


def test_clean_schemas_match_the_former_parquet_schemas(built_showcase: BuildResult) -> None:
    legacy_ana = _FORMER_CLEAN_SCHEMAS["anadata_clean.parquet"]
    legacy_rec = _FORMER_CLEAN_SCHEMAS["recete_clean.parquet"]
    legacy_lab = _FORMER_CLEAN_SCHEMAS["lab_clean.parquet"]

    expected_lab_items: list[tuple[str, pl.DataType]] = []
    for col, dtype in legacy_lab.items():
        expected_lab_items.append((col, dtype))
        if col == "SUB_CODE":
            expected_lab_items.append(("parametre", pl.String()))
    expected_lab = pl.Schema(expected_lab_items)

    schemas = clean_table_schemas()
    assert schemas["anadata_clean.parquet"] == legacy_ana == ANADATA_CLEAN_SCHEMA
    assert schemas["recete_clean.parquet"] == legacy_rec == RECETE_CLEAN_SCHEMA
    assert schemas["lab_clean.parquet"] == expected_lab == LAB_CLEAN_SCHEMA
    assert list(LAB_CLEAN_SCHEMA.names())[2:4] == ["SUB_CODE", "parametre"]

    for name in CLEAN_TABLE_FILES:
        df = built_showcase.clean_tables[name]
        assert pl.Schema(df.schema) == schemas[name], name
        assert all(dt != pl.Null for dt in df.schema.values()), name


# --- 4. Loaders accept the committed clean folder ----------------------------------------------


def test_cache_loaders_accept_committed_clean_folder() -> None:
    ana_raw = load_anadata(_CLEAN_DIR / "anadata_clean.parquet", include_text=True)
    lab_raw = load_labdata(_CLEAN_DIR / "lab_clean.parquet")
    rec_raw = load_recete(_CLEAN_DIR / "recete_clean.parquet")

    clean_counts = cohort.load_registry()["clean_counts"]
    assert ana_raw.height == clean_counts["anadata_clean.parquet"]
    assert lab_raw.height == clean_counts["lab_clean.parquet"]
    assert rec_raw.height == clean_counts["recete_clean.parquet"]

    ana_df, lab_df, rec_df = load_normalized_raw_data(
        load_anadata_fn=lambda include_text=True: load_anadata(
            path=_CLEAN_DIR / "anadata_clean.parquet",
            include_text=include_text,
        ),
        load_labdata_fn=lambda: load_labdata(path=_CLEAN_DIR / "lab_clean.parquet"),
        load_recete_fn=lambda: load_recete(path=_CLEAN_DIR / "recete_clean.parquet"),
    )

    assert ana_df.height == clean_counts["anadata_clean.parquet"]
    assert "patient_id" in ana_df.columns
    assert "visit_date" in ana_df.columns
    assert "yas" in ana_df.columns
    assert "SQ_EPISODE" not in ana_df.columns
    assert len(ana_df.columns) == 32

    assert lab_df.height == clean_counts["lab_clean.parquet"]
    assert list(lab_df.columns) == [
        "patient_id",
        "visit_id",
        "date",
        "test_name",
        "value",
        "ref_min",
        "ref_max",
    ]

    assert rec_df.height == clean_counts["recete_clean.parquet"]
    assert list(rec_df.columns) == ["patient_id", "date", "drug_name"]

    pids = resolve_patient_ids(ana_df, lab_df, rec_df)
    assert pids == cohort.patient_ids()


# --- 5. Smoke: load_sut_build_context ----------------------------------------------------------


def test_smoke_load_sut_build_context_on_committed_showcase(demo_build_context: dict[str, Any]) -> None:
    """`load_sut_build_context(billing_workers=1, sut_data_mode="synthetic_demo")` over the committed claims and clean
    tables (`demo_build_context` of `tests/conftest.py`, built once per session)."""
    ctx = demo_build_context
    expected_pids = cohort.patient_ids()
    assert ctx["patient_ids"] == expected_pids
    assert [m["patient_id"] for m in ctx["patient_meta"]] == expected_pids
    assert len(ctx["billing_reports"]) == cohort.patient_count()


# --- 6. Build equals committed, --check on clean tables & clean_counts, determinism -----------


def test_build_equals_committed_clean_tables_and_registry(
    built_showcase: BuildResult,
) -> None:
    committed_reg = json.loads(_REGISTRY_JSON_PATH.read_text(encoding="utf-8"))
    assert built_showcase.registry == committed_reg
    assert committed_reg["clean_counts"] == {
        name: df.height for name, df in built_showcase.clean_tables.items()
    }
    assert committed_reg["clean_tables_digest"] == clean_tables_digest(built_showcase.clean_tables)

    for name in CLEAN_TABLE_FILES:
        committed_path = _CLEAN_DIR / name
        assert committed_path.is_file(), f"Missing committed clean table {committed_path}"
        committed_df = pl.read_parquet(committed_path)
        built_df = built_showcase.clean_tables[name]
        assert dict(committed_df.schema) == dict(built_df.schema), name
        assert committed_df.equals(built_df, null_equal=True), name


# --- 7. Hygiene on clinical YAML and clean tables ----------------------------------------------


def test_hygiene_on_clinical_yaml_and_clean_tables() -> None:
    clinical_text = CLINICAL_PATH.read_text(encoding="utf-8")
    clinical_raw = json.loads(json.dumps(load_clinical().model_dump()))
    assert hygiene(clinical_raw, clinical_text) == []
    assert not _ANON_RE.search(clinical_text)
    assert not _CURRENCY_RE.search(clinical_text)

    clean_tables = {name: pl.read_parquet(_CLEAN_DIR / name) for name in CLEAN_TABLE_FILES}
    for name, df in clean_tables.items():
        for col, dtype in df.schema.items():
            if dtype == pl.String:
                for val in df[col].drop_nulls().to_list():
                    assert not _ANON_RE.search(val), f"ANON text in {name}.{col}: {val!r}"
                    assert not _CURRENCY_RE.search(val), f"Currency text in {name}.{col}: {val!r}"

    ana_df = clean_tables["anadata_clean.parquet"]
    assert all(PATIENT_ID_RE.fullmatch(v) for v in ana_df["HASTA_ID"].to_list())
    assert all(EPISODE_ID_RE.fullmatch(v) for v in ana_df["SQ_EPISODE"].to_list())

    rec_df = clean_tables["recete_clean.parquet"]
    assert all(PATIENT_ID_RE.fullmatch(v) for v in rec_df["HASTA_ID"].to_list())
    assert all(EPISODE_ID_RE.fullmatch(v) for v in rec_df["RF_EPISODE"].to_list())
