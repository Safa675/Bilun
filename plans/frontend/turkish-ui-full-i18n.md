# Plan: Türkçe UI’yi Tamamen Türkçe Yap — İngilizce Kalıntı Temizliği

**Date:** 2026-07-22  
**Status:** Done — Phases 0–5 implemented (2026-07-22)  
**Goal:** `bilun:locale=tr` iken kullanıcıya görünen metin %100 Türkçe olsun (izin verilen teknik tokenler hariç).  
**Method:** Headless Chromium (Playwright) ile TR cookie/localStorage zorlanarak login → home / patient / compliance / revenue / reference-tools / rule-database tarandı; DOM text + aria/title/placeholder çıkarıldı. Artefaktlar: `scripts/i18n/tr-ui-english-findings.json`, `scripts/i18n/tr-audit-*.png`, audit script `scripts/i18n/audit-tr-ui-english.mjs`.

## Verdict (crawl sonucu)

| Alan | Durum |
|---|---|
| Üst nav, rol, çıkış, dil anahtarları (`shell.ts` / sekmeler) | Zaten TR |
| Hasta fatura raporu bölüm başlıkları / finding-type rozetleri | Çoğunlukla TR |
| **Asıl İngilizce** | Backend `detail` / `note` / `rule_source` stringleri UI’ya ham düşüyor |
| Kind başlıkları | Eksik map → snake_case humanize (`Yatak Puani Standard Bed`) |
| Chat | Ham OpenRouter/API 401 İngilizce |
| Rule Database / Revenue bazı açıklamalar | EN veya TR+EN karışık (uplift loanword) |

**İzin verilen (Türkçe sayılır / çevrilmez):** `SGK`, `SUT`, `DRG`, `MEDULA`, `ICD-10`, `EK-*`, `§…`, prosedür/malzeme kodları, `F-SENTETIK-*` / hasta ID’leri, sayısal tutarlar.

---

## Inventory — görülen İngilizce (filtre sonrası ~30 unique)

### A. Backend not / detail / rule_source (en yüksek hacim) — patient + compliance

| Örnek (görünen) | Kaynak tipi |
|---|---|
| `Standart yatak (510010): 16 billable bed-day(s) (gross LOS …)` | `yatak_puani` opportunity `detail` |
| `Yatak Puani Standard Bed` | kind=`yatak_puani_standard_bed` (i18n map yok → humanize) |
| `Catalog MIAT period: 10 yıl — verify interval vs patient history` | materials MIAT `note` |
| `EK-3C-1 — tıbbi uygunluk (medical appropriateness) required before SGK submission` | materials pre-auth `note` (TR+EN karışık) |
| `Marked as package component and billed separately — invoice/package flag…` | Fix 3 package_flag `note` (bilerek EN yazıldı) |
| `Claim F-… is billed correctly as package…` | billing_strategy `detail` |
| `Procedure 608550 must use package billing…` | compliance_violation `detail` |
| `SUT §1.8.3(2) material copay reference rate: 20%` | copay rate_corrections `detail` |
| `SUT §1.8.5(7) + EK-1/A chronic disease copay exemptions · … emergency visit copay waiver…` | exemption `rule_source` / category evidence |
| `EK-1A, visit type (acil/koruyucu), SGK status, occupational context` | compliance UI helper / evidence label |

**Kod gerçeği:** `SutBillingReportSections.tsx` birçok yerde `item.detail` / `material.note` **doğrudan** basıyor; `translateApiText` yalnızca bazı yüzeylerde çağrılıyor. `apiMessages.ts` ise yalnızca birkaç validation regex’ini çeviriyor — yatak/MIAT/strategy/copay pattern’leri yok.

### B. Chat / LLM gateway

| Örnek | Not |
|---|---|
| `⚠️ API error 401: {"error":{"message":"User not found.","code":401}}` | Tüm sayfalarda (copilot). Ham provider JSON; kullanıcıya TR hata mesajı + kod gösterilmeli. |

### C. Rule Database & Revenue sekmeleri

| Örnek | Not |
|---|---|
| `Registry is implemented; 1,191 rows encoded…` | Rule DB coverage / registry prose EN |
| `L4.4 export subset is 84 deontic…` | Aynı |
| `Aggregated per-patient DRG unbundling findings from exact claim lines…` | Revenue açıklama EN |
| `Gazette Repricing` | Etiket EN (veya map eksik) |
| `surcharge` | Motor/anahtar adı UI’ya sızmış |
| `… uplift (6 pilot kural)` / `Seans, DRG, malzeme ve işlem uplift tespitleri.` | TR metinde İngilizce loanword |

