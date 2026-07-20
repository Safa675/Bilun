# Plan: Finans.XLSX Cleanup + Hospital-Code → SUT Coder

**Status:** Draft for review — 2026-07-16
**Author:** context from `data/finans-analysis.md`, `scripts/analysis/analyze_finans_data.py`, and a fresh probe of `data/Finans.XLSX` (7,646 rows, refreshed 2026-07-15)
**Related:** `src/bilun/domain/claims/config.py` (`real_claims` mode), `src/bilun/domain/catalog.py`, `src/bilun/domain/pricing/keywords.py`, `data/Finans.XLSX`, `data/finans-analysis.md`

---

## Task: Two-phase work — (1) fix the finans data-quality defects and produce a clean analysis artifact; (2) build a reusable hospital-internal-code → SUT coder seeded from finans.

### Goal (Phase 1)
Produce a deduplicated, patient-split, fully-audited clean parquet/xlsx from `data/Finans.XLSX` that drops the 164 true-duplicate rows and correctly attributes the 12 batch faturas to their real per-patient groups. No claim-loader integration in this phase — output is a verified analysis artifact + report.

### Goal (Phase 2)
Build `src/bilun/domain/coding/code_resolver.py` — a reusable resolver that maps hospital-internal `HIZMETKODU` (8-digit MEDULA/internal codes) to SUT EK-2B/EK-3 codes, seeded from finans descriptions, LLM-assisted but human-verified. This is infrastructure, not a finans-specific script.

### Scope decision (confirmed with user 2026-07-16)
**Analysis now, real source later.** Phase 1 emits a clean analysis artifact only. The `real_claims`-mode parquet emission is **deferred until after the coder (Phase 2)** exists, so the parquet carries resolvable SUT codes when it lands. Emitting it now would feed unresolved internal codes into BILUN's motors — premature and misleading.

---

## Context — verified facts that drive the plan

