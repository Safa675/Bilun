## Task: K2 — Kan ürünleri tier'ları — CONFIG katmanı (kanban t_f9ed6c00)

### Goal
4 kan ürünü tier'ı (0.36/0.24/0.20/0.28) × 8 kod (705371, 705430, 705440, 705372,
705373, 705441, 705442, 705443) yapısal olarak `data/gazette/prose_rules/
session_pricing_2_2_2_B.json` → `special_codes.blood_component_partial_bill`
içine işlensin; compile + check + ruff yeşil; motorun genelleştirilmiş
`blood_component_billable_fraction()`'ının okuyacağı `fractions` haritası net.

### Yol seçimi: Path B (JSON'a elle ekle) — gerekçe
- `_payload_preserving_key_order` (scripts/sut/compile_rules.py:109-124),
  `_write_rule_set_for_target` (167-173) ile compile, committed JSON'daki
  üretilmeyen top-level anahtarları (special_codes dahil) korur.
- Tarihsel kanıt: special_codes 8406b8f'den beri var, 2 regenerasyon (13ca112,
  757cae1) sonrası da duruyor.
- Path A (YAML) shared `_compile_fresh`'i değiştirmeyi + var olmayan bir YAML
  special_codes konvansiyonu icat etmeyi gerektirir — tüm fresh target'ları
  riske atar, over-engineering.
- Ampirik test: compile sonrası JSON'da fractions DURUYOR olmalı.

### Subtasks
- [x] `session_pricing_2_2_2_B.json` → `special_codes.blood_component_partial_bill`
      içine `fractions` dict'i ekle (8 kod → fraction; 0.36/0.24/0.20/0.28);
      `codes[]` + `billable_point_fraction` backward-compat için koru; note güncelle.
- [x] Lock kontrolü (`fuser /tmp/bilun_compile_rules_check.lock`); ghost varsa öldür.
- [x] `.venv/bin/python scripts/sut/compile_rules.py` (write) — background ~8-9 dk.
- [x] Compile sonrası doğrula: JSON'da special_codes + fractions DURUYOR;
      `git diff --stat` sadece hedeflenen dosya (format gürültüsü yok).
- [x] `.venv/bin/python scripts/sut/compile_rules.py --check` (byte-identical).
- [x] `.venv/bin/ruff check scripts/`.
- [x] İlgili testler: test_session_pricing_json_driven.py, test_prose_rules.py
      (blood fraction), test_blood_uplift.py — regresyon yok.
- [x] `git status --short` kontrolü (lessons.md kuralı), commit wt/p71-k2'ye (push YOK).
- [x] kanban raporu (yol A/B + şema + compile/check çıktısı + diff stat) + block review-required.

### Out of Scope

## Task: K2-MOTOR — blood_component_billable_fraction genelleştirme + ISBT 128 detector (kanban t_3d61b289)

### Goal
`blood_component_billable_fraction()` 8 kod × 4 tier (0.36/0.24/0.20/0.28) doğru
döndürsün (fractions map yetkili, legacy fallback korunur) ve SUT §4.6 ISBT 128
barkod zorunluluğu için analyze_claim'e bağlı bir detector + registry kaydı eklensin.
Tüm mevcut testler yeşil, ruff temiz.

### Subtasks
- [x] G1: `session_pricing.py:504-511` `blood_component_billable_fraction()`
      genelleştir — önce `fractions` dict, yoksa legacy `codes[]`+`billable_point_fraction`.
      normalize_procedure_code (P-prefix) korunur. 3 tüketici (session_pricing:398,
      drg_unbundling:192, blood_uplift:38) otomatik doğru olur — değiştirilmez.
- [x] G2a: `models.py` → `ProcedureClaimLine`'a opsiyonel `isbt128_barcode: str = ""` ekle
      (MEDULA ISBT 128 kayıt alanı; veri modeli izin verdiği ölçüde okunur).
- [x] G2b: `row_parsers.py:248` yanına `isbt128_barcode=parse_text(row, "isbt128_barcode")` ekle.
- [x] G2c: `blood_component_isbt128.py` detector yaz (icu_bundled_leakage deseni):
      kan bileşeni kodu (8 kod) geçen prosedür satırında barkod boşsa/format dışıysa
      violation; lenient ISBT-128 format kontrolü (`=`/`A` öneki + 13-16 alfanümerik çekirdek).
- [x] G2d: `engine.py` analyze_claim'e 14.7 olarak bağla (icu_bundled_leakage yanı).
- [x] G2e: `rule_registry.py`'ye `blood_component_isbt128_barcode` kaydı ekle
      (icu_bundled_leakage kaydının deseninde, 745 satır sonrası).
