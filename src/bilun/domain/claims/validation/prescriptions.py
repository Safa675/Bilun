"""Drug prescription traceability validation."""

from __future__ import annotations

from typing import Iterable

from src.bilun.domain.claims.models import DrugClaimLine


def validate_prescription_ids(drugs: Iterable[DrugClaimLine], errors: list[str]) -> None:
    for line in drugs:
        if not line.prescription_id:
            errors.append(f"{line.drug_claim_line_id} missing prescription_id")
