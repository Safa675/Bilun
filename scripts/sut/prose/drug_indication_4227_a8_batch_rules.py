"""R5 Epic A8 — Tier A continuation rules for §4.2.27 coagulation / albumin."""

from __future__ import annotations

from typing import Any

_HEMATOLOGY = ["hematoloji"]
_INTERNAL_PEDIATRICS = ["iç hastalıkları", "çocuk sağlığı"]
_FACTOR_PRESCRIBERS = _HEMATOLOGY + _INTERNAL_PEDIATRICS
_HEMO_ICD = ["D66", "D67", "D68"]
_COAG_ICD = _HEMO_ICD + ["D69"]
_FACTOR_DRUGS = [
    "faktör viii",
    "faktör ix",
    "factor viii",
    "factor ix",
    "hemofil",
    "alfinity",
    "koagulasyon faktörü",
]
_PCC = [
    "protrombin kompleksi",
    "prothrombin complex",
    "beriplex",
    "octaplex",
    "kombine koagülasyon",
    "k vitamini",
    "vitamin k",
    "konakion",
]
_VWF = ["von willebrand", "wilate", "haemate", "vwf"]
_EMICIZUMAB = ["emicizumab", "hemlibra"]
_ALBUMIN = ["human albumin", "human albümin", "albümin", "albumin", "albutein"]
_HYPOALB_ICD = ["E86", "R77", "K70", "N04", "R63"]


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
    inpatient_only: bool = False,
    batch: str = "A8",
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
    if inpatient_only:
        payload["inpatient_only"] = True
    return payload


BATCH_A8_RULES: list[dict[str, Any]] = [
    _rule(
        "4.2.27.coagulation_factor_board_report",
        "4.2.27.A",
        _FACTOR_DRUGS,
        icd10_ranges=_COAG_ICD,
        report_required=True,
        report_specialties=_HEMATOLOGY,
        prescriber_specialties=_FACTOR_PRESCRIBERS,
        message_tr=(
            "Koagülasyon faktörü — tanı, faktör ve inhibitör düzeyini gösteren hematoloji "
            "sağlık kurulu raporu; hematoloji/iç hastalıkları/çocuk sağlığı uzman reçetesi "
            "(§4.2.27.A)."
        ),
        gate_b_sources=["C006215"],
    ),
    _rule(
        "4.2.27.prophylaxis_acute_bleed_3day_report",
        "4.2.27.A",
        _FACTOR_DRUGS,
        icd10_ranges=_HEMO_ICD,
        report_required=True,
        report_specialties=_HEMATOLOGY,
        message_tr=(
            "Proflaksi hastasında akut kanama/cerrahi — 3 güne kadar süreli yeni hematoloji "
            "uzman hekim raporu gerekir (§4.2.27.A)."
        ),
        gate_b_sources=["C006217"],
    ),
    _rule(
        "4.2.27.coagulation_emergency_one_day",
        "4.2.27.A",
        _FACTOR_DRUGS,
        icd10_ranges=_HEMO_ICD,
        report_required=True,
        report_specialties=_HEMATOLOGY,
        message_tr=(
            "Koagülasyon faktörü acil müracaat — takip karnesi yoksa el yazısı ile belirtilerek "
            "en fazla 1 günlük doz ve hematoloji sevki (§4.2.27.A)."
        ),
        gate_b_sources=["C006218"],
    ),
    _rule(
        "4.2.27.pcc_acquired_coagulopathy_board",
        "4.2.27.A",
        _PCC,
        icd10_ranges=_COAG_ICD,
        report_required=True,
        report_specialties=_HEMATOLOGY,
        message_tr=(
            "Kombine koagülasyon faktörü/protrombin kompleksi — kazanılmış koagülasyon "
            "bozukluğunda tanı ve faktör düzeyini gösteren hematoloji sağlık kurulu raporu "
            "ile bir dozda reçete (§4.2.27.A)."
        ),
        gate_b_sources=["C006220"],
    ),
    _rule(
        "4.2.27.coumarin_active_bleed_one_day",
        "4.2.27.A",
        _PCC,
        icd10_ranges=["T45", "D68", "K72"],
        message_tr=(
            "Kumarin kaynaklı aktif kanama — kanama yeri belirtilerek uzman hekimlerce "
            "en fazla 1 günlük doz; idame yalnızca hematoloji uzman hekimlerince (§4.2.27.A)."
        ),
        gate_b_sources=["C006222"],
    ),
    _rule(
        "4.2.27.factor_annual_board_report",
        "4.2.27.A",
        _FACTOR_DRUGS,
        icd10_ranges=_COAG_ICD,
        report_required=True,
        report_specialties=_HEMATOLOGY,
        prescriber_specialties=_FACTOR_PRESCRIBERS,
        report_duration_months=12,
        message_tr=(
            "Koagülasyon faktörü — 1 yıllık sağlık kurulu raporu; ilk rapor üçüncü basamak "
            "resmi sağlık kurumunda düzenlenmeli (§4.2.27.A)."
        ),
        gate_b_sources=["C006225"],
    ),
    _rule(
        "4.2.27.vwf_weekly_unit_cap_board",
        "4.2.27.A",
        _VWF + ["faktör viii", "factor viii"],
        icd10_ranges=["D68.0", "D68"],
        report_required=True,
        report_specialties=_HEMATOLOGY,
        report_duration_months=6,
        message_tr=(
            "Von Willebrand/ağır profilaksi — haftalık faktör kullanımı 4500 üniteyi geçemez; "
            "aşım gerekçeleri 6 aya kadar süreli yeni raporda belirtilir (§4.2.27.A)."
        ),
        gate_b_sources=["C006256"],
    ),
    _rule(
        "4.2.27.vwf_acute_bleed_3day_report",
        "4.2.27.A",
        _VWF,
        icd10_ranges=["D68.0", "D68"],
        report_required=True,
        report_specialties=_HEMATOLOGY,
        message_tr=(
            "Von Willebrand akut kanama/cerrahi — 3 güne kadar süreli yeni hematoloji "
            "uzman hekim raporu gerekir (§4.2.27.A)."
        ),
        gate_b_sources=["C006257"],
    ),
    _rule(
        "4.2.27.emicizumab_hematology_monthly_prescription",
        "4.2.27.A",
        _EMICIZUMAB,
        icd10_ranges=["D66"],
        report_required=True,
        report_specialties=_HEMATOLOGY,
        prescriber_specialties=_HEMATOLOGY,
        report_duration_months=3,
        message_tr=(
            "Emicizumab — 3 ay süreli sağlık kurulu raporu; yalnızca hematoloji uzman "
            "reçetesi; ilk 3 aylık tedavi birer aylık dozda reçetelenir (§4.2.27.A)."
        ),
        gate_b_sources=["C006264"],
    ),
    _rule(
        "4.2.27.human_albumin_inpatient_hypoalbuminemia",
        "4.2.27.Ç",
        _ALBUMIN,
        icd10_ranges=_HYPOALB_ICD,
        inpatient_only=True,
        message_tr=(
            "Human albümin — yalnızca yatarak tedavi gören hastalarda albümin ≤2.5 g/dl "
            "için uzman hekim reçetesi; laboratuvar sonuçları epikrizde belirtilir (§4.2.27.Ç)."
        ),
        gate_b_sources=["C006274"],
    ),
]