- [x] T1: `test_blood_component_partial_bill.py` — 8 kod × 4 tier, legacy fallback
      (fractions'sız config mock), fractions önceliği, P-prefix, bilinmeyen kod → None.
- [x] T2: `test_blood_component_isbt128.py` — barkodlu → yok, barkodsuz → missing,
      format bozuk → invalid_format, kan dışı satır → etkilenmez, engine wiring, registry.
- [x] Verifikasyon: ruff + hedef test dosyaları + tam test suite (kırılan olmasın).

### Review (2026-08-12)
- ruff check src/ + yeni test dosyaları → All checks passed.
- Yeni testler: 20 passed (fraction tier + legacy fallback + detector + engine wiring + registry).
- Hedef/komşu testler: 143 passed (session_pricing_json_driven, blood_uplift, blood_uplift_wiring, icu_bundled_leakage, prose_rules, drg_unbundling, elkitabi_tablo23/15/30/31/32/35, sut registry).
- Tam suite: 2485 passed, 9 skipped, 0 failed (43:53).
- `git diff --stat`: 6 dosya değişti +97/−1, 3 yeni dosya (saf ekleme, format gürültüsü yok).
- Kapsam dışı: dataset_builder/medula feed'in isbt128_barcode alanını doldurması (veri katmanı işi; alan doldurulmadığı sürece simüle verideki tüm kan bileşeni satırları missing-barkod ihlali üretir — bu verinin dürüst durumu).

### Out of Scope
- data agent'ın config katmanı (cab21d4 zaten cherry-pick edildi — JSON'a dokunulmaz).
- patient_report recoverable-uplift yolu (brief: ISBT eksikliği uplift değil, uyum/audit).
- dataset_builder / medula feed'in barkod alanını doldurması (veri katmanı işi — raporda not).

---

## Task: K2 — Kan ürünleri tier'ları — CONFIG katmanı (kanban t_f9ed6c00)

### Goal
4 kan ürünü tier'ı (0.36/0.24/0.20/0.28) × 8 kod (705371, 705430, 705440, 705372,
705373, 705441, 705442, 705443) yapısal olarak `data/gazette/prose_rules/
session_pricing_2_2_2_B.json` → `special_codes.blood_component_partial_bill`
içine işlensin; compile + check + ruff yeşil; motorun genelleştirilmiş
`blood_component_billable_fraction()`'ının okuyacağı `fractions` haritası net.

### Yol seçimi: Path B (JSON'a elle ekle) — gerekçe
- `_payload_preserving_key_order` (scripts/sut/compile_rules.py:109-124),
  `_write_rule_set_for_target` (167-173) ile compile, committed JSON'daki
  üretilmeyen top-level anahtarları (special_codes dahil) korur.
- Tarihsel kanıt: special_codes 8406b8f'den beri var, 2 regenerasyon (13ca112,
  757cae1) sonrası da duruyor.
- Path A (YAML) shared `_compile_fresh`'i değiştirmeyi + var olmayan bir YAML
  special_codes konvansiyonu icat etmeyi gerektirir — tüm fresh target'ları
  riske atar, over-engineering.
- Ampirik test: compile sonrası JSON'da fractions DURUYOR olmalı.

### Subtasks
- [x] `session_pricing_2_2_2_B.json` → `special_codes.blood_component_partial_bill`
      içine `fractions` dict'i ekle (8 kod → fraction; 0.36/0.24/0.20/0.28);
      `codes[]` + `billable_point_fraction` backward-compat için koru; note güncelle.
- [x] Lock kontrolü (`fuser /tmp/bilun_compile_rules_check.lock`); ghost varsa öldür.
- [x] `.venv/bin/python scripts/sut/compile_rules.py` (write) — background ~8-9 dk.
- [x] Compile sonrası doğrula: JSON'da special_codes + fractions DURUYOR;
      `git diff --stat` sadece hedeflenen dosya (format gürültüsü yok).
- [x] `.venv/bin/python scripts/sut/compile_rules.py --check` (byte-identical).
- [x] `.venv/bin/ruff check scripts/`.
- [x] İlgili testler: test_session_pricing_json_driven.py, test_prose_rules.py
      (blood fraction), test_blood_uplift.py — regresyon yok.
- [x] `git status --short` kontrolü (lessons.md kuralı), commit wt/p71-k2'ye (push YOK).
- [x] kanban raporu (yol A/B + şema + compile/check çıktısı + diff stat) + block review-required.

### Out of Scope
- Push / PR açma (branch'e commit, push yok).

### Out of Scope
- Motor kodunun genelleştirilmesi (src/bilun/domain/prose_rules/session_pricing.py)
  — Reimbursement task'ı; ben sadece config/veri katmanını işliyorum.
- ISBT 128 barkod format doğrulaması — motor tarafı.
- treatment_pricing_2_4.json / drug_indication_prose.json düzenlemesi
  (corroborating prose, session_pricing motoru okumuyor).
- Push / PR açma (branch'e commit, push yok).
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
