"""W3 tests — multi-category scalar fallback for treatment-pricing rules.

When a claim carries mixed procedure categories (e.g. FTR + muayene), the
context builder surfaces the full set under ``procedure_category_any`` and
leaves the bare ``procedure_category`` scalar UNSET (so exact-equality rules
do not mis-attribute to one category). Before the fix in
``_condition_matches``, ~130 single-value scalar rules
(``procedure_category: "physiotherapy_rehab"``) honest-skipped on any
mixed-category claim because their scalar key was absent from the context.

The fix: when a scalar key (``X``) is checked and absent from the context,
``_condition_matches`` falls back to membership in the ``X_any`` collection.
This module exercises that fallback directly and end-to-end with a real rule.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from src.bilun.domain.claims.models import (
    ClaimDiagnosis,
    ClaimHeader,
    ProcedureClaimLine,
)
from src.bilun.domain.claims.patient_context import PatientClaimContext
from src.bilun.domain.prose_rules.treatment_pricing import (
    _build_treatment_pricing_context,
    _condition_matches,
    check_treatment_pricing_for_context,
    load_treatment_pricing_rules,
)

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Fixture builders — minimal dataclass instances (mirrors the for_context
# test module so the assertions stay concrete).
# ---------------------------------------------------------------------------


def _make_header(
    *,
    claim_id: str = "C1",
    facility_tier: str = "ozel",
    provider_type: str = "sozlesmeli",
    primary_icd10: str = "Z00.0",
) -> ClaimHeader:
    return ClaimHeader(
        claim_id=claim_id,
        patient_id="P1",
        episode_id="E1",
        claim_type="ayakta",
        facility_tier=facility_tier,
        provider_type=provider_type,
        department="genel",
        admission_date=None,
        discharge_date=None,
        claim_start_date=date.today(),
        claim_end_date=date.today(),
        primary_icd10=primary_icd10,
        package_candidate=False,
        expected_total_billed_try=Decimal("100"),
        expected_total_payable_try=Decimal("90"),
        expected_denial_reason="",
        scenario_tag="test",
    )


def _make_procedure(
    *,
    code: str = "P000001",
    category: str = "physiotherapy_rehab",
    claim_id: str = "C1",
    proc_date: date | None = None,
    line_id: str = "PL1",
) -> ProcedureClaimLine:
    return ProcedureClaimLine(
        procedure_line_id=line_id,
        claim_id=claim_id,
        patient_id="P1",
        episode_id="E1",
        procedure_date=proc_date or date.today(),
        procedure_code=code,
        procedure_name="Test procedure",
        procedure_category=category,
        quantity=1,
        unit_price_try=Decimal("100"),
        billed_amount_try=Decimal("100"),
        expected_payable_try=Decimal("90"),
        is_package_included=False,
        package_code="",
        surcharge_applicable=False,
        copay_rate_applicable=False,
        denial_reason_expected="",
        rule_trace_expected="",
    )


def _make_diagnosis(*, code: str = "M54.5", claim_id: str = "C1") -> ClaimDiagnosis:
    return ClaimDiagnosis(
        diagnosis_id="D1",
        claim_id=claim_id,
        patient_id="P1",
        episode_id="E1",
        icd10_code=code,
        is_primary=True,
        diagnosis_role="primary",
        diagnosis_date=date.today(),
        exemption_eligible=False,
    )


def _make_ctx(
    *,
    procedure_lines: tuple[ProcedureClaimLine, ...],
    diagnoses: tuple[ClaimDiagnosis, ...] = (),
    header: ClaimHeader | None = None,
) -> PatientClaimContext:
    return PatientClaimContext(
        patient_id="P1",
        claims=(header or _make_header(),),
        procedure_lines=procedure_lines,
        material_lines=(),
        drug_lines=(),
        diagnoses=diagnoses,
    )


# ---------------------------------------------------------------------------
# 1. Scalar fallback in _condition_matches — mixed-category claim
# ---------------------------------------------------------------------------


def test_scalar_procedure_category_matches_via_any_fallback() -> None:
    """On a mixed-category claim the bare ``procedure_category`` scalar is
    absent; a rule gating on the scalar MUST still match via the
    ``procedure_category_any`` fallback (the rule's value is one of the
    categories present on the claim).
    """
    context = {
        # Bare scalar intentionally absent (multi-category claim).
        "procedure_category_any": ["muayene", "physiotherapy_rehab"],
    }
    assert (
        _condition_matches({"procedure_category": "physiotherapy_rehab"}, context)
        is True
    )
    # A category NOT on the claim must honest-skip.
    assert (
        _condition_matches({"procedure_category": "radiosurgery"}, context) is False
    )


def test_scalar_procedure_category_absent_everywhere_honest_skips() -> None:
    """Neither the scalar nor the *_any collection surfaced → honest skip."""
    assert _condition_matches({"procedure_category": "ftr"}, {}) is False


# ---------------------------------------------------------------------------
# 2. Single-category claim — bare scalar path still works (no regression)
# ---------------------------------------------------------------------------


def test_single_category_still_matches_via_scalar() -> None:
    """A single-category claim sets the bare ``procedure_category`` scalar;
    the exact-equality path must still fire without relying on the fallback.
    """
    ctx = _make_ctx(procedure_lines=(_make_procedure(category="physiotherapy_rehab"),))
    context = _build_treatment_pricing_context(ctx)
    assert context["procedure_category"] == "physiotherapy_rehab"
    assert (
        _condition_matches({"procedure_category": "physiotherapy_rehab"}, context)
        is True
    )


# ---------------------------------------------------------------------------
# 3. End-to-end: a real scalar-gated rule fires on a MIXED-category claim
# ---------------------------------------------------------------------------


def test_scalar_rule_fires_on_mixed_category_claim_end_to_end() -> None:
    """End-to-end: rule ``2.4.4.F-2.(4).physio_session_cap_per_day`` gates on
    the scalar ``procedure_category: "physiotherapy_rehab"`` plus
    ``sessions_per_day: {min: 2}`` and ``diagnosis_not_in: ["G80"]``.

    The claim mixes FTR with ``muayene`` on the same date (so the bare
    ``procedure_category`` scalar is unset and ``sessions_per_day == 2``).
    Before the fix this rule honest-skipped because the scalar was absent;
    after the fix it fires via the ``procedure_category_any`` fallback.

    Guarded: if the rule id or its condition drifts, the test skips rather
    than mis-reporting.
    """
    rules = {r["rule_id"]: (r.get("condition") or {}) for r in load_treatment_pricing_rules()["rules"]}
    rule_id = "2.4.4.F-2.(4).physio_session_cap_per_day"
    cond = rules.get(rule_id)
    if cond is None:
        pytest.skip(f"rule {rule_id} no longer present in the rule set")
    if cond.get("procedure_category") != "physiotherapy_rehab":
        pytest.skip(f"rule {rule_id} no longer gates on scalar physiotherapy_rehab")

    today = date.today()
    # Two FTR lines + one muayene line on the same date → sessions_per_day == 3
    # and a mixed category set {physiotherapy_rehab, muayene}.
    procs = (
        _make_procedure(code="P530010", category="physiotherapy_rehab", proc_date=today, line_id="PL1"),
        _make_procedure(code="P530011", category="physiotherapy_rehab", proc_date=today, line_id="PL2"),
        _make_procedure(code="P000012", category="muayene", proc_date=today, line_id="PL3"),
    )
    ctx = _make_ctx(
        procedure_lines=procs,
        diagnoses=(_make_diagnosis(code="M54.5"),),  # not G80 → diagnosis_not_in passes
    )
    context = _build_treatment_pricing_context(ctx)

    # Precondition: this is genuinely a mixed-category claim.
    assert set(context["procedure_category_any"]) == {"physiotherapy_rehab", "muayene"}
    assert "procedure_category" not in context
    assert context["sessions_per_day"] >= 2

    # The rule fires via the *_any fallback despite the bare scalar being unset.
    violations = check_treatment_pricing_for_context(ctx)
    rule_ids = {v["rule_id"] for v in violations}
    assert rule_id in rule_ids


def test_scalar_rule_honest_skips_when_category_not_present() -> None:
    """Same rule, but the claim carries NONE of the gated category. Even with
    the *_any fallback, the rule must honest-skip (the rule's value is not in
    the surfaced collection). Uses a hemodialysis-only claim.
    """
    today = date.today()
    procs = (
        _make_procedure(code="P501001", category="hemodialysis", proc_date=today, line_id="PL1"),
        _make_procedure(code="P501002", category="hemodialysis", proc_date=today, line_id="PL2"),
    )
    ctx = _make_ctx(
        procedure_lines=procs,
        diagnoses=(_make_diagnosis(code="N18.9"),),
    )
    context = _build_treatment_pricing_context(ctx)
    # Single distinct category → bare scalar is set; fallback is not needed,
    # and the value still does not match.
    assert context["procedure_category"] == "hemodialysis"

    violations = check_treatment_pricing_for_context(ctx)
    rule_ids = {v["rule_id"] for v in violations}
    assert "2.4.4.F-2.(4).physio_session_cap_per_day" not in rule_ids
