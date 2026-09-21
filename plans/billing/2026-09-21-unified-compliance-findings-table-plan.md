# Birleşik Hasta Uyumluluk Bulguları Tablosu — Uygulama Planı

> **Durum:** Safa tarafından ürün kararları onaylandı; uygulama başlamadı
> **Tarih:** 2026-09-21
> **Dal:** `feat/unified-compliance-findings-table`
> **Başlangıç:** `main` / `7cf37ebcd862ac0882ade55c9c38f63d2ba1c93e` — PR #91 dahil
> **Uygulayıcı:** Kodlama ajanı bu planı görev görev uygular; ayrı kaynak motorlarını yeniden yazmaz

## Amaç

Hasta **Mevzuat Uyumluluğu** görünümünde bugün ayrı gösterilen:

1. uyumluluk sınıfındaki `recommended_actions` kayıtlarını ve
2. canonical `claim_compliance.findings` kayıtlarını

tek bir **uyumluluk bulguları tablosunda** göstermek; temiz/eksik/ulaşılamayan
kural değerlendirmelerini tablo satırına çevirmeden ayrı, kompakt bir kapsam
özeti olarak korumak.

Bu değişiklik sunum ve etkileşim birleştirmesidir. Kural motorlarının çalışma
şeklini, finansal toplamları, cohort uyumluluk indeksini veya backend rapor
sözleşmelerini değiştirmez.

---

## Onaylanmış ürün kararları

1. Mevcut iki hasta bulgu tablosu kaldırılıp **tek tablo** oluşturulacak.
2. `Laboratuvar`, `Fatura Stratejisi`, `Malzeme Ön Kontrol`, `İlaç
   Endikasyonu` ayrıntı bölümleri aşağıda kalacak.
3. Birleşik tabloda yalnızca eyleme dönük ihlal/risk bulguları yer alacak.
4. Temiz değerlendirmeler, eksik girdiler ve değerlendirilemeyen kurallar tablo
   satırı olmayacak; ayrı kapsam özetinde gösterilecek.
5. Her bulgu otomatik olarak kesin ihlal sayılmayacak. Durum en az iki sınıf
   taşıyacak:
   - **Kesin ihlal**
   - **Risk — inceleme gerekli**
6. Kaynaklar arası tekilleştirme yalnızca doğrulanmış, ortak canonical
   `finding_id` üzerinden yapılacak. Benzer metin, talep, kod veya SUT maddesi
   tek başına tekilleştirme sebebi olmayacak.
7. Aynı canonical kimliği paylaşmayan benzer satırlar korunacak ve `Kaynak`
   sütunuyla ayrıştırılacak.
8. Örnek kabul davranışı: tabloda dört eyleme dönük bulgu varken kapsam özeti
   “25 yapısal kontrol değerlendirildi · 0 ek bulgu” diyebilecek; ikinci boş
   tablo gösterilmeyecek.
9. Hasta sayfasında gereksiz `Hasta ID` sütunu olmayacak.
10. Uyumluluk sekmesi rozeti, KPI ve görünür tablo satırı aynı tekilleştirilmiş
    satır sayısını kullanacak.
11. Finansal davranış değişmeyecek; `null` tutar `₺0` olarak gösterilmeyecek.
12. Mevcut derin bağlantı, satır seçimi, fatura satırı vurgulama ve SUT maddesi
    inceleme davranışları korunacak.

---

## Mevcut durum

### Birinci tablo: önerilen işlemler

Hasta raporundaki `recommended_actions`, frontend'de
`viewActions(report, "compliance")` ile uyumluluk sınıfına süzülüyor ve
`RecommendedActionsPanel` tarafından gösteriliyor.

İlgili kod:

- `frontend/src/lib/workspaceViews.ts`
- `frontend/src/lib/recommendedActions.ts`
- `frontend/src/components/patient/SutBillingReportSections.tsx`
- `frontend/src/components/patient/views/ComplianceViewSection.tsx`

Bu satırlar Laboratuvar, Fatura Stratejisi, Malzeme ve İlaç Endikasyonu gibi
ayrıntı bloklarının eylem projeksiyonlarıdır. Satır seçimi mevcut
`RecommendedActionItem` nesnesini callback'e ileterek orijinal fatura satırını
vurgular ve ilgili ayrıntı bölümüne kaydırır.

