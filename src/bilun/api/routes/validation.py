"""BILUN claim validation endpoints — `/validate-claim`, `/bundled-consumables`."""

from __future__ import annotations

from fastapi import APIRouter

from src.bilun.shared.models import ClaimValidationRequest
from src.bilun.api.schemas import BundledConsumablesResponse, ValidateClaimResponse
from src.bilun.domain.materials import get_bundled_consumables, get_non_reimbursable_materials
from src.bilun.domain.rule_engine import validate_claim as sut_validate_claim

router = APIRouter()


@router.post("/validate-claim", response_model=ValidateClaimResponse)
def validate_claim_endpoint(req: ClaimValidationRequest):
    """
    Validate a healthcare claim against BILUN bundling and exclusion rules.

    Checks each material line item for:
      - Bundling violations (EK-3B-1): consumables bundled into procedure price
      - Exclusion violations (EK-3B): non-reimbursable materials
      - Gazette price lookup (EK-3H/3I): official SUT material prices

    Returns validation result with violations, savings, and cost estimates.
    """
    claim_dict = {
        "claim_id": req.claim_id,
        "procedure_code": req.procedure_code,
        "materials": [m.model_dump() for m in req.materials],
    }

    result = sut_validate_claim(claim_dict)

    return {
        "claim_id": result.claim_id,
        "coverage_scope": result.coverage_scope,
        "is_valid": result.is_valid,
        "total_claim_amount": result.total_claim_amount,
        "total_savings_try": result.total_savings_try,
        "total_risk_try": result.total_risk_try,
        "n_bundling_violations": result.n_bundling_violations,
        "n_exclusion_violations": result.n_exclusion_violations,
        "validation_time_ms": result.validation_time_ms,
        "summary": result.summary,
        "violations": [
            {
                "rule": v.rule,
                "severity": v.severity,
                "material_name": v.material_name,
                "message": v.message,
                "savings_try": v.savings_try,
                "risk_amount": v.risk_amount,
            }
            for v in result.violations
        ],
        "material_estimates": [
            {
                "material_code": m.material_code,
                "material_name": m.material_name,
                "unit_price": m.unit_price,
                "quantity": m.quantity,
                "total_price": m.total_price,
                "is_reimbursable": m.is_reimbursable,
                "is_bundled": m.is_bundled,
                "source": m.source,
                "notes": m.notes,
            }
            for m in result.material_estimates
        ],
    }


@router.get("/bundled-consumables", response_model=BundledConsumablesResponse)
def get_bundled_consumables_endpoint():
    """
    List all EK-3B-1 consumables bundled into procedure prices.

    These 54 items cannot be billed separately — they are included
    in the procedure fee (EK-2B puan).
    """
    bundled = get_bundled_consumables()
    exclusions = get_non_reimbursable_materials()

    # Enrich bundled items with fields the frontend expects
    enriched_bundled = [
        {
            "item_name": item.get("item_name", ""),
            "description": item.get("description", ""),
            "bundled_in": item.get("description", "EK-3B-1"),
            "effective_date": "2026-01-31",
        }
        for item in bundled
    ]

    # Enrich exclusion categories with fields the frontend expects
    enriched_exclusions = [
        {
            "section": f"EK-3B Madde {item.get('sira_no', '')}",
            "material_code": None,
            "material_name": item.get("material_name", ""),
            "description": item.get("material_name", ""),
            "effective_date": "2026-01-31",
        }
        for item in exclusions
    ]

    from src.bilun.domain.materials.coverage_scope import material_bundling_coverage_scope

    return {
        "coverage_scope": material_bundling_coverage_scope(),
        "bundled_consumables": {
            "count": len(enriched_bundled),
            "items": enriched_bundled,
        },
        "exclusion_categories": {
            "count": len(enriched_exclusions),
            "categories": enriched_exclusions,
        },
    }
