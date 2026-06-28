"""R5 Epic A5 — Tier A batch rules for §4.2.1.C-9 sekukinumab + §4.2.1.C-13 apremilast."""

from __future__ import annotations

from typing import Any

_PSA = ["L40.5"]
_PSORIASIS = ["L40"]
_HS = ["L73.2"]

_ROMATO_REPORT = [
    "iç hastalıkları",
    "romatoloji",
    "fiziksel tıp",
    "klinik immunoloji",
]
_UNIVERSITY_BOARD = ["romatoloji", "klinik immunoloji", "fiziksel tıp"]
_DERM_REPORT = ["dermatoloji"]

_SEKUKINUMAB = ["sekukinumab", "secukinumab", "cosentyx"]
_APREMILAST = ["apremilast", "otezla"]


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
    batch: str = "A5_C9_C13",
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


BATCH_A5_C9_C13_RULES: list[dict[str, Any]] = [
    _rule(
        "4.2.1.sekukinumab_psoriasis_pasi_systemic_failure",
        "4.2.1.C-9",
        _SEKUKINUMAB,
        icd10_ranges=_PSORIASIS,
        message_tr=(
            "Sekukinumab — geleneksel sistemik tedavi yetersiz plak psoriyaziste PASI "
            "değerinin sağlık kurulu raporunda belirtilmesi gerekir (§4.2.1.C-9)."
        ),
        gate_b_sources=["C003852"],
    ),
    _rule(
        "4.2.1.sekukinumab_psa_second_line",
        "4.2.1.C-9",
        _SEKUKINUMAB,
        icd10_ranges=_PSA,
        message_tr=(
            "Sekukinumab — DMARD ve anti-TNF yetersiz aktif psöriyatik artritte "
            "sağlık kurulu raporunda önceki tedavi yetersizliği belirtilmelidir (§4.2.1.C-9)."
        ),
        gate_b_sources=["C003856"],
    ),
    _rule(
        "4.2.1.sekukinumab_hs_adalimumab_failure",
        "4.2.1.C-9",
        _SEKUKINUMAB,
        icd10_ranges=_HS,
        report_duration_months=4,
        message_tr=(
            "Sekukinumab — hidradenitis suppurativada adalimumab yetersizliğinde "
            "4 ay süreli sağlık kurulu raporu gerekir (§4.2.1.C-9)."
        ),
        gate_b_sources=["C003861"],
    ),
    _rule(
        "4.2.1.apremilast_psa_dmard_second_line",
        "4.2.1.C-13",
        _APREMILAST,
        icd10_ranges=_PSA,
        report_specialties=_UNIVERSITY_BOARD,
        prescriber_specialties=_UNIVERSITY_BOARD,
        report_duration_months=6,
        message_tr=(
            "Apremilast — DMARD yetersiz psöriyatik artritte romatoloji/klinik "
            "immünoloji sağlık kurulu raporu gerekir (§4.2.1.C-13)."
        ),
        gate_b_sources=["C003888"],
    ),
    _rule(
        "4.2.1.apremilast_psoriasis_dermatology_board",
        "4.2.1.C-13",
        _APREMILAST,
        icd10_ranges=_PSORIASIS,
        report_specialties=_DERM_REPORT,
        prescriber_specialties=_DERM_REPORT,
        report_duration_months=6,
        message_tr=(
            "Apremilast — sistemik tedavi yetersiz plak psoriyaziste dermatoloji "
            "uzman hekim raporu gerekir (§4.2.1.C-13)."
        ),
        gate_b_sources=["C003889"],
    ),
]
