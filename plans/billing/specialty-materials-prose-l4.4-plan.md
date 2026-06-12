# L4.4 Plan: §3.3 Specialty Annex Prose Engine

**Status:** L4.4 v1 complete — **84/84** corpus traced, **49** rules; Phase 2 integration shipped (2026-06-11)  
**Fact-check:** `docs/core-system/fact-check/algorithms/L4.4_specialty_materials_ek3.md`  
**Registry:** `specialty_materials` (catalog **implemented**); `specialty_materials_prose` (**implemented**, partial corpus)  
**Sibling:** L1.4 `material_bundling_prose` — §3.1–3.2 only (**59 rules**, Phase 8 complete)

## Goal

Encode executable §3.3 specialty material rules (branch annex pricing, non-payment, regulatory conditions) that complement — not duplicate — EK-3 specialty parquets (`get_all_specialty_materials`, ~4,407 rows) and L1.4 bundling prose.

## Boundary vs L1.4

| | L1.4 `material_bundling_prose` | L4.4 `specialty_materials_prose` |
|--|-------------------------------|----------------------------------|
| SUT sections | §3.1, §3.2 | §3.3 |
| Primary deontic | `MUST_NOT_BILL`, separate billing | `NO_PAY`, ceilings, annex limits |
| Catalog | EK-3B-1/2, EK-3/C, allow-list scan | EK-3A–3T specialty parquets |
| Validator pass | `prose_bundling_violations` | **New:** `specialty_prose_violations` (additive) |
| Classifier | `3.` fallback → bundling | `3.3` → `specialty_materials` (```119:119:scripts/sut/prose/classify.py```) |

**Do not** append §3.3 rules to `material_bundling_prose.json`.

## Clause inventory

| Metric | Count |
|--------|------:|
| Total §3.3 clauses | 1,111 |
| `deontic_modality` set | 108 |
| `NO_PAY` | 83 |
| L4.4 export subset (`NO_PAY` ∪ `faturalandır` text) | **84** |
| Classified `specialty_materials` (registry) | 1,105 |
| Rows in `material_bundling_prose.json` | **0** |

Largest encode clusters in the 84-row subset: **3.3.3** (33), **3.3.4** (29), **3.3.1** (7).

## Phases

### Phase 0 — Corpus export

- [x] Export `evidence/clauses/L4.4_specialty_prose.csv` (84-row keyword subset)
- [x] Summary JSON + theme by `section_id` branch (`3.3.1` … `3.3.9`)
- [ ] Human review sample (≥5 rows) + `L4.4_REVIEW_INSTRUCTIONS.md`

### Phase 1 — Artifact + schema (pilot §3.3.1)

- [x] `data/gazette/prose_rules/specialty_materials_prose.schema.json`
- [x] `specialty_materials_prose.json` — **8 rules** from §3.3.1 wound/dressing (4 deontic clauses)
- [x] `src/bilun/domain/prose_rules/specialty_materials.py` evaluator
- [x] Registry `specialty_materials_prose` → `partial`
- [x] Manifest `data/gazette/prose_manifests/L4.4_specialty_prose_encoded_manifest.json`

### Phase 2 — Domain integration

- [x] `validate_claim()` fourth pass (after material bundling) — additive hits only
- [x] `claim_materials.precheck` — `specialty_prose_violations` + `specialty_coverage_scope`
- [x] Claim-line flags for branch-specific conditions (synthetic + loader + parquet export)
- [x] Golden tests + coverage matrix row + UI surfacing (EN/TR)
- [ ] Code-first price lookup (L4.4-3) — deferred to Phase 4

### Phase 3 — Thematic batches (mirror L1.4 Phase 8)

| Batch | Section focus | Export rows | Target rules |
|-------|---------------|------------:|-------------:|
| A | 3.3.1 wound/dressing | 2 (strict) | 8 ✓ |
| B | vision_optik theme | 16 (strict §3.3.3) + 17 hearing/implant | 13 ✓ (22 rules total) |
| C | 3.3.4 orthobiologic/greft | 29 | 12 ✓ (34 rules total) |
| D | `REGULATORY_ACTION` (21) | — | 6–10 |

Long tail (~1,000 non-deontic fikra): manifest headers only, not 1:1 rules.

### Phase 4 — Catalog alignment

- [ ] Code-first `lookup_ek3_list_price_try` / `estimate_material_costs` when `material_code` present
- [ ] Expand registry `annex_refs` to full `_EK3_SPECIALTY_CATALOGS`
- [ ] Temporal effective-date filter (optional P3)

## Definition of done (L4.4 prose v1)

1. `specialty_materials_prose.json` exists; registry prose facet not `missing`.
2. §3.3.1 pilot rules tested; 84-row corpus has `in_l44_encode_manifest` for encoded IDs.
3. UI/API scope distinguishes **bundling** vs **specialty annex** prose (additive MEDULA).
4. Fact-check L4.4 verdict moves from PARTIAL (catalog-only) to PARTIAL (catalog + prose pilot).

## Out of scope

- Replacing EK-3 parquet price tables with prose
- §3.1–3.2 bundling (L1.4)
- MEDULA submission blocking
