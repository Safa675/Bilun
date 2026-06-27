# R5 Epic B — §3.1–3.2 Material bundling (long-tail Gate B)

**Epic ID:** `R5-B`  
**Orchestration:** `plans/billing/r5-gate-b-parallel-index.md`  
**Extends:** `plans/billing/material-bundling-prose-p2-plan.md` (Phase 1–8 **complete**, 59 JSON rules, 0 deferred)  
**Registry:** `material_bundling_prose` — `implemented` (clause coverage **partial**)  
**Runtime:** `src/bilun/domain/prose_rules/material_bundling.py`  
**Artifact:** `data/gazette/prose_rules/material_bundling_prose.json`

---

## Goal

Encode the **remaining §3.1–3.2 long tail** from Phase 8 corpus batch2 backlog (204-row export themes already traced in manifest headers) into executable JSON rules — without duplicating EK-3B-1/2 list engines or opening §3.3 specialty pricing (separate track).

**Done looks like:** §3.1 motor-bound gap **~35 → ≤10**; manifest `gate_b_deferred_clause_ids` stays empty or explicitly justified.

---

## Baseline

| Metric | Value |
|--------|------:|
| §3.1 clauses (`material_bundling_prose`) | 115 |
| Encoded | 80 |
| Motor-bound gap | ~35 |
| JSON rules | 59 |
| Corpus batch2 export | 204 rows (`L1.4_material_bundling_corpus_batch2.csv`) |
| Gate B deferred | **0** |

**§3.3 note:** `specialty_materials_prose` (29/32 encoded) is **Phase B** of this epic or a small follow-up epic — same agent skillset, different JSON file. Not blocking §3.1 completion.

---

## Out of scope

- Full §3.3 (1.111 clauses) — track `specialty_materials_prose` separately
- MEDULA submission blocking replacement
- Care setting / facility tier until claim fields exist (P2 plan deferred item)
- Re-classifying §3.3 rows as `material_bundling_prose`

---

## Phases

### Phase B0 — Gap triage (0.5 day)

- [ ] Filter coverage: §3.1–3.2, `material_bundling_prose`, `has_rule_encoding=false`, not `non_algorithmic`
- [ ] Join with `L1.4_material_bundling_corpus_batch2.csv` — map each gap row to theme (`malzeme_general`, `ek3_list`, `faturalandirma`, …)
- [ ] Mark rows: **encode now** vs **manifest header only** vs **duplicate of EK-3B-1/2**

**Deliverable:** `data/gazette/prose_corpus/L1.4_material_bundling_r5_gap_triage.csv`

### Phase B1 — Theme batches (1–2 weeks)

Process highest-signal themes first (deontic `MUST_NOT_BILL` / `NO_PAY`):

| Batch | Theme | Gap rows (est.) | Target new rules |
|-------|-------|----------------:|-----------------:|
| B1a | Remaining `malzeme_general` | ~10 | 3–5 |
| B1b | Remaining `ek3_list` / annex cross-refs | ~8 | 2–4 |
| B1c | Procurement / ihale edge fıkra | ~5 | 2–3 |
| B1d | KDV / pricing cross-refs not in `material_kdv.py` | ~5 | 2–3 |

Per batch (same pattern as P2 Phase 8):

- [ ] Add rules in `material_bundling_*_batch_rules.py`
- [ ] `scripts/sut/merge_material_bundling_prose.py`
- [ ] Update `L1.4_material_bundling_encoded_manifest.json` `gate_b_sources`
- [ ] Golden row in `golden/material_bundling_gate_b.json`
- [ ] `test_material_bundling_golden.py`

### Phase B2 — §3.3 specialty tail (optional, 1 week)

If same agent continues:

- [ ] 3 unencoded `specialty_materials_prose` clauses → `specialty_materials_prose.json`
- [ ] Manifest: `L4.4_specialty_materials_encoded_manifest.json` (create if missing)
- [ ] Do **not** merge into `material_bundling_prose.json`

### Phase B3 — Integration check

- [ ] `validate_claim()` third pass still ordered correctly
- [ ] `precheck_materials_from_claims()` — prose vs EK-3B-1 separation unchanged
- [ ] MEDULA boundary doc: still **ADDITIVE**
- [ ] Coverage regen + graph regen (orchestrator)

---

## Parallel agent contract

| Owns | Does not touch |
|------|----------------|
| `material_bundling_prose.json`, `L1.4_*`, `material_bundling_*batch*`, `material_bundling.py`, `material_kdv.py` | `drug_indication_prose.json`, `payment_method_2_2.json`, `copay_general_1_8.json` |
| Optional: `specialty_materials_prose.json` in Phase B2 only | `classify.py` §4.2 routing |

---

## Metrics targets

| Metric | Now | Target |
|--------|----:|-------:|
| §3.1 encoded clauses | 80 | **≥105** |
| JSON rules (material_bundling) | 59 | **≥70** |
| Motor-bound gap §3.1 | ~35 | **≤10** |
| gate_b_deferred | 0 | **0** |

---

## Definition of done

1. Every remaining §3.1–3.2 motor-bound row is either encoded or documented as duplicate-of-EK-3 in triage CSV.
2. ≥10 net new JSON rules with golden tests.
3. Manifest `gate_b_sources_encoded` covers all new clause IDs.
4. L1.4 fact-check stays **PARTIAL** with updated clause encode fraction (not false COMPLIANT).

---

## Verification

```bash
pytest tests/unit/domain/prose_rules/test_material_bundling_golden.py \
  tests/unit/domain/materials/test_coverage_scope.py -q
python scripts/sut/merge_material_bundling_prose.py
python scripts/sut/build_sut_coverage.py
```
