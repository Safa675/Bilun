## Task: FI checklist relevance + dayanak UX

### Goal
FI documentation reminders only show when claim signals match; dayanak column shows FI/SUT **section** labels (not F000/C000); column title is “Dayanak”. Plan: `plans/billing/2026-07-29-fi-checklist-relevance-dayanak-plan.md`. Option B locked.

### Subtasks
- [x] Plan onay — Option B (kodsuz branş: sinyal yoksa gizle)
- [x] Phase 1: relevans gates + `sut_anchor` = `Fatura İnceleme {ref}` (+ tests)
- [x] Phase 2: i18n “Dayanak” / “Basis” + footnote
- [x] Phase 3: verify (0003-011 spam down; dayanak filled)

### Out of Scope
- EMR document presence
- Algorithmic FI violation changes
- A2 separate UI block
- Removing `gate_b_sources` from JSON provenance

### Review
- Option B: code-less rules need `relevance_signals`; 6 ORTAK + ORTOPEDİ-6 wired; other 15 code-less hidden until signals added
- Dayanak: `Fatura İnceleme {ref}` (+ optional `sut_section_label`); never F000/C000
- FE: TR Dayanak / EN Basis; footnote mentions FI+SUT
- Tests: 36 passed (`test_fatura_inceleme_checklist`, `test_claim_readiness`, `test_billing_actions`)

---

## Task: Commit & push Finans Coder pipeline removal

### Goal
Commit the working-tree changes (removal of the Finans Coder / coding-resolver pipeline + agent-doc updates) and push to `origin/fix/fi-checklist-relevance-dayanak` with green CI.

### Subtasks
- [x] Delete leftover `tests/unit/scripts/test_finans_cleanup.py` — imports deleted `analyze_finans_data` → pytest collection error (breaks full-suite CI)
- [x] Update `agents/reimbursement/run_checks.sh` — drop step 1 (`verification_loop.py` deleted)
- [x] Update `agents/reimbursement/system-prompt.md` "This runs:" list — remove `verification_loop.py`
- [x] Verify: full `pytest -q` green + `ruff check src/ scripts/` clean
- [x] Commit 1: `chore: remove Finans Coder coding pipeline` (deletions + agent docs + test cleanup + lessons)
- [x] Commit 2: `fix(data): update L1.8 copay-exemption manifest effective_date` (2026-07-25 → 2026-08-01)
- [x] Push; confirm no pre-existing failing CI on branch (AGENTS.md §10)

### Out of Scope
- Re-enabling any Finans Coder functionality
- Deleting historical plan docs that reference the removed pipeline
- `tasks/lessons.md` historical entries mentioning removed scripts

---

## Task: TIER-1 stale clause ref triage + burn-down

### Goal
158 TIER-1 gate_b referansını sil / re-encode / zararsız diye sınıflandırıp rule-set başına PR'larla eritmek. Plan: `plans/update/2026-08-06-stale-clause-triage-plan.md` (K1-K5 onaylı).

