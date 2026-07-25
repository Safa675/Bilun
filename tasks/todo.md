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
- [ ] Track A2: migrate authored YAML/deferral refs to coordinates where unique
- [ ] Track A3: wire loud ambiguity into compile `--check` end-to-end
- [ ] Track B: YAML-only + deferral SoT + goldens policy
- [ ] Track C: canonical manifest + thin compile + coverage + drop corpus CSV + retire shims
- [ ] Track D: UI/docs audit UX on coordinates
- [ ] Track E: delete/demote public `C*`
- [ ] Track F (optional): non-drug Gate B onto generic

### Out of Scope
- Evaluator clinical matching rewrites
- LLM bulk extraction as the simplification strategy
- Fatura `F*` merge into SUT ids

### Review
- Branch: `refactor/sut-pipeline-god-plan`
- A0 finding: 357 encode-eligible coordinate collisions — dual-read must fail loud
