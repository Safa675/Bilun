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
HEADER = [
    "Kamu No", "Güncel Barkod", "İlaç Adı", "Eski Barkod-1", "Eski Barkod-2", "Eşdeğer İlaç Grubu",
    "Terapötik Referans Grubu", "Listeye Giriş Tarihi", "Aktiflenme Tarihi", "Pasiflenme Tarihi",
    "Uygulanan İndirim Oranlarına Esas Durumu", "Band 1", "Band 2", "Band 3", "Band 4", "Özel İskonto",
    "Eczacı İskonto Oranı ", " Band Hesabı Takibinin Başlangıç Tarihi", "Dağıtım Belgesi Son Tarihi",
]


def _drug(kamu_no: str, **changes) -> list:
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
        "4A EKLENENLER": [_drug("A1")],
        "4A PASİFLENENLER": [_drug("A2", c9=dt.datetime(2026, 10, 9))],
        "4A ÇIKARILAN İLAÇLAR": [["A3", "8690000000003", "OLD DRUG"]],
    })
    upserts, removals = read_workbook(path)
    first = upserts[0]
    assert (first["kamu_no"], first["old_barcodes"], first["entry_date"]) == ("A1", "8690000000002", "2026-10-09 00:00:00")
    assert [first[f"discount_tier_{tier}"] for tier in range(1, 5)] == ["0.28", "0.18", "0.1", "0"]
    assert (first["special_discount"], first["pharmacist_discount"]) == ("", "0-2,5%")
    assert upserts[1]["passivation_date"] == "2026-10-09 00:00:00"
    assert removals == ("A3",)


@pytest.mark.parametrize("sheets,header,message", [
    ({"4A YENİ SAYFA": [_drug("A1")]}, HEADER, "Unknown EK-4A announcement sheet"),
    ({"4A EKLENENLER": [_drug("A1")]}, HEADER[:2] + ["Ad"] + HEADER[3:], "unexpected header"),
    ({"4A EKLENENLER": [_drug("A1")], "4A DÜZENLENENLER": [_drug("A1", c2="OTHER NAME")]}, HEADER, "two different rows"),
    ({"4A EKLENENLER": [_drug("A1")], "4A ÇIKARILAN İLAÇLAR": [["A1"]]}, HEADER, "both changes and removes"),
    ({"4A EKLENENLER": [_drug(None)]}, HEADER, "without kamu_no"),
])
def test_unknown_format_or_contradiction_is_refused(tmp_path: Path, sheets: dict, header: list, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        read_workbook(_workbook(tmp_path / "a.xlsx", sheets, header))


def test_identical_rows_on_two_sheets_count_once(tmp_path: Path) -> None:
    path = _workbook(tmp_path / "a.xlsx", {"4A AKTİFLENENLER": [_drug("A1")], "4A BANT HESABINA DAHİL EDİLENLE": [_drug("A1")]})
    assert len(read_workbook(path)[0]) == 1


def test_manifest_pins_both_files(tmp_path: Path) -> None:
    workbook = _workbook(tmp_path / "a.xlsx", {"4A EKLENENLER": [_drug("A1")]})
    notice = tmp_path / "a.pdf"
    notice.write_bytes(b"%PDF notice")
    entry = {"number": "2026/40", "effective": "2026-10-16", "workbook": "a.xlsx", "notice": "a.pdf",
             "workbook_sha256": hashlib.sha256(workbook.read_bytes()).hexdigest(),
             "notice_sha256": hashlib.sha256(notice.read_bytes()).hexdigest()}
    manifest = tmp_path / "ek4a_announcements.json"
    manifest.write_text(json.dumps([entry]))
    [announcement] = load_announcements(manifest, tmp_path)
    assert (announcement.number, announcement.effective) == ("2026/40", dt.date(2026, 10, 16))
    notice.write_bytes(b"%PDF changed")
    with pytest.raises(ValueError, match="notice does not match"):
        load_announcements(manifest, tmp_path)
    assert load_announcements(tmp_path / "missing.json", tmp_path) == []


def test_official_2026_39_announcement() -> None:
    [announcement] = load_announcements(PROJECT_ROOT / "data/gazette/ek4a_announcements.json", PROJECT_ROOT)
    assert (announcement.number, announcement.effective) == ("2026/39", dt.date(2026, 10, 9))
    assert (len(announcement.upserts), announcement.removals) == (167, ("A18234",))
    flagyl = next(row for row in announcement.upserts if row["kamu_no"] == "A03037")
    assert flagyl["passivation_date"] == "2026-10-09 00:00:00"
