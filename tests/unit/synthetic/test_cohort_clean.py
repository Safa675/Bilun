"""Acceptance, schema, content, loader, smoke, determinism, hygiene and mutation tests for `scripts/synthetic/cohort/clean.py`."""

from __future__ import annotations

import ast
from collections import Counter
from collections.abc import Callable, Iterator
from datetime import datetime, time
from decimal import ROUND_HALF_UP, Decimal
import json
from pathlib import Path
import re
from typing import get_args

import polars as pl
import pytest
import yaml

from scripts.synthetic.cohort import (
    ANADATA_CLEAN_SCHEMA,
    CLEAN_TABLE_FILES,
    CLINICAL_PATH,
    EPISODE_ID_RE,
    LAB_CLEAN_SCHEMA,
    PATIENT_ID_RE,
    RECETE_CLEAN_SCHEMA,
    BuildError,
    BuildResult,
    CleanTableError,
    ClinicalLoadError,
    DrugRoute,
    DrugRoutes,
    PatientClinical,
    ShowcaseClinical,
    build_clean_tables,
    build_showcase,
    check_clinical,
    clean_table_schemas,
    clean_tables_digest,
    derive_comorbidity_flags,
    load_clinical,
    resolve_drug_route,
    sentence_case_tr,
    validate_clean_tables,
    validate_cohort_registry,
    write_clean_tables,
    write_showcase,
)
from scripts.synthetic.cohort.build import DEFAULT_OUT_DIR, main
from scripts.synthetic.cohort.clean import _UNIT_TR
from scripts.synthetic.faults import load_siblings
from scripts.synthetic.pathways import load_all
from scripts.synthetic.pathways.loader import hygiene
from scripts.synthetic.pathways.schema import Unit
from src.bilun.cache.context import load_sut_build_context
from src.bilun.cache.data_loader import load_anadata, load_labdata, load_recete
from src.bilun.cache.loaders import load_normalized_raw_data, resolve_patient_ids
from src.bilun.domain.claims.loader import load_sut_claim_dataset
from tests.fixtures import synthetic_cohort as cohort

pytestmark = pytest.mark.unit

_REPO = Path(__file__).resolve().parents[3]
_OUT_DIR = DEFAULT_OUT_DIR
_CLAIMS_DIR = _OUT_DIR / "sut" / "claims"
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

# Hard-coded literal narrative strings for Patient 6 (S6, PK-Merz story) and Patient 7 (S7, ER).
_PATIENT_6_NARRATIVES: dict[str, str] = {
    "YAKINMA": "Başvuru tanısı: Pnömonit, gıda ve kusmuğa bağlı (J69.0).",
    "OYKU": (
        "79 yaşında erkek hasta, 08.06.2026 tarihinde Ic Hastaliklari bölümüne "
        "yatarak tedavi için başvurdu. Kayıtlı tanılar: Pnömonit, gıda ve kusmuğa bağlı; "
        "Esansiyel (primer) hipertansiyon; Disfaji."
    ),
    "Muayene Notu": (
        "Vital bulgular: tansiyon 118/70 mmHg, nabız 102/dk, SpO2 %90. "
        "Boy 172 cm, kilo 63,0 kg, VKİ 21,3."
    ),
    "Tedavi Notu": (
        "Uygulanan işlemler: Elektrokardiyogram; Akciğer grafisi P.A. (Tek yön); "
        "Kan kültürü (Aerob-anaerob) otomatik sistem; Nazogastrik sonda uygulaması. "
        "İlaçlar: NEOFLEKS %0,9 IZOTONIK SODYUM KLORUR SUDAKI COZELTISI PP-TORBA 1000 ML(SETLI); "
        "IESEF 1 G IV ENJEKSIYONLUK COZELTI TOZU; CLEXANE 4000 ANTI-XA IU/0.4 ML 10 KULL HAZIR ENJ; "
        "PK-MERZ IV INF. COZ. 2x500 ML; MADOPAR 125 MG 30 TB."
    ),
}

_PATIENT_7_NARRATIVES: dict[str, str] = {
    "YAKINMA": "Başvuru tanısı: Solunumda göğüs ağrısı (R07.1).",
    "OYKU": (
        "58 yaşında kadın hasta, 19.02.2026 tarihinde Acil Tip bölümüne "
        "acil olarak başvurdu. Kayıtlı tanılar: Solunumda göğüs ağrısı; Dispne."
    ),
    "Muayene Notu": (
        "Vital bulgular: tansiyon 134/82 mmHg, nabız 92/dk, SpO2 %97. "
        "Boy 162 cm, kilo 71,0 kg, VKİ 27,1."
    ),
    "Tedavi Notu": (
        "Uygulanan işlemler: Damar yolu açılması; Elektrokardiyogram; "
        "Akciğer grafisi P.A. (Tek yön); BT anjiografi, pulmoner arter. "
        "İlaçlar: PARTEMOL 1 G/100 ML INF ICIN COZ ICEREN 1 FLK."
    ),
}


@pytest.fixture(autouse=True)
def _fresh_claims_cache() -> Iterator[None]:
    """`load_sut_claim_dataset` caches by arguments: every test starts and ends with an empty cache."""
    load_sut_claim_dataset.cache_clear()
    yield
    load_sut_claim_dataset.cache_clear()


@pytest.fixture(scope="module")
def built_showcase() -> BuildResult:
    return build_showcase()


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


