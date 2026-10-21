# Synthetic demo data (v3 showcase cohort)

`data/synthetic/` holds the synthetic data the app runs on in `BILUN_DATA_MODE=synthetic_demo`: the 9 patients of the v3 showcase cohort, the recipes, pathways, fault registry and reference tables they are built from, and the checks that guard them. Everything here is synthetic or public reference data. Nothing comes from a real patient or a real claim.

The cohort is built from the 9 showcase recipes in `data/synthetic/cohort/showcase_recipes.yaml`, the clinical presentation context in `data/synthetic/cohort/showcase_clinical.yaml`, the care pathways in `data/synthetic/pathways/*.yaml` (and `data/synthetic/faults/siblings/*.yaml`), and the fault registry in `data/synthetic/faults/fault_registry.yaml`.

> **Generated files — do not edit by hand.** Every Parquet table under `sut/claims/` and `sut/clean/`, and `cohort_registry.json`, is built deterministically by `scripts/synthetic/cohort/build.py`. Change the recipes, pathways, faults or reference tables and rebuild; `build --check` fails when a file differs from a fresh build.

## Layout

| Path | Contents |
|---|---|
| `sut/claims/claim_headers.parquet` | 9 showcase claim headers |
| `sut/claims/claim_diagnoses.parquet` | ICD-10 diagnosis rows across the 9 claims |
| `sut/claims/procedure_claim_lines.parquet` | EK-2B and EK-2C procedure lines priced on their service dates |
| `sut/claims/material_claim_lines.parquet` | EK-3/F-1 material lines linked to their surgical procedure lines |
| `sut/claims/drug_claim_lines.parquet` | EK-4A drug lines |
| `sut/claims/expected_rule_outputs.parquet` | 9 answer-key rows derived from `FaultInjectionRecord` entries (a recipe without a fault has none) |
| `sut/claims/patient_copay_profiles.parquet` | 9 patient copay profiles |
| `sut/claims/performed_procedure_lines.parquet` | EMR/PACS performed procedure log lines |
| `sut/claims/medula_rejection_events.parquet` | Empty schema-validated rejection events table |
| `sut/clean/anadata_clean.parquet` | 9 episode clinical records (vitals, diagnoses, comorbidity flags, structured Turkish narratives) |
| `sut/clean/recete_clean.parquet` | 21 prescription records aligned 1-to-1 with billed drug lines; the route of administration (`verilis_yolu`) is read from the TİTCK product name, otherwise from `drug_routes` in `data/synthetic/cohort/showcase_clinical.yaml` |
| `sut/clean/lab_clean.parquet` | 222 lab result rows expanded from billed EK-2B lab procedure lines via `data/synthetic/reference/lab_reference.csv` and `data/synthetic/cohort/showcase_clinical.yaml` |
| `cohort_registry.json` | Claim and clean table digests (`tables_digest`, `clean_tables_digest`), row counts (`counts`, `clean_counts`), named roles (`default_landing`, `showcase_S1`..`showcase_S8`, fixed), `scenarios` (the stories after S8: a patient and the claims of its bills), encounter provenance, and fault injection records |
| `cohort/` | The inputs of the builder: `showcase_recipes.yaml` (patient number, pathway and fault of each encounter) and `showcase_clinical.yaml` (vitals, per-patient lab states, drug routes) |
| `pathways/` | One care pathway per showcase story (see its `README.md`) |
| `faults/` | The fault registry (`fault_registry.yaml`) and the S1 itemized sibling pathway (see its `README.md`) |
| `reference/` | Reference tables and notes the pathways and the lab values draw on: code sets, ICD-10, EK-2B chapters, the drug crosswalk, the lab reference table, public-statistics anchors and their sources |
| `demo_vignettes.json` | Kept byte-identical because the paused strict release lane pins it (`scripts/deploy/generate_candidate_source_roster.py`); no code in `scripts/synthetic/` reads it any more |

The app reads `sut/claims/` through `load_sut_claim_dataset` and `sut/clean/` through `src/bilun/cache/`; `synthetic_demo` mode refuses any directory outside `data/synthetic/sut` (`src/bilun/domain/claims/config.py`).

