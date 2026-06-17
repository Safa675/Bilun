# Plan: §4.2.14.C Drug Indication Prose Expansion

**Status:** Phase 0 + Phase 1 + Sprint 1 complete (131 rules, 2026-06-17)  
**Fact-check:** L4.2 (drug indication) — expect **PARTIAL** until this plan completes  
**Registry:** `drug_indication_prose` — `coverage_status=partial`  
**Sibling:** Tier 3b matcher (`drug_indication.py`, `claim_drug_indication.py`)  
**Artifact:** `data/gazette/prose_rules/drug_indication_prose.json`

## Goal

Expand the Tier 3b pilot into a **§4.2.14.C-first corpus**: encode specialty/oncology/hematology drug endikasyon + sağlık kurulu raporu rules as executable JSON, matched at runtime against exact drug claim lines (INN + ICD-10 + report flag), without re-introducing the false “zero gap” state from Tier 3a (`non_algorithmic`).

## Current boundary (post Tier 3b)

| Layer | Coverage |
|-------|----------|
| §4.2 total clauses | 3,680 |
| §4.2.14.C clauses | **828** (22.5% of §4.2) |
| Primary classifier | `drug_indication_prose` for all §4.2 |
| Encoded JSON rules | **18** (all anchored `4.2.14.C`) |
| Clauses mentioning a pilot INN | 97 / 3,680 §4.2 (2.6%); **62 / 828** in 4.2.14.C (7.5%) |
| Runtime matcher | INN substring + ICD code/range + `drug_specialty_board_report_present` |
| Dashboard gap | 3,679 / 3,680 §4.2 clauses (`partial` → gap) |

**Tier 3b proved the pattern.** This plan scales the **corpus**, not the architecture.

## Clause inventory (4.2.14.C baseline)

| Metric | Count |
|--------|------:|
| Total clauses | 828 |
| Unique `text_tr` | 750 |
| Unique `section_id` (only `4.2.14.C`) | 1 |
| Text shape: numbered fıkra `(1)`, `1)` | 350 |
| Text shape: letter fıkra `a)`, `ç)` | 174 |
| Text shape: parenthesized amendment | 106 |
| Keyword: `rapor` | 236 |
| Keyword: `reçete` | 184 |
| Keyword: `onkoloji` | 151 |
| Keyword: `hematoloji` | 88 |
| Keyword: `endikasyon` (explicit) | 48 |
| Drug-leading segments (heuristic) | ~368 unique |
| Segments not matching Tier 3b pilot | **~357** |

High-frequency **unencoded** INNs (clause mention counts):

| INN | Clauses |
|-----|--------:|
| nivolumab | 21 |
| daratumumab | 13 |
| enzalutamid / sorafenib | 12 each |
| dasatinib / dabrafenib | 11 each |
| nilotinib / azasitidin / decitabin | 9 each |
| trastuzumab / kabazitaksel | 8 each |
| pembrolizumab | 7 |

## Encode tiers (complexity model)

Not every 4.2.14.C fıkra becomes a 1:1 JSON rule on day one. Use three tiers:

### Tier A — Encode now (Tier 3b pattern)

**Signal:** INN list + ICD-10 range/code + `report_required` + `report_specialties`.

Examples already shipped: bevacizumab, bortezomib, pembrolizumab (C34), fludarabin (C/D ranges).

**Matcher:** existing `evaluate_drug_indication_line()` — no code change required.

### Tier B — Encode with extended schema (Phase 2)

**Signal:** Tier A plus structured fields extractable from prose:

| Field | Example prose |
|-------|----------------|
| `report_duration_months` | “6 ay süreli sağlık kurulu raporu” |
| `prescriber_specialties` | “tıbbi onkoloji uzman hekimlerince reçete” |
| `inpatient_only` | “yatarak tedavide hastanelerce temin” |
| `icd10_codes` (exact) | “C34.1”, “D46.9” |
| `excluded_icd10_ranges` | non-oncology misuse |

**Matcher:** extend evaluator to check duration/specialty/inpatient when claim fields exist; otherwise emit `needs_report_verification` (partial exact).

### Tier C — Manifest-only / deferred

**Signal:** Multi-step clinical logic (ECOG, mutation panels, prior therapy lines, response assessment, MoH patient-specific approval).

Examples: “PD-L1 <%50 + platin bazlı 2 kür + EGFR/ALK/ROS negative”, “3. kür sonunda minör yanıt”.

**Action:** trace clause IDs in encode manifest with `encode_tier: C` and `defer_reason`; do **not** block Tier A/B batches.

## Phases

### Phase 0 — Corpus export + Gate B (1–2 days)

- [ ] Export 4.2.14.C candidates → `data/gazette/prose_corpus/L4.2_drug_indication_4.2.14.C.csv`
  - Columns: `clause_id`, `text_tr`, `deontic_modality`, `heuristic_inn`, `encode_tier` (A/B/C), `duplicate_of`, `pilot_rule_id`
