#!/usr/bin/env python3
"""Build rule-interaction graph from encoded Gate B manifests (not full clause corpus).

Nodes: union of encoded_clause_ids across prose manifests (~639 clauses).
Edges: same_billing_context (shared primary_rule_id), same_rule_set (shared motor).

Usage:
  python scripts/sut/build_rule_interaction_graph.py
  python scripts/sut/build_rule_interaction_graph.py --output data/gazette/rule_interaction_graph.json
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

import polars as pl

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from scripts.sut.prose.coverage import (  # noqa: E402
    _MANIFEST_DIR,
    _manifest_clause_ids_from_payload,
)

_DEFAULT_OUT = _PROJECT_ROOT / "data" / "gazette" / "rule_interaction_graph.json"
_COVERAGE_PATH = _PROJECT_ROOT / "data" / "gazette" / "sut_clause_coverage.parquet"


def _load_all_encoded_clause_ids() -> dict[str, set[str]]:
    """Map manifest stem → encoded clause id set."""
    by_manifest: dict[str, set[str]] = {}
    if not _MANIFEST_DIR.is_dir():
        return by_manifest
    for path in sorted(_MANIFEST_DIR.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, list):
            ids = frozenset(str(clause_id) for clause_id in payload)
        else:
            ids = _manifest_clause_ids_from_payload(payload)
        if ids:
            by_manifest[path.stem] = set(ids)
    return by_manifest


def build_rule_interaction_graph() -> dict[str, Any]:
    by_manifest = _load_all_encoded_clause_ids()
    manifest_union: set[str] = set()
    for ids in by_manifest.values():
        manifest_union |= ids

    # Prefer coverage parquet as node source of truth (has_rule_encoding flag).
    all_ids: set[str] = set()
    if _COVERAGE_PATH.is_file():
        cov = pl.read_parquet(_COVERAGE_PATH).filter(pl.col("has_rule_encoding") == True)  # noqa: E712
        all_ids = set(cov["clause_id"].cast(str).to_list())
    if not all_ids:
        all_ids = manifest_union

    clause_meta: dict[str, dict[str, Any]] = {}
    if _COVERAGE_PATH.is_file() and all_ids:
        cov = pl.read_parquet(_COVERAGE_PATH).filter(pl.col("clause_id").is_in(list(all_ids)))
        for row in cov.iter_rows(named=True):
            cid = str(row["clause_id"])
            clause_meta[cid] = {
                "primary_rule_id": row.get("primary_rule_id"),
                "coverage_status": row.get("coverage_status"),
                "has_rule_encoding": bool(row.get("has_rule_encoding")),
            }

    nodes: list[dict[str, Any]] = []
    for cid in sorted(all_ids):
        meta = clause_meta.get(cid, {})
        manifests = [name for name, ids in by_manifest.items() if cid in ids]
        nodes.append(
            {
                "id": cid,
                "primary_rule_id": meta.get("primary_rule_id"),
                "coverage_status": meta.get("coverage_status"),
                "manifests": manifests,
            }
        )

    edges: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()

    # same_billing_context: clauses sharing primary_rule_id
    by_rule: dict[str, list[str]] = defaultdict(list)
    for node in nodes:
        rid = node.get("primary_rule_id")
        if rid:
            by_rule[str(rid)].append(node["id"])

    for rule_id, clause_ids in by_rule.items():
        if len(clause_ids) < 2:
            continue
        anchor = clause_ids[0]
        for other in clause_ids[1:]:
            key = ("same_billing_context", anchor, other)
            if key not in seen:
                seen.add(key)
                edges.append(
                    {
                        "source": anchor,
                        "target": other,
                        "type": "same_billing_context",
                        "rule_id": rule_id,
                    }
                )

    # same_rule_set: clauses appearing in the same manifest file
    for manifest, ids in by_manifest.items():
        id_list = sorted(ids)
        if len(id_list) < 2:
            continue
        anchor = id_list[0]
        for other in id_list[1:]:
            key = ("same_rule_set", anchor, other)
            if key not in seen:
                seen.add(key)
                edges.append(
                    {
                        "source": anchor,
                        "target": other,
                        "type": "same_rule_set",
                        "manifest": manifest,
                    }
                )

    return {
        "version": 1,
        "node_count": len(nodes),
        "edge_count": len(edges),
        "manifest_count": len(by_manifest),
        "nodes": nodes,
        "edges": edges,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=_DEFAULT_OUT)
    args = parser.parse_args()

    graph = build_rule_interaction_graph()
    out_path = args.output if args.output.is_absolute() else _PROJECT_ROOT / args.output
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(graph, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {out_path} — {graph['node_count']} nodes, {graph['edge_count']} edges")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
