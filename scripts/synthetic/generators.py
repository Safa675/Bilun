"""Data generation functions for the SUT synthetic data generator v2."""

from __future__ import annotations

import datetime as dt
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

from constants import (
    CURATED_DIR,
    ICD10_CHAPTER_TO_DRG_GROUP,
    SCENARIO_TEMPLATES,
    SYNTHETIC_NOTICE,
    TURKISH_FEMALE_NAMES,
    TURKISH_MALE_NAMES,
    TURKISH_SURNAMES,
)
from catalog import (
    _drug_unit_price,
    _ek1a,
    _ek2b,
    _ek2c_latest,
    _ek2c1,
    _ek2g,
    _ek3_material,
    _ek4a,
    _money,
)
from payment_method_sampling import (
    episode_care_setting,
    filter_ek2b_pool_for_packaged_claim,
)
from demo_config import vignette_for_patient_id
from fault_injection import (
    apply_vignette_episode_defaults,
    build_optional_override_specs,
)

PAYMENT_METHOD_COMPLIANCE_DEMO_TAG = "payment_method_compliance_demo"

_DRUG_INDICATION_DEMO_SPECS: dict[str, dict[str, Any]] = {
    "bevacizumab_missing_report": {
        "scenario_tag": "sgk_drug_indication_bevacizumab_missing_report",
        "ilac_adi": "AVASTIN 400 MG IV INFUZYONLUK KONSANTRE COZELTI (BEVACIZUMAB)",
        "ilac_kodu": "SUT-DEMO-BEV",
        "barkod": "8690000000001",
        "esdeger_grup": "DEMO-BEV",
        "beklenen_red_nedeni": "Uzmanlik saglik kurulu raporu eksik",
        "beklenen_kural_izi": "4.2.14.C:bevacizumab:missing_board_report",
        "uzmanlik_kurulu_raporu_var": False,
    },
    "nivolumab_indication_mismatch": {
        "scenario_tag": "sgk_drug_indication_nivolumab_indication_mismatch",
        "ilac_adi": "OPDIVO 100 MG IV INFUZYONLUK KONSANTRE COZELTI (NIVOLUMAB)",
        "ilac_kodu": "SUT-DEMO-NIVO",
        "barkod": "8690000000002",
        "esdeger_grup": "DEMO-NIVO",
        "beklenen_red_nedeni": "Endikasyon uyumsuzlugu",
        "beklenen_kural_izi": "4.2.14.C:nivolumab:indication_mismatch",
        "uzmanlik_kurulu_raporu_var": True,
    },
    "daratumumab_report_unknown": {
        "scenario_tag": "sgk_drug_indication_daratumumab_report_unknown",
        "ilac_adi": "DARZALEX 400 MG IV INFUZYONLUK KONSANTRE COZELTI (DARATUMUMAB)",
        "ilac_kodu": "SUT-DEMO-DARA",
        "barkod": "8690000000003",
        "esdeger_grup": "DEMO-DARA",
        "beklenen_red_nedeni": "Saglik kurulu raporu dogrulanmali",
        "beklenen_kural_izi": "4.2.14.C:daratumumab:needs_report_verification",
        "uzmanlik_kurulu_raporu_var": None,
    },
    "pembrolizumab_report_ok": {
        "scenario_tag": "sgk_drug_indication_pembrolizumab_report_ok",
        "ilac_adi": "KEYTRUDA 100 MG IV INFUZYONLUK KONSANTRE COZELTI (PEMBROLIZUMAB)",
        "ilac_kodu": "SUT-DEMO-PEM",
        "barkod": "8690000000004",
        "esdeger_grup": "DEMO-PEM",
        "beklenen_red_nedeni": "",
        "beklenen_kural_izi": "",
        "uzmanlik_kurulu_raporu_var": True,
        "yatarak_tedavi_ilac": True,
    },
    "trastuzumab_report_duration_mismatch": {
        "scenario_tag": "sgk_drug_indication_trastuzumab_report_duration_mismatch",
        "ilac_adi": "HERCEPTIN 440 MG IV INFUZYONLUK KONSANTRE COZELTI (TRASTUZUMAB)",
        "ilac_kodu": "SUT-DEMO-TRAS",
        "barkod": "8690000000005",
        "esdeger_grup": "DEMO-TRAS",
        "beklenen_red_nedeni": "Saglik kurulu rapor suresi uyumsuz",
        "beklenen_kural_izi": "4.2.14.C:trastuzumab:report_duration_mismatch",
        "uzmanlik_kurulu_raporu_var": True,
        "rapor_suresi_ay": 12,
        "recete_eden_uzmanlik": "Tıbbi Onkoloji",
    },
    "trabectedin_missing_report": {
        "scenario_tag": "sgk_drug_indication_trabectedin_missing_report",
        "ilac_adi": "YONDELIS 1 MG IV INFUZYONLUK KONSANTRE COZELTI (TRABECTEDIN)",
        "ilac_kodu": "SUT-DEMO-TRAB",
        "barkod": "8690000000006",
        "esdeger_grup": "DEMO-TRAB",
        "beklenen_red_nedeni": "Uzmanlik saglik kurulu raporu eksik",
        "beklenen_kural_izi": "4.2.14.C:trabectedin:missing_board_report",
        "uzmanlik_kurulu_raporu_var": False,
    },
}

_MATERIAL_PROSE_DEMO_SPECS: dict[str, dict[str, Any]] = {
    "optical_lens_upgrade": {
        "scenario_tag": "sgk_specialty_prose_optical_lens_upgrade",
        "material_code": "SUT-DEMO-OPT",
        "material_name": "Gözlük camı fark ücreti talebi",
        "material_type": "goz",
        "specialty_category": "goz",
        "unit_price": 450.0,
        "expected_rule_id": "3.3.3.A.(4).ek3d_lens_upgrade_difference",
        "specialty_flags": {"optical_lens_upgrade_difference_claim": True},
    },
    "hip_graft_no_pay": {
        "scenario_tag": "sgk_specialty_prose_hip_graft_no_pay",
        "material_code": "SUT-DEMO-GRF",
        "material_name": "Kalça protezi greft malzemesi",
        "material_type": "ortopedi",
        "specialty_category": "ortopedi",
        "unit_price": 3200.0,
        "expected_rule_id": "3.3.4.(6).hip_arthroplasty_graft_no_pay",
        "specialty_flags": {"hip_arthroplasty_graft_claim": True},
    },
    "kdv_ceiling_exceeded": {
        "scenario_tag": "sgk_material_kdv_ceiling_exceeded",
        "material_code": "OP1592",
        "material_name": "ICD kalp pili",
        "material_type": "cihaz",
        "specialty_category": "kardiyoloji",
        "unit_price": 999999.0,
    },
    "procurement_incomplete": {
        "scenario_tag": "sgk_material_bundling_procurement_incomplete",
        "material_code": "OP1000",
        "material_name": "İhale ekranı eksik sözleşmeli malzeme",
        "material_type": "ortez",
        "specialty_category": "ortopedi",
        "unit_price": 850.0,
        "expected_rule_id": "3.1.1.(5).procurement_screen_incomplete",
        "prose_flags": {"ihale_ekrani_eksik_mi": True},
    },
}

_CLAIM_READINESS_DEMO_SPECS: dict[str, dict[str, Any]] = {
    "uts_barcode_missing": {
        "scenario_tag": "sgk_claim_readiness_uts_barcode_missing",
        "material_code": "OP2000",
        "material_name": "ÜTS kaydı eksik implant malzemesi",
        "material_type": "implant",
        "specialty_category": "ortopedi",
        "unit_price": 4200.0,
        "prose_flags": {
            "uts_kayitli_mi": False,
            "titubb_uts_barkod_belge_eksik": True,
        },
    },
}

_MEDULA_DEMO_SPECS: dict[str, dict[str, Any]] = {
    "0012": {
        "scenario_tag": "medula_rejection_1688_molecular_microbiology",
        "visit_date": "2024-07-15",
        "sonuc_kodu": "1688",
        "hata_kodu": "1688",
        "hata_mesaji": (
            "Moleküler mikrobiyoloji işlemi için zorunlu rapor eksik"
        ),
        "medula_asamasi": "fatura_kayit",
    },
    "0018": {
        "scenario_tag": "medula_rejection_0612_board_report_missing",
        "visit_date": "2024-08-20",
        "sonuc_kodu": "0612",
        "hata_kodu": "0612",
        "hata_mesaji": (
            "Uzmanlık sağlık kurulu raporu eksik — işlem faturalanamaz"
        ),
        "medula_asamasi": "fatura_kayit",
    },
    "0025": {
        "scenario_tag": "medula_rejection_1205_service_date_mismatch",
        "visit_date": "2024-09-01",
        "sonuc_kodu": "1205",
        "hata_kodu": "1205",
        "hata_mesaji": "Hizmet tarihi uyumsuz — provizyon ile eşleşmiyor",
        "medula_asamasi": "fatura_kayit",
    },
    "0026": {
        "scenario_tag": "medula_rejection_0521_provision_not_obtained",
        "visit_date": "2024-09-10",
        "sonuc_kodu": "0521",
        "hata_kodu": "0521",
        "hata_mesaji": "Provizyon onay alınmamış — işlem faturalanamaz",
        "medula_asamasi": "provizyon",
    },
    "0027": {
        "scenario_tag": "medula_rejection_0315_specialty_mismatch",
        "visit_date": "2024-09-15",
        "sonuc_kodu": "0315",
        "hata_kodu": "0315",
        "hata_mesaji": "Branş uyumsuz — uzmanlık bilgisi hatalı",
        "medula_asamasi": "fatura_kayit",
    },
    "0028": {
        "scenario_tag": "medula_rejection_0901_duplicate_procedure",
        "visit_date": "2024-09-20",
        "sonuc_kodu": "0901",
        "hata_kodu": "0901",
        "hata_mesaji": "Mükerrer işlem — aynı gün tekrar faturalandırılamaz",
        "medula_asamasi": "fatura_kayit",
    },
    "0029": {
        "scenario_tag": "medula_rejection_0704_uts_barcode_missing",
        "visit_date": "2024-09-25",
        "sonuc_kodu": "0704",
        "hata_kodu": "0704",
        "hata_mesaji": "Malzeme ÜTS barkod kaydı eksik veya geçersiz",
        "medula_asamasi": "fatura_kayit",
    },
    "0030": {
        "scenario_tag": "medula_rejection_0320_package_bundled_procedure",
        "visit_date": "2024-10-01",
        "sonuc_kodu": "0320",
        "hata_kodu": "0320",
        "hata_mesaji": "Paket kapsamındaki işlem ayrı faturalandırılamaz",
        "medula_asamasi": "fatura_kayit",
    },
    "0031": {
        "scenario_tag": "medula_rejection_0411_drug_report_missing",
        "visit_date": "2024-10-05",
        "sonuc_kodu": "0411",
        "hata_kodu": "0411",
        "hata_mesaji": "İlaç endikasyon raporu eksik — sağlık kurulu onayı gerekli",
        "medula_asamasi": "fatura_kayit",
    },
    "0032": {
        "scenario_tag": "medula_rejection_1102_uncontracted_facility",
        "visit_date": "2024-10-10",
        "sonuc_kodu": "1102",
        "hata_kodu": "1102",
        "hata_mesaji": "Sözleşmesiz kurum — SGK anlaşması bulunamadı",
        "medula_asamasi": "fatura_kayit",
    },
}


def _empty_drug_indication_fields() -> dict[str, Any]:
    return {
        "uzmanlik_kurulu_raporu_var": None,
        "rapor_suresi_ay": None,
        "yatarak_tedavi_ilac": None,
        "recete_eden_uzmanlik": None,
    }


def _ensure_drug_indication_columns(drug_claims: list[dict[str, Any]]) -> list[dict[str, Any]]:
    for row in drug_claims:
        for key, default in _empty_drug_indication_fields().items():
            row.setdefault(key, default)
    return drug_claims


def _icd10_in_range(code: str, start: str, end: str) -> bool:
    """Match domain optimization.shared._icd10_in_range for EK-1A checks."""
    import re

    if not code or not start:
        return False
    code = code.strip().upper()
    start = start.strip().upper()
    end = end.strip().upper()
    if not code or not code[0].isalpha():
        return False
    if code[0] != start[0]:
        return False
    if "." in start and start == end:
        return code == start or code.startswith(start + ".")
    if "." in start:
        return code.startswith(start.split(".")[0])
    m_code = re.match(r"[A-Z](\d{2,3})", code)
    m_start = re.match(r"[A-Z](\d{2,3})", start)
    m_end = re.match(r"[A-Z](\d{2,3})", end)
    if not m_code or not m_start or not m_end:
        return False
    return int(m_start.group(1)) <= int(m_code.group(1)) <= int(m_end.group(1))


def _diagnosis_matches_ek1a(code: str) -> bool:
    ek1a_df = _ek1a()
    normalized = str(code or "").strip().upper()
    if not normalized:
        return False
    if ek1a_df.empty:
        return normalized.startswith(("E11", "C92", "I10", "E10", "B20"))
    if not normalized[0].isalpha():
        return False
    letter = normalized[0]
    for _, row in ek1a_df.iterrows():
        start = str(row.get("icd10_start", "")).strip().upper()
        end = str(row.get("icd10_end", "")).strip().upper()
        if start and _icd10_in_range(normalized, start, end):
            return True
    return False


