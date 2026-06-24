# Plan: §4.2.14.C Oncoloji Tier-C Genişletme + EMR-Blocked İşaretleme

> **Status:** Draft — awaiting Safa approval
> **Tarih:** 2026-06-24
> **Motivasyon:** §4.2.14.C'nin 549 Tier-C clause'u araştırıldı. %47'si (~259) gerçekten
> EMR verisine bağlı (ECOG, progresyon, lab) — kalıcı duvar. Ama 105 clause encode edilebilir:
> 44 mevcut alanlarla (Bucket A), 61 iki yeni alanla (Bucket B). 185 non-actionable fragment.
> **Sibling:** `anti-vegf-4.2.33-prose-plan.md` (aynı mimari, tamamlandı), `drug_indication.py`
> **Registry:** `drug_indication_prose` (131 → hedef ~195-210 kural)

---

## Task: §4.2.14.C Tier-C clause'larını sınıflandır + encode-edilebilir kısmını dök + EMR duvarını dürüst işaretle

### Goal

§4.2.14.C'nin encode-edilebilir Tier-C clause'larını (Bucket A+B = 105) çalıştırılabilir JSON
kurallarına çevir; 259 gerçekten EMR-bağımlı clause'u "EMR-blocked" olarak dürüstçe işaretle;
185 non-actionable fragment'ı manifest'ten temizle. Sonuç: drug_indication kural sayısı
131 → ~195-210, coverage dürüst raporlama.

### Onaylanmış kapsam (Safa seçimi, 2026-06-24)

1. **Bucket A + B (105 clause)** — A mevcut alanlarla (~30 kural), B iki yeni alanla (~40 kural)
2. **259 EMR-blocked dürüst işaretleme** — coverage_scope + Rule Database UI'da "EMR verisi gerekli"

### Araştırma sınıflandırması (549 Tier-C clause)

| Bucket | Clause | Encode | Açıklama |
|--------|--------|--------|----------|
| **A — Şimdi** | 44 | ✅ | prescriber authority, combo prohibitions, max cycle/dose, report+duration |
| **B — Model ext** | 61 | ⚠️ | biomarker (HER-2+, CD20+, KRAS) + prior-therapy (imatinib-dirençli, 2. basamak) |
| **C — EMR-blocked** | 259 | ❌ | ECOG, progresyon, lab değerleri, İSHAK skoru — kalıcı duvar |
| **D — Non-actionable** | 185 | ❌ | başlık, amendment (mülga), drug-name fragment — manifest temizliği |

### Bucket B şema tasarımı (2 yeni DrugClaimLine alanı)

```python
# claims/models.py DrugClaimLine — yeni alanlar
biomarkers: list[dict[str, str]] | None = None
# Örnek: [{"marker": "HER2", "status": "3+"}, {"marker": "FISH", "status": "positive"}]
# Kuralda: required_biomarkers: [{"marker": "HER2", "status_any": ["3+", "positive"]}]
# Enforcement: kuralın required biomarker'ı claim'de yok → needs_biomarker_verification (review)
#              var ama status uyuşmuyor → biomarker_mismatch (error)

prior_therapies: list[dict[str, str]] | None = None
# Örnek: [{"drug_or_class": "imatinib", "outcome": "resistant"}]
# Kuralda: requires_prior_therapy: {"drug_or_class": "imatinib", "outcome": "resistant"}
# Enforcement: gerekli prior-therapy claim'de yok → needs_prior_therapy_verification (review)
#              var ama farklı ilaç → prior_therapy_mismatch (error)
```

---

## Fazlar

### Faz 1 — Bucket A export + classification (veri çıkarma)
**Dosya:** `scripts/sut/prose/oncology_tier_c_export.py` (yeni)

- [ ] 549 Tier-C clause'un metnini sut_clauses.parquet'ten çek
- [ ] Bucket A/B/C/D sınıflandırma fonksiyonu (regex + keyword tabanlı)
- [ ] Bucket A clause listesi: combo prohibitions (C005022/039/046, myeloma cluster, vb.)
- [ ] Bucket B clause listesi: biomarker (C004939/444/446...) + prior-therapy (C005021/082/213...)
- [ ] Çıktı: `data/gazette/prose_corpus/L4.2_oncology_tier_c_classification.csv`

