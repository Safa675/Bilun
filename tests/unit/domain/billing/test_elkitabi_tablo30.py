"""El Kitabı Tablo 30 — Radyasyon Onkolojisi (radiation oncology) validation.

This test simulates the radiation-oncology billing scenario from the Sağlık
Bakanlığı "Faturalandırma Usul ve Esasları El Kitabı" (2022), Tablo 30, and
runs it through the unified ``analyze_claim`` engine.

**Scenario (Tablo 30):**
Radiation oncology is billed as a bundle of mutually-exclusive,
course-capped EK-2/B line items in the 800xxx series — NOT a single EK-2/C
package. The El Kitabı defines two sub-rules:

1. **Mutual exclusion within families** — Radiation therapy codes come in
   families (e.g. external-RT design 800070–800110). Only ONE code from
   each family may be billed per treatment course.

2. **Same-day collapse** — For the application families (treatment
   fractions), only one code may be billed per day; multiple fractions on
   the same day must collapse to a single bill.

**Two billing scenarios are exercised:**

- **Scenario A (correct):** codes from DIFFERENT families on one claim
  (one external-RT design code + one conventional RT application code).
  The engine must produce NO radiation_oncology violations.

- **Scenario B (incorrect):** two codes from the SAME course-scoped family
  (external-RT design) on one claim. The engine must fire a
  ``radiation_oncology.course_cap`` violation.

Family membership is verified at import time against
``_family_for_code`` so the codes below are guaranteed to land in the
intended families.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from src.bilun.domain.billing.engine import analyze_claim
from src.bilun.domain.claims.models import ClaimHeader, ProcedureClaimLine
from src.bilun.domain.claims.patient_context import PatientClaimContext
from src.bilun.domain.prose_rules.radiation_oncology import _family_for_code

pytestmark = pytest.mark.unit

# ── Catalog codes (verified against radiation_oncology._FAMILIES) ───────────
#   800070  Eksternal RT tasarımı      → external_rt_design (course, cap=1)
#   800090  Eksternal RT tasarımı      → external_rt_design (course, cap=1)
#   800120  RT planlama/simülasyon     → rt_planning       (course, cap=1)
#   800330  Konvansiyonel RT uygulama  → rt_application    (same_day)
#   800340  Konvansiyonel RT uygulama  → rt_application    (same_day)

_CODE_DESIGN_A = "800070"   # external_rt_design
_CODE_DESIGN_B = "800090"   # external_rt_design  (SAME family as A)
_CODE_PLANNING = "800120"   # rt_planning         (DIFFERENT family)
_CODE_APP_A = "800330"      # rt_application      (DIFFERENT family)
_CODE_APP_B = "800340"      # rt_application      (same family, for same-day test)

# Sanity-check family placement at import time so a future catalog edit does
# not silently flip a code into another family and make the test misleading.
assert _family_for_code(_CODE_DESIGN_A)[0] == "external_rt_design"
assert _family_for_code(_CODE_DESIGN_B)[0] == "external_rt_design"
assert _family_for_code(_CODE_PLANNING)[0] == "rt_planning"
assert _family_for_code(_CODE_APP_A)[0] == "rt_application"
assert _family_for_code(_CODE_APP_B)[0] == "rt_application"


def _make_tablo30_claim(scenario_tag: str = "elkitabi_tablo30") -> ClaimHeader:
    """ClaimHeader for the Tablo 30 radiation-oncology outpatient claim.

    Radiation oncology is typically delivered ayakta (outpatient); the
    claim is a single-day outpatient episode.
    """
    service_date = date(2026, 7, 10)
    return ClaimHeader(
        claim_id="TABLO30-C1",
        patient_id="TABLO30-P1",
        episode_id="TABLO30-E1",
        claim_type="ayakta",
        facility_tier="devlet",
        provider_type="sozlesmeli",
        department="radyasyon_onkolojisi",
        admission_date=service_date,
        discharge_date=None,
        claim_start_date=service_date,
        claim_end_date=service_date,
        primary_icd10="C50.9",  # Malign neoplasm of breast, unspecified
        expected_total_billed_try=Decimal("0"),
        expected_total_payable_try=Decimal("0"),
        expected_denial_reason="",
        scenario_tag=scenario_tag,
    )


def _make_line(
    line_id: str,
    code: str,
    name: str,
    service_date: date,
    *,
    quantity: int = 1,
    billed: str = "500.00",
) -> ProcedureClaimLine:
    """Build a 800xxx EK-2/B procedure line on the Tablo 30 claim."""
    return ProcedureClaimLine(
        procedure_line_id=line_id,
        claim_id="TABLO30-C1",
        patient_id="TABLO30-P1",
        episode_id="TABLO30-E1",
        procedure_date=service_date,
        procedure_code=code,
        procedure_name=name,
        procedure_category="islem",  # EK-2/B line item (not a package)
        quantity=quantity,
        unit_price_try=Decimal(billed),
        billed_amount_try=Decimal(billed),
        expected_payable_try=Decimal(billed),
        is_package_included=False,
        package_code="",
        surcharge_applicable=False,
        copay_rate_applicable=False,
        denial_reason_expected="",
        rule_trace_expected="",
    )


def _radiation_violations(violations: list[dict]) -> list[dict]:
    """Filter engine output down to radiation_oncology violations only."""
    return [v for v in violations if v.get("type") == "radiation_oncology"]


# ── Scenario A — correct billing (different families, no violation) ─────────


def test_scenario_a_correct_billing_no_radiation_violation() -> None:
    """Codes from DIFFERENT families on one claim → no radiation violation.

    Per El Kitabı Tablo 30: one code per family per course is billable.
    Here we bill one external-RT design code (800070) AND one conventional
    RT application code (800330) — these belong to different families
    (external_rt_design vs rt_application), so the claim is correctly
    billed. The engine must NOT emit any radiation_oncology violation.
    """
    service_date = date(2026, 7, 10)
    claim = _make_tablo30_claim()
    procs = [
        _make_line("TABLO30-PL-A1", _CODE_DESIGN_A, "Eksternal RT tasarımı", service_date),
        _make_line("TABLO30-PL-A2", _CODE_APP_A, "Konvansiyonel RT uygulaması", service_date),
    ]
    ctx = PatientClaimContext(
        patient_id="TABLO30-P1",
        claims=(claim,),
        procedure_lines=tuple(procs),
        material_lines=(),
        drug_lines=(),
        diagnoses=(),
    )

    violations = analyze_claim(ctx)
    rad_violations = _radiation_violations(violations)

    assert rad_violations == [], (
        f"Expected NO radiation_oncology violations for codes from different "
        f"families, but got {len(rad_violations)}: "
        f"{[v.get('rule_id') for v in rad_violations]}"
    )


def test_scenario_a_planning_plus_application_different_families() -> None:
    """A second correct combination: RT planning + RT application.

    800120 (rt_planning) and 800330 (rt_application) are again different
    families, so even though both appear on the same service date the
    engine must not flag a radiation_oncology violation (planning is
    course-scoped and single; application is a different family and also
    single on the day).
    """
    service_date = date(2026, 7, 10)
    claim = _make_tablo30_claim()
    procs = [
        _make_line("TABLO30-PL-A3", _CODE_PLANNING, "RT planlama/simülasyon", service_date),
        _make_line("TABLO30-PL-A4", _CODE_APP_A, "Konvansiyonel RT uygulaması", service_date),
    ]
    ctx = PatientClaimContext(
        patient_id="TABLO30-P1",
        claims=(claim,),
        procedure_lines=tuple(procs),
        material_lines=(),
        drug_lines=(),
        diagnoses=(),
    )

    rad_violations = _radiation_violations(analyze_claim(ctx))

    assert rad_violations == [], (
        f"Expected NO radiation_oncology violations for planning+application "
        f"(different families), but got: "
        f"{[v.get('rule_id') for v in rad_violations]}"
    )


# ── Scenario B — incorrect billing (same family, violation expected) ────────


def test_scenario_b_same_family_course_cap_violation() -> None:
    """Two codes from the SAME course-scoped family → course_cap violation.

    Per El Kitabı Tablo 30: the external-RT design family (external_rt_design)
    is capped at one billing per treatment course. Billing both 800070 and
    800090 (both external_rt_design, cap=1) on the same claim is a violation.
    The engine must fire ``radiation_oncology.course_cap.external_rt_design``.
    """
    service_date = date(2026, 7, 10)
    claim = _make_tablo30_claim()
    procs = [
        _make_line("TABLO30-PL-B1", _CODE_DESIGN_A, "Eksternal RT tasarımı", service_date),
        _make_line("TABLO30-PL-B2", _CODE_DESIGN_B, "Eksternal RT tasarımı", service_date),
    ]
    ctx = PatientClaimContext(
        patient_id="TABLO30-P1",
        claims=(claim,),
        procedure_lines=tuple(procs),
        material_lines=(),
        drug_lines=(),
        diagnoses=(),
    )

    violations = analyze_claim(ctx)
    rad_violations = _radiation_violations(violations)

    assert rad_violations, (
        "Expected radiation_oncology course_cap violations for two codes from "
        "the same course-scoped family, but got none."
    )
    # Both offending lines participate → one violation per line.
    rule_kinds = {v["rule_kind"] for v in rad_violations}
    assert rule_kinds == {"course_cap"}, (
        f"Expected only course_cap violations, got rule_kinds={rule_kinds}"
    )
    assert all(v["family_key"] == "external_rt_design" for v in rad_violations)
    assert all(
        v["rule_id"] == "radiation_oncology.course_cap.external_rt_design"
        for v in rad_violations
    )
    assert {v["procedure_code"] for v in rad_violations} == {
        _CODE_DESIGN_A,
        _CODE_DESIGN_B,
    }
    # The violation detail must reference El Kitabı Tablo 30 / SUT §2.4.4.C.
    assert all("Tablo 30" in v["detail"] for v in rad_violations)


def test_scenario_b_same_family_same_day_application_violation() -> None:
    """Two application-family codes on the SAME day → same_day collapse.

    The rt_application family is same_day-scoped: only one code per family
    per service date. Billing both 800330 and 800340 on the same day is a
    same-day collapse violation. The engine must fire
    ``radiation_oncology.same_day_collapse.rt_application``.
    """
    service_date = date(2026, 7, 10)
    claim = _make_tablo30_claim()
    procs = [
        _make_line("TABLO30-PL-B3", _CODE_APP_A, "Konvansiyonel RT uygulaması", service_date),
        _make_line("TABLO30-PL-B4", _CODE_APP_B, "Konvansiyonel RT uygulaması", service_date),
    ]
    ctx = PatientClaimContext(
        patient_id="TABLO30-P1",
        claims=(claim,),
        procedure_lines=tuple(procs),
        material_lines=(),
        drug_lines=(),
        diagnoses=(),
    )

    rad_violations = _radiation_violations(analyze_claim(ctx))

    assert rad_violations, (
        "Expected radiation_oncology same_day_collapse violations for two "
        "application codes billed on the same day, but got none."
    )
    rule_kinds = {v["rule_kind"] for v in rad_violations}
    assert rule_kinds == {"same_day_collapse"}, (
        f"Expected only same_day_collapse violations, got rule_kinds={rule_kinds}"
    )
    assert all(v["family_key"] == "rt_application" for v in rad_violations)
    assert all(
        v["rule_id"] == "radiation_oncology.same_day_collapse.rt_application"
        for v in rad_violations
    )


# ── Diagnostics — what ELSE does the engine produce on a Tablo 30 claim? ────


def test_tablo30_engine_violation_inventory(capsys=None) -> None:
    """Surface the full set of violation types the engine emits for Scenario B.

    This is a documentation/observability test: it prints (and asserts the
    keys of) every distinct ``type`` the engine produces when run against the
    incorrect Scenario B claim, so changes to the engine's behavior on
    radiation-oncology claims are visible in CI output.
    """
    service_date = date(2026, 7, 10)
    claim = _make_tablo30_claim()
    procs = [
        _make_line("TABLO30-PL-B1", _CODE_DESIGN_A, "Eksternal RT tasarımı", service_date),
        _make_line("TABLO30-PL-B2", _CODE_DESIGN_B, "Eksternal RT tasarımı", service_date),
    ]
    ctx = PatientClaimContext(
        patient_id="TABLO30-P1",
        claims=(claim,),
        procedure_lines=tuple(procs),
        material_lines=(),
        drug_lines=(),
        diagnoses=(),
    )

    violations = analyze_claim(ctx)

    # Group by violation type for a readable inventory.
    by_type: dict[str, int] = {}
    for v in violations:
        by_type[v.get("type", "<unknown>")] = (
            by_type.get(v.get("type", "<unknown>"), 0) + 1
        )

    # The radiation_oncology motor MUST be in the inventory for Scenario B.
    assert by_type.get("radiation_oncology", 0) >= 1, (
        f"radiation_oncology missing from inventory: {by_type}"
    )
    # Stable, human-readable record of what the engine produced.
    print("\n[Tablo 30 Scenario B violation inventory]")
    for vtype in sorted(by_type):
        print(f"  {vtype}: {by_type[vtype]}")
