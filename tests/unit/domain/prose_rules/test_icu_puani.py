"""Unit tests for ICU (yoğun bakım) puanı dual-charge detector.

Covers the §2.4.4.H dual-charging model:
  - 3-day stay → 510090 (first) + P552003 × 1 intermediate + 510090 (last)
  - 1-day stay → only 510090 once (first=last)
  - 2-day stay → two 510090s, no intermediate
  - outpatient claim → skipped
  - claim with no ICU codes → skipped
  - missing dates → skipped
  - the claim_icu_puani wrapper against a PatientClaimContext
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from tests.unit._helpers.catalog_prices import list_puan, list_text

pytestmark = pytest.mark.unit

# The ICU puans of the list in force on 10 July 2026 (curated catalog histories): the day rate 510090 and the
# intermediate-day packages P552001 (1st basamak) and P552003 (3rd basamak).
_DAY_RATE_PUAN = list_puan("510090", "2026-07-10")
_P552001_PUAN = list_puan("P552001", "2026-07-10")
_P552003_PUAN = list_puan("P552003", "2026-07-10")


def _make_claim_header(
    *,
    claim_id: str = "C1",
    claim_type: str = "yatis",
    admission: date | None = date(2026, 7, 10),
    discharge: date | None = date(2026, 7, 13),
    facility_tier: str = "3_basamak",
):
    from src.bilun.domain.claims.models import ClaimHeader

    return ClaimHeader(
        claim_id=claim_id,
        patient_id="P1",
        episode_id="E1",
        claim_type=claim_type,
        facility_tier=facility_tier,
        provider_type="sozlesmeli",
        department="Yogun Bakim",
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
    quantity: int = 1,
    billed_amount_try: Decimal = Decimal("742.60"),
):
    from src.bilun.domain.claims.models import ProcedureClaimLine

    return ProcedureClaimLine(
        procedure_line_id=procedure_line_id,
        claim_id=claim_id,
        patient_id="P1",
        episode_id="E1",
        procedure_date=date(2026, 7, 10),
        procedure_code=procedure_code,
        procedure_name=procedure_name,
        procedure_category="islem",
        quantity=quantity,
        unit_price_try=Decimal("742.60"),
        billed_amount_try=billed_amount_try,
        expected_payable_try=Decimal("700.00"),
        is_package_included=False,
        package_code="",
        surcharge_applicable=False,
        copay_rate_applicable=False,
        denial_reason_expected="",
        rule_trace_expected="",
    )


# ── Detector tests ─────────────────────────────────────────────────────────


def test_3day_icu_stay_dual_charge() -> None:
    """3-day ICU stay → 510090 (first) + P552003 × 1 intermediate + 510090 (last)."""
    from src.bilun.domain.prose_rules.icu_puani import detect_icu_puani_opportunities

    header = _make_claim_header(admission=date(2026, 7, 10), discharge=date(2026, 7, 13))
    procs = [
        _make_proc_line(procedure_code="510090"),
        _make_proc_line(
            procedure_line_id="ISL-2", procedure_code="P552003",
            procedure_name="Ucuncu basamak yogun bakim",
        ),
    ]
    opps = detect_icu_puani_opportunities(
        [header], procs, claim_ids_with_procs={"C1"}
    )

    assert len(opps) == 1
    opp = opps[0]
    assert opp["icu_days"] == 3
    assert opp["intermediate_days"] == 1
    assert opp["first_day_code"] == "510090"
    assert opp["last_day_code"] == "510090"
    assert opp["intermediate_package"] == "P552003"
    assert opp["same_day_stay"] is False
    assert opp["rule_id"] == "icu_puani_510090_p55200x"
    assert opp["sut_section_id"] == "2.4.4.H"
    assert opp["included_in_sgk_total"] is True

    # Puan: 2 × 510090 (first+last) + 1 × P552003 (intermediate) × 2.0
    # (EK-2/C-1 ilave oran +100% for Sınıf-3 facility)
    assert opp["total_puan"] == pytest.approx(2 * _DAY_RATE_PUAN + 2.0 * _P552003_PUAN, abs=0.01)
    # recoverable uplift = total TRY minus actual billed ICU amounts.
    # The fixture bills 510090 (742.60) + P552003 (742.60) = 1485.20 already.
    assert opp["actual_billed_try"] == pytest.approx(1485.20, abs=0.01)
    assert opp["recoverable_uplift_try"] == pytest.approx(
        opp["total_try"] - opp["actual_billed_try"], abs=0.01
    )
    assert opp["total_try"] > 0.0


def test_1day_icu_stay_single_day_rate() -> None:
    """1-day ICU stay (same-day admit/discharge) → only 510090 once."""
    from src.bilun.domain.prose_rules.icu_puani import detect_icu_puani_opportunities

    header = _make_claim_header(
        admission=date(2026, 7, 10), discharge=date(2026, 7, 10)
    )
    procs = [_make_proc_line(procedure_code="510090")]
    opps = detect_icu_puani_opportunities(
        [header], procs, claim_ids_with_procs={"C1"}
    )

    assert len(opps) == 1
    opp = opps[0]
    assert opp["icu_days"] == 1
    assert opp["intermediate_days"] == 0
    assert opp["same_day_stay"] is True
    # Only one 510090 day (first=last).
    assert opp["total_puan"] == pytest.approx(_DAY_RATE_PUAN, abs=0.01)


def test_2day_icu_stay_two_day_rates_no_intermediate() -> None:
    """2-day ICU stay → two 510090s (first + last), no intermediate package.

    Per §2.4.4.H.(8), ICU days = ``(discharge - admission).days``. A 2-day
    stay (admit Jul 10 → discharge Jul 12) yields 2 ICU days: first day
    (510090) + last day (510090), with zero intermediate (ara) days.
    """
    from src.bilun.domain.prose_rules.icu_puani import detect_icu_puani_opportunities

    header = _make_claim_header(admission=date(2026, 7, 10), discharge=date(2026, 7, 12))
    procs = [_make_proc_line(procedure_code="510090")]
    opps = detect_icu_puani_opportunities(
        [header], procs, claim_ids_with_procs={"C1"}
    )

    assert len(opps) == 1
    opp = opps[0]
    assert opp["icu_days"] == 2
    assert opp["intermediate_days"] == 0
    assert opp["total_puan"] == pytest.approx(2 * _DAY_RATE_PUAN, abs=0.01)


def test_outpatient_claim_skipped() -> None:
    """Outpatient claim → no opportunity."""
    from src.bilun.domain.prose_rules.icu_puani import detect_icu_puani_opportunities

    header = _make_claim_header(claim_type="ayakta")
    procs = [_make_proc_line(procedure_code="510090")]
    opps = detect_icu_puani_opportunities(
        [header], procs, claim_ids_with_procs={"C1"}
    )
    assert opps == []


def test_no_icu_codes_skipped() -> None:
    """Inpatient claim with no ICU indicator codes → no opportunity."""
    from src.bilun.domain.prose_rules.icu_puani import detect_icu_puani_opportunities

    header = _make_claim_header()
    # Only a generic procedure line — no 510090 / P55200x.
    procs = [_make_proc_line(procedure_code="510010", procedure_name="Standart yatak")]
    opps = detect_icu_puani_opportunities(
        [header], procs, claim_ids_with_procs={"C1"}
    )
    assert opps == []


def test_missing_dates_skipped() -> None:
    """Null admission or discharge → honest skip, no opportunity."""
    from src.bilun.domain.prose_rules.icu_puani import detect_icu_puani_opportunities

    procs = [_make_proc_line(procedure_code="510090")]

    header_no_admit = _make_claim_header(admission=None, discharge=date(2026, 7, 13))
    assert (
        detect_icu_puani_opportunities(
            [header_no_admit], procs, claim_ids_with_procs={"C1"}
        )
        == []
    )

    header_no_discharge = _make_claim_header(admission=date(2026, 7, 10), discharge=None)
    assert (
        detect_icu_puani_opportunities(
            [header_no_discharge], procs, claim_ids_with_procs={"C1"}
        )
        == []
    )


def test_no_procedure_lines_skipped() -> None:
    """No procedure lines at all → ICU presence cannot be confirmed → skip."""
    from src.bilun.domain.prose_rules.icu_puani import detect_icu_puani_opportunities

    header = _make_claim_header()
    assert detect_icu_puani_opportunities([header], None) == []
    assert detect_icu_puani_opportunities([header], []) == []


def test_claim_not_in_filter_skipped() -> None:
    """Claim not in claim_ids_with_procs → skipped."""
    from src.bilun.domain.prose_rules.icu_puani import detect_icu_puani_opportunities

    header = _make_claim_header()
    procs = [_make_proc_line(procedure_code="510090")]
    opps = detect_icu_puani_opportunities([header], procs, claim_ids_with_procs={"OTHER"})
    assert opps == []


def test_basamak_inferred_from_submitted_package() -> None:
    """A claim carrying P552001 (1st basamak) uses that puan, not the default 3rd."""
    from src.bilun.domain.prose_rules.icu_puani import detect_icu_puani_opportunities

    header = _make_claim_header(admission=date(2026, 7, 10), discharge=date(2026, 7, 14))
    procs = [
        _make_proc_line(procedure_code="510090"),
        _make_proc_line(
            procedure_line_id="ISL-2",
            procedure_code="P552001",
            procedure_name="Birinci basamak yogun bakim",
            quantity=2,
        ),
    ]
    opps = detect_icu_puani_opportunities(
        [header], procs, claim_ids_with_procs={"C1"}
    )
    opp = opps[0]
    # 4-day stay → 2 first/last + 2 intermediate (P552001).
    assert opp["icu_days"] == 4
    assert opp["intermediate_days"] == 2
    assert opp["intermediate_package"] == "P552001"
    # 2 × 510090 + 2 × P552001 × 2.0 (ilave oran +100% Sınıf-3)
    assert opp["total_puan"] == pytest.approx(2 * _DAY_RATE_PUAN + 2 * _P552001_PUAN * 2.0, abs=0.01)


# ── EK-2/C-1 ilave oran tests ──────────────────────────────────────────────


def test_ilave_oran_applied_sinif_3() -> None:
    """Sınıf-3 facility → +100% ilave oran on intermediate days (×2.0)."""
    from src.bilun.domain.prose_rules.icu_puani import detect_icu_puani_opportunities

    header = _make_claim_header(
        admission=date(2026, 7, 10),
        discharge=date(2026, 7, 13),
        facility_tier="3_basamak",
    )
    procs = [
        _make_proc_line(procedure_code="510090"),
        _make_proc_line(
            procedure_line_id="ISL-2", procedure_code="P552003",
            procedure_name="Ucuncu basamak yogun bakim",
        ),
    ]
    opps = detect_icu_puani_opportunities(
        [header], procs, claim_ids_with_procs={"C1"}
    )
    opp = opps[0]

    # The uplift is applied + correctly recorded.
    assert opp["ilave_oran_pct"] == pytest.approx(100.0)
    assert opp["ilave_oran_eligible"] is True
    assert opp["ilave_oran_reason"] == "sinif_3_uplift_applied"
    assert opp["intermediate_puan_uplifted"] == pytest.approx(
        opp["intermediate_puan_base"] * 2.0
    )
    # Base puan is the raw EK-2C value; uplifted is doubled.
    assert opp["intermediate_puan_base"] == pytest.approx(_P552003_PUAN, abs=0.01)
    assert opp["intermediate_puan_uplifted"] == pytest.approx(2 * _P552003_PUAN, abs=0.01)


def test_no_uplift_2nd_basamak() -> None:
    """2nd-basamak facility → no uplift (oran=0), totals stay at base."""
    from src.bilun.domain.prose_rules.icu_puani import detect_icu_puani_opportunities

    header = _make_claim_header(
        admission=date(2026, 7, 10),
        discharge=date(2026, 7, 13),
        facility_tier="2_basamak_kamu",
    )
    procs = [
        _make_proc_line(procedure_code="510090"),
        _make_proc_line(
            procedure_line_id="ISL-2", procedure_code="P552003",
            procedure_name="Ucuncu basamak yogun bakim",
        ),
    ]
    opps = detect_icu_puani_opportunities(
        [header], procs, claim_ids_with_procs={"C1"}
    )
    opp = opps[0]

    assert opp["ilave_oran_pct"] == pytest.approx(0.0)
    assert opp["ilave_oran_eligible"] is False
    assert opp["ilave_oran_reason"] == "not_sinif_3"
    # No uplift → base == uplifted.
    assert opp["intermediate_puan_uplifted"] == pytest.approx(
        opp["intermediate_puan_base"]
    )
    # Puan at base (no ×2.0): 2 × 510090 + 1 × P552003
    assert opp["total_puan"] == pytest.approx(2 * _DAY_RATE_PUAN + _P552003_PUAN, abs=0.01)


def test_no_uplift_unresolved_tier() -> None:
    """Unresolved facility tier → honest skip (oran=0), reason recorded."""
    from src.bilun.domain.prose_rules.icu_puani import detect_icu_puani_opportunities

    header = _make_claim_header(
        admission=date(2026, 7, 10),
        discharge=date(2026, 7, 13),
        facility_tier="devlet",  # not in _EXPLICIT_TIER_MAP → unresolved
    )
    procs = [
        _make_proc_line(procedure_code="510090"),
        _make_proc_line(
            procedure_line_id="ISL-2", procedure_code="P552003",
            procedure_name="Ucuncu basamak yogun bakim",
        ),
    ]
    opps = detect_icu_puani_opportunities(
        [header], procs, claim_ids_with_procs={"C1"}
    )
    opp = opps[0]

    assert opp["ilave_oran_pct"] == pytest.approx(0.0)
    assert opp["ilave_oran_eligible"] is False
    assert opp["ilave_oran_reason"] == "tier_unresolved"
    assert opp["intermediate_puan_uplifted"] == pytest.approx(
        opp["intermediate_puan_base"]
    )
    # Puan at base (no uplift).
    assert opp["total_puan"] == pytest.approx(2 * _DAY_RATE_PUAN + _P552003_PUAN, abs=0.01)


# ── Wrapper test ───────────────────────────────────────────────────────────


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


def test_wrapper_3day_stay() -> None:
    """recommend_icu_puani_from_claims emits the dual-charge opportunity."""
    from src.bilun.domain.billing.claim_icu_puani import (
        recommend_icu_puani_from_claims,
    )

    header = _make_claim_header(admission=date(2026, 7, 10), discharge=date(2026, 7, 13))
    procs = [
        _make_proc_line(procedure_code="510090"),
        _make_proc_line(
            procedure_line_id="ISL-2", procedure_code="P552003",
            procedure_name="Ucuncu basamak yogun bakim",
        ),
    ]
    ctx = _make_ctx([header], procs)

    review = recommend_icu_puani_from_claims(ctx)
    assert review.exactness_status == "exact"
    assert review.unavailable_reason is None
    assert len(review.opportunities) == 1
    opp = review.opportunities[0]
    assert opp["icu_days"] == 3
    assert opp["intermediate_days"] == 1
    # confirmed_icu_try aggregates recoverable_uplift_try (net of actuals) of in-scope opportunities.
    assert review.confirmed_icu_try == pytest.approx(opp["recoverable_uplift_try"], abs=0.01)
    assert review.confirmed_icu_try > 0.0


def test_wrapper_no_procedure_lines_returns_missing_inputs() -> None:
    """Empty procedure_lines → missing-inputs review, no opportunities."""
    from src.bilun.domain.billing.claim_icu_puani import (
        recommend_icu_puani_from_claims,
    )

    header = _make_claim_header()
    ctx = _make_ctx([header], [])
    review = recommend_icu_puani_from_claims(ctx)

    assert review.exactness_status == "missing_exact_inputs"
    assert review.unavailable_reason is not None
    assert review.opportunities == []
    assert review.required_inputs_missing  # non-empty
    assert review.confirmed_icu_try == 0.0


# ── Issue #242: ICU segment day-counting & §2.4.4.H tier overbilling ───────


def test_ward_stay_with_3day_icu_segment_does_not_count_14_hospital_days() -> None:
    """A 14-day ward stay with 3 billed ICU nights (510090 + P552001 + 510090) counts 3 ICU days, not 14."""
    from src.bilun.domain.prose_rules.icu_puani import detect_icu_puani_opportunities

    header = _make_claim_header(
        admission=date(2026, 7, 1),
        discharge=date(2026, 7, 15),
        facility_tier="2_basamak_kamu",
    )
    procs = [
        # Each ICU line billed at its list price on the admission day.
        _make_proc_line(
            procedure_line_id="ISL-1", procedure_code="510090",
            billed_amount_try=Decimal(list_text("510090", "2026-07-01")),
        ),
        _make_proc_line(
            procedure_line_id="ISL-2",
            procedure_code="P552001",
            procedure_name="Birinci basamak yogun bakim",
            billed_amount_try=Decimal(list_text("P552001", "2026-07-01")),
        ),
        _make_proc_line(
            procedure_line_id="ISL-3", procedure_code="510090",
            billed_amount_try=Decimal(list_text("510090", "2026-07-01")),
        ),
    ]
    opps = detect_icu_puani_opportunities(
        [header], procs, claim_ids_with_procs={"C1"}
    )
    assert len(opps) == 1
    opp = opps[0]
    assert opp["icu_days"] == 3
    assert opp["intermediate_days"] == 1
    assert opp["recoverable_uplift_try"] == pytest.approx(0.0, abs=0.05)


def test_no_default_p552003_when_only_510090_billed() -> None:
    """When only 510090 is billed (no P55200x package), never default to 3rd-level P552003."""
    from src.bilun.domain.prose_rules.icu_puani import detect_icu_puani_opportunities

    header = _make_claim_header(
        admission=date(2026, 7, 1),
        discharge=date(2026, 7, 10),
    )
    procs = [_make_proc_line(procedure_code="510090", quantity=2)]
    opps = detect_icu_puani_opportunities(
        [header], procs, claim_ids_with_procs={"C1"}
    )
    assert len(opps) == 1
    opp = opps[0]
    assert opp["icu_days"] == 2
    assert opp["intermediate_days"] == 0
    assert opp["intermediate_package"] is None


def test_tier_overbilling_detected_when_p552003_lacks_3rd_level_support() -> None:
    """#255: P552003 without separately billed §2.4.4.H.(2)/(4) support emits a 0-TL info review."""
    from src.bilun.domain.prose_rules.icu_puani import detect_icu_tier_overbilling

    header = _make_claim_header(
        admission=date(2026, 7, 10),
        discharge=date(2026, 7, 13),
        facility_tier="2_basamak_kamu",
    )
    procs = [
        _make_proc_line(procedure_line_id="ISL-1", procedure_code="510090"),
        _make_proc_line(
            procedure_line_id="ISL-2",
            procedure_code="P552003",
            procedure_name="Ucuncu basamak yogun bakim",
            billed_amount_try=Decimal("7647.44"),
        ),
    ]
    findings = detect_icu_tier_overbilling(
        [header], procs, claim_ids_with_procs={"C1"}
    )
    assert len(findings) == 1
    f = findings[0]
    assert f["rule_id"] == "icu_tier_overbilling_2_4_4_H"
    assert f["sut_section_id"] == "2.4.4.H"
    assert f["severity"] == "info"
    assert f["procedure_code"] == "P552003"
    assert f["recommended_tier_2_code"] == "P552002"
    assert f["recommended_tier_1_code"] == "P552001"
    assert f["price_gap_to_tier_2_try"] > 0.0
    assert f["price_gap_to_tier_1_try"] > f["price_gap_to_tier_2_try"]
    assert f["at_risk_try"] == 0.0
    assert f["savings_try"] == 0.0
    assert f["risk_amount"] == 0.0
    assert f["included_in_sgk_total"] is False
    assert f["savings_category"] == "audit_exposure"
    assert "EK-2/C-A" not in f["detail"]
    assert "2.4.4.H" in f["detail"]


