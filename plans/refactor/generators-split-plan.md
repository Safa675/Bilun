# Plan: Refactor `scripts/synthetic/generators.py` (3,046 lines → 6 modules)

## Goal
Split the 3,046-line monolith into focused modules under `scripts/synthetic/gen/`,
each <500 lines, with **zero behavior change** — the regenerated cohort and all
tests must be byte-identical to today. This is a pure structure change: no logic
edits, no spec changes, no data changes. Done = `build_workbook_tables()` produces
the same output and `pytest tests/unit` + the synthetic validator pass unchanged.

## Why (the actual problem this solves)
1. **Token cost.** This file is re-read in nearly every billing/prose session.
   At 3,046 lines (~25k tokens per full read), it is the single largest
   per-session input-token drain in the project. Splitting means future edits
   read only the relevant module (~2–5k tokens), not the whole monolith.
2. **Cognitive load / bug surface.** Two functions exceed 250 lines
   (`_generate_claims_and_lines` = 491, `_inject_medula_anchor_line` = 250).
   Both are where the recent false-positive + cache-crash bugs lived. Smaller
   modules make targeted reads + targeted tests possible.
3. **Merge-conflict magnet.** Every billing change touches this one file.

## Current structure (verified, line spans exact)
```
Line     Lines  Section
1–44     44     imports + helpers
45–323   279    SPEC DICTS: _DRUG_INDICATION_DEMO_SPECS, _CLAIM_READINESS_DEMO_SPECS, _MEDULA_DEMO_SPECS
324–423  100    utility fns: _icd10_in_range, _diagnosis_matches_ek1a, _generate_patients
424–686  263    _assign_scenarios (MEGA)
687–930  244    _pick_procedures + 11 _pick_*_demo_procedures (12 pick fns total)
931–1228 298    more _pick_* variants + _lookup_ek2b_price
1229–1517 289   MATERIAL_PROSE_FLAG_COLUMNS, SPECIALTY_PROSE_FLAG_COLUMNS, _default_*_flags, _ensure_*_flag_coverage
1518–1685 168   _reconcile_claim_header_totals, _inject_specialty_keyword_demo_rows, _ensure_ek2c1_*
1686–1946 261   ProcedureClaimLine assembly + _append_procedure_lines_for_claim (MEGA)
1947–2127 181   _append_material_*  + _append_drug_lines_for_claim
2128–2377 250   _inject_medula_anchor_line (MEGA)
2378–2868 491   _generate_claims_and_lines (MEGA — the orchestrator)
2869–2942 74    _generate_prescriptions, _generate_lab_results
2943–3046 104   build_workbook_tables (the public entry point)
```

## Target module structure
`scripts/synthetic/gen/__init__.py` re-exports the names tests/validator import.
`generators.py` becomes a **shim** that re-exports the same set, so existing
flat `from generators import ...` call sites (validator, tests, generate script)
keep working unchanged.

**Import convention:** the `synthetic/` directory uses flat `sys.path`-based
imports (`from generators import …`), NOT package-relative. Internal `gen/`
modules use **relative imports** (`from .specs import …`) — consistent within
the package. The shim is the only flat-import surface; mixing styles inside
`gen/` causes circular imports, so pick relative and document it.

```
gen/
  __init__.py            (~30 lines)  re-export build_workbook_tables + the 5 shim names
  specs.py               (~300 lines) _DRUG_INDICATION_DEMO_SPECS, _CLAIM_READINESS_DEMO_SPECS, _MEDULA_DEMO_SPECS
  patients.py            (~400 lines) _generate_patients, _assign_scenarios (263), _drg_group, ICD helpers
  procedures.py          (~550 lines) _pick_procedures + 11 _pick_*_demo_procedures + _lookup_ek2b_price
  claim_lines.py         (~500 lines) ClaimEpisodeContext, _append_*_lines_for_claim, _procedure_row_as_claim_line
  materials_flags.py     (~300 lines) MATERIAL/SPECIALTY_PROSE_FLAG_COLUMNS, _default/sample flags, _ensure_*_flag_coverage
                                       (depends ONLY on the flag tuples — NOT on the drug/MEDULA spec dicts)
  medula_anchor.py       (~280 lines) _inject_medula_anchor_line + the MEDULA-specific anchor logic
  reconcile.py           (~200 lines) _reconcile_claim_header_totals, _ensure_ek2c1_*, _inject_specialty_keyword_demo_rows
  orchestrate.py         (~520 lines) _generate_claims_and_lines (491 alone — moved as-is; slimming is follow-up)
  ancillary.py           (~150 lines) _generate_prescriptions, _generate_lab_results
  workbook.py            (~150 lines) build_workbook_tables + assembly glue
generators.py            (~25 lines)  SHIM: re-exports the full set (below)
```
Each module <600 lines. Note `orchestrate.py` is ~520 (the orchestrator alone
is 491) — acceptable; decomposing it is an explicit follow-up, not this pass.

## Refactor strategy (the safe part)
**This is a pure move/refactor, NOT a rewrite.** Every function moves verbatim.
No signatures change. No logic changes. The contract is: same bytes out.

- [ ] **Phase 0 — freeze the baseline.** Capture a golden oracle: per-sheet
      **row counts** + a **per-column hash** over all data columns, **excluding
      `olusturulma_zamani` and `generated_at`** (wall-clock timestamps that make
      byte-identity impossible — `generators.py:3006`, `cohort_tiers.py:80`).
      This is the regression oracle — the refactored version must reproduce it.
