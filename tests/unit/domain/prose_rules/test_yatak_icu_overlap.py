"""Unit tests for YB→servis geçiş günü yatak koordinasyon katmanı.

EK-2B defines both **510010** (Standart yatak) and **510090** (Yoğun bakım)
as covering *"Yemek, yatak, hasta vizit hizmetlerini kapsar"*. When a
patient is discharged/transferred from ICU on day D, 510090 (last ICU day)
already pays for the bed; billing 510010 (service bed) on the same day D is
double-billing.

Covers:
  - reconcile (recoverable-uplift path): ICU discharge day == service entry
    day → the day is dropped from yatak bed days (single bed charge);
    different days → behavior unchanged; package-surgery day + ICU combo
    regression (no double-subtract); same-claim ICU+service; same-day ICU.
  - detect (audit-exposure path): a 510010 line dated on an ICU last day is
    a violation; P-prefix normalization; multi-claim isolation;
    analyze_claim wiring.
  - patient_report post-processing wiring (wrapper + full report).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from tests.unit._helpers.catalog_stubs import (
    FIXTURE_BED_DAILY_TRY,
    install_yatak_catalog_stub,
)

pytestmark = pytest.mark.unit

_ICU_ADMISSION = date(2026, 7, 10)
_ICU_DISCHARGE = date(2026, 7, 13)  # ICU last day → 510090 billed


@pytest.fixture(autouse=True)
def _stub_bed_catalog(monkeypatch: pytest.MonkeyPatch) -> None:
    install_yatak_catalog_stub(monkeypatch)


def _make_claim_header(
    *,
    claim_id: str = "C1",
    claim_type: str = "yatis",
    admission: date | None = _ICU_ADMISSION,
    discharge: date | None = _ICU_DISCHARGE,
    department: str = "Yogun Bakim",
):
    from src.bilun.domain.claims.models import ClaimHeader

    return ClaimHeader(
        claim_id=claim_id,
        patient_id="P1",
        episode_id="E1",
        claim_type=claim_type,
        facility_tier="3_basamak",
        provider_type="sozlesmeli",
        department=department,
        admission_date=admission,
        discharge_date=discharge,
        claim_start_date=admission or date.today(),
        claim_end_date=discharge or date.today(),
        primary_icd10="J96.0",
        package_candidate=False,
        expected_total_billed_try=Decimal("10000"),
        expected_total_payable_try=Decimal("9000"),
        expected_denial_reason="",
        scenario_tag="test",
    )


def _make_proc_line(
    *,
    procedure_line_id: str = "ISL-1",
    claim_id: str = "C1",
    procedure_code: str = "510090",
    procedure_name: str = "Yogun bakim",
    procedure_date: date = _ICU_ADMISSION,
    procedure_category: str = "islem",
    billed_amount_try: str = "742.60",
):
    from src.bilun.domain.claims.models import ProcedureClaimLine

    return ProcedureClaimLine(
        procedure_line_id=procedure_line_id,
        claim_id=claim_id,
        patient_id="P1",
        episode_id="E1",
        procedure_date=procedure_date,
        procedure_code=procedure_code,
        procedure_name=procedure_name,
        procedure_category=procedure_category,
        quantity=1,
        unit_price_try=Decimal(billed_amount_try),
        billed_amount_try=Decimal(billed_amount_try),
        expected_payable_try=Decimal("700.00"),
        is_package_included=False,
        package_code="",
        surcharge_applicable=False,
        copay_rate_applicable=False,
        denial_reason_expected="",
        rule_trace_expected="",
    )


def _make_ctx(claims, procs) -> object:
    from src.bilun.domain.claims.patient_context import PatientClaimContext

    return PatientClaimContext(
        patient_id="P1",
        claims=tuple(claims),
        procedure_lines=tuple(procs),
        material_lines=(),
        drug_lines=(),
        diagnoses=(),
    )


# ── Reconcile: recoverable-uplift path ──────────────────────────────────────


def _yatak_opp(claim_id: str, opps: list[dict]) -> dict:
    return next(o for o in opps if o["claim_id"] == claim_id)


def test_reconcile_icu_discharge_day_equals_service_entry_day() -> None:
    """(a) YB çıkış günü = servis giriş günü → o gün yatak tek kez ödenir.

    ICU claim Jul 10→13 (510090 last day Jul 13); service claim Jul 13→15
    (inclusive LOS 13,14,15). The transition day Jul 13 is already paid by
    510090 → the service bed day is dropped: 3 → 2 billable days.
    """
    from src.bilun.domain.prose_rules.yatak_icu_overlap import (
        reconcile_yatak_bed_days,
    )
    from src.bilun.domain.prose_rules.yatak_puani import (
        detect_yatak_puani_opportunities,
    )

    icu = _make_claim_header(claim_id="ICU", department="Yogun Bakim")
    srv = _make_claim_header(
        claim_id="SRV",
        admission=date(2026, 7, 13),
        discharge=date(2026, 7, 15),
        department="genel_cerrahi",
    )
    procs = [
        _make_proc_line(claim_id="ICU", procedure_line_id="ICU-1", procedure_code="510090"),
        _make_proc_line(
            claim_id="SRV",
            procedure_line_id="SRV-1",
            procedure_code="510010",
            procedure_name="Standart yatak",
            procedure_date=date(2026, 7, 13),
            billed_amount_try="0.00",  # service bed not yet billed → uplift path
        ),
    ]
    claims = [icu, srv]
    opps = detect_yatak_puani_opportunities(claims, procs, claim_ids_with_procs={"ICU", "SRV"})

    srv_opp = _yatak_opp("SRV", opps)
    assert srv_opp["gross_bed_days"] == 3
    assert srv_opp["bed_days"] == 3

    reconciled = reconcile_yatak_bed_days(opps, claims, procs)

    srv_rec = _yatak_opp("SRV", reconciled)
    assert srv_rec["bed_days"] == 2
    assert srv_rec["icu_overlap_days"] == 1
    assert srv_rec["icu_overlap_dates"] == ["2026-07-13"]
    assert srv_rec["expected_yatak_try"] == pytest.approx(2 * FIXTURE_BED_DAILY_TRY, abs=0.01)
    assert srv_rec["recoverable_uplift_try"] == pytest.approx(
        2 * FIXTURE_BED_DAILY_TRY, abs=0.01
    )
    assert "düşüldü" in srv_rec["detail"]

    # The ICU claim's own yatak expectation also drops its 510090 last day.
    icu_rec = _yatak_opp("ICU", reconciled)
    assert icu_rec["gross_bed_days"] == 4
    assert icu_rec["bed_days"] == 3
    assert icu_rec["icu_overlap_days"] == 1


def test_reconcile_credit_line_never_makes_the_recoverable_exceed_the_expected_charge() -> None:
    """A negative 510010 line (a reversal) on the service claim: after the ICU day is dropped the recoverable
    amount is at most the 2 remaining days' charge (review round 2, G4: the formula had no cap)."""
    from src.bilun.domain.prose_rules.yatak_icu_overlap import reconcile_yatak_bed_days
    from src.bilun.domain.prose_rules.yatak_puani import detect_yatak_puani_opportunities

    icu = _make_claim_header(claim_id="ICU", department="Yogun Bakim")
    srv = _make_claim_header(
        claim_id="SRV", admission=date(2026, 7, 13), discharge=date(2026, 7, 15), department="genel_cerrahi"
    )
    procs = [
        _make_proc_line(claim_id="ICU", procedure_line_id="ICU-1", procedure_code="510090"),
        _make_proc_line(
            claim_id="SRV", procedure_line_id="SRV-1", procedure_code="510010", procedure_name="Standart yatak",
            procedure_date=date(2026, 7, 13), billed_amount_try="-100.00",
        ),
    ]
    claims = [icu, srv]
    opps = detect_yatak_puani_opportunities(claims, procs, claim_ids_with_procs={"ICU", "SRV"})

    srv_rec = _yatak_opp("SRV", reconcile_yatak_bed_days(opps, claims, procs))

    assert srv_rec["bed_days"] == 2
    assert srv_rec["expected_yatak_try"] == pytest.approx(2 * FIXTURE_BED_DAILY_TRY, abs=0.01)
    assert srv_rec["recoverable_uplift_try"] == pytest.approx(2 * FIXTURE_BED_DAILY_TRY, abs=0.01)


