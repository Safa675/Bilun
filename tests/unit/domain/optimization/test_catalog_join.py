"""L2.3 / L2.4 — runtime EK-2G and EK-2C-1 catalog joins."""

from __future__ import annotations

from decimal import Decimal

import pytest

from src.bilun.domain.catalog import get_ek2c1_copay_rates
from src.bilun.domain.claims.models import ProcedureClaimLine
from src.bilun.domain.optimization.catalog_join import (
    catalog_copay_rate_applicable,
    catalog_surcharge_eligible,
    copay_rate_matches_catalog,
    get_ek2c1_mandated_copay_rate_pct,
    is_ek2g_surcharge_prohibited,
)
from src.bilun.domain.optimization.claim_context import (
    build_copay_rate_claim_context,
    build_surcharge_claim_context,
)
from src.bilun.domain.optimization.exactness import (
    build_exact_copay_rate_exposure,
    build_exact_surcharge_exposure,
)
from tests.fixtures.t2_catalog_lines import ek2c1_only_code, procedure_line

pytestmark = pytest.mark.unit


def test_ek2g_catalog_marks_prohibited_codes() -> None:
    assert is_ek2g_surcharge_prohibited("551120") is True
    assert catalog_surcharge_eligible("551120") is False


def test_surcharge_exposure_uses_catalog_not_misleading_flags(monkeypatch) -> None:
    line = ProcedureClaimLine(
        procedure_line_id="P1",
        claim_id="C1",
        patient_id="PT",
        episode_id="E1",
        procedure_date=__import__("datetime").date(2026, 1, 1),
        procedure_code="551120",
        procedure_name="EK-2G listed",
        procedure_category="islem",
        quantity=1,
        unit_price_try=Decimal("100"),
        billed_amount_try=Decimal("100"),
        expected_payable_try=Decimal("80"),
        is_package_included=False,
        package_code="",
        surcharge_applicable=True,
        copay_rate_applicable=False,
        denial_reason_expected="",
        rule_trace_expected="",
    )
    ctx = build_surcharge_claim_context("PT", [line])
    assert ctx is not None
    result = build_exact_surcharge_exposure(ctx)
    assert result["n_applicable_procedures"] == 1
    assert result["n_flag_catalog_mismatches"] == 1

    eligible_line = ProcedureClaimLine(
        procedure_line_id="P2",
        claim_id="C1",
        patient_id="PT",
        episode_id="E1",
        procedure_date=__import__("datetime").date(2026, 1, 2),
        procedure_code="P603430",
        procedure_name="Not on EK-2G",
        procedure_category="islem",
        quantity=1,
        unit_price_try=Decimal("100"),
        billed_amount_try=Decimal("100"),
        expected_payable_try=Decimal("80"),
        is_package_included=False,
        package_code="",
        surcharge_applicable=True,
        copay_rate_applicable=False,
        denial_reason_expected="",
        rule_trace_expected="",
    )
    mixed_ctx = build_surcharge_claim_context("PT", [line, eligible_line])
    assert mixed_ctx is not None
    mixed = build_exact_surcharge_exposure(mixed_ctx)
    assert mixed["n_applicable_procedures"] == 1


def test_ek2c1_rate_match_tolerance() -> None:
    """Half a point either side of the mandated rate matches; more does not. On a code the check reads as a copay
    rate (it used P552001, whose 100 is the ICU uplift, and skipped when the code was not read)."""
    code, mandated = ek2c1_only_code()
    assert code not in _ICU_PACKAGES
    assert copay_rate_matches_catalog(mandated, code) is True
    assert copay_rate_matches_catalog(mandated - Decimal("0.4"), code) is True
    assert copay_rate_matches_catalog(mandated + Decimal("0.5"), code) is True
    assert copay_rate_matches_catalog(mandated + Decimal("0.6"), code) is False


# The ICU day packages (EK-2/C P552001-3, P552006-8) are on the EK-2/C-1 list at 100. SUT 2.2.(20) (C000549) adds the
# list's rate to the procedure's points when a Sınıf-3 facility performs it, and the ICU motor applies their 100 that
# way (`icu_puani._resolve_ilave_oran`: the +100 % uplift of the package days); it is no patient copay rate.
_ICU_PACKAGES = ("P552001", "P552002", "P552003", "P552006", "P552007", "P552008")


@pytest.mark.parametrize("code", [*_ICU_PACKAGES, "552002", "p552003", " P552008 ", "P552.006"])
def test_an_icu_package_is_not_read_as_a_copay_rate(code: str) -> None:
    assert get_ek2c1_mandated_copay_rate_pct(code) is None
    assert catalog_copay_rate_applicable(code) is False
    assert copay_rate_matches_catalog(Decimal("0"), code) is True


def test_the_icu_rows_stay_on_the_list_for_the_icu_motors_uplift() -> None:
    """The check leaves the rows to the ICU motor; the catalog keeps them and the motor still reads 100 on a Sınıf-3 claim."""
    from types import SimpleNamespace

    from src.bilun.domain.prose_rules.icu_puani import ICU_PACKAGE_CODES, _resolve_ilave_oran

    rows = get_ek2c1_copay_rates()
    assert {code: rows[code]["copay_rate_pct"] for code in _ICU_PACKAGES} == dict.fromkeys(_ICU_PACKAGES, 100.0)
    assert ICU_PACKAGE_CODES == {code[1:] for code in _ICU_PACKAGES}
    claim = SimpleNamespace(facility_tier="3_basamak", provider_type="sozlesmeli")
    for code in ICU_PACKAGE_CODES:
        assert _resolve_ilave_oran(claim, code) == (100.0, "sinif_3_uplift_applied")


def test_the_rest_of_the_list_is_still_read_as_copay_rates() -> None:
    """Only the six ICU rows are left out: every other listed code keeps its rate."""
    rows = get_ek2c1_copay_rates()
    others = sorted(set(rows) - set(_ICU_PACKAGES))
    assert len(others) == len(rows) - 6 > 400
    assert all(get_ek2c1_mandated_copay_rate_pct(code) == rows[code]["copay_rate_pct"] for code in others)


@pytest.mark.parametrize("package", _ICU_PACKAGES)
def test_an_icu_day_billed_in_full_without_the_copay_flag_is_no_violation(package: str) -> None:
    """S11's ICU days: billed at payable == billed with the flag off. Beside them a listed code billed the same way is
    still a flag and a rate mismatch: the check works, it does not read the ICU uplift."""
    code, _ = ek2c1_only_code()
    lines = [
        procedure_line(package, line_id="L1", copay_flag=False, day=3),
        procedure_line(package, line_id="L2", copay_flag=False, day=4),
        procedure_line(code, line_id="L3", copay_flag=False, day=5),
    ]

    exposure = build_exact_copay_rate_exposure(build_copay_rate_claim_context("P-T2", lines))

    assert (
        exposure["n_applicable_procedures"],
        exposure["n_total_ek2c1"],
        exposure["n_flag_catalog_mismatches"],
        exposure["n_rate_catalog_mismatches"],
        exposure["n_violations"],
    ) == (1, 3, 1, 1, 2)
    assert {row["code"] for row in exposure["flag_catalog_mismatches"] + exposure["rate_catalog_mismatches"]} == {code}
    assert [row["code"] for row in exposure["procedures_with_rates"]] == [code]
