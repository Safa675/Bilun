# SUT package 2026-10-02: ingestion completed (2026-10-13)

**Outcome:** `data/gazette/ingest_state.json` moves from `completion_scope: partial` to `complete` with `last_ingested_date: 2026-10-02`. The prose corpus, the EK-4A snapshot catalog, the EK-4A history and the clause diff did not change byte for byte. The package differs from the 2026-08-29 one in six files, and about nine rows carry values.

Tracking issue: Safa675/Bilun#217. Plan: `tasks/todo.md`, "Complete the ingestion of the 2026-10-02 SUT package".

## Source

| Item | Value |
|---|---|
| Announcement | https://www.sgk.gov.tr/duyuru/detay/02102026-SUT-Degisiklik-Tebligi-Islenmis-Guncel-2013-SUT-2026-10-02-02-50-06 |
| ZIP | `https://www.sgk.gov.tr/Download/DownloadFile?f=8ee647e7-923a-448b-8eac-a91772f34a78.zip&d=f5bf9aae-c24d-4bcd-aa89-6f870210736a`, 32,973,194 bytes |
| ZIP sha256 | `03bf37df87ff48358e23b1018405405bbb436032c9424b17ddbcb828525f7a61` (the value pinned before this work) |
| Files | 349: 318 workbooks (96 `.xls`, 222 `.xlsx`), 17 `.docx`, 14 `.doc` |
| Workbooks | 49 current lists, 269 MÜLGA (repealed) lists. The converter skips MÜLGA by design. |
| Inventory | `raw data/2026.10.02-…/.sut_package_inventory.json`, written by `scripts/sut/sut_fetch.py` |

Environment: the reviewed CI image `bilun-laptop-ci:20261008-runtime-complete` with `requirements-ci.lock` installed offline (Python 3.13.15, pandas 3.0.6, polars 2.0.0, pyarrow 25.0.1). The hosted SUT Monitor workflow cannot run (disabled; see "Findings"), so every step ran by hand.

## What changed against the 2026-08-29 package

341 of 349 files are byte-identical. The consolidated DOCX and the repealed `MÜLGA EK-4A … (Yür. 02.10.2026)` workbook are new and were already in the repo before this work. Six files differ; all but EK-1A cite Resmi Gazete 02/10/2026 no. 33388.

| File | Change | Effective |
|---|---|---|
| EK-1A (`.xls`) | The row "Kronik Tübülo-İnterstisyel Nefrit" gains the code **N11**. The curated exemption list grows 97 to 98 rows. | no marker |
| EK-2B | **+608310** (Bronkoskopi, 1,073.67 puan; amended, art. 3-a) and **+609541** (Özofagus atrezi primer onarımı, torakoskopik, 25,278.02 puan; added, art. 3-b). | 2026-10-10 |
| EK-2C | **+P608310** (group D, 5,456.7) and **+P609541** (group A3, 215,007.17). The code-less "Kemik İliği Nakilleri" package row now appears three times: the original text, the 29/08 amendment, and a new amendment (art. 4-b) that restores the clause "diğer nakillerde nakil öncesi 15 günü ve nakil sonrası 60 …" which the 29/08 text omits. The 29/08 row is also re-emitted with whitespace changes only. | 2026-10-10; 2026-09-05 for the bone-marrow row |
| EK-3O | HO1000 FOTOFEREZ SETİ gains the marker "(Ek: RG-02/10/2026-33388/5 md. Yürürlük: 08/10/2026)" and a new clause "(3) SUT’un 2.4.4.Ç maddesine bakınız." The price is unchanged. | 2026-10-08 |
| EK-4A | The drug list; already handled by #222 and the service-date history. | |
| EK-4G (`.doc`) | **92. Satralizumab** added (art. 7). The converter has no `.doc` support, so no data table holds it. | 2026-10-10 |

Cell-level diff: Polars multiset comparison of every sheet (openpyxl/xlrd values), and of each rewritten raw partition without `__source_file` and `__ingested_at`. The two agree.

## What the pipeline did

