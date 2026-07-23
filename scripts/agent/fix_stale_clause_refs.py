#!/usr/bin/env python3
"""Fix TIER 1 (superseded) stale clause references in prose rule JSONs.

For each superseded clause referenced in a prose rule's gate_b_sources,
this script finds the best replacement clause (current, non-superseded,
in-force) in the same SUT section and updates the gate_b_sources.

The old superseded clause is preserved in a new `superseded_sources` field
for audit traceability, and `verification_status` is set to
`ai_generated_pending_review` per AGENTS.md §4.

Usage:
    python3 scripts/agent/fix_stale_clause_refs.py --dry-run   # preview changes
    python3 scripts/agent/fix_stale_clause_refs.py --apply     # write changes
"""

from __future__ import annotations

import argparse
import glob
import json
import sys
from pathlib import Path

import polars as pl

# IMPORTANT: always reference the main repo's parquet (data outputs are read-only)
PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROSE_RULES_GLOB = PROJECT_ROOT / "data" / "gazette" / "prose_rules" / "*.json"
SUT_CLAUSES_PARQUET = PROJECT_ROOT / "data" / "gazette" / "sut_clauses.parquet"

# Manual overrides for clauses where automated scoring found no good candidate.
# These map to the section heading (stable, non-superseded, in-force).
MANUAL_OVERRIDES: dict[str, str] = {
    "C003563": "C003562",  # 4.2.1.A Leflunomid (1) Mülga -> heading
    "C004929": "C004928",  # 4.2.14.A cytotoxic list (1) partially Mülga -> heading
}


def build_replacement_map(clauses: pl.DataFrame) -> dict[str, str]:
    """Build {old_clause_id: new_clause_id} for all TIER 1 superseded clauses.

    Uses text-overlap scoring within the same section_id to find the best
    non-superseded, in-force replacement. Falls back to section heading.
    """
    superseded = clauses.filter(pl.col("is_superseded_marker") == True)
    sup_ids = set(superseded.get_column("clause_id").to_list())

    replacement_map: dict[str, str] = {}

    for old_cid in sorted(sup_ids):
        if old_cid in MANUAL_OVERRIDES:
            replacement_map[old_cid] = MANUAL_OVERRIDES[old_cid]
            continue

        old_row = clauses.filter(pl.col("clause_id") == old_cid)
        if old_row.height == 0:
            continue
        old = old_row.to_dicts()[0]
        section = old["section_id"]
        old_words = set((old["text_tr"] or "").lower().split())

        # STRICT filter: only in-force, non-superseded candidates.
        # This ensures replacements never become TIER 2 (not-in-force).
        candidates = clauses.filter(
            (pl.col("section_id") == section)
            & (pl.col("is_superseded_marker") == False)
            & (pl.col("is_in_force") == True)
            & (pl.col("clause_id") != old_cid)
        ).to_dicts()

        # Score: text overlap + strong preference for clean (non-struck) clauses.
        # Non-struck gets +3.0 so a clean heading beats a struck content clause.
        best_id = None
        best_score = -1.0
        for c in candidates:
            c_words = set((c["text_tr"] or "").lower().split())
            overlap = float(len(old_words & c_words))
            if not c["had_struck_content"]:
                overlap += 3.0
            if not c["is_heading"]:
                overlap += 0.5
            if overlap > best_score:
                best_score = overlap
                best_id = c["clause_id"]

        if best_id and best_score > 0.0:
            replacement_map[old_cid] = best_id
        elif candidates:
            # Fallback: use the first non-superseded in-force clause
            replacement_map[old_cid] = candidates[0]["clause_id"]

    return replacement_map


