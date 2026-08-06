# TIER-1 Stale Refs — Phase 2 Karar Belgesi (onay bekliyor)

**Tarih:** 2026-08-06
**Kaynak:** `reports/agent/reimbursement/tier1-triage-2026-08-06.md` (otomatik öneri) + 3 paralel hukuki analiz (rule JSON × `text_tr`/`in_force_text` karşılaştırması, kaynak DOCX doğrulamalı)
**Plan:** `plans/update/2026-08-06-stale-clause-triage-plan.md` — Phase 2

## Özet

| | Otomatik öneri | İnsan analizi sonucu |
|---|---|---|
| A (23) | mülga içeriğe bağımlı | **2 RE-ENCODE**, 21 KEEP'e düştü |
| REVIEW (10) | kısmi overlap | **5 RE-ENCODE, 5 KEEP** |
| **Toplam 33** | | **12 RE-ENCODE, 21 KEEP, 0 DELETE** |

**Ana bulgu:** A-sınıfı önerilerin çoğu false-positive — mülga içerik ya başka clause'a taşınmış (lipozomal doksorubisin → C005681, denosumab → C006034, triple-terapi → 4.2.24.B.(12), darbepoetin → C004125/C004127) ya kural zaten güncel metni encode ediyor (dabigatran 12-ay, obinutuzumab) ya da overlap tesadüfi (4.2.14.C.(2) ilaç listesi kuralları). K1 kararı (son karar insan) işe yaradı: golden case `4.2.33.general_switch_to_bevacizumab` otomatikte A idi, analizde KEEP — mülga "yükleme dozu yapılarak" ters yöndeki switch'e ait, kuralın enforce ettiği yön hâlâ yürürlükte.

**Hiçbir kural tamamen ölü hukuka dayanmıyor (0 DELETE)** — 12 kuralın alanları güncel metne uyarlanmalı.

---

## RE-ENCODE listesi (12) — Phase 3 PR kapsamı

