# EK-4A and SUT ingestion repair

Base: `3d29a1fefa2b89f9a8d38e2dccab6fe2285c861e`. Closed PR128: `7be613251322d41ab15bbe29de56acaedf60ecfe`.

## Goal

Repair the producer and metadata without promoting a repealed drug snapshot or overwriting the October 2 clause history. Publish a small draft PR with exact-source semantic evidence, focused tests, independent exact-head review and hosted full CI.

## Evidence before implementation

- Current `ingest_state.json` and 326-row `version_manifest.parquet` agree on August 29 and SHA prefix `ac172631298f4be4`; the 8,413-row corpus is already October 2.
- `sut_monitor.py:66-71` reselects October 2 from the old annex state. Workflow lines 59-65 copy the current corpus as the old side; `sut_clause_diff.py:315-336` then overwrite the historical report with a self-comparison.
- The committed October 2 report has 8,375 stable rows and 42 amended corpus rows (13 old + 29 new). Current self-comparison has 8,413 stable rows and zero actionable rows.
- 34 of 35 changed snapshot parquets in PR128 have strictly equal decoded schema, dtypes, ordered rows and values to current main. Their byte changes are serialization churn.
- Current EK-4A (8,078 rows) reproduces a June 29 repealed source; PR128 (8,148) reproduces the August 29 then-current source. The official October 2 ZIP places the latter under MÜLGA. Neither count alone authorizes promotion.
- Official October 2 ZIP SHA256 `03bf37df87ff48358e23b1018405405bbb436032c9424b17ddbcb828525f7a61` contains 349 files and 318 workbooks. The repository October 2 directory contains only the reviewed DOCX, so it is a partial capture.

## Exact paths and gates

1. `scripts/sut/sut_clause_diff.py`, `tests/unit/scripts/test_sut_clause_diff.py`, `scripts/sut/sut_delta.py`, `tests/unit/scripts/test_sut_delta.py`: preserve dated reports; same-input rerun is byte-preserving; self-comparison cannot erase historical changes; conflicting transitions fail clearly. Delta JSON has the same unconditional dated-file overwrite and receives the same narrow persistence guard. Legacy October inputs are pinned in `data/gazette/deltas/2026-10-02_clause_diff_inputs.json` only after the historical summary and every actionable row are independently reproduced from old corpus SHA `9639c457...` and new corpus SHA `40b2b7eb...`; matching only the legacy report's changed subset is insufficient.
2. `scripts/sut/convert_xlsx_to_parquet.py`, `scripts/sut/sut_monitor.py`, `.github/workflows/sut-monitor.yml`, `scripts/sut/sut_fetch.py`, `tests/unit/scripts/test_ingest_state.py`, `tests/unit/scripts/test_sut_monitor.py`, `tests/unit/scripts/test_sut_fetch.py`: exact input completion, partial/empty/failing inputs cannot advance complete-package state, and rerun is idempotent.
3. `scripts/sut/_common.py`, `scripts/sut/build_curated_catalogs.py` and bounded producer tests if required: preserve semantically unchanged artifacts and prevent a future effective partition being selected early.
4. Exact official current `EK-4A BEDELİ ÖDENECEK İLAÇLAR LİSTESİ.xlsx`, its corresponding `data/gazette/raw/annex=EK-4A/...` partition, `data/gazette/curated/ek4a_drugs.parquet`, `data/gazette/version_manifest.parquet`, `data/gazette/ingest_state.json`: write only after source hashes, key/dtype/name/discount/date semantics and applicability have been measured. Record final exact partition/source path below before writing.
5. `reports/sut-ingest/2026-10-05-semantic-audit.json`, `reports/sut-ingest/2026-10-05-ek4a-ingest-review.md`: reproducible evidence and limitations; no billing or clinical interpretation.

## Verification and boundaries

Positive, negative and regression cases cover historical report preservation, real new transitions, partial input, failed conversion, manifest mismatch, source mismatch, future dates, and same-amendment rerun. Run focused tests and canonical artifact checks locally; full Python/frontend CI runs hosted. Preserve sourceauthority, clinical catalog, coverage and current clause corpus bytes. No main writes, merge, force push, VPS, deployment, secrets or authentication setup.

## Exact source admission confirmed

Official member `2026.10.02-Değişiklik Tebliği İşlenmiş Güncel 2013 SUT/EK-4 LİSTELERİ/EK-4A BEDELİ ÖDENECEK İLAÇLAR LİSTESİ.xlsx`, SHA256 `927918fa6c7459c27bc01619722a9ee6f69cf6eb49ccb7d620534788b453935a`, produces 8,183 curated rows with 16 String columns. Against main: 253 added, 148 removed and 157 modified kamu_no keys; 7,773 unchanged common records. No parsed date after October 5; multiple historical date tokens remain unchanged. No monetary price columns exist.

Final bounded source path: `raw data/2026.10.02-Değişiklik Tebliği İşlenmiş Güncel 2013 SUT/2026.10.02-Değişiklik Tebliği İşlenmiş Güncel 2013 SUT/EK-4 LİSTELERİ/EK-4A BEDELİ ÖDENECEK İLAÇLAR LİSTESİ.xlsx`.
Raw partition: `data/gazette/raw/annex=EK-4A/effective_date=unknown/EK-4A_BEDELI_ODENECEK_ILACLAR_LISTESI__EK-4A.parquet`; this explicitly undated filename is not assigned an invented effective date. Preserve the previous August partition separately at `data/gazette/raw/annex=EK-4A/effective_date=2026-10-02/MULGA_EK-4A_BEDELI_ODENECEK_ILACLAR_LISTESI_Yur._02.10.2026__EK-4A.parquet` only if exact ZIP-member provenance is admitted in the manifest; do not relabel existing raw bytes without the source.

State records the verified bounded EK-4A/prose components and reconciled manifest SHA/count. Global complete-package date stays August 29 until all official October package workbooks have completed ingestion; a partial repository capture cannot authorize October full-package completion. Full ZIP inventory handling belongs to the producer correction, not a 318-workbook source dump in this PR. Add `scripts/sut/sut_ingest_state.py` and focused `tests/unit/scripts/test_sut_ingest_state.py` only if required for the final post-pipeline gate.

## Footer and consumer review gate (before data writes)

The explicit source footer establishes October 10, 2026 for entry-date `*` rows A20335/A20336/A20337 and drug-name suffix `**` rows A15711/A15712/A15809. A19064 suffix `***` uses publication day; A20062 internal dosage `*` is a negative control. Column date scans alone do not establish applicability.

Independent runtime seam review found no service-date input in `materials/drugs.py` lookup/list APIs, the `/drugs` endpoint has an ungated fallback, and `domain/drugs/ek4d_exempt.py` reads the same parquet directly for copay name resolution. A single loader gate would therefore leave a bypass. This task will admit exact raw source/proof and update honest partial metadata, while leaving the committed runtime curated EK-4A bytes unchanged. Historical service-date evaluation and the live 8,183-row promotion remain explicitly deferred.

Producer protection adds only `scripts/sut/catalogs/simple_materials.py` and `tests/unit/scripts/test_ek4a_source_admission.py`: source-footer-bound marker validation must reject future-effective curation before October 10 and unknown/missing footnote semantics; permit the exact boundary only as a current catalog build, without claiming historical payment authority. Test key uniqueness, String barcodes/leading zeros, preserved history cells, source current/MÜLGA separation, and exact internal/suffix marker controls. No runtime/domain code changes.

Plan reviewed against the delegated task, parent scope confirmation, completed official source audit and independent consumer seam review before data writes. Report preservation and fail-closed producer changes can now proceed.
