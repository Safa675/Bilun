"""R5 Epic A1 — Tier A batch-2 rules for §4.2.1 C-1/C-2/C-3 rheumatology biologics (A2)."""

from __future__ import annotations

from typing import Any

_RA = ["M05", "M06"]
_JIA = ["M08"]
_PSA = ["L40.5"]
_PSORIASIS = ["L40"]
_AS = ["M45"]
_CROHN = ["K50"]
_UC = ["K51"]
_UVEITIS = ["H20", "H30"]
_HS = ["L73", "L73.2"]

_ROMATO_REPORT = [
    "iç hastalıkları",
    "romatoloji",
    "fiziksel tıp",
    "klinik immunoloji",
    "çocuk sağlığı",
    "çocuk romatoloji",
]
_GASTRO_REPORT = ["gastroenteroloji", "genel cerrahi", "iç hastalıkları", "çocuk gastroenteroloji"]
_DERM_REPORT = ["dermatoloji"]
_OPHTHAL_REPORT = ["göz hastalıkları"]
_PED_REPORT = ["çocuk sağlığı", "çocuk romatoloji", "çocuk endokrinoloji"]


def _rule(
    rule_id: str,
    sut_section: str,
    drug_names: list[str],
    *,
    icd10_ranges: list[str],
    message_tr: str,
    gate_b_sources: list[str],
    report_specialties: list[str] | None = None,
    prescriber_specialties: list[str] | None = None,
    report_duration_months: int | None = None,
    batch: str = "A2",
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "rule_id": rule_id,
        "sut_section": sut_section,
        "drug_names": drug_names,
        "icd10_ranges": icd10_ranges,
        "report_required": True,
        "report_specialties": report_specialties or _ROMATO_REPORT,
        "message_tr": message_tr,
        "encode_batch": batch,
        "gate_b_sources": gate_b_sources,
    }
    if prescriber_specialties:
        payload["prescriber_specialties"] = prescriber_specialties
    if report_duration_months is not None:
        payload["report_duration_months"] = report_duration_months
    return payload


_ANTI_TNF = [
    "infliksimab",
    "adalimumab",
    "etanersept",
    "golimumab",
    "sertolizumab",
    "certolizumab",
    "remicade",
    "humira",
    "enbrel",
]

