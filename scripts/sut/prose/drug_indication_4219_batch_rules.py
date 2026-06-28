"""R5 Epic A4 — Tier A pilot rules for §4.2.19 migraine prophylaxis / triptans."""

from __future__ import annotations

from typing import Any

_MIGRAINE_ICD = ["G43"]


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
    batch: str = "A4",
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
        payload["report_specialties"] = report_specialties or ["nöroloji"]
    if prescriber_specialties:
        payload["prescriber_specialties"] = prescriber_specialties
    return payload


BATCH_A4_RULES: list[dict[str, Any]] = [
    _rule(
        "4.2.19.triptan_neurology_prescriber",
        "4.2.19",
        [
            "triptan",
            "sumatriptan",
            "zolmitriptan",
            "rizatriptan",
            "eletriptan",
            "naratriptan",
            "almotriptan",
            "frovatriptan",
        ],
        icd10_ranges=_MIGRAINE_ICD,
        prescriber_specialties=["nöroloji"],
        message_tr=(
            "Triptanlar — migren endikasyonunda nöroloji uzman hekimi reçetesi gerekir (§4.2.19)."
        ),
        gate_b_sources=["C006062"],
    ),
    _rule(
        "4.2.19.topiramate_migraine_prophylaxis",
        "4.2.19",
        ["topiramat", "topiramate"],
        icd10_ranges=_MIGRAINE_ICD,
        report_required=True,
        report_specialties=["nöroloji"],
        prescriber_specialties=["nöroloji"],
        message_tr=(
            "Topiramat profilaktik migren — diğer profilaktikler 6 ay etkisiz kaldıktan sonra "
            "nöroloji uzman hekim raporu ile başlanır (§4.2.19)."
        ),
        gate_b_sources=["C006063"],
    ),
]
