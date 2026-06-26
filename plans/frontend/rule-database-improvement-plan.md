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

### Phase 1 — Honest copy + richer clause cards (1 PR, no new routes)

- [ ] i18n: add `coverage.totalRuleEngines` (“Kayıtlı kural motoru” / “Registered rule engines”); use in registry column instead of `totalExtracted`
- [ ] i18n: add `coverage.totalClauses` for left column (keep or rename “Çıkarılan hüküm” → “Canlı hüküm” for clarity)
- [ ] Add glossary help strip component under coverage header
- [ ] Extend `_clause_payload()`: add `primary_rule_id` (raw string), `primary_rule_category`, `matched_rule_ids` (short list). Note: `coverage_status`, `has_algorithmic_gap`, `has_rule_encoding`, `deontic_modality`, `annex_refs` are **already emitted** — no backend change needed for those.
- [ ] Sync `RuleClause` TS type (`frontend/src/lib/api/sut.ts`) with the full backend payload — it currently omits `has_algorithmic_gap`, `has_rule_encoding`, `deontic_modality` (type is behind backend).
- [ ] Upgrade `ClauseCard` → show `clause_id`, status chip, primary motor link, gap/encode badges
- [ ] Subtitle tweak: “{total} kural motoru — hüküm metni ve kullanım için sekmelere geçin”
- [ ] Tests: extend `test_rules_catalog.py` assert new fields on `get_rule_clauses`; snapshot i18n keys

**Done when:** Selecting `copay_rate_ek2c1` shows clauses with visible `clause_id` + primary/gap badges; coverage header no longer says “Çıkarılan hüküm: 36”.

### Phase 2 — Section → clauses drill-down (1 PR)

- [ ] `rules_catalog.list_section_clauses(section_id, section_title?, page, per_page, filters?)`
- [ ] `GET /api/rules/sections/clauses` endpoint + Pydantic response (reuse `RuleClause[]` + pagination meta)
- [ ] `getSectionClauses()` in `frontend/src/lib/api/sut.ts`
- [ ] `SectionBrowserPanel`: selectable rows + detail pane with paginated clauses
- [ ] Empty state when `clause_count === 0`
- [ ] API tests in `tests/unit/api/test_sut_rules_api.py`
- [ ] Domain tests: filter by `(section_id, section_title)`, pagination disjoint

**Done when:** Clicking §3.1.2 row (either title variant) lists its paragraphs with utilization metadata.

### Phase 3 — Global Hükümler browser tab (1 PR)

- [ ] `rules_catalog.list_clauses(...)` with vectorized Polars filters (`q` on `clause_id` + `in_force_text`)
- [ ] `GET /api/rules/clauses` + `GET /api/rules/clauses/{clause_id}`
- [ ] New tab `Hükümler` in `RuleDatabaseSection`
- [ ] `ClauseBrowserPanel` with search + filters + master-detail
- [ ] Clause detail shows all `matched_rule_ids` as links to Kurallar tab
- [ ] Performance: cap `per_page` at 200 (existing `_MAX_PER_PAGE`); debounce search 300ms. **Benchmark first** — global `in_force_text` LIKE across 4.710 rows via Polars filter is expected <100ms (vectorized), but verify before shipping; if slow, consider pre-built section-partitioned parquet or a trigram index.

**Done when:** Search `C002684` or “azasitidin” returns matching hükümler; click shows full text + which motors claim it.

### Phase 4 — Cross-links + polish (optional)

- [ ] Prose anchor chips → navigate to Hükümler with `section_id` filter
- [ ] URL query sync for `tab`, `clause_id`, `section_id`
- [ ] Section rollup consolidation option: “Bölüm başına birleştir” toggle (aggregate 470 duplicate-title rows for 481 unique section_ids → simpler browse — requires backend `group_by section_id` mode or client-side merge)
- [ ] `frontend` component test for `ClauseUtilizationCard` (vitest + mock clause)

---

## Files to touch (by phase)

| Layer | Files |
|-------|--------|
| Domain | `src/bilun/domain/sut/rules_catalog.py` |
| API | `src/bilun/api/routes/rules.py`, `src/bilun/api/schemas.py` |
| Frontend | `frontend/src/components/tabs/sut/sections/RuleDatabaseSection.tsx`, new `ClauseUtilizationCard.tsx` (extract) |
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
_Plan authored 2026-06-26. Supersedes offline HTML audit direction in `plans/billing/prose-corpus-review-export-plan.md` for in-app human review._

_Revised 2026-06-26 after codebase verification: corrected JSON rule count (185→337), unique section count (400→481), and field-exposure facts (5/8 utilization fields already wired through `_clause_payload()`; only 3 need new backend wiring; TS type is behind backend). Added performance benchmark note for global search and ClauseCard layout-stability guidance._
