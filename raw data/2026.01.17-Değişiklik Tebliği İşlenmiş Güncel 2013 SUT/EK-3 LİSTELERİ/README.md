# EK-3 LİSTELERİ

Konum: `raw data/2026.01.17-Değişiklik Tebliği İşlenmiş Güncel 2013 SUT/EK-3 LİSTELERİ`
Son güncelleme: 2026-06-15

EK-3 — Tıbbi malzeme, sarf, protez ve branş bazlı implant tavan fiyatları (SUT Bölüm 3). En çok dosya burada; B/C alt listeleri ödeme kurallarını, E–T alt listeleri branş kataloglarını taşır.

## EK-3 hızlı harita

SGK malzeme eklerini iki aileye ayırır:

| Aile | Ekler | Soru |
|------|-------|------|
| **Ödeme kuralları** | EK-3B, EK-3B-1, EK-3B-2, EK-3C (+ C-1..C-5) | Bu malzeme faturalanabilir mi? SGK öder mi? Rapor gerekir mi? |
| **Branş fiyat tavanları** | EK-3A, EK-3D, EK-3E..3T | Bu implant/sarf için SGK tavan fiyatı ne? |

- **EK-3B-1** → işlem paketine dahil sarf (ayrı satır faturalandırılamaz)
- **EK-3B-2** → SGK hiç ödemez
- **EK-3C-*** → ayakta tedavide protez/sarf; C-1 ön onay, C-2 MIAT aralığı
- **EK-3H / EK-3I** → kardiyoloji / kalp cerrahisi (stent, ICD, kapak)
- **EK-3F-*** → ortopedi alt alanları (artroplasti, artroskopi, tümör, travma)

## Tarife / katalog tabloları (güncel)

### EK-3A
**Birden fazla branşta kullanılan tıbbi malzemeler**
- Yürürlük (dosya adından): `13.12.2025`
- Dosya: `EK-3A BİRDEN FAZLA BRANŞTA KULLANILAN TIBBİ MALZEMELER LİS. (Yür.13.12.2025).xlsx`
- Yaklaşık satır sayısı: **513**
- SUT bağlantısı: §3.3 — çok disiplinli sarf/implant
- BILUN kullanımı: ek3a_multibranch_materials.parquet
- Tipik sütunlar: `SUT KODU, malzeme tanımı, FİYAT (TL)`

### EK-3B
**Kurumca bedeli karşılanmayan tıbbi malzemeler (ana liste)**
- Yürürlük (dosya adından): `03.09.2022`
- Dosya: `EK-3B KURUMCA BEDELİ KARŞILANMAYAN TIBBİ MALZEMELER LİSTESİ (Yür.03.09.2022).xls`
- SUT bağlantısı: §3.1.1(7)/(9) — EK-3/B üst liste
- BILUN kullanımı: Üst katalog; alt listeler 3B-1 ve 3B-2
- Tipik sütunlar: `Malzeme kodu ve adı`

### EK-3B-1
**İşlem puanına dahil basit sıhhi sarf malzemeler**
- Yürürlük (dosya adından): `03.09.2022`
- Dosya: `EK-3B-1 İŞLEM PUANINA DAHİL BASİT SIHHİ SARF MALZEMELER LİSTESİ (Yür.03.09.2022).xls`
- SUT bağlantısı: §3.1.1 — paket içi sarf; ayrı faturalandırılamaz
- BILUN kullanımı: ek3b1_bundled_consumables.parquet (54 kalem) — bundling rule (L1.1)
- Tipik sütunlar: `Sarf kategorisi / malzeme adı`

### EK-3B-2
**Kurumca bedeli karşılanmayan diğer tıbbi malzemeler**
- Yürürlük (dosya adından): `03.09.2022`
- Dosya: `EK-3B-2 KURUMCA BEDELİ KARŞILANMAYAN DİĞER TIBBİ MALZ. LİSTESİ (Yür.03.09.2022).xls`
- SUT bağlantısı: §3.1.1 — SGK ödemez
- BILUN kullanımı: ek3b2_non_reimbursable.parquet (13 kalem) — exclusion rule (L1.2)
- Tipik sütunlar: `Malzeme adı`

### EK-3C
**Ayakta tedavilerde kullanılan tıbbi malzemeler (üst liste)**
- Yürürlük (dosya adından): `03.09.2022`
- Dosya: `EK-3C AYAKTA TEDAVİLERDE KULLANILAN TIBBİ MALZEMELER LİSTESİ (Yür.03.09.2022).xls`
- SUT bağlantısı: §3.1.2 — ayakta malzeme ödeme kuralları
- BILUN kullanımı: Alt listeler C-1..C-5 + formlar
- Tipik sütunlar: `SUT kodu, fiyat`

### EK-3C-1
**Tıbbi uygunluk aranacak tıbbi malzemeler**
- Yürürlük (dosya adından): `03.09.2022`
- Dosya: `EK-3C-1 TIBBİ UYGUNLUK ARANACAK TIBBİ MALZEMELER LİSTESİ (Yür.03.09.2022).xls`
- SUT bağlantısı: §3.1.2 — ön onay / rapor zorunluluğu
- BILUN kullanımı: ek3c1_materials.parquet — material pre-check
- Tipik sütunlar: `SUT kodu, malzeme, koşullar`

### EK-3C-2
**Eksternal alt/üst ekstremite ve gövde protez-ortezler**
- Yürürlük (dosya adından): `24.01.2026`
- Dosya: `EK-3C-2 EKSTERNAL ALT VE ÜST EKSTREMİTE GÖVDE PROT. ORTEZ. LİS. (Yür. 24.01.2026).xls`
- SUT bağlantısı: §3.1.2 — protez/ortez + MIAT aralıkları
- BILUN kullanımı: ek3c2_materials.parquet — MIAT interval checks (L3.5)
- Tipik sütunlar: `SUT kodu, MIAT, fiyat`

### EK-3C-3
**Diğer protez-ortezler**
- Yürürlük (dosya adından): `24.01.2026`
- Dosya: `EK-3C-3 DİĞER PROTEZ ORTEZLER LİSTESİ (Yür. 24.01.2026).xls`
- SUT bağlantısı: §3.1.2
- BILUN kullanımı: ek3c3_materials.parquet
- Tipik sütunlar: `SUT kodu, fiyat`

### EK-3C-4
**Tıbbi sarf malzemeler**
- Yürürlük (dosya adından): `24.01.2026`
- Dosya: `EK-3C-4 TIBBİ SARF MALZEMELER LİSTESİ (Yür. 24.01.2026).xls`
- SUT bağlantısı: §3.1.2
- BILUN kullanımı: ek3c4_materials.parquet
- Tipik sütunlar: `SUT kodu, fiyat`

### EK-3C-5
**Özel hallerde karşılanan tıbbi malzemeler**
- Yürürlük (dosya adından): `24.01.2026`
- Dosya: `EK-3C-5 ÖZEL HALLERDE KARŞILANAN TIBBİ MALZEMELER LİST.(Yür. 24.01.2026).xls`
- SUT bağlantısı: §3.1.2
- BILUN kullanımı: ek3c5_materials.parquet
- Tipik sütunlar: `SUT kodu, koşul, fiyat`

### EK-3D
**Görmeye yardımcı tıbbi malzemeler (gözlük, lens vb.)**
- Yürürlük (dosya adından): `01.01.2026`
- Dosya: `EK-3D GÖRMEYE YARDIMCI TIBBİ MALZEMELER LİSTESİ (Yür.01.01.2026).xlsx`
- Yaklaşık satır sayısı: **56**
- SUT bağlantısı: §3.3.3.A
- BILUN kullanımı: ek3d_vision_materials.parquet
- Tipik sütunlar: `SPH, SUT KODU, FİYAT`

