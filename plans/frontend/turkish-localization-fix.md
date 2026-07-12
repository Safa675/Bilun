# Plan: Turkish Frontend Full Localization Fix (v2)

**Tarih:** 2026-07-02 (rev. 2026-07-12)
**Kapsam:** `frontend/src/` — Türkçe localizasyon sızıntılarının giderilmesi
**Yöntem:** 2 paralel Explore subagent (i18n yapısı + tüm componentler) cross-verify etti; v2 revizyonu 4 paralel bağımsız denetim (i18n mimarisi, sızıntı avı, citation doğrulaması, test/chat/enum analizi) ile doğrulandı.

---

## v2 Revizyon özeti (denetim bulgularına dayalı)

v1'in teşhisi doğru, execution order mantıklı, citation'ları %95.5 oranında isabetli (42/44). Ancak v1:

- **`fmtDate` zaten var** — `lib/i18n/formatters.ts:41`'de locale-aware `fmtDate` tanımlı. Phase 5'in "oluştur" görevi gereksiz; asıl iş wire etmek + barrel export'a eklemek.
- **4 kullanıcı-görünür sızıntı atlandı** — `layout.tsx` meta, `constants.ts` dup, `globals.css` print selector, `configContext.tsx` errors. Bu dosyalar v1'in listesinde yok.
- **Backend enum "label helper'lar kapsıyor" dışlaması kısmen yanlış** — `payment_method_kind`, `severity` (helper var ama çağrılmıyor), `claim_type`/care-setting, `source` raw render ediliyor, helper/bundle girişi yok.
- **2 citation yanlış** — `sutChat.ts:145` ve `:133`.
- **`ApiRequestError`'un `code` alanı yok** — sadece `status`/`detail`/`isNetworkError`. Phase 1 stratejisi bir *uzantı* gerektirir, basit yeniden kullanım değil.

Bu revizyon: Phase 5'i düzeltir, Phase 0 ekler (atlanan sızıntılar), Phase 3'ü enum gap'leriyle genişletir, citation'ları düzeltir.

---

## Goal

Türk frontend'i tamamen Türkçe yap. İngilizce sızıntılarını (hardcoded, backend-derived, formatting, CSS, metadata) gider. Mevcut i18n altyapısı (`t()`, `useT()`, `translate()`, `messages/{en,tr}/`, `lib/i18n/formatters.ts`) çalışıyor — sorun altyapıda değil, sızıntıda.

## Teşhis — İngilizce nereden sızıyor?

i18n altyapısı sağlam: 18 message modülü EN/TR mirror (`index.ts` barrel hariç), `t()`/`useT()`/`translate()` her yerde kullanılıyor, TR message'lar gerçekten Türkçe, `lib/i18n/formatters.ts` zaten locale-aware `fmtDate`/`fmtTRY`/`fmtNum`/`fmtPct` sağlıyor. Sorun **6 sızıntı vektöründe**:

| Vektör | Bulgu sayısı | Açıklama |
|---|---|---|
| **A — API client `throw new Error(English)`** | 10 | `sutChat.ts` ve `apiClient.ts` İngilizce hata fırlatıyor, UI'da raw gösteriliyor |
| **B — Backend-derived English raw render** | 38+ | Backend alanları (`source`, `notes`, `severity`, `violation_kind`, `payment_method_kind`, ISO tarihler) `t()`/helper'dan geçmeden render ediliyor |
| **C — Hardcoded English fallback'lar** | 19 | `useSutApi.ts` default mesajları, `apiMessages.ts` fallback'leri, `recommendedActions.ts` snake_case leak |
| **D — Tarih/numara formatı** | 7 | 7 yerde raw ISO tarih (`YYYY-MM-DD`); `fmtDate` mevcut ama wire edilmemiş ve barrel'dan export yok |
| **E — Metadata / CSS / config sızıntısı** (v1 atladı) | 4 | `layout.tsx` meta EN, `globals.css` print selector TR'de eşleşmiyor, `configContext.tsx` EN throw, `constants.ts` EN dup |
| **F — Backend enum'ları, helper'ı olmayan** (v1 dışladı) | 5+ | `payment_method_kind` (5 değer), `claim_type`/care-setting, `source` raw render; `severity` helper var ama 2 yerde bypass |
| **Toplam** | **~80+** | |

