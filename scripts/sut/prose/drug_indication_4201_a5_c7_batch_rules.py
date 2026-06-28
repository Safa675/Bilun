"""R5 Epic A5 — Tier A batch rules for §4.2.1.C-7 FMF / anakinra / kanakinumab tail."""

from __future__ import annotations

from typing import Any

_FMF = ["E85.0", "E85"]

_ROMATO_REPORT = [
    "iç hastalıkları",
    "romatoloji",
    "fiziksel tıp",
    "klinik immunoloji",
]
_NEPHRO_REPORT = ["nefroloji", "romatoloji", "klinik immunoloji"]
_FMF_REPORT = _ROMATO_REPORT + _NEPHRO_REPORT

_ANAKINRA = ["anakinra", "kineret"]
_CANAKINUMAB = ["kanakinumab", "canakinumab", "ilaris"]
_FMF_BIOLOGICS = _ANAKINRA + _CANAKINUMAB


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
    batch: str = "A5_C7",
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


BATCH_A5_C7_RULES: list[dict[str, Any]] = [
    _rule(
        "4.2.1.anakinra_fmf_colchicine_add_on",
        "4.2.1.C-7",
        _ANAKINRA,
        icd10_ranges=_FMF,
        prescriber_specialties=_ROMATO_REPORT,
        message_tr=(
            "Anakinra — FMF'de kolşisin yetersizliğinde atak/CRP/SAA bulgularının "
            "sağlık kurulu raporunda belirtilmesi gerekir (§4.2.1.C-7)."
        ),
        gate_b_sources=["C003798"],
    ),
    _rule(
        "4.2.1.canakinumab_fmf_anakinra_failure_switch",
        "4.2.1.C-7",
        _CANAKINUMAB,
        icd10_ranges=_FMF,
        prescriber_specialties=_ROMATO_REPORT,
        message_tr=(
            "Kanakinumab — FMF'de 3 ay anakinra yetersizliği veya ciddi yan etki "
            "durumunun sağlık kurulu raporunda belirtilmesi gerekir (§4.2.1.C-7)."
        ),
        gate_b_sources=["C003799"],
    ),
    _rule(
        "4.2.1.anakinra_kanakinumab_tertiary_romato_prescriber",
        "4.2.1.C-7",
        _FMF_BIOLOGICS,
        icd10_ranges=_FMF,
        report_specialties=_ROMATO_REPORT,
        prescriber_specialties=_ROMATO_REPORT,
        message_tr=(
            "Anakinra/kanakinumab — FMF tedavisinde üçüncü basamak kurumda romatoloji "
            "uzman hekiminin yer aldığı sağlık kurulu raporu gerekir (§4.2.1.C-7)."
        ),
        gate_b_sources=["C003801"],
    ),
    _rule(
        "4.2.1.anakinra_canakinumab_fmf_amyloidosis_colchicine",
        "4.2.1.C-7",
        _FMF_BIOLOGICS,
        icd10_ranges=_FMF,
        report_specialties=_FMF_REPORT,
        prescriber_specialties=_FMF_REPORT,
        report_duration_months=12,
        message_tr=(
            "Anakinra/kanakinumab — amiloidozlu FMF'de kolşisin yetersizliğinde "
            "romatoloji/nefroloji uzmanının yer aldığı 1 yıl süreli sağlık kurulu "
            "raporu gerekir (§4.2.1.C-7)."
        ),
        gate_b_sources=["C003802"],
    ),
]
