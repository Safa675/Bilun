"""Amendment markers in SUT list cells: EK-2B keeps marked rows (#226)."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import polars as pl
import pytest

from scripts.sut._common import (
    MARKER_ADDED,
    MARKER_FROM,
    MARKER_REPEALED,
    MARKER_UNDATED,
    _add_validity_ranges,
    amendment_markers,
)
from scripts.sut.catalogs.price_history import extract_ek2b

pytestmark = pytest.mark.unit

_REPO = Path(__file__).resolve().parents[3]
_EK2B_HISTORY = _REPO / "data/gazette/curated/ek2b_catalog_history.parquet"
_ADDED = "(Ek: RG-29/08/2026- 33355/ 14-a md. Yürürlük: 05/09/2026)"
_AMENDED = "(Değişik: RG-29/08/2026- 33355/ 14-ş md. Yürürlük: 05/09/2026)"
# The 30 procedures SGK added to the EK-2B list effective 2026-07-07 (#226).
_ADDED_2026 = (
    "603331 603332 603551 603881 603951 604001 608481 608671 608681 608991 608992 609131 "
    "609541 609892 609893 609894 609912 609951 610231 610271 610272 610273 610362 610481 "
    "610482 610483 618571 618862 702883 801531"
).split()


def _ek2b_list(*rows: tuple[str | None, str, float | None]) -> pd.DataFrame:
    """A raw EK-2B partition: a title column, the header row, then (code cell, name, puan)."""
    header = ("İŞLEM KODU", "İŞLEM ADI", "AÇIKLAMA", "İŞLEM PUANI")
    body = [header, *((code, name, None, puan) for code, name, puan in rows)]
    columns = ["HİZMET BAŞI İŞLEM PUAN LİSTESİ (EK-2/B)", "Unnamed: 1", "Unnamed: 2", "Unnamed: 3"]
    return pd.DataFrame(body, columns=columns).astype(object)


def test_parser_reads_kind_and_yururluk_date_of_each_marker() -> None:
    cells = pd.Series([
        f"603331      {_ADDED}",
        "608310 (Değişik:          RG-02/10/2026- 33388/ 3-a md. Yürürlük: 10/10/2026)",
        "P617710 (Mülga: RG-08/04/2026- 33218/ 10-b md. Yürürlük: 16/04/2026)",
        "801663 (Ek: RG- /03/2025- 328../ 11-ç md. Yürürlük: 5 iş/02/2025)",
        "510010",
        None,
    ])
    markers = amendment_markers(cells)
    assert markers[MARKER_FROM].dt.strftime("%Y-%m-%d").tolist()[:2] == ["2026-09-05", "2026-10-10"]
    assert markers[MARKER_ADDED].tolist() == [True, False, False, False, False, False]
    assert markers[MARKER_REPEALED].notna().tolist() == [False, False, True, False, False, False]
    assert str(markers.loc[2, MARKER_REPEALED].date()) == "2026-04-16"
    assert markers[MARKER_UNDATED].tolist() == [False, False, False, True, False, False]
    assert markers.loc[4:, MARKER_FROM].isna().all()


def test_ek2b_row_whose_code_cell_carries_a_marker_is_kept() -> None:
    out = extract_ek2b(_ek2b_list(
        ("510010", "Standart yatak tarifesi", 374.97),
        (f"603331      {_ADDED}", "Mediastinal malign tümör eksizyonu (torakoskopik)", 21215.39),
        (_ADDED, "Uyku Çalışmaları", None),  # a heading row carries a marker but no code
    ))
    assert out["code"].tolist() == ["510010", "603331"]
    assert out.loc[1, "puan"] == pytest.approx(21215.39)
    assert str(out.loc[1, MARKER_FROM].date()) == "2026-09-05"


def _history(*lists: tuple[str, pd.DataFrame]) -> pd.DataFrame:
    """The EK-2B price history of (effective date, raw list) pairs."""
    frames = [extract_ek2b(raw).assign(effective_date=day) for day, raw in lists]
    return _add_validity_ranges(pd.concat(frames, ignore_index=True), "code")


def test_amended_row_replaces_the_clean_row_of_the_same_code_in_one_list() -> None:
    history = _history(
        ("2026-01-31", _ek2b_list(("702820", "Poligrafik uyku tetkiki", 1192.33))),
        ("2026-07-07", _ek2b_list(
            ("702820", "Poligrafik uyku tetkiki", 1192.33),
            (f"702820 {_AMENDED}", "Uyku tetkiki", 1192.33),
        )),
    )
    assert history.loc[history["effective_date"] == "2026-07-07", "name"].tolist() == ["Uyku tetkiki"]
    assert not set(history.columns) & {MARKER_FROM, MARKER_ADDED, MARKER_REPEALED, MARKER_UNDATED}


def test_curated_ek2b_has_the_procedures_added_by_marked_rows() -> None:
    history = pl.read_parquet(_EK2B_HISTORY)
    missing = sorted(set(_ADDED_2026) - set(history["code"].to_list()))
    assert not missing, missing
