"""Gate B deferred batch — claim-field rules + patches to existing prose rows."""

from __future__ import annotations

from typing import Any

# New rules (require optional booleans on material claim lines / validate_claim dicts).
GATE_B_DEFERRED_BATCH_RULES: list[dict[str, Any]] = [
    {
        "rule_id": "3.1.1.(5).procurement_screen_incomplete",
        "sut_section": "3.1.1",
        "deontic": "NO_PAY",
        "gate_b_sources": ["C002686"],
        "condition": {"procurement_record_incomplete": True},
        "action": {
            "material_outcome": "no_pay",
            "severity": "error",
            "message_tr": (
                "İhale/doğrudan temin sonuç bilgileri eksik — malzeme bedeli "
                "Kurumca karşılanmaz (§3.1.1(5))."
            ),
        },
    },
    {
        "rule_id": "3.1.1.(11).procedure_not_reimbursed_link",
        "sut_section": "3.1.1",
        "deontic": "NO_PAY",
        "gate_b_sources": [],
        "condition": {"procedure_not_reimbursed": True},
        "action": {
            "material_outcome": "no_pay",
            "severity": "error",
            "message_tr": (
                "Bedeli karşılanmayan işleme ait malzeme — Kurumca karşılanmaz "
                "(§3.1.1(11)/(12))."
            ),
        },
    },
    {
        "rule_id": "3.1.1.(14).foreign_facility_overhead",
        "sut_section": "3.1.1",
        "deontic": "NO_PAY",
        "gate_b_sources": ["C002694", "C002694"],
        "condition": {"foreign_facility": True},
        "action": {
            "material_outcome": "no_pay",
            "severity": "warning",
            "message_tr": (
                "Yurt dışı sunucuda işletme/hazine/SHÇEK kesintileri — "
                "malzeme ek giderleri Kurumca karşılanmaz (§3.1.1(12)/(14))."
            ),
        },
    },
    {
        "rule_id": "3.1.1.(18).facility_procedure_restriction",
        "sut_section": "3.1.1",
        "deontic": "NO_PAY",
        "gate_b_sources": ["C002698", "C002698"],
        "condition": {"facility_procedure_restriction_violation": True},
        "action": {
            "material_outcome": "no_pay",
            "severity": "error",
            "message_tr": (
                "Malzemedeki sunucu kısıtına uymayan işlem — bedel ödenmez "
                "(§3.1.1(16)/(18))."
            ),
        },
    },
    {
        "rule_id": "3.1.3.(11).diagnosis_bundled_medula",
        "sut_section": "3.1.3",
        "deontic": "MUST_NOT_BILL",
        "gate_b_sources": ["C002798", "C002798"],
        "condition": {"diagnosis_bundled_no_separate_bill": True},
        "action": {
            "material_outcome": "must_not_bill_separately",
            "severity": "warning",
            "message_tr": (
                "Tanıya dayalı paket kapsamı — ayrıca faturalandırılamaz; "
                "MEDULA kaydı gerekir (§3.1.3(11))."
            ),
        },
    },
]

# Patch existing JSON rules (gate_b_sources / keywords) without duplicating rule_id.
GATE_B_RULE_PATCHES: dict[str, dict[str, Any]] = {
    "3.1.2.(2).not_in_ek3c": {
        "gate_b_sources_append": ["C002707"],
    },
    "3.1.2.c.warranty_maintenance": {
        "gate_b_sources_append": ["C002741"],
        "material_name_any_append": [
            "bakım ve onarım masrafları",
            "bakim ve onarim masraflari",
            "firma tarafından karşılan",
            "firma tarafindan karsilan",
        ],
    },
}

# KDV + allow-list moved to pricing/catalog (see material_bundling_tail_batch_rules.py).
GATE_B_STILL_DEFERRED_CLAUSE_IDS: frozenset[str] = frozenset()
