"""Shared historical result projection for validator API and chatbot callers."""

from __future__ import annotations

from typing import Any

from src.bilun.domain.rule_engine import ClaimValidationResult


def serialize_legacy_validation_result(result: ClaimValidationResult) -> dict[str, Any]:
    """Preserve the original public fields, including all raw detail and money."""
    return {
        "claim_id": result.claim_id,
        "coverage_scope": result.coverage_scope,
        "specialty_coverage_scope": result.specialty_coverage_scope,
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
                "rule": row.rule,
                "severity": row.severity,
                "material_name": row.material_name,
                "message": row.message,
                "savings_try": row.savings_try,
                "risk_amount": row.risk_amount,
                "details": row.details,
            }
            for row in result.violations
        ],
        "material_lines": [
            {
                "material_code": line.material_code,
                "material_name": line.material_name,
                "unit_price": line.unit_price,
                "quantity": line.quantity,
                "total_price": line.total_price,
                "is_reimbursable": line.is_reimbursable,
                "is_bundled": line.is_bundled,
                "source": line.source,
                "exactness_status": line.exactness_status,
                "notes": line.notes,
            }
            for line in result.material_lines
        ],
    }
