# BILUN analytics cache

The cache package builds and serves DuckDB-backed patient outcome payloads for
the SUT analytics API.

## Module map

| Module | Responsibility |
|--------|----------------|
| `builder.py` | Main cache build orchestration |
| `context.py` | Load SUT build + billing contexts |
| `sut_context.py` | Exact SUT claim totals and optimization context |
| `billing_context.py` | Billing report cache inputs |
| `payloads.py` | Row payload builders for cache tables |

## Commands

```bash
# Full cache build (see scripts/bilun/build_cache.py)
.venv/bin/python scripts/bilun/build_cache.py --activate
```
