"""A material line's KDV is the rate it declares (Safa675/Bilun#298).

SUT 3.2.1.C(1) (C002886): "Kurum bilgi işlem sistemine girilen KDV oranında bedel ilave edilerek Kurumca bedelleri
karşılanır". SGK adds KDV at the rate entered in its system, MEDULA's ``MalzemeBilgisiDVO.kdv``: an integer percent the
facility declares on every material line (Kılavuz p.243, p.126); implants carry 10 %. Before #298 every reader added
20 %: an AP1880 head (5,391.89 ex-KDV) declared at 10 % and billed at +20 % (6,470.26) was no KDV review, and the
missing-material uplift of a 10 % line was priced at +20 % (539.18 TL too high for AP1880). A line that declares no
rate keeps the 20 % default and its row says the rate was not declared.
"""

from __future__ import annotations

import itertools
import json
import shutil
from dataclasses import replace
from datetime import date
from decimal import Decimal
from pathlib import Path

import polars as pl
import pytest

from src.bilun.domain.billing.claim_materials import precheck_materials_from_claims
from src.bilun.domain.claims.models import ClaimHeader, MaterialClaimLine, ProcedureClaimLine
from src.bilun.domain.claims.patient_context import PatientClaimContext

pytestmark = pytest.mark.unit

_DAY = date(2026, 9, 4)  # S5's operation day
_EX_KDV = 5391.89  # AP1880 on the EK-3 list (5,391.8865), ex-KDV
_AT_10 = 5931.08  # + 10 %
_AT_20 = 6470.26  # + 20 %, the default
_AT_25 = 6739.86  # + 25 %
_NOT_EXEMPT = {"exempt": False, "n_qualifying": 0, "qualifying_diagnoses": []}


def _claim(claim_id: str = "C1") -> ClaimHeader:
    return ClaimHeader(
        claim_id=claim_id,
        patient_id="P1",
        episode_id="E1",
        claim_type="yatis",
        facility_tier="3_basamak_ozel",
        provider_type="Ozel",
        department="Ortopedi ve Travmatoloji",
        admission_date=date(2026, 9, 3),
        discharge_date=date(2026, 9, 8),
        claim_start_date=date(2026, 9, 3),
        claim_end_date=date(2026, 9, 8),
        primary_icd10="S72.00",
        expected_total_billed_try=Decimal("0"),
        expected_total_payable_try=Decimal("0"),
        expected_denial_reason="",
        scenario_tag="test",
    )


def _proc(procedure_line_id: str = "PL1") -> ProcedureClaimLine:
    return ProcedureClaimLine(
        procedure_line_id=procedure_line_id,
        claim_id="C1",
        patient_id="P1",
        episode_id="E1",
        procedure_date=_DAY,
        procedure_code="612320",
        procedure_name="Kalça protezi",
        procedure_category="islem",
        quantity=1,
        unit_price_try=Decimal("1000"),
        billed_amount_try=Decimal("1000"),
        expected_payable_try=Decimal("1000"),
        is_package_included=False,
        package_code="",
        surcharge_applicable=False,
        copay_rate_applicable=False,
        denial_reason_expected="",
        rule_trace_expected="",
    )


def _ap1880(
    billed: float,
    kdv_percent: int | None,
    *,
    line_id: str = "M1",
    quantity: int = 1,
    foreign: bool = False,
    procedure_line_id: str = "PL1",
) -> MaterialClaimLine:
    return MaterialClaimLine(
        material_line_id=line_id,
        claim_id="C1",
        procedure_line_id=procedure_line_id,
        patient_id="P1",
        material_date=_DAY,
        material_code="AP1880",
        material_name="Femur başı",
        material_type="implant",
        specialty_category="EK-3F-1",
        quantity=quantity,
        unit_price_try=Decimal(str(billed)),
        billed_amount_try=Decimal(str(billed)),
        expected_payable_try=Decimal(str(billed)),
        is_bundled=False,
        requires_pre_auth=False,
        denial_reason_expected="",
        rule_trace_expected="",
        foreign_facility=foreign,
        kdv_percent=kdv_percent,
    )


def _ctx(*materials: MaterialClaimLine, procedures=()) -> PatientClaimContext:
    return PatientClaimContext("P1", (_claim(),), tuple(procedures), tuple(materials), (), ())


def _reviews(*materials: MaterialClaimLine) -> list[dict]:
    return precheck_materials_from_claims(_ctx(*materials)).kdv_price_reviews


