# Public billing access and authenticated developer access

Date: 2026-09-29
Status: Implementation authorized by the user for a new PR; deployment remains a separate release action.

## Goal

Let visitors use Bilun's existing synthetic Billing Officer workflow without signing in. Require a verified developer login for engineering features, and enforce that separation on the server so URLs, cookies, API calls and chatbot requests cannot reveal protected implementation information.

## Confirmed requirements and boundaries

- All current patient and billing records are synthetic/demo data. Anonymous access uses that existing dataset; this change does not require a separate database or a new dataset.
- Opening the app enters Billing Officer mode immediately. A **Developer sign in** action opens the login screen. Successful authorized login opens Developer mode; successful sign-out returns to Billing Officer mode.
- Preserve existing officer workflows, reference tools, validation, chat, findings, amounts, actions and necessary SUT citations. Do not remove a business feature merely because it uses a route with `rules` in its name.
- Developers retain their existing technical views after authentication. The server, not a browser preference, grants this permission.
- Protect Python implementation files, complete private rule definitions, repository tools and unnecessary engineering metadata. Browser JavaScript and permitted API outputs remain inspectable. This plan does not promise that users cannot infer behavior from legitimate inputs and outputs.
- The user authorized implementation and a new PR after approving this plan. Production deployment, credential changes on the live host, and merge remain separate release actions.

## Investigation baseline

The verified live release is `b5098a33c3fc9cbbc123b2446d4ef6353a60d28e`; local `/opt/Bilun` main was `4af38b28`, and the newer billing UX worktree was `85d21345`. Establish the current integration base before implementation; do not implement or deploy from the older main checkout without reconciling the active release and relevant merged UX work.

Evidence:

- [Investigation and findings](/root/artifacts/bilun-code-exposure-investigation-2026-09-29/report.md)
- [Backend authorization tests](/root/artifacts/bilun-code-exposure-investigation-2026-09-29/backend.md)
- [Frontend role and route review](/root/artifacts/bilun-code-exposure-investigation-2026-09-29/frontend.md)
- [Live deployment identification](/root/artifacts/bilun-code-exposure-investigation-2026-09-29/deployment.md)
- [Browser asset measurements](/root/artifacts/bilun-code-exposure-investigation-2026-09-29/browser-code-size.md)

Current relevant implementation:

| Area | Verified starting point |
| --- | --- |
| Login/account model | One configured shared username/password, with server developer classification through `BILUN_DEV_USERNAMES`; this is not a multiuser account directory. [auth.py](/root/artifacts/bilun-wavea-2026-09-27/release-prep/candidate-checkout-b5098a33/src/bilun/api/auth.py:63) |
| Frontend mode | The role selector offers developer mode and writes browser preferences. [RoleSwitcher.tsx](/root/artifacts/bilun-wavea-2026-09-27/release-prep/candidate-checkout-b5098a33/frontend/src/components/shell/RoleSwitcher.tsx:9), [RoleProvider.tsx](/root/artifacts/bilun-wavea-2026-09-27/release-prep/candidate-checkout-b5098a33/frontend/src/components/shell/RoleProvider.tsx:45) |
| API boundary | The common gate verifies a session, while engineering catalogue endpoints lack developer permission checks. [API middleware](/root/artifacts/bilun-wavea-2026-09-27/release-prep/candidate-checkout-b5098a33/src/bilun/api/__init__.py:119), [rules router](/root/artifacts/bilun-wavea-2026-09-27/release-prep/candidate-checkout-b5098a33/src/bilun/api/routes/rules.py:34) |
| Core engine | Python evaluates rules on the server and exposes results, not implementation files, through the reviewed billing flow. [patient_report.py](/root/artifacts/bilun-wavea-2026-09-27/release-prep/candidate-checkout-b5098a33/src/bilun/domain/billing/patient_report.py:95) |

## Target access policy

Use a trusted server identity plus explicit capabilities. Anonymous visitors have only the public billing capabilities. A valid signed session whose username resolves to developer may use developer capabilities. Existing valid nondeveloper sessions must never acquire developer access.

