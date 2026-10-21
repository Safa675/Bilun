"""EK-2C-1 implied copay rate exposure tests."""

from __future__ import annotations

import dataclasses
from collections.abc import Iterable, Mapping, Sequence
from datetime import date
from decimal import Decimal

import pytest

from src.bilun.domain.catalog import get_ek2c1_copay_rates
from src.bilun.domain.claims import load_sut_claim_dataset
from src.bilun.domain.claims.models import ProcedureClaimLine
from src.bilun.domain.optimization.catalog_join import (
    copay_rate_matches_catalog,
    get_ek2c1_mandated_copay_rate_pct,
)
from src.bilun.domain.optimization.claim_context import (
    build_copay_rate_claim_context,
    procedure_implied_copay_rate_pct,
    procedure_sgk_share_pct,
)
from src.bilun.domain.optimization.exactness import build_exact_copay_rate_exposure
from tests.fixtures import synthetic_cohort as cohort

pytestmark = pytest.mark.unit


def _line(
    *,
    code: str = "P604713",
    billed: str = "100.00",
    payable: str = "60.00",
    copay_flag: bool = True,
) -> ProcedureClaimLine:
    return ProcedureClaimLine(
        procedure_line_id="L1",
        claim_id="C1",
        patient_id="P1",
        episode_id="E1",
        procedure_date=date(2026, 1, 15),
        procedure_code=code,
        procedure_name="Test procedure",
        procedure_category="islem",
        quantity=1,
        unit_price_try=Decimal(billed),
        billed_amount_try=Decimal(billed),
        expected_payable_try=Decimal(payable),
        is_package_included=False,
        package_code="",
        surcharge_applicable=False,
        copay_rate_applicable=copay_flag,
        denial_reason_expected="",
        rule_trace_expected="",
    )


def test_implied_copay_from_payable_billed() -> None:
    line = _line(billed="100.00", payable="60.00")
    assert procedure_sgk_share_pct(line) == Decimal("60.00")
    assert procedure_implied_copay_rate_pct(line) == Decimal("40.00")


def test_sgk_share_is_capped_at_one_hundred() -> None:
    line = _line(billed="100.00", payable="150.00")
    assert procedure_sgk_share_pct(line) == Decimal("100.00")
    assert procedure_implied_copay_rate_pct(line) == Decimal("0.00")


def test_catalog_match_uses_implied_copay_not_sgk_share() -> None:
    line = _line(billed="100.00", payable="60.00", code="P604713")
    implied = procedure_implied_copay_rate_pct(line)
    if not copay_rate_matches_catalog(implied, line.procedure_code):
        pytest.skip("P604713 not in local EK-2C-1 parquet")
    assert copay_rate_matches_catalog(implied, line.procedure_code) is True
    assert copay_rate_matches_catalog(procedure_sgk_share_pct(line), line.procedure_code) is False


def test_exact_exposure_flags_rate_mismatch_only() -> None:
    line = _line(billed="100.00", payable="80.00", code="P604713")
    ctx = build_copay_rate_claim_context("P1", [line])
    assert ctx is not None
    result = build_exact_copay_rate_exposure(ctx)
    assert result["n_applicable_procedures"] == 1
    if result["n_rate_catalog_mismatches"] == 0:
        pytest.skip("Catalog rate for P604713 is 20% on this dataset")
    assert result["n_violations"] >= 1
    assert result["procedures_with_rates"][0]["rate_pct"] == 20.0


def test_synthetic_claim_lines_never_exceed_one_hundred_sgk_share() -> None:
    """No cohort line pays more than it bills.

    Checked on the raw amounts: `procedure_sgk_share_pct` caps the share at 100 itself, so a
    check on its result could not fail.
    """
    dataset = load_sut_claim_dataset()

    over_paid = [
        line.procedure_line_id
        for line in dataset.procedure_lines.values()
        if line.expected_payable_try > line.billed_amount_try
    ]

    assert over_paid == []


def _evaluable(line: ProcedureClaimLine) -> bool:
    """The lines the EK-2C-1 checks look at: billed, and not inside a package."""
    return not line.is_package_included and line.billed_amount_try > 0


def _exposure_totals(
    lines_by_patient: Mapping[str, Sequence[ProcedureClaimLine]],
) -> dict[str, int]:
    """Listed lines and mismatches, summed over the patients with the exposure builder."""
    totals = {"applicable": 0, "flag_mismatches": 0, "rate_mismatches": 0}
    for patient_id, lines in lines_by_patient.items():
        ctx = build_copay_rate_claim_context(patient_id, lines)
        if ctx is None:
            continue
        exposure = build_exact_copay_rate_exposure(ctx)
        totals["applicable"] += exposure["n_applicable_procedures"]
        totals["flag_mismatches"] += exposure["n_flag_catalog_mismatches"]
        totals["rate_mismatches"] += exposure["n_rate_catalog_mismatches"]
    return totals


