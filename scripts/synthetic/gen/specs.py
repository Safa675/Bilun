"""Demo spec dicts for synthetic claim generation."""

from typing import Any

PAYMENT_METHOD_COMPLIANCE_DEMO_TAG = "payment_method_compliance_demo"

_DRUG_INDICATION_DEMO_SPECS: dict[str, dict[str, Any]] = {
    "bevacizumab_missing_report": {
        "scenario_tag": "sgk_drug_indication_bevacizumab_missing_report",
        "ilac_adi": "AVASTIN 400 MG IV INFUZYONLUK KONSANTRE COZELTI (BEVACIZUMAB)",
        "ilac_kodu": "SUT-DEMO-BEV",
        "barkod": "8690000000001",
        "esdeger_grup": "DEMO-BEV",
        "beklenen_red_nedeni": "Uzmanlik saglik kurulu raporu eksik",
        "beklenen_kural_izi": "4.2.14.C:bevacizumab:missing_board_report",
        "uzmanlik_kurulu_raporu_var": False,
    },
    "nivolumab_indication_mismatch": {
        "scenario_tag": "sgk_drug_indication_nivolumab_indication_mismatch",
        "ilac_adi": "OPDIVO 100 MG IV INFUZYONLUK KONSANTRE COZELTI (NIVOLUMAB)",
        "ilac_kodu": "SUT-DEMO-NIVO",
        "barkod": "8690000000002",
        "esdeger_grup": "DEMO-NIVO",
        "beklenen_red_nedeni": "Endikasyon uyumsuzlugu",
        "beklenen_kural_izi": "4.2.14.C:nivolumab:indication_mismatch",
        "uzmanlik_kurulu_raporu_var": True,
    },
    "daratumumab_report_unknown": {
        "scenario_tag": "sgk_drug_indication_daratumumab_report_unknown",
        "ilac_adi": "DARZALEX 400 MG IV INFUZYONLUK KONSANTRE COZELTI (DARATUMUMAB)",
        "ilac_kodu": "SUT-DEMO-DARA",
        "barkod": "8690000000003",
        "esdeger_grup": "DEMO-DARA",
        "beklenen_red_nedeni": "Saglik kurulu raporu dogrulanmali",
        "beklenen_kural_izi": "4.2.14.C:daratumumab:needs_report_verification",
        "uzmanlik_kurulu_raporu_var": None,
    },
    "pembrolizumab_report_ok": {
        "scenario_tag": "sgk_drug_indication_pembrolizumab_report_ok",
        "ilac_adi": "KEYTRUDA 100 MG IV INFUZYONLUK KONSANTRE COZELTI (PEMBROLIZUMAB)",
        "ilac_kodu": "SUT-DEMO-PEM",
        "barkod": "8690000000004",
        "esdeger_grup": "DEMO-PEM",
        "beklenen_red_nedeni": "",
        "beklenen_kural_izi": "",
        "uzmanlik_kurulu_raporu_var": True,
        "yatarak_tedavi_ilac": True,
    },
    "trastuzumab_report_duration_mismatch": {
        "scenario_tag": "sgk_drug_indication_trastuzumab_report_duration_mismatch",
        "ilac_adi": "HERCEPTIN 440 MG IV INFUZYONLUK KONSANTRE COZELTI (TRASTUZUMAB)",
        "ilac_kodu": "SUT-DEMO-TRAS",
        "barkod": "8690000000005",
        "esdeger_grup": "DEMO-TRAS",
        "beklenen_red_nedeni": "Saglik kurulu rapor suresi uyumsuz",
        "beklenen_kural_izi": "4.2.14.C:trastuzumab:report_duration_mismatch",
        "uzmanlik_kurulu_raporu_var": True,
        "rapor_suresi_ay": 12,
        "recete_eden_uzmanlik": "Tıbbi Onkoloji",
    },
    "trabectedin_missing_report": {
        "scenario_tag": "sgk_drug_indication_trabectedin_missing_report",
        "ilac_adi": "YONDELIS 1 MG IV INFUZYONLUK KONSANTRE COZELTI (TRABECTEDIN)",
        "ilac_kodu": "SUT-DEMO-TRAB",
        "barkod": "8690000000006",
        "esdeger_grup": "DEMO-TRAB",
        "beklenen_red_nedeni": "Uzmanlik saglik kurulu raporu eksik",
        "beklenen_kural_izi": "4.2.14.C:trabectedin:missing_board_report",
        "uzmanlik_kurulu_raporu_var": False,
    },
}

_MATERIAL_PROSE_DEMO_SPECS: dict[str, dict[str, Any]] = {
    "optical_lens_upgrade": {
        "scenario_tag": "sgk_specialty_prose_optical_lens_upgrade",
        "material_code": "SUT-DEMO-OPT",
        "material_name": "Gözlük camı fark ücreti talebi",
        "material_type": "goz",
        "specialty_category": "goz",
        "unit_price": 450.0,
        "expected_rule_id": "3.3.3.A.(4).ek3d_lens_upgrade_difference",
        "specialty_flags": {"optical_lens_upgrade_difference_claim": True},
    },
    "hip_graft_no_pay": {
        "scenario_tag": "sgk_specialty_prose_hip_graft_no_pay",
        "material_code": "SUT-DEMO-GRF",
        "material_name": "Kalça protezi greft malzemesi",
        "material_type": "ortopedi",
        "specialty_category": "ortopedi",
        "unit_price": 3200.0,
        "expected_rule_id": "3.3.4.(6).hip_arthroplasty_graft_no_pay",
        "specialty_flags": {"hip_arthroplasty_graft_claim": True},
    },
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
        # Anchor: an oncology drug billed without the mandatory indication report.
        "anchor": {
            "type": "drug",
            "ilac_adi": "BEVACİZUMAB 400 MG FLK",
            "ilac_kodu": "SUT-DEMO-BEV",
            "barkod": "8690000000001",
            "esdeger_grup": "bevasizumab",
            "uzmanlik_kurulu_raporu_var": False,
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
