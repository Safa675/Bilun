## Task: Track C slice B — Coverage one function + retire shims (C3 + C5)

### Goal
Coverage derives from parquet + rule JSON + deferral only; delete §4.2.14.C-only side tools once generic covers them; retire `gate_b_shim` and dead exports so `gate_b*.py` is generic + sections + audit.

### Decisions (locked)
- [x] Stay on PR #43 / branch `refactor/sut-pipeline-god-plan`
- [x] Slice A committed (`ad97020`)
- [x] Non-drug ports remain Track F
- [x] Keep phase5 `a1`/`drug_indication_manifest` until §4.2.14.C GateBSection port
- [x] Drug encoded supplement list stays explicit (not full glob) to avoid gap-count drift

### Subtasks

#### C3 — Coverage = one function
- [x] Single `_clause_has_rule_encoding` predicate
- [x] Move `build_defer_reason` → `gate_b_generic` (re-exported from manifest module)
- [x] Delete unused dead manifest path constants
- [x] Delete `drug_indication_a0_inventory` + test
- [ ] Port §4.2.14.C onto `GateBSection` / delete a1 (deferred — high risk)
- [ ] Polars end-to-end enrich (deferred)

#### C5 — Retire shims
- [x] Extend `gate_b_generic.write_artifacts` (batch_rules / manifest_path / write_corpus)
- [x] Compile + tests call generic / `ALL_SECTIONS` directly
- [x] Delete `gate_b_shim.py`
- [x] Delete `anti_vegf_4233_export.py`

### Out of Scope
- Track D/E, Track F non-drug Gate B port
- Full §4.2.14.C generic port (follow-up)
- `plans/deployment/vps-openhands-smoke-test.md`

### Review
- Branch / PR: `refactor/sut-pipeline-god-plan` → https://github.com/Safa675/Bilun/pull/43
- Baseline gaps: 222 / encoded 1994 / di gaps 63 (pin before C3)
- Verified: 123 gate_b + schema tests pass after shim deletion
