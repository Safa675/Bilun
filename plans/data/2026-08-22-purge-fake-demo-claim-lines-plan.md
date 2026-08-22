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
