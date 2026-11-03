"""The EK-2B, EK-2C and EK-2Ç builders price a row as puan × 0.593 cut at the kuruş, SUT 2.2.(15)
(C000544: "yuvarlama işlemi yapılmaksızın virgülden sonra iki basamak"), and so does every curated
row (#299: 510010 is 222.35 from 2026-01-01, not 222.36)."""

from __future__ import annotations

import math
from fractions import Fraction
from pathlib import Path

import pandas as pd
import polars as pl
import pytest

from scripts.sut.catalogs.price_history import extract_ek2b, extract_ek2c, extract_ek2c_dental

pytestmark = pytest.mark.unit

_CURATED = Path(__file__).resolve().parents[3] / "data/gazette/curated"
_KATSAYI = Fraction(593, 1000)
# A curated puan is a float64: the 2020 and 2021 lists hold TL ÷ 0.593 to 15-17 digits, whose
# product misses its TL amount by far less than a millionth of a kuruş.
_FLOAT_ERROR = Fraction(1, 10**9)


def _cut(puan: float) -> float:
    """The oracle: exact rational arithmetic on the puan as written, cut at the kuruş."""
    return math.floor((Fraction(str(puan)) * _KATSAYI + _FLOAT_ERROR) * 100) / 100


def _sheet(title: str, header: tuple[str, ...], rows: list[tuple]) -> pd.DataFrame:
    columns = [title, *(f"Unnamed: {i}" for i in range(1, len(header)))]
    return pd.DataFrame([header, *rows], columns=columns).astype(object)


def test_ek2b_rows_are_cut_at_the_kurus() -> None:
    out = extract_ek2b(_sheet(
        "HİZMET BAŞI İŞLEM PUAN LİSTESİ (EK-2/B)",
        ("İŞLEM KODU", "İŞLEM ADI", "AÇIKLAMA", "İŞLEM PUANI"),
        [
            ("510010", "Standart yatak tarifesi", None, 374.97),
            ("615040", "Tie", None, 11325),
            ("510121", "Refakat", None, "124,95"),
            ("530000", "Exact", " Günde bir adet faturalandırılır. ", 100),
            ("530010", "No puan", None, None),
        ],
    ))
    # The Açıklama is kept, trimmed, for the daily caps (#303); an empty cell reads "".
    assert out["description"].tolist() == ["", "", "", "Günde bir adet faturalandırılır.", ""]
    prices = dict(zip(out["code"], out["price_try"], strict=True))
    assert prices["510010"] == 222.35  # 222.35721
    assert prices["615040"] == 6715.72  # 6,715.725 exactly
    assert prices["510121"] == 74.09  # 74.09535
    assert prices["530000"] == 59.30
    assert math.isnan(prices["530010"])
    assert out["price_try"].dtype == "float64"


def test_ek2c_packages_are_cut_at_the_kurus() -> None:
    out = extract_ek2c(_sheet(
        "TANIYA DAYALI İŞLEM PUAN LİSTESİ (EK-2/C)",
        ("İŞLEM KODU", "İŞLEM ADI", "İŞLEM GRUBU", "AÇIKLAMA", "İŞLEM PUANI"),
        [
            ("P510010", "Package", "A", None, 374.97),
            ("P615040", "Tie", "B", None, 11325),
            ("P701360", "Exact", "C", None, 1000),
        ],
    ))
    assert dict(zip(out["package_code"], out["price_try"], strict=True)) == {
        "P510010": 222.35,
        "P615040": 6715.72,
        "P701360": 593.0,
    }


def test_ek2c_dental_rows_are_cut_at_the_kurus() -> None:
    out = extract_ek2c_dental(_sheet(
        "DİŞ TEDAVİLERİ PUAN LİSTESİ (EK-2/Ç)",
        ("İŞLEM KODU", "İŞLEM ADI", "AÇIKLAMALAR", "İŞLEM PUANI"),
        [
            ("402150", "Kanal tedavisi, tek kanal", None, 374.97),
            ("P401000", "Ortodonti paketi", None, 11325),
        ],
    ))
    assert dict(zip(out["code"], out["price_try"], strict=True)) == {"402150": 222.35, "P401000": 6715.72}


@pytest.mark.parametrize(
    "name, key",
    [
        ("ek2b_catalog_history", "code"),
        ("ek2c_catalog_history", "package_code"),
        ("ek2c_dental_catalog_history", "code"),
    ],
)
def test_every_curated_row_is_its_puan_cut_at_the_kurus(name: str, key: str) -> None:
    frame = pl.read_parquet(_CURATED / f"{name}.parquet", columns=[key, "puan", "price_try", "valid_from"])
    priced = frame.filter(pl.col("puan").is_not_null())
    wrong = [
        (row[key], row["valid_from"], row["puan"], row["price_try"])
        for row in priced.iter_rows(named=True)
        if row["price_try"] != _cut(row["puan"])
    ]
    assert wrong == []
    assert frame.filter(pl.col("puan").is_null())["price_try"].null_count() == frame.filter(
        pl.col("puan").is_null()
    ).height


@pytest.mark.parametrize(
    "name, key, code, price",
    [
        ("ek2b_catalog_history", "code", "510010", 222.35),
        ("ek2b_catalog_history", "code", "510121", 74.09),
        ("ek2b_catalog_history", "code", "615040", 6715.72),
        ("ek2c_catalog_history", "package_code", "P552001", None),
    ],
)
def test_the_issue_codes_on_2026_07_20(name: str, key: str, code: str, price: float | None) -> None:
    day = "2026-07-20"
    frame = pl.read_parquet(_CURATED / f"{name}.parquet").filter(
        (pl.col(key) == code)
        & (pl.col("valid_from") <= day)
        & (pl.col("valid_to").is_null() | (pl.col("valid_to") >= day))
    )
    assert frame.height == 1
    (row,) = frame.iter_rows(named=True)
    assert row["price_try"] == (price if price is not None else _cut(row["puan"]))
