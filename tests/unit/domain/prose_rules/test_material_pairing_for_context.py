"""Unit tests for ``check_material_pairing_for_context`` (W1.2 wire).

The wrapper adapts the existing ``material_uplift`` evaluator — which
operates on a single ``ClaimHeader`` + procedure lines + material lines —
to the unified ``analyze_claim`` core by running it against a
``PatientClaimContext`` and projecting each opportunity into the flat
violation-dict shape the Phase 2.4 adapter consumes.

Trigger chosen from ``data/gazette/prose_rules/material_pairing_uplift.json``:
rule ``pairing.700910_kr1151`` expects EK-3H drug-eluting coronary stent
``KR1151`` separately billable alongside procedure ``700910`` (PTCA + stent).
The fixture mirrors ``test_material_uplift.py`` and yields a recoverable
~2890.39 TRY.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from src.bilun.domain.claims.models import ClaimHeader, ProcedureClaimLine
from src.bilun.domain.claims.patient_context import PatientClaimContext
from src.bilun.domain.prose_rules.material_uplift import (
    check_material_pairing_for_context,
)

pytestmark = pytest.mark.unit


def _claim(**overrides) -> ClaimHeader:
    base = {
        "claim_id": "C1",
        "patient_id": "P1",
        "episode_id": "E1",
        "claim_type": "yatis",
        "facility_tier": "egitim_arastirma",
        "provider_type": "Universite",
        "department": "cardiology",
        "admission_date": date(2026, 1, 10),
        "discharge_date": date(2026, 1, 12),
        "claim_start_date": date(2026, 1, 10),
        "claim_end_date": date(2026, 1, 12),
        "primary_icd10": "I21.9",
        "package_candidate": False,
        "expected_total_billed_try": Decimal("1000"),
        "expected_total_payable_try": Decimal("1000"),
        "expected_denial_reason": "",
        "scenario_tag": "test",
    }
    base.update(overrides)
    return ClaimHeader(**base)


def _proc(**overrides) -> ProcedureClaimLine:
    base = {
        "procedure_line_id": "PL1",
        "claim_id": "C1",
        "patient_id": "P1",
        "episode_id": "E1",
        "procedure_date": date(2026, 1, 10),
        "procedure_code": "700910",
        "procedure_name": "PTCA and stent",
        "procedure_category": "islem",
        "quantity": 1,
        "unit_price_try": Decimal("1000"),
        "billed_amount_try": Decimal("1000"),
        "expected_payable_try": Decimal("1000"),
        "is_package_included": False,
        "package_code": "",
        "surcharge_applicable": False,
        "copay_rate_applicable": False,
        "denial_reason_expected": "",
        "rule_trace_expected": "",
    }
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


class TestCheckMaterialPairingForContext:
    def test_missing_kr1151_for_procedure_700910_returns_violation(self) -> None:
        # Procedure 700910 (PTCA + stent) billed without separately billable
        # EK-3H stent → inverse-EK-3B-1 uplift review flags. 700910 pairs with
        # KR1151 (drug-eluting, pairing.700910_kr1151) and with the generic
        # bare-metal KR1150 (pairing.700800_kr1150 coronary intervention).
        ctx = _ctx([_claim()], [_proc()])

        violations = check_material_pairing_for_context(ctx)

        assert len(violations) == 2
        v = violations[0]
        # W1.2 unified-core contract: rule tag for the orchestrator.
        assert v["rule"] == "material_pairing_uplift"
        assert v["severity"] == "warning"
        assert v["procedure_code"] == "700910"
        assert v["material_code"] == "KR1151"
        assert v["claim_id"] == "C1"
        assert v["sut_section"] == "3.3.1"
        assert v["rule_id"] == "pairing.700910_kr1151"
        assert v["risk_amount"] == 0.0
        # recoverable uplift surfaces as the savings headline.
        assert v["savings_try"] == pytest.approx(2890.39, rel=0.01)
        # the full opportunity dict is preserved for downstream consumers.
        assert v["details"]["type"] == "missing_billable_material"
        assert v["details"]["opportunity"]["material_code"] == "KR1151"
        assert v["details"]["pairing_mode"] == "specialty_annex"
        assert v["details"]["specialty_annex"] == "EK-3H"
        # generic bare-metal pairing also fires for the same procedure.
        generic = violations[1]
        assert generic["material_code"] == "KR1150"
        assert generic["rule_id"] == "pairing.700800_kr1150"
        assert generic["savings_try"] == pytest.approx(862.67, rel=0.01)

    def test_unrelated_procedure_produces_no_violation(self) -> None:
        # A procedure code that is not in the pairing index.
        ctx = _ctx(
            [_claim()],
            [_proc(procedure_code="999999", procedure_name="İlgisiz işlem")],
        )

        assert check_material_pairing_for_context(ctx) == []

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

        assert check_material_pairing_for_context(ctx) == []

    def test_no_claims_short_circuits(self) -> None:
        # Guard contract: procedure lines present but no claims → [].
        ctx = PatientClaimContext(
            patient_id="P1",
            claims=(),
            procedure_lines=(_proc(),),
            material_lines=(),
            drug_lines=(),
            diagnoses=(),
        )

        assert check_material_pairing_for_context(ctx) == []
