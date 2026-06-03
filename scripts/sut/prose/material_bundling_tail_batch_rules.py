"""L1.4 tail batch — separate-billing authorization (C001635, C002695, C001823)."""

from __future__ import annotations

from typing import Any

GATE_B_TAIL_BATCH_RULES: list[dict[str, Any]] = [
    {
        "rule_id": "3.1.1.(15).separate_billing_not_authorized",
        "sut_section": "3.1.1",
        "deontic": "MUST_NOT_BILL",
        "gate_b_sources": ["C001635", "C002695", "C001823"],
        "condition": {"separate_billing_not_authorized": True},
        "action": {
            "material_outcome": "must_not_bill_separately",
            "severity": "warning",
            "message_tr": (
                "EK-3 listesinde olup SUT/eklerinde ayrıca faturalandırma izni "
                "belirtilmeyen malzeme — ilave faturalandırma riski (§3.1.1(15))."
            ),
        },
    },
]

# KDV clauses implemented in pricing layer, not prose JSON.
KDV_PRICING_CLAUSE_IDS: frozenset[str] = frozenset(
    {
        "C001630",
        "C002692",
    }
)
