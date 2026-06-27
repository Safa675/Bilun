"""R5 Epic A2 — Tier A pilot rules for §4.2.13 hepatitis + §4.2.16 special formulas."""

from __future__ import annotations

from typing import Any

_HBV = ["B16", "B18.0", "B18.1"]
_HCV_ACUTE = ["B17.1"]
_HCV_CHRONIC = ["B18.2"]
_METABOLIC = ["E70", "E71", "E72", "E74"]
_CF = ["E84"]
_CELIAC = ["K90.0"]

_GASTRO_INF_REPORT = ["gastroenteroloji", "enfeksiyon hastalıkları"]
_GASTRO_PULMO_REPORT = ["gastroenteroloji", "göğüs hastalıkları"]
_METABOLIC_REPORT = [
    "çocuk metabolizma",
    "metabolizma hastalıkları",
    "endokrinoloji",
    "gastroenteroloji",
]


def _rule(
    rule_id: str,
    sut_section: str,
    drug_names: list[str],
    *,
    icd10_ranges: list[str],
    message_tr: str,
    report_specialties: list[str] | None = None,
    icd10_codes: list[str] | None = None,
    batch: str = "A2",
    gate_b_sources: list[str],
    report_duration_months: int | None = None,
    prescriber_specialties: list[str] | None = None,
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
    if icd10_codes:
        payload["icd10_codes"] = icd10_codes
    if report_duration_months is not None:
        payload["report_duration_months"] = report_duration_months
    if prescriber_specialties:
        payload["prescriber_specialties"] = prescriber_specialties
    return payload


BATCH_A2_RULES: list[dict[str, Any]] = [
    _rule(
        "4.2.13.hepatitis_viral_gastro_inf_report",
        "4.2.13",
        ["hepatit", "viral hepatit"],
        icd10_ranges=["B15", "B16", "B17", "B18", "B19"],
        report_specialties=_GASTRO_INF_REPORT,
        prescriber_specialties=_GASTRO_INF_REPORT + ["çocuk sağlığı", "iç hastalıkları"],
        message_tr=(
            "Viral hepatit ilaçları — gastroenteroloji veya enfeksiyon hastalıkları "
            "uzman hekim ilaç kullanım raporu gerekir (§4.2.13)."
        ),
        gate_b_sources=["C004501"],
    ),
    _rule(
        "4.2.13.hbv_entekavir_board",
        "4.2.13.1",
        ["entekavir"],
        icd10_ranges=_HBV,
        message_tr="Entekavir — kronik HBV endikasyonu ve uzman hekim raporu gerekir (§4.2.13.1).",
        gate_b_sources=["C004572"],
    ),
    _rule(
        "4.2.13.hbv_tenofovir_board",
        "4.2.13.1",
        ["tenofovir"],
        icd10_ranges=_HBV,
        message_tr="Tenofovir — kronik HBV endikasyonu ve uzman hekim raporu gerekir (§4.2.13.1).",
        gate_b_sources=["C004572"],
    ),
    _rule(
        "4.2.13.hbv_lamivudin_board",
        "4.2.13.1",
        ["lamivudin"],
        icd10_ranges=_HBV,
        message_tr="Lamivudin — kronik HBV endikasyonu ve uzman hekim raporu gerekir (§4.2.13.1).",
        gate_b_sources=["C004572"],
    ),
    _rule(
        "4.2.13.hbv_oral_report_duration_6mo",
        "4.2.13.1",
        ["entekavir", "tenofovir", "lamivudin", "telbivudin"],
        icd10_ranges=_HBV,
        report_duration_months=6,
        message_tr=(
            "HBV oral antiviral — ilk rapor süresi en fazla 6 ay olmalıdır (§4.2.13.1)."
        ),
        gate_b_sources=["C004604"],
    ),
    _rule(
        "4.2.13.hcv_acute_interferon_report",
        "4.2.13.3.1",
        ["interferon", "pegile interferon", "peginterferon"],
        icd10_ranges=_HCV_ACUTE,
        message_tr=(
            "Akut hepatit C interferon tedavisi — gastroenteroloji/enfeksiyon "
            "uzman hekim raporu gerekir (§4.2.13.3.1)."
        ),
        gate_b_sources=["C004636", "C004637"],
    ),
    _rule(
        "4.2.13.hcv_ribavirin_combo_report",
        "4.2.13.E-2",
        ["ribavirin"],
        icd10_ranges=_HCV_CHRONIC + _HCV_ACUTE,
        message_tr=(
            "HCV ribavirin kombinasyonu — kronik hepatit C endikasyonu ve "
            "uzman hekim raporu gerekir (§4.2.13)."
        ),
        gate_b_sources=["C004641"],
    ),
    _rule(
        "4.2.13.hcv_sofosbuvir_ledipasvir_board",
        "4.2.13.3.2",
        ["sofosbuvir", "ledipasvir"],
        icd10_ranges=_HCV_CHRONIC,
        message_tr=(
            "Sofosbuvir/ledipasvir — kronik HCV endikasyonu ve gastroenteroloji/enfeksiyon "
            "uzman hekim raporu gerekir (§4.2.13.3.2)."
        ),
        gate_b_sources=["C004690", "C004897"],
    ),
    _rule(
        "4.2.13.hcv_glecaprevir_pibrentasvir_board",
        "4.2.13.3.2",
        ["glekaprevir", "pibrentasvir"],
        icd10_ranges=_HCV_CHRONIC,
        message_tr=(
            "Glekaprevir/pibrentasvir — kronik HCV endikasyonu ve uzman hekim raporu "
            "gerekir (§4.2.13.3.2)."
        ),
        gate_b_sources=["C004815"],
    ),
    _rule(
        "4.2.16.metabolic_formula_pediatric_report",
        "4.2.16",
        ["metabolik mama", "özel formül", "ozel formul", "fenilketonüri", "pku"],
        icd10_ranges=_METABOLIC,
        report_specialties=_METABOLIC_REPORT,
        prescriber_specialties=_METABOLIC_REPORT + ["çocuk sağlığı", "iç hastalıkları"],
        report_duration_months=36,
        message_tr=(
            "Doğuştan metabolik hastalık özel formülü — metabolizma/gastroenteroloji "
            "uzman hekim raporu gerekir (§4.2.16)."
        ),
        gate_b_sources=["C005983"],
    ),
    _rule(
        "4.2.16.protein_metabolism_formula_report",
        "4.2.16",
        ["özel formüllü un", "ozel formul", "aminoasit metabolizması"],
        icd10_ranges=_METABOLIC,
        report_specialties=_METABOLIC_REPORT,
        message_tr=(
            "Protein metabolizması bozukluğu özel formülü — uzman hekim raporu "
            "gerekir (§4.2.16)."
        ),
        gate_b_sources=["C005877", "C005993"],
    ),
    _rule(
        "4.2.16.cystic_fibrosis_formula_report",
        "4.2.16",
        ["kistik fibrozis", "modulen"],
        icd10_ranges=_CF,
        report_specialties=_GASTRO_PULMO_REPORT,
        message_tr=(
            "Kistik fibrozis özel maması — gastroenteroloji/göğüs hastalıkları "
            "uzman hekim raporu gerekir (§4.2.16)."
        ),
        gate_b_sources=["C005947", "C005999"],
    ),
    _rule(
        "4.2.16.celiac_gluten_free_report",
        "4.2.16",
        ["çölyak", "coelyak", "glutensiz"],
        icd10_ranges=_CELIAC,
        report_specialties=["gastroenteroloji"],
        message_tr=(
            "Çölyak hastalığı glutensiz ürün — gastroenteroloji uzman hekim raporu "
            "gerekir (§4.2.16)."
        ),
        gate_b_sources=["C006007"],
    ),
]