def test_reconcile_different_days_behavior_unchanged() -> None:
    """(b) Servis claim'inin LOS'u YB son gününe denk gelmezse davranış değişmez.

    ICU last day Jul 12; service claim Jul 13→15 → no transition-day overlap:
    the service opportunity is returned UNCHANGED (same object, same fields).
    Only the ICU claim's own yatak expectation drops its own 510090 last day
    (that day's bed is already paid by ICU — coordination layer's core rule).
    """
    from src.bilun.domain.prose_rules.yatak_icu_overlap import (
        reconcile_yatak_bed_days,
    )
    from src.bilun.domain.prose_rules.yatak_puani import (
        detect_yatak_puani_opportunities,
    )

    icu = _make_claim_header(
        claim_id="ICU",
        admission=date(2026, 7, 10),
        discharge=date(2026, 7, 12),
    )
    srv = _make_claim_header(
        claim_id="SRV",
        admission=date(2026, 7, 13),
        discharge=date(2026, 7, 15),
        department="genel_cerrahi",
    )
    procs = [
        _make_proc_line(claim_id="ICU", procedure_line_id="ICU-1", procedure_code="510090"),
        _make_proc_line(
            claim_id="SRV",
            procedure_line_id="SRV-1",
            procedure_code="510010",
            procedure_name="Standart yatak",
            procedure_date=date(2026, 7, 14),
        ),
    ]
    claims = [icu, srv]
    opps = detect_yatak_puani_opportunities(claims, procs, claim_ids_with_procs={"ICU", "SRV"})

    srv_opp = _yatak_opp("SRV", opps)
    reconciled = reconcile_yatak_bed_days(opps, claims, procs)

    # Service claim: no transition-day overlap → same object, fields intact.
    srv_rec = _yatak_opp("SRV", reconciled)
    assert srv_rec is srv_opp
    assert srv_rec["bed_days"] == 3
    assert "icu_overlap_days" not in srv_rec
    assert srv_rec["expected_yatak_try"] == pytest.approx(3 * FIXTURE_BED_DAILY_TRY, abs=0.01)

    # ICU claim: its own 510090 last day (Jul 12) is dropped from yatak.
    icu_rec = _yatak_opp("ICU", reconciled)
    assert icu_rec["gross_bed_days"] == 3
    assert icu_rec["bed_days"] == 2
    assert icu_rec["icu_overlap_days"] == 1
    assert icu_rec["icu_overlap_dates"] == ["2026-07-12"]


