## Task: Rule Database tab — copy fixes + individual hüküm drill-down

### Goal
Make the **Kural Veritabanı** tab honest about what each number means (4.710 hüküm vs 36 kural motoru vs 185 JSON satırı) and let a developer **browse individual SUT clauses** — by section, by rule, and globally — with clear utilization metadata (primary motor, coverage status, encode/gap flags).

### Problem statement (current gaps)

| Issue | Where | Impact |
|-------|--------|--------|
| Registry column labeled **“Çıkarılan hüküm”** but shows **36** | `CoverageSummaryPanel` uses `totalExtracted` for `registry.total_rules` | Users think 36 = clause count; confuses with 4.710 |
| **Bölümler** tab shows counts only | `SectionBrowserPanel` — no row action | Cannot see which paragraphs live under §3.1.2 |
| **Kurallar** tab has clause drill-down | `RuleDetailPanel` + `GET /rules/{id}` | Works rule→clauses only; no section→clauses or clause→rules |
| **ClauseCard** omits utilization | Shows `is_primary`/`match_score` only; omits raw `clause_id`, `primary_rule_id`, `primary_rule_category`, `matched_rule_ids`. Note: `coverage_status`, `has_algorithmic_gap`, `has_rule_encoding`, `deontic_modality`, `annex_refs` ARE in the backend payload but missing from the TS type |
| **951 section rows** for ~400 unique `section_id` | `build_section_summary` groups by `(section_id, section_title)` | Same §1.8 appears twice (heading vs body); drill-down key must be explicit |
| **Düz metin motorları** shows § anchors only | `ProseInventoryPanel` | No link from `4.2.33` anchor to underlying clauses |

### Vocabulary (must appear in UI copy)

| Term (TR) | Count (today) | Meaning |
|-----------|---------------|---------|
| **Hüküm** | 4.710 | One in-force SUT paragraph (`clause_id`, e.g. `C002684`) |
| **Kural motoru** | 36 | One `RULE_REGISTRY` entry (`drug_indication_prose`, `copay_rate_ek2c1`, …) |
| **JSON kural satırı** | 337 | One object inside `prose_rules/*.json` `rules[]` (drug_indication alone is 164) |
| **Bölüm özeti satırı** | 951 | Rollup row = `section_id` + `section_title` pair (481 unique section_ids; 470 are duplicate-title rows) |

Add a collapsible **“Sayılar ne anlama geliyor?”** help strip under the coverage pipeline header (EN + TR i18n).

---

## Architecture

### Data already exists (no new parquet required for v1)

Source: `data/gazette/sut_clause_coverage.parquet` (4.710 in-force rows).

Per clause fields to surface:

- Identity: `clause_id`, `section_id`, `section_title`, `section_path`, `paragraph_index`
- Text: `in_force_text` (via existing `clause_display_text()`)
- Classification: `primary_rule_id`, `primary_rule_category`, `matched_rule_ids`, `coverage_status`
- Utilization: `has_algorithmic_gap`, `has_rule_encoding`, `deontic_modality`, `annex_refs`

Section rollup: `sut_coverage_by_section.parquet` (951 rows) — keep for table; clause list filters coverage by `(section_id, section_title?)`.

### New API surface

```
GET /api/rules/clauses
  ?page=1&per_page=50
  &q=...                    # clause_id prefix or text search (in_force_text)
  &section_id=3.1.2
  &section_title=...        # optional — disambiguate rollup rows
  &primary_rule_id=...
  &coverage_status=partial|implemented|...
  &has_gap=true|false
  &has_encoding=true|false

GET /api/rules/clauses/{clause_id}
  → single clause + matched_rule_ids resolved to registry labels

GET /api/rules/sections/clauses   (alias-friendly alternative)
  ?section_id=3.1.2&section_title=...&page=1&per_page=50
```

**Route ordering:** register `/rules/clauses` and `/rules/sections/clauses` **before** `/rules/{rule_id}` in `routes/rules.py` to avoid `clause_id` being captured as `rule_id`.

