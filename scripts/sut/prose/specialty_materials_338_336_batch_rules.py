"""L4.4 — §3.3.8 mobility + §3.3.6 device return/NIMV batches (11 clauses)."""

from __future__ import annotations

from typing import Any

SPECIALTY_338_BATCH_CLAUSE_IDS: frozenset[str] = frozenset(
    {
       
       
       
       
       
       
       
    }
)

SPECIALTY_336_BATCH_CLAUSE_IDS: frozenset[str] = frozenset(
    {"C002997", "C003030", "C002997", "C003030"}
)

# Re-home §3.3.8 clauses already covered by §3.3.7.B rules.
RULE_SOURCE_PATCHES: dict[str, list[str]] = {
    "3.3.7.B.(2).wheelchair_stand_device_duplicate": [],
    "3.3.7.B.(3).stand_up_wheelchair_early_renewal": [],
}

SPECIALTY_338_336_BATCH_RULES: list[dict[str, Any]] = [
    {
        "rule_id": "3.3.8.A.d.paraplegia_standing_table_over_age",
        "sut_section": "3.3.8.A",
        "deontic": "NO_PAY",
        "gate_b_sources": [],
        "condition": {"paraplegia_standing_table_over_age_limit": True},
        "action": {
            "material_outcome": "no_pay",
            "severity": "error",
            "message_tr": (
                "Parapleji — 8 yaş üstü standing table bedeli karşılanmaz "
                "(§3.3.8.A(d))."
            ),
        },
    },
    {
        "rule_id": "3.3.8.A.(3).paraplegia_wheelchair_no_pay",
        "sut_section": "3.3.8.A",
        "deontic": "NO_PAY",
        "gate_b_sources": [],
        "condition": {"paraplegia_wheelchair_separate_billing": True},
        "action": {
            "material_outcome": "no_pay",
            "severity": "error",
            "message_tr": (
                "Parapleji kapsamında ayrıca tekerlekli sandalye — "
                "karşılanmaz (§3.3.8.A(3))."
            ),
        },
    },
    {
        "rule_id": "3.3.8.B.(2).spinal_mobility_device_bundle_excluded",
        "sut_section": "3.3.8.B",
        "deontic": "NO_PAY",
        "gate_b_sources": [],
        "condition": {"spinal_mobility_device_duplicate_billing": True},
        "action": {
            "material_outcome": "no_pay",
            "severity": "error",
            "message_tr": (
                "Tekerlekli sandalye / ayakta dik durma / parapodium ayrıca "
                "ödenmez (§3.3.8.B(2))."
            ),
        },
    },
    {
        "rule_id": "3.3.8.B.(2).spinal_mobility_device_keyword",
        "sut_section": "3.3.8.B",
        "deontic": "NO_PAY",
        "gate_b_sources": [],
        "condition": {
            "material_name_any": [
                "parapodium",
                "ayakta dik durma",
                "ayakta dik konum"]
        },
        "action": {
            "material_outcome": "review_required",
            "severity": "warning",
            "message_tr": (
                "Mobilite cihazı — §3.3.8.B kapsamında ayrı ödeme şüphesi."
            ),
        },
    },
    {
        "rule_id": "3.3.6.(2).returned_device_without_kurum_approval",
        "sut_section": "3.3.6",
        "deontic": "NO_PAY",
        "gate_b_sources": ["C002997", "C002997"],
        "condition": {"returned_device_without_kurum_approval": True},
        "action": {
            "material_outcome": "no_pay",
            "severity": "error",
            "message_tr": (
                "İade cihaz — Kurum stok/onay olmadan hasta temini; "
                "karşılanmaz (§3.3.6(2))."
            ),
        },
    },
    {
        "rule_id": "3.3.6.A-1.heated_humidifier_nimv_separate",
        "sut_section": "3.3.6.A-1",
        "deontic": "NO_PAY",
        "gate_b_sources": ["C003030", "C003030"],
        "condition": {"nimv_heated_humidifier_separate_billing": True},
        "action": {
            "material_outcome": "no_pay",
            "severity": "error",
            "message_tr": (
                "Isıtıcılı nemlendirici NİMV ünitesine dahil — ayrıca "
                "karşılanmaz (§3.3.6.A-1)."
            ),
        },
    },
    {
        "rule_id": "3.3.6.A-1.heated_humidifier_keyword",
        "sut_section": "3.3.6.A-1",
        "deontic": "NO_PAY",
        "gate_b_sources": ["C003030", "C003030"],
        "condition": {
            "material_name_any": [
                "isitici nemlendirici",
                "ısıtıcılı nemlendirici",
                "heated humidifier"]
        },
        "action": {
            "material_outcome": "review_required",
            "severity": "warning",
            "message_tr": (
                "Isıtıcılı nemlendirici — NİMV dâhil mi kontrol edilmeli "
                "(§3.3.6.A-1)."
            ),
        },
    }]