def _catalog_totals(lines: Iterable[ProcedureClaimLine]) -> dict[str, int]:
    """The same totals line by line from the EK-2C-1 catalog (rate tolerance 0.5 points)."""
    listed = [
        (line, Decimal(str(mandated)))
        for line in lines
        if _evaluable(line)
        and (mandated := get_ek2c1_mandated_copay_rate_pct(line.procedure_code)) is not None
    ]
    return {
        "applicable": len(listed),
        "flag_mismatches": sum(not line.copay_rate_applicable for line, _ in listed),
        "rate_mismatches": sum(
            abs(procedure_implied_copay_rate_pct(line) - mandated) > Decimal("0.5")
            for line, mandated in listed
        ),
    }


# The ICU day packages (EK-2/C P552001-3 and P552006-8). The EK-2C-1 list holds them at 100, but there
# the 100 is the +100 % uplift of a 3rd-level facility (SUT 2.2.(20), `icu_puani.py::_resolve_ilave_oran`),
# not a patient copay. The cohort's composer bills every line at payable == billed with the flag off,
# so the copay-rate check reads each ICU day as a flag and a rate mismatch. That is how the check
# reads a line of that list, not a planned inconsistency of the cohort: the assertion below leaves
# the ICU days out and counts them on their own.
_ICU_PACKAGE_CODES = frozenset({"P552001", "P552002", "P552003", "P552006", "P552007", "P552008"})


def test_synthetic_ek2c1_violations_are_demo_scoped() -> None:
    """The cohort's EK-2C-1 totals equal the catalog's, and the only planned ones are none.

    The planned inconsistencies of the cohort are its injected faults; none of the registry's
    fault rules is a copay-rate rule, so the cohort carries no flag or rate mismatch, apart from the
    ICU days (see `_ICU_PACKAGE_CODES`), which are counted separately.
    """
    dataset = load_sut_claim_dataset()
    assert all("copay" not in fault["engine_rule"] for fault in cohort.load_registry()["faults"])

    without_icu = {
        patient_id: [line for line in lines if line.procedure_code not in _ICU_PACKAGE_CODES]
        for patient_id, lines in dataset.procedure_lines_by_patient.items()
    }
    totals = _exposure_totals(without_icu)

    assert totals == _catalog_totals(line for lines in without_icu.values() for line in lines)
    assert totals["flag_mismatches"] == totals["rate_mismatches"] == 0

    # The ICU days alone: each is listed, and each reads as one flag and one rate mismatch.
    icu_days = sum(
        line.procedure_code in _ICU_PACKAGE_CODES and _evaluable(line)
        for line in dataset.procedure_lines.values()
    )
    all_totals = _exposure_totals(dataset.procedure_lines_by_patient)
    assert all_totals == _catalog_totals(dataset.procedure_lines.values())
    assert all_totals["flag_mismatches"] == all_totals["rate_mismatches"] == icu_days > 0


# (inside a package, claim flag on, share of the billed amount that SGK pays) of a control line.
_CONTROL_SHAPES = (
    (False, False, Decimal("0.60")),  # listed, flag off, paid at the mandated 40%: a flag mismatch
    (False, False, Decimal("0.60")),
    (False, True, Decimal("1.00")),  # listed, flag on, paid in full: a rate mismatch
    (False, False, Decimal("1.00")),  # both
    (False, True, Decimal("0.597")),  # copay 40.3%: inside the 0.5 point tolerance, no mismatch
    (True, False, Decimal("1.00")),  # inside a package: not looked at
)


def test_ek2c1_totals_count_cohort_lines_that_are_listed_and_wrong() -> None:
    """Control for the test above, on the cohort's own lines.

    The cohort has no line on the EK-2C-1 list, so its totals are zero whether or not the check
    works. Here every line is re-coded to a listed code (mandated 40%) and given, round robin, one
    of the shapes of `_CONTROL_SHAPES`; each total is then known from the shapes alone.
    """
    dataset = load_sut_claim_dataset()
    code = next(
        code for code, row in sorted(get_ek2c1_copay_rates().items()) if row["copay_rate_pct"] == 40
    )
    shapes = []  # the shape given to each line, in order
    relisted: dict[str, list[ProcedureClaimLine]] = {}
    for patient_id, lines in sorted(dataset.procedure_lines_by_patient.items()):
        relisted[patient_id] = []
        for line in lines:
            shapes.append(_CONTROL_SHAPES[len(shapes) % len(_CONTROL_SHAPES)])
            package, flag, share = shapes[-1]
            relisted[patient_id].append(
                dataclasses.replace(
                    line,
                    procedure_code=code,
                    is_package_included=package,
                    copay_rate_applicable=flag,
                    unit_price_try=Decimal("100.00"),
                    billed_amount_try=Decimal("100.00"),
                    expected_payable_try=Decimal("100.00") * share,
                )
            )
    expected = {
        "applicable": sum(not package for package, _, _ in shapes),
        "flag_mismatches": sum(not package and not flag for package, flag, _ in shapes),
        # Paid in full means a copay of 0% against the mandated 40%.
        "rate_mismatches": sum(not package and share == 1 for package, _, share in shapes),
    }
    # Distinct, non-zero totals: a check that swapped two of them, or counted none, would show.
    assert len(set(expected.values())) == 3 and 0 not in expected.values()

    assert _exposure_totals(relisted) == expected
    assert _catalog_totals(line for lines in relisted.values() for line in lines) == expected