**Extend existing:** enrich `RuleClause` schema + `_clause_payload()`. Five of the eight
utilization fields are **already** wired through `_clause_payload()` to the API
(`coverage_status`, `has_algorithmic_gap`, `has_rule_encoding`, `deontic_modality`,
`annex_refs`) but missing from the `RuleClause` TS type. Only 3 need new backend
wiring: raw `primary_rule_id`, `primary_rule_category`, and `matched_rule_ids` as a
short list (currently only `is_primary` boolean + `match_score` for the queried rule).

### UI structure (four tabs → master–detail)

```
┌─────────────────────────────────────────────────────────────┐
│ Coverage pipeline (fixed labels + glossary)                 │
├──────────┬──────────┬──────────┬────────────────────────────┤
│ Kurallar │ Bölümler │ Hükümler │ Düz metin motorları        │
├──────────┴──────────┴──────────┴────────────────────────────┤
│ Master list (left / top)  │  Detail pane (right / bottom)   │
│ - rule / section / clause │  - ClauseCard(s) or rule meta   │
│   row selection           │  - utilization chips + links    │
└───────────────────────────┴─────────────────────────────────┘
```

**Shared component:** extract `ClauseCard` → `ClauseUtilizationCard` used by:
- `RuleDetailPanel` (rule context: highlight `is_primary`)
- `SectionClausePanel` (section context)
- `ClauseBrowserPanel` (global context)

**ClauseCard additions:**
- Mono `clause_id` header (copy-friendly)
- `CoverageChip` for `coverage_status`
- Chip: primary motor (`primary_rule_id`) — **click → switch to Kurallar tab + select rule**
- Badges: `has_rule_encoding`, `has_algorithmic_gap` (mutually informative)
- Optional: matched secondary motors as outline chips — **cap display at 3** with "+N" overflow; use fixed card height so the master-detail grid doesn't reflow when clause lists vary in matched-rule count

**Section browser:**
- Row click sets `selectedSection = { section_id, section_title }`
- Detail pane loads `GET /rules/sections/clauses?...`
- Show rollup stats at top (clause_count, gap_clause_count from selected row)

**New Hükümler tab:**
- Search input (debounced) → `q` param
- Filters: coverage status, has gap, has encoding, primary rule (dropdown from catalog)
- Paginated table: `clause_id`, `section_id`, excerpt (80 chars), status, primary motor
- Row click → full `ClauseUtilizationCard` + link to rule

**Prose tab (light touch):**
- SUT anchor chips → `onClick` pre-fills Hükümler tab filter `section_id` prefix (e.g. `4.2.33`)

### URL state (optional phase 3)

Query params on dev Rule Database route:
`?tab=clauses&clause=C002684` or `?tab=sections&section=3.1.2`

Enables sharing a specific hüküm link in reviews. Not required for MVP.

---

## Phased delivery

### Phase 1 — Honest copy + richer clause cards (1 PR, no new routes) ✅

- [x] i18n: add `coverage.totalRuleEngines` (“Kayıtlı kural motoru” / “Registered rule engines”); use in registry column instead of `totalExtracted`
- [x] i18n: add `coverage.totalClauses` for left column (keep or rename “Çıkarılan hüküm” → “Canlı hüküm” for clarity)
- [x] Add glossary help strip component under coverage header
- [x] Extend `_clause_payload()`: add `primary_rule_id` (raw string), `primary_rule_category`, `matched_rule_ids` (short list). Note: `coverage_status`, `has_algorithmic_gap`, `has_rule_encoding`, `deontic_modality`, `annex_refs` are **already emitted** — no backend change needed for those.
- [x] Sync `RuleClause` TS type (`frontend/src/lib/api/sut.ts`) with the full backend payload — it currently omits `has_algorithmic_gap`, `has_rule_encoding`, `deontic_modality` (type is behind backend).
- [~] Upgrade `ClauseCard` → show `clause_id`, status chip, primary motor link, gap/encode badges — **badges done; motor is plain text, not a link** (→ Phase 5)
- [x] Subtitle tweak: “{total} kural motoru — hüküm metni ve kullanım için sekmelere geçin”
- [x] Tests: extend `test_rules_catalog.py` assert new fields on `get_rule_clauses`; snapshot i18n keys

