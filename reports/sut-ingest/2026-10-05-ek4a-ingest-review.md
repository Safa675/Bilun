# EK-4A ve otomatik SUT içe aktarma: kaynak ve semantik inceleme

**Karar:** Resmî 2 Ekim EK-4A kaynağı doğrulandı. Tam kaynak çıkarımı **8.183 satırlık inceleme görüntüsüdür; canlı kullanım için onaylanmış değildir.** Kaynak, altı kaydın değişikliğini **10 Ekim 2026** tarihine bağlar. Mevcut 8.078 satırlık çalışma zamanı kataloğu bu incelemede değiştirilmedi. Yeni ödeme/klinik yorum eklenmedi.

Karşılaştırmalar sabit SHA’larla yapıldı: `main=3d29a1fefa2b89f9a8d38e2dccab6fe2285c861e`, PR128 parent `d0337600f45a17aa635f6bbe8d584095a6f3e82e`, kapanmış PR128 head `7be613251322d41ab15bbe29de56acaedf60ecfe`. Bütün sütunlar, veri türleri, null değerleri ve satır sırası çözümlenerek karşılaştırıldı.

## Kök neden kanıtı

`main` EK-4A’sı, **29 Haziran MÜLGA ham bölümünün çıkarımıyla birebir eşit**: 8.078 satır. PR128’deki 8.148 satır ise **29 Ağustos güncel XLSX ve ham parquet çıkarımıyla birebir eşit**. Bu iki kaynak blob’u üç SHA’da da değişmiyor. Güncel çözümleyici MÜLGA’yı dışlayıp Ağustos `unknown` bölümünü seçmesine rağmen, kayıtlı curated çıktı eski Haziran verisini taşıyor (`scripts/sut/_common.py:95`, `scripts/sut/build_curated_catalogs.py:163`). Dolayısıyla PR128’deki fark gerçek bir eski çıktı düzeltmesi; **2 Ekim’in tam güncel EK-4A verisi değil**.

PR128’de değişmiş **35 anlık kataloğun 34’ü** `main` ile tüm çözümlenmiş değerleri ve Arrow alan türleri bakımından eşit. Üç zaman çizelgesi de **bütün tarihsel satır ve sütunlarıyla eşit**: EK-2B 76.673×9, EK-2C 26.584×13, EK-2Ç 1.734×10. Bu üç dosyada yalnız footer `pandas_version 3.0.5→3.0.6` değişiyor; veri sayfaları ve row-group metadata aynı. Bu **37 dosya** anlamlı veri güncellemesi olarak PR’a taşınmamalı. Önceden mevcut zaman aralığı/key tekrarları değişmedi; bu işin kapsamında düzeltilmedi.

Manifest de `main`/PR128 arasında çözümlenmiş olarak eşit. Repodaki 2 Ekim kaynak dizini yalnız DOCX içeriyor; bu dizin tek başına tam ek paketi içe aktarmayı kanıtlamaz. Manifest hash’i veya klasör tarihi kaynak doğrulaması yerine kullanılmamalı.

## Tam resmî kaynak ve gerçek fark