- [ ] Script: `scripts/sut/prose/drug_indication_gate_b.py`
  - Dedup vs existing 18 pilot rules
  - Dedup vs EK-4/A catalog INN (`ek4a_drugs.parquet`) for crosswalk sanity
  - Flag clauses already covered by `copay_exemption_ek4d` / `drug_discount_prose` (out of scope)
- [ ] Human review sample: ≥10 Tier A rows + ≥5 Tier B rows → `docs/gazette/drug-indication-encoding.md`
- [ ] Update schema if Tier B fields added → `drug_indication_prose.schema.json`

**Target export size:** 828 rows in, ~120–180 **Tier A** encode candidates after dedup (not 828 rules).

### Phase 1 — Batch A: high-volume INN sweep (1 week)

Encode **40–60 Tier A rules** grouped by SUT fıkra blocks:

| Batch | Focus | Target rules | Priority INNs |
|-------|--------|-------------:|---------------|
| A1 | IO / targeted lung | 12–15 | nivolumab, pembrolizumab, atezolizumab, durvalumab, erlotinib (extend), gefitinib |
| A2 | Heme/onc injectables | 12–15 | daratumumab, azasitidin, decitabin, blinatumomab, ixazomib, venetoclax |
| A3 | TKI / small molecules | 12–15 | dasatinib, nilotinib, sorafenib, dabrafenib, enzalutamid, temsirolimus |
| A4 | Legacy 4.2.14.C(1)(2) tail | 8–10 | trastuzumab, kabazitaksel, remaining fıkra (1)/(2) list |

Per rule minimum JSON:

```json
{
  "rule_id": "4.2.14.C.(15).nivolumab_nsclc_first_line",
  "sut_section": "4.2.14.C",
  "drug_names": ["nivolumab"],
  "icd10_ranges": ["C34"],
  "report_required": true,
  "report_specialties": ["tıbbi onkoloji"],
  "message_tr": "…"
}
```

Deliverables:

- [ ] Merge into `drug_indication_prose.json` (total **~60–80 rules** after Phase 1)
- [ ] Encode manifest → `data/gazette/prose_manifests/L4.2_drug_indication_4.2.14.C_manifest.json`
- [ ] Golden file → `data/gazette/prose_rules/golden/drug_indication_4.2.14.C_batch_a.json`
- [ ] Unit tests: one positive + one negative per batch INN

### Phase 2 — Schema + matcher extensions (Tier B) (1 week)

- [x] Extend schema: `report_duration_months`, `prescriber_specialties`, `inpatient_only`, `gate_b_sources` (clause IDs)
- [x] Extend `DrugClaimLine` + synthetic ingest:
  - `drug_report_duration_months: int | None`
  - `drug_inpatient_supply: bool | None`
  - `prescriber_specialty: str | None` (optional Phase 2b)
- [x] Evaluator: Tier B checks when fields present; graceful `needs_report_verification` when missing
- [x] Encode **20–30 Tier B rules** where prose is still structurable (report duration + specialty prescription paths)
- [x] Synthetic demo **0019** — trastuzumab `report_duration_mismatch` (Tier B field ingest pin)

### Phase 3 — Domain integration + coverage honesty (3–4 days)

- [x] `drug_indication_coverage_scope()` — report `pilot_rule_count`, `section_4.2.14.C_rule_count`, `encode_tier_C_deferred_count`
- [x] Optional coverage.py enhancement (recommended):
  - Per-clause `has_rule_encoding` when `clause_id` appears in manifest `gate_b_sources`
  - Dashboard shows **engine partial** vs **clause encoded** separately (avoids “50% gap” confusion)
- [x] Rebuild: `scripts/sut/build_sut_coverage.py` + `scripts/sut/rebuild_baseline_metrics.py`
- [x] Fact-check L4.2 row update in `fact_check_audit.py` (supplemental SUT-4.2.14.C note; L4.2 remains EK-2C DRG)

### Phase 4 — Synthetic demos + billing UX (3–4 days)

One demo patient per batch (mirror Tier 3b `SENTETIK-HASTA-0014`):

| Patient | Scenario | Expected violation |
|---------|----------|-------------------|
| 0014 (existing) | bevacizumab + C34.9 + no report | `missing_board_report` |
| 0015 | nivolumab + J45.9 (wrong ICD) | `indication_mismatch` |
| 0016 | daratumumab + C90.x + report unknown | `needs_report_verification` |
| 0017 | pembrolizumab + C34.9 + report OK | no violation |
| 0019 | trastuzumab + 12mo report (expects 3mo) | `report_duration_mismatch` |
| 0020 | trabectedin + sarcoma ICD + report missing | `missing_board_report` |

- [x] `generators.py` demo flags + `exporters.py` column mapping
- [x] `validate_sut_synthetic_data.py` minimum coverage for new drug fields (+ Tier B demo pins)
- [x] API/billing report: surface `drug_indication.violations` in patient billing JSON + Rule Database UI section

### Phase 5 — 4.2.14.C tail + Tier C manifest (ongoing)

