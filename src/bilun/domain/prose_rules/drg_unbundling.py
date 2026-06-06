"""SUT §2.2 prose checks for DRG unbundling on exact claim lines."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from .catalog_membership import normalize_procedure_code
from .claim_utils import group_procedure_lines_by_session, infer_care_setting
from .payment_method import check_payment_method_compliance, resolve_payment_method
from .session_pricing import blood_component_billable_fraction, compute_session_point_factors
from .session_specialty import detect_cross_specialty_session
from .types import CareSetting

if TYPE_CHECKING:
    from src.bilun.domain.claims.models import ClaimHeader, ProcedureClaimLine

_BILLING_TOLERANCE = 0.02


@dataclass
class ClaimUnbundlingFinding:
    claim_id: str
    chapter: str
    bundled_violations: list[dict[str, Any]] = field(default_factory=list)
    payment_method_violations: list[dict[str, Any]] = field(default_factory=list)
    session_violations: list[dict[str, Any]] = field(default_factory=list)
    blood_component_violations: list[dict[str, Any]] = field(default_factory=list)
    itemized_total_try: float = 0.0
    package_total_try: float = 0.0
    potential_savings_try: float = 0.0
    sourced_savings_try: float = 0.0
    heuristic_savings_try: float = 0.0
    itemized_package_uplift_try: float = 0.0

    @property
    def has_risk(self) -> bool:
        return self.potential_savings_try > 0 or bool(
            self.bundled_violations
            or self.payment_method_violations
            or self.session_violations
            or self.blood_component_violations
        )


def _money(value: float | int) -> float:
    return round(float(value), 2)


def _line_billed(line: ProcedureClaimLine) -> float:
    return float(line.billed_amount_try)


def _line_payable(line: ProcedureClaimLine) -> float:
    return float(line.expected_payable_try)


def detect_payment_method_violations(
    claim: ClaimHeader,
    lines: list[ProcedureClaimLine],
) -> list[dict[str, Any]]:
    care_setting: CareSetting = infer_care_setting(claim)  # type: ignore[assignment]
    violations: list[dict[str, Any]] = []

    for line in lines:
        if _line_billed(line) <= 0:
            continue
        billed_as_package = line.procedure_category == "paket"
        compliance = check_payment_method_compliance(
            line.procedure_code,
            billed_as_package=billed_as_package,
            care_setting=care_setting,
            facility_tier=claim.facility_tier,
            provider_type=claim.provider_type,
        )
        if compliance.is_compliant or compliance.mandated_method == "unknown":
            continue

        violations.append(
            {
                "procedure_line_id": line.procedure_line_id,
                "procedure_code": line.procedure_code,
                "procedure_name": line.procedure_name,
                "mandated_method": compliance.mandated_method,
                "billed_as_package": billed_as_package,
                "billed_amount_try": _money(_line_billed(line)),
                "sut_section": compliance.trace.sut_section,
                "rule_id": compliance.trace.rule_id,
                "detail": compliance.detail,
                "risk_amount_try": _money(_line_billed(line)),
            }
        )

    return violations


def detect_session_point_violations(
    lines: list[ProcedureClaimLine],
    *,
    same_incision: bool = True,
    cross_specialty: bool | None = None,
    claim: ClaimHeader | None = None,
) -> list[dict[str, Any]]:
    violations: list[dict[str, Any]] = []

    for session_date, session_lines in group_procedure_lines_by_session(lines).items():
        billable = [
            line
            for line in session_lines
            if not line.is_package_included and _line_billed(line) > 0
        ]
        if len(billable) < 2:
            continue

        codes = [line.procedure_code for line in billable]
        session_cross = (
            detect_cross_specialty_session(billable, claim)
            if cross_specialty is None
            else cross_specialty
        )
        session = compute_session_point_factors(
            codes,
            same_incision=same_incision,
            cross_specialty=session_cross,
        )
        if session.rule_id == "single_procedure":
            continue

        factors = {
            normalize_procedure_code(f.procedure_code): f for f in session.factors
        }
        primary_line = None
        primary_factor = 1.0
        for line in billable:
            factor = factors.get(normalize_procedure_code(line.procedure_code))
            if factor is not None and factor.is_primary:
                primary_line = line
                primary_factor = factor.point_factor
                break

        if primary_line is None or _line_billed(primary_line) <= 0:
            continue

        primary_billed = _line_billed(primary_line)

        for line in billable:
            if line.procedure_line_id == primary_line.procedure_line_id:
                continue
            factor = factors.get(normalize_procedure_code(line.procedure_code))
            if factor is None or factor.point_factor >= primary_factor:
                continue

            expected_billed = primary_billed * (factor.point_factor / primary_factor)
            actual_billed = _line_billed(line)
            if actual_billed <= expected_billed * (1.0 + _BILLING_TOLERANCE):
                continue

            overbill = actual_billed - expected_billed
            violations.append(
                {
                    "procedure_line_id": line.procedure_line_id,
                    "procedure_code": line.procedure_code,
                    "procedure_name": line.procedure_name,
                    "session_date": str(session_date),
                    "expected_point_factor": factor.point_factor,
                    "primary_procedure_code": primary_line.procedure_code,
                    "expected_billed_try": _money(expected_billed),
                    "actual_billed_try": _money(actual_billed),
                    "risk_amount_try": _money(max(0.0, overbill)),
                    "sut_section": session.sut_section,
                    "rule_id": session.rule_id,
                    "detail": (
                        f"Secondary procedure billed at full rate; SUT §{session.sut_section} "
                        f"requires {factor.point_factor:.0%} point factor in same session."
                    ),
                }
            )

    return violations


def detect_blood_component_violations(
    lines: list[ProcedureClaimLine],
) -> list[dict[str, Any]]:
    violations: list[dict[str, Any]] = []

    for line in lines:
        if line.is_package_included or _line_billed(line) <= 0:
            continue
        fraction = blood_component_billable_fraction(line.procedure_code)
        if fraction is None:
            continue

        payable = _line_payable(line)
        billed = _line_billed(line)
        reference = payable if payable > 0 else billed
        max_billable = reference * fraction
        if billed <= max_billable * (1.0 + _BILLING_TOLERANCE):
            continue

        violations.append(
            {
                "procedure_line_id": line.procedure_line_id,
                "procedure_code": line.procedure_code,
                "procedure_name": line.procedure_name,
                "allowed_fraction": fraction,
                "max_billable_try": _money(max_billable),
                "actual_billed_try": _money(billed),
                "risk_amount_try": _money(billed - max_billable),
                "sut_section": "2.2.2.B-1.e",
                "rule_id": "blood_component_partial_bill",
                "detail": (
                    f"Blood component {line.procedure_code} may only be billed at "
                    f"{fraction:.0%} of points in package context."
                ),
            }
        )

    return violations


def analyze_claim_unbundling(
    claim: ClaimHeader,
    lines: list[ProcedureClaimLine],
    *,
    same_incision: bool | None = None,
) -> ClaimUnbundlingFinding | None:
    if not lines:
        return None

    chapter = (claim.primary_icd10 or "R")[:1].upper()
    finding = ClaimUnbundlingFinding(claim_id=claim.claim_id, chapter=chapter)

    finding.bundled_violations = [
        {
            "procedure_line_id": line.procedure_line_id,
            "procedure_code": line.procedure_code,
            "procedure_name": line.procedure_name,
            "billed_amount_try": _money(_line_billed(line)),
            "expected_payable_try": _money(_line_payable(line)),
            "risk_amount_try": _money(max(0.0, _line_billed(line) - _line_payable(line))),
            "savings_basis": "heuristic",
            "detail": (
                "HEURISTIC — package-included flag on claim line; "
                "not verified against SUT §2.2 prose."
            ),
        }
        for line in lines
        if line.is_package_included and _line_billed(line) > 0
    ]

    finding.payment_method_violations = detect_payment_method_violations(claim, lines)
    if same_incision is not None:
        finding.session_violations = detect_session_point_violations(
            lines,
            same_incision=same_incision,
            claim=claim,
        )
    finding.blood_component_violations = detect_blood_component_violations(lines)

    finding.itemized_total_try = _money(
        sum(
            _line_payable(line)
            for line in lines
            if line.procedure_category != "paket" and not line.is_package_included
        )
    )
    finding.package_total_try = _money(
        sum(_line_payable(line) for line in lines if line.procedure_category == "paket")
    )

    sourced = 0.0
    for bucket in (
        finding.payment_method_violations,
        finding.session_violations,
        finding.blood_component_violations,
    ):
        sourced += sum(float(entry.get("risk_amount_try") or 0.0) for entry in bucket)

    heuristic_bundled = sum(
        float(entry.get("risk_amount_try") or 0.0) for entry in finding.bundled_violations
    )

    mandated_methods = {
        resolve_payment_method(
            line.procedure_code,
            care_setting=infer_care_setting(claim),  # type: ignore[arg-type]
            facility_tier=claim.facility_tier,
            provider_type=claim.provider_type,
        ).payment_method
        for line in lines
        if _line_billed(line) > 0 or _line_payable(line) > 0
    }
    mandated_methods.discard("unknown")

    heuristic_uplift = 0.0
    if (
        finding.package_total_try > 0
        and finding.itemized_total_try > finding.package_total_try
        and mandated_methods != {"package"}
    ):
        heuristic_uplift = finding.itemized_total_try - finding.package_total_try

    finding.sourced_savings_try = _money(sourced)
    finding.heuristic_savings_try = _money(heuristic_bundled + heuristic_uplift)
    finding.itemized_package_uplift_try = _money(heuristic_uplift)
    finding.potential_savings_try = _money(sourced + heuristic_bundled + heuristic_uplift)
    return finding


def finding_to_dict(finding: ClaimUnbundlingFinding) -> dict[str, Any]:
    return {
        "claim_id": finding.claim_id,
        "chapter": finding.chapter,
        "bundled_violations": len(finding.bundled_violations),
        "payment_method_violations": len(finding.payment_method_violations),
        "session_violations": len(finding.session_violations),
        "blood_component_violations": len(finding.blood_component_violations),
        "itemized_total_try": finding.itemized_total_try,
        "package_total_try": finding.package_total_try,
        "potential_savings_try": finding.potential_savings_try,
        "sourced_savings_try": finding.sourced_savings_try,
        "heuristic_savings_try": finding.heuristic_savings_try,
        "itemized_package_uplift_try": finding.itemized_package_uplift_try,
        "violations": {
            "bundled": finding.bundled_violations,
            "payment_method": finding.payment_method_violations,
            "session": finding.session_violations,
            "blood_component": finding.blood_component_violations,
        },
    }
