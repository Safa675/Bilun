Plan
Plan: Architectural simplification — pipeline from ~29K to ~10K SLOC
Goal
Eliminate the accidental complexity (duplicate gate_b modules, redundant manifest representations, dead metadata fields, brittle literal tests) while preserving the irreducible logic (extractor, evaluator, rule data, deferral taxonomy). Target: ~10,000 SLOC from ~29,000.

Architecture target

```
SUT docx → extractor → sut_clauses.parquet
                         ↓
Rules (YAML) → compile → rule JSONs → evaluator (runtime, reads ONLY rule JSONs)
                         ↓
              derive manifest (ONE canonical schema, from rules + deferral table)
                         ↓
              derive coverage (from manifest + parquet)
```
Key principle: one source of truth (rules), everything else derived. No independently-maintained representations.

The hard constraint (must preserve)
The deferral taxonomy — emr_blocked / tier_c_deferred clause sets with their defer_themes / defer_reason — is human-encoded clinical judgment that exists nowhere else. It must survive as a first-class data structure (a deferral_table.yaml keyed by clause_id), not buried inside manifest clause_traces.

## Phase 1 — Consolidate 14 gate_b modules into 1 generic (biggest win, safest)
Eliminates: ~4,500 lines of duplicate code.

The 14 per-section drug_indication_*_gate_b.py modules are ~90% identical boilerplate. The only genuine variation is _encode_tier_for_clause (tier-A/B/C classification), which comes in two shapes:

1. Token-list promotions (data-drivable: {section: [drug_tokens]})
2. Hardcoded clause-ID overrides (must stay as lookup tables: {clause_id: tier})

Implementation:
- Create `scripts/sut/prose/gate_b_generic.py` with:
  - `export_candidates(clauses_path, section_prefixes, keywords, *, tier_fn, sort_keys)` — generic parquet filter + enrich
  - `build_manifest(frame, rules, section_id, *, tier_fn, clause_overrides)` — generic manifest builder
  - `write_artifacts(frame, manifest, corpus_csv, manifest_path, *, reconcile=True)` — generic writer
  - `classify_tier(text, section_id, clause_id, *, base_tier_fn, token_promotions, clause_overrides, force_c_sections)` — injectable tier classifier
- Create `scripts/sut/prose/gate_b_sections.py` — a config table of `GateBSection` dataclasses
- The 2 bespoke modules (4210 inversion, 4235_4237 force-defer) are handled by flags (`demote_a_to_c`, `force_c_sections`) in the config
- The 3 audit/repair suites (4201, 4210, 4213) collapse into ONE generic `audit_gap_parity(clauses_path, manifest)` + `repair_untraced(manifest)`
- Deduplicate `_normalize_tr` (currently copied into 15+ files) into the shared module
- NOT consolidated: the 3 non-drug modules (payment_method, material_bundling, copay_exemption)

Verification: compile_rules.py --check passes; all gate_b tests pass; output byte-identical.

## Phase 2 — Unify manifest schema (collapse 18 shapes → 1)
Eliminates: the multi-representation drift bug class permanently.

The canonical manifest schema:
```json
{
  "manifest_version": "canonical-v1",
  "rule_set_id": "...",
  "section_id": "...",
  "section_clause_total": 22,
  "encoded_clause_ids": [...],
  "tier_c_deferred_clause_ids": [...],
  "emr_blocked_clause_ids": [...],
  "non_actionable_clause_ids": [...],
  "tier_a_pending_clause_ids": [...],
  "tier_b_pending_clause_ids": [...],
  "clause_traces": [
    {"clause_id": "...", "manifest_status": "encoded|tier_c_deferred|emr_blocked|non_actionable", "encode_tier": "A|B|C", "defer_themes": [...], "defer_reason": "..."}
  ]
}
```

Eliminated fields (no runtime reader): gate_b_sources_encoded, gate_b_sources_by_rule, gate_b_summary, inn_named_*, tier_c_defer_themes_summary, rules_added_*, batch_clause_ids, scope_note, manifest_coverage_pct, encoded_clause_pct.

## Phase 3 — Extract deferral taxonomy as first-class data
Moves human judgment out of manifests into a reviewable `data/gazette/prose_rules/deferral_table.yaml`.

## Phase 4 — Eliminate corpus CSVs as runtime artifacts
Replace rules_catalog.py corpus-row-count reads with parquet-derived counts.

## Phase 5 — Property-based test assertions
Replace hardcoded literal counts with derived assertions.

**DONE 2026-07-25** (expanded): see `plans/refactor/brittle-test-remediation-plan.md`. Shared helpers in `tests/unit/_helpers/brittle_guards.py`; gate_b / rule-set / synthetic / API census locks softened to derived/`>=`/invariant assertions. Pre-existing: `test_manifest_derivation_invariants.py`.

## Phase 6 — Simplify coverage derivation
Reduces coverage.py from ~500 lines to ~200.

## Phase 7 — Delete dead code + final sign-off

Execution order: 1 → 2 → 3 → (4,5,6 independent) → 7.

Out of scope: evaluator matching logic, extractor docx parsing, 3 non-drug gate_b modules, commit/push.
