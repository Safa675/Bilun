"""Phase 1 Tier A batch rules for §4.2.14.C drug indication prose."""

from __future__ import annotations

from typing import Any

_ONC = ["C00-C97"]
_HEME = ["C00-C97", "D45-D47"]
_LUNG = ["C34"]
_BREAST = ["C50"]
_PROSTATE = ["C61"]
_MELANOMA = ["C43"]
_MM = ["C90"]
_MDS = ["D46-D47"]
_CML = ["C92-C95"]
_RCC = ["C64-C66"]
_HCC = ["C22"]
_GIST = ["C49"]

_ONC_REPORT = ["tıbbi onkoloji"]
_HEME_REPORT = ["tıbbi onkoloji", "hematoloji"]
_LUNG_REPORT = ["tıbbi onkoloji", "göğüs hastalıkları"]


def _rule(
    rule_id: str,
    drug_names: list[str],
    *,
    icd10_ranges: list[str],
    message_tr: str,
    report_specialties: list[str] | None = None,
    icd10_codes: list[str] | None = None,
    batch: str = "",
    report_duration_months: int | None = None,
    prescriber_specialties: list[str] | None = None,
    inpatient_only: bool | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "rule_id": rule_id,
        "sut_section": "4.2.14.C",
        "drug_names": drug_names,
        "icd10_ranges": icd10_ranges,
        "report_required": True,
        "report_specialties": report_specialties or _ONC_REPORT,
        "message_tr": message_tr,
    }
    if icd10_codes:
        payload["icd10_codes"] = icd10_codes
    if batch:
        payload["encode_batch"] = batch
    if report_duration_months is not None:
        payload["report_duration_months"] = report_duration_months
    if prescriber_specialties:
        payload["prescriber_specialties"] = prescriber_specialties
    if inpatient_only:
        payload["inpatient_only"] = inpatient_only
    return payload


# Batch A1 — IO / targeted lung
BATCH_A1: list[dict[str, Any]] = [
    _rule(
        "4.2.14.C.(15).atezolizumab_nsclc_board",
        ["atezolizumab"],
        icd10_ranges=_LUNG,
        report_specialties=_ONC_REPORT,
        message_tr="Atezolizumab — metastatik KHDAK endikasyonu ve tıbbi onkoloji sağlık kurulu raporu gerekir (§4.2.14.C).",
        batch="A1",
    ),
    _rule(
        "4.2.14.C.(15).durvalumab_nsclc_board",
        ["durvalumab"],
        icd10_ranges=_LUNG,
        report_specialties=_ONC_REPORT,
        message_tr="Durvalumab — akciğer kanseri endikasyonu ve tıbbi onkoloji sağlık kurulu raporu gerekir (§4.2.14.C).",
        batch="A1",
    ),
    _rule(
        "4.2.14.C.(15).avelumab_merkel_board",
        ["avelumab"],
        icd10_ranges=_ONC,
        report_specialties=_ONC_REPORT,
        message_tr="Avelumab — endikasyon ve tıbbi onkoloji sağlık kurulu raporu gerekir (§4.2.14.C).",
        batch="A1",
    ),
    _rule(
        "4.2.14.C.(15).osimertinib_egfr_nsclc_board",
        ["osimertinib"],
        icd10_ranges=_LUNG,
        report_specialties=_LUNG_REPORT,
        message_tr="Osimertinib — EGFR+ KHDAK endikasyonu ve sağlık kurulu raporu gerekir (§4.2.14.C).",
        batch="A1",
    ),
    _rule(
        "4.2.14.C.(15).afatinib_egfr_nsclc_board",
        ["afatinib"],
        icd10_ranges=_LUNG,
        report_specialties=_LUNG_REPORT,
        message_tr="Afatinib — EGFR+ KHDAK endikasyonu ve sağlık kurulu raporu gerekir (§4.2.14.C).",
        batch="A1",
    ),
    _rule(
        "4.2.14.C.(15).brigatinib_alk_nsclc_board",
        ["brigatinib"],
        icd10_ranges=_LUNG,
        report_specialties=_LUNG_REPORT,
        message_tr="Brigatinib — ALK+ KHDAK endikasyonu ve sağlık kurulu raporu gerekir (§4.2.14.C).",
        batch="A1",
    ),
    _rule(
        "4.2.14.C.(15).lorlatinib_alk_ros1_board",
        ["lorlatinib"],
        icd10_ranges=_LUNG,
        report_specialties=_LUNG_REPORT,
        message_tr="Lorlatinib — ALK/ROS1+ KHDAK endikasyonu ve sağlık kurulu raporu gerekir (§4.2.14.C).",
        batch="A1",
    ),
    _rule(
        "4.2.14.C.(15).pemetrexed_nsclc_board",
        ["pemetreksed", "pemetrexed"],
        icd10_ranges=_LUNG,
        report_specialties=_ONC_REPORT,
        message_tr="Pemetreksed — KHDAK kemoterapi endikasyonu ve sağlık kurulu raporu gerekir (§4.2.14.C).",
        batch="A1",
    ),
]

