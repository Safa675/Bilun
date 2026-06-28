"""R5 Epic A24 — Tier A pilot rules for §4.2.24 asthma / COPD / allergy indications."""

from __future__ import annotations

from typing import Any

_ASTHMA_ICD = ["J45", "J46"]
_COPD_ICD = ["J44"]
_ALLERGY_ICD = ["J30"]
_RESPIRATORY_ICD = _ASTHMA_ICD + _COPD_ICD + _ALLERGY_ICD
_PULM_PRESCRIBER = [
    "göğüs hastalıkları",
    "göğüs cerrahisi",
    "alerji",
    "iç hastalıkları",
    "çocuk sağlığı",
]
_ALLERGY_PRESCRIBER = [
    "iç hastalıkları",
    "çocuk sağlığı",
    "göğüs hastalıkları",
    "alerji",
]
_ENT_PRESCRIBER = [
    "kulak burun boğaz",
    "iç hastalıkları",
    "çocuk sağlığı",
    "göğüs hastalıkları",
    "alerji",
]
_BIOLOGIC_REPORT = [
    "alerji",
    "immünoloji",
    "göğüs hastalıkları",
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
    batch: str = "A24",
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


BATCH_A24_RULES: list[dict[str, Any]] = [
    _rule(
        "4.2.24.formeterol_salmeterol_prescriber",
        "4.2.24.A",
        ["formeterol", "salmeterol", "vilanterol", "seretide", "symbicort"],
        icd10_ranges=_RESPIRATORY_ICD,
        prescriber_specialties=_PULM_PRESCRIBER,
        message_tr=(
            "Formeterol/salmeterol/vilanterol — göğüs hastalıkları, göğüs cerrahisi, alerji, "
            "iç hastalıkları veya çocuk sağlığı uzman hekim reçetesi gerekir; uzman raporu "
            "ile devam reçetesi diğer hekimlere açılır (§4.2.24.A-1)."
        ),
        gate_b_sources=["C006124"],
    ),
    _rule(
        "4.2.24.montelukast_prescriber_report",
        "4.2.24.A",
        ["montelukast", "zafirlukast", "singulair"],
        icd10_ranges=_ASTHMA_ICD + _ALLERGY_ICD,
        prescriber_specialties=_ALLERGY_PRESCRIBER,
        message_tr=(
            "Montelukast/zafirlukast — iç hastalıkları, çocuk sağlığı, göğüs hastalıkları "
            "veya alerji uzman hekim reçetesi veya uzman hekim raporu gerekir (§4.2.24.A-2)."
        ),
        gate_b_sources=["C006125"],
    ),
    _rule(
        "4.2.24.biologic_tertiary_board",
        "4.2.24.A",
        ["mepolizumab", "benralizumab", "nucala", "fasenra"],
        icd10_ranges=_ASTHMA_ICD,
        report_specialties=_BIOLOGIC_REPORT,
        prescriber_specialties=["göğüs hastalıkları", "alerji", "immünoloji"],
        message_tr=(
            "Mepolizumab/benralizumab — üçüncü basamak kurumda alerji/immünoloji uzmanının "
            "yer aldığı sağlık kurulu raporu ve göğüs hastalıkları/alerji reçetesi gerekir "
            "(§4.2.24.A-3)."
        ),
        gate_b_sources=["C006142"],
    ),
    _rule(
        "4.2.24.copd_inhaler_prescriber",
        "4.2.24.B",
        [
            "formeterol",
            "salmeterol",
            "indakaterol",
            "tiotropium",
            "glikopironyum",
            "vilanterol",
            "umeklidinyum",
            "olodaterol",
            "beclometazon",
            "flutikazon",
            "budesonid",
        ],
        icd10_ranges=_COPD_ICD + _ASTHMA_ICD,
        prescriber_specialties=_PULM_PRESCRIBER,
        message_tr=(
            "KOAH/astım inhale kombinasyonları — göğüs hastalıkları, göğüs cerrahisi, iç "
            "hastalıkları veya çocuk sağlığı uzman hekim reçetesi gerekir (§4.2.24.B-1)."
        ),
        gate_b_sources=["C006160"],
    ),
    _rule(
        "4.2.24.montelukast_antihistamine_combo",
        "4.2.24.C",
        ["montelukast", "antihistaminik", "singulair"],
        icd10_ranges=_ALLERGY_ICD + _ASTHMA_ICD,
        prescriber_specialties=_ENT_PRESCRIBER,
        message_tr=(
            "Montelukast+antihistaminik kombinasyonları — KBB, iç hastalıkları, çocuk "
            "sağlığı, göğüs hastalıkları veya alerji uzman reçetesi/raporu gerekir "
            "(§4.2.24.C-1)."
        ),
        gate_b_sources=["C006184"],
    ),
    _rule(
        "4.2.24.nasal_cs_pediatric_prescriber",
        "4.2.24.Ç",
        [
            "nasal kortikosteroid",
            "flutikazon",
            "mometazon",
            "budesonid",
            "avamys",
            "nasonex",
        ],
        icd10_ranges=_ALLERGY_ICD,
        prescriber_specialties=[
            "çocuk sağlığı",
            "alerji",
            "klinik immünoloji",
            "kulak burun boğaz",
            "aile hekimliği",
        ],
        message_tr=(
            "Nasal kortikosteroid — 2-5 yaş grubunda yalnızca çocuk sağlığı, alerji, klinik "
            "immünoloji, KBB veya aile hekimliği uzman reçetesi gerekir (§4.2.24.Ç-1)."
        ),
        gate_b_sources=["C006192"],
    ),
    _rule(
        "4.2.24.laba_lama_ics_triple_prior",
        "4.2.24.B",
        [
            "indakaterol",
            "glikopironyum",
            "flutikazon",
            "vilanterol",
            "umeklidinyum",
            "trelegy",
            "trimbow",
        ],
        icd10_ranges=_COPD_ICD,
        report_specialties=_PULM_PRESCRIBER,
        report_duration_months=3,
        message_tr=(
            "LABA+LAMA+İKS üçlü kombinasyon — en az 3 ay İKS+LABA veya İKS+LAMA sonrası "
            "göğüs hastalıkları uzman sağlık kurulu raporu gerekir (§4.2.24.B-4)."
        ),
        gate_b_sources=["C006171"],
    ),
    _rule(
        "4.2.24.laba_mono_invalid_prescription",
        "4.2.24.B",
        [
            "formeterol",
            "salmeterol",
            "indakaterol",
            "vilanterol",
            "tiotropium",
            "glikopironyum",
            "olodaterol",
        ],
        icd10_ranges=_COPD_ICD + _ASTHMA_ICD,
        report_required=False,
        message_tr=(
            "LABA/LAMA/İKS mono veya sabit doz dışı kombinasyon reçetesi — bedel "
            "karşılanmaz (§4.2.24.B-7)."
        ),
        gate_b_sources=["C006174"],
    ),
]