def test_reconcile_package_surgery_plus_icu_regression() -> None:
    """(c) Paket penceresi + YB kombinasyonu — paket sonrası YB son günü düşülür.

    Service claim Jul 10→20 (11 gross days) with P610130 (Group C, 8-day
    window Jul 10→17) on Jul 10 (8 bundled days → 3 post-window billable days:
    Jul 18, 19, 20) and an ICU stay ending on Jul 18 → 3 − 1 = 2 billable days.
    """
    from src.bilun.domain.prose_rules.yatak_icu_overlap import (
        reconcile_yatak_bed_days,
    )
    from src.bilun.domain.prose_rules.yatak_puani import (
        detect_yatak_puani_opportunities,
    )

    icu = _make_claim_header(
        claim_id="ICU",
        admission=date(2026, 7, 17),
        discharge=date(2026, 7, 18),
    )
    srv = _make_claim_header(
        claim_id="SRV",
        admission=date(2026, 7, 10),
        discharge=date(2026, 7, 20),
        department="genel_cerrahi",
    )
    procs = [
        _make_proc_line(claim_id="ICU", procedure_line_id="ICU-1", procedure_code="510090"),
        _make_proc_line(
            claim_id="SRV",
            procedure_line_id="SRV-PKG",
            procedure_code="610130",
            procedure_name="Appendektomi",
            procedure_date=date(2026, 7, 10),
            procedure_category="paket",
        ),
        _make_proc_line(
            claim_id="SRV",
            procedure_line_id="SRV-1",
            procedure_code="510010",
            procedure_name="Standart yatak",
            procedure_date=date(2026, 7, 19),
        ),
    ]
    claims = [icu, srv]
    opps = detect_yatak_puani_opportunities(claims, procs, claim_ids_with_procs={"ICU", "SRV"})

    srv_opp = _yatak_opp("SRV", opps)
    assert srv_opp["gross_bed_days"] == 11
    assert srv_opp["surgery_day_bundled"] is True
    assert srv_opp["bed_days"] == 3  # 8-day Group C window Jul 10-17 bundled

    reconciled = reconcile_yatak_bed_days(opps, claims, procs)

    srv_rec = _yatak_opp("SRV", reconciled)
    # Jul 18 (post-window ICU last day) additionally dropped → 2 billable days.
    assert srv_rec["bed_days"] == 2
    assert srv_rec["icu_overlap_days"] == 1
    assert srv_rec["icu_overlap_dates"] == ["2026-07-18"]
    assert srv_rec["expected_yatak_try"] == pytest.approx(2 * FIXTURE_BED_DAILY_TRY, abs=0.01)