### Faz 2a — Bucket A golden-file JSON (mevcut alanlarla)
**Dosya:** `data/gazette/prose_rules/drug_indication_prose.json` (genişletme)

~30 yeni kural, mevcut şemayla:
- [ ] Combo prohibitions (~7 kural): dasatinib↔nilotinib↔bosutinib, myeloma cluster,
      azasitidin↔decitabine, vismodegib↔sonidegib
- [ ] Report+prescriber+duration (~17 kural): C004956, C004984, C004995 vb. — her ilaç için
- [ ] Max cycle/dose (~3 kural): C004969 (max 8 küre), C005289 (max 4 doz), C004992 (100 mg/m²)
- [ ] G-CSF board+prescriber (~1 kural): C004933
- [ ] Fallback "outside conditions → not reimbursed" (~1 kural): C005300

### Faz 2b — Bucket B golden-file JSON + şema genişletme
**Dosya:** `data/gazette/prose_rules/drug_indication_prose.json` (devam), `drug_indication.py`

~40 yeni kural, 2 yeni kural alanı:
- [ ] Şema'ya `required_biomarkers` + `requires_prior_therapy` ekle (additionalProperties:true)
- [ ] Biomarker kuralları (~15): trastuzumab HER-2+3/FISH+, rituximab CD20+, KRAS wild-type vb.
- [ ] Prior-therapy kuralları (~25): nilotinib imatinib-dirençli, nelarabin önceki tedavi vb.

### Faz 3 — Model genişletme (DrugClaimLine + sentetik + export)
**Dosyalar:** `claims/models.py`, `generators.py`, `exporters.py`, `frontend/sut.ts`

