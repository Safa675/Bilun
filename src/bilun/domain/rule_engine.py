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

from src.bilun.domain.claims.growth_hormone import parse_growth_hormone_inputs

import logging
import time
from dataclasses import dataclass, field
from typing import Any
from src.bilun.domain.prose_rules._drug_indication.temporal import parse_service_date

from src.bilun.domain.materials.coverage_scope import material_bundling_coverage_scope
from src.bilun.domain.materials.specialty_coverage_scope import specialty_materials_coverage_scope
from src.bilun.domain.prose_rules.material_bundling import check_material_bundling_prose
from src.bilun.domain.prose_rules.specialty_materials import check_specialty_materials_prose
from src.bilun.domain.rules.bundling_rules import check_bundling_violations
from src.bilun.domain.rules.exclusion_rules import check_exclusion_violations
from src.bilun.domain.analytics import MaterialLinePricing, price_material_lines
from src.bilun.domain.billing.types import EXACTNESS_STATUS_EXACT
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
        material_lines: Priced material lines from billed amounts or EK-3 code lookup.
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
    material_lines: list[MaterialLinePricing] = field(default_factory=list)
    total_claim_amount: float = 0.0
    total_savings_try: float = 0.0
    total_risk_try: float = 0.0
    n_bundling_violations: int = 0
    n_exclusion_violations: int = 0
    validation_time_ms: float = 0.0
    summary: str = ""
    coverage_scope: dict[str, Any] = field(default_factory=material_bundling_coverage_scope)
    specialty_coverage_scope: dict[str, Any] = field(
        default_factory=specialty_materials_coverage_scope
    )


def _run_drug_indication_checks(
    materials: list[dict[str, Any]],
    claim: dict[str, Any],
) -> list[RuleViolation]:
    """Bridge MaterialItem dicts → DrugClaimLine + ClaimHeader and run §4.2 checks.

    Returns a list of RuleViolation(rule="drug_indication"). Skips entirely when
    the claim carries no ``drug_context`` (backwards-compatible: plain material
    claims never trigger drug_indication).
    """
    drug_ctx = claim.get("drug_context")
    if not drug_ctx:
        return []

    from datetime import date
    from decimal import Decimal

    from src.bilun.domain.claims.models import ClaimHeader, DrugClaimLine
    from src.bilun.domain.claims.clinical_evidence import (
        EnteralEvidence, RavulizumabEvidence, parse_clinical_evidence,
    )
    from src.bilun.domain.prose_rules.drug_indication import (
        evaluate_drug_indication_line,
        list_drug_indication_rules,
    )

    rules = list_drug_indication_rules()
    if not rules:
        return []

    icd10 = str(drug_ctx.get("primary_icd10", "")).strip().upper()
    prescriber = str(drug_ctx.get("prescriber_specialty", "")).strip() or None
    report_present = drug_ctx.get("board_report_present")
    report_duration = drug_ctx.get("report_duration_months")

    claim_header = ClaimHeader(
        claim_id=str(claim.get("claim_id", "")),
        patient_id="",
        episode_id="",
        claim_type="ayakta",
        facility_tier="",
        provider_type="",
        department="",
        admission_date=None,
        discharge_date=None,
        claim_start_date=date.today(),
        claim_end_date=date.today(),
        primary_icd10=icd10,
        package_candidate=None,
        expected_total_billed_try=Decimal("0"),
        expected_total_payable_try=Decimal("0"),
        expected_denial_reason="",
        scenario_tag="validate_claim",
    )

    violations: list[RuleViolation] = []
    for idx, mat in enumerate(materials, start=1):
        drug_name = str(mat.get("name", "")).strip()
        if not drug_name:
            continue
        line_id = f"DRUG-{claim.get('claim_id', '')}-{idx:03d}"
        biomarkers = mat.get("biomarkers")
        prior_therapies = mat.get("prior_therapies")
        drug_line = DrugClaimLine(
            drug_claim_line_id=line_id,
            prescription_id="",
            claim_id=claim_header.claim_id,
            patient_id="",
            episode_id="",
            drug_claim_date=parse_service_date(drug_ctx.get("service_date")),
            drug_name=drug_name,
            drug_code=str(mat.get("code", "")),
            barkod="",
            equivalence_group="",
            quantity=int(mat.get("quantity", 1) or 1),
            unit_price_try=Decimal(str(mat.get("unit_price", 0) or 0)),
            billed_amount_try=Decimal(str(mat.get("billed_amount", 0) or 0)),
            expected_payable_try=Decimal("0"),
            discount_tier_expected=Decimal("0"),
            denial_reason_expected="",
            rule_trace_expected="",
            prescriber_specialty=prescriber,
            drug_specialty_board_report_present=report_present,
            drug_report_duration_months=report_duration,
            annual_application_count=mat.get("annual_application_count"),
            is_loading_phase=mat.get("is_loading_phase"),
            biomarkers=tuple(biomarkers) if biomarkers else None,
            prior_therapies=tuple(prior_therapies) if prior_therapies else None,
            **parse_growth_hormone_inputs(mat),
            enteral_evidence=parse_clinical_evidence(mat.get("enteral_evidence"), EnteralEvidence),
            ravulizumab_evidence=parse_clinical_evidence(mat.get("ravulizumab_evidence"), RavulizumabEvidence),
        )
        hit = evaluate_drug_indication_line(
            drug_line=drug_line,
            claim=claim_header,
            diagnoses=[],
            rules=rules,
        )
        if hit is None:
            continue
        violations.append(
            RuleViolation(
                rule="drug_indication",
                severity=hit.get("severity", "warning"),
                material_name=drug_name,
                message=hit.get("message_tr", str(hit.get("violation_kind", ""))),
                savings_try=0.0,
                details=hit,
            )
        )
    return violations