def test_reconcile_package_surgery_day_equals_icu_last_day_no_double_subtract() -> None:
    """Paket penceresi içindeki YB son günü ikinci kez düşülmez (regresyon).

    When the ICU discharge day falls inside the EK-2C package window, the day
    is already excluded by package bundling; the reconcile must NOT subtract
    it a second time from post-window days.
    """
    from src.bilun.domain.prose_rules.yatak_icu_overlap import (
        reconcile_yatak_bed_days,
    )
    from src.bilun.domain.prose_rules.yatak_puani import (
        detect_yatak_puani_opportunities,
    )

    icu = _make_claim_header(claim_id="ICU")
    srv = _make_claim_header(
        claim_id="SRV",
        admission=date(2026, 7, 13),
        discharge=date(2026, 7, 22),
        department="genel_cerrahi",
    )
    procs = [
        _make_proc_line(claim_id="ICU", procedure_line_id="ICU-1", procedure_code="510090"),
        _make_proc_line(
            claim_id="SRV",
            procedure_line_id="SRV-PKG",
            procedure_code="610130",
            procedure_name="Appendektomi",
            procedure_date=date(2026, 7, 13),  # surgery day == ICU last day (window Jul 13-20)
            procedure_category="paket",
        ),
        _make_proc_line(
            claim_id="SRV",
            procedure_line_id="SRV-1",
            procedure_code="510010",
            procedure_name="Standart yatak",
            procedure_date=date(2026, 7, 21),
        ),
    ]
    claims = [icu, srv]
    opps = detect_yatak_puani_opportunities(claims, procs, claim_ids_with_procs={"ICU", "SRV"})

    srv_opp = _yatak_opp("SRV", opps)
    assert srv_opp["bed_days"] == 2  # Jul 13-20 bundled in 8-day Group C window; Jul 21-22 billable

    reconciled = reconcile_yatak_bed_days(opps, claims, procs)

    srv_rec = _yatak_opp("SRV", reconciled)
    assert srv_rec["bed_days"] == 2  # no additional drop — no double subtraction
    assert srv_rec.get("icu_overlap_days", 0) == 0


def test_reconcile_same_claim_icu_and_service_bed() -> None:
    """Aynı claim hem YB hem servis yatağı taşırsa YB son günü düşülür."""
    from src.bilun.domain.prose_rules.yatak_icu_overlap import (
        reconcile_yatak_bed_days,
    )
    from src.bilun.domain.prose_rules.yatak_puani import (
        detect_yatak_puani_opportunities,
    )

    claim = _make_claim_header(claim_id="C1", department="Yogun Bakim")
    procs = [
        _make_proc_line(procedure_line_id="ISL-1", procedure_code="510090"),
        _make_proc_line(
            procedure_line_id="ISL-2",
            procedure_code="510010",
            procedure_name="Standart yatak",
            procedure_date=_ICU_DISCHARGE,
        ),
    ]
    claims = [claim]
    opps = detect_yatak_puani_opportunities(claims, procs, claim_ids_with_procs={"C1"})
    assert _yatak_opp("C1", opps)["bed_days"] == 4

    reconciled = reconcile_yatak_bed_days(opps, claims, procs)

    rec = _yatak_opp("C1", reconciled)
    assert rec["bed_days"] == 3
    assert rec["icu_overlap_days"] == 1
    assert rec["icu_overlap_dates"] == ["2026-07-13"]


def test_reconcile_same_day_icu_stay() -> None:
    """Aynı gün YB yatışı → servis yatağı günü tamamen düşülür (0 gün)."""
    from src.bilun.domain.prose_rules.yatak_icu_overlap import (
        reconcile_yatak_bed_days,
    )
    from src.bilun.domain.prose_rules.yatak_puani import (
        detect_yatak_puani_opportunities,
    )

    claim = _make_claim_header(
        claim_id="C1",
        admission=date(2026, 7, 10),
        discharge=date(2026, 7, 10),
    )
    procs = [
        _make_proc_line(procedure_line_id="ISL-1", procedure_code="510090"),
        _make_proc_line(
            procedure_line_id="ISL-2",
            procedure_code="510010",
            procedure_name="Standart yatak",
            procedure_date=date(2026, 7, 10),
        ),
    ]
    claims = [claim]
    opps = detect_yatak_puani_opportunities(claims, procs, claim_ids_with_procs={"C1"})
    assert _yatak_opp("C1", opps)["bed_days"] == 1

    reconciled = reconcile_yatak_bed_days(opps, claims, procs)

    rec = _yatak_opp("C1", reconciled)
    assert rec["bed_days"] == 0
    assert rec["expected_yatak_try"] == 0.0
    assert rec["recoverable_uplift_try"] == 0.0