def _ceiling(percent: int) -> float:
    return round(5391.8865 * (1 + percent / 100), 2)


# --- the material KDV helpers ---------------------------------------------------------------------------------------


@pytest.mark.parametrize(("percent", "rate"), [(0, 0.0), (1, 0.01), (8, 0.08), (10, 0.10), (18, 0.18), (20, 0.20)])
def test_a_declared_percent_is_the_rate_it_names(percent, rate) -> None:
    from src.bilun.domain.pricing.material_kdv import declared_kdv_rate, material_line_kdv_rate

    assert declared_kdv_rate(percent) == pytest.approx(rate)
    assert material_line_kdv_rate(_ap1880(1, percent)) == (pytest.approx(rate), True)


def test_an_undeclared_line_keeps_the_20_percent_default_and_says_so() -> None:
    from src.bilun.domain.pricing.material_kdv import (
        DEFAULT_MATERIAL_KDV_RATE,
        declared_kdv_rate,
        material_line_kdv_rate,
    )

    assert DEFAULT_MATERIAL_KDV_RATE == 0.20
    assert declared_kdv_rate(None) is None
    assert material_line_kdv_rate(_ap1880(1, None)) == (0.20, False)


def test_the_issue_probe_ceilings() -> None:
    from src.bilun.domain.materials.catalog_lookup import lookup_ek3_list_price_try
    from src.bilun.domain.pricing.material_kdv import ek3_payable_ceiling_try

    ex_kdv = lookup_ek3_list_price_try("AP1880", _DAY)
    assert round(ex_kdv, 2) == _EX_KDV
    assert ek3_payable_ceiling_try(ex_kdv, kdv_rate=0.10) == _AT_10
    assert ek3_payable_ceiling_try(ex_kdv) == _AT_20


# --- the loaders ----------------------------------------------------------------------------------------------------


def _row(**extra) -> dict:
    return {
        "material_line_id": "TEST-M",
        "claim_id": "TEST-C",
        "patient_id": "TEST-P",
        "material_date": date(2026, 9, 1),
        "material_code": "AP1880",
        "billed_amount_try": 100,
        **extra,
    }


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (10, 10),
        (0, 0),
        (8, 8),
        (20, 20),
        (100, 100),
        (10.0, 10),
        ("10", 10),
        (" 18 ", 18),
        (Decimal("10"), 10),
        (None, None),
        (float("nan"), None),
        ("", None),
        ("  ", None),
    ],
)
def test_a_material_row_reads_the_kdv_percent_it_declares(raw, expected) -> None:
    from src.bilun.domain.claims.parsing.row_parsers import parse_material_line

    errors: list[str] = []
    line = parse_material_line(_row(kdv_percent=raw), errors)
    assert not errors
    assert line.kdv_percent == expected
    assert line.kdv_percent is None or type(line.kdv_percent) is int


def test_a_material_row_without_the_column_declares_no_rate() -> None:
    from src.bilun.domain.claims.parsing.row_parsers import parse_material_line

    errors: list[str] = []
    assert parse_material_line(_row(), errors).kdv_percent is None
    assert not errors


@pytest.mark.parametrize(
    "raw", [10.5, "10,5", "%10", "on", 0.1, True, False, -1, 101, "-5", [10], float("inf"), "Infinity", "nan", "sNaN"]
)
def test_a_kdv_percent_that_is_no_whole_percent_from_0_to_100_is_an_error(raw) -> None:
    from src.bilun.domain.claims.parsing.row_parsers import parse_material_line

    errors: list[str] = []
    line = parse_material_line(_row(kdv_percent=raw), errors)
    assert errors == [f"TEST-M invalid kdv_percent: {raw!r}"]
    assert line.kdv_percent is None  # the loader refuses the dataset on the error


def test_the_kdv_percent_round_trips_through_the_parquet_loader(tmp_path: Path) -> None:
    from src.bilun.domain.claims import load_sut_claim_dataset
    from src.bilun.domain.claims.config import DEFAULT_SYNTHETIC_CLAIMS_DIR

    claims_dir = tmp_path / "claim_export"
    shutil.copytree(DEFAULT_SYNTHETIC_CLAIMS_DIR, claims_dir)
    path = claims_dir / "material_claim_lines.parquet"
    materials = pl.read_parquet(path)
    values = list(itertools.islice(itertools.cycle([10, None, 0, 20]), materials.height))
    assert materials.height >= 4
    materials.with_columns(pl.Series("kdv_percent", values, dtype=pl.Int64)).write_parquet(path)

    dataset = load_sut_claim_dataset(claims_dir, mode="real_claims")
    assert [dataset.material_lines[key].kdv_percent for key in materials["material_line_id"]] == values


