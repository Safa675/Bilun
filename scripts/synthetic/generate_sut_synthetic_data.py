#!/usr/bin/env python3
"""Generate the v1 SUT synthetic billing dataset.

Outputs one committed Turkish multi-sheet workbook plus Parquet exports:

    data/synthetic/sut/sentetik_sut_5_hasta.xlsx
    data/synthetic/sut/clean/*.parquet
    data/synthetic/sut/claims/*.parquet
"""

from __future__ import annotations

import argparse
import datetime as dt
from pathlib import Path
from typing import Any

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "data" / "synthetic" / "sut"
GAZETTE_DIR = PROJECT_ROOT / "data" / "gazette"
DATASET_ID = "sentetik_sut_5_v1_1"
WORKBOOK_NAME = "sentetik_sut_5_hasta.xlsx"
SYNTHETIC_NOTICE = (
    "Bu veri seti tamamen sentetiktir; gercek hasta, gercek kurum veya gercek "
    "fatura verisi icermez."
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate SUT synthetic v1 data")
    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_OUTPUT_DIR),
        help="Output directory for workbook and Parquet exports",
    )
    return parser.parse_args()


def _read_parquet(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_parquet(path)


def _latest_ek2c() -> pd.DataFrame:
    df = _read_parquet(GAZETTE_DIR / "curated" / "ek2c_catalog_history.parquet")
    if df.empty:
        return df
    work = df.copy()
    work["effective_date_dt"] = pd.to_datetime(work["effective_date"], errors="coerce")
    return work.sort_values("effective_date_dt").drop_duplicates(
        subset=["package_code"], keep="last"
    )


def _ek2b_lookup(code: str) -> dict[str, Any]:
    df = _read_parquet(GAZETTE_DIR / "ek2b_islem_puan_listesi.parquet")
    if not df.empty:
        row = df[df["ISLEM_KODU"].astype(str) == code]
        if not row.empty:
            item = row.iloc[0].to_dict()
            return {
                "kod": str(item.get("ISLEM_KODU", code)),
                "ad": str(item.get("ISLEM_ADI", code)),
                "fiyat_try": round(float(item.get("ISLEM_BEDELI_TL") or 0.0), 2),
                "kaynak": "EK-2B",
            }
    fallback = {
        "520010": ("Konsultasyon (Her bir brans icin)", 33.17),
        "520030": ("Normal poliklinik muayenesi", 85.73),
        "510010": ("Standart yatak tarifesi", 222.36),
        "530050": ("Biyopsi, igne", 298.36),
        "550010": ("Anestezi oncesi muayene", 89.75),
        "L107020": ("Tam Kan Sayimi (Hemogram)", 19.73),
        "L107010": ("Tam idrar analizi (Strip+Mikroskopi)", 26.31),
        "L101050": ("APTT", 35.53),
    }
    name, price = fallback.get(code, (code, 0.0))
    return {"kod": code, "ad": name, "fiyat_try": price, "kaynak": "EK-2B"}


def _ek2c_lookup(code: str) -> dict[str, Any]:
    df = _latest_ek2c()
    if not df.empty:
        row = df[df["package_code"].astype(str) == code]
        if not row.empty:
            item = row.iloc[0].to_dict()
            return {
                "kod": str(item.get("package_code", code)),
                "ad": str(item.get("name", code)),
                "grup": str(item.get("group", "")),
                "fiyat_try": round(float(item.get("price_try") or 0.0), 2),
                "kaynak": "EK-2C",
            }
    fallback = {
        "P550970": ("Anuloplasti RFT", "D", 9525.57),
        "P614980": ("Noronavigasyonla kitle rezeksiyonu", "A3", 19683.59),
        "P619410": ("Mesane tumoru (TUR) biyopsisi", "C", 9116.73),
        "P704973": ("Kordon kani nakli, allojenik", "A1", 1495907.23),
    }
    name, group, price = fallback.get(code, (code, "", 0.0))
    return {"kod": code, "ad": name, "grup": group, "fiyat_try": price, "kaynak": "EK-2C"}


def _material_lookup(path_name: str, code: str, fallback: tuple[str, float, str]) -> dict[str, Any]:
    df = _read_parquet(GAZETTE_DIR / "curated" / path_name)
    if not df.empty and "sut_code" in df.columns:
        row = df[df["sut_code"].astype(str) == code]
        if not row.empty:
            item = row.iloc[0].to_dict()
            return {
                "kod": str(item.get("sut_code", code)),
                "ad": str(item.get("material_name", code)),
                "fiyat_try": round(float(item.get("price_try") or fallback[1]), 2),
                "kategori": str(item.get("category", fallback[2])),
                "kaynak": str(item.get("source", "EK-3")),
            }
    name, price, category = fallback
    return {"kod": code, "ad": name, "fiyat_try": price, "kategori": category, "kaynak": "EK-3"}


def _drug_lookup(search: str, fallback: tuple[str, str, str, float]) -> dict[str, Any]:
    df = _read_parquet(GAZETTE_DIR / "curated" / "ek4a_drugs.parquet")
    if not df.empty and "drug_name" in df.columns:
        row = df[df["drug_name"].astype(str).str.contains(search, case=False, na=False)]
        if not row.empty:
            item = row.iloc[0].to_dict()
            return {
                "kamu_no": str(item.get("kamu_no", fallback[0])),
                "barkod": str(item.get("barcode", fallback[1])),
                "ad": str(item.get("drug_name", fallback[2])),
                "indirim_kademesi_1": float(item.get("discount_tier_1") or fallback[3]),
                "kaynak": "EK-4A",
            }
    kamu_no, barcode, name, tier = fallback
    return {
        "kamu_no": kamu_no,
        "barkod": barcode,
        "ad": name,
        "indirim_kademesi_1": tier,
        "kaynak": "EK-4A",
    }


def _catalog_subset() -> dict[str, dict[str, Any]]:
    items = {
        "muayene": _ek2b_lookup("520030"),
        "konsultasyon": _ek2b_lookup("520010"),
        "yatak": _ek2b_lookup("510010"),
        "biyopsi": _ek2b_lookup("530050"),
        "anestezi": _ek2b_lookup("550010"),
        "hemogram": _ek2b_lookup("L107020"),
        "idrar": _ek2b_lookup("L107010"),
        "aptt": _ek2b_lookup("L101050"),
        "paket_ortopedi": _ek2c_lookup("P614980"),
        "paket_gastro": _ek2c_lookup("P619410"),
        "paket_hematoloji": _ek2c_lookup("P704973"),
        "ortez": _material_lookup(
            "ek3c2_materials.parquet",
            "OP1000",
            ("ALUMINYUM KOLTUK DEGNEGI", 63.84, "ORTOPEDI"),
        ),
        "hemoklips": _material_lookup(
            "ek3r_gastroenterology_materials.parquet",
            "GS1050",
            ("ENDOSKOPIK HEMOKLIPS, YUKLEMESIZ", 889.35, "KANAMA DURDURUCULAR"),
        ),
        "aferez": _material_lookup(
            "ek3o_hematology_oncology_materials.parquet",
            "HO1001",
            ("LOKOFEREZ SETI", 4513.15, "AFEREZ"),
        ),
        "antibiyotik": _drug_lookup(
            "KLAMOKS",
            ("A10822", "8699569090458", "KLAMOKS BID 625 MG 10 FTB", 0.4),
        ),
        "sefalosporin": _drug_lookup(
            "AKSEF 500",
            ("A00457", "8699540091023", "AKSEF 500 MG 10 FTB", 0.28),
        ),
    }
    return items


def _money(value: float) -> float:
    return round(float(value), 2)


def build_workbook_tables() -> dict[str, pd.DataFrame]:
    c = _catalog_subset()
    patients = [
        {
            "hasta_id": "SENTETIK-HASTA-001",
            "cinsiyet": "K",
            "dogum_yili": 1982,
            "kohort": "checkup",
            "kayit_tarihi": "2024-01-05",
            "ana_senaryo": "temiz_ayaktan_kontrol",
            "veri_tamlik_yuzdesi": 96,
            "sentetik_profil_notu": "Temiz ayaktan kontrol; red veya paket ihlali beklenmez.",
        },
        {
            "hasta_id": "SENTETIK-HASTA-002",
            "cinsiyet": "E",
            "dogum_yili": 1965,
            "kohort": "ex",
            "kayit_tarihi": "2024-02-10",
            "ana_senaryo": "kronik_hastalik_katilim_payi_muafiyeti",
            "veri_tamlik_yuzdesi": 92,
            "sentetik_profil_notu": "Diyabet tanisi ile katilim payi muafiyeti adayi.",
        },
        {
            "hasta_id": "SENTETIK-HASTA-003",
            "cinsiyet": "K",
            "dogum_yili": 1974,
            "kohort": "merged",
            "kayit_tarihi": "2024-05-01",
            "ana_senaryo": "yatis_drg_paket",
            "veri_tamlik_yuzdesi": 90,
            "sentetik_profil_notu": "Yatis, paket adayi ve ortopedi malzemesi icerir.",
        },
        {
            "hasta_id": "SENTETIK-HASTA-004",
            "cinsiyet": "E",
            "dogum_yili": 1958,
            "kohort": "merged",
            "kayit_tarihi": "2024-06-02",
            "ana_senaryo": "malzeme_paket_ihlali",
            "veri_tamlik_yuzdesi": 88,
            "sentetik_profil_notu": "Endoskopi isleminde pakete dahil malzeme ayrica faturalandirilir.",
        },
        {
            "hasta_id": "SENTETIK-HASTA-005",
            "cinsiyet": "K",
            "dogum_yili": 1991,
            "kohort": "cancer",
            "kayit_tarihi": "2024-07-01",
            "ana_senaryo": "ilac_indirimi_ve_hematoloji_paket",
            "veri_tamlik_yuzdesi": 94,
            "sentetik_profil_notu": "Hematoloji paket senaryosu ve ilac fatura satirlari.",
        },
    ]
    episode_specs = [
        ("001", "2024-01-15", "J00", "J00,R53", "Poliklinik", "Ic Hastaliklari"),
        ("002", "2024-02-20", "E11.9", "E11.9,I10", "Poliklinik", "Endokrinoloji"),
        ("003", "2024-05-10", "M17.9", "M17.9,Z96.6", "Yatis", "Ortopedi ve Travmatoloji"),
        ("004", "2024-06-05", "K63.5", "K63.5,K29.7", "Gunubirlik", "Gastroenteroloji"),
        ("005", "2024-07-01", "C92.0", "C92.0,D61.9", "Yatis", "Hematoloji"),
    ]
    episodes = []
    diagnosis_rows = []
    for idx, (suffix, visit_date, primary, all_codes, visit_type, dept) in enumerate(episode_specs):
        patient = patients[idx]
        pid = patient["hasta_id"]
        birth_year = patient["dogum_yili"]
        age = int(visit_date[:4]) - birth_year
        eid = f"B-{pid}-001"
        codes = all_codes.split(",")
        episodes.append(
            {
                "hasta_id": pid,
                "basvuru_id": eid,
                "basvuru_tarihi": visit_date,
                "basvuru_yasi": age,
                "cinsiyet": patient["cinsiyet"],
                "birincil_icd10": primary,
                "tum_icd10_kodlari": all_codes,
                "tani_tipi": "Kesin Tani",
                "gelis_tipi": visit_type,
                "servis_adi": dept,
                "basvuru_icindeki_gelis_sayisi": 1,
                "hasta_toplam_gelis_sayisi": 1,
                "ilk_tani_tarihi": visit_date,
                "son_tani_tarihi": visit_date,
                "tani_gun_farki": 0,
                "sistolik_tansiyon": [118, 142, 128, 135, 110][idx],
                "diyastolik_tansiyon": [76, 88, 82, 84, 70][idx],
                "nabiz": [74, 86, 78, 80, 92][idx],
                "spo2": [98, 97, 96, 98, 95][idx],
                "boy_cm": [168, 176, 162, 172, 165][idx],
                "kilo_kg": [64, 91, 78, 82, 59][idx],
                "bmi": [22.7, 29.4, 29.7, 27.7, 21.7][idx],
                "hipertansiyon_var": idx == 1,
                "kalp_damar_var": False,
                "diyabet_var": idx == 1,
                "kan_hastaligi_var": idx == 4,
                "yakinma": "Sentetik basvuru yakinmasi",
                "oyku": "Sentetik hasta oykusu",
                "muayene_notu": "Sentetik muayene notu",
                "tedavi_notu": "Sentetik tedavi plani",
                "kohort": patient["kohort"],
                "donem": "2024",
            }
        )
        for line_no, code in enumerate(codes, start=1):
            diagnosis_rows.append(
                {
                    "tani_satiri_id": f"TANI-{pid}-{line_no:03d}",
                    "hasta_id": pid,
                    "basvuru_id": eid,
                    "icd10_kodu": code,
                    "tani_rolu": "birincil" if line_no == 1 else "ikincil",
                    "tani_tarihi": visit_date,
                    "ek1a_muafiyet_iliskili_mi": code.startswith("E11") or code.startswith("C92"),
                }
            )

    claim_specs = [
        ("001", "ayaktan", "2_3_basamak_ozel", "Ozel", None, None, "2024-01-15", "2024-01-15", "J00", False, "temiz_ayaktan_kontrol"),
        ("002", "ayaktan", "2_3_basamak_ozel", "Ozel", None, None, "2024-02-20", "2024-02-20", "E11.9", False, "kronik_hastalik_katilim_payi_muafiyeti"),
        ("003", "yatis", "3_basamak", "Universite", "2024-05-10", "2024-05-13", "2024-05-10", "2024-05-13", "M17.9", True, "yatis_drg_paket"),
        ("004", "gunubirlik", "2_3_basamak_ozel", "Ozel", None, None, "2024-06-05", "2024-06-05", "K63.5", True, "malzeme_paket_ihlali"),
        ("005", "yatis", "3_basamak", "Universite", "2024-07-01", "2024-07-21", "2024-07-01", "2024-07-21", "C92.0", True, "ilac_indirimi_ve_hematoloji_paket"),
    ]
    claims = []
    procedure_rows = []
    materials = []
    drug_claims = []
    expected = []
    lab_billing_budget: dict[tuple[str, str], dict[str, Any]] = {}

    def add_expected_output(
        *,
        expected_id: str,
        scenario_tag: str,
        patient_id: str,
        claim_id: str,
        line_id: str,
        line_type: str,
        rule_family: str,
        expected_status: str,
        expected_payable_try: float,
        expected_savings_try: float,
        expected_denial_reason: str,
        expected_rule_trace: str,
        notes: str,
    ) -> None:
        expected.append(
            {
                "beklenen_cikti_id": expected_id,
                "senaryo_etiketi": scenario_tag,
                "hasta_id": patient_id,
                "fatura_id": claim_id,
                "satir_id": line_id,
                "satir_tipi": line_type,
                "kural_ailesi": rule_family,
                "beklenen_durum": expected_status,
                "beklenen_odenebilir_tutar_try": _money(expected_payable_try),
                "beklenen_tasarruf_try": _money(expected_savings_try),
                "beklenen_red_nedeni": expected_denial_reason,
                "beklenen_kural_izi": expected_rule_trace,
                "test_notu": notes,
            }
        )

    procedure_by_patient = {
        "001": [("520030", "muayene", "muayene", 1, None), ("L107020", "hemogram", "laboratuvar", 1, None), ("L107010", "idrar", "laboratuvar", 1, None)],
        "002": [("520010", "konsultasyon", "muayene", 1, None), ("L107020", "hemogram", "laboratuvar", 1, None), ("L101050", "aptt", "laboratuvar", 1, None)],
        "003": [("510010", "yatak", "yatak", 3, "P614980"), ("550010", "anestezi", "anestezi", 1, "P614980"), ("P614980", "paket_ortopedi", "paket", 1, "P614980")],
        "004": [("520010", "konsultasyon", "muayene", 1, None), ("530050", "biyopsi", "islem", 1, "P619410"), ("P619410", "paket_gastro", "paket", 1, "P619410")],
        "005": [("510010", "yatak", "yatak", 20, "P704973"), ("L101050", "aptt", "laboratuvar", 2, "P704973"), ("P704973", "paket_hematoloji", "paket", 1, "P704973")],
    }
    material_by_patient = {
        "003": [("ortez", "ortez", False), ("ortez", "ortez_yedek", False)],
        "004": [("hemoklips", "endoskopi_sarf", True), ("hemoklips", "endoskopi_sarf_yedek", True)],
        "005": [("aferez", "aferez", False)],
    }
    drug_by_patient = {
        "002": [("antibiyotik", 1), ("sefalosporin", 1)],
        "004": [("antibiyotik", 1)],
        "005": [("sefalosporin", 2), ("antibiyotik", 1)],
    }

    for idx, spec in enumerate(claim_specs, start=1):
        suffix = f"{idx:03d}"
        patient = patients[idx - 1]
        pid = patient["hasta_id"]
        eid = f"B-{pid}-001"
        claim_id = f"F-{pid}-001"
        _, claim_type, tier, provider, admission, discharge, start, end, primary, package_candidate, scenario = spec
        total_billed = 0.0
        total_payable = 0.0
        for line_idx, (code, key, category, qty, package_code) in enumerate(
            procedure_by_patient[suffix], start=1
        ):
            item = c[key]
            unit_price = _money(item["fiyat_try"])
            billed = _money(unit_price * qty)
            included = package_code is not None and category != "paket"
            payable = 0.0 if included else billed
            if category == "paket":
                payable = billed
            line_id = f"ISL-{claim_id}-{line_idx:03d}"
            procedure_rows.append(
                {
                    "islem_satiri_id": line_id,
                    "fatura_id": claim_id,
                    "hasta_id": pid,
                    "basvuru_id": eid,
                    "islem_tarihi": start,
                    "islem_kodu": code,
                    "islem_adi": item["ad"],
                    "islem_kategorisi": category,
                    "adet": qty,
                    "birim_fiyat_try": unit_price,
                    "fatura_tutari_try": billed,
                    "beklenen_odenebilir_tutar_try": payable,
                    "pakete_dahil_mi": included,
                    "paket_kodu": package_code,
                    "ilave_ucret_uygulanabilir_mi": scenario in {"yatis_drg_paket", "malzeme_paket_ihlali"},
                    "katilim_payi_orani_uygulanabilir_mi": claim_type == "ayaktan",
                    "beklenen_red_nedeni": "Paket ici islem ayrica odenmez" if included else "",
                    "beklenen_kural_izi": f"{item['kaynak']}:{code}",
                }
            )
            if category == "laboratuvar":
                lab_billing_budget[(eid, code)] = {"islem_satiri_id": line_id, "kalan_adet": qty}
            if included:
                add_expected_output(
                    expected_id=f"BEK-{line_id}",
                    scenario_tag=scenario,
                    patient_id=pid,
                    claim_id=claim_id,
                    line_id=line_id,
                    line_type="islem",
                    rule_family="drg_paket_ayristirma",
                    expected_status="pakete_dahil_red",
                    expected_payable_try=payable,
                    expected_savings_try=billed - payable,
                    expected_denial_reason="Paket ici islem ayrica odenmez",
                    expected_rule_trace=f"{item['kaynak']}:{code}",
                    notes="Satir duzeyi sentetik beklenen cikti",
                )
            total_billed += billed
            total_payable += payable
        for material_idx, (key, material_type, bundled) in enumerate(
            material_by_patient.get(suffix, []), start=1
        ):
            item = c[key]
            billed = _money(item["fiyat_try"])
            payable = 0.0 if bundled else billed
            line_id = f"MLZ-{claim_id}-{material_idx:03d}"
            materials.append(
                {
                    "malzeme_satiri_id": line_id,
                    "fatura_id": claim_id,
                    "islem_satiri_id": f"ISL-{claim_id}-002",
                    "hasta_id": pid,
                    "malzeme_tarihi": start,
                    "malzeme_kodu": item["kod"],
                    "malzeme_adi": item["ad"],
                    "malzeme_tipi": material_type,
                    "uzmanlik_kategorisi": item.get("kategori", ""),
                    "adet": 1,
                    "birim_fiyat_try": _money(item["fiyat_try"]),
                    "fatura_tutari_try": billed,
                    "beklenen_odenebilir_tutar_try": payable,
                    "pakete_dahil_mi": bundled,
                    "on_onay_gerekli_mi": suffix in {"003", "005"},
                    "beklenen_red_nedeni": "Paket kapsamindaki sarf malzeme ayrica odenmez" if bundled else "",
                    "beklenen_kural_izi": f"{item['kaynak']}:{item['kod']}",
                }
            )
            if bundled or suffix in {"003", "005"}:
                add_expected_output(
                    expected_id=f"BEK-{line_id}",
                    scenario_tag=scenario,
                    patient_id=pid,
                    claim_id=claim_id,
                    line_id=line_id,
                    line_type="malzeme",
                    rule_family="faturalama_stratejisi",
                    expected_status="pakete_dahil_red" if bundled else "on_onay_gerekli_odenebilir",
                    expected_payable_try=payable,
                    expected_savings_try=billed - payable,
                    expected_denial_reason="Paket kapsamindaki sarf malzeme ayrica odenmez" if bundled else "",
                    expected_rule_trace=f"{item['kaynak']}:{item['kod']}",
                    notes="Satir duzeyi sentetik beklenen cikti",
                )
            total_billed += billed
            total_payable += payable
        for drug_idx, (key, qty) in enumerate(drug_by_patient.get(suffix, []), start=1):
            item = c[key]
            unit_price = 120.0 if key == "antibiyotik" else 185.0
            billed = _money(unit_price * qty)
            payable = _money(billed * (1 - float(item["indirim_kademesi_1"])))
            line_id = f"ILC-{claim_id}-{drug_idx:03d}"
            prescription_id = f"REC-{claim_id}-{drug_idx:03d}"
            drug_claims.append(
                {
                    "ilac_satiri_id": line_id,
                    "recete_id": prescription_id,
                    "fatura_id": claim_id,
                    "hasta_id": pid,
                    "basvuru_id": eid,
                    "ilac_fatura_tarihi": start,
                    "ilac_adi": item["ad"],
                    "ilac_kodu": item["kamu_no"],
                    "barkod": item["barkod"],
                    "esdeger_grup": "SENTETIK-ESDEGER",
                    "adet": qty,
                    "birim_fiyat_try": unit_price,
                    "fatura_tutari_try": billed,
                    "beklenen_odenebilir_tutar_try": payable,
                    "beklenen_indirim_kademesi": item["indirim_kademesi_1"],
                    "beklenen_red_nedeni": "",
                    "beklenen_kural_izi": f"EK-4A:{item['kamu_no']}",
                }
            )
            add_expected_output(
                expected_id=f"BEK-{line_id}",
                scenario_tag=scenario,
                patient_id=pid,
                claim_id=claim_id,
                line_id=line_id,
                line_type="ilac",
                rule_family="ilac_indirimi",
                expected_status="ilac_indirimi_uygulandi",
                expected_payable_try=payable,
                expected_savings_try=billed - payable,
                expected_denial_reason="",
                expected_rule_trace=f"EK-4A:{item['kamu_no']}",
                notes="Satir duzeyi sentetik beklenen cikti",
            )
            total_billed += billed
            total_payable += payable
        claims.append(
            {
                "fatura_id": claim_id,
                "hasta_id": pid,
                "basvuru_id": eid,
                "fatura_tipi": claim_type,
                "kurum_basamagi": tier,
                "saglayici_tipi": provider,
                "servis_adi": episodes[idx - 1]["servis_adi"],
                "yatis_tarihi": admission,
                "taburcu_tarihi": discharge,
                "fatura_baslangic_tarihi": start,
                "fatura_bitis_tarihi": end,
                "birincil_icd10": primary,
                "paket_adayi_mi": package_candidate,
                "beklenen_toplam_fatura_tutari_try": _money(total_billed),
                "beklenen_toplam_odenebilir_tutar_try": _money(total_payable),
                "beklenen_red_nedeni": "Kismi paket ici satir reddi" if total_payable < total_billed else "",
                "senaryo_etiketi": scenario,
            }
        )
        add_expected_output(
            expected_id=f"BEK-{claim_id}",
            scenario_tag=scenario,
            patient_id=pid,
            claim_id=claim_id,
            line_id="",
            line_type="fatura",
            rule_family="fatura_dogrulama",
            expected_status="kismi_red" if total_payable < total_billed else "odenebilir",
            expected_payable_try=total_payable,
            expected_savings_try=total_billed - total_payable,
            expected_denial_reason="Paket ici satirlar reddedilir" if total_payable < total_billed else "",
            expected_rule_trace=scenario,
            notes="Fatura duzeyi sentetik beklenen cikti",
        )

    recete_rows = []
    for drug in drug_claims:
        recete_rows.append(
            {
                "recete_id": drug["recete_id"],
                "hasta_id": drug["hasta_id"],
                "recete_tarihi": drug["ilac_fatura_tarihi"],
                "basvuru_id": drug["basvuru_id"],
                "ilac_adi": drug["ilac_adi"],
                "ham_ilac_adi": drug["ilac_adi"],
                "ham_dozaj": "1 kutu",
                "verilis_yolu": "Agizdan (Oral)",
                "gun": 7,
                "doz_mg": 500,
                "doz_birimi": "mg",
                "siklik": 2,
                "miktar": drug["adet"],
                "kohort": next(p["kohort"] for p in patients if p["hasta_id"] == drug["hasta_id"]),
                "donem": "2024",
            }
        )
    while len(recete_rows) < 10:
        base = recete_rows[len(recete_rows) % max(len(recete_rows), 1)] if recete_rows else {
            "hasta_id": "SENTETIK-HASTA-001",
            "recete_tarihi": "2024-01-15",
            "basvuru_id": "B-SENTETIK-HASTA-001-001",
            "ilac_adi": c["antibiyotik"]["ad"],
            "ham_ilac_adi": c["antibiyotik"]["ad"],
            "ham_dozaj": "1 kutu",
            "verilis_yolu": "Agizdan (Oral)",
            "gun": 7,
            "doz_mg": 500,
            "doz_birimi": "mg",
            "siklik": 2,
            "miktar": 1,
            "kohort": "checkup",
            "donem": "2024",
        }
        row = dict(base)
        row["recete_id"] = f"REC-EK-{len(recete_rows) + 1:03d}"
        row["recete_tarihi"] = pd.to_datetime(row["recete_tarihi"]) + pd.to_timedelta(len(recete_rows), unit="D")
        row["recete_tarihi"] = row["recete_tarihi"].date().isoformat()
        recete_rows.append(row)

    lab_codes = [c["hemogram"], c["idrar"], c["aptt"]]
    lab_rows = []
    for episode in episodes:
        for rep in range(6):
            for lab in lab_codes:
                value = 8.0 + rep if lab["kod"] == "L107020" else 1.0 + rep
                billing = lab_billing_budget.get((episode["basvuru_id"], lab["kod"]))
                is_billed = bool(billing and billing["kalan_adet"] > 0)
                linked_procedure_line_id = str(billing["islem_satiri_id"]) if is_billed and billing else ""
                if billing and billing["kalan_adet"] > 0:
                    billing["kalan_adet"] -= 1
                lab_rows.append(
                    {
                        "hasta_id": episode["hasta_id"],
                        "basvuru_id": episode["basvuru_id"],
                        "test_tarihi": episode["basvuru_tarihi"],
                        "laboratuvar_kodu": lab["kod"],
                        "laboratuvar_adi": lab["ad"],
                        "sayisal_sonuc": value,
                        "nitel_sonuc": "",
                        "birim": "sentetik_birim",
                        "referans_alt": 0.0,
                        "referans_ust": 10.0,
                        "anormal_mi": value > 10.0,
                        "organ_sistemi": "Sentetik",
                        "kohort": next(p["kohort"] for p in patients if p["hasta_id"] == episode["hasta_id"]),
                        "donem": "2024",
                        "faturalama_durumu": "faturalandirildi"
                        if is_billed
                        else "klinik_kanit_faturalandirilmadi",
                        "islem_satiri_id": linked_procedure_line_id,
                    }
                )

    catalog_rows = []
    for key, item in c.items():
        catalog_rows.append(
            {
                "katalog_tipi": item["kaynak"],
                "katalog_anahtari": key,
                "kod": item.get("kod") or item.get("kamu_no"),
                "ad": item["ad"],
                "grup": item.get("grup", item.get("kategori", "")),
                "fiyat_try": item.get("fiyat_try", ""),
                "kaynak": item["kaynak"],
                "kullanim_senaryosu": "sentetik_sut_5_v1",
            }
        )

    manifest = pd.DataFrame(
        [
            {
                "veri_seti_id": DATASET_ID,
                "versiyon": "1.1.0",
                "olusturulma_zamani": dt.datetime.now(dt.UTC)
                .replace(microsecond=0)
                .isoformat()
                .replace("+00:00", "Z"),
                "rastgelelik_tohumu": 20260504,
                "hasta_sayisi": len(patients),
                "basvuru_sayisi": len(episodes),
                "islem_satiri_sayisi": len(procedure_rows),
                "ilac_satiri_sayisi": len(drug_claims),
                "malzeme_satiri_sayisi": len(materials),
                "laboratuvar_sonucu_sayisi": len(lab_rows),
                "senaryo_etiketleri": ",".join(sorted({c["senaryo_etiketi"] for c in claims})),
                "sentetik_uyari": SYNTHETIC_NOTICE,
            }
        ]
    )
    return {
        "veri_seti_manifestosu": manifest,
        "hastalar": pd.DataFrame(patients),
        "basvurular": pd.DataFrame(episodes),
        "tani_satirlari": pd.DataFrame(diagnosis_rows),
        "fatura_basliklari": pd.DataFrame(claims),
        "islem_fatura_satirlari": pd.DataFrame(procedure_rows),
        "malzeme_fatura_satirlari": pd.DataFrame(materials),
        "ilac_fatura_satirlari": pd.DataFrame(drug_claims),
        "receteler": pd.DataFrame(recete_rows),
        "laboratuvar_sonuclari": pd.DataFrame(lab_rows),
        "beklenen_kural_ciktilari": pd.DataFrame(expected),
        "katalog_alt_kumesi": pd.DataFrame(catalog_rows),
    }


def _normalize_for_parquet(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for col in out.columns:
        if pd.api.types.is_object_dtype(out[col].dtype):
            out[col] = out[col].map(
                lambda x: None
                if x is None or (isinstance(x, float) and pd.isna(x))
                else str(x)
            )
    return out


def _write_workbook(tables: dict[str, pd.DataFrame], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        for sheet_name, df in tables.items():
            df.to_excel(writer, sheet_name=sheet_name, index=False)
            worksheet = writer.sheets[sheet_name]
            worksheet.freeze_panes = "A2"


def _clean_anadata(basvurular: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "HASTA_ID": basvurular["hasta_id"],
            "SQ_EPISODE": basvurular["basvuru_id"],
            "EPISODE_TARIH": pd.to_datetime(basvurular["basvuru_tarihi"]),
            "TANI_YASI": basvurular["basvuru_yasi"],
            "CINSIYET": basvurular["cinsiyet"],
            "KB-S": basvurular["sistolik_tansiyon"],
            "KB-D": basvurular["diyastolik_tansiyon"],
            "Nabiz": basvurular["nabiz"],
            "SPO2": basvurular["spo2"],
            "Boy": basvurular["boy_cm"],
            "Kilo": basvurular["kilo_kg"],
            "BMI": basvurular["bmi"],
            "ILK_TANI_SON_TANI_GUN_FARKI": basvurular["tani_gun_farki"],
            "TOPLAM_GELIS_SAYISI": basvurular["hasta_toplam_gelis_sayisi"],
            "GELIS_SAYISI": basvurular["basvuru_icindeki_gelis_sayisi"],
            "GELIS_TIPI": basvurular["gelis_tipi"],
            "SERVISADI": basvurular["servis_adi"],
            "TANIKODU": basvurular["birincil_icd10"],
            "TUM_EPS_TANILAR": basvurular["tum_icd10_kodlari"],
            "TANI_TIPI": basvurular["tani_tipi"],
            "TANITARIH": pd.to_datetime(basvurular["basvuru_tarihi"]),
            "MIN_TANI_TARIH": pd.to_datetime(basvurular["ilk_tani_tarihi"]),
            "MAX_TANI_TARIH": pd.to_datetime(basvurular["son_tani_tarihi"]),
            "Hipertansiyon Hastada": basvurular["hipertansiyon_var"],
            "Kalp Damar Hastada": basvurular["kalp_damar_var"],
            "Diyabet Hastada": basvurular["diyabet_var"],
            "Kan Hastaliklari Hastada": basvurular["kan_hastaligi_var"],
            "YAKINMA": basvurular["yakinma"],
            "OYKU": basvurular["oyku"],
            "Muayene Notu": basvurular["muayene_notu"],
            "Tedavi Notu": basvurular["tedavi_notu"],
            "kohort": basvurular["kohort"],
            "donem": basvurular["donem"],
        }
    )


def _clean_lab(labs: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "HASTA_ID": labs["hasta_id"],
            "SUB_CODE": labs["laboratuvar_kodu"],
            "sonuc_sayisal": labs["sayisal_sonuc"],
            "sonuc_nitel": labs["nitel_sonuc"],
            "birim": labs["birim"],
            "ref_alt": labs["referans_alt"],
            "ref_ust": labs["referans_ust"],
            "anormal_mi": labs["anormal_mi"],
            "organ_sistemi": labs["organ_sistemi"],
            "kohort": labs["kohort"],
            "donem": labs["donem"],
            "tarih": pd.to_datetime(labs["test_tarihi"]),
        }
    )


def _clean_recete(receteler: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "HASTA_ID": receteler["hasta_id"],
            "RECETE_TARIH": pd.to_datetime(receteler["recete_tarihi"]),
            "RF_EPISODE": receteler["basvuru_id"],
            "ilac_adi": receteler["ilac_adi"],
            "ilac_adi_ham": receteler["ham_ilac_adi"],
            "dozaj_ham": receteler["ham_dozaj"],
            "verilis_yolu": receteler["verilis_yolu"],
            "gun": receteler["gun"],
            "doz_mg": receteler["doz_mg"],
            "doz_birimi": receteler["doz_birimi"],
            "siklik": receteler["siklik"],
            "miktar": receteler["miktar"],
            "kohort": receteler["kohort"],
            "donem": receteler["donem"],
        }
    )


