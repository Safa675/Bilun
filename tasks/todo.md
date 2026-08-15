## Task: Kanonik SUT Fıkra Bağlama ve Uçtan Uca Yapısal Mevzuat Mimarisi Denetimi

### Goal
Codebase genelindeki tüm manuel, şablon bazlı veya kural veritabanına doğrudan bağlanmamış noktaları tespit edip, her fatura iddiasını (claim/finding) doğrudan Resmi Gazete SUT fıkrasına bağlayacak kapsamlı mimari planı hazırlamak.

### Subtasks
- [x] Backend Faturalama ve Katılım Payı / İlave Ücret motorunu denetle (`copay_line_waivers.py`, `line_decomposition.py`, `claim_copay.py`)
- [x] Backend Prose kuralları ve serbest metin üreten şablonları denetle (`prose_rules/`, `rules/`, `sut/`)
- [x] Frontend heuristic, regex ayrıştırıcı ve hardcoded SUT eşleştirmelerini denetle (`billingReportFields.ts`, `apiMessages.ts`, `recommendedActions.ts`)
- [x] Detaylı mimari planı `plans/sut_canonical_clause_linking_architecture_plan.md` dosyasına kaydet
- [x] Kullanıcıya bulguları ve geçiş yol haritasını sun

### Review
Denetim 3 paralel araştırma ajanıyla tamamlandı. Codebase'deki her bir manuel/şablon nokta dosya:satır bazında haritalandı. `plans/sut_canonical_clause_linking_architecture_plan.md` planı oluşturuldu.

## Task: Kanonik SUT Fıkra Bağlama Planı Revizyonu (Track E hizalama + çakışma çözümü)

### Goal
Değerlendirme sonucunda tespit edilen hataları gideren revize mimari planı `plans/sut_canonical_clause_linking_architecture_plan.md` dosyasına yazmak.

### Subtasks
- [x] Plan iddialarını 4 paralel denetim ajanıyla dosya:satır bazında doğrula
- [x] §2.4.4 entegrasyon noktalarını doğrula (`line_decomposition.py`, `optimization/surcharge.py`)
- [x] Revize planı yaz (clause_key sözleşmesi, mevcut altyapının yeniden kullanımı, Aşama 0 çakışma çözümü, düzeltilmiş mevcut durum analizi)
- [ ] Kullanıcı onayı — uygulama bu plandan bağımsız olarak başlatılmaz

### Out of Scope
- Kod değişikliği yok; bu görev yalnızca plan revizyonudur.
- Devam eden (uncommitted) copay UI çalışmasının refactor'ü — revize planın Aşama 0/1 kapsamındadır.

### Review
Revizyon 2026-08-15: plan v2 yazıldı. Kullanıcı onayladı → uygulama görevine geçildi.

## Task: Kanonik SUT Fıkra Bağlama — Uygulama (plan v2)

### Goal
`plans/sut_canonical_clause_linking_architecture_plan.md` v2'yi uygulamak: Aşama 1 (backend billing), Aşama 2 (prose provenance + manifest join), Aşama 3 (frontend kesover; apiMessages yüzey-yüzey, ilk yüzey §2.2), Aşama 4 (doğrulama).

### Subtasks
- [x] Ortak sözleşme: `src/bilun/domain/sut/clause_reference.py` (clause_key tabanlı, coord→key çözümleme `rules_catalog.get_clause()` üzerinden + belirsiz koordinatlar için section-heading fallback)
- [x] Aşama 1: `line_decomposition.py` ilaç yasağı + `ilave_ucret_status`; kanser/acil muafiyeti yapısal muafiyet çıktılarından — **§2.4.4 değil §1.9** (corpus doğrulaması: `1.9.1` ilaç yasağı kapsamı + 5510 md.73, `1.9.3.a` acil, `1.9.3.ç` kanser; bkz. plan Revizyon Notu 5)
- [x] Aşama 1: `copay_line_waivers.py` WaiverResult `clause_ref` + `drug_waiver`; `claim_copay.py` yapısal rate_corrections + kanser/acil context
- [x] Aşama 1: `billing_actions.py` clause_ref + gerekçe-özel aksiyon satırları (EK-4/D, acil, iş kazası, yeşil kart) + `finding_type` (billing_strategy kind parity dahil) + message_code passthrough
- [x] Aşama 1: `api/schemas.py` ClauseReferenceResponse (additive alanlar dict geçişinden zaten akıyordu)
- [x] Aşama 2: ProseRuleTrace `source_type`/`clause_ref` + provenance düzeltmeleri (tablo_15→el_kitabi 16/16, elkitabi_diagnosis_coding, lab_capture_gap→rehber, algoritma_2_09 + 2918 SK md.98, transplant→p609080_package_scope)
- [x] Aşama 2: manifest `clause_traces` join (`clause_linking.py`, 47 manifest, material_bundling emission noktasına bağlı)
- [x] Aşama 3: `resolveCopayIlaveStatus` → saf backend render (heuristikler silindi); annex etiketleri `clause_ref.annex`'ten; `finding_type` setleri silindi; `SutClauseDrawer.tsx` yeni bileşen + tıklanabilir atıflar
- [x] Aşama 3: apiMessages ilk yüzey (§2.2 kümesi, 9 message_code) — backend üreticiler + `translateStructuredApiMessage` + tüm row-taşıyan tüketiciler kesover (BillingSummary dahil; `PaymentMethodCompliance` structured alanları ile drg_unbundling ihlalleri de kod taşıyor)
- [x] Aşama 4: doğrulama — backend migration yüzeyleri 1641 test yeşil; frontend `npx tsc --noEmit` + 223 vitest + `npm run build` yeşil; full suite'te 25 çevresel hata (401 auth-not-configured + başka bir sürecin tuttuğu DuckDB lock) migration yüzeylerinin DIŞINDA; ruff: değişen/yeni dosyalarda 0 hata

