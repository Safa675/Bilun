"""The EK-2B chapter table the synthetic generator uses to keep each bill in one discipline."""

from __future__ import annotations

from pathlib import Path

import polars as pl
import pytest
from polars.testing import assert_frame_equal

from scripts.synthetic.reference.build_ek2b_chapters import (
    CHAPTERS_PATH,
    CODE_MAP_PATH,
    build,
)

pytestmark = pytest.mark.unit

_REPO = Path(__file__).resolve().parents[3]
_WINDOW = ("2026-02-01", "2026-07-07", "2026-09-30")


@pytest.fixture(scope="module")
def committed() -> tuple[pl.DataFrame, pl.DataFrame]:
    return pl.read_parquet(CODE_MAP_PATH), pl.read_csv(CHAPTERS_PATH, infer_schema=False)


def test_committed_tables_match_a_fresh_build(committed) -> None:
    code_map, chapters = build()
    assert_frame_equal(committed[0], code_map)
    # The CSV is read back as text, so compare the fresh summary as text too.
    assert_frame_equal(committed[1], chapters.cast(pl.String))


def test_every_chapter_is_one_block_in_the_list(committed) -> None:
    chapters = committed[1]
    assert chapters.filter(pl.col("one_block_in_list") != "true").is_empty()
    assert {f"6.{i}" for i in range(1, 15)} <= set(chapters["chapter_id"])


def test_every_code_in_force_during_the_demo_window_has_a_chapter(committed) -> None:
    history = pl.read_parquet(_REPO / "data/gazette/curated/ek2b_catalog_history.parquet")
    for day in _WINDOW:
        in_force = history.filter(
            (pl.col("valid_from") <= day) & (pl.col("valid_to").is_null() | (pl.col("valid_to") >= day))
        ).select("code").unique()
        missing = in_force.join(committed[0], on="code", how="anti")
        assert missing.is_empty(), f"{day}: {missing['code'].head(10).to_list()}"


@pytest.mark.parametrize(
    ("code", "chapter_id", "section_id"),
    [
        ("510010", "1", "1"),  # Standart yatak tarifesi
        ("530130", "3", "3"),  # Mekanik ventilatöre bağlanma: acil/genel uygulamalar, not muayene
        ("605975", "6.4", "6.4"),  # VA-ECMO
        ("610180", "6.6", "6.6"),  # Total kolektomi
        ("R100240", "8.3", "8.3.1"),  # BT, a section under radiology
        ("L106910", "9.1", "9.1"),  # Sodyum
        ("908111", "9.A", "9.A"),  # Adenovirus PCR, lettered sub-heading
    ],
)
def test_known_codes_sit_in_their_chapter(committed, code: str, chapter_id: str, section_id: str) -> None:
    row = committed[0].filter(pl.col("code") == code)
    assert row.height == 1
    assert row["chapter_id"][0] == chapter_id
    assert row["section_id"][0] == section_id
