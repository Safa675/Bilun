"""Synthetic material line prose flags (L1.4 ingest)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

SYNTHETIC_DIR = Path(__file__).resolve().parents[3] / "scripts" / "synthetic"
if str(SYNTHETIC_DIR) not in sys.path:
    sys.path.insert(0, str(SYNTHETIC_DIR))

from generators import MATERIAL_PROSE_FLAG_COLUMNS, build_workbook_tables  # noqa: E402


def test_material_lines_include_prose_flag_columns() -> None:
    tables = build_workbook_tables(num_patients=10, seed=20260504)
    materials = tables["malzeme_fatura_satirlari"]
    assert not materials.empty

    for col in MATERIAL_PROSE_FLAG_COLUMNS:
        assert col in materials.columns


def test_material_lines_cover_each_prose_flag_demo_row() -> None:
    tables = build_workbook_tables(num_patients=10, seed=20260504)
    materials = tables["malzeme_fatura_satirlari"]

    assert (~materials["titubb_kayitli_mi"].astype(bool)).any()
    assert (~materials["uts_kayitli_mi"].astype(bool)).any()
    assert materials["ihale_ekrani_eksik_mi"].astype(bool).any()
    assert materials["bagli_islem_odenmez"].astype(bool).any()
    assert materials["yurtdisi_kurum"].astype(bool).any()
    assert materials["kurum_islem_kisiti_ihlali"].astype(bool).any()
    assert materials["tani_medula_paket_ayri_fatura_yok"].astype(bool).any()
    assert materials["ihale_fiyat_referansi_yetersiz"].astype(bool).any()
    assert materials["medula_kod_tarihte_tanimsiz"].astype(bool).any()
    assert materials["barkod_sut_uyumsuz"].astype(bool).any()
    assert materials["tani_paket_malzeme_kapsam"].astype(bool).any()
    assert materials["capraz_brans_fatura_ihlali"].astype(bool).any()
    assert materials["ortez_protez_sozlesme_ihlali"].astype(bool).any()


def test_committed_synthetic_claims_parquet_has_prose_columns() -> None:
    import pandas as pd

    root = Path(__file__).resolve().parents[3]
    path = root / "data" / "synthetic" / "sut" / "claims" / "material_claim_lines.parquet"
    if not path.exists():
        pytest.skip("Committed synthetic claims not present")

    df = pd.read_parquet(path)
    for col in (
        "titubb_registered",
        "procurement_record_incomplete",
        "foreign_facility",
    ):
        assert col in df.columns
    assert df["foreign_facility"].astype(bool).any()
