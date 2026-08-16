# Plan: Üç Görünümlü Modüler Hasta Çalışma Alanı Mimarisi (3-View Patient Workspace Architecture Plan) — Revizyon 2

**Date:** 2026-08-16  
**Status:** Architecture Proposal & Implementation Plan (v2 — Gözden Geçirilmiş, Onaylı)  
**Revision:** v2 (v1 incelemesinde tespit edilen hatalar düzeltildi; kod tabanı doğrulamalı)  
**Target:** `frontend/src/app/patient/[id]/page.tsx`, `frontend/src/components/patient/views/` (yeni), `frontend/src/components/sut/SutClauseDrawer.tsx` (yeni), `frontend/src/components/patient/SutBillingReportSections.tsx` (küçük, geriye uyumlu ekleme), `frontend/src/messages/{tr,en}/billing.ts` ve `patient.ts`

---

## 0. Revizyon Notu (v1 → v2)

v1 planının kod tabanı doğrulamasında bulunan ve v2'de düzeltilen hatalar:

| # | v1 İddiası | Gerçek Durum (kanıt) | v2 Kararı |
|---|---|---|---|
| 1 | Backend'de `BillingActionItem` dataclass'ı var | Yok. Eylem satırları düz dict; üretici `_action_row` (`src/bilun/domain/billing/billing_actions.py:42-76`), rapor modeli `BillingActionReport` (`src/bilun/domain/billing/types.py:743`) | Backend'e **dokunulmaz**. Sınıflandırma mevcut `surface` alanı üzerinden frontend'de yapılır |
| 2 | `FindingType` backend alanı | Frontend TS tipi: `frontend/src/lib/recommendedActions.ts:12` (`"compliance" \| "opportunity" \| "informational"`) | Motor atamasının tek doğruluk kaynağı `getFindingType` (`recommendedActions.ts:43-63`) olur |
| 3 | `SutClauseDrawer.tsx` mevcut, entegre edilecek | Mevcut değil (frontend'de hiç `Drawer` bileşeni yok) | **Yeni bileşen** olarak inşa edilir; veri kaynağı `getSectionClauses` (`frontend/src/lib/api/sut.ts:736-749`, `/api/rules/sections/clauses`), fıkra metni `RuleClause.text_tr` (`sut.ts:487`) |
| 4 | "26 mevcut kural bulgusu" | SENTETIK-HASTA-0001 için `action_count = 24` (hesaplanarak doğrulandı) | Sayılar sabit yazılmaz; KPI'lar rapordan canlı hesaplanır |
| 5 | "4 Gelir Fırsatı" | 0001 için opportunity sınıfında 2 satır (2 yatak puanı) | KPI kartları canlı veriden sayar; mockup'taki örnek sayılar "örnek" olarak etiketlenir |
| 6 | "3 Engine" isimlendirmesi | Backend'de zaten "motor/engine" terminolojisi var (`src/bilun/domain/billing/engine.py`, rule-database UI'ında "engine" = kural seti: `ProseInventoryPanel.tsx`) | Kod tarafında **"view"** terimi kullanılır (çakışma yok); kullanıcıya dönük Türkçe adlar korunur |
| 7 | Bulgular `SutPatientWorkspace.tsx` içinde tek tabloda | Tek tablo `RecommendedActionsPanel` (`SutBillingReportSections.tsx:159-271`), ama bölüm kompozisyonu `page.tsx:630-704`'te; `SutPatientWorkspace.tsx` yalnız hasta başlığı/finansal özet/klinik anlık görüntü render ediyor | Entegrasyon noktası `page.tsx`'tir; `SutPatientWorkspace.tsx` hedef listesinden çıkarıldı |
| 8 | Mevcut sınıflandırma yok sayılıyor | `getFindingType` zaten compliance/opportunity/informational ayrımını `surface` setleriyle yapıyor (`recommendedActions.ts:14-37`) | Yeni backend enum'u **eklenmez** (çift doğruluk kaynağı riski — `tasks/lessons.md` "iki envanter kayması" dersi). Görünümler bu mevcut ayrımı tüketir |

