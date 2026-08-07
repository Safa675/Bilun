# Plan: Stable Clause Identity — Track E Tamamlama + Corpus Update Otomasyonu

**Tarih:** 2026-08-07
**Durum:** ÖNERİ — onay bekliyor (başlanmadı)
**İlişkili:** `plans/billing/sut-pipeline-god-plan.md` (Track A–E, D2), `plans/update/2026-08-07-sut-clause-corpus-update-plan.md` (bu plan onun ön koşulu), `plans/update/2026-08-06-stale-clause-triage-plan.md`
**Branch (öneri):** `feat/stable-clause-identity`

---

## Goal

`clause_id` (yapay `C00xxxx`) kırılganlığını bitirmek: **`clause_coordinate` (çapa) + `content_hash` (ayıraç)** tabanlı kararlı bir clause kimliği kurmak, kalan `C*` referanslarını taşımak ve **Branch B (docx → clause corpus) güncellemesini güvenli/otomatik** hale getirmek.

**Done =** (1) corpus'ta her clause'un kararlı `clause_key`'i var; (2) load-bearing hiçbir referans pozisyonel `C*`'a bağlı değil; (3) 01.07 docx re-extract'i mevcut referansları kırmıyor (değişenler yalnızca triage'a düşüyor); (4) `sut-monitor.yml` Branch B adımını güvenle koşabiliyor; (5) tam pytest + `compile_rules --check` + `audit_manifest_parity` yeşil.

---

## Problem (doğrulanmış ölçümler — 2026-08-07)

| Bulgular | Değer |
|---|---|
| `clause_id` üretimi | `extractor.py:555` → `f"C{i:06d}"` **pozisyonel sayaç** |
| Encode-eligible çakışan coordinate | **624** coordinate, 2575 satır, en kötü 194 (`4.2.14.C.(1)`) |
| `(cc, is_in_force)` | ❌ 1218 grup hâlâ çakışıyor |
| `(cc, is_in_force, clause_type)` | ❌ **1065 grup hâlâ çakışıyor** → composite key **yetersiz** |
| `(cc, in_force_text)` in-force | ✅ **82 gruba düşer** (kalan 82 = aynı coord + aynı içerik = semantik özdeş) |
| JSON artifact'larda kalan `C*` | **1491 unique** referans |
| Corpus durumu | `source_effective_date = 2026-05-23` (bayat); 01.07 docx `raw data/`da hazır |

**Kök neden:** coordinate yapısal olarak benzersiz değil (bir section altında çok sayıda bağımsız `1)` maddesi). `is_in_force`/`clause_type` bunu çözmez; **içerik çözer**. Deterministic suffix de çözmez (pozisyoneldir, re-extract'ta kayar → aynı hastalık).

**Neden corpus update bloke:** re-extract pozisyonel `C*`'ı kaydırır → load-bearing referanslar kırılır. Bu yüzden `2026-08-07-sut-clause-corpus-update-plan.md` manuel triage'a ihtiyaç duyuyor. Kararlı kimlik bu bloğu kaldırır.

---

## Tasarım: `clause_key = coordinate (çapa) + content_hash (ayıraç)`

1. **`clause_coordinate` = çapa.** Hukuki atıf, insan-okunur, re-extract'ta değişmez. gate_b referansı olarak kalır (1128 cite zaten migrate).
2. **`content_hash = sha256(normalize(in_force_text))[:8]` = ayıraç + değişiklik dedektörü.** Coordinate çakıştığında içeriğin hash'iyle ayırt eder.
3. **Kararlılık özelliği (asıl mekanizma):**
   - İçerik değişmedi → aynı hash → referans **stabil**.
   - İçerik değişti (amendment) → hash değişir → referans **triage'a düşer** (Plan 1 triage'ıyla örtüşür).
   - Yeni clause → yeni key; silinen → referans bayraklanır.
4. **Referans formatı:** `coordinate` tek başına unique ise yeterli; çakışma varsa `coordinate#<hash8>`. Resolver coordinate ile bulur, hash ile doğrular/ayırt eder.
5. **82 özdeş collision:** ordinal gerekmez (aynı coord + aynı içerik = semantik özdeş; referans belirsiz değil).

---

## Phases / Subtasks

### Phase 0 — Baseline + C* envanteri (audit)
- [ ] Kalan 1491 `C*` referansını sınıfla: **load-bearing** (gate_b/deferral/API sözleşmesi) vs **opak/türetilmiş** (encoded_clause_ids, manifest iç alan).
- [ ] `clause_coordinate` null oranı (şu an 16/8295) ve 82 özdeş-collision listesi çıkar.
- [ ] Tam pytest + `compile_rules --check` + `audit_manifest_parity` baseline kaydı.

### Phase 1 — Hash normalizasyon kilidi (EN KRİTİK)
- [ ] `normalize_for_hash(text)` tanımı: whitespace katla, unicode NFKC, satır sonu normalize — **hukuki anlamlı karaktere dokunma** (case KORUNUR).
- [ ] Golden fixture'lar: bilinen clause'lar için beklenen hash değerleri (C006549 loading-dose dahil). Hash değişimi = fixture kırar → yanlış normalizasyon anında yakalanır.
- [ ] Unit test: normalizasyon determinizmi + hash stabilitesi.

