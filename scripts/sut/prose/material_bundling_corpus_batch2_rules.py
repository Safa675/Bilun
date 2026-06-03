"""L1.4 Phase 8 — semantic splits for mis-mapped Gate B clauses + corpus hygiene."""

from __future__ import annotations

from typing import Any

CORPUS_BATCH2_RULES: list[dict[str, Any]] = [
    {
        "rule_id": "3.2.1.(2).procurement_price_refs_insufficient",
        "sut_section": "3.2.1",
        "deontic": "NO_PAY",
        "gate_b_sources": ["C001834", "C001837", "C001845", "C001849"],
        "condition": {"procurement_price_refs_insufficient": True},
        "action": {
            "material_outcome": "no_pay",
            "severity": "error",
            "message_tr": (
                "İhale/DTS ekranında son bir yıl içinde en az 3 hastane fiyat "
                "referansı yok — listesiz veya fiyatsız malzeme Kurumca karşılanmaz "
                "(§3.2.1(2))."
            ),
        },
    },
    {
        "rule_id": "3.1.1.(16).medula_code_undefined_on_date",
        "sut_section": "3.1.1",
        "deontic": "NO_PAY",
        "gate_b_sources": ["C001636", "C002696"],
        "condition": {"medula_code_undefined_on_date": True},
        "action": {
            "material_outcome": "no_pay",
            "severity": "error",
            "message_tr": (
                "SUT kodu işlem tarihinde MEDULA'da tanımlı değil — malzeme "
                "bedeli Kurumca karşılanmaz (§3.1.1(14)/(16))."
            ),
        },
    },
]

# Re-home clause IDs that were attached to the wrong prose rule.
CORPUS_BATCH2_RULE_PATCHES: dict[str, dict[str, Any]] = {
    "3.1.1.(2).titubb_uts_incomplete": {
        "gate_b_sources_remove": ["C001636", "C002696"],
    },
    "3.1.2.(2).not_in_ek3": {
        "gate_b_sources_remove": [
            "C001834",
            "C001837",
            "C001840",
            "C001845",
            "C001849",
        ],
    },
    "3.1.2.(7).lost_stolen_miat": {
        "gate_b_sources_remove": ["C002707"],
    },
    "3.1.2.(2).not_in_ek3c": {
        "gate_b_sources_append": ["C002707"],
    },
    "3.1.1.(17).barcode_sut_mismatch": {
        "condition_merge": {"barcode_sut_mismatch": True},
    },
}
