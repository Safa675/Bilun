## Task: Implement public billing and protected developer access

### Goal
Implement the approved public-billing/developer-login plan, verify security and billing behavior, and publish a new reviewed PR without deploying.

### Subtasks
- [x] Review the approved plan and repository instructions; create isolated branch `feat/public-billing-developer-access` from current `origin/main` at `3db12d53` (includes deployed #99, billing UX #100 and refactors #101–106).
- [x] Implement explicit backend access policies, authoritative capabilities and public response projections.
- [x] Secure officer chatbot context/tools and bound public computation.
- [x] Implement capability-driven frontend, developer sign-in, logout/expiry and public billing workflow.
- [x] Add release migration instructions, protected health probes, credential/session cutover support and asset confidentiality verification.
- [x] Review integrated behavior, run focused tests, full CI parity and production browser security checks; resolve failures.
- [x] Review final diff, verify branch CI status, publish/attach a new PR and confirm its checks.

### Out of Scope
Merging, live deployment, live credential rotation, changing clinical/payment calculations, new real-patient datasets or multiuser/SSO provisioning.

### Review
Plan approved by the user; implementation follows `plans/security/2026-09-29-public-billing-developer-access-plan.md`. Main checkout and existing deployment are preserved. Public access defaults disabled pending the documented release cutover.

Implementation & verification evidence:
- Backend access control, authoritative session resolution, and public JSON response projections verified.
- Fixed cohort projection test `test_public_projection_preserves_cohort_business_results_and_cached_nulls` by popping internal `wavea_evidence_detail` payload before projection comparison.
- Fixed Next.js Playwright strict mode conflict on `getByRole("alert")` in `test-access-browser.mjs` by filtering on text.
- Full CI test parity:
  - Ruff check (`ruff check src/ scripts/`): clean
  - Rules compiler check (`python scripts/sut/compile_rules.py --check`): 134 rule/manifest artifacts byte-identical
  - Drug manifest parity check (`python scripts/sut/audit_manifest_parity.py --drug-only`): 23 manifests scanned, 0 issues
  - Unit tests: 964 passed in 538s
  - Cohort projection test: 1 passed in 86s
  - Vitest frontend suite: 70 files passed, 402 tests passed in 17s
  - TypeScript build check (`npx tsc --noEmit`): clean
  - Frontend production build (`next build`): clean
  - Browser E2E security tests (`node scripts/test-access-browser.mjs`): all 4 scenarios passed
  - Public asset verification (`verify_public_assets`): 52 files checked, 0 problems
  - `git diff --check`: clean

---

## Task: Complete hotspot refactoring delivery F — audit decomposition

### Goal
Give audit discovery, classifications, reconciliation, rendering, and CLI their own modules without changing generated outputs or the supported CLI, then publish the final focused PR after E.

### Subtasks
- [x] Create an isolated F worktree from C head `b5bae476` with D/E integration deferred until their verified merges.
- [x] Independently review the approved F boundaries, existing imports/test patch points, source root behavior, and every CLI mode before code edits.
- [x] Capture byte-exact baseline JSON/Markdown, CLI outputs and 1,119 tracked artifact hashes in this worktree before any Python test writers.
- [x] Mechanically extract model, metadata, Python source resolution, inventory validation/rollups, rendering and CLI into `scripts/audits/rule_surfacing/`; keep the old script pathname and callable compatibility.
- [x] Prove generated JSON/Markdown and all supported CLI modes are byte identical; preserve missing-surface and source-contract failures.
- [x] In a separate commit, replace only the exact-format literal deep-link map regex using the bounded token reader, with realistic valid syntax and computed/spread/unresolved rejection regressions.
- [x] Run focused audit tests, full backend gates, standalone CLI from repository and isolated cwd, sequential compiler/manifest checks, and tracked artifact drift checks.
- [x] Obtain independent review of source-vs-classification proof, path handling, imports/patch points and diff; resolve substantive findings.
- [x] Integrate verified E main, rerun affected checks, publish focused PR #106 and request task attachment; complete independent integration review.
- [ ] Verify current-revision CI/GitHub feedback and merge only after all gates pass.
- [ ] Run both frontend and backend gates on final integrated main and complete all three responsibility-locality walkthroughs in the approved plan.
- [ ] Record PR/revisions/verification and finish the agreed refactor only after the completion audit passes.

### Out of Scope
Changing detector semantics, rule coverage/classifications/counts, audit report formatting, frontend/clinical/financial behavior, canonical findings, new dependencies, production data/cache, deployment and unrelated user work.

### Review
The independent read-only inventory defines explicit ownership across `model`, `metadata`, `python_sources`, `surface_sources`, `inventory`, `render`, and `cli`, with the old script retaining compatible callables and a single root/path context. Tests patch nine old-script path globals, three path helpers, and `PATIENT_REPORT_META`; the extraction must keep those seams observable. The map reader is a separate bounded change after pure extraction. Baseline direct `python -I` behavior was captured from `/tmp` for default, check, full/chunk/combined prints and invalid arguments in `/root/artifacts/bilun-hotspot-refactor-2026-09-28/delivery-f`; successful full JSON and Markdown hashes exactly match C's baseline. All 1,119 tracked artifacts are unchanged. F can be implemented in parallel with D/E integration, but publication remains last. Worktree `/root/worktrees/bilun-audit-decomposition`, branch `refactor/hotspot-audit-decomposition`.

The frozen mechanical extraction moves audit ownership to the planned modules while retaining a script-path facade with explicit call-time `AuditContext` from the original root, patched globals and three helper callbacks. Independent review found no actionable issue: all 52 original function bodies are unchanged apart from explicit context plumbing, all 27 facade wrapper signatures and 12 metadata tables remain compatible, and import/source-proof boundaries hold. Scoped Ruff and 78 focused tests passed. All 12 captured direct CLI cases preserve exit codes and stdout; successful modes and parser-exclusivity stderr are byte-identical, while invalid-chunk exception text remains exact with expected relocated traceback frames. Generated JSON/Markdown bytes and all 1,119 tracked artifact hashes remain unchanged. Evidence and the independent review are under `/root/artifacts/bilun-hotspot-refactor-2026-09-28/delivery-f`. The literal-map reader was implemented and reviewed in a separate second commit.

The second stage replaces only the exact-layout map regex with a bounded literal reader in `surface_sources.py`. It accepts the existing 17-entry map plus ordinary comments/whitespace, literal quote styles, trailing commas and explicitly supported type annotations; it rejects dynamic/computed/spread/unresolved/duplicate entries and unsupported syntax. Independent review found a regex-literal false-evidence case, which was fixed by a local fail-closed top-level slash guard and four regressions; re-review found no remaining blocker and A's tokenizer/resolver remain unchanged. Before E integration, corrected source passed 122 focused tests, all 12 captured CLI exit/stdout comparisons, byte-identical full JSON/Markdown, 4,133 full backend tests (eight warnings), full/scoped Ruff, isolated direct CLI `--check`, compiler `--check` (134 byte-identical artifacts), and manifest parity (23/zero). All 1,119 tracked artifact hashes remained unchanged after every gate. A pre-fix interrupted run is separately labeled and not counted. Evidence: `/root/artifacts/bilun-hotspot-refactor-2026-09-28/delivery-f`.

F was rebased onto E's merged main `46a694d0`; all reviewed F source/tests remained byte-identical apart from three trimmed signature spaces with unchanged AST. [PR #106](https://github.com/Safa675/Bilun/pull/106) opened at this integrated candidate. Independent final review cleared its source and contracts. Local integrated gates passed 964 focused and 4,145 full backend tests (three/eight warnings), TypeScript, 383 frontend tests in 65 files, production build, full/scoped Ruff, isolated audit and all 12 CLI modes, exact generated JSON/Markdown, compiler `--check` (134 byte-identical artifacts) and manifest parity (23/zero). All 1,119 tracked data/report artifact hashes were unchanged after every gate. The app attachment request did not return, so attachment is unconfirmed. Its initial current-source CI run `36489935324` passed both jobs at `6fb194cd`; final documentation-only PR-head CI, merge and merge-main CI remain. Evidence: `/root/artifacts/bilun-hotspot-refactor-2026-09-28/delivery-f`.

---

## Task: Complete hotspot refactoring delivery E — drug routing, constraints and evaluation

### Goal
Make route selection, ordered constraints and detailed-result construction independently changeable while preserving every existing public result and clinical decision. Deliver a separate PR after verified D.

### Subtasks
- [x] Review approved Phase E and the stable D implementation for ownership, public wrapper/patch seams, raw-versus-decorated violation shape and ordered constraints.
- [x] Create an isolated E worktree at C head `b5bae476`, with D integration deferred until D is verified and merged.
- [x] Add targeted dynamic-wrapper/default-loader, competing-failure precedence and primary-plus-supplemental identity tests and prove them on the unchanged monolith; re-run after D integration before source edits.
- [x] Integrate verified D main, refresh import/patch inventory, and compare the unchanged D full-output baseline.
- [x] Mechanically extract routing, constraints and evidence helpers into the three approved internal modules, retaining callable identities, public wrappers and cached objects.
- [x] Give the internal evaluator explicit rules; keep default loading in the facade and preserve first-hit, nested payload and supplemental-ID behavior.
- [x] Compare the immutable complete result snapshot and new pre-extraction tests; run focused/full backend, Ruff, isolated audit, compiler/manifest gates sequentially and tracked-artifact hash checks.
- [x] Obtain independent review of AST/signature/dependency and output parity; resolve substantive findings.
- [x] Publish E PR and request task attachment, verify current-revision CI/GitHub feedback, merge with exact-head guard after checks pass, then verify main CI.
- [x] Record PR/revision/evidence and advance to F.

### Out of Scope
New clinical rules or messages, route semantics, corpus/cache changes, canonical findings/projections, rule data/schema/artifact changes, audit parser expansion, deployment or unrelated cleanup.

### Review
The read-only map and explicit extraction traps are recorded at `/root/artifacts/bilun-hotspot-refactor-2026-09-28/delivery-e/read-only-extraction-checklist.md`. E's source changes wait for D integration; targeted baseline tests can be authored on the unchanged monolith in parallel. Worktree `/root/worktrees/bilun-drug-evaluation`, branch `refactor/hotspot-drug-evaluation`.

Three targeted groups (ten cases) passed against the unchanged C monolith at `b5bae476` before E source work: facade default-loader calls for `None` versus explicit `[]`, dynamic public detailed calls and context order/orphan behavior, first-hit precedence across overlapping failures, and primary/supplemental inner-versus-outer identities. Ruff passed. Source/test hashes and logs are under `/root/artifacts/bilun-hotspot-refactor-2026-09-28/delivery-e`. The verified D source can be integrated provisionally before its PR merge; E publication remains dependent on D's final merged main and hosted gates.

After provisional D integration, 12 boundary/cache tests and the immutable complete comparator passed before E source edits. The reviewed extraction gives routing, constraints and evaluation their own modules while keeping all 46 other original function ASTs, 47 signatures, 44 exact callable aliases and four cache objects. The 20,339,608-byte detailed/canonical/legacy/cache/API payload snapshot remains identical. Independent review found no actionable finding, including first-hit order, raw/common nested fields and supplemental inner/outer IDs. The final isolated E source passed 868 focused tests, 4,087 full backend tests (eight warnings), full Ruff, isolated audit `--check`, compiler `--check` (134 byte-identical artifacts), and manifest parity (23 scanned, zero issues), with all 1,119 tracked artifact hashes unchanged after each gate. Evidence: `/root/artifacts/bilun-hotspot-refactor-2026-09-28/delivery-e`. Rebase onto D's merged main and hosted current-revision CI remain before publication/merge.

E was rebased onto D's head-guarded merged main `ec368706` with byte-identical E source/test content. The immutable complete comparator, 868 focused tests (three warnings), Ruff and isolated audit `--check` passed again on the integrated tree; all 1,119 current tracked artifact hashes remain unchanged. D's merge-main CI run `36487251655` passed. PR publication and E current-head hosted CI remain.

E publication: [PR #105](https://github.com/Safa675/Bilun/pull/105) at `671fc9e0` passed both hosted jobs in run `36488702448`, independent review and feedback review, with no human/inline findings (Copilot reported quota exhaustion). It merged with an exact-head guard as `46a694d054ec3a557e25977de386c09405bce215` at 2026-09-28 21:57:26 UTC; the merged tree equals the tested branch. Both main CI jobs passed in run `36489455355`. The app attachment call did not return, so attachment is unconfirmed. Delivery F was then rebased onto this merged tree.

---

## Task: Prepare and implement hotspot refactoring delivery D — drug corpus and matching

### Goal
Extract drug matching and corpus responsibilities behind the existing public module with exact output/cache compatibility, then integrate after delivery C as its own verified PR.

### Subtasks
- [x] Read the approved phase D/E boundaries and create an isolated worktree at main `63df008d`; rebase onto the verified delivery C main before publication.
- [x] Independently inventory public/private accesses, cached objects and monkeypatch seams; review the planned ownership before runtime edits.
- [x] Capture complete representative baseline detailed/canonical/legacy/cache/API results using existing fixtures, including the plan's edge cases, and save an executable before/after comparison outside tracked artifacts.
- [x] Add only meaningful missing compatibility regressions exposed by the extraction risk.
- [x] Extract pure matching and corpus/coverage responsibilities with the same cache instances and shallow-copy semantics; preserve public names and signatures.
- [x] Compare complete outputs and source/audit contracts, obtain independent review, and resolve substantive findings.
- [x] Run focused drug checks and full backend gates sequentially with tracked artifact hash checks; preserve all data and financial/clinical behavior.
- [x] Integrate the verified predecessor, publish and request task attachment for a focused PR, verify current-revision CI/review, and merge only after all gates pass.
- [x] Record evidence and advance to delivery E.

### Out of Scope
Routing/constraint/evaluation extraction (delivery E), semantic or clinical rule changes, canonical/API/cache redesign, generated corpus/manifest rewrites, new dependencies, deployment, and live service changes.

### Review
Preparation may run in parallel with frontend deliveries in this isolated worktree; integration remains B then C then D. The user approved the full hotspot plan and unattended execution with merging only after tests and independent review pass. Runtime edits begin after the concrete baseline/ownership review. The original `/opt/Bilun` checkout remains untouched.

Baseline/ownership review is complete before runtime edits: matching owns pure predicates/normalization/specialty/INN/ICD functions; corpus owns paths/loading/manifest/subsection coverage/promotion/stop conditions. All four original decorated caches and shallow list/dictionary identities remain contracts. The immutable comparator captures 54 line cases, nine full report contexts, all 968 corpus rules, detailed/canonical/legacy/cache/API projections and coverage, including full-corpus order permutations. A second monolithic capture is byte-identical (20,339,608 bytes; SHA256 `5c046be33ba9eccf305034baac29bc1b02ff9b7542fd1e272f4154e9a403d7c1`). It verifies loaded `bilun` and `src.bilun` modules originate inside this worktree (284 origins). The focused baseline passed 122 tests including two missing public cache/default-input contracts; 1,119 tracked artifact hashes remained unchanged. Evidence and executable comparator: `/root/artifacts/bilun-hotspot-refactor-2026-09-28/delivery-d`.

The extraction preserved all 47 original function ASTs and directly re-exports all 22 moved callables, including the four original cache objects, with no internal facade/billing dependency. The immutable complete payload snapshot is byte-identical after extraction. Independent source/runtime review found no actionable regression. Focused checks passed 858 tests; full backend passed 4,077 tests with eight warnings; full Ruff, isolated audit `--check`, compiler `--check` (134 byte-identical artifacts), and manifest parity (23 scanned, zero issues) passed. Hashes of all 1,119 tracked data/report artifacts are unchanged after every writer. These results apply to the isolated D source before integration on C main; publication and current-revision CI remain.

Delivery D publication: [PR #104](https://github.com/Safa675/Bilun/pull/104) at `79fefdcf` passed both hosted jobs in run `36486246248` and independent review, with no human or inline findings (Copilot reported quota exhaustion). It merged head-guarded as `ec368706047d3b3d95ddd5e76131825aa1f18940` at 2026-09-28 21:36:38 UTC; its tree equals the tested branch. Main CI run `36487251655` passed. The app attachment call did not return, so attachment is unconfirmed.

D was rebased onto C's merged main `20873ff6` without any source/test content change. The frozen full-output comparator remained byte-identical; the integrated tree passed 858 focused tests (three warnings), Ruff and isolated audit `--check`, with hashes of all 1,119 current tracked artifacts unchanged after each check. Relative to D's original A base, only the previously reviewed B report matrix provenance differs. C's merge-main CI run `36484758171` passed. D PR publication and current-head hosted CI subsequently passed, as recorded above.

---

## Task: Complete hotspot refactoring delivery C — section presentation decisions

### Goal
Give copay, strategy, drug review, and material presentation clear local ownership while preserving current payload precedence, row decisions, focus behavior and UI output, then deliver a separate verified PR after B.

### Subtasks
- [x] Review delivery C against the actual extracted code and tests; create an isolated branch at B commit `9a539d5d`, to integrate onto verified main before publication.
- [x] Add focused compatibility regressions and verify them against unchanged B components before rewiring those components.
- [x] Extract section-local copay/strategy models preserving existing overlapping filters, row order, first-row header selection, null/zero values, and shared `billingReportFields` behavior.
- [x] Make drug display states explicit and split substantial card/legacy/evaluation rendering while keeping section-owned refs, focus effects and the same precedence/array identity.
- [x] Split material tables into named local components while retaining simultaneous groups, order, source/coverage notices and empty/partial behavior.
- [x] Remove only the proven unreachable strategy override notice, after confirming overrides remain in their dedicated section.
- [x] Run focused tests, full frontend typecheck/tests/build, audit checks and artifact parity; exercise changing/unknown finding selection and drawers in the isolated browser preview.
- [x] Obtain independent implementation review, resolve findings and complete the hypothetical local-column-change walkthrough.
- [x] Integrate verified B main, publish and request task attachment for the focused PR, verify current-revision CI and reviews, then merge only after all gates pass.
- [x] Record evidence and advance to D.

### Out of Scope
Clinical or financial reinterpretation, new features/labels, payload or schema changes, removal of supported legacy data, new generic frameworks/dependencies, deployment, and live data/service changes.

### Review
The approved plan and read-only extraction review establish the five drug states (hidden, structured, legacy, evaluations, empty), first-non-insight copay header selection, per-row mixed shape handling, overlapping strategy categories with violations before claim rows, explicit zero-count preservation, and simultaneous material groups. Detailed scope is saved at `/root/artifacts/bilun-hotspot-refactor-2026-09-28/delivery-c-scope.md`. Worktree: `/root/worktrees/bilun-report-presentation`; branch: `refactor/hotspot-report-presentation`. B merged as [PR #102](https://github.com/Safa675/Bilun/pull/102), main `f63bb12b`, with successful main CI run `36482614267`.

Local C verification is complete against frozen source. Ten independently authored public-section compatibility cases passed on unchanged B before rewiring; after extraction, 41 focused tests and all 383 frontend tests in 65 files passed, as did final TypeScript and the production build. The 64 focused audit/source tests and isolated CLI `--check` passed. Both generated audit files are byte-identical to the B baseline, and hashes of all 1,119 tracked data/report artifacts remain unchanged. Independent source review matched 16 moved markup/helper bodies and found no local import cycles. Chromium passed 20 checks, ten per locale, on both the B baseline and C candidate; every case result is identical, with no page errors or unexpected APIs. The preview used actual patient-page content and synthetic intercepted APIs in a minimal embedded shell; it does not claim production data or full-shell visual coverage. The local-column walkthrough found `MaterialKdvReviewTable` owns its own header/cell rendering and focused test; the owning section's availability, order and other seven renderers need no change. Evidence: `/root/artifacts/bilun-hotspot-refactor-2026-09-28/delivery-c`.

Delivery C publication: [PR #103](https://github.com/Safa675/Bilun/pull/103) at `b5bae476` passed hosted frontend/backend CI run `36483840115` and independent review, with no human or inline findings (Copilot reported quota exhaustion). It was merged head-guarded as `20873ff6e66e75bb3d95b0af5206d58fe6d8d788` at 2026-09-28 21:14:27 UTC. Its merge tree matches the tested source tree. Main CI run `36484758171` passed. The app artifact attachment call is still pending; do not assume attached.

---

## Task: Complete hotspot refactoring delivery B — report section extraction

### Goal
Move each existing report section into its owning module while preserving public imports, markup, behavior, and verified audit provenance, then publish and merge the independently reviewed PR after all gates pass.

### Subtasks
- [x] Confirm the approved plan and unattended authorization; use an isolated branch from merged delivery A at `63df008d` with successful main CI.
- [x] Review the 23-export inventory, helper ownership, source-resolver fixture dependency, and frontend verification requirements before implementation.
- [x] Move the 19 existing report components and genuinely shared helpers into `billing-report/`, preserving bodies and client boundaries; retain explicit named exports at the original module.
- [x] Adapt the real-extraction audit fixture to the new source graph without weakening full-output/evidence assertions.
- [x] Compare candidate audit outputs and record only explained provenance changes; verify tracked artifact hashes.
- [x] Run focused audit checks and full frontend typecheck, tests, and build; exercise the required focus/highlight/drawer/locale/partial-state flows in an isolated browser preview.
- [x] Obtain independent implementation review and resolve substantive findings; complete diff/scope checks.
- [x] Commit, check CI before push, open and attach the focused PR, verify current-revision CI/review, and merge only after all gates pass.
- [x] Record PR/revision/verification and advance to delivery C.

### Out of Scope
Section decision cleanup (delivery C), drug engine changes, general type/schema restructuring, changes to UI or financial/clinical behavior, new dependencies, deployment, live cache/data updates, and unrelated user edits.

### Review
The existing approved plan and fresh export/helper/fixture inspection define this mechanical delivery. The user authorized unattended B–F completion and merges after tests and independent review pass. PR #101 was already merged by `Safa675` when this run resumed; its merge commit is `63df008d9ac91564247b53c83231d283754931ce`, and main CI run `36479428919` passed. The original `/opt/Bilun` checkout and its uncommitted work remain untouched. Worktree: `/root/worktrees/bilun-report-sections`; branch: `refactor/hotspot-report-sections`.

Local verification is complete at source/artifact commit `1dc0b239`: 19 component modules and shared helpers preserve all 23 facade exports and all 29 original declarations (independent AST comparisons). Baseline frontend checks passed 102 tests; final TypeScript, all 373 tests in 64 files, and production build passed. All 64 focused audit/source tests and isolated CLI `--check` passed. Only the matrix changed among 1,119 tracked artifacts: 17 added source-path occurrences across 16 of 97 rows, with every non-provenance field and all Markdown bytes unchanged. No package/lockfile changes remain.

Publication/integration: [PR #102](https://github.com/Safa675/Bilun/pull/102), head `9a539d5d`, passed hosted CI run `36481871547`. Final GitHub review fetch found no human or inline findings; Copilot reported exhausted review quota, so independent agent review provides the completed review evidence. Merged with a head-SHA guard as `f63bb12b1568f5cc02632cdeccff728a6ec9ea54` on 2026-09-28 at 20:55:32 UTC. Main CI run `36482614267` passed. Release Hold remains unchanged; no deployment occurred. The primary checkout remains on main with its original uncommitted edits preserved.

Independent structural review found no import cycles, reverse facade dependencies, or changed declarations. Playwright/system Chromium passed 14 interaction/state checks across English and Turkish, including selected-finding focus and viewport visibility, action-to-invoice highlighting, clause fetching/closing, 390px table scrolling, and exact-empty/partial-noncoverage/collapsed-legacy states. The isolated preview used the actual patient-page content and matching source hashes with intercepted synthetic APIs, `embedded=true`, a minimal provider/layout shell and fallback font; it does not claim production backend or whole-shell visual verification. Logs, scripts, hashes, parity results, and screenshots are under `/root/artifacts/bilun-hotspot-refactor-2026-09-28/delivery-b`.

---

## Task: Fatura uyumluluğu ekranını faturalama görevlisi için anlaşılır hale getir (2026-09-28)

### Goal
Mevcut eyleme dönük bulgular, Wave A inceleme gözlemleri, bilgi/izin kayıtları ve değerlendirme kapsamı hasta ekranında açıkça ayrışsın; her tekil kanıtın kimliği ve bağlantısı korunsun. Ayrıntılı kapsam ve kabul ölçütleri [UX planında](../plans/billing/2026-09-28-billing-officer-compliance-ux-plan.md).

### Subtasks
- [x] Mevcut hasta/kohort bileşenlerini, sayım kaynaklarını, sayfalama sınırını ve test kapılarını incele.
- [x] Ürün düzeni, güvenli gruplama, metin kataloğu, belirsizlik gösterimi ve doğrulama için ayrıntılı plan yaz.
- [x] Planı mevcut veri sözleşmeleri ve testlerle bağımsız olarak karşılaştır; yanlış toplulaştırma ve kayıp deep link risklerini plana işle.
- [x] Ürün planı gözden geçirilip onaylandıktan sonra uygulamaya başla.
- [x] Hasta inceleme sunum modeli, erişilebilir grup/ayrıntı etkileşimi ve seçili tekil kayıt bağlantısını uygula.
- [x] Yapısal/Wave A kapsamını, advisory bölümünü ve iki dilli açıklamaları güncelle; kohort ortak bileşen etkisini doğrula.
- [x] Odaklı davranış testleri, dar ekran yan menü kontrolü, masaüstü/mobil tarayıcı kontrolü ve tüm frontend CI kapılarını tamamla.
- [x] Son diff'i ve sayısal/finansal değişmezleri gözden geçir; incelemeye hazır yeni PR aç.

### Out of Scope
Kural motoru, backend/API/cache, finansal toplamlar, kohortta sayfalar arası gruplama, canlı dağıtım ve mevzuatın hukuki teyidi.

### Review
Plan, mevcut `ComplianceViewSection`, `WaveAEvidenceSection`, `CohortWaveAEvidenceSection`, veri tipleri ve frontend testleriyle iki bağımsız salt-okunur incelemede karşılaştırıldı. Hasta önizlemesi/kohort sayfalaması nedeniyle yalnızca yüklenmiş satırlara ait gruplama sayıları kullanıldı; tekil `evidence_id` bağlantıları korundu. Kullanıcı planı onayladı. Hasta 0043/0001 üzerinde masaüstü, 390 px mobil, klavye, sayfalama ve önizleme dışındaki seçili kayıt tarayıcıda doğrulandı; mobil yan menü tercihi masaüstünde korunuyor. Tam frontend doğrulaması: 64 Vitest dosyasında 373 test, TypeScript ve üretim derlemesi geçti. Backend/API/cache/kural kararları ve finansal hesaplar değiştirilmedi. İncelemeye hazır [PR #100](https://github.com/Safa675/Bilun/pull/100) açıldı; ilk [GitHub CI koşusunda](https://github.com/Safa675/Bilun/actions/runs/36469974065) backend ve frontend başarılı.

---

## Task: Implement hotspot refactoring delivery A and open a draft PR

### Goal
Make the surfacing audit follow supported patient component imports and named re-exports while preserving source evidence, then publish the verified first implementation delivery as a draft PR.

### Subtasks
- [x] Confirm the user-approved hotspot plan and create an isolated worktree on current main `46ae9fdf`, including the merged billing-officer UX work.
- [x] Capture the baseline audit output, focused tests, generated-artifact hashes, and relevant current source contracts.
- [x] Implement the bounded frontend component-source adapter and integrate it without changing application behavior or the later-phase map reader.
- [x] Add meaningful moved-component and missing/false-evidence regressions; preserve existing audit checks.
- [x] Independently review the implementation and resolve findings.
- [x] Run the applicable full backend gates, audit parity checks, and artifact-drift inspection; record results.
- [x] Check branch CI, commit and push the reviewed changes, open and attach a draft PR, and report its CI status.

### Out of Scope
Deliveries B–F, component moves, drug-rule changes, a general TS parser, new dependencies, production data/cache changes, merge, and deployment.

### Review
Implementation authorized by the user after review of `plans/refactor/2026-09-28-bilun-hotspot-refactor-plan.md`. Delivery A is published as [draft PR #101](https://github.com/Safa675/Bilun/pull/101), attached to this task; later deliveries remain tracked in the plan. Work is isolated from the original checkout and its uncommitted planning documents. Independent review's demonstrated false-evidence cases are fixed. Full backend verification passed **4,075 tests, 8 warnings, in 734.61s**, including all 38 new regression cases and the existing committed-output parity check. Reviewed regeneration adds evidence paths to 16 rows, preserving every other serialized field and Markdown bytes. Full Ruff, isolated direct CLI checks, compiler check (**134 byte-identical rule/manifest artifacts**), and manifest parity (**23 manifests, zero issues**) pass. The final 1,091-file artifact hash comparison found only the reviewed matrix change. Base CI was green before the first push; the branch had no failed runs. Hosted PR CI started at publication; current status is available on the PR. No merge or deployment was performed.

---

## Task: Reduce full-suite runtime without reducing coverage

### Goal
Publish a reviewed implementation PR that preserves every backend/frontend test and generated SUT artifact while making full-suite local runs faster and measuring the Polars thread setting on GitHub Actions before selecting its final CI value.

### Subtasks
- [x] Independently review and confirm this plan against the measured three-file prototype and the existing CI gates before implementation.
- [x] Apply safe C YAML loading with the Python SafeLoader fallback in the rule-source and deferral-table loaders, preserving fresh parsed objects and safe-tag behavior.
- [x] Resolve the unchanged all-rule source union once in a module-scoped immutable fixture, preserving all manifest cases and assertion expressions.
- [x] Document `POLARS_MAX_THREADS=1 python -m pytest -q --durations=20` as the standard full-suite local command and add CI duration reporting, leaving the first PR revision's CI thread setting unchanged; add no wrapper, dependency, or pytest bootstrap.
- [x] Review the final source/configuration diff independently, including loader semantics, fixture lifetime, command argument handling, and CI trial attribution.
- [x] Run the complete backend suite from an empty worktree-local cache and compare all 2,774 test identities and statuses with the investigation baseline; run Ruff, compiler `--check`, and manifest parity, requiring 134 byte-identical generated artifacts and no tracked data drift.
- [x] Run all frontend CI gates on the final branch: TypeScript, the complete 320-test Vitest suite, and production build, coordinating heavy local execution with the backend run.
- [x] Record reproducible local timing, exact validation evidence, independent review, and any limitations in the review section; inspect the final diff and check existing CI before each push.
- [x] Commit, push the new branch, and open and attach a draft implementation PR after independent diff review and the completed exact-prototype gates; overlap hosted CI with final-branch local confirmation, keeping the PR draft until final local gates and repeated CI validation pass.
- [x] After the uncapped PR revision is green, add the step-scoped CI thread trial as an environment-only workflow revision; repeat uncapped/capped GitHub Actions attempts with the same source changes, compare full-test and compiler steps, retain the measured CI choice, and record the final result without projecting local speedup onto CI.

### Out of Scope
Merging or deploying; touching the live database/cache; removing, skipping, narrowing, or weakening tests; xdist; broad resolver, artifact-writer, or cleanup refactors; changing production thread settings; changing generated rules/manifests or clinical/payment semantics.

### Review
Plan reviewed and confirmed before implementation. Independent review found no correctness issues: the three backend files have AST parity with the measured prototype, parsing retains the safe fallback and fresh objects, and manifest assertions and parameters are unchanged. [PR #95](https://github.com/Safa675/Bilun/pull/95) contains the implementation on `perf/full-suite-runtime`; no merge or deployment is part of this task.

Local gates passed: **2,774 backend tests, zero skips/errors/failures, 9 warnings, 569.13s pytest / 573.18s external**, with exactly the same ordered identities/statuses as the original baseline; Ruff; compiler check **134 artifacts byte-identical** (47.54s); manifest parity **23 manifests, zero issues**; frontend TypeScript, **55 Vitest files / 320 tests**, and production build. The backend began with an absent worktree-local cache, source/configuration hashes stayed stable throughout validation, and the worktree was clean afterward with no generated-data drift. The original local baseline was 1,024.55s; host activity varies, so local percentages are not CI predictions.

Hosted comparison retained identical installed dependencies, Python 3.13.15, runner image, and cache key. Two successful attempts per configuration ran all 2,774 backend tests and reproduced all 134 compiler artifacts:

| Configuration | Python test step (seconds) | Backend job (seconds) | Compiler step (seconds) |
|---|---|---|---|
| Original main, `7a6e854f` | 329 / 336 | 404 / 415 | 34 / 38 |
| Parser/fixture changes, default threads, `782fe49f` | 231 / 167 | 289 / 225 | 19 / 11 |
| Same source, CI one-thread trial, `61e63746` | 214 / 136 | 270 / 185 | 16 / 10 |

Final decision: retain **default CI threads** and the measured **one-thread local command**. The CI trial's ranges overlap substantially with default-thread runs, and unchanged compiler/startup paths also varied across runner regions; these samples do not establish an isolated CI thread-budget benefit. The parser/fixture improvement is retained, and CI now reports its slowest 20 phases. All existing backend/frontend/compiler/build gates remain enabled. Evidence: [baseline attempts](https://github.com/Safa675/Bilun/actions/runs/36152110893), [default-thread implementation attempts](https://github.com/Safa675/Bilun/actions/runs/36260747322), [one-thread trial attempts](https://github.com/Safa675/Bilun/actions/runs/36261536404). Raw logs, source hashes, case parity, and independent reviews are retained in `/root/artifacts/bilun-test-implementation-2026-09-26`.

---

## Task: Complete the deferred PR #89 Wave A groups in one verified release (2026-09-27)

### Goal
Cover all 25 deferred detector/engine groups (18 focused and seven broad) through canonical, single-evaluation patient/cohort projections, with each authored outcome honestly classified. Ship in reviewable checkpoints on one integration branch, then activate once after a validated cache rebuild and verify the live patient and cohort experience. This is group coverage, not a claim that every possible authored rule ID fires in live data. PR #96's post-merge CI and Deploy completed successfully before this task began.

This is an explicit user-approved expansion of the original strict Wave A filter: mixed monetary outputs use existing financial sections and informational outputs use review-only presentation. Do not label those rows unpriced violations merely because their engines appeared on the deferred candidate list.

### Locked decisions from the grilling interview
- Keep the ten excluded synthetic `kind:<callable>` identities outside this release and report them honestly.
- Compliance contains only eligible, unpriced violations; positive actions are evaluations, review-only outcomes remain outside violation counts, and missing inputs remain unavailable rather than a clean pass.
- Preserve detector decision semantics; add status/skip metadata as needed. A wrong detector is held for a separate focused correction, and the combined release waits for that blocker.
- Give every distinct finding and per-line evaluation a stable source/line identity across patient, cache, cohort, API, and UI. Never collapse multiple rows into one claim identity.
- Show financial-only outcomes in existing patient and cohort financial/recovery sections with separately labeled billed/risk/uplift values and verified source/basis. If provenance or amount is unverified, show an honest review/unavailable state rather than a sourced or confirmed number. Keep existing savings/recovery totals byte/value-equivalent and do not double count or invent zero amounts.
- Show actual findings plus compact evaluated/unavailable summaries, not the full static ID catalog. Verify all cached rows and representative live triggers; use synthetic per-rule tests for rare rules with no live positive case.
- Validate the rebuilt cache and cohort before one user-visible activation; block unexplained financial drift, identity collisions, or finding-count changes; provide a tested rollback to the previous version/cache.

### Release checkpoint, 2026-09-27

The exact-main receipt preflight exposed a separate historical identity: the live PR98 serving cache has build `b1fdcb54` from code `b08c4797`, while the independently rebuilt same-input corrected baseline has build `8065e1d8` from PR98 code `4af38b28`. The issuer currently requires one baseline build ID and identical cache bytes for both, so it cannot sign honestly. A focused follow-up must preserve both identities, verify type-sensitive equality of every legacy content table between the protected serving cache and rebuilt baseline, tie that bridge to the observed old cache, and recheck both caches before receipt issuance. A changed row, missing row, malformed build, or drifted cache must block signing. After merging the correction, rebuild all candidate artifacts from its new exact `main` SHA before activation.

The follow-up now also rejects uncheckpointed DuckDB WAL sidecars at each cache hash, after independent review showed that a read-only query could otherwise observe committed rows absent from the pinned main file SHA. Crash-WAL and broken-symlink regression tests cover the trust boundary. Keep Wave A held until this correction is reviewed, merged, and re-attested from the exact new `main` SHA.

The final route/rollback review found three trust-boundary gaps and one product gap, now addressed in the integration branch. The release transaction checks both the route loaded by Caddy and the Caddyfile installed for restart; recovery reinstalls the barrier if old-route verification fails. Exact GitHub CI verification also requires the candidate SHA to remain current `main`. A protected old-pair recovery adapter seals the PR98 snapshot, stages independent backend/frontend/cache copies, and records a new PID-bound tuple after restart. Mixed cohorts now retain available evidence rows and show selected/available/unavailable coverage rather than suppressing the whole cohort.

Premerge proof at `f4daa876` includes a successful 50-patient/94-bill private candidate-pair Caddy rehearsal after rebuilding the frontend with its build-time API rewrite to port 8002. The new protected old-pair manifest and staged copy passed byte and WAL checks; its real launcher passed an isolated network-namespace rehearsal with all 50 patient and 94 bill legacy API payloads plus frontend assets matching the PR98 equivalence report. These checks are **nonactivating**. The currently pushed `5980538b` PR #97 head has green backend/frontend hosted CI; the new local integration changes still require their own exact-head CI, final merge SHA build, signed receipt, supervised rollback/public barrier verification, and live sign-off. Wave A remains inactive.

PR #98's EK-3B correction is merged and serving, with a protected old runtime/cache/environment snapshot. Draft PR #97 contains the 25-group patient, bill, cohort, API, and UI integration. Production Wave A remains inactive. A traced candidate build for the earlier `a7754c1c` head passed all-cache structural and same-input legacy/financial parity on 50 patients and 94 bills, and a real old/candidate private Caddy rehearsal restored the old pair. That artifact is **not** a release candidate for later code heads.

The release implementation now has a signed startup receipt, exact main-CI issuer, private candidate launcher, actual loaded-Caddy route adapter, old/barrier/candidate route preparation with retained old static assets, a sealed manifest producer, concrete public/private HTTP probes, and a journaled activation/recovery CLI. These are code checkpoints, not activation evidence. The old serving backend still lacks an in-memory code SHA, so the release uses protected byte/behavioral equivalence and keeps that limitation explicit. Final code must still be merged, rebuilt from the exact main SHA, privately rehearsed again, signed only after all independent gates, and switched through the public barrier with rollback verified.

The previous PR #97 head `29e21241` had a red backend CI run because the rule-surfacing audit still looked for the old capability string. The audit now requires the signed startup check and draft cache; its 26 tests pass, including removal-of-signature rejection. A local full suite at the previous head produced 3,988 passes and exactly those 11 audit failures in 889 seconds. After the fix, 224 focused deploy/API/audit tests, Ruff, and manifest parity passed; generated rules and the next hosted CI run remain pending. Never treat the draft PR, an earlier candidate, or a prepared route manifest as authorization to change the public route.

### Subtasks
- [ ] Reconcile all 25 groups: the historical PR #89 baseline has 516 hidden static inventory identities (20 focused entries including a synthetic radiation grouping, plus 496 broad authored IDs) and 526 possible runtime IDs (30 focused plus 496 broad). After source-backed corrections, track 32 focused identities across 18 groups, of which 29 can currently emit rows: #9 and #22 are unavailable until missing dates are ingested, the unsupported hyperthermia grouping cannot emit, and two distinct radiation course candidates were added. Keep the 496 broad authored identities separate from claims of live evaluability. Check emitted IDs, source rows, `billable`/review semantics, input availability, stable identity, monetary paths, and the ten explicit exclusions.
- [ ] Capture baseline code/data identities, financial totals, current patient/cohort payloads, and active cache build ID without changing production state; record representative and negative cases.
- [x] Write detailed focused, broad, and financial/release architecture maps in `plans/billing/`; independently review and approve this task plan and those maps before production code changes.
- [x] Inventory the four flat-only monetary focused outputs from their detector results and patient-report totals before implementing their display; identify exact amount basis, source strength, and whether they currently participate in headline calculations.
- [ ] Extend the canonical finding/evaluation contract with per-rule outcome classification, stable distinct finding/evaluation identities, honest missing-input/skip status, source evidence, review-only status, and a separate typed financial projection while preserving detector decisions.
- [ ] Integrate the 18 focused groups into one-pass evaluation, including explicit classification of the four money-bearing groups and source-derived identity for multirow detectors; add group-level regressions.
- [x] Correct the duplicate-exam ten-day false negative in a separately reviewed detector change, with A/day1 and two B/day2-3 line regressions and unchanged existing cases.
- [x] Resolve the admission 60-day detector's use of service-range end as a purported submission date: official handbook and current SUT do not support the old inference; legacy false emission removed and a per-claim unavailable evaluation added for the missing period-closure date (`5af8985a`; 35 targeted tests/Ruff and independent review passed).
- [x] Correct Tablo 15 #22's mismatch predicate separately: the official handbook concerns an outpatient exam date versus acceptance date, which is not ingested; false inpatient/procedure-date emissions are removed and per-claim unavailable status records the missing input (`632fc517`; 57 targeted tests/Ruff and independent review passed).
- [x] Correct the donor detector's unreachable category branch from official El Kitabı §4.2/Table 15 #24: same-claim donor-preparation evidence now flags distinct exam lines as review-only, with no claim of confirmed MEDULA donor identity (`e22f0261`; 34 direct/provenance tests and Ruff passed).
- [x] Correct the dental GA zero/credit-only anesthesia false positive in a separately reviewed detector change, without inferring a missing uplift.
- [x] Correct yatak zero/credit-only bed false positives and non-ICU evidence attribution separately, preserving the existing bed-day financial calculation (commit `9689247f`; 22 direct tests and Ruff passed; independent review approved).
- [x] Correct radiation predicates against current EK-2B explanatory cells: design, planning, dose, device, application, and session limits now use source-backed review evidence, grouped multi-day quantities are not treated as confirmed same-day excess, and billed amount stays separate from null unverified risk. Distinct 800370 and 800430 course identities were added; unsupported hyperthermia grouping is unavailable. Detector/direct integration passed 49 tests and Ruff with independent source/diff review (`e0ca7875`). Full inventory/report/cache parity remains a release gate.
- [x] Correct the dental precious-metal matcher in a separate Q9 detector checkpoint: reject term-local negations such as `altın içermeyen`, `platin içermeyen`, and `altınsız`, preserve independently affirmative metal/product matches and first-winner/raw ordering, and verify real material-line regressions against the official July/August 2026 §2.4.1(1) source evidence before promotion (`2ee13b08`; 102 targeted tests/Ruff and independent review passed). Free-text ambiguity remains a classification hold.
- [x] Correct EK-3B-1/2 false findings in a separate, independently reviewed checkpoint: separate lexical candidates from matched/not-matched/unavailable annex applicability; honor sterile-glove, inpatient syringe and blood-strip, dressing oxygen, and viscosupplementation exceptions; preserve ordinary glove, urine-strip, and inflow-catheter cases. Use actual owned claim/header facts, clear stale derived flags, expose nullable regulatory status without changing package CSV flags, and require resolved eligibility before any material uplift. Prove dictionary/typed validator, pricing DTO, precheck, uplift, source-line identity, and full patient/bill/cohort financial deltas. If legacy money changes, merge this correction separately and recapture the same-input Wave A baseline before release; never waive financial parity.
- [x] Keep the EK-3B reference catalog source-only: mark entries not evaluated for a patient, preserve conditional exceptions, remove the unsupported effective-date display, and avoid blanket non-reimbursable labels. Retain its collection keys for compatibility and test the rendered explanation.
- [ ] Classify transplant carveouts, missing monetary source/basis, and unverified dental uplift as review/unavailable with null confirmed amount, preserving existing patient/cohort totals.
- [ ] For line-owned financial reviews, show an observed billed charge only when it is reconciled to the exact procedure claim line, with a distinct source/basis field; keep unverified risk or recoverable uplift null and outside all totals. Independently match the observed charge against pinned procedure Parquet before activation. Dental claim-level expected fee remains unavailable as net recovery without a verified basis.
- [ ] Freeze and independently review the exact 496-ID broad classification matrix: source authority/version, authored action meaning, predicate sufficiency, claim-field provenance, proof or withholding gate, and stable reason for every ID, including all 31 `ai_generated_pending_review` rows; retain raw parity and fail closed when an authored condition/action/source digest changes.
- [ ] Integrate the seven broad engines with rule-level authored-action classification and status metadata; account for every authored ID as eligible finding, positive, review, monetary, or unavailable without blanket conversion to violations.
- [ ] Carry canonical nonfinancial, review-only, and financial projections through patient report, cache, cohort index, API, and old-cache fallback; prove identity parity and bounded honest status summaries without new aggregate money.
- [ ] Persist each bill's exhaustive v2 evidence in a separate build-scoped table keyed by `patient_id::claim_id`; keep default bill JSON bounded, validate exact bill/detail key sets and claim ownership, and reconcile bill previews/coverage against its own detail. Do not equate a bill slice with patient evidence filtered by claim when cross-claim context can differ.
- [ ] Reconcile the existing `validate_claim()` public `violations`/validity contract with typed positive/review outcomes; migrate its API, chatbot, frontend validator, and tests together so public counts no longer call permitted or informational actions violations, retaining a documented compatibility path.
- [ ] Render eligible findings and review-only statuses in the existing patient/cohort Compliance UI and sourced monetary outcomes in the existing patient/cohort financial sections; preserve links, pagination, and old-cache honesty.
- [ ] Update surfacing inventory and regression gates so the 25 groups are classified correctly, visible where eligible, and not double counted; retain the ten excluded synthetic identities.
- [ ] Implement a single-activation release gate according to `plans/billing/2026-09-27-wavea-release-gate.md`: listener-aware read-only discovery, protected and privately rehearsed **actually serving** old runtime/cache/effective env/Caddy tuple, and independently reviewed legacy-equivalence attestation without a fabricated old code SHA. Current P0 correctly blocks because old health lacks code SHA, frontend `.env` drifted after its listener started, and protected snapshots are missing.
- [ ] Build an immutable candidate backend/cache/frontend on private :8002/:3099 and verify it through a private :3100 route: stable source-byte manifest, all patient/bill/cohort payloads and financial/action parity, exact CI/code/frontend/build identity, old/new client and asset behavior, plus resource/duration evidence. Never alter :8001/:3000 or the public route during preparation.
- [ ] Replace the current frontend-first deploy with one Caddy maintenance barrier and one public route switch to the verified candidate pair, under a shared lock and fsynced recoverable journal. Recheck SHA/artifact/input identity immediately before switching; rehearse rollback to the old :8001/:3000 routes and restart from protected artifacts on disposable fixtures. Split the 25-minute workflow if measured preparation/recovery cannot fit without weakening same-SHA/stale-head guarantees.
- [ ] Run focused domain, API/cache, frontend, financial, and release-gate tests; then run full backend/frontend CI-equivalent checks, generated-artifact checks, and a no-drift financial snapshot comparison.
- [ ] Independently review the final source, classification, UI, and release diff; resolve all correctness findings and re-run affected checks.
- [ ] Check branch CI before pushes; publish reviewable checkpoint commits/PR, obtain final hosted CI and review feedback, then merge for one production activation.
- [ ] Verify the merged production deploy, active cache build, every cached patient/cohort payload, representative live findings and statuses, financial-path identity/amount labels, unchanged totals, and rollback readiness; record exact evidence and remaining limits.

### Out of Scope
The ten synthetic-identity rows previously excluded from Wave A; new clinical/regulatory rule decisions; new claim-data ingestion solely to make dormant authored IDs fire; changing existing savings/recovery totals; treating positive or review-only outcomes as compliance violations; activating partial checkpoints in production.

### Review
Plan independently reviewed and approved for staged implementation by three agents after correction of classification, identity-count, detector-correctness, retained-client, and deployment-timeout gaps. Product integration and production payload baseline capture remain pending. Latest main is `bbf9acaf` (merged PR #96); its [post-merge CI](https://github.com/Safa675/Bilun/actions/runs/36316401829) and [Deploy](https://github.com/Safa675/Bilun/actions/runs/36316669982) passed. The original read-only audit found 18 focused groups (20 static inventory identities, expanding to 30 possible emitted runtime IDs because radiation had 11 IDs) and seven broad engines (496 authored IDs) hidden. Subsequent correctness fixes changed the current focused tracked/emittable inventory as recorded above; these IDs are possibilities, not guaranteed live findings. Financial, positive, review, missing-input, and stable-identity classification must precede activation. A read-only synthetic baseline at `bbf9acaf` covers 50 patients, 94 bills, and 636 legacy validator rows; its 5.25 MB JSON is saved outside the worktree at `/root/artifacts/bilun-wavea-2026-09-27/baseline-synthetic.json` (SHA-256 `12cfec6940a2beae19de08881e56c88bd018bc166a24ee9e56f536317ff4f5b3`). Patient report baseline sums: SGK uplift/recoverable ₺348,340.41, audit exposure ₺673,902.64, action count 452; bill report financial sums match, with 563 bill actions. These are synthetic comparison fixtures, not production values. A read-only production `/health` response on 2026-09-27 reported `status=ok`, `database_reachable=true`, `cache_ready=true`, active build `b1fdcb54-0abb-426a-94fb-f00d006144a7`, and gazette version `2026-07-07`. This establishes only the health/build baseline; authenticated patient/cohort payloads and source-code identity still need capture before release. A read-only unauthenticated request to `/api/compliance-index?limit=1` returned HTTP 401, so the health response is not a substitute for private payload verification.

Checkpoint commits on the integration branch: `c19293ff` adds seven real line IDs and fixes duplicate-exam matching (independent review, 46 focused tests/Ruff); `f45f7f54` adds stable per-line evaluation IDs through patient/cohort and fixes mixed old/new dedup (independent review, 82 targeted tests/Ruff); `f64ee242` records the reviewed plan and four-group financial inventory; `845f6850` freezes all 496 broad corpus IDs with conservative candidate classifications (independent review, 15 tests/Ruff); `d46dc53b` verifies canonical finding IDs and fails on conflicts (independent review, 25 cohort/API tests/Ruff); `f553edb0` fixes zero/credit-only dental anesthesia false positives (independent review, 18 direct tests/Ruff). All commits are local; the 25-group product, public API/UI, full release gate, full CI, merge and live verification remain outstanding.

Further reviewed local checkpoints: `9689247f` corrects ICU-overlap charge/evidence attribution; `8acce3ab` adds 42-ID information-only payment traceability metadata; `5af8985a` and `632fc517` remove false #9/#22 date verdicts and add unavailable-status helpers; `e22f0261` corrects donor same-claim evidence; `e0ca7875` aligns radiation review candidates with current EK-2B and leaves excess risk null. Read-only release-host findings are recorded in `reports/rule-engine-surfacing/2026-09-27-wavea-host-preflight.md`. These remain local checkpoints, with no public activation.

`0151aeec` adds an independently reviewed, still unintegrated focused adapter for all 18 groups: 32 tracked identities, 29 presently emittable, source-owned line IDs, quarantined stale #9/#22/hyperthermia rows, explicit missing/unavailable statuses, and no confirmed financial amount. Final focused and existing El Kitabı tests passed 28 cases with Ruff. The public report/cache/UI remain unchanged until the later integration checkpoint.

`3b801e9e` subsequently integrated the 18 focused groups into the canonical patient/bill report in one detector pass. The 50-patient/94-bill same-input synthetic comparison against the `bbf9acaf` baseline found **0/50 patient and 0/94 bill differences in legacy report fields**, with unchanged ₺348,340.41 SGK/recoverable sums, ₺673,902.64 audit sum, and 452 patient/563 bill action counts. The separate focused-evidence checkpoint now adds source-linked review and null-amount financial rows, exhaustive 32-ID status detail in a build-scoped patient table, exact cohort counters and sparse paginated review/financial rows, and draft-gated API/old-cache fallback. Its cache trial wrote 50 patient detail rows and one index alongside the 50 reports/94 bills in 122.48 seconds wall time, using about 1.05 GiB peak RSS. The 50-patient detail has 52 review rows and no financial trigger; an additional real-detector fixture verifies both review and financial rows through patient/bill/cache/cohort APIs. Rebuilding the sparse index from those detail blobs produces 52 rows in a 285 KB JSON singleton. Current default patient JSON averages 83 KB; trimming the 32 focused statuses from that default is the next bounded-payload checkpoint. The draft cohort fallback measured 171 ms median across the 50 reports versus 21 ms for a stored-index slice; it stays fail closed on missing/corrupt index or rows. The focused evidence/API/cache suites passed **118 tests**, changed-file Ruff and diff check; a production app integration test also verified unauthenticated 401 and authenticated 200 for all new evidence endpoints. This is an independently reviewed draft-only checkpoint; the seven broad groups, UI, complete-25 attestation, full CI, and release gate remain pending.

`3daf489b` wires all 25 groups into report/cache/API as draft-only evidence, including 50 patient and 94 independently scoped bill details. The matched-input build used four-row bill-detail writes and completed in 126.28 seconds with 1,448,152 KB peak RSS, versus 131.46 seconds/1,654,232 KB before streaming and 122.48 seconds/1,097,784 KB for the focused-only build. Default JSON averaged 65.3 KB per patient and 46.0 KB per bill. Legacy report fields differed in 0/50 patients and 0/94 bills; SGK ₺348,340.41, audit ₺673,902.64, and 477/638 current patient/bill actions were unchanged. The 528-rule, 25-group evidence is still unavailable publicly until independent source/financial/rollback attestation and one activation pass.

---

## Task: Correct EK-3B annex applicability before Wave A activation

### Goal
Prevent EK-3B-1/2 lexical matches from becoming unsupported billing violations, reimbursement decisions, or material uplift; preserve exact source-line ownership and record any resulting financial baseline change separately.

### Subtasks
- [x] Pin and compare official SGK July/August 2026 annex workbooks, extract the exception rows, inspect current SGK notices, and document the limit of historical service-date applicability.
- [x] Audit every existing consumer of EK-3B match flags and money, including legacy validator, material pricing, patient/bill precheck, uplift, and cohort totals; record the before-change baseline boundary.
- [x] Define an immutable tri-state annex assessment (`matched`, `not_matched`, `unavailable`) with candidate row, match kind, and stable reason; keep lexical matching separate and expose only confirmed candidates through old boolean helpers.
- [x] Apply the source exceptions and use/setting qualifiers to both dictionary and typed paths: surgical sterile gloves; inpatient disposable syringes; inpatient blood-sugar strips without broadening that condition to urine strips; dressing-only oxygen; conditional viscosupplementation; preserve ordinary gloves and exact inflow-catheter matches.
- [x] Recompute nullable regulatory flags from actual claim/header facts, clear stale derived flags, and keep the independent package CSV `is_bundled` fact unchanged. Legacy material pricing and API DTOs must distinguish unknown from reimbursable or excluded.
- [x] Keep unresolved or fuzzy-only annex matches out of material uplift; require affirmative resolved eligibility, with regression cases for source-line ownership, duplicate names, code-resolved candidates, stale flags, and missing care/clinical-use facts.
- [x] Run focused suites, full financial patient/bill/cohort comparison, Ruff and generated-artifact checks; independently review the correction and publish it as an isolated checkpoint/PR if existing decisions or money change.
- [ ] Rebuild and pin a new same-input Wave A baseline after the correction is merged, then keep the combined 25-group activation blocked until full-cache parity and rollback gates pass.

PR #98 merged at `4af38b28` after green hosted backend/frontend CI; the synthetic patient/bill/cohort financial trees remained unchanged. Its production deployment and post-merge baseline capture remain separate Wave A release gates.

### Out of Scope
Changing package CSV flags, inventing clinical use or care setting, promoting unknown materials to payable, changing unrelated monetary rules, or treating the 2026 annex file name alone as proof of every earlier service interval.

### Review
The interface and consumer boundary were reviewed before edits against the pinned annex rows and the read-only monetary impact audit. The official consolidated announcement and current GSS listing were checked on 2026-09-27; historical service-date applicability remains a source-manifest gate.

---

## Task: Fix PR #94 CI after repricing removal

### Goal
Make PR #94's backend CI pass by reconciling the committed registry-coverage artifact and cohort-tier test with the retired repricing rule, without changing service-date pricing or unrelated coverage data.

### Subtasks
- [x] Remove only the obsolete `gazette_repricing` row from `sut_registry_coverage.parquet` and verify every remaining row equals the current registry-derived summary.
- [x] Update the cohort-tier test to the current 8/16/26 split and assert former demo patient 0011 is no longer Tier A.
- [x] Run the exact backend CI gates on the final branch: Ruff, full Python test suite, rule compiler artifact check, and manifest parity audit; inspect binary/test diff.
- [x] Commit and push the fix to PR #94, then confirm the new CI result.

### Out of Scope
Restoring the repricing algorithm, broad synthetic regeneration, other SUT coverage changes, PR merge, deployment, or production cache rebuild.

### Review
Local verification passed on the narrow fix: Ruff; full Python suite **2774 passed, 9 warnings**; rule compiler `--check` found **134 byte-identical artifacts**; manifest parity scanned **23 manifests with 0 issues**; targeted registry and cohort-tier suites passed. The parquet change contains only the obsolete registry row removal, with all 46 survivor rows/schema/order unchanged. Full pytest and an interrupted duplicate compiler check temporarily rewrote unrelated drug manifests; their generated changes were cleaned before commit. Fix commit `10d04811` was pushed to PR #94; GitHub CI run `36150469229` completed successfully for backend and frontend.

---

## Task: Publish gazette repricing removal PR

### Goal
Put the completed and verified removal on a fresh branch from current `origin/main`, then open a reviewable PR containing only that removal.

### Subtasks
- [x] Confirm the old PR #92 branch is merged and choose a fresh branch from current `origin/main`.
- [x] Audit and commit the removal patch without unrelated or sensitive additions.
- [x] Transfer the commit to a fresh `origin/main` branch; resolve any conflicts and verify the resulting diff and focused checks.
- [x] Push the branch, open and attach a PR, and confirm its commit/file scope.

### Out of Scope
Merging the PR, deploying, rebuilding production caches, or adding a replacement pricing rule.

### Review
Opened PR #94 on `fix/remove-unsupported-gazette-repricing` against current `main`; the first PR commit contains only the 70-file repricing-removal patch and no older PR #92 commits. Fresh-branch verification: 104 focused backend tests passed (one existing pytest deprecation warning), 134 remaining rule/manifest artifacts were byte-identical, surfacing audit check and Ruff passed, and the worktree/diff were clean before publication. No deployment, production cache rebuild, or merge was performed.

---

## Task: Remove unsupported post-service gazette repricing rule

### Goal
Remove the 30-day price-staleness opportunity from Bilun's runtime and product surfaces so no later SUT tariff increase is shown as recoverable for an earlier procedure.

### Subtasks
- [x] Inventory all runtime, API, frontend, registry, compiler, synthetic, test, and generated references; lock the deletion boundary.
- [x] Remove the detector, billing adapter, runtime registration, rule metadata, opportunity fields and totals, and API projections without changing service-date price lookups.
- [x] Remove patient/cohort UI sections, deep links, translations, frontend types and tests for the opportunity.
- [x] Remove dedicated fixtures, synthetic scenario generation, demos, tests, and generated rule/audit artifacts that specifically advertise repricing.
- [x] Update current architecture/coverage documentation so it no longer claims this rule is implemented; leave historical plans/reports identifiable as historical when appropriate.
- [x] Verify no live repricing references remain, run focused backend/frontend checks and relevant generated-artifact checks, and record results.

### Out of Scope
Changing valid temporal EK-2/B or EK-2/C lookups, adding a replacement pricing detector, editing unrelated SUT rules, regenerating all synthetic cohort data without a dependency need, deployment, or production cache rebuild. PR publication is tracked separately above.

### Review
Removed the post-service repricing evaluator, billing adapter, API/report/cohort fields, registry/compiler entry, patient and optimizer UI, translations, synthetic demo, and current documentation claims. Historical EK-2/B and EK-2/C service-date price lookups remain. Removed the dedicated rule source/compiled JSON/empty manifest/golden and regenerated the rule-surfacing audit matrix and report. The checked-in synthetic cohort was already out of sync with a pristine-HEAD regeneration, so only retired scenario tags, one demo workbook column, and one obsolete metadata row were mechanically scrubbed from its binary artifacts; all other logical records/cells were verified unchanged.

Verification: backend focused suites 139 passed; synthetic billing 22 passed; frontend focused Vitest 63 passed and `tsc --noEmit` passed; temporal pricing 2 passed; synthetic validator and Tier A assertion passed; rule compiler `--check`, surfacing inventory `--check`, changed-file Ruff, compileall, and `git diff --check` passed. A broader `tests/unit` run reached 231 passed with no failures, then was interrupted because it was still at 7% after two minutes. No deployment or production cache rebuild was performed.

---

## Task: Phase 5 Checkpoint 4 — loop-complete closure metadata

### Goal
Record truthful loop-complete metadata for the verified Checkpoint 4 without modifying production code, tests, generated audit artifacts, plans, or configuration.

### Subtasks
- [x] Replace pending-commit closure status/phase/status values with truthful `loop_complete` wording.
- [x] Record the exact final acceptance results, artifact-hash reconciliation, added-line secret/patient-data scan, and temporary symlink check.
- [x] Preserve empty blockers, explicit exclusions/deferred Wave B/C/D scope, and the no-push/no-merge/no-deploy/no-cache-rebuild boundary.
- [x] Run JSON parsing and `git diff --check` after the metadata-only update.

### Out of Scope
Production code, tests, generated audit artifacts, plans, configuration, detector medical semantics, new detector migrations, projection rule-ID allowlists, registry dispatch changes, pricing or financial behavior, production cache rebuilds, commits, pushes, PRs, merges, deployments, and deferred Wave B/C/D or broad prose-family candidates.

### Review
Loop is complete and verified. Final acceptance evidence is focused inventory `17 passed in 2.53s`; authoritative combined backend `272 passed, 1 warning in 32.46s`; frontend `4 passed files, 29 passed tests`; `npx tsc --noEmit` exit 0; generator `--check` exit 0; compileall exit 0; `git diff --check` exit 0; artifact hash reconciliation pass; added-line secret/patient-data scan pass; and temporary frontend/node_modules symlink absent. Blockers are empty. Deferred Wave B/C/D and broad prose-family candidates remain outside scope and require separately approved future scope. No push, PR, merge, deploy, or production cache rebuild occurred; no commit was created. This loop is ready for the acceptance commit, but no further action is required in this loop.

---

## Task: Phase 5 Checkpoint 2 — generic cohort/cache/API projection

### Goal
Project all five supported canonical nonfinancial `RuleFinding` rules through existing patient/bill cache payloads, the generic cohort compliance index, and existing API routes with stable identity, honest evaluation availability, and unchanged financial totals.

### Subtasks
- [x] RED→GREEN: add the smallest cohort regression proving a selected Wave A canonical finding was rejected, then remove the K21/K26 product gate with generic fail-closed serialized-contract validation.
- [x] Remove the rule-ID allowlist and consume canonical serialized findings/evaluations generically without duplicating per-rule mappings, rebuilding finding IDs, or calling detectors.
- [x] Preserve canonical `finding_id == action_id` and validate patient/claim/line ownership and generic line-kind source identity across patient → cache → cohort → API.
- [x] Carry canonical finding fields needed by patient/bill/cohort consumers, including identities, detail/source/severity/evaluation metadata, existing display fields, and null money, while collapsing exact duplicates.
- [x] Aggregate evaluations generically by `(rule_id, claim_id)` so distinct claim evaluations and missing-input statuses are retained; keep missing top-level cache artifacts unavailable rather than fake zero.
- [x] Extend synthetic cache/API regressions for Wave A visibility, future-rule passthrough, stable line-kind IDs, duplicate collapse, null money/unchanged totals, invalid-row fail-closed behavior, and K21/K26 compatibility.
- [x] Run required domain/cache/API tests, compile changed Python files, enforce the no-allowlist/no-ID-rebuild invariant, and run `git diff --check`; record exact evidence in the checkpoint journal.
- [x] Set state to `checkpoint2_accepted` after independent Chief review.

### Out of Scope
Frontend changes, detector-set expansion or medical logic changes, audit generator/matrix/report changes, pricing formulas or financial semantics, DuckDB schema migration, new API routes, deployment or production-cache work, source dirty work, commits, pushes, PRs, merges, and any rule outside the five canonical rules.

### Review
Checkpoint 2 is accepted by Chief. `cohort_compliance.py` now projects serialized findings/evaluations generically with no rule-ID allowlist and no finding-ID reconstruction; canonical IDs are copied unchanged, future well-formed rules pass through, exact duplicates collapse deterministically, and evaluations retain distinct `(rule_id, claim_id)` statuses. Existing cache/API routes and payload JSON were reused without schema migration or cache rebuild. Independent verification: `255 passed, 1 warning` for all billing-domain tests plus claim-compliance and compliance-index API suites; financial invariance `4 passed, 1 warning`; compileall, `git diff --check`, and the forbidden-symbol invariant passed. Audit generator/matrix updates remain intentionally deferred to Checkpoint 4; frontend work is authorized next as Checkpoint 3.

---

## Task: Phase 5 Checkpoint 1 — canonical finding contract + domain plumbing

### Goal
Implement one canonical nonfinancial rule-finding evaluation path for K21, K26, `tablo15_10`, `tablo15_20`, and `tablo15_5`, preserving legacy analyzer output while making patient claim-compliance projection reuse the precomputed batch.

### Subtasks
- [x] RED→GREEN: add deterministic claim/procedure/drug/material finding identity and typed `RuleFinding` / `RuleEvaluation` / batch contract.
- [x] RED→GREEN: add canonical one-pass evaluation for exactly the five authorized detectors, including explicit missing-input evaluations, ownership validation, normalization, de-duplication, deterministic ordering, and null money.
- [x] RED→GREEN: route `analyze_claim` through the canonical evaluation for the five detectors while preserving legacy flat violations and detector order/fields.
- [x] RED→GREEN: make `compute_patient_billing_report` evaluate the batch once and make `project_claim_compliance` a pure projection with zero detector/analyzer calls.
- [x] RED→GREEN: surface the three selected Tablo 15 findings in patient `claim_compliance`, preserving K21/K26 identity/serialization compatibility, duplicate handling, missing context behavior, and unchanged financial totals.
- [x] Run the required focused suites, compileall, and `git diff --check`; record exact RED/GREEN and final verification evidence in the checkpoint journal.
- [x] After all tests are green, update checkpoint state and complete this review section with exact changed paths/results.

### Out of Scope
New Wave A cohort visibility, API/schema/route changes, cache schema changes, frontend work, audit generator/matrix/report changes, pricing/totals semantics, detector medical/regulatory semantics, deployment, production cache rebuild, pushes, merges, and migration of any detector outside the five authorized rules. A minimal existing-K21/K26 cohort compatibility fix was accepted because canonical five-component IDs otherwise regressed across patient and cohort projections.

### Review
Checkpoint 1 is accepted by Chief. Canonical finding identity includes URL-quoted `line_kind` between `claim_id` and `line_id`; K21/K26 cohort projection preserves and validates that identity without surfacing the three Wave A rules yet. Compileall exited 0; focused domain/cohort/API verification passed `96 passed, 1 warning`; the full billing-domain plus claim-compliance API gate passed `244 passed, 1 warning`; `git diff --check` exited 0. Phase 5 Checkpoint 2 is now authorized; frontend work remains pending its acceptance.

---

## Task: Rule Engine surfacing audit + generic finding surface (2026-09-18)

### Goal
Execute `plans/billing/2026-09-18-rule-engine-surfacing-audit-plan.md`: produce exact runtime/visible/hidden/duplicate/financial counts and the complete hidden-rule list before migrating additional existing rules into a generic finding surface.

### Subtasks
- [x] Freeze audit definitions and baseline: registry family, runtime detector, finding kind, visibility, duplicate, and money semantics.
- [x] Build a deterministic static inventory of `analyze_claim` and `compute_patient_billing_report` runtime calls and reconcile it with `RULE_REGISTRY` without treating the registry as a dispatcher.
- [x] Trace every runtime output through report fields, `recommended_actions`, `claim_compliance`, totals, cache/API, and patient/cohort frontend surfaces.
- [x] Generate the machine-readable coverage matrix plus human audit report with exact counts, hidden list, duplicate groups, and financial/nonfinancial classification.
- [x] Add an inventory completeness regression so new runtime detectors cannot appear without a surfacing classification.
- [ ] Review the audit output and lock migration scope before changing runtime/UI behavior.
- [ ] Define one canonical finding contract and migrate the approved hidden nonfinancial validation wave without one-off per-rule wiring.
- [ ] Verify patient/cohort reachability, old-cache honesty, stable finding identities, duplicate behavior, and unchanged financial totals for nonfinancial migrations.

### Dispatch scope: baseline audit only (Phases 0-4)
- [x] Phase 0: freeze taxonomy, source revision, registry breakdown, canonical runtime entrypoints, and product projection entrypoints.
- [x] Phase 1: generate a deterministic static runtime inventory for `analyze_claim` and `compute_patient_billing_report`, including gated calls and registry/artifact reconciliation.
- [x] Phase 2: trace every runtime output through report fields, recommended actions, claim compliance, dedicated sections, and monetary totals.
- [x] Phase 3: trace cache/API plus patient/cohort frontend reachability and deep-link behavior; treat Rule Database as metadata only.
- [x] Phase 4: generate the exact JSON matrix and Markdown audit report, including hidden findings, duplicate groups, unknown mappings, and separate inventory-level counts.
- [x] Add and execute completeness tests for canonical runtime calls, the current two-rule claim-compliance allowlist, registry-only classification, and unmapped runtime-call failure.
- [x] Review the Phase 0-4 diff and executed evidence, create coherent local audit checkpoint commit(s), and stop at `ready_for_review` for Chief acceptance.

### Out of Scope
New SUT/medical detectors, diagnosis-procedure medical-necessity logic, coverage-status metric manipulation, unrelated pricing/recovery changes, and production deployment/cache rebuild during the audit phases.

---

## Task: PR87 claim-compliance correctness fixes (2026-09-18)

### Goal
Implement `plans/billing/2026-09-18-pr87-claim-compliance-fixes-plan.md` on `feat/compliance-k21-k26` so K21/K26 are correct, cohort evaluation payloads are bounded, and claim-compliance findings have their own reachable server-side pagination path.

### Subtasks
- [x] Enforce same-day K21 semantics and replace the different-day regression.
- [x] Reconcile K26 diagnosis presence from header plus normalized primary diagnoses while preserving blank-vs-unavailable behavior.
- [x] Replace unbounded cohort evaluation identities with exact counts plus bounded non-evaluated details and truncation metadata.
- [x] Fetch and paginate `surface=claim_compliance` independently in the frontend, preserving active patient/cohort filters and total-count badges.
- [x] Make claim-compliance monetary summary values nullable in TypeScript and render them nonfinancially.
- [x] Run focused backend/frontend tests, Ruff, TypeScript, changed-file ESLint, then full backend/frontend suites where feasible.
- [x] Record exact verification outcomes in `tasks/k21-k26-result.md` and complete this review section.

### Out of Scope
New SUT detectors, monetary integration for claim-compliance, broad compliance redesign, diagnosis-conflict adjudication, production cache rebuild/deploy, pushing or merging the branch.

### Review
Implemented from plan commit `58f3308a` on `feat/compliance-k21-k26`. K21 now joins bundled services to exact 510090 dates. K26 reconciles a nonblank header diagnosis with normalized primary `ClaimDiagnosis` rows while preserving explicit-blank versus unavailable provenance. Cohort cache data stores per-patient status counts plus at most 20 non-evaluated details; API responses expose exact filtered counts without unbounded successful evaluation identities. Compliance surfaces are fetched and paginated server-side; large patient cohorts fall back to a JSON POST when the GET query would exceed 6,000 characters. Claim-compliance money remains nullable/nonfinancial and old-cache absence stays unavailable.

Final verification on the final tree: focused backend **84 passed**; focused frontend **22 passed**; full backend **2631 passed**; full frontend **266 passed**. Changed-file Ruff, ESLint, TypeScript, and `git diff --check` passed. Independent review first found and drove fixes for stale cohort aggregate state and backend-first rolling-deploy compatibility; the final fresh `codex review --uncommitted` returned **0 findings / patch is correct (0.91 confidence)**. Its read-only sandbox could not run pytest, so the writable-workspace suites above are the execution evidence. No production cache rebuild/deploy, push, merge, or commit was performed.

---

## Task: K21 + K26 reviewer blockers

### Goal
Prevent late-money inference crashes and show accurate scoped presentation counts while retaining legacy actions and financial totals.

### Subtasks
- [x] Confirm the three requested fixes and existing test/runtime conventions; review this narrow plan against the request.
- [x] Use full inference for cohort rows and regress >100 null-money findings before a monetary legacy row, including preserved totals and row money.
- [x] Count scoped claim findings in patient/claim KPI and tab badge only; regress patient, claim and legacy-only counts.
- [x] Omit the claim-compliance dashboard badge for old caches and assert rendered absence.
- [x] Run focused backend/frontend tests, changed-file lint and tsc; record exact outcomes in tasks/k21-k26-result.md.

### Out of Scope
Pagination redesign, broad refactoring, other detectors, money/action integration, other worktrees, commits, pushes and live changes.

### Review
46 backend and 18 frontend tests passed; final tsc and Ruff passed. Changed-file ESLint found only the existing PatientWorkspaceViews navigation-effect error; HEAD stdin lint reproduced the same error, and all other touched frontend files passed lint. No suppression or out-of-scope navigation rewrite. Full inference regression demonstrated red before/green after; scoped counts and old-cache badge have rendered assertions. Exact commands, limitations and results recorded in tasks/k21-k26-result.md. No commit/push/live changes.

---

## Task: K21 + K26 reporting reachability

### Goal
Expose only the existing ICU bundled leakage and missing diagnosis detectors through full-context reporting, cache/API and native compliance UI without any money contribution.

### Subtasks
- [x] Verify normal ingestion provenance and positive/negative scenarios before wiring detectors.
- [x] Add backward-compatible availability tracking and a narrow report-owned nonfinancial projection with stable claim/line identities.
- [x] Connect cache/index/API and native frontend filtering/rendering with patient links.
- [x] Run real-function ingestion integration tests, financial regressions, frontend tests, typecheck and lint sequentially for pytest.
- [x] Replace unbounded evaluation rows with a compact summary and closed, bounded details; verify 120-evaluation rendered regression.
- [x] Inspect artifact drift and record exact evidence in tasks/k21-k26-result.md.

### Out of Scope
Engine merging, validator changes, other detectors, rule catalogs, shipped data, live services, commits, pushes and PR creation.

### Review
K21/K26 implemented through normal ingestion/context, report-owned nonfinancial projection, cache/index/API and native UI. Chief independently reported 71 backend tests and 9 frontend tests passing before the final compact-summary change; typecheck and Ruff passed. Final UI verification: dashboard Vitest file 10/10 passed; ESLint passed for the test and table. Large-list regression verifies 120 evaluations, correct counts, closed details bounded to 20 entries, distinct unknown/clean empty states, findings, links and null money. Prior status inspection showed only scoped source/tests/tasks changes, no catalog/generated-data drift; no new broad inspection or backend run in this final finish. Evidence and limitations: tasks/k21-k26-result.md. No commits, pushes or live changes.

---

## Task: 2026-08-29 SUT rule corpus (PR 80 follow-through)

### Goal
PR 80 ingest is on this branch; encoded YAML/wave keys resolve against the 2026-08-29 clause corpus; compile + coverage artifacts are regenerated; the two new grandfathering bents are encoded; inventory/coverage goldens match the live 08-29 corpus.

### Subtasks
- [x] Remap stale `coord#hash` cites in YAML + `gate_b_wave_config.py` to new hashes (similarity-matched)
- [x] Remap positional `C*` `gate_b_sources` + `clause_type_overrides.yaml` (07-01 → 08-29 id shift)
- [x] Update YAML messages for real law changes (4.1.4.c, 4.2.1.C-3/C-5.a, 4.2.8.A.b, 4.2.14.C KLL, 4.2.15.D-2 radiology)
- [x] Encode new `4.2.1.C-3.d` and `4.2.1.C-5.d` grandfathering rules
- [x] `compile_rules.py` then `compile_rules.py --check`
- [x] `build_sut_coverage.py`
- [x] Changelog
- [x] Recompile §4.2.1 against current coverage so empty-hash `is_in_force=false` ghosts leave traces (pending 16+2)
- [x] Skip extractor empty-hash out-of-force rows in Gate B export
- [x] Freeze coverage/C* inventory goldens to live 08-29 counts (215 gaps / 28 deontic / 215 C* / 249+15 eligible)
- [x] Recompute w4 tier_b resolved C* set from live YAML cites
- [x] Decision note for accepted remap tolerances
- [x] Targeted pytest; `git status` after (pytest can mutate artifacts)
- [x] Full `tests/unit` (2564 passed, 9 skipped)
- [x] Commit, push, update PR #84

### Review
PR 80 ingest is on this branch. Encoded YAML/wave keys resolve against the 2026-08-29 corpus. Gate B export skips extractor empty-hash out-of-force copies. Historical wave2/r6 manifests remapped by clause_key. `tests/unit`: 2564 passed. Do not merge #80 separately; this PR already contains `5f05d3a4`.

### Out of Scope

### Out of Scope
Merging PR 80 itself; encoding unencoded AMENDED coords (2.4.2.B-1.(2), 4.1.4.(4), 4.2.14.B.(1), 4.2.15.D-1.(3)); deferral_table historical stale hashes not on the compile path; synthetic cohort regen.

---

## Task: Chrome tab navigation — left-click replaces, “Yeni sekmede aç” stays

### Goal
Left-click / sidebar navigate in this strip tab (replace unless that tab already exists). Ctrl/middle/right “Yeni sekmede aç” add a background tab and stay; if it already exists, switch to it. The menu click must not fall through onto the patient link.

### Locked decisions (2026-09-03 grill)
- Left-click a patient on Hastalar: this strip tab **becomes** that patient (Hastalar gone).
- Left-click patient B from patient A: this tab becomes B (A gone), unless B already exists → switch to B, leave A.
- Sidebar Hastalar: same rule (replace this tab if Hastalar is not already a tab; switch if it is).
- “Yeni sekmede aç” / Ctrl / middle: not open yet → add unselected tab, **stay**. Already open → switch to it.
- Click-through after the context menu is a bug, not “open and go”.

### Subtasks
- [x] `applyWorkspaceSync` replaces the active tab when the dest is new; still switches when dest exists
- [x] `useOpenPatientBackground` stays on add; `router.push` when that tab already exists
- [x] Context menu swallows the ghost click so the patient link does not navigate
- [x] Update workspace tab unit tests; vitest + tsc
- [x] Browser: left-click replaces; “Yeni sekmede aç” stays on Hastalar with a new unselected tab

### Review
“Yeni sekmede aç” was navigating because the menu click fell through onto the patient link. Menu now adds a background tab and stays on Hastalar. Left-click replaces this strip tab (Hastalar becomes that patient) unless the dest tab already exists, in which case it switches. Ctrl/middle match the menu. Playwright: menu on 0001 stayed on `/?tab=patients` with both tabs; left-click 0043 replaced Hastalar and kept 0001.

### Out of Scope
Chrome “switch immediately” preference; duplicate strip tabs for the same patient; drag-reorder.

---

## Task: Keep local Next.js from OOM-exiting

### Goal
`http://localhost:3000` stays up; Turbopack is not allowed to fill the Node heap and vanish.

### Subtasks
- [x] Switch `next dev` to webpack (Turbopack leaked ~15GB and exited)
- [x] Restart frontend; confirm `/login` returns 200

### Review
Cause was Next 16 Turbopack OOM (~15GB), not a closed browser tab. Dev server now uses webpack. `/login` 200 at http://localhost:3000.

### Out of Scope
Fixing the Turbopack leak itself; changing Node version.

---

## Task: Chrome-gestures to open patient strip tabs

### Goal
Ctrl/Cmd-click, middle-click, and right-click “Open in new tab” on any patient profile link add an in-app strip tab and leave the current view. Five patients = five of those clicks while staying on Hastalar.

### Locked decisions (2026-09-02)
- Workspace strip tabs only (never a new browser window).
- Per-row Chrome gestures, no multi-select.
- Every patient-id navigation: cohort table, compliance, red kuyruğu, revenue/optimizer lists, Ctrl+K, in-workspace patient search.

### Subtasks
- [x] `openBackground` on the workspace store (`ensureWorkspaceTab`, do not change `activeTabId`)
- [x] Shared `PatientTabLink` + context menu; helper tests for href → view and modifier detection
- [x] Cohort table: real patient href + row Ctrl/middle/right-click stay on Hastalar
- [x] Replace remaining patient `<Link>`s (compliance, findings, red kuyruğu, optimizer)
- [x] Ctrl+K and PatientSearch: same gestures; Ctrl+Enter in palette opens background and stays open
- [x] i18n en/tr `openInNewTab`
- [x] vitest + tsc; browser: five Ctrl-clicks on Hastalar leave you on the list with five new strip tabs

### Review
Chrome gestures open in-app strip tabs without leaving the current view. `openBackground` keeps `activeTabId` unchanged. Cohort, compliance, red kuyruğu, optimizer, Ctrl+K, and in-workspace PatientSearch all use the same Ctrl/Cmd-click, middle-click, and right-click “Open in new tab” path. `npx vitest` 249 passed, `npx tsc --noEmit` clean. Browser on http://localhost:3000 Hastalar: five Ctrl-clicks stayed on `/` with five new strip tabs; right-click showed “Open in new tab” and added SENTETIK-HASTA-0039 while still on the list.

### Out of Scope
Multi-select; native browser “Open in new tab”; Shift+click new window.

---

## Task: Chrome-style workspace tabs (equal width, no cap, scroll)

### Goal
The tab strip behaves like Chrome: every open tab is the same width, they keep a standard size until they hit the search/feedback cluster, then they shrink together. No 6-tab cap, no silent LRU close, no `+N`. When they hit min width, a scroll arrow reaches the rest.

### Locked decisions (2026-09-02)
- Equal width (not content-sized).
- Sections AND patients stay as tabs; sidebar click still opens a tab.
- No cap, no eviction; close only via ×.
- Kill `+N`. At min width: hidden-scrollbar track + scroll chevron (Chrome), not an overflow menu.

### Subtasks
- [x] Remove `WORKSPACE_MAX_TABS` eviction from `applyWorkspaceSync`, `ensureWorkspaceTab`, and `readWorkspaceSession`; update unit tests (opening a 7th tab must keep all 7)
- [x] Delete `countInlineWorkspaceTabs` / `splitWorkspaceTabs` and the `+N` overflow UI
- [x] Tab track: `flex-1 min-w-0`, each tab `flex: 1 1 13rem; min-width: 4.5rem; max-width: 13rem` so few tabs stay standard-sized with empty space before search, many tabs shrink equally
- [x] When `n × min-width` exceeds the track: keep min width, `overflow-x` hidden (no visible scrollbar), left/right chevrons, wheel scrolls the track, activating or opening a tab scrolls it into view
- [x] Close/split stay hover-only and must not inflate min width (overlay, not extra flex space)
- [x] i18n: overflow string → scroll-more aria labels (en + tr)
- [x] `npx vitest` + `npx tsc --noEmit` green
- [x] Browser: 3 tabs stay ~208px with a gap before search; 8+ tabs shrink together; more than fit at 72px → chevron, no `+N`; closing a tab restores width; chat-dock open shrinks available width

### Review
Chrome-style strip is live. No 6-tab LRU cap; no `+N`. Playwright: 3 tabs = 208px equal with a gap before search; 8 tabs = 159px equal filling the track; 18 tabs at 720px = 72px min + left scroll chevron. App is running at http://localhost:3000.

### Out of Scope
Drag-reorder, tab groups, a Chrome “new tab” `+` button, pinned tabs, changing how sidebar/search opens tabs, raising keep-alive of hidden patient panes.

---

## Task: Fit workspace tabs to top-bar width

### Goal
The workspace tab strip shows every open tab that actually fits; `+N` appears only when remaining tabs cannot fit beside the search/feedback actions.

### Subtasks
- [x] Add a pure `countInlineWorkspaceTabs` / `splitWorkspaceTabs` helper (fit-to-width, keep active tab inline)
- [x] Unit-test the helper: all fit, overflow needed, tiny bar, active tab in overflow
- [x] Replace the hardcoded `WORKSPACE_INLINE_TABS = 5` split in `WorkspaceTabStrip` with ResizeObserver measurement
- [x] Close the overflow menu when it becomes empty; remeasure on resize and chat-dock inset
- [x] Run `npx vitest` on the helper + `npx tsc --noEmit`
- [x] Verify in the browser: 6 open tabs on a wide window show all; shrinking the window reveals `+N`; no large gap before search

### Review
Root cause was `WORKSPACE_INLINE_TABS = 5`: the 6th tab always went into `+1` regardless of leftover width. Overflow is now measured with ResizeObserver. Playwright: 1600px viewport → 6 inline tabs, no `+N`; 720px → `+4` with the active tab kept visible.

### Out of Scope
Changing `WORKSPACE_MAX_TABS` (still 6). Redesigning tab chrome, labels, or the overflow dropdown itself.

---

## Task: Fix Hermes Cursor proxy HTTP 502 Invalid User API Key

### Goal
Telegram/gateway POSTs to `127.0.0.1:8765` authenticate with the stored Cursor user key instead of a foreign Bearer, so CreateAgent no longer returns 401.

### Subtasks
- [x] Confirm stored `CURSOR_API_KEY` still works for catalog + SDK oneshot (no key echo)
- [x] Prove incoming Hermes `Authorization` is what CreateAgent uses (prefix/len only)
- [x] Patch proxy to always use systemd `CURSOR_API_KEY`; ignore non-`crsr_` Bearer
- [x] Restart `hermes-cursor-proxy`; smoke POST with dummy Bearer + real CLI
- [x] Add gateway `EnvironmentFile` only if `hermes setup` is not mid-run — skipped; setup still on pts/0, proxy fix is sufficient
- [x] Document cause in this review section

### Review
The 502 was not a bad Cursor key. Hermes Telegram sent `Authorization: Bearer no-key-required` to the loopback proxy; the proxy forwarded that to CreateAgent and Cursor 401'd. Proxy now ignores non-`crsr_` Bearers and uses systemd `CURSOR_API_KEY`. Smoke: POST with the placeholder header returned `AUTHFIX_OK` (CreateAgent 200). Retry the Telegram turn; no gateway restart needed.

### Out of Scope
Replacing the live Hermes tree; changing default Muse Spark model; printing the API key.

---

## Task: Wire Cursor Grok into Contabo Hermes (Hermes stays the agent)

Full plan: `plans/ops/2026-08-29-hermes-cursor-provider-vps.md`

### Goal
On `contabo-vps`, Hermes can use Cursor-billed Grok 4.6 / Composer while Hermes keeps tools, memory, and Telegram. Default model stays `muse-spark-1.2-contributor`.

### Subtasks
- [x] Inventory VPS Hermes 0.20.0, gateway unit, plugins, env (no CURSOR_API_KEY yet)
- [x] Drop `cursor_sdk_client.py` (Nous #88212 / hermes-agent-sdk) into the install
- [x] Loopback OpenAI proxy on `127.0.0.1:8765` with Cursor tools disabled
- [x] `pip install cursor-sdk` in the Hermes venv
- [x] systemd user unit `hermes-cursor-proxy`
- [x] `custom_providers` entry; do not change default model
- [x] Add `CURSOR_API_KEY` when available; smoke `grok-4.6` oneshot
- [x] Restart gateway only if `hermes setup` is not mid-run

### Out of Scope
Replacing `/usr/local/lib/hermes-agent` with a fork; Cloud Agent handoff plugins; reverse-engineered `api2.cursor.sh` proxies.

---

## Task: Rebuild SUT coverage parquet + pin RULE_REGISTRY in CI

Full plan: `plans/billing/2026-08-23-demo-coverage-rebuild-and-registry-pin.md`

### Goal
Kural Veritabanı shows SUT clause text for `blood_component_isbt128_barcode` and `yatak_icu_overlap`, and CI fails if a `RULE_REGISTRY` id is missing from `sut_registry_coverage.parquet`.

### Subtasks
- [x] Branch `chore/sut-coverage-rebuild-registry-pin` from up-to-date `main`
- [x] Add `tests/unit/domain/sut/test_registry_coverage_artifact.py` (set equality + blood/yatak `matched_clause_count > 0`; fail if parquet missing)
- [x] Confirm that test **fails** on current parquet (missing those two ids)
- [x] Run `python scripts/sut/build_sut_coverage.py`
- [x] Confirm parquet has 47 rows, ids == `set(RULE_BY_ID)`, blood 3, yatak 12, icu 9
- [x] Re-run the new test + `tests/unit/domain/sut/test_rules_catalog.py` — green (full suite: 2583 passed)
- [x] Commit parquet + test (+ drift fix below, atomic) — `5a3ad53`; manifest sync `34849c6`
- [x] Open PR (#79), CI green (backend 6m13s + frontend)
- [ ] Merge to `main` — BLOCKED on branch protection (review required); needs Safa's merge click or explicit --admin go-ahead (deploy.yml follows)
- [ ] Verify production: `zero_clause_matches` length 6, those two rules have clause cards in the browser (after merge + deploy)

### Drift surfaced by the rebuild (fixed in-PR)
The parquet committed at `1c38126` was stale-at-birth: a pristine-worktree repro
proved that commit's own builder disagreed with it for 5 §4.2 clauses. Fixed via
`deferral_table.yaml` entries (C003658/C003756/C003834 tier_c_deferred, C004257
existing entry un-dropped, C004299 non_actionable) + `load_deferral_table`
resolves non-encode-eligible rows and same-clause_key content duplicates +
`repair_untraced` honest set aligned with the audit + compiled 4201/4210
manifests regenerated + 6 committed-manifest pins recalibrated.

### Out of Scope
Synthetic `skipped_no_data` fields; Fatura İnceleme UI; filling the remaining six zero-clause rows; rebuilding coverage inside CI.

---

## Task: Purge fake "demo"-coded claim lines from the synthetic cohort

**Rev 2 (2026-08-22)** — patched after plan review. Review verified against repo:
all 8 gap claims + 3 fact corrections confirmed. Do-not-implement-as-written lifted;
this rev addresses every item.

### Goal
No claim line in the synthetic cohort carries a fabricated `demo` code. All 13
fake-coded lines are removed at the generator (not filtered out of the parquet),
their scenario machinery is deleted or re-anchored, and the cohort is regenerated
+ cache rebuilt + verified end-to-end.

### Background (verified findings)
- 13 fake-coded lines exist, in 4 families:
  - **Drug-indication demos (6)** — patients 0014,0015,0016,0017,0019,0020,
    codes `SUT-DEMO-BEV/NIVO/DARA/PEM/TRAS/TRAB`.
  - **MEDULA 0411 drug anchor (1)** — patient 0031, code `SUT-DEMO-BEV`.
  - **Material-prose demos (2)** — patients 0021 (`SUT-DEMO-OPT`), 0022 (`SUT-DEMO-GRF`).
  - **§3.3/L4.4 keyword demos (4)** — patient 0001, codes `DEMO-L44-W1/W2/CL1/SS1`.
- None of these codes exist in any real catalog (0 hits in `ek4a_drugs` + all `ek3*`).
- **Fact correction (rev 2):** 5 of 6 oncology BRANDS DO exist in EK-4A
  (OPDIVO×2, DARZALEX×3, KEYTRUDA×1, HERCEPTIN×1, YONDELIS×1); only
  AVASTIN/bevacizumab is absent. Replacement is still out of scope (Safa chose
  deletion), but the earlier "cannot be replaced" claim was overstated for 5/6.
- **Fact correction (rev 2):** patient 0001 is **Tier C** filler (not "unranked").
  The other 9 demo patients are Tier B. Tier A is untouched.
- Rule engines match by drug name/INN and material-name keywords, NOT by code — the
  fake codes are cosmetic placeholders, but the lines are load-bearing for showcases.

### DECISION POINTS (confirmed by Safa 2026-08-22)
- **D1 — MEDULA 0411 (patient 0031):** CONFIRMED re-anchor from `drug` → `claim`
  (claim-level rejection, same pattern as scenario 0032). Keeps the MEDULA Red-Queue
  scenario but drops the fake-coded drug line.
  - *Verified alternative (not taken):* the same claim carries a REAL drug line
    `A16712` (MEXIA XR 14 MG); anchoring 0411 to it would keep drug semantics with
    no fake code. Claim-level kept because it is simpler and matches the confirmed
    decision; `related_line_*` is display-only, playbook matches on `sonuc_kodu 0411`.
- **D2 — Patients 0014–0022 after demo removal:** CONFIRMED keep them as ordinary
  background patients (no renumbering), but strip their scenario entries from
  `demo_manifest.json` / `demo_vignettes.json` and the tier lists. They fall to Tier C.

### ACCEPTED PRODUCT LOSS (recorded, not a surprise after regen)
After the purge, no synthetic patient showcases these in the UI (engines + unit
tests remain; live cohort demos do not):
- §4.2 drug indication (6 oncology lines, 0014–0020) — gone from cohort
- §3.3 optical lens upgrade (0021) and hip-graft no-pay (0022) — gone from cohort
- §3.3 keyword L4.4 (0001, the original UI complaint) — gone (intended)
Kept: §3.1 material prose real codes (0023 OP1592, 0024 OP1000), claim readiness
(0033 OP2000), MEDULA 0411 red-queue (claim-level), all Tier A live demos.

### Subtasks

**Phase 0 — Baseline**
- [x] 0.1 Re-confirm the 13 lines + codes with a fresh parquet read; record counts (drug=7, material=6).
- [x] 0.2 D1/D2 confirmed by Safa: re-anchor MEDULA-0411 to claim-level; keep 0014–0022 as background patients.

**Phase 1 — Generator surgery (`scripts/synthetic/`)**
- [x] 1.1 `gen/specs.py`: delete `_DRUG_INDICATION_DEMO_SPECS` (all 6 SUT-DEMO).
- [x] 1.2 `gen/specs.py`: remove `optical_lens_upgrade` + `hip_graft_no_pay` from `_MATERIAL_PROSE_DEMO_SPECS` (KEEP `kdv_ceiling_exceeded`=OP1592, `procurement_incomplete`=OP1000).
- [x] 1.3 `gen/specs.py`: re-anchor `_MEDULA_DEMO_SPECS["0031"]` drug→claim (per D1).
- [x] 1.4 `gen/patients.py`: delete demo wiring for 0014–0020 (drug) and 0021–0022 (material OPT/GRF); KEEP 0023–0024.
- [x] 1.5 `gen/orchestrate.py`: drop `_DRUG_INDICATION_DEMO_SPECS` import + `drug_indication_demo/spec` wiring, **AND delete the inline drug-row injector block (~lines 405–458: `if drug_indication_spec:` → `ctx.drug_claims.append` + `ctx.expected.append`)** — leaving it would let fake lines be re-created. Keep `material_prose_spec` path (still used by 0023/0024 + claim_readiness).
- [x] 1.6 `gen/reconcile.py`: delete active `_inject_specialty_keyword_demo_rows`.
- [x] 1.7 `gen/materials_flags.py`: delete dead duplicate `_inject_specialty_keyword_demo_rows`.
- [x] 1.8 `gen/workbook.py`: remove its import + the `_inject_specialty_keyword_demo_rows(materials, claims)` call.
- [x] 1.9 `gen/__init__.py` + `generators.py`: remove `_DRUG_INDICATION_DEMO_SPECS` re-exports.
- [x] 1.10 `gen/medula_anchor.py`: delete now-unused `drug` anchor branch (dead-code cleanup).

**Phase 2 — Validator (`validate_sut_synthetic_data.py`)**
- [x] 2.1 Delete `_validate_drug_indication_demos` + `DRUG_INDICATION_DEMO_PATIENTS` + `DRUG_INDICATION_DEMO_TIER_B_FIELDS` + its call site (~line 1278).
- [x] 2.2 Remove 0021/0022 from `MATERIAL_PROSE_DEMO_PATIENTS` / `MATERIAL_PROSE_DEMO_MATERIAL_CODES` / `MATERIAL_PROSE_DEMO_FLAG_EXPECTATIONS` (KEEP 0023/0024).
- [x] 2.3 Keep `DRUG_INDICATION_WORKBOOK_COLUMNS` + §4.2 drug columns (still required schema); keep `_empty_drug_indication_fields` / `_ensure_drug_indication_columns`.
- [x] 2.4 **(rev 2)** Gate/delete the MEDULA `0411` drug-content branch (~lines 966–978): it requires a drug anchor with `uzmanlik_kurulu_raporu_var=False`, which no longer exists after the claim-level re-anchor. Skip the check when the anchor type is claim-level.

**Phase 3 — Curated data + golden + docs**
- [x] 3.1 `demo_manifest.json`: remove `scenario_by_index` entries 0014–0017,0019–0022 and drop the same 8 indices from `tier_b_patient_indices` (KEEP 0018, 0023–0028, 0030–0033); 0031 stays (claim-level).
- [x] 3.2 `demo_vignettes.json`: remove vignettes 0014–0017,0019–0022; keep 0031 (update its description if it references the drug anchor).
- [x] 3.3 **(rev 2)** Trim `data/gazette/prose_rules/golden/material_prose_sprint2.json` (remove the 0021/SUT-DEMO-OPT and 0022/SUT-DEMO-GRF entries). Update human docs that advertise the purged patients: `data/synthetic/README.md`, `docs/gazette/partial-coverage-scope.md`. (`DEMO_COHORT.md` is auto-regenerated by the generator — verify after regen.)

**Phase 4 — Tests**
- [x] 4.1 `test_sgk_uplift_synthetic_demos.py`: delete `TestDrugIndicationSyntheticDemo`; remove the 2 SUT-DEMO params from `TestMaterialProseSyntheticDemo` (keep kdv/procurement); keep the MEDULA 0411 param (claim-level still passes).
- [x] 4.2 `test_claim_drug_indication.py`: KEEP (engine test, in-memory fixtures); optionally rename fixture `SUT-DEMO-BEV`→neutral token.
- [x] 4.3 `frontend/.../SutBillingReportSections.test.tsx`: optionally rename fixture `SUT-DEMO-OPT`→neutral token.
- [x] 4.4 **(rev 2)** `tests/unit/api/test_patient_billing_drug_indication_api.py`: delete/rewrite the 0014, 0017, 0019 tests (they pin violation counts against cohort patients that lose their drug lines).
- [x] 4.5 **(rev 2)** `tests/unit/scripts/test_synthetic_specialty_prose_flags.py`: delete `test_keyword_demo_material_names_present` (asserts DEMO-L44 material names in a live-built workbook).
- [x] 4.6 **(rev 2)** `tests/unit/synthetic/test_vignette_golden.py`: remove 0014–0017,0019–0022 from `test_sprint_demo_indices_0012_to_0033_documented` index list (keep 0012,0018,0023–0028,0030,0031,0033).
- [x] 4.7 **(rev 2)** `tests/unit/synthetic/test_cohort_tiers.py`: update hardcoded counts `tier_b == 24 → 16`, `tier_c == 17 → 25` (8 indices move B→C).

**Phase 5 — Regenerate + validate**
- [x] 5.1 Run `python scripts/synthetic/generate_sut_synthetic_data_v2.py` (runs validator + Tier A assert).
- [x] 5.2 Assert 0 `demo` codes remain — **(rev 2)** across `claims/*.parquet` (drug_code, material_code, equivalence_group), `clean/*.parquet`, AND the `sentetik_sut_v2_50_hasta.xlsx` sheets (the generator writes the workbook too; parquet-only grep is insufficient).
- [x] 5.3 Confirm Tier A patients (0002,0003,0006,0009,0010,0011,0013,0029,0038) still pass `assert_tier_a_post_regen.py`.

**Phase 6 — Test suite + typecheck**
- [x] 6.1 `pytest` (at minimum: `tests/unit/synthetic/`, `tests/unit/scripts/test_synthetic_specialty_prose_flags.py`, `tests/unit/api/test_patient_billing_drug_indication_api.py`, `tests/unit/domain/billing/test_sgk_uplift_synthetic_demos.py`, `test_claim_drug_indication.py`, MEDULA suite).
- [x] 6.2 Frontend `vitest` + `tsc --noEmit` if any fixture renamed.

**Phase 7 — Cache rebuild + end-to-end**
- [x] 7.1 Rebuild billing cache (`BILUN_STARTUP_POLICY=rebuild` + restart backend); confirm `/health` shows a completed build (not `active_build:null`).
- [x] 7.2 Spot-check a regenerated Tier B patient + the API to confirm no `demo` codes surface.

### Out of Scope
- Touching the real rule engines (`drug_indication.py`, specialty-prose, §3.3 keyword rules) — they stay.
- The real-coded material demos: `kdv_ceiling_exceeded` (OP1592), `procurement_incomplete` (OP1000), claim-readiness (OP2000).
- All Tier A showcase patients and the MEDULA scenarios with real-coded anchors.
- Replacing the 6 oncology demo codes with real EK-4A barcodes (5/6 brands DO exist in EK-4A — feasible in principle — but deletion was the chosen path; not requested).
- Renumbering patients or changing the 50-patient cohort size.

### Review
**Done 2026-08-22. Purge complete and verified end-to-end.**

- **Purge:** all 13 fake-coded lines removed at the generator (7 drug `SUT-DEMO-*`,
  2 material `SUT-DEMO-OPT/GRF`, 4 material `DEMO-L44-*`). Zero `SUT-DEMO`/`DEMO-L44`
  cells remain in `claims/*.parquet`, `clean/*.parquet`, and the `.xlsx` (verified).
  Remaining "demo" strings are only legit scenario-tag names of kept demos (copay
  exemption, payment-method) and internal line-IDs of kept real-coded material demos.
- **Regen:** `generate_sut_synthetic_data_v2.py` passes (validator + Tier A assert).
  Tier counts now B=16 / C=25 (8 purged indices moved B→C).
- **Cache:** rebuilt offline (`BILUN_STARTUP_POLICY=rebuild`), new build
  `a5bb830b` activated; active build has 0 demo-code cells across every VARCHAR
  column (the 121 "demo" cells first seen were from superseded builds — filter by
  `build_id`).
- **Tests:** 2570 unit tests pass; frontend `SutBillingReportSections` 26 pass;
  `tsc --noEmit` clean.

**Pre-existing drift fixed along the way (NOT caused by the purge).** The cohort was
last regenerated 2026-06-28 (`21aa6a9`); 318 commits later — incl. the 2026-07-01
SUT amendment (`5e82c31`), 163 newly-wired billing rules, and a generator RNG-path
change — the committed data was stale. Regen surfaced it; fixed:
- 3 validator bugs (missing `hasta_katilim_payi_profilleri` sheet, over-strict
  vignette-manifest alignment, EK-3B-1/2 derived flags wrongly required in parquet).
- Recalibrated drift-pinned goldens/tests: Tier A 0003 band (6300→6750),
  `test_f011` (6300→6750), `test_f015` (new §2.2.1 613080 violation + 3 doc rows),
  `test_0001`→retargeted to 0045-078 (0001-001 flipped to itemized),
  `test_copay_outcome_kind` rate patient 0012→0002.

**Accepted product loss (per D1/D2):** cohort no longer showcases §4.2 drug-indication
(0014–0020), §3.3 optical/hip-graft (0021–0022), or §3.3 keyword L4.4 (0001) — engines
+ unit tests remain. MEDULA 0411 kept as claim-level rejection.

**Not committed** (left for Safa to review/push). Backend left running on the rebuilt
cache (port 8001).

---

## Task: Fill TÜBİTAK 1812 pitch deck template (RV1) with Bilun content — Turkish

**Date: 2026-08-22**

### Goal
Produce a filled, panel-ready Turkish pitch deck from
`/home/safa/Documents/BIGG/Medipol/RV1_1812_Pitch_Deck_Sablonu.pptx` (19 slides),
using ONLY facts from existing sources (no invented numbers):
- AGY112 iş planı formu (`BIGG/Medipol/1812_agy_112_pdf_form_v1.2.pdf`) — primary source
- Başvuru formu (`112 Numaralı İş Fikri Çağrı Dokümanı.doc`) — thematic area (Sağlık ve İyi Yaşam), TRL 4→7
- `Bilun Extras/Presentations/Bilun.pptx` (TR investor deck) — team/advisors, market framing
- Kent Hastanesi interview docs (customer validation evidence)

### Subtasks
- [x] Extract template structure (all 19 slides, shapes, tables, guide rails)
- [x] Extract content from AGY112 form, call doc, TR deck, interviews
- [x] Write plan (this file)
- [x] Python script (python-pptx): fill every placeholder/table with Bilun content, preserving run formatting
- [x] Delete guide-rail scaffolding per template's own instruction ("Nihai sunumdan önce bu rehber alanını silin") + kullanım notu + "Önerilen görsel/Eklenebilecek Unsurlar" boxes
- [x] Fix slide 12 "İŞ PAKETİ 7" → 6; replace generic timeline milestones with Bilun milestones
- [x] Fill checklist slide (18) with Evet + slide refs; adapt backup slide list (19)
- [x] Save as NEW file `RV1_1812_Pitch_Deck_BILUN.pptx` (template untouched)
- [x] Verify: reopen output — zero `[...]` placeholders except `[LOGO / ÜRÜN GÖRSELİ]` and `[FOTOĞRAF]`; zero guide shapes; all table cells filled (231 ops, all tables N/N); rendered to PDF via LibreOffice and visually inspected slides 1/2/7/12 — layout intact

### Content decisions (flagged to user)
- Numbers come verbatim from AGY form even where the form is internally inconsistent
  (2M TL vs 350K TL price points; 5M vs 15M at 12/2028) — deck quotes each section's
  own figure; inconsistencies flagged in final message.
- Slide 13 budget split (45/20/25/10%) is explicitly marked "taslak" — no Bilun budget
  document exists; total = 900.000 TL for %3 equity per current 1812 model.
- Customer validation stated honestly: sözlü pilot onayı, imzalı sözleşme yok.

### Out of Scope
- Adding real images (logo, photos, screenshots) — placeholders kept.
- Fixing AGY form's internal inconsistencies (flagged only).
- Modifying the template file itself.

### Review
Delivered: `/home/safa/Documents/BIGG/Medipol/RV1_1812_Pitch_Deck_BILUN.pptx` (19 slides, Turkish).
- All 19 slides filled from AGY112 form + call doc + TR investor deck + Kent Hastanesi interviews; no invented numbers.
- Guide rails / kullanım notu / scaffolding boxes deleted per the template's own "nihai sunumdan önce silin" instruction.
- Slide 12: 6 work packages with Bilun milestones (KVKK veri aktarımı → 10+ kurum hedefi); "İŞ PAKETİ 7" typo fixed.
- Slides 16/18: risk matrix from AGY 5.1 (5 risks, real B plans, KVKK/etik note); checklist all Evet with slide refs.
- Verification: text dump (0 leftover placeholders), raw-XML spot check, LibreOffice PDF render + visual inspection.
- Known template quirk: small circle cards on slides 2–6 overflow slightly with full sentences — acceptable, polish in PowerPoint if desired.
- Flagged to user: AGY form internal inconsistencies kept as-is per section (2M vs 350K ₺ price points; 5M vs 15M ₺ at 12/2028; 45K vs 50K ₺ unit cost); slide 13 budget split marked "taslak".
- User must still add: logo/ürün görseli (slide 1) and 3 team photos (slide 14).

---

## Task: Reconcile financials (tiered pricing), fill Maliyet Formu (1.35M TL), fix deck overflow

**Date: 2026-08-23**

### Goal
Apply the approved tiered-pricing framing (2M ₺ flagship tier / ~350K ₺ blended ARPU)
consistently across (a) pitch deck, (b) AGY112 fillable PDF; fill Maliyet_Formu.docx with a
1.350.000 ₺ budget tied to work packages; shorten circle-card copy on deck slides 2–6.

### Subtasks
- [x] Plan (this section)
- [x] Deck: 1.35M investment (slides 13/15), slide 13 rows = Maliyet Formu categories, tiered-price notes (slides 7/10/15), shortened circle cards (slides 2–6), checklist row 13 note
- [x] Maliyet_Formu.docx → fill 5 tables (personel 990K / M013 150K / M015 150K / diğer 60K = 1.350.000), save as Maliyet_Formu_BILUN.docx
- [x] AGY fillable PDF: §1.4 tier note; §2.3 tier paragraph; §2.4 break-even sentence → 2M/50K/1.95M/5.4M; 4.4-2 diğer değişken 25K→30K; §4.2 350K→blended; 4.3 milestone 15M→~5M; §4.5 15M→8.75M+; save as v1.3_BILUN.pdf
- [x] Verify: deck re-render slides 2–6/13 visually (circles fit, tables clean); maliyet docx dump (totals 990+150+150+60=1.350K); PDF field dump (all 7 fields updated)

### Budget design (1.350.000 ₺)
- PERSONEL 990.000 (%73): Safa 1,0×18×33K=594K; Enes 0,5×12×33K=198K (Ay 7–18, mezuniyet sonrası); Kadir 0,5×12×33K=198K
- ALET/YAZILIM 150.000 (%11): 2× geliştirme bilgisayarı 90K; TR bulut barındırma+hesaplama 60K
- HİZMET 150.000 (%11): YMM 30K; hukuk 45K; sağlık ekonomisi 45K; sızma testi 30K
- DİĞER 60.000 (%5): seyahat 25K; TÜRKPATENT+telif harçları 15K; iletişim/ofis 20K
- MALZEME: boş (yazılım ürünü)
- Estimates flagged: monthly 33K ≈ 2026 asgari ücret işveren maliyeti tahmini; oranlar kullanıcı onayına açık.

### Out of Scope
- Changing any other AGY content; PRODİS submission; equity % (kept %3, flagged).

### Review
Delivered (all in /home/safa/Documents/BIGG/Medipol/):
- RV1_1812_Pitch_Deck_BILUN.pptx — regenerated: 1,35M ₺ yatırım (slayt 13/15); slayt 13
  satırları Maliyet Formu kategorileriyle birebir; tier notları (7/10/15); daire kartları kısaltıldı
  (2–6, render ile doğrulandı); checklist satırı güncellendi.
- Maliyet_Formu_BILUN.docx — 5 tablo dolu; TOPLAM 1.350.000 ₺.
- 1812_agy_112_pdf_form_v1.3_BILUN.pdf — 7 alan düzeltildi; tüm finansal ifadeler artık
  tier modeliyle tutarlı (2M amiral / ~350K blended; 4.4 tablosu 2M/50K/1.95M/5.4M).
Flagli tahminler (kullanıcı onayına açık): personel 33K ₺/ay ≈ 2026 asgari ücret işveren
maliyeti tahmini; Enes/Kadir 0,5 oran × Ay 7–18 (mezuniyet sonrası); pay oranı %3 korundu.
## Task: Build 5 jury-Q&A backup presentations (TÜBİTAK 1812 RV1)

**Date: 2026-08-23** — source table: RV1 deck slide 19 "Hazır Bulundurulması Gereken Yedek Slaytlar".
Output: `/home/safa/Documents/Bilun Extras/BIGG/Medipol/Back Up Presentations/`

### Goal
Five Turkish backup decks, facts-only (every number cited to AGY-112 v1.3 / RV1 deck /
interviews / repo artifacts; internal inconsistencies flagged, never silently picked).

### Subtasks
- [x] Extract facts via 3 parallel agents (technical; finance/IP/risk; competitor/customer) with "no source" lists
- [x] Write build script (python-pptx, 16:9, quiet design) producing 5 decks
- [x] Deck 1 Teknik Mimari & Test: pipeline, rule lifecycle, Track E diff (8263/94/26/0), coverage numbers (4757/2431/55/2271/622=%13,1), test protocol (2580 pytest + 242 frontend), fact-check 28 units (12/15/1/0), determinism+security, 6 zero-rows limits
- [x] Deck 2 Patent & FSMH: "Henüz başvuru yok" honest; legal rationale; ticari sır+telif+marka (Sınıf 9/42); FSMH envanteri; kurucu→AŞ devir; no EPO search / no university protocol (do not claim)
- [x] Deck 3 Rakip & Müşteri: statüko (Cerebral field quotes), Bizmed/EczAILab/RaporınAI, CodaMetrix/Waystar/Optum (unverified caveats), Olive AI lessons; Kent interviews verbatim; "Sözlü pilot onayı — imzalı sözleşme yok"; TAM/SAM/SOM AGY basis + inconsistency footnotes; Almalı paper 0.13–1.72% caveat
- [x] Deck 4 Finans & Ortaklık: price layers (2M flagship + 15–45K SaaS + %3–4 prim), unit economics, break-even both bases (2.8 vs ~6), milestones, 1812 budget %73/11/11/5 (Maliyet Formu empty-template caveat), %100 kurucu + %10 ESOP + %60 floor, investment path
- [x] Deck 5 Regülasyon & Risk: not-a-medical-device position; KVKK roadmap; etik kurul note; AGY 5-risk matrix table; expanded indicators/responsibles
- [x] Verify: LibreOffice PDF render of all 5; visual inspection of decks 3+4 (tables fit, TR intact, footers present)
- [x] Review section in this file

### Out of Scope
Redesigning RV1 main deck; adding logos/photos; inventing missing artifacts (LoI, EPO search, filled Maliyet Formu).

### Review
Delivered 2026-08-23 to `/home/safa/Documents/Bilun Extras/BIGG/Medipol/Back Up Presentations/`:
Yedek_1_Teknik_Mimari_ve_Test (8 slayt), Yedek_2_Patent_ve_FSMH_Devir_Plani (4),
Yedek_3_Rakip_ve_Musteri_Analizi (7), Yedek_4_Finans_ve_Ortaklik_Yapisi (7),
Yedek_5_Regulasyon_ve_Risk_Matrisi (7). Facts-only: every slide carries a source
footer (AGY-112 v1.3 §, RV1 slayt, interview date, repo path). Internal
inconsistencies (1M vs 2M price, 2.8 vs 6 break-even, TAM bases, 5.40 vs 5.46M
fixed cost, %3-7 vs measured %0.13-1.72) are flagged on-slide, never silently
picked. Missing artifacts NOT claimed: no patent/EPO search, no LoI, no signed
pilot contract, empty Maliyet Formu, no university devir protokolü — each slide
states the honest status instead.
## Task: Phase B migration scope lock (2026-09-19)

### Goal
Produce a Chief-reviewable `migration_scope_proposed` decision for the smallest coherent hidden, unpriced compliance migration slice without changing runtime, API, cache, frontend, or test behavior.

### Subtasks
- [x] Re-read the accepted audit plan, matrix, audit report, state, and journal; derive Wave A candidates only from matrix rows that satisfy every required eligibility condition.
- [x] Select the smallest coherent first vertical slice and document exact detectors, stable emitted rule IDs/kinds, explicit exclusions, and deferred candidates with reasons.
- [x] Define the one-evaluation canonical data flow, initial `RuleFinding` contract, identity/serialization rules, and exact implementation/test file map from domain through patient/cohort Compliance UX.
- [x] Define hard invariants, verification commands, and bounded implementation checkpoints for contract/domain, backend projection/cache/API, frontend surfaces, and CI regression.
- [x] Write `reports/rule-engine-surfacing/2026-09-19-migration-scope.md` and update state/journal while preserving accepted audit counts, hashes, and checkpoint provenance; leave state at `migration_scope_proposed` with next action Chief review.
- [x] Verify only the four authorized files changed, JSON remains valid, provenance/counts/hashes are preserved, no runtime behavior changed, and record the review evidence below.

### Out of Scope
Phase 5 implementation; runtime detector changes; API/cache schema or behavior changes; frontend changes; test behavior changes; financial/revenue migrations; production cache rebuild/deploy; commits, pushes, or merges.

### Review
Phase B proposes exactly three Tablo 15 line-integrity detectors for the first Wave A vertical: `detect_unreported_lab_result`, `detect_missing_drug_barcode`, and `detect_material_identity_errors`. The decision document derives them from the accepted matrix, records their stable rule/line identities, excludes all verified rerun equivalents and synthetic/financial/aggregate/catalog-only rows, defines the one-evaluation `RuleFinding` architecture, maps implementation/test files, and defers all remaining candidates with reasons.

State is `migration_scope_proposed` / `proposed`, phase remains 4, implementation remains `not_started`, and Chief review is the next action. Verification: the accepted starting checkpoint was confirmed as `5122d63472fcc8eb7182e7d45d3daf14c24c7a67`; `jq empty tasks/rule-engine-surfacing-loop/state.json` passed; the committed plan, audit generator, focused audit test, accepted matrix, and accepted audit SHA-256 values recomputed exactly to the hashes retained in state; all accepted audit counts remained unchanged; `git diff --exit-code -- src/bilun frontend tests scripts` passed; `git diff --check` passed; and trailing-whitespace inspection of all four authorized files found no matches. `git status --short` showed only the requested report/state/journal/todo paths. No runtime tests were run because this checkpoint intentionally changes no runtime or test behavior.

Chief review: accepted after independent matrix/source/rerun reconciliation. The next authorized unit is Phase 5 Checkpoint 1 only: canonical finding/evaluation contract and domain plumbing for K21, K26, and the three selected Tablo 15 line-integrity rules.
## Task: Final VPS correction — finding deep links and missing evaluations

### Goal
Consume canonical `finding` patient deep links with deterministic generic row highlighting and preserve only legitimate canonical `claim_id=null` unavailable evaluations in cohort counts, with truthful closure metadata and focused GREEN verification.

### Subtasks
- [x] Reopen the closure state against the current VPS worktree and record the exact migration-scope identity correction before implementation.
- [x] Add focused frontend RED regressions for route finding-query propagation, canonical finding selection/highlighting, and unknown-finding safe fallback.
- [x] Add focused backend RED regressions for counting a legitimate null-claim missing-input evaluation and rejecting malformed null-claim evaluations.
- [x] Run the new frontend and backend regressions and capture the expected RED evidence without changing production behavior first.
- [x] Parse `finding` in the patient route and pass it through the existing generic patient Compliance view to visibly select/highlight the canonical matching row while preserving legacy `action_id` fallback and safe unknown handling.
- [x] Update cohort evaluation validation to retain only well-formed null-claim unavailable evaluations with explicit missing-input metadata, without fabricating claim IDs or changing finding identity, deduplication, financial fields, or totals.
- [x] Run only the affected frontend/backend focused suites, `npx tsc --noEmit`, changed-module/test compileall, `git diff --check`, and invariant scans for financial/rule-allowlist/generated-cache changes.
- [x] Record exact GREEN results, changed files, remaining blockers, and no-commit/no-push boundary in this plan, the loop journal, and closure state; mark loop complete only after all focused gates are GREEN.

### Out of Scope
Financial formulas or totals, detector/rule semantics, rule-ID allowlists, canonical finding identity changes, new routes or schemas, broad/full test suites, generated dependency/cache files, production cache rebuilds, deploys, commits, pushes, PRs, merges, and patient data or credentials.

### Review
Implemented and verified the final VPS correction. Patient URLs now parse and propagate the generic `finding` query through the existing Compliance view; canonical `finding_id` rows visibly highlight, legacy `action_id` remains the fallback, and unknown/missing IDs leave normal rendering unchanged. Cohort validation now preserves only well-formed JSON-null claim evaluations with unavailable status and non-empty required/missing-input metadata, retains deterministic identity semantics without fabricating claims, and keeps financial rows/totals unchanged. Focused backend passed `22 passed, 1 warning`; frontend passed `5 files, 38 tests`; `npx tsc --noEmit`, compileall, Ruff, `git diff --check`, and invariant scans passed. One unrelated HTTP/cache dedup integration test exceeded the bounded 60-second VPS runner timeout; the financial regression passed. No commit, push, PR, merge, deploy, or production cache rebuild occurred.
## Task: Drug indication correctness, canonicalization, and UX — correction pass 1

### Goal
Resolve the independent-review blockers in the first-pass Drug Indication implementation: make route arbitration semantic and order-independent, restore the public legacy contract, keep live/cache/API/UI projections truthful and consistent, and leave the production correction ready for independent review.

### Subtasks
- [x] Add RED regressions for reversed/permuted full-corpus M06/M08 arbitration, canonical diagnosis ordering, corpus-derived diagnosis-specific/ICD-less families, public `validate_claim()`, cache/API round-trip counts, legacy normalization, noncoverage, deep-link selection, empty states, nonfinancial summaries, severity/contract fields, truncation metadata, and fail-closed structured validation.
- [x] Make route arbitration semantic and order-independent; return bounded `ambiguous_route` evidence instead of selecting by corpus order, and prevent ICD-less rules from establishing indication applicability.
- [x] Restore the complete public `/validate-claim` legacy projection, including `rule`, user-safe message, drug identity, explicit nonfinancial values, and stable canonical identities.
- [x] Unify live and cached report normalization/serialization and derive missing nested counts from structured findings/legacy violations without disagreement.
- [x] Add narrowly scoped honest normalization for genuine legacy cache payloads, including old empty/no-result and mixed modern/legacy payloads.
- [x] Represent `not_in_encoded_corpus` as a distinct bounded evaluation/manual-review state without inventing missing inputs, violations, routes, or financial values.
- [x] Thread exact `selectedFindingId` deep links through patient Drug Indication cards; add safe exact selection/highlighting and unknown-ID fallback.
- [x] Fix not-applicable, evaluation-only, noncoverage, and legacy progressive-disclosure UI states.
- [x] Preserve null/nonfinancial Drug Indication semantics through index, filtering, HTTP, and frontend summary/rendering paths.
- [x] Carry severity and every retained structured cohort field through action, cache/cohort, API, and frontend contracts; remove any intentionally patient-only fields from cohort output.
- [x] Add bounded-evidence counts/flags and truthful route/observed-diagnosis truncation disclosures, including available SUT source labels.
- [x] Tighten structured-entry validation fail-closed while retaining honest legacy parent compatibility, and remove plan trailing whitespace.
- [x] Run every requested RED/GREEN verification gate, direct original-vs-reversed corpus probe, deferred-path hash check, and changed-file security/artifact scan; record exact results here.

### Out of Scope
New §4.2 rules or corpus rewrites, broad Wave A/B/C/D expansion, frontend ICD disease dictionaries, financial/recovery semantics, production cache rebuild or deployment, dependency-lock changes, pushes, merges, PRs, and changes to `main`.

### Review — superseded first-pass evidence
The earlier first-pass review claimed completion, but independent review found blocking gaps in semantic arbitration, public legacy serialization, cached/live normalization, legacy-cache honesty, corpus noncoverage, deep-link consumption, empty-state UX, nonfinancial cohort semantics, projection contracts, truncation disclosure, and structured validation. That review is superseded; no audit checkpoint is claimed here.

### Correction pass status
Production correction and the post-production audit checkpoint are ready for independent review. The resumed saved worktree established a RED baseline of `28 failed, 124 passed`; after the bounded corrections, the exact requested suite passed `155 passed in 12.66s`, the affected backend corpus/API/cohort/financial suite passed `661 passed, 2 warnings in 67.53s`, and frontend Drug Indication/dashboard/deep-link coverage passed `3 files, 59 tests`. The direct M06.9/M08.0 probe produced byte-identical original/reversed/permuted payloads with honest `ambiguous_route` results and no selected rule.

After production commit `0e709489a54339f9fd4c2d143f0ce30a53ffb94c`, the deferred audit generator/test/matrix/Markdown checkpoint was refreshed with that exact source revision. The explicit noncoverage contract is that present but unencoded drug lines remain `not_in_encoded_corpus` manual-review evaluations, contribute no violation or money, invent no missing input, and make the Drug Indication/report rollup `partial_exact`. The CI repair focused suite passed `46 passed in 49.67s`; the exact backend CI command passed `2771 passed, 9 warnings in 1120.68s`; all 137 generated SUT rule/manifest artifacts were byte-identical; the surfacing generator `--check`, full-source Ruff, changed-file Ruff, and `git diff --check` passed. No merge, deploy, production cache rebuild, branch switch, or `main` change occurred.

---
## Task: Restore trustworthy frontend asset verification in Deploy

### Goal
Make the production deployment check find its verifier, accept healthy Next.js assets, reject missing assets, and run only after successful CI on this repository's main push.

### Subtasks
- [x] Reproduce the missing verifier on the GitHub runner and the escaped-asset false 404s against the live login page.
- [x] Add a same-repository main-push guard, ensure the VPS deploys only the exact commit whose CI passed, and check out that trusted CI commit on the Deploy runner without persisting checkout credentials.
- [x] Parse escaped Flight asset paths without retaining the escape backslash; preserve de-duplication and checks for real missing assets.
- [x] Add a regression using raw escaped Flight HTML and a local mock server, covering valid direct and Flight-only assets plus a genuinely missing asset.
- [x] Run focused verifier tests, source/workflow checks, and the verifier against the live login page; confirm the expected asset set has no malformed URLs.
- [x] Review the workflow privilege boundary, final diff, and focused test evidence independently.
- [x] Commit on an isolated branch, check existing branch CI, push, open a reviewable PR, and verify its backend/frontend CI checks.
- [x] Record final results and any remaining deployment limitation in this review section.

### Out of Scope
Additional Wave A detectors or rule migration, changes to production cache or pricing, and unrelated deployment architecture. Merging and production deployment wait for review of this specific PR.

### Review
Plan independently reviewed and approved before implementation, with a same-repository main-push gate, read-only checkout of the triggering CI SHA, and a remote SHA match before checkout or service work. Evidence: latest failed Deploy run 36263168625 completed the VPS step but could not find `scripts/deploy/verify_frontend_assets.py` in the runner workspace. The existing verifier separately found 16 malformed escaped URLs among 33 extracted live references; the corresponding clean assets returned 200. A diagnostic run found 23 unique healthy assets; this observed count is not a permanent contract. The workflow currently fetches latest main at deploy time, so an older green CI could otherwise ship a newer unverified commit; compare remote main with the triggering successful CI SHA before changing services.

Implementation verification: two escaped-Flight regressions failed against the old parser. Independent review caught a multiply escaped Flight-only path that the first fix still missed; its regression failed before the follow-up correction and passed after it. The focused file now passes 10/10 tests in 3.46 seconds from this worktree. Ruff and `git diff --check` passed. The workflow parsed as YAML, its deploy shell block passed `bash -n`, and targeted assertions checked its guard/checkout/remote-SHA ordering. The corrected verifier checked the live `/login` endpoint: 23/23 local assets returned nonempty HTTP 200 responses with zero malformed backslash URLs. Independent final diff review found no remaining blocker.

[PR #96](https://github.com/Safa675/Bilun/pull/96) contains the code on `fix/deploy-asset-verification`. Existing branch CI had zero runs before the push. Its [first hosted CI run](https://github.com/Safa675/Bilun/actions/runs/36315626985) completed successfully on commit `a55bb2a4` with both backend and frontend jobs green. The actual Deploy workflow can only validate this change after it lands on `main` and that main commit's CI succeeds; production deployment and merge remain outside this PR implementation task.

---


## Task: Resolve public-access review findings

### Goal
Fix the three verified PR #107 regressions on a branch based on verified current source, with regression tests and one new commit in a draft pull request from current main.

### Subtasks
- [x] Read current repository instructions and verify immutable current main source and PR state.
- [x] Bound outgoing chat context to 20 messages, 8,000 characters per message, and 32,000 total characters; validate new questions before persistence and preserve display history.
- [x] Remove the special developer exemption for username `test`; explicitly configure test allowlists and cover session revocation.
- [x] Include both supported LLM credential environment variables in public-asset scanning and cover the CLI environment path.
- [x] Run focused regressions, relevant broader checks where available, and independent review; record exact verification limits.
- [ ] Confirm the publication target, check its CI and current source, create one new commit and verify its remote contents when authorized.

### Out of Scope
No deployment, real LLM requests, main-branch updates, merges, or unrelated changes. The user approved a new pull request; merge and deployment remain out of scope.

### Plan Review
Reviewed against the three reproduced findings and current main bb41c3f6d78e25e5c0d766f1b0b64be6d4709274. Server limits remain unchanged; frontend display history remains complete. Allowlist policy is the sole developer authority. Only supported credential names are added to the existing scanner.


### Verification Review
- Full frontend Vitest: 71 files, 419 tests passed.
- Frontend TypeScript and production build passed.
- Asset scanner: 14 focused pytest cases passed, including four formerly missed LLM-key leak cases and redacted output.
- Revocation: eight real-session cases passed in an isolated real-auth/middleware harness; the original source failed the two `test` username unset/empty allowlist cases. Thirteen existing password/credential/token tests also passed in isolation.
- Scoped Python Ruff and compileall passed. Independent review found no blocking issue.
- Local Python is 3.12 and the backend checkout is partial; full backend pytest, generated-rule parity, and manifest checks require hosted CI on the published commit. Component handler tests use mocked React hooks; no browser interaction coverage is claimed.
- Original main bb41c3f6d78e25e5c0d766f1b0b64be6d4709274 was rechecked before branch creation; its backend and frontend CI passed. Exact new-commit hosted CI remains pending at publication.

## Task: Fix compatible health cache probes

### Goal
Return truthful health readiness while the running API owns a writable load-only cache connection, without mutating the cache or disturbing that connection.

### Subtasks
- [x] Verify current main source, repository instructions, existing health contract, and the DuckDB mixed-configuration failure.
- [x] Add regressions for existing writable and verified read-only runtime connections, missing caches, non-mutating fallback probes, and probe cleanup.
- [x] Reuse an existing runtime cursor only for the same database; otherwise open an independent read-only probe without initializing runtime state.
- [x] Run RED/GREEN regressions, focused lint and compilation, and independent review.
- [ ] Check base CI, publish one atomic commit on a new branch, open a draft pull request, and verify exact-commit hosted CI.

### Out of Scope
No merge, deployment, production database access, schema migration, cache build, or Wave A rule/activation changes.

### Plan Review
Reviewed against current main 05aba8152087cf049cebcd70ce1629e03ca94649 and the authorized health fix. Preserve the HTTP readiness and detail-access contracts. The probe executes SELECTs only, never calls get_cache_con/get_cache_reader (which can initialize schema), closes only its owned cursor/connection, and does not create a missing database. Success requires active-build health to pass with both runtime access modes while failure paths remain 503 and leave the runtime connection usable.

### Verification Review
- The original probe failed the real load-only singleton regression and misreported an existing writable database with an empty pointer as unreachable (RED: 2 failed, 8 passed).
- The final focused connection suite passed 17/17 tests with DuckDB 1.5.6, including both runtime access modes, repeated and parallel probes, first-reader initialization serialization, missing/other database paths, no schema initialization, byte-identical read-only fallback, startup-not-ready, and owned-cursor cleanup on success/error.
- Scoped Ruff and Python compilation passed.
- Local execution uses Python 3.12 with a partial checkout and an isolated import harness that loads the exact health functions, runtime, storage connection and schema modules. Full application imports, HTTP health tests, Python 3.13, and the full backend/Frontend suite are reserved for hosted CI on the published commit.
- Base main 05aba8152087cf049cebcd70ce1629e03ca94649 has passing backend and frontend checks. No production state was changed.

- Independent review reran all 17 focused regressions successfully and found no remaining blocking issue. The initialization-race case exercises real runtime initialization while the fallback probe holds the cache lock.

## Task: Fix secondary procedure payable bases

### Goal
Apply each procedure occurrence's session factor to its own whole-line payable, add regression coverage, and publish a draft PR with verified CI.

### Subtasks
- [x] Verify current main, repository instructions, pricing semantics, and downstream callers.
- [x] Add failing synthetic regressions for unequal line amounts, duplicate normalized codes, package memberships, quantities, exclusions, fallback amounts, and rounding.
- [x] Replace primary-derived amounts with own-line amounts while preserving occurrence alignment and existing blood caps.
- [x] Run focused regression and integration tests, repository quality gates where available, and independent review.
- [x] Reconcile the two F011 synthetic golden expectations exposed by hosted CI with exact own-line arithmetic.
- [ ] Check base CI, publish an atomic commit on a new branch, open a draft PR, and verify remote commit and hosted CI.

### Out of Scope
No merge, deployment, production records, blood/session overlap arbitration, blood applicability changes, historical catalog ranking fixes, or Wave A changes.

### Plan Review
Reviewed against main 45f97a64385c7b1959c44125b949f2d2e3e1e90b and the authorized standalone secondary-pricing fix. Preserve expected-payable/billed fallback, whole-line quantity semantics, exclusion filters, session grouping, final-total rounding, and existing blood caps. Use source-order factors without normalized-code collisions, retaining the factor-1 fallback for empty/invalid codes. Success includes 1000 + 100 at 30% = 1030, conservation for discount-only factors, and correct downstream DRG/strategy comparisons. Tests use synthetic records and explicit catalog fixtures.

### Verification Review
- RED: the original implementation failed 31 of 35 focused amount/occurrence cases. GREEN: the final focused selection passed 99 tests across session factors, amounts, specialties, DRG uplift, strategy, care-setting review, unbundling, and session uplift. Four existing tests requiring missing dental/synthetic assets were deselected from this focused run.
- New strategy and DRG regressions exercise the real session calculation: a 1100 package produces no false uplift, while a 1000 package produces exactly 30. The payment-compliance exclusion fixture keeps its real eligibility checks and now asserts the correct own-line total, 1885.96, with deterministic catalog ranking.
- Full source/script Ruff, changed-test Ruff, and changed-file Python compilation passed. Independent review reran the 60-case core suite and found no blocking source issue.
- Local verification uses Python 3.12 and a partial source/data checkout. Full pytest was attempted but stopped at collection on missing manifests/raw source assets and a missing requests dependency. Generated-rule checking also requires the absent manifests; manifest parity scanned zero files, so it is not counted as a pass. Complete Python 3.13 backend tests, generated-artifact/parity checks, and frontend gates remain for hosted CI on the published commit.
- Base main 45f97a64385c7b1959c44125b949f2d2e3e1e90b was rechecked with successful backend and frontend checks before publication. No production state was changed.
- First hosted run on 8567ee5: frontend passed all 419 tests and all frontend gates; backend passed 4290 tests with two stale F011 golden failures. SHA-verified synthetic rows and independent review confirm primary 600160 has payable 1800 and secondary 600150 has payable 2200 at 25%, giving itemized 2350 and package-9000 uplift 6650. Updated only the exact vignette/action expectations, added explicit itemized/package assertions, and retained existing tolerances. Five registry/lookup tests and Ruff/compilation passed; the complete hosted rerun remains pending for the follow-up commit.

## Task: Reconcile blood and session uplift

### Goal
Compute one recoverable gap per shared blood/session procedure line using the existing minimum-ceiling composition, then publish a separate draft PR with verified hosted CI.

### Subtasks
- [x] Verify current main after PR111, repository instructions, detector/report consumers, and encoded ceiling composition.
- [x] Add failing direct and report regressions for overlap, no-gap constraints, review-only amounts, identities, ordering, and partial overlap.
- [x] Share the session secondary assessment, cap its blood-line ceiling, and exclude its exact line identities from the independent blood detector.
- [x] Run focused tests, repository quality gates where available, and independent review.
- [ ] Check base CI, publish an atomic scoped commit, open a draft PR, and monitor hosted CI to completion.

### Out of Scope
No merge, deployment, production records, blood-rule package applicability changes, patient-history fixes, historical catalog ranking changes, or Wave A changes.

### Plan Review
Reviewed against main 09749e23f8ba6907f7addca8c7fddea8b66f8475 and the authorized F02 roadmap. Independent review agrees that matching opportunities must compose actual monetary ceilings with min, consistent with the existing session-adjusted payable calculation. A shared secondary-line assessment must cover lines without positive session gaps; ownership remains in the session block so DRG/add-on de-duplication consumes reconciled amounts. Keep the existing clinical-review restriction even when a blood cap reduces a review gap below its heuristic threshold. Never identify opportunities by code alone. Preserve independent lines and blood-only sessions, inputs, rounding, and existing package applicability. Python 3.12/partial data are available locally; hosted CI provides the full Python 3.13 and frontend gates.


### Verification Review
- Reproduced on merged main 09749e2: plasma billed 200 with session ceiling 340.41 and blood ceiling 408.50 emitted 140.41 + 208.50 = 348.91. The reconciled session-owned gap is 140.41; billed plus uplift is 340.41.
- RED: 15 of the first 17 new regressions failed before the fix. GREEN: all 26 final regressions pass, including the actual report assembler, DRG/add-on input boundaries, recommended actions, API serialization, live/cached recovery summaries, and cohort totals for confirmed and review-only cases.
- The broader focused selection passes 135 tests; two existing tests requiring absent synthetic claim tables are explicitly deselected. Source/script Ruff, changed-test Ruff, changed-file compilation, and diff whitespace checks pass.
- Independent review found no blocking issue and passed 104 focused cases plus 1,440 synthetic parameter combinations across amounts, quantities, fractions, incision/specialty settings, and ordering.
- Local Python is 3.12 with a partial source/data checkout. Full pytest was attempted and stopped on nine collection errors from missing manifests/raw source assets and requests. Generated-rule checking reports absent artifacts; manifest parity scans zero manifests, so neither is counted as a pass. The complete Python 3.13 backend, generated-artifact/parity, and frontend gates remain for hosted CI.
- Base main 09749e2 has successful backend and frontend checks. No production state, rule JSON, or unrelated task was changed.
- First hosted run on 98a296c passed 4316 backend tests and all frontend gates, with two scoped failures: the new ceiling evidence fields were absent from the frozen public DTO, and the blood demo still expected the duplicate confirmed 310 TRY. Added only those two scalar DTO fields with patient/bill public-projection assertions that retain private-field filtering. SHA-verified synthetic claim 0004 has blood list/payable 1000, billed 50, and primary P611720 billed 101019.30: min(300,360)-50 = 250, retaining the existing clinical-review restriction. Updated the demo to pin those exact amounts, identity, and zero confirmed blood uplift. The 26 regressions plus the actual 0004 test pass locally; hosted rerun remains the final gate.

## Task: Preserve bill-scoped claim history

### Goal
Restore known same-patient evidence for existing dated rules while keeping every bill's monetary lines and emitted findings limited to that bill, based on verified main 0e40e09f.

### Subtasks
- [x] Reproduce MIAT and ICU failures on verified main and add failing regression tests
- [x] Retain separate historical claim/procedure/material rows when slicing a bill, preserving active-row semantics and rejecting foreign or orphan history
- [x] Route MIAT, ICU overlap, duplicate exam/test and SCT temporal checks through history with their existing per-event date boundaries; scope results to active rows
- [x] Cover boundary dates, future/foreign evidence, repeated slicing, patient behavior, report/cohort additivity, public projection and cache serialization
- [x] Run focused suites, full pytest, lint and artifact checks; disclose environmental gaps
- [ ] Obtain independent diff review, verify main and prior CI, publish a separate draft PR, then monitor and fix scoped CI failures until terminal

### Out of Scope
Other audit findings; new rules or changes to rule constants and authored authority; broad Wave A work; real patient data; access/authentication changes; merge/deploy

### Plan Review
Independent reviewer confirmed the separate history design and the known consumers. History views must replace any retained active-claim rows with current active rows so repeated slicing and dataclass replacements cannot resurrect stale inputs. Duplicate detectors must see prerequisite history before filtering emitted target rows; focused projection must validate historic evidence without broadening source ownership. ICU report/audit rows, MIAT legacy/prose and SCT checks keep their existing dated predicates. Existing unavailable treatment-course/prior-therapy metadata remains unchanged. Success: ICU service bed 3→2 days, MIAT warning restored, unchanged current-bill billed totals and no future/foreign-triggered findings. Local partial checkout limitations will be distinguished from complete hosted CI.

### Verification Review
- RED on verified main 0e40e09f: all five new direct regressions failed (MIAT, ICU bed reconciliation, duplicate exams, duplicate tests, and SCT prior-transplant eligibility). GREEN: all 39 expanded regressions pass, covering date-window boundaries, unknown/future dates, ownership, active-row replacement, repeated slicing, and source-order ties.
- Real report/cohort runs cover single-worker and threaded bill calculations, current-bill money, per-patient additivity, another patient's isolation, focused evidence ownership, public projection, and a DuckDB bill-row round trip. The public DTO adds only ICU overlap day/date evidence and MIAT claim/section/package-code attribution; unknown/private fields still filter out.
- Independent review passed 132 focused tests and 960 bill slices over 240 seeded input orderings, comparing MIAT/ICU/exam/test/SCT results with the same bill's full-patient findings. A same-day SCT tie-order regression caught during review was fixed with identity-preserving history overlays and permutation regressions.
- The combined local focused selection passes 234 tests, including the actual 50-patient/per-bill synthetic report suite, existing public access/probe tests, and deterministic surfacing inventory. Source/script and changed-test Ruff pass.
- Full pytest was attempted on the local Python 3.12 partial checkout and stops at nine collection errors from missing manifests/raw source data and the requests dependency. Generated-rule checking requires absent artifacts; manifest parity scans zero manifests, so neither is counted as a pass. Complete Python 3.13 backend, frontend and artifact/parity gates remain for hosted CI.
- Main 0e40e09f was rechecked immediately before publication: backend, frontend and release-hold checks are successful. No rule constants, source authority, broad rule expansion, access controls, production data, merge or deployment are changed.
- First hosted CI395 on db322e6 passed 4356 backend tests and all frontend gates. Its sole failure was an existing deployment-verifier test explicitly asserting that cross-claim ICU evidence disappears from a bill. Updated that test to require exact ICU evidence parity with the service claim's patient finding while asserting service-only claim inventory and evaluation scope. No runtime code changed. The deployment/cache/history selection passes 61 tests locally; full hosted rerun remains the final gate.


---

## Task: Simplify single-VPS Wave A releases

### Goal
Provide one prepare/status/activate/rollback release interface with version-aware current-cache verification, exact final-artifact attestation and coherent paired recovery on ports 8001/3000.

### Subtasks
- [x] Verify source against main 3f5540cf and read repository instructions and prior tested rollout helpers.
- [x] Bound changes to release tooling, versioned activation integration and focused fault-injection/regression tests.
- [x] Implement original-five and strict current full-v2 baseline comparison across all persisted report/evidence rows without rewriting inputs.
- [x] Confirm and implement the paired-release state machine, preserving current history/mutable state and attesting actual final serving bytes.
- [x] Add operator prepare/status/activate/rollback interface and concise migration/runbook documentation.
- [x] Add explicit opt-in preparation snapshot maintenance for the initial writable load-only deployment; default refuses unsupported online snapshots before stopping services, and durable recovery restores the unchanged old pair before builds.
- [x] Independently verify baseline and candidate build-config environments against their stored hashes, preserving exact historical metadata.
- [x] Build the preparation bundle from explicit machine/input paths: consistent serving snapshot and retained baseline roster, fresh detached target/frontend, traced cache and all verification/rehearsal/signing gates; test fail-closed ordering, default no-mutation snapshot rejection and explicit recoverable snapshot-maintenance integration.
- [x] Verify rollback for failures around both service stops/restarts, database/source/frontend switches, interruption and retry; preserve all historical/mutable state.
- [ ] Obtain independent review and resolve substantive findings.
- [ ] Run applicable local checks, publish only changed blobs on a new draft PR, then verify full hosted CI at the exact final head.

### Out of Scope
Merging or deploying, user-computer/VPS operations, production credential/security/network configuration changes, broad runtime or billing redesign, historical crash attribution, data pruning, and unrelated cleanup.

### Review
User approved this PR. Work uses the authorized GitHub connector and isolated cloud workspace because the declined local task will not be retried. Source inventory is partial only for unavailable data/binary assets, so publication must derive from the verified complete remote base tree and include changed files only. Current-baseline design is confirmed: version comes from complete persisted evidence/report contracts, not API feature visibility or unchanged build_meta schema; original-five migration remains supported; current full-v2 comparisons validate both sides and normalize only independently bound identity fields. The paired transaction design must explicitly bind the final serving database; changing bytes after signing or weakening hashes is prohibited. No production command is executed during implementation.

Snapshot design decision: the current ordinary load-only service owns a writable DuckDB connection. Do not claim an undocumented hot-copy snapshot. The authorized PR includes explicit opt-in snapshot maintenance with warnings, shared locking, durable recovery and interruption tests; actual VPS execution remains out of scope. Later read-only online snapshot support requires tested reader-lock semantics.

## Task: Date-aware SUT drug amendments

### Goal
Select source-verified amendments by the actual drug service date, preserve older rule behavior and disclose missing temporal or clinical evidence.

### Subtasks
- [x] Verify current-main blobs and baseline focused tests.
- [x] Review plan and official October amendment evidence with coordinator.
- [ ] Add a versioned, source-pinned amendment catalog and strict date resolver.
- [ ] Integrate affected drug evaluation with explicit unresolved clinical gates.
- [ ] Propagate optional drug service dates through dict adapters and typed evidence.
- [ ] Add boundary, historical, unknown-date, source and no-false-compliance tests.
- [ ] Run focused and aggregate tests, lint and independently review selected-file overlay.

### Out of Scope
No merge, deployment, VPS access, invented clinical criteria, blanket source dates or claims that historical lower bounds are verified. Other SUT groups remain separate workstreams.

### Verified implementation contract
The service date is optional `drug_context.service_date`, mapped to the actual drug line, never the server date. Date-aware selection uses half-open validity intervals and fails closed on absent, invalid, overlapping or unsupported versions. The three explicitly annotated October 10 successor clauses are source-backed partial evaluations, not complete eligibility decisions. Legacy clinical checks may still run before that boundary, with an explicit unverified historical-version review. Thiotepa stays quarantined; no active amendment is inferred from consolidation. Temporal records do not inflate encoded-rule coverage. Public evidence is bounded and allowlisted, with source IDs/dates/hashes but no raw rule payload. Stream B owns the form/type; this stream owns backend contracts and domain tests.
## Task: 4 Ekim 2026 sınırlı klinik kaynak incelemesi

### Goal
Resmî pozitif kanıt varsa yalnız desteklenen klinik inceleme gününü eklemek; kanıt yetersizse 4 Ekim inceleme gerekliliğini koruyan, kaynak ve yürürlük sınırları doğrulanmış dar sonuç teslim etmek.

### Subtasks
- [x] Ana dizüstü kirli dosyalarını koru; 499dff4 tabanında bağımsız worktree oluştur ve repo talimatlarını oku.
- [x] 4 Ekim SGK ilan dizini, Resmî Gazete günlük içerik ve mükerrer göstergesini canlı resmî kaynaklardan gözle.
- [x] PR128 49af201 başındaki 10 Ekim ilaç / 2 Kasım organ nakli sınırlarını resmî belgeyle eşleştir.
- [x] Kanıt ve ortak dosya sahipliğini üst göreve bildir; clinical_versions.json sahipliği çözülmeden yazma. Üst görev tek yazarlığı 4 Ekim'de açıkça verdi; corpus sahibi patch aktaracak.
- [x] Yeterli kanıt halinde yeni gözlem/makbuz ve tek günlük pencereyi ekle; yetersizse salt inceleme kanıtını ve açık engeli kaydet.
- [x] Tarihsel boşluk, hukuki alt sınır, klinik kapsam, ertesi gün ve tahrif edilmiş kanıt kontrollerini hedefli çalıştır.
- [x] Bağımsız inceleme yaptır; doğrulanmış dar sonucu ve kalan engelleri Türkçe teslim et.

- [x] Yeni pencere eklendiğinde geçmiş continuity günü kendi makbuz kimliğini korusun; dar provenance düzeltmesini regresyonla doğrula.

### Out of Scope
Corpus/parquet yenilemesi, genel mimari, tam tıbbi ödeme uygunluğu, merge, VPS ve deploy.

### Specification and plan review
Kullanıcının devredilen talimatı kapsamı ve küçük taslak PR akışını onaylıyor. Yeni hukuki tarih veya hash çıkarımı yapılmayacak. 12 mevcut aile, Python kaynak otoritesi kataloğu ve hedefli pytest katmanı kullanılacak. Başarı: yalnız gözlenen gün için pozitif resmî kanıt veya dürüst kapalı sonuç; tarihi boşlukları doldurmayan ve clinical_eligibility_complete=false sonucunu koruyan doğrulama. Ortak dosya yazımı üst görevin sahiplik paylaşımına bağlı.

### Progress evidence
Baseline gerçekten çalıştırıldı: `/home/safa/Documents/Bilun/.venv/bin/python -m pytest tests/unit/domain/prose_rules/test_clinical_source_authority.py -q`: 100 passed (2.70s). Aynı runtime ile `scripts/sut/verify_clinical_source_authority.py --check`: 12 aile, 17 yerel asset, through 2026-10-03, exit 0. Yarım fetch commit nesnesi kontrol edildi: 49af201 mevcut. Geçici transport kesintisinde belirsiz yazım tekrarlanmadı; tek yazım bu plan.

New-window implementation review: Yeni pozitif 4 Ekim kanıtı aynı gün ve dört gerekli kategori için dondurulduktan sonra ayrı tek günlük pencere eklenecek. İncelemede mevcut resolver'ın geçmiş continuity gününe son makbuz metadata'sını atadığı görüldü; yalnız eşleşen continuity penceresinin makbuz kimliğini koruyan dar düzeltme kapsamda. Bu, evaluator değişikliği veya yeni mimari değil.

Frozen source result: 4 Ekim RG normal sayı 33390 günlük içerik, current homepage/Son Mükerrer göstergesi (6 Eylül), SGK GSS yeni SUT ilanları (2 Ekim) ve 3 Ekim ayrı ilaç geri ödeme yönetmeliği aynı gün 18:16:11 UTC'de başarılı HTTP200 gözlemlerle donduruldu. Canlı SGK değişiklik DOCX SHA a717ac7e9e932449461c353fcb3d3845ed834d104f35a75505c53185bbcfccbb ve konsolide DOCX SHA227b508558840f6c8083c6b6cc8c4efcbf1fcf342e115df5519b0f3e63d7f573 önceki proof ile bayt düzeyinde aynı. Yeni strict makbuz sgk-rg-clinical-2026-10-04T182213Z: 12 aile, 5 gözlem/4 tür, aynı İstanbul günü, tüm capture ve raw-byte hash kontrolleri exit0. Kanıt bütünlüğü ve resmî dijital imza farklıdır; birlikte yeniden yazılıp pinlenen tüm veriyi runtime bağımsız resmî doğruluk diye onaylamaz.

Commencement result: Resmî SGK konsolide body/w:p indeks1096 organ 02/11/2026;5572/5579/6056 ff/gg/aaaa ilaç10/10/2026. Takvim hesabıyla tarih üretilmedi. Gerçek ilaç temporal suite34 passed; helper suite2 passed; üç ilaç×09/10/11Ekim/None=12 doğrudan assertion geçti. Organ tarih alan runtime selector bulunmadı; PR128 yeni GateB(4)/(5) çıplak koordinatları eski transfer/donör anlamlarıyla çarpışabilir. Bu veri uyumluluğu görevinin açık inceleme konusu, bu kaynak PR'ı çözmez.

### Review
Son dokuz dosyalık hedefli paket, kaynak/HTTP/evaluator/observation testleri ve ilaç temporal testleriyle gerçekten çalıştı: **538 passed, 3 warnings, 17.82s**. Normal sandbox'ta TestClient/AnyIO portal askısı görüldü; izin incelemesinden geçen minimal in-process client 0.34s'de geçti ve aynı tam paket onaylanan ortamda exit0 tamamlandı. Gerçek server/port veya VPS kullanılmadı. Scoped Ruff ve `git diff --check` exit0. Final verifier:12 aile/25 repo-local asset/through2026-10-04, clinical_eligibility_complete=false; `/tmp/bilun-source-authority-assets-20261004.json`.

Bağımsız final diff incelemesinde P1/P2 bulgu yok. Eski katalog tüm alanları/pencereleri korunmuş; yalnız12 tek günlük pencere ve bir makbuz eklenmiş. Bağımsız36 gerçek3/4/5Ekim tarih kontrolü ve final8proof hash kontrolü geçti; ayrı HTTP dışı hedefli koşu394passed39deselected. İncelemecinin yarım HTTP koşusu exit130 ile durduruldu, pass sayılmadı. Kaynak sahibi full HTTP538pass sonucunu yukarıda ayrı doğruladı.

Yayın sırası: Bu kaynak yenilemesi mevcut9639c457 corpus üzerinde bağımsız dar taslak PR olacak. Corpus sahibinin gerçek veri geçişi+catalog seam paketi bunun üstüne ikinci taslak PR olarak taşınacak; ilk kaynak PR'ında corpus veya binding değişikliği yok. Merge/deploy yok.

## Task: PR150 kaynak CI onarımı

### Goal
Mevcut c4f736b kaynak ağacındaki üç doğrulanmış CI hatasını yalnız desteklenmeyen gün fixture'ı ve türetilmiş coverage kanıt hashleriyle düzeltmek; corpus ve dört coverage parquet dosyasını byte düzeyinde korumak.

### Subtasks
- [x] future_source SMA/antifungal fixture'ını ilk desteklenmeyen 5 Ekim'e taşı; not_evaluated ve sıfır predicate beklentilerini koru.
- [x] Mevcut coverage generator'ını geçici dizine çalıştır; dört özgün parquet dosyasının Git HEAD byte eşitliğini ve geçici çıktıyla tam schema/frame eşitliğini doğrula, yalnız mevcut helper'larla sut_coverage_evidence.json dosyasını yenile.
- [x] Coverage evidence ve documentary facts testlerini, anlamlı kaynak paketini, compile_rules.py --check ve 23 manifest parity kapısını çalıştır.
- [x] Değişen dosyaların dar kapsamını, corpus/parquet hashlerinin korunduğunu ve gerçek test sonuçlarını üst göreve teslim et.
- [x] Üst görevin açık yetkisiyle kaynak pencere uzatması, future fixture ve coverage hash kapanışı için kısa önleyici ders kaydı ekle.

### Out of Scope
Corpus geçişi, diğer branch dosyaları, runtime klinik veya tarih penceresi değişiklikleri, frontend kodu, commit/push/merge/deploy. Git işlemleri üst görevin sorumluluğunda.

### Specification and plan review
Üst görev üç hatanın düzeltmesini açıkça yetkilendirdi. DAY+2=4 Ekim artık geçerli kaynak günüdür; ilk desteklenmeyen gün 5 Ekim'dir. Kanıt yenilemesi yalnız dört kalıcı parquet dosyasının Git HEAD ile byte eşitliği ve generator çıktısıyla tam schema/frame eşitliği doğrulandığında uygulanacak; input corpus SHA256 9639c4578223ff46a40499270af5043d229ab2a1a1c3783114b43b64787384ac korunacak. Kaynak kapsamı sekiz yeni 4 Ekim gözlem/makbuz dosyasıyla kapalıdır. Plan uygulamadan önce mevcut generator ve CI komutlarıyla doğrulandı.

Plan refinement before evidence write: Geçici generator Arrow24.0.0 kullanıyor, kayıtlı parquet writer Arrow25.0.1; schema ve frame eşit olsa da serileştirilmiş byte farklı. Bu ayrım üst göreve bildirildi ve yalnız evidence yenilemesi açıkça yeniden yetkilendirildi. Dört özgün parquet ve input corpus Git HEAD ile byte düzeyinde aynı doğrulandı; evidence mevcut build_drug_coverage_evidence helper'ına özgün kalıcı coverage frame verilerek ve coverage_dependency_hashes helper'ıyla gerçek repo dosyaları hashlenerek oluşturuldu. Geçici parquet dosyalarının hiçbiri repo'ya yazılmadı.

### Review
Tek birleşik 11 dosyalık kaynak/ilaç temporal/documentary/coverage paketi gerçekten çalıştı: **721 passed, 2 warnings, 36.17s**. Normal sandbox'taki önceki documentary-only HTTP koşusu asılı kaldığı için exit130 ile durduruldu ve pass sayılmadı; birleşik koşu izin incelemesinden geçen süreç içi TestClient ortamında exit0 tamamlandı. Full backend suite yeniden çalıştırılmadı.

`compile_rules.py --check`: **134 rule/manifest artifacts byte-identical**, exit0. `audit_manifest_parity.py --drug-only`: **23 scanned, 23 with traces, 0 issues**, exit0. Kaynak verifier: **12 families, 25 repository-local assets, through2026-10-04**, exit0. Scoped Ruff ve git diff --check geçti. Dört kalıcı coverage parquet ve 9639 corpus Git HEAD byte hashleriyle aynı; JSON envanteri file_sha256 dışında değişmedi. Kaynak/test/evidence düzeltmesi ve görev/ders belgeleri dışında yazım yok; commit/push üst göreve bırakıldı.

Frontend job111504177367 yalnız bir kez individual rerun edildi; aynı c4f736b kaynak başını kullanan job111510110080'de **83 files/575 tests, typecheck, build, public-assets52files** geçti. Backend yeniden çalıştırılmadı; ilk run'ın başarısız backend sonucu tam CI başarısı sayılmaz. Bağımsız final kaynak diff incelemesi üst görev tarafından atandı.


## Task: PR128 corpus'unu kaynak PR'ı üstünde mekanik doğrulamayla taşı

### Consumer scope update and ownership — 2026-10-04
Üst görev, konumsal consumer uyumluluğunu mevcut veri uyumluluğu kapsamına açıkça aldı: eski coverage ile yeni corpus arasında toplam 4.177 key/4.174 hash uyumsuzluğu ve 36 manifestte 3.066 farklı kayda kayan C* atfı doğrulandı. Provisional dosyalar nihai diye kopyalanmaz. Aşağıdaki gerekli bağımlılıklar önceki beş dosyalık başlangıç kapsamını tamamlar; genel mimari ve klinik tarih/sınır/predicate değişiklikleri eklenmez.

- [x] authority_audit: aynı metnin bent/prose kaymasını mevcut canonical override ile düzelt; compiler ve gerekli manifest/rule çıktılarını mevcut üreticilerle yenile. Tam metin/parent/context değişen atıfları otomatik taşıma; kesin engeli raporla.
- [x] corpus_seam_review: nihai manifest/rule/catalog/source-authority kapanışından mevcut build_sut_coverage.py ile sut_clause_coverage.parquet, sut_coverage_by_rule.parquet, sut_coverage_by_section.parquet, sut_registry_coverage.parquet ve sut_coverage_evidence.json dosyalarını yeniden üret; gerçek consumer ID/key/fullhash ve negatif eski artifact testlerini doğrula.
- [x] independent_review: gerçek corpus40b2 ile hazır local-hash-v1/512 embedding dosyasının 4.090 ID/body/vector eşitliğini bağımsız doğrula ve exact dosyayı kur; 14 retrieval testi ve sıcak indeks kontrolünü çalıştır. Runtime mimarisini genişletme.
- [x] root: kaynak PR'ın bağımsız coverage_evidence pin kapanışını doğrula, gerekiyorsa kaynak corpus'u değiştirmeyen dar evidence düzeltmesini ayrı tut; ortak plan/katalog ve son Git yayını sahipliğini koru.
- [ ] Nihai source/migration/consumer testleri, scoped Ruff, compile --check, manifest parity, evidence closure ve bağımsız inceleme sonucundan sonra ikinci draft PR/full CI durumunu kaydet.

Coverage üretimi diğer girdi sahiplerinin FINALmanifestready sinyaline kadar bekler. Kaynak PR bağımsızdır; merge/deploy/VPS yapılmaz. Mevcut görevde Git yayını yalnız root tarafından yapılır.

### Existing consumer gates — scope confirmed for the night run
Üst görev mevcut veri uyumluluğu kod/test/inceleme/CI akışını tekrar onay almadan tamamlamayı onayladı. Negatif gerçek tüketici kanıtı organ kaynaklarının yalnız pending metadata ile korunmadığını, kaldırılan Carmustine guard-rule'ın ise mevcut correction kapısını atladığını gösterdi. Gerekli düzeltme mevcut iki tüketicinin dar kaynak kapısındadır; yeni klinik aile, genel admission mimarisi, tarih penceresi veya tıbbi predicate eklenmez.

- [x] boundary_audit: treatment_pricing mevcut legacy ve typed tüketicisinde explicit source_review_required durumunu predicate/ödeme sonucu öncesinde tarafsız review çıktısına taşı; kaynak inceleme flag'i olmayan kuralları koru, negatif ve normal tüketici regresyonlarını çalıştır.
- [x] authority_audit: organ kaynak locators/pending marker/policy digest verisini mevcut kapı sözleşmesiyle koordine et; değişen criteria'yı encoded sayma. İlaç correction guard'ının kaldırılmış geçersiz cite-rule'a bağlı olmadan source_target_mismatch davranışını korumasını mevcut temporal seam'de doğrula/düzelt.
- [x] authority_audit: deferral kaynak geçmişiyle kanıtlanan kayıtları mevcut canonical/ID sözleşmesiyle taşı; aynı key'deki farklı body/context veya çelişen judgment'ı otomatik medikal sınıfa atama, belirsiz kalanları açık raporla.
- [x] authority_audit: değişmeyen 2.4.1.(1) dental tam metin/context'i resmî October2 DOCX ile doğrula; mevcut dental_source_proof içinde yalnız gözlenen October2 snapshot sürümünü destekle ve ilgili mevcut policy digestini yenile. Hizmet tarihi/attestation alt sınırlarını, kaynak body hash'ini ve parasal davranışı değiştirme; unsupported snapshot/değişmiş body negatiflerini koru.

### Changed-source compiler contract — reviewed before implementation

Yalnız mevcut treatment_pricing_2_4 ailesinin üç değişmiş kaynak kaydı source_review_required=true, pending verification ve boş gate_b_sources ile derlenecek; tarihsel atıflar inert açıklama/makbuzda korunacak. İki mevcut consumer flag'i predicate öncesi tarafsız review olarak ele alır. Guard'ı olmayan ailelerde review-only marker kabul edilmez; normal encoded atıfların active/fullkey/heading kuralları gevşetilmez. İki değişmiş ff/gg kaydı ve bir yanlış hedefli Carmustine executable kaydı kaldırılırken mevcut temporal correction review davranışı korunur. Bu veri/derleyici sınırına pozitif/negatif test ve bağımsız inceleme gerekir.

Kaynak PR150 exact head58a73b117e71d9610d7e51cf854c3a23aba4fd7b tam CI476 başarılı:8069 backend/575 frontend,134 byte-identical artifacts,23 manifest/0issue. Corpus çalışma ağacı bu head'e ff edilmiş, başlangıç mekanik makbuzunun c4f736be baseline kanıtı değişmemiştir.

### Goal
Kaynak PR c4f736be tabanından PR128 corpus40b2 geçişini aynı klinik tarih ve binding sözleşmesiyle doğrulayıp ikinci dar PR için incelemeye hazır dosya paketi teslim etmek.

### Subtasks
- [x] Temiz corpus-transition worktree tabanı c4f736be ve 17f3694c kod/test kapsamını doğrula; mevcut repo talimatlarını oku.
- [x] Yalnız 17f3694c içindeki beş verifier/diff/test dosyasını ve iki clause-delta açıklama düzeltmesini taşı.
- [x] Gerçek PR128 candidate corpus ve tek atıf yapılan October2 DOCX baytlarını/hash'lerini doğrula; gerekli dosyaları seçerek hazırla.
- [x] Henüz değişmemiş c4f736be baseline katalog/corpus'u üzerinde yeni mechanical migration receipt üret; eski owner receipt'ini kopyalama.
- [x] Gerçek candidate corpus'u kur, katalogda yalnız corpus pinini ve Oct4 review evidence'e yeni receipt pinini ekle; tüm aile/pencere/hukuk/source alanlarını aynen koru.
- [x] Migration verifier/testleri ve kaynak PR'ın 538 hedefli testini onaylanan in-process ortamda gerçekten çalıştır; asset closure ve diff kontrollerini kaydet.
- [x] Exact CI generated gate engelini mevcut dar override/dependency yüzeyinde incele; önerilen ek dosya kapsamını yazmadan önce üst göreve bildir.
- [x] Aynı fulltext ve literal b) Word maddesi kanıtıyla mevcut YAML'da yalnız 4.2.8.A.b#2882a47a türünü bent olarak sabitle; başka key/opaque ID'ye taşınmadığını test et ve generated gate'i yeniden çalıştır.
- [x] Son dosya listesini, gerçek test sonuçlarını ve kalan engelleri üst göreve teslim et; bağımsız incelemeyi bekle.

### Out of Scope
Merge, deploy, VPS, commit/push, PR yayınlama; owner/parent repo yazımı; ingest_state, genel manifest/annex ve tüm442 PR asset'inin taşınması; klinik tarih, hukukî sınır, binding, schema/runtime değişiklikleri ve yeni ödeme uygunluğu iddiası.

### Specification and plan review
Üst görev iki PR sırasını ve bu dar implement paketini açıkça onayladı. Hedef Python3.13 mevcut Bilun .venv'dir. Başarı: c4f736be baseline ile gerçek PR128 Git blobu arasında72 unique binding/8 proof dosyası/12 aile bağlam uyumu; actual installed corpus40b2 ve yeniden üretilmiş makbuzla verifier/test geçişi;5Ekim fail-closed ve source PR continuity receipt fix'i aynen kalır. Plan kapsamı delegated talimatla eşleştirilerek implement öncesi gözden geçirildi.

### Progress evidence
Narrow dependency plan reviewed before write: Üst görev mevcut canonical YAML override desteği ile tek tür düzeltmesini gerekli corpus dependency olarak onayladı. Eski C004159 ve yeni C004167 için full normalized text SHA256 `2882a47a74ff4d7ab0194f6eb1ed4a2aeef8653bd3e370268280d125cc395d24`, coordinate4.2.8.A.b,section4.2.8.A,parent4.2.8,letterb,in_force ve non-heading aynıdır. Git DOCX direct body w:p indeksleri4377/4385 literal `b)` ile başlar ve full normalize edilmiş Word metni corpus'a birebir eşittir. Öneri yalnız `data/gazette/clause_type_overrides.yaml` canonical key→bent ve `tests/unit/scripts/test_stable_clause_type_overrides.py` persistent regression guard'dır; corpus, runtime/schema/strict encode şartı veya generated çıktı değiştirilmez. Kesin dosya/kanıt üst göreve yazmadan önce bildirildi.

Fresh receipt `corpus_migration_pr128.json` c4f736be kaynak baseline'ından gerçek49af2019 candidate Git blobu ile yeniden üretildi:12 aile/8 binding dosyası/72 unique binding; SHA256 `3c7f781b8e223adc6073e69b1dff4af7b5b0e7cb106814a1ca016dde8b3c5bde`. Kurulu corpus gerçek40b2,8413 satır,1421343 bayt. Katalogu yalnız corpus pinini ve Oct4 makbuz evidence satırını geri alarak karşılaştıran assertion tüm eski alanların birebir korunduğunu doğruladı; source_authority.py c4f736be ile bayt düzeyinde aynı. Yalnız tek October2 DOCX taşındı; ingest_state, annexler ve genel manifestler değişmedi.

Son 12 dosyalık birleşik pytest koşusu onaylanan in-process ortamda gerçekten tamamlandı: **579 passed, 3 warnings, 28.54s**. `TESTING=1 BILUN_AUTH_OPTIONAL=1 BILUN_AUTH_USERNAME= BILUN_AUTH_PASSWORD= BILUN_SESSION_SECRET= PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`, pytest `--confcutdir=tests/unit -p no:cacheprovider -o faulthandler_timeout=30` kullanıldı. İlk koşudaki tek hata renal testin eski opaque ID beklentisiydi; beklenti runtime collector'dan değil sabit6 canonical clause key ve kurulu corpus lookup'tan türetildi. Oct4 parity günü migration testlerine eklendi; Oct5 review_required kaldı. Scoped Ruff ve `git diff --check` exit0. Kaynak verifier `--check --json-output /tmp/bilun-corpus-transition-source-assets-20261004.json`:12 aile/26 asset/through2026-10-04, exit0.

Exact CI `scripts/sut/audit_manifest_parity.py --drug-only`:23 manifest/23 trace/0 issue, exit0. `scripts/sut/compile_rules.py --check`:exit1, `csv_wave_clause_ids_metabolic_mid` hedefinde `4.2.8.A.b#2882a47a` candidate C004167(prose) strict encode-eligible şartını karşılamıyor. Aynı metin/key eski corpus'ta C004159(bent); candidate raw Git blobu da prose. Compiler finally bloğu önceden var olan çıktıları geri yükledi; git durumunda generated artifact değişikliği yok. Engelin dar dependency teşhisi sürüyor, bu gate başarılı diye sayılmadı.

### Final producer dependency closure — 2026-10-04

Üst görev, gerekli consumer source guard, runtime/code ve Git/draft PR akışını yetkilendirdi. Başlangıç owner paketinin Out of Scope listesi bu sonraki yetkiyi kısıtlamaz. Genel mimari, yeni medikal predicate/eligibility, tarih uzatması, merge/deploy/VPS kapsam dışında kalır.

Yenilenmiş coverage engine-owned ID envanteri yedi mevcut GateB manifestinin çıktısını değiştirdi. Mevcut compiler WRITE 43 hedefte exit 0; CHECK 134 artifact için byte eşitliği ve drug parity 23/23, sıfır issue ile tamamlandı. Mevcut 939 kural JSON'u byte düzeyinde değişmedi. Eklenen 214 trace aynı baseline full body/parent/context kaynaklarına eşleşti: 80 encoded trace mevcut kural cite'lerinden, 134 deferred trace mevcut authored judgment'tan geldi. Dört trace, existing other-engine primary ownership filtresiyle export'tan çıktı; eski trace payload değişimi sıfır. Provisional/current envanter ile final in-memory normalized producer, yedi engine-owned ID kümesinde birebir aynı doğrulandı.

Consumer report SHA256 `e348650810218bed7e7c8eec18be7e4161d66feda859f8103fa51a4a2bec456d`; catalog SHA256 `07d86ce0a1a978683a72457abe9400a954b0b1e69e9e8ce94b8d308ae2e24471`. 457 fixed input ve 134 monitored output pini kapalıdır (128 mevcut, 6 açıkça absent). Yalnız Oct4 review içindeki mekanik report pini yenilendi; kaynak pencereleri, hukukî sınırlar, tarihsel boşluklar ve clinical_eligibility_complete=false korundu. Kaynak verifier 12 family/27 asset, through Oct4 ile exit 0.

Önceki birleşik author testi **1.662 passed, 3 warnings, 33.65s** ayrı aşamadır. Coverage üreticisinin mevcut authored normalizer çağrısı ve stable source catalog fixture paketi **101 passed, 1 warning, 6.41s** tamamlandı.

Son beş coverage dosyası existing CLI ile final girdilerden üretildi; **124 passed, 1 warning, 7.57s**. 150 dependency hash'i freeze öncesi/sonrası ve evidence içinde birebir aynı; source corpus 40b2 değişmedi. 4.781 aktif satırın immutable ID/key/full body/context alanları ve production-normalized 31 kaynak alanında sıfır uyuşmazlık var. Meşru duplicate-key ekstra 111 satırın multiplicity'si korundu. Root final coverage sonrası compiler --check (134 byte-identical), global Ruff src/scripts, git diff --check ve 58-parent catalog deep comparison exit 0. Yalnız corpus pini ve iki mekanik evidence kaydı geri alınınca katalog tamamen parent ile eşit: version/date/legal/history/receipt alanları değişmedi.

Final coverage evidence SHA256 `6a4d26407b1c3ad8d365a523912aaff5dc4b2002562b07fffef1ea150c4d3092`; diğer dört parquet hash'i bu dosyada gerçek dosya baytlarıyla kayıtlıdır. Bağımsız final test hükmü ve hosted full CI henüz bu kayıtta başarı sayılmadı.

### Independent final review

Tek bağımsız birleşik paket gerçekten **468 passed, 2 mevcut RefResolver warnings, 25.25s** tamamlandı; failure/skip yok, 15 retrieval testi dahil. HTTP/fullsuite veya generator çalıştırılmadı; ayrı task-2 basetemp kullanıldı. Bağımsız source verifier 12 family/27 asset, through Oct4 exit 0. Son read-only assertions exit 0: 457 input, 29 test hash'i, 134 output (128 mevcut/6 deliberate absent) ve 150 coverage dependency hash'i birebir eşit. Katalog 58-parent ile yalnız corpus pini ve iki mekanik kanıt kaydı dışında tamamen aynı. 36 family/date kontrolünde Oct3–4 admitted, Oct5 uncovered_service_date/review_required, clinical_eligibility_complete=false. 4.781 coverage satırının 31 normalized kaynak alanı eşit; gerçek PR128 corpus 8.413 satır/40b2 byte uyumlu. Embedding 4.090×512 local-hash vektörlerinin tamamı yeniden hesaplanarak birebir eşleşti; body hash mismatch sıfır, cold/warm index aynı ve beş query kaynakla uyumlu. Runtime retrieval hash guard eklenmedi; doğrulanan mevcut artifact ve CI coherency testidir.

Bağımsız code/data review P1/P2 bulgu yok; yedi manifestin ek 214 atfı ve 500 mevcut trace payload eşitliği ayrı salt okunur incelemede doğrulandı. Geniş 44-manifest audit'indeki iki copay sorunu 58-parent ile aynı ve bu değişiklikte giderilmiş sayılmadı. Hosted full CI hâlâ bekleniyor; merge/deploy/VPS yapılmadı.

## Task: Corpus CI484 gerçek hatalarını dar kaynak/consumer kapılarıyla düzelt

### Goal
PR154 e11bd142 üzerindeki gerçek 41 backend hatasını mekanik fixture bağımlılığı ile gerçek runtime/snapshot driftini ayırarak düzelt; tarihsel serving izinlerini ve klinik sınırları koruyarak yeni exact head için hosted CI ve bağımsız incelemeyi tamamla.

### Subtasks
- [x] Root: CI484 logunu sakla ve 41 failure sınıflamasını gerçek kaynak/projection kanıtıyla kaydet; frontend tek retry sonucunu backendden ayrı raporla.
- [x] authority_audit: domain/prose stale C* beklentilerini old9639→40b2 aynı full body/context kanıtıyla değiştir; gerekirse yalnız test amaçlı static source identity helper/fixture sahipliğini seam ile paylaş. Consumer çıktısını oracle yapma.
- [x] corpus_seam_review: scripts/GateB/context fixture'ları ve negatif mutasyon hedeflerini gerçek kanıtlı kaynak satırlarına taşı; strict rejection beklentilerini koru. 4.2.14.C census'u bağımsız current source inventory ile doğrula.
- [x] boundary_audit: semantic fingerprint, focused legacy eşitliği, dental fallback, runtime coverage, pipeline smoke ve mevcut surfacing raporlarının gerçek kök nedenini önce bildir. Expected değerlerini yalnız CI geçsin diye değiştirme; gerekli mevcut dar consumer düzeltmesini projection/source kanıtı ve negatif test ile yap.
- [x] independent_review: özellikle historical old→3e release verifier fingerprint/source/serving kapsamının genişlemediğini, fixture bağımsızlığı ve negatif davranışın korunduğunu salt okuyarak doğrula.
- [x] Root: sahipler final code/test/output freeze bildirdikten sonra mekanik consumer report/catalog pin ve coverage evidence kapanışını mevcut helper'larla yenilet; dört coverage parquet'in değişmeden kaldığını veya gerçek gerekçeli üretim farkını açıkça doğrula.
- [ ] Gerçek değişen hedefli testler, compiler/parity/Ruff/source closure ve bağımsız review sonrası yalnız CI hata düzeltmesini commit/push et; yeni head hosted full CI sonucunu ayrı kaydet.

### Out of Scope
Yeni klinik yorum/predicate, tarih penceresi/hukukî sınır uzatma, genel mimari, historical old→3e fingerprintlerini global yeniden baselining, yeni serving transition izni, diğer PR151/152/153 entegrasyonu, frontend kodu, local fullsuite tekrarları, merge/deploy/VPS.

### Specification and plan review
Üst görev mevcut corpus geçişi kapsamındaki mekanik fixture/generated rapor düzeltmelerini açıkça onayladı; kritik fingerprint/dental/legacy durumlarında kaynak/projection kanıtı ve negatif test olmadan gevşetme yasak. Plan owner'lara uygulama öncesi bildirildi. Kaynak PR150 exact58a ve başarılı CI476 değişmez. CI484 gerçek sonuç **41 failed, 8239 passed, 27 warnings, 1124.41s**; compiler/parity backend failure nedeniyle hosted çalışmadı, başarılı sayılmaz. Frontend ilk job111533647997 typecheck/575 test geçti, build font-query hatasıyla düştü. Run bitince yalnız o job için bir rerun kabul edildi; backend rerun yapılmadı. Log task-2/corpus-ci484-backend-failure.log içinde.

### CI484 repair evidence before common closure

CI484 gerçek 41 failure node: 13 domain source-ID fixture, 20 scripts/GateB/source-context fixture, 8 kritik boundary alanı. Kritik alanlar iki gerçek consumer/package hatası (optional dental fallback None ve pipeline seçilen DOCX input-dir eşleşmesi), iki source/projection fixture, bir tarihsel public-coverage fixture ve üç existing surfacing generated-report kontrolüdür. Hosted ilk backend sonucu 41 failed/8239 passed kalır; ayrı frontend tek retry job111538195898 575 test/typecheck/build/public52 ile başarılıdır. Bu sonuç bütün CI başarısı sayılmaz.

Owner koşuları ayrı gerçek aşamalardır: authority RED13 failed/371 passed → GREEN393 passed13.18s; seam RED19 failed/47 passed (committed writer eski test hariç) → GREEN68 passed16.68s; boundary birleşik136 passed22.40s. Bunların toplamı fullsuite sonucu olarak kullanılmaz. 4214c writer tmp_path'a yazar; 655 census bağımsız gerçek source inventory ile hesaplanır. Static fixture131 aktif kimlik taşır; inactive C004584 remap edilmez,10 aynı full body/context eşleşmesi komşulukla ayrıştırılır.

Bağımsız salt okunur inceleme actual immutable Git3f/3e public generatorlarını yeniden çalıştırdı: baseline6ff617…/28input/c556eaf… ve product375aed…/30input/fa4e9ce… fixture/provenance birebir eşleşti. Release verifier/deploy source byte-unchanged; old→current ve current→current actualcoverage reddedilir, üç current route fingerprint pozitif kontrolü korunur. Consumer helper'dan bağımsız131source ve262komşuluk pini doğrulandı. Surfacing97row94byte-equivalent dictionary, exact3invaliddrugIDremoved, financial findings359→359. Ortak report/catalog/evidence kapanışı, final tek focused gate ve yeni exacthead hosted CI henüz pending.

### Final CI repair closure before publication

Consumer report SHA256 b273b9b6a972d5e963a55bda0e5731b35c1b06d7ff6bcf491c63d414e19820c8 (1466826B); catalog b4e65f80f2846699875679ce5ef74d6f55280aac6415189262ddebe89a154194 (19550B). Actual maps467 input/60 test/134 output(128present+6expectedabsent) sıfır uyuşmazlıkla kapandı; yeni3helper ve3historicalpublicfixture açıkça test provenance girdileridir, production/serving yetkisi değildir. Catalog yalnız existingconsumerreportSHA alanında değişti. Finalcoverageevidence227efe04c7cc785b4560d0f9e1b5b3712d1dd9d8e67ac6494809a08161f11dbe (127548B)150dependency içerir; yalnızcatalog/reporthashleri değişti, dörtcoverageparquet HEADe11 ile byte-identical kaldı.

Root compiler --check134byte-identical, drugparity23/23zeroissues, globalRuffsrc/scripts ve gitdiff--check gerçekten exit0. Tek son bağımsız pytest174passed/2mevcutwarnings/30.11s, exit0: CI484 original41failurenode (kanıtlı yeniden adlandırmalar dahil), helper/dental/pipeline negatives, historicalgolden/currentrejection, kaynak/coverageclosure ve11retrieval testi. JUnit sayımıyla ayrışan dört index initialization testi bu174 sayısında yoktur; yalnız bu eksik dört test ayrıca gerçekten4passed/0.20s ile tamamlandı. Son retrieval kapsamı11+4 ayrı koşudur. Independentfinalreadonly467/60/134/150hashpin,58-parentdeepcatalogcomparison,36family/date ve12family/27assetsourceclosure assertions exit0. Full hosted CI yenihead için henüz çalışmadı; bu174 sonuç CI484 history41fail/8239pass veya fullsuite sonucu ile toplanmaz. Merge/deploy/VPS yapılmadı.

CI repair bağımsız final code/data review: P1/P2 bulgu yok; post-test pin/dış hash/diff kontrolleri geçti. Tam actual komutlar ve sonuçlar task-2/independent-ci484-final-commands.json, review makbuzu task-2/independent-ci484-review-result.json içinde. Hosted yenihead fullCI sonucu bu incelemeye dahil değildir.
