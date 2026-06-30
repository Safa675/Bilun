"""R5 Epic A2c — Tier A pilot rules for §4.2.33 anti-VEGF tail."""

from __future__ import annotations

from typing import Any

_EYE_REPORT = ["göz hastalıkları"]
_EYE_PRESCRIBER = ["göz hastalıkları"]
_AMD_ICD = ["H35.3"]
_RVDT_ICD = ["H34.8"]
_PMKNV_ICD = ["H44.2"]
_DMO_ICD = ["E10.3", "E11.3", "E13.3", "E14.3"]


def _rule(
    rule_id: str,
    sut_section: str,
    drug_names: list[str],
    *,
    icd10_codes: list[str],
    message_tr: str,
    gate_b_sources: list[str],
    report_duration_months: int | None = 3,
    loading_dose_count: int | None = None,
    max_applications_per_year: int | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "rule_id": rule_id,
        "sut_section": sut_section,
        "drug_names": drug_names,
        "icd10_codes": icd10_codes,
        "report_required": True,
        "report_specialties": _EYE_REPORT,
        "prescriber_specialties": _EYE_PRESCRIBER,
        "message_tr": message_tr,
        "encode_batch": "A2c",
        "gate_b_sources": gate_b_sources,
    }
    if report_duration_months is not None:
        payload["report_duration_months"] = report_duration_months
    if loading_dose_count is not None:
        payload["loading_dose_count"] = loading_dose_count
    if max_applications_per_year is not None:
        payload["max_applications_per_year"] = max_applications_per_year
    return payload


BATCH_A2C_RULES: list[dict[str, Any]] = [
    _rule(
        "4.2.33.A.bevacizumab_first_line_wet_amd",
        "4.2.33.A",
        ["bevacizumab"],
        icd10_codes=_AMD_ICD,
        message_tr=(
            "Bevacizumab (YAŞ AMD) — ilk tedavi seçeneği; göz hastalıkları uzmanı "
            "sağlık kurulu raporu ve reçete şartı (§4.2.33.A/1)."
        ),
        gate_b_sources=["C006561"],
    ),
    _rule(
        "4.2.33.A.anti_vegf_switch_after_bevacizumab_failure",
        "4.2.33.A",
        ["ranibizumab", "aflibersept"],
        icd10_codes=_AMD_ICD,
        message_tr=(
            "Ranibizumab/aflibersept (YAŞ AMD) — bevacizumab tedavisine cevapsızlıkta "
            "göz hastalıkları uzmanı raporu ile geçiş (§4.2.33.A/2)."
        ),
        gate_b_sources=["C006562"],
        loading_dose_count=3,
    ),
    _rule(
        "4.2.33.C.anti_vegf_switch_after_bevacizumab_pm_knv",
        "4.2.33.C",
        ["ranibizumab", "aflibersept"],
        icd10_codes=_PMKNV_ICD,
        message_tr=(
            "Ranibizumab/aflibersept (PM-KNV) — bevacizumab cevapsızlığında göz "
            "hastalıkları uzmanı raporu ile geçiş (§4.2.33.C/2)."
        ),
        gate_b_sources=["C006568"],
        loading_dose_count=3,
    ),
    _rule(
        "4.2.33.general_ranibizumab_aflibersept_loading_protocol",
        "4.2.33",
        ["ranibizumab", "aflibersept"],
        icd10_codes=_AMD_ICD + _DMO_ICD,
        message_tr=(
            "Ranibizumab/aflibersept — 4-6 hafta arayla ardışık 3 yükleme dozu; "
            "göz hastalıkları uzmanı raporu (§4.2.33/9)."
        ),
        gate_b_sources=["C006553"],
        loading_dose_count=3,
    ),
    _rule(
        "4.2.33.general_switch_to_bevacizumab",
        "4.2.33",
        ["bevacizumab"],
        icd10_codes=_AMD_ICD + _DMO_ICD,
        message_tr=(
            "Bevacizumab — ranibizumab/aflibersept arasında ilaç değişimi gereken "
            "hallerde tedaviye bevacizumab ile devam; göz hastalıkları raporu (§4.2.33/7)."
        ),
        gate_b_sources=["C006549"],
        loading_dose_count=3,
        report_duration_months=None,
    ),
    _rule(
        "4.2.33.Ç.deksametazon_timing_after_anti_vegf",
        "4.2.33.Ç",
        ["deksametazon"],
        icd10_codes=_DMO_ICD,
        message_tr=(
            "Deksametazon ITV — anti-VEGF yükleme sonrası idame sırasında veya "
            "anti-VEGF kontrendikasyonunda; yılda maks 2 uygulama (§4.2.33/12)."
        ),
        gate_b_sources=["C006558"],
        max_applications_per_year=2,
        report_duration_months=None,
    ),
    _rule(
        "4.2.33.E.siklosporin_dry_eye_annual_report",
        "4.2.33.E",
        ["siklosporin"],
        icd10_codes=[],
        message_tr=(
            "Siklosporin göz damlası — göz hastalıkları uzmanı 1 yıl süreli "
            "sağlık kurulu raporu (§4.2.33.D/1, C006575)."
        ),
        gate_b_sources=["C006575"],
        report_duration_months=12,
    ),
    _rule(
        "4.2.33.B.ranibizumab_rvdt_loading_protocol",
        "4.2.33.B",
        ["ranibizumab", "aflibersept"],
        icd10_codes=_RVDT_ICD,
        message_tr=(
            "Ranibizumab/aflibersept (RVDT/SRVT) — deksametazon uygun değilse 3 ay "
            "süreli rapor ve 3 yükleme dozu (§4.2.33.B, C006480 güncellemesi)."
        ),
        gate_b_sources=[],
        loading_dose_count=3,
    ),
]

# Patch existing rule gate_b_sources (siklosporin had C006508, corpus anchor is C006575)
SOURCE_PATCHES: dict[str, list[str]] = {
    "4.2.33.E.siklosporin_kuru_goz": ["C006575", ],
    "4.2.33.A.ranibizumab_wet_amd": ["C006562", ],
    "4.2.33.A.aflibersept_wet_amd": ["C006562", ],
}
