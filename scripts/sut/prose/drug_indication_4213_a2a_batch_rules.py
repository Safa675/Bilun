"""R5 Epic A2a — Tier A tail rules for §4.2.13 viral hepatitis (hepatitis continuation batch)."""

from __future__ import annotations

from typing import Any

_HBV = ["B16", "B18.0", "B18.1"]
_HCV_ACUTE = ["B17.1"]
_HCV_CHRONIC = ["B18.2"]
_HDV = ["B18.0", "B17.0"]

_GASTRO_INF_REPORT = ["gastroenteroloji", "enfeksiyon hastalıkları"]
_GASTRO_INF_PED = _GASTRO_INF_REPORT + ["çocuk sağlığı", "iç hastalıkları"]

_HBV_ORAL = ["entekavir", "tenofovir", "lamivudin", "telbivudin", "adefovir"]
_INTERFERON = ["interferon", "pegile interferon", "peginterferon", "pegasys", "peg intron"]
_RIBAVIRIN = ["ribavirin", "rebetol", "copegus"]
_DAA = [
    "sofosbuvir",
    "ledipasvir",
    "velpatasvir",
    "glekaprevir",
    "pibrentasvir",
    "daklatasvir",
    "simeprevir",
    "ombitasvir",
    "paritaprevir",
    "dasabuvir",
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
    report_duration_months: int | None = None,
    batch: str = "A2a",
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "rule_id": rule_id,
        "sut_section": sut_section,
        "drug_names": drug_names,
        "icd10_ranges": icd10_ranges,
        "report_required": True,
        "report_specialties": report_specialties or _GASTRO_INF_REPORT,
        "message_tr": message_tr,
        "encode_batch": batch,
        "gate_b_sources": gate_b_sources,
    }
    if prescriber_specialties:
        payload["prescriber_specialties"] = prescriber_specialties
    if report_duration_months is not None:
        payload["report_duration_months"] = report_duration_months
    return payload


