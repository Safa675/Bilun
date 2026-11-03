"""Amendment markers in SUT list cells: EK-2B keeps marked rows (#226) and every
curated row applies from its own Yürürlük date (#227), in every list that has them (#291)."""

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
    _add_list_validity,
    _add_validity_ranges,
    amendment_markers,
)
from scripts.sut.catalogs.hierarchical_materials import extract_ek3o
from scripts.sut.catalogs.orthopedic_materials import extract_ek3f4
from scripts.sut.catalogs.price_history import extract_ek2b, extract_ek2c_dental
from src.bilun.domain.materials.catalog_lookup import lookup_ek3_list_price_try

pytestmark = pytest.mark.unit

_REPO = Path(__file__).resolve().parents[3]
_CURATED = _REPO / "data/gazette/curated"
_EK2B_HISTORY = _CURATED / "ek2b_catalog_history.parquet"
_ADDED = "(Ek: RG-29/08/2026- 33355/ 14-a md. Yürürlük: 05/09/2026)"
_AMENDED = "(Değişik: RG-29/08/2026- 33355/ 14-ş md. Yürürlük: 05/09/2026)"
_REPEALED = "(Mülga: RG-08/04/2026- 33218/ 10-b md. Yürürlük: 16/04/2026)"
# The 30 procedures SGK added to the EK-2B list effective 2026-07-07 (#226).
_ADDED_2026 = (
    "603331 603332 603551 603881 603951 604001 608481 608671 608681 608991 608992 609131 "
    "609541 609892 609893 609894 609912 609951 610231 610271 610272 610273 610362 610481 "
    "610482 610483 618571 618862 702883 801531"
).split()


def _ek2b_list(*rows: tuple[str | None, str, float | str | None]) -> pd.DataFrame:
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


def test_amended_row_replaces_the_clean_row_that_starts_on_the_same_day() -> None:
    # An amendment in force when its list starts: both rows start on the list's date.
    in_force_at_start = "(Değişik: RG-29/06/2026- 33295/ 9-a md. Yürürlük: 07/07/2026)"
    history = _history(
        ("2026-01-31", _ek2b_list(("702820", "Poligrafik uyku tetkiki", 1192.33))),
        ("2026-07-07", _ek2b_list(
            ("702820", "Poligrafik uyku tetkiki", 1192.33),
            (f"702820 {in_force_at_start}", "Uyku tetkiki", 1192.33),
        )),
    )
    assert history.loc[history["effective_date"] == "2026-07-07", "name"].tolist() == ["Uyku tetkiki"]
    assert not set(history.columns) & {MARKER_FROM, MARKER_ADDED, MARKER_REPEALED, MARKER_UNDATED}


def test_curated_ek2b_has_the_procedures_added_by_marked_rows() -> None:
    history = pl.read_parquet(_EK2B_HISTORY)
    missing = sorted(set(_ADDED_2026) - set(history["code"].to_list()))
    assert not missing, missing


def _rows(frame: pd.DataFrame, *columns: str) -> list[list[object]]:
    """The columns' values row by row, None for a missing value."""
    part = frame[list(columns)].astype(object)
    return part.where(part.notna(), None).values.tolist()


def _in_force(history: pd.DataFrame, day: str) -> pd.DataFrame:
    keep = history["valid_from"].isna() | (history["valid_from"] <= day)
    return history[keep & (history["valid_to"].isna() | (history["valid_to"] >= day))]


def test_row_marked_after_its_list_date_applies_from_its_yururluk_date() -> None:
    history = _history(
        ("2026-01-31", _ek2b_list(("701223", "Endobronşial Ultrasonografi", 2223.46))),
        ("2026-07-07", _ek2b_list(
            ("701223", "Endobronşial Ultrasonografi", 2223.46),
            (f"701223 {_AMENDED}", "Endobronşial Ultrasonografi (EBUS) eşliğinde biyopsi", 2223.46),
            (f"603331      {_ADDED}", "Mediastinal malign tümör eksizyonu (torakoskopik)", 26822.66),
        )),
    )
    on_list_date = _in_force(history, "2026-07-07").set_index("code")["name"].to_dict()
    on_marker_date = _in_force(history, "2026-09-05").set_index("code")["name"].to_dict()
    assert on_list_date == {"701223": "Endobronşial Ultrasonografi"}
    assert on_marker_date == {
        "701223": "Endobronşial Ultrasonografi (EBUS) eşliğinde biyopsi",
        "603331": "Mediastinal malign tümör eksizyonu (torakoskopik)",
    }
    assert _rows(history, "code", "effective_date", "valid_from", "valid_to") == [
        ["603331", "2026-07-07", "2026-09-05", None],
        ["701223", "2026-01-31", "2026-01-31", "2026-07-06"],
        ["701223", "2026-07-07", "2026-07-07", "2026-09-04"],
        ["701223", "2026-07-07", "2026-09-05", None],
    ]