- [x] Sprint 1: encode remaining 28 Tier A + 11 Tier B pending manifest clauses → **131 rules**, **279 encoded** §4.2.14.C clause IDs, tier A/B pending **0**
- [x] Sprint 1 merge script: `scripts/sut/prose/merge_drug_indication_sprint1.py` + golden `drug_indication_4.2.14.C_sprint1.json`
- [x] Batch encode only when claim ingest adds supporting fields (EMR/report structured ingest) — deferred via Tier C manifest
- [x] Stop condition checker: `drug_indication_v1_stop_conditions()` (manifest + corpus met; INN ≥90% stretch goal documented as open)

## Dependencies

| Dependency | Owner | Notes |
|------------|-------|-------|
| `sut_clauses.parquet` quality | SUT extract pipeline | 4.2.14.C is one `section_id`, many fıkra rows |
| EK-4/A drug name crosswalk | curated parquet | Commercial name ↔ INN normalization |
| Claim ingest fields | synthetic + loader | Tier B needs report duration / inpatient flags |
| Classifier stability | `classify.py` | Keep §4.2 on `drug_indication_prose`; do **not** restore broad `4. → drug_ek4a` |
| ICD-10 on claim | existing | `primary_icd10` + `ClaimDiagnosis` rows |

## Testing strategy

| Layer | Tests |
|-------|-------|
| Rule loader | JSON schema validation, rule count, unique `rule_id` |
| Matcher | `test_drug_indication.py` — per-batch golden vectors |
| Claim wiring | `test_claim_drug_indication.py` — PatientClaimContext integration |
| Coverage | `test_sut_coverage.py` — registry `partial`, manifest file exists |
| Synthetic | demo patient scenario tags resolve to expected violation kinds |
| Regression | Full SUT unit suite (`test_sut_coverage`, billing blocks) |

## Metrics (how we measure progress)

Track after each batch:

| Metric | Baseline (Tier 3b) | Phase 1 target | 4.2.14.C v1 target |
|--------|-------------------:|---------------:|-------------------:|
| JSON rules (4.2.14.C) | 18 | 60–80 | **131** |
| §4.2.14.C clauses mentioning encoded INN | 62 (7.5%) | ~350 (40%) | ~500 (60%) |
| Tier A runtime violations on synthetic demos | 1 patient | 4 patients | 4+ |
| Tier C deferred (manifest only) | 0 traced | 400 traced | 750 traced |
| Global §4.2 dashboard gap | 3,679 | unchanged* | unchanged* |

\*Global gap stays high until registry flips to `implemented` **or** per-clause encoding coverage is wired. Prefer honesty metric: **`4.2.14.C encoded INN coverage %`**.

## Definition of done (4.2.14.C expansion v1)

1. `drug_indication_prose.json` contains **≥80** rules with `sut_section: 4.2.14.C`.
2. Encode manifest traces **100%** of 828 clause IDs (encoded or Tier C deferred).
3. Matcher passes golden tests for all Tier A rules and selected Tier B rules.
4. ≥4 synthetic demo patients with deterministic violation outcomes.
5. `drug_indication_coverage_scope()` exposes honest partial tier + 4.2.14.C progress counters.
6. Fact-check L4.2 documents **PARTIAL** with explicit 4.2.14.C coverage fraction (not falsely COMPLIANT).
7. Registry remains `partial` until Tier C fraction is explicitly accepted or per-clause coverage ships.

## Out of scope (this plan)

- Full §4.2 beyond 4.2.14.C (4.2.13.x, 4.2.16, 4.2.34 — separate batches after v1)
- §4.1 / §4.4 EK-4/A catalog logic (`drug_ek4a`, `drug_discount_prose` — already owned elsewhere)
- Guaranteeing SGK recovery amounts from indication hits (compliance review only)
- Full clinical pathway encoding (ECOG, mutation labs, line-of-therapy) without new claim/report ingest
- Promoting `drug_indication_prose` → `implemented` while global §4.2 gap would mislead

## Suggested execution order

```
Phase 0 (export) → Phase 1A (IO/lung INNs) → tests + demo 0015
               → Phase 1B (heme INNs)     → tests + demo 0016
               → Phase 1C (TKI tail)      → tests + demo 0017
               → Phase 2 (Tier B schema)  → matcher extend
               → Phase 3 (coverage/manifest/fact-check)
               → Phase 5 (Tier C manifest tail)
```

**First PR (recommended):** Phase 0 + Phase 1A (~15 rules: nivolumab/ipilimumab combo splits, atezolizumab, durvalumab, trastuzumab) — highest clause mention density, lowest clinical defer risk.

## References

- Tier 3b commit: `drug_indication_prose` pilot + `claim_drug_indication.py`
- Pattern precedent: `plans/billing/material-bundling-prose-p2-plan.md` (batch encode + manifest)
- Classifier: `scripts/sut/prose/classify.py` — `("4.2", "drug_indication_prose")`
- Schema: `data/gazette/prose_rules/drug_indication_prose.schema.json`
