"""SUT §2.2 prose checks for DRG unbundling on exact claim lines."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from .claim_utils import claim_is_day_case, infer_care_setting
from ..money import money_round_half_up as _money
from .mandated_package_gap import line_payment_method_compliance, mandated_package_gap
from .payment_method import resolve_payment_method
from .session_pricing import (
    billed_package_scopes,
    blood_component_billable_fraction,
    expected_session_billed_try,
)
from .session_scope import line_billed_as_package
from .session_uplift import (
    REVIEW_KIND_CLINICAL,
    iter_session_secondary_assessments,
    session_money_note_tr,
    session_review_detail_tr,
)
from .yatak_puani import c000672_hizmet_basi_lines

if TYPE_CHECKING:
    from src.bilun.domain.claims.models import (
        ClaimHeader,
        DrugClaimLine,
        MaterialClaimLine,
        ProcedureClaimLine,
    )

_BILLING_TOLERANCE = 0.02


@dataclass
class ClaimUnbundlingFinding:
    claim_id: str
    chapter: str
    bundled_violations: list[dict[str, Any]] = field(default_factory=list)
    payment_method_violations: list[dict[str, Any]] = field(default_factory=list)
    session_violations: list[dict[str, Any]] = field(default_factory=list)
    # 0-TL "kontrol et" rows: correct under one reading of a fact the bill does
    # not show, over-billed under the other. Never risk, never ``has_risk``.
    session_reviews: list[dict[str, Any]] = field(default_factory=list)
    blood_component_violations: list[dict[str, Any]] = field(default_factory=list)
    itemized_total_try: float = 0.0
    package_total_try: float = 0.0
    potential_savings_try: float = 0.0
    sourced_savings_try: float = 0.0
    heuristic_savings_try: float = 0.0
    itemized_package_uplift_try: float = 0.0

    @property
    def has_risk(self) -> bool:
        return self.sourced_savings_try > 0 or bool(
            self.bundled_violations
            or self.payment_method_violations
            or self.session_violations
            or self.blood_component_violations
        )


def _line_billed(line: ProcedureClaimLine) -> float:
    return float(line.billed_amount_try)


def _line_payable(line: ProcedureClaimLine) -> float:
    return float(line.expected_payable_try)


def detect_payment_method_violations(
    claim: ClaimHeader,
    lines: list[ProcedureClaimLine],
) -> list[dict[str, Any]]:
    violations: list[dict[str, Any]] = []
    # C000672: a session an EK-2/B operation leads is billed hizmet başı in full.
    hizmet_basi = {id(line) for line in c000672_hizmet_basi_lines(claim, lines)}

    for line in lines:
        if _line_billed(line) <= 0 or id(line) in hizmet_basi:
            continue
        billed_as_package = line_billed_as_package(line)
        # On the line's procedure date, as the #269 gate reads it.
        compliance = line_payment_method_compliance(claim, line)
        if compliance.is_compliant or compliance.mandated_method == "unknown":
            continue

        violation_row: dict[str, Any] = {
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
        if compliance.message_code:
            violation_row["message_code"] = compliance.message_code
            violation_row["message_params"] = compliance.message_params
        violations.append(violation_row)

    return violations


def _session_point_rows(
    lines: list[ProcedureClaimLine],
    *,
    same_incision: bool | None,
    cross_specialty: bool | None,
    claim: ClaimHeader | None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Session money rows and 0-TL review rows (``detect_session_point_violations``)."""
    violations: list[dict[str, Any]] = []
    reviews: list[dict[str, Any]] = []

    for assessment in iter_session_secondary_assessments(
        lines, same_incision=same_incision, cross_specialty=cross_specialty, claim=claim,
    ):
        line, strict, lenient = assessment.line, assessment.factor, assessment.lenient
        # The line's own clause: in a mixed session a package secondary is
        # §2.2.2.B(3)(a)/(b), an EK-2/B one (c)/(ç).
        strict_expected = expected_session_billed_try(line, point_factor=strict.point_factor)
        lenient_expected = expected_session_billed_try(line, point_factor=lenient.point_factor)
        actual_billed = _line_billed(line)
        if strict_expected is None or lenient_expected is None:
            continue
        if actual_billed <= strict_expected * (1.0 + _BILLING_TOLERANCE):
            continue
        row: dict[str, Any] = {
            "procedure_line_id": line.procedure_line_id,
            "procedure_code": line.procedure_code,
            "procedure_name": line.procedure_name,
            "session_date": str(assessment.session_date),
            "primary_procedure_code": assessment.primary_line.procedure_code,
            "actual_billed_try": _money(actual_billed),
        }
        readings = {} if not assessment.missing_facts else {
            "missing_facts": list(assessment.missing_facts),
            "strict_point_factor": strict.point_factor,
            "strict_expected_billed_try": _money(strict_expected),
            "lenient_point_factor": lenient.point_factor,
            "lenient_expected_billed_try": _money(lenient_expected),
        }
        if actual_billed <= lenient_expected * (1.0 + _BILLING_TOLERANCE):
            # Correct under the lenient reading, over-billed under the strict one.
            reviews.append({
                **row,
                "expected_point_factor": strict.point_factor,
                "expected_billed_try": _money(strict_expected),
                "risk_amount_try": 0.0,
                "review_risk_try": _money(actual_billed - strict_expected),
                "review_kind": REVIEW_KIND_CLINICAL,
                "sut_section": strict.trace.sut_section,
                "rule_id": strict.trace.rule_id,
                "detail": session_review_detail_tr(
                    assessment, actual_billed_try=actual_billed,
                    strict_expected_try=strict_expected,
                    lenient_expected_try=lenient_expected, overbilled=True,
                ),
                **readings,
            })
            continue

        detail = (
            f"Secondary procedure billed at full rate; SUT §{lenient.trace.sut_section} "
            f"requires {lenient.point_factor:.0%} point factor in same session."
        )
        if assessment.missing_facts:
            detail += " " + session_money_note_tr(
                assessment, other_reading_extra_try=lenient_expected - strict_expected,
                overbilled=True,
            )
            readings["review_risk_try"] = _money(lenient_expected - strict_expected)
        violations.append({
            **row,
            "expected_point_factor": lenient.point_factor,
            "expected_billed_try": _money(lenient_expected),
            "risk_amount_try": _money(max(0.0, actual_billed - lenient_expected)),
            "sut_section": lenient.trace.sut_section,
            "rule_id": lenient.trace.rule_id,
            "detail": detail,
            **readings,
        })

    return violations, reviews


