# EK-4 LİSTELERİ

Konum: `raw data/2025.01.25-Değişiklik Tebliği İşlenmiş Güncel 2013 SUT/EK-4 LİSTELERİ`
Son güncelleme: 2026-06-12

EK-4 — İlaç geri ödeme kataloğu ve reçeteleme kuralları (SUT Bölüm 4). EK-4A ana ilaç listesidir.

## Tarife / katalog tabloları

### EK-4A
**Bedeli ödenecek ilaçlar listesi**
- Dosya: `EK-4-A BEDELİ ÖDENECEK İLAÇLAR LİSTESİ.xlsx`
- Yaklaşık satır sayısı: **8,377**
- SUT bağlantısı: §4 — SGK ilaç geri ödeme kataloğu
- BILUN kullanımı: ek4a_drugs.parquet (~8.400 ilaç) — drug optimizer, discount validation
- Tipik sütunlar: `Kamu No, Barkod, İlaç Adı, fiyat kademeleri`

### EK-4B
**Hasta özel diyet ürünleri / tıbbi mamalar (PKU, kistik fibroz, süt alerjisi)**
- Dosya: `EK-4-B HAST. ÖZ. (DOĞ.MET.HAST.KİSTİK FİBR. İNEK SÜTÜ ALRJ) DİY. ÜR. TIBBİ MAM. LİST..xlsx`
- Yaklaşık satır sayısı: **76**
- SUT bağlantısı: §4 — özel beslenme
- BILUN kullanımı: Ham kaynak (curated yok)
- Tipik sütunlar: `Kamu No, Barkod, Ürün Adı`

### EK-4C
**Yurt dışı ilaç fiyat listesi**
- Dosya: `EK-4-C YURT DIŞI İLAÇ FİYAT LİSTESİ.xlsx`
- Yaklaşık satır sayısı: **402**
- SUT bağlantısı: §4 — ithal / ruhsatsız ilaç fiyat referansı
- BILUN kullanımı: Ham kaynak
- Tipik sütunlar: `BARKOD, İLACIN ADI, ETKEN MADDE`

## Formlar ve açıklama belgeleri

### EK-4D
**Hasta katılım payından muaf ilaçlar**
- Dosya: `EK-4-D HASTA KATILIM PAYINDAN MUAF İLAÇLAR LİSTESİ.doc`
- SUT bağlantısı: §1.8 — ilaç copay muafiyeti
- BILUN kullanımı: Ham kaynak / ek4d extractor
- Tipik sütunlar: `İlaç listesi`

### EK-4E
**Sistemik antimikrobik ve diğer ilaçların reçeteleme kuralları**
- Dosya: `EK-4-E SİSTEMİK ANTİMİKROBİK VE DİĞER İLAÇLARIN REÇETELEME KURALLARI LİSTESİ.docx`
- SUT bağlantısı: §4 — antibiyotik kısıtları
- BILUN kullanımı: Prose kurallar
- Tür: Word formu / prose (makine okumalı tarife tablosu değil)

### EK-4F
**Ayakta tedavide sağlık raporu ile verilebilen ilaçlar**
- Dosya: `EK-4-F AYAKTA TED. SAĞ.RAP (Uzm. Hek. Rap. Sağ. Kur. Rap.) İLE VER. İLAÇLAR.doc`
- SUT bağlantısı: §4 — rapor zorunluluğu
- BILUN kullanımı: Prose liste
- Tür: Word formu / prose (makine okumalı tarife tablosu değil)

### EK-4G
**Sadece yatarak tedavide ödenen ilaçlar**
- Dosya: `EK-4-G SADECE YATARAK TEDAVİLERDE KULLANIMI HALİNDE BEDELLERİ ÖDENECEK İLAÇLAR LİSTESİ.doc`
- SUT bağlantısı: §4 — yatarak kısıtı
- BILUN kullanımı: Prose liste
- Tür: Word formu / prose (makine okumalı tarife tablosu değil)

### EK-4Ç
**Teşhis kısaltmaları listesi**
- Dosya: `EK-4-Ç TEŞHİS KISALTMALARI LİSTESİ.doc`
- SUT bağlantısı: §4 — laboratuvar kısaltmaları
- BILUN kullanımı: Prose referans
- Tür: Word formu / prose (makine okumalı tarife tablosu değil)

---
BILUN pipeline: `scripts/sut/convert_xlsx_to_parquet.py` → `data/gazette/raw/` → `data/gazette/curated/`