# ── Patient generation ───────────────────────────────────────────────
def _generate_patients(num_patients: int, rng: np.random.Generator) -> list[dict[str, Any]]:
    patients = []
    for i in range(1, num_patients + 1):
        sex = "K" if rng.random() < 0.52 else "E"
        birth_year = rng.integers(1950, 2010)
        name_pool = TURKISH_FEMALE_NAMES if sex == "K" else TURKISH_MALE_NAMES
        name = rng.choice(name_pool)
        surname = rng.choice(TURKISH_SURNAMES)
        record_year = rng.integers(2022, 2025)
        record_month = rng.integers(1, 13)
        record_day = rng.integers(1, 29)
        record_date = f"{record_year}-{record_month:02d}-{record_day:02d}"
        sgk_class = "yesil_kart" if rng.random() < 0.06 else "standard"
        veteran_status = "none"
        if rng.random() < 0.025:
            veteran_status = str(rng.choice(["gazi", "sehit", "yakin"]))
        national_service = "vatani_hizmet" if rng.random() < 0.015 else "none"
        elderly_allowance = bool(birth_year <= 1959 and rng.random() < 0.12)
        patients.append({
            "hasta_id": f"SENTETIK-HASTA-{i:04d}",
            "cinsiyet": sex,
            "dogum_yili": int(birth_year),
            "kohort": rng.choice(["checkup", "ex", "merged", "cancer", "chronic"]),
            "kayit_tarihi": record_date,
            "ana_senaryo": "",
            "veri_tamlik_yuzdesi": int(rng.integers(80, 99)),
            "sentetik_profil_notu": f"{name} {surname} - sentetik profil",
            "sgk_yararlanma_sinifi": sgk_class,
            "gazi_sehit_durumu": veteran_status,
            "vatani_hizmet_durumu": national_service,
            "yasli_aylik_2022": elderly_allowance,
        })
    return patients


# ── Scenario assignment ──────────────────────────────────────────────
def _assign_scenarios(patients: list[dict], rng: np.random.Generator) -> tuple[list[dict], list[dict]]:
    episodes_out = []
    diagnoses_out = []

    for patient in patients:
        pid = patient["hasta_id"]
        if pid in (
            "SENTETIK-HASTA-0006",
            "SENTETIK-HASTA-0007",
            "SENTETIK-HASTA-0008",
            "SENTETIK-HASTA-0009",
            "SENTETIK-HASTA-0010",
            "SENTETIK-HASTA-0011",
            "SENTETIK-HASTA-0012",
            "SENTETIK-HASTA-0013",
            "SENTETIK-HASTA-0014",
            "SENTETIK-HASTA-0015",
            "SENTETIK-HASTA-0016",
            "SENTETIK-HASTA-0017",
            "SENTETIK-HASTA-0018",
            "SENTETIK-HASTA-0019",
            "SENTETIK-HASTA-0020",
            "SENTETIK-HASTA-0021",
            "SENTETIK-HASTA-0022",
            "SENTETIK-HASTA-0023",
            "SENTETIK-HASTA-0024",
            "SENTETIK-HASTA-0025",
            "SENTETIK-HASTA-0026",
            "SENTETIK-HASTA-0027",
            "SENTETIK-HASTA-0028",
            "SENTETIK-HASTA-0029",
            "SENTETIK-HASTA-0030",
            "SENTETIK-HASTA-0031",
            "SENTETIK-HASTA-0032",
            "SENTETIK-HASTA-0033",
        ):
            num_episodes = 1
        else:
            num_episodes = rng.integers(1, 6)
        birth_year = patient["dogum_yili"]

        for ep_idx in range(num_episodes):
            template = rng.choice(SCENARIO_TEMPLATES)

            primary = rng.choice(template["primary_codes"])
            n_secondary = rng.integers(1, 3)
            secondary = list(rng.choice(template["secondary_codes"], size=n_secondary, replace=False))
            all_codes = [primary] + secondary

            visit_roll = float(rng.random())
            if visit_roll < 0.08:
                visit_type = "acil"
            elif visit_roll < 0.13:
                visit_type = "koruyucu"
            elif visit_roll < 0.17:
                visit_type = str(rng.choice(["is_kazasi", "meslek_hastaligi"]))
            else:
                visit_type = rng.choice(template["visit_types"])
            department = rng.choice(template["departments"])

            visit_year = rng.integers(2023, 2025)
            visit_month = rng.integers(1, 13)
            visit_day = rng.integers(1, 29)
            visit_date = f"{visit_year}-{visit_month:02d}-{visit_day:02d}"
            age = int(visit_date[:4]) - birth_year

            eid = f"B-{pid}-{(ep_idx + 1):03d}"

            sbp = int(rng.integers(90, 180))
            dbp = int(rng.integers(50, 110))
            hr = int(rng.integers(55, 120))
            spo2 = int(rng.integers(90, 100))
            height = int(rng.integers(150, 190))
            weight = round(rng.uniform(45, 120), 1)
            bmi = round(weight / ((height / 100) ** 2), 1)

            htn = sbp > 140 or dbp > 90
            dm = "E11" in primary or "E11" in " ".join(secondary)
            cardiac = primary.startswith("I") and any(c.startswith("I") for c in secondary)
            blood_dis = primary.startswith("C9") or primary.startswith("D6")

            episode_row = {
                "hasta_id": pid,
                "basvuru_id": eid,
                "basvuru_tarihi": visit_date,
                "basvuru_yasi": age,
                "cinsiyet": patient["cinsiyet"],
                "birincil_icd10": primary,
                "tum_icd10_kodlari": ",".join(all_codes),
                "tani_tipi": "Kesin Tani",
                "gelis_tipi": visit_type,
                "servis_adi": department,
                "basvuru_icindeki_gelis_sayisi": 1,
                "hasta_toplam_gelis_sayisi": num_episodes,
                "ilk_tani_tarihi": visit_date,
                "son_tani_tarihi": visit_date,
                "tani_gun_farki": 0,
                "sistolik_tansiyon": sbp,
                "diyastolik_tansiyon": dbp,
                "nabiz": hr,
                "spo2": spo2,
                "boy_cm": height,
                "kilo_kg": weight,
                "bmi": bmi,
                "hipertansiyon_var": htn,
                "kalp_damar_var": cardiac,
                "diyabet_var": dm,
                "kan_hastaligi_var": blood_dis,
                "yakinma": f"{department} sentetik yakınma - epizot {ep_idx + 1}",
                "oyku": f"{department} sentetik öykü - epizot {ep_idx + 1}",
                "muayene_notu": f"{department} sentetik muayene - epizot {ep_idx + 1}",
                "tedavi_notu": f"{department} sentetik tedavi - epizot {ep_idx + 1}",
                "kohort": patient["kohort"],
                "donem": "2024",
                "_template": template,
                "_all_codes": all_codes,
            }
            if pid == "SENTETIK-HASTA-0002" and ep_idx == 0:
                episode_row["gelis_tipi"] = "yatis"
                episode_row["_sgk_optional_override_demo"] = "itemized_higher"
                vignette = vignette_for_patient_id(pid)
                if vignette:
                    apply_vignette_episode_defaults(episode_row, vignette)
            elif pid == "SENTETIK-HASTA-0003" and ep_idx == 0:
                episode_row["gelis_tipi"] = "yatis"
                episode_row["_sgk_optional_override_demo"] = "package_higher"
                vignette = vignette_for_patient_id(pid)
                if vignette:
                    apply_vignette_episode_defaults(episode_row, vignette)
            elif pid == "SENTETIK-HASTA-0004" and ep_idx == 0:
                episode_row["gelis_tipi"] = "yatis"
                episode_row["_sgk_blood_uplift_demo"] = True
            elif pid == "SENTETIK-HASTA-0005" and ep_idx == 0:
                episode_row["gelis_tipi"] = "yatis"
                episode_row["_sgk_drg_uplift_demo"] = True
            elif pid == "SENTETIK-HASTA-0006" and ep_idx == 0:
                episode_row["gelis_tipi"] = "yatis"
                episode_row["_sgk_material_uplift_demo"] = True
            elif pid == "SENTETIK-HASTA-0007" and ep_idx == 0:
                episode_row["gelis_tipi"] = "gunubirlik"
                episode_row["_sgk_care_setting_review_demo"] = True
            elif pid == "SENTETIK-HASTA-0008" and ep_idx == 0:
                episode_row["gelis_tipi"] = "gunubirlik"
                episode_row["_sgk_procedure_addon_demo"] = True
            elif pid == "SENTETIK-HASTA-0009" and ep_idx == 0:
                episode_row["gelis_tipi"] = "gunubirlik"
                episode_row["_sgk_procedure_capture_demo"] = True
            elif pid == "SENTETIK-HASTA-0010" and ep_idx == 0:
                episode_row["gelis_tipi"] = "yatis"
                episode_row["_sgk_package_adequacy_demo"] = True
            elif pid == "SENTETIK-HASTA-0011" and ep_idx == 0:
                visit_date = "2024-06-01"
                episode_row["gelis_tipi"] = "poliklinik"
                episode_row["basvuru_tarihi"] = visit_date
                episode_row["ilk_tani_tarihi"] = visit_date
                episode_row["son_tani_tarihi"] = visit_date
                episode_row["basvuru_yasi"] = int(visit_date[:4]) - birth_year
                episode_row["_sgk_gazette_repricing_demo"] = True
            elif pid.rsplit("-", 1)[-1] in _MEDULA_DEMO_SPECS and ep_idx == 0:
                medula_suffix = pid.rsplit("-", 1)[-1]
                medula_spec = _MEDULA_DEMO_SPECS[medula_suffix]
                visit_date = str(medula_spec.get("visit_date") or episode_row["basvuru_tarihi"])
                episode_row["gelis_tipi"] = "poliklinik"
                episode_row["basvuru_tarihi"] = visit_date
                episode_row["ilk_tani_tarihi"] = visit_date
                episode_row["son_tani_tarihi"] = visit_date
                episode_row["basvuru_yasi"] = int(visit_date[:4]) - birth_year
                episode_row["_sgk_medula_playbook_demo"] = True
            elif pid == "SENTETIK-HASTA-0013" and ep_idx == 0:
                episode_row["gelis_tipi"] = "gunubirlik"
                episode_row["_sgk_session_uplift_demo"] = True
            elif pid == "SENTETIK-HASTA-0014" and ep_idx == 0:
                episode_row["gelis_tipi"] = "yatis"
                episode_row["_sgk_drug_indication_demo"] = "bevacizumab_missing_report"
                episode_row["birincil_icd10"] = "C34.9"
                episode_row["_all_codes"] = ["C34.9"]
            elif pid == "SENTETIK-HASTA-0015" and ep_idx == 0:
                episode_row["gelis_tipi"] = "yatis"
                episode_row["_sgk_drug_indication_demo"] = "nivolumab_indication_mismatch"
                episode_row["birincil_icd10"] = "J45.9"
                episode_row["_all_codes"] = ["J45.9"]
            elif pid == "SENTETIK-HASTA-0016" and ep_idx == 0:
                episode_row["gelis_tipi"] = "yatis"
                episode_row["_sgk_drug_indication_demo"] = "daratumumab_report_unknown"
                episode_row["birincil_icd10"] = "C90.0"
                episode_row["_all_codes"] = ["C90.0"]
            elif pid == "SENTETIK-HASTA-0017" and ep_idx == 0:
                episode_row["gelis_tipi"] = "yatis"
                episode_row["_sgk_drug_indication_demo"] = "pembrolizumab_report_ok"
                episode_row["birincil_icd10"] = "C34.9"
                episode_row["_all_codes"] = ["C34.9"]
            elif pid == "SENTETIK-HASTA-0019" and ep_idx == 0:
                episode_row["gelis_tipi"] = "yatis"
                episode_row["_sgk_drug_indication_demo"] = (
                    "trastuzumab_report_duration_mismatch"
                )
                episode_row["birincil_icd10"] = "C50.9"
                episode_row["_all_codes"] = ["C50.9"]
            elif pid == "SENTETIK-HASTA-0020" and ep_idx == 0:
                episode_row["gelis_tipi"] = "yatis"
                episode_row["_sgk_drug_indication_demo"] = "trabectedin_missing_report"
                episode_row["birincil_icd10"] = "C49.9"
                episode_row["_all_codes"] = ["C49.9"]
            elif pid == "SENTETIK-HASTA-0021" and ep_idx == 0:
                episode_row["gelis_tipi"] = "yatis"
                episode_row["_sgk_material_prose_demo"] = "optical_lens_upgrade"
                episode_row["servis_adi"] = "goz"
                episode_row["birincil_icd10"] = "H52.1"
                episode_row["_all_codes"] = ["H52.1"]
            elif pid == "SENTETIK-HASTA-0022" and ep_idx == 0:
                episode_row["gelis_tipi"] = "yatis"
                episode_row["_sgk_material_prose_demo"] = "hip_graft_no_pay"
                episode_row["servis_adi"] = "ortopedi"
                episode_row["birincil_icd10"] = "M16.1"
                episode_row["_all_codes"] = ["M16.1"]
            elif pid == "SENTETIK-HASTA-0023" and ep_idx == 0:
                episode_row["gelis_tipi"] = "yatis"
                episode_row["_sgk_material_prose_demo"] = "kdv_ceiling_exceeded"
                episode_row["servis_adi"] = "kardiyoloji"
                episode_row["birincil_icd10"] = "I49.9"
                episode_row["_all_codes"] = ["I49.9"]
            elif pid == "SENTETIK-HASTA-0024" and ep_idx == 0:
                episode_row["gelis_tipi"] = "yatis"
                episode_row["_sgk_material_prose_demo"] = "procurement_incomplete"
                episode_row["servis_adi"] = "genel_cerrahi"
                episode_row["birincil_icd10"] = "K80.2"
                episode_row["_all_codes"] = ["K80.2"]
            elif pid == "SENTETIK-HASTA-0033" and ep_idx == 0:
                episode_row["gelis_tipi"] = "yatis"
                episode_row["_sgk_claim_readiness_demo"] = "uts_barcode_missing"
                episode_row["servis_adi"] = "ortopedi"
                episode_row["birincil_icd10"] = "M17.9"
                episode_row["_all_codes"] = ["M17.9"]
            elif pid == "SENTETIK-HASTA-0038" and ep_idx == 0:
                visit_date = "2023-10-06"
                episode_row["gelis_tipi"] = "yatis"
                episode_row["basvuru_tarihi"] = visit_date
                episode_row["ilk_tani_tarihi"] = visit_date
                episode_row["son_tani_tarihi"] = visit_date
                episode_row["basvuru_yasi"] = int(visit_date[:4]) - birth_year
                episode_row["birincil_icd10"] = "C92.0"
                episode_row["tum_icd10_kodlari"] = "C92.0"
                episode_row["_all_codes"] = ["C92.0"]
                episode_row["_payment_method_compliance_demo"] = True
            episodes_out.append(episode_row)

            for line_no, code in enumerate(all_codes, start=1):
                exemption = _diagnosis_matches_ek1a(code)

                diagnoses_out.append({
                    "tani_satiri_id": f"TANI-{pid}-{(ep_idx + 1):03d}-{line_no:03d}",
                    "hasta_id": pid,
                    "basvuru_id": eid,
                    "icd10_kodu": code,
                    "tani_rolu": "birincil" if line_no == 1 else "ikincil",
                    "tani_tarihi": visit_date,
                    "ek1a_muafiyet_iliskili_mi": exemption,
                })

    return episodes_out, diagnoses_out


