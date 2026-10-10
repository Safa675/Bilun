"""
EK-4A service-date history built from every raw list version.

Each version (ek4a_timeline.py) applies from its footer's RG date until the next
version's RG date. The footer's numbered clauses date its markers:
  - "(*)" in the entry, activation or passivation column means that event happens on
    the clause date, so the date is written into the column;
  - a name ending in "(**)", "(***)" or "(****)" means the row's new values apply from
    the clause date; until then the drug keeps the previous version's values, or is
    absent if it is new;
  - a clause without a date ("yayımı tarihinde") means the publication date, and a
    name-marker date before publication applies from publication.
A marker the footer does not define gives the span status "unrecognized_marker". A
kamu_no that one list gives to two drugs gives both rows "duplicate_kamu_no". A
pre-marker span whose predecessor is not known (oldest version, after a gap, or after a
duplicated kamu_no) has status "unknown_predecessor".

Pinned SGK announcements between consolidated lists (ek4a_announcements.py) are applied on
top: from the effective date, changed drugs get their announced row and removed drugs end.

Outputs (strings, ISO dates, half-open [valid_from, valid_until), null = open):
  ek4a_history.parquet  one row per drug and run of identical values
  ek4a_windows.parquet  the version windows and the gaps no version covers
Entry, activation and passivation dates stay as source text; they are evaluated against
the service date by the runtime reader.
"""

from __future__ import annotations

import datetime as dt
import re
from functools import lru_cache
from pathlib import Path

import pandas as pd

from scripts.sut._common import _safe_str
from scripts.sut.catalogs.ek4a_announcements import Announcement, load_announcements
from scripts.sut.catalogs.ek4a_timeline import ek4a_timeline
from scripts.sut.catalogs.simple_materials import ek4a_records

FIELDS = (
    "kamu_no", "barcode", "drug_name", "old_barcodes", "equivalence_group", "therapeutic_group",
    "entry_date", "activation_date", "passivation_date", "discount_status",
    "discount_tier_1", "discount_tier_2", "discount_tier_3", "discount_tier_4",
    "special_discount", "pharmacist_discount",
)
DATE_COLUMNS = {"entry_date": "giriş", "activation_date": "aktiflenme", "passivation_date": "pasiflenme"}
_CLAUSE_SPLIT = re.compile(r"(?:^|\s)\d\)\s")
_TOKEN = re.compile(r"\((\*{1,4})\)")
_DATE = re.compile(r"(\d{2})[./](\d{2})[./](\d{4})")
_TRAILING_STARS = re.compile(r"\s*(\*+)$")

Rules = dict[str, tuple[dt.date, frozenset[str]]]


def marker_rules(footer: str, published: dt.date) -> Rules:
    """Marker token -> (effective date, columns it may mark), read from the footer clauses."""
    rules: Rules = {}
    for clause in _CLAUSE_SPLIT.split(footer):
        tokens = _TOKEN.findall(clause)
        if not tokens:
            continue
        found = _DATE.search(clause[clause.index("("):])
        if found:
            day, month, year = (int(value) for value in found.groups())
            date = dt.date(year, month, day)
        elif "yayımı tarihinde" in clause:
            date = published
        else:
            raise ValueError(f"EK-4A footer clause has no effective date: {clause!r}")
        for token in tokens:
            if token in rules:
                raise ValueError(f"EK-4A footer defines ({token}) twice")
            if token == "*":
                head = clause[: clause.index("(*)")]
                columns = frozenset(column for column, word in DATE_COLUMNS.items() if word in head)
                if not columns:
                    raise ValueError("EK-4A footer (*) clause names no date column")
            else:
                columns = frozenset({"drug_name"})
            rules[token] = (date, columns)
    return rules


