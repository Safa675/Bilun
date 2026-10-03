# SMA source-scoped routing review packet

Base: 04878812b87a82392e64671e8edce46c48cfaebe. Snapshot: bilun-sut-d-recovered.

## Changed files
- data/gazette/prose_rule_sources/drug_indication/4.2.49.A.yaml
- data/gazette/prose_rule_sources/drug_indication/4.2.49.B.yaml
- data/gazette/prose_rules/drug_indication_prose.json (11 SMA rows only)
- scripts/sut/prose/clause_identity.py (heading-scoped reference resolver)
- tests/unit/domain/prose_rules/test_drug_indication_4249_source_scope.py

## Source and meaning
SGK current consolidated extraction, publication 2026-10-02; replacement RG 26/04/2025-32882/7, effective 2025-05-06. The containing subsection is essential because identical prose has identical coordinates/content hashes across medications. Exact heading keys: 4.2.49.A#f57da6c0 (A.1 nusinersen); 4.2.49.A#c2df3999 (A.2 risdiplam); 4.2.49.B#1a8f10e4 (B.1 nusinersen); 4.2.49.B#58c3e3be (B.2 risdiplam). Corresponding current paragraph indices: 7425, 7433, 7439, 7449.

The former A.2 coverage/monitoring duplicates wrongly selected nusinersen. The former B.1 coverage/monitoring/CSF/lumbar rows wrongly selected risdiplam. Correct IDs now name the subsection's medicine, and old identifiers are recorded in supersedes_rule_ids. Gate-B evidence now encodes child-key@within:heading-key; the actual shared resolver enforces the containing heading boundary. source_heading_key remains readable metadata. All modified rules explicitly carry ai_generated_pending_review.

This is source attribution and candidate selection repair. It adds zero executable clinical predicates and must not be counted as eight clinical gaps closed. Existing all-criteria and multidisciplinary-monitoring action text remains non-executable. source_effective_date is provenance only; historical clinical applicability is not newly established by this batch. No monetary approval is introduced.

## Verification
- 14 new source/selector tests passed before marking provenance status.
- 81 source-selector/real-resolver/public-evaluation regressions pass; one DOCX-dependent test skips because the local raw data folder is absent.
- Full tests/ attempted: collection blocked by absent raw data directory and requests, 3 errors. No tests were changed to hide those blockers.
- Source YAML and generated JSON exact equality is asserted by the new suite; schema validation is included.
- Compiler --check shows the same six manifest differences on pristine main and D with Python3.13; these are baseline/materialization differences, not hidden scoped passes.
- Resolver regressions cover every SMA rule, source order reversal/index shifts, malformed or missing heading context, and attempts to attach nusinersen-only evidence to a risdiplam heading.

## Review focus
Verify subsection context against SGK source, selector purity for every repaired rule, renaming compatibility needs, and ensure this batch is never described as clinical predicate coverage. No merge/deployment authorized.
