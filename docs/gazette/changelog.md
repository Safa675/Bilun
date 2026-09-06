# Gazette / SUT Tebliği Changelog

Bu dosya, BILUN'un aktif SUT kaynağının hangi tebliği temel aldığını ve yapılan replace/patch işlemlerini izler. Kaynak her zaman **SGK'nın resmî "İşlenmiş Güncel 2013 SUT" paketidir** (OHSAD/üçüncü taraf değil).

---

## 2026-08-29 — Aktif SUT 2026.07.01 → 2026.08.29 (konsolide + kural korpusu)

RG-29/08/2026-33355, yürürlük **05/09/2026**. Kaynak: `2026.08.29-Değişiklik Tebliği İşlenmiş Güncel 2013 SUT`.

### Ingest (PR #80)
- Branch A katalogları + Branch B `sut_clauses.parquet` (8,388 clause).
- Clause diff: **8,323 STABLE / 93 AMENDED / 2 NEW / 0 REMOVED**.
- `ingest_state.json`: `last_ingested_date: 2026-08-29`.

### Encoded-rule follow-through
Track E hashed `gate_b_sources` fail-loud on amendment. Remapped 12 YAML cites + 5 `gate_b_wave_config.py` keys (similarity-matched to the new hash at the same coordinate).

Substantive YAML updates:
- **§4.1.4.c**: non-gyn topikal antifungaller dermatoloji-only; yeni jinekolojik antiinfektif/antiseptik kolu (KÜB pozoloji; 6 ay tüm hekimler, sonrası KHD).
- **§4.2.1.C-3.a / C-5.a**: 3 DMARD × 3 ay önkoşulu mülga; anti-TNF + DAS28>5.1 kaldı. Yeni **C-3.d / C-5.d** grandfathering (05/09/2026 öncesi başlayanlar, devam şartları).
- **§4.2.8.A.b**: rapor 6 ay, nörolojik hastalıklarda 1 yıl.
- **§4.2.14.C**: KLL hash remap (monoterapi; nüks 4-kür / BCL2); nilotinib hash remap.
- **§4.2.15.D-1/D-2**: kurula girişimsel radyoloji (+ D-1: beyin ve sinir cerrahisi).
- **§4.2.38.(8)**: empagliflozin+linagliptin açıkça tip 2 diyabet.

C* positional ids shifted with the re-extract (`clause_type_overrides.yaml` remapped; YAML `C*` `gate_b_sources` retargeted by clause_key). Stale 07-01 overrides had mis-tagged `4.2.9.A.(1)` as `prose`.

Unencoded AMENDED coords (`2.4.2.B-1.(2)`, `4.1.4.(4)`, `4.2.14.B.(1)`, `4.2.15.D-1.(3)`) and synthetic cohort regen are out of scope.

---

## 2026-06-22 — Aktif SUT 2026.04.08 → 2026.05.23 (konsolide replace)

### Yapılan
- **Replace**: Aktif SUT kaynağı `2026.04.08` konsolide paketten `2026.05.23` konsolide pakete değiştirildi.
- **Pipeline**: `convert_xlsx_to_parquet.py` (312 sheets, 0 failures) → `build_curated_catalogs.py` (74 catalogs) → `extract_sut_prose.py` (8,295 clauses) → `ek4d_copay_exempt.py` (3,196 entries) → `generate_readmes.py` (14 READMEs) → `generate_sut_synthetic_data_v2.py` (50 patients, 502 procedure lines, 254 drug lines) → `build_cache.py --activate` (build 96e91a3c).
- **Manifest**: max `effective_date` = `2026-05-23`.

### Değişen EK'ler (04.08 → 23.05 diff)
- **EK-1, EK-2, EK-3**: byte-for-byte identical — zero changes.
- **EK-4A** (bedeli ödenecek ilaçlar): −44.6 KB, eski liste MÜLGA'ya arşivlendi, yeni küçük liste aktif.
- **EK-4D** (katılım payından muaf ilaçlar): +9.2 KB, entries 3,196'ya yükseldi.
- **EK-4E** (sistemik antimikrobik reçete kuralları): +777 B, küçük değişiklik.
- **EK-4F** (ayakta tedavi sağlık raporu ilaçlar): −1.5 KB, bazı ilaçlar çıkarıldı.