def detect_session_point_violations(
    lines: list[ProcedureClaimLine],
    *,
    same_incision: bool | None = None,
    cross_specialty: bool | None = None,
    claim: ClaimHeader | None = None,
) -> list[dict[str, Any]]:
    """Secondaries billed above their §2.2.2.A(5) / B(3) session factor.

    Sessions and factors come from ``iter_session_secondary_assessments``, the
    uplift side's, which pairs factors with lines by occurrence: MEDULA sends one
    line per occurrence, so a repeated code keeps its primary. No claim line
    carries the incision, and a line may lack its branch: then the money is only
    what the bill overstates under the most lenient legal reading (separate
    incision, +25 points; Safa, 2026-10-16, "2b"), and a line between the two
    readings gets a 0-TL review row (``detect_session_point_reviews``) instead.
    A known ``same_incision`` / ``cross_specialty`` keeps the single reading.
    """
    return _session_point_rows(
        lines, same_incision=same_incision, cross_specialty=cross_specialty, claim=claim,
    )[0]


def detect_session_point_reviews(
    lines: list[ProcedureClaimLine],
    *,
    same_incision: bool | None = None,
    cross_specialty: bool | None = None,
    claim: ClaimHeader | None = None,
) -> list[dict[str, Any]]:
    """0-TL "kontrol et" rows: secondaries billed above the strict reading only.

    Each names the fact the bill does not show (kesi bilgisi / branş bilgisi).
    """
    return _session_point_rows(
        lines, same_incision=same_incision, cross_specialty=cross_specialty, claim=claim,
    )[1]


def detect_blood_component_violations(
    lines: list[ProcedureClaimLine],
) -> list[dict[str, Any]]:
    violations: list[dict[str, Any]] = []
    package_scopes = billed_package_scopes(lines)

    for line in lines:
        if (line.patient_id, line.claim_id, line.episode_id) not in package_scopes:
            continue
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


