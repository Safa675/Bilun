"""Unit tests for ``check_procedure_pairing_for_context`` (Phase 3.3 wire).

The wrapper adapts the existing ``procedure_addon_uplift`` evaluator — which
operates on a single ``ClaimHeader`` + its session-grouped
``ProcedureClaimLine`` list — to the unified ``analyze_claim`` core by running
it against a ``PatientClaimContext`` and projecting each opportunity into the
flat violation-dict shape the Phase 2.4 adapter consumes.

Trigger chosen from ``data/gazette/prose_rules/procedure_pairing_prose.json``:
rule ``pairing.701450_701460`` expects add-on ``701460`` (kolonoskopik
polipektomi) on the same session as trigger ``701450`` (kolonoskopi).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from src.bilun.domain.claims.models import ClaimHeader, ProcedureClaimLine
from src.bilun.domain.claims.patient_context import PatientClaimContext
from src.bilun.domain.prose_rules.procedure_addon_uplift import (
    check_procedure_pairing_for_context,
)

pytestmark = pytest.mark.unit


def _claim(**overrides) -> ClaimHeader:
    base = dict(
        claim_id="CLM-PAIR",
        patient_id="P1",
        episode_id="E1",
        claim_type="gunubirlik",
        facility_tier="egitim_arastirma",
        provider_type="Universite",
        department="gastroenterology",
        admission_date=date(2026, 1, 10),
        discharge_date=date(2026, 1, 10),
        claim_start_date=date(2026, 1, 10),
        claim_end_date=date(2026, 1, 10),
        primary_icd10="K63.5",
        expected_total_billed_try=Decimal("900"),
        expected_total_payable_try=Decimal("900"),
        expected_denial_reason="",
        scenario_tag="sgk_procedure_addon_kolonoskopi",
    )
    base.update(overrides)
    return ClaimHeader(**base)


def _proc(**overrides) -> ProcedureClaimLine:
    base = dict(
        procedure_line_id="PL1",
        claim_id="CLM-PAIR",
        patient_id="P1",
        episode_id="E1",
        procedure_date=date(2026, 1, 10),
        procedure_code="701450",
        procedure_name="Kolonoskopi",
        procedure_category="islem",
        quantity=1,
        unit_price_try=Decimal("879.72"),
        billed_amount_try=Decimal("879.72"),
        expected_payable_try=Decimal("879.72"),
        is_package_included=False,
        package_code="",
        surcharge_applicable=False,
        copay_rate_applicable=True,
        denial_reason_expected="",
        rule_trace_expected="",
    )
    base.update(overrides)
    return ProcedureClaimLine(**base)


def _ctx(claims, procs) -> PatientClaimContext:
    return PatientClaimContext(
        patient_id="P1",
        claims=tuple(claims),
        procedure_lines=tuple(procs),
        material_lines=(),
        drug_lines=(),
        diagnoses=(),
    )


class TestCheckProcedurePairingForContext:
    def test_colonoscopy_missing_polypectomy_returns_violation(self) -> None:
        # Trigger 701450 billed, expected add-on 701460 NOT on the session.
        ctx = _ctx([_claim()], [_proc()])

        violations = check_procedure_pairing_for_context(ctx)

        assert len(violations) == 1
        v = violations[0]
        # Phase 3.3 unified-core contract: rule tag for the orchestrator.
        assert v["rule"] == "procedure_pairing"
        assert v["severity"] == "warning"
        assert v["trigger_procedure_code"] == "701450"
        assert v["expected_addon_procedure_code"] == "701460"
        assert v["claim_id"] == "CLM-PAIR"
        assert v["sut_section"] == "2.2.2.A.(5)"
        assert v["rule_id"] == "pairing.701450_701460"
        # recoverable uplift surfaces as the savings headline
        assert v["savings_try"] == pytest.approx(
            float(v["details"]["opportunity"]["recoverable_uplift_try"])
        )
        # the full opportunity dict is preserved for downstream consumers
        assert v["details"]["type"] == "missing_add_on_procedure"
        assert v["details"]["opportunity"]["expected_addon_procedure_code"] == "701460"

    def test_addon_present_suppresses_violation(self) -> None:
        # Add-on 701460 is billed on the same session → no pairing violation.
        ctx = _ctx(
            [_claim()],
            [
                _proc(),
                _proc(
                    procedure_line_id="PL2",
                    procedure_code="701460",
                    procedure_name="Polipektomi",
                    billed_amount_try=Decimal("200"),
                    expected_payable_try=Decimal("200"),
                    unit_price_try=Decimal("200"),
                ),
            ],
        )

        assert check_procedure_pairing_for_context(ctx) == []

    def test_empty_procedure_lines_short_circuits(self) -> None:
        # Guard contract: no procedure_lines → no work, no crash.
        ctx = PatientClaimContext(
            patient_id="P1",
            claims=(_claim(),),
            procedure_lines=(),
            material_lines=(),
            drug_lines=(),
            diagnoses=(),
        )

        assert check_procedure_pairing_for_context(ctx) == []

    def test_unrelated_procedure_produces_no_violation(self) -> None:
        # A procedure code that is neither a trigger nor an expected add-on.
        ctx = _ctx(
            [_claim()],
            [
                _proc(
                    procedure_line_id="PL9",
                    procedure_code="999999",
                    procedure_name="İlgisiz işlem",
                )
            ],
        )

        assert check_procedure_pairing_for_context(ctx) == []