def test_a_parquet_kdv_percent_that_is_no_percent_rejects_the_dataset(tmp_path: Path) -> None:
    from src.bilun.domain.claims import ClaimValidationError, load_sut_claim_dataset
    from src.bilun.domain.claims.config import DEFAULT_SYNTHETIC_CLAIMS_DIR

    claims_dir = tmp_path / "claim_export"
    shutil.copytree(DEFAULT_SYNTHETIC_CLAIMS_DIR, claims_dir)
    path = claims_dir / "material_claim_lines.parquet"
    pl.read_parquet(path).with_columns(pl.lit(0.1).alias("kdv_percent")).write_parquet(path)
    with pytest.raises(ClaimValidationError, match="invalid kdv_percent: 0.1"):
        load_sut_claim_dataset(claims_dir, mode="real_claims")


# --- the KDV price review (§3.1.1(10), §3.2.1.C(1)) -----------------------------------------------------------------


def test_a_10_percent_implant_billed_at_10_percent_is_no_review() -> None:
    assert _reviews(_ap1880(_AT_10, 10)) == []


def test_a_10_percent_implant_billed_at_20_percent_is_a_review_against_its_10_percent_ceiling() -> None:
    [row] = _reviews(_ap1880(_AT_20, 10))
    assert row["gazette_ex_vat_try"] == _EX_KDV
    assert row["gazette_ceiling_try"] == _AT_10
    assert row["billed_try"] == _AT_20
    assert row["kdv_applied"] is True
    assert row["kdv_rate"] == pytest.approx(0.10)
    assert row["kdv_rate_declared"] is True
    assert "10 % KDV declared on the line" in row["note"]
    assert row["material_line_id"] == "M1" and row["claim_id"] == "C1"


def test_an_undeclared_line_keeps_the_20_percent_ceiling_and_its_row_says_no_rate_was_declared() -> None:
    # The default adds no money: billed at +20 % is no review, as before #298.
    assert _reviews(_ap1880(_AT_20, None)) == []
    [row] = _reviews(_ap1880(_AT_25, None))
    assert row["gazette_ceiling_try"] == _AT_20
    assert row["kdv_rate"] == pytest.approx(0.20)
    assert row["kdv_rate_declared"] is False
    assert "20 % default" in row["note"] and "declares no KDV rate" in row["note"]


@pytest.mark.parametrize("percent", [0, 1, 8, 10, 18, 20])
def test_the_ceiling_is_the_list_price_plus_the_declared_rate_to_the_cent(percent) -> None:
    ceiling = _ceiling(percent)
    assert _reviews(_ap1880(ceiling + 0.01, percent)) == []  # the one-cent tolerance
    [row] = _reviews(_ap1880(round(ceiling + 0.02, 2), percent))
    assert row["gazette_ceiling_try"] == ceiling
    assert row["kdv_rate"] == pytest.approx(percent / 100)
    assert row["kdv_rate_declared"] is True


def test_a_quantity_multiplies_the_declared_ceiling() -> None:
    assert _reviews(_ap1880(_AT_10 * 2, 10, quantity=2)) == []
    [row] = _reviews(_ap1880(round(_AT_10 * 2 + 0.02, 2), 10, quantity=2))
    assert row["gazette_ceiling_try"] == pytest.approx(_AT_10 * 2)


def test_a_foreign_facility_adds_no_kdv_whatever_the_line_declares() -> None:
    assert _reviews(_ap1880(_EX_KDV, 10, foreign=True)) == []
    [row] = _reviews(_ap1880(_AT_10, 10, foreign=True))
    assert row["gazette_ceiling_try"] == _EX_KDV
    assert row["kdv_applied"] is False
    assert row["kdv_rate"] == 0.0
    assert row["kdv_rate_declared"] is True
    assert "KDV exempt path" in row["note"]


@pytest.mark.parametrize("order", list(itertools.permutations(range(3))))
def test_every_line_is_priced_at_its_own_rate(order) -> None:
    lines = [
        _ap1880(_AT_20, 10, line_id="M10"),
        _ap1880(_AT_20, None, line_id="MNONE"),
        _ap1880(_AT_20, 20, line_id="M20"),
    ]
    rows = _reviews(*(lines[i] for i in order))
    assert [(row["material_line_id"], row["gazette_ceiling_try"]) for row in rows] == [("M10", _AT_10)]


