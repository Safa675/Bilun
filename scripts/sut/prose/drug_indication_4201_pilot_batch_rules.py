"""R5 Epic A1 — Tier A pilot rules for §4.2.1 rheumatology / biologic indication (INN+ICD+report)."""

from __future__ import annotations

from typing import Any

_RA = ["M05", "M06"]
_PSA = ["L40.5"]
_AS = ["M45"]
_CROHN = ["K50"]
_UC = ["K51"]
_UVEITIS = ["H20", "H30"]

_ROMATO_REPORT = [
    "iç hastalıkları",
    "romatoloji",
    "fiziksel tıp",
    "klinik immunoloji",
    "çocuk sağlığı",
]
_GASTRO_REPORT = ["gastroenteroloji", "genel cerrahi", "iç hastalıkları"]
_OPHTHAL_REPORT = ["göz hastalıkları"]


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
    batch: str = "A1",
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "rule_id": rule_id,
        "sut_section": sut_section,
        "drug_names": drug_names,
        "icd10_ranges": icd10_ranges,
        "report_required": True,
        "report_specialties": report_specialties or _ROMATO_REPORT,
        "message_tr": message_tr,
        "encode_batch": batch,
        "gate_b_sources": gate_b_sources,
    }
    if prescriber_specialties:
        payload["prescriber_specialties"] = prescriber_specialties
    if report_duration_months is not None:
        payload["report_duration_months"] = report_duration_months
    return payload


