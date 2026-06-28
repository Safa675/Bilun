"""R5 Epic A2b — Tier A formula tail rules for §4.2.16 special formulas."""

from __future__ import annotations

from typing import Any

_METABOLIC = ["E70", "E71", "E72", "E74"]
_CF = ["E84"]
_CELIAC = ["K90.0"]
_MALABSORPTION = ["K90", "K91", "E73"]
_CMPA = ["T78.1", "K52.2", "L27.2"]

_METABOLIC_REPORT = [
    "çocuk metabolizma",
    "metabolizma hastalıkları",
    "endokrinoloji",
    "gastroenteroloji",
]
_PEDS_METABOLIC_REPORT = _METABOLIC_REPORT + [
    "çocuk endokrinoloji",
    "çocuk gastroenteroloji",
]
_CMPA_REPORT = [
    "çocuk gastroenteroloji",
    "çocuk immünoloji",
    "çocuk alerji",
    "çocuk sağlığı",
]
_SPECIAL_FORMULA_FALLBACK = [
    "çocuk metabolizma",
    "metabolizma hastalıkları",
    "endokrinoloji",
    "gastroenteroloji",
    "çocuk sağlığı",
    "iç hastalıkları",
]


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
    batch: str = "A2b",
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "rule_id": rule_id,
        "sut_section": sut_section,
        "drug_names": drug_names,
        "icd10_ranges": icd10_ranges,
        "report_required": True,
        "report_specialties": report_specialties or _METABOLIC_REPORT,
        "message_tr": message_tr,
        "encode_batch": batch,
        "gate_b_sources": gate_b_sources,
    }
    if prescriber_specialties:
        payload["prescriber_specialties"] = prescriber_specialties
    if report_duration_months is not None:
        payload["report_duration_months"] = report_duration_months
    return payload