| Surface | Anonymous / Billing Officer | Authenticated developer |
| --- | --- | --- |
| Billing workspace, synthetic patients/bills, compliance and revenue summaries | Available with approved public response fields | Available |
| Officer reference tools: material/procedure/drug lookup, price history and other existing officer tools | Preserve current functionality through bounded, sanitized business endpoints | Available |
| Claim validation | Keep the officer-facing current contract; cap request size/work and sanitize results | Current and explicitly supported developer/legacy contracts |
| SUT clause drawer and citations | Citation text and needed public identifiers | Citation text and permitted engineering detail |
| Billing/Wave A evidence | Business explanation, amounts, findings and relevant citations only | Engineering evidence where intended |
| Rule Database, engine inventory, encoding coverage, deferrals, implementation mappings | Denied | Available |
| Chat | Officer context and an explicit officer tool allowlist; same output filtering as direct APIs | Developer context/tools under verified permission |
| Repository read/search tools and raw internal diagnostics | Denied | Existing constrained developer behavior |
| Health | Minimal status/readiness needed by the public UI and uptime probes | Detailed diagnostics through a protected surface |
| API documentation/schema | Denied or disabled in production | Explicit protected access if retained |
| Raw source/configuration files | Never served by ordinary application routes | No new source-download feature is introduced |

Rules for enforcement:

1. Classify endpoints by **HTTP method and actual route**, not a broad prefix. Every new API route must have an explicit access classification; unclassified routes fail closed.
2. Preserve an explicit public citation projection for `/api/rules/clauses/{id}` used by the officer drawer. Do not open the rest of `/api/rules/*` to accomplish this.
3. Keep `/api/rules`, `/api/rules/prose-inventory` and `/api/rules/deferrals` developer-only. Inventory the remaining detail, source, coverage and Wave A routes before changing the public gate.
4. Keep the current officer validation flow public after bounding and filtering it; restrict `/api/validate-claim/legacy` to developer access unless a verified officer dependency requires a migration first.
5. Unsupported methods and alternate paths must not inherit public permission. Direct backend requests and stale frontend clients receive the same policy as the current UI.
6. Missing/invalid/expired sessions may use approved public billing routes only. Developer APIs return 401 without a valid session and 403 for a valid session lacking permission; frontend routes show developer sign-in or an access-denied state without rendering protected content.

### Starting route inventory

This table records routes inspected in the active candidate; verify it against the final mounted route table during Phase 0. API paths below include `/api`; `/health` and FastAPI documentation paths are separate. It is an explicit starting inventory, not permission to exempt entire prefixes.

| Access | Methods and route patterns |
| --- | --- |
| Public auth/status | `GET /api/auth/me`; `POST /api/auth/login`; `POST /api/auth/logout`; minimal `GET /health` |
| Public synthetic patients/claims | `GET /api/patients`, `/api/patients/search`, `/api/patient/{id}/outcome`, `/api/patients/{id}/claims`, `/api/patients/{id}/claims/{claim}` |
| Public projected billing/analytics | `GET /api/billing-report/{id}`, `/api/billing-report/{id}/bills/{claim}`, `/api/optimization-summary`, `/api/patient/{id}/optimization`, `/api/patient/{id}/bills/{claim}/optimization`, `/api/revenue-recovery`, `/api/patient-alerts`; `GET` and `POST /api/compliance-index` |
| Public synthetic operations | `GET /api/medula-rejections/ingest-status`, `/api/medula-rejections/queue` |
| Public reference tools | `GET /api/procedure/{code}`, `/api/material/{code}/pricing`, `/api/visit-pricing`, `/api/price-history/{code}`, `/api/lab-prices`, `/api/drugs`, `/api/materials/by-specialty`, `/api/bundled-consumables` |
| Public bounded computation/chat | `POST /api/validate-claim` using the current v2 contract; `POST /api/chat` using officer capabilities |
| Public citations | Exact `GET /api/rules/clauses/{clause_id}` with citation-only output |
| Public projected evidence | `GET` and `POST /api/wavea-evidence-index`; `GET /api/wavea-evidence/{patient_id}`; `GET` and `POST /api/wavea-evidence-rows` |
| Developer catalogue routes | `GET /api/rules`, `/api/rules/{rule_id}`, `/api/rules/sections`, `/api/rules/sections/clauses`, `/api/rules/clauses` bulk browsing, `/api/rules/prose-inventory`, `/api/rules/deferrals`, and both registered prose-rule source routes |
| Developer computation/diagnostics | `POST /api/validate-claim/legacy`; the registered `/api/weekly-brief` route; protected detailed health and production schema/documentation if retained |
| Other frontend/server surfaces | Inventory Next route handlers and their methods too, including the existing feedback flow; keep their current supported behavior only after checking payload and side-effect boundaries. No general public exemption for server actions, downloads or future endpoints. |

