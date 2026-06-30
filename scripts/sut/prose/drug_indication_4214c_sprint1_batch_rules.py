"""Sprint 1 — encode remaining §4.2.14.C Tier A/B pending manifest clauses (39 rows)."""

from __future__ import annotations

from typing import Any

from scripts.sut.prose.drug_indication_4214c_batch_rules import _rule

_ONC = ["C00-C97"]
_HEME = ["C00-C97", "D45-D47"]
_RCC = ["C64-C66"]
_CRC = ["C18-C20"]
_HNSCC = ["C00-C14"]
_MESO = ["C45"]
_BCC = ["C44"]
_BRAIN = ["C71"]
_OSTEO = ["C40-C41"]
_GCT = ["C40-C41"]
_CHL = ["C81"]
_TALL = ["C91"]
_TNBC = ["C50"]
_PARATHYROID = ["C75"]
_NET = ["C25"]
_MG = ["G70.0"]
_NMOSD = ["G36.0"]

# Existing rules: append manifest clause IDs only (merge script unions gate_b_sources).
SOURCE_PATCHES: dict[str, list[str]] = {
    "4.2.14.C.alemtuzumab_cll_heme": ["C004938"],
    "4.2.14.C.(3).sorafenib_hcc_rcc_board": ["C005050"],
    "4.2.14.C.(15).afatinib_egfr_nsclc_board": ["C005336", "C005339"],
    "4.2.14.C.ekulizumab_ahus_1mo_nephrology": ["C005400"],
    "4.2.14.C.ekulizumab_ahus_6mo_nephrology": ["C005434"],
    "4.2.14.C.aferez_1mo_heme_board": ["C005355"],
}