# Batch A2 — Heme / myeloma / MDS
BATCH_A2: list[dict[str, Any]] = [
    _rule(
        "4.2.14.C.(2).daratumumab_mm_board",
        ["daratumumab"],
        icd10_ranges=_MM,
        report_specialties=_HEME_REPORT,
        message_tr="Daratumumab — multipl miyelom endikasyonu ve hematoloji/onkoloji sağlık kurulu raporu gerekir (§4.2.14.C).",
        batch="A2",
    ),
    _rule(
        "4.2.14.C.(2).lenalidomide_mm_board",
        ["lenalidomid"],
        icd10_ranges=_MM,
        report_specialties=_HEME_REPORT,
        message_tr="Lenalidomid — multipl miyelom endikasyonu ve sağlık kurulu raporu gerekir (§4.2.14.C).",
        batch="A2",
    ),
    _rule(
        "4.2.14.C.(2).pomalidomide_mm_board",
        ["pomalidomid"],
        icd10_ranges=_MM,
        report_specialties=_HEME_REPORT,
        message_tr="Pomalidomid — multipl miyelom endikasyonu ve sağlık kurulu raporu gerekir (§4.2.14.C).",
        batch="A2",
    ),
    _rule(
        "4.2.14.C.(2).azacitidine_mds_board",
        ["azasitidin", "azacitidine"],
        icd10_ranges=_MDS,
        report_specialties=_HEME_REPORT,
        message_tr="Azasitidin — MDS endikasyonu ve hematoloji/onkoloji sağlık kurulu raporu gerekir (§4.2.14.C).",
        batch="A2",
    ),
    _rule(
        "4.2.14.C.(2).decitabine_mds_board",
        ["decitabin", "decitabine"],
        icd10_ranges=_MDS,
        report_specialties=_HEME_REPORT,
        message_tr="Decitabin — MDS endikasyonu ve hematoloji/onkoloji sağlık kurulu raporu gerekir (§4.2.14.C).",
        batch="A2",
    ),
    _rule(
        "4.2.14.C.(2).blinatumomab_all_board",
        ["blinatumomab"],
        icd10_ranges=_HEME,
        report_specialties=_HEME_REPORT,
        message_tr="Blinatumomab — ALL endikasyonu ve hematoloji/onkoloji sağlık kurulu raporu gerekir (§4.2.14.C).",
        batch="A2",
    ),
    _rule(
        "4.2.14.C.(2).rituximab_lymphoma_board",
        ["rituximab"],
        icd10_ranges=_HEME,
        report_specialties=_HEME_REPORT,
        message_tr="Rituximab — lenfoma endikasyonu ve sağlık kurulu raporu gerekir (§4.2.14.C).",
        batch="A2",
    ),
    _rule(
        "4.2.14.C.(2).obinutuzumab_cll_board",
        ["obinutuzumab"],
        icd10_ranges=_HEME,
        report_specialties=_HEME_REPORT,
        message_tr="Obinutuzumab — KLL endikasyonu ve sağlık kurulu raporu gerekir (§4.2.14.C).",
        batch="A2",
    ),
    _rule(
        "4.2.14.C.(2).elranatamab_mm_board",
        ["elranatamab"],
        icd10_ranges=_MM,
        report_specialties=_HEME_REPORT,
        message_tr="Elranatamab — multipl miyelom endikasyonu ve sağlık kurulu raporu gerekir (§4.2.14.C).",
        batch="A2",
    ),
    _rule(
        "4.2.14.C.(2).midostaurin_aml_board",
        ["midostaurin"],
        icd10_ranges=_HEME,
        report_specialties=_HEME_REPORT,
        message_tr="Midostaurin — AML endikasyonu ve sağlık kurulu raporu gerekir (§4.2.14.C).",
        batch="A2",
    ),
    _rule(
        "4.2.14.C.(2).gilteritinib_aml_board",
        ["gilteritinib"],
        icd10_ranges=_HEME,
        report_specialties=_HEME_REPORT,
        message_tr="Gilteritinib — AML endikasyonu ve sağlık kurulu raporu gerekir (§4.2.14.C).",
        batch="A2",
    ),
    _rule(
        "4.2.14.C.(2).fedratinib_mpn_board",
        ["fedratinib"],
        icd10_ranges=_MDS,
        report_specialties=_HEME_REPORT,
        message_tr="Fedratinib — miyeloproliferatif neoplazi endikasyonu ve sağlık kurulu raporu gerekir (§4.2.14.C).",
        batch="A2",
    ),
]

