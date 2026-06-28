#!/usr/bin/env python3
"""Validate every gate_b_sources clause reference across all prose_rules JSONs.

Cross-checks each cited clause_id against the actual SUT clause corpus
(sut_clauses.parquet). Reports:
  - Dangling references (clause_id not in the corpus)
  - Per-file dangling ratio
  - Worst-offending files

Usage:
    python scripts/sut/validate_gate_b_sources.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import polars as pl

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_RULES_DIR = _PROJECT_ROOT / "data" / "gazette" / "prose_rules"
_CLAUSES_PARQUET = _PROJECT_ROOT / "data" / "gazette" / "sut_clauses.parquet"

# Also check the in-force coverage parquet (may be a subset).
_COVERAGE_PARQUET = _PROJECT_ROOT / "data" / "gazette" / "sut_clause_coverage.parquet"


def _load_clause_ids() -> tuple[frozenset[str], frozenset[str]]:
    """Return (all_clause_ids, in_force_clause_ids) from the parquets."""
    all_ids: set[str] = set()
    if _CLAUSES_PARQUET.exists():
        df = pl.read_parquet(_CLAUSES_PARQUET, columns=["clause_id"])
        all_ids |= {str(c).strip() for c in df["clause_id"].to_list() if c}
    in_force_ids: set[str] = set()
    if _COVERAGE_PARQUET.exists():
        df = pl.read_parquet(_COVERAGE_PARQUET, columns=["clause_id"])
        in_force_ids |= {str(c).strip() for c in df["clause_id"].to_list() if c}
    return frozenset(all_ids), frozenset(in_force_ids)


def _extract_gate_b_sources(rule: dict) -> list[str]:
    """Extract all clause IDs from a rule's gate_b_sources field."""
    gb = rule.get("gate_b_sources")
    if not gb:
        return []
    if isinstance(gb, str):
        return [gb.strip()]
    return [str(g).strip() for g in gb if g]


def main() -> int:
    all_ids, in_force_ids = _load_clause_ids()
    print(f"SUT clause corpus: {len(all_ids)} total clauses")
    print(f"In-force coverage: {len(in_force_ids)} clauses")
    if not all_ids:
        print("ERROR: No clauses loaded from parquet.", file=sys.stderr)
        return 2
    print()

    rule_files = sorted(_RULES_DIR.glob("*.json"))
    # Skip schema files
    rule_files = [f for f in rule_files if "schema" not in f.name and "golden" not in f.name]

    total_rules = 0
    total_refs = 0
    total_dangling = 0
    total_struck = 0
    per_file: list[dict] = []

    for path in rule_files:
        with path.open(encoding="utf-8") as fh:
            data = json.load(fh)

        rules = data.get("rules", data.get("entries", []))
        if not rules:
            continue

        file_rules = 0
        file_refs = 0
        file_dangling: list[tuple[str, str, str]] = []  # (rule_id, clause_id, reason)

        for rule in rules:
            refs = _extract_gate_b_sources(rule)
            if not refs:
                continue
            file_rules += 1
            for ref in refs:
                file_refs += 1
                if ref not in all_ids:
                    file_dangling.append(
                        (rule.get("rule_id", "?"), ref, "NOT IN CORPUS")
                    )
                elif in_force_ids and ref not in in_force_ids:
                    file_dangling.append(
                        (rule.get("rule_id", "?"), ref, "struck/not-in-force")
                    )

        total_rules += file_rules
        total_refs += file_refs
        total_dangling += sum(1 for _, _, r in file_dangling if r == "NOT IN CORPUS")
        total_struck += sum(1 for _, _, r in file_dangling if r == "struck/not-in-force")

        ratio = len(file_dangling) / file_refs * 100 if file_refs else 0
        per_file.append({
            "file": path.name,
            "rules_with_refs": file_rules,
            "total_refs": file_refs,
            "dangling": len(file_dangling),
            "ratio": ratio,
            "details": file_dangling,
        })

    # ── Report ────────────────────────────────────────────────────────────
    print(f"{'File':<45} {'Rules':>6} {'Refs':>6} {'Bad':>6} {'Ratio':>7}")
    print("-" * 75)
    for pf in sorted(per_file, key=lambda x: -x["ratio"]):
        flag = "🔴" if pf["ratio"] > 50 else ("🟡" if pf["ratio"] > 10 else "✅")
        print(
            f"{flag} {pf['file']:<42} {pf['rules_with_refs']:>6} "
            f"{pf['total_refs']:>6} {pf['dangling']:>6} {pf['ratio']:>6.1f}%"
        )

    print("-" * 75)
    print(
        f"{'TOTAL':<46} {total_rules:>6} {total_refs:>6} "
        f"{total_dangling + total_struck:>6} "
        f"{(total_dangling + total_struck) / total_refs * 100 if total_refs else 0:>6.1f}%"
    )
    print(f"  NOT IN CORPUS (fabricated/unknown): {total_dangling}")
    print(f"  struck/not-in-force:               {total_struck}")
    print()

    # ── Detailed dangling refs (top offenders) ────────────────────────────
    print("=== Dangling clause references (not in corpus) — top 30 ===")
    all_dangling = []
    for pf in per_file:
        for rule_id, clause_id, reason in pf["details"]:
            if reason == "NOT IN CORPUS":
                all_dangling.append((pf["file"], rule_id, clause_id))
    for file, rule_id, clause_id in sorted(all_dangling)[:30]:
        print(f"  {file:<35} {rule_id[:45]:<46} {clause_id}")
    if len(all_dangling) > 30:
        print(f"  ... and {len(all_dangling) - 30} more")

    return 0 if total_dangling == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
