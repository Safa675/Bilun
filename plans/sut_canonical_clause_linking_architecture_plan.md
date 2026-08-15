# Plan: Kanonik SUT Fıkra Bağlama ve Uçtan Uca Yapısal Mevzuat Mimarisi (Canonical SUT Clause Linking Plan)

**Date:** 2026-08-15
**Revision:** v2 (değerlendirme sonrası revize — 2026-08-15)
**Status:** Architecture Proposal & Migration Plan (Ready for Review)
**Target:** `src/bilun/domain/{billing, prose_rules, sut, optimization}/`, `src/bilun/api/`, `frontend/src/{lib, components}/`

---

## 0. Revizyon Notu (v1 → v2)

v1 planı 4 paralel denetimle dosya:satır bazında doğrulandı. Temel teşhis doğrudur:
faturalama bulguları (waiver, rate correction, action, line decomposition) yapısal fıkra
kimliği taşımamaktadır. Ancak v1 aşağıdaki nedenlerle uygulanamazdı; v2 bunları düzeltir:

1. **Kimlik modeli Track E ile çelişiyordu.** v1 `clause_id` anahtarlı bir sözleşme öneriyor ve
   `"sut_2024_03_24_1_8_5_8"` biçiminde örnekler veriyordu — bu biçim repoda yalnızca planın
   kendisinde geçmektedir. Repo, Track E (#58–#63: `4163ade`, `0757424`, `eecc2ad`, `d2d8d08`)
   ile pozisyonel `clause_id`'yi (C*) public sözleşmeden **kaldırmıştır**; kalıcı public kimlik
   `clause_key` (coord#hash) + `clause_coordinate`'tir (`src/bilun/domain/sut/rules_catalog.py:747-748`,
   `src/bilun/api/schemas.py:886-902`). v2 sözleşmesi `clause_key` tabanlıdır.
2. **Var olan altyapı sıfırdan kuruluyordu.** `rules_catalog.get_clause()` zaten bir lookup
   servisidir (`rules_catalog.py:950-996`); `rule_registry.py` (47 kayıt) waiver'ların aynı
   `rule_id`'lerini kullanır (`rule_registry.py:52`); 45 manifest (`data/gazette/prose_manifests/`)
   kural→fıkra bağlantısını zaten taşır; `GET /api/rules/clauses/{clause_id}` + frontend
   `getClause()` (`frontend/src/lib/api/sut.ts:784-786`) zaten ayaktadır. v2 bunları yeniden kullanır.
3. **Devam eden (uncommitted) çalışmayla sıfır toplamlı çakışma.** v1'in Aşama 3'te silmeyi
   önerdiği `resolveCopayIlaveStatus`, HEAD'de yoktur; çalışma ağacındaki copay UI diff'inin
   (`plans/frontend/copay_exemption_ui_clarity_plan.md` uygulaması) ta kendisidir. v2, Aşama 0
   ile mülkiyeti netleştirir: hücrenin karar sahibi backend'dir; UI affordance'ları korunur.
4. **Mevcut durum analizindeki sayısal hatalar düzeltildi** (aşağıda §1).
5. **Uygulama sırasında corpus doğrulaması (§1.9 düzeltmesi):** v1 ve clarity planının atıf
   yaptığı "SUT §2.4.4" ilave ücret dayanağı corpus'ta YANLIŞTIR — `2.4.4` satırı bir başlıktır
   ("Diğer bazı tetkik ve tedavi yöntemleri") ve hiçbir `2.4.4.*` alt fıkrası ilave ücret metni
   içermez. İlave ücret corpus'ta **§1.9** altındadır: `1.9.1` (alınması — kapsam EK-2/B + EK-2/C
   fiyatlarıdır, dolayısıyla EK-4/A ilaçları yapısal olarak yasaktır; kanuni dayanak 5510 md.73),
   `1.9.3.a` (acil haller), `1.9.3.ç` (kanser tedavisi). Uygulama bu kanonik koordinatlara
   bağlanmıştır (in-force clause_key'ler: `1.9.1#52ade285`, `1.9.3.a#67236cf6`, `1.9.3.ç#726ecd58`).

---

## 1. Mevcut Durum Analizi (Doğrulanmış ve Düzeltilmiş)

### 1.1 Backend Faturalama & Muafiyet Motoru — teşhis DOĞRU, boşluk gerçek

- `WaiverResult` (`src/bilun/domain/billing/copay_line_waivers.py:36-50`): serbest metin `detail`
  + ham string `sut_section_id` (`"1.8.5(7)"` :176, `"1.8.2.(3)"` :244/:262/:283, `"1.8.5(8)"` :204).
  `clause_id`/`rule_type`/`statutory_law` yok — **ancak** yarı-yapısal `rule_id`, `annex`,
  `exemption_ground` mevcut (`:53-60` `to_rate_correction()`). Geçiş bu alanların üzerine inşa edilir.
  Waiver fonksiyonları: `waiver_ek1a_muayene` (:148), `waiver_inpatient_drug` (:187),
  `waiver_ek4d_drug` (:217), `waiver_composite_procedure` (:312), `waiver_composite_drug` (:347).
- `claim_copay.py`: `rate_corrections` ham dict'ler üretir (`"sut_section": "1.8.5(7)"` :145-153,
  `"1.8.2.(1)"` :285, `"1.8.3.(2)"` :297); `_COPAY_RULE_SOURCE` serbest metin (:36-39).
