"""Unit tests for the traffic-accident SGK payment-pathway detector.

Covers :mod:`src.bilun.domain.prose_rules.traffic_accident_billing`, which
encodes Algoritma Rehberi §2-09 / 2918 Sayılı Karayolları Trafik Kanunu
Madde 98: traffic-accident treatment is always billed to SGK under provizyon
tipi ``trafik kazası`` (account 120.05.01.04) and is patient-pay-exempt.

Cases exercised:
- Copay/surcharge on a traffic-accident claim → copay violation.
- Traffic claim explicitly classified → no wrong-pathway finding.
- Traffic claim detected only via V-code diagnosis → wrong-pathway finding.
- Non-traffic claim → no findings at all.
- V-code diagnosis detection (transport accident ICD-10 block).
- Non-traffic ICD-10 → not detected as traffic.
- Aggregate wrapper returns both finding classes when applicable.
- ``claim_ids_with_procs`` gate filters claims correctly.
- Header classification reads explicit values only (#268): a work accident
  (``is_kazasi``) is not traffic, and ``scenario_tag`` is never read.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date
from decimal import Decimal

import pytest

from src.bilun.domain.claims.models import ClaimHeader, ProcedureClaimLine
from src.bilun.domain.prose_rules.claim_utils import claim_is_traffic_accident
from src.bilun.domain.prose_rules.traffic_accident_billing import (
    detect_traffic_accident_billing,
    detect_traffic_accident_copay,
    detect_traffic_accident_wrong_pathway,
)

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Construction helpers (mirror the pattern in test_common_billing_errors.py).
# ---------------------------------------------------------------------------


def _make_claim_header(
    *,
    claim_id: str = "C1",
    patient_id: str = "P1",
    episode_id: str = "E1",
    claim_type: str = "yatis",
    admission: date | None = date(2026, 7, 10),
    discharge: date | None = date(2026, 7, 13),
    primary_icd10: str = "K35.8",
    department: str = "genel",
    scenario_tag: str = "test",
    occupational_context: str = "none",
) -> ClaimHeader:
    return ClaimHeader(
        claim_id=claim_id,
        patient_id=patient_id,
        episode_id=episode_id,
        claim_type=claim_type,
        facility_tier="devlet",
        provider_type="sozlesmeli",
        department=department,
        admission_date=admission,
        discharge_date=discharge,
        claim_start_date=admission or date.today(),
        claim_end_date=discharge or date.today(),
        primary_icd10=primary_icd10,
        package_candidate=False,
        expected_total_billed_try=Decimal("1000"),
        expected_total_payable_try=Decimal("900"),
        expected_denial_reason="",
        scenario_tag=scenario_tag,
        occupational_context=occupational_context,
    )


def _make_proc_line(
    *,
    procedure_line_id: str = "PL1",
    claim_id: str = "C1",
    procedure_code: str = "401010",
    procedure_category: str = "muayene",
    procedure_date: date = date(2026, 7, 10),
    procedure_specialty_code: str = "1000",
    quantity: int = 1,
    copay_rate_applicable: bool = False,
    surcharge_applicable: bool = False,
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
        quantity=quantity,
        unit_price_try=Decimal("1000"),
        billed_amount_try=Decimal("1000"),
        expected_payable_try=Decimal("1000"),
        is_package_included=False,
        package_code="",
        surcharge_applicable=surcharge_applicable,
        copay_rate_applicable=copay_rate_applicable,
        denial_reason_expected="",
        rule_trace_expected="",
        procedure_specialty_code=procedure_specialty_code,
    )


# ===========================================================================
# detect_traffic_accident_copay
# ===========================================================================


def test_copay_on_traffic_accident_claim_is_violation() -> None:
    """Traffic claim + copay-eligible line → copay violation."""
    claim = _make_claim_header(
        claim_id="C1",
        primary_icd10="S72.0",  # femur fracture, plausible trauma
        scenario_tag="trafik_kazasi",
        occupational_context="traffic_accident",
    )
    line = _make_proc_line(
        procedure_line_id="PL1",
        claim_id="C1",
        procedure_code="401010",
        copay_rate_applicable=True,
    )

    violations = detect_traffic_accident_copay([claim], [line])

    assert len(violations) == 1
    v = violations[0]
    assert v["claim_id"] == "C1"
    assert v["rule_id"] == "trafik_kazasi_copay_charged"
    assert v["severity"] == "error"
    assert v["savings_category"] == "patient_copay_waiver"
    assert v["sut_section_id"] == "algoritma_2_09"
    assert v["procedure_code"] == "401010"
    assert v["copay_rate_applicable"] is True
    assert v["surcharge_applicable"] is False
    # Copay finding carries no pathway keys (those are wrong-pathway only).
    assert "expected_provision_type" not in v
    assert "expected_account_code" not in v
    # Detail cites the rule, not the account code.
    assert "trafik kazası" in v["detail"].lower()
    assert "2918" in v["detail"]


def test_surcharge_on_traffic_accident_claim_is_violation() -> None:
    """Surcharge (fark ücreti) on a traffic claim is also prohibited."""
    claim = _make_claim_header(
        claim_id="C2",
        primary_icd10="V89.9",
        occupational_context="trafik kazasi",
    )
    line = _make_proc_line(
        procedure_line_id="PL2",
        claim_id="C2",
        surcharge_applicable=True,
    )

    violations = detect_traffic_accident_copay([claim], [line])

    assert len(violations) == 1
    v = violations[0]
    assert v["rule_id"] == "trafik_kazasi_copay_charged"
    assert v["surcharge_applicable"] is True
    assert v["copay_rate_applicable"] is False


def test_no_copay_on_traffic_accident_claim_no_violation() -> None:
    """Traffic claim with copay-exempt lines → no copay finding."""
    claim = _make_claim_header(
        claim_id="C1",
        occupational_context="trafik_kazasi",
    )
    line = _make_proc_line(
        claim_id="C1",
        copay_rate_applicable=False,
        surcharge_applicable=False,
    )

    violations = detect_traffic_accident_copay([claim], [line])

    assert violations == []


# ===========================================================================
# detect_traffic_accident_wrong_pathway
# ===========================================================================


def test_traffic_claim_explicitly_classified_no_pathway_violation() -> None:
    """Claim carrying an explicit traffic marker → no wrong-pathway finding."""
    claim = _make_claim_header(
        claim_id="C1",
        primary_icd10="V89.9",
        scenario_tag="trafik_kazasi",
        occupational_context="traffic_accident",
    )

    violations = detect_traffic_accident_wrong_pathway([claim])

    assert violations == []


def test_v_code_diagnosis_detected_as_traffic_flags_pathway() -> None:
    """V-code (transport accident) diagnosis + no traffic marker → pathway error.

    The claim is a traffic accident by ICD-10 but was not classified as one,
    signalling it was likely billed via the normal SGK provision.
    """
    claim = _make_claim_header(
        claim_id="C1",
        primary_icd10="V89.9",  # unspecified motor vehicle accident injury
        scenario_tag="acil",
        occupational_context="none",
    )

    violations = detect_traffic_accident_wrong_pathway([claim])

    assert len(violations) == 1
    v = violations[0]
    assert v["claim_id"] == "C1"
    assert v["rule_id"] == "trafik_kazasi_wrong_pathway"
    assert v["severity"] == "error"
    assert v["savings_category"] == "compliance_adjustment"
    assert v["sut_section_id"] == "algoritma_2_09"
    assert v["expected_provision_type"] == "trafik kazasi"
    assert v["expected_account_code"] == "120.05.01.04"
    assert v["evidence_source"] == "diagnosis"
    assert v["primary_icd10"] == "V89.9"
    assert "2918" in v["rule_reference"]


def test_v_code_with_subcategory_detected() -> None:
    """Sub-categorised V codes (V01.1, V23.4) are also traffic accidents."""
    claim = _make_claim_header(
        claim_id="C1",
        primary_icd10="V23.4",
        scenario_tag="general",
    )

    violations = detect_traffic_accident_wrong_pathway([claim])

    assert len(violations) == 1
    assert violations[0]["rule_id"] == "trafik_kazasi_wrong_pathway"


# ===========================================================================
# Non-traffic detection
# ===========================================================================


def test_non_traffic_claim_no_violation() -> None:
    """Ordinary clinical claim with no traffic signal → no findings."""
    claim = _make_claim_header(
        claim_id="C1",
        primary_icd10="K35.8",  # appendicitis
        scenario_tag="acil",
        occupational_context="none",
    )
    line = _make_proc_line(claim_id="C1", copay_rate_applicable=True)

    assert detect_traffic_accident_wrong_pathway([claim]) == []
    assert detect_traffic_accident_copay([claim], [line]) == []
    assert detect_traffic_accident_billing([claim], [line]) == []


def test_non_traffic_icd10_not_detected() -> None:
    """S/T/K codes are never traffic accidents regardless of context."""
    for code in ("S72.0", "T14.0", "K35.8", "I21.9", "J00"):
        claim = _make_claim_header(
            claim_id="C1",
            primary_icd10=code,
            scenario_tag="general",
            occupational_context="none",
        )
        assert detect_traffic_accident_wrong_pathway([claim]) == [], (
            f"{code} should not be flagged as traffic"
        )


# ===========================================================================
# Aggregate wrapper
# ===========================================================================


def test_aggregate_returns_both_findings() -> None:
    """A mis-routed traffic claim with a copay line yields both findings.

    The claim is a transport accident (V-code) without an explicit traffic
    marker (wrong pathway) AND carries a copay-eligible line (copay violation).
    """
    claim = _make_claim_header(
        claim_id="C1",
        primary_icd10="V89.9",
        scenario_tag="acil",
        occupational_context="none",
    )
    line = _make_proc_line(claim_id="C1", copay_rate_applicable=True)

    violations = detect_traffic_accident_billing([claim], [line])

    rule_ids = {v["rule_id"] for v in violations}
    assert rule_ids == {
        "trafik_kazasi_wrong_pathway",
        "trafik_kazasi_copay_charged",
    }
    # Wrong-pathway findings come first (deterministic ordering).
    assert violations[0]["rule_id"] == "trafik_kazasi_wrong_pathway"


def test_aggregate_empty_when_no_traffic() -> None:
    """Aggregate returns nothing on a non-traffic episode."""
    claim = _make_claim_header(claim_id="C1", primary_icd10="K35.8")
    line = _make_proc_line(claim_id="C1", copay_rate_applicable=True)

    assert detect_traffic_accident_billing([claim], [line]) == []


# ===========================================================================
# Filter gate
# ===========================================================================


def test_claim_ids_with_procs_gate_filters_claims() -> None:
    """The wiring gate skips traffic claims not in the filter set."""
    claim = _make_claim_header(
        claim_id="C1",
        primary_icd10="V89.9",
        scenario_tag="acil",
    )
    line = _make_proc_line(claim_id="C1", copay_rate_applicable=True)

    violations = detect_traffic_accident_billing(
        [claim],
        [line],
        claim_ids_with_procs={"C_OTHER"},
    )

    assert violations == []


def test_claim_ids_with_procs_gate_includes_claim() -> None:
    """Claims in the filter set are evaluated normally."""
    claim = _make_claim_header(
        claim_id="C1",
        primary_icd10="V89.9",
        scenario_tag="acil",
    )
    line = _make_proc_line(claim_id="C1", copay_rate_applicable=True)

    violations = detect_traffic_accident_billing(
        [claim],
        [line],
        claim_ids_with_procs={"C1"},
    )

    assert len(violations) == 2


# ===========================================================================
# Header classification: explicit values only (#268)
# ===========================================================================

# Every header field the old substring check read.
_HEADER_FIELDS = ("occupational_context", "claim_type", "department", "scenario_tag")


def _hbo_claim_and_copay_line(**header: str) -> tuple[ClaimHeader, ProcedureClaimLine]:
    """The #268 claim: inpatient HBO (P702590) for decompression sickness."""
    claim = replace(_make_claim_header(primary_icd10="T70.3"), **header)
    line = _make_proc_line(
        procedure_code="P702590",
        procedure_category="hyperbaric_oxygen",
        copay_rate_applicable=True,
    )
    return claim, line