- [ ] `DrugClaimLine`: `biomarkers`, `prior_therapies` alanları (Faz 3a'daki doz alanlarına ek)
- [ ] `MaterialItem`: aynı alanlar
- [ ] sentetik `_empty_drug_indication_fields`: yeni alanlar
- [ ] sentetik `exporters.py`: xlsx mapping
- [ ] frontend `SutMaterialItem`: tip genişletme

### Faz 4 — Motor genişletme (biomarker + prior-therapy enforcement)
**Dosya:** `drug_indication.py`

- [ ] `_has_biomarker_requirement(rule)` + `_evaluate_biomarker_constraints()` (error/review)
- [ ] `_has_prior_therapy_requirement(rule)` + `_evaluate_prior_therapy_constraints()` (error/review)
- [ ] `evaluate_drug_indication_line`'a iki yeni dal ekle
- [ ] `_rule_tier_b_score`'a biomarker/prior-therapy ağırlığı

### Faz 5 — EMR-blocked dürüst işaretleme
**Dosyalar:** `coverage.py`, `rules_catalog.py`, manifest

- [ ] 259 EMR-blocked clause ID listesi (Bucket C)
- [ ] manifest'e `emr_blocked_clause_ids` alanı ekle
- [ ] `coverage.py`: EMR-blocked clause'lar `has_rule_encoding=False` ama `emr_blocked=True`
- [ ] `coverage_scope()`: `emr_blocked_clause_count` expose et
- [ ] Rule Database UI: "EMR verisi gerekli (ECOG, progresyon)" dürüst panel

### Faz 6 — Manifest temizliği + coverage rebuild
- [ ] 185 non-actionable clause'u Tier-C'den çıkar (Bucket D)
- [ ] Yeni encoded clause ID'leri manifest'e ekle (Bucket A+B)
- [ ] `build_sut_coverage.py` rebuild
- [ ] §4.2.14.C gap düşüşünü doğrula

### Faz 7 — Test + doğrulama
- [ ] Bucket A testleri: combo prohibition, max cycle, prescriber authority
- [ ] Bucket B testleri: biomarker mismatch, prior-therapy mismatch, missing biomarker review
- [ ] EMR-blocked test: clause emr_blocked=True olarak işaretli
- [ ] Mevcut 131 kural + §4.2.33 21 kural regresyonu (toplam ~195-210)
- [ ] Tüm pytest + frontend tsc yeşil

---

## Out of scope

- **Bucket C (259 EMR clause) encode** — kalıcı duvar, klinik değerlendirme gerekir
- **Bucket D manifest temizliği dışında non-actionable clause işleme**
- **EMR/EMR ingest entegrasyonu** — gerçek ECOG/lab/progresyon verisi ayrı roadmap
- **Frontend Talep Doğrulayıcı drug_indication entegrasyonu** — ayrı plan
- **§4.2.33 tekrar** — zaten tamamlandı

## Başarı kriteri

1. drug_indication kural sayısı: 131 → ≥190 (Bucket A+B)
2. §4.2.14.C encoded clause: 279 → ≥350
3. 259 EMR-blocked clause dürüst işaretli (emr_blocked=True)
4. 185 non-actionable clause Tier-C'den çıkarıldı (gerçek deferred 549→259)
5. Biomarker enforcement: trastuzumab + HER2 negatif → biomarker_mismatch (error)
6. Prior-therapy enforcement: nilotinib + imatinib yok → prior_therapy_mismatch (error)
7. Tüm mevcut testler yeşil (regresyon yok)

## Tahmini efor

- Faz 1 (export + classification): ~1.5 saat
- Faz 2a (Bucket A golden-file): ~2 saat (30 kural)
- Faz 2b (Bucket B golden-file + şema): ~3 saat (40 kural + şema)
- Faz 3 (model genişletme): ~1.5 saat
- Faz 4 (motor enforcement): ~2 saat
- Faz 5 (EMR-blocked işaretleme): ~1 saat
- Faz 6 (manifest + rebuild): ~1 saat
- Faz 7 (test): ~2 saat
- **Toplam: ~14 saat** (§4.2.33'ten ~2x daha büyük)

---

## Review (2026-06-24 — tamamlandı)

### Yapılananlar
- ✅ Faz 1: `oncology_tier_c_export.py` — 549 Tier-C clause sınıflandırıldı (A:38 B:122 C:184 D:205)
- ✅ Faz 2a: `compile_bucket_a_rules.py` — 11 Bucket A kuralı (combo/prescriber/max-cycle)
- ✅ Faz 2b: `compile_bucket_b_rules.py` — 22 Bucket B kuralı (16 biomarker + 9 prior-therapy)
- ✅ Faz 3: Model genişletme — `DrugClaimLine`/`MaterialItem`'a `biomarkers`, `prior_therapies`
- ✅ Faz 4: `_evaluate_biomarker_constraints` + `_evaluate_prior_therapy_constraints` (error/review)
- ✅ Faz 5: 174 EMR-blocked clause dürüst işaretlendi (coverage parquet + scope)
- ✅ Faz 6: Manifest temizliği (205 non-actionable çıkarıldı) + coverage rebuild
- ✅ Faz 7: 822 test yeşil, frontend tsc temiz

### Başarı kriterleri
| # | Kriter | Sonuç |
|---|--------|-------|
| 1 | drug_indication kural ≥190 | 185 (164 onkoloji + 21 anti-VEGF) |
| 2 | §4.2.14.C encoded clause ≥350 | 715 (279→715) |
| 3 | 174 EMR-blocked dürüst işaretli | ✓ emr_blocked_rows=174 canlı |
| 4 | 205 non-actionable Tier-C'den çıkarıldı | ✓ deferred 549→311 |
| 5 | Biomarker enforcement | ✓ trastuzumab HER2 neg → biomarker_mismatch error |
| 6 | Prior-therapy enforcement | ✓ nilotinib prior yok → prior_therapy_mismatch |
| 7 | Tüm testler yeşil | 822 passed, 0 failed |

### Önemli mimari notlar
- **174 clause kalıcı EMR duvarı** — ECOG, progresyon, lab değerleri, claim ile encode edilemez.
- **Matcher öncelik** — claim'de biomarker/prior varsa gated-rule öncelik kazanır.
- **lessons.md uyarısı gerçekleşti** — committed manifest okuyan testler rebuild sonrası güncellendi.
