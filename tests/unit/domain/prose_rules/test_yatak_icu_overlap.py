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
    quantity: int = 1,
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
        quantity=quantity,
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

    # The ICU claim's own yatak expectation: its 510090 line (10 July) pays that day itself, and its 510090 last day
    # (13 July) is dropped by the reconciliation: 4 → 2 (it was 3 while the claim's own lines paid nothing).
    icu_rec = _yatak_opp("ICU", reconciled)
    assert icu_rec["gross_bed_days"] == 4
    assert icu_rec["bed_days"] == 2
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

    # ICU claim: its 510090 line (Jul 10) pays that day itself and its own last day (Jul 12) is dropped by the
    # reconciliation: only Jul 11 is left (it was 2 while the claim's own lines paid nothing).
    icu_rec = _yatak_opp("ICU", reconciled)
    assert icu_rec["gross_bed_days"] == 3
    assert icu_rec["bed_days"] == 1
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
    assert _yatak_opp("C1", opps)["bed_days"] == 3  # the 510090 line (10 July) pays that day itself

    reconciled = reconcile_yatak_bed_days(opps, claims, procs)

    rec = _yatak_opp("C1", reconciled)
    assert rec["bed_days"] == 2  # the ICU last day (13 July) goes on top
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
    assert _yatak_opp("C1", opps)["bed_days"] == 0  # the claim's own 510090 line pays the only day

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
    assert _yatak_opp("ICU", reconciled.opportunities)["bed_days"] == 2  # 10 July: its own 510090 line; 13 July: last day
    assert reconciled.confirmed_yatak_try == pytest.approx(
        4 * FIXTURE_BED_DAILY_TRY, abs=0.01
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
    (3 → 2) and the ICU claim's own yatak expectation drops its last day and the
    day its own 510090 line pays (4 → 2).
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
    assert by_claim["ICU"]["bed_days"] == 2
    # Recoverable uplift reflects only the non-overlapped bed days.
    assert report.yatak_puani.confirmed_yatak_try == pytest.approx(
        4 * FIXTURE_BED_DAILY_TRY, abs=0.01
    )


# --- The ER bed (530000) and hemodialysis also take days: an ICU transfer day they took is dropped once ----------
# (tasks/todo.md, 2026-10-19; 530000 "Yatak, yemek, hasta vizit hizmetlerini kapsar", SUT §2.4.4.D-1.(11))


def _transfer_bill(extra_lines, *, service_discharge: date = date(2026, 7, 15)):
    """ICU claim 10-13 July (510090 on 10 July, ICU last day 13 July) and the service claim 13 July - discharge."""
    icu = _make_claim_header(claim_id="ICU", department="Yogun Bakim")
    srv = _make_claim_header(
        claim_id="SRV", admission=date(2026, 7, 13), discharge=service_discharge, department="genel_cerrahi"
    )
    procs = [
        _make_proc_line(claim_id="ICU", procedure_line_id="ICU-1", procedure_code="510090"),
        _make_proc_line(
            claim_id="SRV", procedure_line_id="SRV-1", procedure_code="510010", procedure_name="Standart yatak",
            procedure_date=date(2026, 7, 13), billed_amount_try="0.00",
        ),
        *extra_lines,
    ]
    return [icu, srv], procs


def _er_line(day: date, *, code: str = "530000", billed: str = "577.45"):
    return _make_proc_line(
        claim_id="SRV", procedure_line_id=f"X-{code}-{day.isoformat()}", procedure_code=code, procedure_date=day,
        billed_amount_try=billed,
    )


def test_reconcile_an_icu_transfer_day_the_er_bed_also_pays_is_dropped_once() -> None:
    from src.bilun.domain.prose_rules.yatak_icu_overlap import reconcile_yatak_bed_days
    from src.bilun.domain.prose_rules.yatak_puani import detect_yatak_puani_opportunities

    claims, procs = _transfer_bill([_er_line(date(2026, 7, 13))])
    opps = detect_yatak_puani_opportunities(claims, procs, claim_ids_with_procs={"ICU", "SRV"})
    assert _yatak_opp("SRV", opps)["bed_days"] == 2  # the detector took 13 July out: 530000 pays that day

    reconciled = reconcile_yatak_bed_days(opps, claims, procs)

    srv_rec = _yatak_opp("SRV", reconciled)
    assert srv_rec["bed_days"] == 2  # not 1: the same day is not taken out a second time
    assert "icu_overlap_days" not in srv_rec and "icu_overlap_dates" not in srv_rec
    assert srv_rec["expected_yatak_try"] == pytest.approx(2 * FIXTURE_BED_DAILY_TRY, abs=0.01)


def test_reconcile_an_er_day_and_a_different_icu_transfer_day_are_both_dropped() -> None:
    from src.bilun.domain.prose_rules.yatak_icu_overlap import reconcile_yatak_bed_days
    from src.bilun.domain.prose_rules.yatak_puani import detect_yatak_puani_opportunities

    claims, procs = _transfer_bill([_er_line(date(2026, 7, 14))])
    opps = detect_yatak_puani_opportunities(claims, procs, claim_ids_with_procs={"ICU", "SRV"})
    assert _yatak_opp("SRV", opps)["bed_days"] == 2  # 13 and 15 July

    reconciled = reconcile_yatak_bed_days(opps, claims, procs)

    srv_rec = _yatak_opp("SRV", reconciled)
    assert srv_rec["bed_days"] == 1  # 15 July
    assert (srv_rec["icu_overlap_days"], srv_rec["icu_overlap_dates"]) == (1, ["2026-07-13"])
    assert srv_rec["expected_yatak_try"] == pytest.approx(FIXTURE_BED_DAILY_TRY, abs=0.01)


def test_reconcile_a_stay_of_one_date_the_dialysis_already_took_has_no_icu_overlap_to_record() -> None:
    """The ICU last day is the only day of a one-date service claim that bills hemodialysis: the day bed is in the
    dialysis price, so the detector expects nothing and the ICU reconciliation has nothing to take."""
    from src.bilun.domain.prose_rules.yatak_icu_overlap import reconcile_yatak_bed_days
    from src.bilun.domain.prose_rules.yatak_puani import detect_yatak_puani_opportunities

    claims, procs = _transfer_bill(
        [_er_line(date(2026, 7, 13), code="704230", billed="4342.48")], service_discharge=date(2026, 7, 13)
    )
    opps = detect_yatak_puani_opportunities(claims, procs, claim_ids_with_procs={"ICU", "SRV"})
    assert _yatak_opp("SRV", opps)["bed_days"] == 0

    srv_rec = _yatak_opp("SRV", reconcile_yatak_bed_days(opps, claims, procs))

    assert srv_rec["bed_days"] == 0
    assert "icu_overlap_days" not in srv_rec


def test_reconcile_the_er_bed_inside_a_package_window_changes_nothing_for_the_icu_day() -> None:
    """A mandated/billed package over the transfer day already bundles it (no double subtraction) and the ER line
    inside the window is a bundled day too: the ICU reconciliation behaves as before."""
    from src.bilun.domain.prose_rules.yatak_icu_overlap import reconcile_yatak_bed_days
    from src.bilun.domain.prose_rules.yatak_puani import detect_yatak_puani_opportunities

    package = _make_proc_line(
        claim_id="SRV", procedure_line_id="PKG", procedure_code="P600040", procedure_category="paket",
        procedure_date=date(2026, 7, 13), billed_amount_try="5000.00",
    )
    claims, procs = _transfer_bill([package, _er_line(date(2026, 7, 14))], service_discharge=date(2026, 7, 25))
    opps = detect_yatak_puani_opportunities(claims, procs, claim_ids_with_procs={"ICU", "SRV"})
    srv = _yatak_opp("SRV", opps)
    assert srv["bundled_days"] == 10  # 13-22 July (group B)

    reconciled = reconcile_yatak_bed_days(opps, claims, procs)

    assert _yatak_opp("SRV", reconciled)["bed_days"] == srv["bed_days"] == 3  # 23-25 July


# --- The ICU claim's own lines pay their days (tasks/todo.md, 2026-10-20) -------------------------------------------
# EK-2/B 510090 "Yemek, yatak, hasta vizit hizmetlerini kapsar"; the EK-2/C ICU packages are EK-2/C points, which include
# "Yatak bedeli" (§2.2.2.B-1.(1).a); §2.4.4.H.(8): the first and the exit day are 510090, the days between the packages.
# The detector takes those days out itself (the shared helper); the reconciliation keeps the claim-span rule for the
# claim's last day and the cross-claim transfer day, and never takes a day the detector took.


def _icu_claim_bill(*lines, discharge: date = date(2026, 7, 12), claim_id: str = "ICU"):
    claim = _make_claim_header(claim_id=claim_id, discharge=discharge, department="Yogun Bakim")
    return [claim], list(lines)


def _icu(code: str, day: date, *, quantity: int = 1, category: str = "islem", line_id: str = "", claim_id: str = "ICU"):
    return _make_proc_line(
        claim_id=claim_id, procedure_line_id=line_id or f"{claim_id}-{code}-{day.isoformat()}", procedure_code=code,
        procedure_date=day, procedure_category=category, quantity=quantity,
    )


def _reconciled(claims, procs, ids=("ICU",)):
    from src.bilun.domain.prose_rules.yatak_icu_overlap import reconcile_yatak_bed_days
    from src.bilun.domain.prose_rules.yatak_puani import detect_yatak_puani_opportunities

    opps = detect_yatak_puani_opportunities(claims, procs, claim_ids_with_procs=set(ids))
    return opps, reconcile_yatak_bed_days(opps, claims, procs)


def test_an_icu_claim_billing_510090_on_every_day_expects_no_standard_bed_day() -> None:
    claims, procs = _icu_claim_bill(_icu("510090", _ICU_ADMISSION, quantity=3), discharge=date(2026, 7, 12))

    opps, reconciled = _reconciled(claims, procs)

    row = _yatak_opp("ICU", opps)
    assert (row["gross_bed_days"], row["bed_days"]) == (3, 0)  # the detector alone: S5 showed 2 days, 444.72
    assert row["expected_yatak_try"] == 0.0 and row["recoverable_uplift_try"] == 0.0
    assert "ICU stay" in row["detail"]
    assert reconciled is opps  # nothing left for the reconciliation to take


def test_an_icu_claim_billing_510090_on_its_first_and_last_day_only_expects_nothing_between() -> None:
    claims, procs = _icu_claim_bill(
        _icu("510090", date(2026, 7, 10)), _icu("510090", date(2026, 7, 12)), discharge=date(2026, 7, 12)
    )

    opps, reconciled = _reconciled(claims, procs)

    assert _yatak_opp("ICU", opps)["bed_days"] == 0
    assert reconciled is opps


def test_an_icu_claim_with_a_package_between_the_day_rate_days_expects_no_standard_bed_day() -> None:
    claims, procs = _icu_claim_bill(
        _icu("510090", date(2026, 7, 10)),
        _icu("P552002", date(2026, 7, 11), category="paket"),
        _icu("510090", date(2026, 7, 12)),
        discharge=date(2026, 7, 12),
    )

    opps, reconciled = _reconciled(claims, procs)

    assert _yatak_opp("ICU", reconciled)["bed_days"] == 0


def test_an_unprefixed_icu_package_pays_its_days_too() -> None:
    """552002 billed as an ordinary procedure opens no package window, so only the lines can place the days."""
    claims, procs = _icu_claim_bill(
        _icu("510090", date(2026, 7, 10)), _icu("552002", date(2026, 7, 11)), _icu("510090", date(2026, 7, 12)),
        discharge=date(2026, 7, 12),
    )

    opps, _ = _reconciled(claims, procs)

    row = _yatak_opp("ICU", opps)
    assert row["surgery_day_bundled"] is False and row["bundled_days"] == 0
    assert row["bed_days"] == 0


def test_the_last_day_of_an_icu_claim_is_taken_out_once_when_its_own_line_pays_it() -> None:
    claims, procs = _icu_claim_bill(
        _icu("510090", date(2026, 7, 10)), _icu("510090", date(2026, 7, 13)), discharge=date(2026, 7, 13)
    )

    opps, reconciled = _reconciled(claims, procs)

    row = _yatak_opp("ICU", reconciled)
    assert (row["gross_bed_days"], row["bed_days"]) == (4, 0)  # not -1 more: 13 July is in the ICU stay, taken once
    assert "icu_overlap_days" not in row and "icu_overlap_dates" not in row
    assert reconciled is opps


def test_a_ward_day_after_the_icu_stay_is_still_the_claim_span_rule() -> None:
    """ICU 10-12 July on a claim that runs to 14 July: 13 July stays expected, the claim's last day (14 July) is dropped
    as before (the pinned claim-span model: it also hides a real ward day, a limit left on purpose)."""
    claims, procs = _icu_claim_bill(
        _icu("510090", date(2026, 7, 10)), _icu("510090", date(2026, 7, 12)), discharge=date(2026, 7, 14)
    )

    opps, reconciled = _reconciled(claims, procs)

    assert _yatak_opp("ICU", opps)["bed_days"] == 2  # 13 and 14 July
    row = _yatak_opp("ICU", reconciled)
    assert row["bed_days"] == 1  # 13 July
    assert (row["icu_overlap_days"], row["icu_overlap_dates"]) == (1, ["2026-07-14"])
    assert row["expected_yatak_try"] == pytest.approx(FIXTURE_BED_DAILY_TRY, abs=0.01)


def test_ward_days_before_the_icu_stay_are_expected() -> None:
    claims, procs = _icu_claim_bill(
        _icu("510090", date(2026, 7, 12)), _icu("510090", date(2026, 7, 13)), discharge=date(2026, 7, 14)
    )

    opps, reconciled = _reconciled(claims, procs)

    # 10 and 11 July (ward), 12-13 July are ICU, 14 July is the claim's last day.
    assert _yatak_opp("ICU", opps)["bed_days"] == 3
    assert _yatak_opp("ICU", reconciled)["bed_days"] == 2


def test_the_service_claim_after_an_icu_claim_keeps_its_transfer_day_keys() -> None:
    icu = _make_claim_header(claim_id="ICU", discharge=date(2026, 7, 12), department="Yogun Bakim")
    srv = _make_claim_header(
        claim_id="SRV", admission=date(2026, 7, 12), discharge=date(2026, 7, 14), department="genel_cerrahi"
    )
    procs = [
        _icu("510090", date(2026, 7, 10)),
        _icu("510090", date(2026, 7, 12)),
        _make_proc_line(
            claim_id="SRV", procedure_line_id="SRV-1", procedure_code="510010", procedure_date=date(2026, 7, 13),
            billed_amount_try="0.00",
        ),
    ]

    opps, reconciled = _reconciled([icu, srv], procs, ids=("ICU", "SRV"))

    assert _yatak_opp("ICU", opps)["bed_days"] == 0
    assert _yatak_opp("SRV", opps)["bed_days"] == 3
    srv_rec = _yatak_opp("SRV", reconciled)
    assert srv_rec["bed_days"] == 2
    assert (srv_rec["icu_overlap_days"], srv_rec["icu_overlap_dates"]) == (1, ["2026-07-12"])
    assert "icu_overlap_days" not in _yatak_opp("ICU", reconciled)


def test_icu_days_after_a_package_window_are_taken_once() -> None:
    """Group C package on 10 July (window 10-17 July); ICU 510090 on 18 and 19 July; the claim runs to 20 July."""
    claim = _make_claim_header(claim_id="C1", discharge=date(2026, 7, 20), department="genel_cerrahi")
    procs = [
        _make_proc_line(
            claim_id="C1", procedure_line_id="PKG", procedure_code="610130", procedure_category="paket",
            procedure_date=date(2026, 7, 10),
        ),
        _icu("510090", date(2026, 7, 18), claim_id="C1"),
        _icu("510090", date(2026, 7, 19), claim_id="C1"),
    ]

    opps, reconciled = _reconciled([claim], procs, ids=("C1",))

    row = _yatak_opp("C1", opps)
    assert (row["gross_bed_days"], row["bundled_days"], row["bed_days"]) == (11, 8, 1)  # 20 July only
    rec = _yatak_opp("C1", reconciled)
    assert rec["bed_days"] == 0  # 20 July is the claim's last day
    assert (rec["icu_overlap_days"], rec["icu_overlap_dates"]) == (1, ["2026-07-20"])


def test_a_reversed_icu_line_leaves_the_claims_days_as_they_were() -> None:
    claims, procs = _icu_claim_bill(
        _make_proc_line(claim_id="ICU", procedure_line_id="R1", procedure_code="510090", billed_amount_try="-742.60"),
        discharge=date(2026, 7, 12),
    )

    opps, reconciled = _reconciled(claims, procs)

    assert _yatak_opp("ICU", opps)["bed_days"] == 3
    assert _yatak_opp("ICU", reconciled)["bed_days"] == 2  # the claim's last day, as before


def test_an_icu_claim_whose_lines_are_billed_beside_standard_bed_lines_is_netted() -> None:
    claims, procs = _icu_claim_bill(
        _icu("510090", _ICU_ADMISSION, quantity=3),
        _make_proc_line(
            claim_id="ICU", procedure_line_id="B1", procedure_code="510010", procedure_name="Standart yatak",
            billed_amount_try="667.08", quantity=3,
        ),
        discharge=date(2026, 7, 12),
    )

    _, reconciled = _reconciled(claims, procs)

    row = _yatak_opp("ICU", reconciled)
    assert row["bed_days"] == 0 and row["expected_yatak_try"] == 0.0
    assert row["actual_billed_try"] == pytest.approx(667.08, abs=0.01)  # billed beside the ICU days: the audit's matter
    assert row["recoverable_uplift_try"] == 0.0


def test_a_day_rate_line_of_quantity_two_is_the_first_and_the_exit_day_not_two_consecutive_days() -> None:
    """The ICU motor reads one 510090 line of quantity 2 on a 10-day claim as two ICU days, first and last
    (``test_icu_puani.py``, ``_infer_billed_icu_days``): the bed motor must not call the eight days between ward days."""
    claims, procs = _icu_claim_bill(
        _make_proc_line(claim_id="ICU", procedure_line_id="Q2", procedure_code="510090", quantity=2),
        discharge=date(2026, 7, 19),
    )

    opps, reconciled = _reconciled(claims, procs)

    row = _yatak_opp("ICU", opps)
    assert (row["gross_bed_days"], row["bed_days"]) == (10, 0)
    assert reconciled is opps


def test_the_reconciliation_and_the_helper_read_the_same_icu_codes() -> None:
    """`collect_icu_last_days` marks a claim as an ICU claim by the code set of the helper (`ICU_BED_CODES`)."""
    from src.bilun.domain.prose_rules.yatak_icu_overlap import collect_icu_last_days
    from src.bilun.domain.prose_rules.yatak_puani import ICU_BED_CODES

    claim = _make_claim_header(claim_id="C1")
    for code in sorted(ICU_BED_CODES):
        for spelled in (code, f"P{code}", f" {code[:3]}.{code[3:]} "):
            line = _make_proc_line(claim_id="C1", procedure_code=spelled)
            assert collect_icu_last_days([claim], [line]) == {_ICU_DISCHARGE}, spelled
    for code in ("510010", "510070", "510081", "510120", "530000", "552004", "552005", "5520020"):
        assert collect_icu_last_days([claim], [_make_proc_line(claim_id="C1", procedure_code=code)]) == set(), code


# --- An ICU day package is no surgical package (WP22) --------------------------------------------------------------
# §2.2.2.B-1.(3) (C000701-C000706) sets a package window by the package's işlem grubu (A 15, B 10, C 8, D 5, E 3 days
# from the procedure date). The EK-2/C ICU packages P552001-3 and P552006-8 have none (the group column is empty): they
# are billed for each ICU day between the first and the exit day (§2.4.4.H.(8)), so they open no window in the bed-day
# logic. Their days are the ICU stay of the claim's own lines (above); the days around the stay are ward days. Read as a
# surgical package (a one-day window of each line, from the admission) they took the ward days before the stay and
# stretched an operation's window to the last ICU day; S11's row said "surgery 2026-06-03, window through 2026-06-05".

_ICU_PACKAGES = ("P552001", "P552002", "P552003", "P552006", "P552007", "P552008")


def _pkg(code: str, day: date, *, claim_id: str = "ICU", category: str = "paket"):
    return _icu(code, day, category=category, claim_id=claim_id)


def _s11_shape(package: str = "P552002", *, package_first: bool = False):
    """S11's shape: 510090 on the first ICU day (10 July), the package on the three days between, 510090 on the exit
    day (14 July), and the claim runs to the transfer day (15 July)."""
    day_rates = [_icu("510090", date(2026, 7, 10)), _icu("510090", date(2026, 7, 14))]
    packages = [_pkg(package, date(2026, 7, d)) for d in (11, 12, 13)]
    return _icu_claim_bill(*(packages + day_rates if package_first else day_rates + packages), discharge=date(2026, 7, 15))


@pytest.mark.parametrize("package", _ICU_PACKAGES)
@pytest.mark.parametrize("spelling", ["as listed", "lower case", "padded", "unprefixed", "prefixed, category islem"])
def test_an_icu_package_opens_no_bed_package_window(package: str, spelling: str) -> None:
    """Any spelling that makes the line a package line (the ``paket`` category or a ``P`` code) opens no window."""
    from src.bilun.domain.prose_rules.yatak_puani import claim_bed_package_window

    code = {
        "as listed": package, "lower case": package.lower(), "padded": f" {package} ", "unprefixed": package[1:],
        "prefixed, category islem": package,
    }[spelling]
    category = "islem" if spelling == "prefixed, category islem" else "paket"
    claims, procs = _icu_claim_bill(
        _icu("510090", date(2026, 7, 10)), _pkg(code, date(2026, 7, 11), category=category),
        _icu("510090", date(2026, 7, 12)),
    )

    assert claim_bed_package_window(claims[0], procs) is None


def test_the_shared_package_window_still_counts_an_icu_package() -> None:
    """Only the bed-day logic leaves the ICU packages out: the unbundling gate reads the shared window, and on an ICU claim
    the companion and the newborn bed motors stop before any window (their own ICU gates)."""
    from src.bilun.domain.prose_rules.yatak_puani import claim_package_window

    claims, procs = _s11_shape()

    window = claim_package_window(claims[0], procs)
    assert (window.start, window.end, window.mandated) == (date(2026, 7, 11), date(2026, 7, 13), False)


@pytest.mark.parametrize("package_first", [False, True])
@pytest.mark.parametrize("package", _ICU_PACKAGES)
def test_s11s_shape_has_no_surgery_window_and_its_icu_days_explain_the_bed(package: str, package_first: bool) -> None:
    claims, procs = _s11_shape(package, package_first=package_first)

    opps, reconciled = _reconciled(claims, procs)

    row = _yatak_opp("ICU", opps)
    assert (row["gross_bed_days"], row["bundled_days"], row["surgery_day_bundled"], row["bed_days"]) == (6, 0, False, 1)
    assert "surgery" not in row["detail"] and "package window" not in row["detail"]
    assert (
        "5 day(s) (2026-07-10, 2026-07-11, 2026-07-12, 2026-07-13, 2026-07-14) lie inside the ICU stay" in row["detail"]
    )
    rec = _yatak_opp("ICU", reconciled)
    assert (rec["bed_days"], rec["expected_yatak_try"], rec["recoverable_uplift_try"]) == (0, 0.0, 0.0)
    assert (rec["icu_overlap_days"], rec["icu_overlap_dates"]) == (1, ["2026-07-15"])  # the transfer day


@pytest.mark.parametrize("package_first", [False, True])
@pytest.mark.parametrize(("ward_billed", "recoverable"), [(False, 2 * FIXTURE_BED_DAILY_TRY), (True, 0.0)])
def test_ward_days_before_an_icu_stay_billed_with_packages_are_expected(
    package_first: bool, ward_billed: bool, recoverable: float
) -> None:
    """Ward 10-11 July, ICU 12 (510090), 13-14 (package), 15 (510090), the claim runs to 16 July: 10 and 11 July are ward
    days (the package took them as its window before); 16 July is the claim's last day."""
    ward = [
        _make_proc_line(
            claim_id="ICU", procedure_line_id=f"W{d}", procedure_code="510010", procedure_name="Standart yatak",
            procedure_date=date(2026, 7, d), billed_amount_try=f"{FIXTURE_BED_DAILY_TRY:.2f}",
        )
        for d in (10, 11)
    ] if ward_billed else []
    packages = [_pkg("P552002", date(2026, 7, 13)), _pkg("P552002", date(2026, 7, 14))]
    day_rates = [_icu("510090", date(2026, 7, 12)), _icu("510090", date(2026, 7, 15))]
    lines = packages + day_rates + ward if package_first else ward + day_rates + packages
    claims, procs = _icu_claim_bill(*lines, discharge=date(2026, 7, 16))

    opps, reconciled = _reconciled(claims, procs)

    row = _yatak_opp("ICU", opps)
    assert (row["gross_bed_days"], row["bundled_days"], row["bed_days"]) == (7, 0, 3)  # 10, 11 and 16 July
    rec = _yatak_opp("ICU", reconciled)
    assert rec["bed_days"] == 2  # 10 and 11 July
    assert rec["expected_yatak_try"] == pytest.approx(2 * FIXTURE_BED_DAILY_TRY, abs=0.01)
    assert rec["recoverable_uplift_try"] == pytest.approx(recoverable, abs=0.01)


@pytest.mark.parametrize("icu_first", [False, True])
def test_icu_packages_do_not_stretch_an_operations_window(icu_first: bool) -> None:
    """Group C package on 10 July (window 10-17 July), ward 18-19 July, ICU 20 (510090), 21-22 (package), 23 (510090),
    the claim runs to 24 July: the window is the operation's, its start is the operation's date whatever the order of
    the lines, and 18 and 19 July are ward days (the ICU packages stretched the window over them before)."""
    from src.bilun.domain.prose_rules.yatak_puani import claim_bed_package_window

    claim = _make_claim_header(claim_id="C1", discharge=date(2026, 7, 24), department="genel_cerrahi")
    operation = [_pkg("610130", date(2026, 7, 10), claim_id="C1")]
    icu = [
        _icu("510090", date(2026, 7, 20), claim_id="C1"),
        _pkg("P552002", date(2026, 7, 21), claim_id="C1"),
        _pkg("P552002", date(2026, 7, 22), claim_id="C1"),
        _icu("510090", date(2026, 7, 23), claim_id="C1"),
    ]
    procs = icu + operation if icu_first else operation + icu

    window = claim_bed_package_window(claim, procs)
    opps, reconciled = _reconciled([claim], procs, ids=("C1",))

    assert (window.start, window.end, window.mandated) == (date(2026, 7, 10), date(2026, 7, 17), False)
    row = _yatak_opp("C1", opps)
    assert (row["gross_bed_days"], row["bundled_days"], row["bed_days"]) == (15, 8, 3)  # 18, 19 and 24 July
    assert "surgery 2026-07-10, window through 2026-07-17" in row["detail"]
    assert _yatak_opp("C1", reconciled)["bed_days"] == 2  # 24 July is the claim's last day


@pytest.mark.parametrize("icu_first", [False, True])
def test_a_mandated_operation_beside_icu_packages_keeps_its_mandated_window(icu_first: bool) -> None:
    """A laparoscopic appendectomy billed hizmet başı must be the group C package P610131 (§2.2.2(1)): its window
    (10-17 July) is mandated. The ICU packages billed after it neither make the claim a billed-package claim nor move
    the window (before: start 19 July, end 20 July, not mandated)."""
    from src.bilun.domain.prose_rules.yatak_puani import claim_bed_package_window

    claim = _make_claim_header(claim_id="C1", discharge=date(2026, 7, 24), department="genel_cerrahi")
    operation = [
        _make_proc_line(
            claim_id="C1", procedure_line_id="OP", procedure_code="610131", procedure_name="Appendektomi, laparoskopik",
            procedure_date=date(2026, 7, 10), billed_amount_try="3000.00",
        )
    ]
    icu = [_pkg("P552002", date(2026, 7, 19), claim_id="C1"), _pkg("P552002", date(2026, 7, 20), claim_id="C1")]
    procs = icu + operation if icu_first else operation + icu

    window = claim_bed_package_window(claim, procs)

    assert (window.start, window.end, window.mandated) == (date(2026, 7, 10), date(2026, 7, 17), True)


def test_the_reconciliation_reads_the_bed_window_of_the_detector() -> None:
    """A readmission: ICU claim A ends on 3 July; claim B starts that day on the ward (3-5 July), returns to the ICU on
    6 July (510090), 7-8 July (package), 9 July (510090) and runs to 10 July. B expects 3, 4, 5 and 10 July; 3 July is
    A's ICU exit day and 10 July B's own last day, so 4 and 5 July are left. Read through a window that the ICU packages
    opened (through 8 July), the reconciliation would keep 3 July, which A's 510090 pays."""
    a = _make_claim_header(
        claim_id="A", admission=date(2026, 7, 1), discharge=date(2026, 7, 3), department="Yogun Bakim"
    )
    b = _make_claim_header(
        claim_id="B", admission=date(2026, 7, 3), discharge=date(2026, 7, 10), department="Yogun Bakim"
    )
    procs = [
        _icu("510090", date(2026, 7, 1), claim_id="A"),
        _icu("510090", date(2026, 7, 3), claim_id="A"),
        _icu("510090", date(2026, 7, 6), claim_id="B"),
        _pkg("P552002", date(2026, 7, 7), claim_id="B"),
        _pkg("P552002", date(2026, 7, 8), claim_id="B"),
        _icu("510090", date(2026, 7, 9), claim_id="B"),
    ]

    opps, reconciled = _reconciled([a, b], procs, ids=("A", "B"))

    assert _yatak_opp("B", opps)["bed_days"] == 4  # 3, 4, 5 and 10 July
    rec = _yatak_opp("B", reconciled)
    assert rec["bed_days"] == 2
    assert (rec["icu_overlap_days"], rec["icu_overlap_dates"]) == (2, ["2026-07-03", "2026-07-10"])
    assert rec["recoverable_uplift_try"] == pytest.approx(2 * FIXTURE_BED_DAILY_TRY, abs=0.01)
