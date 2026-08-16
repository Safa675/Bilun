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
- [x] Kullanıcı onayı — uygulama bu plandan bağımsız olarak başlatılmaz

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

### Review
Uygulama 2026-08-15'te tamamlandı. En kritik bulgu: planın ve clarity planının §2.4.4 atfı corpus'a göre YANLIŞTI; ilave ücret mevzuatı §1.9 altında. Tüm kanıtlar dosya:satır bazında testlerle sabitlendi. Kalan takip işleri: (a) apiMessages kalan yüzeyleri (EK-3B :208-224 vd.), (b) `sutRegulatorySources.ts` EK regex'i, (c) ~20 prose dedektörüne clause_ref wiring'i (hazır `clause_linking` primitifleriyle), (d) committed i18n'daki eski atıfların temizlik geçişi ("§2.4" dipnotu, "§1.8.5(8)" ground label'ı).

## Task: Fix Sidebar & Tab Strip Intertwining + Resolve PR Conflicts

### Subtasks
- [x] Resolve git merge conflicts with `main` in `WorkspaceTabStrip.tsx` and `tasks/todo.md`
- [x] Fix `AppSidebar.tsx` layout effect: prevent cleanup from resetting `--shell-sidebar-width` to `0px` when the shell is active
- [x] Ensure `WorkspaceTabStrip` and page layout have robust, bulletproof sidebar offsets across all screen widths and collapsed states
- [x] Verify `npm run typecheck` (`tsc --noEmit`) passes with 0 errors
- [x] Verify `npm test` (`vitest`) passes with 100% test pass rate (232/232 passed)
- [x] Verify `npm run build` succeeds cleanly in 2.4s
- [x] Verify backend checks and parity pass with 0 errors
- [x] Commit and push changes to `experiment/workspace-shell` to update PR #72

## Task: 3 Görünümlü Modüler Hasta Çalışma Alanı (Three-View Patient Workspace)

### Goal
Hasta çalışma alanındaki bulguları tek karışık liste yerine 3 rol odaklı görünüme (1: Mevzuat Uyumluluk & Red Önleme, 2: Gelir Optimizasyonu & Hak Kazanım, 3: Gönderim Öncesi Evrak & Denetim) ayıran **frontend-only** mimariyi uygulamak; motor ataması mevcut `getFindingType` sınıflandırmasından (`frontend/src/lib/recommendedActions.ts`) türetilir, backend değişmez. Plan: `plans/patient_workspace_three_engine_modular_architecture_plan.md` (v2, revize edildi).

### Subtasks
- [x] Plan dokümanını incele ve onayla: `plans/patient_workspace_three_engine_modular_architecture_plan.md` (v2)
- [x] i18n: `messages/tr/billing.ts` + `en/billing.ts`'e `billing.views.*` anahtarlarını ekle; `patient.ts`'te kullanılmayan `billingGroups.compliance|opportunities|reference` anahtarlarını kaldır
- [x] `RecommendedActionsPanel`'e opsiyonel `findingFilter` ve `onOpenClause` prop'larını ekle (mevcut davranış/testler korunur)
- [x] Fıkra çekmecesi: #73'ün kanonik `SutClauseDrawer`'ı (clause_key tabanlı) eylem satırı atıflarına bağlanır
- [x] `views/PatientWorkspaceViews.tsx` — 3 sekmeli tab konteyneri (primitives/Tabs), badge + KPI tetikleyicileri
- [x] `views/ComplianceViewSection.tsx` — KPI şeridi + filter: compliance eylem listesi + Lab/Strategy/OptionalOverride/Materials/DrugIndication bölümleri
- [x] `views/RevenueViewSection.tsx` — KPI şeridi + filter: opportunity eylem listesi + Copay/Session/Blood/Material/Addon/CaptureGap/DrgAdequacy/Gazette/DrgUplift/CareSetting bölümleri
- [x] `views/AuditViewSection.tsx` — KPI şeridi + filter: informational eylem listesi + kontrol listesi + hazır onay kutuları (localStorage) + MEDULA playbook
- [x] `page.tsx` entegrasyonu: 3 eski `BillingReportGroup` bloğunu `PatientWorkspaceViews` ile değiştir; çekmece state'ini bağla; Overview/BillingSummary + seçim/vurgu sözleşmesini koru
- [x] Testler: `PatientWorkspaceViews.test.tsx` + `SutBillingReportSections.test.tsx`'e filter/onOpenClause ek durumları
- [x] Doğrulama: `npx tsc --noEmit`, `npx vitest run`, hedefli `pytest`; `http://localhost:3000/patient/SENTETIK-HASTA-0001` üzerinde sekme/KPI/çekmece/kalıcılık/vurgu kontrolü

### Out of Scope
- Backend/API/veri modeli değişikliği (yeni `engine` enum'u dahil).
- `yatak_puani` / `icu_puani` / `anestezi_puani` / `refakatci` / `yenidogan_yatak` için yeni detay bölümleri.
- Dosya hazır onayının sunucu tarafında kalıcılığı.
- `SutPatientWorkspace.tsx` değişikliği.
- SUT kural motorunun matematiksel hesaplama formülleri.

### Review (2026-08-16)
- **tsc**: `npx tsc --noEmit` temiz (0 hata).
- **vitest**: 47 dosya / 248 test geçti (4 yeni test dosyası + 4 yeni panel durumu dahil).
- **pytest**: `tests/unit/domain/billing` + `tests/unit/domain/claims` → 198 geçti (backend değişmedi).
- **Tarayıcı (headless Playwright, 16/16)**: 3 sekme (badge'ler 18/4/4 canlı veriden), KPI'lar ₺121.714,71 / ₺23.192,18, hazır onay localStorage kalıcılığı (yenileme sonrası korunuyor), fıkra çekmecesi gerçek fıkra metniyle açılıyor, Escape ile kapanıyor. Bilinen tek 404 `/api/frontend-config` (önceden var olan backend eksiği; `ConfigProvider` fallback'e düşüyor).
- **Kullanıcı geri bildirimi (uygulandı)**: "Finansal özet"teki eski master "Önerilen işlemler" tablosu (26 satır, tüm bulgular) kaldırıldı; her bulgu yalnızca ait olduğu görünümde filtrelenmiş olarak listeleniyor (sayfada tek eylem tablosu — doğrulandı). `BillingSummary` artık yalnızca KPI toplamları; ilgili iki test `RecommendedActionsPanel` üzerinden yeniden yazıldı.
- **Not**: Canlı backend'in bellek içi veriseti disktekine göre 2 ek copay satırı içeriyor (26 aksiyon); KPI'lar bu yüzden canlı veriden hesaplanıyor, sabit değil.