# ── DRG group resolution ─────────────────────────────────────────────
def _drg_group(icd10_codes: list[str]) -> str:
    for code in icd10_codes:
        ch = code[0].upper() if code and code[0].isalpha() else "Z"
        if ch in ICD10_CHAPTER_TO_DRG_GROUP:
            return ICD10_CHAPTER_TO_DRG_GROUP[ch]
    return "C"


# ── Procedure selection ──────────────────────────────────────────────
def _pick_procedures(
    episode: dict,
    num_procs: int,
    *,
    ek2b_procs: dict[str, pd.DataFrame],
    ek2c_packages: dict[str, pd.DataFrame],
    rng: np.random.Generator,
    facility_tier: str | None = None,
    provider_type: str | None = None,
    allow_mandatory_side_procs: bool = False,
) -> list[dict]:
    procs: list[dict] = []
    visit_type = episode["gelis_tipi"]
    all_codes = episode.get("_all_codes", [])
    drg_grp = _drg_group(all_codes)
    service_date = episode.get("basvuru_tarihi")
    care_setting = episode_care_setting(visit_type)

    package_code = None
    package_name = None
    package_price = 0.0
    is_package_candidate = (visit_type in ("yatis", "gunubirlik")) and rng.random() < 0.6
    if is_package_candidate and drg_grp in ek2c_packages:
        pkg_pool = ek2c_packages[drg_grp]
        if not pkg_pool.empty:
            pkg_row = pkg_pool.sample(1, random_state=rng.bit_generator).iloc[0]
            package_code = str(pkg_row["package_code"])
            package_name = str(pkg_row["name"])
            package_price = _money(float(pkg_row.get("price_try", 0) or 0))

    def _side_pool(df: pd.DataFrame) -> pd.DataFrame:
        if not package_code or allow_mandatory_side_procs:
            return df
        return filter_ek2b_pool_for_packaged_claim(
            df,
            care_setting=care_setting,
            facility_tier=facility_tier,
            provider_type=provider_type,
            as_of_date=service_date,
            allow_mandatory_side_procs=False,
        )

    if not ek2b_procs.get("muayene", pd.DataFrame()).empty:
        exam_pool = _side_pool(ek2b_procs["muayene"])
        exam_valid = exam_pool[exam_pool["price_try"].notna() & (exam_pool["price_try"] > 0)]
        if not exam_valid.empty:
            row = exam_valid.sample(1, random_state=rng.bit_generator).iloc[0]
            procs.append({
                "code": str(row["code"]),
                "name": str(row["name"]),
                "price": _money(float(row.get("price_try", 0) or 0)),
                "category": "muayene",
            })

    if visit_type == "yatis" and not ek2b_procs.get("yatak", pd.DataFrame()).empty:
        bed_pool = _side_pool(ek2b_procs["yatak"])
        bed_valid = bed_pool[bed_pool["price_try"].notna() & (bed_pool["price_try"] > 0)]
        if not bed_valid.empty:
            row = bed_valid.sample(1, random_state=rng.bit_generator).iloc[0]
            days = int(rng.integers(1, 21))
            procs.append({
                "code": str(row["code"]),
                "name": str(row["name"]),
                "price": _money(float(row.get("price_try", 0) or 0)),
                "category": "yatak",
                "quantity_override": days,
            })

    n_labs = int(rng.integers(1, 4))
    lab_pool = ek2b_procs.get("lab", pd.DataFrame())
    if not lab_pool.empty:
        lab_pool_valid = _side_pool(lab_pool)
        lab_pool_valid = lab_pool_valid[
            lab_pool_valid["price_try"].notna() &
            (lab_pool_valid["price_try"] > 0)
        ]
        if not lab_pool_valid.empty:
            n_sample = min(n_labs, len(lab_pool_valid))
            lab_sample = lab_pool_valid.sample(n_sample, random_state=rng.bit_generator)
            for _, row in lab_sample.iterrows():
                procs.append({
                    "code": str(row["code"]),
                    "name": str(row["name"]),
                    "price": _money(float(row.get("price_try", 0) or 0)),
                    "category": "laboratuvar",
                })

    # Build set of all EK-2C package codes so we never sample them as general procedures
    ek2c_all_codes: set[str] = set()
    for pkg_df in ek2c_packages.values():
        if not pkg_df.empty and "package_code" in pkg_df.columns:
            ek2c_all_codes.update(pkg_df["package_code"].astype(str).tolist())

    remaining = num_procs - len(procs) - (1 if package_code else 0)
    general_pool = ek2b_procs.get("general", pd.DataFrame())
    if remaining > 0 and not general_pool.empty:
        gen_valid = _side_pool(general_pool)
        gen_valid = gen_valid[
            gen_valid["price_try"].notna() &
            (gen_valid["price_try"] > 0)
        ]
        if not gen_valid.empty and ek2c_all_codes:
            gen_valid = gen_valid[~gen_valid["code"].astype(str).isin(ek2c_all_codes)]
        if not gen_valid.empty:
            n_sample = min(remaining, len(gen_valid))
            sample = gen_valid.sample(n_sample, random_state=rng.bit_generator)
            for _, row in sample.iterrows():
                included_in_pkg = False
                if package_code:
                    included_in_pkg = rng.random() < 0.45
                procs.append({
                    "code": str(row["code"]),
                    "name": str(row["name"]),
                    "price": _money(float(row.get("price_try", 0) or 0)),
                    "category": "islem",
                    "included_in_package": included_in_pkg,
                })

    if package_code:
        procs.append({
            "code": package_code,
            "name": package_name or package_code,
            "price": package_price,
            "category": "paket",
            "is_package": True,
        })

    return procs


def _pick_payment_method_compliance_demo_procedures(
    episode: dict,
    *,
    ek2b_procs: dict[str, pd.DataFrame],
    ek2c_packages: dict[str, pd.DataFrame],
    rng: np.random.Generator,
) -> list[dict]:
    """§2.2.2 demo: billed paket + DRG_MANDATORY side line billed as itemized (612070)."""
    _ = (episode, ek2c_packages, rng)
    name_m, price_m = _lookup_ek2b_price("700390", ek2b_procs)
    name_b, unit_b = _lookup_ek2b_price("612070", ek2b_procs)
    name_l, price_l = _lookup_ek2b_price("L116470", ek2b_procs)
    name_i, price_i = _lookup_ek2b_price("G100580", ek2b_procs)
    pkg_name, _pkg_catalog = _lookup_ek2b_price("P615440", ek2b_procs)
    bed_days = 7
    return [
        {
            "code": "700390",
            "name": name_m,
            "price": _money(max(price_m, 17.11)),
            "category": "muayene",
        },
        {
            "code": "612070",
            "name": name_b,
            "price": _money(unit_b),
            "category": "yatak",
            "quantity_override": bed_days,
        },
        {
            "code": "L116470",
            "name": name_l,
            "price": _money(max(price_l, 107.55)),
            "category": "laboratuvar",
        },
        {
            "code": "G100580",
            "name": name_i,
            "price": _money(max(price_i, 1848.56)),
            "category": "islem",
        },
        {
            "code": "P615440",
            "name": pkg_name,
            "price": _money(103260.58),
            "category": "paket",
            "is_package": True,
            "billed_override": 103260.58,
            "payable_override": 61956.35,
        },
    ]


def _lookup_ek2b_price(code: str, ek2b_procs: dict[str, pd.DataFrame]) -> tuple[str, float]:
    general = ek2b_procs.get("general", pd.DataFrame())
    if general.empty:
        return code, 1000.0
    match = general[general["code"].astype(str) == str(code)]
    if match.empty:
        return code, 1000.0
    row = match.iloc[0]
    return str(row["name"]), _money(float(row.get("price_try", 0) or 1000))


def _pick_blood_uplift_demo_procedures(
    episode: dict,
    *,
    ek2b_procs: dict[str, pd.DataFrame],
    ek2c_packages: dict[str, pd.DataFrame],
    rng: np.random.Generator,
) -> list[dict]:
    """§2.2.2.B-1.e demo: 705371 billed below 36% of reference payable."""
    all_codes = episode.get("_all_codes", [])
    drg_grp = _drg_group(all_codes)
    name, _price = _lookup_ek2b_price("705371", ek2b_procs)

    package_code = "609270"
    package_name, package_price = _lookup_ek2b_price(package_code, ek2b_procs)
    if drg_grp in ek2c_packages and not ek2c_packages[drg_grp].empty:
        pkg_row = ek2c_packages[drg_grp].sample(1, random_state=rng.bit_generator).iloc[0]
        package_code = str(pkg_row["package_code"])
        package_name = str(pkg_row.get("name") or package_code)
        package_price = _money(float(pkg_row.get("price_try", 0) or package_price))

    reference_try = 1000.0
    billed_try = 50.0
    return [
        {
            "code": "705371",
            "name": name or "Eritrosit süspansiyonu",
            "price": reference_try,
            "category": "islem",
            "included_in_package": False,
            "billed_override": billed_try,
            "payable_override": reference_try,
        },
        {
            "code": package_code,
            "name": package_name,
            "price": package_price,
            "category": "paket",
            "is_package": True,
        },
    ]


def _pick_material_uplift_demo_procedures(
    episode: dict,
    *,
    ek2b_procs: dict[str, pd.DataFrame],
    ek2c_packages: dict[str, pd.DataFrame],
    rng: np.random.Generator,
) -> list[dict]:
    """§3.1 demo: procedure 600150 billed without expected material OR2640."""
    _ = (episode, ek2c_packages, rng)
    name, price = _lookup_ek2b_price("600150", ek2b_procs)
    price = _money(max(price, 4500.0))
    return [
        {
            "code": "600150",
            "name": name,
            "price": price,
            "category": "islem",
            "included_in_package": False,
            "disable_surcharge": True,
        },
    ]


def _pick_drg_uplift_demo_procedures(
    episode: dict,
    *,
    ek2b_procs: dict[str, pd.DataFrame],
    ek2c_packages: dict[str, pd.DataFrame],
    rng: np.random.Generator,
) -> list[dict]:
    """§2.2.2 DRG uplift demo: package_candidate=False, package billed, itemized higher."""
    _ = (episode, ek2c_packages, rng)
    disable_surcharge = {"disable_surcharge": True}
    name_a, price_a = _lookup_ek2b_price("600150", ek2b_procs)
    name_b, price_b = _lookup_ek2b_price("600160", ek2b_procs)
    price_a = _money(max(price_a, 5000.0))
    price_b = _money(max(price_b, 4000.0))
    package_code = "609270"
    package_name, package_price = _lookup_ek2b_price(package_code, ek2b_procs)
    package_price = _money(min(package_price or 3500.0, 3500.0))
    return [
        {
            "code": "600150",
            "name": name_a,
            "price": price_a,
            "category": "islem",
            "included_in_package": False,
            "billed_override": 0.0,
            "payable_override": price_a,
            **disable_surcharge,
        },
        {
            "code": "600160",
            "name": name_b,
            "price": price_b,
            "category": "islem",
            "included_in_package": False,
            "billed_override": 0.0,
            "payable_override": price_b,
            **disable_surcharge,
        },
        {
            "code": package_code,
            "name": package_name,
            "price": package_price,
            "category": "paket",
            "is_package": True,
            "payable_override": package_price,
            **disable_surcharge,
        },
    ]


def _pick_optional_override_demo_procedures(
    episode: dict,
    *,
    ek2b_procs: dict[str, pd.DataFrame],
    ek2c_packages: dict[str, pd.DataFrame],
    rng: np.random.Generator,
) -> list[dict]:
    """§2.2.2(2) demo: credible submitted billing + optimizer alternative in strategy."""
    demo_kind = episode.get("_sgk_optional_override_demo")
    _ = (ek2c_packages, rng)
    pid = str(episode.get("hasta_id", ""))
    vignette = vignette_for_patient_id(pid)
    if vignette is None:
        msg = f"Missing vignette for optional override demo patient {pid}"
        raise ValueError(msg)
    return build_optional_override_specs(
        vignette,
        str(demo_kind),
        ek2b_procs=ek2b_procs,
    )