def test_amended_row_without_a_clean_row_keeps_the_previous_list_until_its_date() -> None:
    history = _history(
        ("2026-01-31", _ek2b_list(("702820", "Poligrafik uyku tetkiki", 1100.0))),
        ("2026-07-07", _ek2b_list((f"702820 {_AMENDED}", "Uyku tetkiki", 1192.33))),
    )
    assert _rows(history, "valid_from", "valid_to", "puan") == [
        ["2026-01-31", "2026-09-04", 1100.0],
        ["2026-09-05", None, 1192.33],
    ]
    assert _in_force(history, "2026-08-01")["puan"].tolist() == [1100.0]


def test_repealed_row_ends_the_day_before_its_yururluk_date() -> None:
    history = _history(
        ("2026-01-31", _ek2b_list((f"617710 {_REPEALED}", "Silikon yağı çıkarılması", 11160.71))),
        ("2026-07-07", _ek2b_list(("510010", "Standart yatak tarifesi", 374.97))),
    )
    row = history[history["code"] == "617710"]
    assert _rows(row, "valid_from", "valid_to") == [["2026-01-31", "2026-04-15"]]


def test_rows_that_cannot_apply_within_their_list_are_dropped() -> None:
    beyond_next_list = "(Değişik: RG- 04/05/2024- 32536/1 md. Yürürlük: 11/05/2024)"
    unreadable = "(Ek: RG- /03/2025- 328../ 11-ç md. Yürürlük: 5 iş/02/2025)"
    history = _history(
        ("2023-09-02", _ek2b_list(
            (f"530000 {beyond_next_list}", "Acil serviste kritik hasta yatak ve takibi", 208.32),
            (f"801663 {unreadable}", "Tarihi okunamayan işlem", 1.0),
            ("510010", "Standart yatak tarifesi", 100.0),
        )),
        ("2024-05-11", _ek2b_list(("530000", "Acil serviste kritik hasta yatak ve takibi", 300.0))),
    )
    assert _rows(history, "code", "effective_date") == [
        ["510010", "2023-09-02"],
        ["530000", "2024-05-11"],
    ]


def test_single_list_dates_added_amended_and_repealed_rows() -> None:
    frame = pd.DataFrame({
        "sut_code": ["HO1005", "HO1005", "HO1034", "HO1099", "HO2000"],
        "price_try": [2134.44, 2116.57, 4600.0, 10.0, 5.0],
    })
    cells = pd.Series(["HO1005", f"HO1005 {_AMENDED}", f"HO1034 {_ADDED}", f"HO1099 {_AMENDED}", f"HO2000 {_REPEALED}"])
    dated = _add_list_validity(frame.join(amendment_markers(cells)), ["sut_code"])
    assert _rows(dated, "sut_code", "valid_from", "valid_to") == [
        ["HO1005", None, "2026-09-04"],
        ["HO1005", "2026-09-05", None],
        ["HO1034", "2026-09-05", None],
        ["HO1099", None, None],  # amended, but the list has no older row it replaces
        ["HO2000", None, "2026-04-15"],
    ]


def test_ek3o_clause_added_by_a_marker_applies_from_its_date() -> None:
    clause = "(Ek: RG-02/10/2026-33388/5 md. Yürürlük: 08/10/2026)"
    raw = pd.DataFrame({
        "EK-3/O": ["SUT KODU", None, "HO1000", f" HO1034      {_ADDED}"],
        "Unnamed: 1": ["TIBBİ MALZEME ALAN TANIMI", "AFEREZ", "FOTOFEREZ SETİ", "SPD SET"],
        "Unnamed: 2": [
            "AÇIKLAMA", None,
            f"(1) Onay ile karşılanır.\n(2) Sadece 704940 işlem kodunda.   {clause}   (3) SUT’un 2.4.4.Ç maddesine bakınız.",
            "(1) Rapor ile karşılanır.",
        ],
        "Unnamed: 3": ["FİYAT (TL)", None, "10907.76", "4600"],
    })
    out = extract_ek3o(raw)
    assert out["sut_code"].tolist() == ["HO1000", "HO1000", "HO1034"]
    assert out.loc[0, "description"].endswith("(2) Sadece 704940 işlem kodunda.")
    assert out.loc[1, "description"].endswith("(3) SUT’un 2.4.4.Ç maddesine bakınız.")
    assert _rows(out, "valid_from", "valid_to") == [
        [None, "2026-10-07"],
        ["2026-10-08", None],
        ["2026-09-05", None],
    ]