# Batch A3 — TKI / small molecules
BATCH_A3: list[dict[str, Any]] = [
    _rule(
        "4.2.14.C.(3).dasatinib_cml_board",
        ["dasatinib"],
        icd10_ranges=_CML,
        report_specialties=_HEME_REPORT,
        message_tr="Dasatinib — KML endikasyonu ve hematoloji/onkoloji sağlık kurulu raporu gerekir (§4.2.14.C).",
        batch="A3",
    ),
    _rule(
        "4.2.14.C.(3).nilotinib_cml_board",
        ["nilotinib"],
        icd10_ranges=_CML,
        report_specialties=_HEME_REPORT,
        message_tr="Nilotinib — KML endikasyonu ve sağlık kurulu raporu gerekir (§4.2.14.C).",
        batch="A3",
    ),
    _rule(
        "4.2.14.C.(3).imatinib_cml_gist_board",
        ["imatinib"],
        icd10_ranges=_CML + _GIST,
        report_specialties=_HEME_REPORT,
        message_tr="İmatinib — KML/GIST endikasyonu ve sağlık kurulu raporu gerekir (§4.2.14.C).",
        batch="A3",
    ),
    _rule(
        "4.2.14.C.(3).bosutinib_cml_board",
        ["bosutinib"],
        icd10_ranges=_CML,
        report_specialties=_HEME_REPORT,
        message_tr="Bosutinib — KML endikasyonu ve sağlık kurulu raporu gerekir (§4.2.14.C).",
        batch="A3",
    ),
    _rule(
        "4.2.14.C.(3).sorafenib_hcc_rcc_board",
        ["sorafenib"],
        icd10_ranges=_HCC + _RCC,
        report_specialties=_ONC_REPORT,
        message_tr="Sorafenib — hepatoselüler/renal hücreli karsinom endikasyonu ve sağlık kurulu raporu gerekir (§4.2.14.C).",
        batch="A3",
    ),
    _rule(
        "4.2.14.C.(3).sunitinib_rcc_board",
        ["sunitinib"],
        icd10_ranges=_RCC,
        report_specialties=_ONC_REPORT,
        message_tr="Sunitinib — renal hücreli karsinom endikasyonu ve sağlık kurulu raporu gerekir (§4.2.14.C).",
        batch="A3",
    ),
    _rule(
        "4.2.14.C.(3).pazopanib_rcc_board",
        ["pazopanib"],
        icd10_ranges=_RCC,
        report_specialties=_ONC_REPORT,
        message_tr="Pazopanib — renal hücreli karsinom endikasyonu ve sağlık kurulu raporu gerekir (§4.2.14.C).",
        batch="A3",
    ),
    _rule(
        "4.2.14.C.(3).regorafenib_crc_board",
        ["regorafenib"],
        icd10_ranges=["C18-C20"],
        report_specialties=_ONC_REPORT,
        message_tr="Regorafenib — kolorektal kanser endikasyonu ve sağlık kurulu raporu gerekir (§4.2.14.C).",
        batch="A3",
    ),
    _rule(
        "4.2.14.C.(3).cabozantinib_rcc_board",
        ["cabozantinib"],
        icd10_ranges=_RCC,
        report_specialties=_ONC_REPORT,
        message_tr="Cabozantinib — renal hücreli karsinom endikasyonu ve sağlık kurulu raporu gerekir (§4.2.14.C).",
        batch="A3",
    ),
    _rule(
        "4.2.14.C.(3).dabrafenib_melanoma_board",
        ["dabrafenib"],
        icd10_ranges=_MELANOMA,
        report_specialties=_ONC_REPORT,
        message_tr="Dabrafenib — melanom endikasyonu ve sağlık kurulu raporu gerekir (§4.2.14.C).",
        batch="A3",
    ),
    _rule(
        "4.2.14.C.(3).vemurafenib_melanoma_board",
        ["vemurafenib"],
        icd10_ranges=_MELANOMA,
        report_specialties=_ONC_REPORT,
        message_tr="Vemurafenib — BRAF+ melanom endikasyonu ve sağlık kurulu raporu gerekir (§4.2.14.C).",
        batch="A3",
    ),
    _rule(
        "4.2.14.C.(3).trametinib_melanoma_board",
        ["trametinib"],
        icd10_ranges=_MELANOMA,
        report_specialties=_ONC_REPORT,
        message_tr="Trametinib — melanom endikasyonu ve sağlık kurulu raporu gerekir (§4.2.14.C).",
        batch="A3",
    ),
    _rule(
        "4.2.14.C.(3).enzalutamide_prostate_board",
        ["enzalutamid"],
        icd10_ranges=_PROSTATE,
        report_specialties=_ONC_REPORT,
        message_tr="Enzalutamid — kastrasyon dirençli prostat kanseri endikasyonu ve sağlık kurulu raporu gerekir (§4.2.14.C).",
        batch="A3",
    ),
    _rule(
        "4.2.14.C.(3).abiraterone_prostate_board",
        ["abirateron"],
        icd10_ranges=_PROSTATE,
        report_specialties=_ONC_REPORT,
        message_tr="Abirateron — prostat kanseri endikasyonu ve sağlık kurulu raporu gerekir (§4.2.14.C).",
        batch="A3",
    ),
    _rule(
        "4.2.14.C.(3).apalutamide_prostate_board",
        ["apalutamid"],
        icd10_ranges=_PROSTATE,
        report_specialties=_ONC_REPORT,
        message_tr="Apalutamid — prostat kanseri endikasyonu ve sağlık kurulu raporu gerekir (§4.2.14.C).",
        batch="A3",
    ),
    _rule(
        "4.2.14.C.(3).darolutamide_prostate_board",
        ["darolutamid"],
        icd10_ranges=_PROSTATE,
        report_specialties=_ONC_REPORT,
        message_tr="Darolutamid — prostat kanseri endikasyonu ve sağlık kurulu raporu gerekir (§4.2.14.C).",
        batch="A3",
    ),
    _rule(
        "4.2.14.C.(3).olaparib_parpi_board",
        ["olaparib"],
        icd10_ranges=_ONC,
        report_specialties=_ONC_REPORT,
        message_tr="Olaparib — onkoloji endikasyonu ve sağlık kurulu raporu gerekir (§4.2.14.C).",
        batch="A3",
    ),
    _rule(
        "4.2.14.C.(3).temsirolimus_rcc_board",
        ["temsirolimus"],
        icd10_ranges=_RCC,
        report_specialties=_ONC_REPORT,
        message_tr="Temsirolimus — renal hücreli karsinom endikasyonu ve sağlık kurulu raporu gerekir (§4.2.14.C).",
        batch="A3",
    ),
    _rule(
        "4.2.14.C.(3).everolimus_oncology_board",
        ["everolimus"],
        icd10_ranges=_ONC,
        report_specialties=_ONC_REPORT,
        message_tr="Everolimus — endikasyon ve sağlık kurulu raporu gerekir (§4.2.14.C).",
        batch="A3",
    ),
    _rule(
        "4.2.14.C.(3).sirolimus_oncology_board",
        ["sirolimus"],
        icd10_ranges=_ONC,
        report_specialties=_ONC_REPORT,
        message_tr="Sirolimus — endikasyon ve sağlık kurulu raporu gerekir (§4.2.14.C).",
        batch="A3",
    ),
]

