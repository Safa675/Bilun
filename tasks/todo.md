## Task: Fix MATERIAL crosswalk substring collisions + correct audit report

### Goal
The EK-3 catalog is CORRECT (verified end-to-end). The real bug is in the
Phases 1-5 frozen crosswalk: ~42 MATERIAL mappings are wrong because
`build_material_candidates` over-matches on generic device words (`seti`,
`kateter`, `strip`, `bandi`). Fix the resolver scoring, re-resolve & re-freeze
the affected mappings, and correct the audit report's false "EK-3 catalog
broken" claim.

### Diagnosis (verified 2026-07-16)
42/175 (24%) of material mappings have hospital item billed <5% of SUT ceiling.
Root cause = 3 compounding bugs in `code_resolver.py:build_material_candidates`:
- **B1 (line 643):** `if df.get(t,1) > 1` excludes rare query tokens from the
  denominator → a single shared common word (`seti`) divides by itself → score 1.0.
- **B2 (line 652-654):** rare-token bonus `min(score+0.3, 1.0)` clamps
  single-shared-token collisions to a perfect 1.0.
- **B3 (line 130):** generic device words (`seti/set/kateter/strip/bandi/sistem`)
  are NOT stopwords → high-DF tokens that should be near-meaningless.

### Subtasks
- [ ] **F1** Fix `build_material_candidates`:
  - [ ] F1a denominator: include ALL query tokens (drop the `> 1` exclusion)
  - [ ] F1b rare-token bonus: gate on shared_idf/query_idf >= 0.5 before +0.3
  - [ ] F1c material stopwords: add generic device words to a material-only set
- [ ] **F2** Verify resolver: before/after on the 4 known-bad pairs (must now NO_MATCH or pick correct code)
- [ ] **F3** Re-resolve the 42 wrong hospital codes; update `hospital_to_sut.csv`
  (set wrong rows to sut_code="" unresolvable, or remap if a correct candidate exists)
- [ ] **F4** Re-run `finans_pricing_audit.py`; confirm EK-3 numbers are sane
- [ ] **F5** Correct audit report + script comments: EK-3 catalog is correct; bug was crosswalk
- [ ] **F6** Run full test suite (code_resolver tests) to confirm no regressions
- [ ] **F7** Commit on finans-coder

### Key files
- `src/bilun/domain/coding/code_resolver.py:602-667` (build_material_candidates)
- `src/bilun/domain/coding/code_resolver.py:123-138` (_meaningful_tokens stopword set)
- `data/coding/hospital_to_sut.csv` (frozen crosswalk — 42 rows to fix)
- `scripts/analysis/finans_pricing_audit.py` (correct the report comment)

### Out of scope
- EK-4A retail-price audit (still needs TİTCK)
- Re-resolving DRUG/LAB/PROCEDURE categories (only MATERIAL is affected)
- The EK-2B inpatient-panel overcharge finding (separate, valid)

### Definition of done
- 4 known-bad pairs (AE0900/KN1069/KN1122/AN1070) no longer match on the generic word
- EK-3 audit "UNDERCHARGE" count drops substantially (most were crosswalk artifacts)
- Audit report states the corrected finding (crosswalk bug, not catalog bug)
- code_resolver tests green

### Review — Completed (2026-07-16)
- **Root cause reversed:** the EK-3 catalog is CORRECT (verified end-to-end: curated
  == raw parquet == SGK gov XLSX, no collisions/parsing/unit bugs). KN1069 = intrathecal
  baclofen pump *system kit* (103K is realistic), not a catheter. The prior "⚠️ EK-3 not
  trustworthy" warning was my own misread of a truncated display name.
- **Real bug:** `build_material_candidates` over-matched on generic device words.
  3 compounding defects fixed in `code_resolver.py`:
  - denominator excluded rare query tokens (`df>1`) → single shared common word hit 1.0
  - rare-token bonus clamped single-token collisions to 1.0
  - generic words (seti/kateter/strip/bandi) were not stopwords
- **Fix:** denominator now uses `df>=1` (excludes only catalog-absent tokens like SKU
  codes); rare-token bonus gated on base score ≥0.5; added `_MATERIAL_STOPWORDS`.
- **Crosswalk:** removed 26 wrong MATERIAL rows from `hospital_to_sut.csv` (conservative
  rule: generator no longer reproduces AND price ratio <5%). Golden case (OR1160 Foley)
  preserved. NOTE: CSV is gitignored/derived — the durable fix is the resolver change;
  re-running merge_phase4 would regenerate a corrected table.
- **Audit improvement:** EK-3 UNDERCHARGE 1,343 → 347 real + 496 VOIDED_LINE (new flag
  for billed-0 lines). EK-2B UNDERCHARGE 77→23 (+76 voided separated). Suspected-wrong-
  mappings 50→22 codes. Report finding #3 corrected.
- **Tests:** 52/52 coding tests pass. 1 smoke test fails but is PRE-EXISTING (401 auth
  issue, fails identically with my change reverted) — not a regression.

### Lessons (→ tasks/lessons.md)
- Verify a "bad data" claim's premise before reporting it: I called the EK-3 catalog
  broken based on reading a TRUNCATED display name ("İNTRATEKAL KAT…"). The full name
  was "...VE SABİT SALIMLI İNFÜZYON POMPASI" (a pump kit). Truncated ≠ truth.
- IDF-overlap scoring that excludes rare query tokens from the denominator lets a single
  common word divide by itself → false 1.0 matches. Denominator must use all (or
  catalog-present) query tokens.