**Done when:** Selecting `copay_rate_ek2c1` shows clauses with visible `clause_id` + primary/gap badges; coverage header no longer says “Çıkarılan hüküm: 36”.

### Phase 2 — Section → clauses drill-down (1 PR) ✅

- [x] `rules_catalog.list_section_clauses(section_id, section_title?, page, per_page, filters?)`
- [x] `GET /api/rules/sections/clauses` endpoint + Pydantic response (reuse `RuleClause[]` + pagination meta)
- [x] `getSectionClauses()` in `frontend/src/lib/api/sut.ts`
- [x] `SectionBrowserPanel`: selectable rows + detail pane with paginated clauses
- [x] Empty state when `clause_count === 0`
- [x] API tests in `tests/unit/api/test_sut_rules_api.py`
- [x] Domain tests: filter by `(section_id, section_title)`, pagination disjoint
- [~] Detail pane rollup stats show `clause_count` only — **`gap_clause_count` not in header** (→ Phase 5)

**Done when:** Clicking §3.1.2 row (either title variant) lists its paragraphs with utilization metadata.

### Phase 3 — Global Hükümler browser tab (1 PR) ✅

- [x] `rules_catalog.list_clauses(...)` with vectorized Polars filters (`q` on `clause_id` + `in_force_text`)
- [x] `GET /api/rules/clauses` + `GET /api/rules/clauses/{clause_id}`
- [x] New tab `Hükümler` in `RuleDatabaseSection`
- [x] `ClauseBrowserPanel` with search + filters + master-detail
- [~] Clause detail shows all `matched_rule_ids` as links to Kurallar tab — **plain text only** (→ Phase 5)
- [~] Filters: coverage status, has gap, has encoding — **`primary_rule_id` dropdown missing** (API + UI → Phase 5)
- [x] Performance: cap `per_page` at 200 (existing `_MAX_PER_PAGE`); debounce search 300ms. Verified ~12ms search / ~33ms full count on 4.710 rows.

**Done when:** Search `C002684` or “azasitidin” returns matching hükümler; click shows full text + which motors claim it.

### Phase 4 — Cross-links + polish ✅ (partial)

- [x] Prose anchor chips → navigate to Hükümler with `section_id` filter (`rdSection` prefills search)
- [~] URL query sync for `tab`, `clause_id`, `section_id` — **`rdTab` + `rdSection` only; `rdClause` not wired** (→ Phase 5)
- [x] Section rollup consolidation option: “Bölüm başına birleştir” toggle (`consolidate` API param)
- [~] `frontend` component test for `ClauseUtilizationCard` — **`ClauseCard` tested in `RuleDatabaseSection.test.tsx`; not extracted to own file** (→ Phase 5)

### Phase 5 — Gaps from Phases 1–4 (polish + missed plan items)

Items that were specified in Phases 1–4 but shipped incomplete, plus maintainability follow-ups identified in the post-implementation review (2026-06-26).

#### 5a — Cross-navigation (highest user value)

- [ ] **`onNavigateToRule(rule_id)`** callback lifted to `RuleDatabaseSection` — switches to Kurallar tab + `setSelectedRuleId`
- [ ] **`ClauseCard`**: `primary_rule_id` as clickable chip (not plain `<span>`)
- [ ] **`ClauseCard`**: `matched_rule_ids` as outline chips (cap 3 + “+N”); each chip calls `onNavigateToRule`
- [ ] Pass `onNavigateToRule` from `RuleDetailPanel`, `SectionDetailPane`, and `ClauseBrowserPanel` detail pane

**Done when:** Clicking `drug_indication_prose` on any clause card opens that motor in Kurallar.

#### 5b — URL deep links

