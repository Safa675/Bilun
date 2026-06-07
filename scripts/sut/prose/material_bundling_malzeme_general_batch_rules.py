"""L1.4 Phase 8 — malzeme_general theme batch (85 corpus rows)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_HEADER_IDS_PATH = Path("data/gazette/prose_manifests/L1.4_malzeme_general_header_clause_ids.json")

SUT_MATERIAL_LIST_PRICE_CEILING_CLAUSE_IDS: frozenset[str] = frozenset(
    {
        "C001628",
        "C001833",
        "C001836",
    }
)

MALZEME_SCOPE_ONLY_CLAUSE_IDS: frozenset[str] = frozenset(
    {
        "C001616",
        "C002683",
        "C001667",
        "C001665",
    }
)

_REPORT_PRESCRIPTION_SOURCES: list[str] = [
    "C001668",
    "C002759",
    "C001670",
    "C001731",
    "C001732",
    "C002719",
    "C002753",
    "C002760",
    "C002764",
    "C001733",
    "C002761",
    "C001790",
    "C002792",
    "C001791",
    "C002793",
    "C001730",
    "C002758",
    "C001735",
    "C002762",
    "C002734",
    "C001725",
    "C001726",
    "C001727",
    "C001728",
    "C001729",
]

_UNLISTED_SURCHARGE_SOURCES: list[str] = [
    "C001831",
    "C001839",
    "C002823",
    "C002830",
    "C001830",
    "C001844",
    "C002690",
    "C002766",
    "C002790",
    "C002797",
    "C002827",
]

_FACILITY_CONTRACT_SCOPE_SOURCES: list[str] = [
    "C001663",
    "C001737",
    "C002688",
    "C001848",
    "C002825",
    "C001818",
    "C002715",
    "C001825",
]

MALZEME_GENERAL_BATCH_RULES: list[dict[str, Any]] = [
    {
        "rule_id": "3.1.1.(6).inpatient_facility_supply_violation",
        "sut_section": "3.1.1",
        "deontic": "MANDATORY",
        "gate_b_sources": ["C001623", "C002687"],
        "condition": {"inpatient_material_facility_supply_violation": True},
        "action": {
            "material_outcome": "no_pay",
            "severity": "error",
            "message_tr": (
                "Yatarak tedavide malzeme kurumca temin edilmeli — hastaya "
                "reçete ile dışarıdan temin uygunsuz (§3.1.1(5)/(6))."
            ),
        },
    },
    {
        "rule_id": "3.1.1.(7).non_reimbursed_inpatient_patient_charge",
        "sut_section": "3.1.1",
        "deontic": "NO_PAY",
        "gate_b_sources": ["C001624"],
        "condition": {"non_reimbursed_inpatient_patient_charge": True},
        "action": {
            "material_outcome": "no_pay",
            "severity": "warning",
            "message_tr": (
                "Karşılanmayan yatarak malzeme — hasta bilgilendirme/mahsup "
                "kurallarına uygun faturalandırma (§3.1.1(7))."
            ),
        },
    },
    {
        "rule_id": "3.1.3.(10).lab_material_separate_billing",
        "sut_section": "3.1.3",
        "deontic": "MUST_NOT_BILL",
        "gate_b_sources": ["C001795"],
        "condition": {"lab_material_separate_billing": True},
        "action": {
            "material_outcome": "must_not_bill_separately",
            "severity": "error",
            "message_tr": (
                "Laboratuvar malzemesi işlem bedeline dahil — ayrıca "
                "faturalandırılamaz (§3.1.3(10))."
            ),
        },
    },
    {
        "rule_id": "3.1.3.(3).shared_consumable_wrong_branch_billing",
        "sut_section": "3.1.3",
        "deontic": "NO_PAY",
        "gate_b_sources": ["C001788"],
        "condition": {"shared_consumable_wrong_branch_billing": True},
        "action": {
            "material_outcome": "no_pay",
            "severity": "error",
            "message_tr": (
                "Çok branşlı sarf malzemesi kullanıldığı branştan "
                "faturalandırılmalı (§3.1.3(3))."
            ),
        },
    },
    {
        "rule_id": "3.1.2.(6).prescription_quantity_exceeded",
        "sut_section": "3.1.2",
        "deontic": "NO_PAY",
        "gate_b_sources": ["C001663"],
        "condition": {"material_prescription_quantity_exceeded": True},
        "action": {
            "material_outcome": "no_pay",
            "severity": "error",
            "message_tr": (
                "Reçete miktarı SUT limitini aşıyor — fazla adet "
                "Kurumca karşılanmaz (§3.1.2(6))."
            ),
        },
    },
    {
        "rule_id": "3.1.2.report_prescription_invalid",
        "sut_section": "3.1.2",
        "deontic": "REGULATORY_ACTION",
        "gate_b_sources": _REPORT_PRESCRIPTION_SOURCES,
        "condition": {"material_report_prescription_invalid": True},
        "action": {
            "material_outcome": "review_required",
            "severity": "warning",
            "message_tr": (
                "Malzeme sağlık raporu/reçete süresi veya basamak şartı "
                "sağlanmıyor (§3.1.2 / §3.1.2.2)."
            ),
        },
    },
    {
        "rule_id": "3.1.2.b.material_invoice_documentation_incomplete",
        "sut_section": "3.1.2",
        "deontic": "NO_PAY",
        "gate_b_sources": ["C001652", "C002711"],
        "condition": {"material_invoice_documentation_incomplete": True},
        "action": {
            "material_outcome": "no_pay",
            "severity": "error",
            "message_tr": (
                "Fatura eki belge eksik (ruhsatname/sorumlu müdür vb.) — "
                "malzeme ödenmez (§3.1.2(b))."
            ),
        },
    },
    {
        "rule_id": "3.1.4.diagnosis_package_material_unbundled",
        "sut_section": "3.1.4",
        "deontic": "REGULATORY_ACTION",
        "gate_b_sources": ["C001819", "C002818", "C002801"],
        "condition": {"diagnosis_package_material_unbundled": True},
        "action": {
            "material_outcome": "review_required",
            "severity": "info",
            "message_tr": (
                "Tanıya dayalı paket dışı malzeme — EK-2/C ve SUT paket "
                "kurallarına uygunluk doğrulanmalı (§3.1.4)."
            ),
        },
    },
    {
        "rule_id": "3.2.3.emergency_uncontracted_facility_material",
        "sut_section": "3.2.3",
        "deontic": "REGULATORY_ACTION",
        "gate_b_sources": ["C001854", "C002836"],
        "condition": {"emergency_uncontracted_facility_material": True},
        "action": {
            "material_outcome": "review_required",
            "severity": "warning",
            "message_tr": (
                "Sözleşmesiz kurumda acil malzeme — SUT 2.3 acil ödeme "
                "koşulları doğrulanmalı (§3.2.3(1))."
            ),
        },
    },
    {
        "rule_id": "3.2.1.unlisted_material_surcharge_billing",
        "sut_section": "3.2.1",
        "deontic": "REGULATORY_ACTION",
        "gate_b_sources": _UNLISTED_SURCHARGE_SOURCES,
        "condition": {"unlisted_material_surcharge_billing": True},
        "action": {
            "material_outcome": "review_required",
            "severity": "info",
            "message_tr": (
                "Listesiz/fiyatsız malzeme — işletme gideri ve kesinti "
                "kurallarına uygun fiyat doğrulanmalı (§3.2.1)."
            ),
        },
    },
    {
        "rule_id": "3.1.2.g.wheelchair_dual_prescription_invalid",
        "sut_section": "3.1.2",
        "deontic": "NO_PAY",
        "gate_b_sources": ["C002746"],
        "condition": {"wheelchair_dual_prescription_invalid": True},
        "action": {
            "material_outcome": "no_pay",
            "severity": "error",
            "message_tr": (
                "Manuel ve akülü tekerlekli sandalye aynı anda reçete "
                "edilemez (§3.1.2(g))."
            ),
        },
    },
    {
        "rule_id": "3.1.2.(16).outpatient_contract_center_supply_required",
        "sut_section": "3.1.2",
        "deontic": "REGULATORY_ACTION",
        "gate_b_sources": ["C002748"],
        "condition": {"outpatient_contract_center_supply_required": True},
        "action": {
            "material_outcome": "review_required",
            "severity": "warning",
            "message_tr": (
                "Ayakta tedavi malzemesi sözleşmeli merkez/eczaneden "
                "temin edilmeli (§3.1.2(16))."
            ),
        },
    },
    {
        "rule_id": "3.1.2.a.child_growth_miat_renewal_claim",
        "sut_section": "3.1.2",
        "deontic": "REGULATORY_ACTION",
        "gate_b_sources": ["C002726"],
        "condition": {"child_growth_miat_renewal_claim": True},
        "action": {
            "material_outcome": "review_required",
            "severity": "info",
            "message_tr": (
                "Çocuk büyüme-gelişme MIAT yenileme — sağlık raporu ile "
                "erken yenileme koşulları (§3.1.2(a))."
            ),
        },
    },
    {
        "rule_id": "3.1.1.facility_contract_material_supply_scope",
        "sut_section": "3.1.1",
        "deontic": "REGULATORY_ACTION",
        "gate_b_sources": _FACILITY_CONTRACT_SCOPE_SOURCES,
        "condition": {"facility_contract_material_supply_scope": True},
        "action": {
            "material_outcome": "review_required",
            "severity": "info",
            "message_tr": (
                "Sözleşmeli kurum malzeme temin kapsamı — ilgili SUT "
                "temin/teslim şartları geçerlidir."
            ),
        },
    },
]


def load_malzeme_general_header_clause_ids() -> frozenset[str]:
    if not _HEADER_IDS_PATH.is_file():
        return frozenset()
    payload = json.loads(_HEADER_IDS_PATH.read_text(encoding="utf-8"))
    return frozenset(str(item) for item in payload)
