#!/usr/bin/env python3
"""
Build SUT prose coverage matrix: classify clauses and map to domain implementations.

Usage:
  python scripts/sut/build_sut_coverage.py
  python scripts/sut/build_sut_coverage.py --clauses data/gazette/sut_clauses.parquet --output-dir data/gazette
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from scripts.sut.prose.coverage import write_sut_coverage

_DEFAULT_CLAUSES = _PROJECT_ROOT / "data" / "gazette" / "sut_clauses.parquet"
_DEFAULT_OUTPUT_DIR = _PROJECT_ROOT / "data" / "gazette"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build SUT prose coverage matrix.")
    parser.add_argument(
        "--clauses",
        type=Path,
        default=_DEFAULT_CLAUSES,
        help="Input sut_clauses.parquet from Phase 1",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=_DEFAULT_OUTPUT_DIR,
        help="Directory for coverage parquet outputs",
    )
    return parser


def main() -> None:
    args = _build_parser().parse_args()

    if not args.clauses.exists():
        raise SystemExit(
            f"Clauses file not found: {args.clauses}\n"
            "Run: python scripts/sut/extract_sut_prose.py"
        )

    coverage, rule_summary, section_summary, registry_summary = write_sut_coverage(
        args.clauses,
        args.output_dir,
    )

    print(f"Wrote coverage artifacts -> {args.output_dir}")
    print(f"  sut_clause_coverage.parquet: {len(coverage):,} rows")
    print(f"  sut_coverage_by_rule.parquet: {len(rule_summary):,} rows")
    print(f"  sut_coverage_by_section.parquet: {len(section_summary):,} rows")
    print(f"  sut_registry_coverage.parquet: {len(registry_summary):,} rows")

    print("\nCoverage status (primary):")
    print(coverage["coverage_status"].value_counts().to_string())

    gaps = coverage[coverage["has_algorithmic_gap"]]
    print(f"\nClauses with algorithmic gaps: {len(gaps):,} ({100*len(gaps)/len(coverage):.1f}%)")

    print("\nTop gap categories:")
    print(
        gaps["primary_rule_category"]
        .value_counts()
        .head(10)
        .to_string()
    )

    unmapped_rules = registry_summary[~registry_summary["has_clause_mapping"]]
    if not unmapped_rules.empty:
        print("\nRegistry rules with zero clause matches:")
        for _, row in unmapped_rules.iterrows():
            print(f"  - {row['rule_id']}: {row['description']}")


if __name__ == "__main__":
    main()