| Step | Result |
|---|---|
| `sut_fetch.py` | 349 files verified; the three files already committed were unchanged. |
| `convert_xlsx_to_parquet.py --defer-state` | 49 sheets, 0 failures, manifest 328 rows (unchanged count). 48 raw partitions rewritten: 44 provenance only (`__source_file` now names the 2026-10-02 folder), 4 with values (EK-1A, EK-2B, EK-2C, EK-3O). EK-4A raw was not rewritten. |
| `build_curated_catalogs.py --overwrite` | 39 specs ok, 1 error: the EK-4A snapshot ("marker-dated rows; admit only with an explicit as_of"), by design (#208). Curated files changed: `ek1a_chronic_exemptions`, `ek2c_catalog_history`, `ek3o_hematology_oncology_materials`. `ek2b_catalog_history` did not change (see F2). |
| `sut_ingest_state.py --prepare-corpus` | Exit 0; re-extraction equals the committed corpus, so `sut_clauses.parquet` was not written. |
| `sut_clause_diff.py` (legacy receipt) | Preserved: 8,375 stable, 42 amended, 0 new, 0 removed. |
| `sut_delta.py 2026-08-29 2026-10-02` | `deltas/2026-10-02_delta.json` created (read F1 before using it). |

Files that had to stay identical, checked before and after (`sha256sum -c`): `sut_clauses.parquet`, `curated/ek4a_drugs.parquet` (still the 2026-05-23 snapshot, `6ed75694…`), `deltas/2026-10-02_clause_diff.json`, `curated/ek4a_history.parquet`, `curated/ek4a_windows.parquet`, `ek4a_announcements.json`, `sut_coverage_evidence.json`, `src/bilun/domain/constants.py`.

## Findings (not fixed here)

**F1. The annex delta cannot see in-place amendments.** `sut_delta.py` compares as-of slices of the current curated files. 2026-08-29 and 2026-10-02 both resolve to the list effective 2026-07-07, so ek2b, ek2c and ek2c_dental report 0 changes although EK-2C gained P609541. Use the raw-level table above as the review delta. Snapshot annexes need the previous delta's `content_hash` for comparison: only `ek1a` and `ek3o` differ from `2026-08-29_delta.json`.

**F2. `extract_ek2b` drops every row whose code cell carries an amendment marker** (`scripts/sut/catalogs/price_history.py:16,97`: the code must match `^(L\d{6}|R\d{6}|G\d{6}|[5-9]\d{5})$`). `extract_ek2c` strips the marker first (`:115-117`), so EK-2C keeps them. In the EK-2B version effective 2026-07-07, 51 marker rows are lost: 30 procedures that are in no curated version (28 added by RG-29/08/2026-33355, one by RG-29/06/2026, and 609541 by this package) and 21 amendments whose older clean row stays (prices equal). Fixing it changes `ek2b_catalog_history.parquet` and everything pinned to it, so it needs its own change.

**F3. Row-level effective dates are not used; the list's file-level date is.** The new rows carry "Yürürlük: 10/10/2026" (the EK-2B and EK-2C procedures), 05/09/2026 (the bone-marrow row) and 08/10/2026 (the EK-3O clause), but they sit in the list dated 2026-07-07, and the runtime readers keep a row when its file-level `effective_date` is on or before the service date (`src/bilun/domain/loaders/gazette.py:138-146`, `src/bilun/domain/prose_rules/catalog_membership.py:103-119`). So P609541 is eligible for service dates from 2026-07-07, three months before it took effect, and EK-1A N11 and the EK-3O clause (no date column) apply to every date. A claim dated 2026-07-07 to 2026-10-09 can therefore be priced or exempted by a row that did not exist yet. EK-4A has been protected against exactly this since #208; EK-1A, EK-2B, EK-2C and EK-3O are not.

**F4. EK-4G has no data table.** Satralizumab (no. 92) is only in the `.doc`.

**F5. The SUT Monitor workflow is disabled** (`disabled_manually`; its last run, a manual dispatch on 2026-10-10, failed; `reports/sut-ingest/2026-10-10-ek4a-service-date.md` records that hosted runners refuse jobs for this account). New announcement issues appear only when `scripts/sut/sgk_watch.py` is run by hand.

## Verification (2026-10-13)

| Check | Result |
|---|---|
| `ruff check src/ scripts/` (CI image, lock environment) | passed |
| `python -m pytest -q -n 4` | 8,306 passed, 20 warnings (run on the final commit) |
| `python scripts/sut/compile_rules.py --check` | exit 0 |
| `python scripts/sut/audit_manifest_parity.py --drug-only` | exit 0 |
| `git status` after the test run | no tracked file mutated |
| Files that must not change (corpus, EK-4A snapshot and history, clause diff, announcements, coverage evidence, `constants.py`) | byte-identical |
| `python scripts/sut/sgk_watch.py --dry-run` | baseline 2026-10-02: 13 relevant announcements, 9 with an issue, 0 new. The 4 without an issue are dated 2026-08-12 to 2026-08-29, so the new baseline hides none. |

An independent agent re-derived the numbers above from git and reproduced them: the 48 partitions (44 provenance-only, 4 with values), the three curated diffs, F1, F2, the `ingest_state.json` fields and the receipt byte for byte. It also found two wrong statements in the first version of this report (the EK-3O clause (3) and the EK-2C bone-marrow row) and the runtime impact in F3; all three are corrected above.

F1 to F4 are recorded only here; no issue tracks them yet.

## EK-4A component receipt (removed from `ingest_state.json` on completion)

Copied verbatim before `complete_ingestion` dropped `component_receipts`. The `prose` receipt is also kept; `completed_package` in `ingest_state.json` now carries the package-level hashes.

```json
{
  "prose": {
    "source_docx": "raw data/2026.10.02-Değişiklik Tebliği İşlenmiş Güncel 2013 SUT/2026.10.02-Değişiklik Tebliği İşlenmiş Güncel 2013 SUT/02.10.2026 - Değişiklik Tebliği İşlenmiş Güncel 2013 SUT.docx",
    "source_docx_sha256": "227b508558840f6c8083c6b6cc8c4efcbf1fcf342e115df5519b0f3e63d7f573",
    "corpus_sha256": "40b2b7ebdb44c2483867d5413f7af3d97bb55c92d43d3a4be2737d80135425ec",
    "corpus_rows": 8413,
    "source_snapshot_date": "2026-10-02",
    "status": "verified_existing_corpus"
  },
  "EK-4A": {
    "source_publication_url": "https://www.sgk.gov.tr/Download/DownloadFile?f=8ee647e7-923a-448b-8eac-a91772f34a78.zip&d=f5bf9aae-c24d-4bcd-aa89-6f870210736a",
    "source_zip_sha256": "03bf37df87ff48358e23b1018405405bbb436032c9424b17ddbcb828525f7a61",
    "source_package_date": "2026-10-02",
    "source_file": "raw data/2026.10.02-Değişiklik Tebliği İşlenmiş Güncel 2013 SUT/2026.10.02-Değişiklik Tebliği İşlenmiş Güncel 2013 SUT/EK-4 LİSTELERİ/EK-4A BEDELİ ÖDENECEK İLAÇLAR LİSTESİ.xlsx",
    "source_member": "2026.10.02-Değişiklik Tebliği İşlenmiş Güncel 2013 SUT/EK-4 LİSTELERİ/EK-4A BEDELİ ÖDENECEK İLAÇLAR LİSTESİ.xlsx",
    "source_sha256": "927918fa6c7459c27bc01619722a9ee6f69cf6eb49ccb7d620534788b453935a",
    "raw_parquet": "data/gazette/raw/annex=EK-4A/effective_date=unknown/EK-4A_BEDELI_ODENECEK_ILACLAR_LISTESI__EK-4A.parquet",
    "raw_sha256": "57202f7b1b1c2e5eef3be315f6dbebb9243f02ee82919bfe77d1dcb810370cf0",
    "raw_rows": 8188,
    "raw_data_columns": 16,
    "repealed_source_file": "raw data/2026.10.02-Değişiklik Tebliği İşlenmiş Güncel 2013 SUT/2026.10.02-Değişiklik Tebliği İşlenmiş Güncel 2013 SUT/EK-4 LİSTELERİ/MÜLGA EK-4 LİSTELERİ/MÜLGA EK-4A BEDELİ ÖDENECEK İLAÇLAR LİSTESİ (Yür. 02.10.2026).xlsx",
    "repealed_source_member": "2026.10.02-Değişiklik Tebliği İşlenmiş Güncel 2013 SUT/EK-4 LİSTELERİ/MÜLGA EK-4 LİSTELERİ/MÜLGA EK-4A BEDELİ ÖDENECEK İLAÇLAR LİSTESİ (Yür. 02.10.2026).xlsx",
    "repealed_source_sha256": "e453d4c0f6a4b027bfd59c3de58a88f47a3dce17792fe8de6ead82ff23b5cbd6",
    "repealed_raw_parquet": "data/gazette/raw/annex=EK-4A/effective_date=2026-10-02/MULGA_EK-4A_BEDELI_ODENECEK_ILACLAR_LISTESI_Yur._02.10.2026__EK-4A.parquet",
    "repealed_raw_sha256": "478428b4c87ad0586c64d6367159e40507f1ea973aed99c1c05415d4b65b0ea8",
    "source_snapshot_drug_rows": 8183,
    "status": "service_date_history",
    "future_marker_effective_date": "2026-10-10",
    "retained_runtime_curated_sha256": "6ed75694326342eb31e696304b82906a3e22a9f73b8648e6fbdbee1b69d739be",
    "retained_runtime_curated_rows": 8078,
    "runtime_catalog_matches_current_source": true,
    "runtime_reader": "src/bilun/domain/materials/ek4a_as_of.py selects EK-4A by service date from data/gazette/curated/ek4a_history.parquet and ek4a_windows.parquet (every list version)",
    "snapshot_catalog": "data/gazette/curated/ek4a_drugs.parquet stays the 2026-05-23 list (retained_runtime_curated_*); no runtime module reads it, only the synthetic data generator"
  }
}
```

## Keeping it current

Run a package ingest by hand with the steps in `docs/operations/AI-RUNBOOK.md` ("Local SUT package ingest"). The EK-4A weekly announcements follow `reports/sut-ingest/2026-10-10-ek4a-service-date.md`.
