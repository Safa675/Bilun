"""Material and specialty prose flag columns and coverage helpers."""

from __future__ import annotations

from typing import Any

MATERIAL_PROSE_FLAG_COLUMNS: tuple[str, ...] = (
    "titubb_kayitli_mi",
    "uts_kayitli_mi",
    "ihale_ekrani_eksik_mi",
    "bagli_islem_odenmez",
    "yurtdisi_kurum",
    "kurum_islem_kisiti_ihlali",
    "tani_medula_paket_ayri_fatura_yok",
    "ihale_fiyat_referansi_yetersiz",
    "medula_kod_tarihte_tanimsiz",
    "barkod_sut_uyumsuz",
    "tani_paket_malzeme_kapsam",
    "capraz_brans_fatura_ihlali",
    "ortez_protez_sozlesme_ihlali",
    "bakim_onarim_cap_asimi",
    "protez_onarim_belge_eksik",
    "garanti_bakim_prosedur_eksik",
    "ortez_protez_bakim_dogrulanmadi",
    "ihale_dts_zorunlu_alan_eksik",
    "tedarikci_sozlesme_fiyat_yolu",
    "ek3c_yatarak_dis_temin_ihlali",
    "ek3c_liste_fiyati_yok",
    "ek3_kalite_belge_eksik",
    "ek3c_miat_erken_yenileme",
    "ek3c_ismarlama_ihlali",
    "ek3c_tibbi_uygunluk_eksik",
    "ek3c_basi_giysi_sozlesme",
    "ek3c_mucbir_sebep_yenileme",
    "ek3c_ayakta_tedavi_kapsam",
    "yatarak_kurum_temin_ihlali",
    "karsilanmayan_yatarak_hasta",
    "laboratuvar_ayri_fatura",
    "cok_bransli_sarf_brans",
    "recete_miktar_asimi",
    "rapor_recete_gecersiz",
    "fatura_belge_eksik",
    "tani_paket_malzeme",
    "acil_sozlesmesiz_kurum",
    "listesiz_kesinti_fatura",
    "cift_tekerlekli_recete",
    "ayakta_sozlesmeli_temin",
    "cocuk_buyume_miat",
    "sozlesmeli_temin_kapsam",
    "ismarlama_bilesen_titubb_eksik",
    "titubb_uts_barkod_belge_eksik",
)

# L4.4 §3.3 specialty annex prose — keep in sync with specialty_materials.SPECIALTY_CLAIM_FLAGS
SPECIALTY_PROSE_FLAG_COLUMNS: tuple[str, ...] = (
    "specialty_wound_care_excluded",
    "skin_substitute_non_burn_use",
    "immunobullous_wound_care_patient_supply",
    "immunobullous_wound_care_non_moh_facility",
    "optical_patient_access_deadline_missed",
    "emergency_poliklinik_glasses_claim",
    "optical_lens_upgrade_difference_claim",
    "optical_telescopic_with_cap_claim",
    "contact_lens_with_spectacle_billing",
    "tv5680_with_tv1080_tv1090_combo",
    "hearing_in_ear_under_age_limit",
    "hearing_ear_mold_with_initial_device",
    "cochlear_implant_under_12_months",
    "speech_processor_under_5_years",
    "brainstem_implant_under_12_months",
    "incontinence_hydrophilic_catheter_diaper_only",
    "tissue_bank_unauthorized_product",
    "bone_stimulator_combined_use",
    "bone_stimulator_hypertrophic_nonunion",
    "bone_stimulator_with_autograft",
    "bone_stimulator_benign_tumor_use",
    "open_physis_primary_fracture_graft",
    "adult_primary_fracture_bone_stimulator",
    "hip_arthroplasty_graft_claim",
    "graft_allograft_xenograft_combined",
    "primary_ligament_tendon_injury_graft",
    "glucose_meter_early_renewal",
    "wheelchair_stand_device_duplicate_billing",
    "stand_up_wheelchair_early_renewal",
    "paraplegia_standing_table_over_age_limit",
    "paraplegia_wheelchair_separate_billing",
    "spinal_mobility_device_duplicate_billing",
    "returned_device_without_kurum_approval",
    "nimv_heated_humidifier_separate_billing",
    "dental_prosthesis_adhesive_claim",
    "dual_mesh_primary_hernia_repair",
)


