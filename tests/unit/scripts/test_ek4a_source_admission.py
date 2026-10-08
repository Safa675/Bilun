"""Source-footnote admission is a snapshot gate, not a historical payment oracle."""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import pandas as pd
import pytest

from scripts.sut import build_curated_catalogs as builder
from scripts.sut.catalogs.simple_materials import extract_ek4a

pytestmark = pytest.mark.unit

PUBLICATION = dt.date(2026, 10, 2)
BOUNDARY = dt.date(2026, 10, 10)
FOOTNOTE = (
    "RG-02/10/2026- 33388/ 6 md. Yürürlük: "
    "1) Listeye giriş tarihi, aktiflenme tarihi veya pasiflenme tarihi bulunan ilaçlar belirtilen tarihlerde, "
    "2) Listeye giriş tarihi, aktiflenme tarihi veya pasiflenme tarihi bulunmayan ilaçlar yayımları tarihlerinde, "
    "3) Listeye giriş tarihinde (*) işareti bulunan ilaçlar 10/10/2026 tarihinde, "
    "4) İlaç adında (**) işareti bulunan ilaçlar 10/10/2026 tarihinde, "
    "5) İlaç adında (***) işareti bulunan ilaçlar yayımı tarihinde yürürlüğe girer."
)
PROJECT_ROOT = Path(__file__).resolve().parents[3]
OFFICIAL_RAW = PROJECT_ROOT / "data/gazette/raw/annex=EK-4A/effective_date=unknown/EK-4A_BEDELI_ODENECEK_ILACLAR_LISTESI__EK-4A.parquet"


def _source(
    *,
    kamu_no: object = "A00001",
    drug_name: str = "Example drug",
    entry_date: object = "2006-09-04 00:00:00",
    footnote: str | None = FOOTNOTE,
) -> pd.DataFrame:
    header = ["Kamu No", "Güncel Barkod", "İlaç Adı"] + [f"header{i}" for i in range(3, 16)]
    row = [kamu_no, "0001234567890", drug_name, "0001234567891\n0001234567892", "E00001", "", entry_date, "01.01.2020\n02.02.2020", "03.03.2020\n04.04.2020", "REFERANS", "0.41", "--- %", "0", "0", None, "0-2,5%"]
    rows = [header, row]
    if footnote is not None:
        rows.append([footnote] + [None] * 15)
    return pd.DataFrame(rows, columns=[f"col{i}" for i in range(16)])


@pytest.mark.parametrize("entry_date,drug_name", [("*", "Example drug"), ("2006-09-04", "Example drug**")])
@pytest.mark.parametrize("as_of", [dt.date(2006, 9, 4), PUBLICATION, dt.date(2026, 10, 5), BOUNDARY - dt.timedelta(days=1)])
def test_entry_or_exact_double_suffix_blocks_before_source_boundary(
    entry_date: str, drug_name: str, as_of: dt.date
) -> None:
    with pytest.raises(ValueError, match="preserve the prior snapshot"):
        extract_ek4a(_source(entry_date=entry_date, drug_name=drug_name), as_of=as_of)


@pytest.mark.parametrize("entry_date,drug_name", [("*", "Example drug"), ("2006-09-04", "Example drug**")])
def test_boundary_admits_current_snapshot_without_mutating_source_dates(
    entry_date: str, drug_name: str
) -> None:
    source = _source(entry_date=entry_date, drug_name=drug_name)
    before = source.copy(deep=True)
    result = extract_ek4a(source, as_of=BOUNDARY)
    assert result.loc[0, "entry_date"] == entry_date
    assert result.loc[0, "drug_name"] == drug_name
    pd.testing.assert_frame_equal(source, before)


@pytest.mark.parametrize("footnote", [
    None,
    FOOTNOTE.replace("10/10/2026", "unknown", 1),
    FOOTNOTE.replace("10/10/2026", "31/13/2026", 1),
    FOOTNOTE.replace("Listeye giriş tarihinde (*)", "Some unexplained marker (*)"),
    FOOTNOTE.split("5)")[0],
    FOOTNOTE.replace("10/10/2026", "01/10/2026", 1),
])
def test_missing_unknown_partial_invalid_or_inconsistent_footnote_fails_closed(
    footnote: str | None
) -> None:
    with pytest.raises(ValueError, match="footnote"):
        extract_ek4a(_source(entry_date="*", footnote=footnote), as_of=BOUNDARY)