def test_clean_row_counts_and_anadata_field_rules_for_every_patient(
    built_showcase: BuildResult,
) -> None:
    ana_df = built_showcase.clean_tables["anadata_clean.parquet"]
    rec_df = built_showcase.clean_tables["recete_clean.parquet"]
    lab_df = built_showcase.clean_tables["lab_clean.parquet"]

    clean_counts = cohort.load_registry()["clean_counts"]
    assert ana_df.height == clean_counts["anadata_clean.parquet"] == cohort.patient_count()
    assert rec_df.height == clean_counts["recete_clean.parquet"]
    assert lab_df.height == clean_counts["lab_clean.parquet"]

    headers_df = built_showcase.tables["claim_headers.parquet"]
    diagnoses_df = built_showcase.tables["claim_diagnoses.parquet"]
    procs_df = built_showcase.tables["procedure_claim_lines.parquet"]
    perf_df = built_showcase.tables["performed_procedure_lines.parquet"]
    drugs_df = built_showcase.tables["drug_claim_lines.parquet"]

    raw_clinical = yaml.safe_load(CLINICAL_PATH.read_text(encoding="utf-8"))
    vitals_by_no = {p["patient_no"]: p["vitals"] for p in raw_clinical["patients"]}
    pathways = load_all()
    icd_df = pl.read_parquet(_REPO / "data/synthetic/reference/icd10_tr.parquet")
    icd_map = dict(zip(icd_df["code"].to_list(), icd_df["name_tr"].to_list(), strict=True))

    how_map = {
        "yatis": "yatarak tedavi için",
        "acil": "acil olarak",
        "poliklinik": "poliklinik muayenesi için",
        "gunubirlik": "günübirlik işlem için",
    }

    for idx in range(8):
        pno = idx + 1
        pid = f"SENTETIK-HASTA-{pno:04d}"
        row = ana_df.row(idx, named=True)
        hdr = headers_df.row(idx, named=True)
        pw = pathways[hdr["scenario_tag"]]
        pins = pw.showcase
        v = vitals_by_no[pno]

        assert row["HASTA_ID"] == pid == hdr["patient_id"]
        assert row["SQ_EPISODE"] == hdr["episode_id"]

        ref_date_str = hdr["admission_date"] or hdr["claim_start_date"]
        exp_dt = datetime.combine(datetime.strptime(ref_date_str, "%Y-%m-%d").date(), time.min)
        assert row["EPISODE_TARIH"] == exp_dt
        assert row["TANITARIH"] == exp_dt
        assert row["MIN_TANI_TARIH"] == exp_dt
        assert row["MAX_TANI_TARIH"] == exp_dt

        assert row["TANI_YASI"] == pins.age
        exp_sex = "E" if pins.sex == "M" else "K"
        assert row["CINSIYET"] == exp_sex

        assert row["KB-S"] == v["sbp"]
        assert row["KB-D"] == v["dbp"]
        assert row["Nabiz"] == v["pulse"]
        assert row["SPO2"] == v["spo2"]
        assert row["Boy"] == v["height_cm"]
        assert row["Kilo"] == float(v["weight_kg"])

        exp_bmi = float(
            (
                Decimal(str(v["weight_kg"]))
                / ((Decimal(str(v["height_cm"])) / Decimal("100")) ** 2)
            ).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
        )
        assert row["BMI"] == exp_bmi

        assert row["ILK_TANI_SON_TANI_GUN_FARKI"] == 0
        assert row["TOPLAM_GELIS_SAYISI"] == 1
        assert row["GELIS_SAYISI"] == 1
        assert row["GELIS_TIPI"] == hdr["claim_type"]
        assert row["SERVISADI"] == hdr["department"]
        assert row["TANIKODU"] == hdr["primary_icd10"]

        claim_dxs = diagnoses_df.filter(pl.col("claim_id") == hdr["claim_id"])[
            "icd10_code"
        ].to_list()
        assert claim_dxs[0] == hdr["primary_icd10"]
        assert row["TUM_EPS_TANILAR"] == ",".join(claim_dxs)
        assert row["TANI_TIPI"] == "Kesin Tani"

        assert row["Hipertansiyon Hastada"] is ("I10" in claim_dxs)
        assert row["Kalp Damar Hastada"] is False
        assert row["Diyabet Hastada"] is False
        assert row["Kan Hastaliklari Hastada"] is False

        assert row["kohort"] == "showcase"
        assert row["donem"] == str(exp_dt.year)

        # Narrative checks derived independently from table columns and reference ICD names
        prim_name = sentence_case_tr(icd_map[hdr["primary_icd10"]])
        all_names = "; ".join(sentence_case_tr(icd_map[c]) for c in claim_dxs)
        sex_word = "erkek" if exp_sex == "E" else "kadın"
        exp_yakinma = f"Başvuru tanısı: {prim_name} ({hdr['primary_icd10']})."
        exp_oyku = (
            f"{pins.age} yaşında {sex_word} hasta, {exp_dt.strftime('%d.%m.%Y')} tarihinde "
            f"{hdr['department']} bölümüne {how_map[hdr['claim_type']]} başvurdu. "
            f"Kayıtlı tanılar: {all_names}."
        )
        w_str = f"{v['weight_kg']:.1f}".replace(".", ",")
        b_str = f"{exp_bmi:.1f}".replace(".", ",")
        exp_muayene = (
            f"Vital bulgular: tansiyon {v['sbp']}/{v['dbp']} mmHg, nabız {v['pulse']}/dk, "
            f"SpO2 %{v['spo2']}. Boy {v['height_cm']} cm, kilo {w_str} kg, VKİ {b_str}."
        )

        claim_procs = (
            procs_df.filter(
                (pl.col("claim_id") == hdr["claim_id"])
                & (~pl.col("procedure_category").is_in(["laboratuvar", "yatak", "muayene"]))
            )["procedure_name"].to_list()
            + perf_df.filter(pl.col("claim_id") == hdr["claim_id"])["procedure_name"].to_list()
        )
        distinct_procs = list(dict.fromkeys(claim_procs))[:6]
        claim_drugs = list(
            dict.fromkeys(
                drugs_df.filter(pl.col("claim_id") == hdr["claim_id"])["drug_name"].to_list()
            )
        )[:8]
        exp_tedavi = (
            f"Uygulanan işlemler: {'; '.join(distinct_procs) if distinct_procs else 'yok'}. "
            f"İlaçlar: {'; '.join(claim_drugs) if claim_drugs else 'yok'}."
        )

        assert row["YAKINMA"] == exp_yakinma
        assert row["OYKU"] == exp_oyku
        assert row["Muayene Notu"] == exp_muayene
        assert row["Tedavi Notu"] == exp_tedavi

    # Literal hard-coded narrative checks for Patient 6 (S6) and Patient 7 (S7, ER)
    p6_row = ana_df.row(5, named=True)
    for col, expected_str in _PATIENT_6_NARRATIVES.items():
        assert p6_row[col] == expected_str, f"Patient 6 {col}"

    p7_row = ana_df.row(6, named=True)
    for col, expected_str in _PATIENT_7_NARRATIVES.items():
        assert p7_row[col] == expected_str, f"Patient 7 {col}"


