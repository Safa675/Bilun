#!/usr/bin/env python3
"""Export unencoded algorithmic gaps from sut_clause_coverage.parquet."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

_DEFAULT_COVERAGE = _PROJECT_ROOT / "data" / "gazette" / "sut_clause_coverage.parquet"
_DEFAULT_OUTPUT = _PROJECT_ROOT / "reports" / "algorithmic_gaps_unencoded.csv"

_EXPORT_COLUMNS = [
    "clause_id",
    "section_id",
    "clause_type",
    "deontic_modality",
    "primary_rule_id",
    "coverage_status",
    "has_rule_encoding",
    "text_tr",
    "text_excerpt",
]


def export_gaps(
    coverage_path: Path = _DEFAULT_COVERAGE,
    output_path: Path = _DEFAULT_OUTPUT,
) -> int:
    coverage = pd.read_parquet(coverage_path)
    gaps = coverage[coverage["has_algorithmic_gap"] & ~coverage["has_rule_encoding"]]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    cols = [c for c in _EXPORT_COLUMNS if c in gaps.columns]
    gaps[cols].sort_values(["section_id", "clause_id"]).to_csv(output_path, index=False)
    print(f"wrote {len(gaps)} rows → {output_path}")
    return len(gaps)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Export algorithmic gap inventory CSV.")
    parser.add_argument("--coverage", type=Path, default=_DEFAULT_COVERAGE)
    parser.add_argument("--output", type=Path, default=_DEFAULT_OUTPUT)
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    export_gaps(args.coverage, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
