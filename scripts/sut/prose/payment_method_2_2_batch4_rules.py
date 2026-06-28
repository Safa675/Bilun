"""C2 batch 4 — remaining §2.2 p1/p2 deontic clauses (telehealth, evde sağlık, NO_PAY)."""

from __future__ import annotations

from typing import Any

# Gate B clause IDs from L2.2_payment_method_prose.csv (p1_encode + p2_encode, not in batch-1/2/3).
BATCH4_RULES: list[dict[str, Any]] = [
    {
        "rule_id": "2.2.1.B-1.(5).multi_specialty_same_day_no_visit",
        "sut_section": "2.2.1.B-1",
        "condition": {
            "care_setting": "inpatient",
            "same_day_multi_specialty_outpatient": True,
            "procedure_in_annex": "EK-2/C",
        },
        "action": {
            "payment_method": "package",
            "payment_method_tr": (
                "aynı gün çoklu uzmanlık ayakta sonrası yatarak EK-2/C — "
                "EK-2/A muayene faturalandırılamaz"
            ),
            "bill_visit_fee": False,
            "visit_fee_annex": "EK-2/A",
        },
        "gate_b_sources": ["C000565"],
        "encode_batch": "C2b",
    },
    {
        "rule_id": "2.2.1.B-1.(8).reported_therapy_subsequent_days",
        "sut_section": "2.2.1.B-1",
        "condition": {
            "care_setting": "outpatient",
            "therapy_type": "reported_hyperbaric_physio_eswl",
            "visit_sequence": "subsequent_day_after_report",
        },
        "action": {
            "payment_method": "itemized",
            "payment_method_tr": (
                "sağlık raporlu hiperbarik/fizik tedavi/ESWL-ESWT — "
                "rapor sonrası günlerde EK-2/B + EK-2/A-2"
            ),
            "bill_visit_fee": True,
            "visit_fee_annex": "EK-2/A-2",
        },
        "gate_b_sources": ["C000568"],
        "encode_batch": "C2b",
    },
    {
        "rule_id": "2.2.1.B-1.c.training_hospital_outpatient",
        "sut_section": "2.2.1.B-1",
        "condition": {
            "care_setting": "outpatient",
            "facility_type": "training_research_hospital",
        },
        "action": {
            "payment_method": "itemized",
            "payment_method_tr": (
                "eğitim/araştırma hastanesi ayakta — EK-2/B poliklinik + EK-2/A-2 esas"
            ),
            "visit_fee_annex": "EK-2/B",
        },
        "gate_b_sources": ["C000573"],
        "encode_batch": "C2c",
    },
    {
        "rule_id": "2.2.1.B-2.(4).training_hospital_inpatient",
        "sut_section": "2.2.1.B-2",
        "condition": {
            "care_setting": "inpatient",
            "facility_type": "training_research_hospital",
        },
        "action": {
            "payment_method": "itemized",
            "payment_method_tr": (
                "eğitim/araştırma hastanesi yatarak — EK-2/B ve EK-2/Ç puanları esas"
            ),
            "bill_materials_separately": True,
            "bill_drugs_separately": True,
        },
        "gate_b_sources": ["C000612"],
        "encode_batch": "C2a",
    },
    {
        "rule_id": "2.2.1.B-3.(2).home_health_10day_cooldown",
        "sut_section": "2.2.1.B-3",
        "condition": {
            "care_setting": "outpatient",
            "line_type": "home_health",
            "procedure_code": "P920010",
            "prior_outpatient_same_provider_days_lt": 10,
        },
        "action": {
            "payment_method": "package",
            "payment_method_tr": (
                "ayaktan başvuru günü dahil 10 gün içinde P920010 evde sağlık "
                "ikinci kez faturalandırılamaz"
            ),
            "billable": False,
            "max_bill_count": 0,
        },
        "gate_b_sources": ["C000619"],
        "encode_batch": "C2b",
    },
    {
        "rule_id": "2.2.1.B-3.(4).epidermolysis_home_wound_care",
        "sut_section": "2.2.1.B-3",
        "condition": {
            "care_setting": "home",
            "line_type": "home_health",
            "diagnosis": "epidermolysis_bullosa",
            "procedure_code": "530533",
        },
        "action": {
            "payment_method": "itemized",
            "payment_method_tr": (
                "epidermolizis bülloza evde yara bakımı — EK-2/B 530533 esas"
            ),
            "procedure_in_annex": "EK-2/B",
        },
        "gate_b_sources": ["C000621"],
        "encode_batch": "C2b",
    },
    {
        "rule_id": "2.2.1.B-4.(1).telehealth_520032_billing",
        "sut_section": "2.2.1.B-4",
        "condition": {
            "care_setting": "outpatient",
            "line_type": "telehealth",
            "procedure_code": "520032",
        },
        "action": {
            "payment_method": "itemized",
            "payment_method_tr": (
                "uzaktan hasta değerlendirme — EK-2/B 520032 işlem kodu esas"
            ),
            "procedure_in_annex": "EK-2/B",
        },
        "gate_b_sources": ["C000624"],
        "encode_batch": "C2b",
    },
    {
        "rule_id": "2.2.1.B-4.(4).same_specialty_10day_no_visit",
        "sut_section": "2.2.1.B-4",
        "condition": {
            "care_setting": "outpatient",
            "same_specialty_repeat_days_lt": 10,
            "emergency_excluded": True,
            "procedure_in_annex": "EK-2/A",
        },
        "action": {
            "payment_method": "itemized",
            "payment_method_tr": (
                "aynı uzmanlık 10 gün içinde tekrar ayakta — EK-2/A muayene yok "
                "(acil hariç)"
            ),
            "bill_visit_fee": False,
            "billable": False,
        },
        "gate_b_sources": ["C000627"],
        "encode_batch": "C2c",
    },
    {
        "rule_id": "2.2.1.B-4.(5).same_specialty_10day_no_telehealth",
        "sut_section": "2.2.1.B-4",
        "condition": {
            "care_setting": "outpatient",
            "same_specialty_repeat_days_lt": 10,
            "emergency_excluded": True,
            "procedure_code": "520032",
        },
        "action": {
            "payment_method": "itemized",
            "payment_method_tr": (
                "aynı uzmanlık 10 gün içinde tekrar — 520032 uzaktan değerlendirme yok "
                "(acil hariç)"
            ),
            "billable": False,
        },
        "gate_b_sources": ["C000628"],
        "encode_batch": "C2c",
    },
    {
        "rule_id": "2.2.2.A(6).training_hospital_itemized",
        "sut_section": "2.2.2.A",
        "condition": {
            "care_setting": "inpatient",
            "payment_method_path": "itemized",
            "facility_type": "training_research_hospital",
        },
        "action": {
            "payment_method": "itemized",
            "payment_method_tr": (
                "eğitim/araştırma hastanesi hizmet başına ödeme — EK-2/B ve EK-2/Ç esas"
            ),
            "bill_materials_separately": True,
            "bill_drugs_separately": True,
        },
        "gate_b_sources": ["C000652"],
        "encode_batch": "C2a",
    },
    {
        "rule_id": "2.2.(5).interim_supplier_spa_reimbursement",
        "sut_section": "2.2",
        "condition": {
            "provider_type": "medical_supplier_or_spa",
            "contract_status": "pending",
        },
        "action": {
            "payment_method": "itemized",
            "payment_method_tr": (
                "tıbbi malzeme tedarikçisi/kaplıca — sözleşme öncesi kişiye ödeme "
                "(Kurum faturalandırması yok)"
            ),
            "billable": False,
            "payer": "individual_reimbursement",
        },
        "gate_b_sources": ["C000523"],
        "encode_batch": "C2b",
    },
    {
        "rule_id": "2.2.(6).workplace_polyclinic_homecare_no_pay",
        "sut_section": "2.2",
        "condition": {
            "provider_type": "workplace_health_or_polyclinic_or_homecare_center",
        },
        "action": {
            "payment_method": "itemized",
            "payment_method_tr": (
                "işyeri sağlık birimi/özel poliklinik/evde bakım merkezi — "
                "Kurumdan ücret talep edilemez"
            ),
            "billable": False,
        },
        "gate_b_sources": ["C000524"],
        "encode_batch": "C2b",
    },
    {
        "rule_id": "2.2.2.A(4).ivd_kit_control_no_pay",
        "sut_section": "2.2.2.A",
        "condition": {
            "care_setting": "inpatient",
            "line_type": "ivd_kit_control",
            "excluded_test_types": ("seroconversion_panel", "confirmatory"),
        },
        "action": {
            "payment_method": "itemized",
            "payment_method_tr": (
                "invitro diyagnostik kit kontrol testleri (serokonversiyon/doğrulama "
                "hariç) Kurumca karşılanmaz"
            ),
            "billable": False,
        },
        "gate_b_sources": ["C000644"],
        "encode_batch": "C2a",
    },
]
