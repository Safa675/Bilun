"""
src/bilun/domain/constants.py
Paths, code mappings, fallback prices, and tier configurations for the SUT engine.

No dependencies on other src.sut modules.
"""

from __future__ import annotations

from pathlib import Path

# ═══════════════════════════════════════════════════════════════════════════
# Paths
# ═══════════════════════════════════════════════════════════════════════════

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
_SUT_DATA_DIR = _PROJECT_ROOT / "sut data"
_DATA_DIR = _PROJECT_ROOT / "data"
_GAZETTE_DIR = _DATA_DIR / "gazette"
_GAZETTE_CURATED_DIR = _GAZETTE_DIR / "curated"
_LEGACY_DIR = _DATA_DIR / "legacy"

# New primary data sources (compiled from 72 gazette documents)
CHECKUP_JSON_PATH = _GAZETTE_DIR / "sut_checkup_pricing.json"
EK2B_PARQUET_PATH = _GAZETTE_DIR / "ek2b_islem_puan_listesi.parquet"
EK2B_CURATED_HISTORY_PATH = _GAZETTE_CURATED_DIR / "ek2b_catalog_history.parquet"
EK2C_CURATED_HISTORY_PATH = _GAZETTE_CURATED_DIR / "ek2c_catalog_history.parquet"

# Curated EK-3B catalogs (material exclusions & bundled consumables)
EK3B2_NON_REIMBURSABLE_PATH = _GAZETTE_CURATED_DIR / "ek3b2_non_reimbursable.parquet"
EK3B1_BUNDLED_PATH = _GAZETTE_CURATED_DIR / "ek3b1_bundled_consumables.parquet"

# Curated EK-3H/3I material pricing (parquet — replaces legacy JSON)
EK3H_PARQUET_PATH = _GAZETTE_CURATED_DIR / "ek3h_cardiology_materials.parquet"
EK3I_PARQUET_PATH = _GAZETTE_CURATED_DIR / "ek3i_cv_surgery_materials.parquet"

# Curated EK-2A outpatient visit pricing (parquet — replaces legacy JSON)
EK2A_PARQUET_PATH = _GAZETTE_CURATED_DIR / "ek2a_outpatient_visits.parquet"

# Curated EK-4A drug reimbursement data
EK4A_PARQUET_PATH = _GAZETTE_CURATED_DIR / "ek4a_drugs.parquet"

# Curated optimization annexes (scripts/sut/catalogs/optimization.py)
EK1A_CURATED_PATH = _GAZETTE_CURATED_DIR / "ek1a_chronic_exemptions.parquet"
EK2G_CURATED_PATH = _GAZETTE_CURATED_DIR / "ek2g_no_surcharge.parquet"
EK2C1_CURATED_PATH = _GAZETTE_CURATED_DIR / "ek2c1_copay_rates.parquet"

