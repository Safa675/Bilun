"""The lab reference table: real L-codes, in force all window, with catalog names and prices."""

from __future__ import annotations

from pathlib import Path

import polars as pl
import pytest

pytestmark = pytest.mark.unit

_REPO = Path(__file__).resolve().parents[3]
_TABLE = _REPO / "data/synthetic/reference/lab_reference.csv"
_START, _END, _PRICE_DAY = "2026-02-01", "2026-09-30", "2026-03-01"
_COLUMNS = [
    "test_key", "ek2b_code", "catalog_name", "price_try_2026_03_01", "result_parameter", "unit",
    "ref_low_male", "ref_high_male", "ref_low_female", "ref_high_female", "normal_value_range",
    "abnormal_states", "panels", "source_note", "notes",
]


@pytest.fixture(scope="module")
def table() -> pl.DataFrame:
    return pl.read_csv(_TABLE, infer_schema=False)


@pytest.fixture(scope="module")
def history(table: pl.DataFrame) -> pl.DataFrame:
    codes = table["ek2b_code"].unique().to_list()
    return pl.read_parquet(_REPO / "data/gazette/curated/ek2b_catalog_history.parquet").filter(
        pl.col("code").is_in(codes)
    )


def _in_force(history: pl.DataFrame, day: str) -> pl.DataFrame:
    return history.filter(
        (pl.col("valid_from") <= day) & (pl.col("valid_to").is_null() | (pl.col("valid_to") >= day))
    )


def test_schema_and_one_row_per_result(table: pl.DataFrame) -> None:
    assert table.columns == _COLUMNS
    required = ["test_key", "ek2b_code", "catalog_name", "price_try_2026_03_01", "result_parameter",
                "unit", "panels", "source_note"]
    assert table.select(pl.any_horizontal(pl.col(required).is_null()).sum()).item() == 0
    assert table.select(pl.struct("test_key", "result_parameter").is_duplicated().sum()).item() == 0
    assert table["ek2b_code"].str.contains(r"^L\d{6}$").all()


def test_every_code_is_in_force_with_its_name_across_the_window(table, history) -> None:
    # Check the window edges and every catalog boundary inside it.
    inside = history.filter(pl.col("valid_from").is_between(pl.lit(_START), pl.lit(_END)))["valid_from"]
    ends = history.filter(pl.col("valid_to").is_between(pl.lit(_START), pl.lit(_END)))["valid_to"]
    after_ends = ends.str.to_date().dt.offset_by("1d").cast(pl.String)
    days = sorted({_START, _END, *inside.to_list(), *ends.to_list(), *after_ends.to_list()} - {None})
    expected = table.select("ek2b_code", "catalog_name").unique()
    for day in days:
        listed = _in_force(history, day).select(pl.col("code").alias("ek2b_code"), pl.col("name"))
        joined = expected.join(listed, on="ek2b_code", how="left")
        wrong = joined.filter(pl.col("name").is_null() | (pl.col("name") != pl.col("catalog_name")))
        assert wrong.is_empty(), (day, wrong.rows()[:5])


def test_prices_match_the_catalog_on_the_price_day(table, history) -> None:
    listed = _in_force(history, _PRICE_DAY).select(pl.col("code").alias("ek2b_code"), "price_try")
    joined = table.select("ek2b_code", pl.col("price_try_2026_03_01").cast(pl.Float64)).unique().join(
        listed, on="ek2b_code", how="left"
    )
    assert joined.filter((pl.col("price_try") - pl.col("price_try_2026_03_01")).abs() > 0.005).is_empty()


def test_reference_ranges_are_not_inverted_and_clinical_values_are_labelled(table) -> None:
    ranges = table.select(
        pl.col(["ref_low_male", "ref_high_male", "ref_low_female", "ref_high_female"]).cast(pl.Float64, strict=False)
    )
    inverted = ranges.filter(
        (pl.col("ref_low_male") > pl.col("ref_high_male"))
        | (pl.col("ref_low_female") > pl.col("ref_high_female"))
    )
    assert inverted.is_empty()
    assert table["source_note"].str.contains("judgment").all()
