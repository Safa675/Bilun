"""W3 tests — treatment_pricing §2.4 ``check_treatment_pricing_for_context`` wrapper.

Mirrors the structure of ``test_gap_closing_for_context.py``: hand-built
``PatientClaimContext`` fixtures driving the real context builder + evaluator.
The wireable rules exercised here are real entries from
``treatment_pricing_2_4.json`` (verified at module-load time so the tests stay
honest if the JSON changes).
"""

from __future__ import annotations

import dataclasses
from datetime import date
from decimal import Decimal

import pytest

from src.bilun.domain.claims.models import (
    ClaimDiagnosis,
    ClaimHeader,
    DrugClaimLine,
    ProcedureClaimLine,
)
from src.bilun.domain.claims.patient_context import PatientClaimContext
from src.bilun.domain.prose_rules.treatment_pricing import (
    _build_treatment_pricing_context,
    _condition_matches,
    _diagnosis_matches,
    check_treatment_pricing_for_context,
    load_treatment_pricing_rules,
)
from tests.unit._helpers.brittle_guards import soft_floor

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Fixture builders — minimal dataclass instances for one patient/claim.
# ---------------------------------------------------------------------------


def _make_header(
    *,
    claim_id: str = "C1",
    claim_type: str = "ayakta",
    facility_tier: str = "ozel",
    provider_type: str = "sozlesmeli",
    department: str = "genel",
    primary_icd10: str = "Z00.0",
) -> ClaimHeader:
    return ClaimHeader(
        claim_id=claim_id,
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
        primary_icd10=primary_icd10,
        package_candidate=False,
        expected_total_billed_try=Decimal("100"),
        expected_total_payable_try=Decimal("90"),
        expected_denial_reason="",
        scenario_tag="test",
    )