### En kritik hedefler (en yüksek kullanıcı etkisi)

1. **`layout.tsx:40` meta description** (v1 atladı, **HIGH**) — `<meta description>` her lokasyonda İngilizce. TR çevirisi `messages/tr/constants.ts:5`'te hazır ama kullanılmıyor.
2. **`sutChat.ts` + `apiClient.ts`** — 10 İngilizce `throw new Error()`. Çevrilmiş key'ler (`chat.api.*`) zaten var ama API katmanı kullanmıyor.
3. **`apiMessages.ts` fallback'leri** — her helper tanınmayan backend string'inde `return trimmed` ile ham İngilizce döndürür (4 literal `return trimmed` + 3 `|| trimmed` + 1 `return part`).
4. **`SutBillingReportSections.tsx`** — en büyük tek sızıntı noktası (13 raw alan + eklenen enum gap'leri).
5. **`globals.css:248` print selector** (v1 atladı, **MED**) — TR'de eşleşmediği için top-bar butonları print'e sızıyor.
6. **`useSutApi.ts:22-23`** — `"Request was interrupted"` ve `"Failed to load data"` hardcoded defaults.

### Mimari notlar (implementör için)

- **Locale mekanizması:** next-intl DEĞİL. Elle yazılmış: `LocaleProvider` (React context) + `bilun:locale` cookie + `bilun:locale` localStorage + `localeModule.ts`'te module-level singleton (`getModuleLocale()`/`setModuleLocale()`). Locale middleware/path-prefix/Accept-Language yok. `fmtDate` zaten `getModuleLocale()` üzerinden runtime'da locale alıyor. Server component'ler (`layout.tsx`) cookie'den doğrudan okumalı.
- **`t()` tek bir export DEĞİL.** ≥4 dosyada lokal olarak yeniden tanımlı (`apiMessages.ts:10`, `sutLabels.ts:10`, `sutExactness.ts:23`, `sutOptimizerHelpers.ts:18`), her biri `getModuleLocale()` üzerinden `translate()` çağırır.
- **`ApiRequestError` (`apiClient.ts:39-54`) `code` alanı yok** — sadece `status`/`detail`/`isNetworkError`. Phase 1 stratejisi `code` özelliği eklenmesini gerektirir.
- **`useSutApi.ts` ve `sutChat.ts` aynı dizinde DEĞİL** — `sutChat.ts` `lib/api/`'da, `useSutApi.ts` `components/tabs/sut/`'ta.
- **`fmtDate` barrel'dan export yok** — `lib/i18n/index.ts:4` sadece `fmtTRY, fmtTRY2, fmtNum, fmtPct, fmtNumber` export ediyor. `fmtDate` eklenmeli.
- **Test altyapısı:** Vitest (`vitest.config.ts`), 39 test dosyası. TR-çıktı iddiası için precedent var: `apiMessages.test.ts:35-48` `setModuleLocale("tr")` kullanır. `renderWithLocale` SSR helper'ı 15 component testinde kullanılıyor. `useT()` için `renderHook` helper yok ama component-level assertion yeterli.

---

## Phase 0 — Metadata / CSS / config sızıntıları (v1 atladı; en yüksek görünürlük)

**Hedef:** Plan kapsamı dışındaki 4 kullanıcı-görünür sızıntıyı gider.

### Subtasks
- [ ] **[HIGH] `layout.tsx:40` meta description** — `description: SUT_BRAND.metaDescription` ("Bilun billing rule intelligence module") tüm locale'lerde EN. `messages/tr/constants.ts:5`'te TR ("Bilun fatura kuralı zekası modülü") hazır. Server component olduğu için `bilun:locale` cookie'sinden locale oku, doğru catalog'tan çek. (`title: "Bilun"` markadır, sızıntı değil.)
- [ ] **[MED] `lib/constants.ts:25-74` `SUT_BRAND` + `SUT_HOME_TABS`** — hardcoded EN, i18n catalog'unu tekrarlıyor. Çoğu ölü veri ama `metaDescription` (→Phase 0 üst madde) tüketiliyor. Tüketiciyi catalog üzerinden route et veya sabiti sil. `messages/{en,tr}/constants.ts` zaten çevirileri içeriyor.
- [ ] **[MED] `app/globals.css:248-249` print selector** — `header[aria-label="Bilun application bar"]` TR'de eşleşmiyor (aria-label `"Bilun uygulama çubuğu"` olur, `messages/tr/shell.ts:9`); top-bar butonları print'e sızıyor. Selector'ı stable bir hook'a (`data-sut-topbar`) veya class'a taşı.
- [ ] **[MED] `lib/configContext.tsx:101,109`** — `"Config fetch failed: ${res.status}"` + `"Unknown error"` fallback. Bugün render edilmiyor ama latent risk. i18n'den geçir veya dev-only olarak kabul et (belgeli karar).
- [ ] Vitest: `layout.tsx` için TR cookie'de TR meta çıktısı; print selector değişikliği manuel/görsel doğrulama.

### Out of Scope
- `RoleProvider.tsx:57,65`, `LocaleProvider.tsx:88`, `theme.ts:19` invariant throw'ları — programmer-error guard'ları, conventional olarak EN kalır (idomatik).
- `console.warn`/`console.error` dev-only log'ları (`page.tsx:110`, `error.tsx:19`).

---

## Phase 1 — API client İngilizce hataları (en yüksek etki, en kolay)

**Hedef:** `sutChat.ts` ve `apiClient.ts`'teki 10 İngilizce `throw new Error()` string'ini çevrilmiş mesajlarla değiştir.

### Subtasks
- [ ] `sutChat.ts:58` — `"SUT chat request timed out..."` → error code ile caller'a bırak
- [ ] `sutChat.ts:84` — `"Could not reach API at ${url}"` → `t("chat.api.networkError")`
- [ ] `sutChat.ts:145` — ~~"Could not reach API"~~ **aslında "No response received from SUT chat. Please try again."** (v1 citation yanlıştı) → `t("chat.api.noResponse")` veya `emptyResponse`
- [ ] `sutChat.ts:90-93` — `"SUT chat failed: ${status}..."` → error code
- [ ] `sutChat.ts:100` — `"SUT chat returned no response body."` → `t("chat.api.emptyResponse")`
- [ ] `sutChat.ts:159` — `"SUT chat returned an empty response."` → `t("chat.api.emptyResponse")`
- [ ] `sutChat.ts:133` — ~~"empty response"~~ **aslında `throw new Error(payload)` SSE error-frame rethrow** (v1 mislabeled). `payload` backend/EN olabilir; `translateApiText(payload)` veya generic placeholder ile sar.
- [ ] `apiClient.ts:72` — `"Could not reach API at ${url}"` → error code (caller çevirir)
- [ ] `apiClient.ts:90-93` — `"API error: ${status}..."` → error code
- [ ] `apiClient.ts:103` — `"API returned invalid JSON..."` → error code
- [ ] **Strateji:** API katmanı `throw new Error(EnglishString)` yerine `throw new ApiRequestError(code, details)` atsın. **Önce `apiClient.ts:39-54` `ApiRequestError` class'ına `code` alanı ekle** (mevcut sadece `status`/`detail`/`isNetworkError`). Caller (`catch` bloğu) error code'u `t()`'ye çevirir.
- [ ] Eksik `chat.api.*` key'leri varsa `messages/tr/chat.ts` ve `messages/en/chat.ts`'ye ekle
- [ ] Vitest: her error path için TR'de Türkçe çıktı doğrula

### Out of Scope
- Backend error mesajlarının kendisini değiştirme (backend ayrı)

---

## Phase 2 — `apiMessages.ts` fallback'leri (backend→UI köprüsü)

**Hedef:** Backend'den gelen İngilizce string'lerin tanınmayan durumda raw sızmasını engelle.

### Subtasks
- [ ] `translateValidationMessage` (174) — fallback `return trimmed` (213) → `return t("api.unknownViolation")`
- [ ] `translateUnavailableReason` (82) — `return trimmed` (114) → `return t("api.unknownReason")`
- [ ] `translateMethodology` (117) — `return ... || trimmed` (135) → `return ... || t("api.unknownMethodology")`
- [ ] `translateProvenanceText` (138) — `return ... || trimmed` (147) → `return ... || t("api.unknownProvenance")`
- [ ] `translateConsistencyWarning` (150) — `return ... || trimmed` (159) → `return ... || t("api.unknownWarning")`
- [ ] `translateHealthMessage` (162) — `return trimmed` (171) → `return t("api.unknownHealth")`
- [ ] `translateValidationSummary` (216) — per-part `return part` (270) → generic placeholder
- [ ] `translateApiText` (277) — `return trimmed` (300) → generic placeholder (umbrella dispatcher)
- [ ] `translateRequiredInput` (62) — `return input.replace(/_/g, " ")` (68) → değerlendir (basit prettify, belki kabul edilebilir)
- [ ] Regex coverage'ı genişlet — bilinen backend pattern'leri için yeni regex kuralları ekle
- [ ] `messages/tr/api.ts`'ye `unknownViolation`, `unknownReason`, `unknownMethodology` gibi generic fallback key'leri ekle
- [ ] Vitest: tanınmayan string girince artık Türkçe placeholder döner

### Strateji
Her helper'ın raw-return kuyruğunu **generic localized placeholder** ile değiştir. Tanınmayan backend string'i artık ham İngilizce değil, "Bilinmeyen ihlal türü" gibi generic Türkçe olur. Regex coverage'ı paralel olarak genişletilir.

---

## Phase 3 — `SutBillingReportSections.tsx` raw render fix + backend enum gap'leri (en büyük tek dosya)

**Hedef:** 13 raw backend alanını `t()`/format helper'larından geçir + v1'in "out of scope" dediği helper'sız enum'ları kapsama al.

### Dosya yolu
`frontend/src/components/patient/SutBillingReportSections.tsx` (2504 satır)

### 3a — Tarihler (4 yer)
- [ ] `:1195` `service_date` → `fmtDate(item.service_date)`
- [ ] `:1385` `service_date` → `fmtDate(...)`
- [ ] `:1386` `amendment_effective_date` → `fmtDate(...)`
- [ ] `:2197` `last_use_date` → `fmtDate(...)`

### 3b — Enum'lar (helper ile)
- [ ] `:1626` `severity` → `getSutSeverityLabel(item.severity)` (helper `sutLabels.ts:53`'te var, TR label `messages/tr/labels.ts:53-57`'de `error/warning/info` → `Hata/Uyarı/Bilgi` mevcut)
- [ ] `:1486` `severity` (claim checklist) → **aynı helper bypass edilmiş, düzelt** (helper+label zaten var)
- [ ] `:1548` `medula_stage` → `t(\`api.medulaStage.${item.medula_stage}\`)` veya label helper
- [ ] `:1625` `violation_kind` → `t(\`api.violationKind.${item.violation_kind}\`)`

### 3c — Backend enum gap'leri (v1 "out of scope" dedi, denetim show that's wrong) — [YENİ]
- [ ] `:1797,1805` **`payment_method_kind`** (`DRG_MANDATORY`/`DRG_OVERRIDABLE`/`ITEMIZED`/`MISSING_INPUTS`/`NOT_IN_SUT`) — **helper yok, bundle girişi yok**. `messages/{en,tr}/labels.ts`'ye 5 değer ekle + `getPaymentMethodKindLabel` helper veya `t(\`api.paymentMethodKind.${...}\`)`. TR billing memuru `"DRG_OVERRIDABLE"` yerine Türkçe görmeli.
- [ ] `:1792,1794,1802` `claim_type` / `actual_care_setting` / `alternate_care_setting` — raw render, helper yok. Bundle girişi ekle veya `translateApiText(...)`.
- [ ] `:1196` `source` (procedure capture gap) — backend free string (default `"emr"`). `translateApiText(...)` veya generic placeholder.
- [ ] **Karar:** `medula_stage`/`violation_kind`/`payment_method_kind` teknik kodlar olarak mı kabul edilecek (belgeli karar) yoksa çevrilecek mi? Her durumda `payment_method_kind` gibi kararlı enum'lar çevrilmeli.

### 3d — Raw backend text (4 yer)
- [ ] `:1550` `hata_mesaji` → `translateApiText(item.hata_mesaji)` veya generic placeholder
- [ ] `:1630` `message_tr` — null fallback ekle (null ise `t("api.noMessage")`)
- [ ] `:2287,2319` `hit.message || hit.rule_id` → `translateApiText(...)`
- [ ] `:248` `action.detail` → `translateApiText(item.detail)`

### 3e — Backend metadata (LOW)
- [ ] `:1629` `sut_section` — teknik referans (§4.2.14.C gibi), olduğu gibi kalsın (LOW)
- [ ] Vitest: her fix edilen alan için TR'de Türkçe/formatlı çıktı doğrula

---

## Phase 4 — `useSutApi.ts` hardcoded defaults + diğer hardcoded'lar

**Hedef:** Kalan hardcoded İngilizce string'leri temizle.

### Subtasks
- [ ] `useSutApi.ts:22` — `DEFAULT_ABORT_MSG = "Request was interrupted..."` → `t("common.requestAborted")`
- [ ] `useSutApi.ts:23` — `DEFAULT_ERROR_MSG = "Failed to load data."` → `t("common.loadFailed")`
- [ ] **Önemli:** bu default'lar hook init'te set ediliyor — `t()` hook içinde erişilebilir olmalı (caller'dan parametre olarak geçir veya module-level `translate()` kullan). Tam yol: `components/tabs/sut/useSutApi.ts`.
- [ ] `recommendedActions.ts:167` — `recommendedActionSurfaceLabel` fallback → `t("common.unknownSurface")`
- [ ] `recommendedActions.ts:172` — `recommendedActionKindLabel` fallback → `t("common.unknownKind")`
- [ ] `sutLabels.ts:50` — `getSutRecommendedActionLabel` fallback → generic placeholder
- [ ] `messages/tr/common.ts`'ye yeni key'ler ekle
- [ ] Vitest: default mesajlar artık Türkçe

---

## Phase 5 — Tarih/numara formatı standardizasyonu (`fmtDate` zaten var!)

**Hedef:** 7 yerde raw ISO tarih → mevcut `fmtDate` helper'ı wire et.

### v1 HATASI (düzeltildi)
v1 Phase 5 "`lib/i18n/formatters.ts`'e `fmtDate` ekle" diyordu. **`fmtDate` zaten var** (`lib/i18n/formatters.ts:41`), `Intl.DateTimeFormat`/`toLocaleDateString` kullanıyor, `getModuleLocale()` üzerinden locale-aware. Asıl sorun: **barrel'dan export yok** ve call site'larda wire edilmemiş.

### Subtasks
- [ ] **[KRİTİK] `lib/i18n/index.ts:4` barrel export'a `fmtDate` ekle** (mevcut: `fmtTRY, fmtTRY2, fmtNum, fmtPct, fmtNumber`)
- [ ] `SutBillingReportSections.tsx:1195,1385,1386,2197` — (Phase 3a ile çakışıyor, orada yap)
- [ ] `BundledConsumablesSection.tsx:82` — `item.effective_date` → `fmtDate(...)`
- [ ] `ProseInventoryPanel.tsx:93` — `engine.effective_date` → `fmtDate(...)`
- [ ] `MedulaRejectionQueueTab.tsx:281` — `row.rejection_timestamp` → `fmtDate(..., {timeStyle})` (tarih + saat)
- [ ] `TemporalPriceSection.tsx:108` — lokal `fmtDate = (d) => d.slice(0, 10)` → barrel'dan `fmtDate` import et (shadowing'i kaldır)
- [ ] **(Opsiyonel) `fmtDate` iç implementasyonunu** `toLocaleDateString` → `Intl.DateTimeFormat(getIntlLocale(...), ...)` olarak değiştir (plan'ın orijinal yaklaşımı; fonksiyonel olarak `toLocaleDateString` zaten doğru locale çıktısı verir).
- [ ] Vitest: tr-TR locale'de "17.01.2026" formatı, en-US'de "1/17/2026" formatı

---

## Phase 6 — TR bundle "TRY" → "₺" + kalan küçük sızıntılar

**Hedef:** TR message bundle'ındaki "TRY" literallerini "₺" ile değiştir + kalan küçük leak'ler.

### Subtasks
- [ ] `messages/tr/api.ts:91,93,97,99,101` — `{billedAmount} TRY` → `{billedAmount} ₺` (5 yer)
- [ ] `messages/tr/sections.ts:210` — `"Fiyat (TRY)"` → `"Fiyat (₺)"`
- [ ] `messages/tr/sections.ts:315` — `"Toplam İlaç Maliyeti (TRY)"` → `"Toplam İlaç Maliyeti (₺)"`
- [ ] `messages/tr/sections.ts:105` — `"Encode edilmiş"` → `"Kodlanmış"` (loanword fix)

---

## Out of Scope (doğrulanmış)

- **Backend error mesajlarının Türkçeleştirilmesi** — backend ayrı task.
- **Chat LLM yanıt dili** — server-side. Backend robust katmanlı sözleşme uygular: `prompts.py:19-44` MANDATORY system-prompt + locale-keyed prompt seed'leri (`messages/tr/chat.ts:41-58` "Türkçe yanıt verin" ile bitiyor). Client-side post-processing yok, frontend planı sahibi olmamalı. **Denetim: dışlama doğru.**
- **EN locale'nin düzeltilmesi** — sadece TR'ye odaklanıyoruz.
- **Dev-only invariant throw'ları** — `RoleProvider.tsx:57,65`, `LocaleProvider.tsx:88`, `theme.ts:19` (idiomatik programmer-error guard'ları, EN kalır).
- **AI chat-context plumbing (LOW)** — `patient/[id]/page.tsx:525,707` `activeTab="SUT Patient Workspace"`, `sutChatPageContext.ts:114,131` EN description'lar modele gidiyor, DOM'da görünmüyor. Stable routing key'e çevrilebilir ama kullanıcı-görünür değil.
- **Teknik kodlar/§ referansları** — `sut_section` (§4.2.14.C gibi), MEDULA `sonuc_kodu`'ları `font-mono` olarak kalır.

### Açık karar gerekli (Phase 3c)
Backend enum değerleri (`payment_method_kind` kararlı 5-değer enum HARİÇ): `medula_stage`, `violation_kind`, `source`, `claim_type`/care-setting — teknik kod olarak mı kabul edilecek yoksa çevrilecek mi? **`payment_method_kind` kararlı ve kullanıcı-iş-akışında olduğu için çevrilmeli** (Phase 3c'de). Diğerleri için explicit karar belgelenmeli.

---

## Verification (her phase sonunda)

- `npx tsc --noEmit` — type hatası yok
- `npx vitest run` — tüm testler yeşil
- Manuel: tarayıcıda TR locale'de her phase'in etkilediği ekranları kontrol et
- **Print testi (Phase 0):** TR locale'de print preview'da top-bar butonları görünmüyor mu kontrol et
- Hedef: **TR locale'de sıfır İngilizce kullanıcı-görünür metin** (teknik kodlar/§ referansları/dev-only invariant throw hariç)

## Execution order

**Phase 0** (metadata/CSS/config sızıntıları — en yüksek görünürlük) → **Phase 1** (API errors) → **Phase 2** (apiMessages fallback) → **Phase 3** (SutBillingReportSections + enum gap'leri) → **Phase 4** (hardcoded defaults) → **Phase 5** (`fmtDate` wire + barrel export) → **Phase 6** (TRY→₺ + küçük).

Her phase ayrı commit. Phase 0-1-2 en yüksek etki. Phase 3-4-5-6 daha küçük ama gözle görülür.

---

## v2 Değişiklik günlüğü (denetim → plan)

| # | Kaynak | Değişiklik |
|---|---|---|
| 1 | Mimari denetim | **Phase 5 düzeltildi:** `fmtDate` zaten var (`formatters.ts:41`); "oluştur" → "wire et + barrel export'a ekle (`index.ts:4`)" |
| 2 | Sızıntı denetimi | **Phase 0 eklendi:** `layout.tsx:40` meta (HIGH), `constants.ts:25-74` dup (MED), `globals.css:248` print selector (MED), `configContext.tsx:101,109` (MED) |
| 3 | Enum denetimi | **Phase 3c eklendi:** `payment_method_kind` (1797/1805), `claim_type`/care-setting (1792/1794/1802), `source` (1196) — v1 "out of scope" demişti, yanlıştı |
| 4 | Citation denetimi | `sutChat.ts:145` düzeltildi (aslında "No response received", "Could not reach API" değil) |
| 5 | Citation denetimi | `sutChat.ts:133` düzeltildi (SSE error-frame rethrow, "empty response" değil) |
| 6 | Mimari denetim | Phase 1 strateji notu: `ApiRequestError` (`apiClient.ts:39`) `code` alanı yok, ekle |
| 7 | Mimari denetim | Phase 3b: `:1486` severity bypass düzeltmesi eklendi (helper+label var, çağrılmıyor) |
| 8 | Chat denetimi | Out-of-scope "chat LLM dili" doğrulandı (server-side MANDATORY contract `prompts.py:19-44` + locale-keyed prompt seed) |
| 9 | Mimari denetim | "19 module" → "18 module (+ barrel)" |
| 10 | Mimari denetim | Dosya yolu notları: `useSutApi.ts` `components/tabs/sut/`, `sutChat.ts` `lib/api/` (aynı dizin değiller) |

---

## Implementation Review (2026-07-12)

### Durum: Tamamlandı ✅

Tüm 7 phase implement edildi. `npx tsc --noEmit` temiz, `npx vitest run` 39 dosyada 160/160 test yeşil.

### Yapılan değişiklikler (25 dosya, +402/-142)

**Phase 0 — Metadata/CSS/config (4 sızıntı):**
- `layout.tsx`: `generateMetadata()` artık `bilun:locale` cookie'sinden locale okuyup TR catalog'tan meta description çekiyor (EN sabit yerine).
- `AppTopBar.tsx`: `<header>`'a stable `data-sut-topbar` attribute eklendi.
- `globals.css`: print selector `header[aria-label="Bilun application bar"]` → `header[data-sut-topbar]` (TR'de artık eşleşiyor, top-bar print'e sızmıyor).
- `page.tsx`: `activeMeta.label` (EN) → locale-aware `activeTabLabel` (`t()` üzerinden).

**Phase 1 — API errors (10 throw):**
- `ApiRequestError`'a `code` alanı eklendi (`network_error`/`http_error`/`invalid_json`).
- `apiClient.ts` + `sutChat.ts`: tüm İngilizce `throw new Error()` string'leri `getModuleLocale()` + `translate()` pattern ile lokalize edildi.
- `common.apiError.*` ve mevcut `chat.api.*` key'leri kullanılıyor.

**Phase 2 — apiMessages.ts:**
- `try*`/public fonksiyon split: her helper'ın internal `tryTranslate*` (null döner) + public wrapper.
- `translateApiText` dispatcher artık `try*` fonksiyonlarını kullanıyor (daha temiz match-detection).
- **Tasarım kararı (testlerden öğrenilen):** Placeholder yerine pass-through korundu. Backend meşru içerik (çoğu zaten Türkçe) kaybı önlemek için tanınmayan string'ler olduğu gibi geçiyor. Placeholder'lar yalnızca `unknown*` bundle key'leri olarak eklendi ama ana davranış pass-through.

**Phase 3 — SutBillingReportSections.tsx (13+ alan):**
- Tarihler (4): `service_date`/`amendment_effective_date`/`last_use_date` → `fmtDate()`.
- Enum'lar: `severity` (2 yer) → `getSutSeverityLabel()`; `payment_method_kind` (2 yer) → yeni `getPaymentMethodKindLabel()` helper.
- Raw text: `source`/`hata_mesaji`/`message_tr`/`detail`/`hit.message`/`claim_type`/`care_setting`/`medula_stage` → `translateApiText()`.
- Yeni `getPaymentMethodKindLabel` (`sutLabels.ts`) + `api.paymentMethodKind.*` key'leri (5 değer).

**Phase 4 — Hardcoded defaults:**
- `useSutApi.ts`: `DEFAULT_ABORT_MSG`/`DEFAULT_ERROR_MSG` static const → lazy `defaultAbortMessage()`/`defaultErrorMessage()` (call-time locale resolution).
- `recommendedActions.ts`: surface/kind fallback'ları → `t("common.unknownSurface")`/`t("common.unknownKind")`.
- `sutLabels.ts`: `getSutRecommendedActionLabel` fallback → `t("labels.sut.unknown")`.

**Phase 5 — fmtDate:**
- `lib/i18n/index.ts` barrel export'a `fmtDate` eklendi.
- Yeni `fmtDateTime()` helper (`formatters.ts`) — rejection timestamp'lar için tarih+saat.
- 4 call site wire edildi: `BundledConsumablesSection`, `ProseInventoryPanel`, `MedulaRejectionQueueTab` (timestamp), `TemporalPriceSection` (local `fmtDate` kaldırıldı).

**Phase 6 — TRY → ₺:**
- `messages/tr/api.ts`: 5 yer `{amount} TRY` → `{amount} ₺`.
- `messages/tr/sections.ts`: "Fiyat (TRY)" → "Fiyat (₺)", "Toplam İlaç Maliyeti (TRY)" → "Toplam İlaç Maliyeti (₺)", "Encode edilmiş" → "Kodlanmış".

### Önemli tasarım kararları

1. **Pass-through > Placeholder:** Phase 2'de testler gösterdi ki backend `message`/`detail` alanları genellikle meşru, çeşitli içerik taşıyor (bazen Türkçe). Generic placeholder ("Detaylar kullanılamıyor") kullanıcı için bilgi kaybı yaratıyordu. Bu yüzden `translateApiText` tanınmayan string'leri olduğu gibi geçiriyor. Placeholder yalnızca `unknown*` key'leri olarak bundle'da mevcut (gelecek kullanım için).

2. **Enum helper'ları (Phase 3c):** `payment_method_kind` kararlı 5-değer enum olduğu için `getPaymentMethodKindLabel` + bundle key'leri eklendi. `severity` helper+label zaten vardı, sadece çağrılmıyordu — 2 yerde wire edildi. `medula_stage`/`claim_type`/`care_setting`/`source` free-form olduğu için `translateApiText` ile sarıldı.

3. **`configContext.tsx` (Phase 0.3) dışlandı:** `state.error` `useConfig()` public API'sinden dönmüyor (sadece `config`). Bugün render edilmiyor, latent risk. Over-engineering önlemek için dokunulmadı (plan'daki "dev-only olarak kabul et" seçeneği).

### Verification
- `npx tsc --noEmit`: ✅ temiz
- `npx vitest run`: ✅ 39 dosya, 160/160 test yeşil
- Manuel print testi önerilir (Phase 0 CSS selector değişikliği)