def validate_claim(claim: dict[str, Any]) -> ClaimValidationResult:
    """Validate a healthcare claim against SUT rules (Phase 2.4 unified path).

    Thin adapter over the unified ``analyze_claim`` core: builds a
    PatientClaimContext from the claim dict (Phase 2.2 adapter), runs the
    regulatory motors via ``analyze_claim`` (Phase 2.3 core), and projects
    the flat violation list onto a ClaimValidationResult.

    The legacy dict-path body is preserved as ``_validate_claim_legacy`` for
    the parity test (tests/unit/domain/test_validate_claim_adapter_parity.py)
    to compare against. Once that parity test has been green across the full
    fixture cohort for a release cycle, the legacy body can be retired.

    See plans/refactor/rule-encoding-gap-closure-roadmap.md Phase 2.4.
    """
    return _validate_claim_via_context(claim)


def _validate_claim_legacy(claim: dict[str, Any]) -> ClaimValidationResult:
    """
    Legacy dict-path validation (preserved for parity comparison).

    Runs annex list checks plus partial §3.1 / §3.3 prose (see coverage_scope):
      1. Bundling rules (EK-3B-1, 54 rows): consumables bundled into procedure fee.
      2. Exclusion rules (EK-3B-2, 13 rows): non-reimbursable materials.
      3. Material bundling prose (partial JSON): keyword rules not in EK-3B-1.
      4. Specialty annex prose (partial JSON): §3.3 branch rules (L4.4).

    Additionally prices material lines from billed amounts or exact EK-3 codes.

    Args:
        claim: Dict with:
            - "claim_id" (str): Claim identifier.
            - "procedure_code" (str, optional): SUT procedure code.
            - "materials" (list[dict]): Material line items, each with
              "name", "code" (required for exact pricing), optional "unit_price",
              optional "quantity", optional "billed_amount".

    Returns:
        ClaimValidationResult with aggregated violations and material line pricing.
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

    # ── 3b. Partial §3.3 specialty annex prose ───────────────────────
    specialty_violations = check_specialty_materials_prose(materials)
    for sv in specialty_violations:
        outcome = str(sv.get("material_outcome") or "")
        savings = float(sv.get("savings_try") or 0.0)
        risk = float(sv.get("risk_amount") or 0.0)
        if outcome == "no_pay":
            result.violations.append(
                RuleViolation(
                    rule="specialty_materials_prose",
                    severity=sv.get("severity", "error"),
                    material_name=sv.get("material_name", ""),
                    message=sv.get("message", ""),
                    risk_amount=risk,
                    details=sv,
                )
            )
            result.total_risk_try = round(result.total_risk_try + risk, 2)
        else:
            result.violations.append(
                RuleViolation(
                    rule="specialty_materials_prose",
                    severity=sv.get("severity", "warning"),
                    material_name=sv.get("material_name", ""),
                    message=sv.get("message", ""),
                    savings_try=savings or risk,
                    details=sv,
                )
            )
            result.total_savings_try = round(result.total_savings_try + (savings or risk), 2)

    # ── 4. Price material lines (billed amount or exact EK-3 code) ─────
    result.material_lines = price_material_lines(materials)
    result.total_claim_amount = round(
        sum(
            line.total_price
            for line in result.material_lines
            if line.exactness_status == EXACTNESS_STATUS_EXACT
        ),
        2,
    )

    # ── 4b. Drug indication checks (§4.2.14.C + §4.2.33) — only when
    #        the claim carries drug_context (backwards-compatible). ──────
    drug_violations = _run_drug_indication_checks(materials, claim)
    n_drug_violations = 0
    for dv in drug_violations:
        result.violations.append(dv)
        if dv.severity == "error":
            n_drug_violations += 1

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
    if n_drug_violations > 0:
        parts.append(f"{n_drug_violations} drug indication violation(s)")

    parts.append(f"validated in {elapsed:.1f}ms")
    result.summary = " | ".join(parts)

    logger.info(result.summary)
    return result


def _validate_claim_via_context(claim: dict[str, Any]) -> ClaimValidationResult:
    """Adapter-path validation (Phase 2.4) — build ctx, analyze_claim, project.

    Mirrors ``validate_claim``'s contract (same ClaimValidationResult shape,
    same violation aggregation, same summary text) but routes through the
    unified ``analyze_claim`` core via the dict→PatientClaimContext adapter.
    Intended to be byte-equivalent to the legacy ``validate_claim`` for any
    claim dict; the Phase 2.4 parity test pins that. Once verified, this
    becomes the body of ``validate_claim`` and the legacy dict-path body is
    retired.

    See plans/refactor/rule-encoding-gap-closure-roadmap.md Phase 2.4.
    """
    t0 = time.perf_counter()

    if not claim.get("materials", []):
        return project_claim_validation_rows(claim, [], started_at=t0)

    from src.bilun.domain.billing.engine import analyze_claim
    from src.bilun.domain.claims.adapter import build_context_from_material_dict

    ctx = build_context_from_material_dict(claim)
    return project_claim_validation_rows(claim, analyze_claim(ctx), started_at=t0)


def project_claim_validation_rows(
    claim: dict[str, Any],
    raw_violations: list[dict[str, Any]],
    *,
    started_at: float | None = None,
) -> ClaimValidationResult:
    """Preserve the historical result from already-computed motor rows.

    V2 can reuse the same observations for its typed and compatibility views;
    this projector must never run a regulatory detector.
    """
    t0 = time.perf_counter() if started_at is None else started_at

    claim_id = str(claim.get("claim_id", ""))
    materials = claim.get("materials", [])

    result = ClaimValidationResult(claim_id=claim_id)

    if not materials:
        result.summary = "No materials to validate."
        result.validation_time_ms = round((time.perf_counter() - t0) * 1000, 2)
        return result

    # Project the flat violation list onto ClaimValidationResult, mirroring the
    # legacy aggregation (bundling → savings, exclusion → risk, prose motors
    # split by material_outcome, drug_indication severity-tracked).
    n_bundling = 0
    n_exclusion = 0
    n_drug_errors = 0
    for v in raw_violations:
        rule = str(v.get("rule", ""))
        severity = str(v.get("severity", "warning"))
        outcome = str(v.get("material_outcome") or "")
        savings = float(v.get("savings_try") or 0.0)
        risk = float(v.get("risk_amount") or 0.0)

        if rule == "bundling":
            n_bundling += 1
            result.violations.append(
                RuleViolation(
                    rule="bundling",
                    severity=severity,
                    material_name=v.get("material_name", ""),
                    message=v.get("message", ""),
                    savings_try=savings,
                    details=v,
                )
            )
            result.total_savings_try = round(result.total_savings_try + savings, 2)
        elif rule == "exclusion":
            n_exclusion += 1
            result.violations.append(
                RuleViolation(
                    rule="exclusion",
                    severity=severity,
                    material_name=v.get("material_name", ""),
                    message=v.get("message", ""),
                    risk_amount=risk,
                    details=v,
                )
            )
            result.total_risk_try = round(result.total_risk_try + risk, 2)
        elif rule in {"material_bundling_prose", "specialty_materials_prose"}:
            if outcome == "no_pay":
                result.violations.append(
                    RuleViolation(
                        rule=rule,
                        severity=severity,
                        material_name=v.get("material_name", ""),
                        message=v.get("message", ""),
                        risk_amount=risk,
                        details=v,
                    )
                )
                result.total_risk_try = round(result.total_risk_try + risk, 2)
            else:
                result.violations.append(
                    RuleViolation(
                        rule=rule,
                        severity=severity,
                        material_name=v.get("material_name", ""),
                        message=v.get("message", ""),
                        savings_try=savings or risk,
                        details=v,
                    )
                )
                result.total_savings_try = round(
                    result.total_savings_try + (savings or risk), 2
                )
        elif rule == "drug_indication":
            result.violations.append(
                RuleViolation(
                    rule="drug_indication",
                    severity=severity,
                    material_name=v.get("material_name", ""),
                    message=v.get("message", ""),
                    risk_amount=risk,
                    savings_try=savings,
                    details=v,
                )
            )
            if severity == "error":
                n_drug_errors += 1
        else:
            # Catch-all: never silently drop a violation from a motor the
            # unified core runs. Before this branch, any rule tag outside the
            # explicit set above (gap_closing_*,
            # material_pairing_uplift, dental_2_4_1, material_preauth_ek3c1,
            # material_miat_ek3c2, drg_package_adequacy, procedure_pairing)
            # was computed by analyze_claim then discarded here, so /validate-claim
            # under-reported. The risk_amount/savings_try split follows the
            # material_outcome convention (no_pay → risk, must_bill → savings).
            result.violations.append(
                RuleViolation(
                    rule=rule,
                    severity=severity,
                    material_name=v.get("material_name", ""),
                    message=v.get("message", ""),
                    risk_amount=risk,
                    savings_try=savings,
                    details=v,
                )
            )
            if outcome == "no_pay":
                # no_pay → provider risk; add the billed amount to the risk
                # headline (savings stays 0 for no_pay).
                result.total_risk_try = round(result.total_risk_try + risk, 2)
            elif savings:
                # A genuine recoverable savings on a must_bill/review outcome.
                # NOTE: do NOT fold risk into savings — risk_amount on a
                # non-no_pay outcome is not a savings signal, and folding it
                # would inflate total_savings_try for review-only findings.
                result.total_savings_try = round(result.total_savings_try + savings, 2)

    result.n_bundling_violations = n_bundling
    result.n_exclusion_violations = n_exclusion

    # Price material lines (same helper the legacy path uses — pricing is
    # orthogonal to validation and reads the raw dict, not the context).
    result.material_lines = price_material_lines(materials)
    result.total_claim_amount = round(
        sum(
            line.total_price
            for line in result.material_lines
            if line.exactness_status == EXACTNESS_STATUS_EXACT
        ),
        2,
    )

    has_errors = any(v.severity == "error" for v in result.violations)
    result.is_valid = not has_errors

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
    if n_drug_errors > 0:
        parts.append(f"{n_drug_errors} drug indication violation(s)")
    parts.append(f"validated in {elapsed:.1f}ms")
    result.summary = " | ".join(parts)

    logger.info(result.summary)
    return result
