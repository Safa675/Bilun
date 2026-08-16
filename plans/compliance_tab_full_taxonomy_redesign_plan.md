# Plan: SUT Uyumluluk (Compliance) Sekmesi Kapsamlı Yeniden Tasarım Planı (Comprehensive SUT Compliance Taxonomy Redesign)

**Date:** 2026-08-16  
**Status:** Architectural Plan & Implementation Roadmap (Ready for Review)  
**Target:** `frontend/src/components/tabs/SUTCompliance.tsx`, `frontend/src/components/tabs/sut/compliance/`, `frontend/src/lib/workspaceSubtabs.ts`, `src/bilun/domain/optimization/`, `src/bilun/api/routes/optimization.py`

---

## 1. Yönetici Özeti ve Mevcut Durum Analizi

### Mevcut Durumun Eksikliği
Şu anki Bilun uygulamasında **"Uyumluluk" (`/ ?tab=compliance`)** sekmesi sadece 2 alt kategoriye ayrılmıştır:
1. `exemptions` (Katılım Payı Muafiyeti - EK-1A)
2. `surcharge` (İlave / Fark Ücreti - %200 Tavan)

Oysa hastanelerin SGK denetimlerinde ceza ve kesintiye (rejection / deduction) uğradığı **onlarca farklı kritik uyumluluk türü** mevcuttur. Mevcut durum, platformun sahip olduğu malzeme denetimini, DRG paketleme ihlallerini, cerrahi seans çarpanlarını ve gönderim öncesi evrak kontrollerini kohort düzeyinde kullanıcının gözünden kaçırmaktadır.

### Yeniden Tasarım Hedefi (The Full Compliance Taxonomy)
Uyumluluk sekmesini hastanenin tüm risklerini 360 derece izleyebileceği **8 Kapsamlı Uyumluluk Türü** ve **Kohort Risk Radarı** ile yeniden inşa etmek.

---

## 2. Sekiz Kapsamlı Uyumluluk Türü (8-Pillar Compliance Taxonomy)

```
┌──────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                🛡️ SUT UYUMLULUK KONTROL MERKEZİ                                  │
├───────────────────┬───────────────────┬───────────────────┬──────────────────────────────────────┤
│ 1. Katılım Payı   │ 2. İlave Ücret    │ 3. Tıbbi Malzeme  │ 4. Fatura Yöntemi & DRG              │
│    Muafiyetleri   │    & Tavan Kuralı │    & ÜTS / Ön Onay│    Paket İhlalleri                   │
│    (EK-1A, Acil)  │    (§1.9, %200)   │    (§3.1, §3.3)   │    (§2.2.1, §2.2.2)                  │
├───────────────────┼───────────────────┼───────────────────┼──────────────────────────────────────┤
│ 5. Cerrahi, Seans │ 6. Laboratuvar &  │ 7. Gönderim Evrak │ 8. MEDULA Red                        │
│    & Anestezi     │    Tetkik Hataları│    & Epikriz      │    Kılavuzu (Playbook)               │
│    (§2.4 Çarpanı) │    (Tablo 15)     │    (ORTAK-17/21)  │    (1001, 1054 Redleri)              │
└───────────────────┴───────────────────┴───────────────────┴──────────────────────────────────────┘
```

### 1. 🛡️ Katılım Payı & Muafiyet Uyumluluğu (`exemptions`)
* **SUT Dayanağı:** SUT §1.8, EK-1A Listesi, SUT §1.8.5(8).
* **Denetim Kapsamı:** Kanser (Multiple Miyelom vb.), kronik hastalıklar, acil başvurular ve yatan hasta ilaçlarında hastadan haksız katılım payı kesilmesini engelleme; MEDULA `katilimPayindanMuaf=E` bayrağı doğrulama.

### 2. ⚖️ İlave Ücret & Tavan Sınırı Uyumluluğu (`surcharge`)
* **SUT Dayanağı:** SUT §1.9, 5510 Sayılı Kanun Madde 73.
* **Denetim Kapsamı:** Özel/Vakıf hastaneleri %200 tavan kuralı; İlave ücret alınamayacak acil, kanser cerrahisi, yoğun bakım, yanık ve organ nakli vakalarında usulsüz fark ücreti kontrolü; İlaç ve tıbbi malzemeden ilave ücret alma yasağı.

