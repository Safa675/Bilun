# Rule Database — Full Backend → Frontend Surface Plan

> **Status:** Approved — expert-only framing  
> **Last updated:** 2026-06-15  
> **Context:** The Kural Veritabanı tab exposes the rule catalog, per-rule clause drill-down, and a **frozen fact-check audit banner**. Substantial backend coverage work (clause extraction matrix, registry rollup, section summaries, prose rule inventory) exists offline or in parquets but is **not** served to the UI. Users cannot see “how many SUT clauses were extracted vs how many became algorithms” without reading `baseline_metrics.json` or running `build_sut_coverage.py` locally.  
> **Product decision:** Rule Database is an **expert/dev-only surface**, not a consumer dashboard. Analysts will not see it (role-gated). Therefore the UI does not need hand-holding simplification; it should be a dense, honest audit cockpit. Section browser and prose inventory move from “optional v1.1” to core expert features.  
> **Role gating:** Frontend hides Rule Database tab from `billing_analyst` role; shows it to `compliance_engineer` / `dev` / admin roles. Within the tab, all expert panels are visible to authorized roles.  
> **Related:** `src/bilun/domain/sut/rules_catalog.py`, `scripts/sut/prose/coverage.py`, `scripts/sut/rebuild_baseline_metrics.py`, `tasks/archive/sut-fact-check-2026-06/baseline_metrics.json`, `frontend/src/components/tabs/sut/sections/RuleDatabaseSection.tsx`

---

## Task: Expose complete Rule Database backend data in the UI

### Goal

Ship a **coverage-first** Rule Database tab: top summary shows extracted-clause → algorithm pipeline health; rule list and clause drill-down remain; fact-check audit is clearly labeled as historical. All stats are served from **live API reads** of production parquets (or honest empty states), not hardcoded frontend numbers or archived JSON only.

### Success criteria

| # | Criterion | Verify |
|---|---|-----------|
| 1 | `GET /api/rules` includes `coverage_summary` with clause totals + registry status counts when parquets exist | API unit test |
| 2 | Expert UI shows dense coverage summary panel (clauses extracted, by status, algorithmic gap %, registry status counts) | Manual smoke |
| 3 | Coverage summary and fact-check banner are **visually and semantically separate**; fact-check labeled as frozen June 2026 audit | Design review |
| 4 | Rule list shows `has_clause_mapping` / zero-match warning for implemented/partial rules with 0 clauses | UI + data |
| 5 | `GET /api/rules/sections` returns paginated section rollup when `sut_coverage_by_section.parquet` exists | API test |
| 6 | `GET /api/rules/prose-inventory` returns prose engine manifest | API test |
| 7 | `artifacts_available: false` → coverage panel shows build instructions, not zeros masquerading as truth | API test without parquet |
| 8 | TR + EN strings for all new labels | i18n review |
| 9 | Rule Database tab is hidden from analyst role; visible to compliance engineer / dev role | Auth/routing review |

**Removed:** Chat page context enrichment (experts do not need AI headline summaries).

### Out of scope

- Re-running SUT prose extraction or changing classify/match algorithms
- Live re-audit of the 28 fact-check units (frozen snapshot stays)
- New vector / RAG UI (clause search stays chatbot tool)
- Patient billing / optimization surfaces
- Auto-committing `baseline_metrics.json` to API (derive at read time from parquets instead)
- Consumer-friendly simplification of Rule Database (this is an expert cockpit)

---

## Gap analysis — what exists today

### Backend (available)

| Layer | Location | Contents |
|-------|----------|----------|
| **Rule registry** | `src/bilun/domain/sut/rule_registry.py` | ~28 `RuleRegistryEntry`: `coverage_status`, `domain_modules`, SUT § + EK refs, TR labels |
| **Clause coverage matrix** | `data/gazette/sut_clause_coverage.parquet` | Per-clause: `text_tr`, `matched_rule_ids`, `coverage_status`, `has_algorithmic_gap`, deontic modality |
| **Registry coverage** | `data/gazette/sut_registry_coverage.parquet` | Per `rule_id`: `matched_clause_count`, `has_clause_mapping` |
| **By-rule summary** | `data/gazette/sut_coverage_by_rule.parquet` | Primary-rule aggregates (offline build; **not in constants.py**) |
| **By-section summary** | `data/gazette/sut_coverage_by_section.parquet` | Section-level gap counts (offline build; **not in constants.py**) |
| **Source clauses** | `data/gazette/sut_clauses.parquet` | Raw extracted corpus (~8k rows in archived baseline) |
| **Coverage builders** | `scripts/sut/prose/coverage.py` | `build_coverage_summary`, `build_section_summary`, `build_registry_coverage_summary` |
| **Baseline snapshot** | `scripts/sut/rebuild_baseline_metrics.py` → archived JSON | Full rollup template (clause + registry + top gaps) |
| **Fact-check audit** | `src/bilun/domain/sut/fact_check_audit.py` | Frozen 28-unit verdicts → `fact_check_rollup()` |
| **Prose JSON engines** | `data/gazette/prose_rules/*.json` | 12 rule-set files (copay, bundling, session, etc.) |
| **Material scope helper** | `src/bilun/domain/materials/coverage_scope.py` | Prose rule counts, Gate B manifest stats (today on **validation** API only) |

