"""Demo spec dicts for synthetic claim generation."""

from typing import Any

PAYMENT_METHOD_COMPLIANCE_DEMO_TAG = "payment_method_compliance_demo"

_COPAY_EXEMPTION_DEMO_SPECS: dict[str, dict[str, Any]] = {
    "acil_servis": {
        "scenario_tag": "copay_exemption_acil_demo",
        "expected_category": "acil_servis",
    },
    "yesil_kart": {
        "scenario_tag": "copay_exemption_yesil_kart_demo",
        "expected_category": "yesil_kart",
    },
    "ek1a_chronic": {
        "scenario_tag": "copay_exemption_ek1a_demo",
        "expected_category": "ek1a_chronic",
        "primary_icd10": "E11.9",
    },
}

COPAY_EXEMPTION_DEMO_PATIENTS: dict[str, str] = {
    "SENTETIK-HASTA-0034": "acil_servis",
    "SENTETIK-HASTA-0035": "yesil_kart",
    "SENTETIK-HASTA-0036": "ek1a_chronic",
}

_MATERIAL_PROSE_DEMO_SPECS: dict[str, dict[str, Any]] = {
    "kdv_ceiling_exceeded": {
        "scenario_tag": "sgk_material_kdv_ceiling_exceeded",
        "material_code": "OP1592",
        "material_name": "ICD kalp pili",
        "material_type": "cihaz",
        "specialty_category": "kardiyoloji",
        "unit_price": 999999.0,
    },
    "procurement_incomplete": {
        "scenario_tag": "sgk_material_bundling_procurement_incomplete",
        "material_code": "OP1000",
        "material_name": "İhale ekranı eksik sözleşmeli malzeme",
        "material_type": "ortez",
        "specialty_category": "ortopedi",
        "unit_price": 850.0,
        "expected_rule_id": "3.1.1.(5).procurement_screen_incomplete",
        "prose_flags": {"ihale_ekrani_eksik_mi": True},
    },
}

_CLAIM_READINESS_DEMO_SPECS: dict[str, dict[str, Any]] = {
    "uts_barcode_missing": {
        "scenario_tag": "sgk_claim_readiness_uts_barcode_missing",
        "material_code": "OP2000",
        "material_name": "ÜTS kaydı eksik implant malzemesi",
        "material_type": "implant",
        "specialty_category": "ortopedi",
        "unit_price": 4200.0,
        "prose_flags": {
            "uts_kayitli_mi": False,
            "titubb_uts_barkod_belge_eksik": True,
        },
    },
}

