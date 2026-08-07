"""Migrate remaining encode-eligible C* gate_b_sources cites to clause_key (Track E P3).

The earlier Track A2 migration moved **unique** encode-eligible cites to plain
``clause_coordinate``. The cites left behind are the coordinate **collisions**
(plus non-eligible prose/amendment/structural ids). This script rewrites the
encode-eligible collisions to ``coordinate#content_hash`` (clause_key), which the
Track E resolver disambiguates by content hash. Non-eligible ids (prose /
amendment / structural) are left as C* — dual-read keeps them working and the
clause_key resolver would refuse them under ``encode_eligible_only``.

Usage:
  python -m scripts.sut.prose.migrate_gate_b_sources_to_clause_keys --dry-run
  python -m scripts.sut.prose.migrate_gate_b_sources_to_clause_keys
"""

from __future__ import annotations

import argparse
from pathlib import Path

import polars as pl
import yaml

from scripts.sut.prose.clause_identity import (
    clause_key,
    filter_encode_eligible,
    is_clause_id,
    resolve_gate_b_ref_to_clause_ids,
)

_ROOT = Path(__file__).resolve().parents[3]
_SOURCES = _ROOT / "data" / "gazette" / "prose_rule_sources"
_CLAUSES = _ROOT / "data" / "gazette" / "sut_clauses.parquet"


class _NoAliasDumper(yaml.SafeDumper):
    def ignore_aliases(self, data: object) -> bool:
        return True


def _eligible_id_to_key(frame: pl.DataFrame) -> dict[str, str]:
    """Map encode-eligible clause_id -> clause_key, **lossless only**.

    A cite is migrated only when its clause_key resolves back to exactly that
    one clause_id. Identical-content collisions (same coordinate + same hash
    matching several rows) are left as C* so the precise row pointer is kept
    and encoded_clause_ids stay unchanged.
    """
    eligible = filter_encode_eligible(frame)
    mapping: dict[str, str] = {}
    skipped = 0
    for row in eligible.select(
        ["clause_id", "clause_coordinate", "in_force_text"]
    ).iter_rows(named=True):
        cid = str(row["clause_id"])
        key = clause_key(row["clause_coordinate"], row["in_force_text"])
        try:
            ids = resolve_gate_b_ref_to_clause_ids(
                key, frame, in_force_only=True, encode_eligible_only=True
            )
        except Exception:
            skipped += 1
            continue
        if ids == [cid]:
            mapping[cid] = key
        else:
            skipped += 1
    if skipped:
        print(f"  note: {skipped} encode-eligible ids left as C* (non-lossless key)")
    return mapping


def migrate_yaml_file(
    path: Path, id_to_key: dict[str, str], *, dry_run: bool
) -> tuple[int, int]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    rules = payload.get("rules") or []
    changed = 0
    scanned = 0
    for rule in rules:
        sources = rule.get("gate_b_sources") or []
        new_sources: list[str] = []
        rule_changed = False
        for src in sources:
            scanned += 1
            text = str(src)
            if is_clause_id(text) and text in id_to_key:
                new_sources.append(id_to_key[text])
                rule_changed = True
                changed += 1
            else:
                new_sources.append(text)
        if rule_changed:
            rule["gate_b_sources"] = new_sources
    if changed and not dry_run:
        path.write_text(
            yaml.dump(
                payload,
                Dumper=_NoAliasDumper,
                sort_keys=False,
                allow_unicode=True,
                width=120,
                default_flow_style=False,
            ),
            encoding="utf-8",
        )
    return scanned, changed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--family",
        action="append",
        default=[],
        help="prose_rule_sources/<family> to migrate (repeatable). Default: all.",
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--clauses", type=Path, default=_CLAUSES)
    args = parser.parse_args(argv)

    frame = pl.read_parquet(args.clauses)
    id_to_key = _eligible_id_to_key(frame)
    families = args.family or [p.name for p in _SOURCES.iterdir() if p.is_dir()]

    total_scanned = 0
    total_changed = 0
    for family in families:
        family_dir = _SOURCES / family
        if not family_dir.is_dir():
            print(f"skip missing family: {family}")
            continue
        for path in sorted(family_dir.glob("*.yaml")):
            scanned, changed = migrate_yaml_file(path, id_to_key, dry_run=args.dry_run)
            total_scanned += scanned
            total_changed += changed
            if changed:
                print(
                    f"{'[dry-run] ' if args.dry_run else ''}"
                    f"{path.relative_to(_ROOT)}: {changed}/{scanned}"
                )
    print(
        f"{'dry-run ' if args.dry_run else ''}done: rewrote {total_changed}/{total_scanned} "
        f"cites across {len(families)} families (eligible key map size={len(id_to_key)})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
