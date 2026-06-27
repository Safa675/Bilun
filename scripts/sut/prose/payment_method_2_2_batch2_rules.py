"""C2 batch 2 — next §2.2 deontic clauses (ayakta mix, billing prohibitions, komplikasyon)."""

from __future__ import annotations

from typing import Any

# Gate B clause IDs from L2.2_payment_method_prose.csv (p1_encode, not in batch-1 manifest).
BATCH2_RULES: list[dict[str, Any]] = [
    {
        "rule_id": "2.2.(3).aesthetic_must_not_bill",
        "sut_section": "2.2",
        "condition": {
            "billing_purpose": "aesthetic",
            "work_injury_or_congenital_excluded": True,
        },
        "action": {
            "payment_method": "itemized",
            "payment_method_tr": "estetik amaçlı hizmetler Kuruma faturalandırılamaz",
            "billable": False,
        },
        "gate_b_sources": ["C000521"],
        "encode_batch": "C2b",
    },
    {
        "rule_id": "2.2.(8).contracted_tetkik_mandatory",
        "sut_section": "2.2",
        "condition": {
            "provider_contract_status": "contracted",
            "care_setting": "any",
        },
        "action": {
            "payment_method": "itemized",
            "payment_method_tr": "sözleşmeli kuruluş tetkik/tahlil zorunluluğu",
            "tetkik_supply": "in_house_or_procurement",
        },
        "gate_b_sources": ["C000526"],
        "encode_batch": "C2b",
    },
    {
        "rule_id": "2.2.(12).no_pay_without_documentation",
        "sut_section": "2.2",
        "condition": {
            "provider_contract_status": "contracted",
            "documentation_on_request": False,
        },
        "action": {
            "payment_method": "itemized",
            "payment_method_tr": "bilgi/belge ibraz edilemeyen tetkik/tahlil bedeli ödenmez",
            "billable": False,
        },
        "gate_b_sources": ["C000530"],
        "encode_batch": "C2b",
    },
    {
        "rule_id": "2.2.(13).health_report_single_bill",
        "sut_section": "2.2",
        "condition": {
            "line_type": "health_report",
            "report_annex": "EK-2/B",
        },
        "action": {
            "payment_method": "itemized",
            "payment_method_tr": "sağlık raporu bedeli EK-2/B puanları — sadece bir adet",
            "max_bill_count": 1,
        },
        "gate_b_sources": ["C000531"],
        "encode_batch": "C2b",
    },
    {
        "rule_id": "2.2.(14).committee_report_exam_fee",
        "sut_section": "2.2",
        "condition": {
            "requires_health_committee_report": True,
            "line_type": "examination",
        },
        "action": {
            "payment_method": "itemized",
            "payment_method_tr": "sağlık kurulu raporu için sadece bir adet muayene bedeli",
            "max_bill_count": 1,
        },
        "gate_b_sources": ["C000532"],
        "encode_batch": "C2b",
    },
    {
        "rule_id": "2.2.1.B-1.(2).ten_day_same_specialty_no_visit",
        "sut_section": "2.2.1.B-1",
        "condition": {
            "care_setting": "outpatient",
            "same_provider_same_specialty_within_days": 10,
            "visit_type_excluded": "emergency",
        },
        "action": {
            "payment_method": "itemized",
            "payment_method_tr": "10 gün içinde aynı uzmanlık — sadece EK-2/A-2 işlemleri",
            "visit_fee_annex": "EK-2/A-2",
            "bill_visit_fee": False,
        },
        "gate_b_sources": ["C000562"],
        "encode_batch": "C2c",
    },
    {
        "rule_id": "2.2.1.B-1.(11).private_daily_visit_cap",
        "sut_section": "2.2.1.B-1",
        "condition": {
            "care_setting": "outpatient",
            "provider_type": "private",
        },
        "action": {
            "payment_method": "itemized",
            "payment_method_tr": "özel kuruluş günlük muayene sınırı — hekim×6 saat",
            "daily_visit_cap_basis": "physician_hours_x6",
            "bill_visit_fee": False,
        },
        "gate_b_sources": ["C000576"],
        "encode_batch": "C2c",
    },
    {
        "rule_id": "2.2.2.(5).gunubirlik_no_companion_fee",
        "sut_section": "2.2.2",
        "condition": {
            "care_setting": "inpatient",
            "visit_type": "gunubirlik",
            "line_type": "refakatci",
            "procedure_in_annex": "EK-2/B",
        },
        "action": {
            "payment_method": "itemized",
            "payment_method_tr": "günübirlik tedavide refakatçi bedeli ödenmez",
            "billable": False,
        },
        "gate_b_sources": ["C000637"],
        "encode_batch": "C2b",
    },
    {
        "rule_id": "2.2.2.C.(1).complication_itemized_discount",
        "sut_section": "2.2.2.C",
        "condition": {
            "care_setting": "inpatient",
            "event_type": "post_procedure_complication",
            "same_provider": True,
        },
        "action": {
            "payment_method": "itemized",
            "payment_method_tr": "komplikasyon bedelleri hizmet başına ödeme — %10 indirimli",
            "discount_rate": 0.10,
        },
        "gate_b_sources": ["C000703"],
        "encode_batch": "C2c",
    },
]