def test_recete_clean_content_rules_for_all_21_billed_drug_lines(
    built_showcase: BuildResult,
) -> None:
    rec_df = built_showcase.clean_tables["recete_clean.parquet"]
    drugs_df = built_showcase.tables["drug_claim_lines.parquet"]
    assert rec_df.height == drugs_df.height == 21

    cw_df = pl.read_parquet(_REPO / "data/synthetic/reference/drug_crosswalk.parquet").filter(
        pl.col("titck_product_name").is_not_null()
    )
    cw_map = dict(
        zip(cw_df["barcode"].to_list(), cw_df["titck_product_name"].to_list(), strict=True)
    )
    pathways = load_all()
    siblings = load_siblings()
    claims_by_id = {c.header.claim_id: c for c in built_showcase.claims}
    unit_tr_map = {
        "vial": "flakon",
        "box": "kutu",
        "syringe": "enjektör",
        "tablet": "tablet",
        "capsule": "kapsül",
        "bottle": "şişe",
        "ampoule": "ampul",
        "bag": "torba",
    }

    assert rec_df["verilis_yolu"].null_count() == 0

    for idx in range(rec_df.height):
        rec = rec_df.row(idx, named=True)
        dl = drugs_df.row(idx, named=True)
        claim = claims_by_id[dl["claim_id"]]
        pw = (
            siblings["appendicitis_lap_appendectomy_itemized"]
            if claim.header.patient_id == "SENTETIK-HASTA-0001"
            else pathways[claim.header.scenario_tag]
        )
        line_to_entry = {lid: eid for eid, lids in claim.entry_line_ids.items() for lid in lids}
        entry_id = line_to_entry[dl["drug_claim_line_id"]]
        entry = next(d for d in pw.drugs if d.id == entry_id)

        exp_dt = datetime.combine(
            datetime.strptime(dl["drug_claim_date"], "%Y-%m-%d").date(), time.min
        )
        assert rec["HASTA_ID"] == dl["patient_id"]
        assert rec["RECETE_TARIH"] == exp_dt
        assert rec["RF_EPISODE"] == dl["episode_id"]
        assert rec["ilac_adi"] == dl["drug_name"]

        exp_titck = cw_map.get(dl["barkod"], dl["drug_name"])
        assert rec["ilac_adi_ham"] == exp_titck

        exp_unit = unit_tr_map[entry.unit]
        assert rec["dozaj_ham"] == f"{dl['quantity']} {exp_unit}"
        for raw_eng in ("bottle", "ampoule", "bag"):
            assert raw_eng not in rec["dozaj_ham"].lower()
        assert rec["verilis_yolu"] is not None

        assert rec["doz_mg"] is None
        assert rec["doz_birimi"] is None
        assert rec["siklik"] == entry.per_day
        assert rec["miktar"] == dl["quantity"]
        assert rec["kohort"] == "showcase"
        assert rec["donem"] == str(exp_dt.year)

        if entry.course_days is not None:
            assert rec["gun"] == pw.showcase.course_days[entry.id]
        elif entry.per_night is not None:
            assert rec["gun"] == pw.showcase.nights
        else:
            assert rec["gun"] is None


def test_slice_c1_fixups_dozaj_ham_and_route_from_titck(built_showcase: BuildResult) -> None:
    from scripts.synthetic.cohort import derive_route_from_titck, format_dozaj_ham

    expected_units = {
        "vial": "flakon",
        "box": "kutu",
        "syringe": "enjektör",
        "tablet": "tablet",
        "capsule": "kapsül",
        "bottle": "şişe",
        "ampoule": "ampul",
        "bag": "torba",
    }
    for eng, tr in expected_units.items():
        assert format_dozaj_ham(2, eng) == f"2 {tr}"

    rec_df = built_showcase.clean_tables["recete_clean.parquet"]
    assert rec_df["verilis_yolu"].null_count() == 0
    for doz in rec_df["dozaj_ham"].to_list():
        for raw_eng in ("bottle", "ampoule", "bag", "vial", "box", "syringe", "capsule"):
            assert f" {raw_eng}" not in doz

    rows_by_ham = {r["ilac_adi_ham"]: r["verilis_yolu"] for r in rec_df.to_dicts()}
    for substr in ("NEOFLEKS", "KLACID", "PARTEMOL"):
        matched = [v for k, v in rows_by_ham.items() if substr in k]
        assert matched and all(v == "Intravenöz" for v in matched), substr
    for substr in ("PREDNOL-L", "EQIZOLIN"):
        matched = [v for k, v in rows_by_ham.items() if substr in k]
        assert matched and all(v == "İntramusküler/İntravenöz" for v in matched), substr

    assert (
        derive_route_from_titck("PARTEMOL 1 G/100 ML INFUZYON ICIN COZELTI ICEREN FLAKON")
        == "Intravenöz"
    )
    assert derive_route_from_titck("KLACID I.V. 500 MG ENJEKTABL FLAKON") == "Intravenöz"
    assert derive_route_from_titck("PREDNOL-L 40 MG 1 AMPUL IM/IV") == "İntramusküler/İntravenöz"


@pytest.mark.parametrize(
    ("name", "route"),
    [
        ("PREDNOL-L 40 MG IM/IV ENJEKSİYONLUK LİYOFİLİZE TOZ", "İntramusküler/İntravenöz"),
        ("PARTEMOL 1 G/100 ML INFUZYON ICIN COZELTI ICEREN FLAKON", "Intravenöz"),
        ("PARACEROL 10 MG/ML IV İNFÜZYON İÇİN ÇÖZELTİ İÇEREN FLAKON", "Intravenöz"),
        ("IESEF 1 G IV ENJEKSİYONLUK ÇÖZELTİ HAZIRLAMAK İÇİN TOZ", "Intravenöz"),
        ("KLACID 500 MG I.V. LİYOFİLİZE TOZ İÇEREN FLAKON", "Intravenöz"),
        ("MADOPAR 125 MG TABLET, 30 ADET", "Ağızdan (Oral)"),
        ("ORNEK 20 MG KAPSÜL, 28 ADET", "Ağızdan (Oral)"),
        ("ORNEK 500 MG FİLM KAPLI, 14 ADET", "Ağızdan (Oral)"),
        ("İPRAVENT NEBÜLİZASYON İÇİN İNHALASYON ÇÖZELTİSİ", "İnhalasyon"),
        ("ORNEK 40 MG SUBKÜTAN ENJEKSİYON", "Subkütan"),
        (
            "CLEXANE 4000 ANTI-XA IU/0,4 ML ENJEKSİYONLUK ÇÖZELTİ İÇEREN KULLANIMA HAZIR ENJEKTÖR",
            None,
        ),
        ("NEOFLEKS %0,9 IZOTONIK SODYUM KLORUR SUDAKI ÇÖZELTİSİ PP-TORBA1000 ML(SETLI)", None),
        # The same words in their ASCII spelling (the TITCK names come both ways), upper and lower case.
        ("PREDNOL-L 40 MG IM/IV ENJEKSIYONLUK TOZ", "İntramusküler/İntravenöz"),
        ("prednol-l 40 mg im/iv enjeksiyonluk toz", "İntramusküler/İntravenöz"),
        ("ORNEK 500 MG INTRAVENOZ ENJEKSIYON", "Intravenöz"),
        ("ORNEK 500 MG İNTRAVENÖZ ENJEKSİYON", "Intravenöz"),
        ("ORNEK 1 G INFUZYON ICIN COZELTI", "Intravenöz"),
        ("ORNEK 1 G İNFÜZYON İÇİN ÇÖZELTİ", "Intravenöz"),
        ("ORNEK 1 G infüzyon için çözelti", "Intravenöz"),
        ("ORNEK 500 MG I.V. ENJEKSIYON", "Intravenöz"),
        (
            "PLAPANT 40 MG İV ENJEKSİYONLUK ÇÖZELTİ HAZIRLAMAK İÇİN LİYOFİLİZE TOZ, 1 ADET",
            "Intravenöz",
        ),
        ("ORNEK 40 MG IV ENJEKSIYON", "Intravenöz"),
        ("ORNEK 40 MG iv enjeksiyon", "Intravenöz"),
        ("ORNEK 20 MG TABLET, 28 ADET", "Ağızdan (Oral)"),
        ("ORNEK 20 MG KAPSUL, 28 ADET", "Ağızdan (Oral)"),
        ("ORNEK 20 MG kapsül, 28 ADET", "Ağızdan (Oral)"),
        ("ORNEK 500 MG FILM KAPLI TABLET, 14 ADET", "Ağızdan (Oral)"),
        ("ORNEK 500 MG film kaplı, 14 ADET", "Ağızdan (Oral)"),
        ("VENTOLIN INHALASYON COZELTISI", "İnhalasyon"),
        ("VENTOLIN İNHALASYON ÇÖZELTİSİ", "İnhalasyon"),
        ("ORNEK NEBUL ICIN COZELTI", "İnhalasyon"),
        ("ORNEK NEBÜL İÇİN ÇÖZELTİ", "İnhalasyon"),
        ("ornek nebül", "İnhalasyon"),
        ("ORNEK 40 MG SUBKUTAN ENJEKSIYON", "Subkütan"),
        ("ORNEK 40 MG subkütan enjeksiyon", "Subkütan"),
        # Only whole words count for IV (also at the start and at the end), and no word at all: no route.
        ("ORNEK 40 MG IV", "Intravenöz"),
        ("IV ORNEK 40 MG", "Intravenöz"),
        ("ORNEK DIV 5 MG", None),
        ("TRIV 5 MG", None),
        ("ORNEK 5 MG ENJEKTABL", None),
    ],
)
def test_derive_route_from_titck_reads_only_what_the_name_states(
    name: str, route: str | None
) -> None:
    from scripts.synthetic.cohort import derive_route_from_titck

    assert derive_route_from_titck(name) == route


