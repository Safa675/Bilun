## Task: Track F — Non-drug Gate B onto generic

### Goal
Port payment_method / material_bundling / copay_exemption onto `gate_b_generic` + canonical manifests with the same coordinate identity rules as drug Gate B. Exit: no bespoke drug-vs-nondrug Gate B architecture stories.

### Subtasks
- [x] Scout current non-drug gate_b modules vs generic + compile wiring
- [x] Port payment_method onto GateBSection + generic build_manifest
- [x] Port material_bundling onto GateBSection + generic build_manifest
- [x] Port copay_exemption onto GateBSection + generic build_manifest
- [x] Retire/thin bespoke writers; update compile_rules targets
- [x] Same coordinate / dual-read / encode-eligible rules as drug path
- [x] Tests + mark god-plan F; Review

### Out of Scope
- Deleting parquet `clause_id` / wiping collision YAML C*
- Fatura F* (D5)
- Extractor collision fixes (A0)
- New clinical rule content
- specialty_materials / anti_vegf bespoke stages (not in Track F list)

### Review
- Branch / PR: `refactor/sut-pipeline-god-plan` → https://github.com/Safa675/Bilun/pull/43
- Sections: `payment_22`, `material_31_32`, `copay_18` in `ALL_SECTIONS`
- Compile targets all use `write_gate_b_artifacts`
- Legacy modules kept as thin facades for import compatibility
- Manifests: canonical-v1 + `encoded_clause_coordinates` + family extras
- Tests: payment / material / copay Gate B green (17)