---

## 1. Yönetici Özeti ve Mimari Motivasyon

### Mevcut Durumun Sınırları
Hasta çalışma alanında (`/patient/[id]` → `frontend/src/app/patient/[id]/page.tsx`) tüm bulgular tek bir "Önerilen İşlemler" tablosunda (`RecommendedActionsPanel`, `SutBillingReportSections.tsx:159-271`) ve üç genel grupta (uyumluluk / fırsatlar / referans, `page.tsx:630-704`) sunulur:

1. **Rol Odaklılığını Dağıtıyor:** Fatura kesintisini engellemek isteyen *Uyumluluk Uzmanı*, ek gelir arayan *Gelir Yöneticisi* ve SGK klasörünü hazırlayan *Tıbbi Arşiv Memuru* aynı karışık listeyi taramak zorunda kalıyor.
2. **Kavram Kargaşası Yaratıyor:** "Ön Onay Eksikliği (₺129.746,40 Risk)" ile "Standart Yatak Puanı (₺4.224,84 Ek Gelir)" aynı tabloda alt alta duruyor.
3. **Grup Tutarsızlığı:** Mevcut grup atamaları `getFindingType` sınıflandırmasıyla tutarsız (örn. `MaterialsPreCheckSection` "fırsatlar" grubunda ama `surface: "materials"` → compliance; `CareSettingReviewSection` "referans" grubunda ama surface → opportunity; `CopayOptimizationSection` "uyumluluk" grubunda ama surface → opportunity).

### Çözüm: 3 Rol Görünümü (3-View Architecture, frontend-only)
Çalışma alanı 3 rol odaklı **görünüme** ayrıştırılır. Motor atamasının tek doğruluk kaynağı mevcut `getFindingType` sınıflandırmasıdır (`frontend/src/lib/recommendedActions.ts:43-63`). Backend, API şeması veya veri modeli **değişmez**.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ 👤 HASTA: SENTETIK-HASTA-0001  ·  Finansal Özet (değişmez)                    │
├─────────────────────────────────────────────────────────────────────────────┤
│ [ 🛑 Uyumluluk & Red Önleme ] [ 🟢 Gelir Optimizasyonu ] [ 📋 Evrak Denetimi ]│
│   ₺121.714,71 Risk · 18          ₺23.192,18 Ek Gelir · 2     4 Kontrol · 0 Hata│
├─────────────────────────────────────────────────────────────────────────────┤
│ Aktif görünümün KPI kartları + o görünüme ait filtrelenmiş eylem listesi       │
│ + o görünüme ait detay bölümleri (mevcut SutBillingReportSections bileşenleri) │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Neden frontend-only:** Eylem satırları zaten `surface` alanı taşıyor (`billing_actions.py:60-76`), frontend zaten `FindingType` sınıflandırmasını yapıyor ve chip'lerini render ediyor (`SutBillingReportSections.tsx:198,230-235`). Backend'e yeni bir `engine` enum'u eklemek, iki envanterin kayması riskini doğurur (ders: `tasks/lessons.md` — iki envanter kayması). Görünümler saf sunum katmanıdır.

---

## 2. Üç Görünümün Detaylı Tanımı ve Bölüm Haritası

### 🛑 Görünüm 1: Mevzuat Uyumluluk & Red Önleme (ComplianceView)
- **Kullanıcı Profili:** Faturalama Denetmeni, Başhekimlik Mevzuat Ekibi.
- **Ana Görevi:** Fatura MEDULA'ya gönderilmeden önce SGK'nın keseceği hatalı kalemleri ayıklamak.
- **KPI Kartları:** Toplam Denetim Riski (`audit_exposure_try`), Uyumluluk Bulgu Sayısı, Faturalanan-Risk Tutarı.
- **Bölüm Haritası (surface → bölüm):**
  - `lab` → `LabOptimizationSection` (`SutBillingReportSections.tsx:459`)
  - `billing_strategy` (compliance türleri) → `BillingStrategySection` (`:747`) + `OptionalOverrideSection`
  - `materials` → `MaterialsPreCheckSection` (`:2161`) — **grup düzeltmesi**: "fırsatlar"dan buraya taşınır
  - `drug_indication` → `DrugIndicationReviewSection` — **grup düzeltmesi**: "referans"tan buraya taşınır
