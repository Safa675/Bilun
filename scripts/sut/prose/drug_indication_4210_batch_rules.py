"""R5 Epic — Tier A pilot rules for §4.2.10 lysosomal storage diseases (LSD)."""

from __future__ import annotations

from typing import Any

_GAUCHER_ICD = ["E75.22"]
_FABRY_ICD = ["E75.21"]
_MPS_ICD = ["E76"]
_POMPE_ICD = ["E74.02"]
_NPC_ICD = ["E75.24"]

_METABOLISM_REPORT = [
    "çocuk endokrinolojisi ve metabolizma",
    "çocuk metabolizma",
    "endokrinoloji ve metabolizma",
    "gastroenteroloji",
]
_FABRY_REPORT = [
    "çocuk metabolizma",
    "endokrinoloji ve metabolizma",
    "gastroenteroloji",
    "nöroloji",
    "nefroloji",
]
_MPS_REPORT = [
    "çocuk metabolizma",
    "çocuk endokrinolojisi ve metabolizma",
    "endokrinoloji ve metabolizma hastalıkları",
]
_POMPE_NPC_REPORT = [
    "gastroenteroloji",
    "çocuk metabolizma",
    "çocuk endokrinolojisi ve metabolizma",
    "nöroloji",
]


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
    batch: str = "LSD4210",
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
        payload["report_specialties"] = report_specialties or _METABOLISM_REPORT
    if report_duration_months is not None:
        payload["report_duration_months"] = report_duration_months
    if prescriber_specialties:
        payload["prescriber_specialties"] = prescriber_specialties
    return payload