### 3. 📦 Tıbbi Malzeme & Cihaz Uyumluluğu (`materials`)
* **SUT Dayanağı:** SUT §3.1, §3.3, EK-3B-1, EK-3B-2, EK-3C-1.
* **Denetim Kapsamı:**
  * **Ön Onay (Tıbbi Uygunluk):** Yüksek tutarlı protez ve cihazlar için SGK Sağlık Kurulu Ön Onay denetimi (`§3.1.2`).
  * **ÜTS / TİTUBB Kaydı:** Sağlık Bakanlığı Ürün Takip Sistemi'nde tekil bildirim eşleşmesi (`§3.1.1(2)`).
  * **MIAT / Kullanım Ömrü:** 10 yıl vb. cihaz yenilenme süreleri (`§3.1.4`).
  * **Paket İçi (Unbundling) Mükerrer Malzeme:** Ameliyat paketine dahil sarfların ayrı fatura edilmesini engelleme (`AP4340`, `AP1260`).
  * **Özel Branş Sınırları:** Yanık dışı sentetik greft (`SS1`), hidrojel nemlendirici (`W2`) gibi kurumca ödenmeyen sarflar (`§3.3.1`).

### 4. 📑 Fatura Stratejisi & Ödeme Yöntemi Uyumluluğu (`payment_methods`)
* **SUT Dayanağı:** SUT §2.2.1.B-1.a, §2.2.2(1).
* **Denetim Kapsamı:** Organ nakli (608550), amputasyon (611240) gibi zorunlu "Tanıya Dayalı / DRG Paket" işlemlerinin kalem işlem olarak yanlış faturalandırılmasının engellenmesi; DRG paket parçalama (unbundling) ihlallerinin tespiti.

### 5. ✂️ Cerrahi Seans & Çoklu Ameliyat Uyumluluğu (`surgical_sessions`)
* **SUT Dayanağı:** SUT §2.4.
* **Denetim Kapsamı:** Aynı seansta birden fazla cerrahi işlem yapıldığında katsayı kuralları (%100 + %50 + %30); Aynı kesi / farklı kesi kural uyumu; Anestezi puanlama ve seans oranları; Kan ve kan bileşenleri endikasyon uyumu.

### 6. 🧪 Laboratuvar, Tetkik & Teşhis Uyumluluğu (`diagnostics_lab`)
* **SUT Dayanağı:** SUT El Kitabı Tablo 15 (24 Most Common Outpatient Errors).
* **Denetim Kapsamı:** Paket içi biyokimya/mikrobiyoloji tetkik mükerrerlikleri; Aynı gün tekrarlanan rutin tetkikler; ICD-10 tanı kodlama kalitesi ve ana tanı / ek tanı uyumsuzlukları.

### 7. 📋 Gönderim Öncesi Evrak & Epikriz Uyumluluğu (`pre_flight_docs`)
* **SUT Dayanağı:** Fatura İnceleme Usul ve Esasları (FI Kuralları).
* **Denetim Kapsamı:** Cerrahi patoloji raporu zorunluluğu (ORTAK-21); Ortopedi pre-op/post-op radyoloji grafileri (ORTOPEDİ-6); Ameliyat notu detayı (ORTAK-17); Epikriz ve günlük vizit tutarlılığı (ORTAK-27).

### 8. 🚨 MEDULA Red Kılavuzu & Otomasyon Uyumluluğu (`medula_rejections`)
* **SUT Dayanağı:** SGK MEDULA Hata Kılavuzu & Red Takip Sistemi.
* **Denetim Kapsamı:** Sık tekrarlanan MEDULA hata kodları (1001, 1002, 1054, 1072 vb.) ve proaktif düzeltme mekanizmaları.

---

## 3. UI/UX Tasarımı ve Bileşen Mimarisi

