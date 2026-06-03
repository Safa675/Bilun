"""L1.4 Phase 8 — faturalandirma theme batch (corpus batch2 CSV).

These six clauses (C001789, C001799, C002739–C002740, C002791, C002800) are
scope/allowance/regulatory text — not NO_PAY prohibitions. Encoded as claim-field
review rules until branch/cross-list catalog checks ship.
"""

from __future__ import annotations

from typing import Any

FATURALANDIRMA_BATCH_RULES: list[dict[str, Any]] = [
    {
        "rule_id": "3.1.4.(1).diagnosis_bundled_sut_rules_apply",
        "sut_section": "3.1.4",
        "deontic": "REGULATORY_ACTION",
        "gate_b_sources": ["C001799", "C002800"],
        "condition": {"diagnosis_bundled_material_scope": True},
        "action": {
            "material_outcome": "review_required",
            "severity": "info",
            "message_tr": (
                "Tanıya dayalı paket dahil malzeme — §3.1–3.2 SUT kuralları "
                "geçerlidir (§3.1.4(1))."
            ),
        },
    },
    {
        "rule_id": "3.1.3.(4).cross_branch_billing_unauthorized",
        "sut_section": "3.1.3",
        "deontic": "NO_PAY",
        "gate_b_sources": ["C001789", "C002791"],
        "condition": {"cross_branch_material_unauthorized": True},
        "action": {
            "material_outcome": "no_pay",
            "severity": "error",
            "message_tr": (
                "Branş listesinde olmayan malzeme — cross-list SUT kodu ve "
                "geri ödeme kurallarına uygun faturalandırılmalı (§3.1.3(4))."
            ),
        },
    },
    {
        "rule_id": "3.1.2.b.ortez_protez_contract_billing_invalid",
        "sut_section": "3.1.2",
        "deontic": "REGULATORY_ACTION",
        "gate_b_sources": ["C002739", "C002740"],
        "condition": {"ortez_protez_contract_billing_invalid": True},
        "action": {
            "material_outcome": "review_required",
            "severity": "warning",
            "message_tr": (
                "Özel sözleşme yolu ortez/protez faturalandırması — komisyon "
                "tespiti ve sözleşme kapsamı doğrulanmalı (§3.1.2(b))."
            ),
        },
    },
]
