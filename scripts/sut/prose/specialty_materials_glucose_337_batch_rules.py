"""L4.4 — §3.3.2 glucose meter + §3.3.7.B wheelchair mini-batches (4 clauses → 3 rules)."""

from __future__ import annotations

from typing import Any

GLUCOSE_METER_BATCH_CLAUSE_IDS: frozenset[str] = frozenset({"C001928", "C002875"})

SPECIALTY_337_BATCH_CLAUSE_IDS: frozenset[str] = frozenset({"C003072", "C003073"})

GLUCOSE_337_BATCH_RULES: list[dict[str, Any]] = [
    {
        "rule_id": "3.3.2.b.glucose_meter_early_renewal",
        "sut_section": "3.3.2",
        "deontic": "NO_PAY",
        "gate_b_sources": ["C001928", "C002875"],
        "condition": {"glucose_meter_early_renewal": True},
        "action": {
            "material_outcome": "no_pay",
            "severity": "error",
            "message_tr": (
                "Kan şekeri ölçüm cihazı yenilenme süresi 2 yıl — erken temin "
                "bedeli ödenmez (§3.3.2(b))."
            ),
        },
    },
    {
        "rule_id": "3.3.2.b.glucose_meter_early_renewal_keyword",
        "sut_section": "3.3.2",
        "deontic": "NO_PAY",
        "gate_b_sources": ["C001928", "C002875"],
        "condition": {
            "material_name_any": [
                "kan sekeri olcum cihaz",
                "kan şekeri ölçüm cihaz",
                "glukometre",
                "glucose meter",
            ]
        },
        "action": {
            "material_outcome": "review_required",
            "severity": "warning",
            "message_tr": (
                "Kan şekeri ölçüm cihazı — 2 yıllık MIAT kontrolü gerekli "
                "(§3.3.2(b))."
            ),
        },
    },
    {
        "rule_id": "3.3.7.B.(2).wheelchair_stand_device_duplicate",
        "sut_section": "3.3.7.B",
        "deontic": "NO_PAY",
        "gate_b_sources": ["C003072"],
        "condition": {"wheelchair_stand_device_duplicate_billing": True},
        "action": {
            "material_outcome": "no_pay",
            "severity": "error",
            "message_tr": (
                "Tekerlekli sandalye ile birlikte ayakta dik konumlandırma cihazı "
                "ayrıca karşılanmaz (§3.3.7.B(2))."
            ),
        },
    },
    {
        "rule_id": "3.3.7.B.(3).stand_up_wheelchair_early_renewal",
        "sut_section": "3.3.7.B",
        "deontic": "NO_PAY",
        "gate_b_sources": ["C003073"],
        "condition": {"stand_up_wheelchair_early_renewal": True},
        "action": {
            "material_outcome": "no_pay",
            "severity": "error",
            "message_tr": (
                "Stand up wheelchair MIAT 5 yıl — erken yenileme bedeli "
                "karşılanmaz (§3.3.7.B(3))."
            ),
        },
    },
]
