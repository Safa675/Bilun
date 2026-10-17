"""Acceptance, schema, content, loader, smoke, determinism, hygiene and mutation tests for `scripts/synthetic/cohort/clean.py`."""

from __future__ import annotations

import ast
from datetime import datetime, time
from decimal import ROUND_HALF_UP, Decimal
import json
from pathlib import Path
import re
import shutil

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
    PatientClinical,
    ShowcaseClinical,
    build_clean_tables,
    build_showcase,
    check_clinical,
    clean_table_schemas,
    clean_tables_digest,
    derive_comorbidity_flags,
    load_clinical,
    sentence_case_tr,
    validate_clean_tables,
    validate_cohort_registry,
    write_clean_tables,
)
from scripts.synthetic.cohort.build import DEFAULT_OUT_DIR, main
from scripts.synthetic.faults import load_siblings
from scripts.synthetic.pathways import load_all
from scripts.synthetic.pathways.loader import hygiene
from src.bilun.cache.context import load_sut_build_context
from src.bilun.cache.data_loader import load_anadata, load_labdata, load_recete
from src.bilun.cache.loaders import load_normalized_raw_data, resolve_patient_ids
import src.bilun.domain.claims.config as claims_config
from src.bilun.domain.claims.loader import load_sut_claim_dataset

pytestmark = pytest.mark.unit

_REPO = Path(__file__).resolve().parents[3]
_SHOWCASE_DIR = DEFAULT_OUT_DIR
_CLAIMS_DIR = _SHOWCASE_DIR / "sut" / "claims"
_CLEAN_DIR = _SHOWCASE_DIR / "sut" / "clean"
_LEGACY_CLEAN_DIR = _REPO / "data" / "synthetic" / "sut" / "clean"
_REGISTRY_JSON_PATH = _SHOWCASE_DIR / "cohort_registry.json"

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
def _allow_showcase_synthetic_claims_dir(monkeypatch: pytest.MonkeyPatch) -> None:
    """Allow `load_sut_claim_dataset` and `load_sut_build_context` in `synthetic_demo` mode to read showcase."""
    monkeypatch.setattr(claims_config, "SYNTHETIC_SUT_DIR", _SHOWCASE_DIR / "sut")
    monkeypatch.setattr(
        claims_config, "DEFAULT_SYNTHETIC_CLEAN_DIR", _SHOWCASE_DIR / "sut" / "clean"
    )
    load_sut_claim_dataset.cache_clear()
    yield
    load_sut_claim_dataset.cache_clear()


@pytest.fixture(scope="module")
def built_showcase() -> BuildResult:
    return build_showcase()


# --- 2. Clean table schemas & content rules -----------------------------------------------------


def test_clean_schemas_match_legacy_parquet_schemas(built_showcase: BuildResult) -> None:
    legacy_ana = pl.read_parquet_schema(_LEGACY_CLEAN_DIR / "anadata_clean.parquet")
    legacy_rec = pl.read_parquet_schema(_LEGACY_CLEAN_DIR / "recete_clean.parquet")
    legacy_lab = pl.read_parquet_schema(_LEGACY_CLEAN_DIR / "lab_clean.parquet")

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


def test_clean_row_counts_and_anadata_field_rules_for_all_8_patients(
    built_showcase: BuildResult,
) -> None:
    ana_df = built_showcase.clean_tables["anadata_clean.parquet"]
    rec_df = built_showcase.clean_tables["recete_clean.parquet"]
    lab_df = built_showcase.clean_tables["lab_clean.parquet"]

    assert ana_df.height == 8
    assert rec_df.height == 19
    assert lab_df.height == 0

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


