# Finans.XLSX — Veri Bütünlük Analizi

**Kaynak:** `raw data/Finans.XLSX`
**Toplam satır:** 7,646  ·  **Benzersiz FATURANO:** 485  ·  **Benzersiz SIRA:** 6

## Özet Karar

❌ **TUTARSIZ:** 12 fatura birden fazla SIRA'da görünüyor. SIRA hasta numarasıysa bu imkânsız (bir fatura tek hastaya aittir).

## Sağlayıcı İddiası: "6 hasta"

Veride 6 benzersiz SIRA var (iddia edilen 6 ile uyumlu). Ancak satır yoğunluğu ve fatura paylaşımı bu sayının **gerçek hasta sayısı olmayabileceğini** gösteriyor:

| SIRA | Satır | Fatura | Ay | Tarih aralığı | Kod | Satır/Fatura |
|------|-------|--------|----|---------------|-----|--------------|
| 91 | 2,539 | 111 | 51 | 2019-01-11 → 2026-04-17 | 347 | 22.9 |
| 61 | 2,005 | 103 | 53 | 2019-03-13 → 2026-04-08 | 432 | 19.5 |
| 96 | 1,314 | 142 | 48 | 2019-07-19 → 2026-05-05 | 264 | 9.3 |
| 11 | 948 | 71 | 34 | 2019-05-02 → 2025-12-12 | 281 | 13.4 |
| 83 | 710 | 40 | 18 | 2019-01-16 → 2026-03-18 | 216 | 17.8 |
| 89 | 130 | 34 | 12 | 2019-01-12 → 2026-03-09 | 46 | 3.8 |

> Tek bir SIRA'nın 2.500+ satır üretmesi 7 yılda "tek hasta" veya "bir kohort/bölüm" olabilir. Satır yoğunluğu tek başına karar verici değil.

## Karar Verici Kanıt: Birden fazla SIRA'da görünen faturalar

**12 fatura** birden fazla SIRA'da görünüyor (868 satırı etkiliyor). Her biri için ayrıntı:

### FATURANO `1` — 6 SIRA, 475 satır

- Tarih aralığı: **2019-02-15 → 2026-03-18** (2588 gün)
- Hizmet kodu sayısı: 178

| SIRA | Satır | İlk tarih | İlk kod |
|------|-------|-----------|---------|
| 11 | 2 | 2025-01-25 | `07010001` |
| 61 | 308 | 2019-08-01 | `C9078101` |
| 83 | 36 | 2019-02-15 | `70024099` |
| 89 | 1 | 2024-12-25 | `07010001` |
| 91 | 71 | 2019-03-05 | `07010001` |
| 96 | 57 | 2020-08-03 | `60010002` |

### FATURANO `4516147101` — 2 SIRA, 96 satır

- Tarih aralığı: **2021-01-14 → 2021-01-28** (14 gün)
- Hizmet kodu sayısı: 49

| SIRA | Satır | İlk tarih | İlk kod |
|------|-------|-----------|---------|
| 61 | 85 | 2021-01-14 | `C8446001` |
| 91 | 11 | 2021-01-14 | `70019573` |

### FATURANO `4516234836` — 2 SIRA, 73 satır

- Tarih aralığı: **2021-03-08 → 2021-03-17** (9 gün)
- Hizmet kodu sayısı: 36

| SIRA | Satır | İlk tarih | İlk kod |
|------|-------|-----------|---------|
| 61 | 62 | 2021-03-08 | `70019573` |
| 91 | 11 | 2021-03-17 | `C8452001` |

### FATURANO `4516185457` — 2 SIRA, 71 satır

- Tarih aralığı: **2021-01-28 → 2021-02-22** (25 gün)
- Hizmet kodu sayısı: 38

| SIRA | Satır | İlk tarih | İlk kod |
|------|-------|-----------|---------|
| 61 | 70 | 2021-02-10 | `70009020` |
| 91 | 1 | 2021-01-28 | `70019573` |

### FATURANO `4516452538` — 2 SIRA, 42 satır

- Tarih aralığı: **2021-07-30 → 2021-08-25** (26 gün)
- Hizmet kodu sayısı: 29

| SIRA | Satır | İlk tarih | İlk kod |
|------|-------|-----------|---------|
| 61 | 30 | 2021-07-30 | `07010012` |
| 91 | 12 | 2021-08-25 | `C8204001` |

### FATURANO `4518902449` — 2 SIRA, 40 satır