def _default_prose_material_flags() -> dict[str, bool]:
    return {
        "titubb_kayitli_mi": True,
        "uts_kayitli_mi": True,
        "ihale_ekrani_eksik_mi": False,
        "bagli_islem_odenmez": False,
        "yurtdisi_kurum": False,
        "kurum_islem_kisiti_ihlali": False,
        "tani_medula_paket_ayri_fatura_yok": False,
        "ihale_fiyat_referansi_yetersiz": False,
        "medula_kod_tarihte_tanimsiz": False,
        "barkod_sut_uyumsuz": False,
        "tani_paket_malzeme_kapsam": False,
        "capraz_brans_fatura_ihlali": False,
        "ortez_protez_sozlesme_ihlali": False,
        "bakim_onarim_cap_asimi": False,
        "protez_onarim_belge_eksik": False,
        "garanti_bakim_prosedur_eksik": False,
        "ortez_protez_bakim_dogrulanmadi": False,
        "ihale_dts_zorunlu_alan_eksik": False,
        "tedarikci_sozlesme_fiyat_yolu": False,
        "ek3c_yatarak_dis_temin_ihlali": False,
        "ek3c_liste_fiyati_yok": False,
        "ek3_kalite_belge_eksik": False,
        "ek3c_miat_erken_yenileme": False,
        "ek3c_ismarlama_ihlali": False,
        "ek3c_tibbi_uygunluk_eksik": False,
        "ek3c_basi_giysi_sozlesme": False,
        "ek3c_mucbir_sebep_yenileme": False,
        "ek3c_ayakta_tedavi_kapsam": False,
        "yatarak_kurum_temin_ihlali": False,
        "karsilanmayan_yatarak_hasta": False,
        "laboratuvar_ayri_fatura": False,
        "cok_bransli_sarf_brans": False,
        "recete_miktar_asimi": False,
        "rapor_recete_gecersiz": False,
        "fatura_belge_eksik": False,
        "tani_paket_malzeme": False,
        "acil_sozlesmesiz_kurum": False,
        "listesiz_kesinti_fatura": False,
        "cift_tekerlekli_recete": False,
        "ayakta_sozlesmeli_temin": False,
        "cocuk_buyume_miat": False,
        "sozlesmeli_temin_kapsam": False,
        "ismarlama_bilesen_titubb_eksik": False,
        "titubb_uts_barkod_belge_eksik": False,
    }


def _default_specialty_prose_flags() -> dict[str, bool]:
    return {flag: False for flag in SPECIALTY_PROSE_FLAG_COLUMNS}


def _sample_prose_material_flags(*, bundled: bool) -> dict[str, bool]:
    """Default flags only — coverage is applied deterministically after generation."""
    return {**_default_prose_material_flags(), **_default_specialty_prose_flags()}


def _ensure_specialty_flag_coverage(
    materials: list[dict[str, Any]],
    claims: list[dict[str, Any]] | None = None,
) -> None:
    """Guarantee at least one demo row per L4.4 specialty prose claim flag.

    Context-aware: duplicate-billing flags (wheelchair_stand_device_duplicate_billing,
    spinal_mobility_device_duplicate_billing, nimv_heated_humidifier_separate_billing)
    assert a SECOND device was co-billed. They must only be set on materials whose
    claim also carries the referenced co-material — otherwise the §3.3 engine fires a
    "tekerlekli sandalye ile birlikte..." violation on a lone shoulder implant, a false
    positive. When no claim has the co-material, coverage for that flag is skipped
    (honest "no demo row" beats a fabricated one).
    """
    if not materials:
        return

    candidates = [row for row in materials if not row.get("pakete_dahil_mi")] or materials

    # Duplicate-billing flags → required co-material keyword in a sibling line's name.
    duplicate_cos = {
        "wheelchair_stand_device_duplicate_billing": "tekerlekli",
        "spinal_mobility_device_duplicate_billing": "spinal",
        "nimv_heated_humidifier_separate_billing": "nimv",
    }

    def _claim_has_cosiblings(material_row: dict[str, Any], keyword: str) -> bool:
        """True if another material on the same claim has `keyword` in its name."""
        cid = material_row.get("fatura_id")
        return any(
            other.get("fatura_id") == cid
            and other is not material_row
            and keyword in str(other.get("malzeme_adi", "")).lower()
            for other in materials
        )

    for idx, col in enumerate(SPECIALTY_PROSE_FLAG_COLUMNS):
        if any(row.get(col) for row in materials):
            continue
        # Duplicate-billing flags: only assign to a material whose claim has the
        # co-material. If none qualifies, skip coverage for this flag.
        cos_keyword = duplicate_cos.get(col)
        if cos_keyword:
            eligible = [r for r in candidates if _claim_has_cosiblings(r, cos_keyword)]
            if not eligible:
                continue  # no co-material anywhere → skip rather than fabricate
            row = eligible[idx % len(eligible)]
        else:
            row = candidates[idx % len(candidates)]
        row[col] = True
        if float(row.get("fatura_tutari_try") or 0) <= 0:
            row["fatura_tutari_try"] = 100.0
            row["birim_fiyat_try"] = 100.0


