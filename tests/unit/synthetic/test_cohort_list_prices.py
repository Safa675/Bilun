"""Every procedure line of the committed demo bills is priced at its EK-2B or EK-2C puan on its date
× 0.593 cut at the kuruş, SUT 2.2.(15) (C000544, #299): the 510010 bed days are 222.35, not 222.36."""

from __future__ import annotations

import math
from fractions import Fraction
from pathlib import Path

import polars as pl
import pytest

from tests.unit._helpers.catalog_prices import list_puan

pytestmark = pytest.mark.unit

_REPO = Path(__file__).resolve().parents[3]
_LINES = _REPO / "data/synthetic/sut/claims/procedure_claim_lines.parquet"


def _cut(puan: float) -> float:
    return math.floor((Fraction(str(puan)) * Fraction(593, 1000) + Fraction(1, 10**9)) * 100) / 100


def test_every_committed_procedure_line_is_priced_at_its_puan_cut_at_the_kurus() -> None:
    lines = pl.read_parquet(_LINES, columns=["claim_id", "procedure_date", "procedure_code", "unit_price_try"])
    wrong = [
        (row["claim_id"], row["procedure_code"], row["unit_price_try"], price)
        for row in lines.iter_rows(named=True)
        if row["unit_price_try"] != (price := _cut(list_puan(row["procedure_code"], row["procedure_date"])))
    ]
    assert lines.height > 200
    assert wrong == []


def test_the_bed_days_of_the_committed_bills_are_222_35() -> None:
    beds = pl.read_parquet(_LINES).filter(
        (pl.col("procedure_code") == "510010") & (pl.col("procedure_date") >= "2026-01-01")
    )
    assert beds.height > 20
    assert set(beds["unit_price_try"]) == {222.35}
