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
- [ ] Phase 4: TIER-2 örnekleme (~30 ref) + politika kararı
- [ ] Phase 5: TIER-4 dangling sınıflama
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
- [ ] Phase 2: extractor + parquet'a `content_hash`/`clause_key` kolonu
- [ ] Phase 3: resolver dual-read + load-bearing C* migrate (gate_b → deferral → config)
- [ ] Phase 4: C* public contract'tan kaldır (Track E exit)
- [ ] Phase 5: Branch B'yi bağla — 01.07 re-extract + corpus update otomasyonu
- [ ] Phase 6: doğrulama (re-extract stabilite testi, stale reporter önce/sonra)

### Out of Scope
- Fatura F* kimlik sistemi (D5, ayrı epic)
- Yeni prose kural yazımı
- Coordinate hiyerarşi zenginleştirme (content-hash yeterli)

### Review
- Phase 1: 31 test geçti (test_clause_identity), ruff temiz; tam pytest 24F(pre-existing)/2410P/20S
