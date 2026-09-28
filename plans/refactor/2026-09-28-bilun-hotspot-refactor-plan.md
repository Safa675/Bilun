# Bilun targeted hotspot refactoring plan

- Date: 2026-09-28.
- Status: A and B are merged as [PR #101](https://github.com/Safa675/Bilun/pull/101) (`63df008d`) and [PR #102](https://github.com/Safa675/Bilun/pull/102) (`f63bb12b`), with successful main CI. Delivery C is locally verified in `/root/worktrees/bilun-report-presentation` and awaits publication. D extraction is in progress in a separate worktree; E–F remain pending.
- Inspection baseline: `/opt/Bilun`, commit `4af38b28`. Source line references below describe that inspected revision. Delivery A uses a fresh worktree at `/root/worktrees/bilun-hotspot-refactor`, based on current main `46ae9fdf`, including the merged billing-officer UX work.
- Delivery A branch: `refactor/hotspot-audit-sources`. The user authorized opening a new PR and starting implementation; this delivery was published as a draft PR after local verification.
- Unattended continuation: the user subsequently authorized completion of B–F and merges after tests and independent review pass, with no requested time/token cap. Deployment remains outside scope. The persistent run configuration is `/root/artifacts/bilun-hotspot-refactor-2026-09-28/overnight-run.md`.

## Task: Make the billing hotspots easier to change independently

### Goal

Give report presentation, drug-rule evaluation, and surfacing audits clear responsibilities so that a change to one concern can be understood and tested without following unrelated code, while preserving current product behavior.

### Subtasks

- [x] Establish the implementation base, dependency inventory, and behavior baseline.
- [x] Make the audit resolve the actual report components before moving their source.
- [x] Extract report sections while preserving existing imports and UI behavior.
- [x] Separate section-specific data preparation and compatibility handling from rendering.
- [ ] Extract drug corpus/matching code, then route/constraint/evaluation code behind the existing public module.
- [ ] Separate audit discovery, metadata, validation, rendering, and CLI responsibilities.
- [ ] Complete the applicable verification gates and review whether representative changes have become local.

### Out of Scope

- Repo-wide restructuring or arbitrary file/function line limits.
- Splitting all of `frontend/src/lib/domains/sut.ts`, `src/bilun/api/schemas.py`, or `src/bilun/domain/billing/types.py`.
- Redesigning canonical findings, changing public payloads, or migrating API/cache/database schemas.
- Changing clinical rules, rule coverage, route selection semantics, prices, financial totals, evidence limits, translations, or UI design.
- Removing supported legacy payloads, adding a generic rules framework/table framework, or introducing new dependencies.
- Production cache rebuilds, deployments, publishing changes, or merging as part of this planning task.

Small neighboring-file changes needed to preserve imports, tests, or audit evidence are included. Any newly discovered behavior bug gets a separate fix with its own expected behavior and regression test; it is not silently bundled into an extraction.

## 1. Evidence and priorities

| Priority | Current concentration | Evidence at inspection baseline | Intended improvement |
| --- | --- | --- | --- |
| First | Report sections combine JSX, selection, focus state, and payload compatibility | `frontend/src/components/patient/SutBillingReportSections.tsx:1643`, `:1861` | A section's rendering and presentation decisions can be followed locally. |
| Second | Drug indication combines corpus loading, route arbitration, constraints, and result construction | `src/bilun/domain/prose_rules/drug_indication.py:96`, `:833`, `:1066`, `:1535` | Each responsibility has an explicit dependency direction and focused tests. |
| Third, with a small prerequisite first | Audit combines source discovery, metadata, reconciliation, and output generation; frontend checks depend on exact syntax and source location | `scripts/audits/build_rule_surfacing_inventory.py:997`, `:1092`, `:1753`, `:2040` | Components can move without weakening source checks; formatting and report changes stay in their respective modules. |

Preserve useful existing boundaries: canonical drug evaluation calls the prose evaluator once (`src/bilun/domain/billing/drug_indication_findings.py:556`); tests protect that boundary and corpus-order independence (`tests/unit/domain/billing/test_drug_indication_findings.py:111`, `:137`).

## 2. Baseline and compatibility requirements

- [x] Create an isolated implementation worktree from the selected current main revision. Record its SHA and working-tree state; do not reset or repurpose another task's checkout.
- [x] Recheck current exports, callers, source-scanning assumptions, test imports/mocks, and the plan's source anchors for delivery A. Reconcile direct file overlaps on the selected base; coordinate or rebase as necessary without requiring unrelated work to merge or stop.
- [x] Include the billing-officer UX work in the selected implementation base: fetched main `46ae9fdf` contains the merged #100 changes. Preserve that current behavior rather than restoring this older inspection snapshot.
- [x] Run focused baseline checks and retain the existing two audit outputs outside tracked output paths. Record any pre-existing failures; do not rewrite expectations to make an unexplained failure disappear.
- [ ] Use existing fixtures to capture complete representative drug results through detailed, canonical, legacy, and cached/API projections. Compare fields, text, ordering, identities, and null values, not only counts. Add characterization tests only where an extraction risk is currently uncovered.

The following contracts remain stable throughout:

| Area | Preserved contract |
| --- | --- |
| Frontend | Named exports and props, section IDs, finding/action IDs, table order and labels, CSS behavior, selection callbacks, invoice highlighting, focus/scroll, clause drawers, Turkish/English text, empty/partial/legacy states. |
| Drug engine | Public function signatures and module path; default versus explicitly empty inputs; route tie-breaks and ambiguity; first-hit constraint order; exact violation/evidence fields and messages; cache behavior. |
| Canonical/API/cache | One evaluation per drug line, stable IDs, evidence bounds, status/severity and missing-input meaning, serialization and legacy projections, null-money behavior. |
| Audit | Static operation, actual source evidence, rejection of unresolved contracts, evaluator identity and coverage, classifications/counts, deterministic outputs, CLI options and exit behavior. |

## 3. Phase A — Audit prerequisite for moving report sections

The existing auditor checks the physical `SutBillingReportSections.tsx` file. Leaving re-exports there is insufficient (`scripts/audits/build_rule_surfacing_inventory.py:1092`). Complete this phase before the first component move.

- [x] Add the proposed `scripts/audits/rule_surfacing/surface_sources.py` adapter and call it from the existing script. Leave the rest of the script in place for now.
- [x] Resolve components from the known patient views through explicit named imports/re-exports to their definitions. Restrict traversal to this supported graph; detect cycles, unresolved names, and ambiguous definitions.
- [x] Use a bounded Python token reader for the existing TS/TSX forms and the planned named re-export form. Ignore comments and account for strings/balanced delimiters. This is a limited source checker, not a TypeScript typechecker or proof of arbitrary runtime reachability. Unsupported audited forms must produce a clear failure.
- [x] Verify the relevant component is used in the containing view and the expected section ID exists in the resolved component body. For conditional or nested forms, explicitly support the actual existing pattern or fail; an unused import or unrelated declaration must not count as visibility evidence.
- [x] Keep classification metadata separate from evidence. Do not accept a manifest's claim that a component is rendered, or search every frontend file for a matching token.
- [x] Test the current layout and a fixture with a moved/re-exported component. Deleted exports, missing IDs, removed JSX usage, comments containing old tokens, unused imports, and unresolved/ambiguous targets must fail.
- [x] Keep current outputs identical where evidence is unchanged. Review any added caller/definition provenance separately and prove every non-provenance value remains equal.

Acceptance: existing layout and planned extraction both pass with genuine source evidence; removing the actual product surface still fails. The backend CI job needs no Node installation or new dependency.

## 4. Phase B — Extract the report components mechanically

Proposed directory: `frontend/src/components/patient/billing-report/`.

| Proposed file | Responsibility |
| --- | --- |
| `shared.tsx` | Only genuinely shared shell/table/source-cell helpers and styles. Section-specific helpers stay with their section. |
| `RecommendedActionsPanel.tsx`, `BillingSummary.tsx` | Existing actions panel and report summary. |
| `CopayOptimizationSection.tsx` | Copay display and drawer state. |
| `BillingStrategySection.tsx`, `OptionalOverrideSection.tsx` | Existing strategy/compliance and optional-override displays, respectively. |
| `DrugIndicationReviewSection.tsx` | Drug findings/evaluations and selected-finding focus. |
| `MaterialsPreCheckSection.tsx` | Existing material checks and coverage notices. |
| One file per remaining existing exported section | Move the existing lab, care-setting, checklist, and other sections according to the export inventory. Do not invent new product sections. |

- [x] Move shared helpers, summary/actions, then smaller sections, then copay/strategy, then drug/materials. Keep moves separate from logic cleanup in reviewable commits.
- [x] Retain `SutBillingReportSections.tsx` as an explicit named-export facade with the required client boundary. Preserve callers and existing mocks, including helper imports from `PatientFinancialSummary`.
- [x] Import local helpers directly from leaf files; extracted components must not import back through the facade. Preserve required `"use client"` boundaries.
- [x] Preserve markup, ordering, labels, callback signatures, styling, and runtime decisions during this phase.
- [x] Update audit evidence using Phase A's resolution. Generate candidate reports outside the tracked files, compare them, then regenerate the two reports if required. Permit only explained source/provenance changes.

Acceptance: existing UI checks pass through the original imports; report sections live in dedicated files; no behavior changes are needed to complete the move.

## 5. Phase C — Simplify the section decisions

- [x] For copay and strategy, move nontrivial row selection/merging into pure, section-specific presentation functions colocated with that section. Reuse `frontend/src/lib/billingReportFields.ts`; do not create a new global collection of unrelated helpers.
- [x] Give drug presentation an explicit internal state for structured findings, legacy violations, and evaluation-only output. Preserve the existing precedence and empty/partial behavior. Keep focus/ref management in the owning section and split substantial local card/table/notice rendering where it improves readability.
- [x] Split material sub-tables into local presentational components while retaining simultaneous category rendering and coverage/source notices.
- [x] Remove the proven unreachable optional-override check only after a test confirms overrides still render in their dedicated section. The current exclusion and later search are at `SutBillingReportSections.tsx:841` and `:872`; preserve the tested output at `SutBillingReportSections.test.tsx:387`.
- [x] Keep regulatory interpretation in the backend. Presentation functions select and format already computed results; they do not re-evaluate rules or infer new clinical classifications.
- [x] Add tests only for previously uncovered compatibility, selection, or focus decisions affected by this work. Existing behavior tests remain authoritative.

Acceptance: a report display change can be implemented in its section and, where needed, its own presentation function/tests without studying drug evaluation or unrelated report sections. Legacy support remains explicit and tested.

## 6. Phase D — Extract drug corpus and matching responsibilities

Keep `src/bilun/domain/prose_rules/drug_indication.py` as the public facade. The registry records that module path (`src/bilun/domain/sut/rule_registry.py:361`).

Proposed internal package: `src/bilun/domain/prose_rules/_drug_indication/`, with an initially minimal `__init__.py`.

- [x] Add `matching.py` for pure normalization, specialty/INN/ICD matching, diagnosis collection, and rule-field predicates. Move it before or together with corpus code so the corpus does not need to import the facade.
- [x] Add `corpus.py` for paths, corpus/manifest loading, coverage metadata, promotion gates, and stop conditions. Preserve merge order, optional corpus handling, metadata keys, lazy imports, and shallow-copy behavior.
- [x] Preserve the single decorated loader/manifest caches and regex cache, including invalidation behavior. Re-export the decorated functions where appropriate; do not add a second cache on a wrapper or duplicate cached state.
- [x] Inventory and preserve public access to loading/listing/coverage functions as well as evaluators. Recheck dynamic/private accesses and monkeypatch points against the implementation base before removing names.
- [x] Leave canonical finding types, API schemas, rule data, manifests, and clinical messages unchanged.

Acceptance: loaders and coverage outputs are equivalent; corpus/matching work can be tested without importing billing; public callers keep working through the existing module.

Delivery D extraction retains all 47 original function ASTs, directly re-exports 22 moved callable objects, and preserves the four decorated cache instances. An independently reviewed complete 20,339,608-byte output snapshot (54 line cases, nine full contexts, all 968 rules, canonical/legacy/cache/API projections) is identical to the unchanged monolith. The isolated D source passed 858 focused tests, 4,077 backend tests, Ruff, audit `--check`, compiler `--check` (134 byte-identical artifacts), manifest parity (23 manifests, zero issues), and unchanged hashes for 1,119 tracked artifacts. It was then rebased onto C's merged main without changing D source/test content; the full-output comparator, 858 focused tests, Ruff, audit `--check` and current artifact hashes passed on that integrated tree. Hosted PR CI and review feedback are the remaining publication gates; evidence is under `/root/artifacts/bilun-hotspot-refactor-2026-09-28/delivery-d`.

## 7. Phase E — Separate routing, constraints, and evaluation

Add these files inside the same internal package:

| Proposed file | Responsibility |
| --- | --- |
| `routing.py` | Candidate grouping, equivalence, specificity, ambiguity, discriminator handling, and applicable-route selection. |
| `constraints.py` | Existing report, tier-B, dose, biomarker, prior-therapy, and supplemental checks. |
| `evaluation.py` | Detailed-result orchestration, common evidence construction, and violation decoration. |

- [ ] Move route logic while retaining its existing internal result shape. Keep sorted candidate order, stable tie-breaks, supplemental behavior, and the single-rule compatibility branch (`drug_indication.py:858`). Do not redesign semantics during extraction.
- [ ] Move constraints with the exact existing first-hit order: applicability, report presence, tier-B, dose, biomarker, prior therapy, supplemental.
- [ ] Shorten detailed evaluation around those stages. Keep result construction and violation decoration explicit; preserve message text, evidence ordering, provenance, and missing-input fields.
- [ ] Keep default rule loading in the facade and pass explicit rules to the internal evaluator. Preserve `rules=None` versus `rules=[]`.
- [ ] Preserve dynamic calls through the public detailed evaluator where current wrappers/tests depend on them. The canonical caller and monkeypatch test are at `drug_indication_findings.py:556` and `test_drug_indication_findings.py:128`.
- [ ] Preserve all existing public names/signatures, including both line evaluators and `check_drug_indication_for_context`. Context iteration, no-drug behavior, and missing-claim handling stay unchanged.
- [ ] Extend Python source resolution only if the actual audited entrypoints require it; retain explicit source validation rather than treating an unresolvable function as valid.
- [ ] Compare complete baseline and candidate results for known/unknown drugs, absent diagnoses, secondary diagnoses, explicit empty rules, valid/ambiguous routes, supplemental-only cases, report true/false/unknown, and each constraint family. Reuse reversed/permuted-corpus and cache/API tests.

Dependency direction: facade → corpus/evaluation; evaluation → routing/constraints/matching; routing/constraints/corpus → matching where needed. Internal modules never import the facade or billing. The canonical billing module continues to call the prose facade once and owns its existing projections. Consolidating its messages/types with prose is deferred.

Acceptance: exact public-output parity, one evaluation per line, deterministic route/evidence order, preserved caches/imports, and unchanged data/schema artifacts.

## 8. Phase F — Complete the audit decomposition

Proposed package: `scripts/audits/rule_surfacing/`.

| Proposed file | Responsibility |
| --- | --- |
| `model.py` | Existing audit value types. |
| `metadata.py` | Taxonomy and explicit classifications. |
| `python_sources.py` | Python AST resolution, runtime call discovery, and emitted-contract checks. |
| `surface_sources.py` | Phase A's bounded frontend source resolution. |
| `inventory.py` | Reconciliation, validation, rollups, and `build_audit`. |
| `render.py` | Deterministic JSON/Markdown formatting. |
| `cli.py` | Argument handling, output modes, exit behavior. |

- [ ] Keep `scripts/audits/build_rule_surfacing_inventory.py` as the compatible script entrypoint and retain callable imports used by tests/tools. Support execution by script path from the documented working directory.
- [ ] Pass repository paths/context explicitly; moving a module must not change root resolution through `__file__`. Preserve existing test patch points or replace them with equivalent explicit fixture inputs without weakening assertions.
- [ ] Move source discovery, metadata, validation, and rendering mechanically. Require byte-identical generated outputs for this extraction.
- [ ] In a separate commit, replace the exact-format map regex with literal-object reading using the bounded token adapter. Accept ordinary whitespace/comments, quote styles, and supported type annotations; reject computed/spread/unresolved map entries. Keep this confined to the audited contract rather than growing a general language parser.
- [ ] Preserve default counts output, `--check`, `--write`, both full print modes, both chunk print modes, `--chunk-lines`, mutually exclusive write/check modes, and exit codes (`build_rule_surfacing_inventory.py:2040`).
- [ ] Preserve all detector/source/metadata agreement checks, missing-surface failures, and tests proving projectors do not rerun detectors or use rule-ID allowlists.

Acceptance: changing report formatting is local to `render.py`; source syntax is handled by source adapters; classifiers are not used as substitutes for source proof; actual surface/contract removal still fails.

## 9. Verification and artifact handling

Use the implementation worktree's Python environment matching the current CI requirement (Python 3.13 at inspection) and its locked frontend dependencies. Commands below were checked against existing paths/configuration; they have not been run for this planning task. Recheck CI at implementation start (`.github/workflows/ci.yml:17`, `:29`, `:62`).

Focused frontend checks, from `frontend/`:

```bash
npx vitest run src/components/patient/SutBillingReportSections.test.tsx src/lib/billingReportFields.test.ts src/lib/recommendedActions.test.ts src/lib/sutExactness.test.ts src/components/patient/views/ComplianceViewSection.test.tsx src/components/patient/views/PatientWorkspaceViews.test.tsx src/components/tabs/sut/compliance/SUTComplianceDashboard.test.tsx src/components/patient/PatientFinancialSummary.test.tsx 'src/app/patient/[id]/billing/page.test.tsx'
npx tsc --noEmit
```

Focused drug checks, from the repository root:

```bash
python -m pytest -q \
  tests/unit/domain/prose_rules/test_drug_indication*.py \
  tests/unit/domain/prose_rules/test_nivolumab_expansion.py \
  tests/unit/domain/prose_rules/test_specialty_real_data.py \
  tests/unit/domain/billing/test_drug_indication_findings.py \
  tests/unit/domain/billing/test_claim_drug_indication.py \
  tests/unit/api/test_patient_billing_drug_indication_api.py \
  tests/unit/domain/test_rule_engine_validate_claim.py \
  tests/unit/domain/sut/test_rules_catalog.py \
  tests/unit/scripts/test_drug_indication*.py \
  tests/unit/scripts/test_sut_coverage.py \
  tests/unit/scripts/test_rule_surfacing_inventory.py
```

Focused audit checks, also required after physical UI moves:

```bash
python -m pytest -q tests/unit/scripts/test_rule_surfacing_inventory.py
python scripts/audits/build_rule_surfacing_inventory.py --check
```

At completion of each frontend delivery, run the full frontend CI gates:

```bash
npx tsc --noEmit
npx vitest run
npm run build
```

At completion of each backend/audit delivery, run the full backend gates:

```bash
ruff check src/ scripts/
POLARS_MAX_THREADS=1 python -m pytest -q --durations=20
python scripts/sut/compile_rules.py --check
python scripts/sut/audit_manifest_parity.py --drug-only
```

The one-thread setting is for local testing, as recorded in `tasks/todo.md` under the completed suite-runtime task; hosted CI retains its configured environment. All applicable CI jobs remain enabled. Run both groups on the final integrated revision. Do not repeat successful gates on unchanged code without a new concern.

For the frontend deliveries, exercise selected-finding deep links/focus, action-to-invoice highlighting, clause drawers, narrow-screen table scrolling, both locales, and representative empty/partial/legacy states in an isolated preview. Record actual observations rather than claiming browser coverage from unit tests.

Artifact precautions are based on existing behavior: `tests/conftest.py:47` reconciles manifests with `write=True` even for focused tests; `scripts/sut/compile_rules.py:1202` checks by generating in place and restoring bytes. Therefore:

- Run artifact-writing tests/compiler commands sequentially inside the isolated worktree, never against the live checkout or concurrently against shared files.
- Record status and generated-artifact hashes before/after. Investigate unexpected changes and exclude them from refactor commits; do not use broad resets that could discard other work.
- Keep rule corpora, manifests, goldens, database/cache artifacts, and financial output unchanged. Baseline regeneration drift must be handled separately.
- Compare candidate audit output with `--print-json`/`--print-report` outside tracked paths before `--write`. Pure module extraction requires byte equality; actual source moves may change only individually reviewed provenance fields/text, with all remaining output equal.
- The only planned regenerated files are `reports/rule-engine-surfacing/2026-09-18-rule-surfacing-matrix.json` and `reports/rule-engine-surfacing/2026-09-18-rule-surfacing-audit.md`. Run `--check` after any intentional regeneration.
- Finish each delivery with `git diff --check` and a scope review. Test inventory is taken from the implementation base; do not pin the historical test counts from this plan's inspection.

## 10. Delivery order, review, and rollback

| Delivery | Scope | Dependency |
| --- | --- | --- |
| A | Audit component-source prerequisite | Baseline established. |
| B | Mechanical frontend section extraction | A. |
| C | Section-specific presentation/compatibility cleanup | B. |
| D | Drug matching/corpus extraction | Baseline established; integrate after C in the default sequence. |
| E | Drug routing/constraints/evaluation extraction | D. |
| F | Remaining audit decomposition and map-reader cleanup | Earlier moves integrated so evidence is current. |

Use one focused reviewable change per delivery, with separate commits for mechanical moves, decision cleanup, and intentional generated output changes. This table describes future delivery boundaries; it does not create or publish PRs now. Independent review should check output parity and dependency direction, not just file sizes.

Separate worktrees may be used for independent frontend/backend work, but integrate sequentially and regenerate the reports against the integrated revision. Assign one owner to shared facades and generated reports. Keep existing entrypoints throughout; no migration or feature flag is needed. If a delivery regresses behavior, revert that delivery and its associated evidence changes, retaining earlier verified deliveries. Revert dependent deliveries first if any have already landed.

## 11. Definition of done

- [ ] A reviewer can identify the owner of each responsibility and trace dependencies without circular imports or a new catch-all helper module.
- [x] Walk through a hypothetical display-column change: it is confined to that section/presentation function/tests and does not require drug-engine changes. Do not ship a dummy column to demonstrate this.
- [ ] Walk through a route-selection change: its implementation and focused tests are discoverable in routing, with public-contract changes made explicit if ever required. No dummy rule change is included.
- [ ] Walk through an audit-report formatting change: it requires rendering/tests, without changing discovery or visibility definitions.
- [ ] All preserved contracts and before/after comparisons pass, supported legacy behavior remains covered, and no test has been removed or weakened merely to accommodate file moves.
- [ ] Browser observations, test results, final revision, expected provenance diffs, and absence of unrelated artifact drift are recorded for each delivery.
- [ ] Declaration-file cleanup and canonical-model redesign remain deferred. Any further scope is justified by a concrete maintenance problem rather than line count.

## Planning review

The original plan was prepared from read-only frontend, backend, and audit inspections. Independent frontend/scope and audit/verification reviews found no material issues. Review clarified that coordinating overlapping files does not require unrelated work to merge or stop. The listed test paths/globs and document structure were checked before implementation authorization.

## Delivery A implementation record

- Base: `46ae9fdf`; isolated worktree and branch recorded above. Existing main-checkout planning edits remain untouched.
- Baseline: audit `--check` passed; existing audit tests **26 passed in 20.16s**. No generated-file changes followed the focused run.
- Evidence directory: `/root/artifacts/bilun-hotspot-refactor-2026-09-28`, containing both baseline audit outputs, 1,091 tracked artifact hashes, and the baseline test log.
- Implementation and independent review are complete for the bounded supported grammar. Current/moved-source regressions pass; every other serialized field and Markdown byte remains equal after the 16-row provenance-only matrix update.
- Local checks passed: **4,075 backend tests, 8 warnings, 734.61s**; full Ruff; the audit CLI in isolated Python mode from outside the repository; **134 byte-identical generated rule/manifest artifacts**; **23 manifests with zero parity issues**; final artifact hashes changed only for the reviewed audit matrix.
- Publication: [draft PR #101](https://github.com/Safa675/Bilun/pull/101), attached to the task. Hosted CI started at publication; its current status is available on the PR. No merge or deployment was performed. The next planned delivery is the mechanical report-section extraction (B).

## Delivery B implementation record

- Base `63df008d`; source move commit `af58b2d1`, separately reviewed provenance commit `1dc0b239`. Original module remains a 23-export client facade; 19 section files and shared helpers own the unchanged implementation.
- Both author and independent reviewer compared all 29 declarations, preserving signatures/bodies and all original exports. No reverse imports or local import cycles were found.
- Verification passed: baseline 102 frontend tests; final TypeScript, 373 frontend tests in 64 files, production build, 64 audit/source tests, isolated audit CLI check, and diff checks.
- Candidate reports were compared before regeneration: 16 rows gain 17 verified leaf source-path occurrences, with all other serialized values equal and Markdown byte-identical. Post-test hashes of 1,119 tracked artifacts changed only for the expected matrix.
- Browser verification passed 14 English/Turkish checks for finding focus/visibility, invoice highlighting, clause drawer fetch/close, narrow-table scrolling, and representative empty/partial/legacy states. It used the actual extracted patient-page content in an isolated minimal embedded preview with synthetic intercepted APIs; production data, shell visual parity and production fonts were not tested. Preview source hashes match the committed components.
- Evidence: `/root/artifacts/bilun-hotspot-refactor-2026-09-28/delivery-b`. [PR #102](https://github.com/Safa675/Bilun/pull/102) passed hosted CI and merged as `f63bb12b`; main CI run `36482614267` passed. Delivery C's read-only scope review is recorded in `/root/artifacts/bilun-hotspot-refactor-2026-09-28/delivery-c-scope.md`.

## Delivery C implementation record

- Initial base: B head `9a539d5d`; the identical verified tree merged as `f63bb12b`. Ten new public-section compatibility cases passed before any existing section rewiring.
- Copay and strategy now have section-local pure presentation models. Drug has five explicit display states with section-owned ID/ref/focus handling and local card/legacy/evaluation rendering. Eight material table/benchmark renderers have local ownership. The unsupported duplicate override notice was removed while the dedicated override section remains covered.
- Verification passed: final TypeScript, 383 frontend tests in 65 files, production build, 64 audit/source tests, isolated audit CLI check, byte-identical JSON and Markdown audit outputs, and unchanged hashes for all 1,119 tracked data/report artifacts.
- Independent review matched 16 extracted markup/helper units to the prior sections and found no import cycles. Chromium passed 20 cases, ten in each locale, on both baseline and candidate; every case result is identical, with no page errors or unexpected API calls. Checks include a changed finding selection, unknown-finding fallback, invoice highlighting, clause drawers, narrow scrolling, and empty/partial/legacy states. The preview used actual patient-page content with synthetic APIs in a minimal embedded shell; production data and whole-shell visual parity were outside this local check.
- A hypothetical extra KDV review column is confined to `MaterialKdvReviewTable`'s header/cell and a focused assertion; its parent section's availability/order and the other seven renderers remain separate. No dummy column was shipped.
- Evidence: `/root/artifacts/bilun-hotspot-refactor-2026-09-28/delivery-c`. Hosted PR CI/integration are pending; the completed drug baseline is being used for D's separate extraction.
