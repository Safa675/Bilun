# Drug-Indication Rule Validation Harness

Validates Bilun's 967 drug_indication rules against **real prescription data**
from the ILAY hospital corpus, replacing synthetic test data.

## What it does

1. Loads 3.7M ILAY prescriptions, filters to the 68 drugs that match the rule corpus
2. Joins each prescription to its encounter diagnosis via episode ID
3. Builds Bilun `ClaimHeader` + `DrugClaimLine` objects from each pair
4. Runs every prescription through `evaluate_drug_indication_line()` with all 967 rules
5. Records every violation: drug, diagnosis, rule_id, violation_kind, severity
6. Produces a per-rule compliance report

## Why

Bilun's drug_indication rules were tested against 255 synthetic claim rows.
This harness tests them against **~44,000 real prescriptions** — actual
prescribing patterns from a Turkish hospital system. This surfaces:

- **Dead rules** — SUT rules that no real prescription triggers
- **False positives** — rules that fire on legitimate prescriptions
- **Off-label patterns** — drugs prescribed for diagnoses not in the SUT-approved list
- **Coverage gaps** — rule-relevant drugs that never appear in real data

## Usage

```bash
cd /home/safa/Documents/Bilun
python -m scripts.validation.validate_drug_rules
```

Runtime: ~5-10 minutes. No GPU, no cloud. Pure Python regex matching.

## Output

Outputs are derived from real prescriptions (the violation logs carry pseudonymized
patient and visit IDs), so they never go into this repo (KVKK). They are written to
`$BILUN_ILAY_VALIDATION_DIR` (default `~/bilun-local/ilay-validation`); a path inside the
repo is refused (`output_paths.py`), `.gitignore` covers the old repo folders, and
`tests/unit/test_no_real_patient_data_paths.py` fails if they are tracked again.

```
$BILUN_ILAY_VALIDATION_DIR/ilay_validation/
├── violation_log.parquet    # one row per prescription × fired rule
└── rule_compliance.csv      # per-rule: did it match? what fired? is it dead?
```

## Data flow

```
ILAY-Health/data/clean/
├── recete_clean.parquet      (3.7M prescriptions)
└── anadata_clean.parquet     (4M encounters, with TANIKODU)
         │
         ▼
    rx_loader.py
    ─ filter to 68 rule-matched drugs
    ─ join prescriptions ↔ diagnoses via episode ID
    ─ clean ICD-10 labels
         │
         ▼
    ~44K drug-diagnosis pairs
         │
         ▼
    claim_builder.py  →  ClaimHeader + DrugClaimLine (Tier-B fields = None)
         │
         ▼
    evaluate_drug_indication_line()  ←  967 rules from drug_indication_prose.json
         │
         ▼
    violation_log + rule_compliance
```

## Files

| File | Purpose |
|---|---|
| `rx_loader.py` | Load ILAY prescriptions, join to diagnoses, filter to rule-relevant drugs |
| `claim_builder.py` | Build Bilun claim objects from ILAY rows (mirrors test pattern) |
| `validate_drug_rules.py` | Main harness (item 1): diagnosis-dimension validation |
| `validate_specialty_rules.py` | Specialty-scope harness (item 2): prescriber-specialty validation |
| `build_golden_dataset.py` | Extract Bilun-format golden test cases (use `--specialty` for item 2) |

## Notes

- The raw ILAY data stays in `ILAY-Health/data/clean/` and is read by absolute path. The
  outputs derived from it stay outside every repo too (see Output). Until 2026-10-15 they
  were committed under `data/synthetic/sut/claims/ilay_validation/` and
  `data/gazette/prose_rules/golden/ilay/`; they were removed from the tree then
  (`plans/security/2026-10-14-remove-ilay-real-data-plan.md`).
- Tier-B clinical fields (board report, biomarkers, prior therapies) are left as `None`,
  which triggers the realistic "needs_*_verification" review path. This mirrors the
  state of a real hospital claim before HIM review.
- The 68 matched drugs are specialty/chronic meds (PLAVIX, SYMBICORT, HUMIRA, etc.) —
  exactly the drugs the SUT §4.2 rules regulate. Common antibiotics/analgesics
  (AUGMENTIN, PAROL) have no rules to validate.

---

# Item 2 — Specialty Scope Validation

## What it does

Tests Bilun's 366 specialty-restricted drug_indication rules against real ILAY
prescribing data joined to hospital departments. Mirrors item 1's architecture
but validates the **prescriber_specialty** dimension instead of the diagnosis
dimension.

## Why

