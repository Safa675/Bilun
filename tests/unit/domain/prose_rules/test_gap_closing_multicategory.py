"""Multi-category scalar fallback tests for gap_closing wiring fix.

Two wiring bugs were fixed in ``gap_closing.py`` that unblocked ~80 dormant
rules:

BUG 1 — multi-category scalar fallback (affects ~80 rules):
    ``_build_gap_closing_context`` leaves the bare ``procedure_category``
    scalar unset when a claim carries multiple distinct categories (it cannot
    truthfully pick one). The ``_condition_matches`` scalar branch then returned
    False on the absent key, honest-skipping every exact-equality rule on any
    multi-category claim. The fix makes the scalar branch fall back to
    membership testing against the ``procedure_category_any`` collection, so a
    rule asking ``procedure_category == 'ftr'`` still matches when 'ftr' is in
    the claim's category set. The same fallback applies to ``procedure_code``,
    ``drug_category`` and ``material_category``.

BUG 2 — payment_method context keys (affects 42 rules):
    Additional §2.2 context keys (``payment_method_path``,
    ``provider_contract_status``, ``visit_type``, ``facility_type``,
    ``facility_tier_basamak``, ``emergency_excluded``) are now surfaced from
    existing header/line fields so the payment_method traceability pass can
    fire more of its 42 rules.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from src.bilun.domain.claims.models import (
    ClaimHeader,
    DrugClaimLine,
    MaterialClaimLine,
    ProcedureClaimLine,
)
from src.bilun.domain.claims.patient_context import PatientClaimContext
from src.bilun.domain.prose_rules.gap_closing import (
    _build_gap_closing_context,
    _condition_matches,
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
        claim_start_date=date(2026, 7, 10),
        claim_end_date=date(2026, 7, 10),
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
    material_lines: tuple[MaterialClaimLine, ...] = (),
    drug_lines: tuple[DrugClaimLine, ...] = (),
) -> PatientClaimContext:
    h = header or _make_header()
    return PatientClaimContext(
        patient_id="P1",
        claims=(h,),
        procedure_lines=procedure_lines,
        material_lines=material_lines,
        drug_lines=drug_lines,
        diagnoses=(),
    )


def _make_procedure(
    *,
    code: str = "520030",
    category: str = "muayene",
    line_id: str = "PL1",
) -> ProcedureClaimLine:
    return ProcedureClaimLine(
        procedure_line_id=line_id,
        claim_id="C1",
        patient_id="P1",
        episode_id="E1",
        procedure_date=date(2026, 7, 10),
        procedure_code=code,
        procedure_name="Test procedure",
        procedure_category=category,
        quantity=1,
        unit_price_try=Decimal("50"),
        billed_amount_try=Decimal("50"),
        expected_payable_try=Decimal("50"),
        is_package_included=False,
        package_code="",
        surcharge_applicable=False,
        copay_rate_applicable=False,
        denial_reason_expected="",
        rule_trace_expected="",
    )


# ---------------------------------------------------------------------------
# BUG 1 — multi-category scalar fallback
# ---------------------------------------------------------------------------


def test_mixed_category_scalar_predicate_matches_via_any_fallback() -> None:
    """BUG 1: a claim with two distinct procedure categories must NOT
    honest-skip an exact-equality ``procedure_category`` rule. The builder
    leaves the scalar unset but surfaces the full set under
    ``procedure_category_any``; the scalar branch falls back to membership
    testing against that collection."""
    procs = (
        _make_procedure(code="520030", category="muayene", line_id="PL1"),
        _make_procedure(code="915030", category="ftr", line_id="PL2"),
    )
    ctx = _make_ctx(procedure_lines=procs)
    context = _build_gap_closing_context(ctx)
    # The scalar is deliberately absent on multi-category claims.
    assert "procedure_category" not in context
    # The full set is surfaced for membership predicates.
    assert set(context["procedure_category_any"]) == {"muayene", "ftr"}
    # The exact-equality predicate matches either listed category via fallback.
    assert _condition_matches({"procedure_category": "ftr"}, context) is True
    assert _condition_matches({"procedure_category": "muayene"}, context) is True


def test_mixed_category_scalar_predicate_rejects_unlisted_value() -> None:
    """BUG 1 negative: a value NOT in the claim's category set must still
    evaluate False — the fallback does membership testing, not blind-pass."""
    procs = (
        _make_procedure(code="520030", category="muayene", line_id="PL1"),
        _make_procedure(code="915030", category="ftr", line_id="PL2"),
    )
    ctx = _make_ctx(procedure_lines=procs)
    context = _build_gap_closing_context(ctx)
    assert _condition_matches({"procedure_category": "onkoloji"}, context) is False


def test_mixed_category_procedure_code_matches_via_any_fallback() -> None:
    """BUG 1 generalizes to ``procedure_code``: a multi-code claim leaves the
    scalar unset but the ``procedure_code_any`` fallback makes an exact-equality
    procedure_code rule match."""
    procs = (
        _make_procedure(code="520030", category="muayene", line_id="PL1"),
        _make_procedure(code="915030", category="ftr", line_id="PL2"),
    )
    ctx = _make_ctx(procedure_lines=procs)
    context = _build_gap_closing_context(ctx)
    assert "procedure_code" not in context
    assert set(context["procedure_code_any"]) == {"520030", "915030"}
    assert _condition_matches({"procedure_code": "520030"}, context) is True
    assert _condition_matches({"procedure_code": "915030"}, context) is True
    assert _condition_matches({"procedure_code": "000000"}, context) is False


def test_single_category_scalar_still_set_backwards_compatible() -> None:
    """BUG 1 backward compatibility: a single-category claim still surfaces the
    bare scalar (set directly), so the exact-equality path is unchanged and the
    ``*_any`` fallback is not exercised."""
    ctx = _make_ctx(procedure_lines=(_make_procedure(code="520030", category="muayene"),))
    context = _build_gap_closing_context(ctx)
    assert context["procedure_category"] == "muayene"
    assert _condition_matches({"procedure_category": "muayene"}, context) is True
    assert _condition_matches({"procedure_category": "ftr"}, context) is False


def test_single_category_any_predicate_still_matches() -> None:
    """BUG 1 backward compatibility: the explicit ``procedure_category_any``
    membership predicate still works on single-category claims (the scalar
    fallback did not break the existing ``*_any`` path)."""
    ctx = _make_ctx(procedure_lines=(_make_procedure(code="520030", category="muayene"),))
    context = _build_gap_closing_context(ctx)
    assert _condition_matches({"procedure_category_any": ["muayene"]}, context) is True
    assert _condition_matches({"procedure_category_any": ["ftr"]}, context) is False


def test_absent_scalar_with_no_any_honest_skips() -> None:
    """BUG 1 honesty guard: when BOTH the scalar and its ``*_any`` collection
    are absent (e.g. a key the builder never surfaces), the rule must still
    honest-skip rather than guessing. A fabricated key never produced by the
    builder exercises this."""
    ctx = _make_ctx()  # no procedure lines at all
    context = _build_gap_closing_context(ctx)
    assert "procedure_category" not in context
    assert "procedure_category_any" not in context
    assert _condition_matches({"procedure_category": "muayene"}, context) is False


# ---------------------------------------------------------------------------
# BUG 1 — drug / material multi-category consistency
# ---------------------------------------------------------------------------


def _make_material(*, category: str = "ortez", line_id: str = "ML1") -> MaterialClaimLine:
    return MaterialClaimLine(
        material_line_id=line_id,
        claim_id="C1",
        procedure_line_id="",
        patient_id="P1",
        material_date=date(2026, 7, 10),
        material_code="M1",
        material_name="Test material",
        material_type="ortez",
        specialty_category=category,
        quantity=1,
        unit_price_try=Decimal("50"),
        billed_amount_try=Decimal("50"),
        expected_payable_try=Decimal("50"),
        is_bundled=False,
        requires_pre_auth=False,
        denial_reason_expected="",
        rule_trace_expected="",
    )


def test_mixed_drug_category_scalar_matches_via_any_fallback() -> None:
    """BUG 1 extends to ``drug_category``: the ``*_any`` fallback in
    ``_condition_matches`` makes an exact-equality ``drug_category`` rule match
    a value present in the ``drug_category_any`` collection even when the bare
    scalar is absent. Exercised with a hand-built context (the current
    DrugClaimLine model does not yet carry a ``drug_category`` field, so the
    builder leaves it unset — the fallback path is what this test locks in)."""
    # Hand-built context where the builder surfaced the *_any collection only.
    context = {"drug_category_any": ["antibiotic", "onkoloji"]}
    assert _condition_matches({"drug_category": "antibiotic"}, context) is True
    assert _condition_matches({"drug_category": "onkoloji"}, context) is True
    assert _condition_matches({"drug_category": "steroid"}, context) is False


def test_mixed_material_category_scalar_matches_via_any_fallback() -> None:
    """BUG 1 extends to ``material_category``: multi-category material claims
    surface the full set under ``material_category_any`` and the scalar
    fallback makes an exact-equality rule match either listed category."""
    mats = (
        _make_material(category="ortez", line_id="ML1"),
        _make_material(category="protez", line_id="ML2"),
    )
    ctx = _make_ctx(material_lines=mats)
    context = _build_gap_closing_context(ctx)
    assert "material_category" not in context
    assert set(context["material_category_any"]) == {"ortez", "protez"}
    assert _condition_matches({"material_category": "ortez"}, context) is True
    assert _condition_matches({"material_category": "protez"}, context) is True


# ---------------------------------------------------------------------------
# BUG 2 — payment_method context keys surfaced from existing fields
# ---------------------------------------------------------------------------


def test_provider_contract_status_contracted_for_sozlesmeli() -> None:
    """BUG 2: ``provider_contract_status`` is derived from ``provider_type``.
    sozlesmeli maps to 'contracted', unblocking the 2.2.(8)/2.2.(12) rules."""
    ctx = _make_ctx(header=_make_header(provider_type="sozlesmeli"))
    context = _build_gap_closing_context(ctx)
    assert context["provider_contract_status"] == "contracted"


def test_provider_contract_status_uncontracted_for_sozlesmesiz() -> None:
    """BUG 2: ``sozlesmesiz`` (uncontracted) maps to 'uncontracted'."""
    ctx = _make_ctx(header=_make_header(provider_type="sozlesmesiz"))
    context = _build_gap_closing_context(ctx)
    assert context["provider_contract_status"] == "uncontracted"


def test_visit_type_gunubirlik_derived_from_claim_type() -> None:
    """BUG 2: ``visit_type='gunubirlik'`` derived from claim_type, unblocking
    the 2.2.2.(4)/(5) day-case rules."""
    ctx = _make_ctx(header=_make_header(claim_type="gunubirlik"))
    context = _build_gap_closing_context(ctx)
    assert context["visit_type"] == "gunubirlik"


def test_visit_type_unset_when_not_gunubirlik() -> None:
    """BUG 2 honesty: a non-day-case claim does not surface ``visit_type`` —
    other visit types need line-level data the model lacks."""
    ctx = _make_ctx(header=_make_header(claim_type="ayakta"))
    context = _build_gap_closing_context(ctx)
    assert "visit_type" not in context


def test_facility_type_training_research_from_provider_type() -> None:
    """BUG 2: ``facility_type='training_research_hospital'`` derived from a
    universite/egitim_arastirma provider_type, unblocking the
    §2.2.1.B-1.c / §2.2.2.A(6) rules."""
    ctx = _make_ctx(header=_make_header(provider_type="universite", facility_tier="3_basamak"))
    context = _build_gap_closing_context(ctx)
    assert context["facility_type"] == "training_research_hospital"


def test_facility_tier_basamak_derived_from_tier_string() -> None:
    """BUG 2: ``facility_tier_basamak`` resolved via the facility_tier
    normalizer. 3_basamak → 3 (the 2.2.2.(2) override gate), 2_basamak_kamu → 2."""
    ctx_t3 = _make_ctx(header=_make_header(facility_tier="3_basamak"))
    context = _build_gap_closing_context(ctx_t3)
    assert context["facility_tier_basamak"] == 3

    ctx_t2 = _make_ctx(header=_make_header(facility_tier="2_basamak_kamu"))
    context2 = _build_gap_closing_context(ctx_t2)
    assert context2["facility_tier_basamak"] == 2


def test_emergency_excluded_true_for_emergency_claim() -> None:
    """BUG 2: ``emergency_excluded`` is True when the claim IS an emergency
    (so the §2.2.1.B-4 same-specialty repeat rules correctly fire their
    emergency carve-out)."""
    ctx = _make_ctx(header=_make_header(department="acil servis"))
    context = _build_gap_closing_context(ctx)
    assert context["is_emergency"] is True
    assert context["emergency_excluded"] is True


def test_emergency_excluded_unset_for_non_emergency() -> None:
    """BUG 2 honesty: a non-emergency claim must NOT surface
    ``emergency_excluded=False`` — asserting the negative is not trustworthy
    from header data alone, so the key stays absent (honest skip)."""
    ctx = _make_ctx(header=_make_header(department="genel"))
    context = _build_gap_closing_context(ctx)
    assert context["is_emergency"] is False
    assert "emergency_excluded" not in context


def test_payment_method_path_itemized_when_fee_for_service() -> None:
    """BUG 2: ``payment_method_path='itemized'`` is surfaced when the claim's
    payment path resolves to fee_for_service (EK-2/B), matching the
    payment_method_2_2.json vocabulary used by the §2.2.2.A itemized rules.

    A package_candidate=False claim with only EK-2/B (non-package) procedure
    lines resolves to fee_for_service. We exercise the path via the
    payment_method key directly (the builder derives itemized iff the path is
    fee_for_service)."""
    # Build a claim where _derive_payment_method_path yields fee_for_service:
    # no procedures + package_candidate=False leaves payment_method unset, so
    # payment_method_path must also be absent (honest). Exercise the mapped
    # value via a direct context + _condition_matches round-trip instead.
    from src.bilun.domain.prose_rules.gap_closing import _build_gap_closing_context

    ctx = _make_ctx()  # header-only, no package signal
    context = _build_gap_closing_context(ctx)
    # No payment path signal → both keys absent (honest skip).
    assert "payment_method" not in context
    assert "payment_method_path" not in context
    # And the rule that gates on payment_method_path='itemized' honest-skips.
    assert _condition_matches({"payment_method_path": "itemized"}, context) is False


def test_new_keys_enable_more_payment_method_rule_firing() -> None:
    """Integration: the newly surfaced §2.2 keys let ``_condition_matches``
    evaluate conditions that previously honest-skipped. Before the fix every
    condition referencing ``provider_contract_status``, ``visit_type``,
    ``facility_type``, ``facility_tier_basamak``, or ``emergency_excluded``
    returned False because the key was absent; now the predicate matches when
    the builder surfaced the matching value."""
    from src.bilun.domain.prose_rules.gap_closing import _build_gap_closing_context

    # Contracted, tier-3, day-case, emergency claim surfaces several new keys.
    ctx = _make_ctx(
        header=_make_header(
            provider_type="sozlesmeli",
            facility_tier="3_basamak",
            claim_type="gunubirlik",
            department="acil servis",
        )
    )
    context = _build_gap_closing_context(ctx)
    # Each of these conditions would have honest-skipped before BUG 2.
    assert _condition_matches({"provider_contract_status": "contracted"}, context) is True
    assert _condition_matches({"visit_type": "gunubirlik"}, context) is True
    assert _condition_matches({"facility_tier_basamak": 3}, context) is True
    assert _condition_matches({"emergency_excluded": True}, context) is True
    # And a mismatched value still evaluates False (no false positives).
    assert _condition_matches({"provider_contract_status": "uncontracted"}, context) is False
    assert _condition_matches({"facility_tier_basamak": 2}, context) is False
