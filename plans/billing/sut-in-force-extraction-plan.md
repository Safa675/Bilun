# Plan: Yürürlükteki SUT metnini ayrıştır (filter-at-read + stable clause_id)

## Goal

`data/gazette/sut_clauses.parquet`'in 8.295 satırının ~%43'ü (3.563 paragraf)
tamamen üstü çizili (struck) ölü metin; ~424 paragrafta ise canlı metin, eski
üstü çizili metinle **aynı `text_tr` içine karışmış**. Mevcut extractor
(`scripts/sut/prose/extractor.py:255-264`) `<w:strike/>` biçimlendirmesini hiç
okumadan tüm `<w:t>` node'larını birleştiriyor.

Sonuç: API, chatbot retrieval, Gate B corpus ve embedding katmanı ölü metni
canlı zannediyor. §3.1.1(2) fıkrası 3 kopya halinde görünüyor (C001618, C001619
tamamen ölü; C002684 tamamen canlı). Gate B L1.4 corpus'unda 48 satırın 24'ü
struck ghost.

Bu plan, extractor'a run-level strike-strip ekleyerek her paragraf için
**yalnızca yürürlükteki metni** (`in_force_text`) üretir; `clause_id`'leri ve
mevcut 8.295 satırı sabit tutarak 6.855 foreign-key referansını korur; tüm
downstream katmanları `in_force_text` + `is_in_force` üzerinden okur hale gelir.

## Neden filter-at-read, clean break değil

`clause_id` (`C001618` tarzı sequential counter, `extractor.py:404`) **52
dosyada ~6.855 referansla** foreign key: prose manifests (2.991 ref), corpora
(2.528 ref), prose rules (865 ref), coverage parquet, golden testler ve
`src/bilun/domain/prose_rules/drug_indication.py` (runtime).

Clean break (satır sil + yeniden numarala) tüm bu referansları migrate etmeyi
gerektirir — bu "bir sprint" değil, koordine edilmesi gereken 52 dosyalık bir
migration'dur ve §3.1.1(2)'nin 3 kopya olması zincir kırılganlığını artırır.

Filter-at-read aynı ürün davranışını verir (downstream ~4.7k canlı satır görür)
ama **sıfır clause_id migration** ile. clause_id'ler sabit kalır; ölü satırlar
fiziksel silinmez, `is_in_force=false` ile filtrelenir. Arkeoloji kaybolmaz —
audit için `text_tr` (legacy kirli extract) korunur, downstream okumaz.

## Doğrulanmış kök neden (file:line kanıtlı)

| Bulgu | Kanıt |
|---|---|
| 8.295 satır | `data/gazette/sut_clauses.parquet` = 8.295 satır, 24 kolon |
| Extractor strike okumuyor | `scripts/sut/prose/extractor.py:255-264` — tüm `<w:t>` join, `<w:strike/>` sıfır kontrol. Kod genelinde "strike" araması = sıfır eşleşme |
| %43 tamamen struck | 3.563 paragraf = %43 (27.634 `<w:strike/>` occurrence) |
| ~424 mixed-strike paragraf | Canlı+ölü metin aynı `text_tr` içinde karışık |
| §3.1.1(2) 3 kopya | C001618/C001619 %100 struck, C002684 %0 struck (canlı). Yani bu 3 paragrafta mixed-strike yok; iki ölü satır + bir canlı |
| Gate B 24/48 ghost | `data/gazette/prose_corpus/L1.4_material_bundling_prose.csv` = 48 satır, 24'ü struck ghost |
| clause_id FK yoğunluğu | 52 dosya, ~6.855 referans (manifests 2.991, corpora 2.528, rules 865, coverage parquet, testler) |
| Embedding struck gömüyor | `build_clause_embeddings.py:65-72` `is_superseded_marker` (regex, ~286) filtreler ama gerçek strike (~3.563) filtrelemiyor; ~3.277 struck paragraf gömülüyor |

## Kolon şeması (extractor çıktısı)

`clause_id` sabit. 4 yeni kolon eklenir:

| Kolon | Tip | Anlam |
|---|---|---|
| `in_force_text` | str | Yalnızca strike-olmayan `<w:r>` run'larından birleşen metin. Tamamen struck paragraf → `""` |
| `is_in_force` | bool | `in_force_text` anlamlı uzunlukta mı (yürürlükte sayılır mı). `len(in_force_text.strip()) > 0` |
| `had_struck_content` | bool | Paragrafta en az bir `<w:strike/>` run var mıydı (audit) |
| `text_tr` | str | **Legacy** — mevcut kirli extract (tüm run'lar join). Hiçbir downstream okumaz; yalnızca audit/geçmiş için korunur |

**Tanım keskinliği:** `is_in_force` "strike run var mı?" değil, "yürürlükte
sayılır canlı metin var mı?" sorusuna cevaptır. Bir paragraf hem
`had_struck_content=true` hem `is_in_force=true` olabilir (mixed-strike: bir
kısmı ölü, canlı kısmı kaldı). C001618/C001619 → `is_in_force=false`,
`in_force_text=""`. C002684 → `is_in_force=true`, `in_force_text` dolu.

## Subtasks

### Faz 1 — Extractor: run-level strike strip (3 kolon üretimi)

- [ ] `scripts/sut/prose/extractor.py` — `_read_docx_paragraphs` (line 255-264)
      yerine, her `<w:p>` için run bazında dolaş:
      - Her `<w:r>` elementinde `w:rPr/w:strike` varlığını kontrol et
        (Word namespace `w` = `http://schemas.openxmlformats.org/wordprocessingml/2006/main`)
      - Strike run'un `<w:t>` metnini `in_force_text`'e ekleme; strike-olmayan
        run'ların metnini ekle
      - Paragraf için `(in_force_text, had_struck_content)` döndür
      - Tamamen struck → `in_force_text=""`, `had_struck_content=true`
- [ ] Aynı dosya, `extract()` (line ~404 satır civarı row üretimi) — her row'a
      `in_force_text`, `is_in_force`, `had_struck_content` kolonlarını ekle.
      `text_tr` mevcut haliyle (tüm run'lar join) korunsun — legacy audit.
- [ ] `clause_id` ataması **değişmez** — `[f"C{i:06d}" for i in range(1, len+1)]`
      aynı kalır (line 404). Satır sayısı 8.295 sabit.
- [ ] Unit test: §3.1.1(2) için C001618/C001619 → `is_in_force=false`,
      C002684 → `is_in_force=true`. Bir mixed-strike paragraf → `in_force_text`
      yalnızca canlı kısmı içerir. Tamamen struck paragraf → `in_force_text=""`.
- [ ] Unit test: `(Mülga: RG-...)` satırı struck ise `is_in_force=false`.

### Faz 2 — Embeddings: in_force_text üzerinden yeniden üret

- [ ] `scripts/sut/build_clause_embeddings.py` — `select_embeddable` (line 65-72)
      filtresine `(pl.col("is_in_force"))` ekle (mevcut `~is_superseded_marker`
      ve `~is_heading` ile birlikte).
- [ ] `_embed_text` (line 57-62) `text_tr` yerine `in_force_text` okusun.
      `section_id` + `section_title` + `in_force_text` birleştir.
- [ ] `build_clause_embeddings.py`'yi yeniden çalıştır → embedding sidecar
      yeniden üretülür. clause_id'ler aynı olduğu için content_hash değişen
      satırlar yeniden gömülür, değişmeyenler cache'lenir (idempotent mantık
      line 9-10'da tanımlı).

### Faz 3 — Downstream filter-at-read (API, chatbot, coverage)

- [ ] SUT clause API endpoint'ı (`src/bilun/api/routes/` altında SUT clause
      döndüren endpoint) — varsayılan `WHERE is_in_force = true` ile okusun.
      İsteğe bağlı `?include_superseded=true` query param ile legacy erişim
      kalsın (audit/debug için).
- [ ] Chatbot retrieval (clause embedding lookup) — `is_in_force=false` satırı
      asla surface et. Retrieval candidate set zaten Faz 2 sonrası temiz.
- [ ] `data/gazette/sut_clause_coverage.parquet` — `is_in_force=false`
      satırlarını encode候选/coverage hesabından düşür.
- [ ] `src/bilun/domain/prose_rules/drug_indication.py` — clause_id referansları
      (6 ref) hâlâ geçerli mi doğrula; `is_in_force=false` ID'ye referans
      varsa uyar.

### Faz 4 — Gate B corpus + gate_b_sources temizliği (otomatik script)

- [ ] `data/gazette/prose_corpus/L1.4_material_bundling_prose.csv` ve
      `L1.4_material_bundling_corpus_batch2.csv` — 24 struck ghost satırı düşür.
      clause_id'ler sabit olduğu için bu, satır silme değil `is_in_force` join
      ile filtre: `[r for r in corpus if sut_clauses[r.clause_id].is_in_force]`.
- [ ] **Otomatik, tekrar üretilebilir script** yaz (manuel değil): tebliğ
      refresh'inde extractor yeniden çalışınca `is_in_force` değişebilir; bu
      script her çalıştığında gate_b_sources'u
      `[c for c in sources if sut_clauses[c].is_in_force]` ile tazelesin.
      Manuel temizlik = synthetic-data drift problemiyle aynı aile.
- [ ] `data/gazette/prose_manifests/` (7 dosya, 2.991 ref) — `gate_b_sources`
      listelerinden `is_in_force=false` clause_id'leri otomatik script ile
      temizle. Referans clause_id olarak kalır (silinmez), ama metin kaynağı
      olarak kullanılmaz.
- [ ] Golden testlerde struck clause_id assertion varsa güncelle.

### Faz 5 — Doğrulama + ship

- [ ] Extractor unit testleri yeşil (Faz 1).
- [ ] pytest tam yeşil.
- [ ] Embedding sidecar yeniden üretildi, satır sayısı ~4.7k (önce ~8k).
- [ ] API'de `is_in_force=false` satır dönmez (default mod).
- [ ] L1.4 corpus'ta 0 ghost (24 struck satır temizlendi).
- [ ] §3.1.1(2) = tek canlı metin = C002684'nin `in_force_text`'i.
- [ ] Bir mixed-strike paragrafında `in_force_text` yalnızca canlı kısmı içerir
      (spot-check §4.2 amendment zinciri).
- [ ] Chatbot retrieval artık C001618 sınıfı (ölü) satır surface etmiyor.
- [ ] CI yeşil.

## Out of scope

- **clause_id re-numbering** — sequential C00xxxx FK graph'ı sabit kalır. Clean
  break yalnızca clause_id zaten `(section_id, fıkra_no, content_hash)` tarzı
  semantik anahtara taşınırsa mantıklı; şu an değil.
- **Tam yasal versiyon kontrolü** — "bu paragraf RG-2013 tarafından eklendi,
  RG-2019 ile değiştirildi" tarzı değişiklik zinciri arkeolojisi. İşlenmiş
  docx bunu zaten yapmış; ürün bunu tekrar yapmamalı.
- **Text-pattern supersession inference** — `(Mülga:…)` / `(Değişik:…)` regex
  marker'larından supersession çıkarma. Bu ~286 satırı yakalıyor, ~3.277
  struck satırı kaçırıyor; strike biçimlendirmesi tek güvenilir sinyal.
- **`text_tr` kolonunun kaldırılması** — legacy/audit için korunur, downstream
  okumaz. Kaldırmak ayrı bir cleanup task.

## Verification of done

- §3.1.1(2) tek canlı metin gösterir: `C002684.in_force_text`. `C001618`/`C001619`
  `is_in_force=false`, API/chatbot'da görünmez.
- `sut_clauses.parquet` hâlâ 8.295 satır (fiziksel silme yok); ~4.732 satır
  `is_in_force=true`.
- Bir mixed-strike paragrafının `in_force_text`'i yalnızca canlı kelimeleri
  içerir (ölü cümle yok).
- Gate B L1.4 corpus'ta 0 struck ghost.
- Embedding sidecar ~4.7k satır (önce ~8k); struck metin gömülü değil.
- API `GET /sut/clauses` default `is_in_force=true` filtreli döner.
- clause_id referansları (6.855 ref) bozulmamış — hiçbir manifest/test migrate
  edilmedi (Gate B ghost temizliği hariç, o da clause_id silmeden filtreledi).

## Review (2026-06-26)

Uygulandı. Özet metrikler:

| Metrik | Sonuç |
|--------|--------|
| `sut_clauses.parquet` satır | 8.295 (sabit) |
| `is_in_force=true` | 4.710 |
| Embeddings sidecar | 4.020 |
| Coverage parquet | 4.710 |
| L1.4 Gate B corpus | 48 → 24 |

Regenerate pipeline:

```bash
python scripts/sut/extract_sut_prose.py --docx "raw data/2026.05.23-.../23.05.2026 - ....docx"
python scripts/sut/build_sut_coverage.py
python scripts/sut/build_clause_embeddings.py --provider local --force
python scripts/sut/sync_gate_b_in_force.py
```

pytest: 838 passed.
