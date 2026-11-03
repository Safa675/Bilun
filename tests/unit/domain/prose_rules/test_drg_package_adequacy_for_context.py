"""Unit tests for the analyze_claim-wired DRG package adequacy wrapper.

``check_drg_package_adequacy_for_context`` is the violation-emitting adapter the
unified ``analyze_claim`` core consumes (Phase 3.2). It projects the
optimization-shaped opportunity dicts produced by
``detect_drg_package_adequacy_opportunities`` into the flat violation-dict
shape (``rule``, ``severity``, ``material_name``, ``message``, ``savings_try``,
``risk_amount``, ``material_outcome``, ``details``).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from src.bilun.domain.claims.models import ClaimHeader, ProcedureClaimLine
from src.bilun.domain.claims.patient_context import PatientClaimContext
from src.bilun.domain.prose_rules.drg_package_adequacy import (
    check_drg_package_adequacy_for_context,
)


def _claim(**overrides) -> ClaimHeader:
    base = {
        "claim_id": "F-DEMO-001",
        "patient_id": "P1",
        "episode_id": "E1",
        "claim_type": "yatis",
        "facility_tier": "egitim_arastirma",
        "provider_type": "Universite",
        "department": "Genel",
        "admission_date": date(2024, 6, 1),
        "discharge_date": date(2024, 6, 5),
        "claim_start_date": date(2024, 6, 1),
        "claim_end_date": date(2024, 6, 5),
        "primary_icd10": "K50.9",
        "package_candidate": True,
        "expected_total_billed_try": Decimal("10000.00"),
        "expected_total_payable_try": Decimal("9000.00"),
        "expected_denial_reason": "",
        "scenario_tag": "sgk_package_adequacy_undercoded",
    }
    base.update(overrides)
    return ClaimHeader(**base)


def _proc_line(**overrides) -> ProcedureClaimLine:
    base = {
        "procedure_line_id": "ISL-1",
        "claim_id": "F-DEMO-001",
        "patient_id": "P1",
        "episode_id": "E1",
        "procedure_date": date(2024, 6, 1),
        "procedure_code": "600150",
        "procedure_name": "Proc A",
        "procedure_category": "islem",
        "quantity": 1,
        "unit_price_try": Decimal("5000.00"),
        "billed_amount_try": Decimal("5000.00"),
        "expected_payable_try": Decimal("4500.00"),
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


class TestDrgPackageAdequacyForContext:
    def test_emits_violation_for_under_coded_package(self) -> None:
        """Two clinical procs (600150+600160) billed under 609270 flag 609300."""
        claim = _claim()
        procs = [
            _proc_line(),
            _proc_line(
                procedure_line_id="ISL-2",
                procedure_code="600160",
                procedure_name="Proc B",
            ),
            _proc_line(
                procedure_line_id="ISL-3",
                procedure_code="609270",
                procedure_name="Package",
                procedure_category="paket",
                billed_amount_try=Decimal("3500.00"),
                expected_payable_try=Decimal("3500.00"),
            ),
        ]
        ctx = _ctx([claim], procs)

        violations = check_drg_package_adequacy_for_context(ctx)

        assert len(violations) == 1
        v = violations[0]
        # Core engine-adapter keys.
        assert v["rule"] == "drg_package_adequacy"
        assert v["severity"] == "review"
        assert v["material_outcome"] == "documentation_review"
        assert v["risk_amount"] == 0.0
        # Savings carries the recoverable uplift from the candidate package.
        assert v["savings_try"] > 0.0
        # Material name surfaces the candidate (the under-coded review target).
        assert "609300" in v["material_name"]
        # Detail message preserved from the detector.
        assert v["message"]
        # Full opportunity preserved for traceability.
        assert v["details"]["current_package_code"] == "609270"
        assert v["details"]["candidate_package_code"] == "609300"
        assert set(v["details"]["clinical_procedure_codes"]) == {"600150", "600160"}

    def test_no_procedure_lines_returns_empty(self) -> None:
        """Procedure-driven check: empty procedure_lines is a no-op."""
        claim = _claim()
        ctx = _ctx([claim], [])
        assert check_drg_package_adequacy_for_context(ctx) == []

    def test_procedures_that_do_not_trigger_return_empty(self) -> None:
        """A billed package whose footprint is not fully met produces no hit."""
        claim = _claim()
        # Only 600150 present — 609270 footprint {600150} is met, but no larger
        # candidate (609300 needs {600150, 600160}) is satisfiable → no hit.
        procs = [
            _proc_line(),
            _proc_line(
                procedure_line_id="ISL-3",
                procedure_code="609270",
                procedure_name="Package",
                procedure_category="paket",
                billed_amount_try=Decimal("3500.00"),
                expected_payable_try=Decimal("3500.00"),
            ),
        ]
        ctx = _ctx([claim], procs)
        assert check_drg_package_adequacy_for_context(ctx) == []

    def test_the_package_is_read_from_the_codes_not_the_package_candidate_flag(self) -> None:
        """#294: a claim without the synthetic-only flag is evaluated; its package is the
        billed P code (MEDULA has no "paket" category), so 609300 is still flagged."""
        claim = _claim(package_candidate=False)
        procs = [
            _proc_line(),
            _proc_line(
                procedure_line_id="ISL-2",
                procedure_code="600160",
                procedure_name="Proc B",
            ),
            _proc_line(
                procedure_line_id="ISL-3",
                procedure_code="P609270",
                procedure_name="Package",
                billed_amount_try=Decimal("3500.00"),
                expected_payable_try=Decimal("3500.00"),
            ),
        ]
        ctx = _ctx([claim], procs)
        violations = check_drg_package_adequacy_for_context(ctx)
        assert [(v["details"]["current_package_code"], v["material_code"]) for v in violations] == [
            ("609270", "609300"),
        ]