## The 9 showcase patients

| Patient ID | Claim ID | Story | Pathway | Fault ID | Engine rule |
|---|---|---|---|---|---|
| `SENTETIK-HASTA-0001` | `F-SENTETIK-HASTA-0001-001` | `S1` | `appendicitis_lap_appendectomy_package` | `F_S1_PACKAGE_BILLED_ITEMIZED` | `billing_strategy` |
| `SENTETIK-HASTA-0002` | `F-SENTETIK-HASTA-0002-001` | `S2` | `copd_exacerbation_pneumonia_ward` | `F_S2_BED_DAYS_UNDERBILLED` | `yatak_puani` |
| `SENTETIK-HASTA-0003` | `F-SENTETIK-HASTA-0003-001` | `S3` | `lumbar_stenosis_decompression_itemized` | `F_S3_ANAESTHESIA_LINE_MISSING` | `anestezi_puani` |
| `SENTETIK-HASTA-0004` | `F-SENTETIK-HASTA-0004-001` | `S4` | `pyelonephritis_dementia_delirium_ward` | `F_S4_COMPANION_NOT_BILLED` | `refakatci` |
| `SENTETIK-HASTA-0005` | `F-SENTETIK-HASTA-0005-001` | `S5` | `femoral_neck_fracture_cemented_hemiarthroplasty_package` | `F_S5_IMPLANT_UTS_INCOMPLETE` | `material_bundling` |
| `SENTETIK-HASTA-0006` | `F-SENTETIK-HASTA-0006-001` | `S6` | `aspiration_pneumonia_parkinson_ward` | `F_S6_DRUG_INDICATION_NOT_CODED` | `drug_indication` |
| `SENTETIK-HASTA-0007` | `F-SENTETIK-HASTA-0007-001` | `S7` | `pleuritic_chest_pain_er_pulmonary_embolism_ruled_out` | `F_S7_ER_CT_ANGIO_UNBILLED` | `procedure_capture_gap` |
| `SENTETIK-HASTA-0008` | `F-SENTETIK-HASTA-0008-001` | `S8` | `cholelithiasis_umbilical_hernia_two_packages` | `F_S8_SECOND_PACKAGE_FULL_RATE` | `drg_unbundling` |
| `SENTETIK-HASTA-0009` | `F-SENTETIK-HASTA-0009-001` | `S9` | `lumbar_stenosis_decompression_foraminoplasty_itemized` | `F_S9_SECOND_OPERATION_UNDERBILLED` | `session_uplift` |

The registry names the landing patient and each of the first eight stories as a role: `default_landing` is S1, and `showcase_S1` to `showcase_S8` are the eight claims. The roles are fixed. A story after the eighth (`S9`, ...) is a **scenario**, under the top-level key `scenarios`: `scenarios.S9 = {patient_id, claim_ids}`, the patient and the claims of its bills in bill order (one claim today). A recipe without a fault is a clean bill; it adds no injection record and no answer-key row. A test that needs a patient, a claim or a fault reads it through `tests/fixtures/synthetic_cohort.py` (`role`, `scenario`, counts and injection records from the registry) instead of hard-coding ids.

## Regenerate and check

Regenerate the files in `data/synthetic/` (the tables in `sut/claims/` and `sut/clean/`, and `cohort_registry.json`):

```bash
.venv/bin/python -m scripts.synthetic.cohort.build
```

The output directory is `--out DIR` and defaults to `data/synthetic`. Verify that the committed files match an in-memory build by content (table frames and `cohort_registry.json`):

```bash
.venv/bin/python -m scripts.synthetic.cohort.build --check
```

Two builds with the same Polars version write the same bytes, so a rebuild leaves every tracked file unchanged. Another Polars version may lay the same tables out in other Parquet bytes; `--check` compares by content, so it does not fail on that.

## Engine proof

Run the billing and prose-rules engine proof over the committed dataset:

```bash
.venv/bin/python -m scripts.synthetic.cohort.engine_proof
```