def apply_fixes(
    replacement_map: dict[str, str],
    clauses: pl.DataFrame,
    *,
    apply: bool,
) -> tuple[int, int, int]:
    """Apply replacement map to all prose rule JSONs.

    Returns (files_changed, rules_modified, refs_updated).
    """
    sup_ids = set(replacement_map.keys())
    files_changed = 0
    rules_modified = 0
    refs_updated = 0
    changes_log: list[str] = []

    for path in sorted(glob.glob(str(PROSE_RULES_GLOB))):
        raw = Path(path).read_text(encoding="utf-8")
        try:
            doc = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if not isinstance(doc, dict):
            continue
        rsid = doc.get("rule_set_id")
        rules = doc.get("rules")
        if not rsid or not isinstance(rules, list):
            continue

        file_dirty = False
        for rule in rules:
            if not isinstance(rule, dict):
                continue
            sources = rule.get("gate_b_sources")
            if not sources or not isinstance(sources, list):
                continue

            new_sources: list[str] = []
            superseded_sources: list[str] = []
            changed = False

            for cid in sources:
                if cid in sup_ids:
                    new_cid = replacement_map[cid]
                    # Avoid duplicate if replacement already in list
                    if new_cid not in new_sources:
                        new_sources.append(new_cid)
                    if cid not in superseded_sources:
                        superseded_sources.append(cid)
                    changed = True
                    refs_updated += 1
                    changes_log.append(
                        f"  {rsid}/{rule.get('rule_id', '?')}: "
                        f"{cid} -> {new_cid}"
                    )
                else:
                    if cid not in new_sources:
                        new_sources.append(cid)

            if changed:
                rule["gate_b_sources"] = new_sources
                # Preserve old refs for audit trail
                existing_superseded = rule.get("superseded_sources", [])
                for s in superseded_sources:
                    if s not in existing_superseded:
                        existing_superseded.append(s)
                if existing_superseded:
                    rule["superseded_sources"] = existing_superseded
                # Mark as AI-touched per AGENTS.md §4
                rule["verification_status"] = "ai_generated_pending_review"
                rules_modified += 1
                file_dirty = True

        if file_dirty and apply:
            output = json.dumps(doc, indent=2, ensure_ascii=False)
            Path(path).write_text(output + "\n", encoding="utf-8")
            files_changed += 1
        elif file_dirty:
            files_changed += 1

    if changes_log:
        print(f"\nChanges ({refs_updated} refs across {rules_modified} rules):")
        for line in changes_log[:30]:
            print(line)
        if len(changes_log) > 30:
            print(f"  ... and {len(changes_log) - 30} more")

    return files_changed, rules_modified, refs_updated


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Fix TIER 1 stale clause references in prose rule JSONs."
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--dry-run", action="store_true", help="Preview changes only")
    group.add_argument("--apply", action="store_true", help="Write changes to files")
    args = parser.parse_args()

    if not SUT_CLAUSES_PARQUET.exists():
        print(f"ERROR: {SUT_CLAUSES_PARQUET} not found", file=sys.stderr)
        return 1

    clauses = pl.read_parquet(SUT_CLAUSES_PARQUET)
    replacement_map = build_replacement_map(clauses)
    print(f"Built replacement map: {len(replacement_map)} superseded clause IDs")

    # Validate: all replacements must be non-superseded
    for old_cid, new_cid in replacement_map.items():
        new_row = clauses.filter(pl.col("clause_id") == new_cid)
        if new_row.height == 0:
            print(f"ERROR: replacement {new_cid} for {old_cid} not in parquet",
                  file=sys.stderr)
            return 1
        new = new_row.to_dicts()[0]
        if new["is_superseded_marker"]:
            print(f"WARNING: replacement {new_cid} for {old_cid} is ALSO superseded!",
                  file=sys.stderr)

    fc, rm, ru = apply_fixes(replacement_map, clauses, apply=args.apply)

    mode = "APPLIED" if args.apply else "DRY RUN"
    print(f"\n{mode}: {fc} files, {rm} rules, {ru} refs updated")
    if args.apply:
        print("Run stale_clause_refs.py to verify the reduction.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
