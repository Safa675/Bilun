"""R5 Epic — Tier A pilot rules for §4.2.34 multiple sclerosis DMTs."""

from __future__ import annotations

from typing import Any

_MS_ICD = ["G35"]
_NEUROLOGY = ["nöroloji"]


def _rule(
    rule_id: str,
    sut_section: str,
    drug_names: list[str],
    *,
    icd10_ranges: list[str],
    message_tr: str,
    gate_b_sources: list[str],
    report_specialties: list[str] | None = None,
    report_duration_months: int | None = None,
    prescriber_specialties: list[str] | None = None,
    batch: str = "MS4234",
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "rule_id": rule_id,
        "sut_section": sut_section,
        "drug_names": drug_names,
        "icd10_ranges": icd10_ranges,
        "report_required": True,
        "report_specialties": report_specialties or _NEUROLOGY,
        "message_tr": message_tr,
        "encode_batch": batch,
        "gate_b_sources": gate_b_sources,
    }
    if report_duration_months is not None:
        payload["report_duration_months"] = report_duration_months
    if prescriber_specialties:
        payload["prescriber_specialties"] = prescriber_specialties
    return payload


BATCH_MS4234_RULES: list[dict[str, Any]] = [
    _rule(
        "4.2.34.first_line_dmt_neurology_report",
        "4.2.34",
        [
            "beta interferon",
            "interferon beta",
            "avonex",
            "rebif",
            "glatiramer",
            "glatiramer asetat",
            "copolymer",
            "copaxone",
            "teriflunomid",
            "aubagio",
            "dimetil fumarat",
            "tecfidera",
        ],
        icd10_ranges=_MS_ICD,
        prescriber_specialties=_NEUROLOGY,
        report_duration_months=12,
        message_tr=(
            "Beta interferon, glatiramer asetat, teriflunomid veya dimetil fumarat — "
            "EDSS 5,5 altı relaps-remisyon MS'de üçüncü basamak nöroloji uzman hekim "
            "raporu (en fazla 1 yıl) ve nöroloji reçetesi gerekir (§4.2.34)."
        ),
        gate_b_sources=["C006626"],
    ),
    _rule(
        "4.2.34.fingolimod_neurology_report",
        "4.2.34",
        ["fingolimod", "gilenia"],
        icd10_ranges=_MS_ICD,
        prescriber_specialties=_NEUROLOGY,
        report_duration_months=12,
        message_tr=(
            "Fingolimod — EDSS 5,5 altı relaps-remisyon MS'de üçüncü basamak nöroloji "
            "uzman hekim raporu (en fazla 1 yıl) ve nöroloji reçetesi gerekir (§4.2.34)."
        ),
        gate_b_sources=["C006634"],
    ),
    _rule(
        "4.2.34.natalizumab_neurology_report",
        "4.2.34",
        ["natalizumab", "tysabri"],
        icd10_ranges=_MS_ICD,
        prescriber_specialties=_NEUROLOGY,
        report_duration_months=12,
        message_tr=(
            "Natalizumab — EDSS 5,5 altı relaps-remisyon MS'de üçüncü basamak nöroloji "
            "uzman hekim raporu (en fazla 1 yıl) ve nöroloji reçetesi gerekir (§4.2.34)."
        ),
        gate_b_sources=["C006640"],
    ),
    _rule(
        "4.2.34.ocrelizumab_rrms_report",
        "4.2.34",
        ["okrelizumab", "ocrelizumab", "ocrevus"],
        icd10_ranges=_MS_ICD,
        prescriber_specialties=_NEUROLOGY,
        report_duration_months=12,
        message_tr=(
            "Okrelizumab — EDSS 7 altı relaps-remisyon MS'de üçüncü basamak nöroloji "
            "uzman hekim raporu (en fazla 1 yıl) ve nöroloji reçetesi gerekir (§4.2.34)."
        ),
        gate_b_sources=["C006646"],
    ),
    _rule(
        "4.2.34.cladribine_report_body_weight",
        "4.2.34",
        ["kladribin", "cladribine", "mavenclad"],
        icd10_ranges=_MS_ICD,
        prescriber_specialties=_NEUROLOGY,
        report_duration_months=12,
        message_tr=(
            "Kladribin — nöroloji uzman hekim raporunda güncel vücut ağırlığı belirtilmeli; "
            "en fazla 1 yıllık rapor ve nöroloji reçetesi gerekir (§4.2.34)."
        ),
        gate_b_sources=["C006670"],
    ),
    _rule(
        "4.2.34.alemtuzumab_neurology_report",
        "4.2.34",
        ["alemtuzumab", "lemtrada"],
        icd10_ranges=_MS_ICD,
        prescriber_specialties=_NEUROLOGY,
        report_duration_months=12,
        message_tr=(
            "Alemtuzumab — EDSS 7 altı relaps-remisyon MS'de üçüncü basamak nöroloji "
            "uzman hekim raporu (en fazla 1 yıl) ve nöroloji reçetesi gerekir (§4.2.34)."
        ),
        gate_b_sources=["C006676"],
    ),
]
