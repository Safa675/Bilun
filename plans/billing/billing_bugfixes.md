## Task: Fix billing algorithm bugs — duplicate grouping, double-counting, data pipeline

### Goal
Three bugs found: (1) duplicate test detection groups across entire patient history instead of per-visit, (2) drug copay and drug tier correction are the same money counted twice in the grand total, (3) the lab data pipeline strips visit IDs needed for correct grouping. Fix all three and add visit IDs to the data pipeline.

### Subtasks

#### Phase 1 — Data pipeline: add visit ID to lab data
- [ ] `scripts/synthetic/exporters.py`: add `basvuru_id` column to `_clean_lab()` output (current columns: HASTA_ID, SUB_CODE, ..., tarih)
- [ ] `src/bilun/cache/loaders.py`: rename `basvuru_id` → `visit_id` in `_normalize_lab()` and add it to the `keep` list
- [ ] `src/bilun/domain/billing/orchestrator.py`: extract `visit_id` alongside `date` and `test_name` when grouping `lab_df_pl` by patient; pass `patient_lab_visit_ids` to `compute_patient_billing_report()`
- [ ] `src/bilun/domain/billing/orchestrator.py`: update `compute_patient_billing_report()` signature and call site to accept `patient_lab_visit_ids`

#### Phase 2 — Lab algorithm: group by visit ID
- [ ] `src/bilun/domain/billing/lab.py`: add `patient_lab_visit_ids` parameter to `_optimize_lab_billing()`
- [ ] `src/bilun/domain/billing/lab.py`: change hemogram bundling from date-keyed to visit_id-keyed (fall back to date if visit_id missing)
- [ ] `src/bilun/domain/billing/lab.py`: add date/visit grouping to duplicate detection — count duplicates per visit_id, not across entire patient history

#### Phase 3 — Double-counting fix
- [ ] `src/bilun/domain/billing/claim_copay.py`: `total_copay_savings_try` should sum only visit (procedure-line) copay components; keep `rx_copay_savings_try` separate for display but exclude from total
- [ ] `src/bilun/domain/billing/types.py`: update `CopayOptimization.total_copay_savings_try` field doc/comment to clarify it's visit-procedure-only
- [ ] Update tests for new total

#### Phase 4 — Relabel
- [ ] Frontend: rename the total label from "Rule-calculated opportunity" / "Total copay savings" to "Maximum additional SGK reimbursement achievable" or a shorter equivalent
- [ ] Backend context builder: update any text references to "total recoverable" in context.py if needed

#### Phase 5 — Rebuild and verify
- [ ] Run `scripts/bilun/build_cache.py --activate` to regenerate cache with visit IDs and fixed algorithms
- [ ] Run full test suite
- [ ] Spot-check patient SENTETIK-HASTA-0039 totals

### Out of Scope
- **Line-level copay waiver application** — see `copay-ek1a-ek4d-scope-fix-plan.md` (supersedes the old note that copay exemptions “stay as-is” for savings attachment). EK-1A **ICD matching** in `ek1a.py` unchanged.
- Adding real Turkish hospital claim data (synthetic only)
- Full visit-ID propagation to all data types (drugs, procedures, materials) — only lab for now

### Related — synthetic demo data
- Sentetik kohort tier’ları, claim line semantiği, regen + cache: [`data/synthetic/README.md`](../../data/synthetic/README.md)
- Showcase credibility plan: [`plans/data/synthetic-demo-credibility-plan.md`](../data/synthetic-demo-credibility-plan.md)