Reference: the active [API router registration](/root/artifacts/bilun-wavea-2026-09-27/release-prep/candidate-checkout-b5098a33/src/bilun/api/routes/__init__.py:65) and the registered modules in that directory. The newer Wave A routes and v2/legacy validation split must be included; the older main checkout has fewer route declarations.

`/api/weekly-brief` has no frontend caller identified in this review and remains developer-only initially; preserve user-triggered officer chat and its existing auto-brief behavior. The frontend requests `/api/frontend-config`, but neither inspected backend registers it. Do not describe it as an existing working API: retain the current fallback or add a minimal public presentation/demo-status contract only if the redesigned shell requires it, without exposing internal weights. No current export/download API was identified; if one is introduced or found during implementation, classify it explicitly.

## Delivery phases

### Phase 0 — Establish the implementation base and inventory

- [ ] Create an isolated implementation worktree from the agreed current integration base; preserve other tasks and the deployed candidate.
- [ ] Read current repository instructions/lessons and reconcile the active release, billing officer UX changes and any newer merged changes.
- [ ] Inventory all registered API methods/routes and the requests made by each officer workflow, including patient deep links, citation drawers, reference tools, chat and evidence expansion.
- [ ] Produce a checked route-policy table and public response-field inventory. Mark engineering routes as developer-only and distinguish commercial/regulatory reference data from private engine metadata.
- [ ] Record baseline synthetic outputs for representative patients/bills, including empty results, unavailable evidence and applicable multi-section reports. These are comparison fixtures for preserving behavior, not permission bypasses.

Exit: no officer dependency is silently omitted, and every registered route has a proposed access policy.

### Phase 1 — Establish server authority while anonymous billing remains disabled

- [ ] Centralize verified identity and capability resolution using the existing session verifier and username role resolver. Browser role cookies, localStorage, query parameters and request-body `user_role` are never authorization inputs.
- [ ] Extend `/api/auth/me` with the effective role/capabilities and public-access-enabled state required by the shell. An anonymous response identifies only currently enabled public capabilities without exposing configured usernames, credentials or internal settings. Do not cache this response across users. An unavailable identity response never grants developer capabilities.
- [ ] Keep the existing shared credential model for this scope. Explicitly provision the intended configured login as a developer via server configuration; a successful password check alone must not promote an unlisted identity.
- [ ] Cut over to a developer-only credential and invalidate previously shared sessions before granting developer capabilities. Rotate the former shared password (or replace its configured username/password) and the session-signing secret consistently across frontend/backend; do not simply add the old shared username to the developer allowlist. Otherwise existing signed sessions and previous password holders would gain developer access. Never record secret values in the plan, logs or repository.
- [ ] Coordinate the frontend and backend gates around the explicit route policy. Add a proposed `BILUN_PUBLIC_BILLING_ENABLED` release switch, default disabled, with the backend as its authority. Developer protection must hold in either switch state.
- [ ] Do not use `BILUN_AUTH_OPTIONAL` to enable the demo. Keep that development/test bypass disabled in production and out of security-test setup.
- [ ] Use appropriate production session cookie attributes, including HttpOnly, Secure over HTTPS and SameSite, and consistent cookie deletion on logout. Preserve documented local HTTP development support.
- [ ] Apply developer checks to engineering APIs and any diagnostic/documentation routes, including direct backend access. Unknown routes remain protected.

Exit: existing authenticated access works, and a valid nondeveloper session cannot call protected engineering endpoints. Public billing is still closed.

