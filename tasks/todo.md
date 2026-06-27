## Task: R5 Epic D — §1.8 copay exemption Phase D3+D4

**Branch:** `feat/r5-epic-1.8-copay`  
**Plan:** `plans/billing/r5-epic-1.8-copay-exemption.md`

### Goal
Add 8 §1.8.5 exemption JSON rules (Gate B trace), golden tests, D4 billing outcome distinction, regen coverage ≥18 encoded.

### Subtasks
- [x] Add 8 exemption rules to `copay_general_1_8.json` (12 total with 4 rate rules)
- [x] Golden `golden/copay_general_1_8_batch1.json` + `test_copay_general.py`
- [x] Gate B script prefers explicit `gate_b_sources`; regen manifest (19 encoded)
- [x] D4: `copay_primary_outcome`, `outcome_kind` on exemption/rate blobs; bill-level age pass-through
- [x] pytest copay suite (38 passed); coverage regen (19 §1.8 encoded)

### Out of Scope
payment_method_2_2, drug/material JSON.

### Review
Phase D3+D4 complete; uncommitted per user request.

---


**Branch:** `feat/r5-epic-4.2-drug`  
**Plan:** `plans/billing/r5-epic-4.2-drug-indication.md` (extends `drug-indication-4.2.14.C-expansion-plan.md`)

### Goal
Refresh §4.2 drug_indication_prose encode gap inventory: Gate B CSV, manifest vs coverage diff, section-prefix segmentation.

### Subtasks
- [x] Create branch `feat/r5-epic-4.2-drug`
- [x] Script `scripts/sut/prose/drug_indication_a0_inventory.py`
- [x] Artifacts: `L4.2_drug_indication_gap_refresh.csv`, `L4.2_drug_indication_a0_summary.json`
- [x] Unit test `tests/unit/scripts/test_drug_indication_a0_inventory.py`
- [x] Run pytest (a0 inventory + drug_indication domain)

### Out of Scope
payment_method_2_2, copay_general_1_8, material_bundling, coverage.py changes.

### Review
Phase A0 complete; changes uncommitted pending full test pass.
