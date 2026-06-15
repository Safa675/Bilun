"""Constants and configuration for the SUT synthetic data generator v2."""

from __future__ import annotations

from pathlib import Path

SYNTHETIC_NOTICE = (
    "Bu veri seti tamamen sentetiktir; gercek hasta, gercek kurum veya gercek "
    "fatura verisi icermez."
)

SEED = 20260504

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "data" / "synthetic" / "sut"
GAZETTE_DIR = PROJECT_ROOT / "data" / "gazette"
CURATED_DIR = GAZETTE_DIR / "curated"

# ── ICD-10 Chapter → DRG group mapping ───────────────────────────────
ICD10_CHAPTER_TO_DRG_GROUP: dict[str, str] = {
    "I": "A3", "C": "A3", "J": "B", "K": "B", "G": "A3", "E": "C",
    "M": "B", "N": "B", "L": "D", "F": "D", "H": "C", "R": "D",
    "Z": "E", "A": "C", "B": "C", "D": "B", "O": "B", "P": "B",
    "Q": "A3", "S": "B", "T": "B", "U": "C", "V": "C", "W": "C",
    "X": "C", "Y": "C",
}

# ── Medical specialty scenarios ──────────────────────────────────────
SCENARIO_TEMPLATES: list[dict] = [
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
    "Gul", "Hande", "Irem", "Jale", "Kubra", "Leyla", "Meltem", "Nazan",
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