def test_dozaj_ham_without_a_unit_is_the_bare_quantity() -> None:
    from scripts.synthetic.cohort import format_dozaj_ham

    assert format_dozaj_ham(3, None) == "3"
    assert format_dozaj_ham(3, "") == "3"
    assert format_dozaj_ham(3, "capsule") == "3 kapsül"


def test_dozaj_ham_keeps_a_unit_without_a_turkish_word_as_written() -> None:
    """No pathway unit is such a unit (the next test), but the function is not tied to the pathways."""
    from scripts.synthetic.cohort import format_dozaj_ham

    assert format_dozaj_ham(2, "sachet") == "2 sachet"


def test_every_schema_unit_has_a_turkish_word() -> None:
    """A unit added to the pathway schema forces a Turkish word here (`capsule` was missing once)."""
    assert set(_UNIT_TR) == set(get_args(Unit))


def _string_constants_returned(path: Path, function_name: str) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=path.name)
    function = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == function_name
    )
    return {
        node.value.value
        for node in ast.walk(function)
        if isinstance(node, ast.Return)
        and isinstance(node.value, ast.Constant)
        and isinstance(node.value.value, str)
    }


def test_declared_route_vocabulary_is_what_derive_route_from_titck_returns() -> None:
    returned = _string_constants_returned(
        _REPO / "scripts/synthetic/cohort/clean.py", "derive_route_from_titck"
    )
    assert returned == set(get_args(DrugRoute)), "the YAML vocabulary and the derivation differ"
    assert "Subkütan" in returned


def test_product_routes_come_from_the_titck_name_or_from_drug_routes(
    built_showcase: BuildResult,
) -> None:
    from scripts.synthetic.cohort import derive_route_from_titck

    rec_df = built_showcase.clean_tables["recete_clean.parquet"]
    assert rec_df["verilis_yolu"].null_count() == 0

    clexane = rec_df.filter(pl.col("ilac_adi_ham").str.contains("CLEXANE"))
    assert clexane["verilis_yolu"].to_list() == ["Subkütan"] * 3
    neofleks_saline = rec_df.filter(pl.col("ilac_adi_ham").str.contains("NEOFLEKS %0,9"))
    assert neofleks_saline["verilis_yolu"].to_list() == ["Intravenöz"]

    # The declared routes serve exactly the four rows whose TITCK name states no route.
    names = rec_df["ilac_adi_ham"].to_list()
    without_route_in_name = [name for name in names if derive_route_from_titck(name) is None]
    assert len(without_route_in_name) == 4
    assert all(("CLEXANE" in name) or ("NEOFLEKS %0,9" in name) for name in without_route_in_name)

    declared = load_clinical().drug_routes
    assert declared is not None
    assert declared.basis == "judgment"
    assert declared.by_barcode == {
        "8699809950696": "Subkütan",
        "8697637690128": "Intravenöz",
    }
    billed_barcodes = set(built_showcase.tables["drug_claim_lines.parquet"]["barkod"].to_list())
    assert set(declared.by_barcode) <= billed_barcodes


def test_resolve_drug_route_cases() -> None:
    clexane = "CLEXANE 4000 ANTI-XA IU/0,4 ML ENJEKSİYONLUK ÇÖZELTİ İÇEREN KULLANIMA HAZIR ENJEKTÖR"
    klacid = "KLACID 500 MG I.V. LİYOFİLİZE TOZ İÇEREN FLAKON, 1 ADET"
    # declared only
    assert resolve_drug_route(clexane, "8699809950696", {"8699809950696": "Subkütan"}) == "Subkütan"
    # derived only (the declarations are for other products)
    assert (
        resolve_drug_route(klacid, "8699548270482", {"8699809950696": "Subkütan"}) == "Intravenöz"
    )
    # derived and declared agree
    assert (
        resolve_drug_route(klacid, "8699548270482", {"8699548270482": "Intravenöz"}) == "Intravenöz"
    )
    # derived and declared disagree: the error names the product, the barcode and both routes
    with pytest.raises(
        CleanTableError,
        match=r"declares 'Subkütan' for 'KLACID 500 MG .*8699548270482.*'Intravenöz'",
    ):
        resolve_drug_route(klacid, "8699548270482", {"8699548270482": "Subkütan"})
    # neither: the error names the product and the barcode and says where to declare it
    with pytest.raises(
        CleanTableError,
        match=r"'CLEXANE 4000.*\(barcode 8699809950696\).*declare it in drug_routes",
    ):
        resolve_drug_route(clexane, "8699809950696", {})


def _clinical_with_routes(by_barcode: dict[str, DrugRoute]) -> ShowcaseClinical:
    base = load_clinical()
    assert base.drug_routes is not None
    return ShowcaseClinical(
        schema_version=1,
        drug_routes=DrugRoutes(
            by_barcode=by_barcode, basis="judgment", source=base.drug_routes.source
        ),
        patients=base.patients,
    )


