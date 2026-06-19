#!/usr/bin/env python3
"""Export §3.1–3.2 material bundling Gate B clauses (Phase 1)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from scripts.sut.prose.material_bundling_gate_b import (  # noqa: E402
    build_review_sample,
    enrich_gate_b_dataframe,
    gate_b_summary,
    load_candidate_clauses,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="L1.4 Gate B clause export + dedup")
    parser.add_argument(
        "--clauses",
        type=Path,
        default=_PROJECT_ROOT / "data/gazette/sut_clauses.parquet",
    )
    parser.add_argument(
        "--prose-json",
        type=Path,
        default=_PROJECT_ROOT / "data/gazette/prose_rules/material_bundling_prose.json",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=_PROJECT_ROOT / "data/gazette/prose_corpus/L1.4_material_bundling_prose.csv",
    )
    parser.add_argument(
        "--review-out",
        type=Path,
        default=_PROJECT_ROOT / "data/gazette/prose_corpus/L1.4_material_bundling_prose_review_sample.csv",
    )
    parser.add_argument(
        "--summary-out",
        type=Path,
        default=_PROJECT_ROOT / "data/gazette/prose_corpus/L1.4_material_bundling_gate_b_summary.json",
    )
    parser.add_argument("--review-fraction", type=float, default=0.1)
    parser.add_argument("--review-min", type=int, default=5)
    args = parser.parse_args()

    hit = load_candidate_clauses(args.clauses)
    enriched = enrich_gate_b_dataframe(hit, prose_json_path=args.prose_json)
    summary = gate_b_summary(enriched)
    review = build_review_sample(
        enriched, fraction=args.review_fraction, min_rows=args.review_min
    )

    args.out.parent.mkdir(parents=True, exist_ok=True)
    enriched.write_csv(args.out)
    review.write_csv(args.review_out)
    args.summary_out.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    print(f"Wrote {summary['total_rows']} rows to {args.out}")
    print(f"  p1_encode={summary['p1_encode']} skip_annex={summary['skip_annex_duplicate']}")
    print(f"Wrote {len(review)} review rows to {args.review_out}")
    print(f"Summary: {args.summary_out}")


if __name__ == "__main__":
    main()