### API (exposed today)

| Endpoint | Fields |
|----------|--------|
| `GET /api/rules` | `rules[]`, `total`, `artifacts_available`, `fact_check` |
| `GET /api/rules/{rule_id}` | `rule`, `clauses[]`, pagination, `artifacts_available` |

**Not exposed:** clause-level rollup, section rollup, top gap categories, `zero_clause_matches`, prose engine inventory, `generated_at` / build stamp, `sut_clauses` total count.

### Frontend (exposed today)

| UI | Shows |
|----|-------|
| `RuleDatabaseSection` | Search, status filters, master-detail rule list, per-rule `matched_clause_count`, clause cards |
| `FactCheckRollupBanner` | June 2026 audit counts (looks like live coverage — **misleading**) |
| `artifactsUnavailable` banner | Parquet missing warning |

**Not shown:** pipeline summary table, section browser, rules with zero clause mapping, prose JSON stats.

---

## Target architecture

```mermaid
flowchart TB
  subgraph offline [Offline build]
    CL[sut_clauses.parquet]
    BUILD[build_sut_coverage.py]
    CC[sut_clause_coverage.parquet]
    REG[sut_registry_coverage.parquet]
    SEC[sut_coverage_by_section.parquet]
    RULE[sut_coverage_by_rule.parquet]
    CL --> BUILD
    BUILD --> CC
    BUILD --> REG
    BUILD --> SEC
    BUILD --> RULE
  end

  subgraph api [API layer]
    RC[rules_catalog.py]
    R1[GET /api/rules]
    R2[GET /api/rules/{id}]
    R3[GET /api/rules/sections optional]
    RC --> R1
    RC --> R2
    RC --> R3
  end

  subgraph ui [Rule Database tab]
    SUM[CoverageSummaryPanel]
    FC[FactCheckPanel collapsible]
    LIST[RuleList]
    DET[RuleDetailPanel]
    SECUI[SectionTable optional]
    R1 --> SUM
    R1 --> FC
    R1 --> LIST
    R2 --> DET
    R3 --> SECUI
  end

  CC --> RC
  REG --> RC
  SEC --> RC
```

---

## Phase 1 — Backend: `coverage_summary` on catalog (prerequisite)

**Effort:** Small–medium  
**Files:** `src/bilun/domain/sut/rules_catalog.py`, `src/bilun/domain/constants.py`, `src/bilun/api/schemas.py`, `src/bilun/api/routes/rules.py`

### 1.1 Add parquet paths to constants

```python
SUT_COVERAGE_BY_RULE_PATH = _GAZETTE_DIR / "sut_coverage_by_rule.parquet"
SUT_COVERAGE_BY_SECTION_PATH = _GAZETTE_DIR / "sut_coverage_by_section.parquet"
```

### 1.2 Implement `coverage_summary()` in `rules_catalog.py`

Vectorized Polars aggregates (mirror `rebuild_baseline_metrics.py` logic, no pandas in API hot path):

**`clauses` block** (from `sut_clause_coverage.parquet` when present):

- `total_extracted` — row count
- `by_status` — `[{ coverage_status, count }]` for: `implemented`, `partial`, `missing`, `needs_claim_lines`, `non_algorithmic`
- `algorithmic_gaps` — count where `has_algorithmic_gap == true`
- `algorithmic_gap_pct` — rounded 1 decimal
- `top_gap_categories` — top 10 `primary_rule_category` among gaps

**`registry` block** (from `RULE_REGISTRY` + `sut_registry_coverage.parquet`):

- `total_rules`
- `by_status` — `[{ registry_coverage_status, count }]` from each entry's `coverage_status`
- `implemented_rules`, `partial_rules`, `missing_rules`, `needs_claim_lines_rules`, `non_algorithmic_rules` — convenience counts
- `zero_clause_matches` — rules where `coverage_status in (implemented, partial)` AND `matched_clause_count == 0` (data quality flag)
- `rules_without_mapping` — `has_clause_mapping == false`