def test_reconcile_multiple_icu_last_days_dropped() -> None:
    """Birden fazla YB son günü aynı servis LOS'una denk gelirse hepsi düşülür."""
    from src.bilun.domain.prose_rules.yatak_icu_overlap import (
        reconcile_yatak_bed_days,
    )
    from src.bilun.domain.prose_rules.yatak_puani import (
        detect_yatak_puani_opportunities,
    )

    icu1 = _make_claim_header(
        claim_id="ICU1",
        admission=date(2026, 7, 10),
        discharge=date(2026, 7, 12),
    )
    icu2 = _make_claim_header(
        claim_id="ICU2",
        admission=date(2026, 7, 12),
        discharge=date(2026, 7, 13),
    )
    srv = _make_claim_header(
        claim_id="SRV",
        admission=date(2026, 7, 12),
        discharge=date(2026, 7, 15),
        department="genel_cerrahi",
    )
    procs = [
        _make_proc_line(claim_id="ICU1", procedure_line_id="ICU1-1", procedure_code="510090"),
        _make_proc_line(claim_id="ICU2", procedure_line_id="ICU2-1", procedure_code="510090"),
        _make_proc_line(
            claim_id="SRV",
            procedure_line_id="SRV-1",
            procedure_code="510010",
            procedure_name="Standart yatak",
            procedure_date=date(2026, 7, 14),
        ),
    ]
    claims = [icu1, icu2, srv]
    opps = detect_yatak_puani_opportunities(claims, procs, claim_ids_with_procs={"ICU1", "ICU2", "SRV"})

    reconciled = reconcile_yatak_bed_days(opps, claims, procs)

    srv_rec = _yatak_opp("SRV", reconciled)
    # LOS Jul 12-15 (4 days); ICU last days Jul 12 and Jul 13 both inside →
    # 4 − 2 = 2 billable days.
    assert srv_rec["gross_bed_days"] == 4
    assert srv_rec["bed_days"] == 2
    assert srv_rec["icu_overlap_days"] == 2
    assert srv_rec["icu_overlap_dates"] == ["2026-07-12", "2026-07-13"]


# ── Detect: audit-exposure path ─────────────────────────────────────────────


def test_detect_510010_on_icu_discharge_day_violation() -> None:
    """510010 satırı YB çıkış gününe tarihlenmişse violation döner."""
    from src.bilun.domain.prose_rules.yatak_icu_overlap import (
        detect_yatak_icu_overlap,
    )

    icu = _make_claim_header(claim_id="ICU")
    srv = _make_claim_header(
        claim_id="SRV",
        admission=date(2026, 7, 13),
        discharge=date(2026, 7, 15),
        department="genel_cerrahi",
    )
    procs = [
        _make_proc_line(claim_id="ICU", procedure_line_id="ICU-1", procedure_code="510090"),
        _make_proc_line(
            claim_id="SRV",
            procedure_line_id="SRV-1",
            procedure_code="510010",
            procedure_name="Standart yatak",
            procedure_date=date(2026, 7, 13),
        ),
    ]
    violations = detect_yatak_icu_overlap(
        [icu, srv], procs, claim_ids_with_procs={"ICU", "SRV"}
    )

    assert len(violations) == 1
    v = violations[0]
    assert v["type"] == "yatak_icu_overlap_double_billing"
    assert v["claim_id"] == "SRV"
    assert v["rule_id"] == "yatak_icu_overlap_510010"
    assert v["procedure_code"] == "510010"
    assert v["overlap_date"] == "2026-07-13"
    assert v["icu_claim_id"] == "ICU"
    assert v["sut_section_id"] == "2.4.4.H"
    assert v["savings_category"] == "audit_exposure"
    assert v["savings_basis"] == "sourced"
    assert v["severity"] == "error"
    assert v["risk_amount_try"] == pytest.approx(742.60, abs=0.01)
    assert "510090" in v["detail"]