### Phase 2 — `clause_key` kolonu (extractor + parquet)
- [x] `extractor.py`: `add_identity_columns` + `write_sut_clauses_parquet` entegrasyonu (`content_hash` + `clause_key`).
- [x] `sut_clauses.parquet` şema genişletme — **backfill** (23.05 docx raw data'da olmadığı için rejenerasyon yerine mevcut kolonlardan türetme; içerik byte-identical, clause_id değişmedi).
- [x] `clause_key` benzersizlik doğrulaması: in-force 83 özdeş-collision grubu (beklenen ~82; semantik özdeş), NULL-koordinat 16 satır hash-only. `clause_key` NaN-safe yapıldı (pandas None→NaN truthy tuzağı).
- [x] Doğrulama: compile_rules 136 byte-identical, audit_manifest_parity 0 issue, 32 test geçti.

### Phase 3 — Resolver dual-read + collision migrate
- [ ] `clause_identity` resolver: `coordinate` ve `coordinate#hash` çözer; belirsizlikte fail-loud (Track A3 politikası korunur).
- [ ] Load-bearing kalan `C*` referanslarını (Phase 0 envanteri) `coordinate#hash`'e migrate et.
- [ ] Dual-read geçişi: hem `C*` hem `clause_key` kabul; provenance testleri coordinate+hash çözer.

### Phase 4 — C* demote/remove (Track E exit)
- [ ] Public contract'tan `C*` kaldır (gate_b_sources, deferral, API schema `^[CF][0-9]{6}$` → coordinate pattern).
- [ ] `clause_id` ya tamamen düşür ya da **opak, referans verilmeyen** internal kolon olarak bırak (D2 kararı).
- [ ] `stale_clause_refs.py` + `triage_stale_refs.py` şemayı güncelle.
- [ ] Fatura `F*` bu planın **dışında** (kendi epic'i, D5).

### Phase 5 — Corpus update otomasyonu (Branch B bağlama)
- [ ] 01.07 docx re-extract koş → eski/yeni `clause_key` diff'i: değişmeyenler stabil, değişenler triage listesi.
- [ ] `2026-08-07-sut-clause-corpus-update-plan.md` Phase 3 test-triage'ı bu diff üzerinden yürütülür.
- [ ] `sut-monitor.yml` Branch B adımını (extract_sut_prose) **güvenle** aktif et; PR human-gated kalır.
- [ ] Copay `1.8.1` tutarlarının 50/90/100'e hizalandığını doğrula.

### Phase 6 — Doğrulama
- [ ] Tam pytest yeşil; `compile_rules --check` byte-identical; `audit_manifest_parity --drug-only` 0 issue.
- [ ] "Re-extract stabilite" testi: aynı docx iki kez extract → tüm `clause_key` byte-identical.
- [ ] Stale reporter önce/sonra tablosu (T1/T2/T4).

---

## Out of Scope

- Fatura `F*` kimlik sistemi (D5, ayrı epic).
- Yeni prose kural yazımı (corpus değişimi yeni kural gerektirirse ayrı plan).
- Coordinate hiyerarşisini zenginleştirme (`section_path`/`parent_section_id` ile daha spesifik coordinate) — content-hash yeterli; gerekirse ileride.
- 82 özdeş-collision'ın kök-neden temizliği (veri kalitesi; blokaj değil, not edilir).

---

## Riskler

| Risk | Mitigasyon |
|---|---|
| Hash normalizasyonu kırılgan; extractor metin çıkarma değişirse sahte "değişti" sinyali | Phase 1 golden-fixture kilidi; normalizasyon değişimi fixture kırar |
| 1491 `C*`'ın load-bearing/opak sınıflaması yanlış yapılır | Phase 0 audit; migrate yalnız load-bearing olanlara |
| Çakışan coordinate'lerde hash yanlış clause'u seçer | Resolver fail-loud; belirsizlikte compile durur (Track A3) |
| Re-extract yine beklenmedik kırılma üretir | Phase 5 önce/sonra diff + human-gated PR; otomatik merge yok |
| Uzun süre çift-anahtar (dual-key) kalır | D2: dual-read yalnız geçiş fazı; Phase 4'te `C*` public'ten düşer |

---

## Success criteria

1. Corpus'ta her clause'un kararlı `clause_key`'i var; aynı docx re-extract'i byte-identical key üretir.
2. Load-bearing hiçbir referans pozisyonel `C*`'a bağlı değil; `C*` public contract'ta yok.
3. 01.07 docx re-extract'i mevcut kuralları kırmıyor — değişen clause'lar yalnızca triage listesine düşüyor.
4. `sut-monitor.yml` Branch B adımı güvenle koşuyor; corpus 01.07'ye güncelleniyor, copay 50/90/100 hizalı.
5. Tam pytest + `compile_rules --check` + `audit_manifest_parity` yeşil.

---

## Neden bu plan (alternatiflerin elenmesi)

- **Composite key `(cc, is_in_force, clause_type)`:** ölçüldü, 1065 grup hâlâ çakışıyor → ❌
- **Deterministic suffix:** pozisyonel, re-extract'ta kayar → C*'ın aynı hastalığı → ❌
- **Coordinate + content-hash:** içerik değişmeyince stabil, değişince triage'a düşer → ✅ hem C*'ı bitirir hem corpus update'i otomatikleştirir.
