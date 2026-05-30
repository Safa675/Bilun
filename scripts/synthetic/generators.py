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

            episodes_out.append({
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
            })

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
) -> list[dict]:
    procs = []
    visit_type = episode["gelis_tipi"]
    template = episode.get("_template", {})
    all_codes = episode.get("_all_codes", [])
    drg_grp = _drg_group(all_codes)

    if not ek2b_procs.get("muayene", pd.DataFrame()).empty:
        exam_pool = ek2b_procs["muayene"]
        exam_valid = exam_pool[exam_pool["ISLEM_BEDELI_TL"].notna() & (exam_pool["ISLEM_BEDELI_TL"] > 0)]
        if not exam_valid.empty:
            row = exam_valid.sample(1, random_state=rng.bit_generator).iloc[0]
            procs.append({
                "code": str(row["ISLEM_KODU"]),
                "name": str(row["ISLEM_ADI"]),
                "price": _money(float(row.get("ISLEM_BEDELI_TL", 0) or 0)),
                "category": "muayene",
            })

    if visit_type == "yatis" and not ek2b_procs.get("yatak", pd.DataFrame()).empty:
        bed_pool = ek2b_procs["yatak"]
        bed_valid = bed_pool[bed_pool["ISLEM_BEDELI_TL"].notna() & (bed_pool["ISLEM_BEDELI_TL"] > 0)]
        if not bed_valid.empty:
            row = bed_valid.sample(1, random_state=rng.bit_generator).iloc[0]
            days = int(rng.integers(1, 21))
            procs.append({
                "code": str(row["ISLEM_KODU"]),
                "name": str(row["ISLEM_ADI"]),
                "price": _money(float(row.get("ISLEM_BEDELI_TL", 0) or 0)),
                "category": "yatak",
                "quantity_override": days,
            })

    n_labs = int(rng.integers(1, 4))
    lab_pool = ek2b_procs.get("lab", pd.DataFrame())
    if not lab_pool.empty:
        lab_pool_valid = lab_pool[
            lab_pool["ISLEM_BEDELI_TL"].notna() &
            (lab_pool["ISLEM_BEDELI_TL"] > 0)
        ]
        if not lab_pool_valid.empty:
            n_sample = min(n_labs, len(lab_pool_valid))
            lab_sample = lab_pool_valid.sample(n_sample, random_state=rng.bit_generator)
            for _, row in lab_sample.iterrows():
                procs.append({
                    "code": str(row["ISLEM_KODU"]),
                    "name": str(row["ISLEM_ADI"]),
                    "price": _money(float(row.get("ISLEM_BEDELI_TL", 0) or 0)),
                    "category": "laboratuvar",
                })

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

    remaining = num_procs - len(procs) - (1 if package_code else 0)
    general_pool = ek2b_procs.get("general", pd.DataFrame())
    if remaining > 0 and not general_pool.empty:
        gen_valid = general_pool[
            general_pool["ISLEM_BEDELI_TL"].notna() &
            (general_pool["ISLEM_BEDELI_TL"] > 0)
        ]
        if not gen_valid.empty:
            n_sample = min(remaining, len(gen_valid))
            sample = gen_valid.sample(n_sample, random_state=rng.bit_generator)
            for _, row in sample.iterrows():
                included_in_pkg = False
                if package_code:
                    included_in_pkg = rng.random() < 0.45
                procs.append({
                    "code": str(row["ISLEM_KODU"]),
                    "name": str(row["ISLEM_ADI"]),
                    "price": _money(float(row.get("ISLEM_BEDELI_TL", 0) or 0)),
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


# ── Per-claim line builders ──────────────────────────────────────────
def _append_procedure_lines_for_claim(
    ctx: ClaimEpisodeContext,
) -> tuple[float, float]:
    total_billed = 0.0
    total_payable = 0.0

    for line_idx, ps in enumerate(ctx.proc_specs, start=1):
        is_package_proc = (ps["category"] == "paket")
        qty = int(ps.get("quantity_override", 1))
        unit_price = ps["price"]
        billed = _money(unit_price * qty)

        included_in_package = ps.get("included_in_package", False)

        if included_in_package:
            base_payable = 0.0
        elif is_package_proc:
            base_payable = billed
        else:
            base_payable = billed

        surcharge_applicable = ps["code"] not in ctx.ek2g_no_surcharge
        surcharge_rate = None
        if surcharge_applicable and not is_package_proc:
            if ctx.is_university:
                surcharge_rate = round(ctx.rng.uniform(0.90, 1.00), 2) if ctx.rng.random() < 0.8 else None
            else:
                surcharge_rate = round(float(ctx.rng.choice([0.20, 0.30, 0.50, 0.75, 1.00])), 2)

        copay_applicable = ps["code"] in ctx.ek2c1_copay_rates
        copay_rate = ctx.ek2c1_copay_rates.get(ps["code"]) if copay_applicable else None
        if not copay_applicable and ctx.visit_type in ("poliklinik", "gunubirlik") and not is_package_proc:
            copay_applicable = True
            copay_rate = float(ctx.rng.choice([0.20, 0.40, 0.50]))

        expected_payable = base_payable
        if surcharge_rate and surcharge_applicable:
            expected_payable = _money(expected_payable * (1 + surcharge_rate))
        if copay_rate and copay_applicable:
            expected_payable = _money(expected_payable * (1 - copay_rate))

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
            "paket_kodu": ctx.package_code_for_claim if (included_in_package or is_package_proc) else None,
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

    return total_billed, total_payable


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
            "beklenen_red_nedeni": "",
            "beklenen_kural_izi": f"EK-4A:{drug_row.get('kamu_no', '')}",
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
) -> tuple[list[dict], list[dict], list[dict], list[dict], list[dict], dict[tuple, dict]]:
    ek2b_df = _ek2b()
    ek2c_df = _ek2c_latest()
    ek2c1_df = _ek2c1()
    ek2g_df = _ek2g()
    ek4a_df = _ek4a()

    ek2g_no_surcharge: set[str] = set()
    if not ek2g_df.empty:
        ek2g_no_surcharge = set(ek2g_df["procedure_code"].astype(str).tolist())

    ek2c1_copay_rates: dict[str, float] = {}
    if not ek2c1_df.empty:
        for _, row in ek2c1_df.iterrows():
            ek2c1_copay_rates[str(row["procedure_code"])] = float(row["copay_rate_pct"]) / 100.0

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
        ek2b_df["code_str"] = ek2b_df["ISLEM_KODU"].astype(str)
        ek2b_procs["general"] = ek2b_df[
            ~ek2b_df["code_str"].str.startswith("L1") &
            ~ek2b_df["code_str"].str.startswith("P")
        ]
        ek2b_procs["lab"] = ek2b_df[ek2b_df["code_str"].str.startswith("L1")]
        ek2b_procs["yatak"] = ek2b_df[ek2b_df["ISLEM_ADI"].str.contains("yatak", case=False, na=False)]
        ek2b_procs["muayene"] = ek2b_df[
            ek2b_df["ISLEM_ADI"].str.contains("muayene", case=False, na=False) |
            ek2b_df["ISLEM_ADI"].str.contains("konsültasyon", case=False, na=False)
        ]

    claims: list[dict] = []
    procedure_rows: list[dict] = []
    materials: list[dict] = []
    drug_claims: list[dict] = []
    expected: list[dict] = []
    lab_billing_budget: dict[tuple[str, str], dict[str, Any]] = {}

    for ep_idx, episode in enumerate(episodes):
        pid = episode["hasta_id"]
        eid = episode["basvuru_id"]
        visit_type = episode["gelis_tipi"]
        scenario_tag = f"{episode.get('_template', {}).get('specialty', 'genel')}_{visit_type}"
        template = episode.get("_template", {})
        all_codes = episode.get("_all_codes", [])

        claim_id = f"F-{pid}-{(ep_idx + 1):03d}"

        is_university = rng.random() < 0.15
        facility_tier = "3_basamak" if is_university else rng.choice(["2_3_basamak_ozel", "2_basamak_kamu"])
        provider = "Universite" if is_university else rng.choice(["Ozel", "Kamu"])

        start_date = episode["basvuru_tarihi"]
        if visit_type == "yatis":
            start_dt = dt.date.fromisoformat(start_date)
            los = int(rng.integers(1, 22))
            discharge_dt = start_dt + dt.timedelta(days=los)
            admission = start_date
            discharge = discharge_dt.isoformat()
            claim_end = discharge
        else:
            admission = None
            discharge = None
            claim_end = start_date

        package_candidate = visit_type in ("yatis", "gunubirlik") and rng.random() < 0.5

        n_procs = rng.integers(3, 9)
        proc_specs = _pick_procedures(
            episode,
            n_procs,
            ek2b_procs=ek2b_procs,
            ek2c_packages=ek2c_packages,
            rng=rng,
        )

        package_code_for_claim = None
        for ps in proc_specs:
            if ps.get("is_package"):
                package_code_for_claim = ps["code"]
                break

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
        mat_billed, mat_payable = _append_material_lines_for_claim(ctx)
        drug_billed, drug_payable = _append_drug_lines_for_claim(ctx)

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
            "paket_adayi_mi": package_code_for_claim is not None,
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

    return claims, procedure_rows, materials, drug_claims, expected, lab_billing_budget


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

    claims, procedure_rows, materials, drug_claims, expected, lab_billing_budget = (
        _generate_claims_and_lines(episodes, rng)
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
        "malzeme_fatura_satirlari": pd.DataFrame(materials),
        "ilac_fatura_satirlari": pd.DataFrame(drug_claims),
        "receteler": pd.DataFrame(prescriptions),
        "laboratuvar_sonuclari": pd.DataFrame(lab_rows),
        "beklenen_kural_ciktilari": pd.DataFrame(expected),
        "katalog_alt_kumesi": pd.DataFrame(),
    }
