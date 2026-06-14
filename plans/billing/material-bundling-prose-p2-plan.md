# P2 Plan: SUT §3.1–3.2 Material Bundling Prose Engine

**Status:** Phase 1–7 complete (tail done 2026-06-02); **0** Gate B deferred  
**Fact-check:** L1.4 — archived **PARTIAL** verdict; live in `fact_check_audit.py` / Rule Database  
**Registry:** `material_bundling_prose` — `coverage_status=implemented` (clause coverage still partial)

## Goal

Encode executable decision logic for SUT §3.1–3.2 material payment and non-separate-billing prose, integrated with `validate_claim()` and patient material pre-checks, without duplicating rules already covered by EK-3B-1 (54 rows) or EK-3B-2 (13 rows).

## Current boundary (Sprint C)

| Layer | Coverage |
|-------|----------|
| EK-3B-1 list | `bundling_rules.py` — 54 consumable categories |
| EK-3B-2 list | `exclusion_rules.py` — 13 non-reimbursable rows |
| §3.1–3.2 prose | **PARTIAL** — 23 rules; KDV + EK-3 allow-list + §3.1.1(15) (C001635) wired |
| MIAT / pre-auth | §3.1.2 via EK-3C-1/2 catalogs (`claim_materials.py`) — not full §3.1 prose |

## Clause inventory (baseline)

| Prefix | Total clauses | Keyword subset (faturalandır / NO_PAY / MUST_NOT_BILL) |
|--------|---------------|--------------------------------------------------------|
| 3.1 | 301 | 46 |
| 3.2 | 46 | 8 |
| 3.3 | 1,111 | 84 (specialty pricing — track L4.4, not this engine) |

Classification: `scripts/sut/prose/classify.py` → `material_bundling_prose` when section `3.*` and deontic `MUST_NOT_BILL` / `NO_PAY`.

## Phases

### Phase 1 — Extraction (Gate B)

- [x] Export §3.1–3.2 candidates (48 rows: keyword ∪ NO_PAY/MUST_NOT_BILL) → `data/gazette/prose_corpus/L1.4_material_bundling_prose.csv`
- [x] Dedup vs EK-3B-1/2 (`duplicate_of`, `encode_priority` columns; `scripts/sut/prose/material_bundling_gate_b.py`)
- [x] Human review sample (5 rows ≥10% of 40 `p1_encode`) + `docs/gazette/prose-encoding.md`
- [x] Decision table schema → `data/gazette/prose_rules/material_bundling_prose.schema.json`

### Phase 2 — JSON artifact

- [x] Add `data/gazette/prose_rules/material_bundling_prose.json` (**23 rules** after Gate B + tail batch merge)
- [x] Registry `coverage_status` → `implemented` (clause coverage partial)
- [x] Encode manifest `data/gazette/prose_manifests/L1.4_material_bundling_encoded_manifest.json`
- [x] Rebuild coverage matrix (`scripts/sut/rebuild_baseline_metrics.py` → `baseline_metrics.json`)

### Phase 3 — Domain module

- [x] `material_bundling.py` — keywords, EK-3/C/EK-3, pairing, TİTUBB/ÜTS flags, rule priority
- [ ] care setting / facility tier (deferred — no claim fields yet)
- [x] Golden tests `data/gazette/prose_rules/golden/material_bundling_gate_b.json` + `test_material_bundling_golden.py`
- [x] Coverage matrix test: `material_bundling_prose` implemented + JSON on disk (`test_sut_coverage.py`)

### Phase 4 — Integration

- [x] `validate_claim()` — third pass after bundling + exclusion (partial prose)
- [x] `precheck_materials_from_claims()` — `prose_bundling_violations` separate from EK-3B-1 `is_bundled`
- [x] API `coverage_scope.prose_engine_status` → `implemented` (`prose_coverage_tier: partial`)
- [x] UI OUT_OF_SCOPE banners replaced with `bodyImplemented` coverage string; chatbot prompts updated

### Phase 5 — MEDULA / product

- [x] Update `medula_overlap_gaps.md` — L1.4 **ADDITIVE**; materials section resolved
- [x] Document additive vs MEDULA material blocking — `docs/medula/material_bundling_medula_boundary.md`
- [x] Sync fact-check rollup (`MASTER.md`, `L1.4` gap report, `L3.5`, `FIX_BACKLOG`, `algorithms_reference.md`)
- [x] API `coverage_scope`: `medula_overlap_classification`, savings note, deferred clause count
- [x] UI scope notice: MEDULA additive disclaimer (EN/TR)

### Phase 6 — Synthetic prose flag ingest (2026-06-03)

- [x] `generators.py` — seven prose flag columns on `malzeme_fatura_satirlari`
- [x] `exporters.py` — Turkish → English parquet mapping for `material_claim_lines.parquet`
- [x] `validate_sut_synthetic_data.py` — column + minimum coverage checks
- [x] Regenerated `data/synthetic/sut/`; tests in `test_synthetic_material_prose_flags.py`

### Phase 7 — L1.4 tail (2026-06-02)

- [x] `material_kdv.py` — C001630, C002692 (EK-3 list KDV ceiling)
- [x] `ek3_separate_billing_allowed_codes()` — C001823 catalog allow-list scan
- [x] Prose rule `3.1.1.(15).separate_billing_not_authorized` — C001635 (23rd rule)
- [x] `claim_materials.py` — `kdv_price_reviews` on material pre-check
- [x] `gate_b_deferred_clause_ids: []` in encode manifest; `baseline_metrics.json` rebuilt
- [x] Fact-check doc sync (MASTER, FIX_BACKLOG, L1.4 gap, MEDULA overlap, `algorithms_reference`)

## Dependencies

- Prose extraction quality for §3.1–3.2
- Claim ingest: material codes + procedure linkage (L1.1 P2)
- Gate C sign-off on extracted logic before production savings labels

## Definition of done

1. `material_bundling_prose.json` exists and registry is not `missing`.
2. Domain module has tests for all P1-priority decision rows (not in EK-3B-1).
3. `validate_claim()` invokes prose evaluator; fact-check L1.4 verdict moves from OUT_OF_SCOPE to COMPLIANT/PARTIAL as appropriate.
4. UI no longer shows §3.1–3.2 OUT_OF_SCOPE disclaimer (replaced by coverage version string).

### Phase 8 — Corpus batch 2 (2026-06-02)

- [x] Semantic splits: procurement 3-hospital price refs, MEDULA code-on-date, barcode claim flag
- [x] **25 rules** after merge; manifest clause re-homing (C002707 → EK-3/C rule)
- [x] Export `data/gazette/prose_corpus/L1.4_material_bundling_corpus_batch2.csv` (204-row backlog)
- [x] **Faturalandirma theme (6 clauses → 3 rules)** — 2026-06-02
- [x] **Garanti/onarım (9 → 4 rules) + ihale/DTS (2 → 2 rules)** — 2026-06-02
- [x] **ek3_list (99 → 9 rules + 76 annex headers in manifest)** — 2026-06-02
- [x] **malzeme_general (85 → 14 rules + 25 headers)** — 2026-06-02
- [x] **titubb_uts_barkod (3 → 2 rules)** — 2026-06-02; **59 rules**, **204/204** batch2 traced

## Out of scope for P2 plan

- Full §3.3 specialty annex prose (L4.4 pricing track)
- Replacing MEDULA submission blocking
- Guaranteeing SGK recovery amounts from prose hits (additive analytics only)
