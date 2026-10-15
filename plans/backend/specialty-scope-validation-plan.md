# Specialty Scope Validation — Implementation Plan

> **2026-10-15:** the outputs this plan wrote into the repo (`data/synthetic/sut/claims/ilay_validation/`,
> `data/gazette/prose_rules/golden/ilay/`) are derived from real ILAY prescriptions and were removed
> from the tree for KVKK. The harness now writes to `$BILUN_ILAY_VALIDATION_DIR` outside the repo, and
> the specialty regression test uses synthetic cases. Paths below are historical; see
> `plans/security/2026-10-14-remove-ilay-real-data-plan.md`.

## Status

**Pre-build phase.** No code written yet. Plan based on verified investigation
findings (no estimates, only measured numbers).

---

## Goal

Validate Bilun's 366 specialty-restricted `drug_indication` rules against real
ILAY prescribing data joined to hospital departments. Produce:

1. A per-rule compliance report — which specialties actually prescribe each
   specialty-restricted drug
2. A violation log — every (drug × diagnosis × department) triple where a
   non-allowed specialty prescribed a restricted drug
3. Golden test cases in Bilun's test format — drop-in fixtures for the
   `prescriber_specialty_mismatch` violation kind
4. A new Bilun product surface — "department-level prescribing scope audit"
   for hospital compliance teams

This mirrors the item-1 harness (`scripts/validation/validate_drug_rules.py`)
but tests the `prescriber_specialty` dimension instead of the `diagnosis`
dimension.

---

## Verified data facts

All numbers below were measured against the actual parquet files on disk
during the investigation phase.

### Rule corpus

| Metric | Value | Source |
|---|---|---|
| Total `drug_indication` rules | 930 | `load_drug_indication_rules()` |
| Rules with `prescriber_specialties` constraint | **366** (39.4%) | filter on rule dict |
| Rules with specialty constraint AND drug names | **341** | drop empty-drug rules |
| Unique drug tokens across specialty rules | 489 | set union |
| Most common required specialties | iç hastalıkları (101), tıbbi onkoloji (64), romatoloji (59), çocuk sağlığı (59), klinik immunoloji (45) | counter |

### ILAY data

| Metric | Value | Source |
|---|---|---|
| `anadata_clean.parquet` rows | 4,071,488 | `df.height` |
| Unique `SQ_EPISODE` | 2,682,856 | n_unique |
| Unique `SERVISADI` (department) values | 149 | n_unique |
| `recete_clean.parquet` rows | 3,733,161 | `df.height` |
| Unique prescription `RF_EPISODE` | 1,155,682 | n_unique |
| Prescription↔Episode join coverage | **359,441 episodes (31.1%)** | inner join on `RF_EPISODE` = `SQ_EPISODE` |
| Joined prescription rows | **2,181,976** | after join + filter `ilac_adi != "nan"` |

### Overlap

| Metric | Value |
|---|---|
| Rule drug tokens appearing in ILAY data | **39 of 489** |
| Specialty rules with ≥1 drug in ILAY | **87 of 341** (25.5%) |
| Top drugs (by prescription count) | AVAMYS (10,277), PLAVIX (8,226), SYMBICORT (3,648), SERETIDE (3,426), LYRICA (3,277) |

### Real signal (sanity check)

Manual inspection of where specialty-restricted drugs actually get prescribed
showed clear real-world mismatch patterns — Internal Medicine prescribing
specialty drugs in 4-43% of cases per drug. Examples:

| Drug | Expected | Actual primary prescribers |
|---|---|---|
| SERETIDE (pulm) | Göğüs | 50.2% pulm, **29.9% İç Hast.**, 5.6% checkup |
| ARAVA (rheum) | Romatoloji | **42.7% İç Hast.**, 29.1% rheum, 10.3% derm |
| PLAVIX (card) | Kardiyoloji | 76.3% card, **6.8% İç Hast.**, 3.6% neuro |
| ENBREL (rheum/derm) | Rheum/Derm | 92.5% rheum, **7.5% İç Hast.** |

This is **not noise** — the patterns are consistent and match what an SGK
audit would flag.

---

## Out of scope

- The 260 specialty rules whose drug tokens do not appear in ILAY data
- The 31% join coverage problem — we work with the 2.18M joined rows; the
  other 1.55M unjoined prescriptions simply aren't testable
- Clinical-false-positive adjudication (e.g., is "İç Hastalıkları" prescribing
  PLAVIX a legitimate comanagement or a violation?). The harness flags; the
  hospital decides.
- The 18 drug_combination biomarker rules (out of scope per item 1 closure)
- Individual-doctor-level attribution (we have department, not doctor ID)

---

## Architecture

