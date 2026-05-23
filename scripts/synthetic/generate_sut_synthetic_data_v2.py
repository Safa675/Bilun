#!/usr/bin/env python3
"""Generate the v2 SUT synthetic reimbursement dataset.

Parameterized, scalable generator producing claim data that exercises all
BILUN reimbursement surfaces: billing (lab, drug, copay, materials), alerts
(surcharge, copay rates), optimizer per-row data, and DRG pricing.

Outputs:
    data/synthetic/sut/sentetik_sut_v2.xlsx
    data/synthetic/sut/clean/*.parquet
    data/synthetic/sut/claims/*.parquet
"""

from __future__ import annotations

import argparse
import datetime as dt
import random
from collections import defaultdict
from pathlib import Path
from typing import Any

import pandas as pd
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "data" / "synthetic" / "sut"
GAZETTE_DIR = PROJECT_ROOT / "data" / "gazette"
CURATED_DIR = GAZETTE_DIR / "curated"
EK2B_PATH = GAZETTE_DIR / "ek2b_islem_puan_listesi.parquet"

SYNTHETIC_NOTICE = (
    "Bu veri seti tamamen sentetiktir; gercek hasta, gercek kurum veya gercek "
    "fatura verisi icermez."
)

SEED = 20260504

# ── ICD-10 Chapter → DRG group mapping ───────────────────────────────
ICD10_CHAPTER_TO_DRG_GROUP: dict[str, str] = {
    "I": "A3", "C": "A3", "J": "B", "K": "B", "G": "A3", "E": "C",
    "M": "B", "N": "B", "L": "D", "F": "D", "H": "C", "R": "D",
    "Z": "E", "A": "C", "B": "C", "D": "B", "O": "B", "P": "B",
    "Q": "A3", "S": "B", "T": "B", "U": "C", "V": "C", "W": "C",
    "X": "C", "Y": "C",
}

# ── Medical specialty scenarios ──────────────────────────────────────
# Each scenario maps to: (primary_icd10_choices, secondary_icd10_choices,
#   visit_type_distribution, department, ek3_material_catalogs)
SCENARIO_TEMPLATES = [
    {   # Cardiology
        "specialty": "cardiology",
        "primary_codes": ["I10", "I25.1", "I48", "I50.0", "I21.4", "I20.9", "I11.0", "I63.9"],
        "secondary_codes": ["E78.0", "E11.9", "I10", "Z95.1", "N18.9"],
        "visit_types": ["poliklinik", "poliklinik", "yatis", "gunubirlik"],
        "departments": ["Kardiyoloji", "Kardiyoloji"],
        "material_catalogs": [],
    },
    {   # Orthopedics
        "specialty": "orthopedics",
        "primary_codes": ["M17.9", "M16.1", "M75.1", "S72.0", "M51.1", "M54.5", "M23.2", "M77.1"],
        "secondary_codes": ["Z96.6", "E11.9", "I10", "M81.9", "E78.0"],
        "visit_types": ["poliklinik", "yatis", "yatis", "gunubirlik"],
        "departments": ["Ortopedi ve Travmatoloji", "Ortopedi ve Travmatoloji"],
        "material_catalogs": ["ek3c2_materials.parquet", "ek3f1_arthroplasty_materials.parquet"],
    },
    {   # Oncology
        "specialty": "oncology",
        "primary_codes": ["C34.9", "C50.9", "C18.9", "C61", "C92.0", "C82.9", "C83.1", "C90.0"],
        "secondary_codes": ["D61.9", "Z51.1", "R53", "E11.9", "I10"],
        "visit_types": ["poliklinik", "yatis", "yatis", "gunubirlik"],
        "departments": ["Onkoloji", "Hematoloji"],
        "material_catalogs": ["ek3o_hematology_oncology_materials.parquet"],
    },
    {   # Endocrinology
        "specialty": "endocrinology",
        "primary_codes": ["E11.9", "E03.9", "E05.0", "E78.0", "E66.9", "E11.4", "E10.9", "E02"],
        "secondary_codes": ["I10", "E78.0", "N18.3", "H25.9", "G63.2"],
        "visit_types": ["poliklinik", "poliklinik", "poliklinik", "yatis"],
        "departments": ["Endokrinoloji", "Ic Hastaliklari"],
        "material_catalogs": [],
    },
    {   # Gastroenterology
        "specialty": "gastroenterology",
        "primary_codes": ["K29.7", "K63.5", "K21.0", "K80.2", "K57.3", "K70.3", "K50.9", "K85.9"],
        "secondary_codes": ["E11.9", "I10", "K76.0", "Z90.4", "E78.0"],
        "visit_types": ["poliklinik", "gunubirlik", "yatis", "gunubirlik"],
        "departments": ["Gastroenteroloji", "Gastroenteroloji"],
        "material_catalogs": ["ek3r_gastroenterology_materials.parquet"],
    },
    {   # Pulmonology
        "specialty": "pulmonology",
        "primary_codes": ["J44.9", "J45.0", "J18.9", "J15.4", "J96.0", "J84.1", "J81", "J47"],
        "secondary_codes": ["I10", "E11.9", "J00", "R05", "D86.0"],
        "visit_types": ["poliklinik", "yatis", "yatis", "gunubirlik"],
        "departments": ["Gogus Hastaliklari", "Gogus Hastaliklari"],
        "material_catalogs": ["ek3s_pulmonology_materials.parquet"],
    },
    {   # Neurology
        "specialty": "neurology",
        "primary_codes": ["G40.9", "G20", "G35", "I63.9", "G43.9", "G47.3", "G61.0", "G12.2"],
        "secondary_codes": ["I10", "E11.9", "F32.9", "R51", "G96.9"],
        "visit_types": ["poliklinik", "poliklinik", "yatis", "yatis"],
        "departments": ["Noroloji", "Noroloji"],
        "material_catalogs": [],
    },
    {   # Nephrology
        "specialty": "nephrology",
        "primary_codes": ["N18.9", "N17.9", "N03.9", "N20.0", "N40", "N18.3", "I12.0", "N10"],
        "secondary_codes": ["E11.9", "I10", "E78.0", "D50.9", "M81.9"],
        "visit_types": ["poliklinik", "yatis", "yatis", "gunubirlik"],
        "departments": ["Nefroloji", "Ic Hastaliklari"],
        "material_catalogs": ["ek3p_nephrology_materials.parquet"],
    },
]