# All curated specialty material parquet files (EK-3A through EK-3T)
# Maps annex label -> (parquet filename, human description)
_EK3_SPECIALTY_CATALOGS: dict[str, tuple[str, str]] = {
    "EK-3A": ("ek3a_multibranch_materials.parquet", "Multi-Branch Materials"),
    "EK-3E-1": ("ek3e1_spine_surgery_materials.parquet", "Spine Surgery Materials"),
    "EK-3E-2": ("ek3e2_cranial_surgery_materials.parquet", "Cranial Surgery Materials"),
    "EK-3F-1": ("ek3f1_arthroplasty_materials.parquet", "Arthroplasty Materials"),
    "EK-3F-2": ("ek3f2_arthroscopy_materials.parquet", "Arthroscopy/Joint Surgery"),
    "EK-3F-3": ("ek3f3_tumor_resection_materials.parquet", "Tumor Resection Materials"),
    "EK-3F-4": (
        "ek3f4_trauma_reconstruction_materials.parquet",
        "Trauma/Reconstruction",
    ),
    "EK-3G": ("ek3g_ophthalmology_materials.parquet", "Ophthalmology Materials"),
    "EK-3J": ("ek3j_ent_materials.parquet", "ENT Materials"),
    "EK-3K": ("ek3k_obgyn_materials.parquet", "OB/GYN Materials"),
    "EK-3L": ("ek3l_urology_materials.parquet", "Urology Materials"),
    "EK-3M": ("ek3m_radiology_materials.parquet", "Radiology/Endovascular Materials"),
    "EK-3N-1": ("ek3n1_allograft_materials.parquet", "Allograft Products"),
    "EK-3N-2": ("ek3n2_xenograft_materials.parquet", "Xenograft Products"),
    "EK-3N-3": ("ek3n3_synthetic_graft_materials.parquet", "Synthetic Graft Products"),
    "EK-3O": ("ek3o_hematology_oncology_materials.parquet", "Hematology-Oncology"),
    "EK-3P": ("ek3p_nephrology_materials.parquet", "Nephrology Materials"),
    "EK-3R": ("ek3r_gastroenterology_materials.parquet", "Gastroenterology Materials"),
    "EK-3S": ("ek3s_pulmonology_materials.parquet", "Pulmonology/Thoracic Materials"),
    "EK-3T": ("ek3t_anesthesiology_materials.parquet", "Anesthesiology/Pain Materials"),
    "EK-3D": ("ek3d_vision_materials.parquet", "Vision-Aid Materials"),
    "EK-3C-2": ("ek3c2_materials.parquet", "Prosthetics/Orthotics"),
    "EK-3C-3": ("ek3c3_materials.parquet", "Other Prosthetics"),
    "EK-3C-4": ("ek3c4_materials.parquet", "Medical Consumables"),
    "EK-3C-5": ("ek3c5_materials.parquet", "Special-Case Materials"),
}


# ═══════════════════════════════════════════════════════════════════════════
# BILUN test name -> SUT code mapping  (updated to current L1xxxxx format)
# ═══════════════════════════════════════════════════════════════════════════

BILUN_TO_SUT_CODE: dict[str, str] = {
    # ── Inflammatory panel ────────────────────────────────────────────
    "CRP": "L101840",
    "Prokalsitonin": "L106230",
    # ── Renal panel ───────────────────────────────────────────────────
    "Kreatinin": "L104780",
    "Üre": "L107420",
    "GFR": "L104780",  # Calculated from Creatinine
    # ── Hepatic panel ─────────────────────────────────────────────────
    "ALT": "L100300",
    "AST": "L101280",
    "ALP": "L100710",
    "GGT": "L102780",
    "Albumin": "L100320",
    "Bilirubin": "L101730",
    # ── Hematological panel — all bundled under Hemogram ──────────────
    "Hemoglobin": "L107020",
    "Hematokrit": "L107020",
    "Eritrosit": "L107020",
    "Lökosit": "L107020",
    "Trombosit": "L107020",
    "MCV": "L107020",
    "MCH": "L107020",
    "RDW": "L107020",
    "Nötrofil": "L107020",
    "Lenfosit": "L107020",
    "Monosit": "L107020",
    "Bazofil": "L107020",
    "Eozinofil": "L107020",
    # ── Metabolic panel ───────────────────────────────────────────────
    "Glukoz": "L102890",
    "HbA1c": "L102820",
    "Kolesterol": "L104520",
    "Trigliserid": "L107250",
    "LDL": "L105000",
    "HDL": "L103050",
    "Sodyum": "L106910",
    "Potasyum": "L106150",
    "Kalsiyum": "L103820",
    "Protein": "L107180",
    # ── Endocrine panel ───────────────────────────────────────────────
    "TSH": "L107380",
    "T3": "L106760",
    "T4": "L106770",
    # ── Coagulation panel ─────────────────────────────────────────────
    "PT": "L106290",
    "aPTT": "L100050",
    "INR": "L106290",  # Same as PT (INR calculated from PT)
}

