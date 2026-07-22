## Task: Turkish UI full i18n (Phases 0–5)

### Goal
`bilun:locale=tr` shows zero allowlist-excluded English user-facing strings (per `plans/frontend/turkish-ui-full-i18n.md`).

### Subtasks
- [x] Phase 0: Stabilize audit allowlist + script
- [x] Phase 1: Wire `translateApiText` on all detail/note/rule_source renders
- [x] Phase 2: Expand `apiMessages` EN→TR patterns + messages
- [x] Phase 3: Kind maps + loanword cleanup + Gazette/surcharge labels
- [x] Phase 4: Chat error surface TR
- [x] Phase 5: Rule DB / Revenue EN prose → TR messages
- [x] Verify: vitest + Playwright TR crawl → 0 unexpected EN
- [x] Update plan Review + tasks/todo.md

### Out of Scope
- Phase 6 backend locale-aware note generation
- Changing EN locale copy

### Review
- Playwright `scripts/i18n/audit-tr-ui-english.mjs`: **findingCount=0**, unique=0
- Vitest: `apiMessages`, `sutLabels`, `billingReportFields`, `recommendedActions` pass
- Key fixes: billing prose patterns in `apiMessages.ts`; render wraps; kind/label maps; LLM error sanitization; Rule DB honesty/footnote/description_tr + category chips
