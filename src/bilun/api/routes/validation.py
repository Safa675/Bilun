"""BILUN claim validation endpoints — `/validate-claim`, `/bundled-consumables`."""

from __future__ import annotations

from fastapi import APIRouter, Header
from fastapi.responses import JSONResponse

from src.bilun.shared.models import ClaimValidationRequest
from src.bilun.api.schemas import BundledConsumablesResponse, ValidateClaimResponse
from src.bilun.domain.materials import get_bundled_consumables, get_non_reimbursable_materials
from src.bilun.domain.rule_engine import validate_claim as sut_validate_claim
from src.bilun.domain.claim_validation_v2 import typed_validation_payload, validate_claim_v2
from src.bilun.domain.validation_serialization import serialize_legacy_validation_result
from src.bilun.api.validation_schemas import ValidateClaimV2Response

router = APIRouter()


@router.post("/validate-claim", response_model=ValidateClaimV2Response)
def validate_claim_endpoint(
    req: ClaimValidationRequest,
    contract_version: str | None = Header(default=None, alias="X-Bilun-Validation-Contract"),
):
    """Use the marked v2 contract; old clients must explicitly upgrade."""
    if contract_version != "2":
        return JSONResponse(
            status_code=409,
            content={
                "code": "validation_contract_upgrade_required",
                "detail": (
                    "Doğrulayıcı güncellendi; sayfayı yenileyin veya istemciyi yükseltin. / "
                    "Reload the page or upgrade your client to validation contract 2."
                ),
                "legacy_endpoint": "/api/validate-claim/legacy",
            },
        )
    return typed_validation_payload(validate_claim_v2(
        req.model_dump(mode="json"), supplied_claim=req.model_dump(mode="json", exclude_unset=True)
    ))


@router.post("/validate-claim/legacy", response_model=ValidateClaimResponse)
def validate_claim_legacy_endpoint(req: ClaimValidationRequest):
    """Historical unclassified rows and financial aggregation, explicitly named.

    Authentication is enforced by the same application middleware as v2. These
    rows retain the previous semantics and are not typed Compliance findings.
    """
    return serialize_legacy_validation_result(sut_validate_claim(req.model_dump(mode="json")))


@router.get("/bundled-consumables", response_model=BundledConsumablesResponse)
def get_bundled_consumables_endpoint():
    """List annex source entries, without evaluating a claim's applicability.

    Names retain the annex's setting/use qualifiers and exceptions. Collection
    keys are historical compatibility names, not confirmed payment decisions.
    No effective date is asserted from a catalog lacking interval evidence.
    """
    bundled = get_bundled_consumables()
    exclusions = get_non_reimbursable_materials()

    # Enrich bundled items with fields the frontend expects
    enriched_bundled = [
        {
            "item_name": item.get("item_name", ""),
            "description": item.get("description", ""),
            "bundled_in": item.get("description", "EK-3B-1"),
            "effective_date": None,
            "evaluation_status": "not_evaluated",
        }
        for item in bundled
    ]

    # Enrich exclusion categories with fields the frontend expects
    enriched_exclusions = [
        {
            "section": f"EK-3B-2 Madde {item.get('sira_no', '')}",
            "material_code": None,
            "material_name": item.get("material_name", ""),
            "description": item.get("material_name", ""),
            "effective_date": None,
            "evaluation_status": "not_evaluated",
        }
        for item in exclusions
    ]

    from src.bilun.domain.materials.coverage_scope import material_bundling_coverage_scope
    from src.bilun.domain.materials.specialty_coverage_scope import (
        specialty_materials_coverage_scope,
    )

    return {
        "coverage_scope": material_bundling_coverage_scope(),
        "specialty_coverage_scope": specialty_materials_coverage_scope(),
        "bundled_consumables": {
            "count": len(enriched_bundled),
            "items": enriched_bundled,
        },
        "exclusion_categories": {
            "count": len(enriched_exclusions),
            "categories": enriched_exclusions,
        },
    }
