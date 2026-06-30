"""R5 Epic A5 — Tier A batch rules for §4.2.1.C-2 rituximab report + §4.2.1.C-5 DHA tocilizumab."""

from __future__ import annotations

from typing import Any

_RA = ["M05", "M06"]
_DHA = ["M31.6"]

_ROMATO_BOARD = ["romatoloji"]
_DHA_REPORT = ["romatoloji", "klinik immunoloji", "immünoloji ve alerji"]
_RITUXIMAB = ["rituksimab", "rituximab", "mabthera"]
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
    batch: str = "A5_C2_C5",
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "rule_id": rule_id,
        "sut_section": sut_section,
        "drug_names": drug_names,
        "icd10_ranges": icd10_ranges,
        "report_required": True,
        "report_specialties": report_specialties or _ROMATO_BOARD,
        "message_tr": message_tr,
        "encode_batch": batch,
        "gate_b_sources": gate_b_sources,
    }
    if prescriber_specialties:
        payload["prescriber_specialties"] = prescriber_specialties
    if report_duration_months is not None:
        payload["report_duration_months"] = report_duration_months
    return payload


BATCH_A5_C2_C5_RULES: list[dict[str, Any]] = [
    _rule(
        "4.2.1.rituximab_ra_report_section_header",
        "4.2.1.C-2",
        _RITUXIMAB,
        icd10_ranges=_RA,
        report_specialties=_ROMATO_BOARD,
        prescriber_specialties=_ROMATO_BOARD,
        message_tr=(
            "Rituksimab — romatoid artritte sağlık kurulu raporu romatoloji uzman "
            "hekiminin yer aldığı kurumda düzenlenmelidir (§4.2.1.C-2)."
        ),
        gate_b_sources=["C003647"],
    ),
    _rule(
        "4.2.1.tocilizumab_dha_sc_steroid_contraindicated",
        "4.2.1.C-5",
        _TOCILIZUMAB,
        icd10_ranges=_DHA,
        report_specialties=_DHA_REPORT,
        prescriber_specialties=_DHA_REPORT,
        report_duration_months=3,
        message_tr=(
            "Tosilizumab subkütan — dev hücreli arteritte yüksek doz steroid "
            "kontrendike olduğunda 3 ay süreli romatoloji/immünoloji sağlık kurulu "
            "raporu gerekir (§4.2.1.C-5)."
        ),
        gate_b_sources=["C003719"],
    ),
]
