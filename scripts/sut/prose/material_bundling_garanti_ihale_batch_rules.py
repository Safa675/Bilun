"""L1.4 Phase 8 — garanti/onarım (9) + ihale/DTS (2) corpus batch2 themes."""

from __future__ import annotations

from typing import Any

GARANTI_IHALE_BATCH_RULES: list[dict[str, Any]] = [
    {
        "rule_id": "3.1.2.(11).maintenance_cost_cap_exceeded",
        "sut_section": "3.1.2",
        "deontic": "NO_PAY",
        "gate_b_sources": ["C002732", "C002733"],
        "condition": {"maintenance_cost_exceeds_sut_cap": True},
        "action": {
            "material_outcome": "no_pay",
            "severity": "error",
            "message_tr": (
                "Bakım/onarım toplam bedeli malzeme bedelinin %75'ini geçemez "
                "(§3.1.2(11))."
            ),
        },
    },
    {
        "rule_id": "3.1.2.(8).protez_repair_documentation_incomplete",
        "sut_section": "3.1.2",
        "deontic": "REGULATORY_ACTION",
        "gate_b_sources": ["C002727", "C002728", "C002729", "C002744"],
        "condition": {"protez_repair_documentation_incomplete": True},
        "action": {
            "material_outcome": "review_required",
            "severity": "warning",
            "message_tr": (
                "Protez/ortez MIAT veya yenileme talebi — sağlık raporu/kurul "
                "belgesi gerekir (§3.1.2(8))."
            ),
        },
    },
    {
        "rule_id": "3.1.2.(8).warranty_maintenance_procedure_incomplete",
        "sut_section": "3.1.2",
        "deontic": "MANDATORY",
        "gate_b_sources": ["C002723"],
        "condition": {"warranty_maintenance_procedure_incomplete": True},
        "action": {
            "material_outcome": "review_required",
            "severity": "warning",
            "message_tr": (
                "Garanti içi/dışı bakım-onarım başvuru prosedürü tamamlanmamış "
                "(§3.1.2(8)(b))."
            ),
        },
    },
    {
        "rule_id": "3.1.2.(8).ortez_protez_maintenance_unverified",
        "sut_section": "3.1.2",
        "deontic": "REGULATORY_ACTION",
        "gate_b_sources": ["C002721", "C002722"],
        "condition": {"ortez_protez_maintenance_unverified": True},
        "action": {
            "material_outcome": "review_required",
            "severity": "info",
            "message_tr": (
                "Ortez/protez bakım-onarım — garanti kapsamı ve Kurum tespiti "
                "doğrulanmalı (§3.1.2(8))."
            ),
        },
    },
    {
        "rule_id": "3.1.1.(4).ihale_dts_mandatory_fields_incomplete",
        "sut_section": "3.1.1",
        "deontic": "MANDATORY",
        "gate_b_sources": ["C002686"],
        "condition": {"ihale_dts_mandatory_fields_incomplete": True},
        "action": {
            "material_outcome": "no_pay",
            "severity": "error",
            "message_tr": (
                "İhale/DTS ekranında İKN, TİTUBB/ÜTS, fiyat ve zorunlu alanlar "
                "eksik — malzeme bedeli karşılanmaz (§3.1.1(4))."
            ),
        },
    },
    {
        "rule_id": "3.2.1.A.(3).supplier_contract_pricing_path",
        "sut_section": "3.2.1",
        "deontic": "REGULATORY_ACTION",
        "gate_b_sources": ["C001842"],
        "condition": {"supplier_contract_pricing_path": True},
        "action": {
            "material_outcome": "review_required",
            "severity": "info",
            "message_tr": (
                "Tedarikçi sözleşmeli malzeme — ihale fiyatı ve SUT tavanı "
                "doğrulanmalı (§3.2.1.A(3))."
            ),
        },
    },
]