def resolve_markers(record: dict, rules: Rules, published: dt.date) -> tuple[dict, dt.date, str]:
    """Return the row's values with markers applied, the date they apply from, and a status."""
    values = {field: _safe_str(record.get(field)) for field in FIELDS}
    starts, status = published, "ok"
    stars = _TRAILING_STARS.search(values["drug_name"])
    if stars:
        values["drug_name"] = values["drug_name"][: stars.start()]
        rule = rules.get(stars.group(1))
        if rule is None or "drug_name" not in rule[1]:
            status = "unrecognized_marker"
        else:
            starts = max(rule[0], published)
    for column in DATE_COLUMNS:
        if "*" not in values[column]:
            continue
        rule = rules.get("*")
        if values[column] == "*" and rule is not None and column in rule[1]:
            values[column] = rule[0].isoformat()
        else:
            status = "unrecognized_marker"
    return values, starts, status


def _iso(value: dt.date | None) -> str | None:
    return None if value is None else value.isoformat()


def _apply_announcement(spans: list[dict], announcement: Announcement, versions: list) -> list[dict]:
    """Give changed drugs their announced row from the effective date and close removed ones.

    The new values last until the end of the list window holding the effective date; the
    next consolidated list already includes them. A list span of a changed drug that starts
    on or after the effective date in that window is a conflict a reviewer must settle.
    """
    day = announcement.effective
    window = next((v for v in versions if v.valid_from <= day and (v.valid_to is None or day < v.valid_to)), None)
    if window is None:
        raise ValueError(f"EK-4A announcement {announcement.number} takes effect outside every list window")
    end = window.valid_to
    changed = {record["kamu_no"]: record for record in announcement.upserts}
    targets = changed.keys() | set(announcement.removals)
    result = []
    for span in spans:
        if (span["kamu_no"] not in targets or (span["valid_until"] is not None and span["valid_until"] <= day)
                or (end is not None and span["valid_from"] >= end)):
            result.append(span)
        elif span["valid_from"] < day:
            result.append(dict(span, valid_until=day))
        else:
            raise ValueError(f"EK-4A {span['kamu_no']} has a list span from {span['valid_from']} "
                             f"inside announcement {announcement.number}'s window")
    for record in changed.values():
        result.append(dict({field: record[field] for field in FIELDS}, valid_from=day, valid_until=end,
                           status="ok", source=f"announcement {announcement.number}"))
    return result


