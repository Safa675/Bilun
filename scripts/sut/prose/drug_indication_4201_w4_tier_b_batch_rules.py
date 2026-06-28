"""R5 Epic W4 Tier B — §4.2.1 continuation / response-assessment report rules."""

from __future__ import annotations

from typing import Any

_RA = ["M05", "M06"]
_JIA = ["M08"]
_FMF = ["E85.0", "E85"]
_CROHN = ["K50"]
_HS = ["L73.2"]

_ROMATO_BOARD = ["romatoloji"]
_ROMATO_REPORT = [
    "iç hastalıkları",
    "romatoloji",
    "fiziksel tıp",
    "klinik immunoloji",
]
_UNIVERSITY_BOARD = ["romatoloji", "klinik immunoloji", "fiziksel tıp"]
_GASTRO_REPORT = ["gastroenteroloji", "genel cerrahi", "çocuk cerrahisi"]
_PED_REPORT = ["çocuk sağlığı", "çocuk romatoloji"]
_FMF_REPORT = _ROMATO_REPORT + ["nefroloji"]
_DERM_REPORT = ["dermatoloji"]

_ANTI_TNF_CROHN = ["adalimumab", "humira", "infliksimab", "remicade", "sertolizumab", "cimzia"]
_RITUXIMAB = ["rituksimab", "rituximab", "mabthera"]
_TOCILIZUMAB = ["tosilizumab", "tocilizumab", "actemra", "roactemra"]
_JAK = ["tofacitinib", "barisitinib", "upadasitinib", "xeljanz", "olumiant", "rinvoq"]
_FMF_BIOLOGICS = ["anakinra", "kineret", "kanakinumab", "canakinumab", "ilaris"]
_CANAKINUMAB = ["kanakinumab", "canakinumab", "ilaris"]
_SEKUKINUMAB = ["sekukinumab", "secukinumab", "cosentyx"]


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
    batch: str = "W4-TierB",
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


