# Plan: Algorithmic gap closure (`has_algorithmic_gap`)

**Status:** Draft — 2026-06-30  
**North-star metric:** `has_algorithmic_gap = true` clauses with `has_rule_encoding = false`  
**Baseline:** **1,564** remaining (**809 / 2,373** encoded = **34.1%**)  
**Registry:** `drug_indication_prose` stays `partial` until Tier B/C honesty thresholds met  
**Runtime contract:** YAML → `compile_rules.py` → `data/gazette/prose_rules/*.json` → `evaluate_drug_indication_line()` (unchanged)

---

## Goal

Close the **honest algorithmic encode debt** for the SUT communiqué: every clause the coverage model says **should** have a rule either gets:

1. **A prose rule** (YAML section source → runtime JSON) with `gate_b_sources`, or  
2. **A documented deferral** (Tier C / EMR-blocked) so it is **removed from the gap set** without pretending it is encoded.

**Done looks like:**

| Metric | Baseline | Target |
|--------|----------|--------|
| Unencoded algorithmic gaps | 1,564 | **0** (or explicit deferred with `emr_blocked` / manifest tier-C) |
| `has_rule_encoding` on gaps | 34.1% | **100%** encoded **or** reclassified off `has_algorithmic_gap` |
| `build_sut_coverage.py` + `compile_rules.py --check` | green | green after each wave |
| Drug indication §4.2 gap corpus | 1,561 | 0 unencoded **or** tier-C traced |

**Not the goal:** encoding all 4,710 in-force clauses, headings, or `non_algorithmic` definitions.

---

## Baseline inventory (2026-06-30)

### Global

| Bucket | Count |
|--------|------:|
| Algorithmic gaps (`has_algorithmic_gap`) | 2,373 |
| Already encoded | 809 |
| **Remaining** | **1,564** |
| Non-drug remaining | 3 (`procedure_pairing`) |

### Drug indication (`drug_indication_prose`) — 1,561 remaining

| Split | Count | Notes |
|-------|------:|-------|
| **Structural / nav** (heading, amendment, `is_heading`) | 538 | Manifest trace only — **not** 1:1 JSON rules |
| **Substantive** gaps | 1,023 | Real encode / defer decisions |
| Substantive **deontic** | 103 | Highest ROI — normative language |
| Substantive **non-deontic** | 920 | Pathway / criteria — Tier B/C |

### Top §4.2 sections by unencoded gap count

| Section | Unencoded gaps | Deontic |
|---------|---------------:|--------:|
| 4.2.14 (oncology board) | 335 | 103 |
| 4.2.1 | 163 | 0 |
| 4.2.10 (LSD) | 111 | 0 |
| 4.2.13 | 80 | 0 |
| 4.2.6 | 69 | 0 |
| 4.2.9 | 51 | 0 |
| 4.2.15 | 50 | 0 |
| 4.2.28 | 44 | 0 |
| 4.2.27 | 39 | 0 |
| 4.2.24 | 36 | 0 |

### Deontic modalities still unencoded (n=103)

| Modality | Count |
|----------|------:|
| COVERAGE | 72 |
| NO_PAY | 20 |
| PROHIBITED | 5 |
| PERMISSION | 5 |
| MANDATORY | 1 |

---

## Architecture (post Phase 1–3)

| Layer | Location | Role in this plan |
|-------|----------|-------------------|
| Authoring | `data/gazette/prose_rule_sources/drug_indication/*.yaml` | One file per SUT section |
| Compile | `scripts/sut/compile_rules.py` | Merge YAML → JSON + manifests |
| Gate B | `scripts/sut/prose/*_gate_b.py`, `gate_b_core.py` | Corpus CSV + manifest clause traces |
| Coverage | `scripts/sut/build_sut_coverage.py` → `sut_clause_coverage.parquet` | Sets `has_rule_encoding` |
| Runtime | `src/bilun/domain/prose_rules/drug_indication.py` | Evaluates rules on claim lines |

**Per-wave workflow (mandatory):**

1. Export gap CSV for target section prefix (`has_algorithmic_gap ∧ ¬has_rule_encoding`).  
2. Gate B pass → assign encode tier (A / B / C / structural).  
3. Author YAML rules (Tier A/B) or manifest deferral (Tier C / structural).  
4. `python scripts/sut/compile_rules.py --target drug_indication_prose` (+ gate B stage if needed).  
5. `python scripts/sut/build_sut_coverage.py` — verify gap count drops.  
6. Golden + unit tests for new rules.  
7. Commit JSON + manifests + corpus + coverage parquet together.