def _write_clean_exports(tables: dict[str, pd.DataFrame], output_dir: Path) -> None:
    clean_dir = output_dir / "clean"
    clean_dir.mkdir(parents=True, exist_ok=True)
    exports = {
        "anadata_clean.parquet": _clean_anadata(tables["basvurular"]),
        "lab_clean.parquet": _clean_lab(tables["laboratuvar_sonuclari"]),
        "recete_clean.parquet": _clean_recete(tables["receteler"]),
    }
    for name, df in exports.items():
        _normalize_for_parquet(df).to_parquet(clean_dir / name, index=False)


def _english_claim_exports(tables: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    diagnosis_claims = tables["tani_satirlari"].merge(
        tables["fatura_basliklari"][["fatura_id", "hasta_id", "basvuru_id"]],
        on=["hasta_id", "basvuru_id"],
        how="left",
        validate="many_to_one",
    )
    diagnosis_claims = diagnosis_claims.assign(
        birincil_mi=diagnosis_claims["tani_rolu"].astype(str).str.casefold() == "birincil"
    )
    return {
        "claim_headers.parquet": tables["fatura_basliklari"].rename(
            columns={
                "fatura_id": "claim_id",
                "hasta_id": "patient_id",
                "basvuru_id": "episode_id",
                "fatura_tipi": "claim_type",
                "kurum_basamagi": "facility_tier",
                "saglayici_tipi": "provider_type",
                "servis_adi": "department",
                "yatis_tarihi": "admission_date",
                "taburcu_tarihi": "discharge_date",
                "fatura_baslangic_tarihi": "claim_start_date",
                "fatura_bitis_tarihi": "claim_end_date",
                "birincil_icd10": "primary_icd10",
                "paket_adayi_mi": "package_candidate",
                "beklenen_toplam_fatura_tutari_try": "expected_total_billed_try",
                "beklenen_toplam_odenebilir_tutar_try": "expected_total_payable_try",
                "beklenen_red_nedeni": "expected_denial_reason",
                "senaryo_etiketi": "scenario_tag",
            }
        ),
        "claim_diagnoses.parquet": diagnosis_claims.rename(
            columns={
                "tani_satiri_id": "diagnosis_id",
                "fatura_id": "claim_id",
                "hasta_id": "patient_id",
                "basvuru_id": "episode_id",
                "icd10_kodu": "icd10_code",
                "birincil_mi": "is_primary",
                "tani_rolu": "diagnosis_role",
                "tani_tarihi": "diagnosis_date",
                "ek1a_muafiyet_iliskili_mi": "exemption_eligible",
            }
        ),
        "procedure_claim_lines.parquet": tables["islem_fatura_satirlari"].rename(
            columns={
                "islem_satiri_id": "procedure_line_id",
                "fatura_id": "claim_id",
                "hasta_id": "patient_id",
                "basvuru_id": "episode_id",
                "islem_tarihi": "procedure_date",
                "islem_kodu": "procedure_code",
                "islem_adi": "procedure_name",
                "islem_kategorisi": "procedure_category",
                "adet": "quantity",
                "birim_fiyat_try": "unit_price_try",
                "fatura_tutari_try": "billed_amount_try",
                "beklenen_odenebilir_tutar_try": "expected_payable_try",
                "pakete_dahil_mi": "is_package_included",
                "paket_kodu": "package_code",
                "ilave_ucret_uygulanabilir_mi": "surcharge_applicable",
                "katilim_payi_orani_uygulanabilir_mi": "copay_rate_applicable",
                "beklenen_red_nedeni": "denial_reason_expected",
                "beklenen_kural_izi": "rule_trace_expected",
            }
        ),
        "material_claim_lines.parquet": tables["malzeme_fatura_satirlari"].rename(
            columns={
                "malzeme_satiri_id": "material_line_id",
                "fatura_id": "claim_id",
                "islem_satiri_id": "procedure_line_id",
                "hasta_id": "patient_id",
                "malzeme_tarihi": "material_date",
                "malzeme_kodu": "material_code",
                "malzeme_adi": "material_name",
                "malzeme_tipi": "material_type",
                "uzmanlik_kategorisi": "specialty_category",
                "adet": "quantity",
                "birim_fiyat_try": "unit_price_try",
                "fatura_tutari_try": "billed_amount_try",
                "beklenen_odenebilir_tutar_try": "expected_payable_try",
                "pakete_dahil_mi": "is_bundled",
                "on_onay_gerekli_mi": "requires_pre_auth",
                "beklenen_red_nedeni": "denial_reason_expected",
                "beklenen_kural_izi": "rule_trace_expected",
            }
        ),
        "drug_claim_lines.parquet": tables["ilac_fatura_satirlari"].rename(
            columns={
                "ilac_satiri_id": "drug_claim_line_id",
                "recete_id": "prescription_id",
                "fatura_id": "claim_id",
                "hasta_id": "patient_id",
                "basvuru_id": "episode_id",
                "ilac_fatura_tarihi": "drug_claim_date",
                "ilac_adi": "drug_name",
                "ilac_kodu": "drug_code",
                "esdeger_grup": "equivalence_group",
                "adet": "quantity",
                "birim_fiyat_try": "unit_price_try",
                "fatura_tutari_try": "billed_amount_try",
                "beklenen_odenebilir_tutar_try": "expected_payable_try",
                "beklenen_indirim_kademesi": "discount_tier_expected",
                "beklenen_red_nedeni": "denial_reason_expected",
                "beklenen_kural_izi": "rule_trace_expected",
            }
        ),
        "expected_rule_outputs.parquet": tables["beklenen_kural_ciktilari"].rename(
            columns={
                "beklenen_cikti_id": "expected_output_id",
                "senaryo_etiketi": "scenario_tag",
                "hasta_id": "patient_id",
                "fatura_id": "claim_id",
                "satir_id": "line_id",
                "satir_tipi": "line_type",
                "kural_ailesi": "rule_family",
                "beklenen_durum": "expected_status",
                "beklenen_odenebilir_tutar_try": "expected_payable_try",
                "beklenen_tasarruf_try": "expected_savings_try",
                "beklenen_red_nedeni": "expected_denial_reason",
                "beklenen_kural_izi": "expected_rule_trace",
                "test_notu": "assertion_notes",
            }
        ),
    }


def _write_claim_exports(tables: dict[str, pd.DataFrame], output_dir: Path) -> None:
    claims_dir = output_dir / "claims"
    claims_dir.mkdir(parents=True, exist_ok=True)
    for name, df in _english_claim_exports(tables).items():
        _normalize_for_parquet(df).to_parquet(claims_dir / name, index=False)


def main() -> None:
    args = parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    tables = build_workbook_tables()

    workbook_path = output_dir / WORKBOOK_NAME
    _write_workbook(tables, workbook_path)
    _write_clean_exports(tables, output_dir)
    _write_claim_exports(tables, output_dir)

    print("=" * 72)
    print(f"Wrote workbook: {workbook_path}")
    print(f"Wrote clean exports: {output_dir / 'clean'}")
    print(f"Wrote claim exports: {output_dir / 'claims'}")
    print(f"Patients: {len(tables['hastalar'])}")
    print(f"Procedure lines: {len(tables['islem_fatura_satirlari'])}")


if __name__ == "__main__":
    main()