| # | rule_id | Değişiklik | Güven |
|---|---|---|---|
| 1 | `4.2.13.hcv_acute_interferon_report` | `drug_names`'ten çıplak "interferon" düşer (akut HCV artık sadece pegile interferon alfa monoterapisi); `message_tr` güncellenir | yüksek |
| 2 | `4.2.13.hdv_interferon_board` | `drug_names`'ten çıplak "interferon" düşer (HDV+ CHB sadece pegile interferonlar); `message_tr` güncellenir | yüksek |
| 3 | `4.2.14.C.tier_c_b.C005021.nilotinib` | `message_tr`'den "yalnızca" düşer (nilotinib artık dasatinib-direnç şartı olmadan, imatinib-direnç/intolerans ile); opsiyonel: `requires_prior_therapy.outcome` → resistant_or_intolerant, report_specialties'e hematoloji | yüksek |
| 4 | `4.2.14.C.tier_c_b.C005024.dasatinib` | `gate_b_sources`'ten C005025 düşer (dasatinib'le tek bağı mülga "dasatinibe dirençli" ibaresiydi); C005024 kalır | orta |
| 5 | `4.2.24.B.resp.laba_lama_iks_mono_and_triple_maintenance` | `action.enforcement` + `message_tr`'nin triple-terapi yarısı silinir (mülga; yerine 4.2.24.B.(12) geldi, kardeş kural `copd_triple_combo_maintenance` zaten encode ediyor); mono kısmı kalır | yüksek |
| 6 | `4.2.65.derm.diabetic_foot_osteomyelitis_softtissue_report_mandatory` | `report_specialties` boşaltılır (branş atıfları mülga, yerine yenisi gelmedi); `action.enforcement` + `message_tr`'den "…uzman hekimi tarafından" ibareleri düşer; rapor-belirtme yükümlülüğü kalır | yüksek |
| 7 | `4.2.9.mds_esa_hematology_report` | `gate_b_sources`'e C004125 (4.2.9.A.(1)) + C004127 (4.2.9.A.(3)) eklenir (darbepoetin-MDS'nin güncel dayanağı); opsiyonel: boş marker kabuğu C004136 düşer | orta |
| 8 | `4.2.1.leflunomid_ra_psa_report` | `message_tr` mülga "sulfasalazin/metotreksat yetersizlik" şartından arındırılır; specialty listelerinden "klinik immunoloji" düşer; `report_duration_months: 12` eklenir | yüksek |
| 9 | `4.2.14.C.(1).sonidegib_bcc_board` | `gate_b_sources` C005235 (topikal beksaroten clause'u — yanlış atıf) → C005245-C005248 (cc) maddesi); opsiyonel: başlangıç kurulu için dermatoloji/radyasyon onkolojisi/cerrahi eklenir | orta |
| 10 | `4.2.14.C.(1).vismodegib_bcc_board` | Aynı: `gate_b_sources` → C005245-C005248 | orta |
| 11 | `4.2.14.C.deontic.C005234` | `report_specialties` → ["dermatoloji"] (tıbbi onkoloji/hematoloji hiçbir metne uymuyor); `gate_b_sources`'e C005235 eklenir (güncel rapor hükmü: 3 dermatoloji); `message_tr`'deki dangling Mülga marker'ı silinir | orta |
| 12 | `4.2.24.laba_lama_ics_triple_prior` | `gate_b_sources` 4.2.24.B.(4) → 4.2.24.B.(12) (C006180 — aynı RG ile yeniden ihdas edildi); mesajdaki §4.2.24.B-4 → §4.2.24.B-12; opsiyonel: `report_duration_months: 3` alanı gözden geçirilir (önceki-tedavi süresi ile rapor süresini karıştırıyor) | yüksek |

## KEEP listesi (21) — işlem yok

`4.2.33.general_switch_to_bevacizumab`, `4.2.1.anti_tnf_ra_das28_initiation`, `4.2.13.hbv_antiviral_report_renewal_initiation_f7`, `4.2.13.hbv_antiviral_report_renewal_initiation_f8`, `4.2.13.hbv_tenofovir_board`, `4.2.13.hepatitis_prior_therapy_documentation`, `4.2.14.C.(2).anagrelide_board`, `4.2.14.C.(2).bortezomib_heme_onc_board`, `4.2.14.C.(2).fludarabine_cladribine_board`, `4.2.14.C.(2).idarubicin_board`, `4.2.14.C.(2).pentostatin_board`, `4.2.14.C.(2).talidomid_heme_onc_board`, `4.2.14.C.(2).tretinoin_heme_onc_board`, `4.2.15.dabigatran_cardiology_board`, `4.2.17.A.osteoporosis_2yr_report_combo_one_paid`, `4.2.2.antipsychotics_psychiatry_report`, `4.2.1.anti_tnf_prescriber_board`, `4.2.1.tocilizumab_jia_c5_prior_therapy_failure`, `4.2.14.C.alemtuzumab_cll_heme`, `4.2.14.C.deontic.C005555`, `4.2.15.D_1.three_physician_1yr_report`

## Analiz sırasında bulunan ek notlar (bu triage'ın kapsamı dışı)

1. **`4.2.14.C.alemtuzumab_cll_heme`** — alemtuzumab fıkra (2) listesinde hiçbir versiyonda yok; corpus'ta sadece 4.2.34 (MS) altında geçiyor. Amendment-ile-ilgisiz, önceden var olan drug→clause boşluğu. Ayrı inceleme adayı.
2. **`4.2.15.dabigatran_cardiology_board`** — güncel hukuk nöroloji'yi de anchor uzman ve reçeteci olarak kabul ediyor; kuralın `prescriber_specialties` darlığı mülga-öncesi kalıntı (repeal ile bağlantısız, opsiyonel genişletme).
3. **`4.2.14.C.deontic.C005555`** — `report_specialties`'te "tıbbi onkoloji" var ama clause sadece hematoloji diyor (section-wide konvansiyon; kozmetik).

## Onay

- [ ] Safa: 12 RE-ENCODE onaylandı → Phase 3 PR'ları başlar
- [ ] Değişiklik istenen satırlar: ______
