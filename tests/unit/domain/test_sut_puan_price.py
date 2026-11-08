"""SUT 2.2.(15) (C000544): an EK-2/B, EK-2/C or EK-2/Ç price is puan × katsayı taken to two
decimals "yuvarlama işlemi yapılmaksızın", i.e. cut at the kuruş, never rounded (#299).

The helper and the engine's own puan × katsayı products (the anesthesia group charge, the
companion bed without a dated price, the EK-2Ç fallbacks) cut; 510010 is 222.35, not 222.36.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pandas as pd
import pytest

pytestmark = pytest.mark.unit


def _cut(puan_hundredths: int, katsayi_thousandths: int = 593) -> float:
    """The oracle: integer arithmetic on a puan written with two decimals, cut at the kuruş."""
    return (puan_hundredths * katsayi_thousandths // 1000) / 100


@pytest.mark.parametrize(
    "puan, expected",
    [
        (374.97, 222.35),  # 510010: 222.35721, rounded 222.36 before #299
        (11325, 6715.72),  # 615040: 6,715.725 exactly, the tie a half-up rounding takes up
        (124.95, 74.09),  # 510121: 74.09535
        (372.93, 221.14),  # 550190 (anesthesia group E): 221.14749
        (100, 59.30),  # an exact product stays as it is
        (577.4538, 342.43),  # 530000 on the 2026-07-07 list: 342.4301034, cut and rounding agree
    ],
)
def test_puan_price_cuts_the_product_at_the_kurus(puan, expected) -> None:
    from src.bilun.domain.money import puan_price_try

    assert puan_price_try(puan, 0.593) == expected


def test_every_two_decimal_puan_up_to_2500_is_cut_like_integer_arithmetic() -> None:
    from src.bilun.domain.money import puan_price_try

    wrong = [
        hundredths
        for hundredths in range(1, 250_001)
        if puan_price_try(hundredths / 100, 0.593) != _cut(hundredths)
    ]
    assert wrong == []


@pytest.mark.parametrize(
    "puan, katsayi",
    [
        (Decimal("374.97"), Decimal("0.593")),
        ("374.97", "0.593"),
        (374.97, Decimal("0.593")),
        (Decimal("374.97"), 0.593),
    ],
)
def test_puan_price_reads_floats_decimals_and_text_alike(puan, katsayi) -> None:
    from src.bilun.domain.money import puan_price_try

    assert puan_price_try(puan, katsayi) == 222.35


@pytest.mark.parametrize(
    "puan, price",
    [
        # The 2020 and 2021 lists hold the puan as the float of TL ÷ 0.593: the product is the TL
        # amount up to the float's error, which must not cost a kuruş.
        (55.6492411467116, 33.00),  # 510010 on the 2020-03-11 list
        (63.99662731871834, 37.95),  # 510010 on the 2021-06-01 list
        (11.129848229342327, 6.60),  # 510120 on the 2020-03-11 list
        (788.36424957841483, 467.50),
        # A puan SGK wrote short of the quotient is cut like any other: 111.298 × 0.593 = 65.999714.
        (111.298, 65.99),
        (370.994940976, 219.99),  # P552001 on the 2020-03-11 list: 219.999999998768
    ],
)
def test_a_float_of_a_quotient_keeps_its_amount_and_a_short_puan_is_cut(puan, price) -> None:
    from src.bilun.domain.money import puan_price_try

    assert puan_price_try(puan, 0.593) == price


def test_puan_price_returns_a_float_rounded_to_the_kurus() -> None:
    from src.bilun.domain.money import puan_price_try

    value = puan_price_try(374.97, 0.593)
    assert type(value) is float
    assert repr(value) == "222.35"


# --- the engine's own puan × katsayı products ------------------------------------------------


def _header(admission: date, discharge: date, claim_id: str = "C1"):
    from src.bilun.domain.claims.models import ClaimHeader

    return ClaimHeader(
        claim_id=claim_id,
        patient_id="P1",
        episode_id="E1",
        claim_type="yatis",
        facility_tier="devlet",
        provider_type="sozlesmeli",
        department="genel",
        admission_date=admission,
        discharge_date=discharge,
        claim_start_date=admission,
        claim_end_date=discharge,
        primary_icd10="Z00.0",
        expected_total_billed_try=Decimal("1000"),
        expected_total_payable_try=Decimal("900"),
        expected_denial_reason="",
        scenario_tag="test",
    )


def _line(code: str, on: date, billed: str, *, line_id: str = "L1", category: str = "islem"):
    from src.bilun.domain.claims.models import ProcedureClaimLine

    return ProcedureClaimLine(
        procedure_line_id=line_id,
        claim_id="C1",
        patient_id="P1",
        episode_id="E1",
        procedure_date=on,
        procedure_code=code,
        procedure_name="test",
        procedure_category=category,
        quantity=1,
        unit_price_try=Decimal(billed),
        billed_amount_try=Decimal(billed),
        expected_payable_try=Decimal(billed),
        is_package_included=False,
        package_code="",
        surcharge_applicable=False,
        copay_rate_applicable=False,
        denial_reason_expected="",
        rule_trace_expected="",
    )


def test_seven_bed_days_billed_at_222_35_leave_nothing_to_recover() -> None:
    """The issue's bill: 510010 on 7 days at the SUT price, 1,556.45 TL, recovers 0 (was 0.07)."""
    from src.bilun.domain.prose_rules.yatak_puani import detect_yatak_puani_opportunities

    admission = date(2026, 7, 14)
    header = _header(admission, admission + timedelta(days=6))
    beds = [
        _line("510010", admission + timedelta(days=i), "222.35", line_id=f"B{i}", category="yatak")
        for i in range(7)
    ]
    (opp,) = detect_yatak_puani_opportunities([header], beds)

    assert opp["bed_days"] == 7
    assert opp["daily_rate_try"] == 222.35
    assert opp["expected_yatak_try"] == 1556.45
    assert opp["recoverable_uplift_try"] == 0.0


