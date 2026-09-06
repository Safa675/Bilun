## Task: 2026-08-29 SUT rule corpus (PR 80 follow-through)

### Goal
PR 80 ingest is on this branch; encoded YAML/wave keys resolve against the 2026-08-29 clause corpus; compile + coverage artifacts are regenerated; the two new grandfathering bents are encoded.

### Subtasks
- [x] Remap stale `coord#hash` cites in YAML + `gate_b_wave_config.py` to new hashes (similarity-matched)
- [x] Remap positional `C*` `gate_b_sources` + `clause_type_overrides.yaml` (07-01 → 08-29 id shift)
- [x] Update YAML messages for real law changes (4.1.4.c, 4.2.1.C-3/C-5.a, 4.2.8.A.b, 4.2.14.C KLL, 4.2.15.D-2 radiology)
- [x] Encode new `4.2.1.C-3.d` and `4.2.1.C-5.d` grandfathering rules
- [x] `compile_rules.py` then `compile_rules.py --check`
- [x] `build_sut_coverage.py`
- [x] Changelog
- [ ] Targeted pytest
- [ ] Commit, push `cursor/sut-2026-08-29-corpus-bd12`, open PR vs main
- [ ] Commit, push `cursor/sut-2026-08-29-corpus-bd12`, open PR vs main

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
