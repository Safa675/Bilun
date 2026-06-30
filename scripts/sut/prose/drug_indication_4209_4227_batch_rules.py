"""R5 Epic A6 — Tier A pilot rules for §4.2.9 ESA / §4.2.27 coagulation factors."""

from __future__ import annotations

from typing import Any

_ESA_DRUGS = [
    "eritropoietin",
    "epoetin",
    "darbepoetin",
    "roksadustat",
    "aranesp",
    "binocrit",
    "eprex",
    "mircera",
    "retacrit",
    "neo recormon",
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
_HEMO_ICD = ["D66", "D67", "D68"]
_FACTOR_VIIA = ["faktör viia", "factor viia", "novoseven", "eptacog alfa"]
_APCC = ["feiba", "apcc", "aktifleştirilmiş protrombin", "activated prothrombin"]
_VWF = ["von willebrand", "wilate", "haemate", "vwf"]
_ANTI_RH_ICD = ["O26", "O03", "O04", "Z33", "Z34"]


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
    batch: str = "A6",
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


BATCH_A6_RULES: list[dict[str, Any]] = [
    _rule(
        "4.2.9.esa_ckd_monthly_nephrology_report",
        "4.2.9.A-1",
        _ESA_DRUGS,
        icd10_ranges=_CKD_ICD,
        report_required=True,
        report_specialties=_NEPHROLOGY_DIALYSIS,
        prescriber_specialties=_NEPHROLOGY_DIALYSIS,
        report_duration_months=1,
        message_tr=(
            "KBY anemisi ESA — ferritin/TSAT/Hb kriterleri, nefroloji/diyaliz uzman "
            "raporu; muadil ESA kullanımı; bir defada en fazla 1 aylık reçete (§4.2.9.A)."
        ),
        gate_b_sources=["C004127", "C004128", "C004130", "C004131"],
    ),
    _rule(
        "4.2.9.mds_esa_hematology_report",
        "4.2.9.A-2",
        ["eritropoietin", "epoetin", "darbepoetin", "aranesp", "binocrit"],
        icd10_ranges=_MDS_ICD,
        report_required=True,
        report_specialties=_HEMATOLOGY,
        prescriber_specialties=_HEMATOLOGY + ["iç hastalıkları"],
        message_tr=(
            "MDS anemisi ESA — Hb<11, blast <%5 ve sEPO<500 ile tedaviye başlanır; "
            "hematoloji uzman hekim raporu ve hemogram sonucu reçetede belirtilir (§4.2.9.A-2)."
        ),
        gate_b_sources=["C004135", "C004137"],
    ),
    _rule(
        "4.2.9.etelcalcetide_dialysis_ckd_only",
        "4.2.9.E",
        ["etelkalsedid", "etelcalcetide", "mimpara", "parsabiv"],
        icd10_ranges=_CKD_ICD,
        message_tr=(
            "Etelkalsedid — yalnızca hemodiyaliz KBY endikasyonunda karşılanır; "
            "paratiroid karsinomu, primer hiperparatiroidizm veya diyalizsiz KBY "
            "endikasyonlarında bedel karşılanmaz (§4.2.9.E)."
        ),
        gate_b_sources=["C004200"],
    ),
    _rule(
        "4.2.27.hemophilia_acute_bleed_report",
        "4.2.27.A",
        ["faktör viii", "faktör ix", "factor viii", "factor ix", "hemofil", "alfinity"],
        icd10_ranges=_HEMO_ICD,
        report_required=True,
        report_specialties=_HEMATOLOGY,
        message_tr=(
            "Hemofili akut kanama/cerrahi — 3 güne kadar süreli yeni hematoloji "
            "uzman hekim raporu gerekir (§4.2.27.A)."
        ),
        gate_b_sources=["C006227"],
    ),
    _rule(
        "4.2.27.hemophilia_emergency_one_day",
        "4.2.27.A",
        ["faktör viii", "faktör ix", "factor viii", "factor ix", "hemofil"],
        icd10_ranges=_HEMO_ICD,
        report_required=True,
        report_specialties=_HEMATOLOGY,
        message_tr=(
            "Hemofili acil müracaat — takip karnesi yoksa el yazısı ile belirtilerek "
            "en fazla 1 günlük doz ve hematoloji sevki (§4.2.27.A)."
        ),
        gate_b_sources=["C006228"],
    ),
    _rule(
        "4.2.27.factor_seven_a_bleeding_board",
        "4.2.27.A",
        _FACTOR_VIIA,
        icd10_ranges=_HEMO_ICD + ["D69"],
        report_required=True,
        report_specialties=_HEMATOLOGY,
        message_tr=(
            "Faktör VIIa kanama tedavisi — tanı, faktör ve inhibitör düzeyini gösteren "
            "hematoloji sağlık kurulu raporu gerekir (§4.2.27.A)."
        ),
        gate_b_sources=["C006232"],
    ),
    _rule(
        "4.2.27.factor_seven_a_prophylaxis_board",
        "4.2.27.A",
        _FACTOR_VIIA,
        icd10_ranges=_HEMO_ICD,
        report_required=True,
        report_specialties=_HEMATOLOGY,
        report_duration_months=3,
        message_tr=(
            "Faktör VIIa proflaksisi — inhibitörlü hemofili hastalarında 3 aya kadar "
            "süreli sağlık kurulu raporu gerekir (§4.2.27.A)."
        ),
        gate_b_sources=["C006233"],
    ),
    _rule(
        "4.2.27.anticoagulant_bleed_reversal_one_day",
        "4.2.27.A",
        [
            "protrombin kompleksi",
            "prothrombin complex",
            "beriplex",
            "octaplex",
            "k vitamini",
            "vitamin k",
            "konakion",
        ],
        icd10_ranges=["T45", "D68", "K72"],
        message_tr=(
            "Kumarin/NOAK kaynaklı aktif kanama — kanama yeri belirtilerek en fazla "
            "1 günlük doz ve hematoloji sevki (§4.2.27.A)."
        ),
        gate_b_sources=[],
    ),
    _rule(
        "4.2.27.apcc_bleeding_board",
        "4.2.27.A",
        _APCC,
        icd10_ranges=_HEMO_ICD,
        report_required=True,
        report_specialties=_HEMATOLOGY,
        message_tr=(
            "aPCC kanama tedavisi — tanı, faktör ve inhibitör düzeyini gösteren "
            "hematoloji sağlık kurulu raporu ile en fazla 3 günlük doz (§4.2.27.A)."
        ),
        gate_b_sources=["C006246"],
    ),
    _rule(
        "4.2.27.apcc_prophylaxis_board",
        "4.2.27.A",
        _APCC,
        icd10_ranges=_HEMO_ICD,
        report_required=True,
        report_specialties=_HEMATOLOGY,
        report_duration_months=6,
        message_tr=(
            "aPCC proflaksisi — FVIII inhibitör <5 BU oluncaya kadar haftalık "
            "4500 ünite sınırı; 6 aya kadar süreli sağlık kurulu raporu (§4.2.27.A)."
        ),
        gate_b_sources=["C006247"],
    ),
    _rule(
        "4.2.27.itt_tertiary_hematology_board",
        "4.2.27.A",
        ["faktör viii", "factor viii", "hemofil", "immun tolerans"],
        icd10_ranges=["D66"],
        report_required=True,
        report_specialties=_HEMATOLOGY,
        prescriber_specialties=_HEMATOLOGY,
        report_duration_months=6,
        message_tr=(
            "İmmün tolerans tedavisi — üçüncü basamak kurumda üç hematoloji uzmanının "
            "6 aya kadar süreli sağlık kurulu raporu; yalnızca hematoloji reçetesi (§4.2.27.A)."
        ),
        gate_b_sources=["C006249"],
    ),
    _rule(
        "4.2.27.itt_poor_response_exclusion",
        "4.2.27.A",
        ["faktör viii", "factor viii", "hemofil"],
        icd10_ranges=["D66"],
        report_required=True,
        report_specialties=_HEMATOLOGY,
        message_tr=(
            "İTT kötü yanıt kriterleri (inhibitör tanısı 5 yıl+ veya tepe titresi "
            ">200 BU/ml) — Kurumca karşılanmaz; raporda belirtilmeli (§4.2.27.A)."
        ),
        gate_b_sources=["C006250"],
    ),
    _rule(
        "4.2.27.vwf_factor_board_report",
        "4.2.27.A",
        _VWF,
        icd10_ranges=["D68.0", "D68"],
        report_required=True,
        report_specialties=_HEMATOLOGY,
        report_duration_months=12,
        message_tr=(
            "Von Willebrand faktör — tanı ve faktör düzeyini gösteren 1 yıllık "
            "hematoloji sağlık kurulu raporu gerekir (§4.2.27.A)."
        ),
        gate_b_sources=["C006255"],
    ),
    _rule(
        "4.2.27.anti_rh_specialist_prescription",
        "4.2.27.B",
        ["anti rh", "anti-rh", "rho(d)", "micrhogam", "winrho", "rhogam"],
        icd10_ranges=_ANTI_RH_ICD,
        message_tr=(
            "Anti-Rh — doğum sonu, düşük, küretaj, antenatal veya 28. gebelik haftasında "
            "uzman hekim reçetesi gerekir (§4.2.27.B)."
        ),
        gate_b_sources=["C006267", "C006268"],
    ),
]