### İkinci tablo: canonical yapısal uyumluluk bulguları

`claim_compliance.findings`, hasta/talep kapsamına süzüldükten sonra
`ComplianceIndexRow` şekline çevrilip cohort için tasarlanmış
`ComplianceFindingTable` bileşeninde gösteriliyor.

İlgili kod:

- `frontend/src/lib/workspaceViews.ts`
- `frontend/src/components/patient/views/ComplianceViewSection.tsx`
- `frontend/src/components/tabs/sut/compliance/modules/ComplianceFindingTable.tsx`

Bu kayıtların canonical kimliği `finding_id`'dir; yeni payload'larda
`action_id === finding_id` compatibility alias'ı bulunur. Bu satırlar cohort
sayfasından `?finding=<canonical-id>` derin bağlantısıyla seçilebilir.

### Sayım sorunu

Bugünkü uyumluluk sekmesi rozeti ve KPI iki ayrı listenin ham uzunluğunu toplar.
Yeni tasarımda tek birleşik projeksiyon bir kez hesaplanmalı; tablo, rozet ve KPI
aynı listeyi kullanmalıdır.

---

## Mimari karar

### 1. Frontend'e özgü birleşik görünüm modeli

Yeni dosya:

- `frontend/src/lib/complianceFindings.ts`

Yeni test:

- `frontend/src/lib/complianceFindings.test.ts`

Önerilen model:

```ts
export type UnifiedComplianceStatus =
  | "confirmed_violation"
  | "review_risk";

export interface UnifiedComplianceFindingRow {
  rowId: string;
  canonicalFindingId: string | null;
  sourceKind: "recommended_action" | "claim_compliance";
  sourceLabels: string[];
  status: UnifiedComplianceStatus;
  title: string;
  detail: string | null;
  claimId: string | null;
  code: string | null;
  sutLabel: string | null;
  amountValue: number | null;
  amountLabel: string | null;
  action: RecommendedActionItem | null;
  finding: ClaimComplianceFinding | null;
}
```

`buildUnifiedComplianceFindings(report)` şu iki girdiyi kullanmalı:

- `viewActions(report, "compliance")`
- `scopedClaimComplianceFindings(report)`

Ham `recommended_actions` dizisi doğrudan okunmamalı; mevcut legacy fallback ve
sıralama davranışı `viewActions` üzerinden korunmalıdır.

Hasta sayfası için cohort taşıma tipi olan `ComplianceIndexRow` yeniden
kullanılmamalıdır. O tip hasta kimliği, sayfalama ve cohort API ihtiyaçlarını
taşır; yeni tip yalnızca hasta görünümü için bir presentation model olmalıdır.

### 2. Durum sınıflandırması

Frontend yalnızca payload'da doğrulanabilir kanıt varsa **Kesin ihlal** etiketi
vermelidir:

- `claim_compliance` kaydında `status === "violation"`;
- recommended action'da `kind === "compliance_violation"`;
- ilaç endikasyonu action'ında `finding_id`, aynı raporun
  `drug_indication.violations` dizisindeki canonical `finding_id` ile tam
  eşleşiyorsa.

Bunların dışında uyumluluk sınıfına giren recommended action kayıtları
**Risk — inceleme gerekli** olarak gösterilmelidir. `finding_type ===
"compliance"` tek başına kesin ihlal kanıtı değildir.

Bu PR bütün recommended action türleri için authoritative backend status alanı
icat etmeyecek. Ürün daha sonra bütün kaynaklarda normatif kesinlik isterse
ayrı bir backend sözleşmesi planlanmalıdır.

### 3. Canonical tekilleştirme

Bir recommended action ve bir `claim_compliance` bulgusu yalnızca:

- her ikisinde de boş olmayan `finding_id` varsa ve
- değerler tam olarak eşitse

tek satırda birleştirilebilir.

Birleşen satır:

- her iki kaynağı `sourceLabels` içinde göstermeli;
- canonical `finding_id` değerini korumalı;
- recommended action callback'ini fatura satırı vurgulama için korumalı;
- canonical finding linkini/selection kimliğini derin bağlantı için korumalıdır.

Şunlarla tekilleştirme yapılmayacak:

- `action_id` tek başına;
- talep + işlem/malzeme/ilaç kodu;
- talep + SUT maddesi;
- başlık veya açıklama metni;
- kaynak yüzeyi + dizi indeksi.

Canonical kimliği olmayan her satır kendi güvenli `rowId` değeriyle ayrı
kalmalıdır.

### 4. Finansal gösterim

Recommended action tutarı mevcut `recommendedActionAmountParts` davranışından
üretilmelidir. Böylece:

- faturalanan risk,
- SGK uplift,
- uyumluluk tasarrufu,
- audit risk ve
- fiyatlanmamış etiket

anlamları korunur.

Canonical `claim_compliance` kayıtları fiyat taşımıyorsa hücre `—` olmalıdır.
`null`, `undefined` veya fiyatlanmamış durum hiçbir yerde `fmtTRY2(0)` üzerinden
`₺0` yapılmamalıdır.

Aşağıdaki toplamlar değiştirilmemelidir:

- `audit_exposure_try`
- `compliance_adjustment_try`
- `sgk_uplift_try`
- `total_recoverable_try`
- backend `action_count`
- cohort `n_findings`

### 5. Hasta tablosu

Yeni bileşen:

- `frontend/src/components/patient/UnifiedComplianceFindingsTable.tsx`

Sütunlar:

1. `Durum`
2. `Kaynak`
3. `Bulgu / yapılması gereken`
4. `Fatura`
5. `Kod`
6. `SUT`
7. `Risk tutarı`
8. `İncele`

Hasta sayfasında `Hasta ID` sütunu bulunmayacak.

Bileşen Bilun'ın mevcut `DataTable`, `Chip`, tipografi, renk ve boşluk
tokenlarını kullanmalıdır. Yeni dekoratif kart veya açıklama banner'ı
eklenmemelidir.

### 6. Etkileşim sözleşmesi

#### Recommended action satırı

- Satır click/Enter/Space davranışı mevcut `onSelectAction(action)` callback'ini
  çağırmalıdır.
- Mevcut `selectedActionId` vurgusu korunmalıdır.
- Kaynak bölüm anchor'ı bulunuyorsa mevcut şekilde kaydırılmalıdır.
- SUT `clause_ref.clause_key` mevcutsa `onOpenClause` korunmalıdır.

#### Canonical claim-compliance satırı

- Link `claim`, `section=claim-compliance` ve tam
  `finding=<canonical-id>` parametrelerini korumalıdır.
- `selectedFindingId` eşleşmesinde yalnızca tam canonical kimlik seçili
  görünmelidir.
- Bilinmeyen veya yanlış finding ID başka satırı seçmemelidir.

#### Birleşmiş canonical satır

Aynı canonical kimliği paylaşan action + finding satırı her iki kabiliyeti de
korumalıdır:

- satır seçimi action callback'i üzerinden fatura satırı vurgulamayı;
- `İncele` linki canonical finding URL'sini.

### 7. Kapsam özeti

`claim_compliance.evaluations` birleşik bulgu tablosuna eklenmeyecek. Aktif
hasta/talep kapsamına göre ayrı özetlenecek.

Örnek temel metin:

> 25 yapısal kontrol değerlendirildi · 0 ek bulgu

Eksik veya ulaşılamayan değerlendirme varsa aynı kompakt blokta sayılar açıkça
gösterilmeli ve mevcut “değerlendirildi uygun olduğu anlamına gelmez” semantiği
korunmalıdır. İstenirse mevcut ayrıntı `<details>` görünümü korunabilir; ancak
ikinci bir findings tablosu oluşturulmamalıdır.

### 8. Ortak sayım kaynağı

`buildUnifiedComplianceFindings(report)` mümkünse
`PatientWorkspaceViews` seviyesinde bir kez hesaplanmalı ve
`ComplianceViewSection` bileşenine aktarılmalıdır.

Aynı `unifiedRows.length` değeri:

- Uyumluluk sekmesi rozeti,
- `Riskli bulgu` KPI değeri ve
- render edilen tablo satırı

için kullanılmalıdır.

Temiz, eksik-girdili veya ulaşılamayan evaluations bu sayıya dahil edilmemelidir.

---

## Uygulama görevleri

