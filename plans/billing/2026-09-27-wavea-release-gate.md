# Wave A completion: financial display and release gate

Date: 2026-09-27
Status: proposed implementation plan; independent review required before production code changes
Inspected baseline: `bbf9acafc164aa51579e573ea8ac5f5bc1a34ecd`
Scope: the separate financial display, cache verification, activation, and rollback workstream of Wave A completion. The accepted Wave A detector inventory is owned by the parent implementation plan; this document does not expand that inventory or reinterpret regulatory rules.

## Goal and acceptance contract

Show sourced financial risk and uplift separately at patient and cohort level, preserving existing financial totals and the nonfinancial Wave A contract. Prepare code, frontend, and a complete cache before one final deployment gate. Prove rollback restores the previous coherent release before activating the new release in production.

Success requires all of the following:

- Every selected Wave A finding retains its canonical identity, status, severity, evidence, and null-money semantics across computation, cache, patient/bill APIs, cohort filtering, and UI.
- New financial rows project existing authoritative outputs with their original sourcing, eligibility, inclusion, and rounding decisions. They do not create new payable amounts or change existing totals, actions, action counts, or priority.
- Every baseline patient, bill, cached legacy financial field, and cohort financial total is reconciled against the candidate using the same input snapshot. Any intentional new nonfinancial rows are an explicit, inventory-derived delta, not an ignored mismatch.
- All candidate cache rows pass structural and semantic validation; the manifest pins the exact code, data, configuration, frontend artifact, cache build, and verification evidence.
- Preparation and private verification do not change the public release. Only the gated activation transaction changes public state.
- A rehearsed failure after activation restores code, cache, frontend, and relevant service configuration together, and verifies the restored build and representative responses.
- Full backend/frontend CI remains enabled. Final-head CI, source/corpus checks, staging integrity, candidate UI checks, and rollback rehearsal must all pass before production activation.

## Current implementation and limits

References below are repository-relative paths with inspected line numbers. They describe the baseline, not functionality already added by this plan.

