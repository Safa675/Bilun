---
title: "Resmi Gazete -- SUT Regulatory Data"
aliases: ["gazette", "resmi-gazete", "sut-gazette", "sgk-gazette"]
tags: [data, sut, turkish-healthcare, compliance, status/provisional]
type: core-system
status: provisional
source: "data/gazette/"
sources:
  - "data/gazette/raw/"
  - "data/gazette/curated/"
  - "data/gazette/snapshots/"
  - "data/gazette/version_manifest.parquet"
  - "scripts/sut/README.md"
last_compiled: 2026-04-16
model: "claude-opus-4-6"
llm_summary: "37 curated gazette parquets (115K rows from 393 SGK documents, 444 manifest entries) encode Turkish SUT pricing/billing rules — no PHI, publicly available regulatory data."
llm_keywords: [gazette, sut, sgk, regulatory-data, pricing, ek-2b, ek-4a]
llm_questions:
  - "What is the gazette data?"
  - "How many SUT codes are there?"
  - "Does gazette require patient data?"
  - "What is EK-2B?"
related: ["[[sut]]", "[[sgk-sut-regulatory-context]]"]
---

# Resmi Gazete -- SUT Regulatory Data

## Key Facts

- **Rows**: 115,568 across 37 curated parquets. 393 unique source gazette documents (444 manifest entries) tracked.
- **EK-2B**: 7,129 procedure codes (point-based pricing, primary lookup for SUT engine).
- **EK-4A**: 8,428 drugs (tier classification, generic substitution, reimbursability).
- **EK-3**: 3,265 materials across 30 parquet files (22 non-empty, 27 specialty catalogs). 8 annex files are empty (0 rows).
- **No PHI**: Public regulatory data only. Enables SUT commercial wedge (no hospital data partnership required).

The gazette data source is a committed-in-repo copy of Turkey's **Sağlık Uygulama Tebliği** (SUT) regulatory tariff catalogs, sourced from SGK's Resmi Gazete publications and curated into queryable parquet files. It is the data foundation for the [[sut]] pricing and billing engine and is the only data layer in ILAY that requires no PHI.

> [!note] Correct path
> The gazette data lives under `data/gazette/`, not `data/sut/gazette/`. Some historical references in other wiki articles may use the older path.

## Directory layout

```
data/gazette/
├── raw/                        # XLSX → parquet conversions, partitioned
│   └── annex=<CODE>/
│       └── effective_date=<YYYY-MM-DD>/
│           └── <source-file>__<sheet>.parquet
├── curated/                    # 37 cleaned single-purpose catalogs
│   ├── ek2a_outpatient_visits.parquet
│   ├── ek2b_catalog_history.parquet
│   ├── ek2c_catalog_history.parquet
│   ├── ek2c1_copay_rates.parquet
│   ├── ek2g_no_surcharge.parquet
│   ├── ek1a_chronic_exemptions.parquet
│   ├── ek3a_multibranch_materials.parquet
│   ├── ... (27 specialty catalogs) ...
│   └── ek4a_drugs.parquet
├── snapshots/                  # Point-in-time all-annex bundles
│   └── asof_<YYYY-MM-DD>/
│       ├── snapshot_manifest.parquet
│       ├── EK-2A.parquet
│       ├── EK-2B.parquet
│       ├── ... (~32 annex files per snapshot)
│       └── EK-3T.parquet
└── version_manifest.parquet    # cross-annex version tracking
```

## Annex catalog (what each EK-code is)

