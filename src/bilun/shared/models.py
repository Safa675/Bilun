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


class ClaimValidationRequest(BaseModel):
    """Request body for POST /api/validate-claim."""

    claim_id: str = ""
    procedure_code: str = ""
    materials: list[MaterialItem] = []
