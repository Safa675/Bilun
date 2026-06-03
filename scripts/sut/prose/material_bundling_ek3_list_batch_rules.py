"""L1.4 Phase 8 — ek3_list theme batch (99 corpus rows: 76 annex headers + 23 substantive)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_EK3_HEADER_IDS_PATH = Path("evidence/clauses/L1.4_ek3_annex_header_clause_ids.json")

# §3.2.2(1) — list-price ceiling handled in kdv_price_reviews + catalog lookup.
EK3C_LIST_PRICE_CEILING_CLAUSE_IDS: frozenset[str] = frozenset(
    {
        "C001851",
        "C002833",
    }
)

# Scope-only rows (no standalone claim-field rule in this batch).
EK3_SCOPE_ONLY_CLAUSE_IDS: frozenset[str] = frozenset(
    {
        "C001649",
        "C002708",
        "C002745",
    }
)

EK3_LIST_BATCH_RULES: list[dict[str, Any]] = [
    {
        "rule_id": "3.1.1.(8).ek3c_inpatient_external_supply_invalid",
        "sut_section": "3.1.1",
        "deontic": "NO_PAY",
        "gate_b_sources": ["C001626", "C002751"],
        "condition": {"ek3c_inpatient_external_supply_invalid": True},
        "action": {
            "material_outcome": "no_pay",
            "severity": "error",
            "message_tr": (
                "Yatarak tedavi sırasında EK-3/C malzemesi dışarıdan reçete yolu "
                "uygunsuz — sözleşmeli merkez/kurallara uygun temin gerekir "
                "(§3.1.1(8)/(19))."
            ),
        },
    },
    {
        "rule_id": "3.2.2.(2).ek3c_list_price_missing",
        "sut_section": "3.2.2",
        "deontic": "REGULATORY_ACTION",
        "gate_b_sources": ["C001852", "C002834"],
        "condition": {"ek3c_list_price_missing": True},
        "action": {
            "material_outcome": "review_required",
            "severity": "warning",
            "message_tr": (
                "EK-3/C listesinde fiyatı olmayan malzeme — piyasa araştırması "
                "ve benzer ürün en düşük fiyat esas alınmalı (§3.2.2(2))."
            ),
        },
    },
    {
        "rule_id": "3.1.1.(13).ek3_quality_documentation_incomplete",
        "sut_section": "3.1.1",
        "deontic": "REGULATORY_ACTION",
        "gate_b_sources": ["C001631", "C002693"],
        "condition": {"ek3_quality_documentation_incomplete": True},
        "action": {
            "material_outcome": "review_required",
            "severity": "warning",
            "message_tr": (
                "EK-3 malzemesi için kalite/ürün güvenliği belgeleri "
                "eksik — Kurum talep edebilir (§3.1.1(11)/(13))."
            ),
        },
    },
    {
        "rule_id": "3.1.2.(9).ek3c_miat_early_renewal_unauthorized",
        "sut_section": "3.1.2",
        "deontic": "NO_PAY",
        "gate_b_sources": ["C002725"],
        "condition": {"ek3c_miat_early_renewal_unauthorized": True},
        "action": {
            "material_outcome": "no_pay",
            "severity": "error",
            "message_tr": (
                "EK-3/C-2/C-3 malzemesi MIAT süresi dolmadan yenilenemez "
                "(§3.1.2(9))."
            ),
        },
    },
    {
        "rule_id": "3.1.2.(4).ek3c_custom_order_billing_invalid",
        "sut_section": "3.1.2",
        "deontic": "REGULATORY_ACTION",
        "gate_b_sources": ["C001650", "C002709"],
        "condition": {"ek3c_custom_order_billing_invalid": True},
        "action": {
            "material_outcome": "review_required",
            "severity": "warning",
            "message_tr": (
                "EK-3/C 'I' (ısmarlama) malzemesi — kişiye özel üretim kuralları "
                "doğrulanmalı (§3.1.2(4))."
            ),
        },
    },
    {
        "rule_id": "3.1.2.(5).ek3c_medical_appropriateness_incomplete",
        "sut_section": "3.1.2",
        "deontic": "NO_PAY",
        "gate_b_sources": ["C001655", "C002713"],
        "condition": {"ek3c_medical_appropriateness_incomplete": True},
        "action": {
            "material_outcome": "no_pay",
            "severity": "error",
            "message_tr": (
                "EK-3/C-1 malzemesi için tıbbi uygunluk/rapor takibi "
                "tamamlanmamış (§3.1.2(5))."
            ),
        },
    },
    {
        "rule_id": "3.1.2.c.ek3c_custom_garment_contract_invalid",
        "sut_section": "3.1.2",
        "deontic": "REGULATORY_ACTION",
        "gate_b_sources": ["C001654", "C002712"],
        "condition": {"ek3c_custom_garment_contract_invalid": True},
        "action": {
            "material_outcome": "review_required",
            "severity": "warning",
            "message_tr": (
                "Lenfödem/yanık bası giysisi (ısmarlama) — sözleşme yolu "
                "doğrulanmalı (§3.1.2(c))."
            ),
        },
    },
    {
        "rule_id": "3.1.2.(13).ek3c_force_majeure_renewal_claim",
        "sut_section": "3.1.2",
        "deontic": "REGULATORY_ACTION",
        "gate_b_sources": ["C002735"],
        "condition": {"ek3c_force_majeure_renewal_claim": True},
        "action": {
            "material_outcome": "review_required",
            "severity": "info",
            "message_tr": (
                "Mücbir sebep belgeli EK-3/C yenileme — kullanım süresine "
                "bakılmaksızın yenileme yolu (§3.1.2(13))."
            ),
        },
    },
    {
        "rule_id": "3.1.2.(1).ek3c_outpatient_material_scope",
        "sut_section": "3.1.2",
        "deontic": "REGULATORY_ACTION",
        "gate_b_sources": ["C001641", "C002700"],
        "condition": {"ek3c_outpatient_material_scope": True},
        "action": {
            "material_outcome": "review_required",
            "severity": "info",
            "message_tr": (
                "Ayakta tedavi EK-3/C listesi kapsamı — ilgili geri ödeme "
                "kuralları geçerlidir (§3.1.2(1))."
            ),
        },
    },
]


def load_ek3_annex_header_clause_ids() -> frozenset[str]:
    if not _EK3_HEADER_IDS_PATH.is_file():
        return frozenset()
    payload = json.loads(_EK3_HEADER_IDS_PATH.read_text(encoding="utf-8"))
    return frozenset(str(item) for item in payload)
