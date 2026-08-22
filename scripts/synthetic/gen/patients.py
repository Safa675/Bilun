"""Patient and episode generation."""

from __future__ import annotations

from typing import Any

import numpy as np

from constants import ICD10_CHAPTER_TO_DRG_GROUP, SCENARIO_TEMPLATES, TURKISH_FEMALE_NAMES, TURKISH_MALE_NAMES, TURKISH_SURNAMES
from catalog import _ek1a
from demo_config import vignette_for_patient_id
from fault_injection import apply_vignette_episode_defaults
from gen.specs import _MEDULA_DEMO_SPECS

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
        if i == 35:
            sgk_class = "yesil_kart"
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
            "SENTETIK-HASTA-0034",
            "SENTETIK-HASTA-0035",
            "SENTETIK-HASTA-0036",
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
            elif pid == "SENTETIK-HASTA-0034" and ep_idx == 0:
                episode_row["gelis_tipi"] = "acil"
                episode_row["_copay_exemption_demo"] = "acil_servis"
                episode_row["servis_adi"] = "acil_servis"
            elif pid == "SENTETIK-HASTA-0035" and ep_idx == 0:
                episode_row["gelis_tipi"] = "poliklinik"
                episode_row["_copay_exemption_demo"] = "yesil_kart"
            elif pid == "SENTETIK-HASTA-0036" and ep_idx == 0:
                episode_row["gelis_tipi"] = "poliklinik"
                episode_row["birincil_icd10"] = "E11.9"
                episode_row["tum_icd10_kodlari"] = "E11.9"
                episode_row["_all_codes"] = ["E11.9"]
                episode_row["_copay_exemption_demo"] = "ek1a_chronic"
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
def _drg_group(icd10_codes: list[str]) -> str:
    for code in icd10_codes:
        ch = code[0].upper() if code and code[0].isalpha() else "Z"
        if ch in ICD10_CHAPTER_TO_DRG_GROUP:
            return ICD10_CHAPTER_TO_DRG_GROUP[ch]
    return "C"