@pytest.mark.parametrize("bed_amount", ["0", "-0.01", "-742.60"])
def test_detect_non_positive_bed_charge_has_no_double_billing(bed_amount: str) -> None:
    from src.bilun.domain.prose_rules.yatak_icu_overlap import detect_yatak_icu_overlap

    claims = [
        _make_claim_header(claim_id="ICU"),
        _make_claim_header(claim_id="SRV", department="genel_cerrahi"),
    ]
    procs = [
        _make_proc_line(claim_id="ICU", procedure_line_id="ICU-LINE"),
        _make_proc_line(
            claim_id="SRV",
            procedure_line_id="BED-LINE",
            procedure_code="510010",
            procedure_name="Standart yatak",
            procedure_date=_ICU_DISCHARGE,
            billed_amount_try=bed_amount,
        ),
    ]

    assert detect_yatak_icu_overlap(claims, procs) == []


@pytest.mark.parametrize("bed_amount", ["0.01", "742.60"])
def test_detect_positive_bed_names_only_qualifying_icu_evidence(bed_amount: str) -> None:
    from src.bilun.domain.prose_rules.yatak_icu_overlap import detect_yatak_icu_overlap

    claims = [
        _make_claim_header(claim_id="ICU-DAY-RATE"),
        _make_claim_header(claim_id="SRV", department="genel_cerrahi"),
        _make_claim_header(claim_id="OUTPATIENT", claim_type="ayakta"),
        _make_claim_header(claim_id="MISSING-ADMISSION", admission=None),
        _make_claim_header(claim_id="ICU-PACKAGE"),
        _make_claim_header(claim_id="EARLIER-ICU", discharge=date(2026, 7, 12)),
    ]
    procs = [
        _make_proc_line(claim_id=claim_id, procedure_line_id=f"{claim_id}-LINE")
        for claim_id in ("ICU-DAY-RATE", "OUTPATIENT", "MISSING-ADMISSION", "EARLIER-ICU")
    ]
    procs.extend(
        [
            _make_proc_line(
                claim_id="ICU-PACKAGE",
                procedure_line_id="PACKAGE-LINE",
                procedure_code="P552001",
            ),
            _make_proc_line(
                claim_id="SRV",
                procedure_line_id="BED-LINE",
                procedure_code="510010",
                procedure_name="Standart yatak",
                procedure_date=_ICU_DISCHARGE,
                billed_amount_try=bed_amount,
            ),
        ]
    )

    violations = detect_yatak_icu_overlap(claims, procs)

    assert len(violations) == 1
    finding = violations[0]
    assert finding["claim_id"] == "SRV"
    assert finding["procedure_line_id"] == "BED-LINE"
    assert finding["icu_claim_id"] == "ICU-DAY-RATE,ICU-PACKAGE"
    assert finding["risk_amount_try"] == pytest.approx(float(bed_amount))
    assert finding["severity"] == "error"
    assert finding["detail"].endswith("İlgili YB takibi: ICU-DAY-RATE,ICU-PACKAGE.")


def test_detect_different_days_no_violation() -> None:
    """(b) Farklı günler → violation yok."""
    from src.bilun.domain.prose_rules.yatak_icu_overlap import (
        detect_yatak_icu_overlap,
    )

    icu = _make_claim_header(
        claim_id="ICU",
        admission=date(2026, 7, 10),
        discharge=date(2026, 7, 12),
    )
    srv = _make_claim_header(
        claim_id="SRV",
        admission=date(2026, 7, 13),
        discharge=date(2026, 7, 15),
        department="genel_cerrahi",
    )
    procs = [
        _make_proc_line(claim_id="ICU", procedure_line_id="ICU-1", procedure_code="510090"),
        _make_proc_line(
            claim_id="SRV",
            procedure_line_id="SRV-1",
            procedure_code="510010",
            procedure_name="Standart yatak",
            procedure_date=date(2026, 7, 14),
        ),
    ]
    violations = detect_yatak_icu_overlap(
        [icu, srv], procs, claim_ids_with_procs={"ICU", "SRV"}
    )
    assert violations == []


def test_detect_p_prefixed_codes() -> None:
    """P-prefixed MEDULA kodları normalize edilir (P510090 / P510010)."""
    from src.bilun.domain.prose_rules.yatak_icu_overlap import (
        detect_yatak_icu_overlap,
    )

    icu = _make_claim_header(claim_id="ICU")
    srv = _make_claim_header(
        claim_id="SRV",
        admission=date(2026, 7, 13),
        discharge=date(2026, 7, 15),
        department="genel_cerrahi",
    )
    procs = [
        _make_proc_line(
            claim_id="ICU", procedure_line_id="ICU-1", procedure_code="P510090"
        ),
        _make_proc_line(
            claim_id="SRV",
            procedure_line_id="SRV-1",
            procedure_code="P510010",
            procedure_name="Standart yatak",
            procedure_date=date(2026, 7, 13),
        ),
    ]
    violations = detect_yatak_icu_overlap(
        [icu, srv], procs, claim_ids_with_procs={"ICU", "SRV"}
    )
    assert len(violations) == 1
    assert violations[0]["claim_id"] == "SRV"