### D. Kasıtlı teknik (plan kapsamında **değil** — allowlist)

Kod path’leri (`src/bilun/...`), ham JSON debug, tebliğ madde numaraları, katalog kodları.

---

## Root causes (3 katman)

1. **Backend locale-agnostic English prose** — generator’lar (claim_yatak_puani, claim_materials, billing strategy, copay rule_source) tek dil EN string üretiyor.  
2. **Frontend translation gap** — `translateApiText` coverage dar; birçok tablo hücresi translate etmeden render.  
3. **i18n map / loanword gap** — kind keys eksik (`yatak_puani_standard_bed`); TR mesajlarda `uplift` gibi EN kelimeler; Rule DB metinleri EN kalmış.

Missing-key fallback (`translate` → key string) bu crawl’da ana sorun değildi; asıl sorun **değerin zaten EN olması**.

---

## Approach (önerilen)

**Hibrit — frontend-first çeviri + backend TR template’lere kademeli geçiş.**

| Faz | Ne | Neden |
|---|---|---|
| **0** | Allowlist + regresyon crawl (Playwright script CI’ya) | “Tamamen TR” ölçülebilir olsun |
| **1** | Frontend: tüm kullanıcıya dönük `detail`/`note`/`rule_source` path’lerinde `translateApiText` | Hızlı, cache rebuild’siz |
| **2** | `apiMessages.ts`: bilinen EN pattern → TR mesaj anahtarları (yatak, MIAT, package claim, procedure must package, package_flag, preauth, copay reference rate, exemption rule_source parçaları) | Tek merkez |
| **3** | Kind/surface map tamamla + TR loanword temizliği (`uplift`→`artış`/`fırsat`) | Önerilen işlemler + group description |
| **4** | Chat hata yüzeyi TR | 401/provider hataları |
| **5** | Rule DB / Revenue EN prose → `messages/tr` | Sekme içerikleri |
| **6** (opsiyonel sonraki) | Backend locale-aware note üretimi (`Accept-Language` / `locale=tr`) | Uzun vadede `translateApiText` yükünü azaltır |

**Neden önce frontend pattern çevirisi?** Canlı cache zaten EN notları taşıyor; backend’i TR’ye çevirmek cache rebuild ister ve EN istemcileri kırabilir. Pattern map hem eski cache hem yeni API için çalışır.

---

## Subtasks

### Phase 0 — Ölçüm kapısı
- [ ] 0.1 Allowlist dokümante et (SGK/SUT/DRG/MEDULA/ICD/EK-/§/kodlar/ID’ler)
- [ ] 0.2 `scripts/i18n/audit-tr-ui-english.mjs`’i stabilize et (Title-Case TR false-positive filtre)
- [ ] 0.3 CI veya pre-push opsiyonel job: TR crawl → unique EN = 0 (allowlist dışı)
- [ ] 0.4 Baseline JSON’u `scripts/i18n/tr-ui-english-findings.json` olarak sakla (bu planın eki)

### Phase 1 — Render path’lerini kapat
- [ ] 1.1 `SutBillingReportSections.tsx`: `item.detail` / `material.note` / strategy note hücrelerinde `translateApiText` zorunlu
- [ ] 1.2 Compliance / alerts / revenue bileşenlerinde ham `rule_source` metinlerini `translateApiText` veya parçalı çeviri
- [ ] 1.3 Unit test: bilinen EN fixture → TR çıktı (`locale=tr`)

### Phase 2 — `apiMessages` pattern kataloğu (öncelik sırası)
- [ ] 2.1 Yatak: `billable bed-day(s)`, `gross LOS`, `surgery day`, `bundled into EK-2/C package`, `inclusive LOS…`
- [ ] 2.2 Materials: MIAT catalog note; pre-auth “medical appropriateness required…”; package_flag Fix-3 note; EK-3B-1 note
- [ ] 2.3 Strategy: `Claim … is billed correctly as package…`; `Procedure … must use package billing…`
- [ ] 2.4 Copay: `material copay reference rate`; exemption `rule_source` cümleleri (chronic / emergency / preventive / work accident / Vatani Hizmet / GSS…)
- [ ] 2.5 TR+EN mesaj dosyaları (`messages/{tr,en}/api.ts`) paralel anahtarlar
- [ ] 2.6 Regex testleri: her pattern için golden EN → TR