def ek4a_history(
    raw_root: Path, announcements: list[Announcement] | None = None
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Build (history spans, version windows and gaps) from the raw EK-4A partitions.

    Announcements (default: those pinned in ek4a_announcements.json next to the raw root)
    are applied on top of the list versions.
    """
    versions, gaps = ek4a_timeline(raw_root)
    spans: list[dict] = []
    # kamu_no -> (values, status) at the end of the previous version; None when ambiguous.
    previous: dict[str, tuple[dict, str] | None] = {}
    previous_until: dt.date | None = None
    for version in versions:
        frame = ek4a_records(pd.read_parquet(raw_root / version.parquet_path))
        if frame.empty:
            raise ValueError(f"EK-4A {version.parquet_path} has no drug rows")
        # SGK lists from 2025-03-08 to 2025-07-09 give A19661 to two different drugs.
        duplicated = set(frame.loc[frame["kamu_no"].duplicated(), "kamu_no"])
        rules = marker_rules(version.footer, version.valid_from)
        # The oldest version has no known predecessor either.
        after_gap = previous_until != version.valid_from
        current: dict[str, tuple[dict, str] | None] = {}
        for record in frame.to_dict("records"):
            values, starts, status = resolve_markers(record, rules, version.valid_from)
            kamu_no = values["kamu_no"]
            if kamu_no in duplicated:
                status = "duplicate_kamu_no"
            current[kamu_no] = None if kamu_no in duplicated else (values, status)
            end = version.valid_to
            if starts > version.valid_from:
                head_end = starts if end is None else min(starts, end)
                if after_gap or (kamu_no in previous and previous[kamu_no] is None):
                    spans.append(dict(values, valid_from=version.valid_from, valid_until=head_end,
                                      status="unknown_predecessor", source=_iso(version.valid_from)))
                elif kamu_no in previous:
                    old_values, old_status = previous[kamu_no]
                    spans.append(dict(old_values, valid_from=version.valid_from, valid_until=head_end,
                                      status=old_status, source=_iso(version.valid_from)))
            if end is None or starts < end:
                spans.append(dict(values, valid_from=starts, valid_until=end, status=status,
                                  source=_iso(version.valid_from)))
        previous, previous_until = current, version.valid_to

    applied = announcements if announcements is not None else load_announcements(
        raw_root.parent / "ek4a_announcements.json", raw_root.parents[2])
    for announcement in applied:
        spans = _apply_announcement(spans, announcement, versions)

    # Join contiguous spans with identical values; grouping by value keeps duplicates apart.
    key_fields = (*FIELDS, "status")
    groups: dict[tuple, list[dict]] = {}
    for span in spans:
        groups.setdefault(tuple(span[field] for field in key_fields), []).append(span)
    merged: list[dict] = []
    for group in groups.values():
        group.sort(key=lambda item: item["valid_from"])
        run = dict(group[0])
        for span in group[1:]:
            if run["valid_until"] == span["valid_from"]:
                run["valid_until"] = span["valid_until"]
            else:
                merged.append(run)
                run = dict(span)
        merged.append(run)
    merged.sort(key=lambda item: (item["kamu_no"], item["valid_from"], item["barcode"]))
    history = pd.DataFrame(
        [dict({field: span[field] for field in FIELDS}, valid_from=_iso(span["valid_from"]),
              valid_until=_iso(span["valid_until"]), status=span["status"], source_list=span["source"])
         for span in merged],
        columns=[*FIELDS, "valid_from", "valid_until", "status", "source_list"],
    ).astype("string")
    windows = pd.DataFrame(
        [{"kind": "version", "valid_from": _iso(v.valid_from), "valid_until": _iso(v.valid_to),
          "source": v.parquet_path} for v in versions]
        + [{"kind": "gap", "valid_from": _iso(start), "valid_until": _iso(end), "source": None}
           for start, end in gaps]
        + [{"kind": "announcement", "valid_from": _iso(item.effective), "valid_until": None,
            "source": f"announcement {item.number}"} for item in applied],
        columns=["kind", "valid_from", "valid_until", "source"],
    ).astype("string")
    return history, windows


@lru_cache(maxsize=1)
def _built(raw_root: Path, signature: tuple) -> tuple[pd.DataFrame, pd.DataFrame]:
    return ek4a_history(raw_root)


def _ek4a_outputs(raw_root: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Build once per builder run; the two specs below share the result."""
    files = sorted(raw_root.glob("annex=EK-4A/effective_date=*/*.parquet"))
    files += [path for path in [raw_root.parent / "ek4a_announcements.json"] if path.is_file()]
    signature = tuple((str(path), path.stat().st_size, path.stat().st_mtime_ns) for path in files)
    history, windows = _built(raw_root.resolve(), signature)
    return history.copy(), windows.copy()


def extract_ek4a_history(raw_root: Path) -> pd.DataFrame:
    return _ek4a_outputs(raw_root)[0]


def extract_ek4a_windows(raw_root: Path) -> pd.DataFrame:
    return _ek4a_outputs(raw_root)[1]


SPECS: list[dict] = [
    {
        "annex": "EK-4A",
        "output": "ek4a_history.parquet",
        "source": "raw_timeline",
        "extractor": extract_ek4a_history,
        "label": "EK-4A Service-Date History",
    },
    {
        "annex": "EK-4A",
        "output": "ek4a_windows.parquet",
        "source": "raw_timeline",
        "extractor": extract_ek4a_windows,
        "label": "EK-4A Version Windows",
    },
]