def test_curated_609541_is_in_ek2b_and_ek2c_from_2026_10_10() -> None:
    ek2b = pl.read_parquet(_EK2B_HISTORY).filter(pl.col("code") == "609541")
    ek2c = pl.read_parquet(_CURATED / "ek2c_catalog_history.parquet").filter(pl.col("package_code") == "P609541")
    for rows in (ek2b, ek2c):
        assert rows.select("effective_date", "valid_from", "valid_to").rows() == [("2026-07-07", "2026-10-10", None)]


def test_curated_histories_start_each_marked_2026_07_07_row_on_its_own_date() -> None:
    ek2b = pl.read_parquet(_EK2B_HISTORY).filter(pl.col("effective_date") == "2026-07-07")
    moved = ek2b.filter(pl.col("valid_from") != pl.col("effective_date"))
    assert dict(moved.group_by("valid_from").len().rows()) == {"2026-07-14": 1, "2026-09-05": 48, "2026-10-10": 2}
    assert set(_ADDED_2026) <= set(moved["code"].to_list())


def test_curated_ek1a_and_ek3o_carry_the_dates_of_their_markers() -> None:
    ek1a = pl.read_parquet(_CURATED / "ek1a_chronic_exemptions.parquet")
    dated = ek1a.filter(pl.col("valid_from").is_not_null() | pl.col("valid_to").is_not_null())
    assert sorted(dated.select("icd10_start", "valid_from", "valid_to").rows()) == [
        ("G11.3", "2018-02-15", None),
        ("N04", "2015-08-05", None),
        ("Q05", "2015-08-05", None),
        ("Q78", "2015-08-05", None),
    ]
    ek3o = pl.read_parquet(_CURATED / "ek3o_hematology_oncology_materials.parquet")
    dated = ek3o.filter(pl.col("valid_from").is_not_null() | pl.col("valid_to").is_not_null())
    assert dated.select("sut_code", "valid_from", "valid_to").rows() == [
        ("HO1000", None, "2026-10-07"),
        ("HO1000", "2026-10-08", None),
        ("HO1005", None, "2026-09-04"),
        ("HO1005", "2026-09-05", None),
        ("HO1017", None, "2026-09-04"),
        ("HO1017", "2026-09-05", None),
        ("HO1034", "2026-09-05", None),
    ]
    assert not ek3o.filter(pl.col("sut_code").str.contains(r"\(")).height


def test_puan_typed_in_turkish_format_is_read() -> None:
    out = extract_ek2b(_ek2b_list(
        ("702882", "Çoklu Uyku Latansı Testi (ÇULT-MSLT)", "\xa01.291,70"),
        ("701362", "Kolanjioskopi eşliğinde biyopsi", "869,19\xa0"),
        (f"801561 {_AMENDED}", "Kemik yaşı tayini", "\xa0\xa0\xa0 60,54"),
        ("510010", "Standart yatak tarifesi", "374.97"),
    ))
    assert out["puan"].tolist() == [1291.70, 869.19, 60.54, 374.97]


def test_curated_rows_with_a_turkish_formatted_puan_are_priced() -> None:
    ek2b = pl.read_parquet(_EK2B_HISTORY).filter(pl.col("code").is_in(["701362", "702882", "801561"]))
    ek2c = pl.read_parquet(_CURATED / "ek2c_catalog_history.parquet").filter(pl.col("package_code") == "P609231")
    assert ek2b["puan"].null_count() == 0 and ek2c["puan"].null_count() == 0
    priced = ek2b.filter(pl.col("valid_from") == "2025-03-15").select("code", "puan", "valid_to").rows()
    assert priced == [("801561", 60.54, "2025-12-31")]


