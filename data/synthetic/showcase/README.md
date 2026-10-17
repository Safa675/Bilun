# Synthetic showcase cohort dataset (v3, P4)

This directory contains the generated synthetic v3 showcase dataset produced from the 8 showcase recipes in `data/synthetic/cohort/showcase_recipes.yaml`, the care pathways in `data/synthetic/pathways/*.yaml` (and `data/synthetic/faults/siblings/*.yaml`), and the fault registry in `data/synthetic/faults/fault_registry.yaml`.

> **Generated files — do not edit by hand.** Every Parquet table under `sut/claims/` and `cohort_registry.json` is built deterministically by `scripts/synthetic/cohort/build.py`.

## Layout

| Path | Contents |
|---|---|
| `sut/claims/claim_headers.parquet` | 8 showcase claim headers |
| `sut/claims/claim_diagnoses.parquet` | ICD-10 diagnosis rows across the 8 claims |
| `sut/claims/procedure_claim_lines.parquet` | EK-2B and EK-2C procedure lines priced on their service dates |
| `sut/claims/material_claim_lines.parquet` | EK-3/F-1 material lines linked to their surgical procedure lines |
| `sut/claims/drug_claim_lines.parquet` | EK-4A drug lines |
| `sut/claims/expected_rule_outputs.parquet` | 8 answer-key rows derived from `FaultInjectionRecord` entries |
| `sut/claims/patient_copay_profiles.parquet` | 8 patient copay profiles |
| `sut/claims/performed_procedure_lines.parquet` | EMR/PACS performed procedure log lines |
| `sut/claims/medula_rejection_events.parquet` | Empty schema-validated rejection events table |
| `cohort_registry.json` | Table digests, row counts, named roles (`default_landing`, `showcase_S1`..`showcase_S8`), encounter provenance, and fault injection records |

## The 8 showcase patients

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

## Regenerate and check

Regenerate the files in `data/synthetic/showcase/`:

```bash
.venv/bin/python -m scripts.synthetic.cohort.build
```

Verify that the committed files match an in-memory build by content (table frames and `cohort_registry.json`):

```bash
.venv/bin/python -m scripts.synthetic.cohort.build --check
```

## Phase notes

- **Clinical clean tables (`sut/clean/`):** `anadata_clean.parquet`, `lab_clean.parquet`, and `recete_clean.parquet` arrive in the next slice (P4 Slice C).
- **Legacy cohort replacement (P7):** The legacy 50-patient dataset under `data/synthetic/sut/` remains in place until phase P7 swaps the generated v3 cohort into `data/synthetic/sut/`.
