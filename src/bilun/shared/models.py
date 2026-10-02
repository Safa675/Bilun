"""
Pydantic request/response schemas for the BILUN API.
"""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, field_validator


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


class DrugContext(BaseModel):
    """Claim-level drug indication context (optional, only for drug claims).

    When present, the validate-claim endpoint runs the drug_indication engine
    (§4.2.14.C oncology + §4.2.33 anti-VEGF) against each material line.
    Line-level fields (biomarkers, dose counts) stay on MaterialItem.
    """

    service_date: date | None = None

    @field_validator("service_date", mode="before")
    @classmethod
    def validate_service_date(cls, value: object) -> date | None:
        from src.bilun.domain.prose_rules._drug_indication.temporal import parse_service_date

        if value is None:
            return None
        parsed = parse_service_date(value)
        if parsed is None:
            raise ValueError("service_date must be an ISO calendar date (YYYY-MM-DD)")
        return parsed

    primary_icd10: str = ""
    prescriber_specialty: str = ""
    board_report_present: bool | None = None
    report_duration_months: int | None = None


class ClaimValidationRequest(BaseModel):
    """Request body for POST /api/validate-claim."""

    claim_id: str = ""
    procedure_code: str = ""
    materials: list[MaterialItem] = []
    drug_context: DrugContext | None = None
