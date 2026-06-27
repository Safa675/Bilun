# Phase 5 Execution — Rule Database gaps (5a–5d, defer 5e)

Source: plans/frontend/rule-database-improvement-plan.md (edited 2026-06-27)

## Goal
Close the functional/UX gaps deferred from Phases 1–4: cross-navigation, URL deep links, API/filter completeness, polish. Defer file-split refactor (5e).

## Subtasks

### Hotfix (immediate)
- [ ] H1. Fix i18n bug: RuleDatabaseSection.tsx:977 `status.all` → `filters.all`

### 5a — Cross-navigation
- [ ] A1. Lift `onNavigateToRule(rule_id)` callback to RuleDatabaseSection; on call → setActiveTab("rules") + setSelectedRuleId(rule_id) + updateUrl
- [ ] A2. ClauseCard: `primary_rule_id` → clickable chip calling onNavigateToRule
- [ ] A3. ClauseCard: `matched_rule_ids` → outline chips (cap 3 + "+N"), each calls onNavigateToRule
- [ ] A4. Pass onNavigateToRule down to RuleDetailPanel, SectionDetailPane, ClauseBrowserPanel detail pane

### 5b — URL deep links
- [ ] B1. Read `rdClause` on mount → if set, activeTab=clauses, fetch getClause(rdClause), select in browser
- [ ] B2. Clause row click in Hükümler → updateUrl({ rdTab:"clauses", rdClause })
- [ ] B3. Bölümler row select → updateUrl({ rdTab:"sections", rdSection })
- [ ] B4. Dev tooltip/doc note for rdTab/rdClause/rdSection

### 5c — API + filter completeness
- [ ] C1. rules_catalog.list_clauses: add primary_rule_id filter (vectorized Polars)
- [ ] C2. routes/rules.py list_all_clauses: add primary_rule_id query param
- [ ] C3. schemas.py RuleClause: explicitly declare primary_rule_id, primary_rule_category, matched_rule_ids, has_algorithmic_gap, has_rule_encoding (keep extra="allow" for safety)
- [ ] C4. rules_catalog.get_clause + _clause_payload: resolve matched_rules:[{rule_id,rule_category_tr}] from RULE_BY_ID
- [ ] C5. sut.ts listClauses: add primary_rule_id param; RuleClause TS add matched_rules field
- [ ] C6. Hükümler toolbar: motor dropdown from catalog rules[] (36 entries) → primary_rule_id filter
- [ ] C7. Tests: pytest list_clauses(primary_rule_id=...), get_clause matched_rules resolved

### 5d — Polish
- [ ] D1. SectionDetailPane header: show "{clause_count} hüküm · {gap_clause_count} boşluk"
- [ ] D2. GlossaryStrip: replace hardcoded 337/951/481 with live values (prose-inventory rule_count sum + section rollup total + unique sections)
- [ ] D3. Remove dead i18n key coverage.totalExtracted from tr + en

### Verification
- [ ] V1. pytest tests/unit/api/test_sut_rules_api.py tests/unit/domain/sut/test_rules_catalog.py -q
- [ ] V2. cd frontend && npx tsc --noEmit && npx vitest run src/components/tabs/sut/sections/
- [ ] V3. Manual: motor dropdown filters; clause card chip switches to rule; ?rdClause=C002684 loads; section gap header shows

## Out of scope
- 5e file-split refactor (deferred)
- Gate B write path, patient surfaces, chatbot viewer