- **İçerdiği Kural Modülleri (örnek, veriden doğrulandı):** EK-3C-1 ön onay (OP1266, ₺129.746,40), EK-3C-2 MIAT, EK-3B-1 mükerrer malzeme (₺71.286,96 / ₺3.545,95), zorunlu paket yöntemi (608550 `compliance_violation`), §3.3 özel servis kısıtları, §4.2 ilaç endikasyonu.

### 🟢 Görünüm 2: Gelir Optimizasyonu & Hak Kazanım (RevenueView)
- **Kullanıcı Profili:** Gelir Döngüsü Müdürü (RCM), Fatura Servis Şefi.
- **Ana Görevi:** Yasal olarak hak edilen ama faturaya yansıtılmayan gelirleri ortaya çıkarmak.
- **KPI Kartları:** Kurtarılabilir SGK Artışı (`sgk_uplift_try` / `total_recoverable_try`), Gelir Fırsatı Sayısı.
- **Bölüm Haritası:**
  - `copay` → `CopayOptimizationSection` (`:518`) — **grup düzeltmesi**: "uyumluluk"tan buraya taşınır (backend notu: "compliance correction, not repricing" olsa da frontend sınıflandırması ve v1 planının Motor 2 tanımı opportunity yönündedir; tek doğruluk kaynağı `getFindingType`)
  - `session_uplift` → `SessionUpliftSection`; `blood_uplift` → `BloodComponentUpliftSection`; `material_uplift` → `MaterialUpliftSection`; `procedure_addon_uplift` → `ProcedureAddonUpliftSection`; `procedure_capture_gap` → `ProcedureCaptureGapSection`; `drg_package_adequacy` → `DrgPackageAdequacyReviewSection`; `gazette_repricing` → `GazetteRepricingSection`; `drg_uplift` → `DrgUpliftSection`; `care_setting_review` → `CareSettingReviewSection` — **grup düzeltmesi**: "referans"tan buraya taşınır
- **Not:** `yatak_puani`/`icu_puani` vb. yüzeylerin detay bölümleri yok (FE domain tipinde alan yok: `domains/sut.ts`); bu kalemlerin eylemleri Görünüm 2'nin filtrelenmiş eylem listesinde görünmeye devam eder. Detay bölümü eklemek **out of scope** (v3 adayı).

### 📋 Görünüm 3: Gönderim Öncesi Evrak & İnceleme (AuditView)
- **Kullanıcı Profili:** Arşiv Görevlisi, Dosya Hazırlama ve İnceleme Memuru.
- **Ana Görevi:** SGK Fatura İnceleme Komisyonu'nun aradığı kanuni evrakları doğrulamak.
- **KPI Kartları:** Kontrol Maddesi Sayısı (`claim_submission_checklist_count`), Hata Sayısı (`error_count`), Hazır Dosya Sayısı (kullanıcı işaretleri).
- **Bölüm Haritası:**
  - `claim_checklist` → `ClaimSubmissionChecklistSection` + **dosya hazır onay mekanizması** (yeni; aşağıda §5)
  - `medula_playbook` → `MedulaRejectionPlaybookSection`
- **Kriterler (veriden doğrulandı):** ORTAK-17 (EK-2/C ameliyat notu), ORTAK-21 (patoloji), ORTAK-27 (epikriz/klinik seyir/barkod), ORTOPEDİ-6 (pre/post-op grafi) — `fatura_inceleme_ref` değerleri birebir veride mevcut.

---

## 3. Bileşen Mimarisi

