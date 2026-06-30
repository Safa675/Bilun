"""R5 Epic Tier B — §4.2.13 HBV oral antiviral switch/add and report renewal rules."""

from __future__ import annotations

from typing import Any

_HBV = ["B16", "B18.0", "B18.1"]
_HBV_ORAL = ["entekavir", "tenofovir", "lamivudin", "telbivudin", "adefovir"]

_GASTRO_INF_REPORT = ["gastroenteroloji", "enfeksiyon hastalıkları"]
_GASTRO_INF_PED = _GASTRO_INF_REPORT + ["çocuk sağlığı", "iç hastalıkları"]


def _rule(
    rule_id: str,
    sut_section: str,
    drug_names: list[str],
    *,
    icd10_ranges: list[str],
    message_tr: str,
    gate_b_sources: list[str],
    report_specialties: list[str] | None = None,
    batch: str = "TierB",
) -> dict[str, Any]:
    return {
        "rule_id": rule_id,
        "sut_section": sut_section,
        "drug_names": drug_names,
        "icd10_ranges": icd10_ranges,
        "report_required": True,
        "report_specialties": report_specialties or _GASTRO_INF_REPORT,
        "message_tr": message_tr,
        "encode_batch": batch,
        "gate_b_sources": gate_b_sources,
    }


BATCH_4213_TIER_B_RULES: list[dict[str, Any]] = [
    _rule(
        "4.2.13.hbv_oral_antiviral_switch_adult_report",
        "4.2.13.1",
        _HBV_ORAL,
        icd10_ranges=_HBV,
        message_tr=(
            "Erişkin HBV oral antiviral değişimi veya yeni oral antiviral eklenmesi — "
            "gerekçe yeni veya mevcut sağlık kurulu raporunda belirtilmelidir (§4.2.13.1 ç/e)."
        ),
        gate_b_sources=["C004584"],
    ),
    _rule(
        "4.2.13.hbv_oral_antiviral_switch_pediatric_report",
        "4.2.13.1",
        _HBV_ORAL,
        icd10_ranges=_HBV,
        report_specialties=_GASTRO_INF_PED,
        message_tr=(
            "Çocuk HBV oral antiviral değişimi veya yeni oral antiviral eklenmesi — "
            "gerekçe yeni veya mevcut sağlık kurulu raporunda belirtilmelidir (§4.2.13.1 d)."
        ),
        gate_b_sources=["C004593"],
    ),
    _rule(
        "4.2.13.hbv_antiviral_report_renewal_initiation_f7",
        "4.2.13.1",
        _HBV_ORAL,
        icd10_ranges=_HBV,
        message_tr=(
            "HBV antiviral tedavi rapor yenilemesi — başlama kriterlerinin tedaviye "
            "başlandığı tarihteki mevzuata uygun olduğu yeni raporda belirtilmelidir "
            "(§4.2.13.1 (7))."
        ),
        gate_b_sources=[],
    ),
    _rule(
        "4.2.13.hbv_antiviral_report_renewal_initiation_f8",
        "4.2.13.1",
        _HBV_ORAL,
        icd10_ranges=_HBV,
        message_tr=(
            "HBV antiviral tedavi rapor yenilemesi — başlama kriterlerinin tedaviye "
            "başlandığı tarihteki mevzuata uygun olduğu yeni raporda belirtilmelidir "
            "(§4.2.13.1 (8))."
        ),
        gate_b_sources=[],
    ),
]