@pytest.mark.parametrize(
    ("barcode", "product"),
    [("8699809950696", "CLEXANE"), ("8697637690128", "NEOFLEKS %0,9")],
)
def test_removing_a_declared_route_makes_the_build_raise(
    built_showcase: BuildResult, barcode: str, product: str
) -> None:
    declared = load_clinical().drug_routes
    assert declared is not None
    kept = {k: v for k, v in declared.by_barcode.items() if k != barcode}
    assert len(kept) == 1
    with pytest.raises(CleanTableError, match=rf"{product}.*{barcode}.*declare it in drug_routes"):
        build_clean_tables(built_showcase.claims, clinical=_clinical_with_routes(kept))


def test_only_a_clinical_document_can_carry_routes(built_showcase: BuildResult) -> None:
    """A bare list of patients has no `drug_routes`, so the four products without a route name fail."""
    patients = list(load_clinical().patients)
    with pytest.raises(CleanTableError, match=r"CLEXANE.*8699809950696.*declare it in drug_routes"):
        build_clean_tables(built_showcase.claims, clinical=patients)


def test_a_document_without_a_drug_routes_block_makes_the_build_raise_a_clean_table_error(
    built_showcase: BuildResult,
) -> None:
    """The four products whose TITCK name states no route need the block: no block is a CleanTableError."""
    base = load_clinical()
    without = ShowcaseClinical(schema_version=1, drug_routes=None, patients=base.patients)
    with pytest.raises(CleanTableError, match=r"CLEXANE.*8699809950696.*declare it in drug_routes"):
        build_clean_tables(built_showcase.claims, clinical=without)


def test_a_declared_route_that_contradicts_the_titck_name_makes_the_build_raise(
    built_showcase: BuildResult,
) -> None:
    declared = load_clinical().drug_routes
    assert declared is not None
    drug_lines = built_showcase.tables["drug_claim_lines.parquet"]
    klacid_barcode = drug_lines.filter(pl.col("drug_name").str.contains("KLACID"))["barkod"][0]
    wrong = {**declared.by_barcode, klacid_barcode: "Subkütan"}
    with pytest.raises(
        CleanTableError, match=rf"declares 'Subkütan' for 'KLACID.*{klacid_barcode}"
    ):
        build_clean_tables(built_showcase.claims, clinical=_clinical_with_routes(wrong))


# --- 3. Turkish sentence-case helper and four comorbidity boolean derivations ------------------


def test_turkish_sentence_case_helper_and_four_boolean_derivations(
    built_showcase: BuildResult,
) -> None:
    assert sentence_case_tr("İYİ") == "İyi"
    assert sentence_case_tr("IŞIK") == "Işık"
    assert (
        sentence_case_tr("ESANSİYEL (PRİMER) HİPERTANSİYON") == "Esansiyel (primer) hipertansiyon"
    )
    assert sentence_case_tr("") == ""

    ana_df = built_showcase.clean_tables["anadata_clean.parquet"]
    expected_ht_by_story = {
        "S1": False,
        "S2": True,
        "S3": True,
        "S4": True,
        "S5": True,
        "S6": True,
        "S7": False,
        "S8": False,
    }
    for idx, (story, exp_ht) in enumerate(expected_ht_by_story.items()):
        row = ana_df.row(idx, named=True)
        assert row["Hipertansiyon Hastada"] is exp_ht, story
        assert row["Kalp Damar Hastada"] is False, story
        assert row["Diyabet Hastada"] is False, story
        assert row["Kan Hastaliklari Hastada"] is False, story

    # Direct chapter-level mapping checks on each of the four ICD blocks
    assert derive_comorbidity_flags(["I10"]) == {
        "Hipertansiyon Hastada": True,
        "Kalp Damar Hastada": False,
        "Diyabet Hastada": False,
        "Kan Hastaliklari Hastada": False,
    }
    assert derive_comorbidity_flags(["I25.1", "E11.9", "D50.9"]) == {
        "Hipertansiyon Hastada": False,
        "Kalp Damar Hastada": True,
        "Diyabet Hastada": True,
        "Kan Hastaliklari Hastada": True,
    }


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


def test_smoke_load_sut_build_context_on_committed_showcase() -> None:
    ctx = load_sut_build_context(
        billing_workers=1,
        sut_data_mode="synthetic_demo",
        sut_claims_dir=_CLAIMS_DIR,
        sut_clean_dir=_CLEAN_DIR,
    )
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


