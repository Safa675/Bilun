"""
EK-4A changes SGK announces between consolidated lists.

"Bedeli Ödenecek İlaçlar Listesinde Yapılan Düzenlemeler Hakkında Duyuru" comes almost
weekly. Its one-page PDF gives the effective date, and its workbook has one sheet per kind
of change. Every row of the added, edited, activated, passivated and band sheets is the
drug's complete row as it applies from that date. The removal sheet names drugs that leave
the list. data/gazette/ek4a_announcements.json pins each announcement: number, page,
effective date as read from the PDF, and the SHA-256 of both files under raw data/.

A sheet this module does not know, an unexpected header, a data row without a kamu_no or
one drug with two different rows makes loading fail, so a format change is never guessed.
Only announcements published after the consolidated list they change are applied; an older
one is normally already folded into that list (see ek4a_history._apply_announcement).
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

UPSERT_SHEETS = frozenset({
    "4A EKLENENLER", "4A DÜZENLENENLER", "4A AKTİFLENENLER", "4A PASİFLENENLER",
    "4A BANT HESABINA DAHİL EDİLENLE", "4A BANT HESABINDAN ÇIKARILANLAR",
})
REMOVAL_SHEET = "4A ÇIKARILAN İLAÇLAR"
HEADER = (
    "Kamu No", "Güncel Barkod", "İlaç Adı", "Eski Barkod-1", "Eski Barkod-2", "Eşdeğer İlaç Grubu",
    "Terapötik Referans Grubu", "Listeye Giriş Tarihi", "Aktiflenme Tarihi", "Pasiflenme Tarihi",
    "Uygulanan İndirim Oranlarına Esas Durumu",
)
# Columns 11-14 are the four price bands (their labels carry the TL limits).
TAIL = ("Özel İskonto", "Eczacı İskonto Oranı")


@dataclass(frozen=True)
class Announcement:
    number: str
    effective: dt.date
    upserts: tuple[dict[str, str], ...]
    removals: tuple[str, ...]
    published: dt.date | None = None


def _label(value: object) -> str:
    return " ".join(_safe_str(value).split())


def _cell(value: object) -> str:
    """Write a workbook value the way the consolidated raw lists store it."""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    if isinstance(value, (dt.datetime, pd.Timestamp)):
        return str(pd.Timestamp(value))
    return _safe_str(value)


def _rows(frame: pd.DataFrame, sheet: str) -> pd.DataFrame:
    """The data rows below a sheet's "Kamu No" header row."""
    first = frame.iloc[:, 0].map(_label)
    header_rows = first.index[first == "Kamu No"]
    if len(header_rows) != 1:
        raise ValueError(f"EK-4A announcement sheet {sheet!r} needs exactly one 'Kamu No' header")
    header = [_label(value) for value in frame.loc[header_rows[0]]]
    if sheet != REMOVAL_SHEET and (tuple(header[:11]) != HEADER or tuple(header[15:17]) != TAIL):
        raise ValueError(f"EK-4A announcement sheet {sheet!r} has an unexpected header: {header[:17]}")
    body = frame.loc[header_rows[0] + 1:].dropna(how="all")
    if body.iloc[:, 0].map(_label).eq("").any():
        raise ValueError(f"EK-4A announcement sheet {sheet!r} has a data row without kamu_no")
    return body


def read_workbook(path: Path) -> tuple[tuple[dict[str, str], ...], tuple[str, ...]]:
    """(complete rows from the change sheets, kamu_no values removed from the list)."""
    upserts: dict[str, dict[str, str]] = {}
    removals: set[str] = set()
    for sheet, frame in pd.read_excel(path, sheet_name=None, header=None, dtype=object).items():
        if sheet not in UPSERT_SHEETS and sheet != REMOVAL_SHEET:
            raise ValueError(f"Unknown EK-4A announcement sheet {sheet!r}")
        body = _rows(frame, sheet)
        if sheet == REMOVAL_SHEET:
            removals.update(body.iloc[:, 0].map(_label))
            continue
        for row in body.itertuples(index=False):
            cells = [_cell(value) for value in row]
            record = {
                "kamu_no": cells[0], "barcode": cells[1], "drug_name": cells[2],
                "old_barcodes": "\n".join(code for code in cells[3:5] if code),
                "equivalence_group": cells[5], "therapeutic_group": cells[6],
                "entry_date": cells[7], "activation_date": cells[8], "passivation_date": cells[9],
                "discount_status": cells[10],
                "discount_tier_1": cells[11], "discount_tier_2": cells[12],
                "discount_tier_3": cells[13], "discount_tier_4": cells[14],
                "special_discount": cells[15], "pharmacist_discount": cells[16],
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
        if not re.fullmatch(r"\d{4}/\d{1,3}", entry["number"]):
            raise ValueError(f"Invalid EK-4A announcement number {entry['number']!r}")
        for key in ("workbook", "notice"):
            if _sha256(project_root / entry[key]) != entry[f"{key}_sha256"]:
                raise ValueError(f"EK-4A announcement {entry['number']} {key} does not match its SHA-256")
        upserts, removals = read_workbook(project_root / entry["workbook"])
        announcements.append(Announcement(entry["number"], dt.date.fromisoformat(entry["effective"]),
                                          upserts, removals, dt.date.fromisoformat(entry["published"])))
    return sorted(announcements, key=lambda item: (item.effective, item.number))
