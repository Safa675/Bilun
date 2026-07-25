## Task: PR #43 merge gate — make safe to merge

### Goal
PR https://github.com/Safa675/Bilun/pull/43 is CI-green with real (a)-class bugs fixed so it is safe to merge (cleanup PR waits until then).

### Subtasks
- [x] Fix `stale_clause_refs.classify_refs` Polars C*/F* join dropping `clause_id` (false TIER 4 + md TypeError)
- [x] Restore `_normalize_tr` on material Gate B facade (export scripts ImportError)
- [x] Dual-read test helper: coordinate cites compare cleanly to opaque `encoded_clause_ids`
- [x] Update brittle assertions still expecting C*-only `gate_b_sources` / removed `tier_c_defer_themes_summary`
- [x] Fix Clause/Deferral browser React keys + deep-links to prefer unique `clause_id`
- [x] Restore `compile_rules.py --check` parity (regenerate artifacts)
- [x] Cache coverage encoded-id loaders (pipeline_smoke / build_sut_coverage perf)
- [x] Locally re-run previously failing tests + compile --check
- [ ] Push fix commit; watch CI green
- [ ] Review section: merge-safe verdict (CI + reviews + remaining process blockers)

### Out of Scope
- Dead-code cleanup PR
- Wiping collision YAML C* / deleting parquet `clause_id`
- Fatura F* (D5)
- Extractor collision fixes (A0)
- Merging the PR (needs human approving review per branch protection)

### Review
- **Not merge-safe before this fix:** CI red (33 failed / 4 errors); `stale_clause_refs` false TIER 4; material facade ImportError; coverage build hung (~minutes) from uncached dual-read; React keys used colliding coordinates.
- **Local after fix:** previously failing set green; `pipeline_smoke --limit 3` ~11s; `compile_rules --check` ok.
- **Still needed for merge:** push + CI green + 1 approving review (`REVIEW_REQUIRED`).