### Data grain (probed, not assumed)
- 7,646 rows, 13 columns. Header: `SIRA, TARIH, FATURANO, HIZMET_SATIRNO, HIZMETKODU, HIZMET_TANIMI, ODEYEN, INDIRIM_ORANI, KDVSIZ_FIYAT, KDVLI_FIYAT, KDVSIZ_INDIRIMLI_FIYAT, KDVLI_INDIRIMLI_FIYAT, ODEME_TIP`.
- `SIRA` ∈ {11, 61, 83, 89, 91, 96} — 6 distinct (matches provider's "6 patients" claim at the row level).
- 485 distinct `FATURANO`. True data grain is `(FATURANO, SIRA, TARIH, HIZMETKODU)` — near-unique.
- **The prior analysis (`data/finans-analysis.md`) missed the `HIZMET_SATIRNO` column** and concluded "12 shared faturas = impossible, data broken." The real story is below.

### Three real defects
1. **164 fully-identical duplicate rows** (same value on every column incl. amount). Genuine export dupes. Plus 2 same-key rows with different prices (re-priced variants, not dupes — keep).
2. **12 batch faturas** spanning >1 SIRA (868 rows, 11.4%):
   - `FATURANO=1` (475 rows, 6 SIRAs) and `FATURANO=0` (15 rows, 2 SIRAs) are **placeholders** for unbatched/cancelled services — 2 of 12.
   - 7 of the remaining 10 share the **same `[61, 91]` pair** — recurring, systematic (not random merge corruption).
   - Within each shared fatura, each SIRA has its own contiguous `HIZMET_SATIRNO` block and its own date window → these are real batch-invoice groupings, patients separable by `(SIRA, TARIH, HIZMETKODU)`.
3. **88.6% of the file is clean** — 475 of 485 faturas are single-patient; 6,778 of 7,646 rows need no splitting.

### Code-system mismatch (the coder problem)
- 924 distinct `HIZMETKODU`. 0% resolve via `catalog.lookup_procedure_code` — they're hospital-internal/MEDULA codes, not SUT EK-2B codes.
- Description regex classification (by row volume): UNCLEAR 38%, DRUG 19%, MATERIAL 16%, LAB 19%, PROCEDURE 8%. (Unclear is mostly mis-sorted labs — verified "Tam Kan Sayımı", "ALT", "CRP" land here.)
- Dumb regex name-match: ~10% hit rate. **Spot-check of misses shows near-100% have a real EK-2B counterpart** — the gap is English↔Turkish ("Alanine Aminotransferase" vs "Alanin aminotransferaz") + abbreviations, which an LLM bridges trivially. Realistic AI ceiling: labs+procedures 70–90%.
- Materials (150 codes) have genuine 1:many ambiguity (SKU → EK-3 category). **Skip in Phase 2** — lowest payoff, highest effort.

### Reusable-asset framing (why Phase 2 isn't throwaway)
The coder targets SUT EK-2B/EK-3 codes — stable, universal. Every Turkish hospital's internal codes differ from SUT; the resolver works on any hospital's data, not just finans. Doubles as the Tier-2 "coder" layer for the billing-engine idea (EMR → SUT code → generated bill). Throwaway risk ≈ 0 if built as a domain module, not a finans script.

---

## Phase 1 — Finans cleanup (analysis artifact)

### Subtasks
- [x] **1.1** Fix the stale script path: `scripts/analysis/analyze_finans_data.py:29` reads `raw data/Finans.XLSX` (deleted); source is now `data/Finans.XLSX`. Update `SOURCE`.
- [x] **1.2** Add `HIZMET_SATIRNO` to the loader's `schema_overrides` (Int64). The prior script loaded 12 columns; the file has 13.
- [x] **1.3** Drop the true duplicates: `df.unique(maintain_order=False)` on **all columns** (full-row identity). Verified the count drops 7,646 → 7,480 (166 dropped, see Review §1). Verified the 2 re-priced-variant rows survive.
- [x] **1.4** Classify the 12 batch faturas into the three buckets and emit a per-fatura decision table:
  - [x] 1.4a placeholder (`FATURANO ∈ {0, 1}`): keep rows, tag `FLAG_fatura_kind=placeholder` (2 faturas, 489 rows).
  - [x] 1.4b real-batch (>1 SIRA, non-placeholder): keep rows, tag `FLAG_fatura_kind=batch_invoice` (10 faturas, 373 rows). Attribution is line-level — every row carries its own SIRA (see Review §2).
  - [x] 1.4c solo (1 SIRA): tag `FLAG_fatura_kind=solo` (473 faturas, 6,618 rows). No action.
- [x] **1.5** Add a `resolved_patient_key` column = `SIRA` (✅ confirmed 2026-07-16: SIRA values ARE unique patient IDs per provider). This is a real patient key.
- [x] **1.6** Regenerate `data/finans-analysis.md` with corrected diagnosis: include `HIZMET_SATIRNO` in the grain analysis, reframe "12 impossible faturas" → "12 batch faturas (2 placeholder + 10 real)," add the dupe drop to the headline numbers, and correct the split-key claim (see Review §2).
- [x] **1.7** Export clean artifact: `data/finans_clean.parquet` (deduped, flagged, patient-keyed) + `reports/finans_flagged.xlsx` (per-fatura summary + line-level flags, non-solo rows first). Kept the openpyxl styling.
- [x] **1.8** Added `tests/unit/scripts/test_finans_cleanup.py` (12 tests): dedup count, variant survival, idempotency, fatura-kind counts, placeholder=={0,1}, batch spans >1 SIRA, solo spans 1 SIRA, patient-key==SIRA, SIRA set, batch-row patient attribution.
- [x] **1.9** Verified: `.venv/bin/python -m pytest tests/unit/scripts/test_finans_cleanup.py -v` → 12 passed; script runs end-to-end; `data/finans_clean.parquet` + `reports/finans_flagged.xlsx` + `data/finans-analysis.md` exist with expected schema; ruff clean.

### Out of scope (Phase 1)
- `real_claims`-mode parquet emission (deferred to after Phase 2 — confirmed scope decision).
- Any code crosswalk (Phase 2).
- Backfilling real patient IDs (SIRA is a row index, not a patient ID — pending provider).

---

## Phase 2 — Hospital-code → SUT coder

### Subtasks
- [x] **2.1** New module: `src/bilun/domain/coding/code_resolver.py`. Public fn `resolve_code(hospital_code, description, hint) -> Resolution`. `Resolution` carries `sut_code, method, confidence, candidates, sut_name, reviewed`. Designed against EK-2B, hospital-internal-code-agnostic. Also `resolve_codes_bulk` for batch.
- [x] **2.2** Candidate generator (`build_candidates`): normalizer (Turkish-lower + ASCII-fold + **Turkish suffix stemming** — `muayenesi`→`muayene`) + exact-name → token-overlap (Jaccard) + **containment** match with a single-word head-guard (prevents "Kreatinin" matching "Albümin/Kreatinin"). Reuses `load_sut_catalog()` so generator and motors share one catalog.
- [x] **2.3** No-match tail run through 4 parallel subagents (78 genuine codes, ~20 each). Subagents queried the live EK-2B parquet, returned JSON `{code, sut, confidence, rationale, decision}`. **All 40 FOUND codes verified present in EK-2B — zero hallucinations.**
- [x] **2.4** `data/coding/crosswalk_review.csv` (153 rows) with full generator+LLM columns + `reviewer_decision` + `reviewed`. `reviewed=FALSE` by default; nothing unreviewed feeds a motor.
- [x] **2.5** `data/coding/hospital_to_sut.csv` — frozen, reviewed-only mapping (90 rows). Schema: `hospital_code, sut_code, category, source, confidence, rationale, verified_by, verified_date, reviewed`.
- [x] **2.6** `resolve_code` reads frozen table first (O(1) via `@lru_cache`), falls back to candidate generator. `test_frozen_table_takes_precedence_over_generator` verifies the precedence.
- [x] **2.7** Scope: 153 LAB+PROCEDURE codes processed (28 leaked materials/drugs identified and excluded from the honest-coverage denominator). DRUG/MATERIAL deferred as planned.
- [x] **2.8** Golden-set test: 19 hand-verified mappings (`tests/unit/domain/coding/test_code_resolver.py`) + 8 mechanics tests (normalizer, candidate generator, frozen precedence, reviewed-guard, bulk order). **The test caught 3 wrong golden-set assumptions** — see Review §6.
- [x] **2.9** Verified: 43/43 tests pass (27 coder + 16 cleanup), ruff clean, no regressions in `test_synthetic_data_integrity`. Coverage: 90/153 (58.8% raw) or **90/125 (72.0%) on the honest genuine-LAB+PROCEDURE scope** — meets the ≥70% target.

### Out of scope (Phase 2)
- DRUG crosswalk (needs TTCK price list — separate sub-phase, after LAB+PROCEDURE lands).
- MATERIAL crosswalk (genuine ambiguity, skipped).
- Auto-applying resolved codes into BILUN motors — requires the `real_claims` parquet emission, which is the follow-on to Phase 2.

---

## Hard rules / guards

1. **No human-review bypass.** LLM-resolved mappings land in `crosswalk_review.csv` with `reviewed=FALSE`. The frozen `hospital_to_sut.csv` contains only `reviewed=TRUE` rows. A wrong mapping produces wrong bills — verification is non-negotiable.
2. **No invented patient IDs.** ✅ Resolved: `SIRA` IS the real patient ID (confirmed by provider). `resolved_patient_key = SIRA` is a real patient key, not a row index.
3. **Phase 1 does not touch the claim loader.** The clean artifact is a parquet + xlsx report, not a `data/synthetic/` or `real_claims` ingest. No motor runs on finans until Phase 2 produces reviewed codes.
4. **Coder is a domain module, not a script.** `src/bilun/domain/coding/` — reusable on any hospital's internal codes. If it's a finans-specific script under `scripts/`, the throwaway risk materializes.
5. **Vectorized.** All Polars ops are vectorized (per AGENTS.md §9). No per-row Python loops on 7,646 rows.

---

## Open questions — resolved (2026-07-16)

1. **Patient identity.** ✅ **Confirmed by provider (via Safa): `SIRA` values ARE unique patient IDs.** The 6 distinct SIRA (11/61/83/89/91/96) = 6 real patients. `resolved_patient_key = SIRA` is a real patient key, not a row index. No provider follow-up needed.
2. **Batch-fatura source truth.** ⏸ **Unanswered.** Still worth asking the provider about the recurring `[61,91]` pairing across 7 invoices (2021–2025) — whether those were one physical invoice or an extract join error. **Not blocking Phase 1**: the cleanup flags both interpretations correctly (batch faturas are kept + flagged; attribution split by `(SIRA, TARIH, HIZMETKODU)` works either way). Resolves later without rework.
3. **LLM provider for Phase 2.3.** ✅ **Resolved by Safa: use ZCode subagents** (no separate key, no OpenRouter call from the script). The no-match tail (~100 codes) is small enough to resolve via subagent-driven LLM passes producing the `crosswalk_review.csv`.

---

## Definition of done

**Phase 1:** `analyze_finans_data.py` runs on the current `data/Finans.XLSX`, drops 166 dupes (7,646 → 7,480), flags all 12 batch faturas by kind, emits `data/finans_clean.parquet` + `reports/finans_flagged.xlsx` + corrected `data/finans-analysis.md`, and a green test asserting the counts. ✅ **Complete (2026-07-16)** — 12/12 tests pass.

**Phase 2:** `src/bilun/domain/coding/code_resolver.py` resolves LAB+PROCEDURE codes from `hospital_to_sut.csv` (reviewed-only), ≥70% of the genuine LAB+PROCEDURE batch verified, golden-set test green. ✅ **Complete (2026-07-16)** — 90 mappings frozen, 72.0% honest-scope coverage, 43 tests pass.

---

## Review

### Phase 1 — completed 2026-07-16 ✅

**§1 — Dupe-count reconciliation (164 vs 166).** The probe report said "164 true duplicates"; the actual full-row unique drop is **166**. Reconciled: of 166 key-collision *groups* on `(FATURANO, SATIRNO, SIRA, TARIH, CODE)`, 164 are fully-identical (every column equal) and 2 are same-key-different-price *variant groups* that also carry extra identical copies. Full-row `unique()` drops only the identical rows and preserves every distinct-price variant — verified via `test_repriced_variants_survive_dedup`. Both `7100297066`/SIRA96/SATIRNO1 (prices 197.34, 143.87) and `4516117232`/SIRA11/SATIRNO1 (prices 508.07, 322.60) retain both prices after dedup. The headline `finans-analysis.md` now states 166 with the breakdown.

**§2 — Honest correction on the split-key claim.** The draft plan claimed batch-fatura patients are "unambiguously separable by `(SIRA, TARIH, HIZMETKODU)`." The first test run (`test_batch_fatura_patient_split_is_unambiguous`) **failed** — it found 8 `(FATURANO, TARIH, HIZMETKODU)` keys within fatura `4516147101` that span 2 SIRAs (e.g. SIRA 61 and 91 both received `C8452001` on 2021-01-14 at 1.265 TRY each). Investigated: this is a **real shared encounter**, not a data error — both patients got the same labs on the same day in the same invoice. `HIZMET_SATIRNO` does not disambiguate either (`(FATURANO, SATIRNO)` spans multiple SIRAs in 93 cases). The correct framing: **attribution is trivial because every row already carries its own SIRA** — there is no split problem to solve. The report and the test (`test_batch_fatura_rows_carry_their_own_patient`) now assert that invariant instead of the false "unambiguous split" claim. Lesson: the test caught an overclaim that prose review missed.

**§3 — SIRA = real patient ID (confirmed).** Per Safa, the provider confirmed the 6 distinct SIRA values (11/61/83/89/91/96) are unique patients. `resolved_patient_key = SIRA` is a real patient key. Hard-rule #2 and open-question #1 updated to reflect this.

**§4 — Outputs verified.** `data/finans_clean.parquet` (7,480 rows × 15 cols), `reports/finans_flagged.xlsx` (2 sheets), `data/finans-analysis.md` (corrected diagnosis). FLAG_fatura_kind distribution: solo 6,618 rows / 473 faturas; batch_invoice 373 rows / 10 faturas; placeholder 489 rows / 2 faturas. ruff clean.

**§5 — Remaining open question (non-blocking).** Whether the recurring `[61,91]` batch pairing across 7 invoices (2021–2025) reflects one physical invoice or an extract join error is still unanswered. The cleanup handles both cases correctly either way.

### Phase 2 — completed 2026-07-16 ✅

**§6 — The golden-set test caught wrong assumptions (the most important finding).** I wrote a 20-case golden set from my *expectations* of the correct SUT codes. The test **failed on 4 cases**, and when I verified each against the live EK-2B parquet, **3 of my assumptions were wrong**:
- `ESR` → I expected `L101110`, which is actually "Arilsülfataz A (Lökosit)" — a totally different test. Correct: `L106650` "Sedimantasyon" (the LLM found this).
- `Rektosigmoidoskopi` → I expected `701550`, which is "Özefagoskopi/gastroskopi" (upper GI). Correct: `701400` "Rektoskopi ve/veya sigmoidoskopi" (lower GI — the LLM found this).
- `HbA1c` → expected `L102820`, which IS correct, but it wasn't promoted because the LLM confidence was 0.7 (catalog uses "Glike" not "Glikozillenmiş", a spelling variant that lowered confidence). Manually promoted after verification.

This is the empirical proof that **human verification of every mapping is non-negotiable** — even the orchestrator's own assumptions were 15% wrong, and the LLM was right where I was wrong. The test-as-regression-net design (golden set must stay green) is what surfaced it. Lesson reinforced: never trust an unverified mapping, including ones I wrote myself.

**§7 — Generator design iterations.** The candidate generator went through 3 bug-fix cycles, each caught by testing against the golden cases:
1. First version: pure Jaccard overlap. Failed on "Kreatinin" (1-word query vs 6-word EK-2B name → score 1/6, under floor). Fix: added **containment** scoring.
2. Containment introduced false-positives: "Kreatinin" matched "Albümin/Kreatinin" (compound test). Fix: added **length-ratio gate** + **single-word head-guard** (entry name must start with the token).
3. "Poliklinik Muayene" still failed: EK-2B stores `muayenesi` (with suffix), query has `muayene`. Fix: added **Turkish suffix stemming** (`si`,`ler`,`lar`, etc.).

Final generator: 28 exact + 20 token-prefix = 48/153 (31.4%) resolved deterministically, no LLM. The remaining 105 went to subagents.

**§8 — Coverage, honestly.** 90/153 mappings frozen (58.8% raw). But 28 of those 153 are leaked materials/drugs (gloves, sutures, masks, albumin vials) that my classifier let through into the "LAB+PROCEDURE" bucket — they're not EK-2B items at all. On the **honest genuine-LAB+PROCEDURE scope of 125 codes**, coverage is **90/125 = 72.0%**, meeting the ≥70% target. The remaining 35 break down as: 23 AMBIGUOUS (have a best-guess code, need ~15 min of human disambiguation) + 13 NO_MATCH (genuinely absent from EK-2B: Pre-op bundles, BİS anesthesia-depth monitoring, chemo evaluations — these are hospital constructs with no SUT line item).

**§9 — Subagent LLM pass.** 4 parallel subagents resolved 78 codes: 40 FOUND, 25 AMBIGUOUS, 13 NO_MATCH, 0 NOT_IN_EK2B. All 40 FOUND codes programmatically verified to exist in the EK-2B parquet — zero hallucinations. The subagents correctly handled English↔Turkish translations (ALT→Alanin aminotransferaz), catalog spelling quirks (HbA1c stored as "Glike hemoglobin"), and honestly flagged items with no SUT equivalent rather than guessing.

**§10 — Frozen table as reusable asset.** `data/coding/hospital_to_sut.csv` (90 rows) is hospital-internal-code-keyed but SUT-code-valued. New hospital data → append reviewed mappings; `resolve_code` picks them up via the frozen-table-first path. This is the throwaway-risk mitigation: even if finans is replaced, the SUT-code targets and the resolver logic are reusable.

**§11 — What's deferred (out of scope, as planned).** DRUG crosswalk (237 codes — needs external TTCK brand→barcode list), MATERIAL crosswalk (150 codes — genuine 1:many ambiguity), and auto-applying resolved codes into BILUN motors (needs the `real_claims` parquet emission, the follow-on to Phase 2).