# ── Turkish demographics ────────────────────────────────────────────
TURKISH_FEMALE_NAMES = [
    "Ayse", "Fatma", "Emine", "Zeynep", "Meryem", "Havva", "Hatice", "Elif",
    "Derya", "Sibel", "Aylin", "Berna", "Canan", "Dilek", "Esra", "Funda",
    "Gül", "Hande", "Irem", "Jale", "Kubra", "Leyla", "Meltem", "Nazan",
    "Oya", "Pinar", "Rukiye", "Sevda", "Tugba", "Yasemin",
]
TURKISH_MALE_NAMES = [
    "Mehmet", "Mustafa", "Ahmet", "Ali", "Huseyin", "Hasan", "Ibrahim",
    "Ismail", "Yusuf", "Murat", "Osman", "Suleyman", "Kemal", "Omer",
    "Burak", "Cem", "Deniz", "Emre", "Faruk", "Gokhan", "Hakan",
    "Ilker", "Kadir", "Levent", "Mert", "Nihat", "Onur", "Serkan",
    "Tarik", "Volkan",
]
TURKISH_SURNAMES = [
    "Yilmaz", "Kaya", "Demir", "Celik", "Sahin", "Yildiz", "Yildirim",
    "Ozturk", "Aydin", "Ozdemir", "Arslan", "Dogan", "Kilic", "Aslan",
    "Cetin", "Kara", "Koc", "Kurt", "Ozkan", "Simsek", "Polat", "Ozcan",
    "Korkmaz", "Cakir", "Erdogan", "Yavuz", "Tekin", "Aksoy", "Bulut",
]

# ── Gazette catalog loading (cached) ────────────────────────────────
_GAZETTE_CACHE: dict[str, pd.DataFrame] = {}

def _gazette(name: str, path: Path) -> pd.DataFrame:
    if name in _GAZETTE_CACHE:
        return _GAZETTE_CACHE[name]
    if not path.exists():
        df = pd.DataFrame()
    else:
        df = pd.read_parquet(path)
    _GAZETTE_CACHE[name] = df
    return df

