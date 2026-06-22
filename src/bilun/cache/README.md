# BILUN analytics cache

The cache package builds and serves DuckDB-backed patient outcome payloads for
the SUT analytics API.

## Module map

| Module | Responsibility |
|--------|----------------|
| `builder.py` | Main cache build orchestration |
| `context.py` | Load SUT build and expensive backfill contexts |
| `build_expensive.py` | Backfill `patient_outcome_expensive` rows |
| `expensive_compute.py` | Per-patient DRG expensive compute + typed context |
| `sut_context.py` | Exact SUT claim totals and optimization context |
| `billing_context.py` | Billing report cache inputs |
| `payloads.py` | Row payload builders for cache tables |

## Expensive analytics path

1. `load_sut_expensive_context()` loads ANA partitions, `SUTClaimDataset`, and
   exact claim totals (`sut_by_pid`).
2. `backfill_expensive_sections()` iterates patients and calls
   `compute_patient_expensive_sections()` with an `ExpensiveComputeContext`.
3. DRG results are serialized via `domain.analytics.drg_payload.serialize_drg_summary`
   and stored in `patient_outcome_expensive`.
4. API reads normalize stale rows through
   `domain.analytics.drg_payload.normalize_cached_drg_summary_payload`.

DRG normalization and serialization live in `src/bilun/domain/analytics/drg_payload.py`
so cache writes and API reads share one exactness contract.

## Commands

```bash
# Full cache build (see scripts/bilun/build_cache.py)
.venv/bin/python scripts/bilun/build_cache.py --activate

# Expensive DRG backfill only (requires an active complete build)
.venv/bin/python -m src.bilun.cache.build_expensive
# equivalent:
.venv/bin/python scripts/bilun/build_cache.py --expensive-only
```
