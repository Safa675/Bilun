"""R5 Epic A5 — Tier A/B pilot rules for §4.2.35 neuropathic pain / §4.2.37 acromegaly."""

from __future__ import annotations

from typing import Any

_NEUROPATHIC_ICD = ["G60", "G62", "G63", "B02.2", "M79.2"]
_DIABETIC_NEUROPATHY_ICD = ["E11", "G63"]
_FIBROMYALGIA_ICD = ["M79.7", "M79.1"]
_ACROMEGALY_ICD = ["E22.0", "E22"]

_NEUROPATHIC_REPORT = [
    "nöroloji",
    "beyin cerrahisi",
    "fiziksel tıp",
    "fizik tedavi",
    "anestezi",
    "immünoloji",
    "cilt hastalıkları",
    "romatoloji",
    "ortopedi",
    "endokrinoloji",
    "iç hastalıkları",
]
_FIBRO_BOARD = [
    "romatoloji",
    "ortopedi",
    "fizik tedavi",
    "nöroloji",
    "algoloji",
]
_ENDO_REPORT = ["endokrinoloji", "metabolizma"]


def _rule(
    rule_id: str,
    sut_section: str,
    drug_names: list[str],
    *,
    icd10_ranges: list[str],
    message_tr: str,
    gate_b_sources: list[str],
    report_required: bool = True,
    report_specialties: list[str] | None = None,
    report_duration_months: int | None = None,
    prescriber_specialties: list[str] | None = None,
    batch: str = "A5",
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "rule_id": rule_id,
        "sut_section": sut_section,
        "drug_names": drug_names,
        "icd10_ranges": icd10_ranges,
        "report_required": report_required,
        "message_tr": message_tr,
        "encode_batch": batch,
        "gate_b_sources": gate_b_sources,
    }
    if report_specialties is not None:
        payload["report_specialties"] = report_specialties
    if report_duration_months is not None:
        payload["report_duration_months"] = report_duration_months
    if prescriber_specialties:
        payload["prescriber_specialties"] = prescriber_specialties
    return payload


BATCH_A5_RULES: list[dict[str, Any]] = [
    _rule(
        "4.2.35.duloxetine_diabetic_neuropathy_prescriber",
        "4.2.35.A",
        ["duloksetin", "duloxetine", "cymbalta"],
        icd10_ranges=_DIABETIC_NEUROPATHY_ICD,
        report_required=False,
        prescriber_specialties=["endokrinoloji", "nöroloji"],
        message_tr=(
            "Duloksetin — diyabetik periferal nöropatik ağrıda endokrinoloji veya "
            "üçüncü basamak nöroloji uzman hekimi reçetesi gerekir (§4.2.35.A)."
        ),
        gate_b_sources=["C006694"],
    ),
    _rule(
        "4.2.35.neuropathic_pain_specialist_report",
        "4.2.35.A",
        [
            "gabapentin",
            "pregabalin",
            "alfa lipoik",
            "lipoik asit",
            "thioctic acid",
        ],
        icd10_ranges=_NEUROPATHIC_ICD,
        report_specialties=_NEUROPATHIC_REPORT,
        message_tr=(
            "Nöropatik ağrı ilaçları — nöroloji, romatoloji, ortopedi veya endokrinoloji "
            "uzman hekim raporu gerekir (§4.2.35.A)."
        ),
        gate_b_sources=["C006697"],
    ),
    _rule(
        "4.2.35.pregabalin_fibromyalgia_board_6mo",
        "4.2.35.B",
        ["pregabalin", "lyrica"],
        icd10_ranges=_FIBROMYALGIA_ICD,
        report_specialties=_FIBRO_BOARD,
        report_duration_months=6,
        prescriber_specialties=_FIBRO_BOARD,
        message_tr=(
            "Pregabalin fibromiyalji — ikinci/üçüncü basamak sağlık kurulu raporu "
            "(en fazla 6 ay) ve romatoloji/ortopedi/fizik tedavi/nöroloji/algoloji "
            "uzman reçetesi gerekir (§4.2.35.B)."
        ),
        gate_b_sources=["C006705"],
    ),
    _rule(
        "4.2.37.pegvisomant_init_board_2mo",
        "4.2.37.A",
        ["pegvisomant", "somavert"],
        icd10_ranges=_ACROMEGALY_ICD,
        report_specialties=_ENDO_REPORT,
        report_duration_months=2,
        message_tr=(
            "Pegvisomant başlangıç — IGF-1 kontrolü sonrası en fazla 2 ay süreli "
            "sağlık kurulu raporu gerekir (§4.2.37.A)."
        ),
        gate_b_sources=["C006715"],
    ),
    _rule(
        "4.2.37.pegvisomant_endocrine_prescriber",
        "4.2.37.A",
        ["pegvisomant", "somavert"],
        icd10_ranges=_ACROMEGALY_ICD,
        report_specialties=_ENDO_REPORT,
        prescriber_specialties=["endokrinoloji", "metabolizma"],
        message_tr=(
            "Pegvisomant — endokrinoloji ve metabolizma uzman hekimi reçetesi gerekir; "
            "raporda yaşa uygun IGF-1 referans aralığı belirtilmelidir (§4.2.37.A)."
        ),
        gate_b_sources=["C006716", "C006718"],
    ),
]