BATCH_LSD4210_RULES: list[dict[str, Any]] = [
    _rule(
        "4.2.10.gaucher_enzyme_indication_types",
        "4.2.10.A",
        [
            "imiglucerase",
            "cerezyme",
            "velaglucerase",
            "vprive",
            "eliglustat",
            "cerdelga",
            "miglustat",
            "zavesca",
        ],
        icd10_ranges=_GAUCHER_ICD,
        message_tr=(
            "Gaucher hastalığı enzim tedavisi — yalnızca Tip I (non nöropatik) ve "
            "Tip III (kronik nöropatik) formlarda endikedir; Tip II (akut nöropatik) "
            "formda enzim tedavisi yapılmaz (§4.2.10.A)."
        ),
        gate_b_sources=["C004209"],
    ),
    _rule(
        "4.2.10.eliglustat_cyp2d6_report",
        "4.2.10.A-3",
        ["eliglustat", "cerdelga"],
        icd10_ranges=_GAUCHER_ICD,
        report_required=True,
        report_specialties=_METABOLISM_REPORT,
        report_duration_months=6,
        prescriber_specialties=_METABOLISM_REPORT
        + ["çocuk sağlığı ve hastalıkları", "iç hastalıkları"],
        message_tr=(
            "Eliglustat — CYP2D6 metabolizör tipi (OM/HM/YM) raporda belirtilmeli; "
            "6 aylık sağlık kurulu raporu ve uzman reçetesi gerekir (§4.2.10.A-3/A-4)."
        ),
        gate_b_sources=["C004252", "C004257", "C004258"],
    ),
    _rule(
        "4.2.10.gaucher_board_report_6mo",
        "4.2.10.A-4",
        [
            "imiglucerase",
            "cerezyme",
            "velaglucerase",
            "vprive",
            "miglustat",
        ],
        icd10_ranges=_GAUCHER_ICD,
        report_required=True,
        report_specialties=_METABOLISM_REPORT,
        report_duration_months=6,
        prescriber_specialties=_METABOLISM_REPORT
        + ["çocuk sağlığı ve hastalıkları", "iç hastalıkları"],
        message_tr=(
            "Gaucher hastalığı tedavisi — çocuk endokrinolojisi/metabolizma veya "
            "gastroenteroloji uzman hekimlerinin yer aldığı 6 aylık sağlık kurulu "
            "raporu ve uzman reçetesi gerekir (§4.2.10.A-4)."
        ),
        gate_b_sources=["C004257", "C004258"],
    ),
    _rule(
        "4.2.10.fabry_board_report_6mo",
        "4.2.10.B-3",
        [
            "agalsidase",
            "replagal",
            "fabrazyme",
            "migalastat",
            "galafold",
        ],
        icd10_ranges=_FABRY_ICD,
        report_required=True,
        report_specialties=_FABRY_REPORT,
        report_duration_months=6,
        prescriber_specialties=_FABRY_REPORT
        + ["çocuk sağlığı ve hastalıkları", "iç hastalıkları"],
        message_tr=(
            "Fabry hastalığı tedavisi — metabolizma/endokrinoloji uzmanı dahil sağlık "
            "kurulu raporu (6 ay) ve uzman reçetesi gerekir (§4.2.10.B-3)."
        ),
        gate_b_sources=["C004299", "C004300"],
    ),
    _rule(
        "4.2.10.mps1_enzyme_start_date_report",
        "4.2.10.C-2",
        ["laronidase", "aldurazyme"],
        icd10_ranges=["E76.0"],
        report_required=True,
        report_specialties=_MPS_REPORT,
        message_tr=(
            "Tip I Mukopolisakkaridoz enzim tedavisi — enzim tedavisine başlangıç "
            "tarihi her yenilenen raporda belirtilmelidir (§4.2.10.C-2)."
        ),
        gate_b_sources=["C004353"],
    ),
    _rule(
        "4.2.10.mps_board_report_1yr",
        "4.2.10.C-3",
        [
            "laronidase",
            "aldurazyme",
            "idursulfase",
            "elaprase",
            "galsulfase",
            "naglazyme",
            "elosulfase",
            "vimizim",
        ],
        icd10_ranges=_MPS_ICD,
        report_required=True,
        report_specialties=_MPS_REPORT,
        report_duration_months=12,
        prescriber_specialties=_MPS_REPORT
        + ["çocuk sağlığı ve hastalıkları", "iç hastalıkları"],
        message_tr=(
            "Mukopolisakkaridoz tedavisi — üçüncü basamak resmi sağlık kuruluşunda "
            "metabolizma uzmanlarının yer aldığı 1 yıllık sağlık kurulu raporu "
            "gerekir (§4.2.10.C-3)."
        ),
        gate_b_sources=["C004363", "C004364"],
    ),
    _rule(
        "4.2.10.pompe_board_report_1yr",
        "4.2.10.Ç-2",
        ["alglucosidase", "myozyme", "lumizyme"],
        icd10_ranges=_POMPE_ICD,
        report_required=True,
        report_specialties=_POMPE_NPC_REPORT,
        report_duration_months=12,
        prescriber_specialties=_POMPE_NPC_REPORT
        + ["çocuk sağlığı ve hastalıkları", "iç hastalıkları"],
        message_tr=(
            "Pompe hastalığı tedavisi — gastroenteroloji, çocuk metabolizma veya "
            "nöroloji uzman hekimlerinin yer aldığı 1 yıllık sağlık kurulu raporu "
            "gerekir (§4.2.10.Ç-2)."
        ),
        gate_b_sources=["C004371", "C004372"],
    ),
    _rule(
        "4.2.10.npc_board_report_6mo",
        "4.2.10.D-2",
        ["miglustat", "zavesca"],
        icd10_ranges=_NPC_ICD,
        report_required=True,
        report_specialties=_POMPE_NPC_REPORT,
        report_duration_months=6,
        prescriber_specialties=_POMPE_NPC_REPORT
        + ["çocuk sağlığı ve hastalıkları", "iç hastalıkları"],
        message_tr=(
            "Niemann-Pick Tip C tedavisi — gastroenteroloji, çocuk metabolizma veya "
            "nöroloji uzman hekimlerinin yer aldığı 6 aylık sağlık kurulu raporu "
            "gerekir (§4.2.10.D-2)."
        ),
        gate_b_sources=["C004379", "C004380"],
    ),
]