| Area | Current behavior | Consequence |
|---|---|---|
| Canonical compliance | `rule_findings.py` constructs IDs from rule/patient/claim/line-kind/line-ID and fixes all monetary fields to null (`src/bilun/domain/billing/rule_findings.py:68`, `:99`). | Do not put financial amounts into `RuleFinding` or infer money from a billed line attached to a Wave A finding. |
| Patient totals | `finalize_report_totals` computes existing uplift, compliance adjustment, and audit exposure, and sets recoverable equal to uplift (`src/bilun/domain/billing/report_totals.py:64`). | Preserve this arithmetic and existing block eligibility/de-duplication. |
| Cohort totals | Recovery aggregation sums report uplift and assigns the grand total to it (`src/bilun/domain/billing/cohort_summary.py:121`, `:180`). | The new display must not enter the existing aggregation a second time. |
| Risk sourcing | Audit exposure sums payment-method, session, blood, and bundled risks (`src/bilun/domain/billing/claim_audit_exposure.py:11`, `:27`). DRG analysis separates sourced buckets from heuristic bundled risk (`src/bilun/domain/prose_rules/drg_unbundling.py:276`). | Existing audit exposure is not a sourced-only total. Do not relabel it. |
| Uplift qualification | Session rows may be sourced while excluded from the SGK headline for clinical review (`src/bilun/domain/prose_rules/session_uplift.py:152`). DRG uplift de-duplicates strategy/session results (`src/bilun/domain/billing/claim_drg_uplift.py:75`). | Sourcing and recoverability are separate dimensions. Preserve both. |
| Action projection | Action rows omit `savings_basis` and headline inclusion; several uplift IDs use list indexes (`src/bilun/domain/billing/billing_actions.py:105`, `:306`). | Project from authoritative block/detector results, not action amounts or frontend reconstruction. |
| Patient UI | Compliance reads the existing audit scalar; revenue reads existing recoverable uplift (`frontend/src/components/patient/views/ComplianceViewSection.tsx:68`, `frontend/src/components/patient/views/RevenueViewSection.tsx:39`). | Add a separate detail surface; do not silently alter legacy KPIs. |
| Cohort filtering | Revenue currently filters patient summaries and replaces only selected summary fields (`frontend/src/components/tabs/sut/optimizer/SUTOptimizerTab.tsx:1061`). | New financial rows, counts, and any qualified subtotals must all derive from the same filter. Do not reuse unfiltered aggregate fields. |
| Cache | One builder writes patient, bill, recovery, and compliance payloads (`src/bilun/cache/builder.py:249`). Build completion without activation is supported (`:367`). | Build a private complete candidate and validate before promotion. |
| Cache integrity | Recorded checksums contain patient count/data-source values (`src/bilun/cache/builder.py:360`); source hashing uses paths, sizes, and mtimes, not file bytes (`src/bilun/db/hashing.py:10`). | Add release-level content digests and all-row semantic evidence; current metadata is insufficient proof. |
| Source coverage | Builder source paths list clinical/claim parquets, not every rule/catalog/evaluator input (`src/bilun/cache/builder.py:44`, `:134`). | Release inventory must also cover compiled rules, source rules, catalogs, gazette provenance, and relevant code. |
| Deploy order | The workflow checks out new code, activates the frontend, then stages/swaps the cache and restarts backend (`.github/workflows/deploy.yml:90`, `:126`, `:138`, `:193`). | Current workflow cannot provide the required preparation-only phase or coherent rollback. |
| Deploy time budget | The deploy job has a 25-minute cap (`.github/workflows/deploy.yml:30`), while the current cache build alone permits 20 minutes (`:156-179`). | Measure candidate build, full-cache comparison, private browser checks, and rollback rehearsal; raise the cap or split preparation from the short activation job while retaining exact-SHA, stale-head, and release-lock guarantees. A timeout must not leave a prepared artifact active. |
| Rebuild trigger | Cache rebuilding is nested under backend/dependency changes and uses a limited path pattern (`.github/workflows/deploy.yml:108`, `:113`, `:137`). | This release must explicitly require a staged rebuild; do not rely solely on the existing path heuristic for data/cache-only changes. |
| Frontend release | Disposable build, candidate asset verification, symlink activation, and rollback already exist (`scripts/deploy/deploy_frontend.sh:86`, `:110`, `:188`). | Reuse the existing machinery but separate preparation from activation. |
| Health | Readiness checks database access, an active build, and startup cache readiness; degraded responses are HTTP 503 (`src/bilun/api/__init__.py:189`). | Require the expected build/code/source identity too; HTTP 200 alone does not prove the intended release. |
| Cache rollback | Activation supersedes the previous build, but `get_previous_build_id` searches only complete builds (`src/bilun/db/builds.py:262`, `:306`). `set_active_build` checks scope, not completeness (`:240`). | Do not assume these helpers provide rollback. Preserve the previous file and release manifest explicitly. |
| Frontend rollback | Manual rollback can choose the newest noncurrent directory by mtime (`scripts/deploy/rollback_frontend.sh:44`); lifecycle tests cover symlink rollback (`tests/unit/deploy/test_frontend_release_lifecycle.py:138`). | Roll back to the recorded previous SHA; add cross-service/cache failure tests. |

## Proposed financial projection

The checkpoint-1 audit at `reports/rule-engine-surfacing/2026-09-27-wavea-financial-inventory.md` established that the four money-bearing focused groups expose flat validator amounts but do not directly contribute those amounts to current patient/cohort totals. Yatak has a separate bed-day calculation that already affects totals. Confirmed financial display is held until the documented radiation, dental and yatak Q9 correctness defects are resolved in separately reviewed changes; transplant carveouts and unsupported monetary amounts remain review/unavailable. Do not treat an existing flat `risk_amount_try` or expected GA fee as a verified recoverable amount.

### Separate model and ownership

Add a typed `financial_findings` projection to patient and bill reports, with a corresponding cohort index. Proposed module names and field names here are implementation targets, not existing APIs. Keep the existing `claim_compliance` projection unchanged except for the separately approved Wave A detector additions.

Use a frozen financial row with:

