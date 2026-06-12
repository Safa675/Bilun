# EK-2 LİSTELERİ

Konum: `raw data/2026.01.17-Değişiklik Tebliği İşlenmiş Güncel 2013 SUT/EK-2 LİSTELERİ`
Son güncelleme: 2026-06-12

EK-2 — İşlem fiyatlandırma, DRG paketleri, diş tedavileri ve formlar (SUT Bölüm 2). BILUN'un ana fiyat motoru EK-2B ve EK-2C'den beslenir.

## Tarife / katalog tabloları

### EK-2A
**Ayaktan başvurularda ödeme listesi (poliklinik / muayene ücretleri)**
- Yürürlük (dosya adından): `01.01.2026`
- Dosya: `EK-2A AYAKTAN BAŞVURULARDA ÖDEME LİSTESİ (Yür.01.01.2026).xlsx`
- Yaklaşık satır sayısı: **99**
- SUT bağlantısı: §2.2.2.A — ayakta ziyaret fiyatlandırması
- BILUN kullanımı: ek2a_outpatient_visits.parquet
- Tipik sütunlar: `KODU, uzmanlık dalları, ÖH3/U1/U2/U3 fiyat sütunları`

### EK-2A-2
**Ayaktan başvuruda ilave olarak faturalandırılabilecek işlemler listesi**
- Yürürlük (dosya adından): `01.06.2021`
- Dosya: `EK-2A-2 AYAKTAN BAŞ. İLAVE OL. FAT. İŞ. LİSTESİ (Yür. 01.06.2021).xlsx`
- Yaklaşık satır sayısı: **515**
- SUT bağlantısı: §2.2.2.A(5) — ziyarete ek işlem
- BILUN kullanımı: Ham kaynak
- Tipik sütunlar: `İŞLEM KODU, İŞLEM ADI, AÇIKLAMA`

### EK-2B
**Hizmet başı işlem puan listesi (fee-for-service tarife)**
- Yürürlük (dosya adından): `31.01.2026`
- Dosya: `EK-2B HİZMET BAŞI İŞLEM PUAN LİSTESİ (Yür. 31.01.2026).xlsx`
- Yaklaşık satır sayısı: **7,523**
- SUT bağlantısı: §2.2.2 — işlem bazlı ödeme; ana prosedür kataloğu
- BILUN kullanımı: ek2b_catalog_history.parquet (~7.500 kod) — birincil fiyat motoru
- Tipik sütunlar: `İŞLEM KODU, İŞLEM ADI, İŞLEM PUANI`

### EK-2C
**Tanıya dayalı işlem puan listesi (DRG / paket fiyatlandırma)**
- Yürürlük (dosya adından): `31.01.2026`
- Dosya: `EK-2C TANIYA DAYALI İŞLEM PUAN LİSTESİ (Yür. 31.01.2026).xlsx`
- Yaklaşık satır sayısı: **2,616**
- SUT bağlantısı: §2.2.2.B — ICD-10 bölümüne göre paket kodları
- BILUN kullanımı: ek2c_catalog_history.parquet — DRG unbundling, paket vs kalem
- Tipik sütunlar: `İŞLEM KODU, İŞLEM GRUBU, İŞLEM PUANI`

### EK-2C-1
**İlave oran uygulanacak işlemler listesi**
- Yürürlük (dosya adından): `01.06.2021`
- Dosya: `EK-2C-1 İLAVE ORAN UYGULANACAK İŞLEMLER LİSTESİ (Yür. 01.06.2021).xlsx`
- Yaklaşık satır sayısı: **471**
- SUT bağlantısı: §2.2.2(20) — kurum sınıfına göre puan/katılım oranı
- BILUN kullanımı: ek2c1_copay_rates.parquet — copay rate exposure (L2.4)
- Tipik sütunlar: `İŞLEM KODU, ORAN (%)`

### EK-2D-2
**Fizik tedavi ve rehabilitasyon tanı listesi**
- Yürürlük (dosya adından): `01.10.2014`
- Dosya: `EK-2D-2 FİZİK TED.VE REH. TANI LİST (Yür. 01.10.2014).xlsx`
- Yaklaşık satır sayısı: **199**
- SUT bağlantısı: §2.2 — FTR endikasyon ICD kodları
- BILUN kullanımı: Ham kaynak
- Tipik sütunlar: `ICD-10 kodu, tanı adı`