_MEDULA_DEMO_SPECS: dict[str, dict[str, Any]] = {
    "0012": {
        "scenario_tag": "medula_rejection_1688_molecular_microbiology",
        "visit_date": "2024-07-15",
        "sonuc_kodu": "1688",
        "hata_kodu": "1688",
        "hata_mesaji": (
            "Moleküler mikrobiyoloji işlemi için zorunlu rapor eksik"
        ),
        "medula_asamasi": "fatura_kayit",
        # Anchor: a real molecular-microbiology procedure on the claim so the
        # rejection points at the very procedure the missing report concerns.
        "anchor": {
            "type": "procedure",
            "code": "912550",
            "category": "islem",
        },
    },
    "0018": {
        "scenario_tag": "medula_rejection_0612_board_report_missing",
        "visit_date": "2024-08-20",
        "sonuc_kodu": "0612",
        "hata_kodu": "0612",
        "hata_mesaji": (
            "Uzmanlık sağlık kurulu raporu eksik — işlem faturalanamaz"
        ),
        "medula_asamasi": "fatura_kayit",
        # Anchor: a procedure that legally requires a specialty board report.
        "anchor": {
            "type": "procedure",
            "code": "612160",
            "category": "islem",
        },
    },
    "0025": {
        "scenario_tag": "medula_rejection_1205_service_date_mismatch",
        "visit_date": "2024-09-01",
        "sonuc_kodu": "1205",
        "hata_kodu": "1205",
        "hata_mesaji": "Hizmet tarihi uyumsuz — provizyon ile eşleşmiyor",
        "medula_asamasi": "fatura_kayit",
        # Anchor: a procedure whose service date is the subject of the mismatch
        # (the rejection message carries the date-mismatch semantics; the line
        # itself stays within the claim window to satisfy date validation).
        "anchor": {
            "type": "procedure",
            "code": "620030",
            "category": "islem",
        },
    },
    "0026": {
        "scenario_tag": "medula_rejection_0521_provision_not_obtained",
        "visit_date": "2024-09-10",
        "sonuc_kodu": "0521",
        "hata_kodu": "0521",
        "hata_mesaji": "Provizyon onay alınmamış — işlem faturalanamaz",
        "medula_asamasi": "provizyon",
        # Anchor: a high-cost procedure that requires prior provizyon.
        "anchor": {
            "type": "procedure",
            "code": "801510",
            "category": "islem",
        },
    },
    "0027": {
        "scenario_tag": "medula_rejection_0315_specialty_mismatch",
        "visit_date": "2024-09-15",
        "sonuc_kodu": "0315",
        "hata_kodu": "0315",
        "hata_mesaji": "Branş uyumsuz — uzmanlık bilgisi hatalı",
        "medula_asamasi": "fatura_kayit",
        # Anchor: a procedure whose specialty differs from the claim department.
        "anchor": {
            "type": "procedure",
            "code": "700620",
            "category": "islem",
        },
    },
    "0028": {
        "scenario_tag": "medula_rejection_0901_duplicate_procedure",
        "visit_date": "2024-09-20",
        "sonuc_kodu": "0901",
        "hata_kodu": "0901",
        "hata_mesaji": "Mükerrer işlem — aynı gün tekrar faturalandırılamaz",
        "medula_asamasi": "fatura_kayit",
        # Anchor: the same procedure billed twice (the 2nd copy is the duplicate).
        "anchor": {
            "type": "procedure_duplicate",
            "code": "615430",
            "category": "islem",
        },
    },
    "0029": {
        "scenario_tag": "medula_rejection_0704_uts_barcode_missing",
        "visit_date": "2024-09-25",
        "sonuc_kodu": "0704",
        "hata_kodu": "0704",
        "hata_mesaji": "Malzeme ÜTS barkod kaydı eksik veya geçersiz",
        "medula_asamasi": "fatura_kayit",
        # Anchor: a real material on the claim whose ÜTS barcode registration is missing.
        "anchor": {
            "type": "material",
            "material_code": "AP1030",
            "material_name": "Omuz artroplasti implantı",
            "material_type": "implant",
            "specialty_category": "ortopedi",
            "unit_price": 12500.0,
            "prose_flags": {"uts_kayitli_mi": False, "titubb_uts_barkod_belge_eksik": True},
        },
    },
    "0030": {
        "scenario_tag": "medula_rejection_0320_package_bundled_procedure",
        "visit_date": "2024-10-01",
        "sonuc_kodu": "0320",
        "hata_kodu": "0320",
        "hata_mesaji": "Paket kapsamındaki işlem ayrı faturalandırılamaz",
        "medula_asamasi": "fatura_kayit",
        # Anchor: a package header plus one bundled component billed separately.
        "anchor": {
            "type": "procedure_bundled",
            "package_code": "609300",
            "package_price": 9000.0,
            "component_code": "600160",
        },
    },
    "0031": {
        "scenario_tag": "medula_rejection_0411_drug_report_missing",
        "visit_date": "2024-10-05",
        "sonuc_kodu": "0411",
        "hata_kodu": "0411",
        "hata_mesaji": "İlaç endikasyon raporu eksik — sağlık kurulu onayı gerekli",
        "medula_asamasi": "fatura_kayit",
        # Claim-level rejection (drug report missing) — no specific line anchor.
        # The fake SUT-DEMO-BEV drug anchor was purged; the rejection message
        # carries the semantics and the playbook matches on sonuc_kodu 0411.
        "anchor": {
            "type": "claim",
        },
    },
    "0032": {
        "scenario_tag": "medula_rejection_1102_uncontracted_facility",
        "visit_date": "2024-10-10",
        "sonuc_kodu": "1102",
        "hata_kodu": "1102",
        "hata_mesaji": "Sözleşmesiz kurum — SGK anlaşması bulunamadı",
        "medula_asamasi": "fatura_kayit",
        # Claim-level rejection (facility contract) — no specific line anchor.
        "anchor": {
            "type": "claim",
        },
    },
}