@pytest.mark.parametrize("field", _HEADER_FIELDS)
@pytest.mark.parametrize("value", ["is_kazasi", "iş kazası", "is kazasi", "İŞ KAZASI"])
def test_work_accident_is_not_traffic(field: str, value: str) -> None:
    """A work accident contains "kaza" but is not a traffic accident: no
    pathway finding and no ``trafik_kazasi_copay_charged`` on its copay line."""
    claim, line = _hbo_claim_and_copay_line(**{field: value})

    assert claim_is_traffic_accident(claim) is False
    assert detect_traffic_accident_billing([claim], [line]) == []


@pytest.mark.parametrize("field", ["occupational_context", "claim_type"])
@pytest.mark.parametrize(
    "value", ["trafik_kazasi", "traffic_accident", "Trafik Kazası", "TRAFİK KAZASI"]
)
def test_explicit_traffic_value_is_traffic(field: str, value: str) -> None:
    """An explicit traffic value classifies the claim: copay finding only."""
    claim, line = _hbo_claim_and_copay_line(**{field: value})

    assert claim_is_traffic_accident(claim) is True
    violations = detect_traffic_accident_billing([claim], [line])
    assert [v["rule_id"] for v in violations] == ["trafik_kazasi_copay_charged"]


@pytest.mark.parametrize("occupational_context", ["none", "is_kazasi", "trafik_kazasi"])
@pytest.mark.parametrize("primary_icd10", ["T70.3", "V89.9"])
def test_scenario_tag_changes_no_finding(occupational_context: str, primary_icd10: str) -> None:
    """``scenario_tag`` is synthetic-only: blanking it changes no output (#239)."""
    line = _make_proc_line(copay_rate_applicable=True)
    outputs = [
        detect_traffic_accident_billing(
            [
                _make_claim_header(
                    primary_icd10=primary_icd10,
                    occupational_context=occupational_context,
                    scenario_tag=tag,
                )
            ],
            [line],
        )
        for tag in ("", "trafik_kazasi", "is_kazasi")
    ]
    assert outputs[0] == outputs[1] == outputs[2]
