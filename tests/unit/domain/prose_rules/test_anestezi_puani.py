"""Unit tests for anestezi puanı (anesthesia group billing) detector.

Covers the surgical-procedure-puan → anesthesia-group lookup defined in
SUT §2.2.2.A and EK-2/B section "4. ANESTEZİ VE REANİMASYON".

Catalog lookups are stubbed via ``install_anestezi_catalog_stub`` so these
tests do not freeze live gazette prices/katsayı.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest

from src.bilun.domain.billing.claim_anestezi_puani import (
    AnesteziPuaniReview,
    EXACTNESS_STATUS_EXACT,
    EXACTNESS_STATUS_MISSING_INPUTS,
    recommend_anestezi_puani_from_claims,
)
from src.bilun.domain.claims.models import ClaimHeader, ProcedureClaimLine
from src.bilun.domain.claims.patient_context import PatientClaimContext
from src.bilun.domain.prose_rules import anestezi_puani
from src.bilun.domain.prose_rules.anestezi_puani import (
    detect_anestezi_puani_opportunities,
)
from tests.unit._helpers.catalog_stubs import (
    FIXTURE_KATSAYI,
    FIXTURE_PROC_PUAN,
    install_anestezi_catalog_stub,
)

pytestmark = pytest.mark.unit

_A1_GROUP_PUAN = 8942.14
_B_MULTI_GROUP_PUAN = 1863.93
_C_GROUP_PUAN = 894.31
_E_GROUP_PUAN = 372.93


@pytest.fixture(autouse=True)
def _stub_catalog(monkeypatch: pytest.MonkeyPatch) -> None:
    puan_map = {
        **FIXTURE_PROC_PUAN,
        "612070": 303.16,  # Surgical E group (1-1300)
        "610180": 48329.72,  # Surgical A1 group (>= 39001)
        "510010": 374.97,  # Bed code (EK-2B §1 — non-surgical)
        "520030": 195.0,  # Exam code (EK-2B §2 — non-surgical)
        "550170": 894.31,  # Anesthesia C group (EK-2B §4 — non-surgical)
        "L107480": 18.5,  # Lab code (EK-2B §9 — non-surgical)
    }
    install_anestezi_catalog_stub(monkeypatch, puan_by_code=puan_map)
    # These tests pin the EK-2/B §4 group lookup on hizmet başı surgery. 610130,
    # 612070 and 620462 have starred EK-2/C packages that must be billed instead
    # (§2.2.2(1)), whose price includes the anaesthesia (§2.2.2.B-1(1)(g)); that
    # is pinned in tests/unit/domain/billing/test_mandated_package_window.py.
    monkeypatch.setattr(anestezi_puani, "mandated_package_lines", lambda claim, lines: [])


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
        primary_icd10="K35.8",
        package_candidate=False,
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
    procedure_date: date = date(2026, 7, 10),
    billed_amount_try: Decimal = Decimal("1000"),
) -> ProcedureClaimLine:
    return ProcedureClaimLine(
        procedure_line_id=procedure_line_id,
        claim_id=claim_id,
        patient_id="P1",
        episode_id="E1",
        procedure_date=procedure_date,
        procedure_code=procedure_code,
        procedure_name="test procedure",
        procedure_category=procedure_category,
        quantity=1,
        unit_price_try=billed_amount_try,
        billed_amount_try=billed_amount_try,
        expected_payable_try=billed_amount_try,
        is_package_included=False,
        package_code="",
        surcharge_applicable=False,
        copay_rate_applicable=False,
        denial_reason_expected="",
        rule_trace_expected="",
    )


# ── Group resolution cases ───────────────────────────────────────────────────


def test_c_group_appendektomi() -> None:
    """610130 Appendektomi (3,397.78 puan), 2026-07-07 list → group C (550170)."""
    claim = _make_claim_header()
    line = _make_proc_line(procedure_code="610130")
    opps = detect_anestezi_puani_opportunities(
        [claim], [line], claim_ids_with_procs={"C1"}
    )

    assert len(opps) == 1
    opp = opps[0]
    assert opp["anestezi_group"] == "C"
    assert opp["anestezi_code"] == "550170"
    assert opp["anestezi_puan"] == pytest.approx(_C_GROUP_PUAN)
    assert opp["procedure_puan"] == pytest.approx(FIXTURE_PROC_PUAN["610130"], abs=0.01)
    assert opp["expected_try"] == pytest.approx(_C_GROUP_PUAN * FIXTURE_KATSAYI, abs=0.01)
    assert opp["recoverable_uplift_try"] == pytest.approx(
        _C_GROUP_PUAN * FIXTURE_KATSAYI, abs=0.01
    )
    assert opp["rule_id"] == "anestezi_puani_group_lookup"
    assert opp["included_in_sgk_total"] is True
    assert opp["sut_section_id"] == "2.2.2.A"


def test_e_group_low_puan_surgical_procedure() -> None:
    """Low-puan EK-2B §6 surgical procedure (612070, 303.16 puan) → E group (550190)."""
    claim = _make_claim_header()
    line = _make_proc_line(procedure_line_id="PL2", procedure_code="612070")
    opps = detect_anestezi_puani_opportunities(
        [claim], [line], claim_ids_with_procs={"C1"}
    )

    assert len(opps) == 1
    opp = opps[0]
    assert opp["anestezi_group"] == "E"
    assert opp["anestezi_code"] == "550190"
    assert opp["anestezi_puan"] == pytest.approx(_E_GROUP_PUAN)
    assert opp["procedure_puan"] == pytest.approx(303.16, abs=0.01)
    assert opp["expected_try"] == pytest.approx(_E_GROUP_PUAN * FIXTURE_KATSAYI, abs=0.01)


def test_surgical_line_above_5000_puan_emits_row() -> None:
    """Surgical procedures above 5,000 puan yield a row (C for 5,053.36; A1 for 48,329.72)."""
    claim = _make_claim_header()
    line_c = _make_proc_line(procedure_line_id="PL3", procedure_code="620462")
    opps_c = detect_anestezi_puani_opportunities(
        [claim], [line_c], claim_ids_with_procs={"C1"}
    )
    assert len(opps_c) == 1
    assert opps_c[0]["anestezi_group"] == "C"
    assert opps_c[0]["anestezi_code"] == "550170"

    line_a1 = _make_proc_line(procedure_line_id="PL3B", procedure_code="610180")
    opps_a1 = detect_anestezi_puani_opportunities(
        [claim], [line_a1], claim_ids_with_procs={"C1"}
    )
    assert len(opps_a1) == 1
    assert opps_a1[0]["anestezi_group"] == "A1"
    assert opps_a1[0]["anestezi_code"] == "550130"
    assert opps_a1[0]["anestezi_puan"] == pytest.approx(_A1_GROUP_PUAN)


def test_multiple_surgeries_same_session_uses_increased_code() -> None:
    """Multiple surgical lines on the same session emit one 550200-550260 row."""
    claim = _make_claim_header()
    l1 = _make_proc_line(procedure_line_id="PL-S1", procedure_code="610130")
    l2 = _make_proc_line(procedure_line_id="PL-S2", procedure_code="620462")
    opps = detect_anestezi_puani_opportunities(
        [claim], [l1, l2], claim_ids_with_procs={"C1"}
    )
    assert len(opps) == 1
    opp = opps[0]
    # 3397.78 + 5053.36 = 8451.14 → Group B (6001-9000), multi-surgery code 550230
    assert opp["anestezi_group"] == "B"
    assert opp["anestezi_code"] == "550230"
    assert opp["session_procedure_count"] == 2
    assert opp["procedure_puan"] == pytest.approx(8451.14, abs=0.01)
    assert opp["anestezi_puan"] == pytest.approx(_B_MULTI_GROUP_PUAN)


def test_billed_anaesthesia_subtracted_to_zero_recoverable() -> None:
    """Already-billed anaesthesia on the claim reduces recoverable_uplift_try to 0."""
    claim = _make_claim_header()
    surg_line = _make_proc_line(procedure_line_id="PL-SURG", procedure_code="610130")
    anes_line = _make_proc_line(
        procedure_line_id="PL-ANES",
        procedure_code="550170",
        billed_amount_try=Decimal("530.33"),
    )
    opps = detect_anestezi_puani_opportunities(
        [claim], [surg_line, anes_line], claim_ids_with_procs={"C1"}
    )
    assert len(opps) == 1
    assert opps[0]["expected_try"] == pytest.approx(530.33, abs=0.01)
    assert opps[0]["actual_billed_try"] == pytest.approx(530.33, abs=0.01)
    assert opps[0]["recoverable_uplift_try"] == 0.0
    assert opps[0]["included_in_sgk_total"] is False

    ctx = _ctx(claim, surg_line, anes_line)
    review = recommend_anestezi_puani_from_claims(ctx)
    assert review.confirmed_anestezi_try == 0.0


# ── Band-table cutovers (Safa675/Bilun#265) ──────────────────────────────────
# Each EK-2B §4 table starts on the Yürürlük date of its raw-list marker:
# RG 27/07/2022-31905/1-a → 04/08/2022, RG 05/08/2024-32623/10 → 07/08/2024,
# RG 08/04/2026-33218/9-a → 16/04/2026. 615995 puans are the catalog's per date.


@pytest.mark.parametrize(
    ("service_date", "puan", "group", "code"),
    [
        pytest.param(date(2022, 8, 3), 1221.75, "A3", "550150", id="2022-08-03-3000-bands"),
        pytest.param(date(2022, 8, 4), 1221.75, "C", "550170", id="2022-08-04-12001-bands"),
        pytest.param(date(2022, 8, 20), 1221.75, "C", "550170", id="2022-08-20-12001-bands"),
        pytest.param(date(2024, 8, 6), 4260.84, "A3", "550150", id="2024-08-06-12001-bands"),
        pytest.param(date(2024, 8, 7), 4260.84, "C", "550170", id="2024-08-07-32561-bands"),
        pytest.param(date(2026, 4, 15), 5113.0, "B", "550160", id="2026-04-15-32561-bands"),
        pytest.param(date(2026, 4, 16), 5113.0, "C", "550170", id="2026-04-16-39001-bands"),
    ],
)
def test_group_bands_switch_on_the_amendment_yururluk_dates(
    monkeypatch: pytest.MonkeyPatch, service_date: date, puan: float, group: str, code: str
) -> None:
    """615995 on either side of a cutover gets the group of the band table in force that day."""
    install_anestezi_catalog_stub(monkeypatch, puan_by_code={"615995": puan})
    claim = _make_claim_header(admission=service_date, discharge=service_date + timedelta(days=1))
    line = _make_proc_line(procedure_code="615995", procedure_date=service_date)
    opps = detect_anestezi_puani_opportunities([claim], [line], claim_ids_with_procs={"C1"})
    assert [(o["anestezi_group"], o["anestezi_code"]) for o in opps] == [(group, code)]


@pytest.mark.parametrize(
    ("service_date", "puan", "c_group_puan", "billed_try"),
    [
        # Old cutover 2026-07-07 kept the 32561 bands here: B (550160), a false 397.76 TL.
        pytest.param(date(2026, 5, 10), 5113.0, 894.31, Decimal("530.33"), id="2026-05-10"),
        # Old cutover 2026-01-01 kept the 12001 bands here: A3 (550150), a false 1,215.39 TL.
        pytest.param(date(2025, 3, 1), 4260.84, 745.26, Decimal("441.94"), id="2025-03-01"),
    ],
)
def test_group_c_billed_with_615995_yields_no_uplift(
    monkeypatch: pytest.MonkeyPatch,
    service_date: date,
    puan: float,
    c_group_puan: float,
    billed_try: Decimal,
) -> None:
    """615995 billed with 550170 (group C) is complete under the bands in force that day."""
    install_anestezi_catalog_stub(
        monkeypatch, puan_by_code={"615995": puan, "550170": c_group_puan}
    )
    claim = _make_claim_header(admission=service_date, discharge=service_date + timedelta(days=1))
    surgery = _make_proc_line(
        procedure_line_id="PL-SURG", procedure_code="615995", procedure_date=service_date
    )
    anaesthesia = _make_proc_line(
        procedure_line_id="PL-ANES",
        procedure_code="550170",
        procedure_date=service_date,
        billed_amount_try=billed_try,
    )
    opps = detect_anestezi_puani_opportunities(
        [claim], [surgery, anaesthesia], claim_ids_with_procs={"C1"}
    )

    assert len(opps) == 1
    opp = opps[0]
    assert (opp["anestezi_group"], opp["anestezi_code"]) == ("C", "550170")
    assert opp["expected_try"] == pytest.approx(float(billed_try), abs=0.01)
    assert opp["recoverable_uplift_try"] == 0.0
    assert opp["included_in_sgk_total"] is False


# ── Skip cases ───────────────────────────────────────────────────────────────


def test_non_surgical_lab_exam_bed_and_anaesthesia_lines_skipped() -> None:
    """An inpatient bill with only lab, exam, bed, injection, and anaesthesia lines yields no rows."""
    claim = _make_claim_header()
    lines = [
        _make_proc_line(procedure_line_id="PL-LAB", procedure_code="L107480"),
        _make_proc_line(procedure_line_id="PL-EXAM", procedure_code="520030"),
        _make_proc_line(procedure_line_id="PL-BED", procedure_code="510010"),
        _make_proc_line(procedure_line_id="PL-INJ", procedure_code="530390"),
        _make_proc_line(procedure_line_id="PL-ANES", procedure_code="550170"),
    ]
    opps = detect_anestezi_puani_opportunities(
        [claim], lines, claim_ids_with_procs={"C1"}
    )
    assert opps == []


def test_outpatient_skipped() -> None:
    """Outpatient claim → no anesthesia opportunity (anesthesia is inpatient-only)."""
    claim = _make_claim_header(claim_type="ayakta")
    line = _make_proc_line(procedure_code="610130")
    opps = detect_anestezi_puani_opportunities(
        [claim], [line], claim_ids_with_procs={"C1"}
    )
    assert opps == []


def test_package_procedure_skipped() -> None:
    """Paket-category procedure line → bundled, no separate anesthesia opportunity."""
    claim = _make_claim_header()
    line = _make_proc_line(
        procedure_line_id="PL4", procedure_code="610130", procedure_category="paket"
    )
    opps = detect_anestezi_puani_opportunities(
        [claim], [line], claim_ids_with_procs={"C1"}
    )
    assert opps == []


def test_claim_without_procs_filtered() -> None:
    """Claim not in claim_ids_with_procs → skipped."""
    claim = _make_claim_header()
    line = _make_proc_line(procedure_code="610130")
    opps = detect_anestezi_puani_opportunities(
        [claim], [line], claim_ids_with_procs={"OTHER"}
    )
    assert opps == []


def test_unknown_procedure_skipped() -> None:
    """Procedure code not in catalog (no puan) → skip."""
    claim = _make_claim_header()
    line = _make_proc_line(
        procedure_line_id="PL5", procedure_code="619999"
    )
    opps = detect_anestezi_puani_opportunities(
        [claim], [line], claim_ids_with_procs={"C1"}
    )
    assert opps == []


# ── Billing wrapper ──────────────────────────────────────────────────────────


def _ctx(claim: ClaimHeader, *lines: ProcedureClaimLine) -> PatientClaimContext:
    return PatientClaimContext(
        patient_id=claim.patient_id,
        claims=(claim,),
        procedure_lines=tuple(lines),
        material_lines=(),
        drug_lines=(),
        diagnoses=(),
    )


def test_wrapper_missing_inputs_when_no_procedure_lines() -> None:
    """Wrapper returns MISSING_INPUTS when no procedure lines are present."""
    claim = _make_claim_header()
    ctx = PatientClaimContext(
        patient_id=claim.patient_id,
        claims=(claim,),
        procedure_lines=(),
        material_lines=(),
        drug_lines=(),
        diagnoses=(),
    )
    review = recommend_anestezi_puani_from_claims(ctx)
    assert isinstance(review, AnesteziPuaniReview)
    assert review.exactness_status == EXACTNESS_STATUS_MISSING_INPUTS
    assert review.opportunities == []
    assert review.confirmed_anestezi_try == 0.0
    assert review.required_inputs_missing  # non-empty


def test_wrapper_exact_with_appendektomi() -> None:
    """Wrapper with an inpatient appendektomi line → EXACT, one group-C opportunity."""
    claim = _make_claim_header()
    line = _make_proc_line(procedure_code="610130")
    ctx = _ctx(claim, line)
    review = recommend_anestezi_puani_from_claims(ctx)
    assert review.exactness_status == EXACTNESS_STATUS_EXACT
    assert len(review.opportunities) == 1
    assert review.confirmed_anestezi_try == pytest.approx(
        _C_GROUP_PUAN * FIXTURE_KATSAYI, abs=0.01
    )

