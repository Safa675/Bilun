"""SGK's weekly EK-4A announcement workbooks are read exactly or refused."""

from __future__ import annotations

import datetime as dt
import hashlib
import json
from pathlib import Path

import pandas as pd
import pytest

from scripts.sut.catalogs.ek4a_announcements import load_announcements, read_workbook

pytestmark = pytest.mark.unit

PROJECT_ROOT = Path(__file__).resolve().parents[3]
EFFECTIVE = dt.date(2026, 10, 9)
HEADER = [
    "Kamu No", "Güncel Barkod", "İlaç Adı", "Eski Barkod-1", "Eski Barkod-2", "Eşdeğer İlaç Grubu",
    "Terapötik Referans Grubu", "Listeye Giriş Tarihi", "Aktiflenme Tarihi", "Pasiflenme Tarihi",
    "Uygulanan İndirim Oranlarına Esas Durumu", "Band 1", "Band 2", "Band 3", "Band 4", "Özel İskonto",
    "Eczacı İskonto Oranı ", " Band Hesabı Takibinin Başlangıç Tarihi", "Dağıtım Belgesi Son Tarihi",
]
OLD_HEADER = (HEADER[:2] + ["Ürün Adı"] + HEADER[3:5] + ["Eşdeğer (Benzer) Ürün Grubu", "Referans Fiyat Grubu"]
              + HEADER[7:10] + ["Orijinal / Jenerik / Yirmi Yıllık"] + HEADER[11:16] + ["Eczacı İndirim Oranı"])


def _drug(kamu_no: str | None, **changes) -> list:
    row = [kamu_no, "8690000000001", "NEW DRUG 10 MG", "8690000000002", None, "E001A", None,
           dt.datetime(2026, 10, 9), None, None, "EŞDEĞER", 0.28, 0.18, 0.1, 0, None, "0-2,5%", None, None]
    for index, value in changes.items():
        row[int(index[1:])] = value
    return row


def _workbook(path: Path, sheets: dict[str, list[list]], header: list = HEADER) -> Path:
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        for name, rows in sheets.items():
            frame = pd.DataFrame([["EK-1"], ["BEDELİ ÖDENECEK İLAÇLAR LİSTESİ"], header, *rows])
            frame.to_excel(writer, sheet_name=name, header=False, index=False)
    return path


def test_change_sheets_give_complete_rows_and_the_removal_sheet_gives_kamu_numbers(tmp_path: Path) -> None:
    path = _workbook(tmp_path / "a.xlsx", {
        "4A EKLENENLER": [_drug("A00001")],
        "4A PASİFLENENLER": [_drug("A00002", c9=dt.datetime(2026, 10, 9))],
        "4A ÇIKARILAN İLAÇLAR": [["A00003", "8690000000003", "OLD DRUG"]],
        "4H EKLENENLER": [["A99999", "8690000000009"]],  # another annex: ignored
    })
    upserts, removals = read_workbook(path, EFFECTIVE)
    first = upserts[0]
    assert (first["kamu_no"], first["old_barcodes"], first["entry_date"]) == ("A00001", "8690000000002", "2026-10-09 00:00:00")
    assert [first[f"discount_tier_{tier}"] for tier in range(1, 5)] == ["0.28", "0.18", "0.1", "0"]
    assert (first["special_discount"], first["pharmacist_discount"], first["effective"]) == ("", "0-2,5%", "2026-10-09")
    assert upserts[1]["passivation_date"] == "2026-10-09 00:00:00"
    assert removals == ("A00003",)


def test_star_rows_take_the_date_of_their_sheet_note(tmp_path: Path) -> None:
    path = _workbook(tmp_path / "a.xlsx", {
        "4A PASİFLENENLER": [_drug("A00001", c2="OLD DRUG 5 MG*", c9=dt.datetime(2026, 8, 29)), _drug("A00002"),
                             ["NOT: Yanında * işareti bulunan ilaçlar için yürürlük tarihi 29.08.2026 dır."]],
        "Ek-4A Eklenen": [_drug("A00003", c7="*"), [None, None, "* Bu düzenlemeler yayım tarihini takip eden "
                                                            "ilk iş günü yürürlüğe girecektir."]],
    })
    rows = {row["kamu_no"]: row for row in read_workbook(path, EFFECTIVE)[0]}
    assert (rows["A00001"]["drug_name"], rows["A00001"]["effective"]) == ("OLD DRUG 5 MG", "2026-08-29")
    assert rows["A00002"]["effective"] == "2026-10-09"
    assert (rows["A00003"]["entry_date"], rows["A00003"]["effective"]) == ("2026-10-09 00:00:00", "2026-10-09")