### EK-2D-3
**Hiperbarik oksijen tedavisi uygulama listesi**
- Dosya: `EK-2D-3 HİPERBARİK OKSİJEN TEDAVİSİ UYGULAMA LİSTESİ.xls`
- SUT bağlantısı: §2.2 — HBO endikasyonları
- BILUN kullanımı: Ham kaynak
- Tipik sütunlar: `Endikasyon kodları`

### EK-2D-4
**İntraoperatif nöromonitöring — ayrı faturalandırılabilir işlemler**
- Yürürlük (dosya adından): `01.01.2026`
- Dosya: `EK-2D-4 İNT.NÖROMON.İŞL.AYR.FAT.İŞ. LİSTESİ (Yür.01.01.2026).xlsx`
- Yaklaşık satır sayısı: **67**
- SUT bağlantısı: §2.2 — EK-2/C paketinden ayrı EK-2/B kalemleri
- BILUN kullanımı: Ham kaynak — paket/kalem ayrımı
- Tipik sütunlar: `EK-2/C Kodu, EK-2/B Kodu, İşlem Adı`

### EK-2G
**İlave ücret uygulanmayacak işlemler listesi**
- Yürürlük (dosya adından): `05.07.2018`
- Dosya: `EK-2G İLAVE ÜCRET UYGULANMAYACAK İŞLEMLER LİSTESİ (Yür. 05.07.2018).xlsx`
- Yaklaşık satır sayısı: **423**
- SUT bağlantısı: §1.5 — ilave ücret yasağı
- BILUN kullanımı: ek2g_no_surcharge.parquet — surcharge eligibility (L2.3)
- Tipik sütunlar: `KODU, İŞLEM ADI`

### EK-2K
**PGT ile IVF yapılan kalıtsal hastalıklar listesi**
- Yürürlük (dosya adından): `11.08.2021`
- Dosya: `EK-2K PREİMPLANT.GEN.TANI(PGT) İLE İNVİTRO FER.(IVF) YAP.KAL.HAS.LİS. (Yür.11.08.2021).xls`
- SUT bağlantısı: §2.2 — tüp bebek / PGT endikasyonları
- BILUN kullanımı: Ham kaynak
- Tipik sütunlar: `Hastalık / ICD kodları`

### EK-2L
**Mutat taşıt yol ücreti listesi**
- Yürürlük (dosya adından): `30.04.2024`
- Dosya: `EK-2L MUTAT TAŞIT YOL ÜCRETİ LİSTESİ (Yür.30.04.2024).xlsx`
- Yaklaşık satır sayısı: **30**
- SUT bağlantısı: §2.2 — sevk yol ücreti
- BILUN kullanımı: Ham kaynak
- Tipik sütunlar: `SUT Kodu, Mesafe (km), Ücret (TL)`