**`meta` block:**

- `generated_at` — max `source_effective_date` or file mtime of newest parquet (honest staleness indicator)
- `artifacts_available` — same semantics as today
- `clauses_source_available` — `sut_clauses.parquet` exists (optional total for subtitle)

When parquets missing: return `artifacts_available: false`, empty counts, `unavailable_reason` string — **do not fabricate baseline JSON numbers**.

### 1.3 Extend `RuleCatalogResponse`

```python
class CoverageStatusCount(BaseModel):
    status: str
    count: int

class ClauseCoverageSummary(BaseModel):
    total_extracted: int = 0
    by_status: list[CoverageStatusCount] = []
    algorithmic_gaps: int = 0
    algorithmic_gap_pct: float = 0.0
    top_gap_categories: list[dict] = []

class RegistryCoverageSummary(BaseModel):
    total_rules: int = 0
    by_status: list[CoverageStatusCount] = []
    zero_clause_matches: list[RuleCatalogEntry] = []  # or slim { rule_id, coverage_status }

class CoverageSummary(BaseModel):
    clauses: ClauseCoverageSummary
    registry: RegistryCoverageSummary
    meta: dict

class RuleCatalogResponse(BaseModel):
    ...
    coverage_summary: CoverageSummary
```

Wire in `get_rule_catalog()`.

### 1.4 Tests

- [ ] `tests/unit/domain/sut/test_rules_catalog.py` — `coverage_summary()` with mocked parquet / empty
- [ ] `tests/unit/api/test_sut_rules_api.py` — schema validation, counts match `len(RULE_REGISTRY)`
- [ ] Skip integration tests when parquet absent (existing `_needs_coverage` pattern)

---

## Phase 2 — Backend: supplementary endpoints (medium)

### 2.1 `GET /api/rules/sections`

Paginated section rollup from `sut_coverage_by_section.parquet` (core expert feature):

| Field | Source |
|-------|--------|
| `section_id`, `section_title` | parquet |
| `clause_count` | parquet |
| `worst_coverage_status` | parquet |
| `gap_clause_count` | parquet |
| `primary_categories` | JSON list in parquet |

Query: `page`, `per_page`, `q` (section id/title), `min_gap_count`.

Returns `{ sections, total, page, artifacts_available }`.

### 2.2 `GET /api/rules/prose-inventory`

Lightweight prose engine manifest for Rule Database “implementation layer” transparency (core expert feature):

| Field | Source |
|-------|--------|
| `prose_rule_files` | glob `data/gazette/prose_rules/*.json` (exclude `.schema.json`) |
| Per file: `rule_set_id`, `rule_count`, `effective_date` if present | JSON parse |
| `material_bundling_scope` | reuse `material_bundling_coverage_scope()` from `coverage_scope.py` |

Keeps material bundling detail out of `/api/rules` payload size.

### 2.3 Enrich per-rule catalog entry

Add to `RuleCatalogEntry` (already partially there):

- [ ] `has_clause_mapping: bool` — **already in schema**; ensure UI uses it
- [ ] `zero_clause_warning: bool` — computed: implemented/partial + count==0
- [ ] Optional: `prose_rule_set_id` — when `domain_modules` references `prose_rules/`

---

## Phase 3 — Frontend: Coverage summary + registry table (medium)

**Files:** `RuleDatabaseSection.tsx`, new `RuleCoverageSummaryPanel.tsx`, `frontend/src/lib/api/sut.ts`, `frontend/src/messages/{tr,en}/sections.ts`

### 3.1 `CoverageSummaryPanel` (top of tab)

Two-column stat grid + compact table:

**Sol — Hüküm pipeline’ı (clauses)**

| Metrik | TR label |
|--------|----------|
| `total_extracted` | Çıkarılan hükümler |
| `algorithmic_gaps` / `%` | Algoritmik boşluk |
| Status chips | Uygulandı / Kısmi / Eksik / … |

**Sağ — Registry (algorithms)**

| Metrik | TR label |
|--------|----------|
| `total_rules` | Kayıtlı kural ailesi |
| Implemented / partial / missing counts | Durum dağılımı |
| `zero_clause_matches.length` | Eşleşmesiz implemente kurallar (uyarı) |

When `!artifacts_available`: show existing yellow banner + “Özet kullanılamaz — `python scripts/sut/build_sut_coverage.py`”.

### 3.2 `FactCheckPanel` — demote and relabel

