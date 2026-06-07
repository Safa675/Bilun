# Plan: Relocate `reports/sut-fact-check` and root `evidence/`

**Status:** Approved — ready to execute  
**Created:** 2026-06-07  
**Goal:** One canonical layout — **docs** for human reference, **plans** for intent, **data/gazette** for pipeline artifacts — with no third bucket at repo root.

---

## Problem

Two orphan directories sit outside `docs/` and `plans/`:

| Current path | Role today | Wrong because |
|--------------|------------|---------------|
| `reports/sut-fact-check/` | 28 algorithm audit reports, MASTER rollup, FIX_BACKLOG, baseline JSON | Deliverables are **reference documentation**, not runtime reports |
| `evidence/` (repo root) | L1.4 / L4.4 prose corpus exports, encode manifests, coverage parquets | **Pipeline data** read by scripts and `coverage_scope.py`; not docs |

Additionally, audit clause CSVs live under `reports/sut-fact-check/evidence/clauses/` while some algorithm markdown cites `evidence/clauses/section_*.csv` (path drift — files only exist under `reports/...`).

---

## Target layout

```
docs/core-system/fact-check/
├── README.md                         ← index + “audit program closed” banner
├── MASTER.md
├── FIX_BACKLOG.md                    ← historical; open P2 rows migrated to billing plans
├── baseline_metrics.json
├── algorithms/
│   ├── _TEMPLATE.md
│   └── {28 report files}.md
└── evidence/clauses/                 ← audit citation CSVs only (section_1_8_*, section_2_2_*)

docs/medula/medula_overlap_gaps.md    ← move from reports (already linked from medula docs)

docs/gazette/prose-encoding.md       ← move content from evidence/clauses/L1.4_REVIEW_INSTRUCTIONS.md

data/gazette/prose_manifests/        ← runtime + script manifests (JSON)
├── L1.4_material_bundling_encoded_manifest.json
├── L1.4_ek3_annex_header_clause_ids.json
├── L1.4_malzeme_general_header_clause_ids.json
└── L4.4_specialty_prose_encoded_manifest.json

data/gazette/prose_corpus/           ← regenerable Gate B exports (CSV + summaries)
├── L1.4_material_bundling_prose.csv
├── L1.4_material_bundling_prose_review_sample.csv
├── L1.4_material_bundling_gate_b_summary.json
├── L1.4_material_bundling_corpus_batch2.csv
├── L1.4_material_bundling_corpus_batch2_summary.json
├── L4.4_specialty_prose.csv
└── L4.4_specialty_prose_summary.json

data/gazette/                        ← canonical coverage parquets (merge + dedupe)
├── sut_clause_coverage.parquet      ← from evidence/coverage (newer, Jun 3)
├── sut_registry_coverage.parquet    ← from evidence/coverage
├── sut_coverage_by_section.parquet  ← keep newer copy
└── sut_coverage_by_rule.parquet     ← keep newer copy

tasks/archive/sut-fact-check-2026-06/
└── WORKSTREAMS.md                   ← execution log only

reports/README.md                    ← stub redirect (delete after 30 days or next release)
```

**Delete after migration:** `reports/sut-fact-check/`, `evidence/`, empty `reports/` if only stub remains.

---

## File mapping (complete)

### A — `reports/sut-fact-check/` → `docs/`

| From | To |
|------|-----|
| `reports/sut-fact-check/README.md` | Rewrite as `docs/core-system/fact-check/README.md` |
| `reports/sut-fact-check/MASTER.md` | `docs/core-system/fact-check/MASTER.md` |
| `reports/sut-fact-check/FIX_BACKLOG.md` | `docs/core-system/fact-check/FIX_BACKLOG.md` |
| `reports/sut-fact-check/baseline_metrics.json` | `docs/core-system/fact-check/baseline_metrics.json` |
| `reports/sut-fact-check/algorithms/*` | `docs/core-system/fact-check/algorithms/*` |
| `reports/sut-fact-check/evidence/clauses/section_*.csv` | `docs/core-system/fact-check/evidence/clauses/section_*.csv` |
| `reports/sut-fact-check/medula_overlap_gaps.md` | `docs/medula/medula_overlap_gaps.md` |
| `reports/sut-fact-check/WORKSTREAMS.md` | `tasks/archive/sut-fact-check-2026-06/WORKSTREAMS.md` |
| `reports/sut-fact-check/evidence/diffs/` | **Drop** (empty `.gitkeep` only) |
| `reports/sut-fact-check/algorithms/PHASE3_VERDICT_TABLE.md` | `docs/core-system/fact-check/algorithms/PHASE3_VERDICT_TABLE.md` |

