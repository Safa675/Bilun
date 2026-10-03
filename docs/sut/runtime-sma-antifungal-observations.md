# Actual SMA and antifungal observations

This additive slice extends the approved renal observer to the existing SMA and antifungal evaluators. It adds no clinical inputs, eligibility thresholds or payment conclusions. The optional leaf observer preserves the exact original clinical result and check list. The actual shared dispatch creates request-local collectors and carries bounded summaries through the existing clinical evidence, canonical/public and V2/cache contracts.

The 52 authored bindings in `reports/sut-expansion/sma-antifungal-runtime-bindings.json` map comparison identities to exact source references and boolean, enum or numeric units. This is a binding inventory, not an executed-patient count. Every binding has `clause_predicate_complete=false`; the runtime complete-clause mapping remains absent.

- SMA observes only the medication/type-specific comparisons actually reached. Type1/newborn and risdiplam bypasses emit skipped-route receipts; missing type blocks only the lumbar branch. Source/date gates observe no history comparisons.
- Antifungal eager alternatives retain every reached comparison, including false alternatives when another route succeeds. A repeated fact supports multiple predicates but counts once as an observed/missing input fact.
- The micafungin post-neutropenic period uses the actually computed date difference in days. Missing/future end dates block that comparison. The expected-duration restriction is skipped when an allowed population route succeeds; no source3 count is inferred from the broad family source list.
- Itraconazole's unresolved cells/ml versus cells/mm3 authority emits a source block. No ANC comparison or conversion is invented, even when an ANC/mm3 value was supplied.
- Unused supplied fields are not counted as observed. Branch/source/input blocks are separate from predicate attempts. Atomic false comparisons are not billing violations. Clinical eligibility remains incomplete.

The private scope nonce never leaves the request and does not affect the deterministic summary digest. Source IDs require the existing active normative source gate; no arbitrary prose exception is added. Other families remain uninstrumented until their real hooks and caller wiring are added.

Verification:260 focused clinical, receipt, public and V2 tests pass, including12 named/anonymous HTTP cases repeated twice.2400 deterministic cases (1200 SMA and1200 antifungal) exactly match frozen D61 clinical outputs, with and without observations, and all summaries validate. Curated executed paths verify all52 bindings. Ruff passes. This is not a complete hosted CI claim.

Parent is the exact approved renal runtime-v3 packet over D61. Later clinical-family changes require an additive merge of clinical.py; the frozen clinical chain must not be overwritten. GH leaf observations are a separate follow-on integration.