SPRINT1_NEW_RULES: list[dict[str, Any]] = [
    _rule(
        "4.2.14.C.imiquimod_bcc_dermatology_board",
        ["imiquimod"],
        icd10_ranges=_BCC,
        report_specialties=["tıbbi onkoloji", "cilt hastalıkları"],
        prescriber_specialties=["tıbbi onkoloji", "cilt hastalıkları"],
        message_tr="İmiquimod — yüzeysel BCC endikasyonu ve onkoloji/dermatoloji sağlık kurulu raporu gerekir (§4.2.14.C).",
        batch="S1A",
    )
    | {"gate_b_sources": ["C004953"]},
    _rule(
        "4.2.14.C.floxuridin_crc_liver_met_board",
        ["floxuridin"],
        icd10_ranges=_CRC,
        report_specialties=["tıbbi onkoloji", "genel cerrahi", "gastroenteroloji"],
        message_tr="Floxuridin — kolon CA karaciğer metastazı endikasyonu ve sağlık kurulu raporu gerekir (§4.2.14.C).",
        batch="S1A",
    )
    | {"gate_b_sources": ["C004974"]},
    _rule(
        "4.2.14.C.pemetrexed_mesothelioma_board",
        ["pemetreksed", "pemetrexed"],
        icd10_ranges=_MESO,
        report_specialties=["tıbbi onkoloji", "göğüs hastalıkları", "genel cerrahi"],
        message_tr="Pemetreksed — malign plevral mezotelyom endikasyonu ve sağlık kurulu raporu gerekir (§4.2.14.C).",
        batch="S1A",
    )
    | {"gate_b_sources": ["C005058"]},
    _rule(
        "4.2.14.C.raltitrexed_mesothelioma_board",
        ["raltitreksed", "raltitrexed"],
        icd10_ranges=_MESO + _CRC,
        report_specialties=["tıbbi onkoloji"],
        message_tr="Raltitreksed — mezotelyom/kolorektal endikasyonu ve sağlık kurulu raporu gerekir (§4.2.14.C).",
        batch="S1A",
    )
    | {"gate_b_sources": ["C005084"]},
    _rule(
        "4.2.14.C.cinacalcet_parathyroid_board",
        ["cinacalcet"],
        icd10_ranges=_PARATHYROID,
        report_specialties=["endokrinoloji", "genel cerrahi", "tıbbi onkoloji"],
        message_tr="Cinacalcet — paratiroid karsinomu endikasyonu ve sağlık kurulu raporu gerekir (§4.2.14.C).",
        batch="S1A",
    )
    | {"gate_b_sources": ["C005100"]},
    _rule(
        "4.2.14.C.trabectedin_sarcoma_board",
        ["trabektedin", "trabectedin"],
        icd10_ranges=["C49"],
        report_specialties=["tıbbi onkoloji"],
        message_tr="Trabektedin — liyomiyosarkom/liposarkom endikasyonu ve sağlık kurulu raporu gerekir (§4.2.14.C).",
        batch="S1A",
    )
    | {"gate_b_sources": ["C005102"]},
    {
        "rule_id": "4.2.14.C.fluorouracil_topical_prescriber_only",
        "sut_section": "4.2.14.C",
        "drug_names": ["fluorourasil", "5-fu topikal", "fluorouracil"],
        "icd10_ranges": _BCC,
        "report_required": False,
        "prescriber_specialties": ["dermatoloji", "tıbbi onkoloji", "plastik cerrahi"],
        "message_tr": "Topikal fluorourasil — yalnızca dermatoloji/onkoloji/plastik cerrahi reçetesi (§4.2.14.C).",
        "encode_batch": "S1A",
        "gate_b_sources": ["C005189"],
    },
    _rule(
        "4.2.14.C.aksitinib_rcc_board",
        ["aksitinib", "axitinib"],
        icd10_ranges=_RCC,
        report_specialties=["tıbbi onkoloji", "üroloji"],
        message_tr="Aksitinib — metastatik RCC endikasyonu ve sağlık kurulu raporu gerekir (§4.2.14.C).",
        batch="S1A",
    )
    | {"gate_b_sources": ["C005177"]},
    _rule(
        "4.2.14.C.cetuximab_crc_board",
        ["setuksimab", "cetuximab"],
        icd10_ranges=_CRC,
        report_specialties=["tıbbi onkoloji"],
        message_tr="Setuksimab — metastatik kolorektal kanser endikasyonu ve sağlık kurulu raporu gerekir (§4.2.14.C).",
        batch="S1A",
    )
    | {"gate_b_sources": ["C005179"]},
    _rule(
        "4.2.14.C.cetuximab_hnscc_board",
        ["setuksimab", "cetuximab"],
        icd10_ranges=_HNSCC,
        report_specialties=["tıbbi onkoloji", "kulak burun boğaz"],
        message_tr="Setuksimab — skuamoz HNSCC endikasyonu ve sağlık kurulu raporu gerekir (§4.2.14.C).",
        batch="S1A",
    )
    | {"gate_b_sources": ["C005184"]},
    _rule(
        "4.2.14.C.carmustine_brain_tumor_board",
        ["karmustin", "carmustine"],
        icd10_ranges=_BRAIN,
        report_specialties=["tıbbi onkoloji", "radyasyon onkolojisi", "nöroloji"],
        message_tr="Karmustin — beyin tümörü endikasyonu ve sağlık kurulu raporu gerekir (§4.2.14.C).",
        batch="S1A",
    )
    | {"gate_b_sources": ["C005243"]},
    _rule(
        "4.2.14.C.mifamurtide_osteosarcoma_board",
        ["mifamurtide"],
        icd10_ranges=_OSTEO,
        report_specialties=["tıbbi onkoloji", "ortopedi"],
        message_tr="Mifamurtide — yüksek riskli osteosarkom endikasyonu ve sağlık kurulu raporu gerekir (§4.2.14.C).",
        batch="S1A",
    )
    | {"gate_b_sources": ["C005302"]},
    _rule(
        "4.2.14.C.brentuximab_hodgkin_board",
        ["brentuksimab", "brentuximab"],
        icd10_ranges=_CHL + _HEME,
        report_specialties=["hematoloji", "tıbbi onkoloji"],
        message_tr="Brentuksimab vedotin — CD30+ lenfoma endikasyonu ve hematoloji/onkoloji raporu gerekir (§4.2.14.C).",
        batch="S1A",
    )
    | {"gate_b_sources": ["C005318", "C005329"]},
    _rule(
        "4.2.14.C.denosumab_giant_cell_tumor_board",
        ["denosumab"],
        icd10_ranges=_GCT,
        report_specialties=["tıbbi onkoloji", "ortopedi"],
        message_tr="Denosumab 120 mg — dev hücreli kemik tümörü endikasyonu ve sağlık kurulu raporu gerekir (§4.2.14.C).",
        batch="S1A",
    )
    | {"gate_b_sources": ["C005358"]},
    _rule(
        "4.2.14.C.eculizumab_mg_neurology_board",
        ["ekulizumab", "eculizumab"],
        icd10_ranges=_MG,
        report_specialties=["nöroloji"],
        prescriber_specialties=["nöroloji"],
        message_tr="Ekulizumab — jeneralize miyastenia gravis endikasyonu ve nöroloji sağlık kurulu raporu gerekir (§4.2.14.C).",
        batch="S1A",
    )
    | {"gate_b_sources": ["C005483", "C005436"]},
    _rule(
        "4.2.14.C.eculizumab_nmosd_neurology_board",
        ["ekulizumab", "eculizumab"],
        icd10_ranges=_NMOSD,
        report_specialties=["nöroloji"],
        prescriber_specialties=["nöroloji"],
        message_tr="Ekulizumab — NMOSB endikasyonu ve nöroloji sağlık kurulu raporu gerekir (§4.2.14.C).",
        batch="S1A",
    )
    | {"gate_b_sources": ["C005454", "C005481", "C005483"]},
    _rule(
        "4.2.14.C.dinutuximab_neuroblastoma_board",
        ["dinutuksimab", "dinutuximab"],
        icd10_ranges=["C74"],
        report_specialties=["tıbbi onkoloji", "pediatrik onkoloji"],
        message_tr="Dinutuksimab beta — yüksek riskli nöroblastom endikasyonu ve sağlık kurulu raporu gerekir (§4.2.14.C).",
        batch="S1A",
    )
    | {"gate_b_sources": ["C005619"]},
    _rule(
        "4.2.14.C.nelarabine_t_all_board",
        ["nelarabin", "nelarabine"],
        icd10_ranges=_TALL,
        report_specialties=["hematoloji", "tıbbi onkoloji"],
        message_tr="Nelarabin — T-ALL/T-LBL endikasyonu ve hematoloji/onkoloji sağlık kurulu raporu gerekir (§4.2.14.C).",
        batch="S1A",
    )
    | {"gate_b_sources": ["C005647"]},
    _rule(
        "4.2.14.C.sacituzumab_govitecan_tnbc_board",
        ["sacituzumab govitekan", "sacituzumab govitecan"],
        icd10_ranges=_TNBC,
        report_specialties=["tıbbi onkoloji"],
        message_tr="Sacituzumab govitekan — metastatik TNBC endikasyonu ve sağlık kurulu raporu gerekir (§4.2.14.C).",
        batch="S1A",
    )
    | {"gate_b_sources": ["C005683"]},
    _rule(
        "4.2.14.C.nivolumab_classical_hodgkin_board",
        ["nivolumab"],
        icd10_ranges=_CHL,
        report_specialties=["hematoloji", "tıbbi onkoloji"],
        message_tr="Nivolumab — nüks/refrakter klasik Hodgkin lenfoma endikasyonu ve sağlık kurulu raporu gerekir (§4.2.14.C).",
        batch="S1A",
    )
    | {"gate_b_sources": ["C005725"]},
    # Tier B — duration / prescriber variants
    _rule(
        "4.2.14.C.azacitidine_mds_4mo_heme",
        ["azasitidin", "azacitidine"],
        icd10_ranges=["D46"],
        report_specialties=["hematoloji"],
        message_tr="Azasitidin — MDS dirençli anemi; 4 ay süreli hematoloji sağlık kurulu raporu gerekir (§4.2.14.C).",
        batch="S1B",
        report_duration_months=4,
        prescriber_specialties=["hematoloji"],
    )
    | {"gate_b_sources": ["C004978"]},
    _rule(
        "4.2.14.C.azacitidine_mds_6mo_heme",
        ["azasitidin", "azacitidine"],
        icd10_ranges=["D46"],
        report_specialties=["hematoloji"],
        message_tr="Azasitidin — MDS dirençli anemi; 6 ay süreli hematoloji sağlık kurulu raporu gerekir (§4.2.14.C).",
        batch="S1B",
        report_duration_months=6,
        prescriber_specialties=["hematoloji"],
    )
    | {"gate_b_sources": ["C004987"]},
    _rule(
        "4.2.14.C.decitabine_mds_4mo_heme",
        ["decitabin", "decitabine"],
        icd10_ranges=["D46"],
        report_specialties=["hematoloji"],
        message_tr="Decitabin — MDS dirençli anemi; 4 ay süreli hematoloji sağlık kurulu raporu gerekir (§4.2.14.C).",
        batch="S1B",
        report_duration_months=4,
        prescriber_specialties=["hematoloji"],
    )
    | {"gate_b_sources": ["C004996"]},
    _rule(
        "4.2.14.C.sunitinib_net_12mo_oncology",
        ["sunitinib"],
        icd10_ranges=_NET,
        report_specialties=["tıbbi onkoloji", "endokrinoloji"],
        message_tr="Sunitinib — NET endikasyonu; 12 ay süreli sağlık kurulu raporu gerekir (§4.2.14.C).",
        batch="S1B",
        report_duration_months=12,
        prescriber_specialties=["tıbbi onkoloji"],
    )
    | {"gate_b_sources": ["C005038"]},
    _rule(
        "4.2.14.C.everolimus_net_12mo_oncology",
        ["everolimus"],
        icd10_ranges=_NET,
        report_specialties=["tıbbi onkoloji", "endokrinoloji"],
        message_tr="Everolimus — NET endikasyonu; 12 ay süreli sağlık kurulu raporu gerekir (§4.2.14.C).",
        batch="S1B",
        report_duration_months=12,
        prescriber_specialties=["tıbbi onkoloji"],
    )
    | {"gate_b_sources": ["C005087"]},
    _rule(
        "4.2.14.C.eculizumab_pediatric_mg_neurology",
        ["ekulizumab", "eculizumab"],
        icd10_ranges=_MG,
        report_specialties=["nöroloji", "pediatrik nöroloji"],
        message_tr="Ekulizumab — pediatrik jeneralize miyastenia gravis; nöroloji sağlık kurulu raporu gerekir (§4.2.14.C).",
        batch="S1B",
        prescriber_specialties=["nöroloji"],
    )
    | {"gate_b_sources": ["C005482"]},
    _rule(
        "4.2.14.C.eculizumab_mg_12wk_adult_neurology",
        ["ekulizumab", "eculizumab"],
        icd10_ranges=_MG,
        report_specialties=["nöroloji"],
        message_tr="Ekulizumab — yetişkin MG; 12 haftalık ilaç kullanım süresi raporda doğrulanmalı (§4.2.14.C).",
        batch="S1B",
        report_duration_months=3,
        prescriber_specialties=["nöroloji"],
    )
    | {"gate_b_sources": ["C005481"]},
    _rule(
        "4.2.14.C.ribociclib_nsai_combo_breast",
        ["ribosiklib", "ribociclib"],
        icd10_ranges=_TNBC + ["C50"],
        report_specialties=["tıbbi onkoloji"],
        message_tr="Ribosiklib — NSAI kombinasyonu HR+/HER2- metastatik meme kanseri; sağlık kurulu raporu gerekir (§4.2.14.C).",
        batch="S1B",
        prescriber_specialties=["tıbbi onkoloji"],
    )
    | {"gate_b_sources": ["C005570"]},
]

PENDING_CLAUSE_IDS: frozenset[str] = frozenset(
    [
        "C004938",
        "C004953",
        "C004974",
        "C005050",
        "C005058",
        "C005084",
        "C005100",
        "C005102",
        "C005189",
        "C005177",
        "C005179",
        "C005184",
        "C005243",
        "C005302",
        "C005318",
        "C005329",
        "C005336",
        "C005339",
        "C005358",
        "C005483",
        "C005436",
        "C005454",
        "C005481",
        "C005483",
        "C005619",
        "C005647",
        "C005683",
        "C005725",
        "C004978",
        "C004987",
        "C004996",
        "C005038",
        "C005087",
        "C005355",
        "C005400",
        "C005434",
        "C005482",
        "C005481",
        "C005570",
    ]
)
