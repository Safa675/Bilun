"""C2 batch 3 — §2.2 deontic clauses (ayakta mix, evde sağlık, komorbidite)."""

from __future__ import annotations

from typing import Any

# Gate B clause IDs from L2.2_payment_method_prose.csv (p1_encode, not in batch-1/2 manifest).
BATCH3_RULES: list[dict[str, Any]] = [
    {
        "rule_id": "2.2.1.B-1.(3).deferred_ek2a2_no_second_visit",
        "sut_section": "2.2.1.B-1",
        "condition": {
            "care_setting": "outpatient",
            "procedure_in_annex": "EK-2/A-2",
            "deferred_same_provider": True,
        },
        "action": {
            "payment_method": "itemized",
            "payment_method_tr": "randevulu EK-2/A-2 işlem — EK-2/A muayene ikinci kez faturalandırılamaz",
            "bill_visit_fee": False,
            "visit_fee_annex": "EK-2/A",
        },
        "gate_b_sources": ["C000563"],
        "encode_batch": "C2b",
    },
    {
        "rule_id": "2.2.1.B-1.(4).same_day_outpatient_to_inpatient",
        "sut_section": "2.2.1.B-1",
        "condition": {
            "care_setting": "inpatient",
            "same_day_outpatient_visit": True,
            "procedure_in_annex": "EK-2/C",
        },
        "action": {
            "payment_method": "package",
            "payment_method_tr": "aynı gün ayaktan→yatarak EK-2/C — ayakta işlemler B-1(1) esas",
            "bill_materials_separately": True,
            "bill_drugs_separately": True,
        },
        "gate_b_sources": ["C000564"],
        "encode_batch": "C2b",
    },
    {
        "rule_id": "2.2.1.B-1.(6).followup_specialty_no_visit_fee",
        "sut_section": "2.2.1.B-1",
        "condition": {
            "care_setting": "outpatient",
            "visit_sequence": "followup_same_day",
        },
        "action": {
            "payment_method": "itemized",
            "payment_method_tr": "aynı gün takip uzmanlık — EK-2/A muayene yok; EK-2/B poliklinik + EK-2/A-2",
            "bill_visit_fee": False,
            "visit_fee_annex": "EK-2/B",
        },
        "gate_b_sources": ["C000566"],
        "encode_batch": "C2c",
    },
    {
        "rule_id": "2.2.1.B-1.(7).main_side_specialty_split",
        "sut_section": "2.2.1.B-1",
        "condition": {
            "care_setting": "outpatient",
            "visit_sequence": "side_specialty_same_day",
        },
        "action": {
            "payment_method": "itemized",
            "payment_method_tr": "yan dal ayakta ödeme; ana dal EK-2/B poliklinik + EK-2/A-2",
            "visit_fee_annex": "EK-2/B",
            "main_specialty_bill_visit_fee": False,
        },
        "gate_b_sources": ["C000567"],
        "encode_batch": "C2c",
    },
    {
        "rule_id": "2.2.1.B-2.a.itemized_ek2b_ek2c_basis",
        "sut_section": "2.2.1.B-2",
        "condition": {
            "care_setting": "inpatient",
            "payment_method_path": "itemized",
        },
        "action": {
            "payment_method": "itemized",
            "payment_method_tr": "hizmet başına ödeme — EK-2/B ve EK-2/Ç puanları esas",
            "bill_materials_separately": True,
            "bill_drugs_separately": True,
        },
        "gate_b_sources": ["C000592"],
        "encode_batch": "C2a",
    },
    {
        "rule_id": "2.2.1.B-3.(1).home_health_daily_cap",
        "sut_section": "2.2.1.B-3",
        "condition": {
            "care_setting": "home",
            "line_type": "home_health",
            "procedure_code": "P920010",
        },
        "action": {
            "payment_method": "package",
            "payment_method_tr": "evde sağlık P920010 — günde en fazla bir adet",
            "max_bill_count": 1,
            "procedure_in_annex": "EK-2/C",
        },
        "gate_b_sources": ["C000618"],
        "encode_batch": "C2b",
    },
    {
        "rule_id": "2.2.2.A.cross_specialty_uplift_25pt",
        "sut_section": "2.2.2.A",
        "condition": {
            "care_setting": "inpatient",
            "payment_method_path": "itemized",
            "cross_specialty": True,
        },
        "action": {
            "payment_method": "itemized",
            "payment_method_tr": "farklı uzmanlık dallarında yüzdelik oran +25 puan",
            "rate_uplift_points": 25,
        },
        "gate_b_sources": ["C000649"],
        "encode_batch": "C2c",
    },
    {
        "rule_id": "2.2.2.C.(2).comorbidity_itemized",
        "sut_section": "2.2.2.C",
        "condition": {
            "care_setting": "inpatient",
            "event_type": "comorbidity_care",
            "primary_treatment_in_progress": True,
        },
        "action": {
            "payment_method": "itemized",
            "payment_method_tr": "eşlik eden hastalık hizmetleri hizmet başına ödeme",
            "bill_materials_separately": True,
            "bill_drugs_separately": True,
        },
        "gate_b_sources": ["C000704"],
        "encode_batch": "C2c",
    },
]