### Test güncellemeleri
- Drug indication clause count: 828 → 832
- Synthetic data counts: procedure 501→502, material 110→112, drug 245→254, expected 433→438
- `test_billing_actions.py::test_f015`: claim 003-015'in prosedür kodları değişti, compliance violations 2→0, action_count 3→1.
- `generators.py:1500`: EK-2C-1 reconcile sonrası ilave ücret flag'leri temizleniyor (consistency fix).
- `test_synthetic_data_integrity.py`: bilinçli "copay uygulanmamış" violation demo satırı identity check'ten muaf.
- **Sonuç**: 785 passed, 10 skipped.

---

## 2026-06-19 — Aktif SUT 2026.01.17 → 2026.04.08 (konsolide replace)

### Yapılan
- **Replace**: Aktif SUT kaynağı `2026.01.17` konsolide paketten `2026.04.08` konsolide pakete değiştirildi (RG 33218).
- **Pipeline tam rebuild**: `convert_xlsx_to_parquet.py` (311 sheet, 0 failure) → `build_curated_catalogs.py` (tüm EK katalogları) → `extract_sut_prose.py` (8.276 clause) → EK-4/D extractor → README yeniden üretim.
- **Manifest**: `version_manifest.parquet` maksimum `effective_date` artık `2026-04-08`.
- **Chatbot metadata**: `src/bilun/chatbot/metadata.py` artık `gazette_version`'ı manifest'ten canlı okuyor (önceden `None` idi).

