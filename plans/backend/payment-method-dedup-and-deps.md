# Plan: Payment-Method Re-derivation + Cross-Detector Dependency Cleanup

**Tarih:** 2026-07-13
**Kapsam:** `src/bilun/domain/` — payment-method classification duplication + cross-detector dependency wiring
**Yöntem:** 3 paralel Explore subagent (call-site tracing, ctx/findings feasibility, exactness/JSON verification) ile kanıtlandı

---

## v2 Revizyon notu (derin araştırma sonrası)

Bu planın ilk taslağında "findings dict ekle" öneriliştin. Derin araştırma **bunu değiştirdi**: findings dict aşırı kill — yalnızca 3 cross-detector kwarg var (2 detectörde). Bunun yerine gerçek problem **payment-method re-derivation**: aynı `(code, care_setting, tier, provider, as_of)` tuple'ı için `resolve_payment_method` bir claim'de **5N–9N kez** çağrılıyor (N = procedure line sayısı). Bu önceliklendir.

## Goal

Payment-method classification'ı claim başına bir kez hesapla, sonuçları paylaş. Cross-detector de-duplication kwargs'ını standardize et. Eksik pipeline bağlantılarını (`_build_gap_closing_context` 3× rebuild, `_derive_payment_method_path` 2× copy-paste) düzelt.

## Teşhis — kanıtlanmış bulgular

### Problem 1 — `resolve_payment_method` re-derivation (HIGH, en büyük maliyet)

**Maliyet:** Report path'te bir claim için ~5N–9N çağrı; validation path'te ek ~4N. N=10 inpatient claim için **50–130 gereksiz sınıflandırma**.

`resolve_payment_method` ucuz bir dict lookup DEĞİL — her çağrı 3 catalog lookup + tier normalization + dataclass allocation yapıyor (`payment_method.py:170-312`). **Hiç memoization yok.**

**Report path çağrı haritası** (`patient_report.py:compute_patient_billing_report`):

| Detector | resolve_payment_method çağrıları | Şart |
|---|---:|---|
| `billing_strategy` ilk döngü (`claim_strategy.py:291`) | **2N** | her zaman |
| `billing_strategy` ikinci döngü (`claim_strategy.py:350`) | **3N** | package_candidate claim'ler |
| `drg_uplift` (`claim_drg_uplift.py:106,122`) | **2N** | strategy uplift bulmadıysa |
| `care_setting_review` (`care_setting_review.py:85`) | **2N** | care-setting belirsiz + 3. basamak |
| **Validation path ekstra** | | |
| `engine.py:analyze_claim` — `_build_gap_closing_context` 3× + fatura_inceleme 1× | **~4N** | her zaman |

**Kritik gerçek:** cache key `(procedure_code, care_setting, facility_tier, provider_type, as_of_date)` bir report run içinde **stabil** (`as_of_date=None` → `date.today()` catalog içine resolve olur). Yani tüm 5N–9N çağrı **aynı sonuç** döndürür.

### Problem 2 — Duplikat fonksiyon tanımları (MED)

- **`_aggregate_claim_kind`** — 2 kopya: `care_setting_review.py:45` (kinds alır) + `claim_strategy.py:188` (results alır). Mantık neredeyse aynı, farklı input type.
- **`_derive_payment_method_path`** — 2 kopya: `gap_closing.py:236` + `fatura_inceleme.py:370`. fatura'nın docstring'i (`:376`) *"Derive payment method (same as gap_closing.py)"* diyor — yazarlar biliyor ama consolidate etmemiş.
- **`_build_gap_closing_context`** — `engine.py:analyze_claim` içinde **3×** çağrılıyor (misc `:172` + treatment `:173` + traceability `:184`), her seferinde aynı context'i rebuild ediyor.

### Problem 3 — Cross-detector kwargs (LOW — findings dict AŞIRI KILL)

Araştırma gösterdi ki, gerçek cross-detector bağımlılık **yalnızca 3 kwarg, 2 detectörde**:

| Consumer | Kwarg | Producer |
|---|---|---|
| `claim_drg_uplift.py:75` | `session_opportunities` | `recommend_session_uplift_from_claims` |
| `claim_drg_uplift.py:75` | `strategy_recommendations` | `recommend_billing_strategy_from_claims` |
| `claim_procedure_addon_uplift.py:25` | `session_uplift_opportunities` | `recommend_session_uplift_from_claims` |

`patient_report.py` harness'i zaten doğru sırada, lineer, tek fonksiyon (~18 çağrı). Findings dict sadece bu 3 kwarg'ı değiştirirdi — **payoff yok**. Ayrıca kwarg isimleri tutarsız (`session_opportunities` vs `session_uplift_opportunities`).

### Doğrulandı: KEEP-AS-IS kararları

**report_totals.py exactness fusion** — DOĞRU. `_sum_exact_block_field` (`report_totals.py:24-32`) data-driven `BILLING_BLOCK_SPECS` tablosu üzerinden merkezileştirilmiş. Detectörler kendi exactness-only logic'ini re-implement etmiyor. Post-hoc fusion doğru mimari (detectörler saf, tek chokepoint). **Aksiyon yok.**

**JSON condition-on-derived-field** — DOĞRU. `_condition_matches` (`gap_closing.py:77-177`) missing key → honest skip (False döner, asla hata veya false-fire atmaz). 4 JSON rule set (~223 kural) paylaşılan predicate engine kullanıyor. Regression test'li. **Aksiyon yok** (tek low-priority cleanup: `fatura_inceleme.py:119-176` duplikat `_condition_matches` → import).

---

## Phase 1 — `resolve_payment_method` memoization (en yüksek etki)

**Hedef:** Aynı input tuple için tekrar tekrar sınıflandırmayı önle. 5N–9N → N'ye düşür.

### Strateji: wrapper + inner cached function (explicit None→today resolution)

`as_of_date=None` catalog içine resolve olunca cache key kararsızlaşır. Çözüm: `None → date.today()` resolution'ı **wrapper**'da yap, cache **inner** fonksiyona koy. Bu plan v1'in "karar ver" belirsizliğini giderir (GLM eval Sorun 1).

```python
def resolve_payment_method(
    procedure_code: str,
    *,
    care_setting: CareSetting = "inpatient",
    facility_tier: str | None = None,
    provider_type: str | None = None,
    as_of_date: date | None = None,
) -> PaymentMethodResult:
    # None → today() resolution wrapper'da; inner cache key her zaman concrete date
    if as_of_date is None:
        as_of_date = date.today()
    return _resolve_payment_method_cached(
        procedure_code, care_setting, facility_tier, provider_type, as_of_date
    )

@lru_cache(maxsize=None)  # maxsize=None: sınırsız — ~10MB peak (5000 kod × 10 kombinasyon × ~200B)
def _resolve_payment_method_cached(...) -> PaymentMethodResult:
    ...mevcut body...
```

### Subtasks
- [ ] **1.1 Wrapper + inner split:** yukarıdaki pattern'i uygula. `resolve_payment_method` wrapper olur (cache'siz), `_resolve_payment_method_cached` inner olur (`@lru_cache(maxsize=None)`). `maxsize=None` tercih edildi — 5000 EK-2B kodu × ~10 kombinasyon × ~200 byte ≈ 10MB peak, sorun değil (GLM eval Sorun 2).
- [ ] **1.2 `PaymentMethodResult` frozen doğrula:** `@lru_cache` hashable return ister. `__dataclass_params__.frozen = True` doğrulandı (GLM eval). Eğer `ProseRuleTrace` veya nested alanlar mutable ise, onları da frozen yap veya cache'i `frozen=True` ile eşle.
- [ ] **1.3 `check_payment_method_compliance` otomatik faydalanır:** `payment_method.py:315` zaten `resolve_payment_method` çağırıyor (`:325`), yani 1.1 otomatik olarak bunu da hızlandırır. Ekstra cache gerekmez.
- [ ] **1.4 Cache eviction / test izolasyonu:** `@lru_cache`'in `cache_clear()` fonksiyonunu test fixture'larına expose et. `_resolve_payment_method_cached.cache_clear()` conftest'te çağırılsın ki test'ler birbirini etkilemesin.
- [ ] **1.5 Benchmark:** mevcut bir `compute_patient_billing_report` çağrısının süresini before/after ölç (10-line claim). 5N–9N → N düşüşünü doğrula.
- [ ] **1.6 Test:** mevcut tüm payment-method test'leri yeşil kalmalı. Yeni test: aynı input ile 2. çağrının cache'den geldiğini doğrula (`_resolve_payment_method_cached.cache_info()` ile hit count).

