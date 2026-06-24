"""
Pydantic request/response schemas for the BILUN API.
"""

from __future__ import annotations

from pydantic import BaseModel


class MaterialItem(BaseModel):
    """A single material line item in a claim."""

    name: str
    code: str = ""
    unit_price: float = 0.0
    quantity: int = 1
    billed_amount: float = 0.0
    # §4.2.33 anti-VEGF dose protocol (intravitreal injection counts) — optional,
    # only meaningful for ophthalmology drug claims; ignored otherwise.
    annual_application_count: int | None = None
    is_loading_phase: bool | None = None
    # §4.2.14.C oncology biomarker + prior-therapy gating — optional, only for
    # indication-gated oncology drug claims; ignored otherwise.
    biomarkers: list[dict[str, str]] | None = None
    prior_therapies: list[dict[str, str]] | None = None


class ClaimValidationRequest(BaseModel):
    """Request body for POST /api/validate-claim."""

    claim_id: str = ""
    procedure_code: str = ""
    materials: list[MaterialItem] = []