### Yeni Bileşen Yapısı (`frontend/src/components/tabs/sut/compliance/`)
```
frontend/src/components/tabs/sut/compliance/
├── SUTComplianceDashboard.tsx        # Ana sekme çerçevesi & Kohort Risk KPI'ları
├── ComplianceSubtabStrip.tsx         # 8 uyumluluk modülü arasında yatay şık sekme çubuğu
├── modules/
│   ├── CopayExemptionCompliance.tsx  # Modül 1: Katılım Payı
│   ├── SurchargeCompliance.tsx       # Modül 2: İlave Ücret
│   ├── MaterialsCompliance.tsx       # Modül 3: Tıbbi Malzeme & ÜTS / Ön Onay
│   ├── PaymentMethodCompliance.tsx   # Modül 4: Fatura Yöntemi & DRG
│   ├── SurgicalSessionCompliance.tsx # Modül 5: Cerrahi & Seans
│   ├── DiagnosticLabCompliance.tsx   # Modül 6: Laboratuvar & Tablo 15
│   ├── PreFlightDocsCompliance.tsx   # Modül 7: Evrak & Epikriz
│   └── MedulaPlaybookCompliance.tsx  # Modül 8: MEDULA Red Kılavuzu
```

### Üst Özet Risk Kartları (Compliance KPI Header)
Sayfanın en üstünde, seçilen kohort için 4 temel konsolide metrik yer alır:
1. **Toplam Denetim Riski (₺):** 8 modüldeki toplam kesinti riski tutarı.
2. **Kritik İhlalli Hasta Sayısı:** Acil düzeltme bekleyen hasta/fatura sayısı.
3. **Mevzuat Uyumluluk Skoru (%):** Kohortun SUT kurallarına uyumluluk yüzdesi (ör. %94,2).
4. **Ön Onay / Evrak Bekleyen İşlemler:** Tıbbi uygunluk veya patoloji bekleyen dosya sayısı.

---

## 4. Subtab & Navigasyon Entegrasyonu (`workspaceSubtabs.ts`)

`COMPLIANCE_SUB_IDS` 2'den 8'e genişletilir:

```typescript
// frontend/src/lib/workspaceSubtabs.ts

export type ComplianceSubSection =
  | "exemptions"
  | "surcharge"
  | "materials"
  | "payment_methods"
  | "surgical_sessions"
  | "diagnostics_lab"
  | "pre_flight_docs"
  | "medula_rejections";

export const COMPLIANCE_SUB_IDS: readonly ComplianceSubSection[] = [
  "exemptions",
  "surcharge",
  "materials",
  "payment_methods",
  "surgical_sessions",
  "diagnostics_lab",
  "pre_flight_docs",
  "medula_rejections",
] as const;

export const COMPLIANCE_SUB_ICONS: Record<ComplianceSubSection, LucideIcon> = {
  exemptions: ShieldCheck,
  surcharge: ShieldAlert,
  materials: PackageSearch,
  payment_methods: Boxes,
  surgical_sessions: Scissors,
  diagnostics_lab: FlaskConical,
  pre_flight_docs: FileCheck2,
  medula_rejections: AlertOctagon,
};
```

---

## 5. Uygulama Adımları ve Yol Haritası

### Adım 1: Navigasyon ve Alt Sekme Tipleri
- `frontend/src/lib/workspaceSubtabs.ts` güncellenerek 8 uyumluluk modülü ve ikonları tanımlanır.
- `messages/tr/workspace.ts` ve `messages/en/workspace.ts` dil anahtarları eklenir.

### Adım 2: Uyumluluk Modül Bileşenlerinin Oluşturulması
- `frontend/src/components/tabs/sut/compliance/modules/` altında 8 bağımsız modül bileşeni oluşturulur.
- Her modülde ilgili SUT kural referansları, filtreleme tablosu ve tek tıkla hasta faturasına gitme (`buildSutBillingHref`) bağlantısı yer alır.

### Adım 3: Ana Uyumluluk Paneli (`SUTComplianceDashboard.tsx`)
- `SUTCompliance.tsx` güncellenerek yeni 8 modüllü dashboard'a bağlanır.
- Kohort filtre çubuğu (`CohortFilterBar`) tüm 8 modülle senkronize edilir.

### Adım 4: Test ve Doğrulama
- Frontend `vitest` testleri ve `tsc --noEmit` çalıştırılır.
- `http://localhost:3000/?tab=compliance&subtab=materials` vb. tüm alt sekmeler doğrulanır.