- Stable `finding_id`, patient ID, claim ID, line kind, line ID, rule ID, and source engine. Claim-level or multi-line findings retain their true scope and sorted participating line IDs; do not fabricate a single line identity. Identity must not depend on row position or displayed amount.
- `financial_kind`: `risk` or `uplift`; original source surface and original amount field; currency TRY; amount or null; exactness/evaluation status; required/missing inputs.
- `savings_basis` or equivalent original calculation basis; source type; structured clause reference; bounded source evidence; original rule/catalog effective-version evidence where already available.
- An explicit explanation of whether the existing amount contributes to an existing headline, which headline, and whether it requires review. This describes the current calculation; it does not grant new eligibility.
- An overlap/group identifier where the existing computation already establishes one. A display projection must not invent an arbitration rule to make overlapping risks additive.

Populate the projection once from materialized authoritative results. If a financial detector currently exposes only an aggregate, retain its existing detailed result during the original computation rather than rerunning it in the API, cohort index, or UI. Preserve current detector semantics, exactness, source ordering rules, and de-duplication. The existing orchestration finalizes totals, collects actions, and finalizes exactness in `src/bilun/domain/billing/patient_report.py:174`; attach the display projection without changing those outputs.

The sourced-only surface requires an admissible source reference and the existing amount's calculation basis. A nonempty section string, a broad section-heading fallback, or a default source type is not by itself proof of precise monetary authority: `sut_clause_reference` can return an empty key or a section-heading resolution (`src/bilun/domain/sut/clause_reference.py:100`, `:107`). Preserve weaker references honestly as review/unavailable evidence; do not upgrade them to a precise monetary citation or suppress the underlying legacy report row.

Do not use new financial display availability as a reason to remove a selected Wave A finding. Missing financial evidence and missing compliance evidence are independent states.

### Totals and duplication rules

The new projection is display-only with respect to existing totals. Assert unchanged patient/bill `sgk_uplift_try`, `total_recoverable_try`, `compliance_adjustment_try`, `audit_exposure_try`, existing display-only amount fields, all legacy block totals, existing action IDs/counts, and cohort scalar/category totals. Wave A finding counts can increase only by the accepted inventory-derived additions.

Show risk and uplift as separate categories; do not combine them into a net benefit. Sourced review-only uplift remains visibly distinct from confirmed/headline-included uplift. Do not sum different risks on the same line as independent recoverable money. A new summary may show row/patient counts immediately, but an amount subtotal is permitted only for a reviewed, nonoverlapping grouping that reconciles to its authoritative existing calculation. Otherwise show individual amounts and an explicit nonadditive explanation. Preserve null rather than zero for unavailable computations.

Exact duplicate projection rows collapse by canonical ID only when their status, amount, and evidence agree. Conflicting duplicate identities fail validation; they must not be resolved by first/last input order. Input permutation tests cover both duplicates and multi-line groups.

### Patient, bill, cohort, and frontend integration

Extend the domain report type, API response model, serializer, frontend domain types, and cache serializer together. Existing boundaries include `src/bilun/domain/billing/types.py:732`, `src/bilun/api/schemas.py:464`, `src/bilun/api/routes/billing.py:52`, and `src/bilun/cache/build_streaming.py:14`. Include actual JSON serialization in tests rather than relying on dataclass inspection alone.

Patient and bill reports expose the same financial schema with their appropriate scope. Build the cohort index from those canonical patient rows, not from a second detector pass or bill-plus-patient concatenation. Report exhaustive per-patient coverage/status counts and bounded detail evidence separately. Apply patient filters before computing row counts and qualified subtotals; paginate rows without truncating the aggregation universe. An empty selected cohort and an unavailable index are distinct responses.

Add one reusable sourced-financial table to the patient views and cohort surface. Display amount kind, qualification, original headline relationship, claim/line identity, and a source link. Keep existing headline amounts unchanged. Cohort drilldown preserves the canonical finding ID, patient, claim, and selected line. Reuse the existing source drawer/navigation where applicable. Add both supported language strings and accessible labels; raw implementation enums should not be the user's only explanation.