def test_recete_clean_content_rules_for_all_19_billed_drug_lines(
    built_showcase: BuildResult,
) -> None:
    rec_df = built_showcase.clean_tables["recete_clean.parquet"]
    drugs_df = built_showcase.tables["drug_claim_lines.parquet"]
    assert rec_df.height == drugs_df.height == 19

    cw_df = pl.read_parquet(_REPO / "data/synthetic/reference/drug_crosswalk.parquet").filter(
        pl.col("titck_product_name").is_not_null()
    )
    cw_map = dict(
        zip(cw_df["barcode"].to_list(), cw_df["titck_product_name"].to_list(), strict=True)
    )
    pathways = load_all()
    siblings = load_siblings()
    claims_by_id = {c.header.claim_id: c for c in built_showcase.claims}
    unit_tr_map = {"vial": "flakon", "box": "kutu", "syringe": "enjektör", "tablet": "tablet"}

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

        exp_unit = unit_tr_map.get(entry.unit, entry.unit)
        assert rec["dozaj_ham"] == f"{dl['quantity']} {exp_unit}"

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

    assert ana_raw.height == 8
    assert lab_raw.height == 0
    assert rec_raw.height == 19

    ana_df, lab_df, rec_df = load_normalized_raw_data(
        load_anadata_fn=lambda include_text=True: load_anadata(
            path=_CLEAN_DIR / "anadata_clean.parquet",
            include_text=include_text,
        ),
        load_labdata_fn=lambda: load_labdata(path=_CLEAN_DIR / "lab_clean.parquet"),
        load_recete_fn=lambda: load_recete(path=_CLEAN_DIR / "recete_clean.parquet"),
    )

    assert ana_df.height == 8
    assert "patient_id" in ana_df.columns
    assert "visit_date" in ana_df.columns
    assert "yas" in ana_df.columns
    assert "SQ_EPISODE" not in ana_df.columns
    assert len(ana_df.columns) == 32

    assert lab_df.height == 0
    assert list(lab_df.columns) == [
        "patient_id",
        "visit_id",
        "date",
        "test_name",
        "value",
        "ref_min",
        "ref_max",
    ]

    assert rec_df.height == 19
    assert list(rec_df.columns) == ["patient_id", "date", "drug_name"]

    pids = resolve_patient_ids(ana_df, lab_df, rec_df)
    assert pids == [f"SENTETIK-HASTA-{n:04d}" for n in range(1, 9)]


# --- 5. Smoke: load_sut_build_context ----------------------------------------------------------


def test_smoke_load_sut_build_context_on_committed_showcase() -> None:
    ctx = load_sut_build_context(
        billing_workers=1,
        sut_data_mode="synthetic_demo",
        sut_claims_dir=_CLAIMS_DIR,
        sut_clean_dir=_CLEAN_DIR,
    )
    expected_pids = [f"SENTETIK-HASTA-{n:04d}" for n in range(1, 9)]
    assert ctx["patient_ids"] == expected_pids
    assert [m["patient_id"] for m in ctx["patient_meta"]] == expected_pids
    assert len(ctx["billing_reports"]) == 8


# --- 6. Build equals committed, --check on clean tables & clean_counts, determinism -----------


def test_build_equals_committed_clean_tables_and_registry(
    built_showcase: BuildResult,
) -> None:
    committed_reg = json.loads(_REGISTRY_JSON_PATH.read_text(encoding="utf-8"))
    assert built_showcase.registry == committed_reg
    assert committed_reg["clean_counts"] == {
        "anadata_clean.parquet": 8,
        "lab_clean.parquet": 0,
        "recete_clean.parquet": 19,
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
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main(["--check"]) == 0
    capsys.readouterr()

    copy_dir = tmp_path / "showcase_copy"
    shutil.copytree(_SHOWCASE_DIR, copy_dir)
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


def test_clean_import_hygiene_and_no_dataframe_row_loops() -> None:
    source = (_REPO / "scripts/synthetic/cohort/clean.py").read_text(encoding="utf-8")
    tree = ast.parse(source, filename="clean.py")
    imported_modules: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported_modules.append(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.append(node.module)
        elif isinstance(node, ast.Attribute):
            assert node.attr not in {"iter_rows", "rows", "row"}, (
                f"clean.py uses DataFrame row iteration/indexing method {node.attr!r}"
            )

    for mod in imported_modules:
        assert not mod.startswith("pandas"), f"clean.py imports pandas: {mod}"
        assert not mod.startswith("reports"), f"clean.py imports from reports: {mod}"
        assert "billing" not in mod, f"clean.py imports from billing engine: {mod}"
        assert "prose_rules" not in mod, f"clean.py imports from prose_rules engine: {mod}"