# EK-2Ç (dental) keeps its markers like EK-2B (#293): RG-12/12/2024 amended, added and repealed
# rows of the list in force since 11/05/2024, each from Yürürlük 20/12/2024.
_DENTAL_AMENDED = "(Değişik: RG- 12/12/2024- 32750/ 15-a md. Yürürlük: 20/12/2024)"
_DENTAL_ADDED = "(Ek: RG- 12/12/2024- 32750/ 15-b md. Yürürlük: 20/12/2024)"
_DENTAL_REPEALED = "(Mülga: RG- 12/12/2024- 32750/ 15-ç md. Yürürlük: 20/12/2024)"
# (list date, valid_from, rows) of the committed rows a marker starts after their list's date:
# the 45 dated Ek/Değişik cells of the 2024-05-11 list (RG-25/09/2024, RG-12/12/2024 and
# 403010's RG-08/03/2025) and the 3 of the 2026-01-01 list (RG-17/01/2026).
_DENTAL_MOVED = [
    ("2024-05-11", "2024-10-03", 7),
    ("2024-05-11", "2024-12-20", 37),
    ("2024-05-11", "2025-03-15", 1),
    ("2026-01-01", "2026-01-31", 3),
]


def _ek2c_dental_list(*rows: tuple[str | None, str, float | None]) -> pd.DataFrame:
    """A raw EK-2Ç partition: the title column, the header row, then (code cell, name, puan)."""
    header = ("İŞLEM KODU", "İŞLEM ADI", "AÇIKLAMALAR", "İŞLEM PUANI")
    body = [header, *((code, name, None, puan) for code, name, puan in rows)]
    columns = ["DİŞ TEDAVİLERİ PUAN LİSTESİ (EK-2/Ç)", "Unnamed: 1", "Unnamed: 2", "Unnamed: 3"]
    return pd.DataFrame(body, columns=columns).astype(object)


_DENTAL_2024 = _ek2c_dental_list(
    ("402150", "Kanal tedavisi, tek kanal", 1222.74),
    (f"402150 {_DENTAL_AMENDED}", "Kanal tedavisi, tek kanal", 959.04),
    (f"402251     {_DENTAL_ADDED}", "Gangren veya periapikal lezyon tedavisi, tek kanal", 73.01),
    (f"402270 {_DENTAL_REPEALED}", "Gangren veya periapikal lezyon tedavisi, tek kanal", 299.64),
    (_DENTAL_ADDED, "Kanal tedavileri", None),  # a heading row carries a marker but no code
)


def test_ek2c_dental_row_keeps_the_marker_of_its_code_cell() -> None:
    out = extract_ek2c_dental(_DENTAL_2024)
    assert out["code"].tolist() == ["402150", "402150", "402251", "402270"]
    assert out["puan"].tolist() == [1222.74, 959.04, 73.01, 299.64]
    day = pd.Timestamp("2024-12-20")
    assert _rows(out, MARKER_FROM, MARKER_ADDED, MARKER_REPEALED, MARKER_UNDATED) == [
        [None, False, None, False],
        [day, False, None, False],
        [day, True, None, False],
        [None, False, day, False],
    ]


def test_ek2c_dental_history_dates_each_marked_row_by_its_yururluk_date() -> None:
    lists = (
        ("2023-09-02", _ek2c_dental_list(
            ("402150", "Kanal tedavisi, tek kanal", 815.16),
            ("402270", "Gangren veya periapikal lezyon tedavisi, tek kanal", 199.76),
        )),
        ("2024-05-11", _DENTAL_2024),
        ("2026-01-01", _ek2c_dental_list(
            ("402150", "Kanal tedavisi, tek kanal", 1150.848),
            ("402251", "Gangren veya periapikal lezyon tedavisi, tek kanal", 87.612),
        )),
    )
    frames = [extract_ek2c_dental(raw).assign(effective_date=day) for day, raw in lists]
    history = _add_validity_ranges(pd.concat(frames, ignore_index=True), "code")
    assert _rows(history, "code", "puan", "effective_date", "valid_from", "valid_to") == [
        ["402150", 815.16, "2023-09-02", "2023-09-02", "2024-05-10"],
        ["402150", 1222.74, "2024-05-11", "2024-05-11", "2024-12-19"],
        ["402150", 959.04, "2024-05-11", "2024-12-20", "2025-12-31"],
        ["402150", 1150.848, "2026-01-01", "2026-01-01", None],
        ["402251", 73.01, "2024-05-11", "2024-12-20", "2025-12-31"],
        ["402251", 87.612, "2026-01-01", "2026-01-01", None],
        ["402270", 199.76, "2023-09-02", "2023-09-02", "2024-05-10"],
        ["402270", 299.64, "2024-05-11", "2024-05-11", "2024-12-19"],
    ]