Introduce a versioned payload capability, tied to the validated build, for the complete Wave A and financial display contract. Old/missing/invalid capability must render the new surface unavailable, not a false zero or a partial activation. The frontend must tolerate the previous cache/backend contract during rollback and old open browser tabs. Do not infer feature readiness from the existence of one row.

## Full-cache integrity gate

Build baseline and candidate against one immutable or verified-stable input snapshot. Compare the live active cache separately: if its inputs differ from the snapshot, record pre-existing staleness rather than attributing all changes to Wave A. All cache queries must use an explicit selected build ID; historical/superseded rows are not the live dataset (`tasks/lessons.md:58`).

The proposed verifier must exit nonzero on any unexplained difference and emit a machine-readable report containing:

1. **Build integrity:** expected code SHA, build scope/status, declared contract versions, data source mode, full source-content manifest, nonsecret configuration identity, dependency/runtime versions, and expected patient/bill key sets. Recheck input digests after the build; reject a build made while inputs changed.
2. **Database integrity:** successful clean close/checkpoint and reopen; expected tables; unique build-scoped keys; no missing, extra, or orphan patient/bill records; actual counts reconciled with build metadata. Validate the staged database without opening or altering the live one.
3. **Every clinical/billing row:** compare domain output, serialized output, persisted JSON, and public API serialization. Canonical IDs, statuses, severity, line-kind identity, null money, source evidence, exactness, and bounded evidence metadata must survive each boundary. Invalid serialized rows fail closed with honest availability/counts.
4. **Every existing financial value:** normalized decimal/minor-unit comparison using existing rounding semantics, including zero versus null. Compare the full legacy financial payload contract, not a short handpicked list of top-level totals. Compare existing action identities/counts, priority, and category totals. Newly permitted nonfinancial count deltas require exact inventory-derived explanations.
5. **Patient/bill/cohort parity:** cohort rows equal the canonical patient union after the established de-duplication rule; bill rows have the correct claim scope. Do not assume all patient computations equal a naive sum of bills where existing semantics are nonadditive. Require existing additivity invariants and preserve documented exceptions. Test full, empty, singleton, mixed, unknown-ID, and paginated filters.
6. **Financial projection integrity:** each displayed amount traces to one existing authoritative result; original inclusion/review state survives; no heuristic row is promoted to sourced; no compliance finding acquires money; no patient-and-bill double counting or risk/uplift netting occurs.
7. **Coverage and size:** all accepted Wave A rules/line kinds have supported evaluation states; counts are exhaustive even when evidence is bounded. Record payload sizes, peak RSS, build duration, and representative endpoint latency so rollout resource needs are measured.

Use deterministic content digests of canonicalized payloads and source bytes. Keep separate exact-file digests for transport integrity: semantic JSON comparison must not fail solely on irrelevant key ordering, while file tampering must still invalidate the release manifest. Do not call the current metadata-based `source_hash` a content checksum.

## Host discovery and release manifest

Before scheduling deployment, read the authorized target host's current state. Do not infer a host from an old plan or expose secret values. Record:

- Running backend/frontend service definitions, working directories, interpreter/runtime paths, executable code SHA, cache path, startup policy, data mode, and public/proxy routing; distinguish the serving code from repository HEAD.
- Current frontend symlink/release manifest and expected retained assets; active cache build and source identity; previous recoverable code/cache/frontend tuple.
- Free disk on each relevant filesystem, cache/source/release sizes, available RAM and swap, service RSS, CPU budget, build worker settings, and candidate ports. Determine whether simultaneous live services plus candidate services/builds fit; if not, schedule preparation sequentially or reserve explicit maintenance. Do not silently run an oversized parallel build.
- Filesystem/permission constraints for atomic rename/symlinks and service control; process ownership; deploy locks; ability to preserve a checkpointed previous cache; available rollback disk budget.
- Effective nonsecret API routing configuration. `frontend/next.config.ts:4` builds rewrites from `API_PROXY_TARGET`; browser API base can come from `NEXT_PUBLIC_API_URL` (`frontend/src/lib/apiClient.ts:18`). A private frontend asset probe alone does not prove it uses the candidate backend.

Persist a release manifest outside mutable source files containing:

