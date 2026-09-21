# Birleşik Uyumluluk Tablosu — PR #92 İnceleme Düzeltmeleri Planı

> **Durum:** PR #92 bağımsız incelemesinde tespit edilen hatalar doğrulandı; düzeltme uygulaması başlamadı
> **Tarih:** 2026-09-21
> **Dal:** `feat/unified-compliance-findings-table`
> **İncelenen commit:** `c623480f15656c8142463f46ba410443df161c09`
> **PR:** `#92`
> **Uygulayıcı:** Kodlama ajanı bu planı test-önce uygulayacak; backend sözleşmelerini ve finansal toplamları değiştirmeyecek

## Amaç

PR #92'nin onaylanmış birleşik hasta uyumluluk tablosu mimarisini koruyarak
incelemede doğrulanan kimlik, tekilleştirme, para gösterimi, klavye etkileşimi
ve derin bağlantı hatalarını düzeltmek.

Bu plan yeni ürün kapsamı eklemez. Amaç mevcut PR'yi merge edilebilir hale
getirmektir.

---

## İnceleme hükmü ve doğrulanmış başlangıç durumu

PR #92 mevcut haliyle merge edilmemelidir. Aşağıdaki kontroller başarılı olsa
da edge-case davranışları hatalıdır:

- GitHub Actions CI: başarılı
- Frontend odaklı testler: `112 passed`
- TypeScript: `npx tsc --noEmit` başarılı
- Backend invariant testleri: `83 passed`
- GitHub mergeability: conflict yok

Başarılı geniş testler aşağıdaki eksikleri yakalamamaktadır. Düzeltme döngüsü bu
nedenle her hata için önce failing regression testi eklemelidir.

---

## Doğrulanmış hatalar

### Hata 1 — Legacy canonical bulgular seçim ve derin bağlantı kimliğini kaybediyor

**Yer:**

- `frontend/src/lib/complianceFindings.ts`
- `frontend/src/lib/workspaceViews.ts`
- `frontend/src/lib/domains/sut.ts`
- `frontend/src/components/patient/UnifiedComplianceFindingsTable.tsx`

Yeni projeksiyon standalone `claim_compliance` satırlarında
`canonicalFindingId` değerini yalnızca `finding.finding_id` üzerinden kuruyor.
Eski payload'larda belgelenmiş compatibility kimliği olan `action_id` yalnızca
`rowId` olarak kullanılıyor.

Doğrulanmış sonuç:

```json
{
  "rowId": "legacy-canonical-1",
  "canonicalFindingId": null
}
```

Sonuç olarak satır görünse bile:

- `selectedFindingId` ile seçilemiyor,
- `?finding=<id>` Inspect bağlantısı gösterilmiyor,
- mevcut cohort tablosunun desteklediği legacy sözleşme hasta görünümünde
  kırılıyor.

### Hata 2 — Aynı canonical kimliğe bağlı birden fazla action birden fazla satır üretiyor

**Yer:** `frontend/src/lib/complianceFindings.ts`

Kod her action'ı bağımsız işliyor. `mergedFindingIds`, yalnızca canonical
finding'in daha sonra yeniden eklenmesini engelliyor; aynı `finding_id` taşıyan
ikinci action'ın ikinci bir birleşik satır üretmesini engellemiyor.

Doğrulanmış sonuç:

- aynı `finding_id="canonical-1"` taşıyan iki action,
- aynı kimlikte bir canonical finding,
- tabloda iki satır,
- iki satırda aynı `rowId="canonical-1"`.

Bu hata:

- tabloda duplicate satır,
- rozet ve KPI sayısında şişme,
- duplicate React key,
- seçili satır davranışında belirsizlik

oluşturuyor.

### Hata 3 — Bilerek ayrı tutulan satırlar aynı React `rowId` değerini alabiliyor

**Yer:** `frontend/src/lib/complianceFindings.ts`

