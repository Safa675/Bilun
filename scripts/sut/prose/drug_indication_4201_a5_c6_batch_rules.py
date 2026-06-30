"""R5 Epic A5 — Tier A batch rules for §4.2.1.C-6 JAK inhibitors / PsA / IBD / AD pathways."""

from __future__ import annotations

from typing import Any

_RA = ["M05", "M06"]
_PSA = ["L40.5"]
_AS = ["M45"]
_JIA = ["M08"]
_CROHN = ["K50"]
_UC = ["K51"]
_AD = ["L20"]

_ROMATO_REPORT = [
    "iç hastalıkları",
    "romatoloji",
    "fiziksel tıp",
    "klinik immunoloji",
]
_UNIVERSITY_BOARD = ["romatoloji", "klinik immunoloji", "fiziksel tıp"]
_GASTRO_REPORT = ["gastroenteroloji", "genel cerrahi", "iç hastalıkları"]
_DERM_REPORT = ["dermatoloji"]
_AD_BOARD = ["dermatoloji", "immünoloji", "immünoloji ve alerji"]
_PED_REPORT = ["çocuk sağlığı", "çocuk romatoloji"]

_JAK = [
    "tofacitinib",
    "barisitinib",
    "upadasitinib",
    "abrositinib",
    "xeljanz",
    "olumiant",
    "rinvoq",
    "cibinqo",
]
_TOFACITINIB = ["tofacitinib", "xeljanz"]
_UPADACITINIB = ["upadasitinib", "rinvoq"]
_BARICITINIB = ["barisitinib", "olumiant"]
_ABROCITINIB = ["abrositinib", "cibinqo"]


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
    batch: str = "A5_C6",
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