### Phase 2 — Define and enforce public response contracts

- [ ] Build explicit public serializers/models for billing, patient summaries, validation, evidence, reference data and frontend configuration. Project approved fields instead of returning an unrestricted cached dictionary or relying on a blacklist.
- [ ] Preserve amounts, statuses, clinical/billing explanations, recommended actions, public SUT references and stable identifiers needed for rendering, grouping and drilldown. Do not blanket-strip all rule/finding IDs or regulatory citations.
- [ ] Exclude implementation module paths, engine filenames, callable names, engineering coverage/deferral notes, private matching predicates and unnecessary tuning metadata. Review actual public config fields rather than assuming every config value is confidential.
- [ ] Apply projection consistently to cached and computed results, nested fields, response headers, errors and any download/export surface actually supported by the officer workflow. Public errors must not include stack traces or source excerpts.
- [ ] Preserve a citation-only contract for the officer SUT drawer; adapt its client if an endpoint is separated. A guessed rule ID must not select a developer response shape.
- [ ] Make public and developer response variants safe against cross-role caching. Initially use private/no-store caching for identity-dependent responses, or separate URLs with verified cache isolation; do not allow a developer response to populate an anonymous cache entry.
- [ ] Split minimal public health from protected release/build/engine diagnostics. Migrate existing release observers/probes to protected or internal detailed-health access and test that release/build identity checks remain intact; do not remove identity assertions merely to accommodate the smaller public response.

Exit: approved public outputs retain their business meaning and omit protected details, including when served from cache.

### Phase 3 — Close alternate paths through chat and tools

- [ ] Preserve officer chat with server-derived officer identity for guests, independently of the tab name or claimed role in the request.
- [ ] Gate developer context assembly as well as tool schemas/execution. A forged `tab_slug=rule-database` must not inject the internal rule catalogue into officer model context.
- [ ] Preserve and test hard denial of repository read/search tools for officers, even when explicitly requested through a prompt or tool call. Do not depend on the model following a system prompt.
- [ ] Ensure tools that call route functions/services directly receive the same authorization and public projections as HTTP callers. Route decorators alone do not protect these internal calls.
- [ ] Prevent streaming output, tool-result events, citations and error messages from exposing developer-only data. Retain permitted officer explanations and validation functionality.
- [ ] Bound public chat and compute requests using request/body/history limits, tool-step limits, concurrency and configurable rate limits; record selected limits and demonstrate 429/backpressure behavior before public rollout. Preserve existing tool limits where suitable, configure a total LLM usage/cost ceiling, and identify visitor IPs only through trusted proxy configuration rather than arbitrary forwarded headers. Budget/rate exhaustion returns a clear unavailable/limited state and must not alter business results for allowed requests.

Exit: public chat cannot become an alternate path to protected APIs, repository tools or unfiltered results.

### Phase 4 — Update the login and billing experience

- [ ] Open `/` and approved patient/billing deep links directly in Billing Officer mode when public billing is enabled.
- [ ] Replace the anonymous role selector with **Developer sign in**. Update English/Turkish text consistently and reuse the existing login form with a return-to-billing link.
- [ ] Initialize the shell from the server's effective capabilities. Remove authorization dependence on `bilun:role`, `bilun_user_role`, `NEXT_PUBLIC_USER_ROLE` and request-body role claims. Any developer-only display preview must remain separate from permission grants.
- [ ] After successful developer login and permission verification, perform a fresh navigation so the shell loads the authenticated capabilities. Handle rejected login and valid-but-unauthorized credentials without displaying developer UI.
- [ ] Guard direct routes, query-selected tabs and diagnostics (`tab=rule-database`, `admin=1`), not just sidebar links. Authorized developer screens remain functional.
- [ ] On logout, confirm session-cookie removal, clear protected in-memory/query/workspace state, discard inaccessible saved tabs, and perform a fresh navigation to public billing. If logout fails, show the failure rather than claiming the session ended.
- [ ] Handle expired sessions, another tab signing out, back navigation and delayed developer responses safely. The API must deny access immediately even if UI state is briefly stale; protected data must not reappear from client state after successful logout.
- [ ] Preserve the synthetic-demo indicator and existing officer navigation, reference tools, chat, evidence drawers and billing report behavior. New developer-only imports may be separated for loading efficiency, but dynamic imports are not treated as a security control.
- [ ] Preserve existing evidence pagination, selected finding/claim scope and legitimate POST variants used for long filters. Update the frontend API types together with public response contracts so missing technical fields do not break citation or evidence rendering.