### Yanında düzelen latent bug'lar
Bu replace sırasında pipeline'da iki önceden-var-olan gizli hata yüzeye çıktı ve düzeltildi:
1. **`xlrd` eksik** (`requirements.txt`/`pyproject.toml`'da tanımlı değildi) → `.xls` formatındaki EK annex'leri (EK-1A, EK-3B-1/2, EK-3C-1, EK-2Ç vb.) okunamıyordu. Committed `.xls`-kaynaklı parquet'ler eski bir ortamdan kalıntıydı. `xlrd>=2.0.1` eklendi.
2. **`_find_raw_parquet` `unknown` partisyonlarını atlıyordu** (`scripts/sut/_common.py`) → tarihsiz tek-sürüm annex'leri (EK-1A `.xls` dosya adında tarih yok) hiç bulunamıyordu. Tarihli sürüm yoksa `unknown`'a güvenli fallback eklendi. EK-1A artık 97 satırla doğru inşa ediliyor (committed 98 idi).

### Doğrulama
- `pytest tests/`: **732 passed**, 0 failed.
- Test'ler fiyat kataloğuna karşı değil kendi mock input'larına karşı assert ettiği için 04.08 fiyat değişiklikleri test mantığını kırmadı.
- Chatbot `gazette_version` = `2026-04-08` olarak doğrulandı.

---

## 2026-05-23 — Tebliği (RG 33262, yürürlük 01.06.2026) — DURUM: KISMI

### Mevcut durum
23 Mayıs 2026 tebliği BILUN'a **tam konsolide paket olarak henüz alınmadı** — sadece Resmî Gazette delta metni (10 MADDE) ve MADDE 9'a ait ayrı bir EK-4A xlsx mevcut (`raw data/2026.05.23-*`). Tam "İşlenmiş Güncel SUT" paketi SGK'dan indirilip `raw data/` altına açıldığında normal pipeline süreci değişiklikleri içine alır.

### Delta içeriği (10 MADDE) ve BILUN'a etkisi
| MADDE | Konu | BILUN kuralı | Karar |
|---|---|---|---|
| 1 | §4.2.1.C-1 anti-TNF (infliximab/sertolizumab/golimumab) | Yok | **Scope dışı** — BILUN'da anti-TNF indication motoru yok |
| 2 | §4.2.8.A çocuk boy/kilo | Yok | Scope dışı |
| 3 | §4.2.12.B-1 IVIG doz | Yok | Scope dışı |
| 4 | §4.2.14.C prostat ADT (yeni N1/Gleason/PSA + mHSPK kriterleri) | **Var** (`drug_indication_prose.json`, golden-file gated) | **Ertelendi** — elle patch etmek yerine bir sonraki konsolide pakette normal encoder workflow'uyla gelsin |
| 5 | §4.2.24.B salmeterol/arformoterol | Yok | Scope dışı |
| 6 | §4.2.30.A PAH (bosentan/treprostinil/masitentan) | Yok | Scope dışı |
| 7 | §4.2.33 anti-VEGF (ranibizumab/aflibersept yükleme dozu) | Yok | Scope dışı |
| 8 | §4.2.66 gonadotropin | Yok | Scope dışı |
| 9 | EK-4/A ilaç listesi değişti | EK-4A parquet (04.08'den) | **Diff yapıldı, sonuç belirsiz (aşağıda)** |
| 10 | EK-4/D A31 mikobakteri + quinolone/linezolid muafiyeti | `.doc`-parse | Ertelendi — sentetik Mayıs `.doc` kurmak kırılgan |
| 11 | EK-4/E antimikrobik reçeteleme | Yok | Scope dışı |

### EK-4/A diff notu (MADDE 9)
`2026.05.23-EK-4A Yeni Liste.xlsx` (8078 ilaç) ile 04.08 EK-4A (8504 ilaç) karşılaştırıldı: **+82 added, −508 removed, net −426**. Ama sonuç **güvenilir değil**, çünkü:
- Kaldırılanların 300'ünde `passivation_date` boş ve temel ürünler (dekstroz solüsyonları) dahil — bu mantıksız.
- İki dosya da aynı `kamu_no` aralığını (A1..A20xxx) kapsadığı için May dosyası tam liste görünüyor, ama yine de 426 eksik.
- **Şüphe**: İndirilen May xlsx'i SGK'nın tam listesi değil, tebliğin "ekteki" kısmı olabilir. Doğrulanana kadar diff rakamları `ek4a_drugs.parquet`'e uygulanmadı; 04.08 EK-4A aktif kaldı.

### Sonraki adım
- SGK'nın 23.05.2026 tebliği için tam "İşlenmiş Güncel 2013 SUT" paketi indir → `raw data/2026.05.23-Değişiklik Tebliği İşlenmiş Güncel 2013 SUT/` → pipeline replace → §4.2.14.C prostat değişikliği normal encoder süreciyle işlensin.

---

## Periyodik tebliğ takip süreci
SGK SUT'ta ayda ortalama 1-2 değişiklik tebliği yayınlar. Güncel kalmak için:

1. **WebSearch** (MCP quota, ayda birkaç arama): `"SGK SUT değişiklik tebliği YYYY resmi gazete"` ve son tebliğ tarihinden sonrasını ara.
2. **SGK duyuru sayfası**: `sgk.gov.tr/duyuru` altında "İşlenmiş Güncel 2013 SUT" paketini bul.
3. **İndir + aç** `raw data/` altına (mevcut format: `YYYY.AA.GG-Değişiklik Tebliği İşlenmiş Güncel 2013 SUT/`).
4. **Pipeline**: `convert_xlsx_to_parquet.py --input-dir <yeni> --overwrite-manifest` → `build_curated_catalogs.py --overwrite` → `extract_sut_prose.py --docx <yeni docx>` → EK-4/D → README.
5. **Diff**: yeni vs eski `sut_clauses.parquet`'tan değişen maddeleri çıkar, BILUN `rule_registry`'ye dokunanları tespit et.
6. **Doğrula**: `pytest tests/` yeşil olmalı; fiyat-bağımlı fixture varsa güncellenmeli.

**Önemli ayrım**: "Değişiklik tebliği" (delta, sadece MADDE'ler) ile "İşlenmiş Güncel SUT" (tam konsolide metin) farklı şeylerdir. Pipeline her zaman tam konsolide paket ister; delta sadece hangi maddelerin değiştiğini anlamak içindir.
