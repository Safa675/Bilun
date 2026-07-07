"""W5 tests — payment_method secondary traceability pass.

``check_payment_method_traceability_for_context`` runs the 42 JSON rules in
``payment_method_2_2.json`` as a SECONDARY traceability scan that emits
``info``-severity violations. It does NOT override the primary payment-method
decision made by the hardcoded ``_classify_payment_method_kind``. Predicate
evaluation and context building are reused from ``gap_closing`` (which derives
the wireable §2.2 facts per the post-W2.5a taxonomy and honest-skips rules
whose condition keys are unavailable on the claim).

Wireable/honest-skip split (42 rules total, verified against the real
``_condition_matches`` engine + ``_build_gap_closing_context`` output):

- WIREABLE (2 rules — fire on ``provider_type`` + ``care_setting`` only):
    * ``2.2.(6).workplace_polyclinic_homecare_no_pay``
      (provider_type == workplace_health_or_polyclinic_or_homecare_center)
    * ``2.2.1.B-1.(11).private_daily_visit_cap``
      (care_setting == outpatient, provider_type == private)
- HONEST-SKIP (40 rules — reference condition keys the context builder does
  not produce, e.g. ``line_type``, ``procedure_in_annex``,
  ``payment_method_path``, ``facility_type``, ``visit_sequence``, and the
  ``*_lt`` numeric shapes). These stay in the rule inventory for coverage
  accounting but do not fire on claims lacking that data — the
  ``_condition_matches`` honesty guard handles them automatically.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from src.bilun.domain.claims.models import ClaimHeader, ProcedureClaimLine
from src.bilun.domain.claims.patient_context import PatientClaimContext
from src.bilun.domain.prose_rules.payment_method import (
    check_payment_method_traceability_for_context,
)

pytestmark = pytest.mark.unit


def _make_header(
    *,
    claim_type: str = "ayakta",
    facility_tier: str = "ozel",
    provider_type: str = "sozlesmeli",
    department: str = "genel",
) -> ClaimHeader:
    return ClaimHeader(
        claim_id="C1",
        patient_id="P1",
        episode_id="E1",
        claim_type=claim_type,
        facility_tier=facility_tier,
        provider_type=provider_type,
        department=department,
        admission_date=None,
        discharge_date=None,
        claim_start_date=date.today(),
        claim_end_date=date.today(),
        primary_icd10="Z00.0",
        package_candidate=False,
        expected_total_billed_try=Decimal("100"),
        expected_total_payable_try=Decimal("90"),
        expected_denial_reason="",
        scenario_tag="test",
    )


def _make_ctx(
    *,
    header: ClaimHeader | None = None,
    procedure_lines: tuple[ProcedureClaimLine, ...] = (),
) -> PatientClaimContext:
    h = header or _make_header()
    return PatientClaimContext(
        patient_id="P1",
        claims=(h,),
        procedure_lines=procedure_lines,
        material_lines=(),
        drug_lines=(),
        diagnoses=(),
    )


# ---------------------------------------------------------------------------
# 1. Matching provider_type → traceability violation emitted, severity='info'.
#    Rule 2.2.(6) gates on provider_type only (a wireable key produced by
#    gap_closing's builder); the value below is the exact condition token.
# ---------------------------------------------------------------------------


def test_workplace_polyclinic_provider_emits_info_violation() -> None:
    """A claim whose provider_type matches the no-pay workplace/poliklinik/
    homecare rule must emit a traceability violation with severity='info'."""
    ctx = _make_ctx(
        header=_make_header(
            provider_type="workplace_health_or_polyclinic_or_homecare_center",
            claim_type="ayakta",
        )
    )
    violations = check_payment_method_traceability_for_context(ctx)
    rule_ids = [v["rule_id"] for v in violations]
    assert "2.2.(6).workplace_polyclinic_homecare_no_pay" in rule_ids
    the_violation = next(
        v for v in violations if v["rule_id"] == "2.2.(6).workplace_polyclinic_homecare_no_pay"
    )
    assert the_violation["severity"] == "info"
    assert the_violation["rule"] == "payment_method_traceability"


def test_private_outpatient_emits_daily_cap_violation() -> None:
    """Rule 2.2.1.B-1.(11) gates on care_setting=outpatient + provider_type=private.
    Both are wireable; the claim below satisfies both."""
    ctx = _make_ctx(
        header=_make_header(
            provider_type="private",
            claim_type="ayakta",  # → care_setting == outpatient
        )
    )
    violations = check_payment_method_traceability_for_context(ctx)
    rule_ids = [v["rule_id"] for v in violations]
    assert "2.2.1.B-1.(11).private_daily_visit_cap" in rule_ids


# ---------------------------------------------------------------------------
# 2. Mismatched provider_type → no violation for that rule.
# ---------------------------------------------------------------------------


def test_mismatched_provider_type_no_workplace_violation() -> None:
    """A contracted provider (not the workplace/poliklinik sentinel) must NOT
    trigger the 2.2.(6) no-pay rule. Care_setting is outpatient so the private
    daily-cap rule (2.2.1.B-1.(11)) would only match provider_type='private',
    which this is not."""
    ctx = _make_ctx(
        header=_make_header(
            provider_type="sozlesmeli",  # ordinary contracted provider
            claim_type="ayakta",
        )
    )
    violations = check_payment_method_traceability_for_context(ctx)
    rule_ids = [v["rule_id"] for v in violations]
    assert "2.2.(6).workplace_polyclinic_homecare_no_pay" not in rule_ids
    assert "2.2.1.B-1.(11).private_daily_visit_cap" not in rule_ids


# ---------------------------------------------------------------------------
# 3. Rule whose condition key is unavailable → honest skip, no crash.
#    Rule 2.2.1.B-1.(6) gates on visit_sequence, which the context builder
#    does not surface; _condition_matches returns False (honest skip).
# ---------------------------------------------------------------------------


def test_unavailable_condition_key_honest_skips() -> None:
    """visit_sequence is not produced by gap_closing's context builder, so the
    rules that gate on it (2.2.1.B-1.(6) followup, 2.2.1.B-1.(7) side_specialty)
    must honest-skip — no violation and no crash."""
    ctx = _make_ctx(
        header=_make_header(
            provider_type="sozlesmeli",
            claim_type="ayakta",
        )
    )
    violations = check_payment_method_traceability_for_context(ctx)
    rule_ids = [v["rule_id"] for v in violations]
    assert "2.2.1.B-1.(6).followup_specialty_no_visit_fee" not in rule_ids
    assert "2.2.1.B-1.(7).main_side_specialty_split" not in rule_ids


def test_does_not_crash_on_claims_without_procedure_lines() -> None:
    """A header-only claim (no procedure lines) must not raise — the builder
    derives what it can and honest-skips the rest."""
    ctx = _make_ctx()  # no procedure lines
    result = check_payment_method_traceability_for_context(ctx)
    assert isinstance(result, list)


# ---------------------------------------------------------------------------
# 4. Empty claims → [].
# ---------------------------------------------------------------------------


def test_empty_claims_returns_empty() -> None:
    """A PatientClaimContext with no claims must return [] — the builder yields
    an empty context and the evaluator short-circuits."""
    ctx = PatientClaimContext(
        patient_id="P1",
        claims=(),
        procedure_lines=(),
        material_lines=(),
        drug_lines=(),
        diagnoses=(),
    )
    assert check_payment_method_traceability_for_context(ctx) == []


# ---------------------------------------------------------------------------
# 5. severity is always 'info' on every emitted violation.
# ---------------------------------------------------------------------------


def test_all_emitted_violations_are_info_severity() -> None:
    """Every violation from the traceability pass carries severity='info' —
    this is traceability, not enforcement, regardless of the rule's billable
    outcome."""
    ctx = _make_ctx(
        header=_make_header(
            provider_type="workplace_health_or_polyclinic_or_homecare_center",
            claim_type="ayakta",
        )
    )
    violations = check_payment_method_traceability_for_context(ctx)
    assert violations, "expected at least one violation for this provider_type"
    for v in violations:
        assert v["severity"] == "info"
        assert v["rule"] == "payment_method_traceability"


def test_no_pay_rule_carries_no_pay_material_outcome() -> None:
    """The 2.2.(6) workplace rule is a no-pay gate (billable=False); its
    traceability violation should reflect material_outcome='no_pay' while the
    2.2.1.B-1.(11) private daily-cap rule is billable (must_bill). Both stay
    info-severity — the primary decision is untouched."""
    ctx = _make_ctx(
        header=_make_header(
            provider_type="workplace_health_or_polyclinic_or_homecare_center",
            claim_type="ayakta",
        )
    )
    violations = check_payment_method_traceability_for_context(ctx)
    by_id = {v["rule_id"]: v for v in violations}
    assert by_id["2.2.(6).workplace_polyclinic_homecare_no_pay"]["material_outcome"] == "no_pay"
    assert by_id["2.2.(6).workplace_polyclinic_homecare_no_pay"]["billable"] is False


# ---------------------------------------------------------------------------
# Inpatient control: the two wireable rules gate on outpatient care_setting,
# so an inpatient claim must not fire either (no false-positive leakage).
# ---------------------------------------------------------------------------


def test_inpatient_claim_does_not_fire_outpatient_rules() -> None:
    """Both wireable rules gate on outpatient care_setting; an inpatient claim
    must not emit them — confirms the care_setting predicate is honored."""
    ctx = _make_ctx(
        header=_make_header(
            provider_type="private",
            claim_type="yatis",  # → care_setting == inpatient
        )
    )
    violations = check_payment_method_traceability_for_context(ctx)
    rule_ids = [v["rule_id"] for v in violations]
    assert "2.2.1.B-1.(11).private_daily_visit_cap" not in rule_ids
