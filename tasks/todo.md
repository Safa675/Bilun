## Task: Compliance honesty, coverage split, Red Kuyruğu polish

### Goal
Stop the Compliance tab advertising fake 8-pillar data, move the Rule Database coverage dump into its own Kapsam subtab, and make Red Kuyruğu a finished queue over the real API — then wire live finding families from the billing cache.

### Subtasks
- [x] P0.1 Shrink Compliance strip to live `exemptions` + `surcharge`; delete fake radar KPIs, hardcoded badges, and `DEMO_*` modules
- [x] P0.2 Add Rule Database `coverage` (`Kapsam`) subtab; move `CoverageSummaryPanel` + collapsed June archive banner into it; default `rdTab=coverage`
- [x] P0.3 Red Kuyruğu: delete leftover subtitle/Eyebrow, fix `setPage(1)`, server-side `playbook_matched`, Stat KPIs, EN/chat labels, row drawer for corrective steps
- [x] P0 verify: vitest + `tsc --noEmit`; no demo tables; coverage wall gone from Kurallar
- [ ] P1.1 Cache-time `cohort_compliance_index` + `GET /api/compliance-index` from `recommended_actions` where `finding_type == "compliance"`
- [ ] P1.2 Add `copay_rates` Compliance subtab on existing patient-alerts API
- [ ] P1.3 Live modules: materials, drug_indication, lab, payment_methods from the index; header Stats + badges from live counts
- [ ] P1.4 MEDULA: no duplicate playbook; optional live count chip linking to Red Kuyruğu
- [ ] P1 verify: pytest + vitest + tsc; cache rebuild; cohort filter moves KPIs

### Out of Scope
- Encoding remaining SUT gap families
- Reopening the June 2026 algorithm fact-check
- Promoting checklist / session uplift into compliance
- Live MEDULA SOAP / rebill
- Finishing `plans/compliance_tab_full_taxonomy_redesign_plan.md` (superseded)

### Review (P0)
- `npx tsc --noEmit` clean
- vitest: SUTComplianceDashboard, workspaceSubtabs, MedulaRejectionQueueTab, RuleDatabaseSection, constants, optimizer shell, apiMessages — green
- pytest `tests/unit/api/test_medula_rejection_queue_api.py` — 9 passed
- Demo compliance modules deleted; unknown `?compTab=` falls back to exemptions
- Coverage dump and June archive live only on Kapsam (`rdTab=coverage`)