### Görev 1 — Birleşik projection sözleşmesini testle sabitle

**Dosyalar:**

- Oluştur: `frontend/src/lib/complianceFindings.test.ts`
- Oluştur: `frontend/src/lib/complianceFindings.ts`

**RED testleri:**

1. Dört compliance action + sıfır canonical finding → dört satır.
2. Bir canonical violation → `confirmed_violation`.
3. Generic compliance action → `review_risk`.
4. `kind=compliance_violation` → `confirmed_violation`.
5. Drug indication action'ı yalnızca aynı `finding_id` violation kaydında varsa
   kesin ihlal.
6. Aynı canonical `finding_id` iki kaynaktan gelirse tek satır ve iki kaynak.
7. Benzer talep/kod/SUT taşıyan fakat ortak canonical ID taşımayan iki satır
   korunur.
8. Legacy action fallback `viewActions` üzerinden çalışmaya devam eder.
9. Fiyatlanmamış canonical finding'in amount değeri `null` kalır.
10. Projection giriş raporunu veya alt dizilerini mutate etmez.

Test önce başarısız görülmeli, ardından minimal projection uygulanmalıdır.

### Görev 2 — Hasta-özel birleşik tabloyu testle oluştur

**Dosyalar:**

- Oluştur: `frontend/src/components/patient/UnifiedComplianceFindingsTable.tsx`
- Oluştur: `frontend/src/components/patient/UnifiedComplianceFindingsTable.test.tsx`

**RED testleri:**

1. Onaylanan sekiz sütun render edilir.
2. `Hasta ID` başlığı render edilmez.
3. Kesin ihlal ve inceleme riski ayrı chip metni/variant ile gösterilir.
4. Kaynak etiketleri görünür.
5. `null` tutar `—`, hiçbir zaman `₺0` değildir.
6. Recommended action satırı click ve keyboard ile orijinal action callback'ini
   iletir.
7. Canonical finding `?finding=` derin bağlantısını ve selected state'i korur.
8. Birleşmiş satır action seçimi ile canonical inceleme linkini birlikte taşır.
9. Clause inspect butonu satır seçimini yanlışlıkla tetiklemeden `onOpenClause`
   çağırır.
10. Boş liste tek bir açık empty state gösterir; ikinci tablo yaratmaz.

### Görev 3 — Kapsam özetini tablo satırlarından ayır

**Dosyalar:**

- Değiştir: `frontend/src/components/patient/views/ComplianceViewSection.tsx`
- Gerekirse oluştur: `frontend/src/lib/complianceCoverage.ts`
- Test: ilgili view/component testleri

**Davranış:**

- Evaluations aktif hasta/talep kapsamına göre süzülür.
- Evaluated/missing/unavailable sayıları korunur.
- Findings sayısı coverage satırına “ek bulgu” olarak aktarılır fakat temiz
  kontroller tabloya eklenmez.
- “25 değerlendirildi · 0 ek bulgu” senaryosu açık test fixture'ı olur.
- Eksik/unavailable ayrıntı disclosure davranışı korunur.

### Görev 4 — İki hasta tablosunu tek tabloyla değiştir

**Dosyalar:**

- Değiştir: `frontend/src/components/patient/views/ComplianceViewSection.tsx`
- Değiştir: `frontend/src/components/patient/views/PatientWorkspaceViews.tsx`
- Test: `frontend/src/components/patient/views/PatientWorkspaceViews.test.tsx`
- Test: yeni veya mevcut Compliance view testi

**Değişiklikler:**

- Compliance görünümündeki compliance-filtered `RecommendedActionsPanel`
  kaldırılır.
- Ayrı `claim-compliance` `ComplianceFindingTable` kaldırılır.
- Tek `UnifiedComplianceFindingsTable` render edilir.
- Ayrıntı bölümleri ve anchor'ları aynı sırada kalır.
- Projection üst seviyede bir kez hesaplanıp tablo, KPI ve tab badge'e verilir.
- Revenue ve Audit görünümlerindeki `RecommendedActionsPanel` değiştirilmez.
- Cohort dashboard'daki `ComplianceFindingTable` değiştirilmez.

### Görev 5 — TR/EN metinlerini ekle

**Dosyalar:**