Exit: a fresh anonymous browser completes the officer workflow; developer login and logout transition without exposing or leaving usable protected features.

Logout scope: deleting the session cookie removes access from that browser, and expiry is checked on every protected request. The existing stateless token model does not revoke an independently copied token at logout. Do not claim that guarantee; per-token revocation/session-store migration is outside this plan. The initial credential cutover still rotates the signing secret to invalidate all pre-cutover tokens. Data already viewed by an authorized developer cannot be recalled.

### Phase 5 — Verify behavior and confidentiality boundaries

- [ ] Add authorization tests using the real middleware and session verifier for anonymous, valid developer, valid nondeveloper, expired and forged sessions; test missing auth configuration with the public switch both off and on. Public routes may work without developer configuration when explicitly enabled, but protected routes must never open.
- [ ] Verify that pre-cutover session tokens and former shared credentials cannot obtain developer access after credential/secret rotation. The frontend and backend must agree on the new signing configuration.
- [ ] Test direct URLs, changed role cookies/localStorage, forged `user_role`/`tab_slug`, alternate HTTP methods and direct backend requests. Assert all registered routes are classified, with no accidental public fallthrough.
- [ ] Assert representative public payloads against explicit contracts, including nested evidence, citation lookups, validation errors and cached results. Compare public business outputs with the baseline; engineering field removal must not change amounts or findings.
- [ ] Warm relevant response caches as developer, then request the same resource without cookies and as nondeveloper. Repeat in reverse order; public clients must never receive developer fields, and private caches must not reuse stale identity after logout.
- [ ] Test chat context, tool schemas, direct tool execution and streamed results, including attempted repository reads and internal catalogue retrieval.
- [ ] Test login, authorization rejection, sign-out failure/success, session expiry, multi-tab transitions, browser back navigation and stored developer workspace restoration.
- [ ] Exercise representative officer workflows in a production build using a fresh browser, then repeat as developer. Check Network responses and server-rendered/RSC payloads for private fields before and after logout.
- [ ] Inspect `.next/static`, public assets and manifests for unintended backend source, complete private rule definitions, embedded credentials and browser source maps. Add an explicit confidentiality/map gate or extend the verifier; the existing asset-availability check alone does not prove these properties. Keep production maps disabled. Do not assert that minified JavaScript is confidential.
- [ ] Include retained older frontend asset routes in release checks. Older JavaScript already delivered cannot be made unreadable retroactively; new server policy must deny unauthorized requests from those clients too.
- [ ] Run focused checks during implementation, then the full current CI gates on the final candidate. Inspect generated artifacts and repository status afterwards; test fixtures in this project can modify tracked outputs.

Existing validation commands, verified against the inspected CI workflow; recheck them against the chosen implementation base:

```bash
# Repository root, using its configured Python environment
ruff check src/ scripts/
python -m pytest -q --durations=20
python scripts/sut/compile_rules.py --check
python scripts/sut/audit_manifest_parity.py --drug-only

# From frontend/
npm ci
npx tsc --noEmit
npx vitest run
npm run build
```

For local full-suite execution, use the repository's documented thread setting where applicable. Do not run a second full suite without changes or unresolved failures. New browser/security cases are additional checks; they do not replace existing CI gates.