- `line_decomposition.py`: `decompose_drug_line` (:144-155) upstream `surcharge_rate`'i **sorgusuz**
  ilave ücrete çevirir (`decompose_line` :102-105). SUT §1.9.1 / 5510 md.73 ilaç yasağı hiçbir yerde
  uygulanmaz (`domain/billing/` genelinde `5510` grep'i boş). `decompose_procedure_line` (:133-141)
  kanser/acil muafiyeti içermez; tanı bilgisi bu katmana hiç gelmez.
- `billing_actions.py`: tek copay aksiyon satırı `is_exempt`'e bağlıdır (:98-114);
  `action_id="copay:ek1a_exemption_review"` (:107) ve `sut_section_id="1.8.5(7)"` (:112) sabittir.
  **v1'in olduğundan büyük görünen boşluk:** EK-4/D, acil, iş kazası, yeşil kart waiver'ları hiç
  aksiyon satırı üretmez — sorun yalnız "yanlış kimlik" değil "eksik emisyon"dur.
- API: `GET /billing-report/{patient_id}` (`src/bilun/api/routes/billing.py:122`) `dataclasses.asdict`
  ile serileştirir (:50); `CopayOptimizationResponse` (`schemas.py:230-248`) `rate_corrections: list[dict]`
  (:247) taşır; hiçbir billing yüzeyinde yapısal fıkra referansı yoktur. Şema `extra="allow"`
  (:203) olduğundan ek alanlar additive olarak güvenle geçer. Satır-bazında `LineDecomposition`
  hiç dışa açılmaz (yalnız agregat `line_decomposition_status`).

### 1.2 Backend Prose Kuralları — mekanizma DOĞRU, sayılar ve atıflar DÜZELTİLDİ

- `src/bilun/domain/prose_rules/` **52** `.py` dosyası içerir (v1: 42). Yalnız **~19** dosya
  `detail`'i doğrudan f-string'den atar; 40 dosyada f-string geçer. Kullanıcıya dönük metnin önemli
  bölümü Python'da değil `data/gazette/prose_rules/` altındaki **26 JSON kural setinin**
  `denial_tr`/`message_tr` alanlarındadır.
- `common_billing_errors.py`: 16 kural DOĞRU; `_SUT_SECTION_ID = "tablo_15"` (:56, 16 kullanım noktası).
  **Düzeltme:** bu sahte bir SUT maddesi değil, bilinçli bir El Kitabı referansıdır (docstring :3:
  "El Kitabı Tablo 15 — 24 Most Common Outpatient Billing Errors"). Çözüm SUT maddesi uydurmak
  değil, **kaynak tipini (provenance) dürüstçe işaretlemektir**.
- `diagnosis_coding_quality.py`: `"tani_kodlama_kalitesi"` repoda **hiç yoktur**; gerçek değer
  `"elkitabi_diagnosis_coding"` (:39). `"clinical lab capture completeness"` bu dosyada değil
  `lab_capture_gap.py:115`'tedir.
- `traffic_accident_billing.py`: bölüm kimliği `"2-09"` değil `"algoritma_2_09"` (:57);
  `_RULE_REFERENCE = "2918 Sayılı KKT Madde 98 / Algoritma Rehberi §2-09"` (:58). v1'in bu modüle
  §1.8.5 atfetmesi yanlıştır — §1.8.5 copay muafiyet katmanına aittir
  (`domain/optimization/copay_exemption_rules/occupational.py:34,43`, `patient_status.py:43,55,76`).
- Ek kanonik olmayan kimlik: `transplant_package_scope.py:38` (tam cümle bölüm kimliği).
- JSON setler: `treatment_pricing_2_4.json` (202 kural), `dental_2_4_1.json` (19),
  `material_bundling_prose.json` (83 — 83/83 `message_tr` içine § referansı gömülü),
  `drug_combination_4_2.json` (53). Kurallarda kanonik kimlik alanı yoktur (`sut_section` +
  `gate_b_sources` + top-level `sut_anchors` vardır). **Ancak** bağlantı bir üst katmanda mevcuttur:
  `data/gazette/prose_manifests/*_manifest.json` (45 dosya, `canonical-v1`) `encoded_clause_ids` +
  `clause_traces[].rule_id` taşır.
- Veri akışı **iki ayrı yoldan** geçer: (A) doğrulama — `engine.analyze_claim`
  (`billing/engine.py:140`) → `rule_engine.py:438`; (B) hasta raporu — `patient_report.py:58` →
  `BillingActionReport` (`billing/types.py:743`). `ProseRuleTrace` (`prose_rules/types.py:21-28`)
  `rule_id, sut_section, rule_set_id, detail` taşır; `rule_source` ~17 `_PROSE_RULE_SOURCE`
  sabitinden serbest metin olarak gelir (`billing/types.py:240,288,299,...`).
- Mevcut kanonik altyapı (v1 hiç anmıyordu): `rule_registry.py` (`RuleRegistryEntry` :33,
  `_BASE_RULE_REGISTRY` :52, 47 kayıt; `sut_section_prefixes`, `annex_refs`, `coverage_status`),
  `data/gazette/sut_clause_coverage.parquet` (**4.757 satır** — v1'in "10.000+" iddiası yanlış;
  corpus `sut_clauses.parquet` 8.361 satır, tümünde `text_tr` dolu).

### 1.3 Frontend Heuristic & Regex Katmanı — teşhis DOĞRU, bir kritik provenance uyarısı

- `billingReportFields.ts`: `resolveCopayIlaveStatus` (:100) ve `copayCorrectedPayableTry`
  **yalnızca uncommitted çalışma ağacında vardır** (HEAD `75ce764`'te yoktur). Heuristikler gerçek:
  `code.startsWith("A")` (:121), `diseaseCode.startsWith("C")` / `disease.includes("kanser")`
  (:134/:137), `ground.includes("acil")` (:151). Committed olan `copayClaimScopedAnnexLabels`
  (:189-210) elle kodlanmış `"EK-1A"`/`"§1.8.5(8)"`/`"EK-4D"` etiketleri taşır.
- `apiMessages.ts`: 20+ değil, **28** regex tabanlı İngilizce metin ayrıştırıcısı (ör. :104, :131,
  :208, :224, :258-299, :314/:327/:346, :375-461, :485-581).
- `sutRegulatorySources.ts`: `EK_ANNEX_PATTERN` (:25), `parseEkAnnexLabels` (:32-50),
  elle `ek2b → EK-2B` eşlemeleri (:53-72).
- `recommendedActions.ts`: `COMPLIANCE_SURFACES` (:14-18), `OPPORTUNITY_SURFACES` (:20-32),
  `INFORMATIONAL_SURFACES` (:34-37); fallback'te sabit `"1.8.5(7)"`.
- `SutClauseDrawer.tsx` yoktur; en yakın UI `ClauseBrowserPanel.tsx:378` `ClauseCard` (satır içi
  `text_tr`). Backend ucu hazır: `GET /api/rules/clauses/{clause_id}` (`api/routes/rules.py:237`)
  + frontend `getClause()` (`api/sut.ts:784-786`).
- Test altyapısı: vitest kurulu (`frontend/package.json:32`), `SutBillingReportSections.test.tsx`
  mevcut (647 satır); **npm `test` script'i yoktur** — komut `npx vitest run`'dır.

---

## 2. Kilit Kararlar (Değerlendirme ile Sabitlendi)

- **D1 — Kimlik:** Public referans `clause_key` (coord#hash) + `clause_coordinate` taşır;
  pozisyonel `clause_id` (C*) yalnızca internal join anahtarı olarak kalır (Track E kararı).
  `clause_key` satır-benzersiz DEĞİLDİR (4.647 benzersiz / 4.757 satır) → çözümleme
  `rules_catalog.get_clause()`'daki `is_in_force` ayrıştırmasını kullanır (`rules_catalog.py:950-996`).
- **D2 — Metin çoğaltma yok:** Referans nesnesi elle yazılmış `legal_basis_tr/en` metinleri taşımaz.
  Görüntülenecek mevzuat metni corpus'un `text_tr` alanından (`sut_clauses.parquet` /
  `sut_clause_coverage.parquet`) mevcut uç nokta üzerinden çekilir. Elle metin = drift kaynağı.
- **D3 — İlave ücret hücresinin mülkiyeti backend'dedir.** Devam eden UI çalışmasının
  affordance'ları (Düzeltilmiş SGK Ödemesi sütunu, vezne iade uyarısı, tooltip) korunur;
  `resolveCopayIlaveStatus` backend alanlarını render eden saf bir fonksiyona dönüştürülür.
  Backend durum kodları, uncommitted testlerin zaten kullandığı adları alır:
  `drug_prohibited`, `cancer_exempt`, `emergency_exempt` (churn minimum).
- **D4 — Yeniden inşa yok:** `rules_catalog`, `rule_registry`, `prose_manifests/clause_traces`
  ve `/api/rules/clauses` uç noktası genişletilerek kullanılır.
- **D5 — Provenance taksonomisi:** Kanonik olmayan bölüm kimlikleri "sahte SUT maddesi" değil,
  farklı kaynak tipleridir. Sözleşme `source_type` alanı taşır:
  `sut_clause | el_kitabi | algoritma_rehberi | kanun | rehber`.

---

## 3. Ortak Veri Sözleşmesi: `SutClauseReference`

Backend'den dönen her waiver, rate correction, aksiyon satırı ve ilave ücret durumu bu nesneyi taşır.
`RuleClause` (`src/bilun/api/schemas.py:887-926`) şekliyle hizalıdır.

```python
# src/bilun/domain/sut/clause_reference.py (yeni modül — v1'in önerdiği models.py yoktur)
@dataclass(frozen=True)
class SutClauseReference:
    clause_key: str            # Örn: "1.9.3.a#67236cf6" (coord#hash) — implementation anında
                               # rules_catalog.get_clause() ile coordinate'ten çözümlenir; hash elle yazılmaz.
    clause_coordinate: str     # Örn: "1.9.3.a", "1.8.5.(8)" — insan okunur atıf
    source_type: str           # "sut_clause" | "el_kitabi" | "algoritma_rehberi" | "kanun" | "rehber"
    rule_type: str = ""        # "COPAY_WAIVER" | "SURCHARGE_PROHIBITION" | "PACKAGE_MANDATE" | ...
    annex: str = ""            # Örn: "EK-1/A", "EK-4/D"
    statutory_law: str = ""    # Yalnız source_type="kanun" veya SUT dışı kanun atıfı varsa
                               # Örn: "5510 Sayılı Kanun Madde 73", "2918 Sayılı Kanun Madde 98"
```

```typescript
// frontend/src/lib/api/sut.ts yanına (mevcut RuleClause tipiyle hizalı)
export interface SutClauseReference {
  clause_key: string;
  clause_coordinate: string;
  source_type: "sut_clause" | "el_kitabi" | "algoritma_rehberi" | "kanun" | "rehber";
  rule_type?: string;
  annex?: string;
  statutory_law?: string;
}
```

Görüntüleme kuralları:
- Fıkra metni: `GET /api/rules/clauses/{clause_key}` → `RuleClause.text_tr` (mevcut uç nokta,
  `clause_display_text()` mülga/in-force işlemeyle render eder).
- Kanun atıfları (`statutory_law`) metin değil etikettir; kanun metni kapsam dışıdır.
- `effective_date` / gazete numarası referans nesnesine konmaz; gerekiyorsa drawer, corpus/meta
  verisini mevcut uç noktadan gösterir.

---

## 4. Aşamalı Geçiş Yol Haritası

### Aşama 0 — Çakışma Çözümü ve Sözleşme Dondurma (ön koşul)

- [ ] Kararın kaydı: ilave ücret hücresinin kararı backend'e aittir (D3). Devam eden uncommitted
      diff bu haliyle merge EDİLMEZ.
- [ ] Devam eden diff'ten korunacaklar: `copayCorrectedPayableTry`, "Düzeltilmiş SGK Ödemesi"
      sütunu, vezne iade uyarı kutusu, tooltip affordance'ı, ilgili i18n anahtarlarının
      UI kısımları (`correctedPayable*`, `cashierRefundNotice`).
- [ ] Devam eden diff'ten refactor edilecekler: `resolveCopayIlaveStatus`'un prefix/substring
      heuristikleri (:121, :134, :137, :151) → Aşama 3'te backend alanı render'ına dönüşür;
      i18n içine gömülü "SUT §2.4.4 / 5510 md.73" sabit metinleri (doğrusu §1.9.1/§1.9.3 — bkz.
      Revizyon Notu 5) → backend `clause_ref`'ten türetilir.
- [ ] Bu planın sözleşmesi (§3) freeze edilir; Aşama 1 bunun üzerine inşa edilir.

### Aşama 1 — Backend Faturalama: Kanonik Bağlama + §1.9 İlave Ücret Kuralları

- [ ] `src/bilun/domain/sut/clause_reference.py`: `SutClauseReference` dataclass (§3'teki şekil).
- [ ] `clause_key` çözümleme yardımcısı: coordinate → `clause_key` dönüşümü için
      `rules_catalog.get_clause()` kullanılır; hiçbir yerde hash elle kodlanmaz, pozisyonel C* public'e çıkmaz.
- [ ] `line_decomposition.py`:
  - `decompose_drug_line` (:144): ilaç satırında ilave ücret **kural olarak yasaktır**
    (SUT §1.9.1 + 5510 md.73 — kapsam EK-2/B + EK-2/C fiyatlarıdır; EK-4/A ilaçları yapısal
    olarak dışarıdadır) → satır her koşulda `drug_prohibited` durumu + `1.9.1` `clause_ref`
    ile annotat edilir; para matematiği değişmez, yasak bulgusu yapısal olarak görünür olur.
  - `LineDecomposition`'a `ilave_ucret_status` (`drug_prohibited | cancer_exempt | emergency_exempt |
    applicable | none`) ve `surcharge_clause: SutClauseReference | None` eklenir.
  - Kanser/acil prosedür muafiyeti: tanı bilgisi `ProcedureClaimLine`'da yoktur; mevcut yapısal
    muafiyet çıktıları kullanılır (`exemption_range` C00-C97/C90 → `cancer_exempt`;
    `exemption_ground` acil/iş kazası → `emergency_exempt`; clause_ref `1.9.3.a` (acil) /
    `1.9.3.ç` (kanser) — §1.9.3 "ilave ücret alınmayacak sağlık hizmetleri" bentleri).
    Yeni string eşleştirme YAZILMAZ — `domain/optimization/copay_exemption_rules/` çıktileri tüketilir.
- [ ] `copay_line_waivers.py`: `WaiverResult`'a `clause_ref: SutClauseReference | None` eklenir.
      Mevcut `rule_id` alanları (`copay_exemption_ek1a` vb.) `rule_registry.py:52+` kayıtlarıyla
      aynı anahtardır — eşleme `rule_registry` + manifest `clause_traces` üzerinden kurulur;
      ham `sut_section_id` string'leri `clause_coordinate` ile değiştirilir.
- [ ] `claim_copay.py`: `rate_corrections` dict'lerine yapısal `clause_ref` + `rule_type` eklenir
      (:145-153, :285, :297 noktalarından başlayarak).
- [ ] `billing_actions.py`: `_action_row` (:42) `clause_ref` kazanır; **eksik emisyon kapatılır** —
      EK-4/D, acil, iş kazası, yeşil kart waiver sonuçları gerekçe-özel aksiyon satırları üretir;
      sabit `"copay:ek1a_exemption_review"` + `"1.8.5(7)"` (:107/:112) kaldırılır.
- [ ] API: `schemas.py`'de `ClauseRefResponse` (RuleClause ile hizalı); `rate_corrections`,
      `recommended_actions` ve copay bloğunda additive alanlar (`extra="allow"` :203 geçişi güvenli).
- [ ] Testler: `tests/unit/domain/billing/test_line_decomposition.py`,
      `test_copay_line_decomposition.py`, `test_billing_actions.py` genişletilir; yeni:
      ilaç satırında `surcharge_rate` varsa bile `ilave_ucret_try == 0` + `drug_prohibited` golden testi.

### Aşama 2 — Prose Katmanı: Provenance Taksonomisi + Manifest Tabanlı Bağlama

- [ ] `ProseRuleTrace` (`prose_rules/types.py:21-28`) ve finding dict şeması `source_type` +
      `clause_ref` kazanır. İKİ agregasyon yolu da (A: `engine.analyze_claim` → `rule_engine.py:438`;
      B: `patient_report.py:58` → `BillingActionReport`) sözleşmeyi taşır.
- [ ] Provenance düzeltmeleri (SUT maddesi UYDURMADAN):
  - `common_billing_errors.py:56` `"tablo_15"` → `source_type="el_kitabi"`, referans "El Kitabı Tablo 15".
  - `diagnosis_coding_quality.py:39` `"elkitabi_diagnosis_coding"` → `source_type="el_kitabi"` + ICD-10 rehber referansı.
  - `lab_capture_gap.py:115` `"clinical lab capture completeness"` → yapısal kimlik + `source_type`.
  - `traffic_accident_billing.py:57` `"algoritma_2_09"` → `source_type="algoritma_rehberi"` +
    `statutory_law="2918 Sayılı Kanun Madde 98"` (:58 zaten doğru atıf yapıyor, yapılaştırılır).
  - `transplant_package_scope.py:38` cümle-biçimli kimlik → yapısal kimlik.
- [ ] Gerçek SUT dayanağı OLAN kurallar için bağlantı: `rule_registry` `sut_section_prefixes`/
      `annex_refs` → coverage parquet'in `clause_coordinate` kolonu üzerinden `clause_key`'e çözülür.
- [ ] JSON kural setleri: kurallara elle `clause_id` alanı EKLENMEZ. Mevcut manifest
      `encoded_clause_ids` + `clause_traces[].rule_id` bağlantısı load-time join ile bulgulara taşınır.
      `material_bundling_prose.json` (83/83 `message_tr` § gömülü) önceliklidir; `sut_anchors`
      alanları coordinate→clause_key doğrulaması için kullanılır.
- [ ] `rules_catalog.py` genişletme ihtiyacı denetlenir (clause_key→satır O(1) indeksi); mevcut
      `_load_coverage` önbelleği (:97-120) korunur, ayrı servis KURULMAZ.

### Aşama 3 — Frontend Kesover (backend alanları live olduktan sonra)

- [ ] `billingReportFields.ts`: `resolveCopayIlaveStatus` → `row.ilave_ucret_status` +
      `row.clause_ref` render eden saf fonksiyon (uncommitted testlerin `drug_prohibited` /
      `cancer_exempt` / `emergency_exempt` kodları backend'den gelir; test girişleri güncellenir,
      senaryolar korunur). `copayClaimScopedAnnexLabels` (:189-210) elle listesi → backend
      `regulatory_sources` yapısal annex alanı.
- [ ] `apiMessages.ts`: 28 regex ayrıştırıcısı yüzey-yüzey silinir; backend `{ message_code, params,
      text_tr, text_en }` yapılandırılmış mesaj sözleşmesine geçer (önce §2.2 prose kümesi :375-461,
      sonra EK-3B :208-224, sonra kalanı). Tek dev PR YAPILMAZ.
- [ ] `sutRegulatorySources.ts`: `EK_ANNEX_PATTERN` (:25) ve elle eşlemeler (:53-72) silinir;
      annex etiketleri backend yapısal alanından gelir.
- [ ] `recommendedActions.ts`: `COMPLIANCE_SURFACES`/`OPPORTUNITY_SURFACES`/`INFORMATIONAL_SURFACES`
      (:14-37) silinir; backend `finding_type` alanı kullanılır; fallback'teki `"1.8.5(7)"` kaldırılır.
- [ ] `SutClauseDrawer.tsx` (yeni, küçük): rapordaki herhangi bir `clause_coordinate`'e tıklanınca
      `getClause(clause_key)` (`api/sut.ts:784`) ile `RuleClause.text_tr` çeken global çekmece.
      Backend ve veri hattı zaten ayaktadır — bu bir faz değil, bağımsız küçük bir görevdir ve
      Aşama 1 ile paralel yapılabilir.

### Aşama 4 — Doğrulama

- [ ] Backend: Aşama 1 testleri + `tests/unit/domain/sut/test_rules_catalog.py` (clause_key
      çözümleme regresyonları) + `tests/unit/api/test_sut_rules_api.py`.
- [ ] Track E değişmezi: coverage parquet yeniden inşa edildiğinde (`scripts/sut/build_sut_coverage.py`)
      billing bulgularındaki `clause_key` referanslarının geçerli kaldığını doğrulayan test
      (pozisyonel C*'ye regresyon YOK).
- [ ] Frontend: `npx vitest run` (npm `test` script'i yoktur), `npx tsc --noEmit`, `npm run build`;
      `SutBillingReportSections.test.tsx` + `billingReportFields.test.ts` yeşil.
- [ ] Uçtan uca: sentetik hasta raporunda her waiver/aksiyon satırının `clause_ref` taşıdığı ve
      drawer'ın metni gösterdiği doğrulanır.

---

## 5. Riskler ve Azaltımlar

| Risk | Azaltım |
|---|---|
| `clause_key` satır-benzersiz değil (4.647/4.757) | `rules_catalog.get_clause()`'daki `is_in_force` ayrıştırması kullanılır; gerekirse `paragraph_index` opak satır token'ı |
| İki agregasyon yolu (engine vs patient_report) sözleşmeyi taşımayı unutabilir | Aşama 2'nin ilk maddesi her iki yolu da açıkça adar; her yol için ayrı test |
| `apiMessages.ts` kesover'ı büyük (28 ayrıştırıcı) | Yüzey-yüzey, ayrı PR'lar; backend mesaj sözleşmesi additive |
| Uncommitted diff erken merge olursa Aşama 3 churn üretir | Aşama 0 ön koşuldur; diff Aşama 1 backend alanları olmadan merge edilmez |
| `extra="allow"` şema geçişi (:203) | Additive alanlar güvenli; yine de `CopayOptimizationResponse` alan listesi bilinçli güncellenir |
| Prose metinlerinde gömülü § referansları (material_bundling 83/83) | Metinler yeniden yazılmaz; manifest join ile yapısal kimlik eklenir, metin olduğu gibi kalır |

## 6. v1'den Devralınan ve Aynen Korunan Hedefler

- Her fatura iddiasının birinci sınıf fıkra referansı taşıması (hedef doğruydu; kimlik modeli düzeltildi).
- Frontend heuristic/regex katmanının kaldırılması (sayılar düzeltildi, yön aynı).
- Resmî Gazete metnini açan evrensel mevzuat çekmecesi (backend'i hazır; küçük görev olarak korundu).