def _reconcile_claim_header_totals(
    claims: list[dict[str, Any]],
    procedure_rows: list[dict[str, Any]],
    materials: list[dict[str, Any]],
    drug_rows: list[dict[str, Any]],
    expected: list[dict[str, Any]] | None = None,
) -> None:
    """Recompute claim header billed/payable totals from line sums (post L4.4 inject)."""
    billed_by_claim: dict[str, float] = defaultdict(float)
    payable_by_claim: dict[str, float] = defaultdict(float)

    for rows in (procedure_rows, materials, drug_rows):
        for row in rows:
            claim_id = str(row.get("fatura_id", ""))
            if not claim_id:
                continue
            billed_by_claim[claim_id] += float(row.get("fatura_tutari_try") or 0)
            payable_by_claim[claim_id] += float(row.get("beklenen_odenebilir_tutar_try") or 0)

    claim_level_expected = {
        str(row.get("fatura_id", "")): row
        for row in (expected or [])
        if str(row.get("satir_tipi", "")) == "fatura" and not str(row.get("satir_id", ""))
    }

    for claim in claims:
        claim_id = str(claim.get("fatura_id", ""))
        billed = billed_by_claim.get(claim_id, 0.0)
        payable = payable_by_claim.get(claim_id, 0.0)
        claim["beklenen_toplam_fatura_tutari_try"] = _money(billed)
        claim["beklenen_toplam_odenebilir_tutar_try"] = _money(payable)

        expected_row = claim_level_expected.get(claim_id)
        if expected_row is not None:
            expected_row["beklenen_odenebilir_tutar_try"] = _money(payable)
            expected_row["beklenen_tasarruf_try"] = _money(billed - payable)
            expected_row["beklenen_durum"] = (
                "kismi_red" if payable < billed else "odenebilir"
            )


def _inject_specialty_keyword_demo_rows(
    materials: list[dict[str, Any]],
    claims: list[dict[str, Any]],
) -> None:
    """Append billed lines that trigger keyword-only §3.3 rules (no claim flags)."""
    if not claims:
        return

    claim = claims[0]
    claim_id = str(claim.get("fatura_id", ""))
    patient_id = str(claim.get("hasta_id", ""))
    service_date = claim.get("fatura_baslangic_tarihi") or claim.get("fatura_tarihi") or "2024-06-01"

    keyword_demos = (
        ("DEMO-L44-W1", "Transparan film yara örtüsü", 85.0),
        ("DEMO-L44-W2", "Hidrojel yara nemlendirici", 120.0),
        ("DEMO-L44-CL1", "Kontakt lens solüsyonu", 35.0),
        ("DEMO-L44-SS1", "Deri taklidi yedek", 250.0),
    )

    for idx, (code, name, price) in enumerate(keyword_demos):
        line_id = f"MLZ-{claim_id}-L44-{idx + 1:02d}"
        materials.append(
            {
                "malzeme_satiri_id": line_id,
                "fatura_id": claim_id,
                "islem_satiri_id": f"ISL-{claim_id}-001",
                "hasta_id": patient_id,
                "malzeme_tarihi": service_date,
                "malzeme_kodu": code,
                "malzeme_adi": name,
                "malzeme_tipi": "uzmanlik",
                "uzmanlik_kategorisi": "wound",
                "adet": 1,
                "birim_fiyat_try": price,
                "fatura_tutari_try": price,
                "beklenen_odenebilir_tutar_try": price,
                "pakete_dahil_mi": False,
                "on_onay_gerekli_mi": False,
                "beklenen_red_nedeni": "",
                "beklenen_kural_izi": f"L4.4:{code}",
                **_default_prose_material_flags(),
                **_default_specialty_prose_flags(),
            }
        )


def _ensure_prose_flag_coverage(
    materials: list[dict[str, Any]],
    inpatient_claim_ids: frozenset[str] | None = None,
) -> None:
    """Guarantee at least one demo row per prose flag without touching RNG.

    Context-aware: inpatient-scoped flags (non_reimbursed_inpatient_patient_charge,
    inpatient_material_facility_supply_violation, ek3c_inpatient_external_supply_invalid)
    are only set on materials belonging to a yatarak (inpatient) claim, never on an
    outpatient — otherwise the §3.1 engine emits a "yatarak malzeme" violation on a
    poliklinik claim, a false positive an auditor can falsify. Duplicate-billing flags
    require the referenced co-material on the same claim.
    """
    if not materials:
        return

    candidates = [
        row for row in materials if not row.get("pakete_dahil_mi")
    ] or materials
    inpatient_ids = inpatient_claim_ids or frozenset()
    inpatient_candidates = [
        row for row in candidates if row.get("fatura_id") in inpatient_ids
    ] or candidates

    # Flags whose rule text asserts an inpatient (yatarak) context. These use
    # the GENERATOR's Turkish column names (the exported English names differ).
    inpatient_scoped = frozenset(
        {
            "karsilanmayan_yatarak_hasta",          # -> non_reimbursed_inpatient_patient_charge
            "yatarak_kurum_temin_ihlali",           # -> inpatient_material_facility_supply_violation
            "ek3c_yatarak_dis_temin_ihlali",        # -> ek3c_inpatient_external_supply_invalid
        }
    )

    for idx, col in enumerate(MATERIAL_PROSE_FLAG_COLUMNS[2:]):
        if any(row.get(col) for row in materials):
            continue
        pool = inpatient_candidates if col in inpatient_scoped else candidates
        pool[idx % len(pool)][col] = True

    if not any(row.get("titubb_kayitli_mi") is False for row in materials):
        candidates[0]["titubb_kayitli_mi"] = False
    if not any(row.get("uts_kayitli_mi") is False for row in materials):
        candidates[min(1, len(candidates) - 1)]["uts_kayitli_mi"] = False