| Annex | Curated file | Content |
|---|---|---|
| EK-1A | `ek1a_chronic_exemptions.parquet` | Chronic-disease copayment exemption list |
| EK-2A | `ek2a_outpatient_visits.parquet` | Outpatient visit billing codes |
| EK-2B | `ek2b_catalog_history.parquet` | Procedure pricing (point-based, 7,129 codes) — primary source for `src/bilun/domain/catalog.py` |
| EK-2C | `ek2c_catalog_history.parquet` | DRG package pricing by ICD-10 chapter |
| EK-2C-1 | `ek2c1_copay_rates.parquet` | Explicit copayment rate table |
| EK-2G | `ek2g_no_surcharge.parquet` | No-surcharge procedure list |
| EK-3A | `ek3a_multibranch_materials.parquet` | Cross-discipline medical materials |
| EK-3B1 | `ek3b1_bundled_consumables.parquet` | Bundled (non-separately-billable) consumables |
| EK-3B2 | `ek3b2_non_reimbursable.parquet` | Non-reimbursable materials |
| EK-3C1–C5 | `ek3c{1..5}_materials.parquet` | Externally-worn prostheses, orthoses, sarf malzeme |
| EK-3D | `ek3d_vision_materials.parquet` | Vision-aid materials |
| EK-3E-1 / E-2 | spine / cranial surgery materials | |
| EK-3F-1..F-4 | arthroplasty / arthroscopy / tumor-resection / trauma-reconstruction | |
| EK-3G | `ek3g_ophthalmology_materials.parquet` | Ophthalmology materials |
| EK-3H | `ek3h_cardiology_materials.parquet` | Cardiology materials |
| EK-3I | `ek3i_cv_surgery_materials.parquet` | Cardiovascular surgery materials |
| EK-3J | `ek3j_ent_materials.parquet` | Ear, nose, throat materials |
| EK-3K | `ek3k_obgyn_materials.parquet` | Obstetrics/gynaecology materials |
| EK-3L | `ek3l_urology_materials.parquet` | Urology materials |
| EK-3M | `ek3m_radiology_materials.parquet` | Radiology + endovascular/non-vascular interventional materials |
| EK-3N-1..N-3 | allograft / xenograft / synthetic graft | |
| EK-3O | `ek3o_hematology_oncology_materials.parquet` | Hematology-oncology materials |
| EK-3P | `ek3p_nephrology_materials.parquet` | Nephrology materials |
| EK-3R | `ek3r_gastroenterology_materials.parquet` | Gastroenterology materials |
| EK-3S | `ek3s_pulmonology_materials.parquet` | Pulmonology materials |
| EK-3T | `ek3t_anesthesiology_materials.parquet` | Anesthesiology, reanimation, pain therapy materials |
| EK-4A | `ek4a_drugs.parquet` | Reimbursable drug catalog |
| (EK-4B / EK-4C) | raw only | Nutritional products; foreign drug list |

Total: **37 curated parquets** (as of 2026-04-14). Raw parquets under `data/gazette/raw/annex=...` include many historical effective dates per annex (`MULGA_EK-4-A_*` entries under `raw/annex=EK-4/`) that the curated layer deduplicates.

## Three layers, three purposes

### `raw/` — source of truth

Every XLSX file published in Resmi Gazete is converted into a parquet under `raw/annex=<CODE>/effective_date=<YYYY-MM-DD>/`. One file per (source XLSX × sheet). Produced by `scripts/sut/convert_xlsx_to_parquet.py`. Maintains `version_manifest.parquet` to track what has been ingested.

### `curated/` — cleaned single-purpose catalogs

37 files with `valid_from` / `valid_to` temporal columns. Each is the authoritative lookup for one pricing/billing concept. These are what [[sut]] loads at runtime. Produced by `scripts/sut/build_curated_catalogs.py` (extractors in `scripts/sut/catalogs/`).

### `snapshots/asof_<DATE>/` — point-in-time bundles

For a given `asof_date`, each annex's latest effective-date parquet is written into a single bundle directory. Used when the downstream consumer needs a consistent-as-of view without the temporal columns. Produced by `scripts/sut/build_asof_snapshot.py`. Current latest snapshot: `asof_2026-01-31/` (~32 parquets).

## Version manifest

`data/gazette/version_manifest.parquet` tracks every XLSX ever ingested: source filename, annex code, effective date, sheet name, row/col counts, hash. This file is how the conversion pipeline decides what is new vs already-processed on each run.

## Why this data is special

- **No PHI.** The gazette is publicly published regulatory data. This makes [[sut]] the only ILAY product layer that can be sold without a hospital data-sharing agreement.
- **Temporal validity matters.** Prices change on gazette effective dates; billing decisions must use the tariff valid on the service date, not the latest. The `valid_from`/`valid_to` columns in curated catalogs and the raw effective-date partitioning both preserve this.
- **Machine-readable on day one.** The ministry publishes the gazette as XLSX. The ETL pipeline exists so downstream code never touches XLSX directly.

## See also

- [[sut]] — the regulatory engine that queries these parquets at runtime
- [[sgk-sut-regulatory-context]] — regulatory background and how SGK's billing system works
- `scripts/sut/README.md` — full ETL script inventory and execution order