### Yeni Dosyalar — `frontend/src/components/patient/views/`
1. `PatientWorkspaceViews.tsx` — Radix tab konteyneri (mevcut `components/primitives/Tabs.tsx` kullanılır); 3 tetikleyici, her biri `leading` ikonu + count badge + KPI değeri ile; içerik alanı.
2. `ComplianceViewSection.tsx` — Görünüm 1: KPI şeridi (`KpiCard`, `components/tabs/sut/shared.tsx:115`) + `RecommendedActionsPanel` (filter: `"compliance"`) + bölüm listesi.
3. `RevenueViewSection.tsx` — Görünüm 2: KPI şeridi + `RecommendedActionsPanel` (filter: `"opportunity"`) + bölüm listesi.
4. `AuditViewSection.tsx` — Görünüm 3: KPI şeridi + `RecommendedActionsPanel` (filter: `"informational"`) + kontrol listesi (hazır onay kutuları) + MEDULA playbook.

### Değişecek Dosyalar (geriye uyumlu, küçük dokunuşlar)
5. `frontend/src/components/patient/SutBillingReportSections.tsx`:
   - `RecommendedActionsPanel`'e iki **opsiyonel** prop: `findingFilter?: FindingType` (yoksa tüm satırlar — mevcut davranış korunur) ve `onOpenClause?: (sectionId: string) => void` (verilirse fıkra hücresi buton olur, verilmezse mevcut metin).
   - Mevcut testler (`SutBillingReportSections.test.tsx:201,564,609`) bu prop'ları geçmediği için davranışları değişmez.
6. `frontend/src/app/patient/[id]/page.tsx`:
   - "Overview" grubu (`BillingSummary`) **korunur** ama yalnızca KPI toplamları olarak: master eylem listesi (`RecommendedActionsPanel`) kullanıcı geri bildirimiyle kaldırıldı — her bulgu artık yalnızca ait olduğu görünümde, filtrelenmiş olarak listelenir. Satır seçimi ↔ fatura satırı vurgusu sözleşmesi (`page.tsx:434-449`, `SutBillingReportSections.tsx:196-209`) görünüm içi listeler üzerinden aynen çalışır.
   - `compliance` / `opportunities` / `reference` üç `BillingReportGroup` bloğu (`page.tsx:641-704`) kaldırılır; yerine `<PatientWorkspaceViews … />` gelir. `SutOptimizationSection` ve footer değişmez.
   - Fıkra çekmecesi state'i (açık bölüm id) sayfa düzeyinde tutulur ve görünümlere iletilir.

