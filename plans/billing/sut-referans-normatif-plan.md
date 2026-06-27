## Task: SUT referans / normatif / encode ayrımı (dürüst kapsam)

**Branch:** `feat/sut-referans-normatif`  
**Status:** R1–R4 complete (2026-06-27); R5 deferred  
**Goal:** Her canlı hüküm ya **referans**, ya **motora bağlı (encode bekliyor)**, ya **encode edilmiş** olarak doğru etiketlensin; gap KPI’sı gerçek encode borcunu yansıtsın.

### Measured baseline (4.710 in-force rows)

| Bucket | Count | % |
|--------|------:|--:|
| `has_rule_encoding=true` | 639 | 13.6% |
| `deontic_modality` dolu | 553 | 11.7% |
| `non_algorithmic` | 690 | 14.6% |
| deontic var, encode yok | 472 | 10.0% |
| yapısal tip (chapter/heading/amendment), deontic yok | 1.077 | 22.9% |
| `primary_rule_id=null` + `missing` (bug) | 10 → **0** after R1+R3 | — |

**Out of scope:** L0–L4 framework; yeni extractor gate.  
**Graph:** 639 encoded nodes only — not 4.710 clause structure graph.

---

### Phase R1 — Referans sınıflandırma düzeltmeleri ✅

- [x] Plan + branch
- [x] `coverage._has_actionable_signal`: structural types fix (C000002)
- [x] Unit tests: chapter, Genel Hükümler, section_heading
- [x] `build_sut_coverage.py` regen — missing 10→4→**0**, gaps 2383→2377
- [x] pytest green

### Phase R2 — UI üç rozet ✅

- [x] `clauseUtilizationTier` + `UtilizationChip` (Referans | Encode edilmiş | Motora bağlı)
- [x] Hükümler default **Referans gizle** (`exclude_non_algorithmic` API)
- [x] `definitions` → “Tanım / kapsam (referans)” label

### Phase R3 — Classify routing ✅

- [x] §1.10 / §1.11 → `provizyon_medula` (health report / MEDULA hekim şifresi)
- [x] §6.x amendment → `definitions`, not `gazette_repricing` (test)
- [x] Coverage regen; missing **0**

### Phase R4 — Encode etkileşim graph ✅

- [x] `scripts/sut/build_rule_interaction_graph.py`
- [x] Output `data/gazette/rule_interaction_graph.json` — **639 nodes**, 1580 edges
- [x] Edge types: `same_billing_context`, `same_rule_set`
- [x] Unit tests

### Phase R5 — Gate B genişletme ⏸ DEFERRED

**Orchestration:** [`r5-gate-b-parallel-index.md`](./r5-gate-b-parallel-index.md) — 4 paralel epic plan:

| Epic | Plan |
|------|------|
| A §4.2 ilaç | [`r5-epic-4.2-drug-indication.md`](./r5-epic-4.2-drug-indication.md) |
| B §3.1–3.2 malzeme | [`r5-epic-3.1-material-bundling.md`](./r5-epic-3.1-material-bundling.md) |
| C §2.2 ödeme | [`r5-epic-2.2-payment-method.md`](./r5-epic-2.2-payment-method.md) |
| D §1.8 katılım payı | [`r5-epic-1.8-copay-exemption.md`](./r5-epic-1.8-copay-exemption.md) |

Separate program — not in `feat/sut-referans-normatif` unless explicitly started.

---

### Verification

```bash
pytest tests/unit/scripts/test_sut_coverage.py tests/unit/scripts/test_rule_interaction_graph.py \
  tests/unit/domain/sut/test_rules_catalog.py tests/unit/api/test_sut_rules_api.py -q
python scripts/sut/build_sut_coverage.py
python scripts/sut/build_rule_interaction_graph.py
cd frontend && npx vitest run src/lib/clauseUtilization.test.ts src/components/tabs/sut/sections/RuleDatabaseSection.test.tsx
```

### Review (2026-06-27)

- **R1+R3:** Structural reference rows no longer false gaps; §1.10–1.11 routed; `missing=0`.
- **R2:** Single utilization badge replaces overlapping coverage/gap/encoded chips in clause UI; referans hidden by default in Hükümler browser.
- **R4:** Rule interaction graph built from `has_rule_encoding` parquet truth (639 nodes), not full clause corpus.
- **Not done:** Gate B corpus expansion (R5), `depends_on`/`overrides` edges from prose JSON (future), material_constrains from EK-3 pairing.