Bir action yalnızca `action_id="same-id"` taşıyor ve ayrı bir canonical finding
`finding_id="same-id"` taşıyorsa, onaylanmış kurala göre bunlar tekilleştirilmez:
ortak canonical kimlik yalnızca iki tarafta da açık ve eşit `finding_id`
bulunduğunda doğrulanmıştır.

Ancak iki satır da `rowId="same-id"` alıyor. Tekilleştirme kimliği ile render
anahtarı birbirinden ayrılmalıdır.

### Hata 4 — Açık finansal sıfır, bilinmeyen/fiyatlanmamış değere çevriliyor

**Yer:** `frontend/src/lib/complianceFindings.ts`

Canonical finding üzerindeki `billed_try` yalnızca `> 0` ise korunuyor.
`billed_try: 0` değeri `null` haline geliyor ve tablo bunu `—` olarak gösteriyor.

Doğrulanmış sonuç:

```json
{
  "amountValue": null,
  "amountLabel": null
}
```

Onaylanmış semantik:

- `null` / alan yok: bilinmeyen veya finansal olmayan değer, `—`
- sayısal `0`: bilinen sıfır, para formatında `₺0,00`

Bu düzeltme finansal toplam hesaplaması yapmayacak; yalnızca mevcut satır
alanının sıfır değerini kaybetmeyecek.

### Hata 5 — Satır klavye handler'ı iç buton ve linklerin native aktivasyonunu iptal ediyor

**Yer:** `frontend/src/components/patient/UnifiedComplianceFindingsTable.tsx`

`<tr>` üzerindeki `onKeyDown`, event'in hangi elementten geldiğine bakmadan
Enter/Space için `preventDefault()` çağırıp action satırını seçiyor. SUT clause
butonu veya Inspect linki üzerinden kabaran event de aynı handler'a giriyor.

Doğrulanmış davranış:

- Clause butonu + Enter → clause açılmıyor, action seçiliyor.
- Inspect linki + Enter → link açılmıyor, action seçiliyor.
- Clause butonu + Space → clause açılmıyor, action seçiliyor.

Satır klavye aktivasyonu yalnızca event doğrudan satırın kendisinden geldiyse
çalışmalıdır.

### Hata 6 — Canonical deep link exact satıra gitmiyor

**Yer:**

- `frontend/src/components/patient/UnifiedComplianceFindingsTable.tsx`
- `frontend/src/components/patient/views/ComplianceViewSection.tsx`
- `frontend/src/components/patient/views/PatientWorkspaceViews.tsx`
- `frontend/src/app/patient/[id]/page.tsx`

İki alt hata vardır:

1. Birleşmiş satırın Inspect URL'si action surface'inden türetiliyor. Test şu an
   hatalı davranışı sabitliyor:

   ```text
   section=billing-strategy&finding=canonical-find-1
   ```

   Canonical Inspect bağlantısı her zaman:

   ```text
   section=claim-compliance&finding=<canonical-id>
   ```

   sözleşmesini kullanmalıdır.

2. `claim-compliance` anchor'ı birleşik tablonun altında, kapsam özetinde yer
   alıyor. Sayfa routing effect'i anchor'a scroll ederek seçili tablo satırını
   viewport'un üstünde bırakabiliyor. `finding` mevcutsa exact
   `data-finding-id` satırı section anchor'ından önce hedeflenmelidir.

---

## Değişmeyecek sınırlar

1. Backend API ve domain sözleşmeleri değişmeyecek.
2. `action_count`, cohort `n_findings`, finansal toplamlar veya rapor toplamları
   frontend'de yeniden hesaplanmayacak.
3. Metin, claim, kod veya SUT maddesi benzerliğine göre heuristic dedupe
   yapılmayacak.
4. Cross-source dedupe yalnızca action ve canonical finding tarafında açık,
   dolu ve eşit `finding_id` olduğunda yapılacak.
