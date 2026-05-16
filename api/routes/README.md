# `src/api/routes/sut/`

FastAPI routes under `/api/sut/*` — split from the legacy single-file
`routes/sut.py` (799 LOC, 18 endpoints) during the Phase C1 hygiene
refactor. URLs are unchanged.

## Layout

```
src/api/routes/sut/
├── __init__.py        # aggregates a single APIRouter exported as `router`
├── README.md          # this file
├── validation.py      # POST /validate-claim, GET /bundled-consumables
├── pricing.py         # GET /procedure/{code}, /material/{code}/pricing,
│                      #     /drg-pricing, /visit-pricing, /lab-prices,
│                      #     /checkup-pricing, /price-history/{code}
├── alerts.py          # GET /patient-alerts
├── optimization.py    # GET /optimization-summary,
│                      #     /patient/{id}/optimization,
│                      #     /revenue-recovery
└── billing.py         # GET /billing-report/{patient_id}, /drugs,
                       #     /materials/by-specialty
```

## Public surface

```python
from src.api.routes.sut import router  # aggregated, prefix=/api/sut, tags=[sut]
```

## Conventions

- Each submodule declares its own bare `router = APIRouter()` with no
  prefix or tags. The aggregator in `__init__.py` adds `prefix="/api/sut"`
  and `tags=["sut"]`. Don't duplicate them in submodules.
- Submodule-private helpers (e.g. `_validate_patient_alert_params`,
  `_serialize_billing_report`) live in the file that uses them. Helpers
  shared across two submodules go into a new `_shared.py` (none today).
- Heavy `src.sut.*` imports stay lazy / function-local where they
  already are; the imports here mirror the originals.
