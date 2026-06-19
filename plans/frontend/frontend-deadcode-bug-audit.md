# Plan: Frontend Dead-Code & Bug Audit Raporu

**Tarih:** 2026-06-19
**Kapsam:** `frontend/src/` — dead code + runtime bug + stale CSS/dependency tespiti
**Yöntem:** 3 paralel Explore subagent, tüm bulgular `Grep`/`Read` ile kanıtlandı (halüsinasyon yok)

---

## Goal

`frontend/src/` içindeki (1) silinebilir dead code, (2) düzeltilmesi gereken bug'ları, (3) stale CSS/dependency'leri envanterleyip öncelik sırasına koymak. Bu rapor yalnızca tespit raporudur — fix'ler ayrı task'lerde yapılır.

## Out of Scope

- Backend (`src/bilun/`) — ayrı audit gerekir
- Test dosyalarının kendi içindeki kalite
- Gerçek fix implementasyonu (bu rapor onay sonrası ayrı todo'lara bölünür)

---

## Özet sayılar

| Kategori | Sayı |
|---|---|
| Toplam production `.ts/.tsx` dosyası | 150 |
| LIVE | 144 |
| **DEAD/ORPHANED** (hiç import edilmeyen) | **2** |
| **SUPERSEDED** (yenisiyle değiştirilmiş, eski kalmış) | **3** |
| Silinebilir toplam satır (dosya bazlı) | **~466 satır** |
| **CRITICAL bug** | **3** |
| **HIGH bug** | **5** |
| MEDIUM/LOW bug | 14 |
| **Kullanılmayan npm dependency** | **5** |
| **Kullanılmayan CSS sınıfı** | **4** |
| **Kullanılmayan barrel export** | **2 tamamen ölü**, 25+ barrel-bypass |

---

## 1. DEAD CODE — silinebilir dosyalar

### 1.1 Tamamen ölü (orphaned) — güvenle sil

| # | Dosya | Satır | Neden ölü | Yerine geçen |
|---|---|---|---|---|
| D1 | `components/tabs/SUTAnalytics.tsx` | 3 | `SUTPatients`'a 1-satır re-export stub; hiç importer yok | `SUTPatients.tsx` (canlı, `app/page.tsx:36`) |
| D2 | `components/patient/ClaimSelector.tsx` | 74 | Hiç importer yok (test bile yok). Aynı prop shape'inin `BillPicker` karşılığı | `components/patient/BillPicker.tsx` (`app/patient/[id]/page.tsx:30,495`) |

### 1.2 Superseded — yenisi var, eskisi unutulmuş

| # | Dosya | Satır | Neden superseded | Yerine geçen |
|---|---|---|---|---|
| S1 | `components/patient/ClaimDetailPanel.tsx` | 198 | Aynı `PatientClaimDetail` render'ı; hiç importer yok | `OriginalBillView.tsx` (343 satır, `page.tsx:31,516`) |
| S2 | `components/tabs/SUTOptimizer.tsx` | 3 | `SUTOptimizerTab` default'una 1-satır re-export; hiç importer yok. *Yan etki:* `SUTOptimizerTab.tsx:1626`'daki `SUTOptimizer` default export'u da bu alias'tan ulaşılıyordu → o da ölü | `SUTCompliance.tsx`+`SUTRevenue.tsx` named export'ları doğrudan kullanıyor |
| S3 | `components/home/SutWorkspaceLanding.tsx` | 188 | Tam landing ekranı; hiç production importer yok (sadece kendi testi). Home artık tabbed workspace | Tabbed workspace `app/page.tsx:147-166` |

> **S3'ün testi** `SutWorkspaceLanding.test.tsx` de birlikte silinmeli.

### 1.3 Canlı ama runtime'da ölü

| # | Dosya | Durum | Aksiyon |
|---|---|---|---|
| R1 | `components/shell/SutWorkspaceHeader.tsx:3-5` | Body `return null`. Import ediliyor (`app/page.tsx:9,130,189`) ama hiçbir şey render etmiyor | Import'lar + component birlikte kaldırılabilir (kod editi) |
| R2 | `app/patient/[id]/billing/page.tsx:7-18` | `router.push` ile redirect stub, `return null` | **SAKLA** — bu bilinçli route konsolidasyonu, kasıtlı |

---

## 2. BUGS — öncelik sırasına göre

### 🔴 CRITICAL (çöker veya yanlış sonuç)

**C1 — Scoped report'lar kendi kendini abort ediyor**
`frontend/src/app/patient/[id]/page.tsx:348-356`

```js
useEffect(() => {
  if (!patientId || loading) return;
  loadScopedReports(patientId, selectedClaimId);
  return () => { scopedControllerRef.current?.abort(); };
}, [loadScopedReports, loading, patientId, selectedClaimId]);
```

Effect her re-render'da cleanup abort ediyor. `loading` (workspace) flip → `selectedClaimId` async set → iki scoped fetch ardışık çalışır, ilki abort edilir. **Sonuç:** yavaş ağda scoped spinner'lar asla çözülmez / yanlış claim verisi gösterilir. Ayrıca `loading` guard'ı, alakasız workspace fetch bitene kadar scoped raporları bekletiyor — gereksiz coupling.

**C2 — Varsayılan bill seçimi stale claim'den geliyor, locale switch sıfırlıyor**
`frontend/src/app/patient/[id]/page.tsx:203-235`

`loadClaims` `t`'ye bağlı (`:235`), `t` her locale switch'te identity değiştiriyor → effect tekrar çalışıyor → `selectedClaimId` null'a set (`:211`) → kullanıcının `?claim=` URL seçimi kayboluyor.

**C3 — `useParams` memo yanlış çalışıyor**
`frontend/src/app/patient/[id]/page.tsx:73-76`

`useParams()` Next.js'te her render'da **yeni obje referansı** döner → `useMemo([params])` hiç cache'lemiyor. `patientId` her render'da yeniden hesaplanıyor. Şu an latent (gerçek driver `loadWorkspace`), ama yanıltıcı bir "memoize edildi" görünümü.

### 🟠 HIGH (veri kaybı / yanlış state)

| # | Dosya:Satır | Sorun |
|---|---|---|
| H1 | `app/patient/[id]/page.tsx:187-201` | `loadWorkspace` cleanup'ı `loading`'u `true`'ya resetlemiyor. `loadWorkspace` identity değişince (locale) abort oluyor ama `loading=false` kalıyor → yanlış hastanın stale verisi kısa süre gösterilir |
| H2 | `components/chat/SutInlineAIPanel.tsx:322-338` | Auto-brief debounce effect `[patientId, activeTab]`'e bağlı, ama `locale` değişince ayrı effect (`:304-320`) `force:true` ile ateşliyor — pending 400ms debounce hâlâ sırada, çift istek oluşuyor |
| H3 | `app/patient/[id]/page.tsx:185,235,269,346` | `t` tüm `loadX` callback dep'lerinde. **Tek kök neden:** `t`'yi ref'e taşırsan C2, H1, M7 birlikte çözülür |
| H4 | `app/page.tsx:94-123` | `healthStatus` effect her dep değişiminde `setHealthStatus(null)` yapıyor → admin toggle'da panel boş yanıp sönüyor |
| H5 | `SutInlineAIPanel.tsx:633` | Auto-brief stream ederken textarea `disabled` değil (`isResponding` follow-up'ta true). Kullanıcı follow-up gönderirse iki SSE akışı aynı `messages` state'ine yarışıyor → auto-brief `.then`'i (`:259`) follow-up'ı ezip geçebilir |

### 🟡 MEDIUM

- **M1** `SutInlineAIPanel.tsx:521-524` — message key'leri `index`+content prefix karışık; briefing filtrelenince indeks kayıyor, React satırı yanlış tanıyabilir. Stabil message id gerek.
- **M2** `BillPicker.tsx:51-56,66-73` — `new Date(claim_start_date)` null tolerant değil; API kontratı gevşerse sessizce en alta sıralar.
- **M3** `OriginalBillView.tsx:334-337` — varyans negatif/büyük çıkarsa sign/format guard yok; güven kaybı.
- **M4** `OriginalBillView.tsx:246` — `episode_id · claim_type · primary_icd10` null guard'sız; eksik veride `· ·` görünür (çevrede `?.` kullanılıyor, tutarsız).
- **M6** `AppTopBar.tsx:45-61` — `getMedulaRejectionIngestStatus()` mount'ta bir kere `[]` ile çekiliyor; ingest sonradan aktif olursa Operations link'i reload'a kadar çıkmaz. AbortController da yok.
- **M7** `RuleDatabaseSection.tsx:977-1007` — detail effect `[ruleId, page, t]`; locale switch'te rule detail refetch + scroll kaybı. Aynı `t`-dep pattern'i.

### 🟢 LOW

- **L1** Hardcoded `"Thinking"`, `"+"`, `"−"`, `⚠` glyph'leri i18n değil (`SutInlineAIPanel.tsx:549,599`, `RuleDatabaseSection.tsx:168,947`).
- **L2** `resolvePromptKey` (`SutInlineAIPanel.tsx:52-64`) bilinmeyen tab'da sessizce `"sutWorkspace"`'e düşüyor.
- **L3** `parseUiLocale` (`sutChat.ts:8-10`) sadece `"tr"` tanıyor, gerisi `"en"`. Üçüncü locale eklenirse sessiz bozulur.
- **L4** `SutHowItWorksModal.tsx:127` — `<div key={detail}>` içerik-based key; duplike çeviri string'inde collision.
- **L5** `translate.ts:25-29` — `{x}` ve `{{x}}` aynı muamele; translator yanlış kullanırsa sessiz boş.

### Temiz bulunan dosyalar (sorumluluk)

`sutChat.ts`, `apiClient.ts`, `request.ts`, `useSutApi.ts`, `sutChatPageContext.ts`, `PatientSearch.tsx`, `recents.ts` — AbortController/sequence guard/SSR guard hepsi doğru. Burada bug yok.

---

## 3. STALE CSS — `legacy.css`

**Dosya:** `frontend/src/app/styles/legacy.css` (283 satır — planın bahsettiği ~621 satırdan zaten budanmış)

**22 sınıf tanımlı, 19 kullanılıyor, 4 ölü:**

| Sınıf | Satır | Kanıt |
|---|---|---|
| `.sut-filter-control` | `:200` | 0 JSX referans |
| `.loading-state` | `:253` (grup rule) | 0 referans |
| `.loading-spinner` | `:271` + `@keyframes spin` | 0 referans |
| `.app-main` | `:35,41` | 0 JSX (sadece `sut-app-main` kullanılıyor) — confirm gerek |

> **Önemli:** `plans/frontend/legacy-css-dead-code-removal.md` **stale**. Planın "dead classes" listesi zaten silinmiş sınıfları listeliyor (artık dosyada yok). Planın "live classes" listesi `sut-filter-control`, `loading-state`, `loading-spinner`'ı canlı diyor ama **gerçekte ölü**. Ayrıca live listesinde bahsettiği `DrgPricingSection.tsx` dosyası kod tabanında yok.

---

## 4. KULLANILMAYAN NPM DEPENDENCY'LER

`frontend/package.json` — **5 runtime dependency hiç import edilmiyor:**

| Package | Kanıt |
|---|---|
| `@radix-ui/react-collapsible` | 0 import |
| `@radix-ui/react-select` | 0 import |
| `@radix-ui/react-slot` | 0 import (sadece `react-tabs` kullanılıyor) |
| `@tanstack/react-virtual` | 0 import |
| `class-variance-authority` | 0 import (`cva` hiç geçmiyor) |

Kullanılanlar (doğrulandı): `clsx`, `tailwind-merge`, `lucide-react`, `recharts`, `zustand`, `@radix-ui/react-tabs`.

---

## 5. BARREL EXPORT HİJYENİ

### Tamamen ölü (hiçbir yerde referans yok)

- `getNestedMessage` — `lib/i18n/index.ts:3` (translate.ts içinde bile kullanılmıyor)
- `Messages` type — `lib/i18n/index.ts:5`
- `useClearSutChatSession` — `stores/uiStateContext.tsx:56` (altındaki store action da çağrılmıyor)

### Barrel-bypass (12 export'tan 11'i barrel üzerinden değil deep-path ile kullanılıyor)

`lib/i18n/index.ts` barrel'ı neredeyse tamamen atlanmış — sadece `useLocale` barrel üzerinden (`RuleDatabaseSection.tsx:42`). Diğer 11 sembol deep-path (`@/lib/i18n/useTranslations` vb.) ile import ediliyor. Barrel kendisi ölü değil ama amaç dışı.

`components/primitives/index.ts` — tüm **type export'ları** (14 adet: `SurfaceProps`, `StatProps`, ... `ToolbarProps`) haricen kullanılmıyor; `Tabs` default compound export'u da kullanılmıyor. Value export'ları canlı.

---

## 6. ÖNERİLEN FIX SIRASI (ROI'ye göre)

### Dalga 1 — Hızlı kazanç (dead code silme, ~1 saat)
- [ ] D1+D2+S1+S2+S3 dosyalarını sil + S3 testini sil (~466 satır)
- [ ] R1 `SutWorkspaceHeader` import'larını `app/page.tsx:130,189`'dan temizle
- [ ] 4 ölü CSS sınıfını `legacy.css`'ten sil
- [ ] 5 kullanılmayan npm dependency'yi `package.json`'dan çıkar, `npm install`
- [ ] `getNestedMessage`, `Messages` type, `useClearSutChatSession` export'larını kaldır

### Dalwa 2 — Kök neden fix (bug C1, C2, H1, H3, M7 hepsini tek değişiklik çözüyor)
- [ ] `t`'yi `loadX` callback dep'lerinden çıkar → ref taşı. Bu **C2, H1, M7'yi** birlikte çözer.
- [ ] C1: scoped report effect'inin `loading` guard'ını ve cleanup abort pattern'ını düzelt

### Dalga 3 — Yarış/tutarsızlık (H2, H5, M4)
- [ ] H2: auto-brief debounce effect'ine `locale` ekle VEYA locale effect'inde pending debounce'u temizle
- [ ] H5: `isAutoLoading` sırasında textarea `disabled` yap / `handleSend` auto-brief'i abort etsin
- [ ] M4: `OriginalBillView.tsx:246` null guard ekle

### Dalga 4 — Kalan (C3, H4, M1-M3, M6, L1-L5)
- [ ] C3: `useMemo`'yu `useParams`'ın gerçek stabilitesine göre düzelt
- [ ] H4: `healthStatus` effect `setHealthStatus(null)`'ı kaldır veya dep'leri daralt
- [ ] M6: `AppTopBar` ingest status poll'una interval + AbortController ekle
- [ ] i18n hardcoded string'leri (L1)

---

## 7. Doğrulama kriterleri (fix sonrası)

- `npx vitest run` — 137/137 yeşil kalmalı (S3 testi silindikten sonra 136)
- `npm run build` — başarılı
- `npx tsc --noEmit` — başarılı
- Dalga 2 sonrası: patient sayfasında locale switch yapınca `selectedClaimId` korunmalı, scoped report spinner'ı takılı kalmamalı
- Dalga 3 sonrası: auto-brief stream ederken follow-up gönderince çift stream yarışı olmamalı
- `npm ls` — 5 dependency çıktıktan sonra extraneous uyarı yok

## Out of Scope (bu raporda)

- Backend dead code / bug tespiti
- Rule Database UI'sini dürüst hale getirme (Öncelik 4b — ayrı plan)
- Tier C ilaç endikasyonu kapanış yol haritası
- Registry drift (3a) ve stale rakam (3b) düzeltme