# Old-format code -> new-format code (for backward compatibility lookups)
_OLD_TO_NEW_CODE: dict[str, str] = {
    "900890": "L101840",  # CRP
    "903170": "L106230",  # Prokalsitonin
    "902210": "L104780",  # Kreatinin
    "904100": "L107420",  # Üre
    "900200": "L100300",  # ALT
    "900580": "L101280",  # AST
    "900340": "L100710",  # ALP
    "901390": "L102780",  # GGT
    "900210": "L100320",  # Albümin
    "900690": "L101730",  # Bilirubin
    "901620": "L107020",  # Hemogram
    "901500": "L102890",  # Glukoz
    "901450": "L102820",  # HbA1c
    "902110": "L104520",  # Kolesterol
    "903990": "L107250",  # Trigliserid
    "902290": "L105000",  # LDL
    "901580": "L103050",  # HDL
    "903670": "L106910",  # Sodyum
    "903130": "L106150",  # Potasyum
    "901910": "L103820",  # Kalsiyum
    "904030": "L107380",  # TSH
    "903470": "L106760",  # T3
    "903480": "L106770",  # T4
    "905320": "L106290",  # PT / INR
    "904290": "L100050",  # aPTT
}

# Hemogram bundle: all these BILUN test names map to a SINGLE SUT test (L107020).
HEMOGRAM_TESTS: frozenset[str] = frozenset(
    {
        "Hemoglobin",
        "Hematokrit",
        "Eritrosit",
        "Lökosit",
        "Trombosit",
        "MCV",
        "MCH",
        "RDW",
        "Nötrofil",
        "Lenfosit",
        "Monosit",
        "Bazofil",
        "Eozinofil",
    }
)

# Reverse mapping: SUT code -> BILUN test names
_SUT_CODE_TO_BILUN: dict[str, list[str]] = {}
for _name, _code in BILUN_TO_SUT_CODE.items():
    _SUT_CODE_TO_BILUN.setdefault(_code, []).append(_name)


# ═══════════════════════════════════════════════════════════════════════════
# Fallback prices (used ONLY when gazette catalog fails)
# ═══════════════════════════════════════════════════════════════════════════

_FALLBACK_LAB_PRICES: dict[str, tuple[float, float]] = {
    "CRP": (9.86, 9.86),
    "Lökosit": (19.73, 19.73),
    "Nötrofil": (19.73, 19.73),
    "Lenfosit": (19.73, 19.73),
    "Eozinofil": (19.73, 19.73),
    "Monosit": (19.73, 19.73),
    "Bazofil": (19.73, 19.73),
    "Prokalsitonin": (67.13, 67.13),
    "Kreatinin": (7.20, 7.20),
    "Üre": (7.20, 7.20),
    "GFR": (7.20, 7.20),
    "Bilirubin": (6.57, 6.57),
    "ALT": (7.20, 7.20),
    "AST": (6.57, 6.57),
    "ALP": (7.20, 7.20),
    "GGT": (7.20, 7.20),
    "Hemoglobin": (19.73, 19.73),
    "Hematokrit": (19.73, 19.73),
    "Eritrosit": (19.73, 19.73),
    "Trombosit": (19.73, 19.73),
    "MCV": (19.73, 19.73),
    "MCH": (19.73, 19.73),
    "RDW": (19.73, 19.73),
    "Glukoz": (6.57, 6.57),
    "HbA1c": (26.34, 26.34),
    "Kolesterol": (7.20, 7.20),
    "Trigliserid": (7.90, 7.90),
    "LDL": (16.46, 16.46),
    "HDL": (10.51, 10.51),
    "Sodyum": (7.20, 7.20),
    "Potasyum": (7.20, 7.20),
    "Kalsiyum": (17.09, 17.09),
    "Albumin": (6.57, 6.57),
    "Protein": (7.20, 7.20),
    "TSH": (29.59, 29.59),
    "T3": (29.59, 29.59),
    "T4": (29.59, 29.59),
    "INR": (7.20, 7.20),
    "PT": (7.20, 7.20),
    "aPTT": (7.20, 7.20),
}

_FALLBACK_VISIT_PRICES: dict[str, tuple[float, float]] = {
    "outpatient": (85.73, 85.73),
    "inpatient_day": (222.36, 222.36),
    "icu_day": (742.60, 742.60),
    "emergency": (85.73, 85.73),
    "follow_up": (52.48, 52.48),
}

# Prescription cost tiers
SUT_RX_PRICES: dict[str, tuple[float, float]] = {
    "basic": (10.0, 40.0),
    "moderate": (40.0, 150.0),
    "specialty": (150.0, 800.0),
}
SUT_RX_DEFAULT: tuple[float, float] = (20.0, 80.0)

