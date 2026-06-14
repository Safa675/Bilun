"""BILUN routes — pricing, validation, alerts, optimization, billing,
and patient endpoints under ``/api/*``.

The package aggregates 7 thematic submodules behind a single FastAPI
``router`` exported from this module so the app factory can import it
unchanged via ``from src.bilun.api.routes import router``.

Submodule split:
    chat          — BILUN chatbot streaming endpoint
    patients      — patient listing, search, outcome
    validation    — claim validation, bundled-consumables disclosure
    pricing       — procedure / material / visit / lab / checkup lookups
    alerts        — patient-alerts table
    optimization  — optimization-summary, per-patient findings,
                    revenue-recovery dashboard
    billing       — per-patient billing report, drug catalog,
                    materials-by-specialty browser
    rules         — SUT rule database: catalog index + extracted-clause
                    source drill-down
"""

from __future__ import annotations

from fastapi import APIRouter

from . import alerts, billing, chat, optimization, patients, pricing, rules, validation

# Public function re-exports — flat surface for tests and external callers
# that prefer ``from src.bilun.api.routes import <fn>`` over reaching into a
# specific submodule. Endpoint handlers only — no private helpers.
from .alerts import get_patient_alerts  # noqa: F401, E402
from .billing import (  # noqa: F401, E402
    get_drug_catalog,
    get_materials_by_specialty,
    get_patient_billing_report,
)
from .chat import bilun_chat  # noqa: F401, E402
from .optimization import (  # noqa: F401, E402
    get_optimization_summary,
    get_patient_optimization,
    get_revenue_recovery,
)
from .patients import (  # noqa: F401, E402
    get_bilun_patient_outcome,
    get_bilun_patients,
    search_bilun_patients,
)
from .pricing import (  # noqa: F401, E402
    get_checkup_pricing,
    get_lab_prices,
    get_material_pricing,
    get_price_history,
    get_procedure_info,
    get_visit_pricing,
)
from .rules import get_rule_catalog, get_rule_detail  # noqa: F401, E402
from .validation import (  # noqa: F401, E402
    get_bundled_consumables_endpoint,
    validate_claim_endpoint,
)

router = APIRouter(prefix="/api", tags=["bilun"])
router.include_router(chat.router)
router.include_router(patients.router)
router.include_router(validation.router)
router.include_router(pricing.router)
router.include_router(alerts.router)
router.include_router(optimization.router)
router.include_router(billing.router)
router.include_router(rules.router)