### Out of Scope
- apiMessages'ın kalan yüzeyleri (plan gereği yüzey-yüzey, ayrı PR'lar; bu görevde ilk yüzey tamam).
- `sutRegulatorySources.ts` EK regex'i — backend rule_source yapılaşmasını bekler (Aşama 2 follow-up).
- Commit/push/PR — kullanıcı kararı.

### Review
Uygulama 2026-08-15'te tamamlandı. En kritik bulgu: planın ve clarity planının §2.4.4 atfı corpus'a göre YANLIŞTI; ilave ücret mevzuatı §1.9 altında. Tüm kanıtlar dosya:satır bazında testlerle sabitlendi. Kalan takip işleri: (a) apiMessages kalan yüzeyleri (EK-3B :208-224 vd.), (b) `sutRegulatorySources.ts` EK regex'i, (c) ~20 prose dedektörüne clause_ref wiring'i (hazır `clause_linking` primitifleriyle), (d) committed i18n'daki eski atıfların temizlik geçişi ("§2.4" dipnotu, "§1.8.5(8)" ground label'ı).

## Task: Aşama 3 ilk yüzey — §2.2 billing prose + material copay rate structured message contract

### Goal
Backend §2.2 üreticilerine `message_code` + `message_params` ekle (detail byte-identical kalır), frontend'de `translateStructuredApiMessage` ile dokuz §2.2 regex ayrıştırıcısını sil ve row-taşıyan tüketicileri kesover et.

### Subtasks
- [x] Backend: `claim_strategy.py` — 6 claim-level detail + compliance_violation row'larına message_code/message_params (+ doğal coordinate varsa clause_ref)
- [x] Backend: `claim_copay.py` — yalnız material rate informational row'una material_copay_rate kodu
- [x] Frontend: `apiMessages.ts` — `translateStructuredApiMessage` ekle, dokuz §2.2 matcher'ı sil
- [x] Frontend: `SutBillingReportSections.tsx` — CopaySection insight row, BillingStrategySection, OptionalOverrideSection kesover
- [x] Testler: `test_claim_strategy_sut.py`, `test_claim_copay_cancer_context.py`, `apiMessages.test.ts` güncelle
- [x] Doğrulama: touched backend pytest dosyaları + `npx vitest run` + `npx tsc --noEmit`

### Out of Scope
- `prose_rules/types.py` (PaymentMethodCompliance frozen dataclass — eşzamanlı iş; structured alanlar row seviyesinde claim_strategy'de eklenir)
- `drg_unbundling.py` row'ları (dosya sahipliği dışında; detail passthrough devam eder)
- `recommendedActions.ts` (read-only; bare-string tüketici olarak kalır)
- Diğer apiMessages yüzeyleri (EK-3B, validation, yatak, honesty…)

### Review
Tamamlandı (2026-08-15): dokuz message_code üretici tarafında detail byte-identical kalacak şekilde eklendi; frontend regex kümesi silindi, row-taşıyan dört render noktası `translateStructuredApiMessage`'a kesover edildi. Doğrulama: touched pytest dosyaları 16/16, ek güvenlik ağı billing+prose_rules 1574/1575 (tek kalıntı failure eşzamanlı işe ait pre-existing `test_clause_linking` beklentisi), vitest 223/223, tsc temiz.

Not (kapanış, 2026-08-15): Out of Scope'taki üç madde orchestrator tarafından TAMAMLANDI — `PaymentMethodCompliance` structured alanları (types.py + payment_method.py), drg_unbundling ihlal row'ları ve recommendedActions/BillingSummary passthrough. Kalıntı `test_clause_linking` failure'ı pre-existing değildi (section-heading fallback ile çözülen "3.1.2" beklentisi); test yeni davranışa güncellendi. Yüzey tam kapalı.
