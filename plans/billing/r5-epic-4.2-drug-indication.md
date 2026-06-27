# R5 Epic A — §4.2 Drug indication (Gate B tail)

**Epic ID:** `R5-A`  
**Orchestration:** `plans/billing/r5-gate-b-parallel-index.md`  
**Extends:** `plans/billing/drug-indication-4.2.14.C-expansion-plan.md` (Phase 0–5 largely **done**)  
**Registry:** `drug_indication_prose` — `partial`  
**Runtime:** `src/bilun/domain/prose_rules/drug_indication.py`, `claim_drug_indication.py`  
**Artifact:** `data/gazette/prose_rules/drug_indication_prose.json` (**164 rules** on disk, 2026-06)

---

## Goal

Close the **honest encode gap** for §4.2 beyond the completed 4.2.14.C Sprint 1: expand JSON rules and manifest `gate_b_sources` for remaining **actionable** §4.2 fıkra (Tier A/B), trace Tier C as deferred — without falsely marking the whole §4.2 motor as `implemented`.

**Done looks like:** More §4.2 clauses show **Encode edilmiş** in UI; global §4.2 gap stays labeled **partial** until registry policy explicitly changes.

---

## Baseline (coverage parquet, in-force)

| Metric | Value |
|--------|------:|
| §4.2 clauses (drug motors) | 2.369 |
| `has_rule_encoding=true` | 518 |
| Motor-bound gap | ~1.851 |
| Deontic, not encoded | 103 |
| JSON rules on disk | 164 |
| Existing manifest | `L4.2_drug_indication_4.2.14.C_manifest.json` (4.2.14.C focused) |

**Key insight:** Most encode work for 4.2.14.C is **shipped**. This epic is **tail + §4.2 outside 4.2.14.C** (4.2.13, 4.2.16, 4.2.33, etc.) — separate batches.

---

## Out of scope (this epic)

- `drug_ek4a` / EK-4/A catalog pricing (different motor)
- `drug_discount_prose`, `copay_exemption_ek4d` overlap rows
- Full clinical pathway (ECOG, mutation panels) without new claim ingest — **Tier C manifest only**
- Registry flip to `implemented` while ~1.800 §4.2 rows remain unencoded

---

## Phases

### Phase A0 — Inventory refresh (0.5 day)

- [x] Re-run Gate B export: `scripts/sut/prose/drug_indication_gate_b.py`
- [x] Diff manifest vs `has_rule_encoding` — list clause IDs in manifest but not in coverage
- [x] Segment unencoded §4.2 by `section_id` prefix (4.2.14.C vs rest)
- [ ] Update `drug_indication_coverage_scope()` counters in fact-check note (A1+)

**Deliverable:** CSV `data/gazette/prose_corpus/L4.2_drug_indication_gap_refresh.csv` with `encode_tier` column.

### Phase A1 — 4.2.14.C Tier C trace completion (1 week)

- [ ] Ensure **100%** of 828 × 4.2.14.C clause IDs appear in manifest as `encoded` or `tier_C_deferred` with `defer_reason`
- [ ] No new JSON unless Tier A/B row promoted from C after ingest field available
- [ ] Golden: manifest clause count matches corpus export

*(Mostly done per expansion plan Phase 5 — verify only.)*

### Phase A2 — §4.2.13 / 4.2.16 / 4.2.33 pilot batches (2–3 weeks)

Priority: high deontic + high claim-line mention density (grep synthetic drug lines + EK-4A INN crosswalk).

| Batch | Section focus | Target JSON rules | Gate B script |
|-------|---------------|------------------:|---------------|
| A2a | 4.2.13.x biosimilar / substitution | 10–15 | extend gate_b export filter |
| A2b | 4.2.16 reporting | 8–12 | same |
| A2c | 4.2.33 anti-VEGF (extend `anti_vegf_prose`) | 5–10 | link existing 21 rules |

Per batch:

- [ ] `*_batch_rules.py` → merge script → `drug_indication_prose.json`
- [ ] Append `gate_b_sources` per rule
- [ ] Golden file + 2 tests per rule (pos/neg)
- [ ] 1 synthetic demo patient per batch (optional)

### Phase A3 — Matcher / schema (only if Tier B fields needed)

- [ ] Extend schema only when A2 prose requires new fields (reuse Phase 2 fields from expansion plan)
- [ ] `evaluate_drug_indication_line()` — no architecture change unless new field

### Phase A4 — Coverage + graph wiring

- [ ] Update / split manifest: `L4.2_drug_indication_full_manifest.json` OR extend existing manifest sections
- [ ] `python scripts/sut/build_sut_coverage.py`
- [ ] `python scripts/sut/build_rule_interaction_graph.py`
- [ ] Rule Database: drug motor card shows **clause encoded %** separate from registry status

---

## Parallel agent contract

| Owns | Does not touch |
|------|----------------|
| `drug_indication_prose.json`, `L4.2_*`, `drug_indication_*`, `test_drug_indication.py`, `test_claim_drug_indication.py` | `payment_method_2_2.json`, `copay_general_1_8.json`, `material_bundling_prose.json` |

**Merge:** After JSON + manifest, hand off to orchestrator for coverage regen (or run locally on branch only).

---

## Metrics targets

| Metric | Now | Epic target |
|--------|----:|------------:|
| JSON rules (drug_indication) | 164 | **≥200** |
| §4.2 `has_rule_encoding` | 518 | **≥600** |
| Tier C traced (4.2.14.C) | ~750 | **828 (100%)** |
| Synthetic demo patients (drug indication) | 4+ | **+3** for A2 batches |

---

## Definition of done

1. Manifest traces every 4.2.14.C clause (encode or Tier C deferred with reason).
2. ≥2 new §4.2 subsection batches (A2) merged with golden tests.
3. `has_rule_encoding` for §4.2 increases by **≥80** clauses vs baseline.
4. Fact-check L4.2 documents explicit **4.2.14.C encoded %** + **§4.2 rest partial**.
5. No regression in R1–R4 referans / utilization tier logic.

---

## Verification

```bash
pytest tests/unit/domain/prose_rules/test_drug_indication.py \
  tests/unit/domain/billing/test_claim_drug_indication.py \
  tests/unit/scripts/test_sut_coverage.py -q
python scripts/sut/prose/merge_drug_indication_sprint1.py  # or successor merge
python scripts/sut/build_sut_coverage.py
```