5. Legacy `action_id` fallback'i navigasyon/seçim compatibility kimliğidir;
   cross-source dedupe kimliği değildir.
6. Lab, Billing Strategy, Materials ve Drug Indication ayrıntı bölümleri
   kaldırılmayacak veya yeniden sıralanmayacak.
7. Coverage kayıtları actionable finding satırına çevrilmeyecek.
8. Cohort tablosu bu düzeltmenin parçası olmayacak.
9. Yeni npm bağımlılığı eklenmeyecek; zorunlu görülürse önce ayrı gerekçe ve
   onay gerekir.
10. PR otomatik merge edilmeyecek.

---

## Mimari kararlar

### 1. Üç farklı kimlik açıkça ayrılacak

Projeksiyonda tek bir ID farklı amaçlar için kullanılmayacak.

#### A. Canonical dedupe kimliği

Yalnızca açık ve dolu `finding_id`:

```ts
const explicitFindingId = nonEmpty(action.finding_id);
```

Bir action ile canonical finding ancak iki tarafın açık `finding_id` değeri eşit
ise birleşebilir.

#### B. Canonical navigasyon kimliği

Standalone canonical finding için:

```ts
const navigationFindingId =
  nonEmpty(finding.finding_id) ?? nonEmpty(finding.action_id);
```

`action_id` burada yalnızca legacy seçim/deep-link fallback'idir. Action ile
cross-source dedupe yapmak için kullanılmaz.

#### C. Render `rowId`

`rowId`, React key ve tablo içi render kimliğidir. Kaynak namespace'i taşımalı
ve bütün satırlarda benzersiz olmalıdır. Örnek tabanlar:

```text
canonical:<canonical-or-legacy-navigation-id>
action:<action-id>
merged:<explicit-canonical-id>
```

Aynı taban birden fazla kez oluşabiliyorsa deterministic occurrence suffix
kullanılmalıdır:

```text
action:<action-id>:0
action:<action-id>:1
```

Occurrence suffix yalnızca render benzersizliği içindir; semantik dedupe
kararına katılmaz.

### 2. Canonical gruplama action döngüsünden önce yapılacak

Aynı açık canonical `finding_id` değerini taşıyan action'lar bir grup olarak
işlenmelidir. Her canonical kimlik en fazla bir satır üretmelidir.

Önerilen deterministic kural:

1. `viewActions(report, "compliance")` sırası korunur.
2. Grubun ilk action'ı `row.action` için primary action olur.
3. Kaynak label'ları bütün eşleşen action'lardan stable-order ve unique olarak
   birleştirilir.
4. Canonical finding label'ı bir kez eklenir.
5. Durum, gruptaki herhangi bir action veya canonical finding kesin ihlalse
   `confirmed_violation`; aksi halde `review_risk` olur.
6. Tutar ve başlık için ilk action mevcut davranışın deterministic primary
   kaynağıdır; bu PR yeni finansal birleştirme mantığı eklemez.
7. Canonical finding yalnızca bir kez bağlanır.

Bu yaklaşım exact canonical dedupe şartını yerine getirirken mevcut action
callback sözleşmesini minimum değişiklikle korur.

### 3. Sıfır, nullable finansal değer olarak korunacak

Canonical fallback tutar koşulu:

```ts
matchedFinding.billed_try != null
```

olmalıdır; `> 0` şartı olmamalıdır.

Aynı kural standalone canonical finding projeksiyonunda da geçerlidir. Negatif
veya sıfır dahil backend'den gelen sayısal değer frontend tarafından yeniden
yorumlanmayacak.

### 4. Canonical Inspect URL'si action surface'inden bağımsız olacak

`row.canonicalFindingId` mevcutsa Inspect URL:

```ts
buildSutBillingHref(patientId, {
  claimId: row.claimId ?? undefined,
  section: "claim-compliance",
  findingId: row.canonicalFindingId,
});
```