BATCH_4201_W4_TIER_B_RULES: list[dict[str, Any]] = [
    _rule(
        "4.2.1.crohn_fistulizing_month4_cdai_report",
        "4.2.1.C-1",
        _ANTI_TNF_CROHN,
        icd10_ranges=_CROHN,
        report_specialties=_GASTRO_REPORT,
        prescriber_specialties=_GASTRO_REPORT,
        report_duration_months=4,
        message_tr=(
            "Fistülize/şiddetli Crohn — adalimumab/infliksimab/sertolizumab başlangıcında "
            "4 ay süreli sağlık kurulu raporu; 4. ayda CDAI 70 puan düşüşü değerlendirilir "
            "(§4.2.1.C-1 (10))."
        ),
        gate_b_sources=["C003627"],
    ),
    _rule(
        "4.2.1.rituximab_ra_romatoloji_institution_board",
        "4.2.1.C-2",
        _RITUXIMAB,
        icd10_ranges=_RA,
        report_specialties=_ROMATO_BOARD,
        prescriber_specialties=_ROMATO_BOARD,
        message_tr=(
            "Rituksimab — romatoid artritte romatoloji uzman hekiminin bulunduğu kurumda "
            "en az bir romatoloji uzmanının yer aldığı sağlık kurulu raporu gerekir (§4.2.1.C-2 a)."
        ),
        gate_b_sources=["C003642"],
    ),
    _rule(
        "4.2.1.tocilizumab_ra_das28_06_continuation_c3",
        "4.2.1.C-3",
        _TOCILIZUMAB,
        icd10_ranges=_RA,
        prescriber_specialties=_ROMATO_REPORT,
        report_duration_months=3,
        message_tr=(
            "Tosilizumab — romatoid artritte 3. ay DAS28 skorunda 0,6 puandan fazla düşüş "
            "yeni 3 ay süreli sağlık kurulu raporunda belirtilmelidir (§4.2.1.C-3 b)."
        ),
        gate_b_sources=["C003665"],
    ),
    _rule(
        "4.2.1.tocilizumab_ra_das28_06_continuation_c5",
        "4.2.1.C-5",
        _TOCILIZUMAB,
        icd10_ranges=_RA,
        prescriber_specialties=_ROMATO_REPORT,
        report_duration_months=3,
        message_tr=(
            "Tosilizumab — C-5 romatoid artritte 3. ay DAS28 skorunda 0,6 puandan fazla düşüş "
            "yeni 3 ay süreli sağlık kurulu raporunda belirtilmelidir (§4.2.1.C-5 b)."
        ),
        gate_b_sources=["C003693"],
    ),
    _rule(
        "4.2.1.tocilizumab_jia_acr_pediatric_3mo_c5",
        "4.2.1.C-5",
        _TOCILIZUMAB,
        icd10_ranges=_JIA,
        report_specialties=_PED_REPORT,
        prescriber_specialties=_PED_REPORT,
        report_duration_months=3,
        message_tr=(
            "Tosilizumab — juvenil artritte tedavi devamında ACR pediatrik yanıt kriteri "
            "3 ayda bir değerlendirilmeli ve her sağlık kurulu raporunda belirtilmelidir "
            "(§4.2.1.C-5 (4))."
        ),
        gate_b_sources=["C003706", "C003712"],
    ),
    _rule(
        "4.2.1.tofacitinib_ra_prescriber_board_c6",
        "4.2.1.C-6",
        _JAK,
        icd10_ranges=_RA,
        report_specialties=_UNIVERSITY_BOARD,
        prescriber_specialties=_UNIVERSITY_BOARD,
        report_duration_months=6,
        message_tr=(
            "Tofacitinib/barisitinib — romatoid artritte romatoloji veya üniversite/eğitim "
            "hastanesi klinik immunoloji/fiziksel tıp uzmanının yer aldığı en fazla 6 ay "
            "süreli sağlık kurulu raporu gerekir (§4.2.1.C-6 (2))."
        ),
        gate_b_sources=["C003727"],
    ),
    _rule(
        "4.2.1.jia_acr_pediatric_6mo_continuation_c6",
        "4.2.1.C-6",
        _JAK,
        icd10_ranges=_JIA,
        report_specialties=_PED_REPORT,
        prescriber_specialties=_PED_REPORT,
        report_duration_months=6,
        message_tr=(
            "JAK inhibitörleri — juvenil artritte tedavi devamında ACR pediatrik cevap "
            "kriteri 6 ayda bir değerlendirilmeli ve her sağlık kurulu raporunda "
            "belirtilmelidir (§4.2.1.C-6 c)."
        ),
        gate_b_sources=["C003774"],
    ),
    _rule(
        "4.2.1.fmf_jia_acr_pediatric_stop_c7",
        "4.2.1.C-7",
        _FMF_BIOLOGICS,
        icd10_ranges=_JIA + _FMF,
        report_specialties=_PED_REPORT + _FMF_REPORT,
        prescriber_specialties=_PED_REPORT,
        report_duration_months=3,
        message_tr=(
            "Anakinra/tosilizumab/kanakinumab — tedavi devamında ACR pediatrik yanıt "
            "kriteri 3 ayda bir değerlendirilmeli; yanıt alınamayan hastalarda tedavi "
            "sonlandırılır (§4.2.1.C-7 (2))."
        ),
        gate_b_sources=["C003787", "C003790"],
    ),
    _rule(
        "4.2.1.kanakinumab_fmf_3mo_response_c7",
        "4.2.1.C-7",
        _CANAKINUMAB,
        icd10_ranges=_FMF,
        report_specialties=_FMF_REPORT,
        prescriber_specialties=_FMF_REPORT,
        report_duration_months=3,
        message_tr=(
            "Kanakinumab — FMF tedavisinde 3 aylık yanıt değerlendirmesi yapılmalı; "
            "yanıt alınamayan hastalarda tedavi sonlandırılır (§4.2.1.C-7 (3))."
        ),
        gate_b_sources=["C003800"],
    ),
    _rule(
        "4.2.1.sekukinumab_hs_16wk_continuation_c9",
        "4.2.1.C-9",
        _SEKUKINUMAB,
        icd10_ranges=_HS,
        report_specialties=_DERM_REPORT,
        prescriber_specialties=_DERM_REPORT,
        report_duration_months=6,
        message_tr=(
            "Sekukinumab — hidradenitis suppurativada 16 haftalık değerlendirme sonrası "
            "devam kriterlerinin belirtildiği en fazla 6 ay süreli sağlık kurulu raporu "
            "gerekir (§4.2.1.C-9 b)."
        ),
        gate_b_sources=["C003862"],
    ),
]
