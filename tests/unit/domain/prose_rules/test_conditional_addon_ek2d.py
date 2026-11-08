"""Unit tests for EK-2/D conditional add-on billing detector.

Covers the rule that ``P703365`` (intraoperatif nöromonitorizasyon) is
separately billable ONLY when the primary surgical procedure is on the
EK-2/D-4 list, and ``P614981`` (intraoperatif nöronavigasyon) ONLY when a
primary is on the EK-2/D-5 list.

Reference allow-list codes (verified from the in-repo sources):
  EK-2/D-4 (67 procs, parquet asof_2026-01-31):
      615660  Subpial insizyon
      615530  Köşe tümörleri cerrahisi   (also on D-5)
  EK-2/D-5 (29 procs, JSON seed):
      615350  3. ventrikül içi tümörleri
      615530  Köşe tümörleri cerrahisi   (also on D-4)
  Non-list codes used for violation cases:
      610130  Appendektomi               (not on D-4 or D-5)
      530390  Subkütan enjeksiyon        (not on D-4 or D-5)
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from src.bilun.domain.claims.models import ClaimHeader, ProcedureClaimLine
from src.bilun.domain.prose_rules.conditional_addon_ek2d import (
    detect_conditional_addon_ek2d_opportunities,
)

pytestmark = pytest.mark.unit

# Gated add-on procedure codes.
NEUROMONITORING = "P703365"  # intraoperatif nöromonitorizasyon (EK-2/D-4 gated)
NEURONAVIGATION = "P614981"  # intraoperatif nöronavigasyon (EK-2/D-5 gated)


def _make_claim_header(
    *,
    claim_id: str = "C1",
    claim_type: str = "yatis",
    admission: date | None = date(2026, 7, 10),
    discharge: date | None = date(2026, 7, 13),
) -> ClaimHeader:
    return ClaimHeader(
        claim_id=claim_id,
        patient_id="P1",
        episode_id="E1",
        claim_type=claim_type,
        facility_tier="devlet",
        provider_type="sozlesmeli",
        department="genel",
        admission_date=admission,
        discharge_date=discharge,
        claim_start_date=admission or date.today(),
        claim_end_date=discharge or date.today(),
        primary_icd10="C71.9",
        expected_total_billed_try=Decimal("1000"),
        expected_total_payable_try=Decimal("900"),
        expected_denial_reason="",
        scenario_tag="test",
    )


def _make_proc_line(
    *,
    procedure_line_id: str = "PL1",
    claim_id: str = "C1",
    procedure_code: str = "610130",
    procedure_category: str = "islem",
) -> ProcedureClaimLine:
    return ProcedureClaimLine(
        procedure_line_id=procedure_line_id,
        claim_id=claim_id,
        patient_id="P1",
        episode_id="E1",
        procedure_date=date(2026, 7, 10),
        procedure_code=procedure_code,
        procedure_name="test procedure",
        procedure_category=procedure_category,
        quantity=1,
        unit_price_try=Decimal("1000"),
        billed_amount_try=Decimal("1000"),
        expected_payable_try=Decimal("1000"),
        is_package_included=False,
        package_code="",
        surcharge_applicable=False,
        copay_rate_applicable=False,
        denial_reason_expected="",
        rule_trace_expected="",
    )


# ── P703365 (neuromonitoring) gated by EK-2/D-4 ─────────────────────────────


def test_neuromonitoring_with_d4_primary_no_violation() -> None:
    """P703365 + P615660 (on D-4) → no violation."""
    claim = _make_claim_header()
    primary = _make_proc_line(procedure_line_id="PL1", procedure_code="P615660")
    addon = _make_proc_line(
        procedure_line_id="PL2", procedure_code=NEUROMONITORING
    )
    opps = detect_conditional_addon_ek2d_opportunities([claim], [primary, addon])
    assert opps == []


def test_neuromonitoring_without_d4_primary_violation() -> None:
    """P703365 + non-D-4 procedure (P610130 Appendektomi) → violation."""
    claim = _make_claim_header()
    primary = _make_proc_line(procedure_line_id="PL1", procedure_code="P610130")
    addon = _make_proc_line(
        procedure_line_id="PL2", procedure_code=NEUROMONITORING
    )
    opps = detect_conditional_addon_ek2d_opportunities([claim], [primary, addon])

    assert len(opps) == 1
    opp = opps[0]
    assert opp["type"] == "conditional_addon_ek2d"
    assert opp["claim_id"] == "C1"
    assert opp["procedure_code"] == "703365"
    assert opp["rule_id"] == "conditional_addon_ek2d_neuromonitoring"
    assert opp["rule_set_id"] == "conditional_addon_ek2d"
    assert opp["sut_section_id"] == "EK-2/D"
    assert opp["required_list"] == "EK-2/D-4"
    assert opp["savings_category"] == "audit_exposure"
    assert opp["savings_basis"] == "sourced"
    assert opp["detail"]


# ── P614981 (neuronavigation) gated by EK-2/D-5 ─────────────────────────────


def test_neuronavigation_with_d5_primary_no_violation() -> None:
    """P614981 + P615350 (on D-5) → no violation."""
    claim = _make_claim_header()
    primary = _make_proc_line(procedure_line_id="PL1", procedure_code="P615350")
    addon = _make_proc_line(
        procedure_line_id="PL2", procedure_code=NEURONAVIGATION
    )
    opps = detect_conditional_addon_ek2d_opportunities([claim], [primary, addon])
    assert opps == []


def test_neuronavigation_without_d5_primary_violation() -> None:
    """P614981 + non-D-5 procedure (P530390) → violation."""
    claim = _make_claim_header()
    primary = _make_proc_line(procedure_line_id="PL1", procedure_code="P530390")
    addon = _make_proc_line(
        procedure_line_id="PL2", procedure_code=NEURONAVIGATION
    )
    opps = detect_conditional_addon_ek2d_opportunities([claim], [primary, addon])

    assert len(opps) == 1
    opp = opps[0]
    assert opp["type"] == "conditional_addon_ek2d"
    assert opp["claim_id"] == "C1"
    assert opp["procedure_code"] == "614981"
    assert opp["rule_id"] == "conditional_addon_ek2d_neuronavigation"
    assert opp["rule_set_id"] == "conditional_addon_ek2d"
    assert opp["sut_section_id"] == "EK-2/D"
    assert opp["required_list"] == "EK-2/D-5"
    assert opp["savings_category"] == "audit_exposure"
    assert opp["savings_basis"] == "sourced"
    assert opp["detail"]


# ── Edge cases ───────────────────────────────────────────────────────────────


def test_addon_alone_with_no_primary_violation() -> None:
    """P703365 billed alone (no other lines) → violation."""
    claim = _make_claim_header()
    addon = _make_proc_line(
        procedure_line_id="PL1", procedure_code=NEUROMONITORING
    )
    opps = detect_conditional_addon_ek2d_opportunities([claim], [addon])
    assert len(opps) == 1
    assert opps[0]["rule_id"] == "conditional_addon_ek2d_neuromonitoring"


def test_no_addon_lines_no_violation() -> None:
    """Only primary procedures, no add-ons → no violation."""
    claim = _make_claim_header()
    primary = _make_proc_line(procedure_line_id="PL1", procedure_code="P615660")
    opps = detect_conditional_addon_ek2d_opportunities([claim], [primary])
    assert opps == []


def test_both_addons_with_qualifying_primaries_no_violation() -> None:
    """Both add-ons billed with a qualifying primary each → no violation.

    P615530 (Köşe tümörleri cerrahisi) is on BOTH D-4 and D-5, so it qualifies
    as the primary for both add-ons.
    """
    claim = _make_claim_header()
    primary = _make_proc_line(procedure_line_id="PL1", procedure_code="P615530")
    monitoring = _make_proc_line(
        procedure_line_id="PL2", procedure_code=NEUROMONITORING
    )
    navigation = _make_proc_line(
        procedure_line_id="PL3", procedure_code=NEURONAVIGATION
    )
    opps = detect_conditional_addon_ek2d_opportunities(
        [claim], [primary, monitoring, navigation]
    )
    assert opps == []


def test_empty_inputs_no_violation() -> None:
    """No procedure lines → no violation."""
    claim = _make_claim_header()
    opps = detect_conditional_addon_ek2d_opportunities([claim], [])
    assert opps == []


def test_line_without_claim_header_skipped() -> None:
    """Add-on line whose claim_id has no matching header → skipped."""
    claim = _make_claim_header(claim_id="C1")
    addon = _make_proc_line(
        procedure_line_id="PL1", claim_id="C_OTHER", procedure_code=NEUROMONITORING
    )
    opps = detect_conditional_addon_ek2d_opportunities([claim], [addon])
    assert opps == []


def test_multiple_claims_isolated() -> None:
    """Violations are isolated per claim; two claims, only one qualifies."""
    claim_ok = _make_claim_header(claim_id="C1")
    claim_bad = _make_claim_header(claim_id="C2")

    # C1: neuromonitoring WITH a D-4 primary → OK
    ok_primary = _make_proc_line(
        procedure_line_id="PL1", claim_id="C1", procedure_code="P615660"
    )
    ok_addon = _make_proc_line(
        procedure_line_id="PL2", claim_id="C1", procedure_code=NEUROMONITORING
    )
    # C2: neuromonitoring WITHOUT a D-4 primary → violation
    bad_primary = _make_proc_line(
        procedure_line_id="PL3", claim_id="C2", procedure_code="P610130"
    )
    bad_addon = _make_proc_line(
        procedure_line_id="PL4", claim_id="C2", procedure_code=NEUROMONITORING
    )

    opps = detect_conditional_addon_ek2d_opportunities(
        [claim_ok, claim_bad],
        [ok_primary, ok_addon, bad_primary, bad_addon],
    )
    assert len(opps) == 1
    assert opps[0]["claim_id"] == "C2"
