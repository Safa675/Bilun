"""R5 Epic A3 — Tier A pilot rules for §4.2.17 osteoporosis / bone metabolism."""

from __future__ import annotations

from typing import Any

_OSTEO_ICD = ["M80", "M81", "M82"]
_OSTEO_REPORT = [
    "iç hastalıkları",
    "fiziksel tıp",
    "ortopedi",
    "romatoloji",
    "endokrinoloji",
    "kadın hastalıkları",
]
_SEVERE_OSTEO_REPORT = [
    "endokrinoloji",
    "fizik tedavi",
    "fiziksel tıp",
    "geriatri",
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
    prescriber_specialties: list[str] | None = None,
    batch: str = "A3",
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "rule_id": rule_id,
        "sut_section": sut_section,
        "drug_names": drug_names,
        "icd10_ranges": icd10_ranges,
        "report_required": True,
        "report_specialties": report_specialties or _OSTEO_REPORT,
        "message_tr": message_tr,
        "encode_batch": batch,
        "gate_b_sources": gate_b_sources,
    }
    if report_duration_months is not None:
        payload["report_duration_months"] = report_duration_months
    if prescriber_specialties:
        payload["prescriber_specialties"] = prescriber_specialties
    return payload


BATCH_A3_RULES: list[dict[str, Any]] = [
    _rule(
        "4.2.17.osteoporosis_bmd_planning",
        "4.2.17.A",
        ["denosumab", "stronsiyum", "raloksifen", "kalsitonin"],
        icd10_ranges=_OSTEO_ICD,
        message_tr=(
            "Osteoporoz ilaç tedavisi — rapor tarihinden önce son iki yıl içinde KMY "
            "ölçümü planlanmalı; ölçüm yılda birden sık yapılamaz (§4.2.17.A)."
        ),
        gate_b_sources=["C006019"],
    ),
    _rule(
        "4.2.17.secondary_osteoporosis_steroid_board",
        "4.2.17.A",
        ["denosumab"],
        icd10_ranges=["M05", "M06", "K50", "K51", "M45", "E05", "J44", "E10", "Z94"],
        message_tr=(
            "Sekonder osteoporoz (steroid, organ nakli, romatolojik hastalık vb.) — "
            "uzman hekim raporu ve KMY kriterleri gerekir (§4.2.17.A)."
        ),
        gate_b_sources=["C006025"],
    ),
    _rule(
        "4.2.17.bisphosphonate_ho_no_bmd",
        "4.2.17.A",
        ["bifosfonat", "etidronat"],
        icd10_ranges=["M84"],
        message_tr=(
            "Heterotopik ossifikasyon endikasyonlu bifosfonat — prospektüs doz/sürelerinde "
            "KMY ölçümü aranmaksızın kullanılabilir (§4.2.17.A)."
        ),
        gate_b_sources=["C006026"],
    ),
    _rule(
        "4.2.17.bisphosphonate_specialist_report",
        "4.2.17.A",
        ["bifosfonat", "alendronat", "risedronat", "zoledronat", "ibandronat", "etidronat"],
        icd10_ranges=_OSTEO_ICD,
        prescriber_specialties=_OSTEO_REPORT,
        message_tr=(
            "Bifosfonat grubu — iç hastalıkları, fizik tedavi, ortopedi, romatoloji, "
            "endokrinoloji veya kadın doğum uzman hekim raporu gerekir (§4.2.17.A)."
        ),
        gate_b_sources=["C006019", "C006027"],
    ),
    _rule(
        "4.2.17.strontium_raloxifene_bisph_fail",
        "4.2.17.A",
        ["stronsiyum", "raloksifen"],
        icd10_ranges=_OSTEO_ICD,
        message_tr=(
            "Stronsiyum ranelat / raloksifen — bifosfonat tolere edilemeyen veya yanıtsız "
            "osteoporozlu hastalarda uzman hekim raporu gerekir (§4.2.17.A)."
        ),
        gate_b_sources=["C006031"],
    ),
    _rule(
        "4.2.17.denosumab_board_report",
        "4.2.17.A",
        ["denosumab", "prolia"],
        icd10_ranges=_OSTEO_ICD + ["C61", "C50"],
        message_tr=(
            "Denosumab — bifosfonat yanıtsız/tolere edilemeyen veya renal yetmezlik "
            "nedeniyle bifosfonat kullanılamayan osteoporozda sağlık kurulu raporu "
            "gerekir (§4.2.17.A)."
        ),
        gate_b_sources=["C006039"],
    ),
    _rule(
        "4.2.17.calcitonin_vertebral_fracture_report",
        "4.2.17.A",
        ["kalsitonin", "miacalcic", "calcitonin"],
        icd10_ranges=["M80", "M81", "M48.5"],
        report_duration_months=3,
        message_tr=(
            "Kalsitonin — ağrılı vertebral kırığı olan osteoporozda sağlık kurulu raporu "
            "ve en fazla 3 aylık tedavi dozu (§4.2.17.A)."
        ),
        gate_b_sources=["C006040"],
    ),
    _rule(
        "4.2.17.calcitonin_tertiary_bisph_fail",
        "4.2.17.A",
        ["kalsitonin", "miacalcic", "calcitonin"],
        icd10_ranges=_OSTEO_ICD,
        message_tr=(
            "Kalsitonin — ağrılı vertebral kırığı olmayan, bifosfonat yanıtsız/tolere "
            "edilemeyen osteoporozda üçüncü basamak kurum ve uzman hekim raporu "
            "gerekir (§4.2.17.A)."
        ),
        gate_b_sources=["C006041"],
    ),
    _rule(
        "4.2.17.teriparatid_severe_osteoporosis_board",
        "4.2.17.D",
        ["teriparatid", "forteo", "romosozumab", "evenity"],
        icd10_ranges=_OSTEO_ICD,
        report_specialties=_SEVERE_OSTEO_REPORT,
        report_duration_months=6,
        message_tr=(
            "Teriparatid / romosozumab — 65+ yaş, T≤-3,5 ve ≥2 kırık ile röntgen tanılı "
            "şiddetli osteoporozda 24 haftalık sağlık kurulu raporu gerekir (§4.2.17.D)."
        ),
        gate_b_sources=["C006053"],
    ),
]
