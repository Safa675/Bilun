# EK-4 LİSTELERİ

Konum: `raw data/2026.05.23-Değişiklik Tebliği İşlenmiş Güncel 2013 SUT/EK-4 LİSTELERİ`
Son güncelleme: 2026-06-22

EK-4 — İlaç geri ödeme kataloğu ve reçeteleme kuralları (SUT Bölüm 4). EK-4A ana ilaç listesidir.

## Tarife / katalog tabloları (güncel)

### EK-4A
**Bedeli ödenecek ilaçlar listesi**
- Dosya: `EK-4A BEDELİ ÖDENECEK İLAÇLAR LİSTESİ.xlsx`
- Yaklaşık satır sayısı: **8,080**
- SUT bağlantısı: §4 — SGK ilaç geri ödeme kataloğu
- BILUN kullanımı: ek4a_drugs.parquet (~8.400 ilaç) — drug optimizer, discount validation
- Tipik sütunlar: `Kamu No, Barkod, İlaç Adı, fiyat kademeleri`

### EK-4B
**Hasta özel diyet ürünleri / tıbbi mamalar (PKU, kistik fibroz, süt alerjisi)**
- Dosya: `EK-4B HAST. ÖZ. (DOĞ.MET.HAST.KİSTİK FİBR. İNEK SÜTÜ ALRJ) DİY. ÜR. TIBBİ MAM. LİST..xlsx`
- Yaklaşık satır sayısı: **76**
- SUT bağlantısı: §4 — özel beslenme
- BILUN kullanımı: Ham kaynak (curated yok)
- Tipik sütunlar: `Kamu No, Barkod, Ürün Adı`

### EK-4C
**Yurt dışı ilaç fiyat listesi**
- Dosya: `EK-4C YURT DIŞI İLAÇ FİYAT LİSTESİ.xlsx`
- Yaklaşık satır sayısı: **417**
- SUT bağlantısı: §4 — ithal / ruhsatsız ilaç fiyat referansı
- BILUN kullanımı: Ham kaynak
- Tipik sütunlar: `BARKOD, İLACIN ADI, ETKEN MADDE`

## Formlar ve açıklama belgeleri

### EK-4D
**Hasta katılım payından muaf ilaçlar**
- Dosya: `EK-4D HASTA KATILIM PAYINDAN MUAF İLAÇLAR LİSTESİ.doc`
- SUT bağlantısı: §1.8 — ilaç copay muafiyeti
- BILUN kullanımı: Ham kaynak / ek4d extractor
- Tipik sütunlar: `İlaç listesi`

### EK-4E
**Sistemik antimikrobik ve diğer ilaçların reçeteleme kuralları**
- Dosya: `EK-4E SİSTEMİK ANTİMİKROBİK VE DİĞER İLAÇLARIN REÇETELEME KURALLARI LİSTESİ.docx`
- SUT bağlantısı: §4 — antibiyotik kısıtları
- BILUN kullanımı: Prose kurallar
- Tür: Word formu / prose (makine okumalı tarife tablosu değil)

### EK-4F
**Ayakta tedavide sağlık raporu ile verilebilen ilaçlar**
- Dosya: `EK-4F AYAKTA TED. SAĞ.RAP (Uzm. Hek. Rap. Sağ. Kur. Rap.) İLE VER. İLAÇLAR.doc`
- SUT bağlantısı: §4 — rapor zorunluluğu
- BILUN kullanımı: Prose liste
- Tür: Word formu / prose (makine okumalı tarife tablosu değil)

### EK-4G
**Sadece yatarak tedavide ödenen ilaçlar**
- Dosya: `EK-4G SADECE YATARAK TEDAVİLERDE KULLANIMI HALİNDE BEDELLERİ ÖDENECEK İLAÇLAR LİSTESİ.doc`
- SUT bağlantısı: §4 — yatarak kısıtı
- BILUN kullanımı: Prose liste
- Tür: Word formu / prose (makine okumalı tarife tablosu değil)