def _make_procedure(
    *,
    code: str = "P704941",
    category: str = "extracorporeal_photopheresis",
    claim_id: str = "C1",
) -> ProcedureClaimLine:
    return ProcedureClaimLine(
        procedure_line_id="PL1",
        claim_id=claim_id,
        patient_id="P1",
        episode_id="E1",
        procedure_date=date.today(),
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


def _make_diagnosis(*, code: str = "N18.9", claim_id: str = "C1") -> ClaimDiagnosis:
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


def _make_drug(
    *,
    board_report: bool | None = False,
    claim_id: str = "C1",
) -> DrugClaimLine:
    return DrugClaimLine(
        drug_claim_line_id="DR1",
        prescription_id="RX1",
        claim_id=claim_id,
        patient_id="P1",
        episode_id="E1",
        drug_claim_date=date.today(),
        drug_name="Test drug",
        drug_code="D1",
        barkod="",
        equivalence_group="",
        quantity=1,
        unit_price_try=Decimal("50"),
        billed_amount_try=Decimal("50"),
        expected_payable_try=Decimal("45"),
        discount_tier_expected=Decimal("0"),
        denial_reason_expected="",
        rule_trace_expected="",
        drug_specialty_board_report_present=board_report,
    )


def _make_ctx(
    *,
    header: ClaimHeader | None = None,
    procedure_lines: tuple[ProcedureClaimLine, ...] = (),
    drug_lines: tuple[DrugClaimLine, ...] = (),
    diagnoses: tuple[ClaimDiagnosis, ...] = (),
) -> PatientClaimContext:
    h = header or _make_header()
    return PatientClaimContext(
        patient_id="P1",
        claims=(h,),
        procedure_lines=procedure_lines,
        material_lines=(),
        drug_lines=drug_lines,
        diagnoses=diagnoses,
    )


# ---------------------------------------------------------------------------
# Smoke / builder tests
# ---------------------------------------------------------------------------


def test_smoke_loads_all_treatment_pricing_rules() -> None:
    """The loader returns the full rule set; the evaluator only fires wireable ones."""
    rules = load_treatment_pricing_rules()
    assert rules["rule_set_id"] == "treatment_pricing_2_4"
    # Soft floor: corpus grows with SUT encodes (was 193 → 202 at 2026-07-01).
    soft_floor(len(rules["rules"]), 180, label="treatment_pricing_2_4")


def test_build_context_maps_header_fields() -> None:
    """provider_type and facility_tier are surfaced from the header."""
    ctx = _make_ctx(header=_make_header(provider_type="private", facility_tier="devlet"))
    context = _build_treatment_pricing_context(ctx)
    assert context["provider_type"] == "private"
    assert context["facility_tier"] == "devlet"


# ---------------------------------------------------------------------------
# 1. procedure-category-triggered rule FIRES (positive)
# ---------------------------------------------------------------------------


def test_procedure_category_rule_fires() -> None:
    """A procedure-category-only rule fires when the claim carries that category.

    Real rule: ``2.4.4.F-5.(3).robotic_rehab_ek2c_pricing``
    condition: {procedure_category: "robotic_rehab"}.
    """
    proc = _make_procedure(code="P000001", category="robotic_rehab")
    ctx = _make_ctx(procedure_lines=(proc,))
    violations = check_treatment_pricing_for_context(ctx)

    rule_ids = {v["rule_id"] for v in violations}
    assert "2.4.4.F-5.(3).robotic_rehab_ek2c_pricing" in rule_ids
    hit = next(v for v in violations if v["rule_id"].endswith("robotic_rehab_ek2c_pricing"))
    assert hit["rule"] == "treatment_pricing_2_4"
    assert hit["sut_section"] == "2.4.4.F-5"
    # This rule encodes an EK-2/C payment path (payment_tr), so billable=True.
    assert hit["billable"] is True
    assert hit["material_outcome"] == "must_bill"
    assert "robotik rehabilitasyon" in hit["message"]  # payment_tr surfaced


# ---------------------------------------------------------------------------
# 2. Negative case — mismatched category → no violation
# ---------------------------------------------------------------------------


def test_procedure_category_rule_negative() -> None:
    """Same rule, mismatched category → no violation for that rule."""
    proc = _make_procedure(code="P000002", category="physiotherapy_rehab")
    ctx = _make_ctx(procedure_lines=(proc,))
    violations = check_treatment_pricing_for_context(ctx)

    rule_ids = {v["rule_id"] for v in violations}
    assert "2.4.4.F-5.(3).robotic_rehab_ek2c_pricing" not in rule_ids


# ---------------------------------------------------------------------------
# 3. Empty procedure_lines → [] (no crash)
# ---------------------------------------------------------------------------


def test_empty_procedure_lines_returns_empty() -> None:
    """A claim with no procedure lines must not crash and yields no violations."""
    ctx = _make_ctx(procedure_lines=())
    assert check_treatment_pricing_for_context(ctx) == []


def test_empty_context_returns_empty() -> None:
    """No claims at all → empty context → no violations."""
    ctx = PatientClaimContext(
        patient_id="P1",
        claims=(),
        procedure_lines=(),
        material_lines=(),
        drug_lines=(),
        diagnoses=(),
    )
    assert check_treatment_pricing_for_context(ctx) == []


# ---------------------------------------------------------------------------
# 4. ICD-10 PREFIX match — diagnosis_in ["E11"] matches billed "E11.9"
# ---------------------------------------------------------------------------


def test_diagnosis_prefix_match_helper() -> None:
    """``_diagnosis_matches`` does prefix matching, not exact intersection."""
    # E11 matches E11.9 (prefix with dot)
    assert _diagnosis_matches(["E11.9"], ["E11"]) is True
    # exact match still works
    assert _diagnosis_matches(["N18"], ["N18"]) is True
    # N18 matches N18.9
    assert _diagnosis_matches(["N18.9"], ["N18"]) is True
    # different chapter does not match
    assert _diagnosis_matches(["E11.9"], ["N18"]) is False
    # E1 must NOT match E11 (prefix must be a full code segment)
    assert _diagnosis_matches(["E11.9"], ["E1"]) is False
    # empty rule codes → no diagnosis restriction → True
    assert _diagnosis_matches(["E11.9"], []) is True


def test_diagnosis_predicate_prefix_in_condition() -> None:
    """A rule with ``diagnosis_any: ["N18"]`` matches a billed ``"N18.9"`` claim.

    Exercises the full predicate engine path (not just the helper). The header's
    primary ICD (``Z00.0``) is also surfaced into ``diagnosis_codes`` — that is
    correct, so we assert membership, not equality.
    """
    context = _build_treatment_pricing_context(
        _make_ctx(header=_make_header(primary_icd10=""), diagnoses=(_make_diagnosis(code="N18.9"),))
    )
    assert context["diagnosis_codes"] == ["N18.9"]
    # Prefix match: N18 rule matches N18.9 billed code.
    assert _condition_matches({"diagnosis_any": ["N18", "N19"]}, context) is True
    assert _condition_matches({"diagnosis_in": ["E11"]}, context) is False


def test_diagnosis_any_rule_fires_via_prefix() -> None:
    """End-to-end: a real diagnosis-gated rule fires on a prefixed billed code.

    Real rule: ``2.4.4.D-1.(6).home_hemodialysis_ek2c_pricing``
    condition: {procedure_code_any: ["P5010050"], diagnosis_any: ["N18","N19"]}.
    Billed diagnosis ``N18.9`` must match the ``N18`` rule code via prefix.
    """
    proc = _make_procedure(code="P5010050", category="hemodialysis")
    ctx = _make_ctx(
        procedure_lines=(proc,),
        diagnoses=(_make_diagnosis(code="N18.9"),),
    )
    violations = check_treatment_pricing_for_context(ctx)
    rule_ids = {v["rule_id"] for v in violations}
    assert "2.4.4.D-1.(6).home_hemodialysis_ek2c_pricing" in rule_ids


# ---------------------------------------------------------------------------
# 5. Multi-procedure distinct categories → procedure_category_any path
# ---------------------------------------------------------------------------


def test_multi_procedure_category_any_path() -> None:
    """W2.5b: when categories differ, the *_any collection carries the full set
    and a ``procedure_category_any`` predicate matches on it; the bare scalar
    stays unset so exact-equality rules honest-skip rather than mis-attribute.
    """
    procs = (
        _make_procedure(code="P000010", category="peritoneal_dialysis"),
        _make_procedure(code="P000011", category="hemofiltration"),
    )
    ctx = _make_ctx(procedure_lines=procs)
    context = _build_treatment_pricing_context(ctx)

    # Full set surfaced for membership predicates.
    assert set(context.get("procedure_category_any") or []) == {
        "peritoneal_dialysis",
        "hemofiltration",
    }
    # Ambiguous → bare scalar absent.
    assert "procedure_category" not in context

    # The *_any predicate matches when the claim carries a listed category.
    assert (
        _condition_matches(
            {"procedure_category_any": ["peritoneal_dialysis", "hemofiltration", "plasmapheresis"]},
            context,
        )
        is True
    )
    # And rejects an unlisted category.
    assert _condition_matches({"procedure_category_any": ["radiosurgery"]}, context) is False


def test_multi_procedure_any_rule_fires() -> None:
    """End-to-end: a real ``procedure_category_any`` rule fires on a multi-cat claim.

    Real rule: ``2.4.4.D-2.(1).peritoneal_hemofiltration_plasmapheresis_fee_for_service``
    condition: {procedure_category_any: ["peritoneal_dialysis","hemofiltration","plasmapheresis"],
                diagnosis_any: ["N18","N19"]}.
    """
    procs = (
        _make_procedure(code="P000010", category="peritoneal_dialysis"),
        _make_procedure(code="P000011", category="hemofiltration"),
    )
    ctx = _make_ctx(
        procedure_lines=procs,
        diagnoses=(_make_diagnosis(code="N19.1"),),
    )
    violations = check_treatment_pricing_for_context(ctx)
    rule_ids = {v["rule_id"] for v in violations}
    assert (
        "2.4.4.D-2.(1).peritoneal_hemofiltration_plasmapheresis_fee_for_service" in rule_ids
    )


# ---------------------------------------------------------------------------
# Bonus: out-of-scope keys honest-skip; multi-claim scoping.
# ---------------------------------------------------------------------------


def test_out_of_scope_key_honest_skips() -> None:
    """A rule whose condition references a key NOT surfaced (e.g. session
    windows, IVF cycles) honest-skips — _condition_matches returns False, never
    fires, never raises.
    """
    context = {"procedure_category": "ivf"}
    # ``ivf_cycles_lifetime`` is never surfaced by the builder → skip.
    assert _condition_matches(
        {"procedure_category": "ivf", "ivf_cycles_lifetime": {"min": 3}}, context
    ) is False
    # Unknown scalar flag with no context value → skip.
    assert _condition_matches({"bmi": 30}, context) is False


def test_health_board_report_present_from_drug_lines() -> None:
    """health_board_report_present is derived from drug-line board-report flags.

    Real rule: ``2.4.4.C.(1).radiosurgery_board_report_required``
    condition: {procedure_category: "radiosurgery", health_board_report_present: false}.
    A radiosurgery claim WITH a board report present must NOT fire the
    no-report rule; one WITHOUT must.
    """
    proc = _make_procedure(code="P000020", category="radiosurgery")

    # With a board-report drug line → health_board_report_present=True → rule
    # (which gates on ==false) must NOT fire.
    ctx_with = _make_ctx(
        procedure_lines=(proc,),
        drug_lines=(_make_drug(board_report=True),),
    )
    ids_with = {v["rule_id"] for v in check_treatment_pricing_for_context(ctx_with)}
    assert "2.4.4.C.(1).radiosurgery_board_report_required" not in ids_with

    # Without a board-report drug line → health_board_report_present=False → fires.
    ctx_without = _make_ctx(
        procedure_lines=(proc,),
        drug_lines=(_make_drug(board_report=False),),
    )
    ids_without = {v["rule_id"] for v in check_treatment_pricing_for_context(ctx_without)}
    assert "2.4.4.C.(1).radiosurgery_board_report_required" in ids_without


def test_multi_claim_lines_scoped_to_first_claim() -> None:
    """Lines from a second claim must not leak into the first claim's context
    (parity with gap_closing W2.5d). The builder reads claims[0] and scopes
    line aggregation by claim_id.
    """
    first = _make_header(claim_id="C1")
    second = dataclasses.replace(first, claim_id="C2")
    foreign_proc = dataclasses.replace(
        _make_procedure(code="P000099", category="radiosurgery"), claim_id="C2"
    )
    ctx = PatientClaimContext(
        patient_id="P1",
        claims=(first, second),
        procedure_lines=(foreign_proc,),
        material_lines=(),
        drug_lines=(),
        diagnoses=(),
    )
    context = _build_treatment_pricing_context(ctx)
    # The first claim has no procedure lines of its own → no category surfaced.
    assert context.get("procedure_category_any") is None
    assert "radiosurgery" not in (context.get("procedure_category_any") or [])
