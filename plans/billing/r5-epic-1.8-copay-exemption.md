# R5 Epic D — §1.8 Copay exemption & rates (prose trace + status rules)

**Epic ID:** `R5-D`  
**Orchestration:** `plans/billing/r5-gate-b-parallel-index.md`  
**Extends:**  
- `plans/billing/copay-exemption-coverage.md` (status-based exemptions)  
- `plans/billing/copay-ek1a-ek4d-scope-fix-plan.md` (§1.8.5(7) vs (8) / EK-4/D)  
**Registry:** `copay_exemption_ek1a`, `copay_exemption_visit_type`, `copay_exemption_ek4d`, `copay_rate_general`  
**Runtime:** `src/bilun/domain/optimization/copay_exemptions.py`, `copay_exemption_rules/*`  
**Artifact:** `data/gazette/prose_rules/copay_general_1_8.json` (**4 rules** — **no encode manifest**)

---

## Goal

1. **Gate B trace:** Link §1.8 prose JSON to clause IDs so coverage shows encode status honestly.  
2. **Composable exemptions:** Ship status-based rules (acil, koruyucu, yeşil kart, …) per copay-exemption-coverage plan — with `exemption_sources[]`.  
3. **Scope fix:** EK-1A chronic vs §1.8.5(8) inpatient drug vs EK-4/D — correct rule attribution (ek1a plan).

**Done looks like:** §1.8 motor-bound gap drops; APIs report **why** exempt; synthetic data exercises multiple categories.

---

## Baseline

| Metric | Value |
|--------|------:|
| §1.8 clauses (copay motors) | 60 |
| `has_rule_encoding=true` | **0** |
| Deontic, not encoded | 11 |
| JSON prose rules | 4 |
| EK-1A engine | `ek1a.py` — ICD-only today |
| Visit type rules | partial in `visit_type.py`, `patient_status.py` |

---

## Out of scope

- EK-2C-1 copay **rate cap** engine (separate from exemption — do not merge summaries)
- Full MEDULA provision type alignment (`provision_type_medula`) — stub only
- Guaranteeing SGK recovery from exemption flags

---

## Phases

### Phase D0 — Manifest bootstrap (1 day)

- [ ] Create `data/gazette/prose_manifests/L1.8_copay_exemption_encoded_manifest.json`
- [ ] Map existing 4 rules in `copay_general_1_8.json` → `gate_b_sources` clause IDs
- [ ] Script: `scripts/sut/prose/copay_exemption_gate_b.py`
  - Export §1.8.1–1.8.5 candidates → `data/gazette/prose_corpus/L1.8_copay_exemption_prose.csv`
  - Flag overlap with `copay_exemption_ek4d` / EK-4/D catalog rows
- [ ] Regen coverage — expect **0 → ~8–15** encoded §1.8 clauses

### Phase D1 — EK-1A vs §1.8.5(8) scope (3–5 days)

From `copay-ek1a-ek4d-scope-fix-plan.md`:

- [ ] §1.8.5(7)+EK-1A → chronic visit copay waiver scope only
- [ ] §1.8.5(8)(b) → yatis/günübirlik drug proxy until `yatarak_tedavi_ilac` on claim line
- [ ] EK-4/D → `("1.8.2",)` applicability, not blanket EK-1A
- [ ] Each fix: add/update `gate_b_sources` on affected prose or compositor rule

### Phase D2 — Status-based exemption categories (1–2 weeks)

From `copay-exemption-coverage.md` Phase 1–3:

| Category | Module | §1.8 anchor |
|----------|--------|-------------|
| `acil_servis` | `visit_type.py` | 1.8.x acil |
| `koruyucu` | `visit_type.py` | koruyucu |
| `yesil_kart` | `patient_status.py` | 1.8.3 |
| `occupational` | `occupational.py` | iş kazası / meslek hastalığı |

Per category:

- [ ] Rule implementation + unit test
- [ ] Synthetic generator fields (`gelis_tipi`, `sgk_benefit_class`, …)
- [ ] Prose JSON row OR registry-only with manifest clause trace (prefer JSON when deontic prose exists)
- [ ] Extend `check_copay_exemptions()` output shape: `exemption_sources[]`, `categories_not_evaluated[]`

### Phase D3 — Prose expansion (1 week)

- [ ] Add 6–10 JSON rules for remaining deontic §1.8 fıkra not covered by compositor modules
- [ ] Golden: `golden/copay_general_1_8.json`
- [ ] Tests: `tests/unit/domain/optimization/test_copay_exemptions.py` (extend)

### Phase D4 — Product + metrics

- [ ] Cohort cache: pass patient status + claim type into exemption check
- [ ] Billing alerts: distinguish **exempt** vs **rate-capped** (EK-2C-1)
- [ ] Rule Database §1.8 utilization chips reflect encode
- [ ] Fact-check L2.1/L2.2 copay rows updated

---

## Parallel agent contract

| Owns | Does not touch |
|------|----------------|
| `copay_general_1_8.json`, `L1.8_*`, `copay_exemption_gate_b.py`, `copay_exemption_rules/*`, `copay_exemptions.py`, synthetic patient/episode fields for copay | `payment_method_2_2.json`, drug/material JSON |
| `generators.py` copay-related columns only | Payment-method generator DRG mix logic |

---

## Metrics targets

| Metric | Now | Target |
|--------|----:|-------:|
| §1.8 `has_rule_encoding` | 0 | **≥25** |
| JSON rules (copay_general_1_8) | 4 | **≥12** |
| Exemption categories with tests | 1 (EK-1A) | **≥5** |
| Synthetic demo patients (multi-category exempt) | ~EK-1A only | **≥3** scenarios |

---

## Definition of done

1. `L1.8_copay_exemption_encoded_manifest.json` exists; coverage wired.
2. `exemption_sources[]` on API/billing output for ≥5 categories.
3. EK-1A vs §1.8.5(8) vs EK-4/D scope fixes shipped with tests.
4. ≥8 net new encode traces (JSON or manifest) for deontic §1.8 clauses.
5. Docs: `docs/core-system/sut.md` exemption section matches implementation.

---

## Verification

```bash
pytest tests/unit/domain/optimization/test_copay_exemptions.py \
  tests/unit/domain/optimization/test_copay_ek1a.py -q
python scripts/sut/prose/copay_exemption_gate_b.py
python scripts/sut/build_sut_coverage.py
```
