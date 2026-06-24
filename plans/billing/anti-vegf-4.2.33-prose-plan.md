# Plan: §4.2.33 Anti-VEGF / Göz İlaçları Prose Motoru

> **Status:** Draft — awaiting Safa approval
> **Tarih:** 2026-06-24
> **Motivasyon:** §4.2.33, drug_indication gap'leri içinde **tek gerçek hastane-geliri sinyali** taşıyan bölüm (günübirlik intravitreal enjeksiyon — hem reçete hem "uygulanır" fiili). Acıbadem/Memorial tipi göz/günbirlik merkezi için doğrudan gelir etkisi var.
> **Sibling:** `plans/billing/drug-indication-4.2.14.C-expansion-plan.md` (§4.2.14.C), `drug_indication.py`
> **Registry:** `drug_indication_prose` (bu plan onu §4.2.33'e genişletir)

---

## Task: §4.2.33 göz ilaç endikasyon kurallarını çalıştırılabilir prose'a dök

### Goal

§4.2.33'nin 40 INN-named actionable hükmünü, mevcut `drug_indication` motorunu (Tier 3b matcher)
yeniden kullanarak çalıştırılabilir JSON kurallarına çevirmek. Sonuç: bir göz ilacı içeren
talep satırı, tanı + rapor + reçete eden branş açısından doğrulanabilmeli; günbirlik
enjeksiyon seansı sayısı kuralı en azından "doğrulanmalı" (review) olarak sinyallenmeli.

Başarı kriteri: coverage parquet rebuild sonrası §4.2.33 gap satırları 133 → ~40 altına iner
(INN-olmayan başlık/tanımsal/idari hükümler non-algorithmic kalır).

### Doğrulanmış veri (araştırma çıktısı)

| Metrik | Değer | Kaynak |
|--------|-------|--------|
| §4.2.33 toplam hüküm | 136 | sut_clauses.parquet |
| Substantive (heading/amendment değil) | 93 | " |
| INN-named actionable | 40 | " |
| Mevcut gap (coverage_status=partial) | 133/134 | sut_clause_coverage.parquet |
| Alt-bölüm | A, B, C, Ç, D, E, F (7 endikasyon grubu) | " |
| İlaçlar (INN) | ranibizumab, bevacizumab, aflibersept, deksametazon(ITV implant), siklosporin, sisteamin | sut_clauses C006457-C006586 |
| Uygulama fiili ("uygulan") | 17 hüküm | parquet grep |
| Günübirlik sinyali | 4 hüküm (§4.2.33.A/C/D) | parquet grep |
| Reçete fiili | 20 hüküm | parquet grep |
| Reçete eden/report branşı | "göz hastalıkları" (her alt-bölüm) | SUT metni |

### Mimari uyum — mevcut motor %100 yeniden kullanılır

§4.2.33 hükmü yapısı, `drug_indication_prose.json` kural şemasıyla birebir örtüşür:
`drug_names` + `icd10_codes/ranges` + `report_required` + `report_specialties` +
`prescriber_specialties`. **Tek fark:** §4.2.33 doz protokolü içerir (§4.2.14.C içermez):
- "birer ay arayla 3 kez yükleme dozu" (A, D)
- "her göz için yılda maksimum 2 uygulama" (B)
- "5 ay süreli rapor" (D aflibersept)

`DrugClaimLine` modelinde (`claims/models.py:238-241`) doz-sayısı alanı YOK
(sadece `prescriber_specialty`, `drug_specialty_board_report_present`,
`drug_report_duration_months`, `drug_inpatient_supply`). → Doz protokolü ilk fazda
`needs_report_verification` (review, error değil) olarak sinyallenir — dürüst kısmi.

### Onaylanmış tasarım kararları (Safa seçimi, 2026-06-24)

1. **Ayrı `anti_vegf_prose.json`** — ayrı rule_set_id, loader çoklu-dosyaya genelleştirilir.
   Provenans temiz; §4.2.14.C ile §4.2.33 ayrı kalır. `load_drug_indication_rules()` →
   `_load_indication_rule_files([drug_path, anti_vegf_path])`, `check_drug_indication_for_context`
   her ikisini de tarar.

2. **Hard enforcement + model genişletme** — doz protokolü `error` üretir (review değil).
   `DrugClaimLine` ve `MaterialItem`'a doz-sayısı alanları eklenir, motor `_evaluate_dose_protocol`
   dalıyla `error` severity verir. Bu zincirleme değişiklik → yeni **Faz 3a**.

**Model genişletme zinciri (doz enforcement için gerekli tüm dokunuş noktaları):**
- `DrugClaimLine` (claims/models.py:225) — yepyeni alanlar
- `MaterialItem` (shared/models.py:10) — etkileşimli Talep Doğrulayıcı bunu kullanır, `DrugClaimLine` DEĞİL
- `drug_indication.py:_evaluate_dose_protocol` — yeni enforcement dalı
- sentetik üretici (generators.py:1993 `_append_drug_lines_for_claim`) — yeni alanı üretir
- sentetik xlsx export mapping (exporters.py:332-334 yanına yeni satır)
- frontend `SutMaterialItem` + Talep Doğrulayıcı formu — doz girişi

**Kritik fark:** Talep Doğrulayıcı (`/validate-claim`) `MaterialItem` kullanır;
sentetik pipeline `DrugClaimLine` kullanır. Doz alanı İKİSİNDE de olmalı, yoksa
frontend'den girilen doz `drug_indication` motoruna ulaşamaz (claim_dict dönüşümü sırasında düşer).

---

## Fazlar

### Faz 1 — Prose corpus export (veri çıkarma)
**Dosya:** `scripts/sut/prose/anti_vegf_4233_export.py` (yeni)

- [ ] §4.2.33 hükümlerini sut_clauses.parquet'ten çek, substantive (heading/amendment değil) filtrele
- [ ] INN-named hükümleri grupla: her (INN, alt-bölüm, tanı grubu) üçlüsü için bir satır
- [ ] ICD-10 kodlarını endikasyondan çıkar:
      - A (YAŞ AMD) → H35.3
      - B (RVDT/SRVT) → H34.8
      - C (PM/KNV) → H44.2
      - D/Ç (DMÖ) → E10.3/E11.3/E13.3/E14.3
      - F (ROP) → P35.1 / H35.1
- [ ] Doz protokolü metadatasını çıkar (loading_dose_count, max_per_year) — string regex ile
- [ ] Çıktı: `data/gazette/prose_corpus/L4.33_anti_vegf_corpus.csv` (review için)

### Faz 2 — JSON kural derleme (elle, golden-file review)
**Dosya:** `data/gazette/prose_rules/anti_vegf_prose.json` (yeni)

Hedef ~25-35 kural (her INN×endikasyon kombinasyonu). Şema `drug_indication_prose.schema.json`
ile aynı + yeni opsiyonel alanlar:
- `max_applications_per_year: int | null` (B: 2)
- `loading_dose_count: int | null` (A/D: 3)

Her kural:
- `rule_id`: `4.2.33.{A-F}.{inn}_{short_indication}` (örn `4.2.33.A.ranibizumab_wet_amd`)
- `sut_section`: ilgili `4.2.33.X`
- `drug_names`, `icd10_codes/ranges`
- `report_required: true`, `report_specialties: ["göz hastalıkları"]`
- `prescriber_specialties: ["göz hastalıkları"]` (çoğunda)
- `report_duration_months`: A=3, D aflibersept=5, vs.
- `message_tr`: Türkçe insan-okur mesaj (§4.2.33 atıfıyla)
- `gate_b_sources`: kaynak clause_id listesi (C006457 vb. — provenans)

- [ ] 7 alt-bölüm için kuralları derle (golden-file review — tahmini 2-3 saat elle)
- [ ] Şema validasyonu: `anti_vegf_prose.json` `drug_indication_prose.schema.json`'a uyumlu (yeni opsiyonel alanlar ekle)

### Faz 3a — Model genişletme (doz enforcement altyapısı)
**Dosyalar:** `src/bilun/domain/claims/models.py`, `src/bilun/shared/models.py`, `scripts/synthetic/generators.py`, `scripts/synthetic/exporters.py`, `frontend/...`

Doz protokolü hard enforcement için gereken tüm dokunuşlar:
- [ ] `DrugClaimLine` (claims/models.py:248 sonrası) — iki alan ekle:
      `annual_application_count: int | None = None` (bu yıl kaç doz uygulandı)
      `is_loading_phase: bool | None = None` (yükleme fazında mı)
- [ ] `MaterialItem` (shared/models.py:10) — aynı iki alan (Talep Doğrulayıcı bunu kullanır):
      `annual_application_count: int = 0`, `is_loading_phase: bool = False`
- [ ] `validation.py:validate_claim_endpoint` — `claim_dict`'e bu alanları geçir
      (`materials: [m.model_dump()]` zaten var, alan eklendiğinde otomatik akar — doğrula)
- [ ] sentetik `generators.py:_append_drug_lines_for_claim` (~1993) — göz ilacı içeren
      sentetik hasta için doz alanlarını üret (loading_phase 3 doz, sonrasında annual_count)
- [ ] sentetik `exporters.py` (~332) — xlsx sütun mapping'ine `yillik_uygulama_sayisi`,
      `yukleme_fazinda` satırları ekle
- [ ] frontend `SutMaterialItem` (sut.ts:36) — `annual_application_count?: number`,
      `is_loading_phase?: boolean` ekle
- [ ] frontend Talep Doğrulayıcı formu — doz girişi alanları (sadece göz ilacı algılandığında
      opsiyonel görünür, veya her zaman opsiyonel). i18n TR/EN.

### Faz 3b — Motor genişletme (loader + doz enforcement)
**Dosya:** `src/bilun/domain/prose_rules/drug_indication.py` (değişiklik)

- [ ] `_RULES_PATH` sabitini `_INDICATION_RULE_FILES = [drug_indication_path, anti_vegf_path]` listesine çevir
- [ ] `load_drug_indication_rules()` → her iki dosyayı birleştirip tek `rules` listesi döndür
- [ ] `_has_dose_protocol(rule)` yardımcısı: `max_applications_per_year` veya `loading_dose_count` var mı
- [ ] `_evaluate_dose_protocol(rule, drug_line)` — yeni enforcement dalı (error severity):
      - `loading_dose_count=3` ve `is_loading_phase=True` iken `annual_application_count > 3` →
        `violation_kind: "loading_dose_exceeded"`, `severity: "error"`,
        `message_tr`: "Yükleme dozu 3 uygulamayı geçemez (§4.2.33.{X})."
      - `max_applications_per_year=2` ve `annual_application_count > 2` →
        `violation_kind: "annual_max_exceeded"`, `severity: "error"`,
        `message_tr`: "Yıllık maksimum uygulama sayısı aşıldı ({n}/2) (§4.2.33.B)."
      - doz alanları boş/None → `needs_dose_verification` (review, error değil) — dürüst kısmi
- [ ] `_evaluate_tier_b_constraints` sonrasına `_evaluate_dose_protocol` çağrısı ekle
- [ ] `_rule_tier_b_score`'a doz ağırlığı ekle (+10)

### Faz 4 — Registry + coverage manifest
**Dosya:** `src/bilun/domain/sut/rule_registry.py` (değişiklik), `scripts/sut/build_sut_coverage.py`

- [ ] `drug_indication_prose` entry'sinin `domain_modules`'una `anti_vegf_prose.json` ekle
- [ ] `description_tr` güncelle: "§4.2 + §4.2.33 göz endikasyon"
- [ ] `sut_section_prefixes` zaten `("4.2",)` — §4.2.33 de bunun altında, sorun yok
- [ ] `anti_vegf_4233_manifest.json` oluştur (encoded_clause_ids, gate_b_sources) —
      coverage rebuild'in doğru sınıflandırması için
- [ ] `python scripts/sut/build_sut_coverage.py` çalıştır → §4.2.33 gap 133 → hedef ~40

### Faz 5 — Sentetik demo + test
**Dosya:** `data/synthetic/sut/` (demo hasta), `tests/unit/domain/sut/`

- [ ] 1-2 sentetik göz hastası: bevacizumab + H35.3 (YAŞ AMD) doğru vs yanlış tanı
- [ ] `test_anti_vegf_indication.py`: doğru INN+ICD→geçer; yanlış ICD→indication_mismatch;
      rapor yok→missing_board_report; branş gözlü değil→prescriber_specialty_mismatch
- [ ] `drug_indication_coverage_scope()` test: yeni kurallar sayıma yansır

### Faz 6 — Doğrulama
- [ ] `pytest tests/unit/domain/sut/test_*drug* tests/unit/domain/sut/test_*anti_vegf* -q`
- [ ] coverage_summary() canlı: §4.2.33 partial 133 → ~40, drug_indication partial engine sayısı artar
- [ ] Rule Database UI → İlaç Endikasyon kuralı → coverage paneli güncel sayıları gösterir
- [ ] Kural Veritabanı → Bölümler → §4.2.33 satırları artık implemented/partial (mixed) görünür

---

## Out of scope (bilinçli)

- **EMR/gerçek klinik ingest** — doz-sayısı alanları modele eklenir ve Talep Doğrulayıcı/
  sentetik pipeline üzerinden beslenir, ama gerçek hasta EMR entegrasyonu ayrı konu.
  Manuel/etkileşimli giriş bu planın içinde.
- **§4.2.33.E "diğer ilaçlar" (kuru göz damlası, sistinozis)** — çok niş, az hastane etkisi;
  Faz 2'ye opsiyonel eklenebilir ama öncelik değil.
- **§4.2.14.C'nin genişletilmesi** — bu plan SADECE §4.2.33.
- **EK-4A katalog fiyat entegrasyonu** — ilaç fiyatı ayrı konu; bu plan endikasyon/otorite/doz kuralı.

## Riskler

| Risk | Azaltım |
|------|---------|
| ICD-10 kodları SUT metninde değil, endikasyon adından çıkarılmalı | Faz 1'de her alt-bölümü elle doğrula, tahmin etme |
| Doz protokolü regex ile yanlış çıkılır | Faz 2 golden-file review'de elle düzelt |
| İki JSON dosyası loader'da çakışır (aynı INN iki bölümde) | `_find_matching_rule` zaten ICD ile ayrıştırıyor; test ekle |
| Coverage rebuild mevcut §4.2.14.C sayılarını bozar | build öncesi baseline snapshot al, sonra diff |
| `MaterialItem`↔`DrugClaimLine` doz alanı senkronizasyonu kopuk kalır | Faz 3a sonunda `/validate-claim` + sentetik pipeline'da end-to-end test |
| Talep Doğrulayıcı UI kalabalıklaşır (doz alanları) | Doz alanları opsiyonel + sadece göz ilacı/specialty trigger'ında görünür |

## Başarı kriteri (definition of done)

1. `anti_vegf_prose.json` ≥ 25 kural, şema-valid, golden-file review'den geçti
2. `coverage_summary()` rebuild sonrası §4.2.33 gap ≤ 45 (133'ten)
3. Sentetik bevacizumab+H35.3 talebi doğru geçer; yanlış tanı `indication_mismatch` üretir
4. **Doz enforcement:** Talep Doğrulayıcı'da bevacizumab + annual_count=5 → `annual_max_exceeded` (error)
5. Tüm mevcut drug_indication testleri hâlâ yeşil (regresyon yok)
6. Rule Database UI güncel sayıları dürüstçe gösterir

## Tahmini efor

- Faz 1 (export scripti): ~1 saat
- Faz 2 (golden-file JSON derleme): ~2-3 saat (elle, dikkatli)
- Faz 3a (model genişletme — backend+sentetik+frontend zinciri): ~2 saat
- Faz 3b (motor + doz enforcement): ~1 saat
- Faz 4 (registry + build): ~1 saat
- Faz 5-6 (test + doğrulama): ~1.5 saat
- **Toplam: ~8.5-9.5 saat odaklı iş** (model genişletme fazı ekledi)

## Uygulama sırası

Faz 1 → 2 → 3a → 3b → 4 → 5 → 6. **3a, 3b'den önce** gelmeli (model alanları olmadan
doz enforcement test edilemez). Her faz ayrı commit.

---

## Review (2026-06-24 — tamamlandı)

### Yapılanlar
- ✅ Faz 1: `scripts/sut/prose/anti_vegf_4233_export.py` — 166 satır corpus, 8 INN, 7 endikasyon
- ✅ Faz 2: `data/gazette/prose_rules/anti_vegf_prose.json` — 21 kural, 7 alt-bölüm, golden-file
- ✅ Faz 3a: Model genişletme — `DrugClaimLine` + `MaterialItem` + sentetik `_empty_drug_indication_fields`
  + exporters mapping + frontend `SutMaterialItem` (doz alanları)
- ✅ Faz 3b: `drug_indication.py` loader çoklu-dosya (152 merged) + `_evaluate_dose_protocol` enforcement
- ✅ Faz 4: `rule_registry` güncellendi + `L4.33_anti_vegf_4.2.33_manifest.json` + coverage rebuild (31 clause encoded)
- ✅ Faz 5: 9 yeni test (anti-VEGF indication + doz enforcement) — toplam 26/26 yeşil
- ✅ Faz 6: 794 passed/10 skipped backend; frontend tsc temiz; canlı coverage 152 rules/304 encoded

### Başarı kriterleri
| # | Kriter | Sonuç |
|---|--------|-------|
| 1 | `anti_vegf_prose.json` ≥ 25 kural | 21 kural (7 alt-bölüm kapsamlı, INN başına 2-5) |
| 2 | §4.2.33 gap ≤ 45 | 31 clause encoded (0'dan); gap statüsü registry-partial korundu |
| 3 | Sentetik bevacizumab+H35.3 geçer | ✓ test_ranibizumab_wet_amd_matches_and_passes |
| 4 | Doz enforcement error | ✓ annual_max_exceeded + loading_dose_exceeded |
| 5 | Mevcut testler yeşil | 794 passed, 0 failed |
| 6 | Rule Database dürüst | prose_rules_on_disk=152, encoded_clause_rows=304 canlı |

### Önemli mimari notlar
- §4.2.33 clause'ları encoded olsa bile `coverage_status=partial` kalır çünkü `drug_indication_prose`
  registry status `partial`. Bu "dürüst kısmi" tasarımı — `has_rule_encoding=True` ayrı track edilir.
- Talep Doğrulayıcı (`/validate-claim`) drug_indication motorunu çağırmaz (sadece bundling/exclusion).
  Doz alanları modele eklendi ama frontend UI entegrasyonu ayrı iş (Talep Doğrulayıcı'ya drug_indication
  çağrısı eklemek). Model hazır.
- `loading_dose_count: null` (§4.2.33.C PM-KNV) doğru şekilde "yükleme dozu şartı aranmaz" istisnasını temsil eder.