şeklinde oluşturulmalıdır. Action satır seçimi ise mevcut source section scroll
ve fatura highlight davranışını korur. Inspect linki ile satır seçimi aynı
interaction değildir.

### 5. Exact finding scroll, section scroll'dan öncelikli olacak

Hasta sayfasındaki routing effect şu önceliği uygulamalıdır:

1. `findingQuery` varsa, exact `data-finding-id` eşleşmesini bul ve o satıra
   scroll et.
2. Exact satır henüz DOM'da yoksa veya `findingQuery` yoksa `sectionQuery`
   anchor'ına fallback et.
3. Seçili satır state'i mevcut `selectedFindingId` üzerinden korunur.

Selector escaping problemi oluşturmamak için doğrudan kullanıcı değerini CSS
selector string'ine gömmek yerine `[data-finding-id]` elementleri içinden
`dataset.findingId === findingQuery` eşitliği kullanılabilir.

`claim-compliance` anchor'ı birleşik tabloyu/kapsam bloğunu kapsayacak veya
birleşik tablonun hemen önüne taşınacaktır. Aynı ID iki yerde bulunmayacaktır.

### 6. Row keyboard handler yalnızca row-originated event'i işleyecek

Satır handler'ı şu guard'ları taşımalıdır:

```ts
if (event.target !== event.currentTarget) return;
if (event.key !== "Enter" && event.key !== " ") return;
```

Bundan sonra `preventDefault()` ve `handleRowClick()` çağrılabilir. Clause
butonu ve Inspect linkinin native klavye davranışı korunur.

---

## Uygulama görevleri

### Görev 1 — Projection regression testlerini önce kırmızıya getir

**Dosya:**

- Modify: `frontend/src/lib/complianceFindings.test.ts`

**Eklenecek testler:**

1. `finding_id` olmayan, yalnızca `action_id` taşıyan standalone canonical
   finding'in:
   - `canonicalFindingId === action_id`,
   - selectable/deep-linkable identity taşıması.
2. Aynı explicit canonical `finding_id` değerini taşıyan iki action ve bir
   finding'in:
   - tam bir satır üretmesi,
   - unique tek `rowId` taşıması,
   - source label'larını unique birleştirmesi,
   - ilk action'ı deterministic primary action olarak koruması.
3. Action yalnızca `action_id="same-id"`, finding ise
   `finding_id="same-id"` taşıdığında:
   - iki satırın korunması,
   - satırların farklı `rowId` değerleri taşıması,
   - action'ın canonical finding ile yanlış birleşmemesi.
4. Standalone canonical `billed_try: 0` için:
   - `amountValue === 0`,
   - amount label'ın korunması.
5. Merged canonical `billed_try: 0` fallback'i için:
   - action'dan başka tutar gelmiyorsa `amountValue === 0`.
6. Duplicate action ID'leri canonical kimlik olmadan korunuyorsa bütün
   `rowId` değerlerinin unique olması.

**Kırmızı doğrulama:**

```bash
cd frontend
npx vitest run src/lib/complianceFindings.test.ts
```

Beklenen: yeni regression testleri mevcut `c623480f` davranışında fail eder.
Uygulama başlamadan fail çıktıları kaydedilmelidir.

### Görev 2 — Kimlik, gruplama ve tutar projeksiyonunu düzelt

**Dosya:**

- Modify: `frontend/src/lib/complianceFindings.ts`

**Uygulama:**

1. Boş-string normalizasyonu için küçük bir `nonEmpty` helper kullan.
2. Explicit canonical dedupe kimliği ile legacy navigasyon kimliğini ayır.
3. Aynı explicit canonical ID'ye bağlı action'ları bir kez emit et.
4. Stable source label union oluştur.
5. `rowId` değerlerini source namespace + deterministic suffix ile unique yap.
6. Standalone canonical finding'de `finding_id ?? action_id` navigasyon
   fallback'ini geri getir.
