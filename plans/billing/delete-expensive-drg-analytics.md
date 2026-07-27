# Delete expensive DRG analytics (`patient_outcome_expensive` + DRGPanel)

**Branch (when implementing):** `chore/delete-expensive-drg` from `origin/main` via worktree — **no `git pull`** (local deletions must not be restored)  
**Status:** Plan only — do not implement until approved.

---

## Why

1. Cached `patient_outcome_expensive` rows are empty stubs (`missing_exact_inputs` / all zeros) because the build path never passes `sut_claim_dataset` into expensive compute.
2. Even when live-recomputed, the surface is **episode cost comparison UI** (`DRGPanel`) — not revenue-recovery. Billing already covers DRG product value via `drg_uplift`, `drg_package_adequacy`, and `drg_unbundling`.
3. Keeping a half-dead cache table + API fields + chatbot tool adds maintenance cost for no product payoff.

**Decision:** Remove the entire expensive-DRG pipeline end-to-end. Do **not** “fix the cache bug” and keep the panel.

---

## Goal

Done = no `patient_outcome_expensive` write/read path, no `DRGPanel` / `drg_summary` on patient outcome, no `get_drg_episode_cost` chatbot tool, no `domain.analytics.drg*` modules; unit + frontend tests green; billing DRG motors untouched.

---

## In scope

### Delete files

| Path | Role |
|------|------|
| `src/bilun/cache/build_expensive.py` | Backfill CLI + table writes |
| `src/bilun/cache/expensive_compute.py` | Sole production caller of `compute_drg_summary` |
| `src/bilun/domain/analytics/drg.py` | Episode / summary compute |
| `src/bilun/domain/analytics/drg_payload.py` | Serialize / normalize cached payload |
| `tests/unit/cache/test_build_expensive.py` | |
| `tests/unit/cache/test_expensive_compute.py` | |
| `tests/unit/domain/analytics/test_drg_claim_exact.py` | |
| `tests/unit/domain/analytics/test_drg_payload.py` | |

### Edit — cache / DB

- `cache/builder.py` — drop `--skip-expensive-backfill` / `--expensive-only` / `--expensive-timeout-ms`, expensive branch, row_counts `patient_expensive_*`
- `cache/context.py` — drop `_assemble_sut_expensive_context` / `load_sut_expensive_context`
- `cache/README.md` — remove expensive/DRG backfill docs
- `db/schema.py` — remove `CREATE TABLE … patient_outcome_expensive`
- `db/_internal.py` — remove table from `_BUILD_DATA_TABLES`
- `db/patient_meta.py` + `db/__init__.py` — remove `read_patient_outcome_expensive`
- Optional one-shot: `DROP TABLE IF EXISTS patient_outcome_expensive` note in PR (existing DuckDB files keep orphan table until manually dropped; new builds never create it)

### Edit — API / chatbot / frontend

- `api/routes/patients.py` — drop `include_expensive`, merge of `drg_summary` / `consistency_warnings` / `expensive_analytics`
- `api/schemas.py` — drop `ExpensiveAnalyticsState`, `DRGEpisodeResponse`, `DRGSummaryResponse`, related outcome fields
- `api/routes/chat.py` — drop DRG keys from outcome summarizer
- `chatbot/tools.py` — remove `get_drg_episode_cost` + executor
- `chatbot/context.py` — remove DRG / expensive formatting in patient context
- `frontend/.../PatientSection.tsx` — remove `DRGPanel` + noDrgSummary UI
- `frontend/.../SutPatientWorkspace.tsx` — stop rendering `DRGPanel` / expensive-only warnings
- `frontend/src/lib/domains/sut.ts` — drop DRG types / outcome fields
- `frontend/src/messages/{en,tr}/patient.ts` — drop `drgPanel` / `noDrgSummary` (and trim DRG-only `outcomeSummary` copy)

### Edit — package docs / re-exports

- `domain/analytics/__init__.py` — keep `materials` only
- `domain/analytics/README.md`, `domain/__init__.py` — remove DRG examples

### Edit — tests that reference the surface

- `tests/unit/chatbot/test_tools.py`, `test_context_formatters.py`
- `tests/unit/api/test_sut_schema_exactness.py`, `test_sut_chat.py`, `test_sut_cache_concurrency.py`
- `tests/unit/domain/test_dalga1_bugfixes.py` (B-C3 / `domain.analytics.drg` imports)
- Frontend: `PatientSection.test.tsx`, `SutPatientWorkspace.test.tsx`, `PatientFinancialSummary.test.tsx` as needed

---

## Out of scope (KEEP)

These share “DRG” in the name but are **billing / optimization product**, not this pipeline:

- `domain/billing/claim_drg_uplift.py` + billing API surfaces
- `domain/prose_rules/drg_package_adequacy.py` (+ claim wrapper / gazette)
- `domain/prose_rules/drg_unbundling.py` + `domain/optimization/unbundling.py` + patient unbundling KPI UI
- `ek2c_prose_drg_locked` helpers
- `domain/analytics/materials.py` + `price_material_lines`
- Temporal EK-2C pricing helpers used elsewhere
- Historical plan/audit markdown that *mentions* expensive DRG (optional hygiene later)
- User’s unrelated local dirty-tree deletions; no `git pull`

---

## Subtasks (implementation order)

1. [ ] Confirm this plan (product cut OK; API contract break OK)
2. [ ] Branch from `origin/main` via worktree (no pull)
3. [ ] Delete domain + cache expensive modules + their dedicated unit tests
4. [ ] Strip builder / context / schema / patient_meta / exports
5. [ ] Strip API schemas + patient outcome route + chat summarizer
6. [ ] Strip chatbot tool + context formatter
7. [ ] Strip frontend panel, types, i18n keys
8. [ ] Fix remaining tests that mock `drg_summary` / `include_expensive` / `DRGPanel`
9. [ ] Verify: targeted pytest + frontend vitest for touched suites
10. [ ] Commit only deletion files; open PR → `main`

---

## Definition of done

- `rg patient_outcome_expensive|compute_drg_summary|DRGPanel|get_drg_episode_cost|include_expensive` → no product hits (docs/plans excepted)
- `rg drg_uplift|drg_package_adequacy|drg_unbundling` → still present and wired
- Cache builder no longer mentions expensive flags
- Patient outcome response has no `drg_summary` / `expensive_analytics`
- CI-relevant unit + frontend tests for touched areas pass

---

## Risks

| Risk | Mitigation |
|------|------------|
| Breaking change for external `/outcome` consumers | Document in PR; Bilun frontend is the only known client |
| Orphan DuckDB table on existing caches | Stop R/W; optional `DROP` in ops note; schema omit for new DBs |
| Accidental deletion of billing DRG motors | Explicit KEEP list; PR review checklist |
| Dirty local tree pollutes PR | Worktree from `origin/main`; commit only listed paths |

---

## Dependency (delete along arrows)

```
builder (--expensive*) / build_expensive
  → load_sut_expensive_context
  → expensive_compute
      → domain.analytics.drg + drg_payload
  → DuckDB patient_outcome_expensive
       → GET outcome?include_expensive
            → Frontend DRGPanel
            → chatbot get_drg_episode_cost
```