def _pick_gazette_repricing_demo_procedures(
    episode: dict,
    *,
    ek2b_procs: dict[str, pd.DataFrame],
    ek2c_packages: dict[str, pd.DataFrame],
    rng: np.random.Generator,
) -> list[dict]:
    """§3.3 demo: 600150 on 2024-06-01 priced at pre-2026 tebliğ gazette rate."""
    _ = (episode, ek2c_packages, rng)
    name, _price = _lookup_ek2b_price("600150", ek2b_procs)
    stale_price = 449.73
    return [
        {
            "code": "600150",
            "name": name,
            "price": stale_price,
            "category": "islem",
            "included_in_package": False,
            "billed_override": stale_price,
            "payable_override": stale_price,
            "disable_surcharge": True,
        },
    ]


def _pick_package_adequacy_demo_procedures(
    episode: dict,
    *,
    ek2b_procs: dict[str, pd.DataFrame],
    ek2c_packages: dict[str, pd.DataFrame],
    rng: np.random.Generator,
) -> list[dict]:
    """§3.2 demo: package 609270 billed while 600150+600160 support candidate 609300."""
    _ = (episode, ek2c_packages, rng)
    disable_surcharge = {"disable_surcharge": True}
    name_a, price_a = _lookup_ek2b_price("600150", ek2b_procs)
    name_b, price_b = _lookup_ek2b_price("600160", ek2b_procs)
    price_a = _money(max(price_a, 5000.0))
    price_b = _money(max(price_b, 4000.0))
    package_code = "609270"
    package_name, package_price = _lookup_ek2b_price(package_code, ek2b_procs)
    package_price = _money(min(package_price or 3500.0, 3500.0))
    return [
        {
            "code": "600150",
            "name": name_a,
            "price": price_a,
            "category": "islem",
            "included_in_package": False,
            **disable_surcharge,
        },
        {
            "code": "600160",
            "name": name_b,
            "price": price_b,
            "category": "islem",
            "included_in_package": False,
            **disable_surcharge,
        },
        {
            "code": package_code,
            "name": package_name,
            "price": package_price,
            "category": "paket",
            "is_package": True,
            "payable_override": package_price,
            **disable_surcharge,
        },
    ]


def _pick_procedure_capture_demo_procedures(
    episode: dict,
    *,
    ek2b_procs: dict[str, pd.DataFrame],
    ek2c_packages: dict[str, pd.DataFrame],
    rng: np.random.Generator,
) -> list[dict]:
    """§3.1 demo: colonoscopy billed; polypectomy performed in EMR but not submitted."""
    _ = (episode, ek2c_packages, rng)
    return _pick_procedure_addon_demo_procedures(
        episode,
        ek2b_procs=ek2b_procs,
        ek2c_packages=ek2c_packages,
        rng=rng,
    )


def _pick_session_uplift_demo_procedures(
    episode: dict,
    *,
    ek2b_procs: dict[str, pd.DataFrame],
    ek2c_packages: dict[str, pd.DataFrame],
    rng: np.random.Generator,
) -> list[dict]:
    """§2.2.2 session demo: secondary cerrahi line under-billed vs list × point factor."""
    _ = (episode, ek2c_packages, rng)
    primary_name, primary_price = _lookup_ek2b_price("609270", ek2b_procs)
    secondary_name, secondary_price = _lookup_ek2b_price("610070", ek2b_procs)
    primary_price = _money(primary_price)
    secondary_price = _money(secondary_price)
    underbilled = _money(secondary_price * 0.10)
    disable_surcharge = {"disable_surcharge": True}
    return [
        {
            "code": "609270",
            "name": primary_name,
            "price": primary_price,
            "category": "islem",
            "included_in_package": False,
            **disable_surcharge,
        },
        {
            "code": "610070",
            "name": secondary_name,
            "price": secondary_price,
            "category": "islem",
            "included_in_package": False,
            "billed_override": underbilled,
            "payable_override": underbilled,
            **disable_surcharge,
        },
    ]


def _pick_procedure_addon_demo_procedures(
    episode: dict,
    *,
    ek2b_procs: dict[str, pd.DataFrame],
    ek2c_packages: dict[str, pd.DataFrame],
    rng: np.random.Generator,
) -> list[dict]:
    """§2.2.2 demo: colonoscopy billed without expected polypectomy add-on."""
    _ = (episode, ek2c_packages, rng)
    name, price = _lookup_ek2b_price("701450", ek2b_procs)
    price = _money(price)
    return [
        {
            "code": "701450",
            "name": name,
            "price": price,
            "category": "islem",
            "included_in_package": False,
            "disable_surcharge": True,
        },
    ]


def _pick_care_setting_review_demo_procedures(
    episode: dict,
    *,
    ek2b_procs: dict[str, pd.DataFrame],
    ek2c_packages: dict[str, pd.DataFrame],
    rng: np.random.Generator,
) -> list[dict]:
    """§2.2 gunubirlik demo: outpatient mandatory package vs inpatient optional override."""
    _ = (episode, ek2c_packages, rng)

    name_a, price_a = _lookup_ek2b_price("600150", ek2b_procs)
    name_b, price_b = _lookup_ek2b_price("600160", ek2b_procs)
    price_a = _money(max(price_a, 4500.0))
    price_b = _money(max(price_b, 3500.0))

    package_code = "609270"
    package_name, catalog_pkg_price = _lookup_ek2b_price(package_code, ek2b_procs)
    package_price = _money(min(catalog_pkg_price or 3500.0, 3500.0))
    disable_surcharge = {"disable_surcharge": True}

    return [
        {
            "code": "600150",
            "name": name_a,
            "price": price_a,
            "category": "islem",
            "included_in_package": False,
            "billed_override": 0.0,
            "payable_override": price_a,
            **disable_surcharge,
        },
        {
            "code": "600160",
            "name": name_b,
            "price": price_b,
            "category": "islem",
            "included_in_package": False,
            "billed_override": 0.0,
            "payable_override": price_b,
            **disable_surcharge,
        },
        {
            "code": package_code,
            "name": package_name,
            "price": package_price,
            "category": "paket",
            "is_package": True,
            "payable_override": package_price,
            **disable_surcharge,
        },
    ]


# ── Material prose flags (L1.4 claim-field rules) ───────────────────
MATERIAL_PROSE_FLAG_COLUMNS: tuple[str, ...] = (
    "titubb_kayitli_mi",
    "uts_kayitli_mi",
    "ihale_ekrani_eksik_mi",
    "bagli_islem_odenmez",
    "yurtdisi_kurum",
    "kurum_islem_kisiti_ihlali",
    "tani_medula_paket_ayri_fatura_yok",
    "ihale_fiyat_referansi_yetersiz",
    "medula_kod_tarihte_tanimsiz",
    "barkod_sut_uyumsuz",
    "tani_paket_malzeme_kapsam",
    "capraz_brans_fatura_ihlali",
    "ortez_protez_sozlesme_ihlali",
    "bakim_onarim_cap_asimi",
    "protez_onarim_belge_eksik",
    "garanti_bakim_prosedur_eksik",
    "ortez_protez_bakim_dogrulanmadi",
    "ihale_dts_zorunlu_alan_eksik",
    "tedarikci_sozlesme_fiyat_yolu",
    "ek3c_yatarak_dis_temin_ihlali",
    "ek3c_liste_fiyati_yok",
    "ek3_kalite_belge_eksik",
    "ek3c_miat_erken_yenileme",
    "ek3c_ismarlama_ihlali",
    "ek3c_tibbi_uygunluk_eksik",
    "ek3c_basi_giysi_sozlesme",
    "ek3c_mucbir_sebep_yenileme",
    "ek3c_ayakta_tedavi_kapsam",
    "yatarak_kurum_temin_ihlali",
    "karsilanmayan_yatarak_hasta",
    "laboratuvar_ayri_fatura",
    "cok_bransli_sarf_brans",
    "recete_miktar_asimi",
    "rapor_recete_gecersiz",
    "fatura_belge_eksik",
    "tani_paket_malzeme",
    "acil_sozlesmesiz_kurum",
    "listesiz_kesinti_fatura",
    "cift_tekerlekli_recete",
    "ayakta_sozlesmeli_temin",
    "cocuk_buyume_miat",
    "sozlesmeli_temin_kapsam",
    "ismarlama_bilesen_titubb_eksik",
    "titubb_uts_barkod_belge_eksik",
)

# L4.4 §3.3 specialty annex prose — keep in sync with specialty_materials.SPECIALTY_CLAIM_FLAGS
SPECIALTY_PROSE_FLAG_COLUMNS: tuple[str, ...] = (
    "specialty_wound_care_excluded",
    "skin_substitute_non_burn_use",
    "immunobullous_wound_care_patient_supply",
    "immunobullous_wound_care_non_moh_facility",
    "optical_patient_access_deadline_missed",
    "emergency_poliklinik_glasses_claim",
    "optical_lens_upgrade_difference_claim",
    "optical_telescopic_with_cap_claim",
    "contact_lens_with_spectacle_billing",
    "tv5680_with_tv1080_tv1090_combo",
    "hearing_in_ear_under_age_limit",
    "hearing_ear_mold_with_initial_device",
    "cochlear_implant_under_12_months",
    "speech_processor_under_5_years",
    "brainstem_implant_under_12_months",
    "incontinence_hydrophilic_catheter_diaper_only",
    "tissue_bank_unauthorized_product",
    "bone_stimulator_combined_use",
    "bone_stimulator_hypertrophic_nonunion",
    "bone_stimulator_with_autograft",
    "bone_stimulator_benign_tumor_use",
    "open_physis_primary_fracture_graft",
    "adult_primary_fracture_bone_stimulator",
    "hip_arthroplasty_graft_claim",
    "graft_allograft_xenograft_combined",
    "primary_ligament_tendon_injury_graft",
    "glucose_meter_early_renewal",
    "wheelchair_stand_device_duplicate_billing",
    "stand_up_wheelchair_early_renewal",
    "paraplegia_standing_table_over_age_limit",
    "paraplegia_wheelchair_separate_billing",
    "spinal_mobility_device_duplicate_billing",
    "returned_device_without_kurum_approval",
    "nimv_heated_humidifier_separate_billing",
    "dental_prosthesis_adhesive_claim",
    "dual_mesh_primary_hernia_repair",
)


def _default_prose_material_flags() -> dict[str, bool]:
    return {
        "titubb_kayitli_mi": True,
        "uts_kayitli_mi": True,
        "ihale_ekrani_eksik_mi": False,
        "bagli_islem_odenmez": False,
        "yurtdisi_kurum": False,
        "kurum_islem_kisiti_ihlali": False,
        "tani_medula_paket_ayri_fatura_yok": False,
        "ihale_fiyat_referansi_yetersiz": False,
        "medula_kod_tarihte_tanimsiz": False,
        "barkod_sut_uyumsuz": False,
        "tani_paket_malzeme_kapsam": False,
        "capraz_brans_fatura_ihlali": False,
        "ortez_protez_sozlesme_ihlali": False,
        "bakim_onarim_cap_asimi": False,
        "protez_onarim_belge_eksik": False,
        "garanti_bakim_prosedur_eksik": False,
        "ortez_protez_bakim_dogrulanmadi": False,
        "ihale_dts_zorunlu_alan_eksik": False,
        "tedarikci_sozlesme_fiyat_yolu": False,
        "ek3c_yatarak_dis_temin_ihlali": False,
        "ek3c_liste_fiyati_yok": False,
        "ek3_kalite_belge_eksik": False,
        "ek3c_miat_erken_yenileme": False,
        "ek3c_ismarlama_ihlali": False,
        "ek3c_tibbi_uygunluk_eksik": False,
        "ek3c_basi_giysi_sozlesme": False,
        "ek3c_mucbir_sebep_yenileme": False,
        "ek3c_ayakta_tedavi_kapsam": False,
        "yatarak_kurum_temin_ihlali": False,
        "karsilanmayan_yatarak_hasta": False,
        "laboratuvar_ayri_fatura": False,
        "cok_bransli_sarf_brans": False,
        "recete_miktar_asimi": False,
        "rapor_recete_gecersiz": False,
        "fatura_belge_eksik": False,
        "tani_paket_malzeme": False,
        "acil_sozlesmesiz_kurum": False,
        "listesiz_kesinti_fatura": False,
        "cift_tekerlekli_recete": False,
        "ayakta_sozlesmeli_temin": False,
        "cocuk_buyume_miat": False,
        "sozlesmeli_temin_kapsam": False,
        "ismarlama_bilesen_titubb_eksik": False,
        "titubb_uts_barkod_belge_eksik": False,
    }


def _default_specialty_prose_flags() -> dict[str, bool]:
    return {flag: False for flag in SPECIALTY_PROSE_FLAG_COLUMNS}


def _sample_prose_material_flags(*, bundled: bool) -> dict[str, bool]:
    """Default flags only — coverage is applied deterministically after generation."""
    return {**_default_prose_material_flags(), **_default_specialty_prose_flags()}


