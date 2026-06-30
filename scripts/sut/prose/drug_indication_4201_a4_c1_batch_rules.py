"""R5 Epic A4 — Tier A batch rules for §4.2.1.C-1 anti-TNF continuation pathways (A4-C1)."""

from __future__ import annotations

from typing import Any

_JIA = ["M08"]
_AS = ["M45"]

_ROMATO_REPORT = [
    "iç hastalıkları",
    "romatoloji",
    "fiziksel tıp",
    "klinik immunoloji",
    "çocuk sağlığı",
    "çocuk romatoloji",
]
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
    "simponi",
    "cimzia",
]
_INFLIX = ["infliksimab", "remicade"]


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
    batch: str = "A4_C1",
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


BATCH_A4_C1_RULES: list[dict[str, Any]] = [
    _rule(
        "4.2.1.anti_tnf_jia_acr30_continuation_c1",
        "4.2.1.C-1",
        _ANTI_TNF,
        icd10_ranges=_JIA,
        report_specialties=_PED_REPORT,
        prescriber_specialties=_PED_REPORT,
        report_duration_months=3,
        message_tr=(
            "Anti-TNF — juvenil artritte ACR pediatrik 30 yanıtı sonrası "
            "3 ay süreli sağlık kurulu raporu ile tedaviye devam edilir (§4.2.1.C-1)."
        ),
        gate_b_sources=["C003603"],
    ),
    _rule(
        "4.2.1.anti_tnf_jia_acr50_continuation_c1",
        "4.2.1.C-1",
        _ANTI_TNF,
        icd10_ranges=_JIA,
        report_specialties=_PED_REPORT,
        prescriber_specialties=_PED_REPORT,
        report_duration_months=6,
        message_tr=(
            "Anti-TNF — juvenil artritte ACR pediatrik 50 yanıtı ile "
            "6 ay süreli sağlık kurulu raporu ile tedaviye devam edilir (§4.2.1.C-1)."
        ),
        gate_b_sources=["C003603"],
    ),
    _rule(
        "4.2.1.inflix_peripheral_as_second_line_start",
        "4.2.1.C-1",
        _INFLIX,
        icd10_ranges=_AS,
        report_duration_months=3,
        message_tr=(
            "İnfliksimab — periferik eklem tutulumlu ankilozan spondilitte diğer anti-TNF "
            "yetersizliğinin 3 ay süreli sağlık kurulu raporunda belirtilmesi gerekir (§4.2.1.C-1)."
        ),
        gate_b_sources=["C003609"],
    ),
    _rule(
        "4.2.1.inflix_peripheral_as_basdai_continuation",
        "4.2.1.C-1",
        _INFLIX,
        icd10_ranges=_AS,
        report_duration_months=6,
        message_tr=(
            "İnfliksimab — periferik ankilozan spondilitte BASDAİ yanıtı sonrası "
            "6 ay süreli sağlık kurulu raporu ile tedaviye devam edilir (§4.2.1.C-1)."
        ),
        gate_b_sources=["C003609"],
    ),
    _rule(
        "4.2.1.anti_tnf_jia_acr_monitoring_board",
        "4.2.1.C-1",
        _ANTI_TNF,
        icd10_ranges=_JIA,
        report_specialties=_PED_REPORT,
        prescriber_specialties=_PED_REPORT,
        message_tr=(
            "Anti-TNF — juvenil artritte tedavi devamında ACR pediatrik cevap kriterinin "
            "her sağlık kurulu raporunda belirtilmesi gerekir (§4.2.1.C-1)."
        ),
        gate_b_sources=["C003603"],
    ),
    _rule(
        "4.2.1.inflix_peripheral_as_second_line_romato_board",
        "4.2.1.C-1",
        _INFLIX,
        icd10_ranges=_AS,
        prescriber_specialties=_ROMATO_REPORT,
        report_duration_months=3,
        message_tr=(
            "İnfliksimab — periferik ankilozan spondilitte diğer anti-TNF yetersizliğinde "
            "romatoloji uzmanının yer aldığı 3 ay süreli sağlık kurulu raporu gerekir (§4.2.1.C-1)."
        ),
        gate_b_sources=["C003609"],
    ),
]
