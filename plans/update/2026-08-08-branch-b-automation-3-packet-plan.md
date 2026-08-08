# Plan: Branch B Otomasyonu — 3 Paket (docx → clause corpus otomatik güncelleme)

**Tarih:** 2026-08-08
**Durum:** ONAY BEKLİYOR (Safa onayı sonrası Paket 1 başlar)
**İlişkili planlar:** `plans/update/2026-08-07-stable-clause-identity-track-e-plan.md` (Track E), `plans/update/2026-08-07-sut-clause-corpus-update-plan.md` (01.07 corpus, BEKLEMEDE gate'i bu planla kalkar), `plans/update/2026-08-07-track-e-phase0-audit.md`

---

## Goal

`sut-monitor.yml`'daki Branch B adımını (docx → `sut_clauses.parquet` re-extract) **güvenli otomatik** çalışır hale getirmek. Güvenli = re-extract sonrası hiçbir kural referansı sessizce yanlış maddeye bağlanmaz; değişen hükümler fail-loud veya triage listesine düşer; PR insan onayıyla merge olur (auto-merge yok).

**Done =**
1. Authored C* yüzeyi kapanmış (kalanlar belgeli istisna).
2. 01.07 docx re-extract'i elle koşulmuş, copay 1.8.1 = 50/90/100 hizalanmış, downstream rejenere edilmiş, tam pytest yeşil.
3. Re-extract stabilite testi var (aynı docx 2× → clause_key byte-identical).
4. `sut-monitor.yml` Branch B scheduled run güvenli; PR human-gated kalır.

---

## Bağlam (ölçülmüş durum, 2026-08-08)

### Neden bu plan

- Branch A (xlsx ekler → kataloglar) **güncel**: `ingest_state.json` last_ingested=2026-07-01. Branch A artifact'ları (curated/pricing) hiç C* referansı taşımıyor → kimlik işinden bağımsız.
- Branch B (docx → corpus) **bayat**: `sut_clauses.parquet` source_effective_date=2026-05-23. Copay tutarları docx gövdesinde → copay freshness açığı (kural JSON 50/90/100 TL, clause store 26/60 TL). **Asıl iş değeri bu hizalamadır.**
- Track E (#58/#59) public contract'tan `clause_id`'yi kaldırdı (API/frontend/lossless refs); ama **authored C* hâlâ var** ve re-extract'ta pozisyonel `C*` kayarsa bu ref'ler sessizce yanlış maddeye bağlanır. Otomasyonun ön koşulu bunların kapatılmasıdır.

### Ölçümler (bu planı besleyen veriler)

| Ölçüm | Değer | Kaynak |
|---|---|---|
| Toplam distinct gate_b ref | 1822 | prose_rule_sources audit |
| Coordinate-only ref → unique in-force çözüm | 970 | parquet join |
| Coordinate-only ref → **ambiguous** | **0** | parquet join |
| Coord#hash formatındaki ref | 617 | '#' içerenler |
| Saf C* ref | 235 | C###### |
| C* ref → unique-coordinate (doğrudan coordinate'e taşınabilir) | 59 | parquet join |
| C* ref → çakışan koordinat, farklı içerik (coord#hash'e taşınabilir) | 122 | parquet join |
| C* ref → (coord, hash) özdeş-kopya (taşınamaz, istisna) | 54 | 23 koordinatta |
| deferral_table.yaml entry | 1541 (hepsinde clause_coordinate var; 806 unique coord) | yaml audit |
| `clause_id` üretimi | `extractor.py:559` pozisyonel sayaç `C{i:06d}` | kod |
| In-force (coord, hash) çakışma grubu | 83 grup / 193 satır | parquet |
| Encode-eligible in-force çakışma (hiyerarşi v2) | 21 grup / 44 satır | state machine ölçümü |
| Encode-eligible in-force çakışma (hiyerarşi v3 + roman takibi) | 15 grup / 30 satır | state machine ölçümü |
| In-force çakışma satırlarında strike oranı | 1/193 | parquet |
| docx paragrafında gerçek Word listesi (numPr) | 478/8657; sorunlu bölgelerde 0 | document.xml |
| Striketrough sinyali | 7000-7006 bloğu tamamen `<w:strike/>` | document.xml |
| Eski (7) Kladribin | `had_struck_content=True`, `is_in_force=False` | parquet (C006650) |
| Yeni (7) Kladribin | `False`, `True` | parquet (C006657) |

### Temel kavrayışlar (tasarımı belirleyen)

1. **İki kimlik iki ihtiyaçtır, tasarım hatası değil:** `clause_key` (coord#hash) = hüküm kimliği (içerik-anchored, stabil); `clause_id` = satır kimliği (docx'te aynı hükmün tekrar eden oluşumları). Kaynak doküman aynı hükmü tekrarladığı sürece satır kimliği içeride gerekir.
2. **Strike → in-force mekanizması zaten çalışıyor:** docx'te eski metin `<w:strike/>` ile işaretli; extractor `had_struck_content=True` → `is_in_force=False` veriyor; resolver `in_force_only=True`. Amendment çiftleri (aynı fıkra iki kez: eski+yeni) bu mekanizmayla **zaten çözülüyor**.
3. **Hiyerarşi makinesi sıfıra yakınsamıyor:** docx'te makine-okunur liste yok (manual numaralama, tutarsız girinti: 709/708/None; `(n)` vs `n)` derinlik söylemiyor; roman madde varyantları `iii)`/`jjj)`). Her kural yeni desen çıkarıyor: 83→21→15. **Yeni makine kurmak yerine: ölçüm + fail-loud resolver.**
4. **Resolver fail-loud:** bir ref >1 satıra çözülürse compile durur (Track A3). Belirsizlik asla sessiz değil.

---

## Tasarım ilkesi

**Referans kimliği = `clause_coordinate` (veya `coord#hash`); değişim tespiti = hash mismatch → fail-loud; satır kimliği = `clause_id` (yalnızca iç).**

- `coord` tek başına unique çözenler için yeterli (ölçüm: 0 ambiguous coordinate ref).
- `coord#hash` içerik değişiminde mismatch üretir → amendment sonrası ref triage'a düşer (asıl otomasyon güvenliği).
- C* ref: yalnızca 54 özdeş-kopya için kalır, belgeli istisna; re-extract sonrası `stale_clause_refs` + `triage_stale_refs` ile bayraklanır (sessiz kırılma yok).

---

## Phases / Subtasks

### Paket 1 — Referans yüzeyini kapat (ölçüm revizyonu 2026-08-08)

**Ölçümle revize edildi.** Orijinal 1.1 varsayımı ("181 C* gate_b ref taşınabilir") çürüdü:
235 C* ref'in 192'si `prose`/`amendment` (encode-eligible değil → koordinat/clause_key'e taşınması compile'da `NonEncodeEligibleCiteError` fırlatır; Track A3 gereği opaque C* kalmalı), 43'ü eligible ama hepsi (coord, hash) özdeş-kopya (lossless değil; resolver 2+ id döndürür). **Taşınabilir ref = 0 — gate_b_sources durumu zaten güvenli.** Asıl yüzey diğer authored C* kaynaklarıdır.

**Amaç:** Re-extract artık hiçbir authored referansı sessizce kaydıramaz.

- [ ] 1.2 — **wave_config + sections + stub taşıması** (asıl iş):
  - [ ] `gate_b_wave_config.py` `DRUG_INDICATION_WAVE_CLAUSE_IDS` (199 C* → 184 taşınabilir: 113 unique-coord + 71 hash; 13 prose + 2 özdeş kalır). **Manifest etkisi:** `_stage_csv_wave_clause_ids` (compile_rules.py:778-781) C*'leri `encoded_clause_ids`'e yazıyor; manifest'ler hâlâ saf C* (397/397). PR #59 `encoded_clause_keys` dual-write altyapısını ekledi (manifest_index.py:166-169) — wave manifest'lerine uygulanır; parity audit C* karşılaştırmasını korur.
  - [ ] `gate_b_sections.py` (74 C* → 50 taşınabilir: 31 unique + 19 hash; 14 not-in-force + 10 prose/amendment kalır)
  - [ ] `_PAYMENT_SESSION_MANIFEST_STUB` (7 C* → 6 taşınabilir; C000661 prose kalır)
  - [ ] `clause_type_overrides.yaml` (15 C*, hepsi prose) → belgeli istisna, taşınmaz
- [ ] 1.3 — **deferral_table rekey**: `clause_id` C* → koordinata DEĞİL (1004/1541 entry ambiguous coordinate → rekey sessiz kayıp üretir; ölçüldü). Çözüm: coord#hash'e (parquet content_hash join ile). Tüketiciler: `gate_b_generic.py:59-129`, `coverage.py:145-158`
- [ ] 1.4 — 54 özdeş-kopya ref + 192 non-eligible ref belgeli istisna listesi + "artamaz" testi
- [ ] 1.5 — CI ölçüm testi: "ambiguous coord ref = 0" + "in-force (coord, hash) çakışma grubu ≤ 83"
- [ ] 1.7 — **YENİ: C* parquet'te yoksa → compile hatası** (`clause_identity.py:444-448` UnknownC* hoşgörüsünü kapat; re-extract sonrası tam korpus garantisi var)
- [ ] 1.6 — `.github/workflows/ci.yml` commit'lenmemiş `fetch-depth: 1` değişikliğini dahil et
- [ ] 1.8 — **Doğrulama**: `compile_rules --check` (beklenen delta: yalnızca taşınan ref formatı), `audit_manifest_parity` 0 issue, tam pytest + ruff

**Paket 1 Done =** authored C* yüzeyi yalnızca belgeli istisnalardan (≤54+audit kalıntısı) oluşuyor; CI 1.5 ölçümleri ekli ve yeşil.

---

### Paket 2 — 01.07 docx manuel re-extract (orta risk, asıl bilinmeyen)

**Amaç:** Extract'ı yeni docx'le ilk kez koşup Branch B sürecini manuel kanıtlamak; copay hizalamasını kapatmak.

- [ ] 2.1 — Yeni branch `chore/sut-0107-clause-corpus`; `extract_sut_prose.py`'yi 01.07 konsolide docx ile koş (`raw data/2026.07.01-Değişiklik Tebliği İşlenmiş Güncel 2013 SUT/01.07.2026 - Değişiklik Tebliği İşlenmiş Güncel 2013 SUT.docx`). **İlk kez deneniyor** — extractor kırılabilir (2026-06-19 dersi: xlrd/odfpy dependency gap'leri burada çıkar; failures satırını oku).
- [ ] 2.2 — Doğrula: `source_effective_date=2026-07-01`; clause sayısı delta'sı makul (8295'e yakın); **copay 1.8.1 in-force tutarları 50/90/100 TL** (şu an 26/60 — asıl iş değeri).
- [ ] 2.3 — Downstream rejenere: `build_sut_coverage.py` (coverage parquet'leri), `compile_rules.py` (manifestler), embeddings; `sut_clause_diff.py` eski/yeni clause_key diff (stabil/amended/new/removed).
- [ ] 2.4 — Tam `pytest -q`; kırıkları sınıfla: **bilinçli değişim** (yeni clause_key'ler, taşınan hükümler, C* kayması) vs **gerçek kırık**. Golden sabitler YALNIZCA re-audit sonrası güncellenir (2026-06-22 dersi: committed artifact okuyan test vs rebuild eden test ayrımı).
- [ ] 2.5 — Paket 1'deki istisna ref'lerin triage ile doğrulanması: strike→in-force elenenler temizlenir; gerçek özdeş-kopyalar kalır; yeni çakışmalar raporlanır.
- [ ] 2.6 — `stale_clause_refs.py` + `triage_stale_refs.py` önce/sonra tablosu (T1/T2/T4) → PR body'sine.
- [ ] 2.7 — Tek `chore(data)` PR; delta özeti + triage notları; §10 (CI öncesi kontrol) + §11 (review) süreçleri uygulanır.

**Paket 2 Done =** corpus 01.07'de; copay hizalı; CI yeşil; diff/triage raporları PR'da.

---

### Paket 3 — Otomasyonu güvenle bağla (düşük risk, en son)

**Amaç:** `sut-monitor.yml` Branch B adımını scheduled run'da güvenli çalıştırmak.

- [ ] 3.1 — **Re-extract stabilite testi**: aynı docx iki kez extract → tüm `clause_key` byte-identical (Track E Phase 6; test olarak CI'a eklenebilir).
- [ ] 3.2 — `sut-monitor.yml` denetimi: snapshot adımı (`cp sut_clauses.parquet`), `sut_clause_diff.py` çağrısı, PR body render (`clause_diff_summary` + `delta_summary`) — Paket 2'deki gerçek diff çıktısıyla smoke test.
- [ ] 3.3 — Scheduled run'ın güvenlik kriterleri: ref'ler coord/coord#hash olduğundan re-extract refs kırmaz; değişenler triage'a düşer; PR human-gated kalır (branch protection `chore/sut-auto-update`).

**Paket 3 Done =** Branch B bir tam tebliğ döngüsünü (monitor → fetch → extract → diff → PR) sorunsuz üretiyor.

---

## Out of Scope

- 82 özdeş-collision grubunun kök-neden temizliği (dedupe / hiyerarşik koordinat makinesi) — ölçüm + fail-loud yeterli; veri kalitesi işi olarak ayrı plan.
- Fatura `F*` kimlik sistemi (D5).
- Branch A re-ingest (zaten güncel).
- Yeni prose kural yazımı (corpus değişimi yeni kural gerektirirse ayrı plan).
- Katsayı değişimi kontrolü (01/07 tebliğinde varsa ayrı iş).

---

## Riskler

| Risk | Olasılık | Mitigasyon |
|---|---|---|
| Extractor 01.07 docx formatında takılır (ilk kez koşuluyor) | Orta | Paket 2 manuel koşu; failures satırı; 2026-06-19 dependency dersi |
| 181 ref migrasyonu encoded_clause_ids'i değiştirir (lossless beklentisi boşa çıkar) | Düşük | 1.1 doğrulaması: resolver aynı clause_id setini üretmeli; fark = fail |
| deferral rekey 806 unique coord'da çakışma yüzünden takılır | Orta | Çakışanlar coord#hash; test güçlendirme; tek tek triage |
| Re-extract C* kayması golden testleri kırar | Kesin | 2.4 bilinçli re-audit; sessiz güncelleme yok |
| İstisna 54 ref sayısı zamanla artar (yeni tebliğ) | Düşük | 1.4 "artamaz" testi; CI 1.5 eşiği |
| Hash normalizasyonu değişirse sahte "değişti" sinyali | Düşük | Track E golden fixture kilidi (Phase 1) korunur |
| Scheduled run kötü PR üretir (gürültü) | Orta | Human-gated PR; PR body diff özeti; Paket 2 gerçek çıktısıyla kalibrasyon |

---

## Success criteria

1. Authored C* yalnızca belgeli istisna kümesinde (54 + audit kalıntısı); CI: ambiguous coord ref = 0.
2. Corpus source_effective_date=2026-07-01; copay 1.8.1 = 50/90/100; tam pytest + `compile_rules --check` + parity yeşil.
3. Aynı docx 2× extract → clause_key byte-identical (stabilite testi CI'da).
4. `sut-monitor.yml` Branch B bir tam döngü üretir; PR human-gated; değişen hükümler triage'a düşer, sessiz kayma yok.
5. Belirsiz ref çözümü compile'ı durdurur (fail-loud), asla yanlış kural üretmez.

---

## Neden bu plan (alternatiflerin elenmesi)

- **Hiyerarşik koordinat makinesi (dedupe/roman/girinti kuralları):** ölçüldü — 83→21→15 gruba düşüyor ama sıfırlanmıyor; docx'te makine-okunur hiyerarşi yok (numPr yok, girinti tutarsız 709/708/None, `n)` derinliği belirsiz). Karmaşıklık getirir, garanti vermez. → reddedildi.
- **clause_id'yi tamamen silmek:** 54 özdeş-kopya satır (aynı koordinat + aynı içerik) ayırt edilemez; satır kimliği kaynak dokümanın tekrarından doğar. → imkânsız, gerekli değil.
- **Strike→in-force yalnız başına:** amendment çiftlerini çözer (1/193 strike in-force çakışmada) ama canlı metin tekrarlarını (6 ilaç örneği) çözmez. → mevcut mekanizma korunur, yeterli değil.
- **Status quo (54 ref C* kalır, otomasyon yine bağlanır):** C* ref'ler re-extract'ta kayıp yanlış maddeye bağlanır; compile yine geçer → sessiz hatalı kural. → otomasyon güvenliği yok, reddedildi.
