# Task: Payment-Method Re-derivation + Cross-Detector Dependency Cleanup

### Goal
Payment-method classification'ı claim başına bir kez hesapla (5N–9N → N), duplikat fonksiyonları konsolide et, cross-detector kwargs'ı standardize et.

**Tam plan:** `plans/backend/payment-method-dedup-and-deps.md`

### Subtasks

#### Phase 1 — `resolve_payment_method` memoization (HIGH, en yüksek etki)
- [ ] 1.1 `as_of_date=None` cache key sorununu çöz (date.today() resolve stabilitesi)
- [ ] 1.2 `resolve_payment_method`'a `@lru_cache(maxsize=4096)` ekle (`payment_method.py:170`); `PaymentMethodResult` frozen=True doğrula
- [ ] 1.3 `check_payment_method_compliance` otomatik faydalanır (1.2 üzerinden) — ekstra cache yok
- [ ] 1.4 `resolve_payment_method.cache_clear()` test fixture'larına expose (conftest)
- [ ] 1.5 Benchmark: 10-line claim `compute_patient_billing_report` before/after
- [ ] 1.6 Test: cache hit rate >80% doğrula; mevcut payment-method testleri yeşil

#### Phase 2 — Duplikat fonksiyonları konsolide (MED)
- [ ] 2.1 `_derive_payment_method_path`: `fatura_inceleme.py:370` kopyasını sil → `gap_closing.py:236`'dan import
- [ ] 2.2 `fatura_inceleme._condition_matches` (~57 satır) → `gap_closing`'den import (`payment_method.py:415` precedent)
- [ ] 2.3 `_aggregate_claim_kind` 2 kopyayı birleştir (`care_setting_review.py:45` + `claim_strategy.py:188`)
- [ ] 2.4 `_build_gap_closing_context` 3× rebuild'i önle (`engine.py:172,173,184` → local var)
- [ ] 2.5 `claim_strategy.py:369-370` `lines_for_legal_itemized_alternative` 2× çağrıyı tek çağrıya indir
- [ ] 2.6 Test: `test_claim_strategy_*`, `test_gap_closing_*`, `test_fatura_inceleme_*`, `test_payment_method_*` yeşil

#### Phase 3 — Cross-detector kwarg standardizasyonu (LOW)
- [ ] 3.1 `session_opportunities` vs `session_uplift_opportunities` — bir isim seç, her iki detectörde uygula
- [ ] 3.2 `patient_report.py:107-111,128-134` cross-detector sıra bağımlılığını comment ile belgele
- [ ] 3.3 NO-OP: findings dict eklenmedi (araştırma: sadece 3 kwarg/2 detectör, payoff yok — belgelendi)

### Out of Scope
- `report_totals.py` exactness fusion — kanıtlanmış keep-as-is (merkezileştirilmiş, data-driven spec)
- JSON condition-on-derived-field pattern — kanıtlanmış keep-as-is (honest-skip güvenli, regression test'li)
- `engine.py:analyze_claim`'deki 22 `check_*_for_context(ctx)` — hepsi ctx-only, cross-detector veri taşımıyor
- Findings dict — AŞIRI KILL (3 kwarg için yeni abstraction)
- Payment-method'ın kendisini yeniden yazma (sadece cache ekle)
- `_condition_matches` 5 ek kopya (treatment_pricing, material_bundling, specialty_materials, dental_2_4_1) — farklı uzantıları var, ayrı task

### Review — Tamamlandı ✅ (2026-07-13)
- **Phase 1:** `resolve_payment_method` wrapper + `_resolve_payment_method_cached` (`@lru_cache(maxsize=None)`). Benchmark: 5N→N, 80% hit rate.
- **Phase 2:** fatura_inceleme `_condition_matches` + `_derive_payment_method_path` gap_closing'den import edildi (~110 satır silindi); `_pick_claim_kind` ortak helper; `_build_gap_closing_context` `@lru_cache`; claim_strategy 2× çağrı → 1×.
- **Phase 3:** `session_opportunities` standardize + wiring comment.
- **Test:** 1415/1415 prose_rules+billing yeşil; 2165 unit test 0 failure (1 API failure environment issue — DuckDB lock).
- **Net:** ~95 satır azalma + memoization 5× compute azalması. Tam plan: `plans/backend/payment-method-dedup-and-deps.md`
