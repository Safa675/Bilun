## Task: Specialty Scope Validation (Option B)

### Goal
Build a validation harness that tests Bilun's 366 specialty-restricted
`drug_indication` rules against real ILAY prescribing data joined to hospital
departments. Produce violation log + per-rule compliance + golden test cases.

Plan file: `plans/backend/specialty-scope-validation-plan.md`

### Subtasks

#### Phase 1 — Data join
- [x] 1.1 Add `load_specialty_pairs()` to `rx_loader.py`
- [x] 1.2 Reuse `_normalize_tr` for specialty normalization
- [x] 1.3 Sanity-check join produces ≥30K rows *(actual: 15,887 — below threshold but usable, see note below)*
- [x] 1.4 Persist `specialty_pairs.parquet` for debugging

#### Phase 2 — Claim builder extension
- [x] 2.1 Extend `build_drug_line()` with `prescriber_specialty` param
- [x] 2.2 Extend `build_claim()` to forward specialty
- [x] 2.3 Regression: re-run item 1, confirm identical output *(18,062 rows, byte-identical keys)*

#### Phase 3 — Specialty validation harness
- [x] 3.1 Create `validate_specialty_rules.py`
- [x] 3.2 Filter to fireable specialty rules *(actual: 399 of 930 rules have prescriber_specialties)*
- [x] 3.3 Build claims with SERVISADI as prescriber_specialty
- [x] 3.4 Run `evaluate_drug_indication_line()` per row
- [x] 3.5 Write `specialty_violation_log.parquet` *(53 rows)*
- [x] 3.6 Write `specialty_rule_compliance.csv`
- [x] 3.7 Print headline summary

#### Phase 4 — Golden dataset
- [x] 4.1 Extend `build_golden_dataset.py` with `--specialty` mode
- [x] 4.2 Extract representative cases per rule across departments
- [x] 4.3 Write golden JSONs to `golden/ilay/specialty_ilay_*.json`
- [x] 4.4 *(target was 50-150, actual: 8 across 3 rules — see README for why)*

#### Phase 5 — README + mapping
- [x] 5.1 Update README.md with specialty section
- [x] 5.2 Document SERVISADI → rule specialty mapping table
- [x] 5.3 Document department ≠ doctor caveat + KVC substring-collision bug

#### Phase 6 — Pytest integration
- [x] 6.1 Add `test_specialty_real_data.py`
- [x] 6.2 Confirm 10/10 tests pass; 1272 prose_rules tests pass overall (no regressions)

### Out of Scope
- 260 specialty rules with no ILAY drug overlap
- 69% unjoined prescriptions (no department data)
- Clinical-false-positive adjudication (refill prescriptions, comanagement)
- Individual doctor attribution (we have department, not doctor ID)
- Building a dashboard UI (data outputs are sufficient)

---

## Review

**All 6 phases complete.** Build ran from 2026-07-20, end-to-end in worktree
`/home/safa/Documents/Bilun-specialty` on branch `feature/specialty-validation`.

### What was actually delivered vs planned

| Metric | Plan target | Actual |
|---|---|---|
| Joined prescription-department pairs | ~30-60K | 15,887 (lower than estimated) |
| Specialty-restricted rules loaded | ~341 | 399 (more than estimated) |
| Violations fired | 1,000-15,000 | **53** (much lower) |
| Golden test cases | 50-150 | **8** across 3 rules |
| Build time | 3 days | <1 day (clean execution, no surprises) |

### Why the actuals diverged from the plan

1. **Only 53 violations fired** (vs expected 1,000-15,000). The investigation
   showed high "wrong-specialty" prescribing rates (4-43% per drug), but most
   of those prescriptions went to specialties that ARE in the rule's allowed
   list. Example: investigation flagged "PLAVIX prescribed by İç Hastalıkları
   at 6.8%" — but the rule explicitly allows "iç hastalıkları". Not a violation.

2. **43 of 53 violations are false positives** from a Bilun engine bug:
   `_specialty_matches` does naive substring matching, so "Kalp ve Damar
   Cerrahisi" doesn't match the rule token "kalp damar cerrahisi" because
   of the "ve" word. Documented in README §Finding 1.

3. **Only ~10 real specialty-scope violations** in the dataset — mostly
   CYMBALTA prescribed by Cardiology/Internal Medicine (requires endokrinoloji
   or nöroloji). This is genuine signal but a small number.

4. **8 golden cases** reflects the actual engine output honestly. Padding
   the count would defeat the purpose of real-data validation.

### Honest recommendation

The specialty-scope dimension turned out to be **less valuable than the
diagnosis dimension** (item 1) for Bilun's product. Item 1 delivered 89
golden cases and 18K real violations; item 2 delivered 8 golden cases and
53 violations (43 of which are engine bugs). The biggest concrete output
of item 2 is **the discovery that `_specialty_matches` needs improvement
before specialty-scope checks can ship to hospitals**.

The harness and pytest are still useful — they lock in current behavior so
future fixes to the substring-collision bug will require explicitly updating
the golden dataset. But this should not be marketed as a headline Bilun
feature; item 1 is the real validation win.

### Files changed
- `scripts/validation/rx_loader.py` — added `load_specialty_pairs()` + `load_specialty_rule_drug_tokens()`
- `scripts/validation/claim_builder.py` — added `prescriber_specialty` param (item 1 unaffected)
- `scripts/validation/validate_specialty_rules.py` — new file, harness
- `scripts/validation/build_golden_dataset.py` — added `--specialty` mode
- `scripts/validation/README.md` — added full specialty section + SERVISADI mapping + honest findings
- `tests/unit/domain/prose_rules/test_specialty_real_data.py` — new pytest, 10/10 pass
- `data/synthetic/sut/claims/ilay_validation/specialty_pairs.parquet` — intermediate data
- `data/synthetic/sut/claims/ilay_validation/specialty_violation_log.parquet` — 53 rows
- `data/synthetic/sut/claims/ilay_validation/specialty_rule_compliance.csv` — 399 rules
- `data/gazette/prose_rules/golden/ilay/specialty_ilay_4_2_15.json` — 6 golden cases
- `data/gazette/prose_rules/golden/ilay/specialty_ilay_4_2_35.json` — 2 golden cases
- `plans/backend/specialty-scope-validation-plan.md` — plan document
- `tasks/todo.md` — this file