This compares the loaded dataset and the in-memory clean twin against the earlier proofs (`reports/synthetic-data/2026-10-15-showcase-proofs/results/S1.json`..`S9.json`) across totals, user-facing signal multisets, report scalars, and direct detector rows. For `S8`, the full report shows `audit_exposure_try` `3584.80` while the fault record and direct detector call carry `5377.20`, because no claim line carries the incision (`Safa675/Bilun#311` item 6) so the report uses the lenient 50% second-package reading whereas the record carries the same-incision 25% reading. `S9` is the mirror: the report shows the `session_uplift` money at the strictest reading, `151.60` (30% of the second operation, same incision), while the record carries the whole gap to the clean bill, `758.01` (the clean twin bills the separate-incision rate, 50%, and the faulty bill 25%); `KNOWN_REPORT_DIVERGENCES` lists both.

## Coverage metrics

Which of the 20 billing-report blocks and which of the 528 Wave A rule ids do the patients light up? `scripts/synthetic/cohort/coverage_metrics.py` runs the engine's patient report over a claims directory, applies the metric map of `plans/data/2026-10-20-demo-coverage-first-plan.md` section 9.2 (blocks with output, Wave A rule ids evaluated / matched / with a row, finding kinds), writes the numbers per patient and for the cohort as JSON, and prints the difference from an earlier file:

```bash
.venv/bin/python -m scripts.synthetic.cohort.coverage_metrics --out /tmp/before.json
# ... add a story, rebuild the cohort ...
.venv/bin/python -m scripts.synthetic.cohort.coverage_metrics --out /tmp/after.json --compare /tmp/before.json
```

`--claims-dir DIR` measures another claims folder, `--patients ID ...` only those patients. On the 8 patients S1 to S8 it reports 9 of 20 blocks with output, 273 of 528 rule ids evaluated, 14 matched and 14 with a row (`tests/unit/synthetic/test_coverage_metrics.py` pins these). Limits: the report is computed from the claim tables alone, so the patient's `copay_exemption` (the EK-1/A input of the app's cache path) and the lab feed `lab_df_pl` are not passed; a block with output means the engine produced a row, not that the row is right.

## Phase notes

- **Clinical clean tables (`sut/clean/`):** `anadata_clean.parquet` (9 rows), `recete_clean.parquet` (21 rows), and `lab_clean.parquet` (222 rows) are populated deterministically from the showcase claims and clinical registry.
- **Lab results (`sut/clean/lab_clean.parquet`):**
  - One result set per billed EK-2B lab line (14 codes, `parametre` names the result parameter): 222 rows. Patients 5 and 8 have none because their bills are packages; cultures and serology are not L-codes and have no rows.
  - Values come from `data/synthetic/reference/lab_reference.csv` by a deterministic SHA-256 draw of `patient|code|parameter|occurrence|salt` (no random seed, no clock): the central 30 to 70 percent of the sex-specific limits, or 20 to 80 percent of the range of a state.
  - The per-patient states in `data/synthetic/cohort/showcase_clinical.yaml` are judgment (clinician review in issue #309). Repeat samples inside a state are independent draws: there is no automatic trend.
  - Coherence rules: the five differential counts sum to WBC (R1); RBC = HGB·10/MCH, HCT = MCV·RBC/10, MCHC = HGB/HCT·100 (R2); creatinine is inverted from a target eGFR and eGFR is recomputed with CKD-EPI 2021 (R3); HCO3 = 0.0307·pCO2·10^(pH−6.1), BE = 0.93·(HCO3−24.4+14.8·(pH−7.4)) and SaO2 by Severinghaus from pO2 (R4).
  - `anormal_mi` is true outside the sex-specific limits of the CSV (troponin I: M 34.2, F 15.6 ng/L) and for a strip grade other than `Negatif` (R5).

## The legacy 50-patient set

Until P7-lite, `data/synthetic/sut/` held a 50-patient set made by `scripts/synthetic/generate_sut_synthetic_data_v2.py` (the xlsx workbooks, the parquet tables, the Tier A/B/C manifest and `DEMO_COHORT.md`). The set, its generator, its validator and their tests were removed when the showcase patients replaced it. It exists in git history only; `git log --diff-filter=D -- data/synthetic/sut/sentetik_sut_v2_50_hasta.xlsx` finds the commit that removed it, and its parent still has the files.
