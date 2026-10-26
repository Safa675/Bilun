# SUT module layout

This package is split by responsibility and favors direct package imports over
legacy shim modules.

## Loader split

- `loaders/katsayi.py`: SUT puan→TL katsayi history loader.
- `loaders/gazette.py`: curated/parquet gazette loaders and cache helpers.
- `loaders/legacy.py`: fallback/legacy annex loaders used by optimization paths.
- `loaders/__init__.py`: compatibility facade for `src.sut.loaders` imports.

## Stable public seams

- `src.sut.pricing` re-exports cohort/patient/DRG pricing APIs.
- `src.sut.optimization` exposes rule engines and cohort aggregation helpers.
- `src.sut.billing` exposes billing dataclasses and orchestrator entry points.
- `icd10.py` normalises and matches ICD-10 codes for every rule that lists them: a caller names
  its reading (`Icd10Cover.EXACT`: a dotted code covers only itself; `Icd10Cover.LEAVES`: it also
  covers the SKRS leaves under it, the 4.2 drug-indication rules) and ranges go through
  `icd10_in_range`.

## Data source modes

SUT billing surfaces must be driven by explicit claim lines, not diagnosis-only
or midpoint estimates. `SUT_DATA_MODE=synthetic_demo` points the demo at
`data/synthetic/sut/claims` and `data/synthetic/sut/clean` (the 16 patients, 42 bills, of the
v3 showcase cohort; see `data/synthetic/README.md`); calculations are rule-exact
for those generated claim lines and must be labeled as synthetic demo data.

Future `SUT_DATA_MODE=real_claims` deployments should point `SUT_CLAIMS_DIR` and
`SUT_CLEAN_DIR` at contract-specific hospital exports that satisfy the same
claim-line contract. Synthetic and real sources should differ only in the
loader/adapter layer consumed by `SUTClaimDataset`.
