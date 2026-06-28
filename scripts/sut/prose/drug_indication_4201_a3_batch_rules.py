"""R5 Epic A1 — Tier A batch-3 rules for §4.2.1 continuation / rituximab / ustekinumab (A3)."""

from __future__ import annotations

from typing import Any

_RA = ["M05", "M06"]
_JIA = ["M08"]
_PSA = ["L40.5"]
_PSORIASIS = ["L40"]
_AS = ["M45"]
_CROHN = ["K50"]
_GPA = ["M31", "M30"]
_PEMPHIGUS = ["L10"]

_ROMATO_REPORT = [
    "iç hastalıkları",
    "romatoloji",
    "fiziksel tıp",
    "klinik immunoloji",
    "çocuk sağlığı",
    "çocuk romatoloji",
]
_NEPHRO_REPORT = ["nefroloji", "romatoloji", "klinik immunoloji"]
_DERM_REPORT = ["dermatoloji"]
_GASTRO_REPORT = ["gastroenteroloji", "genel cerrahi", "iç hastalıkları"]
_PED_REPORT = ["çocuk sağlığı", "çocuk romatoloji"]

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
_INFLIX_CERT_GOL = ["infliksimab", "golimumab", "sertolizumab", "certolizumab", "remicade", "simponi", "cimzia"]
_RITUXIMAB = ["rituksimab", "rituximab", "mabthera"]
_USTEKINUMAB = ["ustekinumab", "stelara"]
_TOCILIZUMAB = ["tosilizumab", "tocilizumab", "actemra", "roactemra"]
_ABATACEPT = ["abatasept", "abatacept", "orencia"]


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
    batch: str = "A3",
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


