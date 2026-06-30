"""R5 Epic Tier B — §4.2.27 coagulation prescribing, K-vitamin antagonist, pediatric dosing."""

from __future__ import annotations

from typing import Any

_HEMATOLOGY = ["hematoloji"]
_INTERNAL_PEDIATRICS = ["iç hastalıkları", "çocuk sağlığı"]
_FACTOR_PRESCRIBERS = _HEMATOLOGY + _INTERNAL_PEDIATRICS
_HEMO_ICD = ["D66", "D67", "D68"]
_COAG_ICD = _HEMO_ICD + ["D69"]
_ITP_ICD = ["D69.3", "D69"]

_FACTOR_DRUGS = [
    "faktör viii",
    "faktör ix",
    "factor viii",
    "factor ix",
    "hemofil",
    "alfinity",
    "koagulasyon faktörü",
    "kan ürünü",
]
_FACTOR_VIIA = ["faktör viia", "factor viia", "novoseven", "eptacog alfa"]
_PCC = [
    "protrombin kompleksi",
    "prothrombin complex",
    "beriplex",
    "octaplex",
    "kombine koagülasyon",
    "k vitamini",
    "vitamin k",
    "konakion",
    "fitomenadion",
]
_ELTROMBOPAG = ["eltrombopag", "revolade", "promacta"]


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
    batch: str = "4227-TierB",
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
    if prescriber_specialties:
        payload["prescriber_specialties"] = prescriber_specialties
    return payload


BATCH_4227_TIER_B_RULES: list[dict[str, Any]] = [
    _rule(
        "4.2.27.coagulation_prescribing_principles_header",
        "4.2.27",
        _FACTOR_DRUGS + _FACTOR_VIIA + _PCC,
        icd10_ranges=_COAG_ICD,
        report_required=True,
        report_specialties=_HEMATOLOGY,
        prescriber_specialties=_FACTOR_PRESCRIBERS,
        message_tr=(
            "Faktör ve diğer kan ürünleri — reçete edilme ilkelerine uygun hematoloji "
            "sağlık kurulu raporu ve uzman reçetesi gerekir (§4.2.27)."
        ),
        gate_b_sources=["C006210"],
    ),
    _rule(
        "4.2.27.factor_viia_dose_limited_board",
        "4.2.27.A",
        _FACTOR_VIIA,
        icd10_ranges=_COAG_ICD,
        report_required=True,
        report_specialties=_HEMATOLOGY,
        message_tr=(
            "Faktör VIIa — tanı, faktör ve inhibitör düzeyini gösteren hematoloji sağlık "
            "kurulu raporu; hafif-orta kanamada 3 doza, şiddetli kanama/cerrahide 12 doza "
            "kadar uzman reçetesi (§4.2.27.A (3))."
        ),
        gate_b_sources=[],
    ),
    _rule(
        "4.2.27.coagulopathy_hospital_one_day_prescriber",
        "4.2.27.A",
        _FACTOR_DRUGS + _PCC,
        icd10_ranges=_COAG_ICD,
        report_required=True,
        report_specialties=_HEMATOLOGY,
        prescriber_specialties=_FACTOR_PRESCRIBERS,
        message_tr=(
            "Konjenital/kazanılmış koagülasyon bozukluğu — hematoloji sağlık kurulu raporuna "
            "dayanılarak hematoloji reçetesi; hematolog yoksa iç hastalıkları/çocuk sağlığı "
            "uzmanı bir günlük dozda reçete edebilir (§4.2.27.A a)."
        ),
        gate_b_sources=["C006235"],
    ),
    _rule(
        "4.2.27.vitamin_k_acquired_coagulopathy_referral",
        "4.2.27.A",
        _PCC,
        icd10_ranges=["K72", "D68", "T45"],
        message_tr=(
            "Kazanılmış koagülasyon bozukluğu (K vitamini yetersizliği, karaciğer yetmezliği) — "
            "kanama yeri belirtilerek en fazla bir günlük doz ve hematoloji sevki "
            "(§4.2.27.A (2))."
        ),
        gate_b_sources=["C006244"],
    ),
    _rule(
        "4.2.27.vitamin_k_emergency_one_day_no_report",
        "4.2.27.A",
        _PCC,
        icd10_ranges=["K72", "D68", "T45"],
        message_tr=(
            "Kazanılmış koagülasyon acil kanama — yatan veya ayaktan acil müracaatta rapor "
            "aranmaksızın en fazla bir günlük doz; idame hematoloji raporu ile (§4.2.27.A (2))."
        ),
        gate_b_sources=["C006244"],
    ),
    _rule(
        "4.2.27.eltrombopag_pediatric_dosing_report",
        "4.2.27.D",
        _ELTROMBOPAG,
        icd10_ranges=_ITP_ICD,
        report_required=True,
        report_specialties=_HEMATOLOGY + ["çocuk hematolojisi"],
        prescriber_specialties=_HEMATOLOGY + ["çocuk hematolojisi"],
        message_tr=(
            "Eltrombopag ITP — pediatrik başlangıç dozu 1-5 yaş 25 mg, 6-17 yaş/erişkin 50 mg; "
            "doz değişikliklerinde trombosit sayısı raporda belirtilir (§4.2.27.D (2))."
        ),
        gate_b_sources=["C006287"],
    ),
]