- Tarih aralığı: **2025-06-02 → 2025-06-20** (18 gün)
- Hizmet kodu sayısı: 35

| SIRA | Satır | İlk tarih | İlk kod |
|------|-------|-----------|---------|
| 61 | 28 | 2025-06-02 | `61463234` |
| 91 | 12 | 2025-06-20 | `70019573` |

### FATURANO `4516846613` — 2 SIRA, 19 satır

- Tarih aralığı: **2022-02-23 → 2022-03-02** (7 gün)
- Hizmet kodu sayısı: 18

| SIRA | Satır | İlk tarih | İlk kod |
|------|-------|-----------|---------|
| 61 | 11 | 2022-02-23 | `70008198` |
| 91 | 8 | 2022-03-02 | `70019573` |

### FATURANO `4519056884` — 2 SIRA, 16 satır

- Tarih aralığı: **2025-09-16 → 2025-10-28** (42 gün)
- Hizmet kodu sayısı: 15

| SIRA | Satır | İlk tarih | İlk kod |
|------|-------|-----------|---------|
| 61 | 1 | 2025-10-28 | `70008198` |
| 91 | 15 | 2025-09-16 | `70023926` |

### FATURANO `0` — 2 SIRA, 15 satır

- Tarih aralığı: **2022-07-07 → 2026-04-10** (1373 gün)
- Hizmet kodu sayısı: 11

| SIRA | Satır | İlk tarih | İlk kod |
|------|-------|-----------|---------|
| 61 | 14 | 2022-07-07 | `C7126001` |
| 91 | 1 | 2026-04-10 | `70019573` |

### FATURANO `4515917250` — 2 SIRA, 12 satır

- Tarih aralığı: **2020-06-16 → 2020-07-22** (36 gün)
- Hizmet kodu sayısı: 12

| SIRA | Satır | İlk tarih | İlk kod |
|------|-------|-----------|---------|
| 83 | 1 | 2020-07-22 | `70008198` |
| 91 | 11 | 2020-06-16 | `C8204001` |

### FATURANO `2314295307` — 2 SIRA, 5 satır

- Tarih aralığı: **2024-08-06 → 2024-09-23** (48 gün)
- Hizmet kodu sayısı: 4

| SIRA | Satır | İlk tarih | İlk kod |
|------|-------|-----------|---------|
| 11 | 2 | 2024-08-06 | `61463677` |
| 96 | 3 | 2024-09-23 | `61518988` |

### FATURANO `4516318945` — 2 SIRA, 4 satır

- Tarih aralığı: **2021-05-11 → 2021-05-25** (14 gün)
- Hizmet kodu sayısı: 4

| SIRA | Satır | İlk tarih | İlk kod |
|------|-------|-----------|---------|
| 61 | 2 | 2021-05-11 | `70008198` |
| 91 | 2 | 2021-05-25 | `C8415301` |

## Reddedilen Fatura Numaraları (Placeholder)

`FATURANO = 0` ve `FATURANO = 1` gerçek fatura değil — geçersiz/bilinmeyen için kullanılan değer. Bu yüzden birden fazla SIRA'da görünüyor:

| FATURANO | SIRA'lar | Satır | Tarih aralığı |
|----------|----------|-------|---------------|
| 1 | ['11', '61', '83', '89', '91', '96'] | 475 | 2019-02-15 → 2026-03-18 |
| 0 | ['61', '91'] | 15 | 2022-07-07 → 2026-04-10 |

Bunları çıkarsak bile **10 gerçek fatura** hâlâ birden fazla SIRA'da görünüyor — yani placeholder hatası tek açıklama değil.

## Sonuç ve Sorulacak Sorular

1. **"SIRA hasta numarası mı?"** — öyleyse neden 10 gerçek fatura birden fazla SIRA'da görünüyor?
2. **"Her SIRA tek bir hastanın geçmişi mi, yoksa grup/kohort mu?"** — satır yoğunluğu (SIRA 91: 2.500+ satır / 7 yıl) iki duruma da uyuyor.
3. **Gerçek hasta protokol numarası (dosya no / patient ID)** verilmesi — bunlar olmadan gerçek hasta sayısı kanıtlanamaz.

## Çıktılar

- Bu rapor: `reports/finans-analysis.md`
- İşaretli satırlar: `reports/finans_flagged.xlsx` (`FLAG_shared_invoice` sütunu = 1 olanlar problemli)