def test_detect_no_icu_codes_no_violation() -> None:
    """Hiçbir claim'de YB kodu yoksa → violation yok."""
    from src.bilun.domain.prose_rules.yatak_icu_overlap import (
        detect_yatak_icu_overlap,
    )

    srv = _make_claim_header(
        claim_id="SRV",
        admission=date(2026, 7, 13),
        discharge=date(2026, 7, 15),
        department="genel_cerrahi",
    )
    procs = [
        _make_proc_line(
            claim_id="SRV",
            procedure_line_id="SRV-1",
            procedure_code="510010",
            procedure_name="Standart yatak",
            procedure_date=date(2026, 7, 13),
        ),
    ]
    violations = detect_yatak_icu_overlap(
        [srv], procs, claim_ids_with_procs={"SRV"}
    )
    assert violations == []


def test_detect_outpatient_icu_claim_skipped() -> None:
    """Ayakta (outpatient) YB claim'i YB son günü sayılmaz → violation yok."""
    from src.bilun.domain.prose_rules.yatak_icu_overlap import (
        detect_yatak_icu_overlap,
    )

    icu = _make_claim_header(claim_id="ICU", claim_type="ayakta")
    srv = _make_claim_header(
        claim_id="SRV",
        admission=date(2026, 7, 13),
        discharge=date(2026, 7, 15),
        department="genel_cerrahi",
    )
    procs = [
        _make_proc_line(claim_id="ICU", procedure_line_id="ICU-1", procedure_code="510090"),
        _make_proc_line(
            claim_id="SRV",
            procedure_line_id="SRV-1",
            procedure_code="510010",
            procedure_name="Standart yatak",
            procedure_date=date(2026, 7, 13),
        ),
    ]
    violations = detect_yatak_icu_overlap(
        [icu, srv], procs, claim_ids_with_procs={"ICU", "SRV"}
    )
    assert violations == []


def test_detect_no_procedure_lines_no_violation() -> None:
    """Procedure satırı yoksa → violation yok."""
    from src.bilun.domain.prose_rules.yatak_icu_overlap import (
        detect_yatak_icu_overlap,
    )

    header = _make_claim_header()
    assert detect_yatak_icu_overlap([header], None) == []
    assert detect_yatak_icu_overlap([header], []) == []


def test_analyze_claim_wires_yatak_icu_overlap() -> None:
    """Denetim riski yolu: çift faturalanan 510010 analyze_claim'e ulaşır."""
    from src.bilun.domain.billing.engine import analyze_claim

    icu = _make_claim_header(claim_id="ICU")
    srv = _make_claim_header(
        claim_id="SRV",
        admission=date(2026, 7, 13),
        discharge=date(2026, 7, 15),
        department="genel_cerrahi",
    )
    procs = [
        _make_proc_line(claim_id="ICU", procedure_line_id="ICU-1", procedure_code="510090"),
        _make_proc_line(
            claim_id="SRV",
            procedure_line_id="SRV-1",
            procedure_code="510010",
            procedure_name="Standart yatak",
            procedure_date=date(2026, 7, 13),
        ),
    ]
    ctx = _make_ctx([icu, srv], procs)
    violations = analyze_claim(ctx)
    hits = [
        v
        for v in violations
        if v.get("rule_id") == "yatak_icu_overlap_510010"
        or v.get("type") == "yatak_icu_overlap_double_billing"
    ]
    assert len(hits) == 1
    assert hits[0]["procedure_code"] == "510010"
    assert hits[0]["savings_category"] == "audit_exposure"
    assert hits[0]["severity"] == "error"
    assert hits[0]["overlap_date"] == "2026-07-13"


# ── Wrapper + patient_report post-processing wiring ─────────────────────────


