## Task: Fix Local Test Failures (Auth Bypass)

### Goal
Fix 24 local test failures (10 smoke + 14 API) caused by local `.env` credentials overriding the `BILUN_AUTH_OPTIONAL` test bypass.

### Subtasks
- [x] Clear `BILUN_AUTH_USERNAME`, `BILUN_AUTH_PASSWORD`, and `BILUN_SESSION_SECRET` from `os.environ` at the top of `tests/conftest.py`.
- [x] Verify that tests now pass locally.

### Out of Scope
- Modifying actual authentication logic or API endpoints.

### Out of Scope
- Code changes outside of tests and pipeline script fixes.

---

## Task: K3 — YB→Servis geçiş günü yatak koordinasyon katmanı (t_7dadf85b)

### Goal
Aynı takvim gününde hem 510090 (YB çıkış/transfer günü) hem 510010 (servis yatağı) yazılmasından doğan çift faturalamayı önleyen koordinasyon katmanı: recoverable-uplift yolunda YB son günü yatak LOS'undan düşülür, fiilen çift faturalanan 510010 satırı audit-exposure violation olarak işaretlenir.

### Approach (seçim + gerekçe)
Post-processing (yaklaşım 1), drop + flag ikisi birden:
- **Drop**: EK-2B 510090 "yemek, yatak, hasta vizit hizmetlerini kapsar" → YB gününde yatak zaten ödenmiştir; servis yatağı beklentisi o günü içeremez (fatura düzeltme, yanlış recoverable uplift üretilmez).
- **Flag**: 510010 satırı gerçekten YB çıkış gününe tarihlenmişse çift faturalama → audit-exposure violation (icu_bundled_leakage detector deseni, analyze_claim'e bağlanır).
- İki yol tetikleyici olarak ayrık (fiili satır vs beklenen gün) → çift hesaplama yok.

### Subtasks
- [x] Yeni prose modülü `src/bilun/domain/prose_rules/yatak_icu_overlap.py`:
  - ICU kod yardımcıları (icu_puani ile aynı normalizasyon)
  - `_collect_icu_last_days(claims, procedure_lines)` → YB kodlu claim'lerin discharge tarihleri
  - `detect_yatak_icu_overlap(...)` → YB son gününe tarihlenen 510010 satırları için audit-exposure violation
  - `reconcile_yatak_bed_days(yatak_opportunities, claims, procedure_lines)` → YB son günlerini bed_days'den düşer (paket ameliyat günü hariç tutma korunur), expected/recoverable yeniden hesaplanır
- [x] Billing wrapper `src/bilun/domain/billing/claim_yatak_icu_overlap.py` → `reconcile_yatak_icu_overlap(ctx, yatak_review)`
- [x] `patient_report.py`'ye post-processing olarak bağla (yatak_puani sonrası)
- [x] `billing/engine.py` analyze_claim'e detector'ı bağla (icu_bundled_leakage yanına)
- [x] `rule_registry.py`'ye `yatak_icu_overlap` kaydı ekle
- [x] Testler `tests/unit/domain/prose_rules/test_yatak_icu_overlap.py`:
  - (a) YB çıkış günü = servis giriş günü → tek yatak günü
  - (b) farklı günler → davranış değişmez
  - (c) paket ameliyat günü + YB kombinasyonu regresyonu
  - detector violation'ları + analyze_claim bağlantısı + wrapper
- [x] Verifikasyon: `ruff check src/` + hedefli pytest (yatak/icu/overlap/elkitabi)

### Review (sonuçlar)
- Yaklaşım: Post-processing (yaklaşım 1) — drop + flag birlikte. Drop: EK-2B 510090
  "yemek, yatak, vizit kapsar" → YB gününde yatak zaten ödenmiş; servis yatağı beklentisi o
  günü içeremez (recoverable-uplift düzeltmesi). Flag: fiilen 510010 satırı YB çıkış gününe
  tarihlenmişse audit-exposure violation (icu_bundled_leakage deseni, analyze_claim'de).
- `ruff check src/` → All checks passed.
- Hedefli pytest → 133 passed (17 yeni + yatak_puani/icu_puani/icu_bundled_leakage/
  elkitabi_tablo23/claim_integration/orchestrator_grand_total/wired_orphan_engines/
  rules_catalog/sut_coverage).
- Değişen dosyalar: prose_rules/yatak_icu_overlap.py (yeni), billing/claim_yatak_icu_overlap.py
  (yeni), billing/patient_report.py, billing/engine.py, sut/rule_registry.py,
  tests/unit/domain/prose_rules/test_yatak_icu_overlap.py (yeni).

### Out of Scope
- icu_puani/yatak_puani gün sayım içlerini değiştirmek (yaklaşım 2 ortak gün modeli)
- Servis→YB (ilk gün) geçiş ayna senaryosu — kenar durum olarak raporlanır
- Tam pytest suite (20+ dk) — sadece hedefli testler
