#!/usr/bin/env python3
"""
Extract structured SUT prose clauses from the consolidated main docx.

Usage:
  python scripts/sut/extract_sut_prose.py
  python scripts/sut/extract_sut_prose.py --docx "raw data/.../17.01.2026-....docx" --output data/gazette/sut_clauses.parquet
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from scripts.sut.prose.extractor import write_sut_clauses_parquet

_REPO_ROOT = _PROJECT_ROOT
_DEFAULT_DOCX = (
    _REPO_ROOT
    / "raw data"
    / "2026.01.17-Değişiklik Tebliği İşlenmiş Güncel 2013 SUT"
    / "17.01.2026-Değişiklik Tebliği İşlenmiş Güncel 2013 SUT.docx"
)
_DEFAULT_OUTPUT = _REPO_ROOT / "data" / "gazette" / "sut_clauses.parquet"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Extract SUT prose clauses to parquet.")
    parser.add_argument(
        "--docx",
        type=Path,
        default=_DEFAULT_DOCX,
        help="Path to consolidated SUT docx",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=_DEFAULT_OUTPUT,
        help="Output parquet path",
    )
    parser.add_argument(
        "--body-start",
        type=int,
        default=None,
        help="Optional paragraph index where body text begins (skip TOC)",
    )
    return parser


def main() -> None:
    args = _build_parser().parse_args()
    docx_path: Path = args.docx
    output_path: Path = args.output

    if not docx_path.exists():
        raise SystemExit(f"Docx not found: {docx_path}")

    frame = write_sut_clauses_parquet(
        docx_path,
        output_path,
        body_start=args.body_start,
    )

    print(f"Wrote {len(frame):,} clauses -> {output_path}")
    if not frame.empty:
        print(f"  sections: {frame['section_id'].nunique(dropna=True):,}")
        print(f"  with annex refs: {(frame['annex_refs'] != '[]').sum():,}")
        print(f"  with deontic markers: {(frame['deontic_markers'] != '[]').sum():,}")
        print(f"  clause types:\n{frame['clause_type'].value_counts().to_string()}")


if __name__ == "__main__":
    main()