---

## Encode tiers (decision tree)

Use the same tier model as `drug-indication-4.2.14.C-expansion-plan.md`:

### Tier A — Encode now

**Signal:** INN / drug keyword + ICD-10 + report flag (+ optional duration/specialty).  
**Action:** New or patched YAML rule + `gate_b_sources`.  
**Matcher:** Existing `evaluate_drug_indication_line()` — no schema change.

### Tier B — Encode with extended conditions

**Signal:** Tier A + `report_duration_months`, `prescriber_specialties`, `inpatient_only`, lab thresholds already on `DrugClaimLine`.  
**Action:** YAML + schema validation + golden samples.  
**Matcher:** Extend condition keys only if claim adapter already supplies the field.

### Tier C — Defer honestly (remove from gap set)

**Signal:** ECOG, progression, mutation panels, combination pathways, response assessment, MOH approval — **no claim field**.  
**Action:** Gate B manifest `tier_c_deferred` + `defer_themes`; optional `emr_blocked_clause_ids`.  
**Coverage:** `has_rule_encoding = false` but **`has_algorithmic_gap` must become false** via registry/coverage honesty update OR clause reclassified to “deferred motor” (see Wave 0).

### Structural — Manifest trace only

**Signal:** `section_heading`, `amendment`, RG citation lines, empty prose labels.  
**Action:** Manifest `non_actionable` / header trace — **no JSON rule**.  
**Coverage:** Exclude from gap numerator (538 clauses) via `_has_actionable_signal` / classify fix.

---

## Phased execution

### Wave 0 — Hygiene & quick wins (½–1 day)

**Target:** −541 gaps (538 structural + 3 procedure_pairing)

- [ ] **W0.1** Export `reports/algorithmic_gaps_unencoded.csv` from coverage parquet (script or one-off notebook).  
- [ ] **W0.2** Reclassify **538 structural** drug gaps: manifest-only trace OR `coverage_status` fix so they are not `has_algorithmic_gap`. Document in `coverage.py` if new clause_type rule needed.  
- [ ] **W0.3** Encode **3** `procedure_pairing` gaps → `prose_rule_sources` + `procedure_pairing_prose.json`.  
- [ ] **W0.4** Encode **103 deontic substantive** gaps (mostly §4.2.14) — Tier A YAML batch.  
- [ ] **W0.5** Rebuild coverage; confirm: unencoded gaps ≤ **1,023** (substantive drug only).

**Acceptance:** Deontic encode rate **100%**; procedure_pairing gaps **0**; structural clauses not counted in gap dashboard.

---

### Wave 1 — §4.2.14.C oncology tail (3–5 days)

**Target:** −200…−335 gaps (remaining §4.2.14 after deontic wave)

- [ ] **W1.1** Gate B export for §4.2.14.C pending clauses (`drug_indication_phase5` stage).  
- [ ] **W1.2** Tier A/B encode in waves by INN family (reuse `legacy_batch_rule_ids.json` section groupings).  
- [ ] **W1.3** Tier C defer with `defer_themes` for pathway-only rows.  
- [ ] **W1.4** Golden: extend `data/gazette/prose_rules/golden/drug_indication_4.2.14.C*.json`.  
- [ ] **W1.5** `test_all_rule_family_yaml_sources.py` + domain drug indication tests green.

**Acceptance:** §4.2.14 unencoded gap **< 50** (remainder explicit Tier C).

---

### Wave 2 — High-volume §4.2 pilots (1–2 weeks)

Encode or defer by existing Gate B modules (already wired in `compile_rules.py`):

| Section | Unencoded gaps | Gate B / manifest |
|---------|---------------:|-------------------|
| 4.2.1 | 163 | `drug_indication_4201_gate_b` |
| 4.2.10 | 111 | `drug_indication_4210_gate_b` |
| 4.2.13 | 80 | phase5 / combination manifests |
| 4.2.6 | 69 | metabolic mid CSV wave |
| 4.2.9 + 4.2.27 | 90 | `drug_indication_4209_4227_gate_b` |
| 4.2.15 | 50 | `drug_indication_4215_gate_b` |

Per section batch:

- [ ] Run Gate B → tier inventory CSV.  
- [ ] Tier A/B YAML in `prose_rule_sources/drug_indication/`.  
- [ ] Tier C → manifest deferred IDs.  
- [ ] Single compile + coverage rebuild per merged PR (avoid manifest drift).

**Acceptance:** Each section ≥ **80%** of substantive gaps either encoded or tier-C deferred with trace.