- [ ] Read `rdClause` from `searchParams` on mount; if set → `activeTab=clauses`, fetch via `getClause(rdClause)`, select in browser
- [ ] On clause row click in Hükümler → `updateUrl({ rdTab: "clauses", rdClause: clause_id })`
- [ ] `rdSection` on Bölümler row select for shareable section drill-down links (was Phase 4 gap — required, not optional)
- [ ] Document params in plan / dev tooltip: `rdTab`, `rdClause`, `rdSection` (avoid collision with app-shell `?tab=`)

**Done when:** `?rdTab=clauses&rdClause=C004975` opens the correct hüküm without manual search.

#### 5c — API + filter completeness

- [ ] Add `primary_rule_id` param to `list_clauses()` + `GET /api/rules/clauses`
- [ ] Hükümler toolbar: motor dropdown populated from catalog `rules[]` (36 entries)
- [ ] Pydantic `RuleClause`: declare all utilization fields explicitly (`primary_rule_id`, `matched_rule_ids`, `has_algorithmic_gap`, `has_rule_encoding`, …) — stop relying on `extra="allow"` for OpenAPI accuracy
- [ ] `get_clause()` response includes `matched_rules: [{rule_id, rule_category_tr}]` resolved from `RULE_BY_ID` (was Phase 1 architecture spec line 59 — required, not optional)

**Done when:** Filter Hükümler to `drug_indication_prose` only via dropdown; OpenAPI shows full `RuleClause` shape.

#### 5d — UI polish + i18n fixes

> **Hotfix first:** the `status.all` → `filters.all` i18n key bug (below) is a 1-line trivial fix — ship immediately, do not wait for the rest of Phase 5.

- [ ] **i18n bug (hotfix):** `ClauseBrowserPanel` status “all” button uses missing key `status.all` → use `filters.all` (“Tümü”)
- [ ] **Section detail header**: show `{clause_count} hüküm · {gap_clause_count} boşluk` from selected rollup row
- [ ] **Glossary strip**: replace hardcoded `JSON_RULE_COUNT = 337` / `SECTION_ROWS = 951` with live values — sum `prose-inventory` `rule_count`; section rows from coverage meta or section rollup `total`
- [ ] Remove dead i18n key `coverage.totalExtracted` if unused

#### 5e — Maintainability refactor (DEFERRED — not part of this execution)

> **Evaluation note (2026-06-27):** Pure file-split refactor of a *dev-only* tab delivers zero user value. Deferred unless `RuleDatabaseSection.tsx` becomes actively painful to work in. If taken up later, do it **before** the next functional phase so features land in the new files cleanly (avoid double-editing). Listed here as a tracked follow-up only.

#### Phase 5 verification

**PR sizing (per evaluation):**
- PR 1 — functional closure: 5a + 5b + 5c (cross-nav, deep links, API/filter completeness)
- PR 2 — polish: 5d (live glossary counts, section gap header, dead-key removal)
- Hotfix (immediate): i18n `status.all` bug
- Deferred: 5e (file-split refactor)

```bash
pytest tests/unit/api/test_sut_rules_api.py tests/unit/domain/sut/test_rules_catalog.py -q
cd frontend && npm run tsc --noEmit && npm run vitest run src/components/tabs/sut/sections/
```

Manual:
1. Hükümler → motor dropdown → only `drug_indication_prose` clauses.
2. Any clause card → click motor chip → Kurallar tab selects that rule.
3. Paste `?rdTab=clauses&rdClause=C002684` → card loads selected.
4. Bölümler → §3.1.2 → header shows gap count.

**Out of scope for Phase 5:** Gate B encode-from-UI, patient-facing surfaces, chatbot clause viewer.

---

## Files to touch (by phase)

| Layer | Files |
|-------|--------|
| Domain | `src/bilun/domain/sut/rules_catalog.py` |
| API | `src/bilun/api/routes/rules.py`, `src/bilun/api/schemas.py` |
| Frontend | `frontend/src/components/tabs/sut/sections/RuleDatabaseSection.tsx`, `sections/rule-database/*.tsx` (Phase 5 split) |
| API client | `frontend/src/lib/api/sut.ts` |
| i18n | `frontend/src/messages/en/sections.ts`, `frontend/src/messages/tr/sections.ts` |
| Tests | `tests/unit/domain/sut/test_rules_catalog.py`, `tests/unit/api/test_sut_rules_api.py` |

