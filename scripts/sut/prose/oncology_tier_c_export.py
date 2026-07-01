#!/usr/bin/env python3
"""Classify §4.2.14.C Tier-C deferred clauses into encode buckets (L4.2 Phase C).

Thin wrapper around shared tier_c_classify + manifest-scoped export.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

import polars as pl

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from scripts.sut.prose.tier_c_classify import classify_bucket

_DEFAULT_CLAUSES = _PROJECT_ROOT / "data/gazette/sut_clauses.parquet"
_DEFAULT_MANIFEST = (
    _PROJECT_ROOT / "data/gazette/prose_manifests/L4.2_drug_indication_4.2.14.C_manifest.json"
)
_DEFAULT_OUT_CSV = _PROJECT_ROOT / "data/gazette/prose_corpus/L4.2_oncology_tier_c_classification.csv"
_DEFAULT_OUT_SUMMARY = _PROJECT_ROOT / "data/gazette/prose_corpus/L4.2_oncology_tier_c_summary.json"


def build_classification(
    clauses_path: Path, manifest_path: Path
) -> tuple[pl.DataFrame, dict]:
    with manifest_path.open(encoding="utf-8") as f:
        manifest = json.load(f)
    tier_c_ids = set(manifest.get("tier_c_deferred_clause_ids") or [])

    clauses = pl.read_parquet(clauses_path)
    tc = clauses.filter(pl.col("clause_id").is_in(list(tier_c_ids))).sort("paragraph_index")

    rows: list[dict] = []
    for record in tc.iter_rows(named=True):
        bucket = classify_bucket(record)
        text = str(record.get("text_tr") or "")
        rows.append(
            {
                "clause_id": record.get("clause_id"),
                "section_id": record.get("section_id"),
                "bucket": bucket,
                "is_heading": record.get("is_heading"),
                "is_amendment": record.get("is_amendment"),
                "is_superseded": record.get("is_superseded_marker"),
                "char_count": record.get("char_count"),
                "text_excerpt": text[:300],
            }
        )

    df = pl.DataFrame(rows)
    bucket_counts = Counter(r["bucket"] for r in rows)
    summary = {
        "tier_c_total": len(tier_c_ids),
        "classified_rows": len(rows),
        "bucket_counts": dict(sorted(bucket_counts.items())),
        "note": (
            "§4.2.14.C Tier-C classification. A=encodable now, B=model-ext, C=EMR-blocked, "
            "D=non-actionable. Uses scripts.sut.prose.tier_c_classify."
        ),
    }
    return df, summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--clauses", type=Path, default=_DEFAULT_CLAUSES)
    parser.add_argument("--manifest", type=Path, default=_DEFAULT_MANIFEST)
    parser.add_argument("--out-csv", type=Path, default=_DEFAULT_OUT_CSV)
    parser.add_argument("--out-summary", type=Path, default=_DEFAULT_OUT_SUMMARY)
    args = parser.parse_args()

    df, summary = build_classification(args.clauses, args.manifest)
    args.out_csv.parent.mkdir(parents=True, exist_ok=True)
    df.write_csv(args.out_csv)
    args.out_summary.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    print(f"Wrote {df.height} classified clauses to {args.out_csv}")
    print(f"Bucket counts: {summary['bucket_counts']}")


if __name__ == "__main__":
    main()
