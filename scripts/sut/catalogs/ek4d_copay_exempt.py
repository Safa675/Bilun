#!/usr/bin/env python3
"""Build curated EK-4/D copay-exempt drug list from the SUT .doc annex."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import unicodedata
from pathlib import Path
from typing import Any

import pandas as pd

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

DEFAULT_DOC = (
    _PROJECT_ROOT
    / "raw data"
    / "2026.01.17-Değişiklik Tebliği İşlenmiş Güncel 2013 SUT"
    / "EK-4 LİSTELERİ"
    / "EK-4D HASTA KATILIM PAYINDAN MUAF İLAÇLAR LİSTESİ.doc"
)
DEFAULT_OUT_DIR = _PROJECT_ROOT / "data" / "gazette" / "curated"

_TOP_SECTION_RE = re.compile(
    r"^(\d{1,2})\.\s+([A-ZÇĞİÖŞÜ][^\d].*)$",
    re.UNICODE,
)
_ICD_RANGE_RE = re.compile(
    r"\(?\s*([A-Z][0-9]{2}(?:\.[0-9]+)?)\s*-\s*([A-Z][0-9]{2}(?:\.[0-9]+)?)\s*\)?",
    re.UNICODE,
)
_ICD_SINGLE_RE = re.compile(
    r"\(([A-Z][0-9]{2}(?:\.[0-9]+)?)\)",
    re.UNICODE,
)
_ICD_LINE_RE = re.compile(
    r"^([A-Z][0-9]{2}(?:\.[0-9]+)?)\b",
    re.UNICODE,
)
_NUMBERED_DRUG_RE = re.compile(
    r"^\d+(?:\.\d+)+\.?\s+(.+)$",
    re.UNICODE,
)
_CATEGORY_RE = re.compile(
    r"^\d+\.\d+\.?\s+(.+)$",
    re.UNICODE,
)


def _normalize_drug_name(raw: str) -> str:
    text = str(raw or "").strip()
    text = re.sub(r"\*+", "", text).strip()
    text = re.sub(r"\s+", " ", text)
    folded = unicodedata.normalize("NFKD", text.casefold())
    return "".join(ch for ch in folded if not unicodedata.combining(ch))


def _extract_icd_ranges(header: str) -> list[dict[str, str]]:
    ranges: list[dict[str, str]] = []
    for start, end in _ICD_RANGE_RE.findall(header):
        ranges.append({"start": start.upper(), "end": end.upper()})
    for code in _ICD_SINGLE_RE.findall(header):
        code = code.upper()
        if not any(r["start"] == code and r["end"] == code for r in ranges):
            ranges.append({"start": code, "end": code})
    return ranges


def doc_to_text(doc_path: Path) -> str:
    out_dir = doc_path.parent / ".ek4d_txt_cache"
    out_dir.mkdir(parents=True, exist_ok=True)
    txt_path = out_dir / f"{doc_path.stem}.txt"
    if not txt_path.exists() or txt_path.stat().st_mtime < doc_path.stat().st_mtime:
        subprocess.run(
            [
                "libreoffice",
                "--headless",
                "--convert-to",
                "txt:Text",
                "--outdir",
                str(out_dir),
                str(doc_path),
            ],
            check=True,
            capture_output=True,
            timeout=300,
        )
    return txt_path.read_text(encoding="utf-8", errors="replace")


def parse_ek4d_text(text: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    sections: list[dict[str, Any]] = []
    entries: list[dict[str, Any]] = []
    current_section: int | None = None
    current_title = ""

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        top = _TOP_SECTION_RE.match(line)
        if top:
            section_id = int(top.group(1))
            title = top.group(2).strip()
            current_section = section_id
            current_title = title
            sections.append(
                {
                    "section_id": section_id,
                    "title_tr": title,
                    "icd_ranges_json": json.dumps(
                        _extract_icd_ranges(title), ensure_ascii=False
                    ),
                }
            )
            continue

        if current_section is None:
            continue

        icd_line = _ICD_LINE_RE.match(line)
        if icd_line and "\t" in line:
            code = icd_line.group(1).upper()
            entries.append(
                {
                    "section_id": current_section,
                    "entry_type": "icd10_code",
                    "icd10_code": code,
                    "drug_name_tr": "",
                    "drug_name_normalized": "",
                    "category_broad": False,
                }
            )
            continue

        numbered = _NUMBERED_DRUG_RE.match(line)
        if numbered:
            drug_raw = numbered.group(1).strip()
            if len(drug_raw) < 2:
                continue
            if _ICD_LINE_RE.match(drug_raw):
                continue
            entries.append(
                {
                    "section_id": current_section,
                    "entry_type": "drug_name",
                    "icd10_code": "",
                    "drug_name_tr": drug_raw,
                    "drug_name_normalized": _normalize_drug_name(drug_raw),
                    "category_broad": False,
                }
            )
            continue

        category = _CATEGORY_RE.match(line)
        if category:
            label = category.group(1).strip()
            broad = label.rstrip().endswith("*")
            entries.append(
                {
                    "section_id": current_section,
                    "entry_type": "drug_category",
                    "icd10_code": "",
                    "drug_name_tr": label,
                    "drug_name_normalized": _normalize_drug_name(label),
                    "category_broad": broad,
                }
            )

    sections_df = pd.DataFrame(sections).drop_duplicates(subset=["section_id"])
    entries_df = pd.DataFrame(entries)
    if not entries_df.empty:
        entries_df = entries_df.drop_duplicates(
            subset=["section_id", "entry_type", "icd10_code", "drug_name_normalized"]
        )
    return sections_df, entries_df


def build_curated(
    doc_path: Path,
    out_dir: Path,
) -> tuple[Path, Path]:
    text = doc_to_text(doc_path)
    sections_df, entries_df = parse_ek4d_text(text)
    out_dir.mkdir(parents=True, exist_ok=True)
    sections_path = out_dir / "ek4d_sections.parquet"
    entries_path = out_dir / "ek4d_copay_exempt_entries.parquet"
    sections_df.to_parquet(sections_path, index=False)
    entries_df.to_parquet(entries_path, index=False)
    return sections_path, entries_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Build EK-4/D curated copay exempt tables")
    parser.add_argument("--doc", type=Path, default=DEFAULT_DOC)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    args = parser.parse_args()

    if not args.doc.is_file():
        print(f"EK-4/D source not found: {args.doc}", file=sys.stderr)
        return 1

    sections_path, entries_path = build_curated(args.doc, args.out_dir)
    sections = pd.read_parquet(sections_path)
    entries = pd.read_parquet(entries_path)
    print(f"sections: {len(sections)} -> {sections_path.name}")
    print(f"entries: {len(entries)} -> {entries_path.name}")
    if not entries.empty:
        print(entries["entry_type"].value_counts().to_string())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