7. `billed_try: 0` dahil bütün non-null sayısal değerleri koru.
8. Input report'u ve nested array'leri mutate etme.

**Yeşil doğrulama:**

```bash
cd frontend
npx vitest run src/lib/complianceFindings.test.ts
npx tsc --noEmit
```

Beklenen: bütün projection testleri ve TypeScript geçer.

### Görev 3 — Tablo interaction regression testlerini önce kırmızıya getir

**Dosya:**

- Modify: `frontend/src/components/patient/UnifiedComplianceFindingsTable.test.tsx`

**Eklenecek/değişecek testler:**

1. Merged canonical satır Inspect URL beklentisini:

   ```text
   section=claim-compliance&finding=canonical-find-1
   ```

   olarak değiştir.
2. Legacy `action_id` fallback kimliği taşıyan canonical satırın Inspect linki
   render ettiğini doğrula.
3. `amountValue: 0` satırının `₺0,00` gösterdiğini; `—` göstermediğini doğrula.
4. Row keyboard aktivasyon predicate/handler'ı için:
   - event target satır ise Enter/Space action seçer,
   - event target nested button/link ise row action seçmez ve default'u iptal
     etmez.
5. `data-finding-id` attribute'unun legacy fallback kimliğini de taşıdığını
   doğrula.

Yeni DOM test bağımlılığı eklemek yerine keyboard kararını küçük, export edilmiş
ve doğrudan test edilebilir bir helper'a ayırmak tercih edilir. Helper yalnızca
handler kararını kapsamalı; ürün mantığını yeni katmana taşımamalıdır.

**Kırmızı doğrulama:**

```bash
cd frontend
npx vitest run src/components/patient/UnifiedComplianceFindingsTable.test.tsx
```

### Görev 4 — Klavye ve canonical Inspect URL davranışını düzelt

**Dosya:**

- Modify: `frontend/src/components/patient/UnifiedComplianceFindingsTable.tsx`

**Uygulama:**

1. Canonical Inspect URL'sinde section'ı her zaman `claim-compliance` yap.
2. Action row click davranışını ve `recommendedActionSectionId` scroll'unu
   değiştirme.
3. Row `onKeyDown` içinde nested event guard'ı uygula.
4. Clause button ve Inspect link mouse propagation guard'larını koru.
5. Legacy canonical navigasyon kimliği geldiğinde link ve selected state'in
   normal canonical finding gibi çalışmasını sağla.

**Yeşil doğrulama:**

```bash
cd frontend
npx vitest run src/components/patient/UnifiedComplianceFindingsTable.test.tsx
npx tsc --noEmit
```

### Görev 5 — Exact-row scroll regression testini ve routing düzeltmesini yap

**Dosyalar:**

- Modify: `frontend/src/components/patient/views/ComplianceViewSection.tsx`
- Modify: `frontend/src/components/patient/views/ComplianceViewSection.test.tsx`
- Modify: `frontend/src/app/patient/[id]/page.tsx`
- Test location if an existing page test is more appropriate:
  `frontend/src/app/patient/[id]/page.test.tsx` or the closest existing patient
  route test file

**Önce test:**

1. `claim-compliance` anchor'ının birleşik tabloyu kapsadığını veya tablonun
   hemen önünde olduğunu doğrula.
2. DOM scroll target seçimini küçük bir helper'a ayırarak şu önceliği test et:
   - exact `finding_id` eşleşmesi,
   - exact eşleşme yoksa section anchor fallback,
   - ikisi de yoksa no-op.
3. `finding_id` içinde CSS özel karakterleri olduğunda string eşitliğiyle exact
   hedef seçildiğini doğrula.
4. `section=claim-compliance&finding=<id>` durumunda selected row'un scroll
   hedefi olduğunu doğrula.

**Uygulama:**

1. Duplicate olmadan `claim-compliance` anchor'ını birleşik tablo kapsayıcısına
   taşı.
