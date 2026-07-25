"""Migrate unique C*/F* gate_b_sources cites to clause_coordinate (Track A2).

Only rewrites refs whose clause_id maps to an **encode-eligible** coordinate that
is unique in sut_clauses.parquet. Ambiguous / missing / non-eligible ids are left
as C* (correct — dual-read keeps them).

Usage:
  python -m scripts.sut.prose.migrate_gate_b_sources_to_coordinates --dry-run \\
      --family definitions_2_6
  python -m scripts.sut.prose.migrate_gate_b_sources_to_coordinates \\
      --family definitions_2_6
"""

from __future__ import annotations

import argparse
from pathlib import Path

import polars as pl
import yaml

from scripts.sut.prose.clause_identity import filter_encode_eligible, is_clause_id

_ROOT = Path(__file__).resolve().parents[3]
_SOURCES = _ROOT / "data" / "gazette" / "prose_rule_sources"
_CLAUSES = _ROOT / "data" / "gazette" / "sut_clauses.parquet"


class _NoAliasDumper(yaml.SafeDumper):
    def ignore_aliases(self, data: object) -> bool:
        return True


def _unique_id_to_coordinate(frame: pl.DataFrame) -> dict[str, str]:
    eligible = filter_encode_eligible(frame)
    counts = eligible.group_by("clause_coordinate").len()
    unique = set(counts.filter(pl.col("len") == 1)["clause_coordinate"].to_list())
    mapping: dict[str, str] = {}
    for row in eligible.select(["clause_id", "clause_coordinate"]).iter_rows(named=True):
        coord = row["clause_coordinate"]
        if coord in unique:
            mapping[str(row["clause_id"])] = str(coord)
    return mapping


def migrate_yaml_file(path: Path, id_to_coord: dict[str, str], *, dry_run: bool) -> tuple[int, int]:
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
            if is_clause_id(text) and text in id_to_coord:
                new_sources.append(id_to_coord[text])
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
    id_to_coord = _unique_id_to_coordinate(frame)
    families = args.family or [p.name for p in _SOURCES.iterdir() if p.is_dir()]

    total_scanned = 0
    total_changed = 0
    for family in families:
        family_dir = _SOURCES / family
        if not family_dir.is_dir():
            print(f"skip missing family: {family}")
            continue
        for path in sorted(family_dir.glob("*.yaml")):
            scanned, changed = migrate_yaml_file(path, id_to_coord, dry_run=args.dry_run)
            total_scanned += scanned
            total_changed += changed
            if changed:
                print(f"{'[dry-run] ' if args.dry_run else ''}{path.relative_to(_ROOT)}: {changed}/{scanned}")
    print(
        f"{'dry-run ' if args.dry_run else ''}done: rewrote {total_changed}/{total_scanned} "
        f"cites across {len(families)} families "
        f"(unique-coord map size={len(id_to_coord)})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