### Yeni Bileşen — `frontend/src/components/sut/SutClauseDrawer.tsx`
7. Sağdan açılan çekmece: açılışta `getSectionClauses({ section_id })` çağrısı (`frontend/src/lib/api/sut.ts:736-749`); fıkra listesi (`RuleClause.clause_coordinate`, `text_tr` — `sut.ts:475-503`) render edilir.
   - `section_id` formatları: SUT referansları (`3.1.2`, `2.2.2`), EK referansları (`EK-3C-1`), Fatura İnceleme referansları (`ORTAK-21`). API bunları çözemezse zarif boş durum + "Kural Veritabanına Git" bağlantısı (mevcut kural veritabanı UI'ı).
   - `Escape` ve overlay tıklaması ile kapanma; `role="dialog"` + `aria-modal`; odak yönetimi.

---

## 4. Dosya Hazır Onay Mekanizması (Görünüm 3)

- Her kontrol maddesi için "Hazır" onay kutusu; durum **istemci tarafında** `localStorage`'da `bilun:checklist:ready:<patientId>` anahtarıyla saklanır (Set<checklist_id>).
- Backend/veritabanı şeması değişmez (out of scope — v3'te kullanıcı/persistans katmanına taşınabilir).
- SSR güvenliği: `typeof window !== "undefined"` kontrolü; `useEffect` ile ilk yükleme.

---

## 5. i18n Planı

- `frontend/src/messages/tr/billing.ts` + `en/billing.ts`:
  - `billing.views.*`: görünüm başlıkları, açıklamaları, KPI etiketleri, "hazır dosya" etiketleri.
  - `billing.clauseDrawer.*`: çekmece başlığı, yükleniyor, boş durum, "kural veritabanına git", kapat.
- `frontend/src/messages/tr/patient.ts` + `en/patient.ts`:
  - `patient.billingGroups.compliance|opportunities|reference` anahtarları (yalnızca `page.tsx` kullanıyordu — doğrulandı) `patient.views.*` ile değiştirilir; kullanılmayan eski anahtarlar silinir. `overview` korunur.
- Ders uygulaması (`tasks/lessons.md` — eksik katalog): her yeni anahtar için hem tr hem en sözlükte tam karşılık aynı commit'te eklenir.

---

## 6. Test ve Doğrulama Planı

### Yeni Testler
- `frontend/src/components/patient/views/PatientWorkspaceViews.test.tsx`: 3 sekme render, badge sayıları (canlı rapordan: 18/2/4), sekme geçişi, KPI değerleri (₺121.714,71 / ₺23.192,18 formatı), `onOpenClause` tetiklemesi, hazır onay kutusu localStorage davranışı.
- `frontend/src/components/sut/SutClauseDrawer.test.tsx`: `getSectionClauses` mock'lu — fıkra listesi render, boş durum, kapatma (Escape/overlay), API hatası durumu.
- `SutBillingReportSections.test.tsx`'e **ek** durumlar: `findingFilter` filtreleme, `onOpenClause` verildiğinde buton render.
- Mevcut testler: `SutPatientWorkspace.test.tsx`, `SutBillingReportSections.test.tsx`, `PatientFinancialSummary.test.tsx`, `OriginalBillView.test.tsx` — davranışları değişmediği için yeşil kalmalı.

### Doğrulama Adımları (Definition of Done)
1. `cd frontend && npx tsc --noEmit` — sıfır hata (ders: `tasks/lessons.md` — vitest tek başına yeterli değil).
2. `cd frontend && npx vitest run` — tüm suite yeşil (eski + yeni).
3. `pytest -q tests/unit/domain/billing tests/unit/domain/claims` — backend değişmedi; sıhhi kontrol.
4. `http://localhost:3000/patient/SENTETIK-HASTA-0001` üzerinde: 3 sekme geçişi, KPI'lar veriyle eşleşme (Risk ₺121.714,71 / Gelir ₺23.192,18 / Kontrol 4), fıkra çekmecesi açılışı, hazır onay kalıcılığı (yenileme sonrası korunma), eylem seçimi → fatura satırı vurgusu bozulmamış, `?section=` URL davranışı korunmuş.
5. Bill-scope (`?claim=…`) altında sekme görünümlerinin de doğru çalıştığı doğrulanır.

---

## 7. Uygulama Yol Haritası

### Adım 1: i18n anahtarları (tr + en)
### Adım 2: `RecommendedActionsPanel` opsiyonel prop'ları (filter + onOpenClause)
### Adım 3: `SutClauseDrawer` bileşeni
### Adım 4: `views/` bileşenleri (tabs + 3 görünüm + KPI şeritleri + hazır onay kutuları)
### Adım 5: `page.tsx` entegrasyonu (3 eski grup → tek `PatientWorkspaceViews`; çekmece state'i)
### Adım 6: Testler (yeni + ek durumlar)
### Adım 7: Doğrulama (tsc, vitest, hedefli pytest, tarayıcı kontrolü)

---

## 8. Kapsam Dışı (Out of Scope)

- Backend/API/veri modeli değişikliği (yeni `engine` enum'u dahil — bkz. Revizyon Notu #8).
- `yatak_puani`, `icu_puani`, `anestezi_puani`, `refakatci`, `yenidogan_yatak` için yeni detay bölümleri (FE domain tipinde alan yok).
- Dosya hazır onayının sunucu tarafında kalıcılığı / çok kullanıcılı durum.
- `SutPatientWorkspace.tsx`'in değiştirilmesi (bulguları barındırmıyor — doğrulandı).
- SUT kural motorunun matematiksel hesaplama formülleri.
