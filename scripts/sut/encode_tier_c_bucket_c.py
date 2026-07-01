#!/usr/bin/env python3
"""Mark Tier-C Bucket C clauses as EMR-blocked in manifests (no runtime rule encode)."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from scripts.sut.prose.coverage import _load_gate_b_sources_from_rules_json  # noqa: E402
from scripts.sut.tier_c_manifest_ops import update_manifest_bucket  # noqa: E402

_CANDIDATES_JSON = _REPO / "data/gazette/prose_corpus/L4.2_drug_tier_c_rule_candidates.json"
_RULES_JSON = _REPO / "data/gazette/prose_rules/drug_indication_prose.json"
_REPORT_JSON = _REPO / "reports/tier_c_bucket_c_manifest_report.json"
_CATALOG_JSON = _REPO / "data/gazette/prose_corpus/L4.2_drug_tier_c_emr_blocked_catalog.json"


def collect_bucket_c_clause_ids(
    *,
    candidates_path: Path = _CANDIDATES_JSON,
    rules_path: Path = _RULES_JSON,
    skip_already_encoded: bool = True,
) -> tuple[set[str], list[dict]]:
    payload = json.loads(candidates_path.read_text(encoding="utf-8"))
    bucket_c = [r for r in payload.get("rules") or [] if r.get("encode_bucket") == "C"]
    encoded_in_rules = _load_gate_b_sources_from_rules_json(rules_path) if skip_already_encoded else frozenset()
    ids: set[str] = set()
    catalog: list[dict] = []
    for row in bucket_c:
        cid = str(row["clause_id"])
        if cid in encoded_in_rules:
            continue
        ids.add(cid)
        catalog.append(
            {
                "clause_id": cid,
                "sut_section": row.get("sut_section"),
                "defer_themes": row.get("defer_themes") or [],
                "required_emr_fields": row.get("required_emr_fields")
                or row.get("extraction_signals", {}).get("emr_signal_tokens")
                or row.get("defer_themes"),
                "message_tr": row.get("message_tr"),
                "manifest_status": "emr_blocked",
            }
        )
    return ids, catalog


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    clause_ids, catalog = collect_bucket_c_clause_ids()
    stats = {
        "bucket_c_candidates": len(clause_ids),
        "generated_at": date.today().isoformat(),
    }
    print(json.dumps(stats, indent=2))
    if args.dry_run:
        return 0

    manifest_stats = update_manifest_bucket(
        clause_ids,
        status="emr_blocked",
        note_prefix="bucket_c_emr_blocked",
    )
    _CATALOG_JSON.parent.mkdir(parents=True, exist_ok=True)
    _CATALOG_JSON.write_text(
        json.dumps(
            {
                "catalog_id": "drug_indication_tier_c_emr_blocked",
                "effective_date": date.today().isoformat(),
                "runtime_status": "emr_blocked_catalog",
                "clauses": catalog,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    report = {"stats": stats, "manifest": manifest_stats, "catalog_path": str(_CATALOG_JSON)}
    _REPORT_JSON.parent.mkdir(parents=True, exist_ok=True)
    _REPORT_JSON.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"catalog → {_CATALOG_JSON}, report → {_REPORT_JSON}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
