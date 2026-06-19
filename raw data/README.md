# raw data

Konum: `raw data/`
Son güncelleme: 2026-06-19

SGK **Sağlık Uygulama Tebliği (SUT)** kaynak belgeleri. Resmi gazete tebliğ paketleri, ilaç listeleri ve saha röportajları.

## Dizin yapısı

```
raw data/
├── 2026.01.17-Değişiklik Tebliği İşlenmiş Güncel 2013 SUT/          (343 dosya)
├── 2026.04.08-Değişiklik Tebliği İşlenmiş Güncel 2013 SUT/          (341 dosya)
├── Interviews/          (3 dosya)
├── Referans Bazlı İlaç Listesi/          (11 dosya)
├── 0abeb266-fde9-4958-b115-a31a8c2b0336.pdf
├── MEDULA_Kullanim_Kilavuzu.pdf
└── README.md            (bu dosya)
```

## Hangi tebliği kullanmalıyım?

| Klasör | Tebliğ tarihi | Not |
|--------|---------------|-----|
| `2026.01.17-...` | 17 Ocak 2026 | **Güncel** — BILUN gazette ETL hedef kaynağı |
| `2025.01.25-...` | 25 Ocak 2025 | Önceki sürüm; fiyat diff / tarihsel analiz |

## Kök dosyalar

- `0abeb266-fde9-4958-b115-a31a8c2b0336.pdf` — PDF kaynak (içerik dosya adından belirsiz)
- `MEDULA_Kullanim_Kilavuzu.pdf` — MEDULA kullanım kılavuzu (fatura sistemi referansı)

## EK grupları — hızlı rehber

| Grup | Ne içerir? |
|------|------------|
| EK-1 | Katılım payı muafiyetleri, formlar |
| EK-2 | İşlem puanları (2B), DRG paketleri (2C), diş (2Ç) |
| EK-3 | Malzeme tavan fiyatları ve ödeme kuralları |
| EK-4 | İlaç kataloğu (4A) ve reçete kuralları |

İşlenmiş parquet: `data/gazette/curated/` — ayrıntı: `docs/core-system/gazette.md`.

## Alt klasörler

- [2026.01.17-Değişiklik Tebliği İşlenmiş Güncel 2013 SUT](2026.01.17-Değişiklik Tebliği İşlenmiş Güncel 2013 SUT/README.md)
- [2026.04.08-Değişiklik Tebliği İşlenmiş Güncel 2013 SUT](2026.04.08-Değişiklik Tebliği İşlenmiş Güncel 2013 SUT/README.md)
- [Interviews](Interviews/README.md)
- [Referans Bazlı İlaç Listesi](Referans Bazlı İlaç Listesi/README.md)
