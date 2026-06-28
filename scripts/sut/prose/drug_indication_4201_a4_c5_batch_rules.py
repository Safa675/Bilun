"""R5 Epic A1 — Tier A batch A4 rules for §4.2.1.C-5 pediatric tocilizumab + DHA."""

from __future__ import annotations

from typing import Any

_JIA = ["M08"]
_DHA = ["M31.6"]
_PED_REPORT = ["çocuk sağlığı", "çocuk romatoloji"]
_DHA_REPORT = ["romatoloji", "klinik immunoloji", "immünoloji ve alerji"]
_TOCILIZUMAB = ["tosilizumab", "tocilizumab", "actemra", "roactemra"]


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
    batch: str = "A4-C5",
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "rule_id": rule_id,
        "sut_section": sut_section,
        "drug_names": drug_names,
        "icd10_ranges": icd10_ranges,
        "report_required": True,
        "report_specialties": report_specialties or _DHA_REPORT,
        "message_tr": message_tr,
        "encode_batch": batch,
        "gate_b_sources": gate_b_sources,
    }
    if prescriber_specialties:
        payload["prescriber_specialties"] = prescriber_specialties
    if report_duration_months is not None:
        payload["report_duration_months"] = report_duration_months
    return payload


BATCH_A4_C5_RULES: list[dict[str, Any]] = [
    _rule(
        "4.2.1.tocilizumab_jia_c5_prior_therapy_failure",
        "4.2.1.C-5",
        _TOCILIZUMAB,
        icd10_ranges=_JIA,
        report_specialties=_PED_REPORT,
        prescriber_specialties=_PED_REPORT,
        report_duration_months=3,
        message_tr=(
            "Tosilizumab — NSAİ/methotrexat/anti-TNF sonrası ACR pediatrik 30 yanıtı "
            "alınamayan juvenil artritte 3 ay süreli çocuk romatoloji sağlık kurulu "
            "raporu gerekir (§4.2.1.C-5)."
        ),
        gate_b_sources=["C003698"],
    ),
    _rule(
        "4.2.1.tocilizumab_jia_c5_acr30_continuation",
        "4.2.1.C-5",
        _TOCILIZUMAB,
        icd10_ranges=_JIA,
        report_specialties=_PED_REPORT,
        prescriber_specialties=_PED_REPORT,
        report_duration_months=3,
        message_tr=(
            "Tosilizumab — juvenil artritte ilk 3 ay ACR pediatrik 30 yanıtı sonrası "
            "3 ay süreli sağlık kurulu raporu ile tedaviye devam edilir (§4.2.1.C-5)."
        ),
        gate_b_sources=["C003699"],
    ),
    _rule(
        "4.2.1.tocilizumab_jia_c5_acr50_continuation",
        "4.2.1.C-5",
        _TOCILIZUMAB,
        icd10_ranges=_JIA,
        report_specialties=_PED_REPORT,
        prescriber_specialties=_PED_REPORT,
        report_duration_months=6,
        message_tr=(
            "Tosilizumab — juvenil artritte ACR pediatrik 50 yanıtı ile "
            "6 ay süreli sağlık kurulu raporu ile tedaviye devam edilir (§4.2.1.C-5)."
        ),
        gate_b_sources=["C003699"],
    ),
    _rule(
        "4.2.1.tocilizumab_dha_sc_initiation",
        "4.2.1.C-5",
        _TOCILIZUMAB,
        icd10_ranges=_DHA,
        prescriber_specialties=_DHA_REPORT,
        report_duration_months=3,
        message_tr=(
            "Tosilizumab subkütan — dev hücreli arteritte koşulları sağlayan hastalarda "
            "3 ay süreli sağlık kurulu raporu gerekir (§4.2.1.C-5)."
        ),
        gate_b_sources=["C003719"],
    ),
    _rule(
        "4.2.1.tocilizumab_dha_sc_efficacy_continuation",
        "4.2.1.C-5",
        _TOCILIZUMAB,
        icd10_ranges=_DHA,
        report_specialties=_DHA_REPORT,
        prescriber_specialties=_DHA_REPORT,
        report_duration_months=6,
        message_tr=(
            "Tosilizumab subkütan — dev hücreli arteritte 3 ay etkinlik değerlendirmesi "
            "sonrası 6 ay süreli romatoloji/immünoloji sağlık kurulu raporu gerekir (§4.2.1.C-5)."
        ),
        gate_b_sources=["C003722"],
    ),
]
