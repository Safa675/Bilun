## Task: SUT referans / normatif / encode ayrımı (dürüst kapsam)

**Branch:** `feat/sut-referans-normatif`  
**Status:** In progress (2026-06-27)  
**Goal:** Her canlı hüküm ya **referans**, ya **motora bağlı (encode bekliyor)**, ya **encode edilmiş** olarak doğru etiketlensin; gap KPI’sı gerçek encode borcunu yansıtsın.

### Measured baseline (4.710 in-force rows)

| Bucket | Count | % |
|--------|------:|--:|
| `has_rule_encoding=true` | 639 | 13.6% |
| `deontic_modality` dolu | 553 | 11.7% |
| `non_algorithmic` | 690 | 14.6% |
| deontic var, encode yok | 472 | 10.0% |
| yapısal tip (chapter/heading/amendment), deontic yok | 1.077 | 22.9% |
| `primary_rule_id=null` + `missing` (bug) | 10 | 0.2% |

**Out of scope:** L0–L4 framework; yeni extractor gate (önce mevcut alanları düzelt).  
**Graph:** kural etkileşim grafiği yalnızca encode edilmiş ~639 node üzerinde (ayrı alt görev).

---

### Phase R1 — Referans sınıflandırma düzeltmeleri (bu branch)

- [x] Plan + branch
- [x] `coverage._has_actionable_signal`: structural types fix (C000002)
- [x] Unit tests: chapter, Genel Hükümler, section_heading
- [x] `build_sut_coverage.py` regen — missing 10→4, gaps 2383→2377, C000002 fixed
- [x] pytest green (82 tests)

**Done when:** `primary_rule_id=null` + `missing` → 0; C000002 `non_algorithmic`.

### Phase R2 — UI üç rozet (follow-up PR on same branch or next)

- [ ] Rule Database: Referans | Encode edilmiş | Motora bağlı (encode bekliyor)
- [ ] Varsayılan filtre: referans gizli veya ayrı sekme
- [ ] `definitions` motor etiketi → “Tanım / kapsam (referans)”

### Phase R3 — Classify routing (Wave 2 partial-coverage plan)

- [ ] `classify.py` fallback: §6.x tebliğ meta → `non_algorithmic` / doğru motor
- [ ] `medula_rejection` vs `provizyon_medula` primary çakışması
- [ ] Re-run coverage; dashboard gap footnote güncelle

### Phase R4 — Encode etkileşim graph (~639 node)

- [ ] Node set: manifest `encoded_clause_ids` birleşimi
- [ ] Kenar tipleri: `depends_on`, `overrides`, `same_billing_context`, `material_constrains`
- [ ] graphify / export — 4.710 hüküm grafiği değil

### Phase R5 — Gate B genişletme (yüksek TRY sırası)

- [ ] §3.1 malzeme bundling
- [ ] §2.2 paket/ödeme
- [ ] §1.8 katılım payı
- [ ] §4.2 ilaç endikasyon (ayrı epic)

---

### Verification

```bash
pytest tests/unit/scripts/test_sut_coverage.py tests/unit/domain/sut/test_rules_catalog.py -q
python scripts/sut/build_sut_coverage.py
# Compare missing count + C000002 row in sut_clause_coverage.parquet
```

### Review

_(fill on branch merge)_