### Out of Scope
- `resolve_payment_method`'ın kendisini yeniden yazma (sadece cache ekle)
- Catalog lookup'ları cache'leme (onlar zaten `@lru_cache`'li olabilir, kontrol et ama ayrı task)

---

## Phase 2 — Duplikat fonksiyonları konsolide (MED)

**Hedef:** Güvenli, low-risk duplikasyonları konsolide et. **Her birinin farklı uzantıları olan 5 ek kopya AYRI task'a ertelendi** (GLM eval v3 düzeltmesi).

### `_condition_matches` duplikasyon haritası (düzeltildi: 2 değil 7 kopya)

| Dosya | Satır | Uzunluk | Gap_closing ile aynı mı? | Risk |
|---|---|---:|---|---|
| `gap_closing.py:77` | canonical | 101 | — | — |
| `fatura_inceleme.py:116` | kopya | 68 | ✅ evet (docstring itiraf ediyor) | DÜŞÜK — Phase 2.2 |
| `fatura_inceleme_checklist.py:92` | kopya | 23 | ✅ evet (basit subset) | DÜŞÜK — Phase 2.2 |
| `specialty_materials.py:103` | kopya | 35 | muhtemelen evet | ORTA — ertelendi |
| `dental_2_4_1.py:107` | farklı imza | 34 | HAYIR — `mat: dict` alır, `context: dict` değil | ertelendi |
| `material_bundling.py:173` | kopya | 143 | kısmen | ORTA — ertelendi |
| `treatment_pricing.py:161` | **genişletilmiş** | 160 | HAYIR — diagnosis prefix + numeric range eklemiş | ertelendi |

**Kritik:** `treatment_pricing._condition_matches` (160 satır) gap_closing'inkinden (101 satır) farklı olarak ICD-10 diagnosis prefix matching + `{min,max}` numeric range predicate'leri içeriyor (`treatment_pricing.py:161-321`, docstring `:6-7` ve `:16-18`). Bunları gap_closing'e zorla merge etmek regression riski taşır.

### Subtasks
- [ ] **2.1 `_derive_payment_method_path` tek kaynak:** `fatura_inceleme.py:370`'deki kopyayı sil, `gap_closing.py:236`'dan import et. `fatura_inceleme.py:119` comment'i ("Same predicate engine") göre bu zaten planlanmış. `payment_method.py:411` comment'i de aynı notu düşüyor.
- [ ] **2.2 `fatura_inceleme` + `fatura_inceleme_checklist` `_condition_matches` → import:** Bu 2 kopya gap_closing'inkinin safe subset'i. Sil, `from .gap_closing import _condition_matches` yap. `payment_method.py:415-418` bu pattern'i zaten kullanıyor (precedent var). **Sadece bu 2'si — diğer 5 kopya ayrı task.**
- [ ] **2.3 `_aggregate_claim_kind` — sibling fonksiyonlar olarak bırak:** 2 kopya farklı input tipleri alıyor (kinds vs results). **Generic tek fonksiyon YAPMA** (GLM eval uyarısı) — bunun yerine ortak `_pick_claim_kind(kinds: list[PaymentMethodKind])` etrafında iki sibling fonksiyon tut. Hangi detectör hangisini çağırıyor: `care_setting_review.py:76` (kinds), `claim_strategy.py:365` (results), `claim_drg_uplift.py:109` (results).
- [ ] **2.4 `_build_gap_closing_context` rebuild'i azalt — ama wrapper'ları KORU:** `engine.py:172,173,184` 3× context build ediyor (misc + treatment aynı `_build_gap_closing_context`'i 2× çağırıyor; traceability `payment_method.py:447` üzerinden tekrar çağırıyor).

  **Karar (v3 — belirsizlik giderildi):** `check_*_for_context` fonksiyonları **public API** — test dosyaları doğrudan çağırıyor (`test_gap_closing_for_context.py:132,139`, `test_payment_method_traceability_for_context.py:103+`, `test_fatura_inceleme_for_context.py:162+`). Wrapper'ları **kaldırma**.

  **Güvenli çözüm:** `analyze_claim` içinde `_build_gap_closing_context(ctx)` sonucunu **local var'da tut**, ama `check_gap_closing_misc_for_context` / `check_gap_closing_treatment_for_context`'in imzasını değiştirmeden — bunun yerine gap_closing.py içindeki `_build_gap_closing_context`'e **`@lru_cache` ekle** (input `PatientClaimContext` frozen=True → hashable). Böylece 3 çağrı 1 compute olur, public API bozulmaz. `fatura_inceleme._build_fatura_inceleme_context` (124 satır) gap_closing ile neredeyse aynı kod — bu da 2.1+2.2 ile birlikte naturally consolidate olur.
- [ ] **2.5 `claim_strategy.py:370` yerel duplikasyon:** `_itemized_exclusion_metadata` `lines_for_legal_itemized_alternative`'i 2× çağırıyor (`:369` ve `:370`). Sonucu bir kez hesapla, değişkene ata, geç.
- [ ] **2.6 Test:** tüm `test_claim_strategy_*`, `test_gap_closing_*`, `test_fatura_inceleme_*`, `test_payment_method_*` yeşil.

### Out of Scope (ertelendi — ayrı refactor task)
- **`_condition_matches` 5 ek kopyası** (`specialty_materials`, `material_bundling`, `dental_2_4_1`, `treatment_pricing`, ve varsa diğerleri). Her birinin farklı uzantıları var (`treatment_pricing` diagnosis prefix + numeric range; `dental_2_4_1` farklı imza). Acele birleştirmek regression riski. Ayrı task: önce `treatment_pricing`'in extension'larını gap_closing canonical'ına **ekle** (backward-compatible), sonra diğerlerini migrate et.
- `check_*_for_context` wrapper'larını kaldırma — public API, test'ler doğrudan çağırıyor.

---

## Phase 3 — Cross-detector kwarg standardizasyonu (LOW)

**Hedef:** 3 kwarg'ı temizle. Findings dict YOK — aşırı kill.

### Subtasks
- [ ] **3.1 Kwarg isimlerini standardize:** `session_opportunities` (claim_drg_uplift) vs `session_uplift_opportunities` (claim_procedure_addon_uplift) — tutarsız. Birini seç (öneri: `session_opportunities`), her ikisinde uygula.
- [ ] **3.2 `patient_report.py` wiring comment'i:** `:107-111` ve `:128-134`'teki cross-detector bağımlılıkları comment ile işaretle (session + strategy, drg_uplift'tan ÖNCE çalışmalı). **Not:** bu gerçek bir subtask değil, tek satırlık comment — 3.1 ile aynı commit'te yap (GLM eval notu).
- [ ] **3.3 Findings dict ekleme:** araştırma gösterdi ki sadece 3 kwarg, 2 detectörde — findings dict bu payoff için aşırı. Mevcut explicit-kwargs pattern'i koru. **Bu subtask NO-OP** (karar belgelendi).

### Out of Scope
- `engine.py:analyze_claim`'deki 22 `check_*_for_context(ctx)` çağrısı — bunlar zaten ctx-only, hiçbiri cross-detector veri taşımıyor. Findings dict burada hiçbir şey değiştirmezdi.

---

## Verification

- `python -m pytest tests/unit/domain/prose_rules/ tests/unit/domain/billing/ -q` — tüm testler yeşil
- Phase 1 benchmark: `compute_patient_billing_report` tek-claim süresi before/after
- `resolve_payment_method.cache_info()` — hit rate > 80% (10-line claim'de)
- Manuel: bir DRG claim'de `analyze_claim` + `compute_patient_billing_report` çalıştır, doğru violation/uplift ürettiğini doğrula

## Execution order

**Phase 1** (memoization — en yüksek etki, en düşük risk) → **Phase 2** (duplikasyon konsolidasyonu) → **Phase 3** (kwarg standardizasyonu, küçük).

Her phase ayrı commit. Phase 1 tek başına 5N–9N → N düşüşü sağlar (en büyük kazanç).

---

## Araştırma kaynakları (3 paralel agent çıktısı)

- **Agent 1 (payment-method tracing):** resolve_payment_method'un 6 çağrı noktası, report path 5N-9N sayımı, validation path 4N ekstra, `PaymentClaimContext` frozen analizi.
- **Agent 2 (findings dict feasibility):** 22 `check_*_for_context`'in hepsi ctx-only; sadece 3 cross-detector kwarg var (2 detectörde); `CohortClaimContext` ve `SessionPricingResult` frozen-dataclass-with-mutable-dict precedenti mevcut; `(violations, findings)` tuple return 22 çağrı noktasını kırar ama payoff yok.
- **Agent 3 (exactness + JSON verification):** `report_totals.py` merkezileştirilmiş + data-driven spec tablosu (keep-as-is doğru); `_condition_matches` missing-key→honest-skip güvenli + regression test'li (keep-as-is doğru); `fatura_inceleme.py` duplikat `_condition_matches` tek cleanup notu.

## v2 Değişiklik günlüğü

| # | Kaynak | Değişiklik |
|---|---|---|
| 1 | Agent 2 | **Findings dict ÇIKARILDI** — sadece 3 kwarg/2 detectör, payoff yok. Phase 3 kwarg standardizasyonuna indirgendi. |
| 2 | Agent 1 | **Memoization önceliklendirildi** — 5N-9N re-derivation en büyük gerçek maliyet. Phase 1 yapıldı. |
| 3 | Agent 1 | `_build_gap_closing_context` 3× rebuild (validation path) Phase 2'ye eklendi. |
| 4 | Agent 1 | `_aggregate_claim_kind` ve `_derive_payment_method_path` duplikasyonları Phase 2'ye eklendi. |
| 5 | Agent 3 | `report_totals` ve JSON condition pattern "keep-as-is" kanıtla doğrulandı. |
| 6 | Agent 3 | `fatura_inceleme._condition_matches` duplikasyon cleanup olarak Phase 2'ye eklendi. |

## v3 Değişiklik günlüğü (GLM eval doğrulaması sonrası)

Tüm GLM eval iddiaları koda karşı tekrar doğrulandı (bağımsız grep + AST):

| # | GLM eval iddiası | Doğrulandı | Değişiklik |
|---|---|---|---|
| 7 | `_condition_matches` 2 değil **7 kopya** | ✅ grep + AST ile teyit | Phase 2.2 sadece güvenli 2 kopyayı hedefler; diğer 5'i "Out of Scope" olarak ayrı task'a ertelendi |
| 8 | `treatment_pricing._condition_matches` diagnosis prefix + numeric range ekstra özellikleri var | ✅ docstring + grep teyit | Blind consolidate regression riski → ertelendi; ayrı task'ta gap_closing canonical'ına backward-compatible extension gerekir |
| 9 | Phase 1 `as_of_date` çözümü belirsiz ("karar ver") | ✅ doğru eleştiri | Explicit wrapper+inner pattern yazıldı (None→today wrapper'da, cache inner'da) |
| 10 | `maxsize=4096` yeterli ama `maxsize=None` daha güvenli | ✅ ~10MB peak hesabı makul | `maxsize=None` olarak değiştirildi |
| 11 | `check_*_for_context` public API, test'ler doğrudan çağırıyor | ✅ grep teyit (test dosyaları) | Phase 2.4 "wrapper'ları kaldırma" → `@lru_cache` on `_build_gap_closing_context` olarak değiştirildi |
| 12 | Phase 2.3 `_aggregate_claim_kind` generic birleştirme riskli | ✅ farklı input tipleri | Sibling fonksiyonlar (`_pick_claim_kind` etrafında) olarak değiştirildi, generic yapma |
| 13 | Phase 3.2 comment bir subtask değil | ✅ doğru | "3.1 ile aynı commit" notu eklendi |

---

## Implementation Review (2026-07-13)

### Durum: Tamamlandı ✅

Tüm 3 phase implement edildi.

### Verification
- **prose_rules + billing test'leri:** 1415/1415 yeşil
- **Tüm unit test'leri (API hariç):** 2165 passed, 6 skipped, 0 failed
- **API test'leri:** 1 failure var ama **environment issue** (Cursor editor `.cache/bilun.duckdb` lock tutuyor — "Conflicting lock is held in /usr/share/cursor/cursor"). Refactor ile ilgisiz.
- **Phase 1 benchmark:** 5N=50 çağrı → 10 compute (N), **80% hit rate**, 5× azalma — planın tahmini doğrulandı.

### Phase 1 — resolve_payment_method memoization ✅
- Wrapper + inner cached function pattern: `resolve_payment_method` (wrapper, `as_of_date=None → date.today()` resolve) → `_resolve_payment_method_cached` (`@lru_cache(maxsize=None)`).
- `PaymentMethodResult` frozen=True doğrulandı.
- `tests/conftest.py`'ye autouse fixture: her test öncesi cache clear.
- Yeni test: `test_resolve_payment_method_is_memoized` — `first is second` (cache'den identical object), `cache_info().hits >= 1`.

### Phase 2 — Duplikasyon konsolidasyonu ✅
- **2.1 `_derive_payment_method_path`:** fatura_inceleme'deki kopya silindi, gap_closing'den import ediliyor.
- **2.2 `_condition_matches`:** fatura_inceleme'deki 68-satır kopya + `_suffix_len` + `_SET_PREDICATE_SUFFIXES` + `_SCALAR_FIELDS` silindi, gap_closing'den import. **Not:** `fatura_inceleme_checklist._condition_matches` AYNI BIRAKILDI — farklı imza/semantik (docstring: "Simpler than gap_closing"), blind consolidate regression yapardı. GLM eval bu konuda yanlıştı.
- **2.3 `_aggregate_claim_kind`:** `_pick_claim_kind(kinds: set)` ortak helper çıkarıldı (care_setting_review), iki `_aggregate_claim_kind` sibling olarak onu çağırıyor. claim_strategy MISSING_INPUTS check'ini korudu.
- **2.4 `_build_gap_closing_context`:** `@lru_cache(maxsize=None)` eklendi. PatientClaimContext frozen=True → hashable. 3× rebuild (misc + treatment + traceability) → 1 compute. conftest'e cache clear eklendi.
- **2.5 claim_strategy local dedup:** `_itemized_exclusion_metadata` artık `eligible_lines=` kwarg alıyor, 2× çağrı → 1×.

### Phase 3 — Kwarg standardizasyonu ✅
- `session_uplift_opportunities` (claim_procedure_addon_uplift) → `session_opportunities`. İç `detect_*` fonksiyonu eski adı koruyor (internal impl, churn değmez).
- `patient_report.py`'ye cross-detector dependency ordering comment'i eklendi.

### Satır tasarrufu
- fatura_inceleme.py: ~110 satır silindi (`_condition_matches` 68 + `_suffix_len` 5 + `_derive_payment_method_path` 18 + `_SCALAR_FIELDS` 22 - 1 import satırı).
- claim_strategy.py: `_aggregate_claim_kind` 14 → 4 satır.
- Net: ~120 satır silindi, ~25 satır eklendi (cache wrapper + comment + helper + test). Net ~95 satır azalma + memoization kazancı.

### Out of Scope olarak belgelendi (ayrı task)
- `_condition_matches` 5 ek kopya (`treatment_pricing`, `material_bundling`, `specialty_materials`, `dental_2_4_1`) — her birinin farklı uzantıları var, backward-compatible extension gerektirir.
