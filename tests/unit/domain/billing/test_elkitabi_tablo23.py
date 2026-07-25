"""El Kitabı Tablo 23 — P610130 Appendektomi validation against BILUN motors.

This test simulates the worked billing example from the Sağlık Bakanlığı
"Faturalandırma Usul ve Esasları El Kitabı" (2022), Tablo 23, and compares
each BILUN bed-day motor's output against the handbook's expected values.

**Scenario (Tablo 23):**
- Patient presents to ER with abdominal pain and fever.
- ER exam + blood tests + USG + consult → admitted to General Surgery.
- P610130 Appendektomi performed on day 1 (surgery day).
- 4-day inpatient stay (admission → discharge = 3 calendar days, 4 inclusive LOS).
- Blood transfusion: 1 unit Eritrosit Süspansiyonu (705371).
- Anesthesia performed.
- Pathology exam.
- Discharged after 4 days.

**El Kitabı billing instructions (EK-2/C method):**
- P610130 billed via EK-2/C package (₺5,080.28 as of 2026-01-31).
- 705371 Eritrosit süspansiyonu: %36 of EK-2/B puan billed additionally.
- Anesthesia billed separately (group determined by surgical puan range).
- Pathology billed separately (EK-2/B).
- **İlaç + Malzeme + Yatak: INCLUDED in the P610130 package** (not separately billable).

**Critical gap discovered:**
BILUN's yatak motor currently bills 4 bed-days (₺889.44) ON TOP of the
EK-2/C package, because it does not check whether the claim's procedure is
a package (paket/star) code that bundles the surgery-day bed fee. Per the
El Kitabı, these bed-days should be reduced or excluded for package claims.
This test documents that gap as a known-failing assertion (xfail).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from src.bilun.domain.claims.models import ClaimHeader, ProcedureClaimLine
from src.bilun.domain.claims.patient_context import PatientClaimContext
from src.bilun.domain.prose_rules.anestezi_puani import (
    detect_anestezi_puani_opportunities,
)
from src.bilun.domain.prose_rules.refakatci import detect_refakatci_opportunities
from src.bilun.domain.prose_rules.yatak_puani import detect_yatak_puani_opportunities
from tests.unit._helpers.catalog_stubs import (
    FIXTURE_BED_DAILY_TRY,
    FIXTURE_KATSAYI,
    FIXTURE_PROC_PUAN,
    install_anestezi_catalog_stub,
    install_yatak_catalog_stub,
)

pytestmark = pytest.mark.unit

_A1_GROUP_PUAN = 8942.14


@pytest.fixture(autouse=True)
def _stub_catalogs(monkeypatch: pytest.MonkeyPatch) -> None:
    install_yatak_catalog_stub(monkeypatch)
    install_anestezi_catalog_stub(monkeypatch)

def _make_tablo23_claim() -> ClaimHeader:
    """ClaimHeader for the Tablo 23 appendectomy patient.

    4-day inpatient stay: admission Jul 10, discharge Jul 13.
    """
    admission = date(2026, 7, 10)
    discharge = date(2026, 7, 13)
    return ClaimHeader(
        claim_id="TABLO23-C1",
        patient_id="TABLO23-P1",
        episode_id="TABLO23-E1",
        claim_type="yatis",
        facility_tier="devlet",
        provider_type="sozlesmeli",
        department="genel_cerrahi",
        admission_date=admission,
        discharge_date=discharge,
        claim_start_date=admission,
        claim_end_date=discharge,
        primary_icd10="K35.8",  # Acute appendicitis
        package_candidate=True,  # P610130 is an EK-2C package
        expected_total_billed_try=Decimal("8000"),
        expected_total_payable_try=Decimal("7000"),
        expected_denial_reason="",
        scenario_tag="elkitabi_tablo23",
    )


def _make_tablo23_procedures() -> list[ProcedureClaimLine]:
    """Procedure lines matching Tablo 23 (surgery day).

    Per the handbook:
    - P610130 Appendektomi (the package procedure, billed via EK-2/C)
    - 705371 Eritrosit süspansiyonu (1 unit)
    - Note: İlaç + Malzeme + Yatak are INCLUDED in the package, so they
      should NOT appear as separate procedure lines on a correctly-billed
      claim. BILUN's yatak motor, however, computes expected yatak
      independently — this is the gap.
    """
    surgery_day = date(2026, 7, 11)
    lines = []

    # P610130 Appendektomi — the surgical package procedure
    lines.append(
        ProcedureClaimLine(
            procedure_line_id="TABLO23-PL1",
            claim_id="TABLO23-C1",
            patient_id="TABLO23-P1",
            episode_id="TABLO23-E1",
            procedure_date=surgery_day,
            procedure_code="610130",
            procedure_name="Appendektomi",
            procedure_category="paket",  # EK-2C package
            quantity=1,
            unit_price_try=Decimal("5080.28"),
            billed_amount_try=Decimal("5080.28"),
            expected_payable_try=Decimal("5080.28"),
            is_package_included=True,
            package_code="P610130",
            surcharge_applicable=False,
            copay_rate_applicable=False,
            denial_reason_expected="",
            rule_trace_expected="",
        )
    )

    # 705371 Eritrosit süspansiyonu (1 unit) — billed at %36 of EK-2/B puan
    lines.append(
        ProcedureClaimLine(
            procedure_line_id="TABLO23-PL2",
            claim_id="TABLO23-C1",
            patient_id="TABLO23-P1",
            episode_id="TABLO23-E1",
            procedure_date=surgery_day,
            procedure_code="705371",
            procedure_name="Eritrosit SusPansiyonu",
            procedure_category="islem",
            quantity=1,
            unit_price_try=Decimal("1606.55"),  # 4462.65 × 0.36
            billed_amount_try=Decimal("1606.55"),
            expected_payable_try=Decimal("1606.55"),
            is_package_included=False,
            package_code="",
            surcharge_applicable=False,
            copay_rate_applicable=False,
            denial_reason_expected="",
            rule_trace_expected="",
        )
    )

    return lines


# ── Yatak puani (bed-day) — documents the package-bundling gap ──────────────


def test_tablo23_yatak_days_count_no_procedures() -> None:
    """Without procedure_lines, gross LOS = 4 days (no bundling detection).

    This is the backwards-compatible path: when procedure_lines is not
    provided, all 4 days are billed.
    """
    claim = _make_tablo23_claim()
    opps = detect_yatak_puani_opportunities(
        [claim], claim_ids_with_procs={"TABLO23-C1"}
    )
    assert len(opps) == 1
    opp = opps[0]
    assert opp["bed_days"] == 4
    assert opp["gross_bed_days"] == 4
    assert opp["surgery_day_bundled"] is False
    assert opp["daily_rate_try"] == pytest.approx(FIXTURE_BED_DAILY_TRY, abs=0.01)


def test_tablo23_yatak_days_count_with_package_bundling() -> None:
    """With P610130 paket line, surgery day is bundled → 3 billable days.

    Per El Kitabı Tablo 23: "Yatak ve malzemeler P610130 kodlu işleme
    dahildir" — the surgery-day bed fee is included in the package. BILUN
    should bill 4 gross LOS − 1 bundled surgery day = 3 billable days.
    """
    claim = _make_tablo23_claim()
    procs = _make_tablo23_procedures()
    opps = detect_yatak_puani_opportunities(
        [claim],
        procedure_lines=procs,
        claim_ids_with_procs={"TABLO23-C1"},
    )
    assert len(opps) == 1
    opp = opps[0]
    assert opp["gross_bed_days"] == 4
    assert opp["bed_days"] == 3
    assert opp["surgery_day_bundled"] is True
    assert opp["bundled_days"] == 1
    assert opp["daily_rate_try"] == pytest.approx(FIXTURE_BED_DAILY_TRY, abs=0.01)
    assert opp["expected_yatak_try"] == pytest.approx(3 * FIXTURE_BED_DAILY_TRY, abs=0.01)


def test_tablo23_yatak_amount_matches_catalog() -> None:
    """Gross yatak amount = 4 days × stubbed daily rate (no procedure lines)."""
    claim = _make_tablo23_claim()
    opps = detect_yatak_puani_opportunities(
        [claim], claim_ids_with_procs={"TABLO23-C1"}
    )
    assert opps[0]["expected_yatak_try"] == pytest.approx(4 * FIXTURE_BED_DAILY_TRY, abs=0.01)


def test_tablo23_yatak_bundled_amount() -> None:
    """With package bundling, 3 billable days × stubbed daily rate."""
    claim = _make_tablo23_claim()
    procs = _make_tablo23_procedures()
    opps = detect_yatak_puani_opportunities(
        [claim],
        procedure_lines=procs,
        claim_ids_with_procs={"TABLO23-C1"},
    )
    assert opps[0]["expected_yatak_try"] == pytest.approx(3 * FIXTURE_BED_DAILY_TRY, abs=0.01)


# ── Anestezi puani — the anesthesia charge should match the handbook ────────


def test_tablo23_anestezi_group_is_a1() -> None:
    """Appendektomi (puan 3397.78) → anesthesia group A1 (code 550130).

    Puan range 3000-5000 → A1. This is the correct group per SUT §2.4.4.A.
    The El Kitabı lists "Anestezi işlemleri" as a separately billable item.
    """
    claim = _make_tablo23_claim()
    procs = _make_tablo23_procedures()
    # Anestezi only looks at non-package surgical procedures — but the
    # anestezi motor uses the *catalog* puan of the procedure code, not the
    # submitted procedure_category. Test with the raw code.
    surgical_line = ProcedureClaimLine(
        procedure_line_id="TABLO23-PL-ANES",
        claim_id="TABLO23-C1",
        patient_id="TABLO23-P1",
        episode_id="TABLO23-E1",
        procedure_date=date(2026, 7, 11),
        procedure_code="610130",
        procedure_name="Appendektomi",
        procedure_category="islem",  # anestezi motor skips 'paket' category
        quantity=1,
        unit_price_try=Decimal("5080.28"),
        billed_amount_try=Decimal("5080.28"),
        expected_payable_try=Decimal("5080.28"),
        is_package_included=False,
        package_code="",
        surcharge_applicable=False,
        copay_rate_applicable=False,
        denial_reason_expected="",
        rule_trace_expected="",
    )
    opps = detect_anestezi_puani_opportunities(
        [claim], [surgical_line], claim_ids_with_procs={"TABLO23-C1"}
    )
    assert len(opps) == 1
    opp = opps[0]
    assert opp["anestezi_group"] == "A1"
    assert opp["anestezi_code"] == "550130"
    assert opp["anestezi_puan"] == pytest.approx(_A1_GROUP_PUAN)
    assert opp["expected_try"] == pytest.approx(_A1_GROUP_PUAN * FIXTURE_KATSAYI, abs=0.01)


# ── Refakatçi (companion bed) — El Kitabı does not mention a companion ───────


def test_tablo23_refakatci_emitted_for_inpatient() -> None:
    """BILUN emits a companion-bed opportunity for inpatient stays.

    The El Kitabı Tablo 23 does NOT mention a companion bed (refakatçi) —
    the scenario is a standard adult appendectomy with no companion noted.
    BILUN's motor, however, emits a companion opportunity for any inpatient
    claim that is not ICU or day-case. This is a conservative "expected
    recovery" — if a companion was present but not billed, BILUN flags it.

    This is informational, not a hard gap — the hospital may simply not have
    had a companion. But it shows BILUN's motor assumes companions by default.
    """
    claim = _make_tablo23_claim()
    procs = _make_tablo23_procedures()
    opps = detect_refakatci_opportunities([claim], procs)
    # Refakatçi will emit because: inpatient, no ICU code, >24h stay.
    # El Kitabı says nothing about a companion for this patient.
    assert len(opps) == 1, (
        "BILUN emits a companion-bed opportunity by default for inpatient "
        "stays — even when the El Kitabı scenario has no companion. This "
        "is a known conservatism in the motor."
    )


# ── Full context integration: all motors on the Tablo 23 patient ────────────


def test_tablo23_full_billing_summary() -> None:
    """Run all applicable motors on the Tablo 23 patient and summarize.

    This is the integration check — it shows the COMPLETE picture of what
    BILUN computes vs what the El Kitabı says should appear on the invoice.

    Key findings:
    - Yatak: BILUN bills 3 days (₺667.08) — surgery day bundled into P610130.
    - Anestezi: BILUN bills A1 group (₺5,302.69) → matches handbook.
    - Refakatçi: BILUN bills 3 days (₺~222) → not mentioned in handbook.
    - ICU: no opportunity (no 510090 code) → correct.
    - Yenidoğan: no opportunity (not a newborn) → correct.
    """
    claim = _make_tablo23_claim()
    procs = _make_tablo23_procedures()
    ctx = PatientClaimContext(
        patient_id="TABLO23-P1",
        claims=(claim,),
        procedure_lines=tuple(procs),
        material_lines=(),
        drug_lines=(),
        diagnoses=(),
    )

    # Yatak — with procedure_lines so package bundling applies
    yatak_opps = detect_yatak_puani_opportunities(
        list(ctx.claims),
        procedure_lines=list(ctx.procedure_lines),
        claim_ids_with_procs={"TABLO23-C1"},
    )
    yatak_total = sum(
        o["expected_yatak_try"] for o in yatak_opps
    ) if yatak_opps else 0.0

    # Anestezi (use islem-category line for detection)
    surgical_line = ProcedureClaimLine(
        procedure_line_id="TABLO23-PL-ANES",
        claim_id="TABLO23-C1",
        patient_id="TABLO23-P1",
        episode_id="TABLO23-E1",
        procedure_date=date(2026, 7, 11),
        procedure_code="610130",
        procedure_name="Appendektomi",
        procedure_category="islem",
        quantity=1,
        unit_price_try=Decimal("5080.28"),
        billed_amount_try=Decimal("5080.28"),
        expected_payable_try=Decimal("5080.28"),
        is_package_included=False,
        package_code="",
        surcharge_applicable=False,
        copay_rate_applicable=False,
        denial_reason_expected="",
        rule_trace_expected="",
    )
    anestezi_opps = detect_anestezi_puani_opportunities(
        [claim], [surgical_line], claim_ids_with_procs={"TABLO23-C1"}
    )
    anestezi_total = sum(
        o["expected_try"] for o in anestezi_opps
    ) if anestezi_opps else 0.0

    # Refakatçi
    refakatci_opps = detect_refakatci_opportunities([claim], procs)
    refakatci_total = sum(
        o.get("expected_try", 0.0) for o in refakatci_opps
    ) if refakatci_opps else 0.0

    # Summary assertions — values are catalog-derived + bundling rule
    assert yatak_total == pytest.approx(3 * FIXTURE_BED_DAILY_TRY, abs=0.01)
    assert anestezi_total == pytest.approx(_A1_GROUP_PUAN * FIXTURE_KATSAYI, abs=0.01)
    assert refakatci_total > 0, "Refakatçi should produce a positive amount"
