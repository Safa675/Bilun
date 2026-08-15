# Plan: Katılım Payı ve İlave Ücret Tablosu Mevzuat ve Netlik İyileştirmesi

**Date:** 2026-08-15  
**Status:** Ready for Review  
**Target:** `frontend/src/components/patient/SutBillingReportSections.tsx`, `frontend/src/lib/billingReportFields.ts`, `frontend/src/messages/{tr,en}/billing.ts`

---

## 1. Problem ve Kullanıcı İhtiyacı

Mevcut **Katılım Payı Muafiyeti İncelemesi** tablosunda fatura memurlarının yaşadığı iki temel kafa karışıklığı bulunmaktadır:

1. **"SGK Sadece İlk Tutarı mı Öder Yoksa Tamamını mı?" Belirsizliği:**
   - Örnek: `MONOVAS 5 MG` satırında `Faturalanan: ₺111,55`, `SGK Ödenecek (İlk Talep): ₺80,32`, `Katılım Payı: ₺31,24` gösterilmektedir.
   - Fatura memuru ilk bakışta SGK'nın yalnızca ₺80,32 ödeyeceğini düşünebilmektedir. Oysa hasta `katilimPayindanMuaf=E` koduyla faturalandığında SGK katılım payı kesintisini iptal ederek **₺111,55'in (%100) tamamını** hastaneye öder.
   - Faturada "Muafiyet Sonrası Nihai SGK Ödemesi" net bir sütun veya gösterge olarak yer almalıdır.

2. **"İlave Ücret: Kullanılamıyor" İfadesinin Yetersizliği:**
   - İlaç ve kanser/acil satırlarında "Kullanılamıyor" yazılması, sanki sistemde bir veri eksikliği veya hesaplama hatası varmış izlenimi vermektedir.
   - SUT mevzuatı gereği:
     - **İlaçlar (EK-4/A):** SUT §2.4.4 ve 5510 Sayılı Kanun Madde 73 uyarınca ilaçlardan ilave ücret alınması **kanunen yasaktır**.
     - **Kanser ve Acil Vakaları:** SUT §2.4.4(1) uyarınca onkolojik tedavilerden ve acil hal işlemlerinden ilave ücret alınamaz.
   - Hücrede doğrudan yasal gerekçe (ör. `Alınamaz (§2.4.4 İlaç)`, `Muaf (§2.4.4 Kanser)`) ve detaylı tooltip gösterilmelidir.

3. **Vezne İade Rehberliği:**
   - Fatura memuruna; faturanın muafiyetle SGK'dan tam tahsil edilmesi durumunda, hastadan veznede önceden alınmış bir katılım payı varsa bunun hastaya iade edilmesi gerektiğine dair yasal uyarı notu sunulmalıdır.

---

## 2. Hedeflenen Arayüz Değişiklikleri

### A. Tablo Sütun Yapısı Güncellemesi

| İşlem (İlaç / Hizmet) | Muafiyet Gerekçesi | Faturalanan Tutar | İlk SGK Talebi | Kurtarılabilir Katılım Payı | **Düzeltilmiş SGK Ödemesi (%100)** | **İlave Ücret Durumu** |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| MONOVAS 5 MG (A11925) | §1.8.5(8) yatış/günübirlik | ₺111,55 | ₺80,32 | +₺31,24 | **₺111,55** *(Tam SGK Karşılama)* | **Alınamaz (SUT §2.4.4 İlaç)** |
| HUMALOG KWIKPEN (A13539) | Acil ziyaret muafiyeti | ₺449,38 | ₺303,33 | +₺146,05 | **₺449,38** *(Tam SGK Karşılama)* | **Alınamaz (SUT §2.4.4 İlaç)** |

### B. İlave Ücret Durum Çözümleyicisi (`copayIlaveUcretStatus`)

`frontend/src/lib/billingReportFields.ts` içine eklenecek fonksiyon:
1. Eğer satır bir **İlaç (EK-4/A)** ise ➔ `not_applicable_drug` (`"Alınamaz (§2.4.4 İlaç)"`).
2. Eğer hasta **Kanser (C00-C97 / C90)** veya **Onkoloji** tanılı ise ➔ `exempt_cancer` (`"Muaf (§2.4.4 Kanser)"`).
3. Eğer vaka **Acil Servis** ise ➔ `exempt_emergency` (`"Muaf (§2.4.4 Acil)"`).
4. Eğer hesaplanmış geçerli bir ilave ücret varsa ➔ `fmtTRY2(ilave_ucret_try)`.
5. Diğer durumlar ➔ `"—"`.

---

## 3. Yapılacak Somut Alt Görevler (Subtasks)

### 1. Frontend Alan ve Formatlayıcı Mantığı (`billingReportFields.ts`)
- [ ] `copayCorrectedPayableTry(correction)` yardımcı fonksiyonunu ekle (`payable_try + copay_component_try` ➔ `billed_try`).
- [ ] `copayIlaveUcretReason(correction, copayData)` fonksiyonunu ekle (SUT §2.4.4 kuralına göre metin/anahtar döndür).
- [ ] `billingReportFields.test.ts` içine tüm senaryolar için birim testleri ekle.

### 2. Yerelleştirme ve Mesajlar (`messages/{tr,en}/billing.ts`)
- [ ] `billing.copay.correctedPayable` ("Düzeltilmiş SGK Ödemesi" / "Corrected SGK Payable")
- [ ] `billing.copay.correctedPayableTooltip` ("Muafiyet onayı sonrası SGK tarafından hastaneye ödenecek %100 tam tutar")
- [ ] `billing.copay.ilaveReasons.drugProhibited` ("Alınamaz (SUT §2.4.4 İlaç / 5510 md.73)")
- [ ] `billing.copay.ilaveReasons.cancerExempt` ("Muaf (SUT §2.4.4 Kanser)")
- [ ] `billing.copay.ilaveReasons.emergencyExempt` ("Muaf (SUT §2.4.4 Acil)")
- [ ] `billing.copay.cashierRefundNotice` ("Vezne İade Uyarısı: Hastadan önceden katılım payı tahsil edildiyse, MEDULA onayı sonrası hastaya iade makbuzu düzenlenmelidir.")

### 3. Arayüz Bileşeninin Güncellenmesi (`SutBillingReportSections.tsx`)
- [ ] `CopayOptimizationSection` tablosuna "Düzeltilmiş SGK Ödemesi" sütununu ekle.
- [ ] İlave ücret hücresinde ham "Kullanılamıyor" yerine ilgili SUT gerekçesini ve tooltip'ini render et.
- [ ] Muafiyet kartlarının altına vezne iade/hukuki uyarı bilgilendirme kutusunu ekle.

### 4. Doğrulama ve Test
- [ ] `npx vitest run` (özellikle `SutBillingReportSections.test.tsx` ve `billingReportFields.test.ts`).
- [ ] `npx tsc --noEmit` tip kontrolü.
- [ ] `npm run build` üretim derlemesi.
- [ ] Sentetik hasta faturalarında görsel doğrulama.