### EK-4Ç
**Teşhis kısaltmaları listesi**
- Dosya: `EK-4Ç TEŞHİS KISALTMALARI LİSTESİ.doc`
- SUT bağlantısı: §4 — laboratuvar kısaltmaları
- BILUN kullanımı: Prose referans
- Tür: Word formu / prose (makine okumalı tarife tablosu değil)

## MÜLGA — tarihsel sürümler

Yürürlükten kalkmış EK listeleri (SGK konsolide tebliğ içindeki arşiv). BILUN fiyat geçmişi (`ek2b_catalog_history`, `ek2c_catalog_history`, …) için `scripts/sut/convert_xlsx_to_parquet.py --include-mulga` ile `data/gazette/raw/` altına dönüştürülür; varsayılan dönüşüm MÜLGA dosyalarını atlar.

Toplam **15** dosya:

### Diğer (15 sürüm)
- `MÜLGA EK-4B HAS.ÖZ.DĞ.MT.HS.KS.FB. VEİNEK SÜT AL.DİY.ÜR.TIB.M.LİS.(Yür. 02.11.2024).xlsx` — yür. `02.11.2024`, ~74 satır
- `MÜLGA EK-4C YURT DIŞI İLAÇ FİYAT LİSTESİ (Yür. 08.03.2025).xlsx` — yür. `08.03.2025`, ~402 satır
- `MÜLGA EK-4A BEDELİ ÖDENECEK İLAÇLAR LİSTESİ (Yür. 08.04.2026).xlsx` — yür. `08.04.2026`, ~8,430 satır
- `MÜLGA EK-4C YURT DIŞI İLAÇ FİYAT LİSTESİ (Yür. 08.04.2026).xlsx` — yür. `08.04.2026`, ~412 satır
- `MÜLGA EK-4A BEDELİ ÖDENECEK İLAÇLAR LİSTESİ (Yür. 10.07.2025).xlsx` — yür. `10.07.2025`, ~8,048 satır
- `MÜLGA EK-4C YURT DIŞI İLAÇ FİYAT LİSTESİ (Yür. 10.07.2025).xlsx` — yür. `10.07.2025`, ~402 satır
- `MÜLGA EK-4A BEDELİ ÖDENECEK İLAÇLAR LİSTESİ (Yür.17.01.2026).xlsx` — yür. `17.01.2026`, ~8,253 satır
- `MÜLGA EK-4C YURT DIŞI İLAÇ FİYAT LİSTESİ (Yür. 17.01.2026).xlsx` — yür. `17.01.2026`, ~406 satır
- `MÜLGA EK-4A BEDELİ ÖDENECEK İLAÇLAR LİSTESİ (Yür. 17.10.2025).xlsx` — yür. `17.10.2025`, ~8,058 satır
- `MÜLGA EK-4A BEDELİ ÖDENECEK İLAÇLAR LİSTESİ (Yür.23.05.2026).xlsx` — yür. `23.05.2026`, ~8,506 satır
- `MÜLGA EK-4A BEDELİ ÖDENECEK İLAÇLAR LİSTESİ (Yür. 24.05.2025).xlsx` — yür. `24.05.2025`, ~8,508 satır
- `MÜLGA EK-4A BEDELİ ÖDENECEK İLAÇLAR LİSTESİ (Yür. 25.03.2025).xlsx` — yür. `25.03.2025`, ~8,475 satır
- `MÜLGA EK-4A BEDELİ ÖDENECEK İLAÇLAR LİSTESİ (Yür. 25.11.2025).xlsx` — yür. `25.11.2025`, ~8,242 satır
- `MÜLGA EK-4A BEDELİ ÖDENECEK İLAÇLAR LİSTESİ (Yür. 26.06.2025).xlsx` — yür. `26.06.2025`, ~8,525 satır
- `MÜLGA EK-4C YURT DIŞI İLAÇ FİYAT LİSTESİ (Yür. 26.06.2025).xlsx` — yür. `26.06.2025`, ~400 satır

---
BILUN pipeline: `scripts/sut/convert_xlsx_to_parquet.py --include-mulga` → `data/gazette/raw/` → `data/gazette/curated/`