Existing starting tests include `tests/unit/api/test_auth.py`, `tests/unit/api/test_sut_chat.py`, `tests/unit/chatbot/test_tools.py`, `tests/unit/chatbot/test_repo_tools.py`, `frontend/src/lib/userRole.test.ts`, `frontend/src/components/shell/RoleSwitcher.test.tsx`, `frontend/src/lib/workspaceTabs.test.ts` and `frontend/src/app/patient/[id]/billing/page.test.tsx`. Also extend the integrated base's rule API, v2 validation, compliance, per-bill, Wave A, chat API, admin-query and workspace/store tests. Add missing middleware/policy/public-contract coverage; do not merely mirror implementation branches. The shared backend test setup enables auth bypass by default, so permission tests must explicitly clear it and establish their own safe synthetic auth configuration. Frontend unit tests alone do not exercise browser middleware/session transitions: require fresh-profile Playwright checks against the production build.

Exit: permission, response, browser and regression evidence is attached to the implementation review; no unverified confidentiality claim is used as a release gate.

### Phase 6 — Review and controlled rollout

- [ ] Review the final diff and route/field inventories independently. Inspect CI and review feedback before any later publication/merge under repository workflow rules.
- [ ] Prepare a production artifact from the verified integration commit and identify its frontend, backend, cache/build compatibility and session configuration. No clinical/rule dataset regeneration is required solely for these access changes.
- [ ] Record the actual current live service/artifact pair as the rollback baseline. At inspection, ports `3099`/`8002` were already live despite their candidate names. Stage on verified unused loopback ports; do not rerun old candidate-launch scripts or assume `/opt/bilun-frontend/current` identifies the public release. Reconcile any hard-coded ports in release tooling before use.
- [ ] Keep the release switch disabled while deploying backend restrictions, public projections and compatible frontend changes. Verify developer access and authenticated regression checks first.
- [ ] Coordinate the developer credential and signing-secret cutover across both services before enabling developer/public access. Confirm old credentials and pre-cutover tokens fail; retain the rotated secret/credential policy during rollback rather than restoring former shared access.
- [ ] Enable anonymous billing only after all required protections are present. Run public officer and authenticated developer smoke tests against the exact release, including direct denial probes and the citation/chat workflows.
- [ ] Observe authorization failures, public request latency, rate limits and unexpected server errors without logging passwords, tokens or raw chat bodies.
- [ ] Rollback trigger: any unauthorized engineering payload, permission bypass, broken officer workflow or unacceptable compute load. Disable anonymous access first, verify the backend blocks new anonymous API calls, then diagnose or revert compatible artifacts.
- [ ] Never revert to an older permissive backend while anonymous access remains enabled. Keep previous compatible artifacts identified before rollout; update the UI to login-gated operation when the public switch is off.
- [ ] Verify compiled frontend rewrites, loaded and on-disk proxy routing, retained old-asset routes and the paired frontend/backend identity after activation or rollback. Preserve the current release-hold workflow; extend existing release transaction/hold coverage for mismatched permission policy as needed, in addition to ordinary asset/health checks.

Deployment is a separate action, not part of writing this plan. The inspected live candidate has a release-hold workflow, whereas older local main has a different deployment workflow; do not assume a push or merge is the correct deployment mechanism. Reconfirm the actual release process and target at implementation/release time.

## Definition of done

- A new visitor reaches and uses the complete approved synthetic billing workflow without signing in.
- Only the verified configured developer identity can open developer features and receive engineering API/context/tool results.
- Client-side role changes, direct URLs, guessed identifiers, stale assets and forged chat parameters cannot increase permissions.
- Public output includes necessary results and SUT explanations while excluding protected source/implementation metadata across API, chat, cache, errors and supported exports.
- The Python engine and full private rule definitions remain server-side; calculations and synthetic business results are unchanged.
- Sign-out/expiry returns the UI to public billing without retaining usable developer state; API restrictions remain authoritative.
- Production asset checks, authorization tests, browser checks and existing CI gates pass, and rollout/rollback evidence is recorded.

## Out of scope

- Hiding all browser JavaScript, disabling browser tools/right-click, or treating minification/obfuscation as access control.
- A separate developer frontend deployment solely to conceal its UI bundle. Keep confidential data out of assets; use authorization for protected behavior.
- Rewriting the rule engine, changing reimbursement logic, removing regulatory explainability, or regenerating synthetic cohorts.
- Real patient-data onboarding, tenant/account administration, multiuser provisioning, SSO or a new identity provider.
- Production deployment and merging during this PR implementation task.