# --- the missing-material uplift (§3.1) -----------------------------------------------------------------------------


@pytest.fixture
def ap1880_rule(monkeypatch):
    """A pairing rule for the AP1880 head of a 612320 hip operation (no committed rule pairs AP1880)."""
    from src.bilun.domain.prose_rules import material_uplift

    rules = {
        "rules": [
            {
                "rule_id": "test.612320_ap1880",
                "procedure_codes": ["612320"],
                "expected_material_codes": ["AP1880"],
                "pairing_mode": "specialty_annex",
                "sut_section": "3.1.1",
            }
        ]
    }
    monkeypatch.setattr(material_uplift, "load_material_pairing_rules", lambda: rules)


def _uplift(*materials: MaterialClaimLine) -> list[dict]:
    from src.bilun.domain.prose_rules.material_uplift import detect_missing_billable_material_opportunities

    return detect_missing_billable_material_opportunities(_claim(), [_proc()], list(materials))


def test_the_uplift_price_of_a_10_percent_ap1880_is_5931_08() -> None:
    from src.bilun.domain.prose_rules.material_uplift import _price_material_uplift

    assert _price_material_uplift("AP1880", foreign_facility=False, as_of=_DAY, kdv_rate=0.10) == (
        _AT_10,
        "ek3_list_price_with_kdv",
    )
    assert _price_material_uplift("AP1880", foreign_facility=False, as_of=_DAY) == (
        _AT_20,
        "ek3_list_price_with_kdv",
    )


def test_an_ap1880_billed_at_its_declared_10_percent_has_no_uplift(ap1880_rule) -> None:
    # Before #298: 6,470.26 - 5,931.08 = 539.18 TL of false uplift.
    assert _uplift(_ap1880(_AT_10, 10)) == []


def test_an_under_billed_10_percent_ap1880_recovers_up_to_its_10_percent_ceiling(ap1880_rule) -> None:
    [row] = _uplift(_ap1880(3000.00, 10))
    assert row["ceiling_try"] == _AT_10
    assert row["recoverable_uplift_try"] == pytest.approx(_AT_10 - 3000.00)
    assert row["kdv_rate"] == pytest.approx(0.10)
    assert row["kdv_rate_declared"] is True


@pytest.mark.parametrize("linked", [False, True])
def test_a_missing_or_undeclared_ap1880_keeps_the_20_percent_uplift_and_says_no_rate_was_declared(
    ap1880_rule, linked
) -> None:
    materials = [_ap1880(3000.00, None)] if linked else []
    [row] = _uplift(*materials)
    assert row["ceiling_try"] == _AT_20
    assert row["recoverable_uplift_try"] == pytest.approx(_AT_20 - (3000.00 if linked else 0.0))
    assert row["kdv_rate"] == pytest.approx(0.20)
    assert row["kdv_rate_declared"] is False


def test_an_uplift_at_a_foreign_facility_adds_no_kdv(ap1880_rule) -> None:
    [row] = _uplift(_ap1880(3000.00, 10, foreign=True))
    assert row["ceiling_try"] == _EX_KDV
    assert row["kdv_rate"] == 0.0
    assert row["kdv_rate_declared"] is True


@pytest.mark.parametrize(
    ("lines", "expected"),
    [
        # The line compared is the one billed most: its 10 % ceiling is reached, no uplift.
        ([(_AT_10, 10), (100.00, 20)], None),
        # The 20 % line is billed most: 6,470.26 - 6,000.00.
        ([(6000.00, 20), (100.00, 10)], (_AT_20, 470.26)),
        # An undeclared line billed most keeps the default, though another line declares 10 %.
        ([(6000.00, None), (100.00, 10)], (_AT_20, 470.26)),
        # Equal amounts: the lower rate, the smaller uplift.
        ([(3000.00, 20), (3000.00, 10)], (_AT_10, round(_AT_10 - 3000.00, 2))),
        ([(3000.00, None), (3000.00, 10)], (_AT_10, round(_AT_10 - 3000.00, 2))),
    ],
)
@pytest.mark.parametrize("reverse", [False, True])
def test_the_rate_of_several_linked_lines_is_the_rate_of_the_line_compared(ap1880_rule, lines, expected, reverse) -> None:
    materials = [_ap1880(billed, percent, line_id=f"M{i}") for i, (billed, percent) in enumerate(lines)]
    rows = _uplift(*(reversed(materials) if reverse else materials))
    if expected is None:
        assert rows == []
    else:
        [row] = rows
        assert (row["ceiling_try"], row["recoverable_uplift_try"]) == (expected[0], pytest.approx(expected[1]))


