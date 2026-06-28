"""R5 Epic A4 — Tier A batch rules for §4.2.1.C-2 rituximab RA continuation (A4-C2)."""

from __future__ import annotations

from typing import Any

_RA = ["M05", "M06"]

_ROMATO_REPORT = [
    "iç hastalıkları",
    "romatoloji",
    "fiziksel tıp",
    "klinik immunoloji",
]
_ROMATO_BOARD = ["romatoloji"]
_UNIVERSITY_BOARD = ["romatoloji", "klinik immunoloji", "fiziksel tıp"]
_RITUXIMAB = ["rituksimab", "rituximab", "mabthera"]


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
    batch: str = "A4",
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


BATCH_A4_C2_RULES: list[dict[str, Any]] = [
    _rule(
        "4.2.1.rituximab_ra_das28_continuation",
        "4.2.1.C-2",
        _RITUXIMAB,
        icd10_ranges=_RA,
        prescriber_specialties=_UNIVERSITY_BOARD,
        report_duration_months=6,
        message_tr=(
            "Rituksimab — romatoid artritte tedavi devamında DAS28 skorları "
            "6 ay süreli sağlık kurulu raporunda belirtilmelidir (§4.2.1.C-2)."
        ),
        gate_b_sources=["C003646"],
    ),
    _rule(
        "4.2.1.rituximab_ra_romatoloji_board",
        "4.2.1.C-2",
        _RITUXIMAB,
        icd10_ranges=_RA,
        report_specialties=_ROMATO_BOARD,
        prescriber_specialties=_ROMATO_BOARD,
        message_tr=(
            "Rituksimab — romatoid artritte romatoloji kurumunda en az bir romatoloji "
            "uzmanının yer aldığı sağlık kurulu raporu gerekir (§4.2.1.C-2)."
        ),
        gate_b_sources=["C003647", "C003648"],
    ),
    _rule(
        "4.2.1.rituximab_ra_university_tertiary_board",
        "4.2.1.C-2",
        _RITUXIMAB,
        icd10_ranges=_RA,
        report_specialties=_UNIVERSITY_BOARD,
        prescriber_specialties=_UNIVERSITY_BOARD,
        message_tr=(
            "Rituksimab — romatoid artritte üniversite/eğitim hastanesi üçüncü basamak "
            "kurumda romatoloji/klinik immunoloji/fiziksel tıp uzmanının yer aldığı "
            "sağlık kurulu raporu gerekir (§4.2.1.C-2)."
        ),
        gate_b_sources=["C003649"],
    ),
    _rule(
        "4.2.1.rituximab_ra_6mo_renewal",
        "4.2.1.C-2",
        _RITUXIMAB,
        icd10_ranges=_RA,
        prescriber_specialties=_UNIVERSITY_BOARD,
        report_duration_months=6,
        message_tr=(
            "Rituksimab — romatoid artritte her 6 aydan sonraki kullanım için "
            "tedaviye gerekliliğinin belirtildiği yeni sağlık kurulu raporu gerekir (§4.2.1.C-2)."
        ),
        gate_b_sources=["C003652"],
    ),
]