def _ek2b() -> pd.DataFrame:
    return _gazette("ek2b", EK2B_PATH)

def _ek2c_latest() -> pd.DataFrame:
    df = _gazette("ek2c", CURATED_DIR / "ek2c_catalog_history.parquet")
    if df.empty:
        return df
    work = df.copy()
    work["effective_date_dt"] = pd.to_datetime(work["effective_date"], errors="coerce")
    return work.sort_values("effective_date_dt").drop_duplicates(
        subset=["package_code"], keep="last"
    )

def _ek2c1() -> pd.DataFrame:
    return _gazette("ek2c1", CURATED_DIR / "ek2c1_copay_rates.parquet")

def _ek2g() -> pd.DataFrame:
    return _gazette("ek2g", CURATED_DIR / "ek2g_no_surcharge.parquet")

def _ek4a() -> pd.DataFrame:
    return _gazette("ek4a", CURATED_DIR / "ek4a_drugs.parquet")

def _ek3_material(catalog_filename: str) -> pd.DataFrame:
    key = f"ek3_{catalog_filename}"
    return _gazette(key, CURATED_DIR / catalog_filename)

def _ek1a() -> pd.DataFrame:
    return _gazette("ek1a", CURATED_DIR / "ek1a_chronic_exemptions.parquet")


def _money(value: float) -> float:
    return round(float(value), 2)


# ── Price generation for drugs (EK-4A has no price columns) ──────────
def _drug_unit_price(drug_row: pd.Series, rng: np.random.Generator) -> float:
    """Generate a realistic drug unit price in TRY based on discount tier/status."""
    tier_raw = drug_row.get("discount_tier_1")
    try:
        tier = float(tier_raw) if tier_raw is not None else 0.28
    except (ValueError, TypeError):
        tier = 0.28
    status = str(drug_row.get("discount_status", ""))
    base = rng.uniform(20.0, 500.0)
    if "KAN" in status.upper():
        base = rng.uniform(300.0, 3000.0)
    elif tier >= 0.4:
        base = rng.uniform(15.0, 150.0)
    elif tier >= 0.28:
        base = rng.uniform(25.0, 350.0)
    return _money(base)


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
        patients.append({
            "hasta_id": f"SENTETIK-HASTA-{i:04d}",
            "cinsiyet": sex,
            "dogum_yili": birth_year,
            "kohort": rng.choice(["checkup", "ex", "merged", "cancer", "chronic"]),
            "kayit_tarihi": record_date,
            "ana_senaryo": "",
            "veri_tamlik_yuzdesi": int(rng.integers(80, 99)),
            "sentetik_profil_notu": f"{name} {surname} - sentetik profil",
        })
    return patients


# ── Scenario assignment ──────────────────────────────────────────────
def _assign_scenarios(patients: list[dict], rng: np.random.Generator) -> list[dict]:
    """Assign each patient 1-5 episodes with randomly selected specialties."""
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

            visit_type = rng.choice(template["visit_types"])
            department = rng.choice(template["departments"])

            visit_year = rng.integers(2023, 2025)
            visit_month = rng.integers(1, 13)
            visit_day = rng.integers(1, 29)
            visit_date = f"{visit_year}-{visit_month:02d}-{visit_day:02d}"
            age = int(visit_date[:4]) - birth_year

            eid = f"B-{pid}-{(ep_idx + 1):03d}"

            # Vital signs with realistic ranges
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
                # Additional fields for claim generation
                "_template": template,
                "_all_codes": all_codes,
            })

            for line_no, code in enumerate(all_codes, start=1):
                chapter = code[0].upper() if code else "Z"
                exemption = False
                if not _ek1a().empty:
                    ek1a_df = _ek1a()
                    for _, row in ek1a_df.iterrows():
                        icd_range = str(row.get("icd10_range", ""))
                        if icd_range and code.startswith(icd_range.split("-")[0][:3]):
                            exemption = True
                            break
                if not exemption:
                    exemption = code.startswith(("E11", "C92", "I10", "E10", "B20"))

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