def test_multiple_source_footnotes_cannot_supply_an_arbitrary_boundary() -> None:
    source = _source(entry_date="*")
    source.loc[len(source)] = [FOOTNOTE] + [None] * 15
    with pytest.raises(ValueError, match="recognized source footnote"):
        extract_ek4a(source, as_of=BOUNDARY)


def test_triple_suffix_uses_publication_not_double_suffix_date() -> None:
    source = _source(drug_name="Example drug***")
    assert extract_ek4a(source, as_of=PUBLICATION).loc[0, "drug_name"] == "Example drug***"
    with pytest.raises(ValueError, match="preserve the prior snapshot"):
        extract_ek4a(source, as_of=PUBLICATION - dt.timedelta(days=1))


def test_triple_suffix_still_requires_the_complete_publication_policy() -> None:
    with pytest.raises(ValueError, match="footnote"):
        extract_ek4a(_source(drug_name="Example drug***", footnote=None), as_of=BOUNDARY)


def test_internal_dose_asterisk_has_no_footnote_marker_meaning() -> None:
    name = "KFIBROGEN 300 MG/4 ML NEBULIZASYON COZELTISI (56*5 ML NEBUL)"
    result = extract_ek4a(_source(kamu_no="A20062", drug_name=name, footnote=None), as_of=PUBLICATION)
    assert result.loc[0, "kamu_no"] == "A20062"
    assert result.loc[0, "drug_name"] == name


def test_marker_dates_are_bound_to_their_exact_source_clause() -> None:
    different_name_date = FOOTNOTE.replace("4) İlaç adında (**) işareti bulunan ilaçlar 10/10/2026", "4) İlaç adında (**) işareti bulunan ilaçlar 11/10/2026")
    assert len(extract_ek4a(_source(entry_date="*", footnote=different_name_date), as_of=BOUNDARY)) == 1
    with pytest.raises(ValueError, match="2026-10-11"):
        extract_ek4a(_source(drug_name="Example drug**", footnote=different_name_date), as_of=BOUNDARY)


@pytest.mark.parametrize("metadata", [
    {"__is_mulga": True},
    {"__is_mulga": "True"},
    {"__is_mulga": False, "__source_file": "raw data/current/MÜLGA/EK-4A.xlsx"},
    {"__is_mulga": False, "__source_file": "raw data/current/MULGA_EK-4A.xlsx"},
])
def test_repealed_metadata_or_source_path_cannot_be_a_current_snapshot(metadata: dict) -> None:
    source = _source()
    for column, value in metadata.items():
        source[column] = value
    with pytest.raises(ValueError, match="MÜLGA"):
        extract_ek4a(source, as_of=BOUNDARY)


def test_future_source_package_blocks_even_with_nonfuture_footnote() -> None:
    source = _source(drug_name="Example drug***")
    source["__source_file"] = "raw data/2026.10.11-Değişiklik Tebliği İşlenmiş Güncel 2013 SUT/EK-4A.xlsx"
    with pytest.raises(ValueError, match="source package"):
        extract_ek4a(source, as_of=BOUNDARY)


@pytest.mark.parametrize("key", [None, pd.NA, " "])
def test_null_or_empty_drug_key_is_not_silently_dropped(key: object) -> None:
    with pytest.raises(ValueError, match="missing kamu_no"):
        extract_ek4a(_source(kamu_no=key), as_of=BOUNDARY)


def test_duplicate_normalized_drug_keys_are_rejected() -> None:
    source = _source()
    source.loc[len(source)] = source.iloc[1]
    source.loc[len(source) - 1, "col0"] = " A00001 "
    with pytest.raises(ValueError, match="unique kamu_no"):
        extract_ek4a(source, as_of=BOUNDARY)