def _ensure_specialty_flag_coverage(materials: list[dict[str, Any]]) -> None:
    """Guarantee at least one demo row per L4.4 specialty prose claim flag."""
    if not materials:
        return

    candidates = [row for row in materials if not row.get("pakete_dahil_mi")] or materials

    for idx, col in enumerate(SPECIALTY_PROSE_FLAG_COLUMNS):
        if any(row.get(col) for row in materials):
            continue
        row = candidates[idx % len(candidates)]
        row[col] = True
        if float(row.get("fatura_tutari_try") or 0) <= 0:
            row["fatura_tutari_try"] = 100.0
            row["birim_fiyat_try"] = 100.0


def _reconcile_claim_header_totals(
    claims: list[dict[str, Any]],
    procedure_rows: list[dict[str, Any]],
    materials: list[dict[str, Any]],
    drug_rows: list[dict[str, Any]],
    expected: list[dict[str, Any]] | None = None,
) -> None:
    """Recompute claim header billed/payable totals from line sums (post L4.4 inject)."""
    billed_by_claim: dict[str, float] = defaultdict(float)
    payable_by_claim: dict[str, float] = defaultdict(float)

    for rows in (procedure_rows, materials, drug_rows):
        for row in rows:
            claim_id = str(row.get("fatura_id", ""))
            if not claim_id:
                continue
            billed_by_claim[claim_id] += float(row.get("fatura_tutari_try") or 0)
            payable_by_claim[claim_id] += float(row.get("beklenen_odenebilir_tutar_try") or 0)

    claim_level_expected = {
        str(row.get("fatura_id", "")): row
        for row in (expected or [])
        if str(row.get("satir_tipi", "")) == "fatura" and not str(row.get("satir_id", ""))
    }

    for claim in claims:
        claim_id = str(claim.get("fatura_id", ""))
        billed = billed_by_claim.get(claim_id, 0.0)
        payable = payable_by_claim.get(claim_id, 0.0)
        claim["beklenen_toplam_fatura_tutari_try"] = _money(billed)
        claim["beklenen_toplam_odenebilir_tutar_try"] = _money(payable)

        expected_row = claim_level_expected.get(claim_id)
        if expected_row is not None:
            expected_row["beklenen_odenebilir_tutar_try"] = _money(payable)
            expected_row["beklenen_tasarruf_try"] = _money(billed - payable)
            expected_row["beklenen_durum"] = (
                "kismi_red" if payable < billed else "odenebilir"
            )


def _inject_specialty_keyword_demo_rows(
    materials: list[dict[str, Any]],
    claims: list[dict[str, Any]],
) -> None:
    """Append billed lines that trigger keyword-only §3.3 rules (no claim flags)."""
    if not claims:
        return

    claim = claims[0]
    claim_id = str(claim.get("fatura_id", ""))
    patient_id = str(claim.get("hasta_id", ""))
    service_date = claim.get("fatura_baslangic_tarihi") or claim.get("fatura_tarihi") or "2024-06-01"

    keyword_demos = (
        ("DEMO-L44-W1", "Transparan film yara örtüsü", 85.0),
        ("DEMO-L44-W2", "Hidrojel yara nemlendirici", 120.0),
        ("DEMO-L44-CL1", "Kontakt lens solüsyonu", 35.0),
        ("DEMO-L44-SS1", "Deri taklidi yedek", 250.0),
    )

    for idx, (code, name, price) in enumerate(keyword_demos):
        line_id = f"MLZ-{claim_id}-L44-{idx + 1:02d}"
        materials.append(
            {
                "malzeme_satiri_id": line_id,
                "fatura_id": claim_id,
                "islem_satiri_id": f"ISL-{claim_id}-001",
                "hasta_id": patient_id,
                "malzeme_tarihi": service_date,
                "malzeme_kodu": code,
                "malzeme_adi": name,
                "malzeme_tipi": "uzmanlik",
                "uzmanlik_kategorisi": "wound",
                "adet": 1,
                "birim_fiyat_try": price,
                "fatura_tutari_try": price,
                "beklenen_odenebilir_tutar_try": price,
                "pakete_dahil_mi": False,
                "on_onay_gerekli_mi": False,
                "beklenen_red_nedeni": "",
                "beklenen_kural_izi": f"L4.4:{code}",
                **_default_prose_material_flags(),
                **_default_specialty_prose_flags(),
            }
        )


def _ensure_prose_flag_coverage(materials: list[dict[str, Any]]) -> None:
    """Guarantee at least one demo row per prose flag without touching RNG."""
    if not materials:
        return

    candidates = [
        row for row in materials if not row.get("pakete_dahil_mi")
    ] or materials

    for idx, col in enumerate(MATERIAL_PROSE_FLAG_COLUMNS[2:]):
        if any(row.get(col) for row in materials):
            continue
        candidates[idx % len(candidates)][col] = True

    if not any(row.get("titubb_kayitli_mi") is False for row in materials):
        candidates[0]["titubb_kayitli_mi"] = False
    if not any(row.get("uts_kayitli_mi") is False for row in materials):
        candidates[min(1, len(candidates) - 1)]["uts_kayitli_mi"] = False


# ── ClaimEpisodeContext ──────────────────────────────────────────────
@dataclass
class ClaimEpisodeContext:
    pid: str
    eid: str
    visit_type: str
    claim_id: str
    start_date: str
    scenario_tag: str

    facility_tier: str
    is_university: bool
    provider: str
    admission: str | None
    discharge: str | None
    claim_end: str

    package_candidate: bool
    package_code_for_claim: str | None

    all_codes: list[str]
    template: dict[str, Any]

    ek2g_no_surcharge: set[str]
    ek2c1_copay_rates: dict[str, float]
    ek3_all: list[tuple[str, pd.DataFrame]]
    active_drugs: pd.DataFrame

    rng: np.random.Generator

    procedure_rows: list[dict] = field(default_factory=list)
    materials: list[dict] = field(default_factory=list)
    drug_claims: list[dict] = field(default_factory=list)
    expected: list[dict] = field(default_factory=list)
    lab_billing_budget: dict = field(default_factory=dict)

    proc_specs: list[dict] = field(default_factory=list)


def _build_normalized_ek2c1_copay_rates(ek2c1_df: pd.DataFrame) -> dict[str, float]:
    """EK-2C-1 mandated copay fractions keyed by normalized procedure code."""
    from src.bilun.domain.prose_rules.catalog_membership import normalize_procedure_code

    rates: dict[str, float] = {}
    if ek2c1_df.empty:
        return rates
    for _, row in ek2c1_df.iterrows():
        norm = normalize_procedure_code(str(row["procedure_code"]))
        if norm:
            rates[norm] = float(row["copay_rate_pct"]) / 100.0
    return rates


def _reconcile_ek2c1_procedure_lines(
    rows: list[dict[str, Any]],
    ek2c1_copay_rates: dict[str, float],
) -> None:
    """Align EK-2C-1 listed lines: flag on + payable = billed × (1 − mandated copay %)."""
    from src.bilun.domain.prose_rules.catalog_membership import normalize_procedure_code

    for row in rows:
        if row.get("pakete_dahil_mi"):
            code = normalize_procedure_code(str(row.get("islem_kodu") or ""))
            if code in ek2c1_copay_rates:
                row["katilim_payi_orani_uygulanabilir_mi"] = False
                row["katilim_payi_orani"] = None
            continue
        code = normalize_procedure_code(str(row.get("islem_kodu") or ""))
        if not code or code not in ek2c1_copay_rates:
            continue
        billed = float(row.get("fatura_tutari_try") or 0)
        if billed <= 0:
            continue
        copay_frac = ek2c1_copay_rates[code]
        row["katilim_payi_orani_uygulanabilir_mi"] = True
        row["katilim_payi_orani"] = copay_frac
        payable = _money(billed * (1 - copay_frac))
        row["beklenen_odenebilir_tutar_try"] = min(payable, billed)


def _ensure_ek2c1_violation_demos(
    procedure_rows: list[dict[str, Any]],
    ek2c1_copay_rates: dict[str, float],
) -> None:
    """Inject a small fixed set of deliberate EK-2C-1 violations for optimizer demos."""
    from src.bilun.domain.prose_rules.catalog_membership import normalize_procedure_code

    catalog_lines: list[dict[str, Any]] = []
    for row in procedure_rows:
        if row.get("pakete_dahil_mi"):
            continue
        code = normalize_procedure_code(str(row.get("islem_kodu") or ""))
        billed = float(row.get("fatura_tutari_try") or 0)
        if code in ek2c1_copay_rates and billed > 0:
            catalog_lines.append(row)

    if len(catalog_lines) < 3:
        return

    row_rate_1 = catalog_lines[0]
    billed_1 = float(row_rate_1["fatura_tutari_try"])
    row_rate_1["katilim_payi_orani_uygulanabilir_mi"] = True
    row_rate_1["beklenen_odenebilir_tutar_try"] = billed_1

    row_rate_2 = catalog_lines[1]
    billed_2 = float(row_rate_2["fatura_tutari_try"])
    code_2 = normalize_procedure_code(str(row_rate_2["islem_kodu"]))
    mandated_2 = ek2c1_copay_rates[code_2]
    wrong_frac = mandated_2 + 0.20 if mandated_2 <= 0.60 else mandated_2 - 0.20
    if abs(wrong_frac - mandated_2) < 0.01:
        wrong_frac = 0.20
    row_rate_2["katilim_payi_orani_uygulanabilir_mi"] = True
    row_rate_2["katilim_payi_orani"] = wrong_frac
    row_rate_2["beklenen_odenebilir_tutar_try"] = _money(billed_2 * (1 - wrong_frac))

    row_flag = catalog_lines[2]
    row_flag["katilim_payi_orani_uygulanabilir_mi"] = False
    row_flag["katilim_payi_orani"] = None


def _procedure_row_as_claim_line(row: dict) -> "ProcedureClaimLine":
    from datetime import date
    from decimal import Decimal

    from src.bilun.domain.claims.models import ProcedureClaimLine

    return ProcedureClaimLine(
        procedure_line_id=str(row["islem_satiri_id"]),
        claim_id=str(row["fatura_id"]),
        patient_id=str(row["hasta_id"]),
        episode_id=str(row["basvuru_id"]),
        procedure_date=date.fromisoformat(str(row["islem_tarihi"])[:10]),
        procedure_code=str(row["islem_kodu"]),
        procedure_name=str(row.get("islem_adi") or ""),
        procedure_category=str(row.get("islem_kategorisi") or "islem"),
        quantity=int(row.get("adet") or 1),
        unit_price_try=Decimal(str(row.get("birim_fiyat_try") or 0)),
        billed_amount_try=Decimal(str(row.get("fatura_tutari_try") or 0)),
        expected_payable_try=Decimal(str(row.get("beklenen_odenebilir_tutar_try") or 0)),
        is_package_included=bool(row.get("pakete_dahil_mi")),
        package_code="",
        surcharge_applicable=False,
        copay_rate_applicable=False,
        denial_reason_expected="",
        rule_trace_expected="",
    )


def _apply_session_point_billed_factors(
    rows: list[dict],
    *,
    locked_procedure_codes: set[str] | None = None,
) -> tuple[float, float]:
    """Scale secondary same-day billed lines per SUT §2.2.2; returns billed/payable deltas."""
    from src.bilun.domain.prose_rules.catalog_membership import normalize_procedure_code
    from src.bilun.domain.prose_rules.session_pricing import compute_session_point_factors
    from src.bilun.domain.prose_rules.session_specialty import detect_cross_specialty_session

    locked = {
        normalize_procedure_code(code)
        for code in (locked_procedure_codes or set())
    }

    old_billed = sum(float(row.get("fatura_tutari_try") or 0) for row in rows)
    old_payable = sum(float(row.get("beklenen_odenebilir_tutar_try") or 0) for row in rows)

    billable = [
        row
        for row in rows
        if not row.get("pakete_dahil_mi")
        and float(row.get("fatura_tutari_try") or 0) > 0
        and normalize_procedure_code(str(row.get("islem_kodu") or "")) not in locked
    ]
    if len(billable) < 2:
        return 0.0, 0.0

    by_date: dict[str, list[dict]] = defaultdict(list)
    for row in billable:
        by_date[str(row.get("islem_tarihi") or "")].append(row)

    for session_rows in by_date.values():
        if len(session_rows) < 2:
            continue

        codes = [str(row["islem_kodu"]) for row in session_rows]
        stub_lines = [_procedure_row_as_claim_line(row) for row in session_rows]
        cross_specialty = detect_cross_specialty_session(stub_lines, None)
        session = compute_session_point_factors(
            codes,
            same_incision=True,
            cross_specialty=cross_specialty,
        )
        if session.rule_id == "single_procedure":
            continue

        factors = {
            normalize_procedure_code(factor.procedure_code): factor
            for factor in session.factors
        }
        primary_factor = 1.0
        for row in session_rows:
            factor = factors.get(normalize_procedure_code(str(row["islem_kodu"])))
            if factor is not None and factor.is_primary:
                primary_factor = factor.point_factor
                break

        for row in session_rows:
            factor = factors.get(normalize_procedure_code(str(row["islem_kodu"])))
            if (
                factor is None
                or factor.is_primary
                or factor.point_factor >= primary_factor
            ):
                continue

            billed = float(row["fatura_tutari_try"])
            payable = float(row["beklenen_odenebilir_tutar_try"])
            adjusted_billed = _money(billed * factor.point_factor)
            ratio = adjusted_billed / billed if billed > 0 else 1.0
            row["fatura_tutari_try"] = adjusted_billed
            row["beklenen_odenebilir_tutar_try"] = _money(payable * ratio)

    new_billed = sum(float(row.get("fatura_tutari_try") or 0) for row in rows)
    new_payable = sum(float(row.get("beklenen_odenebilir_tutar_try") or 0) for row in rows)
    return _money(new_billed - old_billed), _money(new_payable - old_payable)


