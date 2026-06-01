## Task: Refactor Synthetic Data v2 Generator

### Goal
Break `scripts/synthetic/generate_sut_synthetic_data_v2.py` (1229 lines, one monolithic file) into 5 focused modules with a thin CLI entry point. Zero behavioral changes — same seed produces identical RNG output (row counts, data columns). Files are not byte-identical because the manifest includes a wall-clock timestamp (`olusturulma_zamani`).

### Import Convention
Entry point is `python scripts/synthetic/generate_sut_synthetic_data_v2.py`, which puts `scripts/synthetic/` on `sys.path`. All sibling imports use flat style:
```python
from constants import SEED, DEFAULT_OUTPUT_DIR
from catalog import _ek2b, _ek2c_latest
from generators import build_workbook_tables
```
No `from .constants import ...` (no package-mode `-m` invocation).

### Subtasks

- [ ] **1. Extract `constants.py`** — all immutable configuration and data:
  - `SYNTHETIC_NOTICE`, `SEED`, paths (`PROJECT_ROOT`, `DEFAULT_OUTPUT_DIR`, `GAZETTE_DIR`, `CURATED_DIR`, `EK2B_PATH`)
  - `ICD10_CHAPTER_TO_DRG_GROUP` mapping
  - `SCENARIO_TEMPLATES` list of 8 specialty dicts
  - `TURKISH_FEMALE_NAMES`, `TURKISH_MALE_NAMES`, `TURKISH_SURNAMES`
  - ~100 lines

- [ ] **2. Extract `catalog.py`** — all gazette catalogue loading functions:
  - `_GAZETTE_CACHE` (module-level dict)
  - `_gazette()`, `_ek2b()`, `_ek2c_latest()`, `_ek2c1()`, `_ek2g()`, `_ek4a()`, `_ek3_material()`, `_ek1a()`
  - `_drug_unit_price()`, `_money()`
  - ~170 lines

- [ ] **3. Extract `generators.py`** — all data generation functions:
  - `_generate_patients()`
  - `_assign_scenarios()`
  - `_drg_group()` (currently nested inside `_generate_claims_and_lines`, lift to module-level alongside `_pick_procedures`)
  - `_pick_procedures()` (currently inner function, lift to module-level)
  - `_generate_claims_and_lines()` — **further decomposed** using a `@dataclass` for shared state:
    - Define `ClaimEpisodeContext` dataclass holding: `episode` fields, `claim_id`, `visit_type`, `facility_tier`, `is_university`, `provider`, `admission`, `discharge`, `claim_end`, `start_date`, `package_candidate`, catalog lookups (`ek2g_no_surcharge`, `ek2c1_copay_rates`, `ek2c_packages`, `ek3_all`, `active_drugs`), `rng`, `scenario_tag`, and mutable output lists (`procedure_rows`, `materials`, `drug_claims`, `expected`, `lab_billing_budget` — passed by reference).
    - `_append_procedure_lines_for_claim(ctx, proc_specs)` — processes one episode's procedures, returns `(total_billed_delta, total_payable_delta)`, appends to `ctx.procedure_rows` / `ctx.expected` / `ctx.lab_billing_budget`
    - `_append_material_lines_for_claim(ctx)` — processes one episode's materials using `ctx.template.material_catalogs`, returns totals delta, appends to `ctx.materials` / `ctx.expected`
    - `_append_drug_lines_for_claim(ctx)` — processes one episode's drugs from `ctx.active_drugs`, returns totals delta, appends to `ctx.drug_claims` / `ctx.expected`
    - `_generate_claims_and_lines()` becomes orchestrator: constructs `ClaimEpisodeContext` per episode, calls `_pick_procedures`, then calls the three `_append_*_for_claim` functions, finalizes claim-level record.
  - `_generate_prescriptions()`
  - `_generate_lab_results()`
  - `build_workbook_tables()` — top-level orchestrator
  - ~760 lines

- [ ] **4. Extract `exporters.py`** — all output/export functions:
  - `_normalize_for_parquet()`
  - `_clean_anadata()`, `_clean_lab()`, `_clean_recete()`
  - `_write_workbook()`
  - `_write_clean_exports()`
  - `_english_claim_exports()` — with column rename dicts (these stay inline, not a separate file)
  - `_write_claim_exports()`
  - ~300 lines

- [ ] **5. Slim `generate_sut_synthetic_data_v2.py`** to CLI-only:
  - `parse_args()`
  - `main()` — imports and calls `build_workbook_tables()` + exporters
  - ~40 lines

- [ ] **6. Verify zero behavioral change:**
  - **Step 6a (pre-refactor baseline):** Before touching any code, snapshot baseline:
    ```bash
    python scripts/synthetic/generate_sut_synthetic_data_v2.py --num-patients 50 --seed 20260504
    cp -r data/synthetic/sut /tmp/sut_baseline_refactor
    ```
  - **Step 6b (post-refactor):** Run same command after refactor.
  - **Step 6c (diff):** Compare baseline vs post-refactor excluding the manifest timestamp:
    - Compare row counts per Parquet file (should be identical)
    - Compare data column checksums (hash each column's values, should match)
    - Run the validator on post-refactor output
  - Success = identical row counts, identical data column hashes, validator passes. Byte-identical files are NOT expected due to `olusturulma_zamani` in the manifest.

### Out of Scope
- Changing any generation logic, output format, or CLI interface
- Touching `validate_sut_synthetic_data.py`
- Adding new features or fixing bugs — pure structural refactor

### Target Structure
```
scripts/synthetic/
├── __init__.py
├── generate_sut_synthetic_data_v2.py    → CLI (parse_args + main)
├── validate_sut_synthetic_data.py       → unchanged
├── constants.py                          → config, templates, names
├── catalog.py                            → gazette loading functions
├── generators.py                         → patient, scenario, claim, lab, prescription generators
└── exporters.py                          → clean exports, claim exports, workbook writing
```
