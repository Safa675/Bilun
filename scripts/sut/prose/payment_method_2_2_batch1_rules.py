"""C2 batch 1 — high-priority §2.2 deontic clauses (paket/kalem, yatak, tier)."""

from __future__ import annotations

from typing import Any

# Gate B clause IDs from L2.2_payment_method_prose.csv (p1_encode, not session).
BATCH1_RULES: list[dict[str, Any]] = [
    {
        "rule_id": "2.2.2.A(1).itemized_basis",
        "sut_section": "2.2.2.A",
        "condition": {
            "care_setting": "inpatient",
            "payment_method_path": "itemized",
        },
        "action": {
            "payment_method": "itemized",
            "payment_method_tr": "hizmet başına ödeme — EK-2/B ve EK-2/Ç esas",
            "bill_materials_separately": True,
            "bill_drugs_separately": True,
        },
        "gate_b_sources": ["C000639"],
        "encode_batch": "C2a",
    },
    {
        "rule_id": "2.2.2.A(2).itemized_materials_drugs",
        "sut_section": "2.2.2.A",
        "condition": {
            "care_setting": "inpatient",
            "payment_method_path": "itemized",
        },
        "action": {
            "payment_method": "itemized",
            "payment_method_tr": "hizmet başına ödeme — temin edilen ilaç/malzeme ayrı",
            "bill_materials_separately": True,
            "bill_drugs_separately": True,
        },
        "gate_b_sources": ["C000640"],
        "encode_batch": "C2a",
    },
    {
        "rule_id": "2.2.2.(3).short_stay_day_bed",
        "sut_section": "2.2.2",
        "condition": {
            "care_setting": "inpatient",
            "stay_duration_hours_lt": 24,
        },
        "action": {
            "payment_method": "itemized",
            "payment_method_tr": "24 saatten kısa yatışta gündüz yatak bedeli",
            "bed_fee_basis": "day_rate",
        },
        "gate_b_sources": ["C000635"],
        "encode_batch": "C2b",
    },
    {
        "rule_id": "2.2.2.(4).gunubirlik_no_day_bed",
        "sut_section": "2.2.2",
        "condition": {
            "care_setting": "inpatient",
            "visit_type": "gunubirlik",
            "procedure_in_annex": "EK-2/C",
        },
        "action": {
            "payment_method": "package",
            "payment_method_tr": "günübirlik EK-2/C işlemlerde gündüz yatak bedeli yok",
            "bill_day_bed": False,
        },
        "gate_b_sources": ["C000636"],
        "encode_batch": "C2b",
    },
    {
        "rule_id": "2.2.2.A(3).companion_fee_itemized",
        "sut_section": "2.2.2.A",
        "condition": {
            "care_setting": "inpatient",
            "payment_method_path": "itemized",
            "line_type": "refakatci",
        },
        "action": {
            "payment_method": "itemized",
            "payment_method_tr": "refakatçi bedeli — §2.6.3(2) esas",
            "bill_materials_separately": False,
            "bill_drugs_separately": False,
        },
        "gate_b_sources": ["C000641"],
        "encode_batch": "C2b",
    },
    {
        "rule_id": "2.2.1.(20).class3_package_surcharge",
        "sut_section": "2.2.1",
        "condition": {
            "facility_class": "EK-2/A-1.Sınıf-3",
            "procedure_in_annex": "EK-2/C-1",
        },
        "action": {
            "payment_method": "package",
            "payment_method_tr": "Sınıf-3 EK-2/C-1 işlem oranı ilavesi ile paket",
            "bill_materials_separately": True,
            "bill_drugs_separately": True,
        },
        "gate_b_sources": ["C000538"],
        "encode_batch": "C2c",
    },
    {
        "rule_id": "2.2.1.B-2.(2).g.no_visit_fee",
        "sut_section": "2.2.1.B-2",
        "condition": {
            "care_setting": "inpatient",
            "payment_method_path": "itemized",
            "service_category": "hizmet_basi_listed",
        },
        "action": {
            "payment_method": "itemized",
            "payment_method_tr": "hizmet başına ödeme — EK-2/A muayene tutarı faturalandırılamaz",
            "visit_fee_annex": None,
            "bill_materials_separately": True,
            "bill_drugs_separately": True,
        },
        "gate_b_sources": ["C000606"],
        "encode_batch": "C2c",
    },
]
