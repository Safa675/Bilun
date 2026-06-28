"""R5 Epic Tier B — §4.2.16 protein metabolism special formula rules."""

from __future__ import annotations

from typing import Any

_METABOLIC = ["E70", "E71", "E72", "E74"]

_METABOLIC_REPORT = [
    "çocuk metabolizma",
    "metabolizma hastalıkları",
    "endokrinoloji",
    "gastroenteroloji",
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
    prescriber_specialties: list[str] | None = None,
    batch: str = "TierB",
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "rule_id": rule_id,
        "sut_section": sut_section,
        "drug_names": drug_names,
        "icd10_ranges": icd10_ranges,
        "report_required": True,
        "report_specialties": report_specialties or _METABOLIC_REPORT,
        "message_tr": message_tr,
        "encode_batch": batch,
        "gate_b_sources": gate_b_sources,
    }
    if prescriber_specialties:
        payload["prescriber_specialties"] = prescriber_specialties
    return payload


BATCH_4216_TIER_B_RULES: list[dict[str, Any]] = [
    _rule(
        "4.2.16.protein_metabolism_specialist_prescriber",
        "4.2.16",
        ["özel formüllü un", "ozel formul", "aminoasit metabolizması", "protein metabolizması"],
        icd10_ranges=_METABOLIC,
        prescriber_specialties=_METABOLIC_REPORT,
        message_tr=(
            "Protein metabolizması bozukluğu özel formül — çocuk metabolizma/endokrinoloji/"
            "gastroenteroloji uzman hekim raporu gerekir (§4.2.16 (2))."
        ),
        gate_b_sources=["C005888"],
    ),
    _rule(
        "4.2.16.protein_metabolism_formula_diet_report",
        "4.2.16",
        [
            "özel formüllü un",
            "ozel formul un",
            "aminoasit metabolizması",
            "organik asidemi",
            "üre siklus",
        ],
        icd10_ranges=_METABOLIC,
        prescriber_specialties=_METABOLIC_REPORT,
        message_tr=(
            "Protein metabolizması bozukluğu özel formüllü un — kısıtlı diyet nedeniyle "
            "hayati öneme haiz ürünler uzman hekim raporuna dayanılarak karşılanır (§4.2.16 (3))."
        ),
        gate_b_sources=["C005914", "C005921", "C005928", "C005935", "C005941", "C005987"],
    ),
]
