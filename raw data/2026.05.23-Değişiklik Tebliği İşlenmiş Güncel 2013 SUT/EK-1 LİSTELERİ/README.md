# EK-1 LİSTELERİ

Konum: `raw data/2026.05.23-Değişiklik Tebliği İşlenmiş Güncel 2013 SUT/EK-1 LİSTELERİ`
Son güncelleme: 2026-06-22

EK-1 — Hasta hakları, katılım payı muafiyetleri ve istisnai hizmetler (SUT Bölüm 1).

## Tarife / katalog tabloları (güncel)

### EK-1A
**Ayakta tedavide hekim / diş hekimi muayenesinde katılım payı alınmayacak kronik hastalıklar listesi**
- Dosya: `EK-1A AYAKTA TED.HEK.DİŞ HEK MUA KAT PAY.ALIN KRN HAST LİS..xls`
- Yaklaşık satır sayısı: **100**
- SUT bağlantısı: §1.8.1 — kronik hastalık katılım payı muafiyeti
- BILUN kullanımı: ek1a_chronic_exemptions.parquet — copay exemption checker (L2.1)
- Tipik sütunlar: `ICD-10 kod aralıkları, hastalık adı, harf indeksi`

### EK-1C
**İstisnai sağlık hizmetleri listesi**
- Dosya: `EK-1C  İSTİSNAİ SAĞLIK HİZMETLERİ LİSTESİ.xlsx`
- Yaklaşık satır sayısı: **34**
- SUT bağlantısı: §1.5 — Kurumca karşılanmayan istisnai hizmetler
- BILUN kullanımı: Ham kaynak; curated katmanda ayrı parquet yok
- Tipik sütunlar: `SIRA NO, KODU, İŞLEM ADI`

## Formlar ve açıklama belgeleri

### EK-1B
**Hastane sunulan hizmetler ve ilave ücret gösterge belgesi**
- Yürürlük (dosya adından): `01.05.2013`
- Dosya: `EK-1B HAST. SUN.  HİZM. VE İLAVE ÜCR. GÖST. BELGE (Yürürlük 01.05.2013).docx`
- SUT bağlantısı: §1.5 — özel hastanelerde ilave ücret şeffaflığı
- BILUN kullanımı: Form şablonu; makine okumalı katalog değil
- Tür: Word formu / prose (makine okumalı tarife tablosu değil)

### EK-1D
**Acil halin sona ermesine ilişkin bilgi formu**
- Yürürlük (dosya adından): `15.02.2018`
- Dosya: `EK-1D ACİL HALİN SONA ERMESİNE İLİŞKİN BİLG. FORMU ( Yür.15.02.2018 ).doc`
- SUT bağlantısı: §1.4 — acil hal bildirimi
- BILUN kullanımı: Form şablonu
- Tür: Word formu / prose (makine okumalı tarife tablosu değil)

### EK-1E
- Yürürlük (dosya adından): `15.03.2025`
- Dosya: `EK-1E SÖZLEŞMESİZ SAĞ.HİZ.SUN.ACİL HAL.SUN.SAĞ.HİZ.İL.BİL.FORMU (Yür.15.03.2025).docx`
- Tür: Word formu / prose (makine okumalı tarife tablosu değil)

## MÜLGA — tarihsel sürümler

Yürürlükten kalkmış EK listeleri (SGK konsolide tebliğ içindeki arşiv). BILUN fiyat geçmişi (`ek2b_catalog_history`, `ek2c_catalog_history`, …) için `scripts/sut/convert_xlsx_to_parquet.py --include-mulga` ile `data/gazette/raw/` altına dönüştürülür; varsayılan dönüşüm MÜLGA dosyalarını atlar.

Toplam **1** dosya:

### Diğer (1 sürüm)
- `MÜLGA EK-1B - HAST. SUN.  HİZM. VE İLAVE ÜCR. GÖST. BELGE(Yürürlük 01.05.2013).docx` — yür. `01.05.2013`

---
BILUN pipeline: `scripts/sut/convert_xlsx_to_parquet.py --include-mulga` → `data/gazette/raw/` → `data/gazette/curated/`
