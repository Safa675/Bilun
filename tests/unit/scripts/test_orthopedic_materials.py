"""EK-3/F orthopedic material lists: a coded row is a material even with a blank first cell."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from scripts.sut.catalogs.orthopedic_materials import extract_ek3f1

pytestmark = pytest.mark.unit

_CURATED = Path(__file__).resolve().parents[3] / "data/gazette/curated/ek3f1_arthroplasty_materials.parquet"


def test_coded_row_with_a_blank_site_cell_is_kept() -> None:
    raw = pd.DataFrame(
        [
            ["SUT KODU", "TIBBİ MALZEME ALAN TANIMI", None, None, "FİYAT (TL)"],
            [None, "UYGULAMA YERİ", "CERRAHİ YÖNTEM", "ÜRÜN TANIMI", None],
            [None, "KALÇA", None, None, None],  # no code: a category row
            ["AP2000", "KALÇA", "PRİMER", "FEMORAL STEM", "6465.27"],
            ["AP3220", None, "PRİMER/REVİZYON", "KEMİK ÇİMENTOSU - NORMAL", "492.85"],
            [None, None, None, None, None],
        ],
        columns=["SUT KODU", "Unnamed: 1", "Unnamed: 2", "Unnamed: 3", "Unnamed: 4"],
    )
    out = extract_ek3f1(raw)
    assert out[["sut_code", "material_name", "description", "category"]].values.tolist() == [
        ["AP2000", "KALÇA", "PRİMER | FEMORAL STEM", "KALÇA"],
        ["AP3220", "", "PRİMER/REVİZYON | KEMİK ÇİMENTOSU - NORMAL", "KALÇA"],
    ]


def test_curated_ek3f1_lists_the_bone_cements_in_force() -> None:
    curated = pd.read_parquet(_CURATED)
    cements = curated[curated["description"].str.contains("KEMİK ÇİMENTOSU")].set_index("sut_code")
    assert cements.index.tolist() == [f"AP3{n}" for n in range(180, 260, 10)]
    assert cements.loc["AP3220", "price_try"] == pytest.approx(492.848125)
    assert (cements["material_name"] == "").all()