### EK-3E-1
**Omurga cerrahisi alan grubuna ait tıbbi malzemeler**
- Yürürlük (dosya adından): `13.12.2025`
- Dosya: `EK-3E-1 OMURGA CERRAHİSİ ALAN GR. AİT TIBBİ MALZ. LİST. (Yür.13.12.2025).xlsx`
- Yaklaşık satır sayısı: **287**
- SUT bağlantısı: §3.3 — branş/alan bazlı implant fiyat tavanı
- BILUN kullanımı: ek3e1_spine_materials.parquet
- Tipik sütunlar: `SUT KODU, alan tanımı, FİYAT (TL)`

### EK-3E-2
**Beyin cerrahisi / kraniyal cerrahi malzemeleri**
- Yürürlük (dosya adından): `13.12.2025`
- Dosya: `EK-3E-2 BEYİN CER.BR.KRANİAL CER. ALAN GR.AİT TIB.MAL.LİST. (Yür.13.12.2025).xlsx`
- Yaklaşık satır sayısı: **159**
- SUT bağlantısı: §3.3
- BILUN kullanımı: ek3e2_cranial_materials.parquet
- Tipik sütunlar: `SUT KODU, FİYAT (TL)`

### EK-3F-1
**Ortopedi — artroplasti (kalça/diz protezi vb.)**
- Yürürlük (dosya adından): `13.12.2025`
- Dosya: `EK-3F-1 ORT.TRAV.BR.ARTROPLASTİ ALAN GR. AİT TIB. MALZ. LİST. (Yür.13.12.2025).xlsx`
- Yaklaşık satır sayısı: **341**
- SUT bağlantısı: §3.3
- BILUN kullanımı: ek3f1_arthroplasty_materials.parquet — L4.4 prose (kalça)
- Tipik sütunlar: `Hiyerarşik implant ağacı + SUT kodu`

### EK-3F-2
**Ortopedi — artroskopi ve eklem cerrahisi**
- Yürürlük (dosya adından): `13.12.2025`
- Dosya: `EK-3F-2 ORT.TRAV.BR.ARTROS.EKL.CER.ALAN GR.AİT TIB.MALZ.LİS. (Yür.13.12.2025).xlsx`
- Yaklaşık satır sayısı: **193**
- SUT bağlantısı: §3.3
- BILUN kullanımı: ek3f2_arthroscopy_materials.parquet
- Tipik sütunlar: `SUT KODU, FİYAT`

### EK-3F-3
**Ortopedi — tümör rezeksiyonu**
- Yürürlük (dosya adından): `13.12.2025`
- Dosya: `EK-3F-3 ORT.TRAV.BR.TÜMÖR REZEK.ALAN GR.AİT TIB. MALZ. LİST. (Yür.13.12.2025).xlsx`
- Yaklaşık satır sayısı: **185**
- SUT bağlantısı: §3.3
- BILUN kullanımı: ek3f3_tumor_materials.parquet
- Tipik sütunlar: `SUT KODU, FİYAT`

### EK-3F-4
**Ortopedi — travma ve rekonstrüksiyon**
- Yürürlük (dosya adından): `13.12.2025`
- Dosya: `EK-3F-4 ORT.TRAV.BR.TRAV. REKONS.ALAN GR. AİT TIB.MALZ.LİST (Yür.13.12.2025).xlsx`
- Yaklaşık satır sayısı: **523**
- SUT bağlantısı: §3.3
- BILUN kullanımı: ek3f4_trauma_materials.parquet
- Tipik sütunlar: `SUT KODU, plak/vida hiyerarşisi`

### EK-3G
**Göz sağlığı ve hastalıkları branşı malzemeleri**
- Yürürlük (dosya adından): `13.12.2025`
- Dosya: `EK-3G GÖZ SAĞLIĞI VE HAST. BRNŞ. AİT TIBBİ MALZ. LİST. (Yür.13.12.2025).xlsx`
- Yaklaşık satır sayısı: **262**
- SUT bağlantısı: §3.3
- BILUN kullanımı: ek3g_ophthalmology_materials.parquet
- Tipik sütunlar: `SUT KODU, FİYAT`

### EK-3H
**Kardiyoloji branşı malzemeleri (stent, balon vb.)**
- Yürürlük (dosya adından): `13.12.2025`
- Dosya: `EK-3H KARDİYOLOJİ BRANŞINA AİT TIBBİ MALZ. LİST. (Yür.13.12.2025).xlsx`
- Yaklaşık satır sayısı: **355**
- SUT bağlantısı: §3.3
- BILUN kullanımı: ek3h_cardiology_materials.parquet — PCI stent prose
- Tipik sütunlar: `SUT KODU, FİYAT`

### EK-3I
**Kalp damar cerrahisi malzemeleri (ICD, kapak, greft)**
- Yürürlük (dosya adından): `13.12.2025`
- Dosya: `EK-3I KALP DAMAR CERRAHİSİ BRNŞ. AİT TIBBİ MALZ. LİST. (Yür 13.12.2025).xlsx`
- Yaklaşık satır sayısı: **545**
- SUT bağlantısı: §3.3
- BILUN kullanımı: ek3i_cv_surgery_materials.parquet
- Tipik sütunlar: `SUT KODU, FİYAT`

### EK-3J
**KBB branşı malzemeleri**
- Yürürlük (dosya adından): `13.12.2025`
- Dosya: `EK-3J KULAK BURUN BOĞAZ BRNŞ. AİT TIBBİ MALZ. LİST. (Yür.13.12.2025).xlsx`
- Yaklaşık satır sayısı: **35**
- SUT bağlantısı: §3.3
- BILUN kullanımı: ek3j_ent_materials.parquet
- Tipik sütunlar: `SUT KODU, FİYAT`

### EK-3K
**Kadın hastalıkları ve doğum malzemeleri**
- Yürürlük (dosya adından): `13.12.2025`
- Dosya: `EK-3K KADIN HAST. VE DOĞUM BRNŞ. AİT TIBBİ MALZ. LİST. (Yür.13.12.2025).xlsx`
- Yaklaşık satır sayısı: **30**
- SUT bağlantısı: §3.3
- BILUN kullanımı: ek3k_obgyn_materials.parquet
- Tipik sütunlar: `SUT KODU, FİYAT`

### EK-3L
**Üroloji malzemeleri**
- Yürürlük (dosya adından): `13.12.2025`
- Dosya: `EK-3L ÜROLOJİ BRANŞINA AİT TIBBİ MALZEMELER LİSTESİ (Yür.13.12.2025).xlsx`
- Yaklaşık satır sayısı: **113**
- SUT bağlantısı: §3.3
- BILUN kullanımı: ek3l_urology_materials.parquet
- Tipik sütunlar: `SUT KODU, FİYAT`

### EK-3M
**Radyoloji ve endovasküler girişim malzemeleri**
- Yürürlük (dosya adından): `13.12.2025`
- Dosya: `EK-3M RADYOLOJİ BR VE END.NONV. GİR İŞL AİT TIB MALZ LİST. (Yür.13.12.2025).xlsx`
- Yaklaşık satır sayısı: **417**
- SUT bağlantısı: §3.3
- BILUN kullanımı: ek3m_radiology_materials.parquet
- Tipik sütunlar: `SUT KODU, FİYAT`