def test_cli_check_fails_when_clean_table_or_clean_counts_is_changed(
    built_showcase: BuildResult,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main(["--check"]) == 0
    capsys.readouterr()

    copy_dir = tmp_path / "dataset_copy"
    write_showcase(built_showcase, copy_dir)
    assert main(["--out", str(copy_dir), "--check"]) == 0
    capsys.readouterr()

    # (a) Mutate one value in anadata_clean.parquet in the copy -> --check exits 1
    ana_path = copy_dir / "sut" / "clean" / "anadata_clean.parquet"
    ana_df = pl.read_parquet(ana_path)
    mutated_ana = ana_df.with_columns(
        pl.when(pl.col("HASTA_ID") == "SENTETIK-HASTA-0001")
        .then(pl.lit(135, dtype=pl.Int64))
        .otherwise(pl.col("KB-S"))
        .alias("KB-S")
    )
    mutated_ana.write_parquet(ana_path)
    assert main(["--out", str(copy_dir), "--check"]) == 1
    assert "anadata_clean.parquet" in capsys.readouterr().err

    # Restore anadata_clean.parquet -> --check exits 0
    ana_df.write_parquet(ana_path)
    assert main(["--out", str(copy_dir), "--check"]) == 0
    capsys.readouterr()

    # (b) Mutate clean_counts in cohort_registry.json -> --check exits 1
    reg_path = copy_dir / "cohort_registry.json"
    orig_reg_text = reg_path.read_text(encoding="utf-8")
    reg_data = json.loads(orig_reg_text)
    reg_data["clean_counts"]["recete_clean.parquet"] = 99
    reg_path.write_text(
        json.dumps(reg_data, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    assert main(["--out", str(copy_dir), "--check"]) == 1
    assert "cohort_registry.json" in capsys.readouterr().err


def test_two_builds_produce_byte_identical_clean_tables(
    tmp_path: Path,
    built_showcase: BuildResult,
) -> None:
    dir_a = tmp_path / "build_a"
    dir_b = tmp_path / "build_b"
    assert main(["--out", str(dir_a)]) == 0
    assert main(["--out", str(dir_b)]) == 0

    direct_dir = tmp_path / "direct_clean"
    written = write_clean_tables(
        built_showcase.clean_tables,
        direct_dir,
        claims_tables=built_showcase.tables,
    )
    assert set(written) == set(CLEAN_TABLE_FILES)

    for name in CLEAN_TABLE_FILES:
        bytes_a = (dir_a / "sut" / "clean" / name).read_bytes()
        bytes_b = (dir_b / "sut" / "clean" / name).read_bytes()
        bytes_direct = written[name].read_bytes()
        assert bytes_a == bytes_b == bytes_direct, f"Clean Parquet bytes differed for {name}"


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


# --- 8. In-memory defect detection proofs ------------------------------------------------------


def test_in_memory_defects_are_caught(built_showcase: BuildResult) -> None:
    # (a) A recete row with a drug that is not billed:
    # 1) Modifying ilac_adi on an existing recete row
    rec_df = built_showcase.clean_tables["recete_clean.parquet"]
    tampered_rec_df = rec_df.with_columns(
        pl.when(pl.int_range(0, pl.len()) == 0)
        .then(pl.lit("FATURALANMAMIS SAHTE ILAC 500 MG"))
        .otherwise(pl.col("ilac_adi"))
        .alias("ilac_adi")
    )
    bad_clean_rec = {
        **built_showcase.clean_tables,
        "recete_clean.parquet": tampered_rec_df,
    }
    with pytest.raises(
        CleanTableError,
        match="does not match any billed drug line in drug_claim_lines.parquet",
    ):
        validate_clean_tables(bad_clean_rec, built_showcase.tables)

    # 2) Appending an extra unbilled drug row to recete_clean
    extra_rec_row = pl.DataFrame(
        [
            {
                **rec_df.row(0, named=True),
                "ilac_adi": "FATURALANMAMIS EK ILAC 100 MG",
            }
        ],
        schema=RECETE_CLEAN_SCHEMA,
        strict=True,
    )
    bad_clean_extra_rec = {
        **built_showcase.clean_tables,
        "recete_clean.parquet": pl.concat([rec_df, extra_rec_row]),
    }
    with pytest.raises(
        CleanTableError,
        match="does not match any billed drug line in drug_claim_lines.parquet",
    ):
        validate_clean_tables(bad_clean_extra_rec, built_showcase.tables)

    # (b) An anadata row whose TUM_EPS_TANILAR differs from the claim:
    ana_df = built_showcase.clean_tables["anadata_clean.parquet"]
    tampered_ana_df = ana_df.with_columns(
        pl.when(pl.col("HASTA_ID") == "SENTETIK-HASTA-0002")
        .then(pl.lit("J44.0,I10"))  # missing J18.9 from the claim's diagnoses
        .otherwise(pl.col("TUM_EPS_TANILAR"))
        .alias("TUM_EPS_TANILAR")
    )
    bad_clean_ana = {
        **built_showcase.clean_tables,
        "anadata_clean.parquet": tampered_ana_df,
    }
    with pytest.raises(
        CleanTableError,
        match=r"anadata_clean\.parquet\.TUM_EPS_TANILAR for SENTETIK-HASTA-0002",
    ):
        validate_clean_tables(bad_clean_ana, built_showcase.tables)

    with pytest.raises(
        BuildError,
        match=r"anadata_clean\.parquet\.TUM_EPS_TANILAR for SENTETIK-HASTA-0002",
    ):
        validate_cohort_registry(built_showcase.registry, built_showcase.tables, bad_clean_ana)

    # (c) A vitals block for a missing patient (and a patient missing its vitals block):
    base_clinical = load_clinical()
    extra_patient_clinical = ShowcaseClinical(
        schema_version=1,
        drug_routes=base_clinical.drug_routes,
        patients=[
            *base_clinical.patients[:7],
            PatientClinical(
                patient_no=99,
                vitals=base_clinical.patients[7].vitals,
                basis="judgment",
                source=base_clinical.patients[7].source,
            ),
        ],
    )
    problems = check_clinical(extra_patient_clinical)
    assert [p.check for p in problems] == ["clinical.patient_numbers"]
    with pytest.raises(ClinicalLoadError) as exc_info:
        build_showcase(clinical=extra_patient_clinical)
    assert [p.check for p in exc_info.value.problems] == ["clinical.patient_numbers"]

    with pytest.raises(CleanTableError, match="missing clinical vitals for patient_no 8"):
        build_clean_tables(built_showcase.claims, clinical=extra_patient_clinical)


# --- 9. anadata_clean against the claims, checked with expressions (no loop over the rows) -----------


Tables = dict[str, pl.DataFrame]


def _ana_set(
    ana: pl.DataFrame, patient_no: int, column: str, value: str | int | None
) -> pl.DataFrame:
    """Copy of the anadata table with one cell of one patient's row replaced."""
    return ana.with_columns(
        pl.when(pl.col("HASTA_ID") == f"SENTETIK-HASTA-{patient_no:04d}")
        .then(pl.lit(value, dtype=ana.schema[column]))
        .otherwise(pl.col(column))
        .alias(column)
    )


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        pytest.param(
            # patient 8 has no lab rows, so the missing row is the first thing the check meets
            lambda ana, claims: (pl.concat([ana.head(7), ana.slice(8)]), claims),
            rf"anadata_clean\.parquet row count \({cohort.patient_count() - 1}\) does not equal claim_headers\.parquet row count \({cohort.patient_count()}\)",
            id="a_row_is_missing",
        ),
        pytest.param(
            lambda ana, claims: (
                pl.concat([ana.slice(1, 1), ana.slice(0, 1), ana.slice(2)]),
                claims,
            ),
            r"\(HASTA_ID, SQ_EPISODE\) mismatch against claim_headers\.parquet at row 0: "
            r"expected \(SENTETIK-HASTA-0001, B-SENTETIK-HASTA-0001-001\), "
            r"got \(SENTETIK-HASTA-0002, B-SENTETIK-HASTA-0002-001\)",
            id="two_rows_in_the_other_order",
        ),
        pytest.param(
            lambda ana, claims: (_ana_set(ana, 5, "HASTA_ID", "SENTETIK-HASTA-0099"), claims),
            r"at row 4: expected \(SENTETIK-HASTA-0005, B-SENTETIK-HASTA-0005-001\), "
            r"got \(SENTETIK-HASTA-0099, B-SENTETIK-HASTA-0005-001\)",
            id="another_patient_id",
        ),
        pytest.param(
            lambda ana, claims: (_ana_set(ana, 5, "HASTA_ID", None), claims),
            r"at row 4: expected \(SENTETIK-HASTA-0005, B-SENTETIK-HASTA-0005-001\), "
            r"got \(null, B-SENTETIK-HASTA-0005-001\)",
            id="no_patient_id",
        ),
        pytest.param(
            lambda ana, claims: (
                _ana_set(ana, 5, "SQ_EPISODE", "B-SENTETIK-HASTA-0099-001"),
                claims,
            ),
            r"at row 4: expected \(SENTETIK-HASTA-0005, B-SENTETIK-HASTA-0005-001\), "
            r"got \(SENTETIK-HASTA-0005, B-SENTETIK-HASTA-0099-001\)",
            id="another_episode",
        ),
        pytest.param(
            lambda ana, claims: (_ana_set(ana, 5, "SQ_EPISODE", None), claims),
            r"at row 4: expected \(SENTETIK-HASTA-0005, B-SENTETIK-HASTA-0005-001\), "
            r"got \(SENTETIK-HASTA-0005, null\)",
            id="no_episode",
        ),
        pytest.param(
            lambda ana, claims: (_ana_set(ana, 5, "GELIS_TIPI", "acil"), claims),
            r"anadata_clean\.parquet\.GELIS_TIPI for SENTETIK-HASTA-0005: expected 'yatis', got 'acil'",
            id="another_claim_type",
        ),
        pytest.param(
            lambda ana, claims: (
                _ana_set(_ana_set(ana, 5, "GELIS_TIPI", "acil"), 3, "GELIS_TIPI", "acil"),
                claims,
            ),
            # Two rows are wrong in the same column: the first one is the one named.
            r"anadata_clean\.parquet\.GELIS_TIPI for SENTETIK-HASTA-0003: expected 'yatis', got 'acil'",
            id="the_first_of_two_wrong_rows_is_named",
        ),
        pytest.param(
            lambda ana, claims: (
                _ana_set(_ana_set(ana, 2, "SERVISADI", "X"), 1, "TANIKODU", "Z99"),
                claims,
            ),
            # The columns are checked one after the other: the department of patient 2 comes before the
            # diagnosis code of patient 1, although patient 1 is the earlier row.
            r"anadata_clean\.parquet\.SERVISADI for SENTETIK-HASTA-0002: "
            r"expected 'Gogus Hastaliklari', got 'X'",
            id="department_before_primary_diagnosis",
        ),
        pytest.param(
            lambda ana, claims: (_ana_set(ana, 4, "TANIKODU", None), claims),
            r"anadata_clean\.parquet\.TANIKODU for SENTETIK-HASTA-0004: expected 'N10', got None",
            id="no_primary_diagnosis",
        ),
        pytest.param(
            lambda ana, claims: (_ana_set(ana, 6, "TUM_EPS_TANILAR", ""), claims),
            r"anadata_clean\.parquet\.TUM_EPS_TANILAR for SENTETIK-HASTA-0006 "
            r"\(B-SENTETIK-HASTA-0006-001\): expected 'J69\.0,I10,R13' from claim_diagnoses\.parquet, got ''",
            id="no_diagnoses",
        ),
        pytest.param(
            lambda ana, claims: (
                ana,
                {
                    **claims,
                    "claim_diagnoses.parquet": claims["claim_diagnoses.parquet"].filter(
                        pl.col("episode_id") != "B-SENTETIK-HASTA-0003-001"
                    ),
                },
            ),
            r"anadata_clean\.parquet\.TUM_EPS_TANILAR for SENTETIK-HASTA-0003 "
            r"\(B-SENTETIK-HASTA-0003-001\): expected '' from claim_diagnoses\.parquet, "
            r"got 'M48\.06,I10'",
            id="claim_without_diagnoses",
        ),
        pytest.param(
            lambda ana, claims: (
                _ana_set(
                    pl.concat([ana.slice(1, 1), ana.slice(0, 1), ana.slice(2)]),
                    5,
                    "GELIS_TIPI",
                    "acil",
                ),
                claims,
            ),
            r"\(HASTA_ID, SQ_EPISODE\) mismatch against claim_headers\.parquet at row 0",
            id="the_pair_is_checked_before_the_columns",
        ),
    ],
)
def test_the_anadata_table_is_checked_against_claim_headers_and_diagnoses(
    built_showcase: BuildResult,
    mutate: Callable[[pl.DataFrame, Tables], tuple[pl.DataFrame, Tables]],
    message: str,
) -> None:
    clean = built_showcase.clean_tables
    validate_clean_tables(clean, built_showcase.tables)  # the untouched tables are valid
    ana, claims = mutate(clean["anadata_clean.parquet"], built_showcase.tables)
    with pytest.raises(CleanTableError, match=message):
        validate_clean_tables({**clean, "anadata_clean.parquet": ana}, claims)


def test_a_changed_age_or_sex_in_anadata_is_found_by_the_registry_digest_not_by_validate_clean_tables(
    built_showcase: BuildResult,
) -> None:
    """Only the pathways say how old a patient is; the tables hold no age or sex to compare with.

    Patient 5 (a woman with no lab rows) becoming a man, and patient 1 (no creatinine) a year older, pass
    `validate_clean_tables`: nothing in the claims or in the lab rows contradicts them. The digest in
    `cohort_registry.json` does, and so does `build --check`.
    """
    clean = built_showcase.clean_tables
    ana = clean["anadata_clean.parquet"]
    for column, patient_no, value in (("CINSIYET", 5, "E"), ("TANI_YASI", 1, 35)):
        changed = _ana_set(ana, patient_no, column, value)
        assert not changed.equals(ana)
        tampered = {**clean, "anadata_clean.parquet": changed}
        validate_clean_tables(tampered, built_showcase.tables)
        with pytest.raises(BuildError, match=r"clean_tables_digest mismatch on: \['anadata_clean"):
            validate_cohort_registry(built_showcase.registry, built_showcase.tables, tampered)


# AGENTS.md section 9: no Python loop over the rows, columns, slices or partitions of a DataFrame, and
# none over a Series. These are the ways to get one that the source of `labs.py` and `clean.py` must not use.
_ROW_ITERATION_ATTRIBUTES = frozenset(
    {
        "iter_rows",
        "rows",
        "row",
        "to_dicts",
        "to_dict",
        "iterrows",
        "itertuples",
        "map_elements",
        "map_rows",
        "apply",
        "iter_columns",
        "iter_slices",
        "partition_by",
        "to_numpy",
    }
)
# Builtins that walk their argument: handing them a `.to_list()` or a Series is a loop over its rows.
_ITERATING_BUILTINS = frozenset(
    {
        "zip",
        "enumerate",
        "map",
        "filter",
        "sorted",
        "reversed",
        "list",
        "tuple",
        "set",
        "frozenset",
        "dict",
        "any",
        "all",
        "sum",
        "min",
        "max",
        "next",
        "iter",
    }
)
_SERIES_GETTERS = frozenset({"get_column", "to_series"})

# The one place where a DataFrame is read column by column: the 96-line reference CSV becomes one frozen
# spec object per line (each holds a parsed `abnormal_states` grammar), and a spec is a Python object that
# no expression can build. (file, function, what) -> why.
_ALLOWED_DATAFRAME_LOOPS = {
    ("labs.py", "load_lab_reference_df", "attribute iter_columns"): (
        "builds the 96 parameter spec objects of lab_reference.csv, once, from the typed columns"
    ),
}


def _has_call(node: ast.AST, attribute: str) -> bool:
    return any(
        isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == attribute
        for n in ast.walk(node)
    )


def _is_series(node: ast.AST) -> bool:
    """`frame["column"]`, `frame.get_column(...)` or `.to_series()`: a Series, which no `for` may walk."""
    if isinstance(node, ast.Subscript):
        return isinstance(node.slice, ast.Constant) and isinstance(node.slice.value, str)
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr in _SERIES_GETTERS
    )