[Resmî SGK ZIP’i](https://www.sgk.gov.tr/Download/DownloadFile?f=8ee647e7-923a-448b-8eac-a91772f34a78.zip&d=f5bf9aae-c24d-4bcd-aa89-6f870210736a) için mevcut kaynak doğrulaması `reports/sut-expansion/report-documentation-primary-source-verification.json:85` konumunda. ZIP SHA256 `03bf37df87ff48358e23b1018405405bbb436032c9424b17ddbcb828525f7a61`; güncel `EK-4 LİSTELERİ/EK-4A BEDELİ ÖDENECEK İLAÇLAR LİSTESİ.xlsx` üyesi SHA256 `927918fa6c7459c27bc01619722a9ee6f69cf6eb49ccb7d620534788b453935a`.

ZIP içindeki `(Yür. 02.10.2026)` **MÜLGA** kitabı Ağustos güncel kitabıyla byte eşit (`e453d4c0…`); güncel Ekim kitabıyla farklıdır. Yanlış üye seçimi hash ve veri farkı üzerinden negatif olarak doğrulanabilir.

Güncel Ekim kitabı tek `EK-4A` sayfasında **8.188 temizlenmiş ham satır ×16 veri sütunu** içerir. Değiştirilmemiş extractor 8.183 satır ×16 `String` alan üretir. Beş dışlanan satır: başlık, kamu numarası boş majistral kayıt, yürürlük dipnotu ve iki sondaki kayıt dışı satır (`scripts/sut/catalogs/simple_materials.py:147`). `kamu_no` ve barcode benzersiz; kimlik/ad boşluğu ve bütün sütunlarda null sıfır. Bütün barkodlar 13 basamaklı string; gerçek kaynakta sıfırla başlayan barkod yoktur, bu durum ayrıca sentetik negatif test gerektirir.

| Kaynak karşılaştırması | Eklenen key | Silinen key | Değişen ortak key | Aynı ortak key |
|---|---:|---:|---:|---:|
| main → Ağustos/PR128 | 206 | 136 | 140 | 7.802 |
| main → tam Ekim görüntüsü | 253 | 148 | 157 | 7.773 |
| Ağustos/PR128 → tam Ekim görüntüsü | 48 | 13 | 23 | 8.112 |

`main→Ekim` ortak key alan farkları: ad 81, barcode 36, eski barcode 43, eşdeğer grup 31, terapötik grup 1, giriş/aktif/pasif tarihi üçer, indirim tier1 11, tier2 3, özel indirim 6. Diğer indirim alanları aynı. **Tutar/fiyat sütunu yoktur**; bu sayılar ödeme hakkı iddiası değildir. Çoklu tarih dizileri korunur: giriş 27, aktif/pasif alanlarında 287’şer satır.

## Gelecek yürürlük ve dar düzeltme sınırı

Sadece tarih sütunu taraması yeterli değildir: **sıfır tabanlı ham satır 8.185’teki yürürlük dipnotu**, giriş tarihi `(*)` ve ilaç adı `(**)` için **10/10/2026**, ilaç adı `(***)` için yayım tarihini açıkça belirtir.

- `entry_date='*'`: **A20335, A20336, A20337**; üçü de yeni kayıt.
- Adı tam iki yıldızla biten: **A15711, A15712, A15809**; mevcut kayıtlarda tek hücre farkı adın sonuna `**` eklenmesidir.
- **A19064** tam üç yıldız taşır; yayım işareti iki yıldızla karıştırılmamalı. **A20062** içindeki `56*5 ML` doz çarpanı dipnot işareti değildir.

Extractor dipnotu atar; runtime giriş/aktif tarihlerini yüklemez ve yalnız boş olmayan pasif tarihlerini ad indeksinden dışlar (`src/bilun/domain/materials/drugs.py:40`, `:78`). Doğrudan parquet tüketicileri de bulunduğundan bu inceleme **tam 8.183 satırın canlı promosyona taşınmasına onay vermez**. Dar kaynak kabul koruması, gelecek işaretler varken çıkarımı ertelemeli veya fail closed olmalı; ara canlı projection ve yeni ödeme yorumu üretmemeli.

Gerekli test sınırları: 9/10 Ekim; `*` giriş ve tam `**` son eki; `***` ve iç doz yıldızı; eksik/çelişkili dipnot; yanlış güncel/MÜLGA kaynağı; benzersiz/string kimlikler ve sıfırla başlayan sentetik barcode; doğrulanmış kaynakta aynı amendment tekrarının idempotansı; eski clause delta raporlarının korunması. Corpus state ile XLS ek paketinin tamamlanması ayrı kanıtlanmalı; eski `unknown` raw provenance körlemesine üzerine yazılmamalı.

## Uygulanan kaynak kabulü ve kalan sınır

Resmî güncel kitap ve aynı ZIP'in 2 Ekim MÜLGA kitabı ayrı kaynak kimlikleriyle kabul edildi. Güncel ham bölüm 8.188×24, MÜLGA bölüm 8.152×24; önceki Ağustos bölümünün bütün veri hücreleri MÜLGA kaynağında korunuyor. Manifest 327 satırdır; ilgisiz 325 satırın şema, veri türleri ve değerleri değişmedi. Aynı kabul işleminin ikinci çalıştırması altı kaynak/ham/manifest/state dosyasını byte eşit bıraktı.

State manifest hash/satır sayısıyla tutarlıdır; `completion_scope=partial`, `pending_full_package_date=2026-10-02` ve ayrı prose/EK-4A kaynak hash makbuzları içerir. `last_ingested_date=2026-08-29` son tam paket olarak korunur. Ekim paketinin 318 workbook'u bu PR'da bütünüyle işlenmiş değildir.

Canlı `curated/ek4a_drugs.parquet` (8.078), `sut_clauses.parquet`, sourceauthority/coverage ve mevcut tarihsel clause raporları korunur. Yeni kaynak canlı katalogla eşleşmediği state'te açıkça belirtilir. Hizmet tarihi güvenli projection ve canlı katalog yenilemesi sonraki çalışma olarak kalır; bu PR bunların tamamlandığını ileri sürmez.

Tarihsel clause raporunun özeti ve 42 actionable satırın tamamı eski corpus SHA `9639c457...` → yeni corpus SHA `40b2b7eb...` üzerinden yeniden üretildi. Ayrı [giriş makbuzu](../../data/gazette/deltas/2026-10-02_clause_diff_inputs.json) eski JSON'u değiştirmeden rapor SHA'sını ve typed semantic input hash'lerini bağlar. Sadece değişen satırları doğrulamak, stable satırdaki gizli değişikliği kabul edebileceğinden yeterli sayılmaz.

Makine kanıtı: [2026-10-05-semantic-audit.json](2026-10-05-semantic-audit.json). Ayrıntılı key-by-key ve source→raw→curated tekrar üretim kayıtları task-5 `evidence/` dizinindedir. Genel Ruff, compiler `--check` (134 byte eşit artifact) ve drug manifest parity (23/23, sıfır sorun) geçti. Bağımsız inceleme exact source/raw ve tarihsel rapor kanıtını yeniden üretti; bulduğu işlem kesintisinde yarım fetch dosyası P2'si atomik dosya kurulumu ile kapatıldı. Dört gerçek ani çıkış ve iki eşzamanlı kurulum regresyonu eklendi. Son birleşik hedefli koşu **250 test geçti (22,15 saniye)**. [Taslak PR162](https://github.com/Safa675/Bilun/pull/162) açıldı; son commit incelemesi ve hosted tam CI bekleniyor. Tam test paketi laptopta yinelenmedi. Merge veya deploy yapılmadı.
