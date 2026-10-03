# Source-bound semantic transition: 3f5540cf → 3e0e0c6d

This records the reviewed catalog change and aggregate retained-cache comparison.
It contains no patient identifiers, patient text, raw input tuples, credentials,
or copied cache payloads.

## Immutable identities

- Baseline commit: `3f5540cf199cb464b1fca1d7d7d6ff024d5edc3b`.
- Reviewed candidate commit: `3e0e0c6d88fdcd4817e0a7a84b3361184d78b1ea` (PR #143).
- Candidate Git tree: `6f102905fc1e150de89eefdac91fddbfdff10d10`.
- `data/gazette/prose_rule_sources/drug_indication/4.2.9.A-2.yaml` blobs:
  baseline `8b04c74434acfcdc3af6db2ee31070c32eb495df`; candidate `7b574b32f24e143ef46100894f741a9bdd224878`.
- Candidate `data/gazette/clinical_sources/source_context_repairs_2026_10.json`
  blob: `3ed83b036669f35c2c421e87e5c0bff14a080e21`.
- That packet's consolidated DOCX SHA-256:
  `227b508558840f6c8083c6b6cc8c4efcbf1fcf342e115df5519b0f3e63d7f573`.
- Build IDs: baseline `9483d497-9d4a-4024-ae0c-fde5eebfa0e6`; candidate `c4719f75-f7db-422d-83ee-7c5b6219267a`.

## Reviewed rule intent and source limits

The Git diff removes darbepoetin/Aranesp aliases from `4.2.9.mds_esa_hematology_report`
and `4.2.9.mds_esa_initiation_hematology_report`, and introduces
`4.2.9.A-2.darbepoetin_mds_source_review` for those aliases. The two older rules
remain in the corpus for their retained aliases; they are not globally deleted.
[YAML lines 3, 39 and 75](../../data/gazette/prose_rule_sources/drug_indication/4.2.9.A-2.yaml#L3).

The new rule is a source-review quarantine: drug-specific MDS body mentions were
removed while broader ESA/MDS context remains. Source refs: `prose:4.2.9.A-2#17efb08b`,
`4.2.9.A.(1)#d8313b78`, `4.2.9.A.(3)#a9d0cf5b`, and `4.2.9.A.(4)#ed1d5fdf`.
The review interval is **2024-05-17 through 2026-10-02, inclusive**; absent or
outside dates require the corresponding source version.
[Packet lines 121–131](../../data/gazette/clinical_sources/source_context_repairs_2026_10.json#L121)
and [date guard lines 38–48](../../src/bilun/domain/prose_rules/_drug_indication/constraints.py#L38).

The packet does not establish a complete legal effective interval. The quarantine
supplies neither a payment grant nor an absolute prohibition; clinical eligibility
remains incomplete. Other reviewed windows and unknown historical gaps stay intact.
[Packet lines 2–4](../../data/gazette/clinical_sources/source_context_repairs_2026_10.json#L2).

## Inventory is separate from diagnostic selection

Medicine-matched `specific_routes` are collected before diagnosis filtering and
exported as inventory. Diagnostic selection is separate: changed inventory does
not imply a matched MDS diagnosis or a selected MDS rule.
[routing lines 36–46 and 436–447](../../src/bilun/domain/prose_rules/_drug_indication/routing.py#L36),
[evaluation lines 124–131](../../src/bilun/domain/prose_rules/_drug_indication/evaluation.py#L124).
Tests bind alias retargeting, the quarantine's date boundary and review-only
behavior, unchanged pure-CKD selection, and mixed-diagnosis ambiguity:
[remaining-source test line 60](../../tests/unit/domain/prose_rules/test_remaining_source_context.py#L60)
and [composition tests lines 40–112](../../tests/unit/domain/prose_rules/test_source_context_composition.py#L40).

For one affected retained evaluation, private in-memory predicates confirmed the
exact named rule delta; actual medicine matches both old aliases, neither
retargeted alias, and the new quarantine alias; selected identity stays null;
status, finding identity, clinical/source/runtime evidence and missing/required
inputs stay unchanged. These Boolean results disclose no patient input tuple and
make no diagnostic/clinical eligibility claim.

## Complete retained-cache comparison

Approved same-input proof passed for **12 files**, input-byte SHA-256:
`84efa030d2c5e927f8afb94ce8c494647e398e236d02b560a3d281531231d1f3`.
Source/configuration hashes reconcile independently. Both rosters use
`wavea-source-v1` / `synthetic_demo`; both report contracts use `wavea-evidence-v2`.
All **19 table schemas** match after approved normalization.

| Changed table | Exact ownership and aggregate scope |
| --- | --- |
| `patient_billing_report_rows` | 50 reports: `drug_indication.coverage_scope`; one report also changes route-derived fields under `drug_indication` and sibling `recommended_actions`. |
| `patient_bill_billing_report_rows` | 94 reports: the same metadata change; one report has the same route-derived changes. |
| `cohort_compliance_index` | One `rows[]` entry: `detail`, `eligible_route_count`, `eligible_routes` (one added/two removed), `sut_section_id`. |

The report delta owns `evaluations[].eligible_routes/eligible_route_count`,
`findings[].eligible_routes/eligible_route_count/explanation_tr`,
`violations[].eligible_route_rule_ids/eligible_route_count/detail/message/message_tr`,
and `recommended_actions[].eligible_routes/eligible_route_count/detail/sut_section_id`.
The action and cohort propagation are deterministic projections:
[billing_actions lines 390–423](../../src/bilun/domain/billing/billing_actions.py#L390),
[cohort_compliance lines 345–388](../../src/bilun/domain/billing/cohort_compliance.py#L345).

The other **16 tables** are strictly unchanged: `patient_detail_cache`,
`patient_outcome_base`, `cohort_optimization_summary`, `patient_alerts_summary`,
`cohort_recovery_summary`, `cohort_sut_summary`, `validation_payload`, `patient_meta`,
`cohort_sut_exposure`, `patient_alerts_payload`, `patient_diagnoses`,
`patient_alert_rows`, `patient_billing_reports`, `wavea_evidence_detail`,
`wavea_bill_evidence_detail`, and `wavea_evidence_index`.
Financial amounts, selected identities, statuses, severity and finding kinds have
zero changes. Retain all 19 checks, reject unrelated drift, and complete existing
signing/rehearsal/activation gates.

## Explicit release-tooling contract

Ordinary semantic verification and the serving-to-baseline bridge remain strict.
The optional preparation-manifest field `clinical_transition` contains exactly
`contract`, `expected_candidate_sha`, and `expected_verifier_sha`. The contract is
`bilun-pr143-drug-inventory-transition-v1`; both identities are full Git SHAs
supplied externally by the reviewed release request. Normal preparation,
namespace rehearsal, and receipt issuance require both identities to equal the
exact target head with successful main-branch CI. No future deployment is enabled.

The candidate must be the reviewed product commit or a linear descendant whose
every intervening commit changes only the guard's exact release-tooling/test/doc
paths. Source, catalog, input, unrelated tooling, deployment-automation, merge,
and mutate-then-revert changes fail. The running controller's HEAD, tracked
source/catalog/tooling bytes, and absence of extra source files are independently
bound to the external verifier identity. No self-referential commit hash is
embedded in the implementation.

This contract admits only the retained baseline source hash
`c211fa8490d12db89b5456a071e6a20775c271ade49270776374c0f292b49b92`, configuration hash
`474642a8400d820435d8dbe3f40524ffd357edf8d40cc77a9621fd56b6b5921b`, and the exact
12-file `synthetic_demo` input-byte identity above. Each roster and stored
configuration/source identity is still independently reconciled. Two equally
changed input sets do not acquire an exception.

Both pinned public producers replay in fresh traced subprocesses with an explicit
existing Python runtime and dependency roots, a sanitized environment, and fresh
bytecode lookup paths. An environment-file or unrostered source read fails. Each
cached drug/action projection must equal its own version's replay. The additional
permission boundary checks the exact added/retired route objects, medicine alias
predicates, shared-route order, counts, and independently derived mismatch text.
Coverage metadata must equal the separate public corpus generator and its
source-derived canonical SHA-256: baseline
`6ff61763030de04a3a49167da8c0cead216d726a22ae628b9b8c75d8348b3413`, reviewed product
`375aed0840d735c9c53ab910e6cccfeb4b9d9868ea93449fface1696f95290ac`. The explicit
metadata path boundary also rejects unrelated changes. Clinical evidence and
decisions, selected identities, status, severity, money, and unrelated fields
remain type-exact. Each cohort cache is independently rebuilt from its verified
patient reports before comparison; all 19 tables remain mandatory.

The same proof is recomputed for private HTTP comparison and receipt issuance.
The rehearsal's saved proof, source/config/input identity, and verifier bytes
must match the fresh semantic proof. The receipt issuer follows the sidecar's
hash-verified semantic envelope and requires the sealed report to equal its
fresh verification; the existing signed sidecar/receipt format binds that evidence.

For a read-only regression against the genuine retained candidate cache, the
semantic-checkpoint API may use candidate SHA `3e0e0c6d88fdcd4817e0a7a84b3361184d78b1ea`
and a separate externally reviewed verifier descendant SHA. It uses each original
roster's runtime checkout and the new verifier's own Git history. It does not
relabel cache metadata, issue a receipt, or activate production. A successful
regression or build alone is not deployment evidence.
