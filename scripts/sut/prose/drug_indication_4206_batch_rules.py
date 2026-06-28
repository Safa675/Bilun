"""R5 Epic — Tier A pilot rules for §4.2.6 growth hormone / rhIGF-I indications."""

from __future__ import annotations

from typing import Any

_GH_DEFICIENCY_ICD = ["E23.0", "E23.1", "E23.7", "E34.3"]
_TURNER_ICD = ["Q96"]
_LARON_ICD = ["E34.31", "E34.3"]
_SOMATROPIN = [
    "somatropin",
    "somatrogon",
    "büyüme hormonu",
    "buyume hormonu",
    "genotropin",
    "norditropin",
    "omnitrope",
    "saizen",
    "nutropin",
]
_MECASERMIN = [
    "mecasermin",
    "rhigf",
    "rh igf",
    "igf-1",
    "igf1",
    "increlex",
]


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
    prescriber_specialties: list[str] | None = None,
    report_duration_months: int | None = None,
    batch: str = "A6",
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "rule_id": rule_id,
        "sut_section": sut_section,
        "drug_names": drug_names,
        "icd10_ranges": icd10_ranges,
        "message_tr": message_tr,
        "encode_batch": batch,
        "gate_b_sources": gate_b_sources,
    }
    if report_required:
        payload["report_required"] = True
        if report_specialties:
            payload["report_specialties"] = report_specialties
    if prescriber_specialties:
        payload["prescriber_specialties"] = prescriber_specialties
    if report_duration_months is not None:
        payload["report_duration_months"] = report_duration_months
    return payload


BATCH_A6_RULES: list[dict[str, Any]] = [
    _rule(
        "4.2.6.adult_somatropin_board_report",
        "4.2.6.A-2",
        _SOMATROPIN,
        icd10_ranges=_GH_DEFICIENCY_ICD,
        report_specialties=["endokrinoloji"],
        prescriber_specialties=["endokrinoloji", "iç hastalıkları"],
        report_duration_months=12,
        message_tr=(
            "Erişkin büyüme hormonu — erişkin endokrinoloji uzman hekiminin yer aldığı "
            "sağlık kurulu raporu (en fazla 1 yıl) ve endokrinoloji veya iç hastalıkları "
            "uzman hekim reçetesi gerekir (§4.2.6.A-2)."
        ),
        gate_b_sources=["C003998"],
    ),
    _rule(
        "4.2.6.turner_somatropin_pediatric_board",
        "4.2.6.A-3",
        _SOMATROPIN,
        icd10_ranges=_TURNER_ICD,
        report_specialties=["çocuk endokrinoloji"],
        prescriber_specialties=["çocuk endokrinoloji"],
        report_duration_months=12,
        message_tr=(
            "Turner sendromu somatropin — epifizleri açık, klinik/genetik tanılı hastada "
            "en az bir çocuk endokrinoloji uzman hekiminin yer aldığı sağlık kurulu raporu "
            "(en fazla 1 yıl) ve çocuk endokrinoloji uzman reçetesi gerekir (§4.2.6.A-3)."
        ),
        gate_b_sources=["C004003"],
    ),
    _rule(
        "4.2.6.laron_mecasermin_continuation_board",
        "4.2.6.B-2",
        _MECASERMIN,
        icd10_ranges=_LARON_ICD,
        report_specialties=[
            "çocuk endokrinoloji",
            "çocuk endokrinolojisi ve metabolizma",
        ],
        report_duration_months=12,
        message_tr=(
            "Laron sendromu rhIGF-I (mecasermin) devam tedavisi — epifiz hatları açık "
            "hastalarda yılda bir yenilenen sağlık kurulu raporu gerekir (§4.2.6.B-2)."
        ),
        gate_b_sources=["C004039"],
    ),
]