BATCH_A1_RULES: list[dict[str, Any]] = [
    _rule(
        "4.2.1.leflunomid_ra_psa_report",
        "4.2.1.A",
        ["leflunomid", "arava"],
        icd10_ranges=_RA + _PSA,
        prescriber_specialties=_ROMATO_REPORT,
        message_tr=(
            "Leflunomid — romatoid/psoriatik artritte sulfasalazin veya methotrexat "
            "yetersiz/kontrendike olduğunda uzman hekim raporu gerekir (§4.2.1.A)."
        ),
        gate_b_sources=["C003563"],
    ),
    _rule(
        "4.2.1.gold_preparations_ra_report",
        "4.2.1.B",
        ["altın preparat", "gold", "aurothiomalate", "sodyum aurotiyomalat"],
        icd10_ranges=_RA,
        prescriber_specialties=["fiziksel tıp", "klinik immunoloji", "romatoloji"],
        report_duration_months=12,
        message_tr=(
            "Altın preparatları — romatoid artritte DMARD yetersizliğinde bir yıllık "
            "uzman hekim raporu gerekir (§4.2.1.B)."
        ),
        gate_b_sources=["C003565"],
    ),
    _rule(
        "4.2.1.anti_tnf_prescriber_board",
        "4.2.1.C-1",
        [
            "infliksimab",
            "adalimumab",
            "etanersept",
            "golimumab",
            "sertolizumab",
            "certolizumab",
            "remicade",
            "humira",
            "enbrel",
        ],
        icd10_ranges=_RA,
        prescriber_specialties=_ROMATO_REPORT,
        report_duration_months=6,
        message_tr=(
            "Anti-TNF ilaçlar — romatoid artritte romatoloji/klinik immunoloji/fiziksel "
            "tıp uzmanının yer aldığı en fazla 6 aylık sağlık kurulu raporu gerekir (§4.2.1.C-1)."
        ),
        gate_b_sources=["C003622"],
    ),
    _rule(
        "4.2.1.inflix_cert_gol_ra_second_line",
        "4.2.1.C-1",
        ["infliksimab", "golimumab", "sertolizumab", "certolizumab"],
        icd10_ranges=_RA,
        report_duration_months=3,
        message_tr=(
            "İnfliksimab/golimumab/sertolizumab — diğer anti-TNF yetersiz romatoid artritte "
            "3 ay süreli sağlık kurulu raporu gerekir (§4.2.1.C-1)."
        ),
        gate_b_sources=["C003591"],
    ),
    _rule(
        "4.2.1.anti_tnf_axial_as_board",
        "4.2.1.C-1",
        ["infliksimab", "golimumab", "sertolizumab", "certolizumab"],
        icd10_ranges=_AS,
        report_duration_months=3,
        message_tr=(
            "Anti-TNF — aksiyel tutulumlu ankilozan spondilitte 3 ay süreli "
            "sağlık kurulu raporu gerekir (§4.2.1.C-1)."
        ),
        gate_b_sources=["C003609"],
    ),
    _rule(
        "4.2.1.anti_tnf_peripheral_as_board",
        "4.2.1.C-1",
        ["infliksimab", "adalimumab", "etanersept", "golimumab", "sertolizumab"],
        icd10_ranges=_AS,
        report_duration_months=3,
        message_tr=(
            "Anti-TNF — periferik eklem tutulumlu ankilozan spondilitte 3 ay süreli "
            "sağlık kurulu raporu gerekir (§4.2.1.C-1)."
        ),
        gate_b_sources=["C003610"],
    ),
    _rule(
        "4.2.1.anti_tnf_psoriatic_arthritis_board",
        "4.2.1.C-1",
        ["infliksimab", "adalimumab", "etanersept", "golimumab", "sertolizumab"],
        icd10_ranges=_PSA,
        message_tr=(
            "Anti-TNF — psöriyatik artritte DMARD yetersizliğinde sağlık kurulu "
            "raporu gerekir (§4.2.1.C-1)."
        ),
        gate_b_sources=["C003617"],
    ),
    _rule(
        "4.2.1.adalimumab_crohn_adult_board",
        "4.2.1.C-1",
        ["adalimumab", "infliksimab", "sertolizumab", "humira", "remicade"],
        icd10_ranges=_CROHN,
        report_specialties=_GASTRO_REPORT,
        prescriber_specialties=_GASTRO_REPORT,
        report_duration_months=4,
        message_tr=(
            "Adalimumab/infliksimab/sertolizumab — yetişkin Crohn hastalığında "
            "4 ay süreli sağlık kurulu raporu gerekir (§4.2.1.C-1)."
        ),
        gate_b_sources=["C003629"],
    ),
    _rule(
        "4.2.1.adalimumab_uveitis_adult_board",
        "4.2.1.C-1",
        ["adalimumab", "humira"],
        icd10_ranges=_UVEITIS,
        report_specialties=_OPHTHAL_REPORT,
        prescriber_specialties=_OPHTHAL_REPORT,
        report_duration_months=3,
        message_tr=(
            "Adalimumab — yetişkin non-enfeksiyöz üveitte 3 ay süreli sağlık kurulu "
            "raporu gerekir (§4.2.1.C-1)."
        ),
        gate_b_sources=["C003634"],
    ),
    _rule(
        "4.2.1.abatacept_ra_board",
        "4.2.1.C-2",
        ["abatasept", "abatacept", "orencia"],
        icd10_ranges=_RA,
        prescriber_specialties=["romatoloji", "klinik immunoloji", "fiziksel tıp"],
        message_tr=(
            "Abatasept — anti-TNF yetersiz/kontrendike aktif romatoid artritte "
            "sağlık kurulu raporu gerekir (§4.2.1.C-2)."
        ),
        gate_b_sources=["C003645"],
    ),
    _rule(
        "4.2.1.tocilizumab_ra_board",
        "4.2.1.C-3",
        ["tosilizumab", "tocilizumab", "actemra", "roactemra"],
        icd10_ranges=_RA,
        prescriber_specialties=_ROMATO_REPORT,
        report_duration_months=3,
        message_tr=(
            "Tosilizumab — aktif romatoid artritte methotreksat ile birlikte "
            "3 ay süreli sağlık kurulu raporu gerekir (§4.2.1.C-3)."
        ),
        gate_b_sources=["C003664"],
    ),
    _rule(
        "4.2.1.tofacitinib_ra_board",
        "4.2.1.C-6",
        ["tofacitinib", "barisitinib", "upadasitinib", "xeljanz", "olumiant", "rinvoq"],
        icd10_ranges=_RA,
        prescriber_specialties=_ROMATO_REPORT,
        report_duration_months=3,
        message_tr=(
            "Tofacitinib/barisitinib/upadasitinib — anti-TNF yetersiz romatoid artritte "
            "3 ay süreli sağlık kurulu raporu gerekir (§4.2.1.C-6)."
        ),
        gate_b_sources=["C003738"],
    ),
    _rule(
        "4.2.1.tofacitinib_axial_as_board",
        "4.2.1.C-6",
        ["tofacitinib", "upadasitinib", "xeljanz", "rinvoq"],
        icd10_ranges=_AS,
        report_duration_months=3,
        message_tr=(
            "Tofacitinib/upadasitinib — anti-TNF yetersiz aksiyel/periferik ankilozan "
            "spondilitte 3 ay süreli sağlık kurulu raporu gerekir (§4.2.1.C-6)."
        ),
        gate_b_sources=["C003745", "C003746"],
    ),
    _rule(
        "4.2.1.vedolizumab_uc_report",
        "4.2.1.C-4",
        ["vedolizumab", "entyvio"],
        icd10_ranges=_UC,
        report_specialties=_GASTRO_REPORT,
        prescriber_specialties=_GASTRO_REPORT,
        report_duration_months=6,
        message_tr=(
            "Vedolizumab — anti-TNF yetersiz ülseratif kolitte gastroenteroloji/genel "
            "cerrahi uzman hekim raporu gerekir (§4.2.1.C-4)."
        ),
        gate_b_sources=["C003687"],
    ),
]