### Subtasks
- [x] Phase 0: plan onayı (K1-K5 hepsi onaylandı 2026-08-06) + todo güncelleme
- [x] Phase 1: `scripts/sut/triage_stale_refs.py` — mülga diff + overlap skoru + A/REVIEW/B önerisi; md + parquet rapor (ayrıca stale_clause_refs.py + triage script'ine sys.path bootstrap: bare invocation ModuleNotFoundError düzeltildi)
- [x] Phase 1: unit testler — 13 test yeşil (diff, sınıflama, drug-hit, loading-dose golden fixture, rapor render)
- [x] Phase 1: gerçek data çalıştırıldı → A=23, REVIEW=10, B=125 (`reports/agent/reimbursement/tier1-triage-2026-08-06.md`, gitignored)
- [x] Phase 2: analiz tamam — 33 A/REVIEW vakası 3 paralel subagent ile incelendi → 12 RE-ENCODE, 21 KEEP, 0 DELETE; karar belgesi `plans/update/2026-08-06-tier1-phase2-decisions.md`
- [x] Phase 2: Safa onayı (2026-08-06)
- [x] Phase 3: 12 RE-ENCODE uygulandı (YAML kaynaklar → compile), golden sabitler bilinçli güncellendi, skorlayıcı iyileştirildi (A=23→5); PR açıldı
- [x] Phase 4: TIER-2 örnekleme — 37 vaka, 0/37 gürültü, politika belgesi `plans/update/2026-08-06-tier2-phase4-policy.md`
- [x] Phase 4 uygulama: 4 re-point + siklosporin re-encode + 2 silme (T2 687→674) — PR #57
- [ ] Phase 5: TIER-4 dangling sınıflama (154 ref: tipo vs extractor açığı)
- [ ] Açık PR'leri kapat: #55 (copilot docs follow-up), #57 (T2 burn-down) — §11 review kontrolüyle
- [ ] Phase 6 (opsiyonel): T1 count CI uyarısı

---

## Task: 01.07.2026 SUT clause corpus güncellemesi (Branch B) — BEKLEMEDE

Plan: `plans/update/2026-08-07-sut-clause-corpus-update-plan.md`.
Triage planı bitmeden başlanmayacak (Safa kararı 2026-08-07).
- [ ] Phase 6 (opsiyonel): T1 count CI uyarısı

### Out of Scope
- TIER-3 (intentionally low-priority)
- Reporter'ı gate'e çevirmek
- TIER-2/TIER-4 toplu düzeltmesi (sadece örnekleme + politika)

---

## Task: Track E — Stable clause identity (coordinate + content-hash)

### Goal
Pozisyonel `clause_id` (C*) kırılganlığını bitirip Branch B corpus update'i güvenli/otomatik yapmak. Plan: `plans/update/2026-08-07-stable-clause-identity-track-e-plan.md`.

### Subtasks
- [x] Phase 0: C* envanteri + collision + baseline — `plans/update/2026-08-07-track-e-phase0-audit.md` (load-bearing ~2930; 82 özdeş-collision; composite key yetersiz, content-hash yeterli)
- [x] Phase 1: `normalize_for_hash` + `content_hash` + `clause_key` (`clause_identity.py`) + golden fixture kilidi + 11 unit test (C006549 loading-dose dahil)
- [x] Phase 2: extractor `add_identity_columns`/`backfill_identity_columns` + parquet backfill (23.05 docx raw'da olmadığı için rejener yerine kolon backfill; içerik byte-identical, clause_id değişmedi; `clause_key` NaN-safe)
- [x] Phase 3: resolver dual-read (`coordinate#hash` çözer, mismatch fail-loud) + lossless migration scripti.
- [x] Phase 3b: builder tutarlılığı + data migrasyonu — 843 cite→clause_key (lossless), encoded_clause_ids tutarlı C*, 0 sızıntı, tam suite pre-existing baseline'da (24F/2416P).
- [ ] Phase 4: C* public contract'tan kaldır (Track E exit)
- [ ] Phase 5: Branch B'yi bağla — 01.07 re-extract + corpus update otomasyonu
- [ ] Phase 6: doğrulama (re-extract stabilite testi, stale reporter önce/sonra)

### Out of Scope
- Fatura F* kimlik sistemi (D5, ayrı epic)
- Yeni prose kural yazımı
- Coordinate hiyerarşi zenginleştirme (content-hash yeterli)

### Review
- Phase 1: 31 test geçti (test_clause_identity), ruff temiz; tam pytest 24F(pre-existing)/2410P/20S

---

## Task: Branch B otomasyonu — 3 paket (Safa onayı 2026-08-08)

### Goal
`sut-monitor.yml` Branch B (docx → clause corpus) otomatik güncellemesini güvenli çalışır hale getirmek. Paket 1: authored C* yüzeyini kapat (re-extract artık hiçbir referansı sessizce kaydıramaz). Paket 2: 01.07 docx re-extract'i elle doğrula (asıl bilinmeyen: extractor yeni docx'te çalışıyor mu + copay 50/90/100 hizalaması). Paket 3: stabilite testiyle otomasyonu bağla. Detaylı plan: `plans/update/2026-08-08-branch-b-automation-3-packet-plan.md`. Bu task, `2026-08-07-sut-clause-corpus-update-plan.md`'deki BEKLEMEDE gate'ini kaldırır.

### Subtasks

#### Paket 1 — Referans yüzeyini kapat (ölçüm revizyonu 2026-08-08)

**Ölçüm sonucu:** gate_b_sources'taki 235 C* ref'in 192'si prose/amendment (encode-eligible değil → Track A3 gereği mecburen C*), 43'ü eligible ama hepsi özdeş-kopya (lossless değil). **Taşınabilir ref = 0** — 1.1 maddesi İPTAL, mevcut durum zaten güvenli. Asıl iş diğer authored yüzeylerde.

- [x] 1.2 — **wave_config + sections + stub taşıması** (asıl iş):
  - [x] `gate_b_wave_config.py` (199 C* → 184 taşındı: coord#hash; 15 istisna kalır: 13 prose + 2 özdeş bent); isim `DRUG_INDICATION_WAVE_CLAUSE_IDS` → `_KEYS`; `_stage_csv_wave_clause_ids` resolver ile C*'ye geri çözüyor → manifest byte-identical
  - [x] `gate_b_sections.py` (74 C* → 44 taşındı: coord#hash; 30 kalır: 14 not-in-force + 16 non-eligible); engine `_ref_hit(clause_id, clause_key, refs)` ile hem C* hem coord#hash eşleşiyor (gate_b_generic.py)
  - [x] `_PAYMENT_SESSION_MANIFEST_STUB` (7 C* → 6 taşındı, C000661 prose kalır); `encoded_clause_keys` alanı + `_write_payment_session_manifest` resolver → byte-identical
  - [x] `clause_type_overrides.yaml` (15 C*, hepsi prose) → belgeli istisna, taşınmaz
- [x] 1.3 — **deferral_table rekey**: clause_id C* → coord#hash (847/1541 taşındı, kayıpsız; 694 istisna: non-eligible + not-in-force + özdeş). `load_deferral_table` coord#hash'i C*'ye çözüyor — 1541/1541 çözüldü, kayıp 0. `clause_coordinate` alanı hiçbir tüketicide kullanılmıyordu (sadece status/defer_themes) → güvenli
- [x] 1.4 — istisna envanteri + "artamaz" testi: `tests/unit/scripts/test_authored_cstar_inventory.py` — 5 yüzey toplam 975 C* kilitli (rule_sources 235, deferral 694, sections 30, wave 15, stub 1) + parquet'te varlık guard'ı
- [x] 1.5 — CI ölçüm testi: `test_eligible_cstars_are_identical_duplicates_only` — eligible kalan C*'lerin hepsi özdeş-kopya (85 kilitli), lossless keylenebilir olanlar 0 (kaçırılmış migrasyon yakalanır)
- [x] 1.7 — **YENİ: C* parquet'te yoksa → compile hatası** (`clause_identity.py` UnknownClauseCiteError; 1757 üretim kuralı doğrulandı, 2 yeni unit test)
- [x] 1.6 — `.github/workflows/ci.yml` `fetch-depth: 1` dahil edildi
- [x] 1.8 — Doğrulama: `compile_rules --check` 136/136 byte-identical; scripts suite 501 passed; tam suite 2434 passed / 14 pre-existing API auth kırığı (BILUN_AUTH env eksik — d1c05f4'te de fail, alan dışı); ruff temiz

#### Paket 2 — 01.07 docx manuel re-extract (orta risk)
- [ ] Yeni branch (`chore/sut-0107-clause-corpus`) aç; `extract_sut_prose.py`'yi 01.07 docx ile koş (ilk kez deneniyor; 2026-06-19 dersi: dependency gap'leri burada çıkar)
- [ ] Doğrula: `source_effective_date=2026-07-01`; clause sayısı delta'sı makul; copay 1.8.1 in-force = 50/90/100 (şu an bayat 26/60)
- [ ] Downstream rejenere: coverage parquet'leri, `compile_rules`, manifestler; `sut_clause_diff.py` eski/yeni diff çıkar
- [ ] Tam pytest triage: kırıkları sınıfla — bilinçli değişim (yeni key'ler, taşınan hükümler) vs gerçek kırık; golden sabitler YALNIZCA re-audit sonrası güncellenir
- [ ] Paket 1'deki 54 istisna ref'in triage ile doğrulanması (strike→in-force elenenler temizlenir, gerçek kopyalar kalır)
- [ ] `stale_clause_refs.py` + `triage_stale_refs.py` önce/sonra tablosu (T1/T2/T4)

#### Paket 3 — Otomasyonu bağla (düşük risk)
- [ ] Re-extract stabilite testi: aynı docx iki kez extract → tüm `clause_key` byte-identical (Phase 6)
- [ ] `sut-monitor.yml` Branch B adımı (`extract_sut_prose` + `sut_clause_diff.py`) scheduled run için güvenlik kontrolü; human-gated PR kalır
- [ ] PR body'sinde `clause_diff_summary` + `delta_summary` render doğrulaması

### Out of Scope
- 82 özdeş-collision grubunun kök-neden temizliği (dedupe / hiyerarşik koordinat makinesi — ölçüm + fail-loud yeterli)
- Fatura `F*` kimlik sistemi (D5)
- Branch A re-ingest (zaten güncel)
- Yeni prose kural yazımı

### Review
- **Paket 1 tamamlandı (2026-08-08):** 943→975 C* toplam envanter (ölçüm revizyonuyla yeni yüzeyler dahil) envanter testiyle kilitlendi. wave 184, sections 44, stub 6, deferral 847 ref coord#hash'e taşındı — hepsi lossless (`resolve == [cid]` şartıyla, özdeşler C* kaldı). Manifest üretimi resolver ile C*'ye geri çözüyor → 136 artifact byte-identical. Engine artık `_ref_hit` ile hem C* hem coord#hash kabul ediyor. 1.7: parquet'te olmayan C* → UnknownClauseCiteError (eski hoşgörü kapatıldı). 14 API auth kırığı pre-existing (BILUN_AUTH env, d1c05f4'te de fail) — alan dışı, Paket 2 başlamadan önce CI'da secrets ile yeşil olduğu doğrulanacak.
- **Ölçüm revizyonu 2026-08-08:** 1.1 (181 ref migrasyonu) ölçümle çürüdü — 235 C* ref: 192 prose/amendment (Track A3 gereği C* kalmalı, coord#hash compile'da NonEncodeEligibleCiteError verir — test edildi) + 43 eligible özdeş-kopya (lossless değil). Taşınabilir=0, durum zaten güvenli. Asıl yüzey: wave_config 184, sections 50→44 (section_heading'ler non-eligible çıktı), stub 6. Deferral rekey coord'a değil coord#hash'e (1004/1541 ambiguous). Manifest encoded_clause_ids hâlâ saf C* — resolver katmanı manifest'leri değiştirmeden kaynağı temizliyor (dual-write yerine resolve-back tercih edildi; byte-identical kanıtı daha güçlü).
