"""R5 Epic A5 — Tier A pilot rules for §4.2.18 orlistat + §4.2.36 Parkinson."""

from __future__ import annotations

from typing import Any

_OBESITY_ICD = ["E66"]
_PARKINSON_ICD = ["G20", "G21"]
_EXTRAPYRAMIDAL_ICD = ["G24", "G25"]
_NEURO_GERI_REPORT = ["nöroloji", "geriatri"]
_NEURO_GERI_PRESCRIBER = ["nöroloji", "geriatri"]
_TOLCAPONE_PRESCRIBER = ["nöroloji", "iç hastalıkları"]


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
    batch: str = "A5",
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
        payload["report_specialties"] = report_specialties or _NEURO_GERI_REPORT
    if report_duration_months is not None:
        payload["report_duration_months"] = report_duration_months
    if prescriber_specialties:
        payload["prescriber_specialties"] = prescriber_specialties
    return payload


BATCH_A5_RULES: list[dict[str, Any]] = [
    _rule(
        "4.2.18.orlistat_monthly_prescription",
        "4.2.18",
        ["orlistat", "xenical"],
        icd10_ranges=_OBESITY_ICD,
        report_duration_months=1,
        message_tr=(
            "Orlistat — reçeteler birer aylık düzenlenmelidir (§4.2.18)."
        ),
        gate_b_sources=["C006059"],
    ),
    _rule(
        "4.2.36.parkinson_dopamine_agonists_report",
        "4.2.36",
        [
            "apomorfin",
            "kabergolin",
            "entakapon",
            "rasagilin",
            "rasajilin",
            "pergolid",
            "pramipexol",
            "bornaprin",
            "ropinirol",
        ],
        icd10_ranges=_PARKINSON_ICD,
        report_required=True,
        report_specialties=_NEURO_GERI_REPORT,
        message_tr=(
            "Parkinson dopamin agonistleri — nöroloji veya geriatri uzman hekim "
            "raporuna dayanılarak reçete edilir (§4.2.36)."
        ),
        gate_b_sources=["C006707"],
    ),
    _rule(
        "4.2.36.tolcapone_tertiary_neurology_report",
        "4.2.36",
        ["tolkapon", "tolcapone"],
        icd10_ranges=_PARKINSON_ICD,
        report_required=True,
        report_specialties=_NEURO_GERI_REPORT,
        prescriber_specialties=_TOLCAPONE_PRESCRIBER,
        report_duration_months=1,
        message_tr=(
            "Tolkapon — entakapon dirençli vakalarda nöroloji/geriatri uzman hekim "
            "raporu ile nöroloji veya iç hastalıkları uzmanı tarafından en fazla "
            "1 aylık reçete (§4.2.36)."
        ),
        gate_b_sources=["C006708"],
    ),
    _rule(
        "4.2.36.amantadine_sulfate_report",
        "4.2.36",
        ["amantadin sülfat", "amantadine sulfate", "pk-merz"],
        icd10_ranges=_PARKINSON_ICD + _EXTRAPYRAMIDAL_ICD,
        report_required=True,
        report_specialties=_NEURO_GERI_REPORT,
        message_tr=(
            "Amantadin sülfat — parkinson veya ilaç kaynaklı ekstrapiramidal "
            "reaksiyonlarda nöroloji/geriatri uzman hekim raporu gerekir (§4.2.36)."
        ),
        gate_b_sources=["C006709"],
    ),
    _rule(
        "4.2.36.amantadine_hcl_parkinson_report",
        "4.2.36",
        ["amantadin hidroklorür", "amantadin hcl", "amantadine hydrochloride", "amantix"],
        icd10_ranges=_PARKINSON_ICD,
        report_required=True,
        report_specialties=_NEURO_GERI_REPORT,
        message_tr=(
            "Amantadin hidroklorür — yalnızca parkinson hastalığında nöroloji veya "
            "geriatri uzman hekim raporu gerekir (§4.2.36)."
        ),
        gate_b_sources=["C006711"],
    ),
]
