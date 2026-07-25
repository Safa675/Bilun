## Task: SUT pipeline god plan (simplify encode identity + SoT)

### Goal
Execute `plans/billing/sut-pipeline-god-plan.md`: SUT-native paragraph identity (`clause_coordinate`), single authored truth (YAML + deferral), derived manifests/coverage, thin compile.

### Decisions (locked 2026-07-25)
- [x] D1 Full simplification
- [x] D2 Phased `C*` removal (coordinates when unique; `C*` for collisions)
- [x] D3 Non-drug Gate B = Track F last
- [x] D4 Encode-eligible universe only

### Subtasks
- [x] Draft + approve god plan
- [x] Track A0: uniqueness audit (`plans/billing/sut-pipeline-a0-uniqueness-audit.md`)
- [x] Track A1 foundation: `clause_identity.py` dual-read + schema + gate_b_generic resolve + tests
- [x] Coverage dual-read via `clause_identity` (`coverage.py` + tests)
- [x] Deferral table accepts optional `clause_coordinate` keys (resolve → clause_id)
- [x] Track A3: compile write path asserts resolvable cites (`assert_gate_b_sources_resolvable`)
- [x] Track A2 pilot: migrate `definitions_2_6` unique cites (56/70) + recompile
- [x] Track A2 bulk: migrate remaining families (1128 cites) + recompile fresh targets
- [x] Update tests for dual-read (manifest invariants, treatment provenance, 4218 tier-A)
- [x] Track B1: YAML-only — retire SOURCE_PATCHES/DROPS stages (no-op + empty modules)
- [x] Track B2: move coverage reclassify set → deferral_table `non_actionable`
- [x] Track B3: derive provenance goldens; delete pure-provenance golden JSON
- [ ] Track C: canonical manifest + thin compile + coverage + drop corpus CSV + retire shims
- [ ] Track D: UI/docs audit UX on coordinates
- [ ] Track E: delete/demote public `C*`
- [ ] Track F (optional): non-drug Gate B onto generic

### Out of Scope
- Evaluator clinical matching rewrites
- LLM bulk extraction as the simplification strategy
- Fatura `F*` merge into SUT ids

### Review
- Branch / PR: `refactor/sut-pipeline-god-plan` → https://github.com/Safa675/Bilun/pull/43
- A0: 357 encode-eligible coordinate collisions — keep `C*` for those
- A2 pilot: definitions_2_6 YAML/JSON/golden/manifest now use coordinates where unique
- Migrate tool: `python -m scripts.sut.prose.migrate_gate_b_sources_to_coordinates --family …`