- [ ] **Phase 1 — extract leaf modules with no internal deps first** (lowest risk):
      - `specs.py` (3 dicts, depends on nothing but `Any`)
      - `materials_flags.py` (depends on specs for the flag lists)
      - `ancillary.py` (prescriptions + lab_results — self-contained)
- [ ] **Phase 2 — extract the mid-layer** (depend on Phase 1):
      - `patients.py`, `procedures.py` (depend on specs + helpers)
      - `reconcile.py` (totals/ekc1 — depends on nothing below it)
- [ ] **Phase 3 — extract the line-builders + medula** (depend on Phase 1+2):
      - `claim_lines.py` (ClaimEpisodeContext + the 3 _append_* functions)
      - `medula_anchor.py` (_inject_medula_anchor_line)
- [ ] **Phase 4 — extract the orchestrator last** (depends on everything):
      - `orchestrate.py` (_generate_claims_and_lines, slimmed)
      - `workbook.py` (build_workbook_tables)
- [ ] **Phase 5 — replace generators.py with a shim.** The shim must re-export
      **every name** that tests/validator import from `generators` (verified by
      grepping the call sites):
      ```python
      # generators.py — back-compat shim (deprecated; call sites migrate later)
      from gen.workbook import build_workbook_tables
      from gen.claim_lines import ClaimEpisodeContext
      from gen.materials_flags import MATERIAL_PROSE_FLAG_COLUMNS, SPECIALTY_PROSE_FLAG_COLUMNS
      from gen.specs import _CLAIM_READINESS_DEMO_SPECS, _MEDULA_DEMO_SPECS
      ```
      Missing any of these causes an ImportError in the validator/tests at run
      time — the explicit list prevents a half-done shim. (Internal gen/ modules
      use relative imports: `from .specs import …`.)

## Verification (done = ALL pass)
- [ ] **Row-count + column-hash oracle (NOT byte-identity).** The workbook
      contains wall-clock timestamps that make byte-identity impossible:
      `olusturulma_zamani` (`generators.py:3006`) and `generated_at`
      (`cohort_tiers.py:80`) both use `datetime.now(UTC)`. The oracle must:
      - Compare **row counts per sheet** (all tables except the manifest).
      - Compare a **per-column hash** over all data columns.
      - **Exclude** `olusturulma_zamani` and `generated_at` from the hash.
      - **Normalize dtypes before hashing** — verified during execution that
        Excel round-trip introduces representation differences that are NOT
        data changes: `1.0`↔`True` (Excel stores bools as floats), `'612'`↔
        `'0612'` (leading-zero codes), `0.33`↔`0.3299999...` (float display),
        `nan`↔`''` (empty cells). The oracle must normalize booleans to a
        canonical form and strip trailing `.0` from numeric codes, or it will
        false-fail on ~159 cells that are semantically identical. (Aligns with
        the older `synthetic-data-v2-refactor.md` convention. Freezing time in
        tests is a separate task, out of scope here.)
- [ ] `python scripts/synthetic/generate_sut_synthetic_data_v2.py` succeeds.
- [ ] `python scripts/synthetic/validate_sut_synthetic_data.py` passes
      (unchanged — including the false-positive applicability guards we added).
- [ ] `python scripts/synthetic/assert_tier_a_post_regen.py` passes.
- [ ] `pytest tests/unit -q` is green. (Tie to the *command*, not a test count —
      the count moves as the suite grows.)

## Out of scope (explicit)
- **No logic changes.** If a function is ugly but works, it moves verbatim.
  Cleaning up internal logic is a separate, riskier task — do it AFTER the
  split is proven byte-identical, one function at a time, with the golden
  fixture catching regressions.
- **No decomposing the 4 mega-functions in this pass.** `_generate_claims_and_lines`
  (491 lines) and `_inject_medula_anchor_line` (250) move as-is into their own
  modules. Breaking them into sub-functions is valuable but doubles the risk;
  capture as a follow-up under the new module structure.
- **No test additions.** Existing tests + the golden fixture are the guard.
  New unit tests per module is a follow-up.
- **No updating the import call sites** (validator/tests/generate script) — the
  shim keeps them working. Switching them to the new paths is a later cleanup.

## Risk + rollback
- **Risk:** low *if* the golden oracle (row-count + column-hash, timestamps
  excluded) is enforced at every phase. A bad move shows up immediately as a
  count or hash diff. Note: full byte-identity is impossible due to the
  wall-clock timestamps — the oracle deliberately excludes them, so a "pass"
  means data is identical, not bytes.
- **Rollback:** each phase is one commit; revert the commit to undo. The shim
  means a partial refactor (some modules extracted, some not) still works.
- **Do NOT regenerate the committed data during this refactor.** The point is
  to prove the code produces the SAME data. Regenerating mid-refactor obscures
  whether a diff is a bug or expected.

## Token-cost note
After this refactor, a billing/prose session that needs to edit
`_inject_medula_anchor_line` reads `medula_anchor.py` (~280 lines / ~2.3k
tokens) instead of the whole monolith (~25k tokens) — roughly a **10x reduction
on that read**, repeated across every future session. This is the concrete
payoff for the token-burn concern.
