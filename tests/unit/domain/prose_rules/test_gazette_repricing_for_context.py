"""Unit tests for ``check_gazette_repricing_for_context`` (W1.2 wire).

The wrapper adapts the existing ``gazette_repricing`` evaluator — which
operates on a single ``ClaimHeader`` + its ``ProcedureClaimLine`` list — to
the unified ``analyze_claim`` core by running it against a
``PatientClaimContext`` and projecting each opportunity into the flat
violation-dict shape the Phase 2.4 adapter consumes.

Trigger chosen from ``data/gazette/prose_rules/gazette_repricing_prose.json``:
rule ``repricing.600150`` flags procedure ``600150`` priced at the stale
pre-amendment EK-2/B list rate when service falls within 30 days before the
2026-01-01 tebliğ. The fixture (service date 2025-12-02, billed 449.73 TRY)
mirrors ``test_gazette_repricing.py`` and yields a recoverable 89.95 TRY.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from src.bilun.domain.claims.models import ClaimHeader, ProcedureClaimLine
from src.bilun.domain.claims.patient_context import PatientClaimContext
from src.bilun.domain.prose_rules.gazette_repricing import (
    check_gazette_repricing_for_context,
)
from tests.unit._helpers.catalog_stubs import (
    FIXTURE_GAZETTE_AMENDED_TRY,
    FIXTURE_GAZETTE_SERVICE_TRY,
    install_gazette_price_stub,
)

pytestmark = pytest.mark.unit

@pytest.fixture(autouse=True)
def _stub_gazette(monkeypatch):
    return install_gazette_price_stub(monkeypatch)


def _claim(**overrides) -> ClaimHeader:
    # Service date within 30 days of the 2026-01-01 tebliğ (2025-12-02 = 30 days).
    base = {
        "claim_id": "F-DEMO-001",
        "patient_id": "P1",
        "episode_id": "E1",
        "claim_type": "poliklinik",
        "facility_tier": "2_basamak_kamu",
        "provider_type": "Kamu",
        "department": "Genel",
        "admission_date": None,
        "discharge_date": None,
        "claim_start_date": date(2025, 12, 2),
        "claim_end_date": date(2025, 12, 2),
        "primary_icd10": "L98.9",
        "package_candidate": False,
        "expected_total_billed_try": Decimal(str(FIXTURE_GAZETTE_SERVICE_TRY)),
        "expected_total_payable_try": Decimal(str(FIXTURE_GAZETTE_SERVICE_TRY)),
        "expected_denial_reason": "",
        "scenario_tag": "sgk_gazette_repricing_600150",
    }
    base.update(overrides)
    return ClaimHeader(**base)


def _proc_line(**overrides) -> ProcedureClaimLine:
    base = {
        "procedure_line_id": "ISL-1",
        "claim_id": "F-DEMO-001",
        "patient_id": "P1",
        "episode_id": "E1",
        "procedure_date": date(2025, 12, 2),
        "procedure_code": "600150",
        "procedure_name": "Proc",
        "procedure_category": "islem",
        "quantity": 1,
        "unit_price_try": Decimal(str(FIXTURE_GAZETTE_SERVICE_TRY)),
        "billed_amount_try": Decimal(str(FIXTURE_GAZETTE_SERVICE_TRY)),
        "expected_payable_try": Decimal(str(FIXTURE_GAZETTE_SERVICE_TRY)),
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


class TestCheckGazetteRepricingForContext:
    def test_stale_price_after_teblig_returns_violation(self, _stub_gazette) -> None:
        # 600150 billed at the pre-amendment rate, service within 30 days of
        # the 2026-01-01 tebliğ → gazette repricing review flag.
        ctx = _ctx([_claim()], [_proc_line()])

        violations = check_gazette_repricing_for_context(ctx)

        assert len(violations) == 1
        v = violations[0]
        # W1.2 unified-core contract: rule tag for the orchestrator.
        assert v["rule"] == "gazette_repricing"
        assert v["severity"] == "warning"
        assert v["procedure_code"] == "600150"
        assert v["claim_id"] == "F-DEMO-001"
        assert v["sut_section"] == "2.2"
        assert v["rule_id"] == "gazette_repricing.600150"
        # review-only motor: never an automatic rebill.
        assert v["review_only"] is True
        assert v["risk_amount"] == 0.0
        # recoverable repricing surfaces as the savings headline.
        assert v["savings_try"] == pytest.approx(float(_stub_gazette["recoverable"]), rel=0.01)
        # the full opportunity dict is preserved for downstream consumers.
        assert v["details"]["type"] == "stale_gazette_price"
        assert v["details"]["opportunity"]["procedure_code"] == "600150"
        assert v["details"]["rebill_permitted"] is False

    def test_payable_already_at_new_price_suppresses_violation(self) -> None:
        # Line already billed at the post-amendment rate → no stale-price flag.
        ctx = _ctx(
            [_claim()],
            [
                _proc_line(
                    expected_payable_try=Decimal(str(FIXTURE_GAZETTE_AMENDED_TRY)),
                    billed_amount_try=Decimal(str(FIXTURE_GAZETTE_AMENDED_TRY)),
                    unit_price_try=Decimal(str(FIXTURE_GAZETTE_AMENDED_TRY)),
                )
            ],
        )

        assert check_gazette_repricing_for_context(ctx) == []

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

        assert check_gazette_repricing_for_context(ctx) == []

    def test_no_claims_short_circuits(self) -> None:
        # Guard contract: procedure lines present but no claims → [].
        ctx = PatientClaimContext(
            patient_id="P1",
            claims=(),
            procedure_lines=(_proc_line(),),
            material_lines=(),
            drug_lines=(),
            diagnoses=(),
        )

        assert check_gazette_repricing_for_context(ctx) == []

    def test_multi_claim_context_lines_scoped_per_claim(self) -> None:
        """Multi-claim context: each claim is processed independently and lines
        are scoped to their own claim_id. The second claim's stale-price line
        produces a violation attributed to the second claim (not the first).
        """
        first_claim = _claim()  # F-DEMO-001, in repricing window
        second_claim = _claim(
            claim_id="F-DEMO-002",
            scenario_tag="other",
        )
        # The stale-price line belongs to the SECOND claim.
        foreign_line = _proc_line(claim_id="F-DEMO-002", procedure_line_id="ISL-2")
        ctx = _ctx([first_claim, second_claim], [foreign_line])

        # First claim has no procedure lines → no violation for it.
        # Second claim has the stale-price line → violation attributed to F-DEMO-002.
        violations = check_gazette_repricing_for_context(ctx)
        assert len(violations) == 1
        assert violations[0]["claim_id"] == "F-DEMO-002"