### B — root `evidence/` → `data/gazette/`

| From | To |
|------|-----|
| `evidence/clauses/L1.4_material_bundling_encoded_manifest.json` | `data/gazette/prose_manifests/` |
| `evidence/clauses/L1.4_ek3_annex_header_clause_ids.json` | `data/gazette/prose_manifests/` |
| `evidence/clauses/L1.4_malzeme_general_header_clause_ids.json` | `data/gazette/prose_manifests/` |
| `evidence/clauses/L4.4_specialty_prose_encoded_manifest.json` | `data/gazette/prose_manifests/` |
| `evidence/clauses/L1.4_material_bundling_prose.csv` | `data/gazette/prose_corpus/` |
| `evidence/clauses/L1.4_material_bundling_prose_review_sample.csv` | `data/gazette/prose_corpus/` |
| `evidence/clauses/L1.4_material_bundling_gate_b_summary.json` | `data/gazette/prose_corpus/` |
| `evidence/clauses/L1.4_material_bundling_corpus_batch2.csv` | `data/gazette/prose_corpus/` |
| `evidence/clauses/L1.4_material_bundling_corpus_batch2_summary.json` | `data/gazette/prose_corpus/` |
| `evidence/clauses/L4.4_specialty_prose.csv` | `data/gazette/prose_corpus/` |
| `evidence/clauses/L4.4_specialty_prose_summary.json` | `data/gazette/prose_corpus/` |
| `evidence/clauses/L1.4_REVIEW_INSTRUCTIONS.md` | `docs/gazette/prose-encoding.md` (update internal paths) |
| `evidence/coverage/*.parquet` | `data/gazette/` (overwrite older `sut_coverage_by_*` where newer) |

---

## Execution phases

### Phase 0 — Prep (no moves yet)

- [ ] Create target directories: `docs/core-system/fact-check/{algorithms,evidence/clauses}`, `docs/gazette/`, `data/gazette/{prose_manifests,prose_corpus}`, `tasks/archive/sut-fact-check-2026-06/`
- [ ] Run `rg 'reports/sut-fact-check|evidence/clauses|evidence/coverage' -l` and save file list as baseline
- [ ] Confirm `evidence/coverage/` parquets are newer than `data/gazette/sut_coverage_by_*.parquet` (Jun 3 vs Jun 2 — use evidence copies)

### Phase 1 — Move pipeline data (`evidence/` → `data/gazette/`)

**Do this first** — only 1 runtime Python import (`coverage_scope.py`).

- [ ] `git mv` manifests → `data/gazette/prose_manifests/`
- [ ] `git mv` corpus CSVs + summaries → `data/gazette/prose_corpus/`
- [ ] `git mv` coverage parquets → `data/gazette/` (add `sut_clause_coverage.parquet`, `sut_registry_coverage.parquet` if missing)
- [ ] Update **runtime** path:
  - [ ] `src/bilun/domain/materials/coverage_scope.py` → `_MANIFEST` under `data/gazette/prose_manifests/`
- [ ] Update **scripts** defaults (8 files):
  - [ ] `scripts/sut/export_material_bundling_clauses.py`
  - [ ] `scripts/sut/export_material_bundling_corpus_batch2.py`
  - [ ] `scripts/sut/export_specialty_prose_corpus.py`
  - [ ] `scripts/sut/merge_material_bundling_prose.py`
  - [ ] `scripts/sut/merge_specialty_materials_prose.py`
  - [ ] `scripts/sut/prose/material_bundling_ek3_list_batch_rules.py`
  - [ ] `scripts/sut/prose/material_bundling_malzeme_general_batch_rules.py`
  - [ ] `scripts/sut/rebuild_baseline_metrics.py` — coverage dir → `data/gazette/`, manifest/summary → `prose_manifests/` / `prose_corpus/`
- [ ] Move `L1.4_REVIEW_INSTRUCTIONS.md` → `docs/gazette/prose-encoding.md`; fix artifact paths inside
- [ ] Remove empty `evidence/`

### Phase 2 — Move fact-check docs (`reports/` → `docs/`)

- [ ] `git mv` reports tree per mapping table A (except WORKSTREAMS → archive)
- [ ] Rewrite `docs/core-system/fact-check/README.md`:
  - Program status: audit complete 2026-06; fix waves mostly done
  - Link to `plans/billing/algorithm-sut-fact-check-plan.md`
  - Clarify two evidence types: `docs/.../evidence/clauses/` (audit) vs `data/gazette/prose_corpus/` (encoding)