```
scripts/validation/
├── __init__.py                         (exists)
├── README.md                           (exists — update)
├── rx_loader.py                        (exists — reused, no changes)
├── claim_builder.py                    (exists — extend to set prescriber_specialty)
├── validate_drug_rules.py              (exists — item 1, untouched)
├── build_golden_dataset.py             (exists — extend)
└── validate_specialty_rules.py         (NEW — main harness for option B)
```

The new file `validate_specialty_rules.py` mirrors `validate_drug_rules.py`
exactly in shape (load → build claims → validate → write outputs → print
headline summary). Only the data join and the rule-selection differ.

### Data flow

```
ILAY prescriptions (recete_clean.parquet)
    ↓ inner join on RF_EPISODE = SQ_EPISODE
ILAY encounters (anadata_clean.parquet, columns: SQ_EPISODE, SERVISADI)
    ↓ filter to rows where drug_name matches ≥1 rule token
    ↓ carry SERVISADI as prescriber_specialty on DrugClaimLine
Bilun's evaluate_drug_indication_line() (existing function — unchanged)
    ↓ iterates all 930 rules, fires prescriber_specialty_mismatch when wrong
Specialty violation log + per-rule compliance + golden JSON test cases
```

### The claim builder extension

`claim_builder.py`'s `build_drug_line()` currently sets `prescriber_specialty=None`.
The only change needed: pass the joined `SERVISADI` value through. One new
parameter, one new assignment — no other code paths affected. Item 1 keeps
working because it passes `None`.

---

## Subtasks

### Phase 1 — Data join (Day 1)