### EK-3N-1
**Allogreft ürün grubu**
- Yürürlük (dosya adından): `13.12.2025`
- Dosya: `EK-3N-1 ALLOGREFT ÜRÜN GRUBU LİSTESİ (Yür.13.12.2025).xlsx`
- Yaklaşık satır sayısı: **126**
- SUT bağlantısı: §3.3
- BILUN kullanımı: ek3n1_allograft_materials.parquet
- Tipik sütunlar: `SUT KODU, FİYAT`

### EK-3N-2
**Xenogreft ürün grubu**
- Yürürlük (dosya adından): `13.12.2025`
- Dosya: `EK-3N-2 XENOGREFT ÜRÜN GRUBU LİSTESİ (Yür.13.12.2025).xlsx`
- Yaklaşık satır sayısı: **33**
- SUT bağlantısı: §3.3
- BILUN kullanımı: ek3n2_xenograft_materials.parquet
- Tipik sütunlar: `SUT KODU, FİYAT`

### EK-3N-3
**Sentetik greft ürün grubu**
- Yürürlük (dosya adından): `13.12.2025`
- Dosya: `EK-3N-3 SENTETİK GREFT ÜRÜN GRUBU LİSTESİ (Yür.13.12.2025).xlsx`
- Yaklaşık satır sayısı: **19**
- SUT bağlantısı: §3.3
- BILUN kullanımı: ek3n3_synthetic_graft_materials.parquet
- Tipik sütunlar: `SUT KODU, FİYAT`

### EK-3O
**Hematoloji-onkoloji malzemeleri**
- Yürürlük (dosya adından): `13.12.2025`
- Dosya: `EK-3O HEMATOLOJİ-ONKOLOJİ BRNŞ. AİT TIBBİ MALZ. LİST. (Yür.13.12.2025).xlsx`
- Yaklaşık satır sayısı: **34**
- SUT bağlantısı: §3.3
- BILUN kullanımı: ek3o_hematology_oncology_materials.parquet
- Tipik sütunlar: `SUT KODU, FİYAT`

### EK-3P
**Nefroloji malzemeleri (diyaliz vb.)**
- Yürürlük (dosya adından): `13.12.2025`
- Dosya: `EK-3P NEFROLOJİ BRANŞINA AİT TIBBİ MALZEMELER LİSTESİ (Yür.13.12.2025).xlsx`
- Yaklaşık satır sayısı: **49**
- SUT bağlantısı: §3.3
- BILUN kullanımı: ek3p_nephrology_materials.parquet
- Tipik sütunlar: `SUT KODU, FİYAT`

### EK-3R
**Gastroenteroloji malzemeleri**
- Yürürlük (dosya adından): `13.12.2025`
- Dosya: `EK-3R GASTROENTEROLOJİ BRANŞINA AİT TIBBİ MALZ. LİST. (Yür.13.12.2025).xlsx`
- Yaklaşık satır sayısı: **189**
- SUT bağlantısı: §3.3
- BILUN kullanımı: ek3r_gastroenterology_materials.parquet
- Tipik sütunlar: `SUT KODU, FİYAT`

### EK-3S
**Göğüs hastalıkları ve göğüs cerrahisi malzemeleri**
- Yürürlük (dosya adından): `13.12.2025`
- Dosya: `EK-3S GÖĞÜS HAST VE GÖĞ. CERR. BRNŞ. AİT TIBBİ MLZ. LİST. (Yür.13.12.2025).xlsx`
- Yaklaşık satır sayısı: **101**
- SUT bağlantısı: §3.3
- BILUN kullanımı: ek3s_pulmonology_materials.parquet
- Tipik sütunlar: `SUT KODU, FİYAT`

### EK-3T
**Anesteziyoloji, reanimasyon ve ağrı tedavisi malzemeleri**
- Yürürlük (dosya adından): `13.12.2025`
- Dosya: `EK-3T ANEST, REAN VE AĞRI TED. BRNŞ. AİT TIBBİ MLZ. LİST. (Yür.13.12.2025).xlsx`
- Yaklaşık satır sayısı: **40**
- SUT bağlantısı: §3.3
- BILUN kullanımı: ek3t_anesthesiology_materials.parquet
- Tipik sütunlar: `SUT KODU, FİYAT`

## Formlar ve açıklama belgeleri

### EK-3C-6
**Ampute mobilite ölçeği formu**
- Yürürlük (dosya adından): `22.03.2025`
- Dosya: `EK-3C-6 AMPUTE MOB. ÖLÇEĞİ FORMU (Yür.22.03.2025).docx`
- SUT bağlantısı: §3.1.2 — protez değerlendirme
- BILUN kullanımı: Form şablonu (2026 tebliğinde yeni)
- Tür: Word formu / prose (makine okumalı tarife tablosu değil)

## MÜLGA — tarihsel sürümler

Yürürlükten kalkmış EK listeleri (SGK konsolide tebliğ içindeki arşiv). BILUN fiyat geçmişi (`ek2b_catalog_history`, `ek2c_catalog_history`, …) için `scripts/sut/convert_xlsx_to_parquet.py --include-mulga` ile `data/gazette/raw/` altına dönüştürülür; varsayılan dönüşüm MÜLGA dosyalarını atlar.

Toplam **202** dosya:

### Diğer (202 sürüm)
- `MÜLGA EK-3A BİRDEN FAZLA BRANŞTA KULLANILAN TIBBİ MALZEMELER.xls`
- `MÜLGA EK-3B KURUMCA BEDELİ KARŞILANMAYAN TIBBİ MALZEMELER.xls`
- `MÜLGA EK-3B-1 İŞLEM PUANINA DAHİL BASİT SIHHİ SARF MALZEMELER.xls`
- `MÜLGA EK-3B-2 KURUMCA BEDELİ KARŞILANMAYAN DİĞER TIBBİ MALZEMELER.xls`
- `MÜLGA EK-3C  AYAKTA TEDAVİLERDE KULLANILAN TIBBİ MALZEMELER.xls`
- `MÜLGA EK-3C-1 (Yür-01.01.2015)TIBBİ UYGUNLUK ARANACAK TIBBİ MALZEMELER.xls`
- `MÜLGA EK-3C-1 TIBBİ UYGUNLUK ARANACAK TIBBİ MALZEMELER (Yür-01.01.2015).xls`
- `MÜLGA EK-3C-2 EKST. ALT VE ÜST EKST.GÖVDE PRO. ORT (Yür-01.10.2014).xls`
- `MÜLGA EK-3C-3 DİĞER PROTEZ ORTEZLER.xls`
- `MÜLGA EK-3C-4 TIBBİ SARF MALZEMELER.xls`
- `MÜLGA EK-3C-5(Yür-01.01.2015) YENİ ÖZEL HAL. KARŞ. TIBBİ MALZ (Yür.-01.10.2014).xlsx`, ~85 satır
- `MÜLGA EK-3C-5(Yür-01.10.2014)ÖZEL HALLERDE KARŞ. TIBBİ MAL..xls`
- `MÜLGA EK-3D GÖRMEYE YARDIMCI TIBBİ MALZEMELER.xls`
- `MÜLGA EK-3E-1  OMURGA CERRAHİSİ.xls`
- `MÜLGA EK-3E-2 (Yür-01.10.2014)YENİ BEY.CERR.KRA.CERR.(Yür.01.08.13).xls`
- `MÜLGA EK-3E-2 BEY. CERR. KRAN. CERR..xlsx`, ~248 satır
- `MÜLGA EK-3F-1 ORT VE TRAV.BRA.ART.xlsx`, ~366 satır
- `MÜLGA EK-3F-2 (Yür-01.10.14)ORT.VE TRAV.BRA.ART.(EK Yür.01.08.14).xls`
- `MÜLGA EK-3F-3 (Yür.14.10.14)ORT.TRAV BRA.TÜM. REZ  (Yür.01.10.14).xls`
- `MÜLGA EK-3F-4(Yür-01.10.14)ORT TRA  BRA.TRA. REK.  (Yür 01.10.14).xlsx`, ~511 satır
- `MÜLGA EK-3F-4(Yür-01.10.14)YENİ ORT.TRAV.BRA.TRA (EK-Yür 01.08.14).xlsx`, ~511 satır
- `MÜLGA EK-3H KARDİYOLOJİ (Yür 01.10.14).xls`
- `MÜLGA EK-3M RAD. BRANŞ. VE ENDO.GİR  İŞL(Yürürlük 01 10 2014).xls`
- `MÜLGA EK-3M Yür.01.10.14 YENİ RAD.BRA.END..GİR. İŞL.(Yür. 01.08.13).xls`
- `MÜLGA EK-3S (Yür-01.10.2014)GÖĞÜS H. GÖĞ CERR.BRA(EK.Yür 01.08.14 ).xls`
- `MÜLGA EK-3T ANES. REAN. VE AĞRI TED. BRANŞ (Yür.-01.10.2014).xlsx`, ~68 satır
- `MÜLGA EK-3T(Yür.01.10.14)ANES. REA. AĞRI TED.BRA(EK-Yür-01.08.14 ).xlsx`, ~49 satır
- `MÜLGA EK-3C-1 TIBBİ UYGUNLUK ARANACAK TIBBİ MALZEMELER (Yür.01.01.2015).xls` — yür. `01.01.2015`
- `MÜLGA EK-3C-2 EKST. ALT VE ÜST PROT. ORT(Yür.01.01.2015).xls` — yür. `01.01.2015`
- `MÜLGA EK-3C-5 ÖZEL HAL. KARŞ. TIBBİ MALZ. LİST. (Yür. 01.01.2015).xlsx` — yür. `01.01.2015`, ~121 satır
- `MÜLGA EK-3A BİRDEN FAZLA BR. KULL TIB ML. LİST(Yür. 01.06.2021).xlsx` — yür. `01.06.2021`, ~624 satır
- `MÜLGA EK-3C-2 EKSTERNAL ALT VE ÜST EKSTR. GÖVDE PROT. ORT. LİST (Yür. 01.06.2021).xls` — yür. `01.06.2021`
- `MÜLGA EK-3C-3 DİĞER PROTEZ ORTEZLER LİSTESİ (Yür. 01.06.2021).xls` — yür. `01.06.2021`
- `MÜLGA EK-3C-4 TIBBİ SARF MALZEMELER LİSTESİ (Yür. 01.06.2021).xls` — yür. `01.06.2021`
- `MÜLGA EK-3C-5 ÖZEL HAL. KARŞ. TIBBİ MALZ. LİST. (Yür. 01.06.2021).xlsx` — yür. `01.06.2021`, ~102 satır
- `MÜLGA EK-3D GÖRMEYE YARDIMCI TIBBİ MALZEMELER LİSTESİ (Yür. 01.06.2021).xls` — yür. `01.06.2021`
- `MÜLGA EK-3E-1 OMURGA CERRAHİSİ ALAN GR. AİT TIB MALZ LİST(Yür. 01.06.2021).xlsx` — yür. `01.06.2021`, ~294 satır
- `MÜLGA EK-3E-2 BEYİN CER.BR.KR.CER. ALAN GR. AİT TIB MLZ.LİST (Yür. 01.06.2021).xlsx` — yür. `01.06.2021`, ~159 satır
- `MÜLGA EK-3F-1 ORT.VE TRAVM. BRA. ARTROPLASTİ LİSTESİ (Yür. 01.06.2021).xlsx` — yür. `01.06.2021`, ~346 satır
- `MÜLGA EK-3F-2 ORT. VE TRAV. BRANŞ ART. LİST. (Yür.01.06.2021).xlsx` — yür. `01.06.2021`, ~193 satır
- `MÜLGA EK-3F-3 ORT. VE TRAV. BR. TÜMÖR REZ.LİST. (Yür. 01.06.2021).xlsx` — yür. `01.06.2021`, ~187 satır
- `MÜLGA EK-3F-4 ORT VE TRAV BRŞ TRAV VE REK LİST. (Yür. 01.06.2021).xlsx` — yür. `01.06.2021`, ~526 satır
- `MÜLGA EK-3G GÖZ SAĞLIĞI VE HAS. BR. AİT TIBBİ MALZEMELER LİST. (Yür. 01.06.2021).xlsx` — yür. `01.06.2021`, ~261 satır
- `MÜLGA EK-3H KARDİYOLOJİ BRANŞINA AİT TIBBİ MALZEMELER LİST. (Yür. 01.06.2021).xlsx` — yür. `01.06.2021`, ~356 satır
- `MÜLGA EK-3I KALP DAMAR CERRAHİSİ BR. AİT TIBBİ MALZ. LİST. (Yür. 01.06.2021).xlsx` — yür. `01.06.2021`, ~548 satır
- `MÜLGA EK-3J KULAK BURUN BOĞAZ BR.AİT TIB.ML.LİST.(Yür. 01.06.2021).xlsx` — yür. `01.06.2021`, ~35 satır
- `MÜLGA EK-3K KADIN HAS. VE DOĞUM BR. AİT TIBBİ MALZEMELER LİST.(Yür. 01.06.2021).xlsx` — yür. `01.06.2021`, ~30 satır
- `MÜLGA EK-3L ÜROLOJİ BR. AİT TIBBİ MALZ. LİST. (Yür. 01.06.2021).xlsx` — yür. `01.06.2021`, ~113 satır
- `MÜLGA EK-3M RADY.BR.ENDOV.NONV.GRŞ. İŞL. AİT TIB.ML.LİST(Yür. 01.06.2021).xlsx` — yür. `01.06.2021`, ~418 satır
- `MÜLGA EK-3N-1 ALLOGREFT ÜRÜN GRUBU LİSTESİ (Yür. 01.06.2021).xlsx` — yür. `01.06.2021`, ~126 satır
- `MÜLGA EK-3N-2 XENOGREFT ÜRÜN GRUBU LİSTESİ (Yür. 01.06.2021).xlsx` — yür. `01.06.2021`, ~22 satır
- `MÜLGA EK-3N-3 SENTETİK GREFT ÜRÜN GRUBU LİSTESİ (Yür. 01.06.2021).xlsx` — yür. `01.06.2021`, ~19 satır
- `MÜLGA EK-3O HEMATOLOJİ-ONKOLOJİ BR. LİST. (Yür. 01.06.2021).xlsx` — yür. `01.06.2021`, ~41 satır
- `MÜLGA EK-3P NEFROLOJİ BRANŞINA AİT TIBBİ MALZEMELER LİST. (Yür. 01.06.2021).xlsx` — yür. `01.06.2021`, ~49 satır
- `MÜLGA EK-3R GASTRO.BR. AİT TIB. ML.LİST. (Yür. 01.06.2021).xlsx` — yür. `01.06.2021`, ~190 satır
- `MÜLGA EK-3S GÖĞÜS HAST.VE GÖĞÜS CERR. BR. LİST. (Yür. 01.06.2021).xlsx` — yür. `01.06.2021`, ~105 satır
- `MÜLGA EK-3T ANES. REAN. VE AĞRI TED. BR. LİST. (Yür. 01.06.2021).xlsx` — yür. `01.06.2021`, ~40 satır
- `MÜLGA EK-3F-1 ( Yür 01.07.2015)-ORT.VE TRAVM. BRA. ARTROPLASTİ (Yür. 01.08.2014).xlsx` — yür. `01.07.2015`, ~344 satır
- `MÜLGA EK-3F-1 ORT.VE TRAVM. BRA. ARTROPLASTİ (Yür. 01.07.2015).xlsx` — yür. `01.07.2015`, ~458 satır
- `MÜLGA EK-3G  (Yür-01.10.2014)YENİ-GÖZ SAG.VE HAST.(Yür. 01.08.2013).xls` — yür. `01.08.2013`
- `MÜLGA EK-3G GÖZ SAGLIGI VE HASTALIKLARI (Yürürlük 01.08.2013).xls` — yür. `01.08.2013`
- `MÜLGA EK-3H  KARDİYOLOJİ ( Yürürlük 01.08.2013).xlsx` — yür. `01.08.2013`, ~411 satır
- `MÜLGA EK-3H YENİ(Yür-01.10.2014)-KARDİYOLOJİ (Yürürlük 01.08.2013).xls` — yür. `01.08.2013`
- `MÜLGA EK-3I  KALP DAMAR CERRAHİSİ (Yürürlük 01.08.2013).xlsx` — yür. `01.08.2013`, ~601 satır
- `MÜLGA EK-3I (Yür-01.10.2014)YENİ-KALP DAMAR CERR. (Yür. 01.08.2013).xls` — yür. `01.08.2013`
- `MÜLGA EK-3J KBB (Yürürlük 01.08.2013).xls` — yür. `01.08.2013`
- `MÜLGA EK-3J KBB (Yürürlük 01.08.2013).xlsx` — yür. `01.08.2013`, ~34 satır
- `MÜLGA EK-3K KADIN HASTALIKLARI VE DOGUM (Yür. 01.08.2013).xls` — yür. `01.08.2013`
- `MÜLGA EK-3K KADIN HASTALIKLARI VE DOGUM (Yürürlük 01.08.2013).xls` — yür. `01.08.2013`
- `MÜLGA EK-3L  ÜROLOJİ (Yürürlük 01.08.2013).xls` — yür. `01.08.2013`
- `MÜLGA EK-3L ÜROLOJİ (Yürürlük 01.08.2013).xls` — yür. `01.08.2013`
- `MÜLGA EK-3M RADYOLOJİ VE ENDOVASK. GİR. İŞL. (Yürürlük 01.08.2013).xlsx` — yür. `01.08.2013`, ~464 satır
- `MÜLGA EK-3O HEMATOLOJİ-ONKOLOJİ BRANŞI  (EK-Yürürlük 01.08.2013).xls` — yür. `01.08.2013`
- `MÜLGA EK-3P NEFROLOJİ BRANŞI (EK- Yürürlük 01.08.2013).xls` — yür. `01.08.2013`
- `MÜLGA EK-3N-1 ALLOGREFT ÜRÜN GRUBU  ( Yürürlük 01.08.2014).xlsx` — yür. `01.08.2014`, ~228 satır
- `MÜLGA EK-3N-1 ALLOGREFT ÜRÜN GRUBU (Yürürlük 01.08.2014).xls` — yür. `01.08.2014`
- `MÜLGA EK-3N-2(Yür-01.10.2014)XENOGREFT ÜRÜN GR(EK-Yür. 01.08.2014).xlsx` — yür. `01.08.2014`, ~25 satır
- `MÜLGA EK-3N-3 SENTETİK GREFT ÜRÜN GRUBU (EK-Yürürlük 01.08.2014).xlsx` — yür. `01.08.2014`, ~19 satır
- `MÜLGA EK-3R (Yür-01.10.2014)GASTRO. BRA.(EK-Yür. 01.08.2014 ).xls` — yür. `01.08.2014`
- `MÜLGA EK-3A BİRDEN FAZ. BRŞ. KUL.TIB. ML.(Ek-Yür. 01.10.2014).xls` — yür. `01.10.2014`
- `MÜLGA EK-3C-2   EKST.ALT VE ÜST PROT.ORT. (Yür. 01.10.2014).xls` — yür. `01.10.2014`
- `MÜLGA EK-3C-2(Yür-01.01.2015)YENİ EKST.ALT VE ÜST PROT.ORT.Ek-Yür. 01.10.2014).xls` — yür. `01.10.2014`
- `MÜLGA EK-3E-2 BEYİN CERRH. KRANİAL CERR.  (Yür. 01.10.2014).xls` — yür. `01.10.2014`
- `MÜLGA EK-3F-2 ORT. VE TRAV. BRANŞ ART.( Yür. 01.10.2014).xls` — yür. `01.10.2014`
- `MÜLGA EK-3F-3(Yür.01.10.2014)ORT.TRAV.BRATÜM.REZ( EK Yür 01.08.14).xls` — yür. `01.10.2014`
- `MÜLGA EK-3F-4 ORT VE TRAV BRŞ TRAV VE REK  (EK-Yürürlük 01.10.2014).xlsx` — yür. `01.10.2014`, ~550 satır
- `MÜLGA EK-3G GÖZ SAGLIGI VE HASTALIKLARI (Yürürlük 01.10.2014).xls` — yür. `01.10.2014`
- `MÜLGA EK-3I KALP DAMAR CERRAHİSİ (Yürürlük 01.10.2014).xls` — yür. `01.10.2014`
- `MÜLGA EK-3N-2(Yür.14.10.14) XENOGREFT ÜRÜN GRUBU (Yür 01.10.2014).xlsx` — yür. `01.10.2014`, ~20 satır
- `MÜLGA EK-3R GASTROENTEROLOJİ BRANŞI (EK-Yürürlük 01.10.2014 ).xls` — yür. `01.10.2014`
- `MÜLGA EK-3S GÖĞÜS HAST.VE GÖĞÜS CERR. BRANŞ. (EK-Yür. 01.10.2014).xls` — yür. `01.10.2014`
- `MÜLGA EK-3A BİRDEN FAZLA BR. KULL TIB ML. LİST(Yür.03.09.2022).xlsx` — yür. `03.09.2022`, ~597 satır
- `MÜLGA EK-3C-2 EKSTERNAL ALT VE ÜST EKSTR. GÖVDE PROT. ORT. LİST(Yür.03.09.2022).xls` — yür. `03.09.2022`
- `MÜLGA EK-3C-3 DİĞER PROTEZ ORTEZLER LİSTESİ (Yür.03.09.2022).xls` — yür. `03.09.2022`
- `MÜLGA EK-3C-4 TIBBİ SARF MALZEMELER LİSTESİ (Yür.03.09.2022).xls` — yür. `03.09.2022`
- `MÜLGA EK-3C-5 ÖZEL HAL. KARŞ. TIBBİ MALZ. LİST. (Yür.03.09.2022).xls` — yür. `03.09.2022`
- `MÜLGA EK-3D GÖRMEYE YARDIMCI TIBBİ MALZEMELER LİSTESİ (Yür.03.09.2022).xls` — yür. `03.09.2022`
- `MÜLGA EK-3E-1 OMURGA CERRAHİSİ ALAN GR. AİT TIB MALZ LİST(Yür.03.09.2022).xlsx` — yür. `03.09.2022`, ~287 satır
- `MÜLGA EK-3E-2 BEYİN CER.BR.KR.CER. ALAN GR. AİT TIB MLZ.LİST (Yür.03.09.2022).xlsx` — yür. `03.09.2022`, ~159 satır
- `MÜLGA EK-3F-1 ORT.VE TRA. BR.ARTROPLASTİ AL.GR.AİT TB ML.LİST (Yür.03.09.2022).xlsx` — yür. `03.09.2022`, ~346 satır
- `MÜLGA EK-3F-2 ORT.VE TR.BR.AR.VE EKLEM CR.AL.GR.AİT TIB ML.LİS(Yür.03.09.2022).xlsx` — yür. `03.09.2022`, ~193 satır
- `MÜLGA EK-3F-3 ORT.VE TRAV.BR.TÜMÖR REZ.AL.GR.AİT TIB.ML.LİST(Yür.03.09.2022).xlsx` — yür. `03.09.2022`, ~187 satır
- `MÜLGA EK-3F-4 ORT.VE TR.BR.TRAV.VE REK.AL.GR.AİT TIB.ML.LİS.(Yür.03.09.2022).xlsx` — yür. `03.09.2022`, ~526 satır
- `MÜLGA EK-3G GÖZ SAĞ.VE HAST.BR.AİT TIB.ML.LİS.(Yür.03.09.2022).xlsx` — yür. `03.09.2022`, ~260 satır
- `MÜLGA EK-3H KARDİYOLOJİ BRANŞINA AİT TIBBİ MALZEMELER LİSTESİ (Yür.03.09.2022).xlsx` — yür. `03.09.2022`, ~355 satır
- `MÜLGA EK-3I KALP DAMAR CER.BR.AİT TIB.ML.LİST.(Yür.03.09.2022).xlsx` — yür. `03.09.2022`, ~547 satır
- `MÜLGA EK-3J KULAK BURUN BOĞAZ BR.AİT TIB.ML.LİST.(Yür.03.09.2022).xlsx` — yür. `03.09.2022`, ~35 satır
- `MÜLGA EK-3K KADIN HAST. VE DOĞUM BRANŞINA AİT TIBBİ MLZ LİST(Yür.03.09.2022).xlsx` — yür. `03.09.2022`, ~30 satır
- `MÜLGA EK-3L ÜROLOJİ BRANŞINA AİT TIBBİ MALZEMELER LİSTESİ (Yür.03.09.2022).xlsx` — yür. `03.09.2022`, ~113 satır
- `MÜLGA EK-3M RADY.BR. ENDOV.NONV.GRŞ.İŞL.AİT TIB.ML.LİST(Yür.03.09.2022).xlsx` — yür. `03.09.2022`, ~418 satır
- `MÜLGA EK-3N-1 ALLOGREFT ÜRÜN GRUBU LİSTESİ (Yür.03.09.2022).xlsx` — yür. `03.09.2022`, ~126 satır
- `MÜLGA EK-3N-2 XENOGREFT ÜRÜN GRUBU LİSTESİ (Yür.03.09.2022).xlsx` — yür. `03.09.2022`, ~22 satır
- `MÜLGA EK-3N-3 SENTETİK GREFT ÜRÜN GRUBU LİSTESİ (Yür.03.09.2022).xlsx` — yür. `03.09.2022`, ~19 satır
- `MÜLGA EK-3O HEMATOLOJİ-ONKOLOJİ BR.AİT TIB. ML.LİST.(Yür.03.09.2022).xlsx` — yür. `03.09.2022`, ~41 satır
- `MÜLGA EK-3P NEFROLOJİ BRANŞINA AİT TIBBİ MALZEMELER LİSTESİ (Yür.03.09.2022).xlsx` — yür. `03.09.2022`, ~49 satır
- `MÜLGA EK-3R GASTRO.BR. AİT TIB. ML.LİST.(Yür.03.09.2022).xlsx` — yür. `03.09.2022`, ~190 satır
- `MÜLGA EK-3S GÖĞÜS HAST.VE GÖĞÜS CER.BR.AİT TIB.ML.LİST.(Yür.03.09.2022).xlsx` — yür. `03.09.2022`, ~105 satır
- `MÜLGA EK-3T ANES.REA.VE AĞRI TED. BR.AİT TIB. MALZ.LİST.(Yür.03.09.2022).xlsx` — yür. `03.09.2022`, ~40 satır
- `MÜLGA EK-3A BİRDEN FAZLA BR. KULL TIB ML. LİST(Yür.08.02.2022).xlsx` — yür. `08.02.2022`, ~632 satır
- `MÜLGA EK-3C AYAKTA TEDAVİLERDE KULLANILAN TIBBİ MALZEMELER (Yür. 08.02.2022).xls` — yür. `08.02.2022`
- `MÜLGA EK-3C-1 TIBBİ UYGUNLUK ARANACAK TIBBİ MALZEMELER (Yür. 08.02.2022).xls` — yür. `08.02.2022`
- `MÜLGA EK-3C-2 EKSTERNAL ALT VE ÜST EKSTR. GÖVDE PROT. ORT. LİST (Yür.08.02.2022).xls` — yür. `08.02.2022`
- `MÜLGA EK-3C-3 DİĞER PROTEZ ORTEZLER LİSTESİ (Yür.08.02.2022).xls` — yür. `08.02.2022`
- `MÜLGA EK-3C-4 TIBBİ SARF MALZEMELER LİSTESİ (Yür.08.02.2022).xls` — yür. `08.02.2022`
- `MÜLGA EK-3C-5 ÖZEL HAL. KARŞ. TIBBİ MALZ. LİST. (Yür.08.02.2022).xls` — yür. `08.02.2022`
- `MÜLGA EK-3E-1 OMURGA CERRAHİSİ ALAN GR. AİT TIB MALZ LİST(Yür.08.02.2022).xlsx` — yür. `08.02.2022`, ~287 satır
- `MÜLGA EK-3E-2 BEYİN CER.BR.KR.CER. ALAN GR. AİT TIB MLZ.LİST  (Yür.08.02.2022).xlsx` — yür. `08.02.2022`, ~159 satır
- `MÜLGA EK-3F-1 ORT.VE TRA. BR.ARTROPLASTİ AL.GR.AİT TB ML.LİST (Yür. 08.02.2022).xlsx` — yür. `08.02.2022`, ~346 satır
- `MÜLGA EK-3F-2 ORT.VE TR.BR.AR.VE EKLEM CR.AL.GR.AİT TIB ML.LİS(Yür.08.02.2022).xlsx` — yür. `08.02.2022`, ~193 satır
- `MÜLGA EK-3F-3ORT.VE TRAV.BR.TÜMÖR REZ.AL.GR.AİT TIB.ML.LİST(Yür. 08.02.2022).xlsx` — yür. `08.02.2022`, ~187 satır
- `MÜLGA EK-3F-4 ORT.VE TR.BR.TRAV.VE REK.AL.GR.AİT TIB.ML.LİS.(Yür. 08.02.2022).xlsx` — yür. `08.02.2022`, ~526 satır
- `MÜLGA EK-3G GÖZ SAĞ.VE HAST.BR.AİT TIB.ML.LİS.(Yür. 08.02.2022).xlsx` — yür. `08.02.2022`, ~260 satır
- `MÜLGA EK-3H KARDİYOLOJİ BRANŞINA AİT TIBBİ MALZEMELER LİSTESİ (Yür. 08.02.2022).xlsx` — yür. `08.02.2022`, ~355 satır
- `MÜLGA EK-3I KALP DAMAR CER.BR.AİT TIB.ML.LİST.(Yür. 08.02.2022).xlsx` — yür. `08.02.2022`, ~547 satır
- `MÜLGA EK-3J KULAK BURUN BOĞAZ BR.AİT TIB.ML.LİST.(Yür.08.02.2022).xlsx` — yür. `08.02.2022`, ~35 satır
- `MÜLGA EK-3K KADIN HAST. VE DOĞUM BRANŞINA AİT TIBBİ MLZ LİST(Yür. 08.02.2022).xlsx` — yür. `08.02.2022`, ~30 satır
- `MÜLGA EK-3L ÜROLOJİ BRANŞINA AİT TIBBİ MALZEMELER LİSTESİ (Yür. 08.02.2022).xlsx` — yür. `08.02.2022`, ~113 satır
- `MÜLGA EK-3M RADY.BR. ENDOV.NONV.GRŞ.İŞL.AİT TIB.ML.LİST(Yür. 08.02.2022).xlsx` — yür. `08.02.2022`, ~418 satır
- `MÜLGA EK-3N-1 ALLOGREFT ÜRÜN GRUBU LİSTESİ (Yür. 08.02.2022).xlsx` — yür. `08.02.2022`, ~126 satır
- `MÜLGA EK-3N-2 XENOGREFT ÜRÜN GRUBU LİSTESİ (Yür.08.02.2022).xlsx` — yür. `08.02.2022`, ~22 satır
- `MÜLGA EK-3O HEMATOLOJİ-ONKOLOJİ BR.AİT TIB. ML.LİST.(Yür. 08.02.2022).xlsx` — yür. `08.02.2022`, ~41 satır
- `MÜLGA EK-3P NEFROLOJİ BRANŞINA AİT TIBBİ MALZEMELER LİSTESİ (Yür. 08.02.2022).xlsx` — yür. `08.02.2022`, ~49 satır
- `MÜLGA EK-3R GASTRO.BR. AİT TIB. ML.LİST. (Yür.08.02.2022).xlsx` — yür. `08.02.2022`, ~190 satır
- `MÜLGA EK-3S GÖĞÜS HAST.VE GÖĞÜS CER.BR.AİT TIB.ML.LİST.(Yür.08.02.2022).xlsx` — yür. `08.02.2022`, ~105 satır
- `MÜLGA EK-3T ANES.REA.VE AĞRI TED. BR.AİT TIB. MALZ.LİST.(Yür. 08.02.2022).xlsx` — yür. `08.02.2022`, ~40 satır
- `MÜLGA EK-3C-2 EKSTERNAL ALT VE ÜST EKSTR. GÖVDE PROT ORT. LİST (Yür.13.08.2024).xls` — yür. `13.08.2024`
- `MÜLGA EK-3C-3 DİĞER PROTEZ ORTEZLER LİSTESİ (Yür.13.08.2024).xls` — yür. `13.08.2024`
- `MÜLGA EK-3C-4 TIBBİ SARF MALZEMELER LİSTESİ (Yür.13.08.2024).xls` — yür. `13.08.2024`
- `MÜLGA EK-3C-5 ÖZEL HALLERDE KARŞILANAN TIBBİ MALZ. LİST (Yür.13.08.2024).xls` — yür. `13.08.2024`
- `MÜLGA EK-3F-3 ORT VE TRAV BRANŞ. TÜMÖR REZ (Yür.14.10.2014).xlsx` — yür. `14.10.2014`, ~379 satır
- `MÜLGA EK-3N-2 XENOGREFT ÜRÜN GRUBU (Yürürlük 14.10.2014).xlsx` — yür. `14.10.2014`, ~22 satır
- `MÜLGA EK-3E-1 OMURGA CERRAHİSİ (Yürürlük 18.03.2014).xls` — yür. `18.03.2014`
- `MÜLGA EK-3C-2 EKST.ALT VE ÜST EKST. GÖVDE PROTEZ ORT. LİS. (Yür.23.08.2024).xls` — yür. `23.08.2024`
- `MÜLGA EK-3A BİRDEN FAZLA BR. KULL TIB ML. LİST (Yür. 24.03.2023).xlsx` — yür. `24.03.2023`, ~597 satır
- `MÜLGA EK-3C-2 EKSTERNAL ALT VE ÜST EKSTR. GÖVDE PROT. ORT. LİST.(Yür. 24.03.2023).xls` — yür. `24.03.2023`
- `MÜLGA EK-3C-3 DİĞER PROTEZ ORTEZLER LİSTESİ (Yür. 24.03.2023).xls` — yür. `24.03.2023`
- `MÜLGA EK-3C-4 TIBBİ SARF MALZEMELER LİSTESİ  (Yür. 24.03.2023).xls` — yür. `24.03.2023`
- `MÜLGA EK-3C-5 ÖZEL HAL. KARŞ. TIBBİ MALZ. LİST.  (Yür. 24.03.2023).xls` — yür. `24.03.2023`
- `MÜLGA EK-3D GÖRMEYE YARDIMCI TIBBİ MALZEMELER LİSTESİ  (Yür. 24.03.2023).xls` — yür. `24.03.2023`
- `MÜLGA EK-3E-1 OMURGA CER. ALAN GRUBUNA AİT TIBBİ MLZ. LİST.  (Yür. 24.03.2023).xlsx` — yür. `24.03.2023`, ~287 satır
- `MÜLGA EK-3E-2 BEYİN CER.BR.KR.CER. ALAN GR. AİT TIB MLZ.LİST (Yür. 24.03.2023).xlsx` — yür. `24.03.2023`, ~159 satır
- `MÜLGA EK-3F-1 ORT.VE TRA. BR.ARTROPLASTİ AL.GR.AİT TB ML.LİST (Yür. 24.03.2023).xlsx` — yür. `24.03.2023`, ~346 satır
- `MÜLGA EK-3F-2 ORT.VE TR.BR.AR.VE EKLEM CR.AL.GR.AİT TIB ML.LİS(Yür. 24.03.2023).xlsx` — yür. `24.03.2023`, ~193 satır
- `MÜLGA EK-3F-3 ORT.VE TRAV.BR.TÜMÖR REZ.AL.GR.AİT TIB.ML.LİST (Yür. 24.03.2023).xlsx` — yür. `24.03.2023`, ~187 satır
- `MÜLGA EK-3F-4 ORT.VE TR.BR.TRAV.VE REK.AL.GR.AİT TIB.ML.LİS.(Yür. 24.03.2023).xlsx` — yür. `24.03.2023`, ~526 satır
- `MÜLGA EK-3G GÖZ SAĞ.VE HAST.BR.AİT TIB.ML.LİS. (Yür. 24.03.2023).xlsx` — yür. `24.03.2023`, ~260 satır
- `MÜLGA EK-3H KARDİYOLOJİ BRANŞINA AİT TIBBİ MALZEMELER LİSTESİ  (Yür. 24.03.2023).xlsx` — yür. `24.03.2023`, ~354 satır
- `MÜLGA EK-3I KALP DAMAR CER.BR.AİT TIB.ML.LİST.(Yür.24.03.2023).xlsx` — yür. `24.03.2023`, ~546 satır
- `MÜLGA EK-3J KULAK BURUN BOĞAZ BR.AİT TIB.ML.LİST.(Yür.24.03.2023).xlsx` — yür. `24.03.2023`, ~35 satır
- `MÜLGA EK-3K KADIN HAST. VE DOĞUM BRANŞINA AİT TIBBİ MLZ LİST (Yür. 24.03.2023).xlsx` — yür. `24.03.2023`, ~30 satır
- `MÜLGA EK-3L ÜROLOJİ BRANŞINA AİT TIBBİ MALZEMELER LİSTESİ  (Yür. 24.03.2023).xlsx` — yür. `24.03.2023`, ~113 satır
- `MÜLGA EK-3M RADY.BR. ENDOV.NONV.GRŞ. İŞL.AİT TIB.ML.LİST(Yür. 24.03.2023).xlsx` — yür. `24.03.2023`, ~417 satır
- `MÜLGA EK-3N-1 ALLOGREFT ÜRÜN GRUBU LİSTESİ  (Yür. 24.03.2023).xlsx` — yür. `24.03.2023`, ~126 satır
- `MÜLGA EK-3N-2 XENOGREFT ÜRÜN GRUBU LİSTESİ  (Yür. 24.03.2023).xlsx` — yür. `24.03.2023`, ~22 satır
- `MÜLGA EK-3N-3 SENTETİK GREFT ÜRÜN GRUBU LİSTESİ  (Yür. 24.03.2023).xlsx` — yür. `24.03.2023`, ~19 satır
- `MÜLGA EK-3O HEMATOLOJİ-ONKOLOJİ BR.AİT TIB. ML.LİST.(Yür. 24.03.2023).xlsx` — yür. `24.03.2023`, ~41 satır
- `MÜLGA EK-3P NEFROLOJİ BRANŞINA AİT TIBBİ MALZEMELER LİSTESİ  (Yür. 24.03.2023).xlsx` — yür. `24.03.2023`, ~49 satır
- `MÜLGA EK-3R GASTRO.BR. AİT TIB. ML.LİST. (Yür. 24.03.2023).xlsx` — yür. `24.03.2023`, ~190 satır
- `MÜLGA EK-3S GÖĞÜS HAST.VE GÖĞÜS CER.BR.AİT TIB.ML.LİST.(Yür. 24.03.2023).xlsx` — yür. `24.03.2023`, ~105 satır
- `MÜLGA EK-3T ANES.REA.VE AĞRI TED. BR.AİT TIB. MALZ.LİST.(Yür. 24.03.2023).xlsx` — yür. `24.03.2023`, ~40 satır
- `MÜLGA EK-3C-3 DİĞER PROTEZ ORTEZLER LİSTESİ (Yür. 30.04.2024).xls` — yür. `30.04.2024`
- `MÜLGA EK-3A BİRDEN FAZLA BRANŞTA KULLANILAN TIBBİ MALZEMELER LİSTESİ (Yür.30.08.2023).xlsx` — yür. `30.08.2023`, ~598 satır
- `MÜLGA EK-3E-1 OMURGA CERRAHİSİ ALAN GRUBUNA AİT TIBBİ MALZEMELER LİSTESİ (Yür.30.08.2023).xlsx` — yür. `30.08.2023`, ~288 satır
- `MÜLGA EK-3E-2 BEYİN CER. BR.KRANİAL CERRAHİSİ ALAN GR. AİT TIB.MAL.LİS.(Yür.30.08.2023).xlsx` — yür. `30.08.2023`, ~162 satır
- `MÜLGA EK-3F-1 ORT. VE TRAV. BR. ARTROPLASTİ ALAN GR. AİT TIB. MALZ. LİST. (Yür.30.08.2023).xlsx` — yür. `30.08.2023`, ~347 satır
- `MÜLGA EK-3F-2 ORT. VE TRAV. BR. ARTR. VE EKLEM CERR. ALAN GR. AİT TIBBİ MALZ. LİST (Yür.30.08.2023).xlsx` — yür. `30.08.2023`, ~193 satır
- `MÜLGA EK-3F-3 ORT. VE TRAV. BR. TÜMÖR REZEKSİYON ALAN GR. AİT TIB. MALZ. LİST. (Yür.30.08.2023).xlsx` — yür. `30.08.2023`, ~187 satır
- `MÜLGA EK-3F-4 ORT. VE TRAV. BR. TRAV. VE REKONS. ALAN GR. AİT TIB. MALZ. LİST. (Yür.30.08.2023).xlsx` — yür. `30.08.2023`, ~530 satır
- `MÜLGA EK-3G GÖZ SAĞLIĞI VE HASTALIKLARI BRANŞINA AİT TIBBİ MALZEMELER LİSTESİ (Yür.30.08.2023).xlsx` — yür. `30.08.2023`, ~263 satır
- `MÜLGA EK-3H KARDİYOLOJİ BRANŞINA AİT TIBBİ MALZEMELER LİSTESİ (Yür.30.08.2023).xlsx` — yür. `30.08.2023`, ~357 satır
- `MÜLGA EK-3I KALP DAMAR CERRAHİSİ BRANŞINA AİT TIBBİ MALZEMELER LİSTESİ (Yür.30.08.2023).xlsx` — yür. `30.08.2023`, ~552 satır
- `MÜLGA EK-3J KULAK BURUN BOĞAZ BRANŞINA AİT TIBBİ MALZEMELER LİSTESİ (Yür.30.08.2023).xlsx` — yür. `30.08.2023`, ~35 satır
- `MÜLGA EK-3K KADIN HASTALIKLARI VE DOĞUM BRANŞINA AİT TIBBİ MALZEMELER LİSTESİ (Yür.30.08.2023).xlsx` — yür. `30.08.2023`, ~30 satır
- `MÜLGA EK-3L ÜROLOJİ BRANŞINA AİT TIBBİ MALZEMELER LİSTESİ (Yür.30.08.2023).xlsx` — yür. `30.08.2023`, ~117 satır
- `MÜLGA EK-3M RADYOLOJİ BR VE ENDOVASNONVAS GİR İŞL AİT TIB MALZ LİST (Yür.30.08.2023).xlsx` — yür. `30.08.2023`, ~430 satır
- `MÜLGA EK-3N-1 ALLOGREFT ÜRÜN GRUBU LİSTESİ (Yür.30.08.2023).xlsx` — yür. `30.08.2023`, ~126 satır
- `MÜLGA EK-3N-2 XENOGREFT ÜRÜN GRUBU LİSTESİ (Yür.30.08.2023).xlsx` — yür. `30.08.2023`, ~22 satır
- `MÜLGA EK-3O HEMATOLOJİ-ONKOLOJİ BRANŞINA AİT TIBBİ MALZEMELER LİSTESİ (Yür.30.08.2023).xlsx` — yür. `30.08.2023`, ~55 satır
- `MÜLGA EK-3P NEFROLOJİ BRANŞINA AİT TIBBİ MALZEMELER LİSTESİ (Yür.30.08.2023).xlsx` — yür. `30.08.2023`, ~50 satır
- `MÜLGA EK-3R GASTROENTEROLOJİ BRANŞINA AİT TIBBİ MALZEMELER LİSTESİ (Yür.30.08.2023).xlsx` — yür. `30.08.2023`, ~190 satır
- `MÜLGA EK-3S GÖĞÜS HAST VE GÖĞÜS CERR. BRNŞ. AİT TIBBİ MALZ. LİST. (Yür.30.08.2023).xlsx` — yür. `30.08.2023`, ~110 satır
- `MÜLGA EK-3T ANESTEZİYOLOJİ, REAN VE AĞRI TED. BRNŞ. AİT TIBBİ MALZ. LİST. (Yür.30.08.2023).xlsx` — yür. `30.08.2023`, ~41 satır

---
BILUN pipeline: `scripts/sut/convert_xlsx_to_parquet.py --include-mulga` → `data/gazette/raw/` → `data/gazette/curated/`
