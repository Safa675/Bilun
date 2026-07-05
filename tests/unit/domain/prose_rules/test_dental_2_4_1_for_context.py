"""Phase 3.1 — ``check_dental_2_4_1_for_context`` context-wrapper tests.

Proves the ``_for_context`` shim threads a ``PatientClaimContext`` into the
canonical ``check_dental_2_4_1_prose`` material-dict evaluator: it resolves
``procedure_category`` from the material's linked ``ProcedureClaimLine`` (the
field lives on the procedure line, not ``MaterialClaimLine`` — see
``claims/models.py`` line 67) and copies through the rule-specific booleans so
the module's honesty guard skips non-surfaced rules.

Trigger rule (the wireable precious-metal case, ``dental_2_4_1.json`` line 14):
a ``dental_restoration`` material whose name contains a precious-metal keyword
(altın/platin/bego gold ewl/…) and carries
``material_contains_precious_metal=True`` must emit the
``2.4.1.(1).precious_metal_no_pay`` no-pay violation. The clean case — same
material without the flag — emits nothing (the honesty guard skips the rule).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from src.bilun.domain.claims.models import (
    ClaimHeader,
    MaterialClaimLine,
    ProcedureClaimLine,
)
from src.bilun.domain.claims.patient_context import PatientClaimContext
from src.bilun.domain.prose_rules.dental_2_4_1 import (
    check_dental_2_4_1_for_context,
)

pytestmark = pytest.mark.unit


def _make_material_line(
    *,
    name: str,
    code: str = "",
    material_line_id: str = "ML-DENTAL-1",
    procedure_line_id: str = "PL-DENTAL-1",
    material_contains_precious_metal: bool = False,
) -> MaterialClaimLine:
    """Build a minimal MaterialClaimLine carrying dental-surfaced flags.

    ``material_contains_precious_metal`` is not a first-class
    ``MaterialClaimLine`` field yet; it is set on the frozen dataclass instance
    via ``dataclasses.replace``-style construction so the shim's ``hasattr``
    copy-through picks it up (forward-compat with the model extension).
    """
    base = MaterialClaimLine(
        material_line_id=material_line_id,
        claim_id="C1",
        procedure_line_id=procedure_line_id,
        patient_id="P1",
        material_date=date(2026, 1, 1),
        material_code=code,
        material_name=name,
        material_type="consumable",
        specialty_category="general",
        quantity=1,
        unit_price_try=Decimal("500"),
        billed_amount_try=Decimal("500"),
        expected_payable_try=Decimal("500"),
        is_bundled=False,
        requires_pre_auth=False,
        denial_reason_expected="",
        rule_trace_expected="",
    )
    # Attach the surfaced dental flag directly to the instance. The frozen
    # dataclass is constructed above with all required fields; the dental
    # boolean is set as an object attribute so ``hasattr`` in the shim copies it
    # onto the material dict (mirrors how the build-time enricher would plumb
    # it once the model grows the field).
    object.__setattr__(
        base, "material_contains_precious_metal", material_contains_precious_metal
    )
    return base


def _make_procedure_line(
    *,
    procedure_category: str,
    procedure_line_id: str = "PL-DENTAL-1",
) -> ProcedureClaimLine:
    return ProcedureClaimLine(
        procedure_line_id=procedure_line_id,
        claim_id="C1",
        patient_id="P1",
        episode_id="E1",
        procedure_date=date(2026, 1, 1),
        procedure_code="DENTAL-PROC",
        procedure_name="Dental procedure",
        procedure_category=procedure_category,
        quantity=1,
        unit_price_try=Decimal("100"),
        billed_amount_try=Decimal("100"),
        expected_payable_try=Decimal("100"),
        is_package_included=False,
        package_code="",
        surcharge_applicable=False,
        copay_rate_applicable=False,
        denial_reason_expected="",
        rule_trace_expected="",
    )


def _make_ctx(
    *,
    materials: tuple[MaterialClaimLine, ...],
    procedures: tuple[ProcedureClaimLine, ...] = (),
) -> PatientClaimContext:
    header = ClaimHeader(
        claim_id="C1",
        patient_id="P1",
        episode_id="E1",
        claim_type="inpatient",
        facility_tier="state",
        provider_type="public",
        department="general",
        admission_date="2026-01-01",
        discharge_date="2026-01-02",
        claim_start_date="2026-01-01",
        claim_end_date="2026-01-02",
        primary_icd10="Z00.0",
        package_candidate=False,
        expected_total_billed_try=Decimal("600"),
        expected_total_payable_try=Decimal("500"),
        expected_denial_reason="",
        scenario_tag="dental_for_context",
    )
    return PatientClaimContext(
        patient_id="P1",
        claims=(header,),
        procedure_lines=procedures,
        material_lines=materials,
        drug_lines=(),
        diagnoses=(),
    )


def test_dental_precious_metal_violation_surfaced_from_context() -> None:
    """A dental_restoration precious-metal material must surface the no-pay rule.

    This is the wireable positive case from ``dental_2_4_1.json`` line 14:
    ``procedure_category == dental_restoration`` + name matches a precious-metal
    keyword (``bego gold ewl``) + ``material_contains_precious_metal == True``
    ⇒ the ``2.4.1.(1).precious_metal_no_pay`` rule fires with
    ``billable=False`` / ``material_outcome="no_pay"``.
    """
    material = _make_material_line(
        name="Bego gold EWL kron",
        material_contains_precious_metal=True,
    )
    procedure = _make_procedure_line(procedure_category="dental_restoration")
    ctx = _make_ctx(
        materials=(material,),
        procedures=(procedure,),
    )

    violations = check_dental_2_4_1_for_context(ctx)

    assert len(violations) == 1, "precious-metal dental material must be flagged"
    v = violations[0]
    assert v["rule"] == "dental_2_4_1"
    assert v["rule_id"] == "2.4.1.(1).precious_metal_no_pay"
    assert v["severity"] == "error"
    assert v["billable"] is False
    assert v["material_outcome"] == "no_pay"
    assert v["sut_section"] == "2.4.1"


def test_dental_turkish_normalization_in_name_match() -> None:
    """``altın`` (Turkish dotless i / diacritics) must normalize-match the
    precious-metal keyword list — the same assertion as
    ``test_turkish_normalization_in_keyword_match`` in
    ``test_wired_orphan_engines.py``, but threaded through the context wrapper.
    """
    material = _make_material_line(
        name="altın kaplama",
        material_contains_precious_metal=True,
    )
    procedure = _make_procedure_line(procedure_category="dental_restoration")
    ctx = _make_ctx(materials=(material,), procedures=(procedure,))

    violations = check_dental_2_4_1_for_context(ctx)

    assert len(violations) == 1
    assert "precious_metal" in violations[0]["rule_id"]


def test_clean_dental_material_emits_no_violation() -> None:
    """The same dental_restoration line WITHOUT ``material_contains_precious_metal``
    must emit nothing — the honesty guard in ``_condition_matches`` skips the
    rule when its boolean condition data is absent on the surfaced material dict.
    """
    material = _make_material_line(
        name="çelik kron",
        material_contains_precious_metal=False,
    )
    procedure = _make_procedure_line(procedure_category="dental_restoration")
    ctx = _make_ctx(materials=(material,), procedures=(procedure,))

    assert check_dental_2_4_1_for_context(ctx) == []


def test_non_dental_category_does_not_fire_dental_rule() -> None:
    """A precious-metal-named material on a NON-dental procedure category must
    not trip the dental rule (the rule conditions are gated on
    ``procedure_category == dental_restoration``).
    """
    material = _make_material_line(
        name="Bego gold EWL kron",
        material_contains_precious_metal=True,
    )
    procedure = _make_procedure_line(procedure_category="orthopedic_surgery")
    ctx = _make_ctx(materials=(material,), procedures=(procedure,))

    assert check_dental_2_4_1_for_context(ctx) == []


def test_empty_context_emits_nothing() -> None:
    """A context with no material lines short-circuits cleanly."""
    ctx = _make_ctx(materials=(), procedures=())

    assert check_dental_2_4_1_for_context(ctx) == []


def test_procedure_category_falls_back_to_material_specialty_category() -> None:
    """When no procedure line is linked, the material's own ``specialty_category``
    feeds ``procedure_category`` — a dental specialty material still surfaces the
    precious-metal rule without a linked procedure line.
    """
    material = _make_material_line(
        name="Bego gold EWL kron",
        material_contains_precious_metal=True,
    )
    # Override the specialty_category to a dental category so the fallback path
    # resolves ``procedure_category`` from the material itself.
    object.__setattr__(material, "specialty_category", "dental_restoration")
    ctx = _make_ctx(materials=(material,), procedures=())

    violations = check_dental_2_4_1_for_context(ctx)

    assert len(violations) == 1
    assert "precious_metal" in violations[0]["rule_id"]