# ── Claim generation ─────────────────────────────────────────────────
def _generate_claims_and_lines(
    episodes: list[dict],
    rng: np.random.Generator,
) -> tuple[list[dict], list[dict], list[dict], list[dict], list[dict], dict[tuple, dict]]:
    """Generate claims, procedures, materials, drugs, expected outputs, lab budgets."""

    ek2b_df = _ek2b()
    ek2c_df = _ek2c_latest()
    ek2c1_df = _ek2c1()
    ek2g_df = _ek2g()
    ek4a_df = _ek4a()

    # Build lookup sets
    ek2g_no_surcharge: set[str] = set()
    if not ek2g_df.empty:
        ek2g_no_surcharge = set(ek2g_df["procedure_code"].astype(str).tolist())

    ek2c1_copay_rates: dict[str, float] = {}
    if not ek2c1_df.empty:
        for _, row in ek2c1_df.iterrows():
            ek2c1_copay_rates[str(row["procedure_code"])] = float(row["copay_rate_pct"]) / 100.0

    # Latest EK-2C packages by group, indexed
    ek2c_packages: dict[str, pd.DataFrame] = {}
    if not ek2c_df.empty:
        for grp in ek2c_df["group"].dropna().unique():
            grp_df = ek2c_df[ek2c_df["group"] == grp]
            if not grp_df.empty:
                ek2c_packages[str(grp)] = grp_df

    # EK-3 materials: load all non-empty catalogs
    ek3_all: list[tuple[str, pd.DataFrame]] = []
    ek3_empty_catalogs: set[str] = set()
    for cat_name in sorted(CURATED_DIR.glob("ek3*_materials.parquet")):
        df = _ek3_material(cat_name.name)
        if df.empty:
            ek3_empty_catalogs.add(cat_name.name)
            continue
        ek3_all.append((cat_name.name, df))

    # Drug index
    active_drugs = ek4a_df[
        ek4a_df["passivation_date"].isna() |
        (ek4a_df["passivation_date"].astype(str).isin(["", "nan", "None"]))
    ] if not ek4a_df.empty else ek4a_df

    claims = []
    procedure_rows = []
    materials = []
    drug_claims = []
    expected = []
    lab_billing_budget: dict[tuple[str, str], dict[str, Any]] = {}

    # ICD10 chapter to DRG group for package selection
    def _drg_group(icd10_codes: list[str]) -> str:
        for code in icd10_codes:
            ch = code[0].upper() if code and code[0].isalpha() else "Z"
            if ch in ICD10_CHAPTER_TO_DRG_GROUP:
                return ICD10_CHAPTER_TO_DRG_GROUP[ch]
        return "C"

    # --- EK-2B procedure cache by category ---
    ek2b_procs: dict[str, pd.DataFrame] = {}
    if not ek2b_df.empty:
        ek2b_df["code_str"] = ek2b_df["ISLEM_KODU"].astype(str)
        # Non-lab, non-package procedures
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

    def _pick_procedures(episode: dict, num_procs: int) -> list[dict]:
        """Pick realistic procedures for an episode."""
        procs = []
        visit_type = episode["gelis_tipi"]
        template = episode.get("_template", {})
        all_codes = episode.get("_all_codes", [])
        drg_grp = _drg_group(all_codes)

        # Always include an examination/consultation
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

        # For inpatient: add bed
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

        # Lab tests
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

        # Decide if package candidate — pick EK-2C package from matching DRG group
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

        # Add generic procedures (before package to decide bundling)
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

        # Add package as a procedure line (EK-2C package codes ARE billable procedures)
        if package_code:
            procs.append({
                "code": package_code,
                "name": package_name or package_code,
                "price": package_price,
                "category": "paket",
                "is_package": True,
            })

        return procs

    # --- Generate claims ---
    for ep_idx, episode in enumerate(episodes):
        pid = episode["hasta_id"]
        eid = episode["basvuru_id"]
        visit_type = episode["gelis_tipi"]
        scenario_tag = f"{episode.get('_template', {}).get('specialty', 'genel')}_{visit_type}"
        template = episode.get("_template", {})
        all_codes = episode.get("_all_codes", [])

        claim_id = f"F-{pid}-{(ep_idx + 1):03d}"

        # Facility tier
        is_university = rng.random() < 0.15
        facility_tier = "3_basamak" if is_university else rng.choice(["2_3_basamak_ozel", "2_basamak_kamu"])
        provider = "Universite" if is_university else rng.choice(["Ozel", "Kamu"])

        # Admission/discharge dates
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

        # Package candidate
        package_candidate = visit_type in ("yatis", "gunubirlik") and rng.random() < 0.5

        # Pick procedures
        n_procs = rng.integers(3, 9)
        proc_specs = _pick_procedures(episode, n_procs)

        # Determine package code for the claim
        package_code_for_claim = None
        for ps in proc_specs:
            if ps.get("is_package"):
                package_code_for_claim = ps["code"]
                break

        total_billed = 0.0
        total_payable = 0.0

        for line_idx, ps in enumerate(proc_specs, start=1):
            is_package_proc = (ps["category"] == "paket")
            qty = int(ps.get("quantity_override", 1))
            unit_price = ps["price"]
            billed = _money(unit_price * qty)

            included_in_package = ps.get("included_in_package", False)

            # Compute base payable
            if included_in_package:
                base_payable = 0.0
            elif is_package_proc:
                base_payable = billed
            else:
                base_payable = billed

            # Surcharge: True by default unless code in EK-2G prohibited list
            surcharge_applicable = ps["code"] not in ek2g_no_surcharge
            surcharge_rate = None
            if surcharge_applicable and not is_package_proc:
                if is_university:
                    surcharge_rate = round(rng.uniform(0.90, 1.00), 2) if rng.random() < 0.8 else None
                else:
                    surcharge_rate = round(float(rng.choice([0.20, 0.30, 0.50, 0.75, 1.00])), 2)

            # Copay rate: True if in EK-2C-1, OR if outpatient claim (general copay)
            copay_applicable = ps["code"] in ek2c1_copay_rates
            copay_rate = ek2c1_copay_rates.get(ps["code"]) if copay_applicable else None
            if not copay_applicable and visit_type in ("poliklinik", "gunubirlik") and not is_package_proc:
                # Outpatient and day-surgery non-package procedures have general copay
                copay_applicable = True
                copay_rate = float(rng.choice([0.20, 0.40, 0.50]))

            # Expected payable with surcharge/copay adjustments
            expected_payable = base_payable
            if surcharge_rate and surcharge_applicable:
                expected_payable = _money(expected_payable * (1 + surcharge_rate))
            if copay_rate and copay_applicable:
                expected_payable = _money(expected_payable * (1 - copay_rate))

            denial_reason = ""
            if included_in_package:
                denial_reason = "Paket ici islem ayrica odenmez"

            line_id = f"ISL-{claim_id}-{line_idx:03d}"
            procedure_rows.append({
                "islem_satiri_id": line_id,
                "fatura_id": claim_id,
                "hasta_id": pid,
                "basvuru_id": eid,
                "islem_tarihi": start_date,
                "islem_kodu": ps["code"],
                "islem_adi": ps["name"],
                "islem_kategorisi": ps["category"],
                "adet": qty,
                "birim_fiyat_try": unit_price,
                "fatura_tutari_try": billed,
                "beklenen_odenebilir_tutar_try": expected_payable,
                "pakete_dahil_mi": included_in_package,
                "paket_kodu": package_code_for_claim if (included_in_package or is_package_proc) else None,
                "ilave_ucret_uygulanabilir_mi": surcharge_applicable,
                "ilave_ucret_orani": surcharge_rate,
                "katilim_payi_orani_uygulanabilir_mi": copay_applicable,
                "katilim_payi_orani": copay_rate,
                "beklenen_red_nedeni": denial_reason,
                "beklenen_kural_izi": f"EK-2B:{ps['code']}" if not is_package_proc else f"EK-2C:{ps['code']}",
            })

            if ps["category"] == "laboratuvar":
                lab_billing_budget[(eid, ps["code"])] = {
                    "islem_satiri_id": line_id,
                    "kalan_adet": qty,
                    "test_adi": ps["name"],
                }

            if included_in_package:
                expected.append({
                    "beklenen_cikti_id": f"BEK-{line_id}",
                    "senaryo_etiketi": scenario_tag,
                    "hasta_id": pid,
                    "fatura_id": claim_id,
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

        # Materials: only for yatis/gunubirlik, from matching EK-3 catalogs
        material_catalogs = template.get("material_catalogs", [])
        if material_catalogs and visit_type in ("yatis", "gunubirlik") and ek3_all:
            n_materials = rng.integers(1, 5)
            for mat_idx in range(n_materials):
                cat_name = rng.choice(material_catalogs)
                cat_df = next((df for name, df in ek3_all if cat_name in name), None)
                if cat_df is None or cat_df.empty:
                    continue
                # Filter to rows with valid prices and codes
                valid = cat_df[
                    cat_df["price_try"].notna() &
                    (cat_df["price_try"] > 0) &
                    cat_df["sut_code"].notna()
                ]
                if valid.empty:
                    continue
                row = valid.sample(1, random_state=rng.bit_generator).iloc[0]

                bundled = package_code_for_claim is not None and rng.random() < 0.55
                mat_billed = _money(float(row.get("price_try", 0) or 0))
                mat_payable = 0.0 if bundled else mat_billed
                pre_auth = rng.random() < 0.5

                m_line_id = f"MLZ-{claim_id}-{(mat_idx + 1):03d}"
                materials.append({
                    "malzeme_satiri_id": m_line_id,
                    "fatura_id": claim_id,
                    "islem_satiri_id": f"ISL-{claim_id}-{(mat_idx % max(1, len(proc_specs))) + 1:03d}",
                    "hasta_id": pid,
                    "malzeme_tarihi": start_date,
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
                    expected.append({
                        "beklenen_cikti_id": f"BEK-{m_line_id}",
                        "senaryo_etiketi": scenario_tag,
                        "hasta_id": pid,
                        "fatura_id": claim_id,
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

        # Drugs
        n_drugs = rng.integers(1, 5)
        if n_drugs > 0 and not active_drugs.empty:
            drug_sample = active_drugs.sample(n_drugs, random_state=rng.bit_generator)
            for drug_idx, (_, drug_row) in enumerate(drug_sample.iterrows(), start=1):
                unit_price = _drug_unit_price(drug_row, rng)
                qty = int(rng.integers(1, 4))
                billed = _money(unit_price * qty)
                tier_raw = drug_row.get("discount_tier_1")
                try:
                    discount_tier = float(tier_raw) if tier_raw is not None else 0.28
                except (ValueError, TypeError):
                    discount_tier = 0.28
                payable = _money(billed * (1 - discount_tier))

                d_line_id = f"ILC-{claim_id}-{drug_idx:03d}"
                prescription_id = f"REC-{claim_id}-{drug_idx:03d}"
                drug_claims.append({
                    "ilac_satiri_id": d_line_id,
                    "recete_id": prescription_id,
                    "fatura_id": claim_id,
                    "hasta_id": pid,
                    "basvuru_id": eid,
                    "ilac_fatura_tarihi": start_date,
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
                expected.append({
                    "beklenen_cikti_id": f"BEK-{d_line_id}",
                    "senaryo_etiketi": scenario_tag,
                    "hasta_id": pid,
                    "fatura_id": claim_id,
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

        # Claim-level record
        total_billed = max(total_billed, 0.01)
        total_payable = max(total_payable, 0.0)
        total_billed = _money(total_billed)
        total_payable = _money(total_payable)
        claims.append({
            "fatura_id": claim_id,
            "hasta_id": pid,
            "basvuru_id": eid,
            "fatura_tipi": visit_type,
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

        # Claim-level expected output
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
    """Generate lab results for ALL lab procedures, billed and unbilled."""
    lab_rows = []
    for episode in episodes:
        eid = episode["basvuru_id"]
        pid = episode["hasta_id"]
        kohort = episode["kohort"]

        for (budget_eid, code), budget in lab_billing_budget.items():
            if budget_eid != eid:
                continue
            qty = int(budget.get("kalan_adet", 0))
            test_name = budget.get("test_adi", code)
            # Generate at least 3 reps per test (billed + unbilled)
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


# ── Main build ────────────────────────────────────────────────────────
def build_workbook_tables(
    num_patients: int = 50,
    min_claims_per_patient: int = 1,
    max_claims_per_patient: int = 5,
    seed: int = SEED,
) -> dict[str, pd.DataFrame]:
    rng = np.random.default_rng(seed)

    # Phase 0: Generate patients with assigned scenarios
    patients = _generate_patients(num_patients, rng)
    episodes, diagnosis_rows = _assign_scenarios(patients, rng)

    # Assign per-patient diagnosis summaries back to patients
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

    # Update episode totals
    for ep in episodes:
        pid = ep["hasta_id"]
        n_eps = len(patient_episodes.get(pid, []))
        ep["hasta_toplam_gelis_sayisi"] = n_eps

    # Manifest
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

    return {
        "veri_seti_manifestosu": manifest,
        "hastalar": pd.DataFrame(patients),
        "basvurular": pd.DataFrame(episodes),
        "tani_satirlari": pd.DataFrame(diagnosis_rows),
        "fatura_basliklari": pd.DataFrame(claims),
        "islem_fatura_satirlari": pd.DataFrame(procedure_rows),
        "malzeme_fatura_satirlari": pd.DataFrame(materials),
        "ilac_fatura_satirlari": pd.DataFrame(drug_claims),
        "receteler": pd.DataFrame(prescriptions),
        "laboratuvar_sonuclari": pd.DataFrame(lab_rows),
        "beklenen_kural_ciktilari": pd.DataFrame(expected),
        "katalog_alt_kumesi": pd.DataFrame(),  # empty — catalog subset not needed for v2
    }


# ── Export functions ──────────────────────────────────────────────────
def _normalize_for_parquet(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for col in out.columns:
        if pd.api.types.is_object_dtype(out[col].dtype):
            out[col] = out[col].map(
                lambda x: None if x is None or (isinstance(x, float) and pd.isna(x)) else str(x)
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
    return pd.DataFrame({
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
    })


def _clean_lab(labs: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame({
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
    })


def _clean_recete(receteler: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame({
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
    })


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

    # procedure_claim_lines — add surcharge_rate and copay_rate columns
    proc_df = tables["islem_fatura_satirlari"]
    proc_renamed = proc_df.rename(columns={
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
        "ilave_ucret_orani": "surcharge_rate",
        "katilim_payi_orani_uygulanabilir_mi": "copay_rate_applicable",
        "katilim_payi_orani": "copay_rate",
        "beklenen_red_nedeni": "denial_reason_expected",
        "beklenen_kural_izi": "rule_trace_expected",
    })

    return {
        "claim_headers.parquet": tables["fatura_basliklari"].rename(columns={
            "fatura_id": "claim_id", "hasta_id": "patient_id", "basvuru_id": "episode_id",
            "fatura_tipi": "claim_type", "kurum_basamagi": "facility_tier",
            "saglayici_tipi": "provider_type", "servis_adi": "department",
            "yatis_tarihi": "admission_date", "taburcu_tarihi": "discharge_date",
            "fatura_baslangic_tarihi": "claim_start_date", "fatura_bitis_tarihi": "claim_end_date",
            "birincil_icd10": "primary_icd10", "paket_adayi_mi": "package_candidate",
            "beklenen_toplam_fatura_tutari_try": "expected_total_billed_try",
            "beklenen_toplam_odenebilir_tutar_try": "expected_total_payable_try",
            "beklenen_red_nedeni": "expected_denial_reason",
            "senaryo_etiketi": "scenario_tag",
        }),
        "claim_diagnoses.parquet": diagnosis_claims.rename(columns={
            "tani_satiri_id": "diagnosis_id", "fatura_id": "claim_id",
            "hasta_id": "patient_id", "basvuru_id": "episode_id",
            "icd10_kodu": "icd10_code", "birincil_mi": "is_primary",
            "tani_rolu": "diagnosis_role", "tani_tarihi": "diagnosis_date",
            "ek1a_muafiyet_iliskili_mi": "exemption_eligible",
        }),
        "procedure_claim_lines.parquet": proc_renamed,
        "material_claim_lines.parquet": tables["malzeme_fatura_satirlari"].rename(columns={
            "malzeme_satiri_id": "material_line_id", "fatura_id": "claim_id",
            "islem_satiri_id": "procedure_line_id", "hasta_id": "patient_id",
            "malzeme_tarihi": "material_date", "malzeme_kodu": "material_code",
            "malzeme_adi": "material_name", "malzeme_tipi": "material_type",
            "uzmanlik_kategorisi": "specialty_category", "adet": "quantity",
            "birim_fiyat_try": "unit_price_try", "fatura_tutari_try": "billed_amount_try",
            "beklenen_odenebilir_tutar_try": "expected_payable_try",
            "pakete_dahil_mi": "is_bundled", "on_onay_gerekli_mi": "requires_pre_auth",
            "beklenen_red_nedeni": "denial_reason_expected",
            "beklenen_kural_izi": "rule_trace_expected",
        }),
        "drug_claim_lines.parquet": tables["ilac_fatura_satirlari"].rename(columns={
            "ilac_satiri_id": "drug_claim_line_id", "recete_id": "prescription_id",
            "fatura_id": "claim_id", "hasta_id": "patient_id",
            "basvuru_id": "episode_id", "ilac_fatura_tarihi": "drug_claim_date",
            "ilac_adi": "drug_name", "ilac_kodu": "drug_code",
            "esdeger_grup": "equivalence_group", "adet": "quantity",
            "birim_fiyat_try": "unit_price_try", "fatura_tutari_try": "billed_amount_try",
            "beklenen_odenebilir_tutar_try": "expected_payable_try",
            "beklenen_indirim_kademesi": "discount_tier_expected",
            "beklenen_red_nedeni": "denial_reason_expected",
            "beklenen_kural_izi": "rule_trace_expected",
        }),
        "expected_rule_outputs.parquet": tables["beklenen_kural_ciktilari"].rename(columns={
            "beklenen_cikti_id": "expected_output_id", "senaryo_etiketi": "scenario_tag",
            "hasta_id": "patient_id", "fatura_id": "claim_id",
            "satir_id": "line_id", "satir_tipi": "line_type",
            "kural_ailesi": "rule_family", "beklenen_durum": "expected_status",
            "beklenen_odenebilir_tutar_try": "expected_payable_try",
            "beklenen_tasarruf_try": "expected_savings_try",
            "beklenen_red_nedeni": "expected_denial_reason",
            "beklenen_kural_izi": "expected_rule_trace",
            "test_notu": "assertion_notes",
        }),
    }


def _write_claim_exports(tables: dict[str, pd.DataFrame], output_dir: Path) -> None:
    claims_dir = output_dir / "claims"
    claims_dir.mkdir(parents=True, exist_ok=True)
    for name, df in _english_claim_exports(tables).items():
        _normalize_for_parquet(df).to_parquet(claims_dir / name, index=False)


# ── CLI ───────────────────────────────────────────────────────────────
def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate SUT synthetic v2 data")
    parser.add_argument("--num-patients", type=int, default=50)
    parser.add_argument("--min-claims-per-patient", type=int, default=1)
    parser.add_argument("--max-claims-per-patient", type=int, default=5)
    parser.add_argument("--output-dir", type=str, default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--seed", type=int, default=SEED)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    tables = build_workbook_tables(
        num_patients=args.num_patients,
        min_claims_per_patient=args.min_claims_per_patient,
        max_claims_per_patient=args.max_claims_per_patient,
        seed=args.seed,
    )

    dataset_id = f"sentetik_sut_v2_{args.num_patients}_hasta"
    workbook_path = output_dir / f"{dataset_id}.xlsx"
    _write_workbook(tables, workbook_path)
    _write_clean_exports(tables, output_dir)
    _write_claim_exports(tables, output_dir)

    print("=" * 72)
    print(f"Dataset: {dataset_id}")
    print(f"Workbook: {workbook_path}")
    print(f"Clean exports: {output_dir / 'clean'}")
    print(f"Claim exports: {output_dir / 'claims'}")
    print(f"Patients: {len(tables['hastalar'])}")
    print(f"Episodes: {len(tables['basvurular'])}")
    print(f"Claims: {len(tables['fatura_basliklari'])}")
    print(f"Procedure lines: {len(tables['islem_fatura_satirlari'])}")
    print(f"Material lines: {len(tables['malzeme_fatura_satirlari'])}")
    print(f"Drug lines: {len(tables['ilac_fatura_satirlari'])}")
    print(f"Lab rows: {len(tables['laboratuvar_sonuclari'])}")
    print(f"Diagnoses: {len(tables['tani_satirlari'])}")
    print(f"Expected outputs: {len(tables['beklenen_kural_ciktilari'])}")
    print(f"Prescriptions: {len(tables['receteler'])}")
    print("=" * 72)


if __name__ == "__main__":
    main()
