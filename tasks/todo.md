## Task: Frontend EN/TR localization

### Goal
English default UI with Turkish toggle (🇬🇧/🇹🇷) in AppTopBar; ₺ formatting; chat re-brief on locale change.

### Plan
[plans/frontend-i18n-tr.md](../plans/frontend-i18n-tr.md)

### Subtasks
- [x] Phase 0: i18n foundation (`LocaleProvider`, `useT`, formatters, `LocaleSwitcher`)
- [x] Phase 1: Shell — AppTopBar, SkipToContent, error page, `SutHowItWorksModal`, fonts `latin-ext`
- [x] Phase 2: Home landing, cohort filter bar, `PatientInvoiceTable`, `PatientSearch`
- [x] Phase 3: Patient workspace, billing page, `SutBillingReportSections`
- [x] Phase 4: Optimizer + all `sections/*` reference tools + `ToolsSection` + `PatientSection`
- [x] Phase 5: Chat panel UI, TR/EN prompts, locale change clears thread + re-brief
- [x] Phase 6 (partial): Admin/synthetic chips, message catalogs, build + core i18n tests pass
- [x] Phase 6: `tr/sections.ts` full Turkish translations; test helper + locale-wrapped component tests

### Review (2026-05-30)
**Done:** Full UI migration across shell, home, patient/billing, optimizer, reference tools, modals, admin/synthetic. `npm run build` passes; all vitest suites pass with `renderToStaticMarkupWithLocale`.

**Optional follow-up:** Add dedicated TR locale snapshot tests for key screens.
