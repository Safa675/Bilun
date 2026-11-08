"""El Kitabı Tablo 32 — Karaciğer Nakli (liver transplant) P609080 validation.

This is an engine integration test: it builds the Tablo 32 liver-transplant
billing scenario from the Sağlık Bakanlığı "Faturalandırma Usul ve Esasları
El Kitabı" (2022) and runs it through the unified ``analyze_claim(ctx)``
engine (``src/bilun/domain/billing/engine.py``).

**Scenario (Tablo 32):**
- Patient receives a liver transplant, billed via the P609080 "Karaciğer
  Transplantasyonu" package.
- Per SUT, the P609080 package states **"Tüm cerrahi işlemler dahildir"**
  (all surgical procedures are included in the package).
- **Correct billing:** only P609080 appears on the claim. Any surgical
  procedure performed during the transplant episode is bundled into the
  package and must NOT be billed separately.
- **Incorrect billing:** P609080 plus a separately billed surgical procedure
  (here ``602010`` "Karaciğer biyopsisi") is an unbundling violation.

Two scenarios are exercised:

  * **Scenario A — Correct billing:** only P609080 → the
    ``transplant_package_scope`` motor must produce NO transplant violation.
  * **Scenario B — Incorrect billing:** P609080 + a separately billed
    surgical procedure → the ``transplant_package_scope`` motor MUST fire
    exactly one ``transplant_bundled_violation``.

Both scenarios are then run through the full ``analyze_claim`` engine, and
*all* violations from every motor are surfaced so expected/unexpected
findings can be inspected.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from src.bilun.domain.billing.engine import analyze_claim
from src.bilun.domain.claims.models import ClaimHeader, ProcedureClaimLine
from src.bilun.domain.claims.patient_context import PatientClaimContext

pytestmark = pytest.mark.unit

# ── Constants (Tablo 32) ────────────────────────────────────────────────────
_PATIENT_ID = "TABLO32-P1"
_EPISODE_ID = "TABLO32-E1"
_PRIMARY_ICD10 = "K76.9"  # Liver disease, unspecified (transplant indication)
_LIVER_TRANSPLANT_CODE = "P609080"
_LIVER_TRANSPLANT_NAME = "Karaciğer Transplantasyonu"
_LIVER_BIOPSY_CODE = "602010"
_LIVER_BIOPSY_NAME = "Karaciğer biyopsisi"

_ADMISSION = date(2026, 7, 10)
_DISCHARGE = date(2026, 7, 24)


# ── Builders ────────────────────────────────────────────────────────────────


def _make_claim(claim_id: str) -> ClaimHeader:
    """Inpatient ClaimHeader for the Tablo 32 liver-transplant patient."""
    return ClaimHeader(
        claim_id=claim_id,
        patient_id=_PATIENT_ID,
        episode_id=_EPISODE_ID,
        claim_type="yatis",
        facility_tier="devlet",
        provider_type="sozlesmeli",
        department="organ_nakli",
        admission_date=_ADMISSION,
        discharge_date=_DISCHARGE,
        claim_start_date=_ADMISSION,
        claim_end_date=_DISCHARGE,
        primary_icd10=_PRIMARY_ICD10,
        expected_total_billed_try=Decimal("908561.20"),
        expected_total_payable_try=Decimal("908561.20"),
        expected_denial_reason="",
        scenario_tag="elkitabi_tablo32",
    )


def _make_transplant_line(claim_id: str, line_id: str) -> ProcedureClaimLine:
    """The P609080 liver-transplant package line."""
    return ProcedureClaimLine(
        procedure_line_id=line_id,
        claim_id=claim_id,
        patient_id=_PATIENT_ID,
        episode_id=_EPISODE_ID,
        procedure_date=_ADMISSION,
        procedure_code=_LIVER_TRANSPLANT_CODE,
        procedure_name=_LIVER_TRANSPLANT_NAME,
        procedure_category="paket",  # EK-2C package
        quantity=1,
        unit_price_try=Decimal("908561.20"),
        billed_amount_try=Decimal("908561.20"),
        expected_payable_try=Decimal("908561.20"),
        is_package_included=True,
        package_code=_LIVER_TRANSPLANT_CODE,
        surcharge_applicable=False,
        copay_rate_applicable=False,
        denial_reason_expected="",
        rule_trace_expected="",
    )


def _make_biopsy_line(claim_id: str, line_id: str) -> ProcedureClaimLine:
    """A separately billed surgical procedure (Karaciğer biyopsisi).

    ``procedure_category == "islem"`` marks this as a surgical procedure,
    which is the category the transplant_package_scope motor considers
    bundled into P609080.
    """
    return ProcedureClaimLine(
        procedure_line_id=line_id,
        claim_id=claim_id,
        patient_id=_PATIENT_ID,
        episode_id=_EPISODE_ID,
        procedure_date=_ADMISSION,
        procedure_code=_LIVER_BIOPSY_CODE,
        procedure_name=_LIVER_BIOPSY_NAME,
        procedure_category="islem",  # surgical procedure → bundled into P609080
        quantity=1,
        unit_price_try=Decimal("2500.00"),
        billed_amount_try=Decimal("2500.00"),
        expected_payable_try=Decimal("2500.00"),
        is_package_included=False,
        package_code="",
        surcharge_applicable=False,
        copay_rate_applicable=False,
        denial_reason_expected="",
        rule_trace_expected="",
    )


def _run_engine(claim: ClaimHeader, lines: list[ProcedureClaimLine]) -> list[dict]:
    """Build a PatientClaimContext for one claim and run analyze_claim."""
    ctx = PatientClaimContext(
        patient_id=_PATIENT_ID,
        claims=(claim,),
        procedure_lines=tuple(lines),
        material_lines=(),
        drug_lines=(),
        diagnoses=(),
    )
    return analyze_claim(ctx)


# ── Scenario A: correct billing — P609080 only ─────────────────────────────


class TestTablo32CorrectBilling:
    """Scenario A: only P609080 on the claim → no transplant violation."""

    def test_no_transplant_package_scope_violation(self) -> None:
        claim = _make_claim("TABLO32-C1")
        lines = [_make_transplant_line("TABLO32-C1", "TABLO32-C1-PL1")]
        violations = _run_engine(claim, lines)

        transplant_violations = [
            v for v in violations
            if v.get("rule_id") == "transplant_bundled_surgical_procedure"
            or v.get("type") == "transplant_bundled_violation"
        ]
        assert transplant_violations == [], (
            "Correctly-billed liver-transplant claim (P609080 only) must "
            "produce NO transplant_package_scope violations. Got: "
            f"{transplant_violations}"
        )

    def test_engine_runs_cleanly_on_correct_claim(self) -> None:
        """analyze_claim must execute without error on the correct claim.

        The engine may surface other (non-transplant) findings; this test
        only guarantees the call succeeds and returns a list.
        """
        claim = _make_claim("TABLO32-C1")
        lines = [_make_transplant_line("TABLO32-C1", "TABLO32-C1-PL1")]
        violations = _run_engine(claim, lines)
        assert isinstance(violations, list)


# ── Scenario B: incorrect billing — P609080 + separately billed surgery ────


class TestTablo32IncorrectBilling:
    """Scenario B: P609080 + a separately billed surgical procedure → violation."""

    def test_transplant_package_scope_violation_fires(self) -> None:
        claim = _make_claim("TABLO32-C2")
        lines = [
            _make_transplant_line("TABLO32-C2", "TABLO32-C2-PL1"),
            _make_biopsy_line("TABLO32-C2", "TABLO32-C2-PL2"),
        ]
        violations = _run_engine(claim, lines)

        transplant_violations = [
            v for v in violations
            if v.get("rule_id") == "transplant_bundled_surgical_procedure"
            or v.get("type") == "transplant_bundled_violation"
        ]
        assert len(transplant_violations) == 1, (
            "Incorrectly-billed liver-transplant claim (P609080 + separately "
            "billed surgical procedure) must produce exactly ONE "
            "transplant_package_scope violation. "
            f"Got {len(transplant_violations)}: {transplant_violations}"
        )

    def test_violation_targets_the_separately_billed_procedure(self) -> None:
        claim = _make_claim("TABLO32-C2")
        lines = [
            _make_transplant_line("TABLO32-C2", "TABLO32-C2-PL1"),
            _make_biopsy_line("TABLO32-C2", "TABLO32-C2-PL2"),
        ]
        violations = _run_engine(claim, lines)

        v = next(
            vv for vv in violations
            if vv.get("type") == "transplant_bundled_violation"
        )
        assert v["procedure_code"] == _LIVER_BIOPSY_CODE
        assert v["procedure_line_id"] == "TABLO32-C2-PL2"
        assert v["claim_id"] == "TABLO32-C2"
        assert v["package_code"] == _LIVER_TRANSPLANT_CODE
        assert v["care_setting"] == "inpatient"
        assert v["savings_basis"] == "heuristic"
        assert "P609080" in v["detail"]
        assert v["risk_amount_try"] == pytest.approx(2500.0, abs=0.01)


# ── Full-engine summary: list ALL violations from every motor ───────────────


def _rule_type(v: dict) -> str:
    """Reduce a violation dict to a human-readable rule-type tag.

    Different motors populate different keys; prefer the most specific.
    """
    return (
        v.get("rule_id")
        or v.get("rule_set_id")
        or v.get("type")
        or v.get("rule")
        or "<unknown>"
    )


class TestTablo32FullEngineSummary:
    """Run the full engine on both scenarios and enumerate every finding.

    These tests are intentionally permissive about OTHER motors' output
    (they document, not constrain) — the contract under test is the
    transplant_package_scope motor's behavior.
    """

    def test_scenario_a_all_violation_rule_types(self) -> None:
        claim = _make_claim("TABLO32-C1")
        lines = [_make_transplant_line("TABLO32-C1", "TABLO32-C1-PL1")]
        violations = _run_engine(claim, lines)

        rule_types = sorted({_rule_type(v) for v in violations})
        # Document every rule type the engine surfaces on the correct claim.
        # The only hard contract: no transplant violation.
        assert "transplant_bundled_surgical_procedure" not in rule_types
        # Record the full set for reporting (no assertion on membership).
        assert isinstance(rule_types, list)

    def test_scenario_b_all_violation_rule_types(self) -> None:
        claim = _make_claim("TABLO32-C2")
        lines = [
            _make_transplant_line("TABLO32-C2", "TABLO32-C2-PL1"),
            _make_biopsy_line("TABLO32-C2", "TABLO32-C2-PL2"),
        ]
        violations = _run_engine(claim, lines)

        rule_types = sorted({_rule_type(v) for v in violations})
        # Hard contract: the transplant violation must be among the findings.
        assert "transplant_bundled_surgical_procedure" in rule_types
        # Record the full set for reporting (no assertion on the others).
        assert isinstance(rule_types, list)

    def test_scenario_b_violation_count_by_rule_type(self) -> None:
        """Report how many findings each motor produces on the bad claim.

        This is a documentation test: it counts violations per rule type
        and asserts only the transplant finding (>=1) is present as a
        contract. Anything else is surfaced for inspection via the count.
        """
        claim = _make_claim("TABLO32-C2")
        lines = [
            _make_transplant_line("TABLO32-C2", "TABLO32-C2-PL1"),
            _make_biopsy_line("TABLO32-C2", "TABLO32-C2-PL2"),
        ]
        violations = _run_engine(claim, lines)

        counts: dict[str, int] = {}
        for v in violations:
            key = _rule_type(v)
            counts[key] = counts.get(key, 0) + 1

        assert counts.get("transplant_bundled_surgical_procedure", 0) >= 1