### Phase 3 — UI dictionary / loanword
- [ ] 3.1 `yatak_puani_standard_bed` (+ diğer `*_standard_bed` / bed kinds) → `billing.recommendedActions.kinds.*`
- [ ] 3.2 `patient.billingGroups.opportunitiesDescription` vb. `uplift` → Türkçe (`artış` / `fırsat tespitleri`)
- [ ] 3.3 `Gazette Repricing` / `surcharge` sızıntılarını TR etikete bağla
- [ ] 3.4 Humanize fallback’i TR locale’te İngilizce Title-Case üretmeyecek şekilde yumuşat (veya unknownKind TR “Bilinmeyen tür”)

### Phase 4 — Chat hataları
- [ ] 4.1 Provider/API hatalarını kullanıcıya: `Sohbet şu an kullanılamıyor (kod 401).` + opsiyonel daraltılmış teknik detay (dev rolünde)
- [ ] 4.2 `User not found` / network / 5xx için `messages/tr/chat.ts` (veya mevcut chat mesaj modülü)

### Phase 5 — Rule Database & Revenue EN prose
- [ ] 5.1 Registry / L4.4 / DRG unbundling açıklama metinlerini TR mesajlara taşı
- [ ] 5.2 Hardcoded EN string grep (`frontend/src` + rule-db components) → `t(...)`
- [ ] 5.3 Playwright ile `rule-database` + `revenue` sayfalarını yeniden tara

### Phase 6 — (Sonraki epic) Backend locale-aware notes
- [ ] 6.1 Note generator’lara `locale: "tr"|"en"` 
- [ ] 6.2 API’nin `Accept-Language` / query locale kabulü
- [ ] 6.3 Cache rebuild sonrası Phase 2 regex’leri regressiyon olarak kalır (geriye dönük EN cache)

---

## Out of Scope
- İngilizce UI’nin bozulması (EN locale birebir korunacak)
- Tıbbi/resmi kod ve ek adlarının “çevrilmesi” (EK-3B-1, 510010, MEDULA alan adları)
- Chat modelinin Türkçe cevap kalitesi (ayrı prompt/locale işi)
- Bu planda kod yazımı — **önce onay**

---

## Definition of done
1. Playwright TR crawl (`audit-tr-ui-english.mjs`) allowlist dışı **0** unique İngilizce string  
2. SENTETIK-HASTA-0001 önerilen işlemler: yatak satırı başlığı TR; not TR; materials/strategy notları TR  
3. Compliance exemption `rule_source` satırları TR  
4. Chat 401 kullanıcıya TR  
5. Rule DB / Revenue görünür EN prose kalmamış  
6. `vitest` apiMessages + recommendedActions label testleri yeşil  
7. EN locale spot-check: mevcut EN metinler regresyonsuz

## Risks
- Regex kırılganlığı (backend note formatı değişince) → golden test + Phase 6’ya geçiş  
- Aşırı çeviri (kod/ek adları) → allowlist  
- Cache’deki eski EN notlar → Phase 2 şart (frontend map olmadan rebuild yetmezdi; rebuild sonrası da EN generator devam ediyor)

## Open questions
1. **MEDULA / tebliğ alan adları** (`katilimPayindanMuaf`) UI’da TR açıklama + parantezde ham alan mı, yoksa sadece TR mi?  
2. **Chat ham JSON** hiç gösterilsin mi (yalnızca `dev` rolünde)?  
3. Phase 6 (backend TR notes) bu sprint’te mi, yoksa Phase 1–5 yeterli mi?

## Review
**2026-07-22 — Phases 0–5 complete**

- Playwright TR crawl: `findingCount=0` / `unique=0` (`scripts/i18n/tr-ui-english-findings.json`)
- Frontend: `translateApiText` on billing detail/note/rule_source paths; expanded `api.billingProse` + `api.llmError`; kind `yatak_puani_standard_bed`; labels for `gazette_repricing` / `ruleCategory.surcharge`; SectionBrowser category chips; MethodologyBadge on revenue tab
- Backend: LLM stream errors use `_llm_http_error_message` (no raw JSON); Rule DB `description_tr` / `footnote_tr` loanword cleanup
- Phase 6 deferred (backend locale-aware note generation)
- Open Q defaults: chat shows sanitized TR errors (no provider JSON); Phase 6 not in this sprint
