#!/usr/bin/env python3
"""Sync Gate B artifacts with sut_clauses in-force filter.

Drops ``is_in_force=false`` clause IDs from prose rule ``gate_b_sources``,
manifest ``gate_b_sources`` / ``gate_b_sources_encoded`` lists, and manifest
``encoded_clause_ids`` lists (which feed the coverage ``has_rule_encoding``
flag), then re-runs L1.4 corpus export scripts.

Usage:
  python scripts/sut/sync_gate_b_in_force.py
  python scripts/sut/sync_gate_b_in_force.py --dry-run
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

import polars as pl

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from src.bilun.domain.constants import SUT_CLAUSES_PATH  # noqa: E402

_PROSE_RULES_DIR = _PROJECT_ROOT / "data/gazette/prose_rules"
_MANIFEST_DIR = _PROJECT_ROOT / "data/gazette/prose_manifests"
# Clause-id lists scrubbed of is_in_force=false IDs. The first group feeds the
# coverage has_rule_encoding flag; the tier_* groups partition the manifest
# status set and must be kept in sync with clause_traces.
_CLAUSE_ID_LIST_KEYS = frozenset(
    {
        "gate_b_sources",
        "gate_b_sources_encoded",
        "encoded_clause_ids",
        "tier_a_pending_clause_ids",
        "tier_b_pending_clause_ids",
        "tier_c_deferred_clause_ids",
        "non_actionable_clause_ids",
    }
)
_RULE_ID_CLAUSE_RE = re.compile(r"\.(C\d{6})\.")


def _load_in_force_ids(clauses_path: Path) -> frozenset[str]:
    df = pl.read_parquet(clauses_path)
    if "is_in_force" not in df.columns:
        raise SystemExit(
            f"{clauses_path} missing is_in_force — run extract_sut_prose.py first"
        )
    return frozenset(df.filter(pl.col("is_in_force"))["clause_id"].to_list())


def _remap_clause_id(clauses: pl.DataFrame, clause_id: str, in_force: frozenset[str]) -> str | None:
    if clause_id in in_force:
        return clause_id
    row = clauses.filter(pl.col("clause_id") == clause_id)
    if row.is_empty():
        return None
    section = row["section_id"][0]
    legacy = str(row["text_tr"][0] or "").strip()
    if not legacy:
        return None
    prefix = legacy[:40]
    candidates = clauses.filter(
        pl.col("is_in_force")
        & (pl.col("section_id") == section)
        & pl.col("in_force_text").str.starts_with(prefix[:25])
    )
    if candidates.height == 1:
        return str(candidates["clause_id"][0])
    if candidates.height > 1:
        return str(candidates.sort("paragraph_index")["clause_id"][0])
    # Drug bent lines: match leading "x) drugname" token
    bent = legacy.split(";")[0].strip()[:30]
    if bent:
        loose = clauses.filter(
            pl.col("is_in_force")
            & (pl.col("section_id") == section)
            & pl.col("in_force_text").str.starts_with(bent)
        )
        if loose.height >= 1:
            return str(loose.sort("paragraph_index")["clause_id"][0])
    return None


def _section_chain(section: str) -> list[str]:
    parts: list[str] = []
    current = section.strip()
    while current:
        parts.append(current)
        if "." not in current:
            break
        current = current.rsplit(".", 1)[0]
    return parts


def _infer_sources_from_rule(
    rule: dict[str, Any],
    clauses: pl.DataFrame,
) -> list[str]:
    section = str(rule.get("sut_section") or "")
    drugs = rule.get("drug_names") or []
    if not section:
        return []
    drug = str(drugs[0]).lower() if isinstance(drugs, list) and drugs else ""

    for sec in _section_chain(section):
        if drug:
            cands = clauses.filter(
                pl.col("is_in_force")
                & pl.col("section_id").str.starts_with(sec)
                & pl.col("in_force_text").str.to_lowercase().str.contains(drug)
            )
            if not cands.is_empty():
                return [str(cands.sort("paragraph_index")["clause_id"][0])]

    for sec in _section_chain(section):
        cands = clauses.filter(
            pl.col("is_in_force") & pl.col("section_id").str.starts_with(sec)
        )
        if not cands.is_empty():
            return [str(cands.sort("paragraph_index")["clause_id"][0])]
    return []


def _remap_gate_b_sources(
    sources: list[Any],
    clauses: pl.DataFrame,
    in_force: frozenset[str],
) -> list[str]:
    remapped: list[str] = []
    seen: set[str] = set()
    for raw in sources:
        cid = str(raw)
        target = _remap_clause_id(clauses, cid, in_force)
        if target and target not in seen:
            seen.add(target)
            remapped.append(target)
    return remapped


def _filter_clause_id_list(values: list[Any], in_force: frozenset[str]) -> list[str]:
    return [str(v) for v in values if str(v) in in_force]


def _scrub_gate_b_sources_in_rules(
    rules_dir: Path,
    clauses: pl.DataFrame,
    in_force: frozenset[str],
    *,
    dry_run: bool,
) -> int:
    removed = 0
    for path in sorted(rules_dir.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        changed = False
        for rule in data.get("rules") or []:
            if not isinstance(rule, dict):
                continue
            sources = rule.get("gate_b_sources")
            if not isinstance(sources, list):
                continue
            filtered = _remap_gate_b_sources(sources, clauses, in_force)
            if not filtered:
                rid = str(rule.get("rule_id") or "")
                match = _RULE_ID_CLAUSE_RE.search(rid)
                if match:
                    remapped = _remap_clause_id(clauses, match.group(1), in_force)
                    if remapped:
                        filtered = [remapped]
            if not filtered:
                filtered = _infer_sources_from_rule(rule, clauses)
            if filtered != sources:
                removed += len(sources) - len(filtered)
                rule["gate_b_sources"] = filtered
                changed = True
        if changed and not dry_run:
            path.write_text(
                json.dumps(data, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
    return removed


def _scrub_manifests(manifest_dir: Path, in_force: frozenset[str], *, dry_run: bool) -> int:
    removed = 0
    for path in sorted(manifest_dir.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            continue
        changed = False

        # 1. Filter clause-id lists (all keys that partition the manifest status set).
        for key, value in list(data.items()):
            if key not in _CLAUSE_ID_LIST_KEYS or not isinstance(value, list):
                continue
            filtered = _filter_clause_id_list(value, in_force)
            if filtered != value:
                removed += len(value) - len(filtered)
                data[key] = filtered
                changed = True

        # 2. Filter clause_traces row array (each row has a clause_id).
        traces = data.get("clause_traces")
        if isinstance(traces, list) and traces and isinstance(traces[0], dict):
            kept = [t for t in traces if str(t.get("clause_id")) in in_force]
            if len(kept) != len(traces):
                data["clause_traces"] = kept
                changed = True

        # 3. Re-sync derived count fields so they match the filtered lists.
        for list_key, count_key in _MANIFEST_COUNT_FIELDS.items():
            value = data.get(list_key)
            if isinstance(value, list) and count_key in data:
                data[count_key] = len(value)
                changed = True

        # 4. Re-sync section_clause_total to the in-force trace count. The raw
        #    section total counted struck paragraphs; after filtering, the
        #    authoritative count is len(clause_traces).
        traces = data.get("clause_traces")
        if isinstance(traces, list) and "section_clause_total" in data:
            data["section_clause_total"] = len(traces)
            changed = True

        if changed and not dry_run:
            path.write_text(
                json.dumps(data, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
    return removed


# (count_field) ← len(list_field) pairs to re-sync after filtering.
_MANIFEST_COUNT_FIELDS = {
    "encoded_clause_ids": "encoded_clause_count",
    "tier_a_pending_clause_ids": "tier_a_pending_count",
    "tier_b_pending_clause_ids": "tier_b_pending_count",
    "tier_c_deferred_clause_ids": "tier_c_deferred_count",
}


def main() -> None:
    parser = argparse.ArgumentParser(description="Sync Gate B with in-force clauses")
    parser.add_argument("--clauses", type=Path, default=SUT_CLAUSES_PATH)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    in_force = _load_in_force_ids(args.clauses)
    clauses = pl.read_parquet(args.clauses)
    print(f"in_force clause_ids: {len(in_force):,}")

    removed_rules = _scrub_gate_b_sources_in_rules(
        _PROSE_RULES_DIR, clauses, in_force, dry_run=args.dry_run
    )
    removed_manifests = _scrub_manifests(_MANIFEST_DIR, in_force, dry_run=args.dry_run)
    print(f"gate_b_sources removed from prose rules: {removed_rules}")
    print(f"gate_b_sources removed from manifests: {removed_manifests}")

    if args.dry_run:
        l14 = _PROJECT_ROOT / "data/gazette/prose_corpus/L1.4_material_bundling_prose.csv"
        if l14.is_file():
            before = pl.read_csv(l14).height
            after = pl.read_csv(l14).filter(pl.col("clause_id").is_in(list(in_force))).height
            print(f"L1.4 corpus would be: {before} -> {after} rows")
        return

    subprocess.run(
        [sys.executable, str(_PROJECT_ROOT / "scripts/sut/export_material_bundling_clauses.py")],
        check=True,
        cwd=_PROJECT_ROOT,
    )
    subprocess.run(
        [
            sys.executable,
            str(_PROJECT_ROOT / "scripts/sut/export_material_bundling_corpus_batch2.py"),
        ],
        check=True,
        cwd=_PROJECT_ROOT,
    )


if __name__ == "__main__":
    main()
