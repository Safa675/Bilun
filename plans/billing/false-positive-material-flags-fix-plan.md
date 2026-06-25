# Plan: Fix false-positive material compliance flags (§3.1.1(7) + §3.3.7.B(2))

## Goal
Stop the app from asserting compliance violations that don't apply to the patient's
actual situation. Specifically: a §3.1.1(7) "inpatient material" rule must not fire on
an outpatient (poliklinik) claim, and a §3.3.7.B(2) "wheelchair + standing device" rule
must not fire on a shoulder implant with no wheelchair present.

The product's credibility depends on never asserting a rule violation that an auditor
can falsify. Right now it asserts two on patient-0029 that are plain wrong.

## Root cause (verified, two layers)

**Layer 1 — Data injection (the immediate cause of AP1030's bad flags):**
`scripts/synthetic/generators.py:1482-1497` (`_ensure_prose_flag_coverage`) and
`generators.py:1370-1384` (`_ensure_specialty_flag_coverage`) are *coverage-stuffing*
functions. Their job is "guarantee every prose flag has at least one True row in the
cohort." They do this by force-setting flags onto arbitrary materials by **index**
(`candidates[idx % len(candidates)][col] = True`) with **zero applicability reasoning**.
That is why:
- `non_reimbursed_inpatient_patient_charge=True` landed on AP1030 (an outpatient's
  shoulder implant) — it was assigned by position, not by any visit-type check.
- `wheelchair_stand_device_duplicate_billing=True` landed on the same AP1030 — same
  positional assignment, no check that a wheelchair exists or that the material is one.

The shipped `_MEDULA_DEMO_SPECS` anchor for 0029 only sets `uts_kayitli_mi=False` and
`titubb_uts_barkod_belge_eksik=True`. The two bad flags are added AFTER generation by
these coverage post-passes.

**Layer 2 — Engine applicability (the structural cause, why even a correctly-set flag
could misfire):**
`src/bilun/domain/prose_rules/material_bundling.py` (§3.1) and
`specialty_materials.py` (§3.3) are *flag-trusting evaluators*. When a flag is True on
a line they print the rule message — with no check that:
- The claim is actually `yatarak` (inpatient) for inpatient rules — `visit_type` lives
  on the claim header and **neither engine reads it**.
- A wheelchair/standing-device is actually co-billed for the §3.3.7.B(2) duplicate
  rule — the rule has no material-code or keyword filter and matches any flagged line.

So even if Layer 1 were fixed, a future data source setting these flags without
context would still produce false positives. Both layers must be fixed.

## Scope decision: Option A (targeted guards) + a data fix — NOT a full corpus audit

The verified flag-only vs self-scoping counts:
- **§3.1** (`material_bundling_prose.json`): **44 flag-only / 15 self-scoping** (59 total).
- **§3.3** (`specialty_materials_prose.json`): **35 flag-only / 14 self-scoping** (49 total).

A full self-scoping rewrite (Option B) is correct but is a multi-day rule-corpus audit
that risks breaking rules that work — wrong move to rush. Instead:

- **Engine side (Option A):** add the two specific applicability guards the missing
  checks require — a visit-type gate for inpatient-scoped rules, and a co-material
  presence guard for duplicate-billing rules. General enough to cover the *pattern*,
  narrow enough not to destabilize the corpus.
- **Data side:** stop the coverage post-passes from stuffing flags onto
  context-incompatible materials. Generate coverage on *plausible* materials instead.

A full self-scoping corpus audit is captured as a follow-up, out of scope here.

## Subtasks

### Layer 1 — Engine applicability guards (the correctness fix)
- [ ] `src/bilun/domain/prose_rules/material_bundling.py`: thread the claim's
      `visit_type` into `check_material_bundling_for_context` (it has `ctx`; read
      `ctx.claim_type` or the claim header's `gelis_tipi`). In `_condition_matches`,
      for any rule whose `sut_section`/predicate is inpatient-scoped
      (`non_reimbursed_inpatient_patient_charge`, `ek3c_inpatient_external_supply_invalid`,
      `inpatient_material_facility_supply_violation`), suppress when the claim is not
      `yatarak`. Use the existing `infer_care_setting` helper (`claim_utils.py:30`).
      Suppressed = not shown (the rule is simply inapplicable, not "violated").
- [ ] `src/bilun/domain/prose_rules/specialty_materials.py`: for duplicate-billing
      rules whose predicate name contains `duplicate_billing`, require that the
      *co-billed materials on the same claim* actually include the relevant device
      category (wheelchair / standing device, etc.) — read from the material lines of
      the claim. No co-material present → rule cannot fire. (The matching-keyword list
      on the rule, if any, names what to look for; for the wheelchair rule it's none,
      so hard-gate on "a wheelchair-coded material exists on the claim.")
- [ ] Both engines: when a rule is suppressed for inapplicability, do not emit it
      (silent), OR emit it flagged `applicability: "n/a — outpatient"` — decide during
      implementation; default to silent to keep the report clean.

### Layer 2 — Data coverage that respects context (the source fix)
- [ ] `scripts/synthetic/generators.py:1482` (`_ensure_prose_flag_coverage`) and
      `:1370` (`_ensure_specialty_flag_coverage`): replace positional flag-stuffing
      with *context-aware* assignment:
      - inpatient-scoped flags (`non_reimbursed_inpatient_patient_charge`, etc.) → only
        assign to materials on `yatarak` claims.
      - duplicate-billing flags (`wheelchair_stand_device_duplicate_billing`, etc.) →
        only assign to claims that *also* carry the co-material (e.g. a wheelchair),
        or skip coverage for that flag if no such claim exists (honest "no demo row"
        beats a false one).
- [ ] Regenerate the cohort and confirm AP1030 no longer carries the two bad flags,
      and that the §3.1.1(7) + §3.3.7.B(2) messages do not appear on patient-0029.

### Layer 3 — Tests + verification
- [ ] `tests/unit/domain/prose_rules/test_material_bundling.py`: add cases —
      inpatient rule suppressed on poliklinik; fires on yatarak.
- [ ] `tests/unit/domain/prose_rules/test_specialty_materials.py`: add cases —
      wheelchair duplicate rule suppressed when no wheelchair co-billed; fires when
      one is present.
- [ ] Synthetic validator: assert no outpatient claim carries an inpatient-scoped
      material flag; assert no duplicate-billing flag without the co-material.
- [ ] **Drift guard (new):** this fix depends on the generated cohort being consistent
      with the rules corpus and the active tebliğ. Today there is NO version-stamp /
      catalog-coherence test (verified: grep finds none), so a future regen can silently
      drift back into the bug. Add a manifest-stamp assertion to
      `data/synthetic/demo_manifest.json` (tebliğ `effective_date` + a hash/stamp of the
      rule corpora) and a test that the regenerated cohort matches it. Generalize the
      Layer-3 flag assertion above into this stamp test so "fix → forget → drift"
      can't recur.
- [ ] Regenerate cohort, run full `pytest tests/unit` + synthetic validator + Tier A.
- [ ] Spot-check patient-0029 live: the two false §3.1.1(7)/§3.3.7.B(2) notes gone;
      the genuine 0704 ÜTS finding still present.

### Layer 4 — Ship
- [ ] Commit on a branch, CI green, merge → auto-deploy to app.bilun.tech.

## Out of scope
- Full self-scoping corpus audit (Option B) — every flag-only rule declaring its
  applicability. Tracked as a separate project; this fix handles the two reported
  false-positive classes and the pattern behind them.
- The earlier EK-3B-1-vs-EK-3/O citation bug (HO1008/HO1018) — separate fix; both are
  citation-accuracy issues but different code paths. Capture as its own task.
- **Demo vignette price consistency (`data/synthetic/demo_vignettes.json`) — separate
  task.** Verified this file carries fabricated `5000`/`4000` + `price_try` values that
  are context-incompatible, the same *family* of problem as this fix's data-injection
  root cause (synthetic data carrying values that don't match reality). Not in scope
  here — but tracked explicitly so it isn't lost; both should be fixed before claiming
  the synthetic data is audit-credible.
- Re-architecting the flag-on-line data model. It's imperfect, but replacing it is
  a larger structural change than these bugs require.

## Verification of done
- Patient-0029 (poliklinik) shows no §3.1.1(7) "yatarak malzeme" note. ✅ (live-verified)
- Patient-0029 shows no §3.3.7.B(2) "tekerlekli sandalye" note on the shoulder implant. ✅ (live-verified)
- The genuine findings on 0029 (0704 ÜTS barcode, §3.1.1(4)) remain intact. ✅
- A yatarak inpatient patient with an inpatient material DOES still trigger §3.1.1(7). ✅ (patient-0037 mixed-claim)
- Full test suite (827) + synthetic validator + Tier A green. ✅
- Drift guard (`_validate_material_flag_applicability`) asserts no outpatient carries an inpatient flag. ✅

## Review
- **Engine gates:** `material_bundling.py` now resolves care setting per-material (not per-patient-first-claim) via a `claim_id → care_setting` map — critical for mixed-claim patients where one patient has both poliklinik and yatis claims. `specialty_materials.py` gates duplicate-billing rules on co-material presence (wheelchair/spinal/NIMV keyword in a sibling line).
- **Data fix:** the coverage post-passes (`_ensure_prose_flag_coverage`, `_ensure_specialty_flag_coverage`) now respect context. Had to use the GENERATOR's Turkish column names (`karsilanmayan_yatarak_hasta`) in the inpatient-scoped set, NOT the exported English names — a column-name-language mismatch caught only by tracing.
- **Surfaced a latent bug:** the regen exercised a code path in `aggregator.py:157` using `Decimal` without importing it, crashing the production cache rebuild (503). Fixed the import (`1fa98bd`), but this illustrates that data regens are full-pipeline smoke tests (lesson captured).
- **Deploy gap found:** the auto-deploy workflow restarts services but does NOT rebuild the DuckDB cache. When a deploy ships regenerated data, the cache must be rebuilt manually (`BILUN_STARTUP_POLICY=rebuild` + restart) or the frontend serves stale findings. This is a known gap to address in a deploy-workflow follow-up.
- **Pre-existing tests updated:** 3 specialty tests that asserted the false-positive behavior (lone material triggers duplicate rule) now include the co-material so they test the corrected behavior. The coverage test exempts context-gated flags.