---

### Wave 3 — Mid-tail §4.2 (1–2 weeks)

Sections: 4.2.24, 4.2.28, 4.2.12, 4.2.46, 4.2.34, 4.2.49, 4.2.33, 4.2.30, 4.2.23, 4.2.70, 4.2.17, 4.2.42, …

- [ ] Same Gate B → tier → YAML/defer loop.  
- [ ] Prefer **section-scoped PRs** (align with existing `L4.2_drug_indication_*` manifests).  
- [ ] Track EMR-blocked clauses in section manifests (`emr_blocked_clause_ids` where applicable).

**Acceptance:** Unencoded substantive drug gaps **< 200**.

---

### Wave 4 — Long tail + registry honesty (ongoing)

- [ ] §4.2.41, 4.2.47, 4.2.60, 4.2.72–75 (0–10% encoded today).  
- [ ] **Registry decision:** when to move `drug_indication_prose` from `partial` → `implemented`  
  - Proposed gate: ≥ **95%** substantive gaps encoded **or** tier-C deferred with manifest; deontic **100%**.  
- [ ] Dashboard: show **encoded / deferred / true gap** separately (avoid false “zero gap”).

---

## Coverage honesty rules (critical)

A clause must **leave** the 1,564 backlog by exactly one path:

| Outcome | `has_rule_encoding` | `has_algorithmic_gap` | Artifact |
|---------|--------------------|-----------------------|----------|
| Encoded | `true` | `false` | YAML rule + manifest `encoded` |
| Tier C deferred | `false` | `false` | manifest `tier_c_deferred` + coverage policy |
| EMR blocked | `false` | `false` | `emr_blocked_clause_ids` |
| Structural | `false` | `false` | non_actionable trace |
| True remaining gap | `false` | `true` | none — backlog |

**Forbidden:** `has_rule_encoding = true` without `gate_b_sources`; manifest encoded without JSON rule (except `SOURCE_PATCHES` append-only).

---

## Verification checklist (every wave)

```bash
python scripts/sut/compile_rules.py --check
python scripts/sut/build_sut_coverage.py
python -m pytest tests/unit/scripts/test_all_rule_family_yaml_sources.py -q
python -m pytest tests/unit/domain/prose_rules/test_drug_indication_*.py -q
python -m pytest tests/unit/scripts/test_drug_indication_*_gate_b.py -q
```

**Coverage SQL (Polars):**

```python
cov = pl.read_parquet("data/gazette/sut_clause_coverage.parquet").filter(pl.col("is_in_force"))
gaps = cov.filter(pl.col("has_algorithmic_gap") & ~pl.col("has_rule_encoding"))
assert gaps.height == 0  # ultimate target
```

---

## Metrics dashboard (track weekly)

| Metric | Formula |
|--------|---------|
| Gap encode % | `encoded_gaps / total_gaps` |
| Remaining backlog | `gaps ∧ ¬encoded` |
| Substantive backlog | exclude structural clause_types |
| Deontic backlog | deontic ∧ gap ∧ ¬encoded |
| §4.2.14 backlog | section prefix filter |
| Rules in JSON | `len(drug_indication_prose.json rules)` |
| YAML parity | `test_all_rule_family_yaml_sources` |

---

## Out of scope

- Encoding `non_algorithmic` motors (definitions, billing documents) — 700 clauses  
- Runtime YAML loading in `src/bilun/` (JSON contract unchanged)  
- Full EMR / clinical pathway ingestion (Tier C stays deferred until schema exists)  
- Non–drug-indication algorithmic motors (already ~0 gap except procedure_pairing)

---

## Dependencies & references

- `plans/billing/drug-indication-4.2.14.C-expansion-plan.md` — tier A/B/C model  
- `plans/billing/r5-epic-4.2-drug-indication.md` — Gate B parallel index  
- `plans/billing/oncology-4.2.14.C-tier-c-expansion-plan.md` — EMR-blocked policy  
- `docs/gazette/rule-compiler.md` — YAML-first compile  
- `scripts/sut/prose/coverage.py` — `has_algorithmic_gap` / `has_rule_encoding` truth

---

## Suggested first PR (Wave 0 slice)

1. `reports/algorithmic_gaps_unencoded.csv` generator script  
2. 103 deontic Tier A YAML rules (§4.2.14)  
3. 3 procedure_pairing rules  
4. Structural gap reclassification (538)  
5. Coverage parquet refresh  

**Expected gap after PR1:** ~1,023 substantive drug + 0 non-drug ≈ **1,023** (down from 1,564).