### EK-2Ç
**Diş tedavileri puan listesi**
- Yürürlük (dosya adından): `01.01.2026`
- Dosya: `EK-2Ç DİŞ TEDAVİLERİ PUAN LİSTESİ (Yür.01.01.2026).xls`
- SUT bağlantısı: §2.2 — ağız diş sağlığı işlemleri
- BILUN kullanımı: Ham kaynak (diş prosedürleri EK-2B'den ayrı)
- Tipik sütunlar: `Diş işlem kodları ve puanları`

## Formlar ve açıklama belgeleri

### EK-2A-1
**Sağlık hizmeti sunucularının ayakta tedavilerde sınıflandırılması listesi**
- Yürürlük (dosya adından): `19.09.2025`
- Dosya: `EK-2A-1 SAĞLIK HİZMETİ SUN. AYAKTA TED. SINIFLANDIRILMASI LİS. (Yür. 19.09.2025).docx`
- SUT bağlantısı: §2.2 — kurum sınıfı (ÖH3, U1, U2, U3)
- BILUN kullanımı: Referans tablo; EK-2A fiyat sütunlarıyla eşleşir
- Tipik sütunlar: `Kurum türü, sınıf`

### EK-2D-1
**PET görüntüleme klinik uygulama kriterleri**
- Yürürlük (dosya adından): `30.04.2024`
- Dosya: `EK-2D-1 POZİT. EMİ.TOM. (PET) GÖR. KLİNİK UYG. (Yür. 30.04.2024).docx`
- SUT bağlantısı: §2.2 — PET endikasyonları
- BILUN kullanımı: Klinik kriter prose
- Tür: Word formu / prose (makine okumalı tarife tablosu değil)

### EK-2D-5
**İntraoperatif nöronavigasyon — ayrı faturalandırılabilir işlemler**
- Yürürlük (dosya adından): `25.12.2021`
- Dosya: `EK-2D-5 “İNTRAOPERATİF NÖRONAVİGASYON” İŞL AYR FATURALAN İŞL LİST (Yür.25.12.2021).docx`
- SUT bağlantısı: §2.2 — nöronavigasyon eşlemesi
- BILUN kullanımı: Ham kaynak
- Tipik sütunlar: `İşlem kod eşlemeleri`

### EK-2E-1
**Yurt dışına tedaviye gönderileceklere ilişkin belge**
- Dosya: `EK-2E-1 YURT DIŞINA TEDAVİYE GÖNDERİLECEKLERE İLİŞKİN.doc`
- SUT bağlantısı: §2.3 — yurt dışı tedavi
- BILUN kullanımı: Form şablonu
- Tür: Word formu / prose (makine okumalı tarife tablosu değil)

### EK-2E-2
**Yurt dışı tetkike ilişkin sağlık kurulu raporu**
- Dosya: `EK-2E-2 YURT DIŞI TETKİKE İLİŞKİN SAĞLIK KURULU RAPORU.doc`
- SUT bağlantısı: §2.3
- BILUN kullanımı: Form şablonu
- Tür: Word formu / prose (makine okumalı tarife tablosu değil)

### EK-2E-3
**Yurt dışı tedavi/tetkik hasta izleme çizelgesi**
- Dosya: `EK-2E-3 YURT DIŞI TEDAVİ TETKİK İÇİN HASTA İZLEME ÇİZELGESİ.doc`
- SUT bağlantısı: §2.3
- BILUN kullanımı: Form şablonu
- Tür: Word formu / prose (makine okumalı tarife tablosu değil)

### EK-2F
**Hasta sevk formu**
- Dosya: `EK-2F HASTA SEVK FORMU.doc`
- SUT bağlantısı: §2.1 — sevk zinciri
- BILUN kullanımı: Form şablonu
- Tür: Word formu / prose (makine okumalı tarife tablosu değil)

### EK-2Y
**Yasa dışı ve kötüye kullanılan madde doğrulama analiz formu**
- Yürürlük (dosya adından): `11.02.2020`
- Dosya: `EK-2Y YASA DIŞI VE KÖTÜYE KULL. MAD. DOĞ. ANALİZ. FORMU (Yür.11.02.2020).docx`
- SUT bağlantısı: §2.2 — madde bağımlılığı tarama
- BILUN kullanımı: Form şablonu
- Tür: Word formu / prose (makine okumalı tarife tablosu değil)

### EK-2Ç-1
**Diş tedavileri puan listesine ilişkin açıklamalar**
- Dosya: `EK-2Ç-1 DİŞ TEDAVİLERİ PUAN LİSTESİNE İLİŞKİN AÇIKLAMALAR.doc`
- SUT bağlantısı: EK-2Ç yorumlama notları
- BILUN kullanımı: Prose/açıklama belgesi
- Tür: Word formu / prose (makine okumalı tarife tablosu değil)

### EK-2Ç-2
**Diş tedavileri kontrol formu**
- Yürürlük (dosya adından): `25.07.2014`
- Dosya: `EK-2Ç-2  DİŞ TEDAVİLERİ KONTROL FORMU (Yür. 25.07.2014).doc`
- SUT bağlantısı: Diş tedavisi denetim formu
- BILUN kullanımı: Form şablonu
- Tür: Word formu / prose (makine okumalı tarife tablosu değil)

### EK-2Ç-3
**Tanıya dayalı ortodontik tedavi kontrol formu**
- Yürürlük (dosya adından): `04.03.2019`
- Dosya: `EK-2Ç-3 TANIYA DAYALI ORTODONTİK TEDAVİ KONTROL FORMU (Yür. 04.03.2019).docx`
- SUT bağlantısı: Ortodonti ön onay
- BILUN kullanımı: Form şablonu
- Tür: Word formu / prose (makine okumalı tarife tablosu değil)

---
BILUN pipeline: `scripts/sut/convert_xlsx_to_parquet.py` → `data/gazette/raw/` → `data/gazette/curated/`
