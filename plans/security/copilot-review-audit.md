# Copilot/Bugbot PR Review Audit — Findings

**Date:** 2026-07-13
**Method:** Identified 22 PRs with Copilot reviews → dispatched 7 parallel subagents → each finding verified against current `main` code with file:line citations.
**Question answered:** For every Copilot finding — was it right or wrong, and did any real bug slip into the codebase because the review was missed?

---

## Executive summary

| Metric | Count |
|---|---|
| PRs with Copilot reviews examined | 22 (#6-8, #12-27, #29-31) |
| Distinct Copilot findings adjudicated | ~45 |
| **RIGHT — bug confirmed, still live in `main`** | **5** |
| RIGHT — caught and already fixed in follow-up commits | 5 |
| RIGHT — but dormant (latent, no runtime impact today) | 8 |
| DEBATABLE (valid observation, but overstated or fix is wrong) | 7 |
| WRONG (false positive) | 8 |
| PRs where Copilot was quota-blocked (no findings) | 5 (#9-12, #16, #20, #21, #27, #30) |

**Bottom line:** Copilot was substantively correct on ~40% of findings and caught **2 genuinely serious bugs before they shipped** (a build-breaking re-export in PR #8, a silent rule-coverage hole from a typo in PR #7). The missed reviews did NOT cause widespread bugs to ship — the codebase is in better shape than the premise feared. But there are **5 real, currently-live issues** worth fixing, and one is **High severity** (the SUT-monitor stale-date bug).

---

## 🔴 Bugs confirmed LIVE in `main` (the ones that matter)

These are real defects that exist in the current codebase right now, verified by reading the code.

### 1. PR #29 Finding 4 — SUT-monitor workflow reads stale `OLD_DATE` after ingest [HIGH]
**File:** `.github/workflows/sut-monitor.yml:44-56`
**Bug:** The workflow's "Compute delta" step reads `OLD_DATE` from `ingest_state.json`, but the "Run ingest pipeline" step (which runs *before* it) already overwrites that file with the new tebliğ date. Result: `OLD_DATE == NEW_DATE`, so the temporal delta (ek2b/ek2c price/name changes) always reports empty. The auto-PR summary misrepresents every amendment.
**Fix:** Add a "Capture pre-ingest date" step before the ingest step.

### 2. PR #6 Finding 1 — `billed_amount_try` parity divergence between adapter and legacy path [MEDIUM]
**Files:** `src/bilun/domain/claims/adapter.py:161` vs `src/bilun/domain/rules/bundling_rules.py:49-51`
**Bug:** The adapter path computes `billed = billed_amount or (unit_price × quantity)`, but the legacy dict-path always uses `billed = unit_price × quantity`. When a claim dict carries a `billed_amount` that differs from `unit_price × quantity`, the two paths compute different savings/risk for identical input — violating the parity guarantee that gates retiring the legacy path.
**Fix:** Align both paths on the same `billed` derivation.

### 3. PR #8 Finding 3 — Bill-scoped financial summary shows patient-level totals under a "selected bill only" label [MEDIUM]
**Files:** `frontend/src/components/patient/PatientFinancialSummary.tsx:34,66-68,78-91`
**Bug:** When a user scopes to one bill, the UI says "Totals and recoverable amounts for the selected bill only" — but the Total billed / Expected payable / Bill count KPIs still read from `outcome.sut_claim_totals` (patient-aggregate). The per-bill data needed to fix this exists (`PatientClaimSummary`), it's just not wired.
**Fix:** Source the KPIs from the per-bill summary when a bill is selected.

### 4. PR #22 Finding 2 — ICU e-nabız/blood-product rules can never fire (dormant) [MEDIUM]
**File:** `src/bilun/domain/prose_rules/treatment_pricing.py` context builder + `data/gazette/prose_rule_sources/treatment_pricing_2_4/2.4.4.H.yaml` rules 9, 10a, 10b
**Bug:** Three normative ICU rules (blood-product separate billing, e-nabız +60 TL uplift, e-nabız absence downgrade) reference context keys (`enabiz_278_data_package_sent`, `blood_product_separately_billed`) that `_build_treatment_pricing_context` never surfaces. The evaluator honest-skips on every claim, so these rules are dead code. This is "by-design honest-skip" but means the rules are inventory-only until the context builder is extended.
**Fix:** Surface the missing keys in the context builder (requires a data-source for e-nabız submission status).

### 5. PR #19 Finding 1 — Stale `provenance_note` in procedure_pairing [LOW]
**File:** `data/gazette/prose_rules/procedure_pairing_prose.json:150`
**Bug:** File-level note says "verification_status=pilot_heuristic on every rule" but 2 of 8 rules are `ai_generated_pending_review`. Misleads audit consumers. No runtime impact.

---

## ✅ Bugs Copilot caught and that WERE fixed (credit where due)

| PR | Finding | What Copilot caught | Where fixed |
|---|---|---|---|
| #7 | Typo `sozlessmesiz` → should be `sozlesmesiz` | Silent rule-coverage hole: uncontracted-facility rules would never fire | `b1ed817` (explicitly credits Copilot) |
| #8 | `export {ExactnessBlock as ExactnessNotice} from "..."` produces no local binding | **Build-breaking** (TS2304) — JSX reference undefined | `6a72843` |
| #13 | Stale 26/60 TL copay amounts | Version-sensitive flat fees | `5e82c31` (PR #29 repriced to 50/90/100 TL) |
| #14 | `message_tr` contradicted new `deontic`/`material_out Outcome` (YAML + JSON) | Said "bundled" after flip to "separately payable" | `58ee385` |

Both the PR #7 typo and the PR #8 build break were **genuine, correctly-diagnosed bugs** — one High, one Critical. Following the Copilot reviews caught them before they caused damage.

---

## ❌ Copilot FALSE POSITIVES (where it was wrong)

These are findings where Copilot's claimed impact doesn't hold up. A common pattern: Copilot assumed rule-data fields drive evaluator behavior, but in this codebase many fields (`bill_visit_fee`, `enforcement`, `point_uplift_pct`, `payment_fraction`, `max_copay_pct_of_minimum_wage`) are documentation/metadata only.

| PR | Finding | Why it's wrong |
|---|---|---|
| #13 | `vatani_hizmet` missing §1.8.4 | SUT C000366 explicitly waives only 1.8.1-1.8.3. Applying the "fix" would have **waived IVF copays** incorrectly — a real bug introduced. |
| #15 | Removing `bill_visit_fee: false` is a billing regression | No code anywhere reads `bill_visit_fee`. There's no default-to-true path. |
| #18 | "Unexplained" C000337 golden change | It was the catch-up for a deliberate deletion in PR #17. |
| #18 | Rule reordering breaks evaluation | The evaluator appends every match — no first-match-wins, no ordering effect. |
| #19 | Missing `same_incision` causes runtime error/skip | Evaluator uses `bool(rule.get("same_incision", True))`; and the rule is never loaded anyway (no trigger codes). |
| #22 | Missing `enforcement` field causes silent skip | Evaluator never reads `enforcement`. |
| #22 | Out-of-order JSON rules break evaluation | Same as #18 — no first-match-wins. |
| #29 | `new_tebliğ` vs `new_teblig` output key breaks the whole pipeline [importance 9] | Workflow checks the ASCII key on the success path; the Turkish-ğ key is only on skip paths. Copilot's suggested fix would have **caused** the breakage. |

---

## 🟡 Dormant findings (RIGHT but no runtime impact today)

Copilot correctly identified logic issues in gap_closing/treatment_pricing rules, but the condition keys are never surfaced by the context builders, so the rules honest-skip on every claim. These are **latent** — they'd bite the day someone wires the keys.

- PR #17 Findings 1-3: AND-logic gaps in gap_closing rules (er_stabilization, extra_fee scope, off-label approval)
- PR #25 Findings 1-2: PSMA board AND-logic, contradictory foci conditions
- Several PR #25 "numeric-dropping bug fixes": keys unsurfaced, so documentary-only

---

## 🟠 A pattern Copilot missed (surfaces repeatedly)

The subagents independently surfaced a systemic issue Copilot did **not** flag: **many newly-encoded normative rules reference context keys the engine never populates.** This isn't a bug per-PR — it's a coverage gap across PRs #17, #22, #24, #25. The rules are honest-skipped, so they're inert inventory rather than live enforcement. The motor docstrings document this as "out-of-scope rules," so it's a known limitation, but it means a large fraction of recently-added normative coverage is currently documentation-only.

Additionally, subagents found bugs Copilot missed entirely:
- **PR #25 bonus:** `2.4.4.F-3.(1b)` uses `supervised_by_pmr_specialist` but the context builder surfaces `supervised_by_pmr_specialty` (different spelling) — rule never fires despite the key being wireable.
- **PR #25 bonus:** `2.4.4.G-u.(1)` uses `risk_group_adjustment_fraction: {low, high}` but the evaluator's numeric-range branch only recognizes `{min, max}` — wrong shape.
- **Live in main (not from any reviewed PR):** `3.3.33.C.(1)` rule_id collision across two sections (bone-anchored vs middle-ear), and `3.3.26.c.*` rule_id/message letter mismatch.

---

## Quota-blocked PRs (no Copilot content to review)

Copilot hit its review quota on PRs #9, #10, #11, #12, #16, #20, #21, #27, #30 — these got only boilerplate ("No major issues detected"). The subagents verified these PRs' substantive claims against the code anyway; all verified correct (e.g., PR #27 yatak-puani day-counting is correct, PR #30 detectors are sound, PR #21 wildcard fix is complete).

---

## Recommendation

1. **Fix the 5 live bugs above** — the SUT-monitor stale-date bug (#29-F4) is the priority; it's actively producing misleading auto-PRs.
2. **Don't apply Copilot's suggested patches blindly** — 3 of its "fixes" (PR #13 vatani_hizmet, #15 bill_visit_fee, #29 output-key) would have *introduced* bugs.
3. **Re-run Copilot reviews when not quota-blocked** — the quota misses were genuine, but the verified content of the reviews that did complete shows Copilot adds real value (caught 2 serious bugs, was right on ~40% of findings).
4. **Audit the context-builder coverage** — the dormant-rules pattern (many rules honest-skip because keys aren't surfaced) is the biggest latent gap, and it's not something per-PR review would catch.

Full per-finding detail with file:line citations is in the subagent reports above; this is the consolidated verdict.