def test_older_header_labels_in_the_same_columns_are_accepted(tmp_path: Path) -> None:
    path = _workbook(tmp_path / "a.xlsx", {"4A PASIFLENEN İLAÇLAR": [_drug("A00001")]}, OLD_HEADER)
    assert read_workbook(path, EFFECTIVE)[0][0]["discount_status"] == "EŞDEĞER"


@pytest.mark.parametrize("sheets,header,message", [
    ({"4A YENİ SAYFA": [_drug("A00001")]}, HEADER, "Unknown EK-4A announcement sheet"),
    ({"4A EKLENENLER": [_drug("A00001")]}, HEADER[:2] + ["Ad"] + HEADER[3:], "unexpected header"),
    ({"4A EKLENENLER": [_drug("A00001")], "4A DÜZENLENENLER": [_drug("A00001", c2="OTHER")]}, HEADER, "two different rows"),
    ({"4A EKLENENLER": [_drug("A00001")], "4A ÇIKARILANLAR": [["A00001"]]}, HEADER, "both changes and removes"),
    ({"4A EKLENENLER": [_drug(None)]}, HEADER, "neither a drug nor a note"),
    ({"4A EKLENENLER": [_drug("A00001", c2="DRUG*")]}, HEADER, "has a '\\*' but its sheet no note"),
    ({"4A EKLENENLER": [_drug("A00001"), ["NOT: * işaretli ilaçlar ayrıca duyurulacaktır."]]}, HEADER, "gives '\\*' no date"),
])
def test_unknown_format_or_contradiction_is_refused(tmp_path: Path, sheets: dict, header: list, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        read_workbook(_workbook(tmp_path / "a.xlsx", sheets, header), EFFECTIVE)


def test_identical_rows_on_two_sheets_count_once(tmp_path: Path) -> None:
    path = _workbook(tmp_path / "a.xlsx", {"4A AKTİFLENENLER": [_drug("A00001")],
                                           "4A BANT HESABINA DAHİL EDİLENLE": [_drug("A00001")]})
    assert len(read_workbook(path, EFFECTIVE)[0]) == 1


def test_manifest_pins_both_files_and_the_list_that_includes_it(tmp_path: Path) -> None:
    workbook = _workbook(tmp_path / "a.xlsx", {"4A EKLENENLER": [_drug("A00001")]})
    notice = tmp_path / "a.pdf"
    notice.write_bytes(b"%PDF notice")
    entry = {"number": "2026/40", "published": "2026-10-14", "effective": "2026-10-16",
             "workbook": "a.xlsx", "notice": "a.pdf", "folded_into_list": "2026-11-01",
             "workbook_sha256": hashlib.sha256(workbook.read_bytes()).hexdigest(),
             "notice_sha256": hashlib.sha256(notice.read_bytes()).hexdigest()}
    manifest = tmp_path / "ek4a_announcements.json"
    manifest.write_text(json.dumps([entry]))
    [announcement] = load_announcements(manifest, tmp_path)
    assert (announcement.number, announcement.effective, announcement.folded_into) == (
        "2026/40", dt.date(2026, 10, 16), dt.date(2026, 11, 1))
    notice.write_bytes(b"%PDF changed")
    with pytest.raises(ValueError, match="notice does not match"):
        load_announcements(manifest, tmp_path)
    assert load_announcements(tmp_path / "missing.json", tmp_path) == []


def test_official_announcements_since_the_2026_08_29_list() -> None:
    loaded = load_announcements(PROJECT_ROOT / "data/gazette/ek4a_announcements.json", PROJECT_ROOT)
    summary = [(a.number, a.effective.isoformat(), a.folded_into and a.folded_into.isoformat(),
                len(a.upserts), len(a.removals)) for a in loaded]
    assert summary == [
        ("2026/34", "2026-09-04", "2026-10-02", 20, 2),
        ("2026/35", "2026-09-11", "2026-10-02", 6, 0),
        ("2026/36", "2026-09-18", "2026-10-02", 44, 0),
        ("2026/37", "2026-09-25", "2026-10-02", 4, 0),
        ("olağanüstü 2026/2", "2026-09-28", None, 1, 0),  # not in the 2026-10-02 list
        ("2026/38", "2026-10-02", None, 6, 0),  # not in the 2026-10-02 list either
        ("2026/39", "2026-10-09", None, 167, 1),
    ]
    starred = [row for row in loaded[0].upserts if row["effective"] == "2026-08-29"]
    assert len(starred) == 14  # 2026/34's note: '*' passivations apply from 29.08.2026
