"""Export functions for the SUT synthetic data generator v2."""

from __future__ import annotations

from pathlib import Path

import pandas as pd


def _medula_rejection_export(df: pd.DataFrame) -> pd.DataFrame:
    columns = {
        "medula_red_satir_id": "rejection_event_id",
        "fatura_id": "claim_id",
        "hasta_id": "patient_id",
        "basvuru_id": "episode_id",
        "medula_asamasi": "medula_stage",
        "sonuc_kodu": "sonuc_kodu",
        "hata_kodu": "hata_kodu",
        "hata_mesaji": "hata_mesaji",
        "red_zamani": "rejection_timestamp",
        "ilgili_islem_kodu": "related_procedure_code",
        "ilgili_islem_satiri_id": "related_procedure_line_id",
    }
    if df.empty:
        return pd.DataFrame(columns=list(columns.values()))
    return df.rename(columns=columns)


def _performed_procedure_export(df: pd.DataFrame) -> pd.DataFrame:
    columns = {
        "gerceklestirilen_satir_id": "performed_line_id",
        "fatura_id": "claim_id",
        "hasta_id": "patient_id",
        "basvuru_id": "episode_id",
        "hizmet_tarihi": "service_date",
        "islem_kodu": "procedure_code",
        "islem_adi": "procedure_name",
        "kaynak": "source",
    }
    if df.empty:
        return pd.DataFrame(columns=list(columns.values()))
    return df.rename(columns=columns)


