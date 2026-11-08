"""El Kitabı Tablo 35 — P615660 Subpial insizyon + P703365 Nöromonitorizasyon.

This test simulates the worked billing example from the Sağlık Bakanlığı
"Faturalandırma Usul ve Esasları El Kitabı" (2022), Tablo 35, and exercises
the EK-2/D conditional add-on detector (motor #13 in ``analyze_claim``).

**Scenario (Tablo 35):**
- Patient admitted for brain-tumor resection (primary_icd10 = C71.9).
- P615660 Subpial insizyon performed — this IS on the EK-2/D-4 list, i.e. it
  is a "qualifying primary" that permits the neuromonitoring add-on.
- P703365 İntraoperatif nöromonitorizasyon billed as an add-on.

**EK-2/D rule (SUT EK-2/D-4 & EK-2/D-5):**
Two intraoperative add-on procedures are *separately billable only when the
primary surgical procedure performed in the same claim is on the matching
EK-2/D allow-list*:

* ``P703365`` — *İntraoperatif nöromonitorizasyon* — gated by **EK-2/D-4**
  (67 procedures, sourced from
  ``data/gazette/snapshots/asof_2026-01-31/EK-2D-4.parquet``).
* ``P614981`` — *İntraoperatif nöronavigasyon* — gated by **EK-2/D-5**
  (29 procedures, sourced from
  ``data/gazette/prose_rules/ek2d5_neuronavigation_codes.json``).

When the add-on is billed but NO qualifying primary from the relevant list is
present on the same claim, the add-on is over-billed → a violation is emitted.

**What this test proves:**
1. **Positive case (correct billing):** P615660 (on D-4) + P703365 on the same
   claim → NO ``conditional_addon_ek2d`` violation. The add-on is legitimately
   billable alongside its qualifying primary.
2. **Negative case (violation):** P703365 billed alongside a non-D-4 procedure
   (520030 Muayene) → ``conditional_addon_ek2d_neuromonitoring`` violation IS
   emitted.
3. **Cross-list check:** P615660 is on D-4 but NOT on D-5 (verified by reading
   the D-5 seed file). So P615660 + P614981 (nöronavigasyon) → the
   ``conditional_addon_ek2d_neuronavigation`` violation IS emitted, because the
   primary does not qualify under the D-5 list.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from src.bilun.domain.billing.engine import analyze_claim
from src.bilun.domain.claims.models import ClaimHeader, ProcedureClaimLine
from src.bilun.domain.claims.patient_context import PatientClaimContext
from src.bilun.domain.prose_rules.catalog_membership import normalize_procedure_code
from src.bilun.domain.prose_rules.conditional_addon_ek2d import (
    load_ek2d4_code_set,
    load_ek2d5_code_set,
)

pytestmark = pytest.mark.unit

_PATIENT_ID = "TABLO35-P1"
_EPISODE_ID = "TABLO35-E1"

# ── Catalog constants (verified against EK-2/D-4 & EK-2/D-5 asof_2026-01-31) ─
#   615660 (Subpial insizyon): on EK-2/D-4 list (qualifies P703365 add-on)
#                             NOT on EK-2/D-5 list (does NOT qualify P614981)
#   703365 (Nöromonitorizasyon): the EK-2/D-4 gated add-on
#   614981 (Nöronavigasyon):     the EK-2/D-5 gated add-on
#   520030 (Muayene):            a non-surgical exam, NOT on D-4 or D-5


def _make_claim(claim_id: str) -> ClaimHeader:
    """ClaimHeader for the Tablo 35 brain-tumor patient.

    4-day inpatient stay: admission Jul 10, discharge Jul 13.
    """
    admission = date(2026, 7, 10)
    discharge = date(2026, 7, 13)
    return ClaimHeader(
        claim_id=claim_id,
        patient_id=_PATIENT_ID,
        episode_id=_EPISODE_ID,
        claim_type="yatis",
        facility_tier="devlet",
        provider_type="sozlesmeli",
        department="norosirurji",
        admission_date=admission,
        discharge_date=discharge,
        claim_start_date=admission,
        claim_end_date=discharge,
        primary_icd10="C71.9",  # Brain, unspecified — malignant neoplasm
        expected_total_billed_try=Decimal("12000"),
        expected_total_payable_try=Decimal("10000"),
        expected_denial_reason="",
        scenario_tag="elkitabi_tablo35",
    )


def _make_procedure(
    *,
    line_id: str,
    claim_id: str,
    code: str,
    name: str,
    service_date: date | None = None,
    category: str = "islem",
) -> ProcedureClaimLine:
    """Build a single ProcedureClaimLine matching the Tablo 23 construction."""
    proc_date = service_date or date(2026, 7, 11)  # surgery day
    return ProcedureClaimLine(
        procedure_line_id=line_id,
        claim_id=claim_id,
        patient_id=_PATIENT_ID,
        episode_id=_EPISODE_ID,
        procedure_date=proc_date,
        procedure_code=code,
        procedure_name=name,
        procedure_category=category,
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


def _conditional_addon_violations(violations: list[dict]) -> list[dict]:
    """Filter the analyze_claim output down to the conditional_addon motor."""
    return [v for v in violations if v.get("type") == "conditional_addon_ek2d"]


# ── Seed-data sanity: P615660 is on D-4 but NOT on D-5 ──────────────────────


def test_p615660_membership_in_d4_and_d5() -> None:
    """Catalog sanity check (verified against the seed files).

    P615660 (Subpial insizyon) MUST be on the EK-2/D-4 list so that it
    qualifies the P703365 neuromonitoring add-on — this is the premise of
    Tablo 35. It is NOT on the EK-2/D-5 list, so it does NOT qualify the
    P614981 neuronavigation add-on.
    """
    d4 = load_ek2d4_code_set()
    d5 = load_ek2d5_code_set()
    assert normalize_procedure_code("615660") in d4, (
        "P615660 must be on EK-2/D-4 — premise of Tablo 35."
    )
    assert normalize_procedure_code("615660") not in d5, (
        "P615660 is NOT on EK-2/D-5 — neuronavigation is not qualified by it."
    )


# ── Test 1: correct billing — P615660 + P703365 → NO conditional_addon ─────


def test_tablo35_correct_neuromonitoring_no_violation() -> None:
    """Positive case: P615660 (on D-4) + P703365 on the same claim.

    Per EK-2/D-4, the neuromonitoring add-on is legitimately billable
    alongside a qualifying primary. The conditional_addon motor must NOT
    fire. (Other motors may emit unrelated violations — see
    test_tablo35_other_motors_are_unrelated.)
    """
    claim = _make_claim("TABLO35-C1-CORRECT")
    procs = [
        _make_procedure(
            line_id="TABLO35-PL-CORRECT-PRIMARY",
            claim_id="TABLO35-C1-CORRECT",
            code="615660",
            name="Subpial insizyon",
        ),
        _make_procedure(
            line_id="TABLO35-PL-CORRECT-ADDON",
            claim_id="TABLO35-C1-CORRECT",
            code="703365",
            name="İntraoperatif nöromonitorizasyon",
        ),
    ]
    ctx = PatientClaimContext(
        patient_id=_PATIENT_ID,
        claims=(claim,),
        procedure_lines=tuple(procs),
        material_lines=(),
        drug_lines=(),
        diagnoses=(),
    )

    violations = analyze_claim(ctx)
    conditional = _conditional_addon_violations(violations)

    assert conditional == [], (
        "P615660 is on EK-2/D-4, so P703365 neuromonitoring is legitimately "
        "billable — no conditional_addon violation should be emitted."
    )


# ── Test 2: violation — P703365 + non-D-4 primary → violation emitted ──────


def test_tablo35_neuromonitoring_without_qualifying_primary_violation() -> None:
    """Negative case: P703365 billed with a non-D-4 procedure (520030 muayene).

    520030 (Muayene) is NOT on the EK-2/D-4 list, so neuromonitoring has no
    qualifying primary on this claim → the conditional_addon motor MUST fire
    exactly one violation of rule ``conditional_addon_ek2d_neuromonitoring``.
    """
    claim = _make_claim("TABLO35-C2-VIOLATION")
    procs = [
        _make_procedure(
            line_id="TABLO35-PL-VIO-ADDON",
            claim_id="TABLO35-C2-VIOLATION",
            code="703365",
            name="İntraoperatif nöromonitorizasyon",
        ),
        _make_procedure(
            line_id="TABLO35-PL-VIO-EXAM",
            claim_id="TABLO35-C2-VIOLATION",
            code="520030",
            name="Poliklinik muayenesi",
        ),
    ]
    ctx = PatientClaimContext(
        patient_id=_PATIENT_ID,
        claims=(claim,),
        procedure_lines=tuple(procs),
        material_lines=(),
        drug_lines=(),
        diagnoses=(),
    )

    violations = analyze_claim(ctx)
    conditional = _conditional_addon_violations(violations)

    assert len(conditional) == 1, (
        "Exactly one conditional_addon violation expected when P703365 has no "
        "qualifying D-4 primary on the claim."
    )
    v = conditional[0]
    assert v["rule_id"] == "conditional_addon_ek2d_neuromonitoring"
    assert v["addon_code"] == normalize_procedure_code("703365")
    assert v["required_list"] == "EK-2/D-4"
    assert v["claim_id"] == "TABLO35-C2-VIOLATION"
    assert "EK-2/D-4" in v["detail"]
    assert v["savings_category"] == "audit_exposure"


# ── Test 3: P615660 + P614981 nöronavigasyon — D-5 cross-list check ────────


def test_tablo35_neuronavigation_not_qualified_by_subpial() -> None:
    """Cross-list case: P615660 (on D-4, NOT on D-5) + P614981 nöronavigasyon.

    P615660 qualifies neuromonitoring (D-4) but does NOT qualify neuronavigation
    (D-5) — verified against ``ek2d5_neuronavigation_codes.json``. Therefore
    billing P614981 alongside P615660 has no qualifying D-5 primary and the
    ``conditional_addon_ek2d_neuronavigation`` violation MUST fire.

    This documents that the D-4 and D-5 lists are DISTINCT: a procedure
    qualifying one add-on does not automatically qualify the other.
    """
    claim = _make_claim("TABLO35-C3-NAV")
    procs = [
        _make_procedure(
            line_id="TABLO35-PL-NAV-PRIMARY",
            claim_id="TABLO35-C3-NAV",
            code="615660",
            name="Subpial insizyon",
        ),
        _make_procedure(
            line_id="TABLO35-PL-NAV-ADDON",
            claim_id="TABLO35-C3-NAV",
            code="614981",
            name="İntraoperatif nöronavigasyon",
        ),
    ]
    ctx = PatientClaimContext(
        patient_id=_PATIENT_ID,
        claims=(claim,),
        procedure_lines=tuple(procs),
        material_lines=(),
        drug_lines=(),
        diagnoses=(),
    )

    violations = analyze_claim(ctx)
    conditional = _conditional_addon_violations(violations)

    assert len(conditional) == 1, (
        "P615660 is NOT on EK-2/D-5, so P614981 neuronavigation has no "
        "qualifying primary → exactly one D-5 violation expected."
    )
    v = conditional[0]
    assert v["rule_id"] == "conditional_addon_ek2d_neuronavigation"
    assert v["addon_code"] == normalize_procedure_code("614981")
    assert v["required_list"] == "EK-2/D-5"
    assert v["claim_id"] == "TABLO35-C3-NAV"


# ── Other-motor inventory: confirm the non-conditional violations are ───────
# ── unrelated to the EK-2/D add-on rule.                                   ──


def test_tablo35_other_motors_are_unrelated() -> None:
    """Any non-conditional_addon violations come from OTHER motors.

    On the positive Tablo 35 claim (P615660 + P703365), the conditional_addon
    motor is silent. Other motors may still emit violations (e.g. a Tablo 15
    exam/admission-date mismatch from the 1-day gap between admission and the
    first procedure). This test asserts that NONE of those carry the
    ``conditional_addon_ek2d`` type or the EK-2/D rule_ids — they are
    independent motors, not misattributed add-on findings.
    """
    claim = _make_claim("TABLO35-C1-CORRECT")
    procs = [
        _make_procedure(
            line_id="TABLO35-PL-CORRECT-PRIMARY",
            claim_id="TABLO35-C1-CORRECT",
            code="615660",
            name="Subpial insizyon",
        ),
        _make_procedure(
            line_id="TABLO35-PL-CORRECT-ADDON",
            claim_id="TABLO35-C1-CORRECT",
            code="703365",
            name="İntraoperatif nöromonitorizasyon",
        ),
    ]
    ctx = PatientClaimContext(
        patient_id=_PATIENT_ID,
        claims=(claim,),
        procedure_lines=tuple(procs),
        material_lines=(),
        drug_lines=(),
        diagnoses=(),
    )

    violations = analyze_claim(ctx)
    ek2d_rule_ids = {
        "conditional_addon_ek2d_neuromonitoring",
        "conditional_addon_ek2d_neuronavigation",
    }

    for v in violations:
        # No violation from another motor may masquerade as an EK-2/D finding.
        assert v.get("type") != "conditional_addon_ek2d", (
            "conditional_addon_ek2d must be silent on the correct claim."
        )
        assert v.get("rule_id") not in ek2d_rule_ids, (
            f"Unexpected EK-2/D rule_id from another motor: {v.get('rule_id')}"
        )
