"""W1.3 tests — gap_closing _for_context wrappers."""

from __future__ import annotations

import dataclasses
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
    check_gap_closing_misc_for_context,
    check_gap_closing_treatment_for_context,
)

pytestmark = pytest.mark.unit


def _make_header(
    *,
    claim_type: str = "ayakta",
    facility_tier: str = "ozel",
    provider_type: str = "sozlesmeli",
    department: str = "genel",
    scenario_tag: str = "test",
) -> ClaimHeader:
    from datetime import date
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
        expected_total_billed_try=Decimal("100"),
        expected_total_payable_try=Decimal("90"),
        expected_denial_reason="",
        scenario_tag=scenario_tag,
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
    category: str = "genel",
) -> ProcedureClaimLine:
    from datetime import date
    return ProcedureClaimLine(
        procedure_line_id="PL1",
        claim_id="C1",
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


def test_build_context_maps_header_fields() -> None:
    """_build_gap_closing_context surfaces facility_tier, provider_type, claim_type."""
    ctx = _make_ctx(header=_make_header(facility_tier="devlet", provider_type="sozlesmeli", claim_type="ayakta"))
    context = _build_gap_closing_context(ctx)
    assert context["facility_tier"] == "devlet"
    assert context["provider_type"] == "sozlesmeli"
    assert context["care_setting"] == "outpatient"


def test_build_context_derives_emergency_from_department() -> None:
    """is_emergency derived from 'acil' in department."""
    ctx = _make_ctx(header=_make_header(department="acil servis"))
    context = _build_gap_closing_context(ctx)
    assert context["is_emergency"] is True


def test_build_context_derives_emergency_from_claim_type_and_ignores_scenario_tag() -> None:
    """Safa675/Bilun#239: claim_type='acil' sets is_emergency=True even when department is non-ER, and scenario_tag never sets is_emergency."""
    ctx_er = _make_ctx(
        header=_make_header(
            claim_type="acil",
            department="Ic Hastaliklari",
            scenario_tag="",
        )
    )
    assert _build_gap_closing_context(ctx_er)["is_emergency"] is True

    ctx_tag_only = _make_ctx(
        header=_make_header(
            claim_type="ayakta",
            department="Ic Hastaliklari",
            scenario_tag="acil_sozlesmesiz_kurum",
        )
    )
    assert _build_gap_closing_context(ctx_tag_only)["is_emergency"] is False


@pytest.mark.parametrize("claim_type", ["yatis", "yatarak", "YATARAK", "inpatient"])
def test_inpatient_care_setting_aliases_are_normalized_consistently(claim_type: str) -> None:
    # SUT §2.1.2/§2.1.2.A and §2.2.2 use yatarak/yatan-hasta terminology;
    # claim_utils.infer_care_setting already recognizes this inpatient alias.
    ctx = _make_ctx(header=_make_header(claim_type=claim_type))
    assert _build_gap_closing_context(ctx)["care_setting"] == "inpatient"


def test_build_context_surfaces_procedure_fields() -> None:
    """procedure_category, procedure_code_any surfaced from procedure lines."""
    ctx = _make_ctx(procedure_lines=(_make_procedure(code="520030", category="kardiyoloji"),))
    context = _build_gap_closing_context(ctx)
    assert context["procedure_category"] == "kardiyoloji"
    assert "520030" in (context["procedure_code_any"] or [])


def test_gap_closing_misc_runs_without_crash() -> None:
    """check_gap_closing_misc_for_context returns a list (may be empty for this claim)."""
    ctx = _make_ctx()
    result = check_gap_closing_misc_for_context(ctx)
    assert isinstance(result, list)


def test_gap_closing_treatment_runs_without_crash() -> None:
    """check_gap_closing_treatment_for_context returns a list."""
    ctx = _make_ctx()
    result = check_gap_closing_treatment_for_context(ctx)
    assert isinstance(result, list)


def test_gap_closing_empty_context_returns_empty() -> None:
    """No claims → empty context → no violations."""
    from src.bilun.domain.claims.patient_context import PatientClaimContext
    ctx = PatientClaimContext(
        patient_id="P1",
        claims=(),
        procedure_lines=(),
        material_lines=(),
        drug_lines=(),
        diagnoses=(),
    )
    assert check_gap_closing_misc_for_context(ctx) == []
    assert check_gap_closing_treatment_for_context(ctx) == []


# ---------------------------------------------------------------------------
# Regression tests — Bugbot findings on PR #7 W1.3 (fixed in W2.5).
# These guard against the bugs silently returning. The pre-fix tests above
# all bypass _build_gap_closing_context by hand-feeding the literal dict, so
# the derivation bugs went undetected. These exercise the real builder.
# ---------------------------------------------------------------------------


def test_payment_method_path_diagnosis_from_a_billed_package_line() -> None:
    """W2.5a (HIGH): payment_method must derive the §2.2.2.B path
    (diagnosis_based / fee_for_service), NOT the procedure-level
    package/itemized decision. A claim that bills a package line must surface
    ``payment_method="diagnosis_based"`` so the 6 §2.2.2.B treatment rules
    that gate on that value can fire. Before the fix this emitted
    ``"package"`` and the rules silently never matched.

    #294: the fallback reads the billed P code (an outpatient EK-2/C package off
    EK-2/A-2 sets no claim kind).
    """
    ctx = _make_ctx(
        header=_make_header(),
        procedure_lines=(_make_procedure(code="P609270"),),
    )
    context = _build_gap_closing_context(ctx)
    assert context.get("payment_method") == "diagnosis_based"


def test_payment_method_path_unset_when_no_signal() -> None:
    """W2.5a (HIGH): when no payment-path signal exists (no procedure lines),
    the key must be ABSENT so _condition_matches honest-skips rather than
    emitting a wrong value.
    """
    ctx = _make_ctx(header=_make_header())
    context = _build_gap_closing_context(ctx)
    assert "payment_method" not in context


def test_multi_procedure_any_predicate_matches() -> None:
    """W2.5b (MEDIUM): when a claim has >1 distinct procedure category, the
    ``procedure_category_any`` collection must carry the full set AND a
    ``procedure_category_any`` rule condition must match. Before the fix the
    builder set the base field to None and _condition_matches read the base
    field, so multi-category claims silently honest-skipped.
    """
    procs = (
        _make_procedure(code="520030", category="kardiyoloji"),
        _make_procedure(code="510020", category="norolji"),
    )
    ctx = _make_ctx(procedure_lines=procs)
    context = _build_gap_closing_context(ctx)
    # Full set surfaced for membership predicates.
    assert set(context.get("procedure_category_any") or []) == {"kardiyoloji", "norolji"}
    # The _any predicate itself evaluates true when the claim carries a listed
    # category — direct exercise of the fixed _condition_matches path.
    from src.bilun.domain.prose_rules.gap_closing import _condition_matches
    assert _condition_matches({"procedure_category_any": ["kardiyoloji"]}, context) is True
    assert _condition_matches({"procedure_category_any": ["onkoloji"]}, context) is False


def test_multi_procedure_bare_scalar_unset_when_ambiguous() -> None:
    """W2.5b complement: the bare ``procedure_category`` scalar (read by the
    11 exact-equality rules) must be ABSENT when the claim has multiple
    distinct categories — we cannot truthfully pick one, so those rules
    honest-skip rather than mis-attribute.
    """
    procs = (
        _make_procedure(code="520030", category="kardiyoloji"),
        _make_procedure(code="510020", category="norolji"),
    )
    ctx = _make_ctx(procedure_lines=procs)
    context = _build_gap_closing_context(ctx)
    assert "procedure_category" not in context


def test_facility_uncontracted_recognizes_correct_spelling() -> None:
    """Copilot nit fix: the uncontracted sentinel is ``sozlesmesiz`` (single
    s), matching the synthetic generators. The double-s typo ``sozlessmesiz``
    would never match a real provider_type, silently dropping the flag.
    """
    ctx = _make_ctx(header=_make_header(provider_type="sozlesmesiz"))
    context = _build_gap_closing_context(ctx)
    assert context["facility_uncontracted"] is True
    assert context["facility_contracted"] is False


def test_multi_claim_context_lines_scoped_to_first_claim() -> None:
    """W2.5d (HIGH, Bugbot round 2): _build_gap_closing_context reads header
    fields from claims[0] but must NOT aggregate procedure/drug/material lines
    from a second claim in the same bundle. A foreign procedure line must not
    leak into the first claim's procedure_category_any. Before the fix every
    line was aggregated regardless of claim_id.
    """
    first_header = _make_header()  # claim_id C1
    second_header = _make_header()
    second_header = dataclasses.replace(second_header, claim_id="C2")
    # A procedure line that belongs to the SECOND claim only.
    foreign_proc = _make_procedure(code="999999", category="onkoloji")
    foreign_proc = dataclasses.replace(foreign_proc, claim_id="C2")
    ctx = PatientClaimContext(
        patient_id="P1",
        claims=(first_header, second_header),
        procedure_lines=(foreign_proc,),
        material_lines=(),
        drug_lines=(),
        diagnoses=(),
    )
    context = _build_gap_closing_context(ctx)
    # The first claim has no procedure lines of its own → its category set
    # must be empty, not contaminated by the second claim's "onkoloji" line.
    assert context.get("procedure_category_any") is None
    assert "onkoloji" not in (context.get("procedure_category_any") or [])


def test_care_setting_maps_poliklinik_and_gunubirlik_to_outpatient() -> None:
    """Bugbot round 2: poliklinik (outpatient clinic) and gunubirlik (day-case)
    previously fell through to the raw Turkish token, which
    _resolve_claim_kind would then mis-classify as inpatient. Both must map
    to "outpatient" so §2.2 payment-method classification is correct.
    """
    for claim_type in ("poliklinik", "gunubirlik"):
        ctx = _make_ctx(header=_make_header(claim_type=claim_type))
        context = _build_gap_closing_context(ctx)
        assert context["care_setting"] == "outpatient", f"{claim_type} should map to outpatient"
