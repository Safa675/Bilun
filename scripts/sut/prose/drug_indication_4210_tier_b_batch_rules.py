"""R5 Epic Tier B — §4.2.10 LSD legacy continuation and annual evaluation rules."""

from __future__ import annotations

from typing import Any

_GAUCHER_ICD = ["E75.22"]
_MPS1_ICD = ["E76.0"]

_GAUCHER_ENZYME = [
    "imiglucerase",
    "cerezyme",
    "velaglucerase",
    "vprive",
    "eliglustat",
    "cerdelga",
    "miglustat",
    "zavesca",
]
_MPS1_ENZYME = ["laronidase", "aldurazyme"]

_METABOLISM_REPORT = [
    "çocuk endokrinolojisi ve metabolizma",
    "çocuk metabolizma",
    "endokrinoloji ve metabolizma",
    "gastroenteroloji",
]
_MPS_REPORT = [
    "çocuk metabolizma",
    "çocuk endokrinolojisi ve metabolizma",
    "endokrinoloji ve metabolizma hastalıkları",
]


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
    batch: str = "LSD4210-TierB",
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "rule_id": rule_id,
        "sut_section": sut_section,
        "drug_names": drug_names,
        "icd10_ranges": icd10_ranges,
        "report_required": True,
        "report_specialties": report_specialties or _METABOLISM_REPORT,
        "message_tr": message_tr,
        "encode_batch": batch,
        "gate_b_sources": gate_b_sources,
    }
    if report_duration_months is not None:
        payload["report_duration_months"] = report_duration_months
    return payload


BATCH_4210_TIER_B_RULES: list[dict[str, Any]] = [
    _rule(
        "4.2.10.gaucher_enzyme_legacy_continuation_report",
        "4.2.10.A-1",
        _GAUCHER_ENZYME,
        icd10_ranges=_GAUCHER_ICD,
        report_specialties=_METABOLISM_REPORT,
        report_duration_months=6,
        message_tr=(
            "Gaucher enzim tedavisi — önceki SUT hükümlerine göre başlanan hastalarda tedavi "
            "rapor süresi sonuna kadar devam eder; yeni raporda başlangıç kriterlerinde düzelme "
            "belirtilmelidir. Aralıksız 1 yıl tedavi arası sonrası başlangıç kriterleri yeniden "
            "aranır (§4.2.10.A-1 (5))."
        ),
        gate_b_sources=["C004235"],
    ),
    _rule(
        "4.2.10.mps1_annual_evaluation_continuation",
        "4.2.10.C-2",
        _MPS1_ENZYME,
        icd10_ranges=_MPS1_ICD,
        report_specialties=_MPS_REPORT,
        report_duration_months=12,
        message_tr=(
            "Tip I MPS enzim tedavisi — ilk rapor tarihinden sonraki yıllık değerlendirme "
            "raporunda tedaviye devam kriterleri belirtilmelidir (§4.2.10.C-2 (1))."
        ),
        gate_b_sources=["C004357"],
    ),
]