class _LoopFinder(ast.NodeVisitor):
    def __init__(self) -> None:
        self.scope: list[str] = ["<module>"]
        self.findings: list[tuple[int, str, str]] = []

    def _add(self, node: ast.AST, what: str) -> None:
        self.findings.append((getattr(node, "lineno", 0), self.scope[-1], what))

    def _walks(self, node: ast.AST, owner: ast.AST) -> None:
        """`node` is walked by `owner` (a `for`, a comprehension, or a call to an iterating builtin)."""
        if _has_call(node, "to_list"):
            self._add(owner, "to_list iterated")
        elif _is_series(node):
            self._add(owner, "Series iterated")

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self.scope.append(node.name)
        self.generic_visit(node)
        self.scope.pop()

    visit_AsyncFunctionDef = visit_FunctionDef  # type: ignore[assignment]

    def visit_Attribute(self, node: ast.Attribute) -> None:
        if node.attr in _ROW_ITERATION_ATTRIBUTES:
            self._add(node, f"attribute {node.attr}")
        self.generic_visit(node)

    def visit_For(self, node: ast.For) -> None:
        self._walks(node.iter, node)
        self.generic_visit(node)

    def visit_comprehension(self, node: ast.comprehension) -> None:
        self._walks(node.iter, node.iter)
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        if isinstance(node.func, ast.Name) and node.func.id in _ITERATING_BUILTINS:
            for argument in node.args:
                self._walks(argument.value if isinstance(argument, ast.Starred) else argument, node)
        self.generic_visit(node)


