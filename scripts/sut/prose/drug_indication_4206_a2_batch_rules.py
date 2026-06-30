"""R5 Epic A2 — Tier A/B board-report rules for §4.2.6 growth hormone / rhIGF-I."""

from __future__ import annotations

from typing import Any

_GH_DEFICIENCY_ICD = ["E23.0", "E23.1", "E23.7", "E34.3"]
_PWS_ICD = ["Q87.1"]
_CKD_ICD = ["N18", "N19", "N25"]
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

_PED_ENDO_REPORT = [
    "çocuk endokrinoloji",
    "çocuk endokrinolojisi ve metabolizma",
]
_PED_ENDO_PRESCRIBER = ["çocuk endokrinoloji"]
_ENDO_REPORT = ["endokrinoloji"]
_CKD_REPORT = ["çocuk nefroloji", "çocuk endokrinoloji", "nefroloji"]


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
    batch: str = "A2",
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "rule_id": rule_id,
        "sut_section": sut_section,
        "drug_names": drug_names,
        "icd10_ranges": icd10_ranges,
        "report_required": True,
        "message_tr": message_tr,
        "encode_batch": batch,
        "gate_b_sources": gate_b_sources,
    }
    if report_specialties:
        payload["report_specialties"] = report_specialties
    if prescriber_specialties:
        payload["prescriber_specialties"] = prescriber_specialties
    if report_duration_months is not None:
        payload["report_duration_months"] = report_duration_months
    return payload


BATCH_A2_RULES: list[dict[str, Any]] = [
    _rule(
        "4.2.6.general_gh_age_group_board",
        "4.2.6.A",
        _SOMATROPIN,
        icd10_ranges=_GH_DEFICIENCY_ICD,
        report_specialties=_ENDO_REPORT,
        prescriber_specialties=_ENDO_REPORT,
        report_duration_months=12,
        message_tr=(
            "Büyüme hormonu — yaş grubuna göre endokrinoloji uzman hekiminin yer aldığı "
            "sağlık kurulu raporu (en fazla 1 yıl) ve endokrinoloji uzman reçetesi "
            "gerekir (§4.2.6.A)."
        ),
        gate_b_sources=["C003941"],
    ),
    _rule(
        "4.2.6.pediatric_gh_monitoring_board",
        "4.2.6.A-1",
        _SOMATROPIN,
        icd10_ranges=_GH_DEFICIENCY_ICD,
        report_specialties=_ENDO_REPORT,
        report_duration_months=12,
        message_tr=(
            "Pediatrik büyüme hormonu devam tedavisi — endokrinoloji uzman hekiminin yer "
            "aldığı 1 yıllık sağlık kurulu raporu ve epifiz hatları takibi gerekir "
            "(§4.2.6.A-1)."
        ),
        gate_b_sources=[],
    ),
    _rule(
        "4.2.6.pediatric_somatropin_initiation_board",
        "4.2.6.A-1",
        _SOMATROPIN,
        icd10_ranges=_GH_DEFICIENCY_ICD,
        report_specialties=_PED_ENDO_REPORT,
        prescriber_specialties=_PED_ENDO_PRESCRIBER,
        report_duration_months=12,
        message_tr=(
            "Pediatrik somatropin başlangıcı — çocuk endokrinoloji uzman hekiminin yer "
            "aldığı 1 yıllık sağlık kurulu raporu gerekir (§4.2.6.A-1)."
        ),
        gate_b_sources=["C003966", ],
    ),
    _rule(
        "4.2.6.pediatric_gh_renewal_board",
        "4.2.6.A-1",
        _SOMATROPIN,
        icd10_ranges=_GH_DEFICIENCY_ICD,
        report_specialties=_PED_ENDO_REPORT,
        report_duration_months=12,
        message_tr=(
            "Pediatrik büyüme hormonu yenileme — epifiz hatları açık hastalarda 1 yıllık "
            "sağlık kurulu raporu gerekir (§4.2.6.A-1)."
        ),
        gate_b_sources=["C003982"],
    ),
    _rule(
        "4.2.6.pws_somatropin_tertiary_board",
        "4.2.6.A-4",
        _SOMATROPIN,
        icd10_ranges=_PWS_ICD,
        report_specialties=_PED_ENDO_REPORT,
        prescriber_specialties=_PED_ENDO_PRESCRIBER,
        report_duration_months=3,
        message_tr=(
            "Prader-Willi sendromu somatropin — üçüncü basamak kurumda çocuk endokrinoloji "
            "uzman hekiminin yer aldığı 3 aylık sağlık kurulu raporu gerekir (§4.2.6.A-4)."
        ),
        gate_b_sources=["C004016"],
    ),
    _rule(
        "4.2.6.ckd_gh_nephro_endo_board",
        "4.2.6.A-5",
        _SOMATROPIN,
        icd10_ranges=_CKD_ICD,
        report_specialties=_CKD_REPORT,
        prescriber_specialties=_PED_ENDO_PRESCRIBER,
        report_duration_months=6,
        message_tr=(
            "KBY ilişkili büyüme bozukluğu somatropin — çocuk nefroloji ve çocuk "
            "endokrinoloji uzman hekimlerinin yer aldığı 6 aylık sağlık kurulu raporu "
            "gerekir (§4.2.6.A-5)."
        ),
        gate_b_sources=["C004030"],
    ),
    _rule(
        "4.2.6.laron_mecasermin_initiation_board",
        "4.2.6.B",
        _MECASERMIN,
        icd10_ranges=_LARON_ICD,
        report_specialties=_PED_ENDO_REPORT,
        prescriber_specialties=_PED_ENDO_PRESCRIBER,
        message_tr=(
            "Laron sendromu rhIGF-I (mecasermin) başlangıcı — çocuk endokrinoloji uzman "
            "hekiminin yer aldığı sağlık kurulu raporu ve reçete gerekir (§4.2.6.B)."
        ),
        gate_b_sources=["C004033"],
    ),
]
