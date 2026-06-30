"""R5 Epic A5 — Tier A batch rules for §4.2.1.C-8 vedolizumab Crohn/UC pathways."""

from __future__ import annotations

from typing import Any

_CROHN = ["K50"]
_UC = ["K51"]

_GASTRO_REPORT = ["gastroenteroloji", "genel cerrahi", "iç hastalıkları"]
_VEDOLIZUMAB = ["vedolizumab", "entyvio"]


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
    batch: str = "A5_C8",
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "rule_id": rule_id,
        "sut_section": sut_section,
        "drug_names": drug_names,
        "icd10_ranges": icd10_ranges,
        "report_required": True,
        "report_specialties": report_specialties or _GASTRO_REPORT,
        "message_tr": message_tr,
        "encode_batch": batch,
        "gate_b_sources": gate_b_sources,
    }
    if prescriber_specialties:
        payload["prescriber_specialties"] = prescriber_specialties
    if report_duration_months is not None:
        payload["report_duration_months"] = report_duration_months
    return payload


BATCH_A5_C8_RULES: list[dict[str, Any]] = [
    _rule(
        "4.2.1.vedolizumab_crohn_anti_tnf_initiation",
        "4.2.1.C-8",
        _VEDOLIZUMAB,
        icd10_ranges=_CROHN,
        report_specialties=_GASTRO_REPORT,
        prescriber_specialties=_GASTRO_REPORT,
        report_duration_months=4,
        message_tr=(
            "Vedolizumab — anti-TNF yetersiz Crohn hastalığında doz/süre belirtilen "
            "4 ay süreli sağlık kurulu raporu gerekir (§4.2.1.C-8)."
        ),
        gate_b_sources=["C003839", "C003839"],
    ),
    _rule(
        "4.2.1.vedolizumab_uc_anti_tnf_second_line",
        "4.2.1.C-8",
        _VEDOLIZUMAB,
        icd10_ranges=_UC,
        report_specialties=_GASTRO_REPORT,
        prescriber_specialties=_GASTRO_REPORT,
        report_duration_months=6,
        message_tr=(
            "Vedolizumab — anti-TNF yetersiz ülseratif kolitte gastroenteroloji/genel "
            "cerrahi uzman hekim raporu gerekir (§4.2.1.C-8)."
        ),
        gate_b_sources=["C003840"],
    ),
]