# Batch A4 — Legacy fıkra tail / mAbs / taxanes
BATCH_A4: list[dict[str, Any]] = [
    _rule(
        "4.2.14.C.(1).trastuzumab_her2_board",
        ["trastuzumab"],
        icd10_ranges=_BREAST,
        report_specialties=_ONC_REPORT,
        message_tr="Trastuzumab — HER2+ meme kanseri endikasyonu ve sağlık kurulu raporu gerekir (§4.2.14.C).",
        batch="A4",
    ),
    _rule(
        "4.2.14.C.(1).pertuzumab_her2_board",
        ["pertuzumab"],
        icd10_ranges=_BREAST,
        report_specialties=_ONC_REPORT,
        message_tr="Pertuzumab — HER2+ meme kanseri endikasyonu ve sağlık kurulu raporu gerekir (§4.2.14.C).",
        batch="A4",
    ),
    _rule(
        "4.2.14.C.(1).lapatinib_her2_board",
        ["lapatinib"],
        icd10_ranges=_BREAST,
        report_specialties=_ONC_REPORT,
        message_tr="Lapatinib — HER2+ meme kanseri endikasyonu ve sağlık kurulu raporu gerekir (§4.2.14.C).",
        batch="A4",
    ),
    _rule(
        "4.2.14.C.(1).trastuzumab_emtansine_board",
        ["trastuzumab emtansin", "t-dm1", "ado-trastuzumab"],
        icd10_ranges=_BREAST,
        report_specialties=_ONC_REPORT,
        message_tr="Trastuzumab emtansin — HER2+ meme kanseri endikasyonu ve sağlık kurulu raporu gerekir (§4.2.14.C).",
        batch="A4",
    ),
    _rule(
        "4.2.14.C.(1).panitumumab_crc_board",
        ["panitumumab"],
        icd10_ranges=["C18-C20"],
        report_specialties=_ONC_REPORT,
        message_tr="Panitumumab — kolorektal kanser endikasyonu ve sağlık kurulu raporu gerekir (§4.2.14.C).",
        batch="A4",
    ),
    _rule(
        "4.2.14.C.(1).ramucirumab_crc_board",
        ["ramucirumab"],
        icd10_ranges=["C18-C20"],
        report_specialties=_ONC_REPORT,
        message_tr="Ramucirumab — kolorektal/gastrik kanser endikasyonu ve sağlık kurulu raporu gerekir (§4.2.14.C).",
        batch="A4",
    ),
    _rule(
        "4.2.14.C.(1).aflibercept_crc_board",
        ["aflibercept", "ziv-aflibercept"],
        icd10_ranges=["C18-C20"],
        report_specialties=_ONC_REPORT,
        message_tr="Aflibercept — kolorektal kanser endikasyonu ve sağlık kurulu raporu gerekir (§4.2.14.C).",
        batch="A4",
    ),
    _rule(
        "4.2.14.C.(1).kabazitaxel_prostate_board",
        ["kabazitaksel", "cabazitaxel"],
        icd10_ranges=_PROSTATE,
        report_specialties=_ONC_REPORT,
        message_tr="Kabazitaksel — prostat kanseri endikasyonu ve sağlık kurulu raporu gerekir (§4.2.14.C).",
        batch="A4",
    ),
    _rule(
        "4.2.14.C.(1).paclitaxel_oncology_board",
        ["paklitaksel", "paclitaxel", "nab-paklitaksel"],
        icd10_ranges=_ONC,
        report_specialties=_ONC_REPORT,
        message_tr="Paklitaksel — onkoloji endikasyonu ve sağlık kurulu raporu gerekir (§4.2.14.C).",
        batch="A4",
    ),
    _rule(
        "4.2.14.C.(1).vismodegib_bcc_board",
        ["vismodegib"],
        icd10_ranges=["C44"],
        report_specialties=_ONC_REPORT,
        message_tr="Vismodegib — bazal hücreli karsinom endikasyonu ve sağlık kurulu raporu gerekir (§4.2.14.C).",
        batch="A4",
    ),
    _rule(
        "4.2.14.C.(1).sonidegib_bcc_board",
        ["sonidegib"],
        icd10_ranges=["C44"],
        report_specialties=_ONC_REPORT,
        message_tr="Sonidegib — bazal hücreli karsinom endikasyonu ve sağlık kurulu raporu gerekir (§4.2.14.C).",
        batch="A4",
    ),
    _rule(
        "4.2.14.C.(1).interferon_oncology_board",
        ["interferon"],
        icd10_ranges=_ONC,
        report_specialties=_ONC_REPORT,
        message_tr="Interferon — onkoloji endikasyonu ve sağlık kurulu raporu gerekir (§4.2.14.C).",
        batch="A4",
    ),
    _rule(
        "4.2.14.C.(1).fotemustine_oncology_board",
        ["fotemustin"],
        icd10_ranges=_ONC,
        report_specialties=_ONC_REPORT,
        message_tr="Fotemustin — onkoloji endikasyonu ve sağlık kurulu raporu gerekir (§4.2.14.C).",
        batch="A4",
    ),
    _rule(
        "4.2.14.C.(1).temozolomide_oncology_board",
        ["temozolomid"],
        icd10_ranges=_ONC,
        report_specialties=_ONC_REPORT,
        message_tr="Temozolomid — onkoloji endikasyonu ve sağlık kurulu raporu gerekir (§4.2.14.C).",
        batch="A4",
    ),
    _rule(
        "4.2.14.C.(1).denosumab_oncology_board",
        ["denosumab"],
        icd10_ranges=_ONC,
        report_specialties=_ONC_REPORT,
        message_tr="Denosumab — kemik metastazı endikasyonu ve sağlık kurulu raporu gerekir (§4.2.14.C).",
        batch="A4",
    ),
    _rule(
        "4.2.14.C.(1).zoledronate_oncology_board",
        ["zoledronik", "zoledronic"],
        icd10_ranges=_ONC,
        report_specialties=_ONC_REPORT,
        message_tr="Zoledronik asit — kemik metastazı endikasyonu ve sağlık kurulu raporu gerekir (§4.2.14.C).",
        batch="A4",
    ),
    _rule(
        "4.2.14.C.(1).idelalisib_cll_board",
        ["idelalisib"],
        icd10_ranges=_HEME,
        report_specialties=_HEME_REPORT,
        message_tr="İdelalisib — KLL endikasyonu ve sağlık kurulu raporu gerekir (§4.2.14.C).",
        batch="A4",
    ),
    _rule(
        "4.2.14.C.(1).gemtuzumab_aml_board",
        ["gemtuzumab"],
        icd10_ranges=_HEME,
        report_specialties=_HEME_REPORT,
        message_tr="Gemtuzumab — AML endikasyonu ve sağlık kurulu raporu gerekir (§4.2.14.C).",
        batch="A4",
    ),
    _rule(
        "4.2.14.C.(1).niraparib_parpi_board",
        ["niraparib"],
        icd10_ranges=_ONC,
        report_specialties=_ONC_REPORT,
        message_tr="Niraparib — onkoloji endikasyonu ve sağlık kurulu raporu gerekir (§4.2.14.C).",
        batch="A4",
    ),
    _rule(
        "4.2.14.C.(1).etoposide_oncology_board",
        ["etoposid"],
        icd10_ranges=_ONC,
        report_specialties=_ONC_REPORT,
        message_tr="Etoposid — onkoloji endikasyonu ve sağlık kurulu raporu gerekir (§4.2.14.C).",
        batch="A4",
    ),
]

PHASE1_BATCH_RULES: list[dict[str, Any]] = BATCH_A1 + BATCH_A2 + BATCH_A3 + BATCH_A4
