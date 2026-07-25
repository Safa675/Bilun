"""Backfill clause_coordinate onto deferral_table.yaml entries (Track E).

Joins each entry's opaque ``clause_id`` to ``sut_clauses.parquet`` and writes
``clause_coordinate`` when missing. Keeps ``clause_id`` as the remappable join
key (collision-safe). Does not delete or reorder existing authored fields beyond
inserting ``clause_coordinate`` immediately after ``clause_id``.

Usage:
  python -m scripts.sut.prose.backfill_deferral_coordinates --dry-run
  python -m scripts.sut.prose.backfill_deferral_coordinates
"""

from __future__ import annotations

import argparse
from pathlib import Path

import polars as pl
import yaml

_ROOT = Path(__file__).resolve().parents[3]
_DEFERRAL = _ROOT / "data" / "gazette" / "prose_rules" / "deferral_table.yaml"
_CLAUSES = _ROOT / "data" / "gazette" / "sut_clauses.parquet"


class _NoAliasDumper(yaml.SafeDumper):
    def ignore_aliases(self, data: object) -> bool:
        return True


def _id_to_coordinate(frame: pl.DataFrame) -> dict[str, str]:
    """Prefer in-force coordinate; fall back to any row for that clause_id."""
    mapping: dict[str, str] = {}
    if "is_in_force" in frame.columns:
        forced = frame.filter(pl.col("is_in_force") == True)  # noqa: E712
        for row in forced.select(["clause_id", "clause_coordinate"]).iter_rows(named=True):
            coord = row.get("clause_coordinate")
            if coord:
                mapping[str(row["clause_id"])] = str(coord)
    for row in frame.select(["clause_id", "clause_coordinate"]).iter_rows(named=True):
        cid = str(row["clause_id"])
        coord = row.get("clause_coordinate")
        if cid not in mapping and coord:
            mapping[cid] = str(coord)
    return mapping


def backfill_entries(
    entries: list[dict],
    id_to_coord: dict[str, str],
) -> tuple[list[dict], int, int]:
    filled = 0
    missing = 0
    out: list[dict] = []
    for entry in entries:
        cid = str(entry.get("clause_id") or "").strip()
        existing = str(entry.get("clause_coordinate") or "").strip()
        coord = existing or id_to_coord.get(cid) or ""
        if not existing and coord:
            filled += 1
        elif not coord:
            missing += 1
        # Rebuild with coordinate immediately after clause_id for readability.
        rebuilt: dict = {}
        if cid:
            rebuilt["clause_id"] = cid
        if coord:
            rebuilt["clause_coordinate"] = coord
        for key, value in entry.items():
            if key in {"clause_id", "clause_coordinate"}:
                continue
            rebuilt[key] = value
        out.append(rebuilt)
    return out, filled, missing


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--deferral", type=Path, default=_DEFERRAL)
    parser.add_argument("--clauses", type=Path, default=_CLAUSES)
    args = parser.parse_args(argv)

    payload = yaml.safe_load(args.deferral.read_text(encoding="utf-8")) or {}
    entries = list(payload.get("entries") or [])
    frame = pl.read_parquet(args.clauses, columns=["clause_id", "clause_coordinate", "is_in_force"])
    id_to_coord = _id_to_coordinate(frame)
    new_entries, filled, missing = backfill_entries(entries, id_to_coord)
    print(
        f"{'dry-run ' if args.dry_run else ''}"
        f"deferral backfill: filled={filled} already_had="
        f"{len(entries) - filled - missing} still_missing={missing} total={len(entries)}"
    )
    if args.dry_run or filled == 0:
        return 0 if missing == 0 else 1

    payload["entries"] = new_entries
    args.deferral.write_text(
        yaml.dump(
            payload,
            Dumper=_NoAliasDumper,
            sort_keys=False,
            allow_unicode=True,
            width=100,
            default_flow_style=False,
        ),
        encoding="utf-8",
    )
    return 0 if missing == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
