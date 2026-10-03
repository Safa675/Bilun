# GH leaf runtime observations over the reviewed GH44 tree

This additive packet preserves the reviewed clinical results, required/missing input lists and prior 31 predicate identities/source references. It adds 21 pediatric initiation/CKD growth identities for 52 authored bindings. These are atomic necessary checks, not full eligibility or complete source-clause evaluation.

## Exact parent and dependencies

- GH44 manifest SHA-256: `10e84db8792b431c76d137e1d8b50008d90f24923125a5e2dba365ad73ebe91f`. All 44 physical snapshot/worktree hashes were checked before starting.
- Collector/coverage dependency: approved renal-v3, manifest SHA-256 `41ece9b0e16fca9bf97ead4e09cde4603fe357789fc32d667fa31b36c1c72649`. Its collector/coverage modules were copied unchanged for local tests and are not edits in this packet. The approved SMA/antifungal helper extends this compatible interface.
- Prior GH observation8 remains preserved at `bilun-gh-runtime-review`. This packet supersedes observation8 for leaf integration over GH44, without replacing any clinical/source packet.

## Caller contract

Use one request-local `ClinicalObservationCollector`, family `growth_hormone`, evaluator version `gh.atomic.v1.2026-10-02`.

Existing optional `observer=None` entry points remain: `evaluate_growth_hormone_continuation`, `evaluate_pws_preconditions`, `evaluate_pws_clinical_checks`, `evaluate_ckd_gh_preconditions`, `evaluate_ckd_gh_checks`, `evaluate_mecasermin_preconditions`, and `evaluate_mecasermin_checks`.

New optional entry points: `evaluate_pediatric_gh_initiation_preconditions` and `evaluate_pediatric_gh_initiation_checks`. CKD checks forward the observer internally to `evaluate_ckd_growth_pathways`. Check functions forward the observer to their preconditions for direct calls; a preceding shared precondition call produces identical, deduplicable receipts. Retain summaries even when the clinical return is `None`.

Shared medicine/rule selection, orchestration, public projection, cache contract and corrected source view remain coordinator-owned. No shared caller, clinical-family dispatch, DTO, sink, source corpus or compiled rule is edited. Adult closed-epiphysis context remains structural source context with no new clinical predicate.

## New comparisons and boundaries

Pediatric initiation contributes 13 bindings. Standard growth compares only the explicitly recorded age band against its source threshold. The printed `2,1` and `4,1` transitions are not reinterpreted. Missing stage facts block inputs; known contradictory stage/age evidence produces a source-block route before thresholds. Puberty observes specialist assessment and epiphyseal status without numeric velocity/bone-age predicates. Prepubertal bone delay uses the original Decimal difference and inclusive two-year threshold, and is skipped before age four.

SGA1 preserves the original weight-or-length short circuit: successful weight comparison skips length and does not count an unused supplied length. Age >=4 and last-year growth SDS <0 are separate checks. SGA2 first observes explicit SGA birth confirmation; only confirmed scope reaches strict height SDS <-2.5 and parent-adjusted SDS <-1. Organic/surgical and neurosecretory pathways emit source blocks for unimplemented assessment; no standard-path predicate is inferred.

CKD growth contributes eight bindings: growth percentile <25; recorded height percentile <3 and SDS <-2; and five Boolean facts in `a OR (b1 AND b2 AND b3) OR c`. Branch flags are explicitly compared before the unchanged three-valued combination, so false/unknown alternatives remain genuine atomic observations when another branch succeeds. Original clinical OR behavior and missing-input lists are preserved.

Missing one or both height representations produces a source block without height threshold predicates. With both independently recorded, the actual comparisons are emitted; disagreement produces a separate source block. This asserts neither percentile/SDS equivalence nor a legal requirement to measure both. Contradictory first-year/elapsed-year transplant facts block before exclusions/dose/growth. Earlier exclusion/dose failures do not emit unreached growth receipts; continuation observes dose and skips initiation checks.

Reconciliation guards are routes, not normative predicates. Missing actual facts, source uncertainty and phase/protocol bypasses remain distinct. No raw clinical values, diagnosis-derived facts, clock date, numeric conversion or invented source interval is added. All predicate receipts have `clause_predicate_complete=false`; full source-clause counts remain null. Mecasermin metrics still require the specifically reviewed stable-key corrected source view, never a broad prose exception.

## Verification

- 531 combined GH clinical/source/prior-observation/expanded-observation tests passed. The expanded file contributes 54 cases, including all 243 three-valued CKD branch assignments within its exhaustive test, historical/unknown dates, signed boundaries, source notation/reconciliation and repeated precondition/check sequencing. Workspace log: `gh-runtime-extended-combined.log`.
- `scripts/sut/audit_gh_observation_parity.py` validates the supplied exact GH44 manifest/worktree, loads original leaves separately and explicitly restores the original CKD nested helper. All 4,775 deterministic clinical outputs match with and without observers, and all summaries validate. Every one of the 52 bindings was executed. Results and original leaf hashes: `gh-runtime-differential-result.json` beside this report.
- Prior 31 bindings are compared exactly against observation8. All 21 new bindings include fields, operator, bound and units. Active normative source resolution passes for all new pathways in repeated-call tests.
- Ruff passes for all changed Python files. Frozen clinical/source snapshots are preserved. This is bounded local verification; final shared transport/HTTP integration and hosted CI remain separate gates.
