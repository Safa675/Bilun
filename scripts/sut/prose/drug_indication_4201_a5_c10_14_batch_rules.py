"""R5 Epic A5 — Tier A batch rules for §4.2.1.C-10/C-11/C-12/C-14 IL-17/IL-23 biologics."""

from __future__ import annotations

from typing import Any

_PSA = ["L40.5"]
_PSORIASIS = ["L40"]

_IXEKIZUMAB = ["ixekizumab", "iksekizumab", "taltz"]
_GUSELKUMAB = ["guselkumab", "tremfya"]
_RISANKIZUMAB = ["risankizumab", "skyrizi"]
_BIMEKIZUMAB = ["bimekizumab", "bimzelx"]


def _rule(
    rule_id: str,
    sut_section: str,
    drug_names: list[str],
    *,
    icd10_ranges: list[str],
    message_tr: str,
    gate_b_sources: list[str],
    batch: str = "A5_C10_14",
) -> dict[str, Any]:
    return {
        "rule_id": rule_id,
        "sut_section": sut_section,
        "drug_names": drug_names,
        "icd10_ranges": icd10_ranges,
        "report_required": True,
        "message_tr": message_tr,
        "encode_batch": batch,
        "gate_b_sources": gate_b_sources,
    }


BATCH_A5_C10_14_RULES: list[dict[str, Any]] = [
    _rule(
        "4.2.1.ixekizumab_psoriasis_pasi_systemic_failure",
        "4.2.1.C-10",
        _IXEKIZUMAB,
        icd10_ranges=_PSORIASIS,
        message_tr=(
            "İxekizumab — geleneksel sistemik tedavi yetersiz plak psoriyaziste PASI "
            "değerinin sağlık kurulu raporunda belirtilmesi gerekir (§4.2.1.C-10)."
        ),
        gate_b_sources=["C003867"],
    ),
    _rule(
        "4.2.1.ixekizumab_psa_second_line",
        "4.2.1.C-10",
        _IXEKIZUMAB,
        icd10_ranges=_PSA,
        message_tr=(
            "İxekizumab — DMARD ve anti-TNF yetersiz aktif psöriyatik artritte "
            "sağlık kurulu raporunda önceki tedavi yetersizliği belirtilmelidir (§4.2.1.C-10)."
        ),
        gate_b_sources=["C003872"],
    ),
    _rule(
        "4.2.1.guselkumab_psoriasis_pasi_systemic_failure",
        "4.2.1.C-11",
        _GUSELKUMAB,
        icd10_ranges=_PSORIASIS,
        message_tr=(
            "Guselkumab — geleneksel sistemik tedavi yetersiz plak psoriyaziste PASI "
            "değerinin sağlık kurulu raporunda belirtilmesi gerekir (§4.2.1.C-11)."
        ),
        gate_b_sources=["C003878"],
    ),
    _rule(
        "4.2.1.risankizumab_psoriasis_pasi_systemic_failure",
        "4.2.1.C-12",
        _RISANKIZUMAB,
        icd10_ranges=_PSORIASIS,
        message_tr=(
            "Risankizumab — geleneksel sistemik tedavi yetersiz plak psoriyaziste PASI "
            "değerinin sağlık kurulu raporunda belirtilmesi gerekir (§4.2.1.C-12)."
        ),
        gate_b_sources=["C003883"],
    ),
    _rule(
        "4.2.1.bimekizumab_psoriasis_pasi_systemic_failure",
        "4.2.1.C-14",
        _BIMEKIZUMAB,
        icd10_ranges=_PSORIASIS,
        message_tr=(
            "Bimekizumab — geleneksel sistemik tedavi yetersiz plak psoriyaziste PASI "
            "değerinin sağlık kurulu raporunda belirtilmesi gerekir (§4.2.1.C-14)."
        ),
        gate_b_sources=["C003894"],
    ),
]