def _apply_mandated_package_gap(
    finding: ClaimUnbundlingFinding,
    claim: ClaimHeader,
    lines: list[ProcedureClaimLine],
    *,
    drug_lines: Sequence[DrugClaimLine],
    material_lines: Sequence[MaterialClaimLine],
) -> None:
    """A hizmet başı bill whose package is mandated is re-priced as that package (#269).

    The package replaces the lines inside its window, so the money at risk on
    them is what the bill overstates (``MandatedPackageGap.excess_try``): 0 when
    the package pays at least as much under the most lenient reading, never the
    full lines. The rows stay as findings (SUT §2.2.2(1)) and share the excess:
    the must-package rows first, then the session rows of the covered lines,
    each in its detector's order and up to the risk it showed alone. The
    replaced lines without a row (tests, stay, drugs) leave their part on the
    first must-package row, which also carries what the strict reading alone
    would add (``review_risk_try``, 0-TL). The package prices the covered
    lines, so their session reviews go. The billing strategy row reports the
    same comparison.
    """
    gap = mandated_package_gap(
        claim, lines, drug_lines=drug_lines, material_lines=material_lines,
    )
    if gap is None:
        return
    covered = gap.replaced_line_ids
    finding.session_reviews = [
        row for row in finding.session_reviews if row["procedure_line_id"] not in covered
    ]
    package_rows = [
        row for row in finding.payment_method_violations
        if row["mandated_method"] == "package" and not row["billed_as_package"]
        and row["procedure_line_id"] in covered
    ]
    session_rows = [
        row for row in finding.session_violations if row["procedure_line_id"] in covered
    ]
    rows = [*package_rows, *session_rows]
    left = gap.excess_try
    for row in rows:
        share = min(left, float(row["risk_amount_try"]))
        row["risk_amount_try"] = _money(share)
        left = _money(left - share)
        row["package_total_try"] = gap.package_total_try
        row["billed_itemized_total_try"] = gap.replaced_total_try
        if gap.lenient_package_total_try is not None:
            row["package_total_lenient_try"] = gap.lenient_package_total_try
    if left > 0 and package_rows:
        package_rows[0]["risk_amount_try"] = _money(package_rows[0]["risk_amount_try"] + left)
    if gap.review_excess_try > 0 and package_rows:
        package_rows[0]["review_risk_try"] = gap.review_excess_try


def _net_session_risk_of_payment_method_risk(finding: ClaimUnbundlingFinding) -> None:
    """A line's exposure never exceeds what was billed on it.

    A must-package line billed hizmet başı already puts its billed amount at
    risk (payment-method row); a session factor on the same line is part of
    that money, so it adds only what the payment-method row leaves.
    """
    counted: dict[str, float] = {}
    for row in finding.payment_method_violations:
        line_id = str(row.get("procedure_line_id") or "")
        counted[line_id] = counted.get(line_id, 0.0) + float(row.get("risk_amount_try") or 0.0)
    for row in finding.session_violations:
        already = counted.get(str(row.get("procedure_line_id") or ""), 0.0)
        if already <= 0:
            continue
        left = float(row["actual_billed_try"]) - already
        row["risk_amount_try"] = _money(max(0.0, min(float(row["risk_amount_try"]), left)))


def analyze_claim_unbundling(
    claim: ClaimHeader,
    lines: list[ProcedureClaimLine],
    *,
    same_incision: bool | None = None,
    drug_lines: Sequence[DrugClaimLine] = (),
    material_lines: Sequence[MaterialClaimLine] = (),
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
            "savings_basis": "audit_flag",
            "detail": (
                "HEURISTIC — package-included flag on claim line; "
                "not verified against SUT §2.2 prose."
            ),
        }
        for line in lines
        if line.is_package_included and _line_billed(line) > 0
    ]

    finding.payment_method_violations = detect_payment_method_violations(claim, lines)
    # ``same_incision`` None: the bill does not show the incision (no claim line
    # carries it), so session money is taken above the most lenient reading.
    finding.session_violations, reviews = _session_point_rows(
        lines, same_incision=same_incision, cross_specialty=None, claim=claim,
    )
    # A line billed by the wrong method is at risk as a whole; its session
    # factor is no separate question.
    wrong_method = {row["procedure_line_id"] for row in finding.payment_method_violations}
    finding.session_reviews = [
        row for row in reviews if row["procedure_line_id"] not in wrong_method
    ]
    # Net first: the gap shares its excess by the risk each row shows alone.
    _net_session_risk_of_payment_method_risk(finding)
    _apply_mandated_package_gap(
        finding,
        claim,
        lines,
        drug_lines=drug_lines,
        material_lines=material_lines,
    )
    finding.blood_component_violations = detect_blood_component_violations(lines)

    finding.itemized_total_try = _money(
        sum(
            _line_payable(line)
            for line in lines
            if not line_billed_as_package(line) and not line.is_package_included
        )
    )
    finding.package_total_try = _money(
        sum(_line_payable(line) for line in lines if line_billed_as_package(line))
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
            day_case=claim_is_day_case(claim),
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
    finding.potential_savings_try = finding.sourced_savings_try
    return finding


def finding_to_dict(finding: ClaimUnbundlingFinding) -> dict[str, Any]:
    return {
        "claim_id": finding.claim_id,
        "chapter": finding.chapter,
        "bundled_violations": len(finding.bundled_violations),
        "payment_method_violations": len(finding.payment_method_violations),
        "session_violations": len(finding.session_violations),
        "session_reviews": len(finding.session_reviews),
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
            "session_review": finding.session_reviews,
            "blood_component": finding.blood_component_violations,
        },
    }