def dataframe_loop_findings(source: str) -> list[tuple[int, str, str]]:
    """(line, enclosing function, what) for every loop over DataFrame rows, columns or a Series in `source`.

    It reads the syntax only, so it cannot follow a list that was made by `.to_list()` into a variable and
    walked later; the two ways in that it does see are a `.to_list()` (or a Series) that is walked on the
    spot by a `for`, a comprehension or a builtin that iterates, and the attributes above.
    """
    finder = _LoopFinder()
    finder.visit(ast.parse(source))
    return finder.findings


@pytest.mark.parametrize(
    "snippet",
    [
        pytest.param("for x in df['a'].to_list():\n    pass", id="for_over_to_list"),
        pytest.param("y = [x for x in df['a'].to_list()]", id="comprehension_over_to_list"),
        pytest.param("y = list(zip(df['a'].to_list(), df['b'].to_list()))", id="zip_of_to_lists"),
        pytest.param("y = dict(zip(a['k'].to_list(), a['v'].to_list()))", id="dict_of_zip"),
        pytest.param("y = sorted(df['a'].to_list())", id="sorted_to_list"),
        pytest.param("y = zip(*df['a'].to_list())", id="starred_to_list"),
        pytest.param("for x in df['a']:\n    pass", id="for_over_a_series"),
        pytest.param("for x in df.get_column('a'):\n    pass", id="for_over_get_column"),
        pytest.param("y = [x for x in df['a']]", id="comprehension_over_a_series"),
        pytest.param("y = sum(df['a'])", id="sum_of_a_series"),
        pytest.param("y = list(df.to_series())", id="list_of_to_series"),
        pytest.param("df.iter_rows()", id="iter_rows"),
        pytest.param("df.iter_columns()", id="iter_columns"),
        pytest.param("df.iter_slices(10)", id="iter_slices"),
        pytest.param("df.partition_by('a')", id="partition_by"),
        pytest.param("df['a'].to_numpy()", id="to_numpy"),
        pytest.param("df.to_dicts()", id="to_dicts"),
        pytest.param("df.row(0, named=True)", id="row"),
        pytest.param("df.rows()", id="rows"),
        pytest.param("df['a'].map_elements(f)", id="map_elements"),
    ],
)
def test_the_loop_finder_flags_each_way_to_loop_over_dataframe_data(snippet: str) -> None:
    assert dataframe_loop_findings(snippet), snippet


@pytest.mark.parametrize(
    "snippet",
    [
        pytest.param("for line in claim.procedures:\n    pass", id="objects"),
        pytest.param("y = [s.key for s in specs]", id="spec_objects"),
        pytest.param("y = dict(zip(names, cells, strict=True))", id="zip_of_names"),
        pytest.param("for a, b in (('x', 'y'), ('z', 'w')):\n    pass", id="tuple_literal"),
        pytest.param("y = max((line['limit_decimals'], *map(f, tokens)))", id="mapping_value"),
        pytest.param("y = df['a'][0]", id="indexing_a_series"),
        pytest.param("y = df['a'].to_list()", id="to_list_not_iterated"),
        pytest.param("y = df.select(pl.col('a')).item()", id="item"),
        pytest.param("for name in df.columns:\n    pass", id="column_names"),
    ],
)
def test_the_loop_finder_leaves_loops_over_python_objects_alone(snippet: str) -> None:
    assert dataframe_loop_findings(snippet) == [], snippet


def test_the_loop_finder_names_the_function_it_finds_a_loop_in() -> None:
    source = "def outer():\n    def inner():\n        return df.partition_by('a')\n    return 1\n"
    assert dataframe_loop_findings(source) == [(3, "inner", "attribute partition_by")]
    assert dataframe_loop_findings("df.rows()") == [(1, "<module>", "attribute rows")]


@pytest.mark.parametrize("filename", ["clean.py", "labs.py"])
def test_clean_and_labs_import_hygiene_and_no_dataframe_row_loops(filename: str) -> None:
    source = (_REPO / "scripts/synthetic/cohort" / filename).read_text(encoding="utf-8")
    tree = ast.parse(source, filename=filename)
    imported_modules: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported_modules.append(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.append(node.module)

    found = Counter((function, what) for _, function, what in dataframe_loop_findings(source))
    allowed = {
        (function, what): why
        for (name, function, what), why in _ALLOWED_DATAFRAME_LOOPS.items()
        if name == filename
    }
    unexpected = {key: count for key, count in found.items() if key not in allowed}
    assert not unexpected, (
        f"{filename} loops over DataFrame data (AGENTS.md section 9): {unexpected}"
    )
    # An allowlist entry must be used exactly once, so that a loop cannot be added next to it and a
    # stale entry cannot stay behind.
    assert {key: found.get(key, 0) for key in allowed} == dict.fromkeys(allowed, 1)

    for mod in imported_modules:
        assert not mod.startswith("pandas"), f"{filename} imports pandas: {mod}"
        assert not mod.startswith("reports"), f"{filename} imports from reports: {mod}"
        assert "billing" not in mod, f"{filename} imports from billing engine: {mod}"
        assert "prose_rules" not in mod, f"{filename} imports from prose_rules engine: {mod}"


def test_there_is_one_allowed_dataframe_loop_and_it_is_the_reference_reader() -> None:
    assert list(_ALLOWED_DATAFRAME_LOOPS) == [
        ("labs.py", "load_lab_reference_df", "attribute iter_columns")
    ]
