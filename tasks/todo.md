## Task: L3.1 §2.2.2.B session fractions (2026-06-11)

### Goal
Close L3.1-hemo PARTIAL gap: apply §2.2.2.A(5) session point factors per lab encounter in normative costing and compliance flags.

### Subtasks
- [x] Refactor `lab.py`: per-encounter code list → `compute_session_point_factors`
- [x] `LabOptimization.session_fraction_savings` + `total_savings` rollup
- [x] Unit tests (single visit, cross-visit, hemogram+labs combo)
- [x] Frontend: combined savings display + `session_fraction_overbilling` label
- [x] Update L3.1 doc + FIX_BACKLOG; run tests

### Review
- L3.1-hemo verdict: COMPLIANT (was PARTIAL on §2.2.2.B gap).
- `same_incision=True` default for same-visit labs (§2.2.2.A(5) 30% secondary).
- 5/5 `test_lab_session_fractions.py` pass.

### Out of Scope
- Claim-line billed amount comparison (lab path has test names only)
- `cross_specialty` auto-detect (no specialty on lab lists)
- `same_incision=False` param (default True until kesi metadata)

---

## Task: L2.4 EK-2C-1 polish (2026-06-11)

### Goal
Close L2.4 polish: synthetic reconcile, demo-scoped violations, package-line exclusion, i18n, cache.

### Subtasks
- [x] Synthetic: normalized EK-2C-1 keys + `_reconcile_ek2c1_procedure_lines` + 3 demo violations
- [x] `copay_rate_evaluable_line` — skip package-included / zero-billed from rate checks
- [x] EN/TR i18n: "copay rate" / "katılım payı oranı" (not "add-on rate" / "ilave oran")
- [x] Update `L2.4_copay_rate_ek2c1.md`
- [x] Regenerate synthetic; tests pass; rebuild cache

### Review
- Synthetic: ≤2 rate + ≤1 flag demo violations; SGK share >100% = 0.
- Package-included EK-2C-1 lines excluded via `copay_rate_evaluable_line`.
- Cache rebuilt: `6c5e8030-805a-443c-9f69-5d19576149a2`.

---

## Task: L4.4 specialty §3.3 prose — finish integration (2026-06-11)

### Goal
Close L4.4 Phase 2: synthetic claim flags, coverage scope, UI surfacing, golden tests, registry sync.

### Subtasks
- [x] `specialty_coverage_scope.py` + `MaterialPreCheck.specialty_coverage_scope`
- [x] Synthetic: L4.4 flag columns + coverage + keyword demo rows (generators/exporters/validate)
- [x] Orchestrator action counts + `claim_materials` rule_source + chat context
- [x] Frontend: `specialty_prose_violations` + scope notice (EN/TR)
- [x] Golden tests + `test_sut_coverage` + synthetic flag tests
- [x] Registry `specialty_materials_prose` → implemented; update L4.4 plan
- [x] Regenerate synthetic parquets; run tests

### Review
- 49 §3.3 rules wired end-to-end: validate_claim, precheck, synthetic flags (37 claim fields), UI table + scope notice.
- Runtime wiring: validation API + ClaimValidator/BundledConsumables scope notices; cache rebuilt (`6bff5ee5`).
- Synthetic reconcile fix: L4.4 demo rows update claim header + expected outputs.
- Patient `SENTETIK-HASTA-0001`: exact materials precheck, **5** specialty violations; **17/50** patients flagged.

### Out of Scope
- L4.4 Phase 4 catalog alignment (code-first EK-3 price lookup)
- Full §3.3 long-tail encode beyond existing 49 rules
