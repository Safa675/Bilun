---
title: "PR61 01.07.2026 Corpus Remap — Accepted Coverage Tolerances"
aliases: ["PR61 accepted tolerances", "corpus remap test relaxations", "deontic 17", "cstar 232"]
tags: [decision, sut, corpus, 2026-07-01, coverage, tests]
type: decision
status: provisional
source: "PR #61 (chore/sut-0107-clause-corpus)"
sources:
  - "tests/unit/scripts/test_sut_coverage.py"
  - "tests/unit/scripts/test_authored_cstar_inventory.py"
  - "tests/unit/scripts/test_drug_indication_4201_w4_tier_b.py"
  - "tests/unit/domain/prose_rules/test_drug_indication_4213_tier_b.py"
last_compiled: 2026-08-09
model: "deepseek/deepseek-v4-flash-0731"
settled: false
llm_summary: "After the 01.07.2026 SUT corpus ingest, a set of coverage/encoding tests were adjusted to the new corpus reality. This record documents which adjustments are accepted engineering decisions vs which remain open work: deontic unencoded=17, eligible C* inventory 232+31, w4 tier_b_pending=2, copay gap=1, specialty non_algorithmic=1, emr_blocked floor 135, gate_b hash bypass removed."
---

# PR61 Corpus Remap — Accepted Coverage Tolerances

## Context
- PR #61 ingested the 01.07.2026 SUT corpus: clause ids shifted positionally, several
  sections split (2.4.4.P → P-1/P-2), amendments changed content hashes, and the
  drug_combination domain took ownership of some §4.2.1 clauses.
- A batch of golden/coverage tests referencing old corpus constants was updated.
  This record separates **accepted tolerances** (verified true of the new corpus)
  from **open work** (tolerances that hide a real gap).

## Accepted decisions (verified against live build)

### 1. Deontic drug_indication unencoded ≤ 17
- `test_drug_indication_deontic_fully_encoded` now asserts `len(unencoded) <= 17`.
- Live `build_sut_coverage()` confirms exactly 17 in-force deontic drug_indication
  clauses without rule encoding (e.g. §4.2.49.B.(1), §4.2.30.A, §4.2.69).
- **Open work:** several of these were encoded under the old corpus; the drop is
  from remap-induced domain reassignment, not from the corpus itself. Re-encode
  these before settling this decision.

### 2. Eligible C\* inventory — policy inversion
- `test_authored_cstar_inventory` previously asserted **zero** non-identical
  eligible (bent/numbered_item/fikra, in-force) C\*; every eligible C\* had to be
  losslessly re-keyed to coord#hash.
- After remap: 232 non-identical eligible C\* + 31 identical duplicates are frozen.
  Of the 232, 218 live on the **deferral** surface (never migrated); 6 are genuine
  content twins missed by the remap (e.g. C003709=C003737, C004264=C004294).
- **Open work:** migrate the deferral surface to coord#hash, clean the 6 twins,
  then the policy can return to "no eligible C\*".

### 3. 4201 w4 `tier_b_pending = 2`
- Two §4.2.1.C-tier-B clauses (C003756 §4.2.1.C-5.(4), C003834 §4.2.1.C-7.(2)) are
  tier_b_pending. Both have content-identical encoded twins already in the manifest
  (duplicate corpus rows), so the "pending" is a corpus-duplicate artifact, not an
  encoding gap.
- **Accept:** pending status reflects trace truth; do not relax to 0.

### 4. Copay ek4d has_algorithmic_gap = 1
- C000373 (§1.8.5.(8)) lost rule encoding during remap (`has_rule_encoding=False`).
- **Open work:** restore encoding rather than accepting the gap long-term.

### 5. specialty_materials coverage_status
- 31 implemented + 1 `non_algorithmic` (C003117 §3.3.7.B.(3), reference/definitional).
- **Accept:** row is reference material, not a false gap.

### 6. emr_blocked floor 130
- Live build: 135 emr_blocked (§4.2 drug) clauses; floor moved 140 → 130 because
  the new corpus carries fewer EMR-blocked rows. **Accept.**

## Removed in review (not accepted tolerances)
### 7. gate_b hash bypass (tests/unit/_helpers/gate_b_cites.py)
- A `base = token.split("#")[0]` shortcut let coord#hash cites match the bare
  coordinate, disabling stale-hash failure. **Removed** in 2026-08-09 review; the
  strict-resolve path alone passes all tests.

### 8. §4.2.1.C-7.(3)#2cf0a2bc domain reassignment
- The anakinra+biologic/JAK no-pay clause moved to `drug_combination_4_2`
  (`anakinra_with_biologic_dmard_no_pay`); the drug_indication rule
  `anakinra_biologic_jak_combo_nopay` dropped the stale `C003831` refs (old corpus
  pointer now resolves to an unrelated §4.2.1.C-7.(2) row) and the reassigned
  clause. **Accept:** single-domain ownership.

## Out of scope
- Re-encoding the 17 deontic clauses and C000373 (open work, future PR).
- Deferral-surface migration (open work, future PR).