- Move **below** coverage summary
- Collapsible by default (`<details>` or disclosure)
- Title: **“Algoritma denetimi (Haziran 2026 — arşiv)”**
- Subtitle clarifies: frozen snapshot, not live clause counts

### 3.3 Registry status table (optional inline)

Sortable mini-table under summary:

| Kural | Kategori | Durum | Hüküm sayısı | Modül |
|-------|----------|-------|--------------|-------|

Could reuse filtered `rules` from catalog instead of duplicate API — **client-side from existing `GET /api/rules`**.

Highlight rows in `zero_clause_matches`.

### 3.4 Rule list enhancements

- Warning icon when `zero_clause_warning`
- Tooltip: “Registry uygulandı olarak işaretli ancak eşleşen SUT hükmü yok”
- Keep existing `matched_clause_count` suffix

### 3.5 Types + API client

Extend `RuleCatalogResponse` in `sut.ts` with `coverage_summary` types matching backend schemas.

---

## Phase 4 — Frontend: Section browser + prose inventory panels (medium)

- Sub-tab or toggle: **“Bölümlere göre”** vs **“Kurallara göre”**
- Section table: § id, başlık, hüküm sayısı, en kötü durum, gap sayısı
- Row click → filter rule list to rules whose `sources.sut_sections` contains that § (client filter) OR deep-link to first matching rule
- Prose inventory panel: list of prose JSON engines with rule counts and effective dates

These are dense expert surfaces; no consumer simplification needed.

---

## Phase 5 — Data pipeline & CI (small)

### 5.1 Document build order in plan README snippet

```bash
python scripts/sut/extract_sut_prose.py   # → sut_clauses.parquet
python scripts/sut/build_sut_coverage.py  # → coverage parquets
```

### 5.2 CI / dev ergonomics

- [ ] Add parquet presence check to `tests/unit/api/test_sut_rules_api.py` (already partial)
- [ ] Document in `AGENTS.md` or `docs/core-system/` that Rule Database full UI requires coverage parquets
- [ ] Optional: CI job builds coverage from committed `sut_clauses.parquet` if clause file tracked

### 5.3 Align `rebuild_baseline_metrics.py`

Refactor to call `rules_catalog.coverage_summary()` once implemented — single source of truth for archive JSON and API.

---

## Phase 6 — i18n (small)

### 6.1 Page context — removed

Chat context enrichment for rule-database tab is **not needed**. Experts using the Rule Database do not require an AI headline summary of coverage numbers.

### 6.2 i18n keys

Add under `sections.ruleDatabase.coverage.*`:

- `title`, `clausesTitle`, `registryTitle`, `algorithmicGaps`, `zeroClauseWarning`, `buildHint`, status labels mirroring backend enums

### 6.3 Deontic / category — already done

Keep `useLocalizedRule` + `useDeonticLabel`; no change required.

---

## Phase 7 — Verification

### Manual smoke

1. **With parquets:** coverage panel shows non-zero clause total; registry counts sum to ~28; fact-check collapsed below
2. **Without parquets:** no coverage numbers; rule list still works; no fake fact-check confusion
3. **TR locale:** all new strings Turkish
4. Select `copay_exemption_ek1a` → clause drill-down unchanged

### Automated

```bash
.venv/bin/pytest tests/unit/domain/sut/test_rules_catalog.py tests/unit/api/test_sut_rules_api.py -q
cd frontend && npm test -- RuleDatabase
```

---

## Implementation order

| Step | Phase | Delivers |
|------|-------|----------|
| 1 | 1.1–1.4 | `coverage_summary` API |
| 2 | 3.1–3.2, 3.4–3.5 | Coverage panel + fact-check demotion + zero-clause warnings |
| 3 | 5.3 | baseline_metrics uses same function |
| 4 | 2.1, 4 | Section browser panel |
| 5 | 2.2, 4 | Prose inventory panel |
| 6 | 6.2 | i18n polish |

---

## Risks & mitigations

| Risk | Mitigation |
|------|------------|
| Parquets not in repo / dev env | Honest `artifacts_available`; build hint in UI |
| Large API payload | Keep summary aggregated; sections paginated |
| User confuses fact-check vs coverage | Separate panels + TR copy |
| Stale parquet vs live code | Show `meta.generated_at` / file mtime |
| Duplicating `baseline_metrics.json` | Derive live; archive script calls same code |

---

## Review (fill after implementation)

- [ ] Phase 1 API merged
- [ ] Coverage panel live in TR
- [ ] Fact-check relabeled
- [ ] Tests green
- [ ] Safa sign-off on optional Phase 2 section browser
