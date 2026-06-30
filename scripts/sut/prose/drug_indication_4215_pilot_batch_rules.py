"""R5 Epic A15 — Tier A pilot rules for §4.2.15 antithrombotic indications."""

from __future__ import annotations

from typing import Any

_CAD_ICD = ["I25"]
_ACS_ICD = ["I21", "I22", "I20", "I24"]
_STENT_ICD = ["Z95.1", "Z95.5"]
_VASCULAR_ICD = ["I70", "I63", "I65", "I66"]
_VALVE_ICD = ["Z95.2", "Z95.3", "Z95.4"]
_ANGINA_ICD = ["I20"]
_CARDIO_PRESCRIBER = ["kardiyoloji", "kalp damar cerrahisi"]
_ACS_PRESCRIBER = ["kardiyoloji", "kalp damar cerrahisi", "iç hastalıkları", "acil tıp"]
_BROAD_CARDIO_REPORT = [
    "kardiyoloji",
    "iç hastalıkları",
    "nöroloji",
    "kalp damar cerrahisi",
    "acil tıp",
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
    batch: str = "A15",
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


_CLOPIDOGREL = ["klopidogrel", "plavix"]


BATCH_A15_RULES: list[dict[str, Any]] = [
    _rule(
        "4.2.15.clopidogrel_stent_no_report",
        "4.2.15.A",
        _CLOPIDOGREL,
        icd10_ranges=_STENT_ICD,
        report_required=False,
        prescriber_specialties=_CARDIO_PRESCRIBER,
        message_tr=(
            "Klopidogrel koroner stent — kardiyoloji veya kalp damar cerrahisi uzmanı "
            "rapor aranmaksızın stent öncesi 24 saat ve taburcu sonrası 4 hafta reçete "
            "edebilir (§4.2.15.A-1)."
        ),
        gate_b_sources=["C005776"],
    ),
    _rule(
        "4.2.15.clopidogrel_acs_no_report_acute",
        "4.2.15.A",
        _CLOPIDOGREL,
        icd10_ranges=_ACS_ICD,
        report_required=False,
        prescriber_specialties=_ACS_PRESCRIBER,
        message_tr=(
            "Klopidogrel akut koroner sendrom — kardiyoloji, kalp damar cerrahisi, iç "
            "hastalıkları veya acil tıp uzmanı rapor aranmaksızın reçete edebilir "
            "(§4.2.15.A-2)."
        ),
        gate_b_sources=["C005777"],
    ),
    _rule(
        "4.2.15.clopidogrel_family_medicine_renewal",
        "4.2.15.A",
        _CLOPIDOGREL,
        icd10_ranges=_CAD_ICD + _VASCULAR_ICD,
        report_specialties=["aile hekimliği"],
        report_duration_months=12,
        message_tr=(
            "Klopidogrel rapor yenileme — ilk iki rapor dönemi (toplam 24 ay) sonrası "
            "aile hekimliği uzmanı en fazla 12 aylık rapor düzenleyebilir (§4.2.15.A)."
        ),
        gate_b_sources=["C005778"],
    ),
    _rule(
        "4.2.15.clopidogrel_valve_cad_report",
        "4.2.15.A",
        _CLOPIDOGREL,
        icd10_ranges=_VALVE_ICD + _CAD_ICD + _VASCULAR_ICD,
        report_specialties=_BROAD_CARDIO_REPORT,
        report_duration_months=12,
        message_tr=(
            "Klopidogrel kapak biyoprotezi / KAH / periferik arter / inme — kardiyoloji, "
            "iç hastalıkları, nöroloji, kalp damar cerrahisi veya acil tıp uzman raporu "
            "(en fazla 12 ay) gerekir (§4.2.15.A-3)."
        ),
        gate_b_sources=["C005779"],
    ),
    _rule(
        "4.2.15.clopidogrel_peripheral_stent",
        "4.2.15.A",
        _CLOPIDOGREL,
        icd10_ranges=_VASCULAR_ICD + _STENT_ICD,
        report_required=False,
        prescriber_specialties=_BROAD_CARDIO_REPORT + ["beyin cerrahisi", "radyoloji"],
        message_tr=(
            "Klopidogrel periferik/serebral stent — kardiyoloji, iç hastalıkları, nöroloji, "
            "kalp damar cerrahisi, beyin cerrahisi veya girişimsel radyoloji uzmanı rapor "
            "aranmaksızın reçete edebilir (§4.2.15.A-4)."
        ),
        gate_b_sources=["C005780"],
    ),
    _rule(
        "4.2.15.clopidogrel_cabg_board",
        "4.2.15.B",
        _CLOPIDOGREL,
        icd10_ranges=_CAD_ICD,
        report_specialties=["kalp damar cerrahisi", "kardiyoloji", "genel cerrahi"],
        report_duration_months=12,
        message_tr=(
            "Klopidogrel CABG sonrası — en az bir kalp damar cerrahisi uzmanının yer aldığı "
            "1 yıllık sağlık kurulu raporu gerekir (§4.2.15.B-1)."
        ),
        gate_b_sources=["C005782"],
    ),
    _rule(
        "4.2.15.ranolazin_stable_angina_board",
        "4.2.15.F",
        ["ranolazin", "ranexa"],
        icd10_ranges=_ANGINA_ICD,
        report_specialties=["kardiyoloji"],
        prescriber_specialties=["kardiyoloji", "iç hastalıkları"],
        report_duration_months=12,
        message_tr=(
            "Ranolazin — kronik stabil anginada beta blokör/CCB intoleransında kardiyoloji "
            "uzman raporu (en fazla 12 ay) ve kardiyoloji/iç hastalıkları reçetesi gerekir "
            "(§4.2.15.F)."
        ),
        gate_b_sources=["C005870"],
    ),
    _rule(
        "4.2.15.dabigatran_cardiology_board",
        "4.2.15.D",
        ["dabigatran", "pradaxa"],
        icd10_ranges=_CAD_ICD + _VASCULAR_ICD,
        report_specialties=["kardiyoloji"],
        prescriber_specialties=["kardiyoloji", "iç hastalıkları"],
        report_duration_months=12,
        message_tr=(
            "Dabigatran — tanımlı endikasyonlarda geçiş gerekçeli en az bir kardiyoloji "
            "uzmanının yer aldığı 1 yıllık sağlık kurulu raporu gerekir (§4.2.15.D-3)."
        ),
        gate_b_sources=[],
    ),
]