def test_the_pairing_violation_carries_the_rate_in_its_opportunity(ap1880_rule) -> None:
    from src.bilun.domain.prose_rules.material_uplift import check_material_pairing_for_context

    [violation] = check_material_pairing_for_context(_ctx(_ap1880(3000.00, 10), procedures=[_proc()]))
    assert violation["savings_try"] == pytest.approx(_AT_10 - 3000.00)
    assert violation["details"]["ceiling_try"] == _AT_10
    assert violation["details"]["opportunity"]["kdv_rate_declared"] is True


# --- the public report ----------------------------------------------------------------------------------------------


def test_the_public_billing_report_keeps_the_rate_and_whether_it_was_declared(ap1880_rule) -> None:
    from src.bilun.api.public_responses import project_public_response
    from src.bilun.api.routes.billing import _serialize_billing_report
    from src.bilun.domain.billing.orchestrator import compute_patient_billing_report

    # PL1: two heads above their ceilings (reviews) and billed in full (no uplift); PL2: one under-billed head.
    materials = (
        _ap1880(_AT_20, 10, line_id="M10"),
        _ap1880(_AT_25, None, line_id="MNONE"),
        _ap1880(3000.00, 10, line_id="MLOW", procedure_line_id="PL2"),
    )
    ctx = _ctx(*materials, procedures=[_proc("PL1"), _proc("PL2")])
    report = compute_patient_billing_report("P1", claim_context=ctx, copay_exemption=_NOT_EXEMPT)
    payload = json.loads(json.dumps(_serialize_billing_report(report), default=str))
    public = project_public_response(payload, "/api/billing-report/{patient_id}")

    reviews = {row["material_line_id"]: row for row in public["materials"]["kdv_price_reviews"]}
    assert {key: (row["gazette_ceiling_try"], row["kdv_rate"], row["kdv_rate_declared"]) for key, row in reviews.items()} == {
        "M10": (_AT_10, pytest.approx(0.10), True),
        "MNONE": (_AT_20, pytest.approx(0.20), False),
    }
    [opportunity] = public["material_uplift"]["opportunities"]
    assert (opportunity["procedure_line_id"], opportunity["ceiling_try"]) == ("PL2", _AT_10)
    assert (opportunity["kdv_rate"], opportunity["kdv_rate_declared"]) == (pytest.approx(0.10), True)


# --- the committed demo ---------------------------------------------------------------------------------------------


def test_no_committed_demo_material_line_declares_a_rate_and_none_has_a_kdv_review() -> None:
    from scripts.synthetic.cohort.engine_proof import load_showcase_dataset
    from src.bilun.domain.claims.patient_context import build_bill_claim_context

    dataset = load_showcase_dataset()
    lines = list(dataset.material_lines.values())
    assert len(lines) == 6
    assert {line.kdv_percent for line in lines} == {None}
    for line in lines:
        ctx = build_bill_claim_context(line.patient_id, line.claim_id, dataset)
        assert precheck_materials_from_claims(ctx).kdv_price_reviews == []


def test_s5s_ap1880_declared_at_10_percent_and_billed_at_20_percent_is_a_review_against_5931_08() -> None:
    from scripts.synthetic.cohort.engine_proof import load_showcase_dataset
    from src.bilun.domain.claims.patient_context import build_bill_claim_context
    from tests.fixtures import synthetic_cohort as cohort

    role = cohort.role("showcase_S5")
    ctx = build_bill_claim_context(role.patient_id, role.claim_id, load_showcase_dataset())
    [head] = [line for line in ctx.material_lines if line.material_code == "AP1880"]
    assert float(head.billed_amount_try) == _EX_KDV  # the demo bills the list price without KDV
    declared = replace(head, kdv_percent=10, billed_amount_try=Decimal(str(_AT_20)))
    ctx = replace(ctx, material_lines=tuple(declared if line is head else line for line in ctx.material_lines))

    [row] = precheck_materials_from_claims(ctx).kdv_price_reviews
    assert (row["material_line_id"], row["gazette_ceiling_try"], row["kdv_rate_declared"]) == (
        head.material_line_id,
        _AT_10,
        True,
    )