# ── Per-claim line builders ──────────────────────────────────────────
def _append_procedure_lines_for_claim(
    ctx: ClaimEpisodeContext,
) -> tuple[float, float]:
    total_billed = 0.0
    total_payable = 0.0
    row_start = len(ctx.procedure_rows)

    for line_idx, ps in enumerate(ctx.proc_specs, start=1):
        is_package_proc = (ps["category"] == "paket")
        qty = int(ps.get("quantity_override", 1))
        unit_price = ps["price"]
        billed_override = "billed_override" in ps
        billed = _money(ps["billed_override"]) if billed_override else _money(unit_price * qty)

        included_in_package = ps.get("included_in_package", False)

        if included_in_package:
            sgk_base = 0.0
        elif is_package_proc:
            sgk_base = billed
        else:
            sgk_base = billed

        surcharge_applicable = (
            not ps.get("disable_surcharge")
            and ps["code"] not in ctx.ek2g_no_surcharge
        )
        if included_in_package:
            surcharge_applicable = False
        surcharge_rate = None
        if surcharge_applicable and not is_package_proc:
            if ctx.is_university:
                surcharge_rate = round(ctx.rng.uniform(0.90, 1.00), 2) if ctx.rng.random() < 0.8 else None
            else:
                surcharge_rate = round(float(ctx.rng.choice([0.20, 0.30, 0.50, 0.75, 1.00])), 2)

        from src.bilun.domain.prose_rules.catalog_membership import normalize_procedure_code

        norm_code = normalize_procedure_code(ps["code"])
        copay_applicable = norm_code in ctx.ek2c1_copay_rates
        copay_rate = ctx.ek2c1_copay_rates.get(norm_code) if copay_applicable else None
        if (
            not copay_applicable
            and ctx.visit_type in ("poliklinik", "gunubirlik")
            and not is_package_proc
        ):
            copay_applicable = True
            copay_rate = float(ctx.rng.choice([0.20, 0.40, 0.50]))
        if included_in_package:
            copay_applicable = False
            copay_rate = None

        if "payable_override" in ps:
            # Keep explicit demo overrides deterministic and mark rates unavailable.
            copay_applicable = False
            copay_rate = None
            surcharge_rate = None

        if billed_override:
            denominator = 1.0 + float(surcharge_rate or 0.0)
            sgk_base = _money(billed / denominator) if denominator > 0 else billed

        expected_payable = sgk_base
        patient_copay = 0.0
        if copay_rate and copay_applicable:
            expected_payable = _money(sgk_base * (1 - copay_rate))
            patient_copay = _money(sgk_base * copay_rate)
        surcharge_amount = (
            _money(sgk_base * float(surcharge_rate))
            if surcharge_applicable and surcharge_rate
            else 0.0
        )
        if not included_in_package and not billed_override:
            billed = _money(expected_payable + patient_copay + surcharge_amount)
        if expected_payable > billed:
            expected_payable = billed
        if "payable_override" in ps:
            expected_payable = _money(ps["payable_override"])

        denial_reason = ""
        if included_in_package:
            denial_reason = "Paket ici islem ayrica odenmez"

        line_id = f"ISL-{ctx.claim_id}-{line_idx:03d}"
        ctx.procedure_rows.append({
            "islem_satiri_id": line_id,
            "fatura_id": ctx.claim_id,
            "hasta_id": ctx.pid,
            "basvuru_id": ctx.eid,
            "islem_tarihi": ctx.start_date,
            "islem_kodu": ps["code"],
            "islem_adi": ps["name"],
            "islem_kategorisi": ps["category"],
            "adet": qty,
            "birim_fiyat_try": unit_price,
            "fatura_tutari_try": billed,
            "beklenen_odenebilir_tutar_try": expected_payable,
            "pakete_dahil_mi": included_in_package,
            "paket_kodu": (
                (ps.get("candidate_package_code") or ctx.package_code_for_claim)
                if (included_in_package or is_package_proc or ps.get("candidate_package_code"))
                else None
            ),
            "ilave_ucret_uygulanabilir_mi": surcharge_applicable,
            "ilave_ucret_orani": surcharge_rate,
            "katilim_payi_orani_uygulanabilir_mi": copay_applicable,
            "katilim_payi_orani": copay_rate,
            "beklenen_red_nedeni": denial_reason,
            "beklenen_kural_izi": f"EK-2B:{ps['code']}" if not is_package_proc else f"EK-2C:{ps['code']}",
        })

        if ps["category"] == "laboratuvar":
            ctx.lab_billing_budget[(ctx.eid, ps["code"])] = {
                "islem_satiri_id": line_id,
                "kalan_adet": qty,
                "test_adi": ps["name"],
            }

        if included_in_package:
            ctx.expected.append({
                "beklenen_cikti_id": f"BEK-{line_id}",
                "senaryo_etiketi": ctx.scenario_tag,
                "hasta_id": ctx.pid,
                "fatura_id": ctx.claim_id,
                "satir_id": line_id,
                "satir_tipi": "islem",
                "kural_ailesi": "drg_paket_ayristirma",
                "beklenen_durum": "pakete_dahil_red",
                "beklenen_odenebilir_tutar_try": expected_payable,
                "beklenen_tasarruf_try": _money(billed - expected_payable),
                "beklenen_red_nedeni": "Paket ici islem ayrica odenmez",
                "beklenen_kural_izi": f"EK-2B:{ps['code']}",
                "test_notu": "Satir duzeyi sentetik beklenen cikti",
            })

        total_billed += billed
        total_payable += expected_payable

    claim_rows = ctx.procedure_rows[row_start:]
    locked_codes = {
        str(ps["code"]) for ps in ctx.proc_specs if "billed_override" in ps
    }
    delta_billed, delta_payable = _apply_session_point_billed_factors(
        claim_rows,
        locked_procedure_codes=locked_codes,
    )
    _reconcile_ek2c1_procedure_lines(claim_rows, ctx.ek2c1_copay_rates)
    total_billed = _money(total_billed + delta_billed)
    total_payable = _money(total_payable + delta_payable)

    return total_billed, total_payable


def _append_material_prose_demo_line(
    ctx: ClaimEpisodeContext,
    spec: dict[str, Any],
) -> tuple[float, float]:
    """Inject a single pinned material line for Sprint 2 prose/KDV demos."""
    proc_line_id = f"ISL-{ctx.claim_id}-001"
    if ctx.procedure_rows:
        for row in ctx.procedure_rows:
            if row.get("fatura_id") == ctx.claim_id:
                proc_line_id = str(row.get("islem_satiri_id") or proc_line_id)
                break

    mat_billed = _money(float(spec.get("unit_price") or 0))
    m_line_id = f"MLZ-{ctx.claim_id}-DEMO-001"
    prose_flags = _default_prose_material_flags()
    prose_flags.update(spec.get("prose_flags") or {})
    specialty_flags = _default_specialty_prose_flags()
    specialty_flags.update(spec.get("specialty_flags") or {})

    ctx.materials.append({
        "malzeme_satiri_id": m_line_id,
        "fatura_id": ctx.claim_id,
        "islem_satiri_id": proc_line_id,
        "hasta_id": ctx.pid,
        "malzeme_tarihi": ctx.start_date,
        "malzeme_kodu": str(spec.get("material_code") or ""),
        "malzeme_adi": str(spec.get("material_name") or ""),
        "malzeme_tipi": str(spec.get("material_type") or "genel"),
        "uzmanlik_kategorisi": str(spec.get("specialty_category") or "genel"),
        "adet": 1,
        "birim_fiyat_try": mat_billed,
        "fatura_tutari_try": mat_billed,
        "beklenen_odenebilir_tutar_try": mat_billed,
        "pakete_dahil_mi": False,
        "on_onay_gerekli_mi": False,
        "beklenen_red_nedeni": "",
        "beklenen_kural_izi": f"MAT-PROSE-DEMO:{spec.get('material_code', '')}",
        **prose_flags,
        **specialty_flags,
    })
    return mat_billed, mat_billed


def _append_material_lines_for_claim(ctx: ClaimEpisodeContext) -> tuple[float, float]:
    total_billed = 0.0
    total_payable = 0.0

    material_catalogs = ctx.template.get("material_catalogs", [])
    if not material_catalogs or ctx.visit_type not in ("yatis", "gunubirlik") or not ctx.ek3_all:
        return total_billed, total_payable

    n_materials = ctx.rng.integers(1, 5)
    for mat_idx in range(n_materials):
        cat_name = ctx.rng.choice(material_catalogs)
        cat_df = next((df for name, df in ctx.ek3_all if cat_name in name), None)
        if cat_df is None or cat_df.empty:
            continue
        valid = cat_df[
            cat_df["price_try"].notna() &
            (cat_df["price_try"] > 0) &
            cat_df["sut_code"].notna()
        ]
        if valid.empty:
            continue
        row = valid.sample(1, random_state=ctx.rng.bit_generator).iloc[0]

        bundled = ctx.package_code_for_claim is not None and ctx.rng.random() < 0.55
        mat_billed = _money(float(row.get("price_try", 0) or 0))
        mat_payable = 0.0 if bundled else mat_billed
        pre_auth = ctx.rng.random() < 0.5

        m_line_id = f"MLZ-{ctx.claim_id}-{(mat_idx + 1):03d}"
        prose_flags = _sample_prose_material_flags(bundled=bundled)
        ctx.materials.append({
            "malzeme_satiri_id": m_line_id,
            "fatura_id": ctx.claim_id,
            "islem_satiri_id": f"ISL-{ctx.claim_id}-{(mat_idx % max(1, len(ctx.proc_specs))) + 1:03d}",
            "hasta_id": ctx.pid,
            "malzeme_tarihi": ctx.start_date,
            "malzeme_kodu": str(row.get("sut_code", "")),
            "malzeme_adi": str(row.get("material_name", "")),
            "malzeme_tipi": str(row.get("category", "genel")),
            "uzmanlik_kategorisi": str(row.get("category", "genel")),
            "adet": 1,
            "birim_fiyat_try": mat_billed,
            "fatura_tutari_try": mat_billed,
            "beklenen_odenebilir_tutar_try": mat_payable,
            "pakete_dahil_mi": bundled,
            "on_onay_gerekli_mi": pre_auth,
            "beklenen_red_nedeni": "Paket kapsamindaki sarf malzeme ayrica odenmez" if bundled else "",
            "beklenen_kural_izi": f"EK-3:{row.get('sut_code', '')}",
            **prose_flags,
        })
        if bundled or pre_auth:
            ctx.expected.append({
                "beklenen_cikti_id": f"BEK-{m_line_id}",
                "senaryo_etiketi": ctx.scenario_tag,
                "hasta_id": ctx.pid,
                "fatura_id": ctx.claim_id,
                "satir_id": m_line_id,
                "satir_tipi": "malzeme",
                "kural_ailesi": "faturalama_stratejisi",
                "beklenen_durum": "pakete_dahil_red" if bundled else "on_onay_gerekli_odenebilir",
                "beklenen_odenebilir_tutar_try": mat_payable,
                "beklenen_tasarruf_try": _money(mat_billed - mat_payable),
                "beklenen_red_nedeni": "Paket kapsamindaki sarf malzeme ayrica odenmez" if bundled else "",
                "beklenen_kural_izi": f"EK-3:{row.get('sut_code', '')}",
                "test_notu": "Satir duzeyi sentetik beklenen cikti",
            })
        total_billed += mat_billed
        total_payable += mat_payable

    return total_billed, total_payable


def _append_drug_lines_for_claim(ctx: ClaimEpisodeContext) -> tuple[float, float]:
    total_billed = 0.0
    total_payable = 0.0

    n_drugs = ctx.rng.integers(1, 5)
    if n_drugs <= 0 or ctx.active_drugs.empty:
        return total_billed, total_payable

    drug_sample = ctx.active_drugs.sample(n_drugs, random_state=ctx.rng.bit_generator)
    for drug_idx, (_, drug_row) in enumerate(drug_sample.iterrows(), start=1):
        unit_price = _drug_unit_price(drug_row, ctx.rng)
        qty = int(ctx.rng.integers(1, 4))
        billed = _money(unit_price * qty)
        tier_raw = drug_row.get("discount_tier_1")
        try:
            discount_tier = float(tier_raw) if tier_raw is not None else 0.28
        except (ValueError, TypeError):
            discount_tier = 0.28
        payable = _money(billed * (1 - discount_tier))
        copay_rate = discount_tier if discount_tier > 0 else None

        d_line_id = f"ILC-{ctx.claim_id}-{drug_idx:03d}"
        prescription_id = f"REC-{ctx.claim_id}-{drug_idx:03d}"
        ctx.drug_claims.append({
            "ilac_satiri_id": d_line_id,
            "recete_id": prescription_id,
            "fatura_id": ctx.claim_id,
            "hasta_id": ctx.pid,
            "basvuru_id": ctx.eid,
            "ilac_fatura_tarihi": ctx.start_date,
            "ilac_adi": str(drug_row.get("drug_name", "")),
            "ilac_kodu": str(drug_row.get("kamu_no", "")),
            "barkod": str(drug_row.get("barcode", "")),
            "esdeger_grup": str(drug_row.get("equivalence_group", "")),
            "adet": qty,
            "birim_fiyat_try": unit_price,
            "fatura_tutari_try": billed,
            "beklenen_odenebilir_tutar_try": payable,
            "beklenen_indirim_kademesi": discount_tier,
            "katilim_payi_orani": copay_rate,
            "ilave_ucret_orani": None,
            "beklenen_red_nedeni": "",
            "beklenen_kural_izi": f"EK-4A:{drug_row.get('kamu_no', '')}",
            **_empty_drug_indication_fields(),
        })
        ctx.expected.append({
            "beklenen_cikti_id": f"BEK-{d_line_id}",
            "senaryo_etiketi": ctx.scenario_tag,
            "hasta_id": ctx.pid,
            "fatura_id": ctx.claim_id,
            "satir_id": d_line_id,
            "satir_tipi": "ilac",
            "kural_ailesi": "ilac_indirimi",
            "beklenen_durum": "ilac_indirimi_uygulandi",
            "beklenen_odenebilir_tutar_try": payable,
            "beklenen_tasarruf_try": _money(billed - payable),
            "beklenen_red_nedeni": "",
            "beklenen_kural_izi": f"EK-4A:{drug_row.get('kamu_no', '')}",
            "test_notu": "Satir duzeyi sentetik beklenen cikti",
        })
        total_billed += billed
        total_payable += payable

    return total_billed, total_payable