2. Hasta sayfası scroll effect'ine `findingQuery` dependency'sini ekle.
3. Finding hedefini section hedefinden önce çöz.
4. Element bulunduğunda mevcut smooth/start scroll davranışını koru.
5. `findingQuery` yoksa mevcut section navigation davranışını değiştirme.

**Yeşil doğrulama:**

```bash
cd frontend
npx vitest run \
  src/components/patient/views/ComplianceViewSection.test.tsx \
  src/lib/patientRoute.test.ts
npx tsc --noEmit
```

Hasta sayfası için yeni veya mevcut ayrı test dosyası eklenirse komuta o dosya
da dahil edilmelidir.

### Görev 6 — Birleşik kabul testi ve regresyon taraması

**Frontend odaklı:**

```bash
cd frontend
npx vitest run \
  src/lib/complianceFindings.test.ts \
  src/components/patient/UnifiedComplianceFindingsTable.test.tsx \
  src/components/patient/views/ComplianceViewSection.test.tsx \
  src/components/patient/views/PatientWorkspaceViews.test.tsx \
  src/components/patient/SutBillingReportSections.test.tsx \
  src/lib/workspaceViews.test.ts \
  src/lib/recommendedActions.test.ts \
  src/lib/patientRoute.test.ts
npx tsc --noEmit
npm run build
```

**Backend invariantleri:**

```bash
/opt/Bilun/.venv/bin/python -m pytest -o addopts='' -q \
  tests/unit/domain/billing/test_rule_findings.py \
  tests/unit/domain/billing/test_claim_compliance.py \
  tests/unit/domain/billing/test_cohort_compliance.py \
  tests/unit/api/test_claim_compliance_pipeline.py \
  tests/unit/api/test_compliance_index_api.py
```

**Repository kontrolleri:**

```bash
git diff --check origin/main...HEAD
ruff check src/ scripts/
python scripts/sut/compile_rules.py --check
python scripts/sut/audit_manifest_parity.py --drug-only
```

Frontend-only düzeltme backend testlerini değiştirmemelidir. Backend invariant
suite'te yeni failure oluşursa hata gizlenmeyecek veya test kapsamı daraltılarak
atlatılmayacaktır.

---

## Manuel kabul senaryoları

### Senaryo A — Legacy canonical finding

Payload:

- `finding_id` yok,
- `action_id="legacy-canonical-1"`,
- `status="violation"`.

Beklenen:

- Satır görünür.
- Inspect linki görünür.
- URL `section=claim-compliance&finding=legacy-canonical-1` içerir.
- URL ile açıldığında exact satır seçilir ve viewport'a getirilir.

### Senaryo B — Çoklu action, tek canonical finding

Payload:

- iki action aynı açık `finding_id="canonical-1"`,
- bir canonical finding aynı `finding_id`.

Beklenen:

- Tek tablo satırı.
- Rozet ve KPI bu finding'i bir sayar.
- Tek ve unique React key.
- Kaynak label'ları unique ve stable order ile görünür.
- Primary action click mevcut invoice highlight/section behavior'ını korur.
- Canonical Inspect exact finding URL'sine gider.

### Senaryo C — Metinsel/ID-benzeri çakışma ama canonical eşleşme yok

Payload:

- action yalnızca `action_id="same-id"`,
- canonical finding `finding_id="same-id"`,
- action'da açık `finding_id` yok.

Beklenen:

- İki satır korunur.
- İki `rowId` farklıdır.
- Heuristic/alias dedupe yapılmaz.

### Senaryo D — Sıfır ve null para ayrımı

Beklenen:

- `billed_try: 0` → `₺0,00`.
- `billed_try: null` veya alan yok → `—`.
- Global finansal KPI/toplamlarda değişiklik yok.

### Senaryo E — Klavye etkileşimi

Beklenen:

- Action row focus + Enter/Space → action seçimi.
- Clause button focus + Enter/Space → clause drawer; row selection yok.
- Inspect link focus + Enter → canonical URL navigation; row selection yok.
- Mouse davranışları aynı kalır.

### Senaryo F — Canonical deep link

URL:

```text
/patient/<id>?claim=<claim>&section=claim-compliance&finding=<canonical-id>
```

Beklenen:

- Uyumluluk view aktif.
- Exact birleşik satır seçili.
- Exact satır viewport'a getirilmiş.
- Coverage summary'ye veya action detail section'a yanlış scroll yok.

---

## Kabul kriterleri

PR #92 ancak aşağıdakilerin tamamı doğrulanınca yeniden merge incelemesine
hazır sayılır:

- [ ] Legacy `action_id` canonical navigasyon fallback'i çalışıyor.
- [ ] Legacy fallback cross-source dedupe için kullanılmıyor.
- [ ] Aynı explicit canonical `finding_id` en fazla bir birleşik satır üretiyor.
- [ ] Bütün `rowId` değerleri tabloda unique.
- [ ] Canonical olmayan benzer satırlar korunuyor.
- [ ] `0` para değeri korunuyor ve formatlanıyor.
- [ ] `null`/nonfinancial tutar `₺0` yapılmıyor.
- [ ] Nested clause button Enter/Space ile çalışıyor.
- [ ] Nested Inspect link Enter ile çalışıyor.
- [ ] Row keyboard activation yalnızca row-originated event'i işliyor.
- [ ] Canonical Inspect linkleri her zaman `section=claim-compliance` kullanıyor.
- [ ] `finding` query exact birleşik satıra scroll ediyor.
- [ ] Exact satır yoksa section fallback çalışıyor.
- [ ] Action row click invoice highlight ve source-section scroll'u koruyor.
- [ ] Unified table, badge ve KPI aynı deduplicated row listesini kullanıyor.
- [ ] Coverage summary actionable row sayısına karışmıyor.
- [ ] Ayrıntı bölümleri korunuyor.
- [ ] Backend count/financial semantics değişmiyor.
- [ ] Yeni regression testleri eski commit üzerinde kırmızı, düzeltme üzerinde yeşil gösterildi.
- [ ] Focused frontend testleri, TypeScript, build ve backend invariant suite başarılı.
- [ ] `git diff --check` başarılı.
- [ ] PR draft halinde kalıyor ve bağımsız re-review yapılmadan merge edilmiyor.

---

## Önerilen implementation commit dizisi

Plan commit'inden sonra uygulama aşağıdaki küçük commitlerle yapılabilir:

1. `test(compliance): cover unified findings review regressions`
2. `fix(compliance): preserve canonical identity and unique rows`
3. `fix(compliance): restore keyboard and exact deep links`
4. Gerekirse yalnızca test/cleanup için:
   `test(compliance): verify unified findings acceptance cases`

Her commit kendi test kapsamıyla doğrulanmalıdır. Failure varken sırf commit sayısını
korumak için ilerlenmemelidir.

---

## Stop koşulları

Aşağıdakilerden biri gerekirse uygulama durdurulup yeni karar alınmalıdır:

1. Çözüm backend payload veya canonical finding üretimini değiştirmeyi
   gerektirirse.
2. Bir canonical ID grubunda bütün action'ların ayrı navigasyon hedeflerini aynı
   anda tabloda göstermek için ürün tasarımı genişletilmek istenirse.
3. Finansal tutarlar birleştirilecek, toplanacak veya yeniden adlandırılacaksa.
4. Exact-row scroll için genel hasta sayfası routing mimarisinin geniş çapta
   değiştirilmesi gerekirse.
5. Yeni frontend test/runtime bağımlılığı eklemek gerekirse.
6. Cohort table veya başka Compliance yüzeylerinde davranış değişikliği
   oluşursa.

Bu koşullar mevcut review düzeltme kapsamının dışındadır; sessizce PR #92'ye
alınmamalıdır.