def test_wrapper_reconciles_yatak_review() -> None:
    """claim_yatak_icu_overlap wrapper, review metadata'yı koruyarak düzeltir."""
    from src.bilun.domain.billing.claim_yatak_icu_overlap import (
        reconcile_yatak_icu_overlap,
    )
    from src.bilun.domain.billing.claim_yatak_puani import (
        recommend_yatak_puani_from_claims,
    )

    icu = _make_claim_header(claim_id="ICU")
    srv = _make_claim_header(
        claim_id="SRV",
        admission=date(2026, 7, 13),
        discharge=date(2026, 7, 15),
        department="genel_cerrahi",
    )
    procs = [
        _make_proc_line(claim_id="ICU", procedure_line_id="ICU-1", procedure_code="510090"),
        _make_proc_line(
            claim_id="SRV",
            procedure_line_id="SRV-1",
            procedure_code="510010",
            procedure_name="Standart yatak",
            procedure_date=date(2026, 7, 13),
            billed_amount_try="0.00",
        ),
    ]
    ctx = _make_ctx([icu, srv], procs)

    review = recommend_yatak_puani_from_claims(ctx)
    assert review.exactness_status == "exact"
    assert _yatak_opp("SRV", review.opportunities)["bed_days"] == 3

    reconciled = reconcile_yatak_icu_overlap(ctx, review)
    assert reconciled.exactness_status == "exact"
    assert reconciled.unavailable_reason is None
    assert reconciled.rule_source == review.rule_source
    assert _yatak_opp("SRV", reconciled.opportunities)["bed_days"] == 2
    assert _yatak_opp("ICU", reconciled.opportunities)["bed_days"] == 3
    assert reconciled.confirmed_yatak_try == pytest.approx(
        5 * FIXTURE_BED_DAILY_TRY, abs=0.01
    )


def test_wrapper_no_overlap_returns_same_review() -> None:
    """YB kodu yoksa wrapper review'u değiştirmeden döner (no-op identity)."""
    from src.bilun.domain.billing.claim_yatak_icu_overlap import (
        reconcile_yatak_icu_overlap,
    )
    from src.bilun.domain.billing.claim_yatak_puani import (
        recommend_yatak_puani_from_claims,
    )

    # Service-only context: no ICU claim → no ICU last day → nothing to drop.
    srv = _make_claim_header(
        claim_id="SRV",
        admission=date(2026, 7, 13),
        discharge=date(2026, 7, 15),
        department="genel_cerrahi",
    )
    procs = [
        _make_proc_line(
            claim_id="SRV",
            procedure_line_id="SRV-1",
            procedure_code="510010",
            procedure_name="Standart yatak",
            procedure_date=date(2026, 7, 14),
        ),
    ]
    ctx = _make_ctx([srv], procs)

    review = recommend_yatak_puani_from_claims(ctx)
    reconciled = reconcile_yatak_icu_overlap(ctx, review)
    assert reconciled is review
    assert _yatak_opp("SRV", reconciled.opportunities)["bed_days"] == 3

    # Missing-inputs review (no procedure lines) is also returned unchanged.
    empty_ctx = _make_ctx([srv], [])
    empty_review = recommend_yatak_puani_from_claims(empty_ctx)
    assert empty_review.opportunities == []
    assert reconcile_yatak_icu_overlap(empty_ctx, empty_review) is empty_review


def test_patient_report_wires_reconcile() -> None:
    """(a) patient_report'ta YB çıkış günü = servis giriş günü → tek yatak günü.

    Full report: the service claim's expected yatak drops the ICU last day
    (3 → 2) and the ICU claim's own yatak expectation drops it too (4 → 3).
    """
    from src.bilun.domain.billing.patient_report import compute_patient_billing_report

    icu = _make_claim_header(claim_id="ICU")
    srv = _make_claim_header(
        claim_id="SRV",
        admission=date(2026, 7, 13),
        discharge=date(2026, 7, 15),
        department="genel_cerrahi",
    )
    procs = [
        _make_proc_line(claim_id="ICU", procedure_line_id="ICU-1", procedure_code="510090"),
        _make_proc_line(
            claim_id="SRV",
            procedure_line_id="SRV-1",
            procedure_code="510010",
            procedure_name="Standart yatak",
            procedure_date=date(2026, 7, 13),
            billed_amount_try="0.00",
        ),
    ]
    ctx = _make_ctx([icu, srv], procs)

    report = compute_patient_billing_report("P1", claim_context=ctx)

    by_claim = {o["claim_id"]: o for o in report.yatak_puani.opportunities}
    assert by_claim["SRV"]["bed_days"] == 2
    assert by_claim["SRV"]["icu_overlap_days"] == 1
    assert by_claim["ICU"]["bed_days"] == 3
    # Recoverable uplift reflects only the non-overlapped bed days.
    assert report.yatak_puani.confirmed_yatak_try == pytest.approx(
        5 * FIXTURE_BED_DAILY_TRY, abs=0.01
    )