def test_tier_overbilling_not_emitted_when_ecmo_or_dialysis_present() -> None:
    """#255: P552003 with separately billable §2.4.4.H.(2)/(4) items (ECMO A3, haemodialysis, haemofiltration) clears."""
    from src.bilun.domain.prose_rules.icu_puani import detect_icu_tier_overbilling

    header = _make_claim_header(
        admission=date(2026, 7, 10),
        discharge=date(2026, 7, 13),
    )
    for support_code, support_name in (
        ("605977", "Perkütan (Veno-venöz) VV-ECMO takılması veya çıkartılması"),
        ("704230", "Hemodiyaliz"),
        ("704290", "Sürekli hemodiafiltrasyon/hemofiltrasyon tedavisi"),
        ("704920", "Aferez, Terapötik plazma değişimi (1 seans)"),
    ):
        procs = [
            _make_proc_line(procedure_line_id="ISL-1", procedure_code="510090"),
            _make_proc_line(
                procedure_line_id="ISL-2",
                procedure_code="P552003",
                procedure_name="Ucuncu basamak yogun bakim",
            ),
            _make_proc_line(
                procedure_line_id="ISL-3",
                procedure_code=support_code,
                procedure_name=support_name,
            ),
        ]
        assert (
            detect_icu_tier_overbilling(
                [header], procs, claim_ids_with_procs={"C1"}
            )
            == []
        )

