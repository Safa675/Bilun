"""R5 Epic A5 — Tier A pilot rules for §4.2.38 diabetes drug indication."""

from __future__ import annotations

from typing import Any

_DIABETES_ICD = ["E10", "E11", "E13", "E14"]
_SPECIALIST_REPORT = [
    "endokrinoloji",
    "iç hastalıkları",
    "çocuk sağlığı",
    "kardiyoloji",
]
_ENDO_INTERNAL = ["endokrinoloji", "iç hastalıkları"]


def _rule(
    rule_id: str,
    sut_section: str,
    drug_names: list[str],
    *,
    icd10_ranges: list[str],
    message_tr: str,
    gate_b_sources: list[str],
    report_required: bool = False,
    report_specialties: list[str] | None = None,
    prescriber_specialties: list[str] | None = None,
    report_duration_months: int | None = None,
    batch: str = "A5",
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
        payload["report_specialties"] = report_specialties or _ENDO_INTERNAL
    if prescriber_specialties:
        payload["prescriber_specialties"] = prescriber_specialties
    if report_duration_months is not None:
        payload["report_duration_months"] = report_duration_months
    return payload


BATCH_A5_RULES: list[dict[str, Any]] = [
    _rule(
        "4.2.38.first_line_oral_antidiabetic",
        "4.2.38",
        [
            "metformin",
            "glucophage",
            "sulfonilüre",
            "glibenklamid",
            "gliklazid",
            "gliclazide",
            "akarboz",
            "acarbose",
            "insan insülin",
            "human insulin",
        ],
        icd10_ranges=_DIABETES_ICD,
        message_tr=(
            "Metformin, sulfonilüreler, alfa glukozidaz inhibitörleri ve insan insülinleri "
            "— tip 1/2 diyabet endikasyonunda tüm hekimler reçete edebilir (§4.2.38)."
        ),
        gate_b_sources=["C006723"],
    ),
    _rule(
        "4.2.38.analog_insulin_pioglitazone_specialist",
        "4.2.38",
        [
            "analog insülin",
            "insulin lispro",
            "insulin aspart",
            "insulin glargine",
            "insulin detemir",
            "insulin degludec",
            "pioglitazon",
            "actos",
        ],
        icd10_ranges=_DIABETES_ICD,
        report_required=True,
        report_specialties=_SPECIALIST_REPORT,
        prescriber_specialties=_SPECIALIST_REPORT,
        message_tr=(
            "Analog insülinler ve pioglitazon — endokrinoloji, iç hastalıkları, çocuk "
            "sağlığı veya kardiyoloji uzman hekim raporu/reçetesi gerekir (§4.2.38)."
        ),
        gate_b_sources=["C006727"],
    ),
    _rule(
        "4.2.38.degludec_aspart_unstable_glucose_board",
        "4.2.38",
        [
            "insülin degludek",
            "insulin degludec",
            "ryzodeg",
            "degludec",
            "insülin aspart",
            "insulin aspart",
        ],
        icd10_ranges=_DIABETES_ICD,
        report_required=True,
        report_specialties=["endokrinoloji"],
        prescriber_specialties=_ENDO_INTERNAL,
        report_duration_months=24,
        message_tr=(
            "İnsülin degludek+aspart kombinasyonu — labil glisemi/hipoglisemi riskinde "
            "endokrinoloji içeren sağlık kurulu raporu (24 ay) ve uzman reçetesi "
            "gerekir (§4.2.38)."
        ),
        gate_b_sources=["C006730"],
    ),
    _rule(
        "4.2.38.dpp4_gliptin_specialist_report",
        "4.2.38",
        [
            "sitagliptin",
            "vildagliptin",
            "saksagliptin",
            "linagliptin",
            "alogliptin",
            "januvia",
            "gliptin",
            "dpp-4",
        ],
        icd10_ranges=_DIABETES_ICD,
        report_required=True,
        report_specialties=_ENDO_INTERNAL,
        message_tr=(
            "DPP-4 antagonistleri — metformin/sülfonilüre maksimum dozda yetersiz "
            "kontrol sonrası endokrinoloji veya iç hastalıkları uzman hekim raporu "
            "gerekir (§4.2.38)."
        ),
        gate_b_sources=["C006735"],
    ),
    _rule(
        "4.2.38.glargine_lixisenatide_obesity_report",
        "4.2.38",
        [
            "liksisenatid",
            "lixisenatide",
            "soliqua",
            "xultophy",
            "insülin glarjin liksisenatid",
            "insulin glargine lixisenatide",
        ],
        icd10_ranges=_DIABETES_ICD,
        report_required=True,
        report_specialties=["endokrinoloji"],
        prescriber_specialties=_ENDO_INTERNAL,
        report_duration_months=12,
        message_tr=(
            "İnsülin glarjin+liksisenatid kombinasyonu — VKİ≥35, pankreatit öyküsü "
            "olmayan tip 2 diyabette 1 yıllık endokrinoloji uzman hekim raporu "
            "gerekir (§4.2.38)."
        ),
        gate_b_sources=["C006747"],
    ),
]
