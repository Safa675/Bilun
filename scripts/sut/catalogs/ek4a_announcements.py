"""
EK-4A changes SGK announces between consolidated lists.

"Bedeli Ödenecek İlaçlar Listesinde Yapılan Düzenlemeler Hakkında Duyuru" comes almost
weekly. Its one-page PDF gives the effective date, and its workbook has one sheet per kind
of change. Every row of the added, edited, activated, passivated and band sheets is the
drug's complete row as it applies from that date. The removal sheet names drugs that leave
the list. data/gazette/ek4a_announcements.json pins each announcement: number, page,
effective date as read from the PDF, the SHA-256 of both files under raw data/, and the
consolidated list that already includes it (`folded_into_list`, null while none does).
A list does not always include every announcement published before it: the 2026-10-02 list
includes 2026/34 to 2026/37 but not the extraordinary decision of 2026-09-25 or 2026/38.

A row can carry its own date: a "*" after a drug name, or a "*" in a date cell, means the
date a note row of the same sheet gives ("NOT: Yanında * işareti bulunan ilaçlar için
yürürlük tarihi 29.08.2026", or "* ... yayım tarihini takip eden ilk iş günü ...", the
announcement's effective date).

A sheet or header this module does not know, a row that is neither a drug nor a note, a "*"
without a note, or one drug with two different rows makes loading fail, so a format change
is never guessed.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from scripts.sut._common import _safe_str

# Every sheet name SGK has used, and what it holds. A new name stops loading until reviewed.
SHEETS = {
    "4A EKLENENLER": "upsert", "Ek-4A Eklenen": "upsert", "4A DÜZENLENENLER": "upsert",
    "4A AKTİFLENENLER": "upsert", "4A PASİFLENENLER": "upsert", "4A PASIFLENEN İLAÇLAR": "upsert",
    "4A BANT HESABINA DAHİL EDİLENLE": "upsert", "4A BANT HESABINDAN ÇIKARILANLAR": "upsert",
    "4A ÇIKARILAN İLAÇLAR": "remove", "4A ÇIKARILANLAR": "remove",
    "4H EKLENENLER": "other_annex",  # EK-4/H rows in 2026/35; not part of EK-4A
}
# Accepted header labels (columns 0-10, then 15-16); columns 11-14 are the four price bands.
HEADERS = (
    (("Kamu No", "Güncel Barkod", "İlaç Adı", "Eski Barkod-1", "Eski Barkod-2", "Eşdeğer İlaç Grubu",
      "Terapötik Referans Grubu", "Listeye Giriş Tarihi", "Aktiflenme Tarihi", "Pasiflenme Tarihi",
      "Uygulanan İndirim Oranlarına Esas Durumu"), ("Özel İskonto", "Eczacı İskonto Oranı")),
    # Older labels, same columns (2026/37 passivation sheet).
    (("Kamu No", "Güncel Barkod", "Ürün Adı", "Eski Barkod-1", "Eski Barkod-2", "Eşdeğer (Benzer) Ürün Grubu",
      "Referans Fiyat Grubu", "Listeye Giriş Tarihi", "Aktiflenme Tarihi", "Pasiflenme Tarihi",
      "Orijinal / Jenerik / Yirmi Yıllık"), ("Özel İskonto", "Eczacı İndirim Oranı")),
)
_KAMU_NO = re.compile(r"A\d{5}")
_NOTE_DATE = re.compile(r"yürürlük tarihi (\d{2})\.(\d{2})\.(\d{4})")
_TRAILING_STAR = re.compile(r"\s*\*$")
DATE_CELLS = (7, 8, 9)  # entry, activation, passivation


@dataclass(frozen=True)
class Announcement:
    number: str
    effective: dt.date
    upserts: tuple[dict[str, str], ...]  # each row carries its own "effective" ISO date
    removals: tuple[str, ...]
    folded_into: dt.date | None = None  # RG date of the first list that includes it


def _label(value: object) -> str:
    return " ".join(_safe_str(value).split())


def _cell(value: object) -> str:
    """Write a workbook value the way the consolidated raw lists store it."""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    if isinstance(value, (dt.datetime, pd.Timestamp)):
        return str(pd.Timestamp(value))
    return _safe_str(value)


def _note_date(text: str, effective: dt.date) -> dt.date | None:
    """The date a note row gives to "*" rows, or None if the note is not about "*"."""
    if "*" not in text:
        return None
    found = _NOTE_DATE.search(text)
    if found:
        day, month, year = (int(value) for value in found.groups())
        return dt.date(year, month, day)
    if "yayım tarihini takip eden ilk iş günü" in text:
        return effective
    raise ValueError(f"EK-4A announcement note gives '*' no date: {text!r}")


def _sheet_rows(frame: pd.DataFrame, sheet: str, effective: dt.date) -> tuple[list[list[str]], dt.date | None]:
    """(drug rows as cell texts, the "*" date from the sheet's note rows) below its header."""
    first = frame.iloc[:, 0].map(_label)
    header_rows = first.index[first == "Kamu No"]
    if len(header_rows) != 1:
        raise ValueError(f"EK-4A announcement sheet {sheet!r} needs exactly one 'Kamu No' header")
    header = [_label(value) for value in frame.loc[header_rows[0]]]
    if SHEETS[sheet] == "upsert" and (tuple(header[:11]), tuple(header[15:17])) not in HEADERS:
        raise ValueError(f"EK-4A announcement sheet {sheet!r} has an unexpected header: {header[:17]}")
    rows, star = [], None
    for row in frame.loc[header_rows[0] + 1:].itertuples(index=False):
        cells = [_cell(value) for value in row]
        filled = [cell for cell in cells if cell]
        if not filled:
            continue
        if _KAMU_NO.fullmatch(cells[0]):
            rows.append(cells)
        elif len(filled) == 1 and filled[0].startswith(("NOT", "*")):
            star = _note_date(filled[0], effective) or star
        else:
            raise ValueError(f"EK-4A announcement sheet {sheet!r} has a row that is neither a drug nor a note")
    return rows, star


def read_workbook(path: Path, effective: dt.date) -> tuple[tuple[dict[str, str], ...], tuple[str, ...]]:
    """(complete rows from the change sheets, kamu_no values removed from the list)."""
    upserts: dict[str, dict[str, str]] = {}
    removals: set[str] = set()
    for sheet, frame in pd.read_excel(path, sheet_name=None, header=None, dtype=object).items():
        if sheet not in SHEETS:
            raise ValueError(f"Unknown EK-4A announcement sheet {sheet!r}")
        if SHEETS[sheet] == "other_annex":
            continue
        rows, star = _sheet_rows(frame, sheet, effective)
        if SHEETS[sheet] == "remove":
            removals.update(cells[0] for cells in rows)
            continue
        for cells in rows:
            starts = effective
            if _TRAILING_STAR.search(cells[2]) or any(cells[index] == "*" for index in DATE_CELLS):
                if star is None:
                    raise ValueError(f"EK-4A announcement row {cells[0]} has a '*' but its sheet no note")
                cells[2] = _TRAILING_STAR.sub("", cells[2])
                for index in DATE_CELLS:
                    if cells[index] == "*":
                        cells[index] = f"{star.isoformat()} 00:00:00"
                starts = star
            record = {
                "kamu_no": cells[0], "barcode": cells[1], "drug_name": cells[2],
                "old_barcodes": "\n".join(code for code in cells[3:5] if code),
                "equivalence_group": cells[5], "therapeutic_group": cells[6],
                "entry_date": cells[7], "activation_date": cells[8], "passivation_date": cells[9],
                "discount_status": cells[10],
                "discount_tier_1": cells[11], "discount_tier_2": cells[12],
                "discount_tier_3": cells[13], "discount_tier_4": cells[14],
                "special_discount": cells[15], "pharmacist_discount": cells[16],
                "effective": starts.isoformat(),
            }
            if upserts.setdefault(record["kamu_no"], record) != record:
                raise ValueError(f"EK-4A announcement gives {record['kamu_no']} two different rows")
    if removals & set(upserts):
        raise ValueError(f"EK-4A announcement both changes and removes {sorted(removals & set(upserts))}")
    return tuple(upserts.values()), tuple(sorted(removals))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_announcements(manifest: Path, project_root: Path) -> list[Announcement]:
    """Pinned announcements, oldest effective date first; [] when there is no manifest."""
    if not manifest.is_file():
        return []
    announcements = []
    for entry in json.loads(manifest.read_text(encoding="utf-8")):
        if not re.fullmatch(r"(?:\d{4}/\d{1,3}|olağanüstü \d{4}/\d)", entry["number"]):
            raise ValueError(f"Invalid EK-4A announcement number {entry['number']!r}")
        for key in ("workbook", "notice"):
            if _sha256(project_root / entry[key]) != entry[f"{key}_sha256"]:
                raise ValueError(f"EK-4A announcement {entry['number']} {key} does not match its SHA-256")
        effective = dt.date.fromisoformat(entry["effective"])
        upserts, removals = read_workbook(project_root / entry["workbook"], effective)
        folded = entry.get("folded_into_list")
        announcements.append(Announcement(entry["number"], effective, upserts, removals,
                                          dt.date.fromisoformat(folded) if folded else None))
    return sorted(announcements, key=lambda item: (item.effective, item.number))
