"""L1.4 Phase 8 — titubb_uts_barkod theme (3 corpus batch2 clauses)."""

from __future__ import annotations

from typing import Any

TITUBB_UTS_BATCH_RULES: list[dict[str, Any]] = [
    {
        "rule_id": "3.1.1.(3).ismarlama_device_component_titubb_incomplete",
        "sut_section": "3.1.1",
        "deontic": "NO_PAY",
        "gate_b_sources": ["C001620"],
        "condition": {"ismarlama_device_component_titubb_incomplete": True},
        "action": {
            "material_outcome": "no_pay",
            "severity": "error",
            "message_tr": (
                "Ismarlama cihaz bileşeni (Tıbbi Cihaz Yönetmeliği kapsamı) için "
                "ayrı TİTUBB kayıt/bildirim tamamlanmalı — nihai ürün muafiyeti "
                "bileşenlere uygulanmaz (§3.1.1(3))."
            ),
        },
    },
    {
        "rule_id": "3.1.1.(4).titubb_uts_barcode_documentation_missing",
        "sut_section": "3.1.1",
        "deontic": "REGULATORY_ACTION",
        "gate_b_sources": ["C001621", "C002685"],
        "condition": {"titubb_uts_barcode_documentation_missing": True},
        "action": {
            "material_outcome": "review_required",
            "severity": "warning",
            "message_tr": (
                "TİTUBB/ÜTS barkod bilgisi hasta dosyasında muhafaza/ibraz "
                "edilmeli (§3.1.1(3)/(4); EK-3/A <100 TL yatarak istisnası hariç)."
            ),
        },
    },
]