BATCH_A5_C6_RULES: list[dict[str, Any]] = [
    _rule(
        "4.2.1.jak_ra_dmard_initiation",
        "4.2.1.C-6",
        _JAK,
        icd10_ranges=_RA,
        report_duration_months=3,
        message_tr=(
            "JAK inhibitörleri — romatoid artritte DMARD yetersizliğinde (DAS28>5.1) "
            "3 ay süreli sağlık kurulu raporu gerekir (§4.2.1.C-6)."
        ),
        gate_b_sources=["C003738"],
    ),
    _rule(
        "4.2.1.jak_psa_second_line_initiation",
        "4.2.1.C-6",
        _JAK,
        icd10_ranges=_PSA,
        message_tr=(
            "JAK inhibitörleri — DMARD ve anti-TNF yetersiz aktif psöriyatik artritte "
            "sağlık kurulu raporunda önceki tedavi yetersizliği belirtilmelidir (§4.2.1.C-6)."
        ),
        gate_b_sources=["C003741", "C003741"],
    ),
    _rule(
        "4.2.1.tofacitinib_axial_as_initiation",
        "4.2.1.C-6",
        _TOFACITINIB,
        icd10_ranges=_AS,
        report_duration_months=3,
        message_tr=(
            "Tofacitinib — aksiyel tutulumlu ankilozan spondilitte anti-TNF yetersizliğinde "
            "3 ay süreli sağlık kurulu raporu gerekir (§4.2.1.C-6)."
        ),
        gate_b_sources=["C003745"],
    ),
    _rule(
        "4.2.1.tofacitinib_peripheral_as_initiation",
        "4.2.1.C-6",
        _TOFACITINIB,
        icd10_ranges=_AS,
        report_duration_months=3,
        message_tr=(
            "Tofacitinib — periferik eklem tutulumlu ankilozan spondilitte anti-TNF "
            "yetersizliğinde 3 ay süreli sağlık kurulu raporu gerekir (§4.2.1.C-6)."
        ),
        gate_b_sources=["C003746"],
    ),
    _rule(
        "4.2.1.jak_ra_university_prescriber_board",
        "4.2.1.C-6",
        _JAK,
        icd10_ranges=_RA,
        report_specialties=_UNIVERSITY_BOARD,
        prescriber_specialties=_UNIVERSITY_BOARD,
        report_duration_months=6,
        message_tr=(
            "JAK inhibitörleri — romatoid artritte üniversite/eğitim hastanesi "
            "romatoloji/klinik immunoloji/fiziksel tıp sağlık kurulu raporu gerekir "
            "(§4.2.1.C-6)."
        ),
        gate_b_sources=["C003739"],
    ),
    _rule(
        "4.2.1.upadacitinib_anti_tnf_second_line",
        "4.2.1.C-6",
        _UPADACITINIB,
        icd10_ranges=_AS,
        report_duration_months=3,
        message_tr=(
            "Upadasitinib — anti-TNF yetersizliğinde 3 ay süreli sağlık kurulu raporu "
            "gerekir (§4.2.1.C-6)."
        ),
        gate_b_sources=["C003749", "C003778"],
    ),
    _rule(
        "4.2.1.upadacitinib_crohn_anti_tnf",
        "4.2.1.C-6",
        _UPADACITINIB,
        icd10_ranges=_CROHN,
        report_specialties=_GASTRO_REPORT,
        prescriber_specialties=_GASTRO_REPORT,
        report_duration_months=3,
        message_tr=(
            "Upadasitinib — Crohn hastalığında anti-TNF yetersizliğinde doz/süre "
            "belirtilen 3 ay süreli sağlık kurulu raporu gerekir (§4.2.1.C-6)."
        ),
        gate_b_sources=["C003753"],
    ),
    _rule(
        "4.2.1.upadacitinib_uc_anti_tnf",
        "4.2.1.C-6",
        _UPADACITINIB,
        icd10_ranges=_UC,
        report_specialties=_GASTRO_REPORT,
        prescriber_specialties=_GASTRO_REPORT,
        report_duration_months=6,
        message_tr=(
            "Upadasitinib — ülseratif kolitte anti-TNF yetersizliğinde gastroenteroloji/"
            "genel cerrahi uzman hekim raporu gerekir (§4.2.1.C-6)."
        ),
        gate_b_sources=["C003755"],
    ),
    _rule(
        "4.2.1.upadacitinib_ad_dermatology_board",
        "4.2.1.C-6",
        _UPADACITINIB,
        icd10_ranges=_AD,
        report_specialties=_DERM_REPORT,
        prescriber_specialties=_DERM_REPORT,
        report_duration_months=4,
        message_tr=(
            "Upadasitinib — atopik dermatitte üçüncü basamak kurumda üç dermatoloji "
            "uzmanının yer aldığı 4 ay süreli sağlık kurulu raporu gerekir (§4.2.1.C-6)."
        ),
        gate_b_sources=["C003766"],
    ),
    _rule(
        "4.2.1.baricitinib_ad_specialist_board",
        "4.2.1.C-6",
        [*_BARICITINIB, *_ABROCITINIB],
        icd10_ranges=_AD,
        report_specialties=_AD_BOARD,
        prescriber_specialties=_AD_BOARD,
        report_duration_months=4,
        message_tr=(
            "Barisitinib/abrositinib — atopik dermatitte dermatoloji/immünoloji uzman "
            "hekimlerinin yer aldığı 4 ay süreli sağlık kurulu raporu gerekir (§4.2.1.C-6)."
        ),
        gate_b_sources=["C003766"],
    ),
    _rule(
        "4.2.1.jak_ibd_gi_prescriber",
        "4.2.1.C-6",
        _UPADACITINIB,
        icd10_ranges=_UC + _CROHN,
        prescriber_specialties=_GASTRO_REPORT,
        message_tr=(
            "Upadasitinib — IBD tedavisinde sağlık kurulu raporuna dayanılarak "
            "gastroenteroloji/genel cerrahi/iç hastalıkları uzman hekimlerince "
            "reçete düzenlenmelidir (§4.2.1.C-6)."
        ),
        gate_b_sources=["C003770"],
    ),
    _rule(
        "4.2.1.tofacitinib_pjia_second_line",
        "4.2.1.C-6",
        _TOFACITINIB,
        icd10_ranges=_JIA,
        report_specialties=_PED_REPORT,
        prescriber_specialties=_PED_REPORT,
        report_duration_months=3,
        message_tr=(
            "Tofacitinib — metotreksat/TNF/IL-6 yetersiz poliartiküler juvenil artritte "
            "3 ay süreli sağlık kurulu raporu gerekir (§4.2.1.C-6)."
        ),
        gate_b_sources=["C003772"],
    ),
    _rule(
        "4.2.1.jak_pjia_pediatric_tertiary_board",
        "4.2.1.C-6",
        _JAK,
        icd10_ranges=_JIA,
        report_specialties=_PED_REPORT,
        prescriber_specialties=_PED_REPORT,
        message_tr=(
            "JAK inhibitörleri — juvenil artritte çocuk romatoloji uzmanının yer aldığı "
            "üçüncü basamak sağlık kurulu raporu gerekir (§4.2.1.C-6)."
        ),
        gate_b_sources=["C003775"],
    ),
    _rule(
        "4.2.1.jak_efficacy_continuation_romato_immuno",
        "4.2.1.C-6",
        _JAK,
        icd10_ranges=_RA + _PSA + _AS,
        report_specialties=_UNIVERSITY_BOARD,
        prescriber_specialties=["romatoloji", "immünoloji", "klinik immunoloji"],
        report_duration_months=6,
        message_tr=(
            "JAK inhibitörleri — tedavi devamında etkinlik yanıtının romatoloji veya "
            "immünoloji uzman hekim raporunda belirtilmesi gerekir (§4.2.1.C-6)."
        ),
        gate_b_sources=["C003781"],
    ),
]
