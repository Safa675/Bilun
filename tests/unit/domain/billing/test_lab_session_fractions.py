"""L3.1 §2.2.2.B session fraction tests for lab optimizer."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit


def test_lab_session_fraction_no_adjustment_single_test() -> None:
    from src.bilun.domain.billing.lab import _optimize_lab_billing

    result = _optimize_lab_billing(
        "P1",
        ["Glukoz"],
        patient_lab_visit_ids=["V1"],
    )

    assert result.session_fraction_savings == 0.0
    assert not any(
        f["flag_type"] == "session_fraction_overbilling" for f in result.flagged_tests
    )


def test_lab_session_fraction_two_distinct_tests_same_visit() -> None:
    from src.bilun.domain.billing.lab import _optimize_lab_billing

    result = _optimize_lab_billing(
        "P1",
        ["Glukoz", "CRP"],
        patient_lab_visit_ids=["V1", "V1"],
    )

    session_flags = [
        f for f in result.flagged_tests if f["flag_type"] == "session_fraction_overbilling"
    ]
    assert len(session_flags) == 1
    assert session_flags[0]["sut_code"] in {"L102890", "L101840"}
    assert session_flags[0]["expected_point_factor"] == pytest.approx(0.30, abs=0.01)
    assert result.session_fraction_savings > 0.0
    assert result.total_savings == result.session_fraction_savings


def test_lab_session_fraction_respects_visit_boundaries() -> None:
    from src.bilun.domain.billing.lab import _optimize_lab_billing

    result = _optimize_lab_billing(
        "P1",
        ["Glukoz", "CRP"],
        patient_lab_visit_ids=["V1", "V2"],
    )

    assert result.session_fraction_savings == 0.0
    assert not any(
        f["flag_type"] == "session_fraction_overbilling" for f in result.flagged_tests
    )


def test_lab_session_fraction_after_hemogram_bundling() -> None:
    from src.bilun.domain.billing.lab import _optimize_lab_billing

    result = _optimize_lab_billing(
        "P1",
        ["Hemoglobin", "Hematokrit", "Glukoz"],
        patient_lab_visit_ids=["V1", "V1", "V1"],
    )

    assert result.hemogram_bundling_savings > 0.0
    assert result.session_fraction_savings > 0.0
    assert result.total_savings == pytest.approx(
        result.hemogram_bundling_savings + result.session_fraction_savings,
        abs=0.02,
    )
    assert any(f["flag_type"] == "hemogram_unbundling" for f in result.flagged_tests)
    assert any(
        f["flag_type"] == "session_fraction_overbilling" for f in result.flagged_tests
    )


def test_lab_session_fraction_skips_unknown_encounter() -> None:
    from src.bilun.domain.billing.lab import _optimize_lab_billing

    result = _optimize_lab_billing("P1", ["Glukoz", "CRP"])

    assert result.session_fraction_savings == 0.0