BATCH_A2_RULES: list[dict[str, Any]] = [
    _rule(
        "4.2.1.anti_tnf_ra_das28_initiation",
        "4.2.1.C-1",
        _ANTI_TNF,
        icd10_ranges=_RA,
        prescriber_specialties=_ROMATO_REPORT,
        report_duration_months=3,
        message_tr=(
            "Anti-TNF — erişkin romatoid artritte DMARD yetersizliğinde DAS28 takibi ile "
            "3 ay süreli sağlık kurulu raporu gerekir (§4.2.1.C-1)."
        ),
        gate_b_sources=["C003587"],
    ),
    _rule(
        "4.2.1.infliximab_ra_das28_second_line",
        "4.2.1.C-1",
        ["infliksimab", "remicade"],
        icd10_ranges=_RA,
        prescriber_specialties=_ROMATO_REPORT,
        report_duration_months=3,
        message_tr=(
            "İnfliksimab — diğer anti-TNF yetersiz romatoid artritte DAS28 yanıtı ile "
            "3 ay süreli sağlık kurulu raporu gerekir (§4.2.1.C-1)."
        ),
        gate_b_sources=["C003591"],
    ),
    _rule(
        "4.2.1.anti_tnf_jia_start_board",
        "4.2.1.C-1",
        _ANTI_TNF,
        icd10_ranges=_JIA,
        report_specialties=_PED_REPORT,
        prescriber_specialties=_PED_REPORT,
        report_duration_months=3,
        message_tr=(
            "Anti-TNF — juvenil idiyopatik artritte NSAİ/methotrexat yetersizliğinde "
            "ACR pediatrik 30 yanıtı ile 3 ay süreli sağlık kurulu raporu gerekir (§4.2.1.C-1)."
        ),
        gate_b_sources=["C003593"],
    ),
    _rule(
        "4.2.1.anti_tnf_jia_dmard_failure_board",
        "4.2.1.C-1",
        _ANTI_TNF,
        icd10_ranges=_JIA,
        report_specialties=_PED_REPORT,
        prescriber_specialties=_PED_REPORT,
        report_duration_months=3,
        message_tr=(
            "Anti-TNF — juvenil artritte NSAİ ve DMARD yetersizliğinde "
            "3 ay süreli sağlık kurulu raporu gerekir (§4.2.1.C-1)."
        ),
        gate_b_sources=["C003602"],
    ),
    _rule(
        "4.2.1.adalimumab_jia_uveitis_first_line",
        "4.2.1.C-1",
        ["adalimumab", "humira"],
        icd10_ranges=_JIA + _UVEITIS,
        report_specialties=_PED_REPORT + _OPHTHAL_REPORT,
        prescriber_specialties=_PED_REPORT,
        report_duration_months=3,
        message_tr=(
            "Adalimumab — üveit eşlikli juvenil artritte ilk seçenek anti-TNF olarak "
            "3 ay süreli sağlık kurulu raporu gerekir (§4.2.1.C-1)."
        ),
        gate_b_sources=["C003602"],
    ),
    _rule(
        "4.2.1.infliximab_as_basdai_second_line",
        "4.2.1.C-1",
        ["infliksimab", "remicade"],
        icd10_ranges=_AS,
        report_duration_months=3,
        message_tr=(
            "İnfliksimab — diğer anti-TNF yetersiz ankilozan spondilitte BASDAİ yanıtı ile "
            "3 ay süreli sağlık kurulu raporu gerekir (§4.2.1.C-1)."
        ),
        gate_b_sources=["C003609"],
    ),
    _rule(
        "4.2.1.inflix_psa_second_line_psarc",
        "4.2.1.C-1",
        ["infliksimab", "golimumab", "sertolizumab", "certolizumab"],
        icd10_ranges=_PSA,
        report_duration_months=3,
        message_tr=(
            "İnfliksimab/golimumab/sertolizumab — diğer anti-TNF yetersiz psöriyatik artritte "
            "PSARC yanıtı ile 3 ay süreli sağlık kurulu raporu gerekir (§4.2.1.C-1)."
        ),
        gate_b_sources=["C003621"],
    ),
    _rule(
        "4.2.1.anti_tnf_psoriasis_vulgaris_board",
        "4.2.1.C-1",
        _ANTI_TNF,
        icd10_ranges=_PSORIASIS,
        report_specialties=_DERM_REPORT,
        prescriber_specialties=_DERM_REPORT,
        report_duration_months=6,
        message_tr=(
            "Anti-TNF — plak psoriyaziste DMARD direncinde dermatoloji uzmanının yer aldığı "
            "6 ay süreli sağlık kurulu raporu gerekir (§4.2.1.C-1)."
        ),
        gate_b_sources=["C003625"],
    ),
    _rule(
        "4.2.1.adalimumab_pediatric_crohn_board",
        "4.2.1.C-1",
        ["adalimumab", "infliksimab", "humira", "remicade"],
        icd10_ranges=_CROHN,
        report_specialties=_GASTRO_REPORT,
        prescriber_specialties=_GASTRO_REPORT,
        report_duration_months=4,
        message_tr=(
            "Adalimumab/infliksimab — çocuk Crohn hastalığında konvansiyonel tedavi "
            "yetersizliğinde 4 ay süreli sağlık kurulu raporu gerekir (§4.2.1.C-1)."
        ),
        gate_b_sources=["C003630"],
    ),
    _rule(
        "4.2.1.anti_tnf_uc_conv_failure_board",
        "4.2.1.C-1",
        ["infliksimab", "adalimumab", "remicade", "humira"],
        icd10_ranges=_UC,
        report_specialties=_GASTRO_REPORT,
        prescriber_specialties=_GASTRO_REPORT,
        report_duration_months=6,
        message_tr=(
            "Anti-TNF — ülseratif kolitte konvansiyonel tedavi yetersizliğinde "
            "6 ay süreli uzman hekim raporu gerekir (§4.2.1.C-1)."
        ),
        gate_b_sources=["C003631"],
    ),
    _rule(
        "4.2.1.adalimumab_pediatric_uveitis_board",
        "4.2.1.C-1",
        ["adalimumab", "humira"],
        icd10_ranges=_UVEITIS,
        report_specialties=_OPHTHAL_REPORT,
        prescriber_specialties=_OPHTHAL_REPORT,
        report_duration_months=3,
        message_tr=(
            "Adalimumab — çocuk non-enfeksiyöz kronik anterior üveitte "
            "3 ay süreli sağlık kurulu raporu gerekir (§4.2.1.C-1)."
        ),
        gate_b_sources=["C003635"],
    ),
    _rule(
        "4.2.1.adalimumab_hs_dermatology_board",
        "4.2.1.C-1",
        ["adalimumab", "humira"],
        icd10_ranges=_HS,
        report_specialties=_DERM_REPORT,
        prescriber_specialties=_DERM_REPORT,
        report_duration_months=3,
        message_tr=(
            "Adalimumab — hidradenitis suppurativa'da antibiyotik yetersizliğinde "
            "3 ay süreli dermatoloji sağlık kurulu raporu gerekir (§4.2.1.C-1)."
        ),
        gate_b_sources=["C003636"],
    ),
    _rule(
        "4.2.1.abatacept_ra_tnf_failure_board",
        "4.2.1.C-2",
        ["abatasept", "abatacept", "orencia"],
        icd10_ranges=_RA,
        prescriber_specialties=["romatoloji", "klinik immunoloji", "fiziksel tıp"],
        message_tr=(
            "Abatasept — anti-TNF yetersiz/kontrendike aktif romatoid artritte "
            "methotreksat ile kombine sağlık kurulu raporu gerekir (§4.2.1.C-2)."
        ),
        gate_b_sources=["C003645"],
    ),
    _rule(
        "4.2.1.tocilizumab_ra_university_board",
        "4.2.1.C-3",
        ["tosilizumab", "tocilizumab", "actemra", "roactemra"],
        icd10_ranges=_RA,
        prescriber_specialties=_ROMATO_REPORT,
        report_duration_months=3,
        message_tr=(
            "Tosilizumab — aktif romatoid artritte DMARD/anti-TNF yetersizliğinde "
            "üniversite/eğitim hastanesi 3 ay süreli sağlık kurulu raporu gerekir (§4.2.1.C-3)."
        ),
        gate_b_sources=["C003664"],
    ),
    _rule(
        "4.2.1.tocilizumab_pediatric_anti_tnf_failure",
        "4.2.1.C-3",
        ["tosilizumab", "tocilizumab", "actemra", "roactemra"],
        icd10_ranges=_JIA,
        report_specialties=_PED_REPORT,
        prescriber_specialties=_PED_REPORT,
        report_duration_months=3,
        message_tr=(
            "Tosilizumab — anti-TNF yetersiz juvenil artritte methotreksat ile kombine "
            "3 ay süreli çocuk romatoloji sağlık kurulu raporu gerekir (§4.2.1.C-3)."
        ),
        gate_b_sources=["C003669"],
    ),
]
