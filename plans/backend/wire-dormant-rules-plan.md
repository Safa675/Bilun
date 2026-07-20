# Plan: Wire Dormant Rules — Code-Gap Phase

**Tarih:** 2026-07-15
**Kapsam:** `src/bilun/domain/` — dormant rule activation via context-builder fixes
**Yöntem:** Derin kod tabanı analizi + doğrulanmış file:line bulguları

---

## Goal

~1,360 of ~1,943 encoded rules are dormant. Bu planın odak noktası: **~150-200 kuralı aktive etmek** yalnızca kod değişikliği ile — şema genişletmesi gerektirmeyen, mevcut data model field'larını surface eden düzeltmeler.

## Teşhis — kanıtlanmış bulgular

Dormancy'nin 4 kök nedeni var. Bu plan sadece **kod-gab (code-gap)** kategorisini hedefler:

| Kök neden | Payı | Bu plan kapsamında mı? |
|---|---:|---|
| Şema gabı (field hiç yok: bmi, ecog_score, pdl1, vb.) | ~35-40% | ❌ Hayır — product kararı gerekir |
| **Kod gabı (field var, builder surface etmiyor)** | **~25-30%** | **✅ Evet — bu plan** |
| EMR geçmiş/timeline gabı (cross-claim history) | ~20-25% | ❌ Hayır — ingestion değişikliği gerekir |
| Saf sentetik veri gabı (sag_sol gibi) | ~10-15% | ✅ Kısmen — sag_sol zaten düzeltildi (#9) |

### Doğrulanmış kod-gab listesi (agent ile teyit edildi)

| # | Bulgü | Mevcut durum | Kuralları aktive eder | Çaba |
|---|---|---|---:|---|
| 1 | `health_report_present` alias tutarsızlığı | gap_closing `health_report_present` kullanıyor, treatment_pricing `health_board_report_present` — 4 kural honest-skip | 4 | S |
| 2 | `patient_age` türetme dead code | `birth_year` var ama `patient_status.py:83-85` dead assignment (`age = None`) | 4 (dental + treatment) | S |
| 3 | `facility_type` dental'de yok | treatment_pricing'de var (biz ekledik #22), dental_2_4_1'de yok | 7 (dental) | S |
| 4 | copay_general 25/30 kural resolver'sız | 5 service_type'ın resolver'ı yok (copay_exemption=20, muayene=1, surcharge=1, refund=1, box_count=1) | 25 | M |
| 5 | drug_combination context builder yok | 52 key `_BLOCKED_KEYS`'te; 9 key wireable; context builder hiç yok | ~6 (wireable) | M |
| 6 | `indication_not_in` alias blocked | `diagnosis_any` wireable ama `indication_not_in` blocked — naming alias gap | 3 | S |
| 7 | `loading_dose_incomplete` blocked | `is_loading_phase` DrugClaimLine'da var, drug_indication kullanıyor, drug_combination kullanmıyor | 1 | S |
| 8 | `procedure_specialty_code` gap_closing'de yok | Field var (models.py:82), treatment_pricing surface ediyor, gap_closing surface etmiyor | 0 (bugün hiç kural referencing yok — future-proofing) | S |

**Toplam potansiyel:** ~50 kural + 25 copay_general = **~75 kural aktive edilebilir**

---

## Phase 1 — Alias ve naming düzeltmeleri (en kolay, en yüksek etki)

**Hedef:** 4+4+7 = 15 kuralı naming/alias düzeltmeleriyle aktive et.

### Subtasks
- [ ] **1.1 `health_report_present` alias:** treatment_pricing.py:646 `health_board_report_present` yanına `health_report_present` alias ekle (aynı değer). gap_closing zaten `health_report_present` kullanıyor. 4 kural aktive olur.
- [ ] **1.2 `patient_age` türetme:** `patient_status.py:83-85`'teki dead assignment'ı düzelt: `age = date.today().year - profile.birth_year if profile.birth_year else None`. Dental (3 kural) + treatment_pricing (1 kural) = 4 kural aktive olur.
- [ ] **1.3 `facility_type` dental:** `dental_2_4_1.py`'nin context builder'ına `facility_type` derivation ekle (treatment_pricing.py:422-438 ve gap_closing.py:437-449'daki aynı mantığı kopyala). 7 dental kural aktive olur.
- [ ] **Test:** Her phase için, yeni aktive olan kuralların fixture'larla test edildiğini doğrula.

---

## Phase 2 — drug_combination context builder (orta çaba)

**Hedef:** drug_combination için bir context builder oluştur ve wireable key'leri surface et.

### Subtasks
- [ ] **2.1 Context builder oluştur:** `_build_drug_combination_context(ctx)` fonksiyonu yaz. Şunları surface et:
  - `procedure_code_any` (ProcedureClaimLine'dan — şu an _BLOCKED_KEYS'te)
  - `facility_tier` / `facility_tier_in` (ClaimHeader'dan — şu an _BLOCKED_KEYS'te)
  - `loading_dose_incomplete` (DrugClaimLine.is_loading_phase'den)
  - `indication_not_in` (diagnosis_any'nin negated alias'ı)
- [ ] **2.2 `_BLOCKED_KEYS`'ten çıkar:** 2.1'de surface edilen key'leri `_BLOCKED_KEYS`'ten `_WIREABLE_KEYS`'e taşı.
- [ ] **2.3 `indication_not_in` predicate:** `_condition_matches`'a negated diagnosis logic ekle (diagnosis_any'nin tersi).
- [ ] **Test:** drug_combination test'lerinde yeni wireable key'lerin çalıştığını doğrula.

---

## Phase 3 — copay_general resolver'ları (en büyük tek blok, 25 kural)

**Hedef:** copay_general_1_8.json'daki 25 dormant kural için resolver ekle.

### Subtasks
- [ ] **3.1 `copay_exemption` service_type (20 kural):** Bu kurallar §1.8.2/EK-4D muafiyet mantığı içeriyor. Şu an `copay_exemption_context.py` ayrı bir modül — bu kuralları ya copay_general'a taşı ya da copay_exemption modülüne resolver ekle. Hangi yaklaşımın doğru olduğuna karar ver.
- [ ] **3.2 `copay_muayene` service_type (1 kural):** Muayene katılım payı oranı resolver'ı.
- [ ] **3.3 `copay_surcharge` service_type (1 kural):** Fark ücreti resolver'ı.
- [ ] **3.4 `copay_refund` service_type (1 kural):** İade resolver'ı.
- [ ] **3.5 `drug_injectable_box_count` service_type (1 kural):** Enjektör kutu sayısı resolver'ı.
- [ ] **3.6 Stale docstring güncelle:** copay_general.py:30-33 "unblocks the 13 dormant rules" comment'ini gerçek sayıyla güncelle.
- [ ] **Test:** Her yeni resolver için fixture test.

### Out of Scope
- copay_exemption kurallarının tamamı EK-4D ilaç muafiyet listesi gerektirir — bu bir şema/veri kararı olabilir. 3.1'de karar verilecek.

---

## Phase 4 — gap_closing specialty + kalan küçük düzeltmeler

**Hedef:** Future-proofing + kalan küçük code-gap'ler.

### Subtasks
- [ ] **4.1 `procedure_specialty_code` gap_closing:** `_build_gap_closing_context`'e specialty surface ekle (treatment_pricing.py:459-468 pattern). Bugün hiç kural referencing yapmıyor ama gelecekte eklenebilir.
- [ ] **4.2 `_condition_matches` negated-set predicate genişletme:** `*_not_any` pattern gap_closing + treatment_pricing'de zaten çalışıyor (fix #4 sonrası), ama drug_combination'da da çalıştığını doğrula.
- [ ] **4.3 Stale docstring'ler:** dental_2_4_1.py:13-14, treatment_pricing.py:25-37 — "not on claim model" yazan yerleri, eğer artık surface ediliyorsa güncelle.

---

## Verification (her phase sonunda)

- `python -m pytest tests/unit/domain/prose_rules/ -q` — tüm testler yeşil
- Manuel: bir claim'de yeni aktive olan kuralların gerçekten fire ettiğini doğrula
- Dormancy count: her phase sonunda kaç kuralın aktive olduğunu say (instrumented run)

## Execution order

**Phase 1** (alias/naming — 15 kural, S effort) → **Phase 2** (drug_combination builder — ~6 kural, M) → **Phase 3** (copay_general — 25 kural, M) → **Phase 4** (future-proofing — 0 bugün, S).

Her phase ayrı commit. Phase 1 en yüksek etki/çaba oranı.

---

## Out of Scope (şema/veri kararı gerektiren)

Bu kurallar field'ın data model'de hiç OLMAMASINDAN dolayı dormant — kod değişikliği tek başına çözemez:

- `bmi`, `ecog_score`, `pdl1_expression`, `child_pugh`, `nyha_class` (~25 kural) — klinik gözlem field'ları
- `report_tier`, `board_from`, `board_includes` (~3 kural) — kurul kompozisyonu
- `enabiz_278_submitted`, `provision_type` (~2 kural) — operasyonel metadata
- IVF cycle metadata (~8 kural) — özel alan
- `stem_cell_type`, `overseas_treatment_days`, `hours_since_onset` (~3 kural) — spesifik klinik veri
- Sequential drug history (~20 kural) — cross-claim timeline ingestion

Bunlar için ayrı bir "schema expansion" planı gerekir (data model tasarımı + EMR ingestion contract).
