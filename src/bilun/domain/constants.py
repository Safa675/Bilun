"""
src/bilun/domain/constants.py
Paths, code mappings, and runtime policy for the SUT engine.

No dependencies on other src.sut modules.
"""

from __future__ import annotations

from pathlib import Path

# ═══════════════════════════════════════════════════════════════════════════
# Paths
# ═══════════════════════════════════════════════════════════════════════════

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
_DATA_DIR = _PROJECT_ROOT / "data"
_GAZETTE_DIR = _DATA_DIR / "gazette"
_GAZETTE_CURATED_DIR = _GAZETTE_DIR / "curated"
_PROSE_RULES_DIR = _GAZETTE_DIR / "prose_rules"
PROSE_MANIFESTS_DIR = _GAZETTE_DIR / "prose_manifests"

# SUT prose corpus — extracted clauses + rule-coverage matrix (rule database)
SUT_CLAUSES_PATH = _GAZETTE_DIR / "sut_clauses.parquet"
SUT_CLAUSE_COVERAGE_PATH = _GAZETTE_DIR / "sut_clause_coverage.parquet"
SUT_REGISTRY_COVERAGE_PATH = _GAZETTE_DIR / "sut_registry_coverage.parquet"
SUT_COVERAGE_BY_RULE_PATH = _GAZETTE_DIR / "sut_coverage_by_rule.parquet"
SUT_COVERAGE_BY_SECTION_PATH = _GAZETTE_DIR / "sut_coverage_by_section.parquet"

# SUT clause embeddings — sidecar vectors for semantic clause retrieval (chatbot)
SUT_CLAUSE_EMBEDDINGS_PATH = _GAZETTE_DIR / "sut_clause_embeddings.parquet"

# SUT puan → TL coefficient history (authoritative; not check-up package data)
KATSAYI_HISTORY_PATH = _GAZETTE_DIR / "sut_katsayi_history.json"
DEFAULT_KATSAYI = 0.593

# New primary data sources (compiled from 72 gazette documents)
EK2B_CURATED_HISTORY_PATH = _GAZETTE_CURATED_DIR / "ek2b_catalog_history.parquet"
EK2C_CURATED_HISTORY_PATH = _GAZETTE_CURATED_DIR / "ek2c_catalog_history.parquet"

# EK-2Ç dental procedures (same puan/price structure as EK-2B, 40xxxx codes).
# Built by scripts/sut/build_curated_catalogs.py from the EK-2Ç annex family
# once the Turkish-character regex in convert_xlsx_to_parquet.py routes the
# dental workbook into annex=EK-2Ç (previously mis-bucketed as "EK-2").
EK2C_DENTAL_CURATED_HISTORY_PATH = (
    _GAZETTE_CURATED_DIR / "ek2c_dental_catalog_history.parquet"
)


def _resolve_latest_dental_xls() -> Path | None:
    """Dynamically resolve the EK-2Ç dental .xls from the latest SUT folder.

    Searches ``raw data/<latest>-Değişiklik Tebliği.../EK-2 LİSTELERİ/`` for
    a file matching ``EK-2Ç DİŞ TEDAVİLERİ PUAN LİSTESİ*.xls``. Uses rglob to
    handle SGK zip nesting variations.
    """
    import re as _re

    _SUT_SUFFIX = "Değişiklik Tebliği İşlenmiş Güncel 2013 SUT"
    _DATE_RE = _re.compile(r"^(\d{4})\.(\d{2})\.(\d{2})-")
    raw_root = _PROJECT_ROOT / "raw data"
    if not raw_root.exists():
        return None
    candidates: list[tuple[str, Path]] = []
    for entry in raw_root.iterdir():
        if not entry.is_dir() or not entry.name.endswith(_SUT_SUFFIX):
            continue
        m = _DATE_RE.match(entry.name)
        if m:
            candidates.append((f"{m.group(1)}-{m.group(2)}-{m.group(3)}", entry))
    if not candidates:
        return None
    candidates.sort(key=lambda x: x[0])
    latest_dir = candidates[-1][1]
    # rglob handles nested-folder zips from SGK
    for p in latest_dir.rglob("EK-2Ç*.xls"):
        return p
    for p in latest_dir.rglob("*DİŞ*TEDAVİLERİ*.xls"):
        return p
    return None


# Fallback: the original .xls when the curated parquet has not been built yet.
# Resolved dynamically from the latest SUT folder (no hardcoded date).
_EK2C_DENTAL_XLS_FALLBACK: Path | None = _resolve_latest_dental_xls()

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

# EK-4/D — copay-exempt drugs by disease (from SUT .doc annex)
EK4D_SECTIONS_PATH = _GAZETTE_CURATED_DIR / "ek4d_sections.parquet"
EK4D_ENTRIES_PATH = _GAZETTE_CURATED_DIR / "ek4d_copay_exempt_entries.parquet"

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


# Runtime policy: when True, all billing surfaces require SUT claim lines.
# Missing claim context returns explicit "missing_exact_inputs" instead of
# falling back to ICD-chapter heuristics, medians, or hardcoded defaults.
SUT_REQUIRE_CLAIM_LINES = True