def test_the_anesthesia_group_charge_is_cut(monkeypatch) -> None:
    """Group E (550190, 372.93 puan): 221.14 TL; a line billed at 221.14 recovers nothing."""
    from tests.unit._helpers.catalog_stubs import install_anestezi_catalog_stub
    from src.bilun.domain.prose_rules import anestezi_puani

    # 612070 (303.16 puan) is surgery of group E; its starred package is not what this pins.
    install_anestezi_catalog_stub(monkeypatch, puan_by_code={"612070": 303.16, "550190": 372.93})
    monkeypatch.setattr(anestezi_puani, "mandated_package_lines", lambda claim, lines: [])
    on = date(2026, 7, 14)
    header = _header(on, on + timedelta(days=2))
    lines = [_line("612070", on, "179.77"), _line("550190", on, "221.14", line_id="L2")]
    (opp,) = anestezi_puani.detect_anestezi_puani_opportunities([header], lines)

    assert opp["anestezi_code"] == "550190"
    assert opp["anestezi_puan"] == 372.93
    assert opp["expected_try"] == 221.14
    assert opp["recoverable_uplift_try"] == 0.0


def test_the_companion_bed_without_a_dated_price_is_cut(monkeypatch) -> None:
    """510121 when the dated EK-2B price is missing: 124.95 × 0.593 = 74.09 a night, 3 nights 222.27."""
    from src.bilun.domain.prose_rules import refakatci

    monkeypatch.setattr(refakatci, "get_ek2b_price_for_date", lambda *a, **k: None)
    monkeypatch.setattr(refakatci, "get_katsayi", lambda *a, **k: 0.593)
    monkeypatch.setattr(refakatci, "_refakatci_puan", lambda: 124.95)
    header = _header(date(2026, 7, 10), date(2026, 7, 13))
    (opp,) = refakatci.detect_refakatci_opportunities([header], [_line("510121", date(2026, 7, 10), "0")])

    assert opp["days"] == 3
    assert opp["expected_try"] == 222.27
    assert "74.09 TRY/day" in opp["detail"]


def test_a_dental_row_without_a_price_is_priced_by_the_cut(monkeypatch, tmp_path) -> None:
    from src.bilun.domain.loaders import gazette

    frame = pd.DataFrame(
        {
            "code": ["402150", "402251"],
            "name": ["Kanal tedavisi, tek kanal", "Gangren tedavisi"],
            "puan": [374.97, 11325.0],
            "price_try": [None, None],
            "effective_date": ["2026-01-01", "2026-01-01"],
            "valid_from": ["2026-01-01", "2026-01-01"],
            "valid_to": pd.Series([None, None], dtype="string"),
        }
    )
    path = tmp_path / "dental.parquet"
    frame.to_parquet(path, index=False)
    monkeypatch.setattr(gazette, "EK2C_DENTAL_CURATED_HISTORY_PATH", path)
    monkeypatch.setattr(gazette, "_EK2C_DENTAL_XLS_FALLBACK", None)
    monkeypatch.setattr(gazette, "_ek2c_dental_raw_cache", None)
    monkeypatch.setattr(gazette, "_ek2c_dental_by_asof_cache", {})

    by_code = gazette._load_curated_ek2c_dental_by_asof("2026-07-20")
    assert {code: entry["price_try"] for code, entry in by_code.items()} == {
        "402150": 222.35,
        "402251": 6715.72,
    }


def test_the_dental_workbook_fallback_prices_by_the_cut(monkeypatch, tmp_path) -> None:
    """Without a curated EK-2Ç history the loader reads the workbook and prices it like the builder."""
    from src.bilun.domain.loaders import gazette

    workbook = tmp_path / "EK-2C_DIS_Yur.01.01.2026.xls"
    workbook.write_bytes(b"")
    sheet = pd.DataFrame(
        [
            ["İŞLEM KODU", "İŞLEM ADI", "AÇIKLAMALAR", "İŞLEM PUANI"],
            ["402150", "Kanal tedavisi, tek kanal", None, 374.97],
            ["402251 (Ek: RG-17/01/2026)", "Gangren tedavisi", None, 11325],
            [None, "Kanal tedavileri", None, None],
        ]
    )
    monkeypatch.setattr(pd, "read_excel", lambda *a, **k: sheet)
    monkeypatch.setattr(gazette, "EK2C_DENTAL_CURATED_HISTORY_PATH", tmp_path / "missing.parquet")
    monkeypatch.setattr(gazette, "_EK2C_DENTAL_XLS_FALLBACK", workbook)

    frame = gazette._read_ek2c_dental_frame()
    assert dict(zip(frame["code"], frame["price_try"], strict=True)) == {"402150": 222.35, "402251": 6715.72}
