#!/usr/bin/env python3
"""Mark Tier-C Bucket D pathway fragments as non-actionable in manifests."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from scripts.sut.tier_c_manifest_ops import update_manifest_bucket  # noqa: E402

_CANDIDATES_JSON = _REPO / "data/gazette/prose_corpus/L4.2_drug_tier_c_rule_candidates.json"
_INVENTORY_CSV = _REPO / "data/gazette/prose_corpus/L4.2_drug_tier_c_rule_extraction.csv"
_REPORT_JSON = _REPO / "reports/tier_c_bucket_d_manifest_report.json"


def collect_bucket_d_clause_ids(
    *,
    candidates_path: Path = _CANDIDATES_JSON,
    inventory_path: Path = _INVENTORY_CSV,
) -> set[str]:
    """Collect Bucket D pathway fragment clause IDs from rule candidates only.

    ``inventory_path`` is accepted for API compatibility but intentionally
    unused: Bucket D sourcing is candidate-driven (``encode_bucket`` /
    ``pathway_fragment`` flags), not inventory CSV rows.
    """
    _ = inventory_path
    payload = json.loads(candidates_path.read_text(encoding="utf-8"))
    return {
        str(r["clause_id"])
        for r in payload.get("rules") or []
        if r.get("encode_bucket") == "D" or r.get("pathway_fragment")
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    clause_ids = collect_bucket_d_clause_ids()
    stats = {"bucket_d_fragments": len(clause_ids), "generated_at": date.today().isoformat()}
    print(json.dumps(stats, indent=2))
    if args.dry_run:
        return 0

    manifest_stats = update_manifest_bucket(
        clause_ids,
        status="non_actionable",
        note_prefix="bucket_d_non_actionable",
    )
    report = {"stats": stats, "manifest": manifest_stats}
    _REPORT_JSON.parent.mkdir(parents=True, exist_ok=True)
    _REPORT_JSON.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"report → {_REPORT_JSON}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