def _normalize_for_parquet(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for col in out.columns:
        if pd.api.types.is_object_dtype(out[col].dtype):
            out[col] = out[col].map(
                lambda x: None if x is None or (isinstance(x, float) and pd.isna(x)) else str(x)
            )
    return out


def _clean_anadata(basvurular: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame({
        "HASTA_ID": basvurular["hasta_id"],
        "SQ_EPISODE": basvurular["basvuru_id"],
        "EPISODE_TARIH": pd.to_datetime(basvurular["basvuru_tarihi"]),
        "TANI_YASI": basvurular["basvuru_yasi"],
        "CINSIYET": basvurular["cinsiyet"],
        "KB-S": basvurular["sistolik_tansiyon"],
        "KB-D": basvurular["diyastolik_tansiyon"],
        "Nabiz": basvurular["nabiz"],
        "SPO2": basvurular["spo2"],
        "Boy": basvurular["boy_cm"],
        "Kilo": basvurular["kilo_kg"],
        "BMI": basvurular["bmi"],
        "ILK_TANI_SON_TANI_GUN_FARKI": basvurular["tani_gun_farki"],
        "TOPLAM_GELIS_SAYISI": basvurular["hasta_toplam_gelis_sayisi"],
        "GELIS_SAYISI": basvurular["basvuru_icindeki_gelis_sayisi"],
        "GELIS_TIPI": basvurular["gelis_tipi"],
        "SERVISADI": basvurular["servis_adi"],
        "TANIKODU": basvurular["birincil_icd10"],
        "TUM_EPS_TANILAR": basvurular["tum_icd10_kodlari"],
        "TANI_TIPI": basvurular["tani_tipi"],
        "TANITARIH": pd.to_datetime(basvurular["basvuru_tarihi"]),
        "MIN_TANI_TARIH": pd.to_datetime(basvurular["ilk_tani_tarihi"]),
        "MAX_TANI_TARIH": pd.to_datetime(basvurular["son_tani_tarihi"]),
        "Hipertansiyon Hastada": basvurular["hipertansiyon_var"],
        "Kalp Damar Hastada": basvurular["kalp_damar_var"],
        "Diyabet Hastada": basvurular["diyabet_var"],
        "Kan Hastaliklari Hastada": basvurular["kan_hastaligi_var"],
        "YAKINMA": basvurular["yakinma"],
        "OYKU": basvurular["oyku"],
        "Muayene Notu": basvurular["muayene_notu"],
        "Tedavi Notu": basvurular["tedavi_notu"],
        "kohort": basvurular["kohort"],
        "donem": basvurular["donem"],
    })


def _clean_lab(labs: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame({
        "HASTA_ID": labs["hasta_id"],
        "basvuru_id": labs["basvuru_id"],
        "SUB_CODE": labs["laboratuvar_kodu"],
        "sonuc_sayisal": labs["sayisal_sonuc"],
        "sonuc_nitel": labs["nitel_sonuc"],
        "birim": labs["birim"],
        "ref_alt": labs["referans_alt"],
        "ref_ust": labs["referans_ust"],
        "anormal_mi": labs["anormal_mi"],
        "organ_sistemi": labs["organ_sistemi"],
        "kohort": labs["kohort"],
        "donem": labs["donem"],
        "tarih": pd.to_datetime(labs["test_tarihi"]),
    })


def _clean_recete(receteler: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame({
        "HASTA_ID": receteler["hasta_id"],
        "RECETE_TARIH": pd.to_datetime(receteler["recete_tarihi"]),
        "RF_EPISODE": receteler["basvuru_id"],
        "ilac_adi": receteler["ilac_adi"],
        "ilac_adi_ham": receteler["ham_ilac_adi"],
        "dozaj_ham": receteler["ham_dozaj"],
        "verilis_yolu": receteler["verilis_yolu"],
        "gun": receteler["gun"],
        "doz_mg": receteler["doz_mg"],
        "doz_birimi": receteler["doz_birimi"],
        "siklik": receteler["siklik"],
        "miktar": receteler["miktar"],
        "kohort": receteler["kohort"],
        "donem": receteler["donem"],
    })


def _write_workbook(tables: dict[str, pd.DataFrame], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        for sheet_name, df in tables.items():
            df.to_excel(writer, sheet_name=sheet_name, index=False)
            worksheet = writer.sheets[sheet_name]
            worksheet.freeze_panes = "A2"


def _write_clean_exports(tables: dict[str, pd.DataFrame], output_dir: Path) -> None:
    clean_dir = output_dir / "clean"
    clean_dir.mkdir(parents=True, exist_ok=True)
    exports = {
        "anadata_clean.parquet": _clean_anadata(tables["basvurular"]),
        "lab_clean.parquet": _clean_lab(tables["laboratuvar_sonuclari"]),
        "recete_clean.parquet": _clean_recete(tables["receteler"]),
    }
    for name, df in exports.items():
        _normalize_for_parquet(df).to_parquet(clean_dir / name, index=False)


def _english_claim_exports(tables: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    diagnosis_claims = tables["tani_satirlari"].merge(
        tables["fatura_basliklari"][["fatura_id", "hasta_id", "basvuru_id"]],
        on=["hasta_id", "basvuru_id"],
        how="left",
        validate="many_to_one",
    )
    diagnosis_claims = diagnosis_claims.assign(
        birincil_mi=diagnosis_claims["tani_rolu"].astype(str).str.casefold() == "birincil"
    )

    proc_df = tables["islem_fatura_satirlari"]
    proc_renamed = proc_df.rename(columns={
        "islem_satiri_id": "procedure_line_id",
        "fatura_id": "claim_id",
        "hasta_id": "patient_id",
        "basvuru_id": "episode_id",
        "islem_tarihi": "procedure_date",
        "islem_kodu": "procedure_code",
        "islem_adi": "procedure_name",
        "islem_kategorisi": "procedure_category",
        "adet": "quantity",
        "birim_fiyat_try": "unit_price_try",
        "fatura_tutari_try": "billed_amount_try",
        "beklenen_odenebilir_tutar_try": "expected_payable_try",
        "pakete_dahil_mi": "is_package_included",
        "paket_kodu": "package_code",
        "ilave_ucret_uygulanabilir_mi": "surcharge_applicable",
        "ilave_ucret_orani": "surcharge_rate",
        "katilim_payi_orani_uygulanabilir_mi": "copay_rate_applicable",
        "katilim_payi_orani": "copay_rate",
        "beklenen_red_nedeni": "denial_reason_expected",
        "beklenen_kural_izi": "rule_trace_expected",
    })

    return {
        "claim_headers.parquet": tables["fatura_basliklari"].rename(columns={
            "fatura_id": "claim_id", "hasta_id": "patient_id", "basvuru_id": "episode_id",
            "fatura_tipi": "claim_type", "kurum_basamagi": "facility_tier",
            "saglayici_tipi": "provider_type", "servis_adi": "department",
            "yatis_tarihi": "admission_date", "taburcu_tarihi": "discharge_date",
            "fatura_baslangic_tarihi": "claim_start_date", "fatura_bitis_tarihi": "claim_end_date",
            "birincil_icd10": "primary_icd10", "paket_adayi_mi": "package_candidate",
            "beklenen_toplam_fatura_tutari_try": "expected_total_billed_try",
            "beklenen_toplam_odenebilir_tutar_try": "expected_total_payable_try",
            "beklenen_red_nedeni": "expected_denial_reason",
            "senaryo_etiketi": "scenario_tag",
            "mesleki_kontekst": "occupational_context",
        }),
        "patient_copay_profiles.parquet": tables["hasta_katilim_payi_profilleri"].rename(
            columns={
                "hasta_id": "patient_id",
                "sgk_yararlanma_sinifi": "sgk_benefit_class",
                "gazi_sehit_durumu": "veteran_martyr_status",
                "vatani_hizmet_durumu": "national_service_status",
                "yasli_aylik_2022": "elderly_allowance_2022",
                "dogum_yili": "birth_year",
            }
        ),
        "claim_diagnoses.parquet": diagnosis_claims.rename(columns={
            "tani_satiri_id": "diagnosis_id", "fatura_id": "claim_id",
            "hasta_id": "patient_id", "basvuru_id": "episode_id",
            "icd10_kodu": "icd10_code", "birincil_mi": "is_primary",
            "tani_rolu": "diagnosis_role", "tani_tarihi": "diagnosis_date",
            "ek1a_muafiyet_iliskili_mi": "exemption_eligible",
        }),
        "procedure_claim_lines.parquet": proc_renamed,
        "performed_procedure_lines.parquet": _performed_procedure_export(
            tables.get("gerceklestirilen_islem_satirlari", pd.DataFrame())
        ),
        "medula_rejection_events.parquet": _medula_rejection_export(
            tables.get("medula_red_satirlari", pd.DataFrame())
        ),
        "material_claim_lines.parquet": tables["malzeme_fatura_satirlari"].rename(columns={
            "malzeme_satiri_id": "material_line_id", "fatura_id": "claim_id",
            "islem_satiri_id": "procedure_line_id", "hasta_id": "patient_id",
            "malzeme_tarihi": "material_date", "malzeme_kodu": "material_code",
            "malzeme_adi": "material_name", "malzeme_tipi": "material_type",
            "uzmanlik_kategorisi": "specialty_category", "adet": "quantity",
            "birim_fiyat_try": "unit_price_try", "fatura_tutari_try": "billed_amount_try",
            "beklenen_odenebilir_tutar_try": "expected_payable_try",
            "pakete_dahil_mi": "is_bundled", "on_onay_gerekli_mi": "requires_pre_auth",
            "beklenen_red_nedeni": "denial_reason_expected",
            "beklenen_kural_izi": "rule_trace_expected",
            "titubb_kayitli_mi": "titubb_registered",
            "uts_kayitli_mi": "uts_registered",
            "ihale_ekrani_eksik_mi": "procurement_record_incomplete",
            "bagli_islem_odenmez": "procedure_not_reimbursed",
            "yurtdisi_kurum": "foreign_facility",
            "kurum_islem_kisiti_ihlali": "facility_procedure_restriction_violation",
            "tani_medula_paket_ayri_fatura_yok": "diagnosis_bundled_no_separate_bill",
            "ihale_fiyat_referansi_yetersiz": "procurement_price_refs_insufficient",
            "medula_kod_tarihte_tanimsiz": "medula_code_undefined_on_date",
            "barkod_sut_uyumsuz": "barcode_sut_mismatch",
            "tani_paket_malzeme_kapsam": "diagnosis_bundled_material_scope",
            "capraz_brans_fatura_ihlali": "cross_branch_material_unauthorized",
            "ortez_protez_sozlesme_ihlali": "ortez_protez_contract_billing_invalid",
            "bakim_onarim_cap_asimi": "maintenance_cost_exceeds_sut_cap",
            "protez_onarim_belge_eksik": "protez_repair_documentation_incomplete",
            "garanti_bakim_prosedur_eksik": "warranty_maintenance_procedure_incomplete",
            "ortez_protez_bakim_dogrulanmadi": "ortez_protez_maintenance_unverified",
            "ihale_dts_zorunlu_alan_eksik": "ihale_dts_mandatory_fields_incomplete",
            "tedarikci_sozlesme_fiyat_yolu": "supplier_contract_pricing_path",
            "ek3c_yatarak_dis_temin_ihlali": "ek3c_inpatient_external_supply_invalid",
            "ek3c_liste_fiyati_yok": "ek3c_list_price_missing",
            "ek3_kalite_belge_eksik": "ek3_quality_documentation_incomplete",
            "ek3c_miat_erken_yenileme": "ek3c_miat_early_renewal_unauthorized",
            "ek3c_ismarlama_ihlali": "ek3c_custom_order_billing_invalid",
            "ek3c_tibbi_uygunluk_eksik": "ek3c_medical_appropriateness_incomplete",
            "ek3c_basi_giysi_sozlesme": "ek3c_custom_garment_contract_invalid",
            "ek3c_mucbir_sebep_yenileme": "ek3c_force_majeure_renewal_claim",
            "ek3c_ayakta_tedavi_kapsam": "ek3c_outpatient_material_scope",
            "yatarak_kurum_temin_ihlali": "inpatient_material_facility_supply_violation",
            "karsilanmayan_yatarak_hasta": "non_reimbursed_inpatient_patient_charge",
            "laboratuvar_ayri_fatura": "lab_material_separate_billing",
            "cok_bransli_sarf_brans": "shared_consumable_wrong_branch_billing",
            "recete_miktar_asimi": "material_prescription_quantity_exceeded",
            "rapor_recete_gecersiz": "material_report_prescription_invalid",
            "fatura_belge_eksik": "material_invoice_documentation_incomplete",
            "tani_paket_malzeme": "diagnosis_package_material_unbundled",
            "acil_sozlesmesiz_kurum": "emergency_uncontracted_facility_material",
            "listesiz_kesinti_fatura": "unlisted_material_surcharge_billing",
            "cift_tekerlekli_recete": "wheelchair_dual_prescription_invalid",
            "ayakta_sozlesmeli_temin": "outpatient_contract_center_supply_required",
            "cocuk_buyume_miat": "child_growth_miat_renewal_claim",
            "sozlesmeli_temin_kapsam": "facility_contract_material_supply_scope",
            "ismarlama_bilesen_titubb_eksik": "ismarlama_device_component_titubb_incomplete",
            "titubb_uts_barkod_belge_eksik": "titubb_uts_barcode_documentation_missing",
            "specialty_wound_care_excluded": "specialty_wound_care_excluded",
            "skin_substitute_non_burn_use": "skin_substitute_non_burn_use",
            "immunobullous_wound_care_patient_supply": "immunobullous_wound_care_patient_supply",
            "immunobullous_wound_care_non_moh_facility": "immunobullous_wound_care_non_moh_facility",
            "optical_patient_access_deadline_missed": "optical_patient_access_deadline_missed",
            "emergency_poliklinik_glasses_claim": "emergency_poliklinik_glasses_claim",
            "optical_lens_upgrade_difference_claim": "optical_lens_upgrade_difference_claim",
            "optical_telescopic_with_cap_claim": "optical_telescopic_with_cap_claim",
            "contact_lens_with_spectacle_billing": "contact_lens_with_spectacle_billing",
            "tv5680_with_tv1080_tv1090_combo": "tv5680_with_tv1080_tv1090_combo",
            "hearing_in_ear_under_age_limit": "hearing_in_ear_under_age_limit",
            "hearing_ear_mold_with_initial_device": "hearing_ear_mold_with_initial_device",
            "cochlear_implant_under_12_months": "cochlear_implant_under_12_months",
            "speech_processor_under_5_years": "speech_processor_under_5_years",
            "brainstem_implant_under_12_months": "brainstem_implant_under_12_months",
            "incontinence_hydrophilic_catheter_diaper_only": "incontinence_hydrophilic_catheter_diaper_only",
            "tissue_bank_unauthorized_product": "tissue_bank_unauthorized_product",
            "bone_stimulator_combined_use": "bone_stimulator_combined_use",
            "bone_stimulator_hypertrophic_nonunion": "bone_stimulator_hypertrophic_nonunion",
            "bone_stimulator_with_autograft": "bone_stimulator_with_autograft",
            "bone_stimulator_benign_tumor_use": "bone_stimulator_benign_tumor_use",
            "open_physis_primary_fracture_graft": "open_physis_primary_fracture_graft",
            "adult_primary_fracture_bone_stimulator": "adult_primary_fracture_bone_stimulator",
            "hip_arthroplasty_graft_claim": "hip_arthroplasty_graft_claim",
            "graft_allograft_xenograft_combined": "graft_allograft_xenograft_combined",
            "primary_ligament_tendon_injury_graft": "primary_ligament_tendon_injury_graft",
            "glucose_meter_early_renewal": "glucose_meter_early_renewal",
            "wheelchair_stand_device_duplicate_billing": "wheelchair_stand_device_duplicate_billing",
            "stand_up_wheelchair_early_renewal": "stand_up_wheelchair_early_renewal",
            "paraplegia_standing_table_over_age_limit": "paraplegia_standing_table_over_age_limit",
            "paraplegia_wheelchair_separate_billing": "paraplegia_wheelchair_separate_billing",
            "spinal_mobility_device_duplicate_billing": "spinal_mobility_device_duplicate_billing",
            "returned_device_without_kurum_approval": "returned_device_without_kurum_approval",
            "nimv_heated_humidifier_separate_billing": "nimv_heated_humidifier_separate_billing",
            "dental_prosthesis_adhesive_claim": "dental_prosthesis_adhesive_claim",
            "dual_mesh_primary_hernia_repair": "dual_mesh_primary_hernia_repair",
        }),
        "drug_claim_lines.parquet": tables["ilac_fatura_satirlari"].rename(columns={
            "ilac_satiri_id": "drug_claim_line_id", "recete_id": "prescription_id",
            "fatura_id": "claim_id", "hasta_id": "patient_id",
            "basvuru_id": "episode_id", "ilac_fatura_tarihi": "drug_claim_date",
            "ilac_adi": "drug_name", "ilac_kodu": "drug_code",
            "esdeger_grup": "equivalence_group", "adet": "quantity",
            "birim_fiyat_try": "unit_price_try", "fatura_tutari_try": "billed_amount_try",
            "beklenen_odenebilir_tutar_try": "expected_payable_try",
            "beklenen_indirim_kademesi": "discount_tier_expected",
            "beklenen_red_nedeni": "denial_reason_expected",
            "beklenen_kural_izi": "rule_trace_expected",
            "uzmanlik_kurulu_raporu_var": "drug_specialty_board_report_present",
        }),
        "expected_rule_outputs.parquet": tables["beklenen_kural_ciktilari"].rename(columns={
            "beklenen_cikti_id": "expected_output_id", "senaryo_etiketi": "scenario_tag",
            "hasta_id": "patient_id", "fatura_id": "claim_id",
            "satir_id": "line_id", "satir_tipi": "line_type",
            "kural_ailesi": "rule_family", "beklenen_durum": "expected_status",
            "beklenen_odenebilir_tutar_try": "expected_payable_try",
            "beklenen_tasarruf_try": "expected_savings_try",
            "beklenen_red_nedeni": "expected_denial_reason",
            "beklenen_kural_izi": "expected_rule_trace",
            "test_notu": "assertion_notes",
        }),
    }


def _write_claim_exports(tables: dict[str, pd.DataFrame], output_dir: Path) -> None:
    claims_dir = output_dir / "claims"
    claims_dir.mkdir(parents=True, exist_ok=True)
    for name, df in _english_claim_exports(tables).items():
        _normalize_for_parquet(df).to_parquet(claims_dir / name, index=False)