BATCH_A3_RULES: list[dict[str, Any]] = [
    _rule(
        "4.2.1.anti_tnf_jia_acr_continuation",
        "4.2.1.C-1",
        _ANTI_TNF,
        icd10_ranges=_JIA,
        report_specialties=_PED_REPORT,
        prescriber_specialties=_PED_REPORT,
        report_duration_months=3,
        message_tr=(
            "Anti-TNF — juvenil artritte ACR pediatrik 30/50 yanıtı ile tedavi devamında "
            "3–6 ay süreli sağlık kurulu raporu gerekir (§4.2.1.C-1)."
        ),
        gate_b_sources=["C003603"],
    ),
    _rule(
        "4.2.1.inflix_cert_gol_as_second_line",
        "4.2.1.C-1",
        _INFLIX_CERT_GOL,
        icd10_ranges=_AS,
        report_duration_months=3,
        message_tr=(
            "İnfliksimab/golimumab/sertolizumab — diğer anti-TNF yetersiz ankilozan spondilitte "
            "BASDAİ yanıtı ile 3 ay süreli sağlık kurulu raporu gerekir (§4.2.1.C-1)."
        ),
        gate_b_sources=["C003614"],
    ),
    _rule(
        "4.2.1.inflix_cert_gol_psa_psarc_second_line",
        "4.2.1.C-1",
        _INFLIX_CERT_GOL,
        icd10_ranges=_PSA,
        report_duration_months=3,
        message_tr=(
            "İnfliksimab/golimumab/sertolizumab — diğer anti-TNF yetersiz psöriyatik artritte "
            "PSARC yanıtı ile sağlık kurulu raporu gerekir (§4.2.1.C-1)."
        ),
        gate_b_sources=["C003621"],
    ),
    _rule(
        "4.2.1.rituximab_gpa_mpa_nephrology",
        "4.2.1.C-2",
        _RITUXIMAB,
        icd10_ranges=_GPA,
        report_specialties=_NEPHRO_REPORT,
        prescriber_specialties=_NEPHRO_REPORT,
        report_duration_months=1,
        message_tr=(
            "Rituksimab — siklofosfamid dirençli GPA/MPA tedavisinde nefroloji/immünoloji "
            "1 ay süreli sağlık kurulu raporu gerekir; 6 aydan önce tekrar kullanılamaz (§4.2.1.C-2)."
        ),
        gate_b_sources=["C003651"],
    ),
    _rule(
        "4.2.1.rituximab_pemphigus_dermatology",
        "4.2.1.C-2",
        _RITUXIMAB,
        icd10_ranges=_PEMPHIGUS,
        report_specialties=_DERM_REPORT,
        prescriber_specialties=_DERM_REPORT,
        report_duration_months=6,
        message_tr=(
            "Rituksimab — pemfigus vulgaris tedavisinde üçüncü basamak kurumda dermatoloji "
            "6 ay süreli sağlık kurulu raporu; PDAİ skoru ve yanıt değerlendirmesi belirtilir (§4.2.1.C-2)."
        ),
        gate_b_sources=["C003659"],
    ),
    _rule(
        "4.2.1.tocilizumab_ra_das28_continuation_c3",
        "4.2.1.C-3",
        _TOCILIZUMAB,
        icd10_ranges=_RA,
        prescriber_specialties=_ROMATO_REPORT,
        report_duration_months=6,
        message_tr=(
            "Tosilizumab — romatoid artritte tedavi devamında DAS28 skorları "
            "6 ay süreli sağlık kurulu raporunda belirtilmelidir (§4.2.1.C-3)."
        ),
        gate_b_sources=["C003667"],
    ),
    _rule(
        "4.2.1.abatacept_jia_acr30_continuation",
        "4.2.1.C-3",
        _ABATACEPT,
        icd10_ranges=_JIA,
        report_specialties=_PED_REPORT,
        prescriber_specialties=_PED_REPORT,
        report_duration_months=3,
        message_tr=(
            "Abatasept — juvenil artritte ilk 3 ay ACR pediatrik 30 yanıtı sonrası "
            "3 ay süreli sağlık kurulu raporu ile tedaviye devam edilir (§4.2.1.C-3)."
        ),
        gate_b_sources=["C003670"],
    ),
    _rule(
        "4.2.1.abatacept_jia_acr50_continuation",
        "4.2.1.C-3",
        _ABATACEPT,
        icd10_ranges=_JIA,
        report_specialties=_PED_REPORT,
        prescriber_specialties=_PED_REPORT,
        report_duration_months=6,
        message_tr=(
            "Abatasept — juvenil artritte ACR pediatrik 50 yanıtı ile "
            "6 ay süreli sağlık kurulu raporu ile tedaviye devam edilir (§4.2.1.C-3)."
        ),
        gate_b_sources=["C003672"],
    ),
    _rule(
        "4.2.1.ustekinumab_psoriasis_pasi_report",
        "4.2.1.C-4",
        _USTEKINUMAB,
        icd10_ranges=_PSORIASIS,
        report_specialties=_DERM_REPORT,
        prescriber_specialties=_DERM_REPORT,
        message_tr=(
            "Ustekinumab — plak psoriyaziste sağlık kurulu raporunda başlangıç PASI "
            "değeri ve tedavi şeması belirtilmelidir (§4.2.1.C-4)."
        ),
        gate_b_sources=["C003677"],
    ),
    _rule(
        "4.2.1.ustekinumab_psa_dmard_tnf_failure",
        "4.2.1.C-4",
        _USTEKINUMAB,
        icd10_ranges=_PSA,
        prescriber_specialties=_ROMATO_REPORT,
        report_duration_months=3,
        message_tr=(
            "Ustekinumab — DMARD ve anti-TNF yetersiz aktif psöriyatik artritte "
            "3 ay süreli sağlık kurulu raporu gerekir (§4.2.1.C-4)."
        ),
        gate_b_sources=["C003682"],
    ),
    _rule(
        "4.2.1.ustekinumab_crohn_anti_tnf_failure",
        "4.2.1.C-4",
        _USTEKINUMAB,
        icd10_ranges=_CROHN,
        report_specialties=_GASTRO_REPORT,
        prescriber_specialties=_GASTRO_REPORT,
        report_duration_months=4,
        message_tr=(
            "Ustekinumab — yetişkin Crohn hastalığında anti-TNF yetersizliğinde "
            "4 ay süreli sağlık kurulu raporu gerekir (§4.2.1.C-4)."
        ),
        gate_b_sources=["C003686"],
    ),
    _rule(
        "4.2.1.tocilizumab_ra_c5_university_das",
        "4.2.1.C-5",
        _TOCILIZUMAB,
        icd10_ranges=_RA,
        prescriber_specialties=_ROMATO_REPORT,
        report_duration_months=3,
        message_tr=(
            "Tosilizumab — anti-TNF yetersiz aktif romatoid artritte (DAS28>5.1) "
            "üniversite/eğitim hastanesi 3 ay süreli sağlık kurulu raporu gerekir (§4.2.1.C-5)."
        ),
        gate_b_sources=["C003691"],
    ),
    _rule(
        "4.2.1.tocilizumab_ra_c5_methotrexat_combo",
        "4.2.1.C-5",
        _TOCILIZUMAB,
        icd10_ranges=_RA,
        prescriber_specialties=_ROMATO_REPORT,
        report_duration_months=3,
        message_tr=(
            "Tosilizumab — DMARD/anti-TNF yetersiz romatoid artritte methotreksat ile "
            "kombine 3 ay süreli sağlık kurulu raporu gerekir (§4.2.1.C-5)."
        ),
        gate_b_sources=["C003692"],
    ),
    _rule(
        "4.2.1.tocilizumab_ra_das28_continuation_c5",
        "4.2.1.C-5",
        _TOCILIZUMAB,
        icd10_ranges=_RA,
        prescriber_specialties=_ROMATO_REPORT,
        report_duration_months=6,
        message_tr=(
            "Tosilizumab — C-5 romatoid artritte tedavi devamında DAS28 skorları "
            "6 ay süreli sağlık kurulu raporunda belirtilmelidir (§4.2.1.C-5)."
        ),
        gate_b_sources=["C003695"],
    ),
    _rule(
        "4.2.1.tocilizumab_sjia_anakinra_response",
        "4.2.1.C-5",
        _TOCILIZUMAB + ["anakinra", "kineret"],
        icd10_ranges=_JIA,
        report_specialties=_PED_REPORT,
        prescriber_specialties=_PED_REPORT,
        report_duration_months=3,
        message_tr=(
            "Tosilizumab/anakinra — sistemik juvenil artritte ACR pediatrik 50 yanıtı ile "
            "3 ay süreli sağlık kurulu raporu gerekir (§4.2.1.C-5)."
        ),
        gate_b_sources=["C003705", "C003711"],
    ),
]
