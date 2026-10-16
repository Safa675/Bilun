"""EK-2/A-2 history: the list that decides an outpatient package (Safa, 2026-10-16).

SUT §2.2.1.B-1(10)(a) (C000581, C000582): an outpatient EK-2/C procedure is billed as
its package only when it is on EK-2/A-2. The curated history dates every row from its
list's date or its own Yürürlük marker, as EK-2B and EK-2C are (#227).
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import polars as pl
import pytest
from polars.testing import assert_frame_equal

from scripts.sut._common import MARKER_FROM, MARKER_REPEALED, _add_validity_ranges
from scripts.sut.catalogs.outpatient_procedures import extract_ek2a2
from src.bilun.domain.loaders.ek2a2 import EK2A2_CURATED_HISTORY_PATH, ek2a2_codes_as_of

pytestmark = pytest.mark.unit

_REPO = Path(__file__).resolve().parents[3]
_RAW = _REPO / "data/gazette/raw/annex=EK-2A-2"
_COLUMNS = ["code", "name", "effective_date", "valid_from", "valid_to"]


def _ek2a2_list(*rows: tuple[str | None, str]) -> pd.DataFrame:
    """A raw EK-2A-2 partition: the title column, the header row, then (code cell, name)."""
    body = [("İŞLEM KODU", "İŞLEM ADI", "AÇIKLAMA"), *((code, name, None) for code, name in rows)]
    columns = [
        "AYAKTAN BAŞVURULARDA İLAVE OLARAK FATURALANDIRILACAK İŞLEMLER LİSTESİ  (EK-2/A-2)",
        "Unnamed: 1",
        "Unnamed: 2",
    ]
    return pd.DataFrame(body, columns=columns).astype(object)


def test_extractor_keeps_coded_rows_with_their_markers() -> None:
    out = extract_ek2a2(_ek2a2_list(
        ("608310", "Bronkoskopi, tanısal"),
        ("800931    (Ek: RG-08/04/2026- 33218/ 8-a md. Yürürlük: 16/04/2026)", "Kolin PET"),
        ("802220  (Mülga: RG-08/04/2026- 33218 8-b md. Yürürlük: 16/04/2026)", "Oral kolesistografi"),
        # Rows naming a whole EK-2/B section hold no code.
        ("(Ek:RG- 08/02/2022- 31744 /  9-a md.  Yürürlük: 16/02/2022)",
         "SUT eki EK-2/B Listesinde yer alan “9.C. MOLEKÜLER GENETİK TETKİKLER” başlığındaki tetkikler"),
        (None, 'SUT eki EK-2/B Listesinde yer alan "8.3.1. BİLGİSAYARLI TOMOGRAFİ (BT)" başlığındaki tetkikler'),
        ("L100000", "1,25-Dihidroksi vitamin D"),
    ))
    assert out["code"].tolist() == ["608310", "800931", "802220", "L100000"]
    assert str(out.loc[1, MARKER_FROM].date()) == "2026-04-16"
    assert str(out.loc[2, MARKER_REPEALED].date()) == "2026-04-16"


def test_curated_history_is_the_dated_rebuild_of_the_raw_lists() -> None:
    # The dated versions: 2020-03-11 (MÜLGA) and the list in force since 2021-06-01.
    frames = [
        extract_ek2a2(pd.read_parquet(next((_RAW / f"effective_date={day}").glob("*.parquet"))))
        .assign(effective_date=day)
        for day in ("2020-03-11", "2021-06-01")
    ]
    rebuilt = _add_validity_ranges(pd.concat(frames, ignore_index=True), "code")
    expected = pl.from_pandas(rebuilt[_COLUMNS].astype("string")).sort(_COLUMNS, nulls_last=True)
    curated = pl.read_parquet(EK2A2_CURATED_HISTORY_PATH, columns=_COLUMNS)
    assert_frame_equal(curated.sort(_COLUMNS, nulls_last=True), expected)
    assert curated.height == 1035


@pytest.mark.parametrize(
    "code, valid_from, valid_to",
    [
        ("800931", "2026-04-16", None),  # Ek: RG-08/04/2026, Yürürlük 16/04/2026.
        ("802220", "2021-06-01", "2026-04-15"),  # Mülga from 16/04/2026.
        ("L107610", "2021-06-01", "2024-04-29"),  # Mülga from 30/04/2024.
        ("801592", "2025-03-15", None),  # Ek from 15/03/2025.
    ],
)
def test_curated_rows_carry_the_dates_of_their_markers(code, valid_from, valid_to) -> None:
    rows = pl.read_parquet(EK2A2_CURATED_HISTORY_PATH).filter(
        (pl.col("code") == code) & (pl.col("effective_date") == "2021-06-01"),
    )
    assert rows.select("valid_from", "valid_to").rows() == [(valid_from, valid_to)]


def test_reader_applies_each_row_on_its_own_dates() -> None:
    assert "800931" not in ek2a2_codes_as_of("2026-04-15")
    assert "800931" in ek2a2_codes_as_of("2026-04-16")
    assert "802220" in ek2a2_codes_as_of("2026-04-15")
    assert "802220" not in ek2a2_codes_as_of("2026-04-16")
    # 608310 is on every dated version; nothing is dated before the 2020-03-11 list.
    assert "608310" in ek2a2_codes_as_of("2020-03-11")
    assert ek2a2_codes_as_of("2020-03-10") == frozenset()