- [ ] Add banner to `MASTER.md` top: canonical path + “open tail owned by billing plans”
- [ ] Fix **internal** markdown paths in moved reports (~8 files cite old `reports/sut-fact-check/evidence/` or bare `evidence/clauses/section_*.csv`):
  - [ ] `L2.1`, `L2.2`, `P0.1`, `P0.2`, `L1.1` (+ any others from `rg` after move)
  - [ ] Normalize audit CSV refs to `docs/core-system/fact-check/evidence/clauses/section_*.csv`

### Phase 3 — Update external references

**Plans (6 files):**

- [ ] `plans/billing/algorithm-sut-fact-check-plan.md` — all deliverable paths
- [ ] `plans/billing/material-bundling-prose-p2-plan.md` — fact-check + corpus paths
- [ ] `plans/billing/specialty-materials-prose-l4.4-plan.md`
- [ ] `plans/billing/sgk-uplift-roadmap.md`
- [ ] `plans/billing/strategy-algorithm-sut-fix.md`
- [ ] `plans/docs/docs-fact-check-fix.md` — add cross-link to new fact-check location

**Docs (2 files):**

- [ ] `docs/medula/medula_bilun_overlap.md` — link to `docs/medula/medula_overlap_gaps.md`
- [ ] `docs/medula/material_bundling_medula_boundary.md`

**Optional constants** (if any hard-coded in domain):

- [ ] `coverage_scope.py` `P2_PLAN_PATH`, `MEDULA_BOUNDARY_DOC` — verify still valid

### Phase 4 — Stub and archive cleanup

- [ ] Add `reports/README.md`:

  ```markdown
  # Moved

  SUT fact-check reports → `docs/core-system/fact-check/`
  Prose pipeline evidence → `data/gazette/prose_manifests/` and `prose_corpus/`
  ```

- [ ] Migrate open `FIX_BACKLOG.md` P2 rows into owning plans; mark migrated in FIX_BACKLOG
- [ ] Delete `reports/sut-fact-check/` if anything left after `git mv`
- [ ] Delete `reports/README.md` in a follow-up once links are swept (or keep one release)

### Phase 5 — Verification

- [ ] `rg 'reports/sut-fact-check' .` → zero hits (except stub README if kept)
- [ ] `rg 'evidence/clauses' .` → zero hits pointing at old root path
- [ ] `rg 'evidence/coverage' .` → zero hits
- [ ] `python scripts/sut/rebuild_baseline_metrics.py` succeeds; output at `docs/core-system/fact-check/baseline_metrics.json`
- [ ] `pytest tests/unit/domain/prose_rules/test_material_bundling_golden.py -q` (manifest path)
- [ ] `pytest tests/unit/domain/materials/ -q` if coverage_scope tested
- [ ] Spot-open `docs/core-system/fact-check/algorithms/L2.1_*.md` — evidence CSV link resolves

---

## Path constants convention (post-move)

Prefer repo-root-relative paths in docs; in code use either:

```python
_GAZETTE = Path(__file__).resolve().parents[N] / "data" / "gazette"
_MANIFEST = _GAZETTE / "prose_manifests" / "L1.4_material_bundling_encoded_manifest.json"
```

or a single helper in `src/bilun/domain/constants.py` (e.g. `_PROSE_MANIFESTS_DIR`) — **only if** more than two call sites; otherwise inline path update is enough.

---

## Out of scope

- Re-running all 28 fact-check gates or changing verdicts
- L1.4 / L4.4 corpus expansion (stays in billing plans)
- Syncing `algorithms_reference.md` from fact-check (separate `docs-fact-check-fix.md` task)
- SGK Phase 3 uplift addendum to L3.6 (do after relocation or in same PR if trivial)
- Git history rewrite / `git filter-repo`

---

## Definition of done

1. No `reports/sut-fact-check/` tree (or stub only with redirect)
2. No root `evidence/` tree
3. All fact-check markdown under `docs/core-system/fact-check/`
4. All prose pipeline artifacts under `data/gazette/prose_{manifests,corpus}/`
5. Coverage parquets canonical in `data/gazette/` only
6. `coverage_scope.py` + 8 scripts use new paths
7. `rg` clean for old paths; targeted tests green

---

## Suggested PR split

| PR | Contents | Risk |
|----|----------|------|
| **PR1** | Phase 1 only (`evidence/` → `data/gazette/`) | Low — small code surface |
| **PR2** | Phase 2–4 (`reports/` → `docs/` + link sweep) | Medium — many markdown links |
| **PR3** | Optional: delete `reports/README.md` stub | Trivial |

Single PR is also fine if you prefer one atomic move.

---

## Review

_(Fill after execution.)_