# ── Claims and lines orchestrator ────────────────────────────────────
def _generate_claims_and_lines(
    episodes: list[dict],
    rng: np.random.Generator,
) -> tuple[
    list[dict],
    list[dict],
    list[dict],
    list[dict],
    list[dict],
    list[dict],
    dict[tuple, dict],
]:
    ek2b_df = _ek2b()
    ek2c_df = _ek2c_latest()
    ek2c1_df = _ek2c1()
    ek2g_df = _ek2g()
    ek4a_df = _ek4a()

    ek2g_no_surcharge: set[str] = set()
    if not ek2g_df.empty:
        ek2g_no_surcharge = set(ek2g_df["procedure_code"].astype(str).tolist())

    ek2c1_copay_rates = _build_normalized_ek2c1_copay_rates(ek2c1_df)

    ek2c_packages: dict[str, pd.DataFrame] = {}
    if not ek2c_df.empty:
        for grp in ek2c_df["group"].dropna().unique():
            grp_df = ek2c_df[ek2c_df["group"] == grp]
            if not grp_df.empty:
                ek2c_packages[str(grp)] = grp_df

    ek3_all: list[tuple[str, pd.DataFrame]] = []
    for cat_name in sorted(CURATED_DIR.glob("ek3*_materials.parquet")):
        df = _ek3_material(cat_name.name)
        if df.empty:
            continue
        ek3_all.append((cat_name.name, df))

    active_drugs = ek4a_df[
        ek4a_df["passivation_date"].isna() |
        (ek4a_df["passivation_date"].astype(str).isin(["", "nan", "None"]))
    ] if not ek4a_df.empty else ek4a_df

    ek2b_procs: dict[str, pd.DataFrame] = {}
    if not ek2b_df.empty:
        ek2b_df["code_str"] = ek2b_df["code"].astype(str)
        ek2b_procs["general"] = ek2b_df[
            ~ek2b_df["code_str"].str.startswith("L1") &
            ~ek2b_df["code_str"].str.startswith("P")
        ]
        ek2b_procs["lab"] = ek2b_df[ek2b_df["code_str"].str.startswith("L1")]
        ek2b_procs["yatak"] = ek2b_df[ek2b_df["name"].str.contains("yatak", case=False, na=False)]
        ek2b_procs["muayene"] = ek2b_df[
            ek2b_df["name"].str.contains("muayene", case=False, na=False) |
            ek2b_df["name"].str.contains("konsültasyon", case=False, na=False)
        ]

    claims: list[dict] = []
    procedure_rows: list[dict] = []
    performed_rows: list[dict] = []
    medula_rejection_rows: list[dict] = []
    materials: list[dict] = []
    drug_claims: list[dict] = []
    expected: list[dict] = []
    lab_billing_budget: dict[tuple[str, str], dict[str, Any]] = {}

    for ep_idx, episode in enumerate(episodes):
        pid = episode["hasta_id"]
        eid = episode["basvuru_id"]
        visit_type = episode["gelis_tipi"]
        override_demo = episode.get("_sgk_optional_override_demo")
        blood_demo = episode.get("_sgk_blood_uplift_demo")
        drg_demo = episode.get("_sgk_drg_uplift_demo")
        material_demo = episode.get("_sgk_material_uplift_demo")
        care_setting_demo = episode.get("_sgk_care_setting_review_demo")
        procedure_addon_demo = episode.get("_sgk_procedure_addon_demo")
        procedure_capture_demo = episode.get("_sgk_procedure_capture_demo")
        package_adequacy_demo = episode.get("_sgk_package_adequacy_demo")
        gazette_repricing_demo = episode.get("_sgk_gazette_repricing_demo")
        medula_playbook_demo = episode.get("_sgk_medula_playbook_demo")
        medula_demo_spec = (
            _MEDULA_DEMO_SPECS.get(pid.rsplit("-", 1)[-1])
            if medula_playbook_demo
            else None
        )
        session_uplift_demo = episode.get("_sgk_session_uplift_demo")
        drug_indication_demo = episode.get("_sgk_drug_indication_demo")
        material_prose_demo = episode.get("_sgk_material_prose_demo")
        claim_readiness_demo = episode.get("_sgk_claim_readiness_demo")
        payment_method_compliance_demo = episode.get("_payment_method_compliance_demo")
        drug_indication_spec = (
            _DRUG_INDICATION_DEMO_SPECS.get(str(drug_indication_demo))
            if drug_indication_demo
            else None
        )
        material_prose_spec = (
            _MATERIAL_PROSE_DEMO_SPECS.get(str(material_prose_demo))
            if material_prose_demo
            else None
        )
        claim_readiness_spec = (
            _CLAIM_READINESS_DEMO_SPECS.get(str(claim_readiness_demo))
            if claim_readiness_demo
            else None
        )
        scenario_tag = (
            PAYMENT_METHOD_COMPLIANCE_DEMO_TAG
            if payment_method_compliance_demo
            else medula_demo_spec["scenario_tag"]
            if medula_demo_spec
            else drug_indication_spec["scenario_tag"]
            if drug_indication_spec
            else material_prose_spec["scenario_tag"]
            if material_prose_spec
            else claim_readiness_spec["scenario_tag"]
            if claim_readiness_spec
            else "sgk_session_uplift_cerrahi"
            if session_uplift_demo
            else "sgk_gazette_repricing_600150"
            if gazette_repricing_demo
            else "sgk_package_adequacy_undercoded"
            if package_adequacy_demo
            else "sgk_procedure_capture_kolonoskopi"
            if procedure_capture_demo
            else "sgk_procedure_addon_kolonoskopi"
            if procedure_addon_demo
            else "sgk_care_setting_review_gunubirlik"
            if care_setting_demo
            else "sgk_blood_uplift_yatis"
            if blood_demo
            else "sgk_material_uplift_yatis"
            if material_demo
            else "sgk_drg_uplift_yatis"
            if drg_demo
            else f"sgk_optional_override_{override_demo}"
            if override_demo
            else f"{episode.get('_template', {}).get('specialty', 'genel')}_{visit_type}"
        )
        template = episode.get("_template", {})
        all_codes = episode.get("_all_codes", [])

        claim_id = f"F-{pid}-{(ep_idx + 1):03d}"

        is_university = bool(
            override_demo
            or blood_demo
            or drg_demo
            or material_demo
            or care_setting_demo
            or procedure_addon_demo
            or procedure_capture_demo
            or package_adequacy_demo
            or gazette_repricing_demo
            or medula_playbook_demo
            or session_uplift_demo
            or drug_indication_demo
            or material_prose_demo
            or claim_readiness_demo
        ) or rng.random() < 0.15
        if payment_method_compliance_demo:
            facility_tier = "2_basamak_kamu"
            provider = "Kamu"
            is_university = False
        else:
            facility_tier = (
                "egitim_arastirma"
                if is_university
                else rng.choice(["2_3_basamak_ozel", "2_basamak_kamu"])
            )
            provider = "Universite" if is_university else rng.choice(["Ozel", "Kamu"])

        start_date = episode["basvuru_tarihi"]
        if visit_type == "yatis":
            start_dt = dt.date.fromisoformat(start_date)
            los = int(rng.integers(1, 22))
            discharge_dt = start_dt + dt.timedelta(days=los)
            admission = start_date
            discharge = discharge_dt.isoformat()
            claim_end = discharge
        elif care_setting_demo or visit_type == "gunubirlik":
            admission = start_date
            discharge = start_date
            claim_end = start_date
        else:
            admission = None
            discharge = None
            claim_end = start_date

        if blood_demo:
            proc_specs = _pick_blood_uplift_demo_procedures(
                episode,
                ek2b_procs=ek2b_procs,
                ek2c_packages=ek2c_packages,
                rng=rng,
            )
        elif material_demo:
            proc_specs = _pick_material_uplift_demo_procedures(
                episode,
                ek2b_procs=ek2b_procs,
                ek2c_packages=ek2c_packages,
                rng=rng,
            )
        elif care_setting_demo:
            proc_specs = _pick_care_setting_review_demo_procedures(
                episode,
                ek2b_procs=ek2b_procs,
                ek2c_packages=ek2c_packages,
                rng=rng,
            )
        elif gazette_repricing_demo:
            proc_specs = _pick_gazette_repricing_demo_procedures(
                episode,
                ek2b_procs=ek2b_procs,
                ek2c_packages=ek2c_packages,
                rng=rng,
            )
        elif package_adequacy_demo:
            proc_specs = _pick_package_adequacy_demo_procedures(
                episode,
                ek2b_procs=ek2b_procs,
                ek2c_packages=ek2c_packages,
                rng=rng,
            )
        elif procedure_capture_demo:
            proc_specs = _pick_procedure_capture_demo_procedures(
                episode,
                ek2b_procs=ek2b_procs,
                ek2c_packages=ek2c_packages,
                rng=rng,
            )
        elif procedure_addon_demo:
            proc_specs = _pick_procedure_addon_demo_procedures(
                episode,
                ek2b_procs=ek2b_procs,
                ek2c_packages=ek2c_packages,
                rng=rng,
            )
        elif session_uplift_demo:
            proc_specs = _pick_session_uplift_demo_procedures(
                episode,
                ek2b_procs=ek2b_procs,
                ek2c_packages=ek2c_packages,
                rng=rng,
            )
        elif drg_demo:
            proc_specs = _pick_drg_uplift_demo_procedures(
                episode,
                ek2b_procs=ek2b_procs,
                ek2c_packages=ek2c_packages,
                rng=rng,
            )
        elif payment_method_compliance_demo:
            proc_specs = _pick_payment_method_compliance_demo_procedures(
                episode,
                ek2b_procs=ek2b_procs,
                ek2c_packages=ek2c_packages,
                rng=rng,
            )
        elif override_demo:
            proc_specs = _pick_optional_override_demo_procedures(
                episode,
                ek2b_procs=ek2b_procs,
                ek2c_packages=ek2c_packages,
                rng=rng,
            )
        else:
            n_procs = rng.integers(3, 9)
            proc_specs = _pick_procedures(
                episode,
                n_procs,
                ek2b_procs=ek2b_procs,
                ek2c_packages=ek2c_packages,
                rng=rng,
                facility_tier=facility_tier,
                provider_type=provider,
                allow_mandatory_side_procs=False,
            )

        package_code_for_claim = None
        for ps in proc_specs:
            if ps.get("is_package"):
                package_code_for_claim = ps["code"]
                break
            if ps.get("candidate_package_code"):
                package_code_for_claim = str(ps["candidate_package_code"])

        # DRG uplift demo keeps package lines but package_candidate=False so strategy defers.
        package_candidate = package_code_for_claim is not None and (
            not drg_demo or package_adequacy_demo or override_demo
        )

        ctx = ClaimEpisodeContext(
            pid=pid,
            eid=eid,
            visit_type=visit_type,
            claim_id=claim_id,
            start_date=start_date,
            scenario_tag=scenario_tag,
            facility_tier=facility_tier,
            is_university=is_university,
            provider=provider,
            admission=admission,
            discharge=discharge,
            claim_end=claim_end,
            package_candidate=package_candidate,
            package_code_for_claim=package_code_for_claim,
            all_codes=all_codes,
            template=template,
            ek2g_no_surcharge=ek2g_no_surcharge,
            ek2c1_copay_rates=ek2c1_copay_rates,
            ek3_all=ek3_all,
            active_drugs=active_drugs,
            rng=rng,
            procedure_rows=procedure_rows,
            materials=materials,
            drug_claims=drug_claims,
            expected=expected,
            lab_billing_budget=lab_billing_budget,
            proc_specs=proc_specs,
        )

        proc_billed, proc_payable = _append_procedure_lines_for_claim(ctx)
        if procedure_capture_demo:
            addon_name, _addon_price = _lookup_ek2b_price("701460", ek2b_procs)
            performed_rows.append({
                "gerceklestirilen_satir_id": f"EMR-{claim_id}-001",
                "fatura_id": claim_id,
                "hasta_id": pid,
                "basvuru_id": eid,
                "hizmet_tarihi": start_date,
                "islem_kodu": "701460",
                "islem_adi": addon_name,
                "kaynak": "emr",
            })
        if medula_demo_spec:
            claim_proc_rows = [
                row for row in procedure_rows if row["fatura_id"] == claim_id
            ]
            first_proc = claim_proc_rows[0] if claim_proc_rows else None
            medula_rejection_rows.append({
                "medula_red_satir_id": f"MEDULA-{claim_id}-001",
                "fatura_id": claim_id,
                "hasta_id": pid,
                "basvuru_id": eid,
                "medula_asamasi": medula_demo_spec["medula_asamasi"],
                "sonuc_kodu": medula_demo_spec["sonuc_kodu"],
                "hata_kodu": medula_demo_spec["hata_kodu"],
                "hata_mesaji": medula_demo_spec["hata_mesaji"],
                "red_zamani": start_date,
                "ilgili_islem_kodu": first_proc["islem_kodu"] if first_proc else "",
                "ilgili_islem_satiri_id": (
                    first_proc["islem_satiri_id"] if first_proc else ""
                ),
            })
        if material_demo or override_demo:
            mat_billed, mat_payable = 0.0, 0.0
        elif material_prose_spec or claim_readiness_spec:
            mat_billed, mat_payable = _append_material_prose_demo_line(
                ctx,
                material_prose_spec or claim_readiness_spec or {},
            )
        else:
            mat_billed, mat_payable = _append_material_lines_for_claim(ctx)
        if override_demo:
            drug_billed, drug_payable = 0.0, 0.0
        else:
            drug_billed, drug_payable = _append_drug_lines_for_claim(ctx)
        if drug_indication_spec:
            d_line_id = f"ILC-{claim_id}-IND-001"
            prescription_id = f"REC-{claim_id}-IND-001"
            unit_price = 12500.0
            qty = 1
            billed = _money(unit_price * qty)
            payable = _money(billed * 0.72)
            drug_row: dict[str, Any] = {
                "ilac_satiri_id": d_line_id,
                "recete_id": prescription_id,
                "fatura_id": claim_id,
                "hasta_id": pid,
                "basvuru_id": eid,
                "ilac_fatura_tarihi": start_date,
                "ilac_adi": drug_indication_spec["ilac_adi"],
                "ilac_kodu": drug_indication_spec["ilac_kodu"],
                "barkod": drug_indication_spec["barkod"],
                "esdeger_grup": drug_indication_spec["esdeger_grup"],
                "adet": qty,
                "birim_fiyat_try": unit_price,
                "fatura_tutari_try": billed,
                "beklenen_odenebilir_tutar_try": payable,
                "beklenen_indirim_kademesi": 0.28,
                "beklenen_red_nedeni": drug_indication_spec["beklenen_red_nedeni"],
                "beklenen_kural_izi": drug_indication_spec["beklenen_kural_izi"],
                "uzmanlik_kurulu_raporu_var": drug_indication_spec["uzmanlik_kurulu_raporu_var"],
                **_empty_drug_indication_fields(),
            }
            drug_row["uzmanlik_kurulu_raporu_var"] = drug_indication_spec["uzmanlik_kurulu_raporu_var"]
            for optional_key in ("rapor_suresi_ay", "yatarak_tedavi_ilac", "recete_eden_uzmanlik"):
                if optional_key in drug_indication_spec:
                    drug_row[optional_key] = drug_indication_spec[optional_key]
            ctx.drug_claims.append(drug_row)
            ctx.expected.append({
                "beklenen_cikti_id": f"BEK-{d_line_id}",
                "senaryo_etiketi": drug_indication_spec["scenario_tag"],
                "hasta_id": pid,
                "fatura_id": claim_id,
                "satir_id": d_line_id,
                "satir_tipi": "ilac",
                "kural_ailesi": "drug_indication",
                "beklenen_durum": (
                    drug_indication_spec["beklenen_kural_izi"].split(":")[-1]
                    if drug_indication_spec.get("beklenen_kural_izi")
                    else "odenebilir"
                ),
                "beklenen_odenebilir_tutar_try": payable,
                "beklenen_tasarruf_try": _money(billed - payable),
                "beklenen_red_nedeni": drug_indication_spec["beklenen_red_nedeni"],
                "beklenen_kural_izi": drug_indication_spec["beklenen_kural_izi"],
                "test_notu": "§4.2 drug indication demo drug line",
            })
            drug_billed += billed
            drug_payable += payable

        total_billed = proc_billed + mat_billed + drug_billed
        total_payable = proc_payable + mat_payable + drug_payable
        total_billed = max(total_billed, 0.01)
        total_payable = max(total_payable, 0.0)
        total_billed = _money(total_billed)
        total_payable = _money(total_payable)

        occupational_context = "none"
        if visit_type in ("is_kazasi", "meslek_hastaligi"):
            occupational_context = visit_type

        claims.append({
            "fatura_id": claim_id,
            "hasta_id": pid,
            "basvuru_id": eid,
            "fatura_tipi": visit_type,
            "mesleki_kontekst": occupational_context,
            "kurum_basamagi": facility_tier,
            "saglayici_tipi": provider,
            "servis_adi": episode["servis_adi"],
            "yatis_tarihi": admission,
            "taburcu_tarihi": discharge,
            "fatura_baslangic_tarihi": start_date,
            "fatura_bitis_tarihi": claim_end,
            "birincil_icd10": all_codes[0] if all_codes else "",
            "paket_adayi_mi": package_candidate,
            "beklenen_toplam_fatura_tutari_try": _money(total_billed),
            "beklenen_toplam_odenebilir_tutar_try": _money(total_payable),
            "beklenen_red_nedeni": "Kismi paket ici satir reddi" if total_payable < total_billed else "",
            "senaryo_etiketi": scenario_tag,
        })

        expected.append({
            "beklenen_cikti_id": f"BEK-{claim_id}",
            "senaryo_etiketi": scenario_tag,
            "hasta_id": pid,
            "fatura_id": claim_id,
            "satir_id": "",
            "satir_tipi": "fatura",
            "kural_ailesi": "fatura_dogrulama",
            "beklenen_durum": "kismi_red" if total_payable < total_billed else "odenebilir",
            "beklenen_odenebilir_tutar_try": _money(total_payable),
            "beklenen_tasarruf_try": _money(total_billed - total_payable),
            "beklenen_red_nedeni": "Paket ici satirlar reddedilir" if total_payable < total_billed else "",
            "beklenen_kural_izi": scenario_tag,
            "test_notu": "Fatura duzeyi sentetik beklenen cikti",
        })

    return (
        claims,
        procedure_rows,
        performed_rows,
        medula_rejection_rows,
        materials,
        drug_claims,
        expected,
        lab_billing_budget,
    )