BATCH_A2B_4216_RULES: list[dict[str, Any]] = [
    _rule(
        "4.2.16.special_formula_ek4b_specialist_report",
        "4.2.16",
        ["özel mama", "ozel mama", "tıbbi mama", "metabolik mama", "kistik fibrozis maması"],
        icd10_ranges=_METABOLIC + _CF + _CELIAC,
        report_specialties=_METABOLIC_REPORT,
        prescriber_specialties=_SPECIAL_FORMULA_FALLBACK,
        message_tr=(
            "EK-4/B özel mama — metabolizma/endokrinoloji/gastroenteroloji uzman hekim "
            "raporu gerekir; yoksa çocuk sağlığı/iç hastalıkları (§4.2.16)."
        ),
        gate_b_sources=["C005875", "C005908"],
    ),
    _rule(
        "4.2.16.pediatric_metabolic_formula_3yr_board",
        "4.2.16",
        ["metabolik mama", "fenilketonüri", "pku", "özel formül", "ozel formul"],
        icd10_ranges=_METABOLIC,
        report_specialties=_PEDS_METABOLIC_REPORT,
        prescriber_specialties=_PEDS_METABOLIC_REPORT + ["çocuk sağlığı"],
        report_duration_months=36,
        message_tr=(
            "Doğuştan metabolik hastalık özel formülü — çocuk metabolizma/endokrinoloji/"
            "gastroenteroloji uzman hekim 3 yıl süreli rapor gerekir (§4.2.16)."
        ),
        gate_b_sources=["C005910"],
    ),
    _rule(
        "4.2.16.celiac_gluten_free_1yr_gastro_report",
        "4.2.16",
        ["glutensiz", "özel formüllü un", "ozel formul", "çölyak", "coelyak"],
        icd10_ranges=_CELIAC,
        report_specialties=["gastroenteroloji"],
        prescriber_specialties=["gastroenteroloji"],
        report_duration_months=12,
        message_tr=(
            "Çölyak glutensiz ürün — gastroenteroloji uzman hekim 1 yıl süreli "
            "rapor gerekir (§4.2.16)."
        ),
        gate_b_sources=["C005883", "C005894"],
    ),
    _rule(
        "4.2.16.celiac_gluten_free_3yr_board",
        "4.2.16",
        ["glutensiz un", "glutensiz makarna", "çölyak", "glutensiz bisküvi"],
        icd10_ranges=_CELIAC,
        report_specialties=["gastroenteroloji"],
        prescriber_specialties=["gastroenteroloji", "çocuk sağlığı", "iç hastalıkları"],
        report_duration_months=36,
        message_tr=(
            "Çölyak glutensiz ürün — gastroenteroloji (veya yoksa çocuk sağlığı/iç "
            "hastalıkları) 3 yıl süreli rapor gerekir (§4.2.16)."
        ),
        gate_b_sources=[
            "C005950",
            "C005955",
            "C005961",
            "C005967",
            "C005972",
            "C006002",
        ],
    ),
    _rule(
        "4.2.16.infant_cmpa_hydrolyzed_formula_report",
        "4.2.16",
        ["hidrolize mama", "hidrolize", "inek sütü alerjisi", "cmpa"],
        icd10_ranges=_CMPA,
        report_specialties=_CMPA_REPORT,
        prescriber_specialties=_CMPA_REPORT,
        message_tr=(
            "İnek sütü/çoklu gıda protein alerjisi hidrolize mama — çocuk gastroenteroloji/"
            "immünoloji-alerji (veya çocuk sağlığı) uzman hekim raporu gerekir (§4.2.16)."
        ),
        gate_b_sources=["C005948"],
    ),
    _rule(
        "4.2.16.infant_cmpa_amino_acid_severe_formula",
        "4.2.16",
        ["aminoasit mama", "neocate", "alfamino", "pirinç proteini", "aminoasit bazlı"],
        icd10_ranges=_CMPA,
        report_specialties=_CMPA_REPORT,
        prescriber_specialties=_CMPA_REPORT,
        message_tr=(
            "Ağır CMPA vakalarında aminoasit/pirinç proteini bazlı mama — çocuk "
            "gastroenteroloji/immünoloji-alerji uzman hekim raporu gerekir (§4.2.16)."
        ),
        gate_b_sources=["C005948"],
    ),
    _rule(
        "4.2.16.infant_cmpa_medical_formula_2025",
        "4.2.16",
        ["tıbbi mama", "tibbi mama", "medical formula", "cmpa mama"],
        icd10_ranges=_CMPA,
        report_specialties=_CMPA_REPORT,
        prescriber_specialties=_CMPA_REPORT,
        message_tr=(
            "İki yaşına kadar CMPA tıbbi mama — çocuk gastroenteroloji/alerji/immünoloji "
            "(veya çocuk sağlığı) uzman hekim raporu gerekir (§4.2.16)."
        ),
        gate_b_sources=["C006000"],
    ),
    _rule(
        "4.2.16.malabsorption_special_formula_report",
        "4.2.16",
        ["malabsorbsiyon", "tedavi edici mama", "malabsorbsiyon maması"],
        icd10_ranges=_MALABSORPTION,
        report_specialties=["gastroenteroloji", "çocuk metabolizma", "metabolizma hastalıkları"],
        prescriber_specialties=["gastroenteroloji", "çocuk metabolizma", "çocuk sağlığı", "iç hastalıkları"],
        message_tr=(
            "Malabsorbsiyona neden olan hastalıkta özel mama — gastroenteroloji/metabolizma "
            "uzman hekim raporu gerekir (§4.2.16)."
        ),
        gate_b_sources=["C005875"],
    ),
    _rule(
        "4.2.16.metabolic_formula_prescriber_fallback",
        "4.2.16",
        ["doğuştan metabolik", "metabolik formül", "metabolik formul"],
        icd10_ranges=_METABOLIC,
        report_specialties=_METABOLIC_REPORT + ["çocuk sağlığı", "iç hastalıkları"],
        prescriber_specialties=["çocuk sağlığı", "iç hastalıkları"],
        message_tr=(
            "Metabolik özel formül — uzman hekim bulunmadığında çocuk sağlığı veya "
            "iç hastalıkları uzman hekim raporu ile reçete edilebilir (§4.2.16)."
        ),
        gate_b_sources=["C005875", "C005910"],
    ),
    _rule(
        "4.2.16.special_formula_all_prescriber_with_report",
        "4.2.16",
        ["özel formül mama", "ozel formul mama", "hastalığa özel mama"],
        icd10_ranges=_METABOLIC + _CF + _CELIAC + _CMPA,
        report_specialties=_METABOLIC_REPORT + _CMPA_REPORT,
        message_tr=(
            "Hastalığa özel özel mama — uzman hekim raporu olmadan reçete edilemez; "
            "rapor sonrası tüm hekimler reçete edebilir (§4.2.16)."
        ),
        gate_b_sources=["C005908"],
    ),
]
