# Plan: Fix Documentation After Fact-Check

## Goal
Update all 12 docs in `docs/` to reflect the current codebase structure, correct factual errors, remove unverifiable claims, and fix broken references.

---

## Subtasks

### Phase 1 — Global Path Rewrite (affects ~7 docs)
- [ ] Replace all `src/sut/` → `src/bilun/domain/` throughout docs/
- [ ] Replace all `src/api/schemas/sut.py` → `src/bilun/api/schemas.py`
- [ ] Replace all `src/analytics_cache/` → `src/bilun/cache/`
- [ ] Replace all `src/pipeline/` → `src/bilun/cache/`

### Phase 2 — sut.md (most errors)
- [ ] Fix: "60 exports" → "0 exports (package intentionally does not re-export)"
- [ ] Fix: API prefix `/api/sut/` → `/api/` on all 11 listed endpoints
- [ ] Fix: endpoint count "18" at line 29 → actual SUT endpoint count
- [ ] Fix: EK-3 row count ~4,667 → 3,265
- [ ] Fix: "444 gazette source documents" → "444 manifest entries (393 unique source files)"
- [ ] Remove or mark unverifiable: 91.6% phantom flag rate (192,919/210,606) — no code in repo
- [ ] Remove or mark unverifiable: 14,110-code price audit — no code in repo
- [ ] Fix path reference: `src/sut/constants.py:56-85` → `src/bilun/domain/constants.py`
- [ ] Fix path reference: `src/sut/__init__.py` → `src/bilun/domain/__init__.py`
- [ ] Fix path reference: `src/sut/billing/__init__.py` → `src/bilun/domain/billing/__init__.py`

### Phase 3 — gazette.md
- [ ] Fix: "117,285 total rows" → 115,568
- [ ] Fix: "4,407+ materials" → 3,265 materials
- [ ] Fix: "27 specialty catalogs" → clarify actual count (30 files, 22 non-empty, 8 empty)

### Phase 4 — algorithms_reference.md
- [ ] Fix: HEMOGRAM_TESTS "~20" → 13 entries
- [ ] Fix: Lab 3-tier lookup description to match actual implementation (L-code detection → gazette dict → lowercase fallback)
- [ ] Update path references throughout (already covered by Phase 1)

### Phase 5 — Decision Docs (2026-05-04, 2026-05-05, 2026-05-10)
- [ ] 2026-05-04: Remove or update reference to `plans/sut-synthetic-data-creation-plan-2026-05-04.md` (does not exist)
- [ ] 2026-05-04: Fix filename `sentetik_sut_5_hasta.xlsx` → `sentetik_sut_v2_50_hasta.xlsx`
- [ ] 2026-05-05: Remove or update reference to `plans/sut-dead-legacy-approximation-removal-plan-2026-05-04.md` (does not exist)
- [ ] 2026-05-05: Remove or update reference to `plans/sut-synthetic-demo-production-mode-plan-2026-05-05.md` (does not exist)
- [ ] 2026-05-10: Remove or update reference to `scripts/start_split_app.sh` (does not exist — behavior is in `src/bilun/domain/claims/config.py`)
- [ ] 2026-05-10: Update env var names: `SUT_DATA_MODE`/`SUT_CLAIMS_DIR` → `BILUN_DATA_MODE`/`BILUN_CLAIMS_DIR`
- [ ] 2026-05-10: Mark "272,663 patients" claim as unverifiable
- [ ] 2026-05-10: Mark "5 synthetic patient payload rows" verification claim — actual is 50 patients

### Phase 6 — External Docs
- [ ] olive-ai-post-mortem.md: Fix or remove broken `[[ilay-demo-readiness-audit]]` link (page does not exist)
- [ ] olive-ai-post-mortem.md: Fix or remove broken `[[ilay-wedge-strategy]]` link (page does not exist)
- [ ] olive-ai-post-mortem.md: Remove `[[ibm-watson-health-failure]]` reference if it also doesn't exist

### Phase 7 — Verify
- [ ] Run `grep -r "src/sut/" docs/` — should return zero hits
- [ ] Run `grep -r "src/api/" docs/` — should return zero hits (unless correct `src/bilun/api/`)
- [ ] Run `grep -r "src/pipeline/" docs/` — should return zero hits
- [ ] Run `grep -r "src/analytics_cache/" docs/` — should return zero hits
- [ ] Spot-check 3 docs for remaining issues

---

## Out of Scope
- Creating the missing plan files (`sut-synthetic-data-creation-plan`, `sut-dead-legacy-approximation-removal-plan`, `sut-synthetic-demo-production-mode-plan`)
- Creating missing wiki pages (`ilay-demo-readiness-audit`, `ilay-wedge-strategy`)
- Adding actual code for the unverifiable claims (91.6% flag rate analysis, 14,110-code audit)
- Renaming the synthetic data file from 50 to 5 patients
- Fixing empty EK-3 curated parquet files (data issue, not doc issue)