| Manifest field | Required content |
|---|---|
| Release identity | Unique release ID; exact reviewed code SHA; exact successful CI head/run; implementation inventory and contract versions. |
| Frontend | Prepared release path/SHA, Next build ID, asset-manifest/content digests, API routing contract, private asset/browser verification report. |
| Cache | Immutable candidate path, selected build ID, scope/status, schema/feature versions, checkpoint status, content digest after final close, table/key counts, semantic payload digests. |
| Inputs | Byte-content digests of clinical/claim inputs, rules, catalogs, gazette provenance, and relevant source inventory; data mode; nonsecret effective configuration digest. |
| Runtime | Python/Node/dependency versions and candidate service configuration references; do not embed credentials or secret-bearing environment dumps. |
| Evidence | Full CI, compiler/parity, all-cache verifier, representative API/browser tests, resource observations, failure-injection and rollback reports, each tied to the candidate identity. |
| Previous release | Exact code/runtime/frontend/cache paths and IDs, service configuration references, known-good health/API observations, and retention protection. |
| Transaction journal | Prepared/validated/activating/active/rolled-back state, timestamped completed steps, and failure/recovery outcome. |

No activation may use a manifest whose content or identity no longer matches the staged artifacts. Protect the previous tuple from pruning until acceptance and the agreed retention window expire.

## One final activation transaction

Implement a single release coordinator with preparation, validation, activation, and rollback phases. The normal production workflow must use this gate for this release; no earlier frontend activation or automatic second cache build may bypass it. Preserve the existing restriction to successful same-repository main push CI and stale-head checks (`.github/workflows/deploy.yml:22`, `:79`). Recheck the expected deploy SHA immediately before activation.

Measure the full preparation and activation durations on disposable/staging resources before setting GitHub job timeouts. If one job cannot safely fit the measured preparation plus verification and recovery budget, split it into a long-lived preparation job and a short activation job bound by the same immutable release manifest, exact CI SHA, exclusive lock, and stale-head recheck. Do not rely on the current 25-minute cap or let a timeout promote a partly verified candidate.

### Preparation and private verification

1. Acquire the release-preparation lock and record the current serving tuple. Prepare backend code in an isolated immutable checkout/runtime; do not move the live working tree to new code during preparation.
2. Build to a unique versioned staging database with explicit claims/clinical input paths and no live-pointer mutation. Complete without `--activate`, then run full-cache verification. Mark an internal staging pointer only after these checks, for private candidate serving; this is not public activation. Reject noncomplete or wrong-scope builds explicitly rather than relying on `set_active_build` alone.
3. Checkpoint and close the candidate database, reopen it for integrity checks, and retain a clean snapshot suitable for promotion. Manage WAL consistently; do not rename an actively written database and sidecar as if two independent moves were one transaction.
4. Prepare the exact frontend release using the existing disposable worktree/asset machinery, stopping before `current` activation. Run the candidate backend with an explicit candidate cache path and load-only policy; an absent cache must fail verification rather than trigger a fallback production build.
5. Verify the exact prepared frontend artifact against the candidate API. Because frontend API routing can be build-time configuration, inspect the emitted routing contract. Use an isolated candidate proxy or an explicit browser-test routing harness to direct requests to the candidate backend; do not rebuild a different frontend artifact after verification or accidentally validate against production API data. Verify production routing separately during activation.
6. Run representative authenticated API/browser cases, source navigation, empty/unavailable states, filters, old-client compatibility, and rollback rehearsal. Finish the release manifest only when every required gate passes.

### Public activation and postactivation checks

The recommended bounded implementation uses a short maintenance/traffic barrier for the activation transaction. Backend and frontend service changes are not jointly atomic. The barrier must cover public API and frontend traffic while the coherent tuple is changed; preserve health/operator access needed for verification. Discover and test the target proxy mechanism before implementation. If a suitable barrier is unavailable, a blue/green proxy switch is an explicit alternative requiring independent design review; do not claim an atomic release from sequential restarts alone.

Under one exclusive activation lock:

1. Verify the manifest, expected current/previous tuple, successful CI head, input/artifact digests, available resources, and rollback target. Refuse stale or partially prepared releases.
2. Enter the tested traffic barrier. Record journal state `activating`. Quiesce affected writers/services before changing cache targets; preserve the previous checkpointed cache/runtime. Do not prune or overwrite the only rollback copy.
3. Switch backend code/runtime and cache configuration to the prepared versions; start load-only. Require HTTP success, `cache_ready=true`, exact expected active build, and code/source/contract identity plus representative API responses. Add explicit release identity exposure where necessary; current `/health` alone is insufficient.
4. Switch frontend `current` to the already prepared release and restart it. Verify local and public routing/assets, expected release identity, representative authenticated screens, and retained old browser assets. Do not rebuild during this step.
5. If all checks pass, remove the traffic barrier and verify public representative requests again. Record `active`; retain the prior tuple. If any check fails, execute rollback before reopening normal traffic.

This is one final public activation gate after staged validation, with a measured short interruption. Its downtime budget must be set from the rehearsal and host resource discovery, not guessed. The implementation must not silently substitute a partially visible staged rollout.

## Tested rollback

Rollback takes the recorded previous release ID, not “latest” directories or inferred historical build pointers. Under the same activation lock and traffic barrier:

1. Stop/quiesce candidate services and writers; record the failure and last completed transaction step.
2. Restore the previous backend runtime/code target, cache path/build, frontend target, and relevant service configuration. Keep old and new cache/WAL families isolated. Use the retained checkpointed file rather than mutating statuses in a shared historical database.
3. Restart backend load-only and frontend; require previous build/code/frontend identity, readiness, source version, representative patient/bill/cohort responses, and old assets.
4. Restore normal traffic only after successful verification. Record `rolled-back` and keep diagnostic artifacts. A failed rollback leaves the barrier in place and reports an actionable deployment failure; it must not print rollback success while suppressing failed restart/verification commands.

Rehearse activation and rollback on disposable resources with the same coordinator, not only unit tests of a symlink helper. Include process interruption at each journal boundary and idempotent recovery on rerun. Manual rollback and retention pruning must share the release lock and respect the protected previous tuple.

## Validation and failure injection

| Gate | Required evidence and failure behavior |
|---|---|
| Domain contract | Inventory-derived rule cases; canonical identity including line kind; preserved evaluation/status/severity; all money null on nonfinancial rows; source and amount qualification; input permutations; identical and conflicting duplicates; all legacy totals/actions unchanged. |
| Serialization and API | Dataclass/dict/JSON round trips; patient and bill routes; all source/status fields preserved; malformed/old payloads unavailable; missing patient versus missing cache distinguished; matching payload capability. |
| Cohort | Exhaustive union/count parity; no patient/bill double count; all filters and pagination; no top-10 fallback presented as a complete filtered universe; unavailable/empty distinctions. |
| Cold threaded build | Reset lazy resolver state and build through actual threaded cohort paths; no permanently cached missing clause reference. This guards the documented race in `tasks/lessons.md:79`. |
| Full cache | Every patient/bill key and payload, every legacy financial amount, cohort reconciliation, input stability, complete metadata, byte-content checksums, clean reopen. No representative-only substitute. |
| Full CI | Exact complete backend pytest, Ruff, compiler `--check`, manifest parity, TypeScript, all Vitest tests, production build; retain original case identities and statuses while accounting for explicitly added tests. Commands remain in `.github/workflows/ci.yml:30` and `:59`. |
| Build failure | Detector exception, incomplete/missing table, duplicate key, malformed row, changed source input, wrong code SHA, wrong build scope/status, or digest mismatch prevents public activation. Previous public tuple remains intact. |
| Candidate failure | Missing cache, failed startup, bad API routing, authentication failure, missing assets, unresolved required source, or API/UI disagreement prevents activation; no live fallback build. |
| Activation failure | Fail backend restart/readiness, frontend restart/asset checks, public routing, or representative API verification at each step. Restore the exact previous tuple before reopening traffic. |
| Interruption/concurrency | Kill coordinator at each journal boundary; rerun recovery is deterministic. Competing deploy/rollback/prune is serialized. Superseded CI/deploy SHA cannot promote a stale candidate. |
| WAL/storage failure | Incomplete checkpoint, sidecar mismatch, insufficient disk, cross-filesystem atomicity assumption, or permission failure causes preflight rejection or tested rollback; never discard the last recoverable cache. |
| Rollback failure | Restored service cannot restart or verify: report failure honestly and keep the traffic barrier. Recovery instructions identify recorded previous artifacts without exposing secrets. |
| Retained clients | Previous frontend assets remain available. `/validate-claim.violations` intentionally loses positive/review/info rows at activation, so test an old frontend against the new API and explicitly document that its old violation list becomes shorter and cannot display the new `advisories` field. Test the new frontend against the previous API after rollback: absent advisories/capability render unavailable or as an honest legacy result, without invented zeroes or a crash. Verify retained old assets and both routing directions. |