BATCH_A2A_RULES: list[dict[str, Any]] = [
    _rule(
        "4.2.13.hepatitis_prior_therapy_documentation",
        "4.2.13",
        _HBV_ORAL + _INTERFERON + _RIBAVIRIN + _DAA,
        icd10_ranges=["B15", "B16", "B17", "B18", "B19"],
        message_tr=(
            "Hepatit tedavisi — önceki ilaçlar, tanı ve tedavi başlama/kesilme kriterleri "
            "raporda belirtilmelidir; oral antiviral ilk rapor en fazla 6 ay (§4.2.13)."
        ),
        gate_b_sources=["C004506"],
    ),
    _rule(
        "4.2.13.hbv_dna_initiation_board",
        "4.2.13.1",
        _HBV_ORAL,
        icd10_ranges=_HBV,
        prescriber_specialties=_GASTRO_INF_PED,
        message_tr=(
            "HBV oral antiviral başlangıcı — HBV DNA ≥10.000 kopya/ml ve biyopsi sonuçları "
            "rapor ekinde belirtilmelidir (§4.2.13.1)."
        ),
        gate_b_sources=["C004514", "C004535"],
    ),
    _rule(
        "4.2.13.hbv_immunosuppression_lamivudin_prophylaxis",
        "4.2.13.1.2",
        ["lamivudin", "entekavir", "tenofovir"],
        icd10_ranges=_HBV,
        report_duration_months=12,
        message_tr=(
            "HBsAg(+) immünsupresif/kemoterapi/monoklonal antikor tedavisi — lamivudin profilaksisi "
            "tedavi süresince ve sonrası en fazla 12 ay rapor gerekir (§4.2.13.1.2)."
        ),
        gate_b_sources=["C004614"],
    ),
    _rule(
        "4.2.13.hdv_interferon_board",
        "4.2.13.2",
        _INTERFERON + _HBV_ORAL,
        icd10_ranges=_HDV + _HBV,
        prescriber_specialties=_GASTRO_INF_REPORT,
        message_tr=(
            "HDV(+) kronik hepatit B — interferon/pegile interferon; anti-HDV ve HBV DNA "
            "reçete/raporda belirtilmelidir (§4.2.13.2)."
        ),
        gate_b_sources=["C004628"],
    ),
    _rule(
        "4.2.13.hcv_acute_interferon_24w_monotherapy",
        "4.2.13.E-1",
        _INTERFERON,
        icd10_ranges=_HCV_ACUTE,
        report_duration_months=24,
        message_tr=(
            "Akut hepatit C — HCV RNA pozitif raporda belirtilerek 24 hafta interferon "
            "monoterapisi; ribavirin eklenmez (§4.2.13.E-1)."
        ),
        gate_b_sources=["C004634"],
    ),
    _rule(
        "4.2.13.hcv_ribavirin_genotype_duration",
        "4.2.13.E-2",
        _RIBAVIRIN + _INTERFERON,
        icd10_ranges=_HCV_CHRONIC,
        report_duration_months=48,
        message_tr=(
            "HCV ribavirin kombinasyonu — genotip 1/4 için 48 hafta; 12. hafta HCV RNA "
            "2 log azalmama halinde süre sınırı uygulanır (§4.2.13.E-2)."
        ),
        gate_b_sources=["C004642"],
    ),
    _rule(
        "4.2.13.hcv_daa_tertiary_gastro_once",
        "4.2.13.3.2",
        _DAA,
        icd10_ranges=_HCV_CHRONIC,
        prescriber_specialties=_GASTRO_INF_PED,
        message_tr=(
            "HCV DAA — üçüncü basamak kurumda gastroenteroloji/enfeksiyon uzman raporu ve "
            "tedavi şeması; bir defaya mahsus (§4.2.13.3.2)."
        ),
        gate_b_sources=["C004679"],
    ),
    _rule(
        "4.2.13.hcv_daa_child_pugh_report",
        "4.2.13.3.2",
        _DAA,
        icd10_ranges=_HCV_CHRONIC,
        prescriber_specialties=_GASTRO_INF_PED,
        message_tr=(
            "HCV DAA — Child-Pugh sınıflamasını kanıtlayıcı belgeler ve tedavi şeması "
            "üçüncü basamak uzman hekim raporunda belirtilmelidir (§4.2.13.3.2)."
        ),
        gate_b_sources=["C004814"],
    ),
    _rule(
        "4.2.13.hcv_specialist_report_criteria",
        "4.2.13.3.2",
        _DAA + _INTERFERON + _RIBAVIRIN,
        icd10_ranges=_HCV_CHRONIC + _HCV_ACUTE,
        prescriber_specialties=_GASTRO_INF_REPORT,
        message_tr=(
            "HCV uzman hekim raporu — HCV RNA, siroz durumu, Child-Pugh B/C kanıtı, "
            "genotip ve önceki tedaviler belirtilmelidir (§4.2.13.3.2)."
        ),
        gate_b_sources=["C004898"],
    ),
    _rule(
        "4.2.13.hcv_reteatment_prior_therapy_report",
        "4.2.13.3.2.A",
        _INTERFERON + _RIBAVIRIN + ["boceprevir", "telaprevir"],
        icd10_ranges=_HCV_CHRONIC,
        message_tr=(
            "HCV yeniden tedavi — önceki peginterferon/ribavirin/PI deneyimi "
            "sağlık raporunda belirtilmelidir (§4.2.13.3.2.A)."
        ),
        gate_b_sources=["C004760", "C004851"],
    ),
    _rule(
        "4.2.13.hcv_genotype_b_48w_monitoring",
        "4.2.13.3.2.B",
        _INTERFERON + _RIBAVIRIN,
        icd10_ranges=_HCV_CHRONIC,
        report_duration_months=48,
        message_tr=(
            "HCV genotip 1/4 peginterferon+ribavirin — 48 hafta tedavi; 12. hafta HCV RNA "
            "monitoring ve erken kesme kriterleri raporda belirtilmelidir (§4.2.13.3.2.B)."
        ),
        gate_b_sources=["C004724", "C004795"],
    ),
    _rule(
        "4.2.13.hcv_pediatric_early_stop_rechallenge",
        "4.2.13.3.2.B",
        _INTERFERON + _RIBAVIRIN,
        icd10_ranges=_HCV_CHRONIC,
        report_specialties=_GASTRO_INF_PED,
        prescriber_specialties=_GASTRO_INF_PED,
        message_tr=(
            "Pediatrik kronik HCV — 12. haftadan önce komplikasyonla kesilen interferon+ribavirin "
            "tedavisi yeniden başlatma kuralları (§4.2.13.3.2.B)."
        ),
        gate_b_sources=["C004916"],
    ),
]