- Değiştir: `frontend/src/messages/tr/billing.ts`
- Değiştir: `frontend/src/messages/en/billing.ts`
- Gerekirse optimizer coverage metinlerini yeniden kullan; mevcut key'leri
  silme.

**Yeni metin grupları:**

- kesin ihlal;
- risk — inceleme gerekli;
- kaynak;
- bulgu / yapılması gereken;
- risk tutarı;
- incele;
- yapısal kontrol kapsam satırı;
- eksik/ulaşılamayan evaluation suffix'leri;
- birleşik tablo empty state'i.

Revenue/Audit `RecommendedActionsPanel` ve cohort compliance index hâlâ mevcut
translation key'lerini kullandığı için eski key'ler kaldırılmamalıdır.

### Görev 6 — Sayım, finans ve navigasyon regresyonlarını kapat

**Test dosyaları:**

- `frontend/src/lib/workspaceViews.test.ts`
- `frontend/src/lib/recommendedActions.test.ts`
- `frontend/src/components/patient/views/PatientWorkspaceViews.test.tsx`
- `frontend/src/lib/patientRoute.test.ts`
- `frontend/src/lib/constants.test.ts`
- `frontend/src/components/tabs/sut/compliance/SUTComplianceDashboard.test.tsx`

**Zorunlu kabul testleri:**

1. Tab badge = KPI = görünür birleşik satır sayısı.
2. Canonical dedupe sayımdan önce uygulanır.
3. Missing/unavailable evaluations bulgu sayısına girmez.
4. `audit_exposure_try`, `complianceBilledAtRisk` ve rapor toplamları değişmez.
5. Drug-indication para davranışı mevcut invariantı korur.
6. Unknown/nonfinancial amount `₺0` olmaz.
7. Canonical cohort→patient finding URL tam kimliği seçer.
8. Recommended action seçimi doğru fatura satırını vurgulamaya devam eder.
9. `billing-lab`, `billing-strategy`, `materials-pre-check`,
   `drug-indication`, `claim-compliance` section sahipliği bozulmaz.
10. Cohort dashboard'un mevcut tablosu ve pagination davranışı değişmez.

### Görev 7 — Backend invariant testlerini değişiklik yapmadan çalıştır

Frontend-only kapsam backend davranışını değiştirmemelidir. Aşağıdaki testler
regresyon kapısıdır:

- `tests/unit/domain/billing/test_rule_findings.py`
- `tests/unit/domain/billing/test_claim_compliance.py`
- `tests/unit/domain/billing/test_cohort_compliance.py`
- `tests/unit/api/test_claim_compliance_pipeline.py`
- `tests/unit/api/test_compliance_index_api.py`

Bu testlerden biri frontend çalışması sonrası kırılırsa kapsam genişletilmeden
önce kök sebep açıklanmalıdır.

---

## Muhtemel dosya değişiklikleri

### Yeni

- `frontend/src/lib/complianceFindings.ts`
- `frontend/src/lib/complianceFindings.test.ts`
- `frontend/src/components/patient/UnifiedComplianceFindingsTable.tsx`
- `frontend/src/components/patient/UnifiedComplianceFindingsTable.test.tsx`

### Değişecek

- `frontend/src/components/patient/views/ComplianceViewSection.tsx`
- `frontend/src/components/patient/views/PatientWorkspaceViews.tsx`
- `frontend/src/components/patient/views/PatientWorkspaceViews.test.tsx`
- `frontend/src/messages/tr/billing.ts`
- `frontend/src/messages/en/billing.ts`
- Gerektiği kadar mevcut frontend regression testleri

### Değişmemesi gerekenler

- Backend kural motorları
- `BillingActionReport` API sözleşmesi
- `src/bilun/domain/billing/cohort_compliance.py`
- Cohort `/api/compliance-index` route'u
- Cohort `ComplianceFindingTable` davranışı
- Finansal toplama/hesaplama kodu
- Cache üretim sözleşmesi

---

## Doğrulama komutları

### Hedefli frontend

Mevcut bağımlılık ağacı kullanılarak:

```bash
cd frontend

npx vitest run \
  src/lib/complianceFindings.test.ts \
  src/components/patient/UnifiedComplianceFindingsTable.test.tsx \
  src/components/patient/views/PatientWorkspaceViews.test.tsx \
  src/components/tabs/sut/compliance/SUTComplianceDashboard.test.tsx \
  src/components/patient/SutBillingReportSections.test.tsx \
  src/lib/workspaceViews.test.ts \
  src/lib/recommendedActions.test.ts \
  src/lib/patientRoute.test.ts \
  src/lib/constants.test.ts \
  src/lib/api/sut.complianceIndex.test.ts

npx tsc --noEmit
npm run build
```

### Backend invariantleri

Repo Python ortamıyla:

```bash
python -m pytest -q \
  tests/unit/domain/billing/test_rule_findings.py \
  tests/unit/domain/billing/test_claim_compliance.py \
  tests/unit/domain/billing/test_cohort_compliance.py \
  tests/unit/api/test_claim_compliance_pipeline.py \
  tests/unit/api/test_compliance_index_api.py
```

### Final CI-parite kapıları

```bash
ruff check src/ scripts/
python -m pytest -q
python scripts/sut/compile_rules.py --check
python scripts/sut/audit_manifest_parity.py --drug-only

cd frontend
npx tsc --noEmit
npx vitest run
npm run build
```

---

## Kabul kriterleri

- [ ] Hasta Compliance görünümünde yalnızca bir özet bulgular tablosu vardır.
- [ ] Compliance recommended actions ve canonical claim findings aynı tabloda
      görünür.
- [ ] Ayrıntı kaynak bölümleri aşağıda korunur.
- [ ] Temiz/missing/unavailable evaluations tablo satırı değildir.
- [ ] Yapısal kontrol kapsamı ayrı, kompakt ve yanlış güven vermeyen metinle
      görünür.
- [ ] Kesin ihlal ile inceleme riski görsel ve semantik olarak ayrıdır.
- [ ] Tekilleştirme yalnızca ortak canonical `finding_id` üzerinden yapılır.
- [ ] Ortak canonical kimliği olmayan benzer satırlar kaybolmaz.
- [ ] Hasta ID sütunu gösterilmez.
- [ ] Tab badge, KPI ve tablo sayısı aynıdır.
- [ ] `null`/nonfinancial amount `₺0` olarak gösterilmez.
- [ ] Recommended action satır seçimi ve fatura vurgusu çalışır.
- [ ] Canonical finding deep-link ve exact selection çalışır.
- [ ] SUT madde inceleme callback'i çalışır.
- [ ] Revenue/Audit recommended-action tabloları değişmez.
- [ ] Cohort compliance index tablosu değişmez.
- [ ] Finansal toplamlar ve backend action counts değişmez.
- [ ] Hedefli frontend, backend invariantleri ve final CI kapıları yeşildir.

---

## Kapsam dışı

- Bütün backend motorlarını tek canonical finding üretim hattına taşımak.
- Heuristik/semantik cross-engine deduplication.
- Yeni kural yazmak veya mevcut SUT kurallarını değiştirmek.
- Finansal değerleri birleşik tablodan yeniden hesaplamak.
- Cohort indeksini veya cohort UI tablosunu yeniden tasarlamak.
- API/cache şeması migrasyonu.
- Revenue veya Audit görünümünü birleştirmek.
- Detay bölümlerini kaldırmak.
- Her recommended action için yeni authoritative backend violation status alanı
  eklemek.

---

## Stop koşulları

Uygulama sırasında aşağıdakilerden biri görülürse frontend inference genişletilip
sessizce devam edilmemelidir:

1. Aynı gerçek bulguyu güvenli biçimde tekilleştirmek için ortak canonical
   kimlik yoksa.
2. Bir recommended action'ın kesin ihlal mi inceleme riski mi olduğu mevcut
   payload'dan kanıtlanamıyorsa ve ürün kesin sınıflandırma gerektiriyorsa.
3. Birleşik görünüm finansal toplamların yeniden hesaplanmasını gerektiriyorsa.
4. Deep-link veya satır vurgulama korunmadan yeni bir genel click modeli
   gerektiriyorsa.
5. Cohort sözleşmesinin değiştirilmesi zorunlu hale geliyorsa.

Bu durumda mevcut frontend PR kapsamı durdurulur ve ihtiyaç duyulan backend
canonical sözleşmesi ayrı plan/PR olarak Safa'ya sunulur.