Synthetic rule/status tests must cover every authored/runtime ID, including IDs whose required facts are unavailable in present claim data. Representative candidate and live checks must cover triggered groups and line kinds actually present, a negative/no-finding case, missing inputs, unavailable evidence, sourced risk, confirmed uplift, sourced review-only uplift, overlapping representations, a multi-bill patient, singleton/empty/mixed cohorts, patient drilldown, and clause navigation. They do not require an impossible positive live example of each possible ID. Derive expected values from the pinned candidate API/build; do not hard-code outdated plan KPIs (`tasks/lessons.md:712`). Representative checks supplement the all-cache gate, not replace it.

## Implementation sequence and independent review checkpoints

- [ ] Integrate this document with the parent inventory/implementation plan in `tasks/todo.md`; independently review scope, selected financial sources, acceptance contract, and the traffic-barrier approach before any production code.
- [ ] Inventory authoritative financial outputs and their current eligibility/de-duplication, source strength, overlap, and headline relationship. Define supported rows without inventing missing regulatory authority.
- [ ] Implement typed display projection and patient/bill/cohort serialization with unchanged legacy totals/actions and fail-closed unavailable states; run meaningful contract/parity tests.
- [ ] Implement shared patient/cohort UI, filters, source links, bilingual labels, compatibility behavior, and browser tests.
- [ ] Implement full-cache verifier, stable input snapshot/content manifest, candidate capability, and deterministic verification reports; validate all cache rows.
- [ ] Discover authorized host resources/routing and document the exact preparation, traffic barrier, activation, retention, and rollback commands without exposing credentials.
- [ ] Split existing frontend preparation/activation and implement the release coordinator/journal; run failure injection and complete rollback rehearsal on disposable resources.
- [ ] Run every final-branch CI gate, inspect independent code review, and verify source/artifact identity. Any necessary source or artifact change invalidates affected prior gates.
- [ ] Prepare the production candidate privately, run staged all-cache verification and representative browser/API checks, and produce the immutable release manifest.
- [ ] Review the concrete release manifest and rehearsal evidence at the final activation gate; activate only within the user's existing explicit deployment authorization and confirmed target scope.
- [ ] Verify the live tuple and representative cases, retain the previous release, and record completion or rollback outcome with measured timing and limitations.

## Out of scope

New medical/regulatory interpretations; inferred money for nonfinancial findings; changing existing payment/recovery arithmetic; broad financial overlap arbitration; promoting heuristic evidence to sourced authority; unrelated detector migrations; narrowing/skipping existing tests; silently regenerating different inputs to hide drift; merging/deploying before the parent approval/review gates; and changing the live system during this planning task.

## Self-review

This document was checked against the inspected source boundaries and the requested scope. It separates planning targets from current functionality, preserves nonfinancial money-null and legacy-total contracts, does not call mixed audit exposure sourced, accounts for source provenance lost in actions, distinguishes sourced from confirmed uplift, and requires all-cache verification rather than sample-only verification.

The activation design addresses the current frontend-before-cache ordering, metadata-only hashes, missing previous-cache retention, incomplete pointer rollback semantics, and candidate frontend/API routing. It does not claim cross-service atomicity: the proposed traffic barrier must be discovered and tested, with downtime measured before approval. The independent implementation-plan review is still pending; no production code, deployment, or runtime validation has been performed by creating this file.