Some SUT rules gate drugs on specialist scope ("must be prescribed by
kardiyoloji / romatoloji / etc."). Item 1 didn't test this dimension because
the `prescriber_specialty` field was `None`. Item 2 fills that gap by feeding
the encounter's `SERVISADI` (department) into the same field the engine checks.

## Usage

```bash
cd /home/safa/Documents/Bilun
python -m scripts.validation.validate_specialty_rules         # produces violation log
python -m scripts.validation.build_golden_dataset --specialty # extracts golden test cases
```

Runtime: ~20 seconds. Faster than item 1 because only ~16K prescriptions are
in scope (vs 18K for item 1) and only specialty-restricted rules are loaded.

## Output

```
$BILUN_ILAY_VALIDATION_DIR/ilay_validation/
├── specialty_pairs.parquet             # intermediate: prescription × department join
├── specialty_violation_log.parquet     # one row per prescriber_specialty_mismatch
└── specialty_rule_compliance.csv       # per-rule: violations, top violating departments

$BILUN_ILAY_VALIDATION_DIR/golden_ilay/
└── specialty_ilay_*.json               # golden cases, local use only
```

CI covers the same three specialty rules with synthetic cases in
`tests/unit/domain/prose_rules/test_specialty_scope_cases.py`.

## Verified numbers (first run)

| Metric | Value |
|---|---|
| Specialty-restricted drug_indication rules | 366 (of 930 total) |
| Rules with non-empty `drug_names` | 341 |
| Specialty-rule drug tokens appearing in ILAY | 39 |
| ILAY prescriptions joined to a department | 15,887 |
| Unique departments in joined data | 60 |
| **Specialty mismatches fired by Bilun's engine** | **53** |
| Golden test cases extracted | 8 (across 3 rules) |

## Honest findings & limitations

### Finding 1: The engine's `prescriber_specialty` matching has a substring-collision bug

43 of the 53 mismatches are caused by **string-matching false positives** in
Bilun's `_specialty_matches` function (`src/bilun/domain/prose_rules/drug_indication.py:83`).

The function does naive substring matching: `token in normalized_actual`.

| Actual department | Rule token | Should match? | Does match? |
|---|---|---|---|
| `Kalp ve Damar Cerrahisi (KVC)` | `kalp damar cerrahisi` | ✅ Yes | ❌ No (the `ve` breaks substring) |
| `Kalp ve Damar Cerrahisi (KVC)` | `kardiyoloji` | ❌ No (different dept) | ❌ No |

Result: KVC prescribing PLAVIX (clopidogrel) fires 40 violations even though
the rule explicitly lists "kalp damar cerrahisi" as an allowed specialty. This
is a Bilun engine bug surfaced by the harness.

### Finding 2: Real specialty-scope violations are rare in this dataset

After excluding the false-positive cluster, only ~10 actual prescribing scope
violations exist:

- 5 cases of `Kardiyoloji` prescribing **CYMBALTA** (duloxetine, requires
  endokrinoloji or nöroloji)
- 4 cases of `İç Hastalıkları` prescribing **CYMBALTA**
- 1 case of `Damar Cerrahisi` prescribing PLAVIX

### Finding 3: Investigation vs engine output divergence

The pre-build investigation showed Internal Medicine prescribing specialty
drugs (PLAVIX, LYRICA, SYMBICORT) in 4-43% of cases — but the engine did NOT
flag most of these as violations. Why? Because many specialty rules ALLOW
"iç hastalıkları" as an authorized specialty. The investigation was
looking at where drugs are prescribed; the engine checks whether that
department is in the rule's allowed list. The two questions have different
answers.

### Caveat: Department ≠ individual doctor's board specialty

`SERVISADI` is the clinic the patient visited, not the doctor's diploma.
A patient could see an Internal Medicine doctor who holds a cardiology
subspecialty — the data would show "İç Hastalıkları" but the doctor is
board-certified in cardiology. This creates unavoidable false positives in
the engine output.

### Caveat: 69% of prescriptions cannot be evaluated

Only 31% of prescription episodes link to encounter departments. The other
69% come from external pharmacies or unstructured workflows not logged as
encounters. This biases the results toward in-hospital prescribing patterns.

## SERVISADI → rule specialty mapping (observed)

The most common departments and how they align with rule specialty tokens:

| SERVISADI | Rule tokens that match | Notes |
|---|---|---|
| `İç Hastalıkları` | `iç hastalıkları` | Direct match, very common allowed specialty |
| `Kardiyoloji` | `kardiyoloji` | Direct match |
| `Göğüs Hastalıkları` | `göğüs hastalıkları` | Direct match |
| `Kulak Burun Boğaz` | `kulak burun boğaz`, `kbb` | Direct match |
| `Romatoloji` | `romatoloji` | Direct match |
| `Nöroloji` | `nöroloji` | Direct match |
| `Çocuk Sağlığı ve Hastalıkları` | `çocuk sağlığı`, `çocuk sağlığı ve hastalıkları` | Direct match |
| `Kalp ve Damar Cerrahisi (KVC)` | `kalp damar cerrahisi` | ⚠️ Substring collision — "ve" breaks match |
| `Fizik Tedavi ve Rehabilitasyon` | `fiziksel tıp`, `fizik tedavi` | ⚠️ Different terms — may not match |
| `Acil Servis` | `acil tıp`, `acil` | Direct match |

The KVC mismatch is the dominant source of false positives. Fixing it (by
extending `_specialty_matches` to handle Turkish "ve" between words, or by
adding "Kalp ve Damar Cerrahisi" as an alias token) would drop the violation
count from 53 to ~10.

## Recommendation for Bilun product

The specialty-scope dimension is **less valuable than the diagnosis dimension**
(item 1) for these reasons:

1. The signal-to-noise ratio is poor (43/53 violations are engine bugs)
2. The rule corpus uses inconsistent terminology vs hospital department names
3. Real prescribing scope violations are rare in this outpatient dataset
4. The golden dataset is small (8 cases vs item 1's 89)

**Recommended use**: Ship the harness as a one-shot audit tool, not a
continuous CI check. The 8 golden cases can be added to Bilun's test suite
manually. The bigger value is the **finding** — Bilun's `_specialty_matches`
function needs improvement before specialty-scope checks are reliable enough
to ship to hospital customers.