# ── Prescription generation ──────────────────────────────────────────
def _generate_prescriptions(drug_claim_rows: list[dict], patients: list[dict]) -> list[dict]:
    prescriptions = []
    pid_to_kohort = {p["hasta_id"]: p["kohort"] for p in patients}
    for drug in drug_claim_rows:
        prescriptions.append({
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
            "kohort": pid_to_kohort.get(drug["hasta_id"], "checkup"),
            "donem": "2024",
        })
    return prescriptions


# ── Lab result generation ────────────────────────────────────────────
def _generate_lab_results(
    episodes: list[dict],
    lab_billing_budget: dict[tuple[str, str], dict],
    rng: np.random.Generator,
) -> list[dict]:
    lab_rows: list[dict] = []
    for episode in episodes:
        eid = episode["basvuru_id"]
        pid = episode["hasta_id"]
        kohort = episode["kohort"]

        for (budget_eid, code), budget in lab_billing_budget.items():
            if budget_eid != eid:
                continue
            qty = int(budget.get("kalan_adet", 0))
            test_name = budget.get("test_adi", code)
            total_reps = max(int(qty) + 2, 4)
            for rep in range(total_reps):
                ref_low = round(rng.uniform(0.0, 5.0), 2)
                ref_high = round(rng.uniform(10.0, 200.0), 2)
                value = round(rng.uniform(ref_low * 0.5, ref_high * 1.5), 2)
                abnormal = value < ref_low or value > ref_high
                is_billed = rep < int(qty)

                lab_rows.append({
                    "hasta_id": pid,
                    "basvuru_id": eid,
                    "test_tarihi": episode["basvuru_tarihi"],
                    "laboratuvar_kodu": code,
                    "laboratuvar_adi": test_name,
                    "sayisal_sonuc": value,
                    "nitel_sonuc": "Pozitif" if abnormal and rng.random() < 0.3 else "",
                    "birim": rng.choice(["mg/dL", "mm/h", "/mm3", "U/L", "g/dL", "mEq/L"]),
                    "referans_alt": ref_low,
                    "referans_ust": ref_high,
                    "anormal_mi": abnormal,
                    "organ_sistemi": rng.choice([
                        "Hematoloji", "Biyokimya", "Endokrinoloji",
                        "Mikrobiyoloji", "Seroloji", "Onkoloji",
                    ]),
                    "kohort": kohort,
                    "donem": "2024",
                    "faturalama_durumu": "faturalandirildi" if is_billed else "klinik_kanit_faturalandirilmadi",
                    "islem_satiri_id": budget.get("islem_satiri_id", "") if is_billed else "",
                })
    return lab_rows


# ── Main build orchestrator ──────────────────────────────────────────
def build_workbook_tables(
    num_patients: int = 50,
    min_claims_per_patient: int = 1,
    max_claims_per_patient: int = 5,
    seed: int = 20260504,
) -> dict[str, pd.DataFrame]:
    rng = np.random.default_rng(seed)

    patients = _generate_patients(num_patients, rng)
    episodes, diagnosis_rows = _assign_scenarios(patients, rng)

    patient_episodes: dict[str, list] = defaultdict(list)
    patient_scenarios: dict[str, set] = defaultdict(set)
    for ep in episodes:
        patient_episodes[ep["hasta_id"]].append(ep)
        patient_scenarios[ep["hasta_id"]].add(
            ep.get("_template", {}).get("specialty", "genel")
        )
    for p in patients:
        pid = p["hasta_id"]
        n_eps = len(patient_episodes.get(pid, []))
        p["hasta_toplam_gelis_sayisi"] = n_eps
        p["ana_senaryo"] = ",".join(sorted(patient_scenarios.get(pid, {"genel"})))

    (
        claims,
        procedure_rows,
        performed_rows,
        medula_rejection_rows,
        materials,
        drug_claims,
        expected,
        lab_billing_budget,
    ) = _generate_claims_and_lines(episodes, rng)
    _ensure_prose_flag_coverage(materials)
    _ensure_specialty_flag_coverage(materials)
    _inject_specialty_keyword_demo_rows(materials, claims)
    ek2c1_copay_rates = _build_normalized_ek2c1_copay_rates(_ek2c1())
    _reconcile_ek2c1_procedure_lines(procedure_rows, ek2c1_copay_rates)
    _ensure_ek2c1_violation_demos(procedure_rows, ek2c1_copay_rates)
    _reconcile_claim_header_totals(
        claims, procedure_rows, materials, drug_claims, expected
    )

    prescriptions = _generate_prescriptions(drug_claims, patients)
    lab_rows = _generate_lab_results(episodes, lab_billing_budget, rng)

    for ep in episodes:
        pid = ep["hasta_id"]
        n_eps = len(patient_episodes.get(pid, []))
        ep["hasta_toplam_gelis_sayisi"] = n_eps

    scenario_tags = sorted({c["senaryo_etiketi"] for c in claims})
    manifest = pd.DataFrame([{
        "veri_seti_id": f"sentetik_sut_v2_{num_patients}_hasta",
        "versiyon": "2.0.0",
        "olusturulma_zamani": dt.datetime.now(dt.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "rastgelelik_tohumu": seed,
        "hasta_sayisi": len(patients),
        "basvuru_sayisi": len(episodes),
        "islem_satiri_sayisi": len(procedure_rows),
        "ilac_satiri_sayisi": len(drug_claims),
        "malzeme_satiri_sayisi": len(materials),
        "laboratuvar_sonucu_sayisi": len(lab_rows),
        "senaryo_etiketleri": ",".join(scenario_tags[:50]),
        "sentetik_uyari": SYNTHETIC_NOTICE,
    }])

    copay_profiles = [
        {
            "hasta_id": p["hasta_id"],
            "sgk_yararlanma_sinifi": p.get("sgk_yararlanma_sinifi", "standard"),
            "gazi_sehit_durumu": p.get("gazi_sehit_durumu", "none"),
            "vatani_hizmet_durumu": p.get("vatani_hizmet_durumu", "none"),
            "yasli_aylik_2022": bool(p.get("yasli_aylik_2022", False)),
            "dogum_yili": int(p.get("dogum_yili") or 1970),
        }
        for p in patients
    ]

    return {
        "veri_seti_manifestosu": manifest,
        "hastalar": pd.DataFrame(patients),
        "hasta_katilim_payi_profilleri": pd.DataFrame(copay_profiles),
        "basvurular": pd.DataFrame(episodes),
        "tani_satirlari": pd.DataFrame(diagnosis_rows),
        "fatura_basliklari": pd.DataFrame(claims),
        "islem_fatura_satirlari": pd.DataFrame(procedure_rows),
        "gerceklestirilen_islem_satirlari": pd.DataFrame(performed_rows),
        "medula_red_satirlari": pd.DataFrame(medula_rejection_rows),
        "malzeme_fatura_satirlari": pd.DataFrame(materials),
        "ilac_fatura_satirlari": pd.DataFrame(_ensure_drug_indication_columns(drug_claims)),
        "receteler": pd.DataFrame(prescriptions),
        "laboratuvar_sonuclari": pd.DataFrame(lab_rows),
        "beklenen_kural_ciktilari": pd.DataFrame(expected),
        "katalog_alt_kumesi": pd.DataFrame(),
    }