- [ ] **1.1** Add `load_specialty_pairs()` to `rx_loader.py`
  - Inner join `recete_clean` ↔ `anadata_clean` on episode ID
  - Select only columns needed: `HASTA_ID`, `RF_EPISODE`, `ilac_adi`,
    `RECETE_TARIH`, `SERVISADI`, plus the encounter's `TANIKODU` for
    diagnosis constraint checking (some specialty rules also gate on
    diagnosis)
  - Filter to rows where `ilac_adi` matches one of the 39 known rule tokens
  - Return a `DataFrame` with ~preserved row count (investigation showed
    2.18M joined rows; after token filter, expect ~50-60K — same order of
    magnitude as item 1's 18K)
- [ ] **1.2** Add specialty normalization helper
  - Turkish-aware casefold + strip combining marks (already exists in
    `validate_drug_rules.py` — reuse `_normalize_tr`)
  - No abbreviation expansion needed — `SERVISADI` values are full names
    ("İç Hastalıkları", "Kulak Burun Boğaz"), not abbreviations
- [ ] **1.3** Sanity-check the join — assert row count ≥ 30K (well below the
  raw 2.18M, but high enough to support meaningful per-rule statistics)
- [ ] **1.4** Persist an intermediate parquet
  `data/synthetic/sut/claims/ilay_validation/specialty_pairs.parquet` for
  debugging and downstream re-use

### Phase 2 — Claim builder extension (Day 1)

- [ ] **2.1** Extend `build_drug_line()` in `claim_builder.py` with optional
  `prescriber_specialty: str | None = None` parameter
- [ ] **2.2** Extend `build_claim()` to accept and forward specialty
- [ ] **2.3** Verify item 1 still works — re-run
  `python -m scripts.validation.validate_drug_rules` and confirm same
  18,266 prescriptions / 18,062 violations output (regression test)

### Phase 3 — Specialty validation harness (Day 2)

- [ ] **3.1** Create `validate_specialty_rules.py` mirroring
  `validate_drug_rules.py` structure
- [ ] **3.2** Filter rules to those with non-empty `prescriber_specialties`
  and ≥1 drug name in the 39-token overlap set → expect ~87 active rules
- [ ] **3.3** Build one `DrugClaimLine` per prescription, setting
  `prescriber_specialty = row["SERVISADI"]` and `primary_icd10 =
  row["TANIKODU"]`
- [ ] **3.4** Call `evaluate_drug_indication_line()` for each row, collect
  violations where `violation_kind == "prescriber_specialty_mismatch"`
- [ ] **3.5** Write `specialty_violation_log.parquet`
- [ ] **3.6** Write `specialty_rule_compliance.csv` (per-rule stats):
  `rule_id, sut_section, drug_tokens_sample, required_specialties,
  n_prescriptions, n_violations, violation_rate, top_violating_departments`
- [ ] **3.7** Print headline summary (mirroring item 1's output format)

### Phase 4 — Golden dataset (Day 2-3)

- [ ] **4.1** Extend `build_golden_dataset.py` with a `--kind specialty`
  mode (or split into a sibling `build_specialty_golden.py` if cleaner)
- [ ] **4.2** For each rule with ≥3 violations, extract 1-3 representative
  cases covering different violating departments — aim for diversity, not
  volume
- [ ] **4.3** Write golden JSON files to
  `data/gazette/prose_rules/golden/ilay/specialty_*.json` using the same
  envelope format as item 1's golden files
- [ ] **4.4** Target: 80-150 golden test cases across 30-50 SUT sections

### Phase 5 — Report & README (Day 3)

- [ ] **5.1** Update `scripts/validation/README.md` with the specialty
  section: what it tests, how to run, expected outputs, known limitations
- [ ] **5.2** Document the SERVISADI → rule specialty mapping table
  (which department names correspond to which rule specialty tokens) — this
  is reusable documentation for future Bilun features
- [ ] **5.3** Add the honest-disclaimer section: department ≠ individual
  doctor specialty, refill prescriptions may be legitimate, etc.

### Phase 6 — (Optional) Pytest integration (Day 3-4)

- [ ] **6.1** Add `tests/unit/domain/prose_rules/test_specialty_real_data.py`
  that loads the golden JSON files and runs them through
  `evaluate_drug_indication_line()`
- [ ] **6.2** Wire into Bilun's existing pytest CI (mirroring how item 1's
  golden cases will be wired — depends on item 1's pytest integration
  landing first)

---

## Risks & mitigations

| Risk | Mitigation |
|---|---|
| False positives from legitimate comanagement (İç Hastalıkları refilling PLAVIX for chronic CAD patients) | The harness flags; hospital adjudicates. Each violation row carries the department + drug + diagnosis so a human can decide. Document this clearly in the README. |
| Department name mismatch (e.g., "Deri Hastalıkları" vs rule's "dermatoloji") | Investigation showed most names align directly; the few that don't can be normalized with a 10-15 row mapping table. Build that table once. |
| 31% join coverage biasing the results | Document the bias in the README. The 31% that DID join is still 2.18M prescriptions — large enough for statistically meaningful per-rule compliance numbers. |
| Some specialty rules require BOTH right specialty AND right diagnosis | We pass both SERVISADI and TANIKODU to the claim builder; `evaluate_drug_indication_line()` checks both. Diagnosis-correct + specialty-wrong is still a `prescriber_specialty_mismatch`. |
| Item 1 regression when modifying `claim_builder.py` | Phase 2.3 explicitly re-runs item 1 to confirm identical output before proceeding |

---

## Success criteria

The plan is done when ALL of these hold:

1. `python -m scripts.validation.validate_specialty_rules` runs end-to-end
   in under 5 minutes on the local machine
2. The violation log has ≥1,000 rows (we expect 5,000-15,000 based on the
   manual sample showing 4-43% violation rates per drug)
3. The compliance CSV has 87 rows (one per fireable rule), each with
   non-empty `top_violating_departments`
4. ≥50 golden test cases are written in Bilun's golden JSON format
5. Item 1's harness produces byte-identical output before and after the
   `claim_builder.py` modification
6. README.md documents the SERVISADI → specialty mapping and the
   department-≠-doctor caveat

---

## What this is NOT

- Not a clinical-false-positive adjudication tool
- Not a doctor-level performance review (no doctor IDs in the data)
- Not a billing-rejection predictor (we still don't have SGK adjudication
  data — same limitation as item 1)
- Not an ML model — pure rule-engine validation, same as item 1
- Not a new product — it's a deeper test of Bilun's existing rules along a
  new dimension (specialty, in addition to item 1's diagnosis dimension)

---

## Timeline

3 days of focused work. No GPU, no external services, no model training.
Pure Python + Polars rule-engine validation, same architecture as item 1.

| Day | Phase | Output |
|---|---|---|
| 1 | Data join + claim builder extension + regression check | `specialty_pairs.parquet`, extended `build_drug_line()`, item 1 re-run identical |
| 2 | Validation harness + outputs | `specialty_violation_log.parquet`, `specialty_rule_compliance.csv`, headline summary printed |
| 3 | Golden dataset + README + (optional) pytest | 50-150 golden JSONs, README updated, optional pytest wired |

---

## Decision points to confirm before coding

1. **Where does `validate_specialty_rules.py` live?** — Recommendation:
   `scripts/validation/` next to `validate_drug_rules.py`. Same package,
   parallel harness, symmetric naming. (No new directory.)

2. **How to handle `claim_builder.py` modification?** — Recommendation:
   extend the existing functions with optional parameters rather than
   forking into separate builders. Item 1 stays at zero changes; item 2
   adds parameters with `None` defaults.

3. **Should this produce a Bilun product surface (department-level audit
   dashboard)?** — Recommendation: NOT in this plan. The data outputs
   (`specialty_rule_compliance.csv`) are sufficient for a future dashboard
   feature. Building the dashboard is a separate UI task.

4. **Pytest integration in this plan or deferred?** — Recommendation:
   deferred to Phase 6 (optional). Land the harness + golden dataset first,
   wire pytest once both item 1 and item 2 are stable.
