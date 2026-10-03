# Actual SMA and antifungal observations

This additive slice extends the approved renal observer to the existing SMA and antifungal evaluators. It adds no clinical inputs, eligibility thresholds or payment conclusions. The optional leaf observer preserves the exact original clinical result and check list. The actual shared dispatch creates request-local collectors and carries bounded summaries through the existing clinical evidence, canonical/public and V2/cache contracts.

The original 52 authored bindings in `reports/sut-expansion/sma-antifungal-runtime-bindings.json` map comparison identities to exact source references and boolean, enum or numeric units. This is a binding inventory, not an executed-patient count. Every binding has `clause_predicate_complete=false`; the runtime complete-clause mapping remains absent.

- SMA observes only the medication/type-specific comparisons actually reached. Type1/newborn and risdiplam bypasses emit skipped-route receipts; missing type blocks only the lumbar branch. Source/date gates observe no history comparisons.
- Antifungal eager alternatives retain every reached comparison, including false alternatives when another route succeeds. A repeated fact supports multiple predicates but counts once as an observed/missing input fact.
- The micafungin post-neutropenic period uses the actually computed date difference in days. Missing/future end dates block that comparison. The expected-duration restriction is skipped when an allowed population route succeeds; no source3 count is inferred from the broad family source list.
- Itraconazole's unresolved cells/ml versus cells/mm3 authority emits a source block. No ANC comparison or conversion is invented, even when an ANC/mm3 value was supplied.
- Unused supplied fields are not counted as observed. Branch/source/input blocks are separate from predicate attempts. Atomic false comparisons are not billing violations. Clinical eligibility remains incomplete.

The private scope nonce never leaves the request and does not affect the deterministic summary digest. Source IDs require the existing active normative source gate; no arbitrary prose exception is added. Other families remain uninstrumented until their real hooks and caller wiring are added.

Original observer verification:260 focused clinical, receipt, public and V2 tests pass, including12 named/anonymous HTTP cases repeated twice.2400 deterministic cases (1200 SMA and1200 antifungal) exactly match frozen D61 clinical outputs, with and without observations, and all summaries validate. Curated executed paths verify all52 bindings. Ruff passes. This is not a complete hosted CI claim.

Parent is the exact approved renal runtime-v3 packet over D61. Later clinical-family changes require an additive merge of clinical.py; the frozen clinical chain must not be overwritten. GH leaf observations are a separate follow-on integration.


## Original85 documentary completion amendment

The current binding inventory has 61 authored bindings: the original 52 plus two itraconazole prophylaxis facts and seven risdiplam Type-1 documentary facts. All nine execute through the real observed reader, retaining `clause_predicate_complete=false`. This is bounded necessary-fact coverage, never a complete-clause or payment conclusion.

Itraconazole oral-solution prophylaxis separately checks expected development of neutropenia and the deep-fungal-infection-prophylaxis indication. Current neutropenia, expected duration, and posaconazole's prolonged-neutropenia fact cannot substitute. The literal `<500 hücre/ml` source unit remains unresolved; supplied ANC/mm³ is never compared or converted.

Risdiplam Type-1 checks documented monitoring and assessment in the motor, cognitive, nutritional, respiratory, rehabilitation and orthopedic domains, plus health-board-report documentation. Each boolean means both monitoring and assessment are documented in that domain. These source-specific checks do not establish adequacy, cadence or undefined age/disease standards; the latter remain an explicit source-review blocker. Missing subtype is unknown; Type-2/3/newborn pathways, nusinersen and gene therapy do not inherit this Type-1 source row.

The identical monitoring paragraph under the preceding nusinersen heading is not interchangeable. Exact reference `4.2.49.A.(2)#481b9b26@within:4.2.49.A#c2df3999` resolves to original85 clause C007119. Baseline parquet paragraph 7412, captured October extraction paragraph 7437, and physical October DOCX paragraph 7365 are distinct index systems. Original DOCX bytes and run-level evidence are recorded in `data/gazette/source_evidence/sma_antifungal_documentary_facts.json`.


### Treatment-period gate and evaluator version

The documentary obligation explicitly says “Tedavi süresince.” Type-1 risdiplam documentary comparisons therefore require the strict `risdiplam_treatment_period=during_treatment` fact. `not_started` skips these seven comparisons; a missing, malformed or unsupported period yields an applicability review without comparing the documentary facts. An initiation label is never inferred to mean treatment is already in progress. Existing safety predicates remain independent. The source-standard review still applies whenever the documentary branch is reached.

The live SMA and antifungal collectors now use `sma.atomic.v2.2026-10-03` and `antifungal.atomic.v2.2026-10-03`. Renal and GH versions are unchanged. This distinguishes the expanded executed-binding/gating contracts in private receipt identity and deterministic summary digests without expanding public metadata.
