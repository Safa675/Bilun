"""
rule_engine.py — Claim validation orchestrator for SUT optimization.

Validates healthcare claims against Turkish SUT regulations by running
bundling and exclusion rules, then aggregating results into a single
validation report with violation details and savings estimates.

Usage:
    from src.sut_optimization.rule_engine import validate_claim

    result = validate_claim({
        "claim_id": "CLM-001",
        "procedure_code": "520030",
        "materials": [
            {"name": "Bistüri ucu", "unit_price": 5.0, "quantity": 2},
            {"name": "Stent", "unit_price": 2000.0, "quantity": 1},
        ],
    })
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any

from src.bilun.domain.materials.coverage_scope import material_bundling_coverage_scope
from src.bilun.domain.prose_rules.material_bundling import check_material_bundling_prose
from src.bilun.domain.rules.bundling_rules import check_bundling_violations
from src.bilun.domain.rules.exclusion_rules import check_exclusion_violations
from src.bilun.domain.analytics import MaterialCostEstimate, estimate_material_costs

logger = logging.getLogger("ilay.sut_optimization.rule_engine")


@dataclass
class RuleViolation:
    """A single rule violation found during claim validation."""

    rule: str  # "bundling" | "exclusion"
    severity: str  # "warning" | "error"
    material_name: str
    message: str
    savings_try: float = 0.0
    risk_amount: float = 0.0
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class ClaimValidationResult:
    """Complete validation result for a claim submission.

    Attributes:
        claim_id: The claim being validated.
        is_valid: True if no error-severity violations found.
        violations: List of rule violations found.
        material_estimates: Cost estimates for each material line item.
        total_claim_amount: Sum of all material line items.
        total_savings_try: Potential savings from bundling violations.
        total_risk_try: Amount at risk from exclusion violations.
        n_bundling_violations: Count of bundling rule violations.
        n_exclusion_violations: Count of exclusion rule violations.
        validation_time_ms: Time taken to validate (milliseconds).
        summary: Human-readable summary of findings.
    """

    claim_id: str = ""
    is_valid: bool = True
    violations: list[RuleViolation] = field(default_factory=list)
    material_estimates: list[MaterialCostEstimate] = field(default_factory=list)
    total_claim_amount: float = 0.0
    total_savings_try: float = 0.0
    total_risk_try: float = 0.0
    n_bundling_violations: int = 0
    n_exclusion_violations: int = 0
    validation_time_ms: float = 0.0
    summary: str = ""
    coverage_scope: dict[str, Any] = field(default_factory=material_bundling_coverage_scope)


def validate_claim(claim: dict[str, Any]) -> ClaimValidationResult:
    """
    Validate a healthcare claim against SUT bundling and exclusion rules.

    Runs annex list checks plus partial §3.1 prose keywords (see coverage_scope):
      1. Bundling rules (EK-3B-1, 54 rows): consumables bundled into procedure fee.
      2. Exclusion rules (EK-3B-2, 13 rows): non-reimbursable materials.
      3. Material bundling prose (partial JSON): keyword rules not in EK-3B-1.

    Additionally computes material cost estimates using gazette prices.

    Args:
        claim: Dict with:
            - "claim_id" (str): Claim identifier.
            - "procedure_code" (str, optional): SUT procedure code.
            - "materials" (list[dict]): Material line items, each with
              "name", optional "unit_price", optional "quantity", optional "code".

    Returns:
        ClaimValidationResult with aggregated violations and cost estimates.
    """
    t0 = time.perf_counter()

    claim_id = str(claim.get("claim_id", ""))
    procedure_code = str(claim.get("procedure_code", ""))
    materials = claim.get("materials", [])

    result = ClaimValidationResult(claim_id=claim_id)

    if not materials:
        result.summary = "No materials to validate."
        result.validation_time_ms = round((time.perf_counter() - t0) * 1000, 2)
        return result

    # ── 1. Run bundling rules ────────────────────────────────────────
    bundling_violations = check_bundling_violations(
        materials, procedure_code=procedure_code
    )
    for bv in bundling_violations:
        result.violations.append(
            RuleViolation(
                rule="bundling",
                severity=bv.get("severity", "warning"),
                material_name=bv.get("material_name", ""),
                message=bv.get("message", ""),
                savings_try=bv.get("savings_try", 0.0),
                details=bv,
            )
        )
    result.n_bundling_violations = len(bundling_violations)
    result.total_savings_try = round(
        sum(v.savings_try for v in result.violations if v.rule == "bundling"), 2
    )

    # ── 2. Run exclusion rules ───────────────────────────────────────
    exclusion_violations = check_exclusion_violations(materials)
    for ev in exclusion_violations:
        result.violations.append(
            RuleViolation(
                rule="exclusion",
                severity=ev.get("severity", "error"),
                material_name=ev.get("material_name", ""),
                message=ev.get("message", ""),
                risk_amount=ev.get("risk_amount", 0.0),
                details=ev,
            )
        )
    result.n_exclusion_violations = len(exclusion_violations)
    result.total_risk_try = round(
        sum(v.risk_amount for v in result.violations if v.rule == "exclusion"), 2
    )

    # ── 3. Partial §3.1 prose (keyword rules) ─────────────────────────
    prose_violations = check_material_bundling_prose(
        materials, procedure_code=procedure_code
    )
    for pv in prose_violations:
        outcome = str(pv.get("material_outcome") or "")
        savings = float(pv.get("savings_try") or 0.0)
        risk = float(pv.get("risk_amount") or 0.0)
        if outcome == "no_pay":
            result.violations.append(
                RuleViolation(
                    rule="material_bundling_prose",
                    severity=pv.get("severity", "error"),
                    material_name=pv.get("material_name", ""),
                    message=pv.get("message", ""),
                    risk_amount=risk,
                    details=pv,
                )
            )
            result.total_risk_try = round(result.total_risk_try + risk, 2)
        else:
            result.violations.append(
                RuleViolation(
                    rule="material_bundling_prose",
                    severity=pv.get("severity", "warning"),
                    material_name=pv.get("material_name", ""),
                    message=pv.get("message", ""),
                    savings_try=savings or risk,
                    details=pv,
                )
            )
            result.total_savings_try = round(result.total_savings_try + (savings or risk), 2)

    # ── 4. Compute material cost estimates ───────────────────────────
    result.material_estimates = estimate_material_costs(materials)
    result.total_claim_amount = round(
        sum(m.total_price for m in result.material_estimates), 2
    )

    # ── 5. Determine validity ────────────────────────────────────────
    has_errors = any(v.severity == "error" for v in result.violations)
    result.is_valid = not has_errors

    # ── 6. Build summary ─────────────────────────────────────────────
    elapsed = round((time.perf_counter() - t0) * 1000, 2)
    result.validation_time_ms = elapsed

    parts: list[str] = []
    if result.is_valid:
        parts.append(f"Claim {claim_id}: VALID")
    else:
        parts.append(f"Claim {claim_id}: INVALID")

    parts.append(
        f"{len(materials)} materials, {result.total_claim_amount:.2f} TRY total"
    )

    if result.n_bundling_violations > 0:
        parts.append(
            f"{result.n_bundling_violations} bundling violation(s), "
            f"savings: {result.total_savings_try:.2f} TRY"
        )
    if result.n_exclusion_violations > 0:
        parts.append(
            f"{result.n_exclusion_violations} exclusion violation(s), "
            f"risk: {result.total_risk_try:.2f} TRY"
        )

    parts.append(f"validated in {elapsed:.1f}ms")
    result.summary = " | ".join(parts)

    logger.info(result.summary)
    return result