def test_exact_keyless_majistral_summary_is_excluded_but_data_bearing_row_is_rejected() -> None:
    source = _source()
    annotation = [None] * 16
    annotation[2], annotation[9] = "ZZZ MAJISTRAL ILAC", "MAJİSTRAL"
    annotation[15] = "0-2,5%"
    source.loc[len(source)] = annotation
    assert len(extract_ek4a(source, as_of=BOUNDARY)) == 1
    source.loc[len(source) - 1, "col1"] = "0001234567890"
    with pytest.raises(ValueError, match="missing kamu_no"):
        extract_ek4a(source, as_of=BOUNDARY)


def test_barcode_strings_leading_zeros_nulls_and_history_cells_are_preserved() -> None:
    source = _source()
    source.loc[1, "col5"] = pd.NA
    result = extract_ek4a(source, as_of=BOUNDARY)
    assert result.loc[0, "barcode"] == "0001234567890"
    assert result.loc[0, "old_barcodes"] == "0001234567891\n0001234567892"
    assert result.loc[0, "equivalence_group"] == "E00001"
    assert result.loc[0, "therapeutic_group"] == ""
    assert result.loc[0, "activation_date"] == "01.01.2020\n02.02.2020"
    assert result.loc[0, "passivation_date"] == "03.03.2020\n04.04.2020"
    assert all(pd.api.types.is_string_dtype(dtype) for dtype in result.dtypes)


def test_numeric_barcode_becomes_a_string_without_changing_existing_strings() -> None:
    source = _source()
    source["col1"] = source["col1"].astype(object)
    source.loc[1, "col1"] = 1234567890123
    assert extract_ek4a(source, as_of=BOUNDARY).loc[0, "barcode"] == "1234567890123"


def test_builder_before_boundary_preserves_existing_curated_bytes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    raw = tmp_path / "raw/annex=EK-4A/effective_date=unknown/current.parquet"
    raw.parent.mkdir(parents=True)
    _source(entry_date="*").to_parquet(raw, index=False)
    output = tmp_path / "curated/ek4a_drugs.parquet"
    output.parent.mkdir()
    prior = extract_ek4a(_source(kamu_no="A00002"), as_of=PUBLICATION)
    prior.to_parquet(output, index=False, compression=None)
    before = output.read_bytes(), output.stat().st_mtime_ns
    argv = ["builder", "--parquet-root", str(tmp_path), "--annex", "EK-4A", "--overwrite", "--as-of", "2026-10-05"]
    monkeypatch.setattr("sys.argv", argv)
    assert builder.main() == 1
    assert (output.read_bytes(), output.stat().st_mtime_ns) == before
    monkeypatch.setattr("sys.argv", argv[:-1] + [BOUNDARY.isoformat()])
    assert builder.main() == 0
    assert pd.read_parquet(output).loc[0, "kamu_no"] == "A00001"
    assert pd.read_parquet(output).loc[0, "entry_date"] == "*"


def test_exact_official_raw_footer_and_current_snapshot_boundary() -> None:
    source = pd.read_parquet(OFFICIAL_RAW)
    before = source.copy(deep=True)
    footer = source.iloc[8185, 0]
    assert " ".join(footer.split()) == FOOTNOTE
    with pytest.raises(ValueError, match="2026-10-10"):
        extract_ek4a(source, as_of=dt.date(2026, 10, 5))
    admitted = extract_ek4a(source, as_of=BOUNDARY)
    assert len(admitted) == 8183
    assert admitted["kamu_no"].is_unique
    assert admitted["kamu_no"].ne("").all()
    assert admitted["entry_date"].eq("*").sum() == 3
    assert admitted["drug_name"].str.contains(r"(?<!\*)\*\*$", regex=True).sum() == 3
    assert admitted["drug_name"].str.contains(r"(?<!\*)\*\*\*$", regex=True).sum() == 1
    assert all(pd.api.types.is_string_dtype(dtype) for dtype in admitted.dtypes)
    pd.testing.assert_frame_equal(source, before)
