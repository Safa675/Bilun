# R5 Epic C — §2.2 Payment method (prose trace + gap encode)

**Epic ID:** `R5-C`  
**Orchestration:** `plans/billing/r5-gate-b-parallel-index.md`  
**Related (runtime, not Gate B):** `plans/billing/payment-method-compliance-data-fix-plan.md`  
**Registry:** `payment_method_package`, `payment_method_itemized`, `payment_method_tier_override` — `partial`  
**Runtime:** `src/bilun/domain/prose_rules/payment_method.py`  
**Artifact:** `data/gazette/prose_rules/payment_method_2_2.json` (**5 rules** — **no encode manifest yet**)

---

## Goal

Wire §2.2 prose rules into the **honest coverage model**: create Gate B manifest with `gate_b_sources`, map encoded clauses to `has_rule_encoding=true`, and expand JSON for high-priority **deontic** §2.2 fıkra (package vs itemized vs session fraction).

**Done looks like:** §2.2 clauses show **Encode edilmiş** where JSON exists; payment-method compliance and strategy share one prose source of truth.

---

## Baseline

| Metric | Value |
|--------|------:|
| §2.2 clauses (payment motors) | 88 |
| `has_rule_encoding=true` | **0** (manifest missing) |
| Deontic, not encoded | 38 |
| JSON rules on disk | 5 (`payment_method_2_2.json`) |
| Session pricing sibling | `session_pricing_2_2_2_B.json` (4 rules) — coordinate, do not duplicate |

**Root issue:** Runtime engine works; **coverage parquet never sees encode** because `prose_manifests/` has no L2.2 manifest linking clause IDs.

---

## Out of scope

- Full §2.2.2.B session-fraction engine (separate `session_pricing_2_2_2_B` track — document as PARTIAL)
- Automatic bill separator product feature (payment-method plan P2)
- DRG package adequacy (`drg_package_adequacy_prose`) — different motor

---

## Phases

### Phase C0 — Manifest bootstrap (1 day) — **highest leverage**

- [ ] Create `data/gazette/prose_manifests/L2.2_payment_method_encoded_manifest.json`
- [ ] For each rule in `payment_method_2_2.json`, attach `gate_b_sources`: clause IDs from Gate B export
- [ ] Script: `scripts/sut/prose/payment_method_gate_b.py` (new)
  - Export §2.2 candidates → `data/gazette/prose_corpus/L2.2_payment_method_prose.csv`
  - Columns: `clause_id`, `section_id`, `deontic_modality`, `payment_kind_hint`, `duplicate_of`, `encode_priority`
- [ ] Run `build_sut_coverage.py` — expect §2.2 encoded jump **0 → ~15–25** (5 rules × multi-clause sources)

### Phase C1 — Align with compliance data-fix plan (3–5 days)

From `payment-method-compliance-data-fix-plan.md` (can run same agent, sequential sub-phases):

- [ ] P0: synthetic generator — no accidental DRG_MANDATORY mix on paket claims
- [ ] P1: `itemized_total_try` excludes `compliance_violation` lines
- [ ] Ensure `check_payment_method_compliance()` and prose JSON reference same `resolve_payment_method` outcomes

**Gate B link:** Each compliance rule maps to §2.2 clause IDs in manifest.

### Phase C2 — Encode priority fıkra (1–2 weeks)

Target deontic clusters (84 rows on `payment_method_package` motor):

| Batch | Topic | Target rules |
|-------|-------|-------------:|
| C2a | Paket vs kalem (2.2.2 core) | 3–5 |
| C2b | Yatak / muayene / lab mix rules | 3–5 |
| C2c | Tier override / facility tier | 2–4 |
| C2d | Ayakta mix / evde sağlık / komorbidite (batch 3) | 5–8 |

- [x] Extend `payment_method_2_2.json` + schema if needed
- [x] Golden: `data/gazette/prose_rules/golden/payment_method_2_2_batch1.json` (+ batch2, batch3)
- [x] Tests: `tests/unit/domain/prose_rules/test_payment_method.py` (create or extend)
- [x] C2 batch 3: `payment_method_2_2_batch3_rules.py` + `merge_payment_method_batch3.py`
- [x] C2 batch 4: `payment_method_2_2_batch4_rules.py` + `merge_payment_method_batch4.py` (13 rules → 42 JSON total)

### Phase C3 — Session pricing boundary (document)

- [x] Cross-ref `session_pricing_2_2_2_B.json` rules in manifest `related_rule_sets`
- [x] Fact-check L3.1 hemogram: §2.2.2.B gap explicitly **unimplemented** or partial encode
- [x] Do not merge session fraction into payment_method JSON without matcher design

### Phase C4 — UX + fact-check

- [x] Rule Database payment_method motor: show encoded clause count
- [x] Update `fact_check_audit.py` L2.2 row with encode fraction
- [x] Coverage + graph regen

---

## Parallel agent contract

| Owns | Does not touch |
|------|----------------|
| `payment_method_2_2.json`, `L2.2_*`, `payment_method_gate_b.py`, `payment_method.py`, `claim_strategy.py` (payment sections only), synthetic generator payment mix | Drug / material / copay JSON |
| Optional: `session_pricing_2_2_2_B.json` manifest cross-ref only | Full session fraction engine rewrite |

---

## Metrics targets

| Metric | Now | Target |
|--------|----:|-------:|
| §2.2 `has_rule_encoding` | 20 | **≥40** (49/148) |
| JSON rules (payment_method_2_2) | 29 | **≥15** (42) |
| Deontic unencoded §2.2 | 38 | **≤15** |
| Synthetic accidental paket+DRG_MANDATORY mix | unknown | **0** (demo cohort) |

---

## Definition of done

1. `L2.2_payment_method_encoded_manifest.json` exists; all JSON rules have `gate_b_sources`.
2. Coverage shows **>0** §2.2 encoded clauses (manifest wired).
3. ≥10 net new JSON rules with golden tests.
4. Payment-method compliance plan P0+P1 merged or tracked in same branch.
5. Fact-check L2.2 documents PARTIAL with explicit encode %.

---

## Verification

```bash
pytest tests/unit/domain/prose_rules/test_payment_method.py \
  tests/unit/domain/billing/test_claim_strategy.py -q  # if payment tests exist
python scripts/sut/prose/payment_method_gate_b.py
python scripts/sut/build_sut_coverage.py
```
