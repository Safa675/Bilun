## Task: Delete expensive DRG analytics

### Goal
Remove the entire `patient_outcome_expensive` / `DRGPanel` / `compute_drg_summary` pipeline; billing DRG motors stay.

### Subtasks
- [x] Confirm plan `plans/billing/delete-expensive-drg-analytics.md`
- [x] Pull `origin/main`; branch `chore/delete-expensive-drg`
- [x] Delete cache+domain DRG modules and dedicated unit tests
- [x] Strip builder/context/schema/patient_meta wiring
- [x] Strip API outcome fields + chatbot tool/context
- [x] Strip frontend `DRGPanel`, types, i18n
- [x] Fix remaining tests that mock `drg_summary` / `include_expensive`
- [ ] Verify targeted pytest + vitest; open PR

### Out of Scope
- Billing `drg_uplift` / `drg_package_adequacy` / `drg_unbundling`
- Fixing the empty-cache bug to keep the panel
- Historical plan markdown hygiene
- Unrelated local dirty-tree deletions

### Plan
Full inventory + risks: `plans/billing/delete-expensive-drg-analytics.md`

### Review
- Deleted: `build_expensive`, `expensive_compute`, `drg.py`, `drg_payload.py` + 4 dedicated tests
- Outcome API no longer has `include_expensive` / `drg_summary` / `expensive_analytics`
- Frontend claim-summary remains; `DRGPanel` gone
- Billing DRG motors untouched
