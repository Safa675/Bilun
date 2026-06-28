"""R5 Epic A7 — Tier A continuation rules for §4.2.9 ESA / iron / paricalcitol (legacy clauses)."""

from __future__ import annotations

from typing import Any

_ESA_LEGACY = [
    "eritropoietin",
    "epoetin",
    "darbepoetin",
    "aranesp",
    "binocrit",
    "eprex",
    "mircera",
    "retacrit",
    "neo recormon",
    "metoksipolietilen glikol",
]
_CKD_ICD = ["N18"]
_MDS_ICD = ["D46", "D47"]
_HEMATOLOGY = ["hematoloji"]
_NEPHROLOGY_DIALYSIS = [
    "nefroloji",
    "iç hastalıkları",
    "çocuk sağlığı",
    "diyaliz",
]
_ROKSADUSTAT = ["roksadustat", "evrenzo", "roxadustat"]
_PARICALCITOL = ["parikalsitol", "paricalcitol", "zemplar"]


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
    report_duration_months: int | None = None,
    prescriber_specialties: list[str] | None = None,
    batch: str = "A7",
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
        payload["report_specialties"] = report_specialties or _HEMATOLOGY
    if report_duration_months is not None:
        payload["report_duration_months"] = report_duration_months
    if prescriber_specialties:
        payload["prescriber_specialties"] = prescriber_specialties
    return payload


BATCH_A7_RULES: list[dict[str, Any]] = [
    _rule(
        "4.2.9.esa_legacy_muadil_monthly_report",
        "4.2.9.A",
        _ESA_LEGACY,
        icd10_ranges=_CKD_ICD + _MDS_ICD,
        report_required=True,
        report_specialties=_NEPHROLOGY_DIALYSIS + _HEMATOLOGY,
        report_duration_months=1,
        message_tr=(
            "Eritropoietin alfa-beta-zeta, metoksipolietilen glikol epoetin beta ve "
            "darbepoetin endikasyon muadili olarak kullanılabilir; raporda doz/süre "
            "belirtilir ve bir defada en fazla 1 aylık reçete verilir (§4.2.9.A)."
        ),
        gate_b_sources=["C004118", "C004119"],
    ),
    _rule(
        "4.2.9.esa_ckd_iron_hb_nephrology_report",
        "4.2.9.A-1",
        _ESA_LEGACY,
        icd10_ranges=_CKD_ICD,
        report_required=True,
        report_specialties=_NEPHROLOGY_DIALYSIS,
        prescriber_specialties=_NEPHROLOGY_DIALYSIS,
        report_duration_months=1,
        message_tr=(
            "KBY anemisi ESA — TSAT/ferritin ve Hb kriterleri; demir eksikliğinde önce "
            "demir tedavisi; hedef Hb 11-12 g/dl; tetkik sonuçları raporda belirtilir "
            "(§4.2.9.A-1)."
        ),
        gate_b_sources=["C004121"],
    ),
    _rule(
        "4.2.9.esa_ckd_legacy_nephrology_prescriber",
        "4.2.9.A-1",
        _ESA_LEGACY,
        icd10_ranges=_CKD_ICD,
        report_required=True,
        report_specialties=_NEPHROLOGY_DIALYSIS,
        prescriber_specialties=_NEPHROLOGY_DIALYSIS,
        message_tr=(
            "KBY anemisi ESA — nefroloji veya diyaliz sertifikalı uzman hekim raporuna "
            "dayanılarak nefroloji/diyaliz sertifikalı hekimlerce reçete edilir "
            "(§4.2.9.A-1)."
        ),
        gate_b_sources=["C004122"],
    ),
    _rule(
        "4.2.9.roksadustat_esa_switch_dialysis_report",
        "4.2.9.A-1",
        _ROKSADUSTAT,
        icd10_ranges=_CKD_ICD,
        report_required=True,
        report_specialties=_NEPHROLOGY_DIALYSIS,
        prescriber_specialties=_NEPHROLOGY_DIALYSIS,
        report_duration_months=1,
        message_tr=(
            "Roksadustat — stabil diyaliz hastasında ESA'dan geçişte klinik neden raporda "
            "belirtilmeli; başlangıç dozu önceki 4 haftalık ortalama ESA dozuna göre "
            "ayarlanır (§4.2.9.A-1)."
        ),
        gate_b_sources=["C004134"],
    ),
    _rule(
        "4.2.9.mds_esa_initiation_hematology_report",
        "4.2.9.A-2",
        ["eritropoietin", "epoetin", "darbepoetin", "aranesp", "binocrit"],
        icd10_ranges=_MDS_ICD,
        report_required=True,
        report_specialties=_HEMATOLOGY,
        prescriber_specialties=_HEMATOLOGY + ["iç hastalıkları"],
        message_tr=(
            "MDS anemisi ESA — Hb<11, blast <%5 ve sEPO<500 ile başlanır; hedef Hb 12 g/dl; "
            "hematoloji uzman raporu ve hemogram reçetede belirtilir (§4.2.9.A-2)."
        ),
        gate_b_sources=["C004136"],
    ),
    _rule(
        "4.2.9.paricalcitol_oral_pd_nephrology_report",
        "4.2.9.C-2",
        _PARICALCITOL,
        icd10_ranges=_CKD_ICD,
        report_required=True,
        report_specialties=_NEPHROLOGY_DIALYSIS,
        prescriber_specialties=_NEPHROLOGY_DIALYSIS,
        report_duration_months=3,
        message_tr=(
            "Parikalsitol oral — evre 5 KBY periton diyaliz hastalarında PTH/Ca/P kriterleri; "
            "nefroloji raporu; tetkikler 3 ayda bir tekrarlanır (§4.2.9.C-2)."
        ),
        gate_b_sources=["C004160"],
    ),
]