**Out of scope for this plan:**
- Editing / encoding clauses from UI (Gate B write path stays offline)
- Replacing `prose_corpus` CSV pipeline
- Production patient-facing surfaces (dev-only tab unchanged)
- Rebuilding section rollup parquet schema (defer consolidation to Phase 4)
- Chatbot RAG clause viewer (separate product surface)

---

## Success criteria

1. A new developer can answer **“§3.1.2’de kaç hüküm var ve hangileri gap?”** without leaving Rule Database.
2. Coverage header never implies **36 = hüküm count**.
3. Any displayed clause shows **`clause_id` + primary motor + coverage_status + encode/gap flags**.
4. **Rule → clauses** (existing), **section → clauses** (new), **global search** (new) all use the same enriched clause payload.
5. All new endpoints have unit tests; existing 838+ test suite stays green.

---

## Verification checklist

```bash
# Backend
pytest tests/unit/api/test_sut_rules_api.py tests/unit/domain/sut/test_rules_catalog.py -q

# Frontend
cd frontend && npm run tsc --noEmit && npm run vitest run
```

Manual (dev role):
1. Open Kural Veritabanı → confirm left “Canlı hüküm: 4.710”, right “Kural motoru: 36”.
2. Bölümler → click §4.2.14.C (or §3.1.2) → clause list loads.
3. Hükümler → search `C004975` → card shows `drug_indication_prose` + gap badge.
4. Kurallar → `material_bundling_prose` → clause cards show same metadata as section browse.

---

## Review

### 2026-06-26 — Plan authored
Supersedes offline HTML audit direction in `plans/billing/prose-corpus-review-export-plan.md` for in-app human review.

### 2026-06-26 — Pre-implementation revision
Corrected JSON rule count (185→337), unique section count (400→481), and field-exposure facts (5/8 utilization fields already wired through `_clause_payload()`; only 3 need new backend wiring; TS type is behind backend). Added performance benchmark note for global search and ClauseCard layout-stability guidance.

### 2026-06-26 — Phases 1–4 implementation review
**Shipped:** honest coverage labels, glossary, enriched `ClauseCard`, section drill-down, Hükümler global browser, prose anchor → Hükümler, consolidate toggle, 62 backend tests + `ClauseCard` vitest.

**Grade: A−** functionally; **B+** polish. Core goal met (browse individual hükümler by rule, section, global search).

**Deferred to Phase 5:** motor/cross-tab navigation, `rdClause` deep links, `primary_rule_id` API filter + dropdown, Pydantic schema completeness, glossary live counts, section gap header, i18n `status.all` bug, component file split.

**Benchmarks (local):** `list_clauses(q="azasitidin")` ~12ms; full 4.710 count ~33ms.

### 2026-06-27 — Phase 5 evaluation + implementation
**Plan revised** per evaluation: promoted `matched_rules` registry resolution and `rdSection` deep link from "optional" to required (they were original Phase 1/4 spec, not optional); deferred 5e file-split refactor (zero user value on a dev-only tab); reordered i18n `status.all` bug as an immediate hotfix.

**Implemented (5a–5d):** `onNavigateToRule` cross-navigation with clickable motor/secondary chips on `ClauseCard`; `rdClause` + `rdSection` URL deep links (read on mount, write on select); `primary_rule_id` filter end-to-end (domain → API → TS → motor dropdown); explicit `RuleClause` Pydantic fields + `matched_rules` resolution from `RULE_BY_ID`; `MatchedRuleRef` schema; live glossary counts (prose-inventory + section rollup fetches replacing hardcoded 337/951/481); section detail header showing clause + gap counts; i18n `status.all` → `filters.all` hotfix; removed dead `coverage.totalExtracted` key.

**Verified:** 892 backend tests pass (+2 new: `primary_rule_id` filter, `matched_rules` resolution); tsc clean; 7 vitest tests pass.

**Deferred:** 5e file-split refactor (tracked as optional follow-up).
