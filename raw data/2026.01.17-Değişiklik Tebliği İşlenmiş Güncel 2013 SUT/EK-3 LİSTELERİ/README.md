# EK-3 LİSTELERİ

Konum: `raw data/2026.01.17-Değişiklik Tebliği İşlenmiş Güncel 2013 SUT/EK-3 LİSTELERİ`
Son güncelleme: 2026-06-12

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

## Tarife / katalog tabloları

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

---
BILUN pipeline: `scripts/sut/convert_xlsx_to_parquet.py` → `data/gazette/raw/` → `data/gazette/curated/`
