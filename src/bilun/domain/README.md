# SUT module layout

This package is split by responsibility and favors direct package imports over
legacy shim modules.

## Loader split

- `loaders/checkup.py`: check-up JSON loading/indexes.
- `loaders/gazette.py`: curated/parquet gazette loaders and cache helpers.
- `loaders/legacy.py`: fallback/legacy annex loaders used by optimization paths.
- `loaders/__init__.py`: compatibility facade for `src.sut.loaders` imports.

## Stable public seams

- `src.sut.pricing` re-exports cohort/patient/DRG pricing APIs.
- `src.sut.optimization` exposes rule engines and cohort aggregation helpers.
- `src.sut.billing` exposes billing dataclasses and orchestrator entry points.

## Data source modes

SUT billing surfaces must be driven by explicit claim lines, not diagnosis-only
or midpoint estimates. `SUT_DATA_MODE=synthetic_demo` points the demo at
`data/synthetic/sut/claims` and `data/synthetic/sut/clean`; calculations are
rule-exact for those generated claim lines and must be labeled as synthetic demo
data.

Future `SUT_DATA_MODE=real_claims` deployments should point `SUT_CLAIMS_DIR` and
`SUT_CLEAN_DIR` at contract-specific hospital exports that satisfy the same
claim-line contract. Synthetic and real sources should differ only in the
loader/adapter layer consumed by `SUTClaimDataset`.