# Comorbidity-linked procedure cost ranges per episode
SUT_COMORBIDITY_PROCEDURE_COSTS: dict[str, tuple[float, float]] = {
    "Hipertansiyon": (100.0, 500.0),
    "Kalp Damar": (500.0, 5000.0),
    "Diyabet": (200.0, 1000.0),
    "Kan Hastalıkları": (300.0, 2000.0),
    "Kronik Hastalıklar Diğer": (200.0, 1500.0),
    "Ameliyat Geçmişi": (1000.0, 15000.0),
}

# ICD-10 chapter -> estimated procedure cost range
SUT_ICD10_PROCEDURE_COSTS: dict[str, tuple[float, float]] = {
    "I": (500.0, 8000.0),
    "C": (1000.0, 25000.0),
    "J": (200.0, 3000.0),
    "K": (300.0, 5000.0),
    "G": (400.0, 6000.0),
    "E": (150.0, 1500.0),
    "M": (200.0, 4000.0),
    "N": (300.0, 4000.0),
    "L": (100.0, 1000.0),
    "F": (100.0, 800.0),
    "H": (150.0, 2000.0),
    "R": (50.0, 300.0),
    "Z": (50.0, 200.0),
}

# ICD-10 Chapter -> EK-2C Group Mapping
_ICD10_CHAPTER_TO_EK2C_GROUP: dict[str, str] = {
    "I": "A3",
    "C": "A3",
    "J": "B",
    "K": "B",
    "G": "A3",
    "E": "C",
    "M": "B",
    "N": "B",
    "L": "D",
    "F": "D",
    "H": "C",
    "R": "D",
    "Z": "E",
    "A": "C",
    "B": "C",
    "D": "B",
    "O": "B",
    "P": "B",
    "Q": "A3",
    "S": "B",
    "T": "B",
    "U": "C",
    "V": "C",
    "W": "C",
    "X": "C",
    "Y": "C",
}

# ICD-10 chapter descriptions
_ICD10_CHAPTER_DESC: dict[str, str] = {
    "A": "Infectious diseases",
    "B": "Infectious diseases",
    "C": "Neoplasms",
    "D": "Blood/immune disorders",
    "E": "Endocrine/metabolic",
    "F": "Mental/behavioral",
    "G": "Nervous system",
    "H": "Eye/ear",
    "I": "Circulatory system",
    "J": "Respiratory system",
    "K": "Digestive system",
    "L": "Skin/subcutaneous",
    "M": "Musculoskeletal",
    "N": "Genitourinary",
    "O": "Pregnancy/childbirth",
    "P": "Perinatal",
    "Q": "Congenital malformations",
    "R": "Symptoms/signs",
    "S": "Injury",
    "T": "Injury/poisoning",
    "U": "Special purpose",
    "V": "External causes",
    "W": "External causes",
    "X": "External causes",
    "Y": "External causes",
    "Z": "Health encounters",
}

# Cost tier classification thresholds
COST_TIERS: list[tuple[float, str, str]] = [
    (10000, "Very High", "Yüksek maliyet — aktif müdahale beklenir"),
    (5000, "High", "Yüksek — yakın takip ve bütçe planlaması gerekir"),
    (2000, "Moderate", "Orta düzey — rutin bakım maliyeti"),
    (500, "Low", "Düşük — minimal kaynak tüketimi"),
    (0, "Minimal", "Minimal maliyet — koruyucu sağlık hizmeti"),
]

# Hospital actual cost multipliers relative to SUT max prices.
# These are base multipliers; compute_patient_markup() in analytics.py
# adjusts them per patient based on volume, drug tier, visit mix, and
# procedure complexity.
_HOSPITAL_MARKUP: dict[str, float] = {
    "lab": 1.3,
    "visit": 1.5,
    "rx": 1.8,
    "procedure": 2.0,
}

# Default LOS values
_DEFAULT_INPATIENT_LOS = 4.0
_DEFAULT_ICU_LOS = 3.0
_MAX_SINGLE_VISIT_LOS = 90