def test_curated_ek2c_dental_rows_carry_the_dates_of_their_markers() -> None:
    dental = pl.read_parquet(_CURATED / "ek2c_dental_catalog_history.parquet")
    moved = dental.filter(pl.col("valid_from") != pl.col("effective_date"))
    assert sorted(moved.group_by("effective_date", "valid_from").len().rows()) == _DENTAL_MOVED
    repealed = dental.filter(pl.col("code").is_in(["402270", "402271", "402272", "402273"]))
    assert repealed.group_by("code").agg(pl.col("valid_to").max()).sort("code")["valid_to"].to_list() == [
        "2024-12-19"
    ] * 4


# #291: the EK-3 material lists, EK-2G and EK-2C-1 keep only the code of a marked code cell and date the row
# by its marker, as EK-2B and EK-3O do. Their code columns, in every curated list.
_CODE_COLUMNS = ("sut_code", "procedure_code", "code", "package_code")


def test_no_curated_code_cell_carries_an_amendment_marker() -> None:
    marked = {}
    for path in sorted(_CURATED.glob("*.parquet")):
        frame = pl.read_parquet(path)
        for column in set(_CODE_COLUMNS) & set(frame.columns):
            cells = frame[column].cast(pl.String)
            hits = cells.filter(cells.str.contains(r"(?i)RG\s*-|Y[üu]r[üu]rl[üu]k")).to_list()
            if hits:
                marked[f"{path.name}:{column}"] = hits
    assert not marked, marked


def test_curated_ek3_rows_apply_from_the_date_of_their_code_cell_marker() -> None:
    def rows(name: str, code: str) -> list[tuple]:
        frame = pl.read_parquet(_CURATED / name).filter(pl.col("sut_code") == code)
        return frame.select("valid_from", "valid_to", "price_try").rows()

    # Değişik RG-29/06/2026 (Yürürlük 07/07/2026): the list keeps the old price beside the new one.
    assert rows("ek3t_anesthesiology_materials.parquet", "AN1210") == [
        (None, "2026-07-06", 558.80825),
        ("2026-07-07", None, 1117.62),
    ]
    assert [lookup_ek3_list_price_try("AN1210", day) for day in ("2026-07-06", "2026-07-07")] == [558.80825, 1117.62]
    # Ek RG-17/01/2026 (Yürürlük 31/01/2026) adds KR4003; Mülga RG-29/06/2026 repeals 102495 from 07/07/2026.
    assert rows("ek3h_cardiology_materials.parquet", "KR4003") == [("2026-01-31", None, 50450.4)]
    assert [lookup_ek3_list_price_try("KR4003", day) for day in ("2026-01-30", "2026-01-31")] == [None, 50450.4]
    assert [day for day, _, _ in rows("ek3e1_spine_surgery_materials.parquet", "102495")] == [None]
    assert lookup_ek3_list_price_try("102495", "2026-07-06") is not None
    assert lookup_ek3_list_price_try("102495", "2026-07-07") is None


def test_ek3f_degisik_marker_in_a_text_cell_dates_only_a_row_the_list_keeps_an_older_one_of() -> None:
    changed = "(Değişik:RG-17/01/2026-33140/14 md. Yürürlük:24/01/2026)   CoCr /TİTANYUM CoCr"
    raw = pd.DataFrame(
        [
            ["SUT KODU", "TIBBİ MALZEME ALAN TANIMI", None, None, "FİYAT (TL)"],
            [None, "OPERASYON BÖLGESİ", "BİÇİM", "MATERYAL", None],
            [None, "ORTAK KULLANIM", None, None, None],
            ["TV5680", "ORTAK KULLANIM", "PİNLER", "BİYOÇÖZÜNÜR", "2658.90625"],
            ["TV5680", "ORTAK KULLANIM", "PİNLER", changed, "2700.00"],
            ["AP1880", "KALÇA", "FEMORAL BIPOLAR BAŞ", changed, "5391.8865"],
        ],
        columns=["SUT KODU", "Unnamed: 1", "Unnamed: 2", "Unnamed: 3", "Unnamed: 4"],
    )
    out = extract_ek3f4(raw)
    assert _rows(out, "sut_code", "valid_from", "valid_to", "price_try") == [
        ["TV5680", None, "2026-01-23", 2658.90625],
        ["TV5680", "2026-01-24", None, 2700.0],
        ["AP1880", None, None, 5391.8865],  # amended, but the list has no older row it replaces
    ]
    assert out.loc[2, "description"] == f"FEMORAL BIPOLAR BAŞ | {changed}"  # the text stays as SGK wrote it
