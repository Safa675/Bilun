# SUT 2026-07-01 Güncelleme Planı (v2, review-corrected)

**Branch:** `feat/sut-update-pipeline`
**Hedef:** 2026-07-01 SUT tebliği (RG 33297) tarafından getirilen 63 yeni/değişmiş paragrafı BILUN'a yansıtmak.

---

## Mevcut Durum

Katalog güncellemesi (EK listeleri) **tamamlandı** — pipeline otomatik çalıştı:
- EK-2B/C/Ç: 0 değişiklik (puan/fiyat aynı)
- EK-1A: copay tutarları güncellendi (26→50₺, 60→100₺) — parquet rebuild edildi
- EK-3/4 malzeme/ilaç: rebuild edildi

SUT ana metni (prose rules) **henüz güncellenmedi** — `extract_sut_prose.py` yeni docx ile çalıştırılmadı.

---

## Etkilenen BILUN Bileşenleri

| Öncelik | Değişiklik | BILUN Etkisi | Efor |
|---|---|---|---|
| 🟡 MED | FTR seans limitleri değişti (§2.4.4.F) | Mevcut YAML condition'larını güncelle | 2-3 saat |
| 🟡 MED | Yeni Pulmoner Rehab paketi P701074 | **Pipeline gap — P701074 EK-2C'de yok!** Önce bunu çöz | 1-2 saat |
| 🟡 MED | HBO/FTR/ESWL rapor süresi kuralları | Süre koşullarını güncelle | 1-2 saat |
| 🟢 LOW | Yeni ilaç endikasyonları (PNH/NMOSB/PSMA/SMA) | drug_indication JSON'a yeni kurallar ekle | 2-4 saat |
| ~~HIGH~~ | ~~Copay hardcoded tutarlar~~ | **No-op** — copay data-driven (copay_general_1_8.json + EK-1A parquet), hardcoded literal yok | ~0 |

---

## Adımlar

### Adım 1: SUT prose re-extract + drift triage (~1 saat)

**Beklenti:** `compile_rules.py --check` byte-identical GEÇMEYECEK — clause drift olacak. Bu drift çalışma listesidir.

- [ ] `extract_sut_prose.py` yeni docx ile çalıştır → `sut_clauses.parquet` güncellenir
- [ ] Eski (8.295) vs yeni clause sayısını karşılaştır
- [ ] `compile_rules.py` çalıştır (compile et, --check değil)
- [ ] Drift diff'i triage et: hangi YAML/JSON dosyaları değişti? Bu diff Steps 3-6'nın çalışma listesidir.

### Adım 2: P701074 ambiguity çöz (~30 dk)

**Problem:** P701074 "Pulmoner Rehab paketi" SUT metninde referans var ama EK-2C parquet'de yok.

- [ ] Yeni SUT docx'inde "701074" geçen yerleri bul: tam bağlamı nedir?
- [ ] EK-2C xlsx'inde 701074 var mı? (raw data/2026.07.01.../EK-2C...xlsx'i doğrudan kontrol et)
- [ ] Eğer xlsx'de var ama parquet'de yoksa: **pipeline bug** — extract hatası
- [ ] Eğer xlsx'de de yoksa: bu bir **prose reference** (§2.4.4.F-7), package code değil — yeni kural encode edilirken string olarak referans verilir

### Adım 3: Copay doğrulama (~15 dk — no-op bekleniyor)

**Beklenti:** No-op. Copay amounts `copay_general_1_8.json` (30 rule, data-driven percentages) + EK-1A parquet üzerinden resolve ediliyor. Hardcoded literal yok.

- [ ] `copay_general_1_8.json`'daki percentage rate'lerin hala geçerli olduğunu doğrula
- [ ] Sentetik data'da copay tutarlarının yeni EK-1A ile tutarlı olduğunu spot-check et
- [ ] Eğer tutarsızlık varsa: EK-1A parquet veya copay_general_1_8.json rate'lerini güncelle

### Adım 4: FTR kural metinlerini güncelle (~2-3 saat)

- [ ] Adım 1'deki drift diff'ten `2.4.4.F` ile ilgili değişen YAML kurallarını belirle
- [ ] `2.4.4.F-2.(5).physio_annual_region_session_caps` kuralının condition'ını yeni SUT metniyle karşılaştır
- [ ] Değişen seans limitleri/kategorileri YAML'de güncelle
- [ ] Yeni Pulmoner Rehab alt-bölümü (§2.4.4.F-7) için kurallar yaz (Adım 2 sonucuna göre)

### Adım 5: HBO rapor süresi güncellemesi (~1-2 saat)

- [ ] Adım 1'deki drift diff'ten `2.4.4.B` ile ilgili değişen kuralları belirle
- [ ] HBO rapor-tedavi süre koşullarını yeni metinle karşılaştır
- [ ] Değişen koşulları YAML'de güncelle

### Adım 6: Yeni ilaç endikasyonları (~2-4 saat)

- [ ] PNH (Paroksismal Noktürnal Hemoglobinüri) endikasyonlarını `4.2.14.C.yaml`'a ekle
- [ ] NMOSB (Nöromiyelitis Optika Spektrum Bozukluğu) endikasyonlarını ekle
- [ ] Actinyum-225 PSMA tedavi endikasyonlarını ekle
- [ ] SMA gen tedavisi güncellenmiş metni yansıt

### Adım 7: Doğrulama (~30 dk)

- [ ] `compile_rules.py --check` byte-identical (yeni baseline ile)
- [ ] `pytest tests/unit/ tests/smoke/` green
- [ ] SUT clause delta raporu (eski vs yeni clause sayısı + drift özeti)

---

## Efor Tahmini

| Adım | Efor | Tip |
|---|---|---|
| 1: Re-extract + drift triage | ~1 saat | Mekanik |
| 2: P701074 ambiguity | ~30 dk | Araştırma |
| 3: Copay doğrulama | ~15 dk | Doğrulama (no-op bekleniyor) |
| 4: FTR kuralları | ~2-3 saat | **İnsan authoring** |
| 5: HBO kuralları | ~1-2 saat | **İnsan authoring** |
| 6: İlaç endikasyonları | ~2-4 saat | **İnsan authoring** |
| 7: Doğrulama | ~30 dk | Mekanik |
| **Toplam** | **~8-11 saat** | Bulk = prose-rule reconciliation |

---

## Out of Scope

- Obezite cerrahisi (yeni Yönetmelik gerekiyor, SUT içeriği yetersiz)
- Clause ID kayması düzeltmesi (ayrı task)
- SUT ana metnindeki tüm 63 paragrafın derin analizi (sadece BILUN'u etkileyenler)
- Evde sağlık diş tedavisi (düşük değer, ertelendi)
